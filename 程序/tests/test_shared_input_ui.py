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

    # ── R2971／REQ-S01-90：✦／＋ 图标下拉面板（与 / 补全同款浮层） ──

    def _panel_labels(self, panel):
        return [w for w in _descendants(panel)
                if isinstance(w, tk.Label) and str(w.cget('text') or '')]

    def _click(self, widget):
        """合成一次真实单击：映射窗口后按控件中心坐标投递（与 test_cell_menu 同法）。"""
        self.win.deiconify()
        self.win.update()
        x, y = widget.winfo_width() // 2, widget.winfo_height() // 2
        widget.event_generate('<Button-1>', x=x, y=y,
                              rootx=widget.winfo_rootx() + x,
                              rooty=widget.winfo_rooty() + y)
        self.win.update()

    def test_skill_dropdown_shows_canonical_names_and_inserts(self):
        """✦ 下拉行只显示技能包原始 name（不映射别名、不拼 displayName），
        点名把 /name 写进输入框、不自动发送；面板是 place 浮层不是弹窗。"""
        box = self._make()
        box._skill_list_items = lambda: [
            {'name': 'pipeline-script-preparation', 'displayName': '全流程AIGC·剧本',
             'description': '剧本技能说明'},
            SimpleNamespace(name='mine-skill', stage='storyboard')]
        box.open_skill_list()
        self.win.update_idletasks()
        panel = box.skill_panel
        self.assertTrue(panel.is_open())
        self.assertEqual(panel.winfo_manager(), 'place', '下拉面板是 place 浮层，不是弹窗')
        texts = [str(w.cget('text')) for w in self._panel_labels(panel)]
        self.assertIn('pipeline-script-preparation', texts)
        self.assertIn('mine-skill', texts)
        self.assertFalse(any('全流程AIGC' in t or ' · ' in t for t in texts),
                         '技能行只显示原始 name，不映射别名')
        target = next(w for w in self._panel_labels(panel)
                      if str(w.cget('text')) == 'mine-skill')
        self._click(target)
        self.assertEqual(box.text(), '/mine-skill')
        self.assertEqual(self.sent, [], '点技能只插入命令，不自动发送')
        self.assertFalse(panel.is_open())

    def test_skill_dropdown_toggle_and_escape_close(self):
        """再点 ✦ 收起；Esc 与切页同样收掉图标下拉。"""
        box = self._make()
        box.open_skill_list()
        self.assertTrue(box.skill_panel.is_open())
        box.open_skill_list()
        self.assertFalse(box.skill_panel.is_open())
        box.open_add_menu()
        self.assertTrue(box.add_panel.is_open())
        self.assertEqual(box.close_completion(), 'break')
        self.assertFalse(box.add_panel.is_open())
        box.open_skill_list()
        self.assertTrue(box.skill_panel.is_open())
        box.set_stage('assets')
        self.assertFalse(box.skill_panel.is_open(), '切页收掉图标下拉')

    def test_add_menu_entries_and_skill_drilldown(self):
        """＋ 下拉含添加附件／添加模型…／添加技能…；技能项下钻出仓库与本地。"""
        box = self._make()
        box.open_add_menu()
        self.win.update_idletasks()
        panel = box.add_panel
        self.assertTrue(panel.is_open())
        texts = [str(w.cget('text')) for w in self._panel_labels(panel)]
        self.assertEqual(texts, ['添加附件', '添加模型…', '添加技能…'])
        drill = next(w for w in self._panel_labels(panel)
                     if str(w.cget('text')) == '添加技能…')
        self._click(drill)
        texts = [str(w.cget('text')) for w in self._panel_labels(panel)]
        self.assertEqual(texts, ['‹ 返回', '从仓库导入', '本地安装'])
        back = next(w for w in self._panel_labels(panel)
                    if str(w.cget('text')) == '‹ 返回')
        self._click(back)
        texts = [str(w.cget('text')) for w in self._panel_labels(panel)]
        self.assertEqual(texts, ['添加附件', '添加模型…', '添加技能…'])

    def test_panels_are_mutually_exclusive_and_outside_click_closes(self):
        """两个图标面板互斥；点面板与图标钮之外收掉，点图标钮本身仍是开合。"""
        box = self._make()
        box.pack(fill='x')
        self.win.update_idletasks()
        box.open_skill_list()
        self.assertTrue(box.skill_panel.is_open())
        box.open_add_menu()
        self.assertFalse(box.skill_panel.is_open(), '开＋先收✦')
        self.assertTrue(box.add_panel.is_open())
        self._click(box.input)
        self.assertFalse(box.add_panel.is_open(), '点输入框＝面板外，收掉')
        box.open_add_menu()
        self.assertTrue(box.add_panel.is_open())
        self._click(box.attachment_button)
        self.assertTrue(box.add_panel.is_open(), '点图标钮不算外点')
        box.attachment_button.invoke()
        self.assertFalse(box.add_panel.is_open(), '图标钮 command 负责开合')

    def test_typing_slash_closes_icon_panel(self):
        """面板开着时输入 / ：收掉图标面板、照常弹补全。"""
        box = self._make()
        box.open_skill_list()
        self.assertTrue(box.skill_panel.is_open())
        box.set_text('/')
        box._on_key_release(SimpleNamespace(keysym='/'))
        self.win.update()
        self.assertFalse(box.skill_panel.is_open())
        self.assertTrue(box.completion.open)


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
