"""无 Tk 的桌面自动流程调度器。

桌面只注入 ``after`` / ``after_cancel`` 与阶段轮询回调；本模块统一周期任务
的重排、取消、异常兜底，以及各自动流程的到期轮询判断。
"""
import time
from collections import deque

import app_logging


# 后台任务生命周期的唯一迁移清单。每一项都必须证明同一代次覆盖提交、替换、
# 取消、成功、失败和迟到交付拒绝；含连续进度消息的入口还必须把进度与最终结果
# 绑定到同一 ticket。状态只记录已落地的事实，待迁移项不得借清单宣称已收口。
HISTORY_LIMIT = 20
QUEUE_LIMIT = 10


BACKGROUND_TASK_MIGRATION = (
    {'entry': 'Desktop.async_', 'category': 'final-result', 'state': 'migrated'},
    {'entry': 'auto_edit', 'category': 'final-result', 'state': 'migrated'},
    {'entry': 'auto_handoff', 'category': 'final-result', 'state': 'migrated'},
    {'entry': 'auto_video', 'category': 'progress-and-result', 'state': 'migrated'},
    {'entry': 'auto_asset', 'category': 'progress-and-result', 'state': 'migrated'},
    {'entry': 'auto_keyframe', 'category': 'progress-and-result', 'state': 'migrated'},
    {'entry': 'previs_jobs', 'category': 'special-process', 'state': 'migrated'},
    {'entry': 'cloud_monitor', 'category': 'cross-page-monitor', 'state': 'migrated'},
)


class DesktopAutomationScheduler:
    """管理桌面拥有的周期回调，不持有窗口或阶段状态。"""

    def __init__(self, *, schedule_after, cancel_scheduled, is_stopping):
        self._schedule_after = schedule_after
        self._cancel_scheduled = cancel_scheduled
        self._is_stopping = is_stopping
        self._tasks = {}

    def start(self, name, interval_ms, callback, *, on_error, remember_timer):
        self.cancel(name)
        self._tasks[name] = {
            'interval_ms': interval_ms,
            'callback': callback,
            'on_error': on_error,
            'remember_timer': remember_timer,
            'timer': None,
        }
        self._schedule(name)

    def cancel(self, name):
        task = self._tasks.pop(name, None)
        if task is None:
            return
        timer = task['timer']
        if timer:
            try:
                self._cancel_scheduled(timer)
            except Exception:
                app_logging.swallowed()
        task['remember_timer'](None)

    def cancel_all(self):
        for name in tuple(self._tasks):
            self.cancel(name)

    def run_due(self, *, now, due_at, delay_seconds, allowed, set_due, poll,
                on_error, handled_exceptions):
        """到期且允许时才轮询；先推进下次到期时间，失败也保留节流。"""
        if not allowed() or now < due_at():
            return False
        set_due(now + delay_seconds)
        try:
            poll()
        except handled_exceptions as exc:
            on_error(exc)
            return False
        return True

    def _schedule(self, name):
        task = self._tasks.get(name)
        if task is None or self._is_stopping():
            return
        timer = self._schedule_after(task['interval_ms'], lambda: self._run(name))
        task['timer'] = timer
        task['remember_timer'](timer)

    def _run(self, name):
        task = self._tasks.get(name)
        if task is None:
            return
        task['timer'] = None
        task['remember_timer'](None)
        try:
            task['callback']()
        except Exception as exc:
            task['on_error'](exc)
        finally:
            if name in self._tasks:
                self._schedule(name)


# 迟到结果登记的条数上限（取消说明的三态记录同样有界）。
LATE_RESULT_LIMIT = 8


class BackgroundTaskQueue:
    """后台忙时的排队清单（先进先出，有上限）。

    只存放“互相独立、可以晚点再做”的主动任务；前一项失败不会取消后一项。破坏性或依赖当前
    界面状态的操作不要排队，仍走原来的“请稍候”拦截。本类不持有 Tk，也不自己启动任务。
    """

    def __init__(self, limit=QUEUE_LIMIT):
        self._limit = limit
        self._items = deque()

    def enqueue(self, fn, done=None, label='', show_progress=True, retryable=False):
        if len(self._items) >= self._limit:
            raise ValueError('排队任务已满（最多 %d 个），请等当前任务结束' % self._limit)
        self._items.append({'fn': fn, 'done': done, 'label': str(label or ''), 'show_progress': bool(show_progress),
                            'retryable': bool(retryable)})
        return len(self._items)

    def pop(self):
        return self._items.popleft() if self._items else None

    def labels(self):
        return [item['label'] for item in self._items]

    def clear(self):
        self._items.clear()


class RetryRegistry:
    """可重试任务的登记：只有调用方声明“只读／幂等”的任务才登记，失败后由用户手动重试。

    登记的是重新发起所需的 (fn, done, label, show_progress)，按序号保存，最多保留
    ``HISTORY_LIMIT`` 条。**不做自动重试**：付费生成类请求重复提交会重复计费。
    """

    def __init__(self):
        self._specs = {}

    def remember(self, ticket, spec):
        self._specs[ticket] = tuple(spec)
        for old in list(self._specs)[:-HISTORY_LIMIT]:
            del self._specs[old]

    def tickets(self):
        return set(self._specs)

    def latest_failed_ticket(self, history):
        for row in reversed(history):
            if row.get('state') == 'failed' and row.get('ticket') in self._specs:
                return row['ticket']
        return None

    def take_latest_failed(self, history):
        """取出（并删除）最近一次失败且可重试任务的登记；没有返回 None。"""
        ticket = self.latest_failed_ticket(history)
        return self._specs.pop(ticket) if ticket is not None else None


class BackgroundTaskLifecycle:
    """桌面单一主动后台任务的代次、取消与收尾判定。

    任意线程都可能在逻辑取消后才返回；本对象不尝试强杀 Python 线程，
    而是让主线程只接纳当前代次的结果，避免关闭窗口或中断请求后触发迟到 UI 回调。
    """

    def __init__(self):
        self._active_ticket = None
        self._seen = []
        self._facts = None
        self._cancel = None
        self._late = []
        self._last = None
        self._started = None
        self._history = deque(maxlen=HISTORY_LIMIT)

    def _record(self, ticket, state, error=''):
        """把已结束的一次任务记进最近历史（只留 ``HISTORY_LIMIT`` 条，供运行状况面板读取）。"""
        started = self._started or {}
        self._history.append({'ticket': ticket, 'state': state, 'label': started.get('label', ''),
                              'error': app_logging.redact(error)[:200] if error else '',
                              'elapsed_s': round(time.monotonic() - started['at'], 1) if 'at' in started else None})
        self._started = None

    def history(self):
        return list(self._history)

    def submit(self, ticket, *, remote_task_id=None, costly=False, label=''):
        """登记当前代次；有成本或远端任务同时记下可查询编号，供取消时说明。"""
        self.cancel()
        self._started = {'at': time.monotonic(), 'label': str(label or '')}
        self._active_ticket = ticket
        self._facts = {'remote_task_id': (str(remote_task_id) if remote_task_id else None),
                       'costly': bool(costly)}
        self._seen.append(ticket)
        del self._seen[:-LATE_RESULT_LIMIT]
        self._last = {'ticket': ticket, 'state': 'running'}
        return ticket

    def accepts(self, ticket):
        return self._active_ticket == ticket

    def finish(self, ticket, *, succeeded, error=''):
        if not self.accepts(ticket):
            # 迟到的结果既不进界面，也不被静默丢弃：留一条可查询的隔离登记。
            self._record_late(ticket, succeeded)
            return False
        self._active_ticket = None
        self._facts = None
        self._last = {'ticket': ticket, 'state': 'succeeded' if succeeded else 'failed'}
        self._record(ticket, self._last['state'], error)
        return True

    def cancel(self, ticket=None, *, costly=False, remote_task_id=None,
               remote_cancel_requested=False, remote_cancel_confirmed=False):
        """取消只代表本机停止等待；远端是否已停、是否计费须由调用方核对后再声明。"""
        if self._active_ticket is None or (ticket is not None and ticket != self._active_ticket):
            return False
        cancelled = self._active_ticket
        facts = self._facts or {}
        remote = str(remote_task_id) if remote_task_id else facts.get('remote_task_id')
        costs = bool(costly or facts.get('costly') or remote)
        self._active_ticket = None
        self._facts = None
        self._last = {'ticket': cancelled, 'state': 'cancelled'}
        self._record(cancelled, 'cancelled')
        if costs or remote_cancel_requested or remote_cancel_confirmed:
            self._cancel = {'ticket': cancelled, 'remote_task_id': remote, 'costly': costs,
                            'remote_cancel_requested': bool(remote_cancel_requested),
                            'remote_cancel_confirmed': bool(remote_cancel_confirmed)}
        return True

    def cancellation_status(self, ticket=None):
        """把取消说成可核对的事实，而不是一句「已取消」。

        返回本机状态、远端三态（confirmed 已确认／pending 已请求未确认／
        not-requested 未请求／unknown 未知）、可查询编号，以及给界面直接用的说明
        文字；没有成本或远端信息时返回 None（普通任务保持旧的取消语义）。
        """
        record = self._cancel
        if record is None or (ticket is not None and ticket != record['ticket']):
            return None
        if record['remote_cancel_confirmed']:
            remote = 'confirmed'
        elif record['remote_cancel_requested']:
            remote = 'pending'
        elif record['remote_task_id']:
            remote = 'not-requested'
        else:
            remote = 'unknown'
        parts = ['本机已停止等待这一批结果。']
        if remote == 'confirmed':
            parts.append('远端取消已确认。')
        elif remote == 'pending':
            parts.append('已请求远端取消，尚未收到远端确认；远端仍可能继续执行。')
        elif remote == 'not-requested':
            parts.append('未向远端发出取消请求；远端仍可能继续执行。')
        else:
            parts.append('未登记远端任务编号，无法确认远端状态；远端仍可能继续执行。')
        if record['costly'] and remote != 'confirmed':
            parts.append('远端确认前不能当作未计费，最终用量以远端账单为准。')
        ids = ['本机批次 ' + str(record['ticket'])]
        if record['remote_task_id']:
            ids.append('远端任务 ' + str(record['remote_task_id']))
        parts.append('可查询编号：' + '、'.join(ids) + '。')
        return dict(record, local='stopped', remote=remote, text=''.join(parts))

    def late_results(self):
        """被拒绝的迟到结果登记；既不进界面，也不被静默丢弃。"""
        return [dict(item) for item in self._late]

    def snapshot(self):
        return dict(self._last) if self._last is not None else None

    def _record_late(self, ticket, succeeded):
        if ticket not in self._seen:
            return
        self._late.append({'ticket': ticket, 'succeeded': bool(succeeded)})
        del self._late[:-LATE_RESULT_LIMIT]
