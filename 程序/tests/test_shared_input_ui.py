"""R2893 轮 3：共享输入框组件——布局、``/`` 补全、发送门禁与模型快照（真 Tk 隐藏桌面）。"""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace

import desktop_shared_input as shared_input
from ui_shortcuts import ShortcutRegistry


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


class SharedInputLayoutTests(unittest.TestCase):
    def setUp(self):
        self.win = tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        self.root.mkdir()
        self.desktop = SimpleNamespace(root=self.root, status=tk.StringVar(master=self.win, value=''),
                                       win=self.win)
        self.sent = []

    def _make(self, **kwargs):
        options = {'on_send': lambda text, parsed: self.sent.append((text, parsed)) or True,
                   'skills': [SimpleNamespace(name='mine-skill', stage='storyboard')],
                   'engines': ()}
        options.update(kwargs.pop('options', {}))
        box = shared_input.SharedStageInput(self.win, desktop=self.desktop, options=options, **kwargs)
        box.pack(fill='x')
        self.win.update_idletasks()
        self.addCleanup(box.destroy)
        return box

    def test_layout_has_four_entries_and_text_area(self):
        box = self._make()
        texts = {str(w.cget('text')) for w in _descendants(box)
                 if isinstance(w, tk.Widget) and w.winfo_class() in ('TButton',)}
        # R2923/R2942：入口改图标文字按钮——✦ 技能、＋ 附件、🎤 语音与发送图标；
        # 模型选择器是共享框内右侧的下拉按钮（Menubutton），非模态弹窗、无外框纯下拉。
        from ui_tokens import ICON_ADD, ICON_MICROPHONE, ICON_SEND, ICON_SKILL
        for label in (ICON_SKILL, ICON_ADD, ICON_MICROPHONE, ICON_SEND):
            self.assertIn(label, texts)
        menus = [w for w in _descendants(box)
                 if isinstance(w, tk.Widget) and w.winfo_class() == 'TMenubutton']
        self.assertEqual(len(menus), 1, '共享输入框内应有一颗模型下拉按钮')
        self.assertTrue(str(menus[0].cget('text')).strip(), '模型下拉按钮显示当前模型名')
        self.assertIsInstance(box.input, tk.Text)
        # R2923：整个输入盒收进一张 Card——输入框在上、图标行在下（左✦＋🎤，右模型下拉＋发送）。
        self.assertEqual(box.input.master.winfo_class(), 'TFrame')
        row = box.input.master.winfo_children()[-1]
        self.assertEqual(row.winfo_class(), 'TFrame')

    def test_slash_completion_opens_and_escape_closes(self):
        box = self._make()
        box.set_text('/sto')
        box._on_key_release(SimpleNamespace(keysym='s'))
        self.win.update()
        self.assertTrue(box.completion.open)
        self.assertGreater(box.completion.list.size(), 0)
        self.assertIn('storyboard', box.completion.list.get(0))
        box.close_completion()
        self.assertFalse(box.completion.open)

    def test_completion_prefers_current_stage_skills(self):
        box = self._make(stage='storyboard')
        box.set_text('/')
        box._on_key_release(SimpleNamespace(keysym='/'))
        self.assertEqual(box.completion.list.get(0), '/mine-skill')
        box.close_completion()

    def test_send_blocked_when_upstream_blank(self):
        box = self._make(stage='continuity')
        box.set_text('帮我整理连贯性')
        self.assertFalse(box.send())
        self.assertIn('资产管理', self.desktop.status.get())
        self.assertEqual(self.sent, [])

    def test_ungated_upstream_missing_blocks_via_completion_evidence(self):
        box = self._make(stage='script_structure')
        box.set_text('整理结构')
        self.assertFalse(box.send())
        self.assertIn('剧本准备', self.desktop.status.get())

    def test_script_stage_passes_input_gate(self):
        # script 的简报必填门禁由宿主发送路径负责，共享框本身不拦。
        box = self._make(stage='script')
        box.set_text('自由聊天内容')
        self.assertTrue(box.send())
        self.assertEqual(self.sent[0][0], '自由聊天内容')
        self.assertIsNone(self.sent[0][1])
        self.assertEqual(box.text(), '')

    def test_command_parsed_and_snapshot_locked_in_flight(self):
        # storyboard 的上游 script_structure 在空项目上未完成，发送门禁会拦；
        # 用 script 页（无上游门禁）验证命令解析与快照语义，目标阶段仍是 storyboard。
        box = self._make(stage='script')
        box.set_text('/storyboard 重排镜头')
        self.assertTrue(box.send())
        text, parsed = self.sent[0]
        self.assertEqual(parsed['kind'], 'stage')
        self.assertEqual(parsed['stage'], 'storyboard')
        self.assertTrue(box.in_flight)
        box.end_request()
        self.assertFalse(box.in_flight)
        self.assertIsNone(box.request_model)

    def test_set_stage_keeps_same_instance(self):
        box = self._make()
        input_widget = box.input
        box.set_stage('assets')
        self.assertIs(box.input, input_widget)
        self.assertEqual(box.stage, 'assets')


class UpstreamGateTests(unittest.TestCase):
    """``upstream_send_error`` 的放行／拦截分支（门禁本体由 stage_parallel／completion_evidence 保证）。"""

    def test_script_and_unknown_stage_pass(self):
        self.assertEqual(shared_input.upstream_send_error(None, 'script'), '')
        self.assertEqual(shared_input.upstream_send_error(None, ''), '')
        self.assertEqual(shared_input.upstream_send_error(None, 'not-a-stage'), '')

    def test_gated_stage_upstream_ready_passes(self):
        from unittest import mock
        import stage_parallel
        ready = {'verdict': stage_parallel.PASS, 'ok': True, 'from': 'animatic'}
        with mock.patch.object(stage_parallel, 'evaluate', return_value=ready):
            self.assertEqual(shared_input.upstream_send_error(object(), 'assets'), '')

    def test_gated_stage_blocked_reports_reason(self):
        from unittest import mock
        import stage_parallel
        blocked = {'verdict': stage_parallel.BLOCKED, 'ok': False, 'from': 'animatic',
                   'detail': '预演未确认', 'reject': '先确认预演'}
        with mock.patch.object(stage_parallel, 'evaluate', return_value=blocked):
            error = shared_input.upstream_send_error(object(), 'assets')
        self.assertTrue(error)

    def test_ungated_stage_upstream_complete_passes(self):
        from unittest import mock
        with mock.patch('stage_completion_service.completion_evidence', return_value=(True, '')), \
                mock.patch('stage_parallel.stage_state', return_value=''):
            self.assertEqual(shared_input.upstream_send_error(object(), 'audio'), '')

    def test_ungated_stage_upstream_blank_rejected(self):
        from unittest import mock
        with mock.patch('stage_completion_service.completion_evidence',
                        return_value=(False, '没有视频成果')), \
                mock.patch('stage_parallel.stage_state', return_value=''):
            error = shared_input.upstream_send_error(object(), 'audio')
        self.assertIn('视频生成', error)


if __name__ == '__main__':
    unittest.main()
