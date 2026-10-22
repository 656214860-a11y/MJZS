"""压平 App.tick：旧实现原样内嵌，用记账宿主把各种消息、结果、到期时刻都喂一遍，
逐次对照宿主上发生的调用与状态。"""
import queue
import tkinter as tk
import unittest
from unittest import mock

import app

LEGACY_SRC = r'''def _legacy_tick(self):
    # Keep network tracking alive even when its panel is hidden or a UI refresh fails.
    if self.closed:return
    try:
        while not self.local_messages.empty():
            sid,text=self.local_messages.get_nowait()
            selection=self.tree.selection()
            if selection and selection[0]==sid:self.progress_text.set(sid+' · '+text)
            else:self.write('后台任务 '+sid+' · '+text)
        try:ok,value=self.results.get_nowait()
        except queue.Empty:pass
        else:
            self.busy=False;self.submitting_sid=None
            if self.local_submit_sid:
                if not ok:self.local_submit_error[self.local_submit_sid]=str(value)
                self.local_submit_sid=None
            callback=getattr(self,'on_success',None);self.on_success=None
            if ok and callback:
                try:callback(value)
                except Exception as exc:self.write('成片目录打开失败：'+str(exc))
            self.next_poll=(max(time.monotonic(),getattr(self,'poll_started',0)+self.poll_wait) if self.quiet_run else time.monotonic()) if ok else time.monotonic()+30
            phase='write_result'
            try:
                if not (ok and self.quiet_run and self.last_poll_messages.get(self.polling_sid)==str(value)):self.write(str(value))
                if ok and self.quiet_run:self.last_poll_messages[self.polling_sid]=str(value)
                # 第 47 期第 5 条：手动／批量提交收了尾就说一句；后台轮询的进度不报（太吵）。
                phase='report_done'
                if ok and not self.quiet_run:self.report_done(value)
                phase='window_state'
                if self.window.winfo_ismapped():
                    phase='refresh'
                    self.refresh()
                    phase='update_progress'
                    self.update_progress()
                phase='failure_notice'
                if not ok:
                    if self.quiet_run:
                        self.write('后台查询或下载暂时中断，30秒后自动重试；不会重新提交生成。')
                    elif self.window.winfo_ismapped():
                        self.notifier.error(str(value), title='操作未完成')
            except Exception as exc:
                # Results/task IDs are persisted by the engine; rendering must not stop polling.
                self._record_result_render_failure(exc,phase)
        if time.monotonic()>=self.next_ui_update:
            self.next_ui_update=time.monotonic()+1
            try:
                self.update_prompt_controls()
                if self.window.winfo_ismapped():
                    self.update_progress();self.refresh_shared_progress()
            except (tk.TclError,ValueError,OSError):pass
        try:self.prompt_results.poll(self)
        except (OSError,ValueError):pass  # Project temporarily locked; retry next poll.
        if time.monotonic()>=self.auto_submit_due:
            self.auto_submit_due=time.monotonic()+5
            try:self.auto_submit_scan()
            except Exception as exc:
                try:self.write('无人值守自动提交检查失败：'+str(exc))
                except tk.TclError:pass
        try:self.auto_poll()
        except Exception as exc:
            self.next_poll=time.monotonic()+30
            try:self.write('后台跟踪暂时异常，30秒后重试查询，不会重新提交生成：'+str(exc))
            except tk.TclError:pass
    finally:
        if not self.closed:
            try:
                if self.window.winfo_exists():self.timer=self.scheduler.after(150,self.tick)
            except tk.TclError:
                # Tk 可能在存活检查或注册下一次回调时已退出。
                pass
'''


class _Node:
    def __init__(self, log, label, returns=None):
        self._log, self._label, self._returns = log, label, returns or {}

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)

        def call(*args, **kwargs):
            self._log.append((self._label + '.' + name, tuple('<host>' if isinstance(a, _Host) else '<fn>' if callable(a) else a for a in args),
                              sorted(kwargs.items())))
            value = self._returns.get(name)
            if isinstance(value, BaseException):
                raise value
            return value
        return call


class _Host:
    FLAGS = ('on_success', 'poll_started', 'next_poll')
    REAL = ('_tick_result', '_tick_messages', '_tick_periodic', '_tick_reschedule')

    def __init__(self, case):
        self.log = []
        self.case = case
        self.closed = case.get('closed', False)
        self.local_messages = queue.Queue()
        for item in case.get('messages', ()):
            self.local_messages.put(item)
        self.results = queue.Queue()
        if 'result' in case:
            self.results.put(case['result'])
        self.tree = _Node(self.log, 'tree', {'selection': case.get('selection', ())})
        self.progress_text = _Node(self.log, 'progress_text')
        self.busy = True
        self.submitting_sid = 'S'
        self.local_submit_sid = case.get('local_sid')
        self.local_submit_error = {}
        if case.get('callback'):
            self.on_success = self._callback
        self.poll_wait = 4
        if 'poll_started' in case:
            self.poll_started = case['poll_started']
        self.quiet_run = case.get('quiet', False)
        self.last_poll_messages = dict(case.get('last', {}))
        self.polling_sid = 'P'
        self.window = _Node(self.log, 'window', {'winfo_ismapped': case.get('mapped', True),
                                                'winfo_exists': case.get('exists', True)})
        self.notifier = _Node(self.log, 'notifier')
        self.next_ui_update = case.get('ui_due', 0)
        self.auto_submit_due = case.get('submit_due', 0)
        self.prompt_results = _Node(self.log, 'prompt_results', {'poll': case.get('prompt_poll')})
        self.scheduler = _Node(self.log, 'scheduler', {'after': case.get('after', 'T')})
        self.timer = None

    def _callback(self, value):
        self.log.append(('callback', value))
        if self.case.get('callback') == 'raise':
            raise OSError('打不开')

    def __getattr__(self, name):
        if name.startswith('__') or name in self.FLAGS:
            raise AttributeError(name)
        if name in self.REAL and hasattr(app.App, name):   # 抽出来的辅助方法照样跑真的
            return getattr(app.App, name).__get__(self)

        def call(*args, **kwargs):
            self.log.append(('self.' + name, tuple('<fn>' if callable(a) else repr(a) for a in args)))
            error = self.case.get('raise', {}).get(name)
            if error is not None:
                raise error
        return call

    def state(self):
        return (self.log, self.busy, self.submitting_sid, self.local_submit_sid, self.local_submit_error,
                getattr(self, 'on_success', 'unset'), getattr(self, 'next_poll', None),
                self.last_poll_messages, self.next_ui_update, self.auto_submit_due, self.timer,
                self.local_messages.qsize(), self.results.qsize())


CASES = {
    'closed': {'closed': True, 'result': (True, 'v')},
    'idle': {'ui_due': 999, 'submit_due': 999},
    'messages': {'messages': [('A', '一'), ('B', '二')], 'selection': ('A',)},
    'messages_no_selection': {'messages': [('A', '一')]},
    'ok_plain': {'result': (True, 'v')},
    'ok_callback': {'result': (True, 'v'), 'callback': True},
    'ok_callback_raises': {'result': (True, 'v'), 'callback': 'raise'},
    'ok_quiet_new': {'result': (True, 'v'), 'quiet': True, 'poll_started': 150},
    'ok_quiet_same': {'result': (True, 'v'), 'quiet': True, 'last': {'P': 'v'}},
    'ok_unmapped': {'result': (True, 'v'), 'mapped': False},
    'failed_local': {'result': (False, RuntimeError('坏')), 'local_sid': 'L'},
    'ok_local': {'result': (True, 'v'), 'local_sid': 'L'},
    'failed_quiet': {'result': (False, 'x'), 'quiet': True},
    'failed_mapped': {'result': (False, 'x')},
    'failed_unmapped': {'result': (False, 'x'), 'mapped': False},
    'render_raises': {'result': (True, 'v'), 'raise': {'refresh': ValueError('炸')}},
    'report_raises': {'result': (True, 'v'), 'raise': {'report_done': KeyError('k')}},
    'ui_tick_tcl': {'raise': {'update_prompt_controls': tk.TclError('t')}},
    'ui_tick_runtime_escapes': {'raise': {'update_prompt_controls': RuntimeError('漏')}},
    'ui_tick_unmapped': {'mapped': False},
    'prompt_poll_oserror': {'prompt_poll': OSError('锁')},
    'submit_scan_raises': {'raise': {'auto_submit_scan': RuntimeError('扫')}},
    'auto_poll_raises': {'raise': {'auto_poll': RuntimeError('查')}},
    'auto_poll_raises_write_tcl': {'raise': {'auto_poll': RuntimeError('查'), 'write': tk.TclError('w')}},
    'window_gone': {'exists': False},
    'after_tcl': {'after': tk.TclError('退出')},
}


class TickEquivalence(unittest.TestCase):
    def setUp(self):
        namespace = dict(vars(app))
        exec(compile(LEGACY_SRC, 'legacy_tick', 'exec'), namespace)
        self.legacy = namespace['_legacy_tick']

    def _run(self, case, method):
        host = _Host(case)
        with mock.patch.object(app.time, 'monotonic', return_value=100.0):
            try:
                method(host)
            except Exception as exc:   # 逃逸的异常也要一致
                host.log.append(('escaped', type(exc).__name__, str(exc)))
        return [repr(x) for x in host.state()], len(host.log)

    def test_every_case_matches(self):
        events = 0
        for name, case in CASES.items():
            old, _ = self._run(case, self.legacy)
            new, count = self._run(case, app.App.tick)
            self.assertEqual(new, old, name)
            events += count
        self.assertGreater(events, 80)   # 对照不能是空对空


if __name__ == '__main__':
    unittest.main()
