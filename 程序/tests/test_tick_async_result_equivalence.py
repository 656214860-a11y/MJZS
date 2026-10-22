"""压平 AsyncTasksMixin._tick_async_result：旧实现原样内嵌，用记账宿主把各种结果都喂一遍，
逐次对照宿主上发生的调用与状态（worker、发送框、自动链标记）。"""
import queue
import unittest

import desktop_async_tasks

LEGACY_SRC = r'''def _legacy_tick_async_result(self):
    """消费主后台任务结果，并恢复相关 UI 与自动链。"""
    # 首帧的创意历史发现不属于用户操作，单独回收，绝不改变 worker 状态。
    try:
        while True:
            generation,root,apply,path,error=self._brief_load_results.get_nowait()
            if (generation==getattr(self,'_idea_brief_generation',0)
                    and root==self.root and not self.shutting_down):
                if error:self.status.set('创意历史未加载：%s；请稍后重试。' % error)
                else:apply(path)
    except queue.Empty:pass
    try:
        ticket,ok,value,done=self.q.get_nowait()
        was_active=self.background_tasks.accepts(ticket)
        if not self.background_tasks.finish(ticket, succeeded=ok, error='' if ok else str(value)) or ticket!=self._async_ticket:
            if was_active and ticket==self._async_ticket:
                self.worker=False;self.busy_state.set_busy(False)
                self.status.set('本机已停止等待；在途任务与迟到结果可在运行状况核对。')
                self._start_next_queued()
            return
        self.worker=False;self.busy_state.set_busy(False)
        if ok and done:done(value)
        elif ok:self.status.set(str(value))
        elif not ok:
            # 创意对话失败也要恢复发送框；否则一次网络错误会把唯一发送入口永久锁住。
            if getattr(self,'_idea_requesting',False):
                self.idea_chat_controller.cancel_request()
                send=getattr(self,'idea_send',None)
                if send is not None and send.winfo_exists():send.state(['!disabled'])
            self._script_agent_launching=False
            self.update_script_interrupt_button()
            self.clear_thinking()
            self.notifier.error(str(value), title='操作未完成')
        # 自动链派到结构剧本时，若恰有另一项后台工作在收尾，不能把这次
        # 暂时占用误判成永久失败。只保留一个待派发标记；当前队列清空后
        # 仍走 L3 注册器重新启动，避免在 UI 层复制派发逻辑或无限重试。
        if getattr(self, '_auto_structure_retry', False) and not self.worker:
            self._auto_structure_retry=False
            try:self.pet_start('script_structure')
            except (OSError, ValueError, KeyError, TypeError) as exc:
                self.status.set('自动恢复结构剧本暂缓：'+str(exc))
        self._start_next_queued()
    except queue.Empty:pass
'''


class _Node:
    def __init__(self, log, label, returns=None):
        self._log, self._label, self._returns = log, label, returns or {}

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)

        def call(*args, **kwargs):
            self._log.append((self._label + '.' + name, tuple('<fn>' if callable(a) else a for a in args),
                              sorted(kwargs.items())))
            value = self._returns.get(name)
            if isinstance(value, BaseException):
                raise value
            return value(*args) if callable(value) else value
        return call


class _Host:
    def __init__(self, case, method):
        self.log = []
        self.method = method
        self.root = 'R'
        self.shutting_down = case.get('shutting_down', False)
        self._idea_brief_generation = 2
        self._async_ticket = 7
        self.worker = True
        self._brief_load_results = queue.Queue()
        for item in case.get('briefs', ()):
            self._brief_load_results.put(item)
        self.q = queue.Queue()
        if 'result' in case:
            self.q.put(case['result'])
        self.background_tasks = _Node(self.log, 'tasks', {'accepts': case.get('accepts', True),
                                                          'finish': case.get('finish', True)})
        self.busy_state = _Node(self.log, 'busy')
        self.status = _Node(self.log, 'status')
        self.notifier = _Node(self.log, 'notifier')
        self.idea_chat_controller = _Node(self.log, 'idea')
        if case.get('requesting') is not None:
            self._idea_requesting = case['requesting']
        if case.get('send') is not None:
            self.idea_send = _Node(self.log, 'send', {'winfo_exists': case['send']})
        if case.get('retry'):
            self._auto_structure_retry = True
        self._pet_error = case.get('pet_error')

    def pet_start(self, stage):
        self.log.append(('pet_start', stage))
        if self._pet_error:
            raise self._pet_error

    FLAGS = ('_auto_structure_retry', '_idea_requesting', '_script_agent_launching', '_pet_error', 'idea_send')

    def __getattr__(self, name):
        if name.startswith('__') or name in self.FLAGS:
            raise AttributeError(name)
        if name == '_async_failed':   # 抽出来的失败收尾：照样跑真方法，记账的是它里面的调用
            return desktop_async_tasks.AsyncTasksMixin._async_failed.__get__(self)
        return lambda *args, **kwargs: self.log.append(('self.' + name, args, sorted(kwargs.items())))

    def state(self):
        return (self.log, self.worker, getattr(self, '_auto_structure_retry', None),
                getattr(self, '_script_agent_launching', None), self.q.qsize(), self._brief_load_results.qsize())


def _apply(log):
    return lambda path: log.append(('apply', path))


CASES = {
    'empty': {},
    'briefs': {'briefs': [(2, 'R', 'APPLY', 'p1', ''), (1, 'R', 'APPLY', 'p2', ''), (2, 'X', 'APPLY', 'p3', ''),
                          (2, 'R', 'APPLY', 'p4', '坏了')]},
    'briefs_shutting_down': {'briefs': [(2, 'R', 'APPLY', 'p1', '')], 'shutting_down': True},
    'rejected_current': {'result': (7, True, 'v', None), 'finish': False},
    'rejected_inactive': {'result': (7, True, 'v', None), 'finish': False, 'accepts': False},
    'stale_ticket': {'result': (3, True, 'v', None)},
    'ok_done': {'result': (7, True, 'v', 'DONE')},
    'ok_plain': {'result': (7, True, 'v', None)},
    'failed_plain': {'result': (7, False, RuntimeError('网断了'), None)},
    'failed_requesting_send_alive': {'result': (7, False, 'x', None), 'requesting': True, 'send': True},
    'failed_requesting_send_gone': {'result': (7, False, 'x', None), 'requesting': True, 'send': False},
    'failed_requesting_no_send': {'result': (7, False, 'x', None), 'requesting': True},
    'failed_not_requesting': {'result': (7, False, 'x', None), 'requesting': False, 'send': True},
    'retry_ok': {'result': (7, True, 'v', None), 'retry': True},
    'retry_raises': {'result': (7, False, 'x', None), 'retry': True, 'pet_error': ValueError('还在忙')},
}


class TickAsyncResultEquivalence(unittest.TestCase):
    def setUp(self):
        namespace = dict(vars(desktop_async_tasks))
        exec(compile(LEGACY_SRC, 'legacy_tick_async_result', 'exec'), namespace)
        self.legacy = namespace['_legacy_tick_async_result']

    def _run(self, case, method):
        host = _Host(case, method)
        fix = lambda item: tuple(_apply(host.log) if v == 'APPLY' else
                                 (lambda value: host.log.append(('done', value))) if v == 'DONE' else v for v in item)
        items = [fix(i) for i in host._brief_load_results.queue]
        host._brief_load_results.queue.clear()
        host._brief_load_results.queue.extend(items)
        items = [fix(i) for i in host.q.queue]
        host.q.queue.clear()
        host.q.queue.extend(items)
        method(host)
        return [repr(x) for x in host.state()], len(host.log)

    def test_every_case_matches(self):
        current = desktop_async_tasks.AsyncTasksMixin._tick_async_result
        events = 0
        for name, case in CASES.items():
            old, _ = self._run(case, self.legacy)
            new, count = self._run(case, current)
            self.assertEqual(new, old, name)
            events += count
        self.assertGreater(events, 40)   # 对照不能是空对空


if __name__ == '__main__':
    unittest.main()
