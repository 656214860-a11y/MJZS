"""宠物 Agent 的事件契约与进程内总线（纯标准库，不碰 Tk／网络）。

与「共享状态，不共享上下文」一致：制作链路只把「发生了什么」发成事件，宠物 UI、阶段状态机、
通知聚合各自订阅，互不直接调用。总线只做三件事——收（线程安全入队）、发（逐个订阅者调用且
互不影响）、记（幂等键去重 + 审计日志）。工作线程只 publish，界面线程在既有 150ms 心跳里 pump。
"""
import hashlib
import json
import queue
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


class Bus:
    """线程安全的事件总线：工作线程入队，界面线程 pump 后分发并落审计日志。"""

    def __init__(self, journal=None, seen_limit=SEEN_LIMIT):
        self.queue = queue.Queue()
        self.journal = Path(journal) if journal else None
        self.seen_limit = seen_limit
        self.touched = 0          # 进入总线的条数（含被幂等丢掉的）
        self.delivered = 0        # 成功送达订阅者的次数
        self.dropped = 0          # 幂等去重丢掉的条数
        self.history = []         # 最近事件，供进度面板与测试查看
        self.errors = []          # 订阅者异常：记录但不影响其他订阅者
        self._known = set()
        self._seen = []
        self._subs = {}           # kind 或 '*' → [回调]

    def subscribe(self, kind, callback):
        """订阅某类事件（'*' 表示全部）。返回回调，便于测试里直接引用。"""
        self._subs.setdefault(kind, []).append(callback)
        return callback

    def publish(self, item):
        """工作线程调用：只入队，不碰界面，不写盘。"""
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
                self.errors.append((item['kind'], str(exc)))
            else:
                self.delivered += 1

    def _write(self, item):
        if self.journal is None:
            return
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        with self.journal.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + '\n')

    def stage_name(self, stage):
        return stage_name(stage)
