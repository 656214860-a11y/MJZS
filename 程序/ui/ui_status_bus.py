# -*- coding: utf-8 -*-
"""统一文字提示模块的消息模型与消息总线（R2985 P0）。

业务模块只 ``publish(Message(...))``；UI 订阅者（统一状态栏）统一渲染。
线程安全：工作线程 publish 入队，UI 线程经 ``pump()``（挂 root.after 心跳）消费；
订阅回调都在 pump 线程（UI 线程）执行，业务侧不得在回调里做重活。

API 形态借鉴 PyPubSub（BSD-2-Clause）的 subscribe/publish；零第三方依赖，只借架构思路。
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field

import infra.app_logging as app_logging

LEVELS = ('info', 'success', 'warning', 'error')
PERSISTENT_LEVELS = ('warning', 'error')
AUTO_DISMISS_MS = 8000.0
DEDUPE_WINDOW_S = 3.0


@dataclass
class Message:
    """一条结构化消息：级别、正文、存活时长（None=常驻直到替换或处理）与来源。"""

    level: str
    text: str
    ttl: float | None
    source: str = ''
    at: float = field(default_factory=time.time)

    def __post_init__(self):
        if self.level not in LEVELS:
            raise ValueError('未知消息级别 %r（可选：%s）' % (self.level, '/'.join(LEVELS)))
        if self.ttl is not None and self.ttl < 0:
            raise ValueError('ttl 不能为负')

    @classmethod
    def make(cls, level, text, *, source='', auto=True):
        """按级别给默认生命周期：error/warning 常驻（直到替换或处理），其余自动消失。"""
        ttl = None if level in PERSISTENT_LEVELS else (AUTO_DISMISS_MS if auto else None)
        return cls(level=level, text=str(text), ttl=ttl, source=source)


def deliver_notice(bus, status, level, text):
    """通知分发的统一出口（R3056 从 ui_widgets 迁入以守住模块行数棘轮）：
    有总线走四级消息并同步泵（旧 StringVar 同帧镜像），无总线落旧状态栏；
    错误级另写应用日志（app_logging 轮转日志+脱敏过滤）。"""
    if bus is not None:
        bus.publish(Message.make(level, text, source='notifier'))
        bus.pump()
    else:
        setter = getattr(status, 'set', None)
        if callable(setter):
            setter(text)
    if level == 'error':
        logging.getLogger('ui_widgets').error('通知错误：%s', text)


class StatusBus:
    """进程内消息总线：publish 线程安全；pump 在 UI 线程分发并维护历史。

    事件回调签名 ``fn((kind, message, previous))``：
    - ``('current', message, previous)``：新消息上屏，previous 为被替换的旧消息或 None；
    - ``('expired', None, None)``：当前消息到期或已处理，栏位回到中性。
    """

    def __init__(self, history_limit=50):
        self._queue: 'queue.Queue[Message]' = queue.Queue()
        self._lock = threading.Lock()
        self._subscribers = []
        self._history = []
        self._current = None
        self._history_limit = history_limit

    # ---- 订阅 ----
    def subscribe(self, fn):
        with self._lock:
            self._subscribers.append(fn)

        def _unsubscribe():
            with self._lock:
                if fn in self._subscribers:
                    self._subscribers.remove(fn)

        return _unsubscribe

    # ---- 发布（任意线程） ----
    def publish(self, message):
        if not isinstance(message, Message):
            raise TypeError('publish 只接受 Message 实例')
        self._queue.put(message)

    # ---- 消费（UI 线程） ----
    def pump(self):
        drained = 0
        while True:
            try:
                message = self._queue.get_nowait()
            except queue.Empty:
                return drained
            self._deliver(message)
            drained += 1

    def _deliver(self, message):
        now = time.time()
        with self._lock:
            current = self._current
            if (current is not None and current.level == message.level
                    and current.text == message.text
                    and now - current.at < DEDUPE_WINDOW_S):
                # 幂等合并：刷新时间与存活时长，不重复入历史、不重复广播。
                current.at = now
                if current.ttl is not None:
                    current.ttl = message.ttl
                return
            previous = self._current
            self._current = message
            if previous is not None:
                self._history.append(previous)
                del self._history[:-self._history_limit]
        self._broadcast(('current', message, previous))

    def expire_current(self):
        """UI 定时器到点：当前普通消息进历史，栏位回到中性。常驻消息不会被过期。"""
        with self._lock:
            if self._current is None or self._current.ttl is None:
                return False
            self._history.append(self._current)
            del self._history[:-self._history_limit]
            self._current = None
        self._broadcast(('expired', None, None))
        return True

    def dismiss(self):
        """显式处理当前消息（常驻消息也适用）：移入历史并清空栏位。"""
        with self._lock:
            if self._current is None:
                return False
            self._history.append(self._current)
            del self._history[:-self._history_limit]
            self._current = None
        self._broadcast(('expired', None, None))
        return True

    def _broadcast(self, event):
        with self._lock:
            subscribers = list(self._subscribers)
        for fn in subscribers:
            fn(event)

    # ---- 查询 ----
    @property
    def current(self):
        with self._lock:
            return self._current

    def history(self, limit=None):
        with self._lock:
            items = list(self._history)
        if limit is not None:
            items = items[-limit:]
        return items


def publish_startup_warnings(bus, items):
    """轮 3B H2：启动自检暂存的非 FATAL 项在主窗口状态栏发一次【警告】。

    同一 ``code`` 每次启动至多一条（去重后取前 4 条，其余折叠计数）；
    ``items`` 为空／None 静默返回；任何内部失败不影响启动。
    """
    items = [item for item in (items or []) if item is not None]
    if not items or bus is None:
        return
    try:
        seen = set()
        unique = []
        for item in items:
            code = str(getattr(item, 'code', '') or id(item))
            if code in seen:
                continue
            seen.add(code)
            unique.append(item)
        shown = []
        for item in unique[:4]:
            code = str(getattr(item, 'code', '') or '')
            message = str(getattr(item, 'message', '') or '')
            shown.append((code + '：' if code else '') + message)
        text = '【警告】启动自检：' + '；'.join(shown)
        if len(unique) > 4:
            text += ' 等 %d 项' % len(unique)
        text += '；处理建议见诊断导出'
        bus.publish(Message.make('warning', text, source='selfcheck', auto=False))
    except Exception:
        app_logging.swallowed()
