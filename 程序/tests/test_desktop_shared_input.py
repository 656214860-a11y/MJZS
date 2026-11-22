# -*- coding: utf-8 -*-
"""共享输入框的「阶段发送动作」登记表：没有对话流程的阶段，发送键承载页面登记的制作动作。

``SharedStageInput.set_stage_action``／``stage_action``／``run_stage_action``：

- 输入框空着点发送（或回车）＝执行当前阶段登记的动作，和点页面上的制作按钮是同一个入口；
  这条路不过上游门禁、不清输入框、不动在途标记与模型快照；
- 输入框有字时，没有对话流程的阶段（``desktop_shared_send._send_free``）照样执行并说明
  文字用不上，文字留在输入框；没登记的阶段保持原来的提示；
- 这一阶段正在执行时不重复开动。

页面一侧的登记（剧本结构页）见 test_ui_batch5_stage_panel_and_script_page。
"""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import desktop_shared_input as shared_input
import desktop_shared_send as shared_send
import orchestrator.stage_flow as stage_flow
from contract import pet_bus

STAGE = 'script_structure'
STAGE_NAME = '剧本结构'


class _Event:
    state = 0


class _ShiftEvent:
    state = 0x1


class _Desktop:
    """最小桌面替身：状态栏、项目根、safe 与 Agent 流程入口（只记录）。"""

    def __init__(self, win, root):
        self.win = win
        self.root = root
        self.status = tk.StringVar(master=win, value='')
        self.page_index = pet_bus.STAGES.index(STAGE)
        self.projects = SimpleNamespace(info={'projects': []})
        self.opened = []
        self.open_flow_agent = lambda *args, **kw: self.opened.append(args)

    def safe(self, fn):
        return fn()


class _StageActionCase(unittest.TestCase):
    """真实的共享输入框接上真实的发送分流；当前阶段停在剧本结构。"""

    def setUp(self):
        self.win = tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / 'project'
        root.mkdir()
        stage_flow.reset()
        self.addCleanup(stage_flow.reset)
        self.desktop = _Desktop(self.win, root)
        self.box = shared_input.SharedStageInput(
            self.win, desktop=self.desktop, options=shared_send.host_options(self.desktop))
        self.addCleanup(self.box.destroy)
        self.desktop.shared_input = self.box
        self.box.set_stage(STAGE)
        self.calls = []

    def make(self):
        self.calls.append('make')

    def status(self):
        return self.desktop.status.get()


class EmptySendRunsStageActionTests(_StageActionCase):
    """输入框空着点发送：执行当前阶段登记的动作。"""

    def test_empty_send_runs_the_registered_action_once(self):
        self.box.set_stage_action(STAGE, self.make)
        self.box.input.insert('1.0', '  \n')
        raw = self.box.input.get('1.0', 'end-1c')
        self.box.request_snapshot = mock.Mock(return_value='snapshot')
        with mock.patch.object(shared_input, 'upstream_send_error',
                               return_value='上游未完成') as gate:
            self.assertIs(self.box.send(), True)
        self.assertEqual(self.calls, ['make'])
        gate.assert_not_called()
        self.box.request_snapshot.assert_not_called()
        self.assertEqual(self.box.input.get('1.0', 'end-1c'), raw, '空文本这条路不清输入框')
        self.assertFalse(self.box.in_flight)
        self.assertIsNone(self.box.request_model, '空文本这条路不捕获模型快照')
        self.assertEqual(self.status(), '', '不经过发送分流，状态栏由动作自己写')
        self.assertEqual(self.desktop.opened, [])

    def test_empty_send_without_registration_does_nothing(self):
        self.assertIs(self.box.send(), False)
        self.assertEqual(self.status(), '')
        self.assertFalse(self.box.in_flight)
        self.assertEqual(self.desktop.opened, [])

    def test_action_of_another_stage_waits_until_the_page_switches(self):
        self.box.set_stage('script')
        self.box.set_stage_action(STAGE, self.make)
        self.assertIs(self.box.send(), False)
        self.assertEqual(self.calls, [])
        self.box.set_stage(STAGE)
        self.assertIs(self.box.send(), True)
        self.assertEqual(self.calls, ['make'])

    def test_running_stage_is_not_started_twice(self):
        self.box.set_stage_action(STAGE, self.make)
        stage_flow.mark(STAGE, 'stage.executing', 'manual')
        self.assertIs(self.box.send(), False)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.status(), shared_input.STAGE_ACTION_BUSY % STAGE_NAME)
        self.assertIn(STAGE_NAME, self.status())
        self.assertIn('正在执行', self.status())
        stage_flow.mark(STAGE, 'stage.completed')
        self.assertIs(self.box.send(), True)
        self.assertEqual(self.calls, ['make'])

    def test_enter_on_an_empty_box_runs_the_action(self):
        self.box.set_stage_action(STAGE, self.make)
        self.assertIsNone(self.box._on_return(_ShiftEvent()), 'Shift+Enter 仍是换行')
        self.assertEqual(self.calls, [])
        self.assertEqual(self.box._on_return(_Event()), 'break')
        self.assertEqual(self.calls, ['make'])

    def test_registration_is_replaced_and_removed(self):
        first = lambda: self.calls.append('first')
        second = lambda: self.calls.append('second')
        self.box.set_stage_action(STAGE, first)
        self.box.set_stage_action(STAGE, second)
        self.assertIs(self.box.stage_action(), second)
        self.assertIs(self.box.stage_action(STAGE), second)
        self.assertIsNone(self.box.stage_action('edit'))
        self.assertIs(self.box.run_stage_action(), True)
        self.assertEqual(self.calls, ['second'], '后登记的覆盖先登记的')
        self.box.set_stage_action(STAGE, None)
        self.assertIsNone(self.box.stage_action(STAGE))
        self.assertIs(self.box.run_stage_action(STAGE), False)
        self.assertEqual(self.calls, ['second'])

    def test_action_errors_are_left_to_the_action(self):
        def boom():
            raise ValueError('动作自己报错')
        self.box.set_stage_action(STAGE, boom)
        with self.assertRaises(ValueError):
            self.box.send()
        self.assertFalse(self.box.in_flight)


class TextSendOnStageWithoutFlowTests(_StageActionCase):
    """输入框有字、阶段没有对话流程：登记了动作就执行并说明文字用不上；没登记保持原提示。"""

    def hint(self):
        return shared_send.STAGE_ACTION_TEXT_UNUSED % STAGE_NAME

    def test_text_send_runs_the_action_and_keeps_the_text(self):
        seen = []
        self.box.set_stage_action(STAGE, lambda: seen.append(self.status()))
        self.box.set_text('帮我整理一下结构')
        with mock.patch.object(shared_input, 'upstream_send_error', return_value=''):
            self.assertIs(self.box.send(), False)
        self.assertEqual(seen, [self.hint()], '说明先写、动作后跑，且只跑一次')
        self.assertEqual(self.status(), self.hint())
        self.assertIn(STAGE_NAME, self.status())
        self.assertNotIn('暂无对话入口', self.status())
        self.assertEqual(self.box.text(), '帮我整理一下结构', '文字留在输入框')
        self.assertFalse(self.box.in_flight)
        self.assertIsNone(self.box.request_model)
        self.assertEqual(self.desktop.opened, [], '不新开 Agent 对话')

    def test_the_action_has_the_last_word_in_the_status_bar(self):
        self.box.set_stage_action(
            STAGE, lambda: self.desktop.status.set('三虎开始整理结构剧本'))
        self.assertIs(shared_send.send(self.desktop, STAGE, '整理一下', None), False)
        self.assertEqual(self.status(), '三虎开始整理结构剧本',
                         '动作自己的开工提示或报错不能被说明盖掉')

    def test_text_send_on_a_running_stage_only_says_busy(self):
        self.box.set_stage_action(STAGE, self.make)
        stage_flow.mark(STAGE, 'stage.executing', 'auto')
        self.assertIs(shared_send.send(self.desktop, STAGE, '整理一下', None), False)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.status(), shared_input.STAGE_ACTION_BUSY % STAGE_NAME)

    def test_text_send_still_respects_the_upstream_gate(self):
        self.box.set_stage_action(STAGE, self.make)
        self.box.set_text('帮我整理一下结构')
        with mock.patch.object(shared_input, 'upstream_send_error',
                               return_value='请先完成/确认「剧本准备」阶段'):
            self.assertIs(self.box.send(), False)
        self.assertEqual(self.calls, [], '有字的发送仍先过上游门禁')
        self.assertEqual(self.status(), '请先完成/确认「剧本准备」阶段')
        self.assertEqual(self.box.text(), '帮我整理一下结构')

    def test_text_send_without_registration_keeps_the_old_hint(self):
        self.assertIs(shared_send.send(self.desktop, STAGE, '整理一下', None), False)
        self.assertIn('「%s」阶段暂无对话入口' % STAGE_NAME, self.status())
        self.assertEqual(self.desktop.opened, [])

    def test_registration_does_not_leak_to_other_stages(self):
        self.box.set_stage_action(STAGE, self.make)
        self.assertIs(shared_send.send(self.desktop, 'edit', '随便聊聊', None), False)
        self.assertEqual(self.calls, [])
        self.assertIn('「%s」阶段暂无对话入口' % pet_bus.stage_name('edit'), self.status())

    def test_stages_with_a_flow_ignore_stage_actions(self):
        self.box.set_stage_action('storyboard', self.make)
        self.assertIs(
            shared_send.send(self.desktop, 'storyboard', '按这个节奏分镜', None), True)
        self.assertEqual(self.calls, [], '有对话流程的阶段照旧走 Agent 流程')
        self.assertEqual(self.desktop.opened[0][:3],
                         ('storyboard', '初步分镜', '按这个节奏分镜'))

    def test_skill_command_on_stage_without_flow_is_unchanged(self):
        skill = SimpleNamespace(name='结构整理', stage=STAGE,
                                path=Path('skills') / 'x' / '结构整理.skill.md')
        self.box.skill_items = lambda: [skill]
        self.box.set_stage_action(STAGE, self.make)
        parsed = {'kind': 'skill', 'name': '结构整理', 'stage': STAGE, 'rest': ''}
        self.assertIs(shared_send.send(self.desktop, STAGE, '/结构整理', parsed), False)
        self.assertEqual(self.calls, [], '技能命令在没有对话流程的阶段仍只提示')
        self.assertIn('暂无 Agent 入口', self.status())
        self.assertEqual(self.desktop.opened, [])


if __name__ == '__main__':
    unittest.main()
