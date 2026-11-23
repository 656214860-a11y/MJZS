# -*- coding: utf-8 -*-
"""第 47 期第 6／7 条：强制定位到真进程，程序关得掉。

用户报的是「点了停止还在制作」「关不掉程序」。这两条链路的自检：

* 第 6 条：qwen_adapter.run_background 原来走 subprocess.run，不进引擎台账，「强制停止制作」
  找不到它；现在跟其它引擎同一套（Popen ＋ register_process／forget_process）。
* 第 7 条：有活儿在跑时关窗不再是一句「请等待」，而是问一句「要强制关闭吗」；答「是」就把
  还在跑的引擎进程与白模批次收掉再退，白模那个浏览器监视页也跟着收。

桌面那几条不建真窗口：直接拿替身对象调 Desktop 的方法（close／force_quit／finish_close 只碰
几个字段和两个模块级函数），替身够了。

运行：python test_force_quit.py
"""
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)


class FakeQwen:
    """假 Popen：把响应写进 stdout 那个文件，并按顺序记下这次对话。"""

    made = []
    events = []
    returncode = 0
    response = [{'type': 'result', 'subtype': 'success', 'result': '白模做好啦'}]
    raw_response = None

    def __init__(self, args, **kwargs):
        self.args = list(args); self.kwargs = kwargs; self.pid = 4242
        self.returncode = FakeQwen.returncode
        FakeQwen.made.append(self)

    def communicate(self, prompt=None, timeout=None):
        FakeQwen.events.append(('对话', prompt))
        self.kwargs['stdout'].write(FakeQwen.raw_response if FakeQwen.raw_response is not None
                                    else json.dumps(FakeQwen.response, ensure_ascii=False))
        return '', ''


class BackgroundProcessTests(unittest.TestCase):
    """run_background：这一趟也进台账，成不成都要销号。"""

    def setUp(self):
        import qwen_setup
        from orchestrator import qwen_adapter
        from infra import workflow_process_registry
        self.adapter = qwen_adapter
        FakeQwen.made = []; FakeQwen.events = []; FakeQwen.returncode = 0
        FakeQwen.response = [{'type': 'result', 'subtype': 'success', 'result': '白模做好啦'}]
        FakeQwen.raw_response = None
        self.stub(workflow_process_registry, 'register_process',
                  lambda project, process: FakeQwen.events.append(('登记', process)))
        self.stub(workflow_process_registry, 'forget_process',
                  lambda project, process: FakeQwen.events.append(('销号', process)))
        self.stub(qwen_setup, 'environment', lambda model='', api=None: {})
        self.stub(subprocess, 'Popen', FakeQwen)

    def stub(self, module, name, value):
        original = getattr(module, name)
        setattr(module, name, value)
        self.addCleanup(setattr, module, name, original)

    def run_it(self, project):
        return self.adapter.run_background({'program': sys.executable, 'model': 'qwen-max'},
                                           project, project / '输出', project / '制作报告.txt',
                                           project / '运行日志.txt', '提示词')

    def test_the_task_is_on_the_ledger_while_it_runs(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            self.run_it(project)
            self.assertEqual(len(FakeQwen.made), 1, '真的起了一个进程')
            self.assertEqual([name for name, _ in FakeQwen.events], ['登记', '对话', '销号'],
                             '先登记、再对话、最后销号')
            self.assertIs(FakeQwen.events[0][1], FakeQwen.made[0])
            self.assertIs(FakeQwen.events[2][1], FakeQwen.made[0])
            self.assertEqual(FakeQwen.events[1][1], '提示词', '任务从标准输入递进去')
            self.assertEqual(FakeQwen.made[0].kwargs['stdin'], subprocess.PIPE)
            self.assertEqual((project / '制作报告.txt').read_text(encoding='utf-8'), '白模做好啦')

    def test_a_failed_run_is_taken_off_the_ledger_too(self):
        FakeQwen.returncode = 1
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                self.run_it(Path(td))
            self.assertEqual([name for name, _ in FakeQwen.events], ['登记', '对话', '销号'],
                             '失败了也要销号，别在台账里留个死进程')

    def test_invalid_response_never_publishes_partial_response_file(self):
        FakeQwen.response = {'not': 'a result'}
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            with self.assertRaises(ValueError):
                self.run_it(project)
            self.assertTrue((project / '制作报告.response.json').is_file(),
                            '有效 JSON 响应仍应保留作诊断')
            self.assertEqual(list(project.glob('*.tmp')), [])

    def test_malformed_response_does_not_replace_previous_diagnostic(self):
        FakeQwen.raw_response = '{incomplete'
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            response = project / '制作报告.response.json'
            response.write_text('{"old": true}', encoding='utf-8')
            with self.assertRaises(json.JSONDecodeError):
                self.run_it(project)
            self.assertEqual(response.read_text(encoding='utf-8'), '{"old": true}')
            self.assertEqual(list(project.glob('*.tmp')), [])


class QuitTests(unittest.TestCase):
    """第 47 期第 7 条：有活儿在跑时也关得掉。"""

    def setUp(self):
        import desktop, previs_automation, workflow_engines
        self.desktop = desktop
        self.closed = []; self.terminated = []; self.stopped = []; self.asked = []
        self.answer = False
        self.stub(workflow_engines, 'terminate',
                  lambda project: (self.terminated.append(str(project)), [111])[1])
        self.stub(previs_automation, 'force_stop',
                  lambda project, state: (self.stopped.append(str(project)), [])[1])
        # Desktop.close 已统一走 desktop.confirm；继续替换旧 messagebox 会让
        # 子进程真的弹出模态确认窗，令安全全量回归永久等待。
        self.stub(desktop, 'confirm', self.ask)

    def stub(self, module, name, value):
        original = getattr(module, name)
        setattr(module, name, value)
        self.addCleanup(setattr, module, name, original)

    def ask(self, _parent, title, text, **kwargs):
        self.asked.append((title, text))
        return self.answer

    def subject(self, **fields):
        subject = type('Stub', (), {})()
        subject.root = Path('项目'); subject.win = None; subject.worker = None
        subject.cloud_monitor_busy = False; subject.video_sessions = {}; subject.previs_jobs = {}
        subject._closing = False; subject._automation_processes_stopped = False; subject.flow_processes = {}
        subject.cancel_timers = lambda: None
        subject.close_tray = lambda: None
        subject.pet_hides_instead_of_quitting = lambda: False
        subject.flush_brief = lambda: None
        subject.finish_close = lambda: self.closed.append('收摊')
        # close() 里现算「在等什么」：替身把这一条接到真方法上，量的是真理由。
        subject.busy_reason = lambda: self.desktop.Desktop.busy_reason(subject)
        subject.force_quit = lambda: self.desktop.Desktop.force_quit(subject)
        subject.stop_automation_processes = lambda: self.desktop.Desktop.stop_automation_processes(subject)
        for name, value in fields.items():
            setattr(subject, name, value)
        return subject

    def reason(self, **fields):
        return self.desktop.Desktop.busy_reason(self.subject(**fields))

    def test_the_reason_says_what_is_holding_the_window(self):
        self.assertEqual(self.reason(), '')
        self.assertIn('白模', self.reason(previs_jobs={'busy': True}))
        self.assertIn('Agent', self.reason(worker=object()))
        self.assertIn('线上', self.reason(cloud_monitor_busy=True))
        self.assertIn('视频', self.reason(video_sessions={'k': SimpleNamespace(busy=True)}))
        self.assertIn('提示词', self.reason(video_sessions={'k': SimpleNamespace(busy=False, optimizer_busy=True)}))

    def test_closing_while_busy_asks_instead_of_only_refusing(self):
        subject = self.subject(worker=object())
        self.assertIsNone(self.desktop.Desktop.close(subject))
        self.assertEqual(len(self.asked), 1, '问了一句')
        self.assertIn('Agent', self.asked[0][1])
        self.assertIn('强制关闭', self.asked[0][1])
        self.assertEqual(self.closed, [], '答「否」：照旧守着，不关')
        self.assertFalse(subject._closing)

    def test_saying_yes_forces_the_quit(self):
        self.answer = True
        subject = self.subject(worker=object())
        self.assertTrue(self.desktop.Desktop.close(subject))
        self.assertEqual(self.terminated, [str(subject.root)], '先把引擎进程收掉')
        self.assertEqual(self.closed, ['收摊'])
        self.assertTrue(subject._closing)

    def test_a_quiet_close_does_not_ask(self):
        subject = self.subject()
        self.assertIsNone(self.desktop.Desktop.close(subject))
        self.assertEqual(self.asked, [])
        self.assertEqual(self.closed, ['收摊'])
        self.assertTrue(subject._closing)

    def test_force_quit_stops_the_previs_batch_first(self):
        subject = self.subject(previs_jobs={'busy': True})
        self.assertTrue(subject.force_quit())
        self.assertEqual(self.stopped, [str(subject.root)], '白模那一批也要停下来')
        self.assertTrue(subject._forcing_quit)
        self.assertEqual(self.closed, ['收摊'])

    def maintenance_subject(self, failure=None, forcing=False):
        import infra.storage_maintenance as storage_maintenance
        from infra import log_maintenance
        from infra import workspace_maintenance
        events = []
        for name, module in [('storage', storage_maintenance), ('logs', log_maintenance),
                             ('workspace', workspace_maintenance)]:
            def launch(app, name=name):
                events.append(name)
                if failure and failure[0] == name:
                    raise failure[1]
            self.stub(module, 'launch_cleanup', launch)
        subject = self.subject(app=object(), _forcing_quit=forcing)
        subject.win = SimpleNamespace(destroy=lambda: events.append('destroy'))
        return subject, events

    def test_opened_project_snapshot_is_captured_before_destroy_and_forwarded(self):
        from unittest.mock import patch
        roots = {Path('external-first'), Path('external-second')}
        for forcing in (False, True):
            subject, events = self.maintenance_subject(forcing=forcing)
            subject._temporary_sweep_roots = roots.copy()
            def destroy():
                events.append('destroy')
                subject._temporary_sweep_roots.clear()
            subject.win.destroy = destroy
            with patch('orchestrator.exit_maintenance.launch_cleanup') as launch:
                self.desktop.Desktop.finish_close(subject)
            self.assertEqual(events, ['destroy'])
            self.assertEqual(set(launch.call_args.kwargs['temporary_projects']), roots)
            self.assertEqual(launch.call_args.kwargs['forced'], forcing)

    def test_maintenance_order_after_window_destroy(self):
        subject, events = self.maintenance_subject()
        self.desktop.Desktop.finish_close(subject)
        self.assertEqual(events, ['destroy', 'storage', 'logs', 'workspace'])

    def test_storage_launch_failure_propagates_and_stops_later_launches(self):
        error = OSError('private path must not enter summary')
        subject, events = self.maintenance_subject(('storage', error))
        with self.assertRaises(OSError) as caught:
            self.desktop.Desktop.finish_close(subject)
        self.assertIs(caught.exception, error)
        self.assertEqual(events, ['destroy', 'storage'])

    def test_optional_launch_oserror_does_not_stop_following_launch(self):
        subject, events = self.maintenance_subject(('logs', OSError('denied')))
        self.desktop.Desktop.finish_close(subject)
        self.assertEqual(events, ['destroy', 'storage', 'logs', 'workspace'])

    def test_optional_programming_error_still_propagates(self):
        subject, events = self.maintenance_subject(('logs', ValueError('bad adapter')))
        with self.assertRaises(ValueError):
            self.desktop.Desktop.finish_close(subject)
        self.assertEqual(events, ['destroy', 'storage', 'logs'])

    def test_forced_exit_keeps_storage_only(self):
        subject, events = self.maintenance_subject(forcing=True)
        self.desktop.Desktop.finish_close(subject)
        self.assertEqual(events, ['destroy', 'storage'])

    def test_repeated_close_does_not_repeat_finish(self):
        subject = self.subject()
        self.desktop.Desktop.close(subject)
        self.desktop.Desktop.close(subject)
        self.assertEqual(self.closed, ['收摊'])

    def test_finish_close_takes_the_monitor_page_down(self):
        import infra.storage_maintenance as storage_maintenance
        from infra import log_maintenance
        from orchestrator import previs_monitor
        from infra import workspace_maintenance
        monitors = []; destroyed = []
        launched_logs = []
        launched_workspaces = []
        self.stub(previs_monitor, 'stop', lambda state: monitors.append(state))
        self.stub(storage_maintenance, 'launch_cleanup', lambda app: None)
        self.stub(log_maintenance, 'launch_cleanup', lambda app: launched_logs.append(app))
        self.stub(workspace_maintenance, 'launch_cleanup', lambda app: launched_workspaces.append(app))
        state = {'monitor': ('http://127.0.0.1:1/', object())}
        subject = self.subject(previs_jobs=state, app=object())
        subject.win = SimpleNamespace(destroy=lambda: destroyed.append('窗口'))
        self.desktop.Desktop.finish_close(subject)
        self.assertEqual(monitors, [state], '监视页跟着程序一起收')
        self.assertEqual(destroyed, ['窗口'])
        self.assertEqual(launched_logs, [subject.app], '正常退出后才异步维护程序日志')
        self.assertEqual(launched_workspaces, [subject.app], '正常退出后才异步做仓库卫生')

    def test_force_quit_does_not_schedule_log_maintenance(self):
        import infra.storage_maintenance as storage_maintenance
        from infra import log_maintenance
        from infra import workspace_maintenance
        launched_logs = []
        launched_workspaces = []
        self.stub(storage_maintenance, 'launch_cleanup', lambda app: None)
        self.stub(log_maintenance, 'launch_cleanup', lambda app: launched_logs.append(app))
        self.stub(workspace_maintenance, 'launch_cleanup', lambda app: launched_workspaces.append(app))
        subject = self.subject(app=object(), _forcing_quit=True)
        subject.win = SimpleNamespace(destroy=lambda: None)
        self.desktop.Desktop.finish_close(subject)
        self.assertEqual(launched_logs, [], '强制退出不额外做日志维护')
        self.assertEqual(launched_workspaces, [], '强制退出不额外做仓库卫生')

    def test_stop_automation_processes_ends_other_projects_once(self):
        """T3：当前项目之外登记的进程也要被结束；第二次调用返回空列表。"""
        import workflow_engines
        calls = []
        self.stub(workflow_engines, 'terminate_all',
                  lambda timeout=3.0: (calls.append(timeout), [702])[1])
        subject = self.subject(root=Path(tempfile.mkdtemp()))
        self.addCleanup(lambda: __import__('shutil').rmtree(subject.root, ignore_errors=True))
        first = subject.stop_automation_processes()
        self.assertEqual(calls, [3.0])
        self.assertIn(702, first)
        self.assertEqual(self.terminated, [str(subject.root)], '仍先结束当前项目')
        self.assertEqual(subject.stop_automation_processes(), [],
                         '「只做一次」：第二次必须立刻返回空列表')
        self.assertEqual(len(calls), 1)

    def test_stop_automation_processes_without_root_still_terminates_all(self):
        """当前没有打开项目时，退出仍要收掉登记表里其它项目的进程。"""
        import workflow_engines
        calls = []
        self.stub(workflow_engines, 'terminate_all',
                  lambda timeout=3.0: (calls.append(timeout), [801])[1])
        subject = self.subject(root=None)
        self.assertEqual(subject.stop_automation_processes(), [801])
        self.assertEqual(calls, [3.0])
        self.assertEqual(self.terminated, [], 'root 为空时不调 terminate(project)')

    def test_finish_close_logs_background_pool_status(self):
        """T4：退出时记一行各池排队数；pool_status 抛错也不挡收摊。"""
        import infra.executors as executors
        status = {'io': {'workers': 1, 'queued': 2, 'closing': False}}
        self.stub(executors, 'pool_status', lambda: status)
        subject, events = self.maintenance_subject()
        with self.assertLogs('desktop_lifecycle', level='INFO') as logs:
            self.desktop.Desktop.finish_close(subject)
        joined = '\n'.join(logs.output)
        self.assertIn('退出时后台任务', joined)
        self.assertIn('queued', joined)
        self.assertEqual(events, ['destroy', 'storage', 'logs', 'workspace'])

        subject2, events2 = self.maintenance_subject()
        self.stub(executors, 'pool_status',
                  lambda: (_ for _ in ()).throw(RuntimeError('pool boom')))
        self.desktop.Desktop.finish_close(subject2)
        self.assertEqual(events2, ['destroy', 'storage', 'logs', 'workspace'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
