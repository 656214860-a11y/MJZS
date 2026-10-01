# -*- coding: utf-8 -*-
"""第 63 期：11 个阶段子 Agent 的启动逻辑（并行配置 ＋ 全局并发控制 ＋ 阶段间门禁 ＋ 统一日志）。

附件「全部阶段子Agent启动逻辑优化命令」要的是：每个阶段说清「怎么起子 Agent」——并行单元、
并行度、批内串行、并发上限、重试策略；三虎按这份配置发号；阶段之间加门禁；全局并发不超过 8；
每次启动与结束都记进 logs/。

这份表是**唯一出处**：编排器（pet_agent.Agent）按它发号、按它重试；任务书（workflow_tasks）按它
写「怎么并行」；页面（stage_flow／stage_models）按它显示与拦截；检查脚本按它核对。谁都不另写一套。

三条判定口径（照 app 一直的规矩来）：

1. 并行只给「生成类」阶段（分镜、资产、首帧、预演、视频、配音），校验／编排类一律单 Agent（并行度 1）；
2. 门禁只拦**上游真的做了却没做全**的情况。上游压根没开始时不拦——从第 47 期起就是「用户想先做
   哪一步就做哪一步」，门禁不该把空项目锁死；
3. 并发上限是硬上限（全局 8，单阶段按表），挡下来的活儿排队降速，直接丢掉。
"""
import json
import time
from datetime import datetime
from pathlib import Path

# ── 一、并行单元与并行配置表（附件「各阶段并行配置速查表」一个字都不改） ────────────
NONE = 'none'
SCENE = 'scene'
ASSET = 'asset'
SHOT = 'shot'
BATCH = 'batch'
TRACK = 'track'
CHECK = 'check'
UNIT_NAMES = {NONE: '无（整段串行）', SCENE: '场景', ASSET: '资产（角色／场景／道具）', SHOT: '镜头',
              BATCH: '批次', TRACK: '音轨（角色／场景）', CHECK: '检查项'}
# 重试用尽之后怎么办：block＝中断这一步并报错；manual＝标记「待您处理」继续往下；
# report＝把每一条问题连同修复建议写进报告。
ON_BLOCK = 'block'
ON_MANUAL = 'manual'
ON_REPORT = 'report'
ON_EXHAUST = {ON_BLOCK: '重试仍失败就中断这一步并报错', ON_MANUAL: '重试仍失败就标记「待您处理」',
              ON_REPORT: '重试仍失败就连同修复建议写进报告'}
GLOBAL_LIMIT = 8                      # 全局最多同时跑 8 个子 Agent
POLL_SECONDS = 0.01                   # 等并发号时看一次的时间（很短，别拖住界面）
WAIT_SECONDS = 30.0                   # 同一资源撞车时最多等这么久，等不到照样往下走

CONFIG = {
    'script': {'unit': NONE, 'min': 1, 'max': 1, 'serial': False, 'limit': 1,
               'retry': {'attempts': 2, 'backoff': 'fixed', 'on_exhaust': ON_BLOCK},
               'why': '故事理解→角色提取→场景提取→道具提取是一条依赖链，后一步读前一步的产出'},
    'script_structure': {'unit': NONE, 'min': 1, 'max': 1, 'serial': False, 'limit': 1,
                         'retry': {'attempts': 2, 'backoff': 'fixed', 'on_exhaust': ON_BLOCK},
                         'why': '剧本结构需要通读剧本原稿，再统一整理成可供分镜读取的正稿'},
    'storyboard': {'unit': SCENE, 'min': 2, 'max': 3, 'serial': True, 'limit': 3,
                   'retry': {'attempts': 2, 'backoff': 'fixed', 'on_exhaust': ON_BLOCK},
                   'why': '一个场景一个 Agent；同一场景内的镜头必须串行，免得动作接不上'},
    'assets': {'unit': ASSET, 'min': 3, 'max': 5, 'serial': True, 'limit': 5,
               'retry': {'attempts': 2, 'backoff': 'fixed', 'on_exhaust': ON_BLOCK},
               'why': '一项资产一个 Agent；资产内部（正典板→状态变体→锚点→参考职责）必须串行'},
    'continuity': {'unit': NONE, 'min': 1, 'max': 1, 'serial': False, 'limit': 1,
                   'retry': {'attempts': 2, 'backoff': 'fixed', 'on_exhaust': ON_BLOCK},
                   'why': '要读完整分镜与资产才能判冲突，必须全局视角'},
    'final': {'unit': NONE, 'min': 1, 'max': 1, 'serial': False, 'limit': 1,
              'retry': {'attempts': 2, 'backoff': 'fixed', 'on_exhaust': ON_BLOCK},
              'why': '批次划分是全局算法，边界处的三元组要前后镜头一起看'},
    'keyframe': {'unit': SHOT, 'min': 4, 'max': 6, 'serial': False, 'limit': 6,
                 'retry': {'attempts': 2, 'backoff': 'fixed', 'on_exhaust': ON_MANUAL},
                 'why': '每个镜头的首帧互不依赖，按镜头并行最快'},
    'previs': {'unit': BATCH, 'min': 2, 'max': 3, 'serial': True, 'limit': 3,
               'retry': {'attempts': 2, 'backoff': 'fixed', 'on_exhaust': ON_MANUAL},
               'why': '一个批次一个 Agent；同批次内的空间连续性要求镜头按顺序做'},
    'video': {'unit': BATCH, 'min': 2, 'max': 3, 'serial': True, 'limit': 3,
              'retry': {'attempts': 2, 'backoff': 'exp', 'on_exhaust': ON_MANUAL},
              'rate_limit': True,
              'why': '一个批次一个 Agent；同批次内镜头串行，跨批次可并行'},
    'audio': {'unit': TRACK, 'min': 3, 'max': 5, 'serial': True, 'limit': 5,
              'retry': {'attempts': 2, 'backoff': 'fixed', 'on_exhaust': ON_MANUAL},
              'why': '一条角色轨一个 Agent；同一角色的台词串行，音色才一致'},
    'edit': {'unit': NONE, 'min': 1, 'max': 1, 'serial': False, 'limit': 1,
             'retry': {'attempts': 2, 'backoff': 'fixed', 'on_exhaust': ON_BLOCK},
             'why': '时间线拼接是全局操作，视频轨、音频轨、字幕轨要按时间码对齐'},
    'delivery': {'unit': CHECK, 'min': 2, 'max': 4, 'serial': False, 'limit': 4,
                 'retry': {'attempts': 2, 'backoff': 'fixed', 'on_exhaust': ON_REPORT},
                 'why': '画面／音频／格式三类检查彼此独立，可以一起跑，最后汇总一份报告'},
}
DEFAULT_RETRY = {'attempts': 2, 'backoff': 'fixed', 'on_exhaust': ON_BLOCK}


def stages():
    """有并行配置的阶段（就是状态机那 11 步，顺序一致）。"""
    return tuple(CONFIG)


def config(stage):
    """某个阶段的配置（没登记的阶段按「单 Agent、不并行」算，不抛异常）。"""
    row = CONFIG.get(str(stage or ''))
    if row is None:
        return {'unit': NONE, 'min': 1, 'max': 1, 'serial': False, 'limit': 1,
                'retry': dict(DEFAULT_RETRY), 'why': '未登记的阶段按单 Agent 串行处理'}
    return dict(row, retry=dict(row.get('retry') or DEFAULT_RETRY))


def unit(stage):
    return config(stage)['unit']


def unit_name(stage):
    return UNIT_NAMES.get(unit(stage), str(unit(stage)))


def degree(stage):
    """并行度区间 (下限, 上限)。"""
    row = config(stage)
    return (row['min'], row['max'])


def concurrency_limit(stage):
    return int(config(stage)['limit'])


def serial_within(stage):
    return bool(config(stage)['serial'])


def retry_policy(stage):
    return config(stage)['retry']


def retry_attempts(stage):
    return int(retry_policy(stage).get('attempts') or 0)


def on_exhaust(stage):
    return str(retry_policy(stage).get('on_exhaust') or ON_BLOCK)


def rate_limited(stage):
    """这一步要不要处理接口限流（只有视频生成：Seedance 返回限流时降速排队）。"""
    return bool(config(stage).get('rate_limit'))


def label(stage):
    from pet_bus import STAGE_NAMES
    return str(STAGE_NAMES.get(str(stage or ''), stage or ''))


def degree_text(stage):
    low, high = degree(stage)
    return '%d' % low if low == high else '%d-%d' % (low, high)


def degree_label(stage):
    """一行并行说明（弹窗／页面用）：「场景 2-3 路」；单 Agent 阶段写「无（串行）」。"""
    row = config(stage)
    if row['unit'] == NONE:
        return '无（串行）'
    return '%s %s 路' % (UNIT_NAMES[row['unit']].split('（')[0], degree_text(stage))


def unit_label(stage):
    """并行单元的人话名（去掉括号里的补充，页面一行写不下）。"""
    return UNIT_NAMES[config(stage)['unit']].split('（')[0]


def rows():
    """各阶段并行配置速查表（阶段、并行单元、并行度、批内串行、并发上限、重试）。"""
    out = []
    for stage in stages():
        row = config(stage)
        retry = row['retry']
        policy = '%d 次后%s' % (retry.get('attempts'), ON_EXHAUST.get(retry.get('on_exhaust'), '中断'))
        if row.get('rate_limit'):
            policy += '；限流降速排队'
        out.append((label(stage), UNIT_NAMES[row['unit']], degree_text(stage),
                    '是' if row['serial'] else '—', row['limit'], policy, row['why']))
    return tuple(out)


def table_text():
    """速查表的纯文本版（写进 README／维护记录，人工核对用）。"""
    head = ('阶段', '并行单元', '并行度', '批内串行', '并发上限', '重试策略')
    lines = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    for row in rows():
        lines.append('| ' + ' | '.join(str(value) for value in row[:6]) + ' |')
    return '\n'.join(lines) + '\n'


def brief_lines(stage):
    """任务书里那几句「怎么并行」（附件任务2.1～2.11 的应有逻辑，逐阶段写成人话）。"""
    row = config(stage)
    name = label(stage)
    if row['unit'] == NONE:
        return ('本步只有 1 个执行者，不要开并行子任务：%s。' % row['why'],
                '整段按顺序做完再汇报，中途不要另开一路去做同一件事。')
    lines = ['本步按「%s」并行，最多同时 %s 路（上限 %d 路）：每个%s一个执行者。'
             % (UNIT_NAMES[row['unit']], degree_text(stage), row['limit'], UNIT_NAMES[row['unit']].split('（')[0]),
             '同一条里必须串行（做完一个再做下一个），不同条之间才可以并行。' if row['serial']
             else '各单元之间互不依赖，可以并行推进。']
    if stage == 'storyboard':
        lines.append('生成每个镜头时立刻核对三元组（scene_id＋character_ids＋costume_id）与前一个镜头一致，'
                     '并写入 batch_id；资产已锁定时，锚点从资产清单逐字引用。')
        lines.append('各场景做完后按剧本顺序拼接成一份分镜 JSON，并核对跨场景衔接（上一场结束状态＝下一场开始状态）。')
        lines.append('同一集只输出一份分镜 JSON，发现已存在就跳过并说明，不生成副本、不换文件名重写。')
    if stage == 'assets':
        lines.append('每项资产内部按顺序做：正典板（转盘图）→ 状态变体 → 锚点字符串 → 参考职责声明。')
        lines.append('转盘图手上不持道具，所有面板同背景色、同光照方向；生成 4 个版本，预筛到 2 个候选等用户点一下。')
    if stage == 'keyframe':
        lines.append('首帧从资产清单逐字读取 character_anchor，禁止自由描述长相与服装；场景按 scene 参考图。')
    if stage == 'previs':
        lines.append('同批次内的镜头禁止并行，必须按镜头顺序逐条生成，保证空间连续性。')
    if stage == 'video':
        lines.append('视频提示词只写动作、镜头运动与物理交互，不写长相、服装、场景描述。')
        lines.append('单批次失败重试 %d 次，仍失败标记「待您处理」；接口返回限流就降速排队，不要硬冲。'
                     % retry_attempts(stage))
    if stage == 'audio':
        lines.append('同一角色的所有台词串行生成，并引用同一个音色 ID；字幕按场景分轨，同一场景内串行。')
    if stage == 'delivery':
        lines.append('画面、音频、格式三类检查各一个执行者，并行跑；全部做完后由 1 个汇总执行者出一份报告，'
                     '任一项不通过都要写清具体问题与修复建议。')
    lines.append('失败重试：最多 %d 次，仍失败就%s。'
                 % (retry_attempts(stage), ON_EXHAUST.get(on_exhaust(stage), '中断并报错').replace('重试仍失败就', '')))
    return tuple(lines)


def brief_text(stage):
    """任务书用的那几行拼成一段。"""
    return '\n'.join(brief_lines(stage))


def brief_block(stage):
    """任务书里那一段（带标题，直接拼在任务描述后面）：本步怎么起子 Agent。"""
    return '\n【本步怎么并行（照这个来）】\n' + brief_text(stage) + '\n'


def pseudocode():
    """编排器怎么用这份配置（交付物 4 的伪代码，给人看）。"""
    return ('POST /stage/run {stage}:\n'
            '  cfg = CONFIG[stage]                       # 并行单元／并行度／批内串行／并发上限／重试\n'
            '  gate = GATES[stage]                       # 上游产出不全就挡回去（见 gate()）\n'
            '  if not gate.ok and gate.upstream_started: return 409 gate.reject\n'
            '  if not governor.acquire(stage, resource): return 202 "已排队降速"\n'
            '  log(stage, task, "start")\n'
            '  run units with at most cfg.limit in flight, serial inside a unit\n'
            '  on failure: retry cfg.retry.attempts times, then cfg.retry.on_exhaust\n'
            '  log(stage, task, "ok" | "failed")\n'
            '  governor.release(ticket)\n')


# ── 二、全局并发控制器（附件任务3.3） ──────────────────────────────────────────
class Governor:
    """全局并发控制器：全局 ≤8、单阶段 ≤该阶段上限、同一资源串行（撞上就降速排队）。

    只发号与记账，不碰界面也不起线程：真正的线程仍由各阶段自己的管线开。``clock`` 可注入，
    自检里放进假时钟就不用 sleep。
    """

    def __init__(self, limit=GLOBAL_LIMIT, clock=time.time):
        self.limit = int(limit)
        self.clock = clock
        self.tickets = []                     # 正在跑的号（列表有序：先到先服务）
        self.slowed = []                      # 因并发上限／资源冲突被挡回去的记录
        self.counter = 0

    def running(self):
        return len(self.tickets)

    def stage_running(self, stage):
        return sum(1 for ticket in self.tickets if ticket['stage'] == str(stage or ''))

    def resources(self):
        return tuple(ticket['resource'] for ticket in self.tickets if ticket['resource'])

    def limit_of(self, stage):
        return max(1, min(concurrency_limit(stage), self.limit))

    def acquire(self, stage, resource='', at=None):
        """要一个号：拿得到就给票据，拿不到就说明为什么（并发上限／同一资源已在跑）。"""
        stage = str(stage or '')
        resource = str(resource or '')
        now = float(self.clock() if at is None else at)
        reason = ''
        if self.running() >= self.limit:
            reason = '全局并发已达上限 %d 路，先排队' % self.limit
        elif self.stage_running(stage) >= self.limit_of(stage):
            reason = '%s 并发已达上限 %d 路，先排队' % (label(stage), self.limit_of(stage))
        elif resource and resource in self.resources():
            reason = '同一资源 %s 正在处理，降速等待' % resource
        if reason:
            self.slowed.append({'at': now, 'stage': stage, 'resource': resource, 'reason': reason})
            del self.slowed[:-64]
            return {'ok': False, 'reason': reason, 'ticket': None}
        self.counter += 1
        ticket = {'id': '%s-%d' % (stage or 'stage', self.counter), 'stage': stage,
                  'resource': resource, 'at': now}
        self.tickets.append(ticket)
        return {'ok': True, 'reason': '', 'ticket': ticket}

    def release(self, ticket):
        """还号：认号不认人（重复还会返回 False，不会把别人的号扣掉）。"""
        if not isinstance(ticket, dict):
            return False
        for index, item in enumerate(self.tickets):
            if item['id'] == ticket.get('id'):
                del self.tickets[index]
                return True
        return False

    def release_stage(self, stage):
        """把一个阶段手上的号全还了（阶段收场时兜底，免得漏还卡住后面的）。"""
        stage = str(stage or '')
        before = len(self.tickets)
        self.tickets = [ticket for ticket in self.tickets if ticket['stage'] != stage]
        return before - len(self.tickets)

    def reset(self):
        self.tickets = []
        self.slowed = []

    def snapshot(self):
        """面板要的那几个数（纯读）。"""
        return {'limit': self.limit, 'running': self.running(), 'slowed': len(self.slowed),
                'stages': {stage: self.stage_running(stage) for stage in stages() if self.stage_running(stage)},
                'tickets': tuple(dict(ticket) for ticket in self.tickets)}


_SHARED = None


def shared():
    """全进程唯一的那一个并发控制器（第 63 期任务 4.2）。

    原来三虎自己建一个、SKILL 编排器再自己开一堆线程，两处各管一段，说白了谁都没管住。
    现在谁要发号都问这一份：全局 8 这条线是所有阶段一起数的，不是每个模块各数 8。
    """
    global _SHARED
    if _SHARED is None:
        _SHARED = Governor()
    return _SHARED


def _claim(governor, stage, item, at, wait):
    """要一个并发号：拿不到就小睡一下再看，最多等 ``wait`` 秒。

    并发上限那条路已经由「开几条线」卡死了（见 parallel_map 的 workers），这里兜的是
    「同一个资源撞车」——同一批次／同一项资产不能在两个 Agent 手上同时改。
    等不到就带着空号往下走：不丢单元，只记一笔降速。
    """
    if governor is None:
        return None
    deadline = time.time() + max(0.0, float(wait))
    while True:
        ticket = governor.acquire(stage, resource=str(item) if item is not None else '',
                                  at=at).get('ticket')
        if ticket is not None or time.time() >= deadline:
            return ticket
        time.sleep(POLL_SECONDS)


def parallel_map(stage, items, worker, governor=None, at=None, wait=WAIT_SECONDS):
    """按该阶段的并行度把一批单元跑掉：同时最多 ``limit`` 个在飞，返回 [(单元, 结果, 异常)]。

    批内串行由调用方保证（一个单元一个 worker 调用）；这里只管「同时在飞几个」。
    开几条线＝「阶段并行度的上限」与「全局并发上限」取小——上限是硬上限，撞上就排队；
    governor 给了还要逐个要号，同一资源撞车就等一等再上（不丢单元、不改变顺序）。
    """
    import threading
    values = list(items)
    high = degree(stage)[1]
    workers = max(1, min(high, governor.limit if governor else GLOBAL_LIMIT))
    results = [None] * len(values)
    lock = threading.Lock()
    cursor = [0]

    def run():
        while True:
            with lock:
                index = cursor[0]
                if index >= len(values):
                    return
                cursor[0] += 1
            item = values[index]
            ticket = None
            try:
                ticket = _claim(governor, stage, item, at, wait)
                results[index] = (item, worker(item), None)
            except Exception as exc:                       # 一个单元失败不影响别的单元
                results[index] = (item, None, exc)
            finally:
                if governor is not None and ticket:
                    governor.release(ticket)

    threads = [threading.Thread(target=run, daemon=True) for _ in range(max(1, workers))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


# ── 三、统一日志格式（附件任务5.3 ＋ 3.3：每次启动与结束都记进 logs/） ─────────────
LOG_NAME = 'agent_logs.jsonl'
LOG_FIELDS = ('at', 'stage', 'task', 'status', 'detail')


def log_row(stage, task, status, detail='', at=None):
    """一条日志：时间戳／阶段／任务／状态／详情（五个键固定，谁写都是这一份）。"""
    stamp = float(at) if at is not None else time.time()
    return {'at': stamp, 'time': datetime.fromtimestamp(stamp).strftime('%Y-%m-%d %H:%M:%S'),
            'stage': str(stage or ''), 'stage_name': label(stage), 'task': str(task or ''),
            'status': str(status or ''), 'detail': str(detail or '')}


def log_path(project, stage):
    """这一阶段的日志文件：项目根 `logs/<阶段>.agent_logs.jsonl`。

    不再为了记一条日志预建整套编号阶段目录；阶段名仍在文件名与每条记录中保留。
    """
    if project is None:
        return None
    root = Path(project)
    name = str(stage or '').strip() or 'project'
    safe = ''.join(ch if ch.isalnum() or ch in ('-', '_') else '_' for ch in name)
    return root / 'logs' / (safe + '.' + LOG_NAME)


def log_write(project, stage, task, status, detail='', at=None):
    """写一条。写不进去只返回 None——日志不该把干活的那一步拖下水。"""
    path = log_path(project, stage)
    if path is None:
        return None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(log_row(stage, task, status, detail, at), ensure_ascii=False,
                                    sort_keys=True) + '\n')
    except OSError:
        return None
    return path


def log_read(project, stage=None, limit=20):
    """读回最近的若干条（阶段给了就只读那一个阶段）。"""
    path = log_path(project, stage) if stage else None
    if path is None or not path.is_file():
        return ()
    rows = []
    try:
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        return ()
    return tuple(rows[-int(limit):]) if limit else tuple(rows)


def log_line(row):
    """一条日志的人话版（面板／报告里直接用）。"""
    return '%s　%s　%s　%s　%s' % (row.get('time', ''), row.get('stage_name') or row.get('stage', ''),
                                  row.get('task', ''), row.get('status', ''), row.get('detail', ''))

# ── 四、阶段间门禁（附件任务3.2：上游产出不全就挡住，不让往下走） ───────────────────
# 每条门禁查三件事：上游输出 JSON 是否完整、关键字段是否齐全、有没有未处理的错误。
# 判定口径见模块头第 2 条：上游**真的做了**却没做全才拦；压根没开始不拦。
GATES = (
    {'id': 'SG-01', 'from': 'assets', 'to': 'continuity', 'title': '资产锁定', 'check': 'assets_locked',
     'condition': '资产清单每一项都导入了图片，角色锚点已锁定',
     'reject': '先到 03 资产管理 把资产补齐、锁定锚点'},
    {'id': 'SG-02', 'from': 'continuity', 'to': 'final', 'title': '连贯性台账', 'check': 'ledger_ready',
     'condition': 'continuity_ledger.json 已生成，且没有未裁决的待办',
     'reject': '先到 04 连贯性清单 生成台账、裁决冲突'},
    {'id': 'SG-03', 'from': 'final', 'to': 'keyframe', 'title': '批次划分', 'check': 'batches_ready',
     'condition': '每镜都写了 batch_id，每批 ≤4 镜、≤18 秒，批次内三元组一致',
     'reject': '先到 05 分镜定稿 重新划分批次并写入 batch_id'},
    {'id': 'SG-04', 'from': 'keyframe', 'to': 'previs', 'title': '首帧校验', 'check': 'frames_ready',
     'condition': '每个镜头的首帧都在，且不是空文件',
     'reject': '先到 06 首帧管理 补上缺的首帧'},
    {'id': 'SG-05', 'from': 'previs', 'to': 'video', 'title': '预演校验', 'check': 'previs_ready',
     'condition': '需要白模的镜头都有可播放的预演产物',
     'reject': '先到 07 白模预演 补上缺的预演，或把该镜头改成无需白模'},
)
GATE_IDS = tuple(row['id'] for row in GATES)


def gate_for(stage):
    """进入某个阶段前要过的那条门禁（没有门禁的阶段返回 None）。"""
    text = str(stage or '')
    for row in GATES:
        if row['to'] == text:
            return dict(row)
    return None


def gate_ids():
    return GATE_IDS


def _result(row, ok, started, detail, problems=(), artifacts=()):
    return {'id': row['id'], 'from': row['from'], 'to': row['to'], 'title': row['title'],
            'condition': row['condition'], 'reject': row['reject'], 'ok': bool(ok),
            'started': bool(started), 'detail': str(detail or ''), 'problems': tuple(problems),
            'artifacts': tuple(str(item) for item in artifacts)}


def blocked_text(result):
    """这条门禁没过时面板要写的那一句（一句话说清缺什么、去哪儿补）。"""
    if result is None or result['ok']:
        return ''
    head = '%s 还没做完：%s' % (label(result['from']), result['detail'] or result['condition'])
    return head + '。' + result['reject']


def stage_state(project, stage):
    """阶段机里这一步的状态（读不出来给空串，绝不影响门禁判断）。"""
    if project is None or not str(stage or ''):
        return ''
    try:
        import pet_state
        machine = pet_state.Machine(project, persist=False).load()
        entry = machine.stages.get(str(stage)) or {}
        return str(entry.get('state') or '')
    except Exception:
        return ''


def has_run(project, stage):
    """这一步真的做过吗：阶段机说在跑／成了／失败了就算做过（pending 不算）。"""
    return stage_state(project, stage) in ('running', 'success', 'failed', 'retrying', 'skipped')


def _adopted(project):
    """已采用的分镜：返回 [(文件路径, 镜头列表)]；读不出来的跳过。"""
    from agent.core import read
    from storyboard_selection import adopted
    out = []
    for source in adopted(project):
        try:
            data = read(source)
        except Exception:
            continue
        if isinstance(data, dict) and isinstance(data.get('shots'), list):
            out.append((source, [shot for shot in data['shots'] if isinstance(shot, dict)]))
    return out


def assets_locked(project):
    """SG-01：资产清单每一项都导入了图片，角色锚点已锁定。"""
    from agent.core import read
    from asset_context import library_dir
    row = gate_for('continuity')
    try:
        base = library_dir(project)
        file = base / 'assets' / '资产清单' / 'assets.json'
        rows = read(file) if file.is_file() else {}
    except Exception as exc:
        return _result(row, True, False, '资产清单读不出来，先不拦：%s' % exc)
    if not isinstance(rows, dict) or not rows:
        return _result(row, True, False, '资产清单还没生成（资产管理还没做），先不拦')
    problems = []
    missing = [aid for aid, item in rows.items()
               if not isinstance(item, dict) or not str(item.get('image') or '').strip()]
    if missing:
        problems.append('%d 项资产还没导入图片：%s' % (len(missing), '、'.join(sorted(missing)[:6])))
    unlocked = [aid for aid, item in rows.items()
                if str(aid).startswith('CHAR') and isinstance(item, dict) and not item.get('locked')]
    if unlocked:
        problems.append('%d 个角色还没锁定锚点：%s' % (len(unlocked), '、'.join(sorted(unlocked)[:6])))
    noanchor = [aid for aid, item in rows.items()
                if str(aid).startswith('CHAR') and isinstance(item, dict)
                and not str(item.get('character_anchor') or item.get('base_anchor') or '').strip()]
    if noanchor:
        problems.append('%d 个角色还没有锚点字符串：%s' % (len(noanchor), '、'.join(sorted(noanchor)[:6])))
    unfinished = len({*missing, *unlocked, *noanchor})
    detail = ('%d 项资产里有 %d 项没到位' % (len(rows), unfinished)) if problems \
        else ('资产已全部导入并锁定（%d 项）' % len(rows))
    # 「做过」的凭据：阶段机说跑过，或者清单里已经有资产落了图／锁了锚点。
    # 只有名字（刚扫出来的初稿）不算做过——第 47 期起的规矩：还没开始就一律放行。
    touched = [aid for aid, item in rows.items() if isinstance(item, dict) and (
        str(item.get('image') or '').strip() or item.get('locked')
        or str(item.get('character_anchor') or item.get('base_anchor') or '').strip())]
    started = has_run(project, 'assets') or bool(touched)
    if not problems:
        return _result(row, True, started, detail, (), [file])
    if not started:
        return _result(row, True, False, '资产管理还没做，先不拦', (), [file])
    return _result(row, False, True, detail, problems, [file])


def ledger_ready(project):
    """SG-02：连贯性台账已生成、没有未裁决的待办。"""
    row = gate_for('final')
    from continuity_ledger import gate as ledger_gate
    from continuity_ledger import read as read_ledger
    try:
        ledger = read_ledger(project)
    except Exception as exc:
        return _result(row, True, False, '连贯性台账读不出来，先不拦：%s' % exc)
    if not isinstance(ledger, dict) or not ledger:
        return _result(row, True, False, '连贯性台账还没生成（这一步还没做），先不拦')
    ok, problems = ledger_gate(ledger)
    detail = '台账已生成' if ok else '台账里还有 %d 条未裁决的待办' % len(problems)
    return _result(row, ok, True, detail, problems, [str(project) + '/03_continuity/output/continuity_ledger.json'])


def batches_ready(project):
    """SG-03：每镜都有 batch_id，每批 ≤4 镜、≤18 秒、批内三元组一致。

    只查「批次划分」这件事本身——九个新增字段是分镜定稿自己的校验（见 shot_batches.validate），
    拿它当门禁会把「没走定稿就直接做首帧」这条老路堵死。
    """
    row = gate_for('keyframe')
    from shot_batches import check_batches
    entries = _adopted(project)
    if not entries:
        return _result(row, True, False, '还没有已采用的分镜，先不拦')
    problems = []
    artifacts = []
    for source, shots in entries:
        if not shots:
            continue
        artifacts.append(str(source))
        missing = [shot.get('id') or '?' for shot in shots if not str(shot.get('batch_id') or '').strip()]
        if missing:
            problems.append('%s 里 %d 个镜头没有 batch_id：%s'
                            % (source.name, len(missing), '、'.join(str(item) for item in missing[:6])))
        problems.extend(check_batches(shots))
    started = has_run(project, 'final') or any(str(shot.get('batch_id') or '').strip()
                                               for _, shots in entries for shot in shots)
    if not problems:
        return _result(row, True, True, '批次划分完成', (), artifacts)
    if not started:
        return _result(row, True, False, '分镜定稿还没做，先不拦', (), artifacts)
    return _result(row, False, True, '批次划分还有 %d 处问题' % len(problems), problems[:20], artifacts)


def frames_ready(project):
    """SG-04：每个镜头的首帧都在，且不是空文件。"""
    row = gate_for('previs')
    from keyframe_comfy import pending_shots
    from storyboard_paths import media_root
    entries = _adopted(project)
    if not entries:
        return _result(row, True, False, '还没有已采用的分镜，先不拦')
    problems = []
    artifacts = []
    total = 0
    for source, shots in entries:
        if not shots:
            continue
        artifacts.append(str(source))
        total += len(shots)
        base = media_root(source)
        for shot in pending_shots(shots, base):
            problems.append('%s 缺首帧：%s' % (shot.get('id') or '?', (base / str(shot.get('frame') or '')).name))
        for shot in shots:
            path = (base / str(shot.get('frame') or '')).resolve()
            try:
                if path.is_file() and not path.stat().st_size:
                    problems.append('%s 的首帧是空文件：%s' % (shot.get('id') or '?', path.name))
            except OSError:
                continue
    any_frame = False
    for source, shots in entries:
        base = media_root(source)
        for shot in shots:
            try:
                if (base / str(shot.get('frame') or '')).resolve().is_file():
                    any_frame = True
                    break
            except OSError:
                continue
        if any_frame:
            break
    if not problems:
        return _result(row, True, True, '%d 个镜头的首帧都在' % total, (), artifacts)
    if not (any_frame or has_run(project, 'keyframe')):
        return _result(row, True, False, '首帧管理还没做，先不拦', (), artifacts)
    return _result(row, False, True, '%d 个镜头缺首帧' % len(problems), problems[:20], artifacts)


def previs_ready(project):
    """SG-05：需要白模的镜头都有可播放的预演产物。"""
    row = gate_for('video')
    from previs_routing import classify, ready
    entries = _adopted(project)
    if not entries:
        return _result(row, True, False, '还没有已采用的分镜，先不拦')
    need = []
    for source, shots in entries:
        for shot in shots:
            try:
                level = classify(shot)[0]
            except Exception:
                continue
            if level == 'complex':
                need.append(shot.get('id') or '?')
    if not need:
        return _result(row, True, True, '没有需要白模的镜头', (), [str(source) for source, _ in entries])
    missing = []
    for sid in need:
        try:
            if not ready(project, sid):
                missing.append(sid)
        except Exception:
            missing.append(sid)
    artifacts = [str(source) for source, _ in entries]
    if not missing:
        return _result(row, True, True, '%d 个镜头需要白模，都有预演' % len(need), (), artifacts)
    made = has_run(project, 'previs') or any(ready(project, sid) for sid in need)
    if not made:
        return _result(row, True, False, '白模预演还没做，先不拦', (), artifacts)
    return _result(row, False, True, '%d 个镜头还没有白模预演' % len(missing),
                   ['缺预演：' + '、'.join(map(str, missing[:6]))], artifacts)


def evaluate(project, stage):
    """进入某个阶段前的门禁结论；没有门禁的阶段返回一个「通过」的空结果。"""
    row = gate_for(stage)
    if row is None:
        return {'id': '', 'from': '', 'to': str(stage or ''), 'title': '无门禁', 'condition': '这一步没有前置门禁',
                'reject': '', 'ok': True, 'started': False, 'detail': '没有前置门禁', 'problems': (),
                'artifacts': ()}
    return globals()[row['check']](project)


def blocked_stages(project, stage):
    """这一步被哪些上游阶段挡住（只算真的做了却没做全的）。stage_flow.blockers 用它。"""
    result = evaluate(project, stage)
    if result['ok'] or not result['started']:
        return ()
    return (result['from'],) if result['from'] else ()


def audit(project):
    """五条门禁的现状（报告／页面用）。"""
    return tuple(evaluate(project, row['to']) for row in GATES)


def audit_text(project):
    """门禁现状的纯文本表。"""
    lines = ['| 门禁 | 上游 → 这一步 | 通过条件 | 现状 |', '|---|---|---|---|']
    for result in audit(project):
        state = '通过' if result['ok'] else ('挡住：' + result['detail'])
        if result['ok'] and not result['started']:
            state = '上游还没开始（不拦）'
        lines.append('| %s %s | %s → %s | %s | %s |'
                     % (result['id'], result['title'], label(result['from']), label(result['to']),
                        result['condition'], state))
    return '\n'.join(lines) + '\n'


def gate_text(project, stage):
    """面板要的那一句：门禁挡住就写清缺什么、去哪儿补；没挡住返回空串。"""
    try:
        return blocked_text(evaluate(project, stage))
    except Exception:
        return ''


def page_lines(project, stage):
    """阶段页上那两行（并行配置 ＋ 门禁现状），纯文字，读不出来也不抛。"""
    row = config(stage)
    head = '并行：%s' % degree_label(stage)
    if row['unit'] != NONE:
        head += '　单元：%s　上限：%d 路　批内%s' % (unit_label(stage), row['limit'],
                                              '串行' if row['serial'] else '可并行')
    gate = gate_for(stage)
    if gate is None:
        return (head, '门禁：这一步没有前置门禁')
    if project is None:
        return (head, '门禁：还没打开项目')
    try:
        result = evaluate(project, stage)
    except Exception as exc:
        return (head, '门禁：暂时读不出来（%s）' % exc)
    if not result['ok']:
        state = blocked_text(result)
    elif result['started']:
        state = '通过（%s）' % result['detail']
    else:
        state = '上游还没开始，不拦'
    return (head, '门禁：%s %s %s' % (gate['id'], gate['title'], state))
