# -*- coding: utf-8 -*-
"""共享输入框的「阶段发送动作」登记表：没有对话流程的阶段，发送键承载页面登记的制作动作。

``SharedStageInput.set_stage_action``／``stage_action``／``run_stage_action``：

- 输入框空着点发送（或回车）＝执行当前阶段登记的动作，和点页面上的制作按钮是同一个入口；
  其他阶段不过上游门禁、不清输入框、不动在途标记与模型快照；S03 空发送例外，
  须过上游门禁、冻结模型快照并在受理后清稿，拒绝时保留原文；
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
        with mock.patch.object(shared_send, 'upstream_send_error',
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


class StoryboardEmptySendTests(_StageActionCase):
    """S03 空发送也过上游门禁并捕获模型快照；其他阶段保留原 stage_action 契约。"""

    def setUp(self):
        super().setUp()
        self.box.set_stage('storyboard')
        self.desktop.page_index = pet_bus.STAGES.index('storyboard')

    def test_upstream_rejection_does_not_run_action_or_capture_model(self):
        self.box.set_stage_action('storyboard', self.make)
        self.box.input.insert('1.0', '  \n')
        raw = self.box.input.get('1.0', 'end-1c')
        self.box.request_snapshot = mock.Mock(return_value='snapshot')
        with mock.patch.object(shared_send, 'upstream_send_error',
                               return_value='请先确认结构剧本') as gate:
            self.assertIs(self.box.send(), False)
        gate.assert_called_once_with(self.desktop.root, 'storyboard', self.box.status)
        self.assertEqual(self.calls, [])
        self.box.request_snapshot.assert_not_called()
        self.assertEqual(self.box.input.get('1.0', 'end-1c'), raw)
        self.assertFalse(self.box.in_flight)

    def test_accepted_empty_send_exposes_snapshot_then_releases_request(self):
        seen = []
        self.box.set_stage_action(
            'storyboard', lambda: seen.append(self.box.request_model) or True)
        self.box.request_snapshot = mock.Mock(return_value='snapshot')
        with mock.patch.object(shared_send, 'upstream_send_error', return_value=''):
            self.assertIs(self.box.send(), True)
        self.assertEqual(seen, ['snapshot'])
        self.box.request_snapshot.assert_called_once_with()
        self.assertIsNone(self.box.request_model)
        self.assertFalse(self.box.in_flight)

    def test_rejected_action_propagates_false_and_releases_request(self):
        self.box.set_stage_action('storyboard', lambda: False)
        self.box.request_snapshot = mock.Mock(return_value='snapshot')
        with mock.patch.object(shared_send, 'upstream_send_error', return_value=''):
            self.assertIs(self.box.send(), False)
        self.assertIsNone(self.box.request_model)
        self.assertFalse(self.box.in_flight)


class TextSendOnStageWithoutFlowTests(_StageActionCase):
    """非聊天制作阶段输入框有字发送：直连 API 按 SKILL 仅输出阶段文件；未配 API 时提示选模型。"""

    def test_text_send_dispatches_to_stage_file_direct_api(self):
        seen = []
        self.box.set_text('帮我把第二场节奏加快')
        with mock.patch.object(shared_send, 'upstream_send_error', return_value=''), \
             mock.patch.object(shared_send, 'send_stage_file',
                               side_effect=lambda d, s, t='', **kw: seen.append((s, t)) or True):
            self.assertIs(self.box.send(), True)
        self.assertEqual(seen, [(STAGE, '帮我把第二场节奏加快')])
        self.assertEqual(self.box.text(), '', '受理后清空输入框')
        self.assertFalse(self.box.in_flight)
        self.assertIsNone(self.box.request_model)
        self.assertEqual(self.desktop.opened, [], '直连 API 输出文件，不新开 Agent 对话')

    def test_text_send_without_api_model_keeps_text_and_guides_user(self):
        self.box.set_text('帮我整理一下结构')
        with mock.patch.object(shared_send, 'upstream_send_error', return_value=''), \
             mock.patch('infra.model_pool.pool', return_value={}):
            self.assertIs(self.box.send(), False)
        self.assertNotIn('暂无对话入口', self.status())
        self.assertIn('API 模型', self.status())
        self.assertEqual(self.box.text(), '帮我整理一下结构', '未受理时保留输入框文字')
        self.assertEqual(self.desktop.opened, [])

    def test_text_send_still_respects_the_upstream_gate(self):
        self.box.set_stage_action(STAGE, self.make)
        self.box.set_text('帮我整理一下结构')
        with mock.patch.object(shared_send, 'upstream_send_error',
                               return_value='请先完成/确认「剧本准备」阶段'), \
             mock.patch.object(shared_send, 'send_stage_file') as direct:
            self.assertIs(self.box.send(), False)
        direct.assert_not_called()
        self.assertEqual(self.calls, [], '有字的发送仍先过上游门禁')
        self.assertEqual(self.status(), '请先完成/确认「剧本准备」阶段')
        self.assertEqual(self.box.text(), '帮我整理一下结构')

    def test_text_send_on_edit_stage_uses_direct_api_or_guides(self):
        seen = []
        with mock.patch.object(shared_send, 'send_stage_file',
                               side_effect=lambda d, s, t='', **kw: seen.append((s, t)) or True):
            self.assertIs(shared_send.send(self.desktop, 'edit', '修剪转场', None), True)
        self.assertEqual(seen, [('edit', '修剪转场')])
        with mock.patch('infra.model_pool.pool', return_value={}):
            self.assertIs(shared_send.send(self.desktop, 'edit', '随便聊聊', None), False)
        self.assertNotIn('暂无对话入口', self.status())
        self.assertIn('API 模型', self.status())

    def test_other_flow_stages_prefer_direct_api_and_fallback_to_flow(self):
        """assets 等阶段有 API 时直连输出阶段文件；未配 API 时回落原 Agent 流程。"""
        self.box.set_stage_action('assets', self.make)
        seen = []
        with mock.patch.object(shared_send, 'send_stage_file',
                               side_effect=lambda d, s, t='', **kw: seen.append((s, t)) or True):
            self.assertIs(shared_send.send(self.desktop, 'assets', '补几个角色', None), True)
        self.assertEqual(seen, [('assets', '补几个角色')])
        self.assertEqual(self.desktop.opened, [])
        with mock.patch('infra.model_pool.pool', return_value={}):
            self.assertIs(shared_send.send(self.desktop, 'assets', '补几个角色', None), True)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.desktop.opened[0][:3], ('assets', '资产管理', '补几个角色'))

    def test_run_stage_action_propagates_false(self):
        self.box.set_stage_action(STAGE, lambda: False)
        self.assertIs(self.box.run_stage_action(), False)
        self.box.set_stage_action(STAGE, lambda: None)
        self.assertIs(self.box.run_stage_action(), True)

    def test_skill_command_on_stage_without_flow_runs_direct_api(self):
        skill = SimpleNamespace(name='结构整理', stage=STAGE,
                                path=Path('skills') / 'x' / '结构整理.skill.md')
        self.box.skill_items = lambda: [skill]
        self.box.set_stage_action(STAGE, self.make)
        parsed = {'kind': 'skill', 'name': '结构整理', 'stage': STAGE, 'rest': ''}
        seen = []
        with mock.patch.object(shared_send, 'send_stage_file',
                               side_effect=lambda d, s, t='', **kw: seen.append((s, kw.get('only'))) or True):
            self.assertIs(shared_send.send(self.desktop, STAGE, '/结构整理', parsed), True)
        self.assertEqual(seen, [(STAGE, ['结构整理'])])
        with mock.patch('infra.model_pool.pool', return_value={}):
            self.assertIs(shared_send.send(self.desktop, STAGE, '/结构整理', parsed), False)
        self.assertEqual(self.calls, [])
        self.assertNotIn('暂无 Agent 入口', self.status())
        self.assertIn('API 模型', self.status())
        self.assertEqual(self.desktop.opened, [])


if __name__ == '__main__':
    unittest.main()
