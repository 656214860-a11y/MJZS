"""无 Tk 的桌面自动流程调度器。

桌面只注入 ``after`` / ``after_cancel`` 与阶段轮询回调；本模块统一周期任务
的重排、取消、异常兜底，以及各自动流程的到期轮询判断。
"""
import time
from collections import deque

import infra.app_logging as app_logging


# 后台任务生命周期的唯一迁移清单。每一项都必须证明同一代次覆盖提交、替换、
# 取消、成功、失败和迟到交付拒绝；含连续进度消息的入口还必须把进度与最终结果
# 绑定到同一 ticket。状态只记录已落地的事实，待迁移项不得借清单宣称已收口。
HISTORY_LIMIT = 20
QUEUE_LIMIT = 10
# 排队满的错误提示只留一份（enqueue 带计数变体、两个落盘入口共用无计数版）。
QUEUE_FULL_TEXT = '排队任务已满，请等当前任务结束'


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


def _read_runtime_record(path):
    """读本机后台排队／执行记录；读不出的坏文件改名留存，按空记录重建。

    这两份记录只加锁、原子替换，不等落盘（``save(..., durable=False)``），断电后可能读出全零
    或半份。这时把原文件改名为 ``<名>.corrupt`` 留给排查，返回空记录，不让一份坏文件挡住所有
    后台操作；读得出但版本或结构不对的，仍由调用方报错、不覆盖。调用方须持有
    ``agent.publication.access()``。
    """
    from pathlib import Path
    from agent.core import read, replace
    path = Path(path)
    if not path.exists():
        return {'version': 1, 'tasks': []}
    try:
        return read(path)
    except ValueError:
        corrupt = path.with_name(path.name + '.corrupt')
        try:
            replace(path, corrupt)
        except OSError:
            app_logging.swallowed('后台记录读不出，改名留存失败，按空记录继续')
        else:
            app_logging.swallowed('后台记录读不出，已改名为 %s，按空记录重建' % corrupt.name)
        return {'version': 1, 'tasks': []}


class PersistentBackgroundTaskQueue(BackgroundTaskQueue):
    """描述符落盘；领取先于执行，未知在途任务只登记、不自动重提。"""

    def __init__(self, path, *, handlers, clock=time.time, aging_seconds=60, limit=QUEUE_LIMIT):
        super().__init__(limit)
        from pathlib import Path
        self.path = Path(path)
        self.handlers = dict(handlers)
        self.clock = clock
        self.aging_seconds = max(1, aging_seconds)

    def _load(self):
        data = _read_runtime_record(self.path)
        if data.get('version') != 1 or not isinstance(data.get('tasks'), list):
            raise ValueError('排队记录损坏，未重建或重提任务')
        return data

    def _save(self, data):
        from agent.core import save
        active = [row for row in data['tasks'] if row['state'] in ('queued', 'claimed')]
        history = [row for row in data['tasks'] if row['state'] not in ('queued', 'claimed')]
        data['tasks'] = active + history[-HISTORY_LIMIT:]
        save(self.path, data, durable=False)

    def _expire(self, data):
        changed = False
        for row in data['tasks']:
            if row['state'] == 'queued' and row.get('expires_at') is not None and self.clock() >= row['expires_at']:
                row['state'] = 'expired'
                changed = True
        return changed

    def _key(self, row):
        age = max(0, self.clock() - row['created']) // self.aging_seconds
        return (-row['priority'] - age, row['created'])

    def enqueue(self, fn, done=None, label='', show_progress=True, retryable=False, *, priority=0):
        from agent.publication import access
        priority = int(priority)
        with access():
            data = self._load()
            if self._expire(data):
                self._save(data)
            if len(self._items) + sum(row['state'] == 'queued' for row in data['tasks']) >= self._limit:
                raise ValueError(QUEUE_FULL_TEXT)
            super().enqueue(fn, done, label, show_progress, retryable)
            self._items[-1].update(priority=priority, created=self.clock())
            return len(self.labels())

    def enqueue_descriptor(self, kind, payload, *, label='', priority=0, expires_at=None):
        import json
        import math
        import uuid
        from agent.publication import access
        if kind not in self.handlers:
            raise ValueError('未注册的可恢复任务类型：' + str(kind))
        if expires_at is not None and (not isinstance(expires_at, (int, float)) or not math.isfinite(expires_at)):
            raise ValueError('任务过期时间必须是有限时间戳')
        # Deep-copy only JSON data; callbacks and live UI objects never reach disk.
        payload = json.loads(json.dumps(payload, allow_nan=False))
        if not isinstance(payload, dict):
            raise TypeError('可恢复任务参数必须是对象')
        row = {'id': uuid.uuid4().hex, 'kind': kind, 'payload': payload, 'label': str(label),
               'priority': int(priority), 'created': self.clock(), 'expires_at': expires_at, 'state': 'queued'}
        with access():
            data = self._load()
            self._expire(data)
            if len(self._items) + sum(item['state'] == 'queued' for item in data['tasks']) >= self._limit:
                raise ValueError(QUEUE_FULL_TEXT)
            data['tasks'].append(row)
            self._save(data)
        return row['id']

    def _finish(self, task_id, state):
        from agent.publication import access
        with access():
            data = self._load()
            for row in data['tasks']:
                if row['id'] == task_id and row['state'] == 'claimed':
                    row['state'] = state
                    self._save(data)
                    return

    def pop(self):
        from agent.publication import access
        with access():
            data = self._load()
            changed = self._expire(data)
            choices = list(self._items) + [row for row in data['tasks'] if row['state'] == 'queued']
            if not choices:
                if changed: self._save(data)
                return None
            row = min(choices, key=self._key)
            if 'fn' in row:
                self._items.remove(row)
                if changed: self._save(data)
                return row
            row['state'] = 'claimed'
            self._save(data)
        def run():
            try:
                handler = self.handlers.get(row['kind'])
                if handler is None:
                    raise ValueError('恢复任务类型不可用：' + row['kind'])
                result = handler(row['payload'])
            except Exception:
                # A handler may have submitted remotely before its exception.
                # Keep the durable claim for reconciliation; never auto-retry it.
                raise
            self._finish(row['id'], 'completed')
            return result
        return {'fn': run, 'done': None, 'label': row['label'], 'show_progress': True,
                'retryable': False, 'task_id': row['id']}

    def labels(self):
        from agent.publication import access
        with access():
            rows = list(self._items) + [row for row in self._load()['tasks'] if row['state'] == 'queued'
                and (row.get('expires_at') is None or row['expires_at'] > self.clock())]
            return [row['label'] for row in sorted(rows, key=self._key)]

    def unresolved(self):
        from agent.publication import access
        with access():
            return [dict(row) for row in self._load()['tasks'] if row['state'] == 'claimed']

    def cancel(self, task_id):
        from agent.publication import access
        with access():
            data = self._load()
            for row in data['tasks']:
                if row['id'] == task_id and row['state'] == 'queued':
                    row['state'] = 'cancelled'
                    self._save(data)
                    return True
        return False

    def clear(self):
        from agent.publication import access
        with access():
            data = self._load()
            for row in data['tasks']:
                if row['state'] == 'queued': row['state'] = 'cancelled'
            self._save(data)
            super().clear()


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

    def __init__(self, path=None):
        self._active_ticket = None
        import uuid
        self._path = path
        self._session = uuid.uuid4().hex
        self._controls = {}
        self._seen = []
        self._facts = None
        self._cancel = None
        self._late = []
        self._last = None
        self._started = None
        self._history = deque(maxlen=HISTORY_LIMIT)

    def _persist(self, ticket, **facts):
        if self._path is None:
            return
        from agent.core import save
        from agent.publication import access
        with access():
            data = _read_runtime_record(self._path)
            if data.get('version') != 1 or not isinstance(data.get('tasks'), list):
                raise ValueError('后台执行记录损坏，无法覆盖')
            key = self._session + ':' + str(ticket)
            row = next((row for row in data['tasks'] if row['id'] == key), None)
            if row is None:
                row = {'id': key, 'ticket': ticket, 'created': time.time()}
                data['tasks'].append(row)
            if row.get('state') == 'late' and facts.get('state') in ('cancelled', 'stopped'):
                facts.pop('state')
            if facts.get('event') == 'remote' and facts.get('remote_task_id'):
                remote = {'id': facts['remote_task_id'], 'provider': facts.get('provider', '')}
                remotes = row.setdefault('remote_tasks', [])
                if remote not in remotes:
                    remotes.append(remote)
            if row.get('remote_task_id') and not facts.get('remote_task_id'):
                facts.pop('remote_task_id', None)
            if row.get('costly'):
                facts.pop('costly', None)
            if row.get('remote_tasks') and facts.get('state') in ('succeeded', 'failed'):
                facts['local_outcome'] = facts['state']
                facts['state'] = 'reconcile'
            if facts.get('event') == 'late':
                row.setdefault('late_units', []).append({
                    'stage': facts.get('stage'), 'unit': app_logging.redact(str(facts.get('unit', '')))[:200],
                    'succeeded': facts.get('succeeded')})
                facts['state'] = 'late'
                facts.pop('unit', None)
            row.update(facts)
            row['updated'] = time.time()
            unresolved = [row for row in data['tasks'] if row.get('state') not in ('succeeded', 'failed')]
            history = [row for row in data['tasks'] if row.get('state') in ('succeeded', 'failed')]
            data['tasks'] = unresolved + history[-HISTORY_LIMIT:]
            save(self._path, data, durable=False)

    def unresolved_records(self):
        if self._path is None:
            return []
        from agent.publication import access
        with access():
            data = _read_runtime_record(self._path)
            return [dict(row) for row in data['tasks'] if row.get('state') not in ('succeeded', 'failed')]

    def execution_control(self, ticket):
        return self._controls[ticket]

    def run(self, ticket, fn):
        import threading
        from contract.platform_tools import execution_scope, ExecutionStopped
        control = self.execution_control(ticket)
        finished, lock = threading.Event(), threading.Lock()
        result, stopped = [], [False]
        def work():
            value, error = None, None
            try:
                with execution_scope(control):
                    control.checkpoint()
                    value = fn()
            except Exception as exc:
                error = exc
            with lock:
                result[:] = [value, error]
                late = stopped[0]
                finished.set()
            if late:
                self._persist(ticket, state='late', succeeded=error is None)
        threading.Thread(target=work, daemon=True).start()
        while not finished.wait(.02):
            try:
                control.checkpoint()
            except ExecutionStopped as exc:
                with lock:
                    stopped[0] = True
                    already_finished = finished.is_set()
                self._persist(ticket, state='stopped', reason=exc.reason)
                if already_finished:
                    self._persist(ticket, state='late', succeeded=result[1] is None)
                raise ExecutionStopped(exc.reason, started=True) from exc
        if result[1] is not None:
            raise result[1]
        return result[0]

    def _record(self, ticket, state, error=''):
        """把已结束的一次任务记进最近历史（只留 ``HISTORY_LIMIT`` 条，供运行状况面板读取）。"""
        started = self._started or {}
        self._history.append({'ticket': ticket, 'state': state, 'label': started.get('label', ''),
                              'error': app_logging.redact(error)[:200] if error else '',
                              'elapsed_s': round(time.monotonic() - started['at'], 1) if 'at' in started else None})
        self._started = None

    def history(self):
        return list(self._history)

    def submit(self, ticket, *, remote_task_id=None, costly=False, label='', timeout=3600, project=None):
        """登记当前代次；有成本或远端任务同时记下可查询编号，供取消时说明。"""
        from pathlib import Path
        self.cancel()
        from contract.platform_tools import ExecutionControl
        self._controls[ticket] = ExecutionControl(timeout, observer=lambda facts: self._persist(ticket, **facts))
        for old in list(self._controls)[:-LATE_RESULT_LIMIT]:
            del self._controls[old]
        self._started = {'at': time.monotonic(), 'label': str(label or '')}
        self._active_ticket = ticket
        self._facts = {'remote_task_id': (str(remote_task_id) if remote_task_id else None),
                       'costly': bool(costly)}
        self._seen.append(ticket)
        del self._seen[:-LATE_RESULT_LIMIT]
        self._last = {'ticket': ticket, 'state': 'running'}
        self._persist(ticket, state='running', label=app_logging.redact(str(label or '')),
                      run_id=self._controls[ticket].run_id,
                      project=str(Path(project).resolve()) if project is not None else None,
                      remote_task_id=self._facts['remote_task_id'], costly=self._facts['costly'])
        return ticket

    def accepts(self, ticket):
        return self._active_ticket == ticket

    def finish(self, ticket, *, succeeded, error='', on_stopped=None):
        if not self.accepts(ticket):
            # 迟到的结果既不进界面，也不被静默丢弃：留一条可查询的隔离登记。
            self._record_late(ticket, succeeded)
            return False
        from contract.platform_tools import ExecutionStopped
        try:
            self.execution_control(ticket).checkpoint()
        except ExecutionStopped as exc:
            self.cancel(ticket)
            self._persist(ticket, state='stopped', reason=exc.reason)
            if on_stopped is not None:
                on_stopped()
            return False
        self._active_ticket = None
        self._facts = None
        self._last = {'ticket': ticket, 'state': 'succeeded' if succeeded else 'failed'}
        self._record(ticket, self._last['state'], error)
        self._persist(ticket, state=self._last['state'], error=app_logging.redact(str(error))[:200])
        return True

    def cancel(self, ticket=None, *, costly=False, remote_task_id=None,
               remote_cancel_requested=False, remote_cancel_confirmed=False):
        """取消只代表本机停止等待；远端是否已停、是否计费须由调用方核对后再声明。"""
        if self._active_ticket is None or (ticket is not None and ticket != self._active_ticket):
            return False
        cancelled = self._active_ticket
        self._controls[cancelled].cancel()
        facts = self._facts or {}
        remote = str(remote_task_id) if remote_task_id else facts.get('remote_task_id')
        costs = bool(costly or facts.get('costly') or remote)
        self._active_ticket = None
        self._facts = None
        self._last = {'ticket': cancelled, 'state': 'cancelled'}
        self._record(cancelled, 'cancelled')
        self._persist(cancelled, state='cancelled', remote_task_id=remote, costly=costs,
                      remote_cancel_requested=bool(remote_cancel_requested),
                      remote_cancel_confirmed=bool(remote_cancel_confirmed))
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
        self._persist(ticket, state='late', succeeded=bool(succeeded))
        del self._late[:-LATE_RESULT_LIMIT]


def inspect_project_storage(payload):
    """可恢复的只读盘点：只保存项目路径，不捕获窗口或当前项目。"""
    from pathlib import Path
    from infra.storage_maintenance import storage_summary
    from orchestrator.engine import adopted_edit_version
    if set(payload) != {'root'} or not isinstance(payload['root'], str):
        raise ValueError('存储盘点参数无效')
    root = Path(payload['root'])
    if not root.is_absolute() or not root.is_dir():
        raise ValueError('存储盘点项目目录不存在')
    report = storage_summary(root, select_adopted=adopted_edit_version)
    sizes = report['bytes']
    lines = ['存储盘点（只读）', str(root)]
    for key, title in (('protected', '来源声明及明确引用文件'), ('unclassified', '其他文件（未证明可清理）'), ('recycled', '回收站（仍占磁盘）')):
        lines.append('%s：%.2f MiB' % (title, sizes[key] / 1048576))
    lines.append('旧生成版本保留期：%s天；采用、成片引用、未结算和锁定版本保留。' % (report['retention_days'] or '配置无效'))
    for key, title in (('adopted_bytes', '当前采用版本'), ('other_version_bytes', '其余生成版本'), ('recyclable_bytes', '可回收旧生成版本')):
        value = report[key]
        lines.append('%s：%s' % (title, '未知' if value is None else '%.2f MiB' % (value / 1048576)))
    lines.append('同盘可恢复回收立即释放：0 MiB；保留期可在项目 storage_policy.json 的 retention_days 配置。')
    for row in report['versions'][:50]:
        lines.append('%s v%s：%.2f MiB，%s，%s' % (row['shot'], row['version'], row['bytes'] / 1048576,
                     '当前采用' if row.get('adopted') else '未采用', row['reason']))
    if len(report['versions']) > 50:
        lines.append('另有%d个版本，以上总量包含全部版本。' % (len(report['versions']) - 50))
    lines.append('项目首页可恢复回收站内容；本操作不移动或删除文件。')
    if report['errors']:
        lines.append('盘点不完整／自动清理阻断：' + '；'.join(report['errors'][:5]))
    return '\n'.join(lines)
