# -*- coding: utf-8 -*-
"""SKILL 预算硬限制：Token 日 200 万、生图 200 张/项目、视频 100 镜/项目。

三本账分开记，互不挪用：
- Token 走 pet_llm 那本台账（全程序只此一份，按北京时间的「当天」算）；
- 生图与视频是「项目内累计」，落在项目的 工作流任务/SKILL/预算.json。

界面与编排器都只问这里：check() 给结论（能不能再花），spend() 记账，snapshot() 给面板显示。
"""
import threading
import time

import infra.budget as budget_engine
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import contract.stage_layout as stage_layout
from agent.core import save
from contract.pet_bus import STAGE_NAMES, read_json

PROGRAM = Path(__file__).resolve().parents[1]
BUDGET_PATH = (stage_layout.WORKFLOW_DIR, 'SKILL', '预算.json')
# 第 44 期：「设置 → 预算」里改的就是三虎那本配额账（配置/宠物/配置.json 的 budget_limits），
# 这里不再另立一份存额度的文件——一份设置、两处（三虎账本与 SKILL 编排）都照它算。
PET_CONFIG = ('配置', '宠物', '配置.json')
PET_LIMIT_OF = {'tokens': 'tokens', 'images': 'image', 'videos': 'video'}
KINDS = ('tokens', 'images', 'videos')
DEFAULTS = {'tokens_per_day': 2000000, 'images_per_project': 200, 'videos_per_project': 100}
# unknown 预留的对账窗口：执行中途失败落 unknown 后按「未提交」保留一天，
# 超时由 reserved()/load() 按 released 处理，不再永久占额度（AUD-SKILL D2）。
UNKNOWN_TTL = 24 * 3600
LIMIT_OF = {'tokens': 'tokens_per_day', 'images': 'images_per_project', 'videos': 'videos_per_project'}
LABELS = {'tokens': 'Token（每天）', 'images': '生图（每项目）', 'videos': '视频（每项目）'}
_TRANSACTION_LOCK = threading.RLock()


def budget_path(project):
    return Path(project).joinpath(*BUDGET_PATH)


def limits(config=None):
    """额度：默认三条硬限制，配置里写了就按配置（只认这三把键）。"""
    out = dict(DEFAULTS)
    data = config if isinstance(config, dict) else {}
    for key in DEFAULTS:
        try:
            value = int(data.get(key, out[key]))
        except (TypeError, ValueError):
            continue
        if value > 0:
            out[key] = value
    return out


def pet_config_path(program=None):
    return Path(program or PROGRAM).joinpath(*PET_CONFIG)


def pet_limits(program=None):
    """三虎配额账 → 这里的三把键；缺项不补（调用方 limits() 会补默认值）。"""
    data = read_json(pet_config_path(program))
    limits = data.get('budget_limits') if isinstance(data, dict) else None
    limits = limits if isinstance(limits, dict) else {}
    out = {}
    for kind, key in PET_LIMIT_OF.items():
        try:
            value = int(limits.get(key))
        except (TypeError, ValueError):
            continue
        if value > 0:
            out[LIMIT_OF[kind]] = value
    return out


def configured(program=None):
    """界面改完立刻按新额度算：默认三条 ＋ 配置文件里那几把键。"""
    return limits(pet_limits(program))


def for_project(project, program=None, ledger=None, clock=time.time):
    """按当前设置给一个项目建账本（编排器与阶段面板都走它，额度只此一处）。"""
    return Budget(project=project, config=pet_limits(program), ledger=ledger, clock=clock)


class Budget:
    """一个项目的预算账本；Token 那本可以挂在 pet_llm.Ledger 上（有就不自己记）。"""

    def __init__(self, project=None, config=None, ledger=None, clock=time.time):
        self.project = Path(project) if project else None
        self.config = config if isinstance(config, dict) else {}
        self.ledger = ledger
        self.clock = clock
        self.counters = {'tokens': 0, 'images': 0, 'videos': 0}
        self.reservations = {}
        self.load()

    @contextmanager
    def transaction(self):
        """同进程串行、跨进程字节锁；崩溃释放锁但保留预留账。"""
        with _TRANSACTION_LOCK:
            if self.project is None:
                yield
                return
            path = budget_path(self.project).with_suffix('.lock')
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('a+b') as stream:
                if not path.stat().st_size:stream.write(b'0'); stream.flush()
                stream.seek(0)
                # 产品随附 Windows Python；锁实现必须在随附运行时中可用。
                import msvcrt
                try:msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError:raise ValueError('预算账本正在更新，请稍后重试') from None
                try:
                    self.load()
                    yield
                finally:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)

    def reserve(self, request_id, kind, amount=1):
        kind = self._kind(kind)
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise ValueError('预算预留量必须是正整数')
        with self.transaction():
            if request_id in self.reservations:
                return False, '该请求已预留或结算，请先核对原任务，不能重复提交'
            enough, note = self.check(kind, amount)
            if not enough:return enough, note
            self.reservations[request_id] = {'kind': kind, 'amount': amount, 'state': 'reserved'}
            self.save()
            return True, note

    def finish(self, request_id, *, completed=False, not_submitted=False):
        with self.transaction():
            entry = self.reservations.get(request_id)
            if not entry or entry['state'] in ('settled', 'released'):return
            if not_submitted:
                entry['state'] = 'released'
            elif completed:
                kind = entry['kind']
                if not (kind == 'tokens' and self.ledger is not None):
                    self.counters[kind] += entry['amount']
                entry['state'] = 'settled'
            else:
                entry['state'] = 'unknown'
                entry['unknown_at'] = float(self.clock())
            self.save()

    def reserved(self, kind):
        now = float(self.clock())
        return sum(row['amount'] for row in self.reservations.values()
                   if row['kind'] == kind and row['state'] in ('reserved', 'unknown')
                   and not self._unknown_expired(row, now))

    def _unknown_expired(self, row, now=None):
        """unknown 预留是否已过对账窗口；旧账没有 unknown_at 视为已超时。"""
        if row.get('state') != 'unknown':
            return False
        at = row.get('unknown_at')
        if isinstance(at, bool) or not isinstance(at, (int, float)):
            return True
        return (now if now is not None else float(self.clock())) - at >= UNKNOWN_TTL

    def _release_expired_unknown(self):
        """对账清扫：unknown 超时的预留转 released，额度不再被占；返回是否有改动。"""
        now = float(self.clock())
        changed = False
        for row in self.reservations.values():
            if self._unknown_expired(row, now):
                row['state'] = 'released'
                changed = True
        return changed

    # ── 额度与用量 ──────────────────────────────────────────────────────────
    def limit(self, kind):
        kind = self._kind(kind)
        return limits(self.config)[LIMIT_OF[kind]]

    def used(self, kind):
        kind = self._kind(kind)
        if kind == 'tokens' and self.ledger is not None:
            return int(self.ledger.today_tokens())
        return int(self.counters.get(kind, 0))

    def remaining(self, kind):
        # I16：剩余额度的算术收敛到 L1 预算引擎（headroom 与原式逐字等价）。
        return budget_engine.headroom(self.limit(kind), self.used(kind), self.reserved(kind))

    def check(self, kind, amount=1):
        """还能不能再花 amount：返回 (能不能, 一句话)。"""
        kind = self._kind(kind)
        amount = max(0, int(amount))
        left = self.remaining(kind)
        if amount > left:
            return False, '%s 额度不够：还剩 %d，本次要 %d' % (LABELS[kind], left, amount)
        return True, '%s 还剩 %d' % (LABELS[kind], left)

    def over(self, kind):
        return self.used(kind) >= self.limit(kind)

    def spend(self, kind, amount=1):
        """记账：Token 那本交给 pet_llm 的台账，其余加进本项目的计数器。"""
        kind = self._kind(kind)
        amount = max(0, int(amount))
        if kind == 'tokens' and self.ledger is not None:
            return self.used(kind)
        with self.transaction():
            self.counters[kind] = self.counters.get(kind, 0) + amount
            self.save()
            return self.counters[kind]

    def snapshot(self):
        return {kind: {'used': self.used(kind), 'limit': self.limit(kind),
                       'reserved': self.reserved(kind),
                       'remaining': self.remaining(kind), 'label': LABELS[kind]} for kind in KINDS}

    @staticmethod
    def _kind(kind):
        text = str(kind or '')
        if text not in KINDS:
            raise ValueError('没登记的预算类别：' + text)
        return text

    # ── 落盘 ────────────────────────────────────────────────────────────────
    def load(self):
        if self.project is None:
            return self
        from agent.core import read
        path = budget_path(self.project)
        data = read(path) if path.exists() else {}
        if not isinstance(data, dict):raise ValueError('预算账损坏，请核对后恢复')
        if isinstance(data, dict):
            reservations = data.get('reservations', {})
            if not isinstance(reservations, dict):raise ValueError('预算预留账损坏，请核对后恢复')
            for row in reservations.values():
                if (not isinstance(row, dict) or row.get('kind') not in KINDS
                        or row.get('state') not in ('reserved', 'unknown', 'settled', 'released')
                        or type(row.get('amount')) is not int or row['amount'] <= 0):
                    raise ValueError('预算预留账损坏，请核对后恢复')
            self.reservations = reservations
            self._release_expired_unknown()
            for kind in KINDS:
                value = data.get(kind, 0)
                if type(value) is not int or value < 0:raise ValueError('预算计数损坏，请核对后恢复')
                self.counters[kind] = value
        return self

    def save(self):
        if self.project is None:
            return None
        path = budget_path(self.project)
        data = dict(self.counters)
        data['reservations'] = self.reservations
        data['updated_at'] = float(self.clock())
        save(path, data)
        return path


# ── REL-09：全自动档付费步骤的一次一授权（pet 与 desktop 两侧共用同一份实现）─────────
# 行数门禁倒逼的落点：pet_ui_stages 已到体量上限、desktop_pet_bridge 反向 import 会成环，
# 只有 L3 的这里两侧都进得来。「三虎五类配额接线」本身是配额判定，与本模块职责一致。
PAID_STAGE_KINDS = {'assets': ('image', '生图'), 'video': ('video', '视频'), 'audio': ('voice', '配音')}
PAID_STEP_TOKENS = 500        # 一次付费派发的估算 Token（正整数安全默认；实际消耗以派发后台账为准）
PAID_STEP_STEPS = {'assets': '约 1 次生图', 'video': '约 1 段视频', 'audio': '约 1 条配音'}


def paid_quota_text(budget, kind, label, estimate):
    """REL-09 确认框的「剩余额度」行：阶段配额与 Token（每天）各按 remaining/limit 列。"""
    quota, tokens = budget.check(kind), budget.check('tokens', estimate)
    return '剩余额度：%s %d/%d；Token（每天）%d/%d' % (
        label, quota['remaining'], quota['limit'], tokens['remaining'], tokens['limit'])


def paid_stage_guard(host, stage, var=None):
    """REL-09：全自动档付费步骤的一次性授权闸——问、记、开、收场都在这一处。

    先按当次估算查阶段配额与 Token 日额（剩余 ≤0 或小于估算都算见底），见底不弹窗，
    直接 spend/pause＋stage.failed 转人工；弹出的确认写明四件事——步骤名、当次数量
    （原单位）、估算 Token、剩余额度——并声明授权只对这一次步骤有效。弹窗失败、超时
    没等到、用户拒绝一律按未授权收场；授权后记一格配额（越线同样转人工），再打开这
    一步自己的无人值守开关，返回 True。其余一律返回那句人话（已 pause＋stage.failed），
    绝不派发。host 是三虎侧对象（.agent／.errors／.asker／.auto_variable／.confirm_start）。
    """
    agent, entry = getattr(host, 'agent', None), PAID_STAGE_KINDS.get(stage)
    name = STAGE_NAMES.get(stage, stage) or '这一步'
    if agent is None or entry is None:
        return True                                    # 非付费步骤／没有账本就不拦
    kind, label = entry
    budget = agent.budget
    budget.sync_tokens(getattr(getattr(agent, 'client', None), 'ledger', None))
    quota = budget.check(kind)
    if not quota['ok']:
        agent.spend(kind, stage=stage)                 # spend 会 pause＋budget.exceeded＋stage.failed
        return '「%s」的%s配额不够（%d/%d）：请您接手这一步' % (name, label, quota['used'], quota['limit'])
    tokens = budget.check('tokens', PAID_STEP_TOKENS)
    if not tokens['ok']:
        reason = '「%s」预计消耗 Token %d，今天的 Token 见底（剩 %d/%d）：请您接手这一步' % (
            name, PAID_STEP_TOKENS, tokens['remaining'], tokens['limit'])
        agent.pause(reason, stage=stage)
        return reason
    text = ('「%s」这一步要花钱：本次%s，预计消耗 Token %d。%s。授权只对这一次步骤有效，'
            '现在做吗？' % (name, PAID_STEP_STEPS.get(stage, '约 1 次'), PAID_STEP_TOKENS,
                           paid_quota_text(budget, kind, label, PAID_STEP_TOKENS)))
    asker = getattr(host, 'asker', None)
    try:
        granted = (bool(asker('确认付费步骤', text)) if callable(asker)
                   else host.confirm_start('确认付费步骤', text))
    except Exception as exc:
        errors = getattr(host, 'errors', None)
        if errors is not None:
            errors.append(('paid.ask', str(exc)))
        granted = False
    if not granted:
        reason = '「%s」是付费步骤，您没有授权：请您接手这一步' % name
        agent.pause(reason, stage=stage)
        return reason
    if not agent.spend(kind, stage=stage)['ok']:         # 越线时 spend 已 pause＋stage.failed
        return '「%s」的%s配额刚用完：请您接手这一步' % (name, label)
    try:
        flag = host.auto_variable(var) if var else None
        if flag is not None:
            flag.set(True)
    except Exception as exc:
        errors = getattr(host, 'errors', None)
        if errors is not None:
            errors.append(('paid.var', str(exc)))
    return True


def run_stage_kick(host, stage, kick):
    """REL-09 自 PetStagesMixin.start_stage 抽出：授权后的派发与失败收口（宿主无关）。"""
    prefix = {'script_structure': '剧本结构未派发：', 'storyboard': '分镜批次未派发：',
              'keyframe': '首帧批次未派发：'}.get(stage, '阶段未派发：')
    failure_key = None
    try:
        started = kick(stage)
    except Exception as exc:
        host.errors.append(('start', str(exc)))
        started = prefix + str(exc)
        failure_key = uuid4().hex
    if started is False:
        started = prefix + '运行登记或启动动作未成功'
        failure_key = uuid4().hex
    started = str(started or '')
    if started and started.startswith(prefix):
        host._emit('stage.failed', stage=stage, error=started, key=failure_key)
    return started
