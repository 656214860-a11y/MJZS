"""宠物 Agent 的事件契约与进程内总线（纯标准库，不碰 Tk／网络）。

与「共享状态，不共享上下文」一致：制作链路只把「发生了什么」发成事件，宠物 UI、阶段状态机、
通知聚合各自订阅，互不直接调用。总线只做三件事——收（线程安全入队）、发（逐个订阅者调用且
互不影响）、记（幂等键去重 + 审计日志）。工作线程只 publish，界面线程在既有 150ms 心跳里 pump。
"""
import hashlib
import json
import queue
import threading
import time
from pathlib import Path
# 宽松读 JSON 只有 agent.core.read_json 一份实现，这里再导出一次：宠物各模块只 import pet_bus。
from agent.core import read_json

# 13 个制作阶段与页面序号一一对应（「参考网站」是工具页，不进状态机）。
# 第 62 期任务 11：「连贯性清单」从资产页底部的折叠区升成独立的一步（资产管理之后、分镜定稿之前），
# 页表、状态机、依赖图与三虎的进度面板都按这一份顺序走。
STAGES = ('script', 'script_structure', 'storyboard', 'animatic', 'assets', 'continuity', 'final', 'keyframe', 'previs', 'video', 'audio',
          'edit', 'delivery')
STAGE_NAMES = {'script': '剧本准备', 'script_structure': '剧本结构', 'storyboard': '初步分镜', 'animatic': '分镜预演', 'assets': '资产管理', 'continuity': '连贯性清单',
               'final': '分镜定稿', 'keyframe': '首帧管理', 'previs': '白模预演', 'video': '视频生成',
               'audio': '配音与字幕', 'edit': '后期剪辑', 'delivery': '质检与交付'}


def stage_name(stage, fallback=None):
    """返回制作阶段的唯一用户可见名称；未知阶段保留调用方给出的回退值。"""
    key = str(stage or '')
    return STAGE_NAMES.get(key, key if fallback is None else fallback)


def stage_step(stage):
    """用户在导航里看到的阶段步号；与阶段目录、页面编号同源（两位，1 起）。"""
    key = str(stage or '')
    index = STAGES.index(key) + 1 if key in STAGES else 0
    return ('第%02d步' % index) if index else ''


def stage_label(stage):
    """用户在导航里看到的页面标签（两位步号 + 空格 + 权威名称）；未知阶段退回显示名。"""
    key = str(stage or '')
    if key in STAGES:
        return '%02d %s' % (STAGES.index(key) + 1, STAGE_NAMES[key])
    return stage_name(key)


# 事件契约：kind → 必填负载字段。新事件必须先在这里登记，契约与实现不会各写一份。
CONTRACT = {
    'stage.started': ('stage',),
    'stage.completed': ('stage',),
    'stage.failed': ('stage', 'error'),
    'stage.retrying': ('stage', 'attempt', 'delay'),
    'stage.executing': ('stage',),
    'stage.paused': ('stage',),
    'script.completed': ('stage',),
    'asset.reference.found': ('character', 'candidates'),
    'firstframe.task.failed': ('shot', 'error'),
    'video.task.failed': ('shot', 'error'),
    'voice.task.failed': ('shot', 'error'),
    'delivery.ready': ('path',),
    'budget.warning': ('budget', 'used', 'limit'),
    'budget.exceeded': ('budget', 'used', 'limit'),
    'notify.aggregate': ('text',),
    'intent.command': ('text',),
}
STAGE_EVENTS = ('stage.started', 'stage.completed', 'stage.failed', 'stage.retrying')
# 第 54 期：这两个只报「这一刻这一步在不在跑」，不改状态机的状态——所以不进 STAGE_EVENTS
# （Machine.apply 只按 STAGE_EVENTS 认事件，混进去会被当成一次重试）。
LIVE_EVENTS = ('stage.executing', 'stage.paused')
# 认「必须带一个登记过的阶段名」的那几类事件。
STAGE_NAMED = STAGE_EVENTS + LIVE_EVENTS
SEEN_LIMIT = 512
HISTORY_LIMIT = 64
# O42：待处理事件上限。工作线程只 publish、界面线程每 150ms 心跳 pump 一次（每轮上限 200），
# 生产者比这快时原来那条无界队列会一直涨。到水位后只从「可以少一条」的事件里让路（见
# SHEDDABLE_EVENTS）：工作线程永不被阻塞，完成／失败／暂停／用户指令／预算一律不让路。
PENDING_LIMIT = 1024
ERROR_LIMIT = 64           # 订阅者异常在内存里只留最近这些条，累计数另记 errors_total
ERROR_PERSIST_LIMIT = 128  # 订阅者异常写审计日志的上限：异常风暴也不得撑爆磁盘
# 到水位后允许让路的事件：只报「这一刻在跑」和「汇总说一句」，丢了不丢状态；
# 终态（stage.completed／stage.failed／script.completed／delivery.ready 等）与
# stage.paused（它带着并发号的归还）都不在此列，背压永不丢它们。
SHEDDABLE_EVENTS = ('stage.executing', 'notify.aggregate')


def identify(kind, payload):
    """幂等键：同一件事重复上报只算一次（重试与轮询会让同一条消息被报多次）。"""
    body = json.dumps({'kind': kind, **{str(key): payload.get(key) for key in sorted(payload)}},
                      ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(body.encode('utf-8')).hexdigest()[:32]


def event(kind, key=None, **payload):
    """构造事件：校验契约与阶段名，带墙钟时间 at 与幂等键 id。"""
    if kind not in CONTRACT:
        raise ValueError('未登记的事件：' + str(kind))
    stage = payload.get('stage')
    if kind in STAGE_NAMED and stage not in STAGES:
        raise ValueError('未登记的制作阶段：' + str(stage))
    missing = [name for name in CONTRACT[kind] if payload.get(name) in (None, '')]
    if missing:
        raise ValueError(str(kind) + ' 缺少字段：' + '、'.join(missing))
    return {'kind': kind, 'at': time.time(), 'id': key or identify(kind, payload), **payload}


class ErrorLog(list):
    """界面与 Agent 的错误记录：只留最近 ERROR_LIMIT 条，total 记累计数。

    150ms 心跳里一个持续的异常每秒会记好几笔；用普通 list 会一直涨到进程退出。
    """

    def __init__(self, limit=ERROR_LIMIT):
        super().__init__()
        self.limit = limit
        self.total = 0

    def append(self, item):
        self.total += 1
        super().append(item)
        extra = len(self) - self.limit
        if extra > 0:
            del self[:extra]


def emit_safe(bus, errors, kind, **payload):
    """发一条事件：没挂总线、不合契约、订阅者出错都只记一笔，绝不把界面线程带崩。

    父 Agent 与界面两侧都要「发事件失败也不能停下来」这一条，各写一遍迟早走偏。
    """
    if bus is None:
        return None
    try:
        return bus.emit(kind, **payload)
    except Exception as exc:
        errors.append((kind, str(exc)))
        return None


def is_sheddable(kind):
    """这一条是不是「队列到水位时可以让路」的进度／汇总事件（见 SHEDDABLE_EVENTS）。"""
    return str(kind or '') in SHEDDABLE_EVENTS


class Bus:
    """线程安全的事件总线：工作线程入队，界面线程 pump 后分发并落审计日志。"""

    def __init__(self, journal=None, seen_limit=SEEN_LIMIT, pending_limit=PENDING_LIMIT,
                 error_limit=ERROR_LIMIT):
        self.queue = queue.Queue()
        self.journal = Path(journal) if journal else None
        self.seen_limit = seen_limit
        self.pending_limit = pending_limit
        self.error_limit = error_limit
        self.touched = 0          # 进入总线的条数（含被幂等丢掉的）
        self.delivered = 0        # 成功送达订阅者的次数
        self.dropped = 0          # 幂等去重丢掉的条数（入队前合并的 + pump 时撞上已发过的）
        self.shed = 0             # 到水位后让路丢掉的进度／汇总条数（O42 背压）
        self.errors_total = 0     # 订阅者异常累计条数（errors 只留最近 error_limit 条）
        self.water = 0            # 待处理事件数的历史最高水位，供验收测量
        self.history = []         # 最近事件，供进度面板与测试查看
        self.errors = []          # 订阅者异常：记录但不影响其他订阅者（有界环形）
        self._queued = set()      # 已入队、还没 pump 的幂等键（水位与合并都看它）
        self._lock = threading.Lock()
        self._known = set()
        self._seen = []
        self._subs = {}           # kind 或 '*' → [回调]

    def subscribe(self, kind, callback):
        """订阅某类事件（'*' 表示全部）。返回回调，便于测试里直接引用。"""
        self._subs.setdefault(kind, []).append(callback)
        return callback

    def unsubscribe(self, kind, callback=None):
        """退订：给了回调只摘那一个，不给则整类摘空；返回摘掉的回调数。

        关页／换项目时把订阅释放干净——旧页面不再收事件，也不会被事件反过来唤醒。
        """
        callbacks = self._subs.get(kind)
        if not callbacks:
            return 0
        if callback is None:
            return len(self._subs.pop(kind))
        kept = [item for item in callbacks if item is not callback]
        removed = len(callbacks) - len(kept)
        if kept:
            self._subs[kind] = kept
        else:
            self._subs.pop(kind, None)
        return removed

    def release(self):
        """释放全部订阅，返回共摘掉几个回调；换项目／关页时清干净，不残留旧订阅。"""
        removed = sum(len(items) for items in self._subs.values())
        self._subs = {}
        return removed

    def publish(self, item):
        """工作线程调用：只入队，不碰界面，不写盘。

        入队前做两件背压的事，都不阻塞工作线程：同一件事（同一幂等键）已经在队列里就不再
        重复入队（pump 时本来也会去重，提到这里是不让它把内存撑大）；队列到水位时只让
        SHEDDABLE_EVENTS 里的进度／汇总事件让路并计数，终态与暂停一律照常入队。
        """
        kind = item.get('kind') if isinstance(item, dict) else None
        key = item.get('id') if isinstance(item, dict) else None
        with self._lock:
            if key is not None and key in self._queued:
                self.dropped += 1
                self.touched += 1
                return item
            if len(self._queued) >= self.pending_limit and is_sheddable(kind):
                self.shed += 1
                self.touched += 1
                return item
            if key is not None:
                self._queued.add(key)
                if len(self._queued) > self.water:
                    self.water = len(self._queued)
        self.queue.put(item)
        self.touched += 1
        return item

    def emit(self, kind, **payload):
        return self.publish(event(kind, **payload))

    def pump(self, limit=200):
        """界面线程调用：分发队列里的新事件，返回本轮处理条数（每轮有上限，避免卡帧）。"""
        count = 0
        while count < limit:
            try:
                item = self.queue.get_nowait()
            except queue.Empty:
                break
            count += 1
            self._dequeued(item)
            if item['id'] in self._known:
                self.dropped += 1
                continue
            self._remember(item['id'])
            self.history.append(item)
            del self.history[:-HISTORY_LIMIT]
            self._write(item)
            self._deliver(item)
        return count

    def _remember(self, key):
        self._seen.append(key)
        self._known.add(key)
        if len(self._seen) > self.seen_limit:
            self._known.discard(self._seen.pop(0))

    def _deliver(self, item):
        for callback in list(self._subs.get(item['kind'], ())) + list(self._subs.get('*', ())):
            try:
                callback(item)
            except Exception as exc:                     # 订阅者自己的问题，不能拖垮总线
                self._record_error(item['kind'], str(exc))
            else:
                self.delivered += 1

    def _dequeued(self, item):
        """出队即从待处理表里摘掉：水位回到真实值，幂等键也让位给后来的重复上报。"""
        key = item.get('id') if isinstance(item, dict) else None
        if key is None:
            return
        with self._lock:
            self._queued.discard(key)

    def _record_error(self, kind, message):
        """订阅者异常：内存留最近 error_limit 条，累计数另记，并落一份持久诊断。"""
        self.errors_total += 1
        self.errors.append((kind, message))
        extra = len(self.errors) - self.error_limit
        if extra > 0:
            del self.errors[:extra]
        if self.errors_total <= ERROR_PERSIST_LIMIT:
            self._diagnose(kind, message)

    def _diagnose(self, kind, message):
        """把订阅者异常写进审计日志：内存里的环形会被后来的覆盖，磁盘上留一份可追。

        与事件同一份 jsonl（pet_agent 的 skip／submit 也记在这里）；写不进去只记一笔，
        绝不让诊断本身把总线带崩。
        """
        if self.journal is None:
            return
        try:
            self.journal.parent.mkdir(parents=True, exist_ok=True)
            row = {'kind': 'bus.subscriber.error', 'at': time.time(), 'event': kind, 'error': message}
            with self.journal.open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
        except OSError as exc:
            self.errors.append(('journal.error', str(exc)))
            extra = len(self.errors) - self.error_limit
            if extra > 0:
                del self.errors[:extra]

    def _write(self, item):
        if self.journal is None:
            return
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        with self.journal.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + '\n')

    @property
    def pending(self):
        """还没 pump 掉的事件数（按幂等键去重后的真实水位）。"""
        with self._lock:
            return len(self._queued)

    def stats(self):
        """总线现状（只读）：待处理、历史最高水位与各计数，供进度面板与验收测量。"""
        return {'pending': self.pending, 'water': self.water, 'touched': self.touched,
                'delivered': self.delivered, 'dropped': self.dropped, 'shed': self.shed,
                'errors': self.errors_total, 'history': len(self.history)}

    def stage_name(self, stage):
        return stage_name(stage)
