# -*- coding: utf-8 -*-
"""第 54 期附件一／三／五：阶段配置只做配置，手动制作走精简窗，直接执行落到次级执行页。

* 附件一：阶段配置里没有「执行选中」那颗按钮，但「SKILL 说明」一个字都不动。
* 附件三：点「手动制作XX」弹的那扇窗只有三行核心信息与三个按钮
  （修改配置／直接执行／取消）；依赖未满足时「直接执行」置灰并多一行警告。
  第 55 期第 4 条：原来那三个「查看…详情」折叠项按用户要求删掉，这一窗只剩该做的选择。
* 附件五：第三层次级执行页——SKILL 清单 ＋ 进度 ＋ 日志 ＋ 失败项 ＋ 重试失败项。

运行：python test_manual_plan.py
"""
from skip_reasons import (
    MISSING_NODE,
    PLATFORM_DIRECTORY_LINK,
    PLATFORM_TKINTER,
    PLATFORM_TK_DISPLAY,
    PLATFORM_WORKING_SET,
    REQUIRES_BUNDLED_SKILL,
)
import json, os, sys, tempfile, unittest
from widget_test_support import widget_list as _widget_list, widget_texts as _widget_texts
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

import stage_flow


def project(td, state=None):
    """最小项目：够 stage_flow 读阶段配置与阶段状态就行。"""
    proj = Path(td) / 'p'
    (proj / '工作流任务' / '宠物').mkdir(parents=True)
    if state:
        (proj / '工作流任务' / '宠物' / '阶段状态.json').write_text(
            json.dumps(state, ensure_ascii=False), encoding='utf-8')
    return proj


def desktop(proj, win=None):
    subject = type('Stub', (), {})()
    subject.root = proj
    subject.app = HERE
    subject.win = win
    subject.errors = []
    return subject




def widget_texts(widget, classes=('TButton', 'Button', 'TLabel', 'Label')):
    return _widget_texts(widget, classes)


def widget_list(widget, classes=('TButton', 'Button')):
    return _widget_list(widget, classes)



class PlanTests(unittest.TestCase):
    """stage_models.plan 的三种去处（弹窗那一层由 PlanWindowTests 盯着）。"""

    def setUp(self):
        import skill_panel, stage_models
        self.sm, self.panel_module = stage_models, skill_panel
        self.addCleanup(setattr, stage_models, 'PLANNER', None)
        self.opened = []
        original = skill_panel.show
        skill_panel.show = lambda desktop, stage, function=None: self.opened.append(stage)
        self.addCleanup(setattr, skill_panel, 'show', original)

    def test_an_unknown_choice_counts_as_cancel(self):
        self.sm.PLANNER = lambda *a, **k: 'nonsense'
        self.assertIsNone(self.sm.plan(desktop(None), 'assets'))

    def test_a_broken_window_cancels_and_explains_the_failure(self):
        def boom(*a, **k):
            raise RuntimeError('没有窗口')
        self.sm.PLANNER = boom
        subject = desktop(None)
        subject.status = type('Status', (), {'value': '', 'set': lambda self, value: setattr(self, 'value', value)})()
        self.assertIsNone(self.sm.plan(subject, 'assets'))
        self.assertIn('未能打开操作确认窗口', subject.status.value)

    def test_the_window_gets_the_stage_and_the_parent(self):
        seen = []
        self.sm.PLANNER = lambda d, stage, parent=None: (seen.append((stage, parent)), 'run')[1]
        self.sm.plan(desktop(None), 'previs', '窗口')
        self.assertEqual(seen, [('previs', '窗口')])

    def test_direct_run_runs_the_action(self):
        self.sm.PLANNER = lambda *a, **k: 'run'
        ran = []
        run = self.sm.manual_command(desktop(None), 'assets', lambda: ran.append('done'))
        self.assertTrue(run())
        self.assertEqual(ran, ['done'])

    def test_cancel_runs_nothing(self):
        self.sm.PLANNER = lambda *a, **k: None
        ran = []
        self.assertFalse(self.sm.manual_command(desktop(None), 'assets', lambda: ran.append('done'))())
        self.assertEqual(ran, [])

    def test_configure_opens_the_panel_and_skips_this_round(self):
        self.sm.PLANNER = lambda *a, **k: 'configure'
        ran = []
        run = self.sm.manual_command(desktop(None), 'assets', lambda: ran.append('done'))
        self.assertFalse(run())
        self.assertEqual(ran, [], '去改配置这一趟不动手')
        self.assertEqual(self.opened, ['assets'], '打开的就是这一阶段的面板')

    def test_the_config_path_is_reachable_on_its_own(self):
        self.sm.open_config(desktop(None), 'video')
        self.assertEqual(self.opened, ['video'])

    def test_a_broken_config_panel_explains_the_failure(self):
        import ui_plugin_registry
        original = ui_plugin_registry.module
        ui_plugin_registry.module = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('面板不可用'))
        self.addCleanup(setattr, ui_plugin_registry, 'module', original)
        subject = desktop(None)
        subject.status = type('Status', (), {'value': '', 'set': lambda self, value: setattr(self, 'value', value)})()
        self.assertIsNone(self.sm.open_config(subject, 'video'))
        self.assertIn('未能打开阶段配置', subject.status.value)


class PlanWindowTests(unittest.TestCase):
    """附件三那张图：三行 ＋ 三个折叠 ＋ 三个按钮。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            from tkinter import ttk
            cls.tk, cls.ttk = tk, ttk
        except Exception:
            cls.tk = None

    def setUp(self):
        import stage_models
        self.sm = stage_models

    def test_popup_jobs_are_cancelled_when_the_window_closes(self):
        """快速关闭精简窗时，延迟的点活／取消置顶回调不能遗留给 Tcl。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        root = self.tk.Tk(); root.withdraw()
        self.addCleanup(lambda: root.winfo_exists() and root.destroy())
        popup = self.tk.Toplevel(root)
        self.addCleanup(lambda: popup.winfo_exists() and popup.destroy())
        job = self.sm._schedule_popup_job(popup, 60000, lambda: None)
        self.assertIn(job, popup._stage_model_popup_jobs)
        self.sm._cancel_popup_jobs(popup)
        self.assertEqual(popup._stage_model_popup_jobs, set())

    def open_plan(self, proj, click, stage='storyboard'):
        """弹一次那扇窗，等它画好之后按 ``click`` 那颗按钮，返回 (选择, 看到的控件树)。"""
        win = self.tk.Tk(); win.withdraw()
        self.addCleanup(win.destroy)
        seen = {}
        real_desktop = desktop(proj, win)

        def look():
            windows = [w for w in win.winfo_children() if isinstance(w, self.tk.Toplevel)]
            seen['windows'] = len(windows)
            if not windows:
                return
            window = windows[0]
            seen['texts'] = widget_texts(window)
            buttons = {str(w.cget('text')): w for w in widget_list(window, ('TButton',))}
            seen['buttons'] = sorted(buttons)
            seen['state'] = str(buttons['直接执行'].cget('state')) if '直接执行' in buttons else ''
            target = buttons.get(click)
            if target is not None:
                target.invoke()

        win.after(80, look)
        choice = self.sm.plan_window(real_desktop, stage, win)
        return choice, seen

    def test_the_window_has_three_buttons_and_no_folds(self):
        """第 55 期第 4 条：三个「查看…详情」折叠项按用户要求删掉，只剩三颗按钮。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            choice, seen = self.open_plan(project(td), '取消')
            self.assertEqual(seen['windows'], 1, '只冒这一扇窗')
            self.assertEqual(sorted(seen['buttons']), ['修改配置', '取消', '直接执行'],
                             '三颗按钮，一个折叠项都没有')
            self.assertFalse([text for text in seen['texts'] if text.endswith('▼')],
                             '一个折叠项都不许留')
            self.assertIsNone(choice, '「取消」＝什么都不做')

    def test_the_default_lines_stay_within_four(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            _, seen = self.open_plan(project(td), '取消')
            heads = [text for text in seen['texts']
                     if text.startswith(('模型：', 'SKILL：', '预计：', '依赖：'))]
            self.assertLessEqual(len(heads), 4)
            self.assertTrue(any(text.startswith('模型：') for text in heads))
            self.assertTrue(any(text.startswith('SKILL：') for text in heads))

    def test_the_run_button_is_greyed_when_a_dependency_failed(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = project(td, {'stages': {'final': {'state': 'failed'}}})
            # 置灰的按钮点不动，所以按「取消」收场，只看那颗按钮的状态。
            _, seen = self.open_plan(proj, '取消', stage='keyframe')
            self.assertEqual(seen['state'], 'disabled', '前置翻了车就不给直接执行')
            self.assertTrue(any(text.startswith('依赖：') for text in seen['texts']),
                            '并多一行警告')

    def test_direct_run_is_enabled_when_nothing_is_wrong(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            choice, seen = self.open_plan(project(td), '直接执行')
            self.assertEqual(seen['state'], 'normal')
            self.assertEqual(choice, 'run')

    def test_modify_config_returns_the_configure_choice(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            choice, _ = self.open_plan(project(td), '修改配置')
            self.assertEqual(choice, 'configure')



class SelfTestGuardTests(unittest.TestCase):
    """第 60 期第 6 条：自检／探针进程里这两处弹窗一律不冒。

    用户截了张图说「卡在这里」：单独跑某个测试文件时（没有 run_selftests 那层假函数），
    用例一点「手动制作资产」就冒出真的那扇窗，停在 wait_window 上把用例卡死，
    窗留在桌面上不走。这里盯住那条保险。
    """

    def setUp(self):
        import stage_models
        self.sm = stage_models
        for name in ('SELF_TEST', 'PLANNER', 'ASKER'):
            self.addCleanup(setattr, self.sm, name, None)

    def test_a_test_or_probe_process_is_recognised(self):
        import sys, types
        self.addCleanup(sys.modules.__setitem__, '__main__', sys.modules.get('__main__'))
        for filename, expected in (('C:/x/test_manual_gate.py', True),
                                   ('C:/x/test_manual_plan.py', True),
                                   ('C:/x/probe60_plan.py', True),
                                   ('C:/程序/main.py', False),
                                   ('C:/程序/启动漫剧制作助手.pyw', False),
                                   ('C:/x/run_selftests.py', False)):
            module = types.ModuleType('__main__')
            module.__file__ = filename
            sys.modules['__main__'] = module
            self.assertEqual(self.sm.self_test(), expected, filename)

    def test_no_window_opens_when_the_process_is_a_self_test(self):
        self.sm.SELF_TEST = True
        called = []
        original = self.sm.plan_window
        self.sm.plan_window = lambda *a, **k: called.append(a)
        self.addCleanup(setattr, self.sm, 'plan_window', original)
        self.assertEqual(self.sm.plan(desktop(None), 'assets'), 'run',
                         '自检里按「直接执行」走，不冒窗')
        self.assertEqual(called, [], '一扇窗都不许冒')

    def test_an_explicit_fake_still_wins(self):
        self.sm.SELF_TEST = True
        self.sm.PLANNER = lambda *a, **k: 'configure'
        self.assertEqual(self.sm.plan(desktop(None), 'assets'), 'configure',
                         '用例自己换的假函数优先')

    def test_the_model_question_answers_itself_in_a_self_test(self):
        self.sm.SELF_TEST = True
        self.sm.ASKER = None
        import tkinter.messagebox as box
        original = box.askyesno
        box.askyesno = lambda *a, **k: (_ for _ in ()).throw(AssertionError('自检里不该弹真窗'))
        self.addCleanup(setattr, box, 'askyesno', original)
        self.assertFalse(self.sm._ask('先挑一下模型', '正文'))

    def test_the_model_gate_lets_the_work_go_on_in_a_self_test(self):
        self.sm.SELF_TEST = True
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / 'p'
            proj.mkdir()
            self.assertTrue(self.sm.before_manual(desktop(proj), 'previs'),
                            '自检里不拦：照旧开工')
            self.assertTrue(self.sm.before_manual(desktop(proj), 'assets'))


class PanelTests(unittest.TestCase):
    """附件一：面板只做配置——「执行选中」删了，「SKILL 说明」一个字都不动。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def build(self, proj):
        import skill_panel
        win = self.tk.Tk(); win.withdraw()
        self.addCleanup(win.destroy)
        panel = skill_panel.show(desktop(proj, win), 'storyboard')
        win.update_idletasks()
        return win, panel

    def test_the_execute_button_is_gone(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            win, panel = self.build(project(td))
            texts = widget_texts(panel.winfo_toplevel())
            self.assertNotIn('执行选中', texts)
            # 第 62 期任务 4：那两颗与「SKILL 管理」「预设」重复的按钮删掉了。
            for gone in ('全选', '重置'):
                self.assertNotIn(gone, texts, '重复入口「%s」该删掉' % gone)
            self.assertNotIn('执行', texts, '保存预设已并入左侧下拉，不再保留独立执行按钮')
            self.assertEqual(
                tuple(panel.preset_actions.cget('values')),
                ('选择操作', '保存为预设', '删除预设', '重命名预设', '复制本预设到其他页面'))

    def test_the_skill_notes_are_untouched(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            win, panel = self.build(project(td))
            self.assertIsNotNone(panel.note_list, '「SKILL 说明」那一栏还在')
            self.assertIsNotNone(panel.note_text)
            self.assertGreater(panel.note_list.size(), 0, '左边列着这一阶段的 SKILL')
            self.assertGreater(len(panel.note_text.get('1.0', 'end').strip()), 0,
                               '右边排着选中那一条的说明正文')

    def test_the_panel_still_runs_when_asked_programmatically(self):
        """按钮没了，run() 留着当可编程入口——自检与外部调用照旧能用。"""
        import skill_panel
        self.assertTrue(callable(getattr(skill_panel.Panel, 'run', None)))


class ExecPageTests(unittest.TestCase):
    """第三层次级执行页（附件三的次级执行页 ＋ 附件五第 3 条）。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def test_the_summary_counts_the_three_buckets(self):
        import skill_orchestrator as so
        import stage_exec
        run = {'results': [{'skill': 'a', 'status': so.DONE},
                           {'skill': 'b', 'status': so.PAGE},
                           {'skill': 'c', 'status': so.FAILED},
                           {'skill': 'd', 'status': so.MISSING}]}
        self.assertEqual([row['skill'] for row in stage_exec.failures(run)], ['c', 'd'])
        self.assertEqual(stage_exec.progress_text(run), '做完了 1 个，1 个要回页面按，没成 2 个')

    def test_a_missing_project_is_reported(self):
        import stage_exec
        with self.assertRaises(ValueError):
            stage_exec.run(desktop(None), 'edit')

    def test_the_page_shows_the_failures_and_can_retry_them(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import skill_orchestrator as so
        import stage_exec
        calls = []

        def fake_run(desk, stage, only=None, trigger='manual'):
            calls.append(list(only) if only else None)
            if only:
                return {'results': [{'skill': name, 'status': so.DONE} for name in only], 'text': '重试完成'}
            return {'results': [{'skill': 'edit-a', 'status': so.DONE},
                                {'skill': 'edit-b', 'status': so.FAILED}], 'text': '第一趟'}

        original = stage_exec.run
        stage_exec.run = fake_run
        self.addCleanup(setattr, stage_exec, 'run', original)
        with tempfile.TemporaryDirectory() as td:
            win = self.tk.Tk(); win.withdraw()
            self.addCleanup(lambda: win.winfo_exists() and win.destroy())
            handle = stage_exec.show(desktop(project(td), win), 'edit', win)
            win.update_idletasks()
            self.assertEqual(handle['failures'], ['edit-b'], '第一趟里没成的那一个')
            self.assertIn('第一趟', handle['log'].get('1.0', 'end'))
            handle['retry']()
            self.assertEqual(calls, [None, ['edit-b']], '重试只重试失败的那一个')
            self.assertEqual(handle['failures'], [])
            self.assertIn('重试完成', handle['log'].get('1.0', 'end'))


class ManualButtonNameTests(unittest.TestCase):
    """附件二第 3 条：每页那颗按钮的文字就是那张表里的名字（页面级由 test_ui_edges_pages 盯着）。"""

    def test_the_table_is_the_only_source_of_truth(self):
        import stage_models
        self.assertIs(stage_models.manual_label_for, stage_flow.manual_label)

    def test_every_manual_label_matches_the_button_helper(self):
        from pet_bus import STAGES
        for stage in STAGES:
            with self.subTest(stage=stage):
                self.assertEqual(stage_flow.manual_label(stage), stage_flow.MANUAL_LABELS[stage])


class CodeTestPhaseTests(unittest.TestCase):
    """第 65 期任务 11：代码测试阶段点「手动制作XX」一律不弹窗，直接开工。

    用户原话：「优化全部页面点击按钮『手动制作XX』的弹窗逻辑，代码测试阶段无需弹窗」。
    全程序九个「手动制作XX」入口都从 stage_models.manual_command 这一处过，所以这里盯住那一处：
    ① 认得出这一趟是测试；② 那扇精简窗与第 47 期那句模型提醒都不冒；③ 活儿照旧真开工。
    """

    def setUp(self):
        import stage_models
        self.sm = stage_models
        for name in ('SELF_TEST', 'PLANNER', 'ASKER'):
            self.addCleanup(setattr, self.sm, name, getattr(self.sm, name))
            setattr(self.sm, name, None)

    def test_a_unittest_process_is_a_code_test_phase(self):
        self.assertTrue(self.sm.tests_active(), 'unittest 跑着的进程就算代码测试阶段')

    def test_the_runner_and_a_plain_entry_are_told_apart(self):
        import sys, types
        saved = [(name, sys.modules.pop(name)) for name in ('unittest', 'pytest') if name in sys.modules]
        self.addCleanup(lambda: [sys.modules.__setitem__(name, module) for name, module in saved])
        original = sys.modules.get('__main__')
        self.addCleanup(sys.modules.__setitem__, '__main__', original)
        for filename, expected in (('C:/x/test_manual_plan.py', True),
                                   ('C:/x/probe65_plan.py', True),
                                   ('C:/x/run_selftests.py', True),
                                   ('C:/程序/main.py', False),
                                   ('C:/程序/启动漫剧制作助手.pyw', False)):
            module = types.ModuleType('__main__')
            module.__file__ = filename
            sys.modules['__main__'] = module
            self.assertEqual(self.sm.tests_active(), expected, filename)

    @staticmethod
    def boom(*args, **kwargs):
        raise AssertionError('代码测试阶段不许弹窗')

    def test_no_window_and_no_ask_in_a_code_test_phase(self):
        import tkinter.messagebox as box
        self.addCleanup(setattr, box, 'askyesno', box.askyesno)
        box.askyesno = self.boom
        original = self.sm.plan_window
        self.addCleanup(setattr, self.sm, 'plan_window', original)
        self.sm.plan_window = self.boom
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / 'p'
            proj.mkdir()
            ran = []
            run = self.sm.manual_command(desktop(proj), 'assets', lambda: ran.append('done'))
            self.assertTrue(run())
            self.assertEqual(ran, ['done'], '测试阶段不弹窗，但活儿照旧真开工')


if __name__ == '__main__':
    unittest.main(verbosity=2)
