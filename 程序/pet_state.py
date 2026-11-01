"""10 阶段工作流状态机：一切判据来自文件与事件，不经过 LLM。

- 阶段枚举与页面序号一一对应（见 pet_bus.STAGES），不另建状态源。
- 每阶段状态：pending / running / success / failed / retrying / skipped。
- 进度 = 已完成阶段 + 当前阶段的确定性计数（缺计数时不编数字）；ETA 用计数速率算，时钟可注入。
- 每次变化落盘 工作流任务/宠物/阶段状态.json（原子替换），启动时恢复。
"""
import time
from pathlib import Path
import stage_layout
from agent.core import save
from pet_bus import STAGES, STAGE_NAMES, STAGE_EVENTS, read_json

PENDING, RUNNING, SUCCESS, FAILED, RETRYING, SKIPPED = ('pending', 'running', 'success', 'failed', 'retrying', 'skipped')
SETTLED = (SUCCESS, SKIPPED)
PAGE_OF = {stage: index for index, stage in enumerate(STAGES)}
STATE_PATH = (stage_layout.WORKFLOW_DIR, '宠物', '阶段状态.json')


def state_path(project):
    return Path(project).joinpath(*STATE_PATH)


class Machine:
    """阶段状态机。clock 注入让 ETA 用例不依赖真实等待。"""

    def __init__(self, project, clock=time.monotonic, persist=True):
        self.project = Path(project)
        self.clock = clock
        self.persist = persist
        self.path = state_path(self.project)
        self.stages = {stage: {'state': PENDING, 'reason': '', 'attempts': 0, 'detail': None} for stage in STAGES}
        self.elapsed = {stage: 0.0 for stage in STAGES}
        self.rates = {}
        self.samples = {}
        self.started = {}
        self.units = {stage: 0 for stage in STAGES}        # 各阶段累计产出单位（镜头数／资产数）
        self.run_units = {stage: 0 for stage in STAGES}    # 本轮已见的最大计数，收尾时才并入 units

    # ── 状态迁移 ────────────────────────────────────────────────────────────
    def start(self, stage):
        self._check(stage)
        self.started[stage] = self.clock()
        self.run_units[stage] = 0
        self.stages[stage].update(state=RUNNING, reason='')
        return self

    def detail(self, stage, done, total):
        """记录阶段内确定性子进度（镜头数/资产数），同时采样速率用于 ETA。"""
        self._check(stage)
        self.stages[stage]['detail'] = {'done': int(done), 'total': int(total)}
        self.run_units[stage] = max(self.run_units.get(stage, 0), int(done))
        self._sample(stage, int(done))
        return self

    def complete(self, stage, reason=''):
        self._check(stage)
        self._accumulate(stage)
        self.stages[stage].update(state=SUCCESS, reason=reason, detail=None)
        return self

    def fail(self, stage, error=''):
        self._check(stage)
        self._accumulate(stage)
        self.stages[stage].update(state=FAILED, reason=str(error), attempts=self.stages[stage]['attempts'] + 1)
        return self

    def retry(self, stage, attempt=None, delay=None):
        self._check(stage)
        entry = self.stages[stage]
        entry.update(state=RETRYING, attempts=entry['attempts'] + 1 if attempt is None else int(attempt))
        if delay is not None:
            entry['reason'] = '第 ' + str(entry['attempts']) + ' 次重试，' + str(round(float(delay), 1)) + ' 秒后'
        return self

    def skip(self, stage, reason=''):
        self._check(stage)
        self.stages[stage].update(state=SKIPPED, reason=reason, detail=None)
        return self

    def apply(self, item, persist=False):
        """按事件推进状态机；返回是否发生了变化（调用方决定要不要落盘）。"""
        kind = (item or {}).get('kind')
        if kind not in STAGE_EVENTS:
            return False
        stage = item.get('stage')
        entry = self.stages.get(stage)
        if entry is None:
            return False
        before = (entry['state'], entry['attempts'], entry['reason'])
        if kind == 'stage.started':
            self.start(stage)
        elif kind == 'stage.completed':
            self.complete(stage, item.get('detail') or '')
        elif kind == 'stage.failed':
            self.fail(stage, item.get('error') or '')
        else:
            self.retry(stage, item.get('attempt'), item.get('delay'))
        changed = before != (self.stages[stage]['state'], self.stages[stage]['attempts'], self.stages[stage]['reason'])
        if changed and persist:
            self.save()
        return changed

    def subscribe(self, bus):
        """订阅总线上全部阶段事件（其余事件由父 Agent 处理）。"""
        def listener(item):
            self.apply(item, persist=self.persist)
        return bus.subscribe('*', listener)

    # ── 查询 ────────────────────────────────────────────────────────────────
    def current(self):
        for stage in STAGES:
            if self.stages[stage]['state'] not in SETTLED:
                return stage
        return None

    def next_after(self, stage):
        """阶段顺序里紧邻的下一个阶段（下游踢一脚用）。"""
        if stage not in PAGE_OF:
            raise ValueError('未登记的制作阶段：' + str(stage))
        index = PAGE_OF[stage] + 1
        return STAGES[index] if index < len(STAGES) else None

    def settled(self):
        return [stage for stage in STAGES if self.stages[stage]['state'] in SETTLED]

    def dwell(self):
        """各阶段累计停留秒数：只算真正在跑的时间，重启后从恢复时刻接着计。"""
        return {stage: round(self.elapsed.get(stage, 0.0), 1) for stage in STAGES}

    def units_of(self, stage):
        return int(self.units.get(stage, 0) or 0)

    def per_unit(self, stage):
        """平均每个产出单位耗时（秒）；没有产出单位时返回 None——不编数字。"""
        count = self.units_of(stage)
        span = self.elapsed.get(stage, 0.0)
        if count <= 0 or span <= 0:
            return None
        return round(span / count, 1)

    def per_unit_all(self):
        """有产出单位的阶段 → 平均耗时（秒／单位）；没有产出的阶段一个都不写。"""
        result = {}
        for stage in STAGES:
            rate = self.per_unit(stage)
            if rate is not None:
                result[stage] = rate
        return result

    def slowest(self, limit=3):
        """停留最久的几个阶段，按阶段顺序破平；只列有停留时间的。"""
        rows = sorted(((seconds, stage) for stage, seconds in self.elapsed.items() if seconds > 0),
                      key=lambda item: (-item[0], PAGE_OF[item[1]]))
        return [(stage, round(seconds, 1)) for seconds, stage in rows[:max(0, int(limit))]]

    def progress(self):
        """确定性进度：已完成阶段 + 当前阶段的计数比（没有计数就不编数字）。"""
        done = len(self.settled())
        stage = self.current()
        ratio = None
        if stage:
            entry = self.stages[stage]
            if entry['detail'] and entry['detail'].get('total'):
                ratio = min(1.0, entry['detail']['done'] / entry['detail']['total'])
        percent = round(100.0 * (done + (ratio or 0.0)) / len(STAGES), 1)
        return {'percent': percent, 'stage': stage, 'stage_name': STAGE_NAMES.get(stage, '') if stage else '',
                'done_stages': done, 'total_stages': len(STAGES), 'ratio': ratio,
                'detail': self.stages[stage]['detail'] if stage else None, 'eta_seconds': self.eta()}

    def eta(self):
        """当前阶段剩余时间 + 其余阶段按已完成阶段均值估算；信息不足时返回 None。"""
        stage = self.current()
        if stage is None:
            return 0.0
        entry = self.stages[stage]
        eta = None
        if entry['detail'] and entry['detail'].get('total') and self.rates.get(stage):
            remaining = max(0, entry['detail']['total'] - entry['detail']['done'])
            eta = remaining / self.rates[stage]
        spans = [self.elapsed[name] for name in STAGES if self.stages[name]['state'] == SUCCESS and self.elapsed.get(name)]
        if len(spans) < 2:
            return None if eta is None else round(eta, 1)
        rest = len(STAGES) - PAGE_OF[stage] - 1
        average = sum(spans) / len(spans) * rest
        return round((eta or 0.0) + average, 1)

    def summary(self):
        """一句话进度，供气泡与状态栏用（纯模板，不经 LLM）。"""
        state = self.progress()
        if state['stage'] is None:
            return '全部 ' + str(len(STAGES)) + ' 个阶段已完成'
        text = str(state['done_stages']) + '/' + str(len(STAGES)) + ' 阶段完成 · 当前：' + state['stage_name']
        if state['detail']:
            text += '（' + str(state['detail']['done']) + '/' + str(state['detail']['total']) + '）'
        return text

    # ── 落盘 ────────────────────────────────────────────────────────────────
    def snapshot(self):
        return {'updated_at': time.time(),
                'stages': {stage: dict(self.stages[stage]) for stage in STAGES},
                'elapsed': dict(self.elapsed),
                'units': dict(self.units), 'run_units': dict(self.run_units)}

    def save(self):
        if not self.persist:
            return None
        save(self.path, self.snapshot())
        return self.path

    def load(self):
        """恢复上次快照；文件损坏时保持初始状态（宁可从「未知」重新观测，也不猜）。"""
        data = read_json(self.path)
        if not isinstance(data, dict):
            return self
        for stage, saved in (data.get('stages') or {}).items():
            entry = self.stages.get(stage)
            if entry is None or not isinstance(saved, dict):
                continue
            entry['state'] = saved.get('state') if saved.get('state') in (PENDING, RUNNING, SUCCESS, FAILED, RETRYING, SKIPPED) else PENDING
            entry['reason'] = str(saved.get('reason') or '')
            entry['attempts'] = int(saved.get('attempts') or 0)
        for stage, seconds in (data.get('elapsed') or {}).items():
            if stage in self.elapsed:
                try:
                    self.elapsed[stage] = float(seconds)
                except (TypeError, ValueError):
                    continue
        for key, target in (('units', self.units), ('run_units', self.run_units)):
            for stage, count in (data.get(key) or {}).items():
                if stage in target:
                    try:
                        target[stage] = max(0, int(count))
                    except (TypeError, ValueError):
                        continue
        # 快照里只有状态没有计时器：恢复出来的「正在跑」阶段必须重新起表，
        # 否则重启之后这一段停留永远不会增长（第 9 期修）。
        for stage in STAGES:
            if self.stages[stage]['state'] == RUNNING and self.started.get(stage) is None:
                self.started[stage] = self.clock()
        return self

    # ── 内部 ────────────────────────────────────────────────────────────────
    def _check(self, stage):
        if stage not in self.stages:
            raise ValueError('未登记的制作阶段：' + str(stage))

    def _accumulate(self, stage):
        # 重复的 stage.completed／stage.failed 不能被算两次：已收尾的阶段直接返回。
        if self.stages[stage]['state'] in SETTLED:
            return
        started = self.started.get(stage)
        if started is not None:
            self.elapsed[stage] = self.elapsed.get(stage, 0.0) + max(0.0, self.clock() - started)
            self.started[stage] = None
        self.units[stage] = self.units.get(stage, 0) + int(self.run_units.get(stage, 0))
        self.run_units[stage] = 0

    def _sample(self, stage, done):
        now = self.clock()
        previous = self.samples.get(stage)
        self.samples[stage] = (done, now)
        if previous is None:
            return
        span = now - previous[1]
        grew = done - previous[0]
        if span <= 0 or grew <= 0:
            return
        fresh = grew / span
        old = self.rates.get(stage)
        self.rates[stage] = fresh if old is None else old * 0.7 + fresh * 0.3
