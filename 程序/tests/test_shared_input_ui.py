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

    def _caret_end(self, box):
        """``set_text`` 后光标停在开头；候选触发以光标为准，测试统一放到行尾。"""
        box.input.mark_set('insert', 'end-1c')

    def test_slash_completion_opens_and_escape_closes(self):
        box = self._make()
        box.set_text('/sto')
        self._caret_end(box)
        box._on_key_release(SimpleNamespace(keysym='s'))
        self.win.update()
        self.assertTrue(box.candidates.open)
        self.assertGreater(len(box.candidates.entries), 0)
        labels = [e['label'] for e in box.candidates.entries]
        self.assertTrue(any('storyboard' in label for label in labels))
        box.close_completion()
        self.assertFalse(box.candidates.open)

    def test_completion_prefers_current_stage_skills(self):
        box = self._make(stage='storyboard')
        box.set_text('/')
        self._caret_end(box)
        box._on_key_release(SimpleNamespace(keysym='/'))
        self.assertEqual(box.candidates.entries[0]['label'], '/mine-skill')
        box.close_completion()

    # ── R2980／REQ-S01-91：光标级 ``/`` 与 ``@`` 候选浮层 ──

    def test_slash_trigger_boundaries(self):
        """``/`` 只在行首或空白后触发：词中、URL、分数都不弹。"""
        box = self._make()
        for text in ('a/b', 'https://example.com', '3/4'):
            with self.subTest(text=text):
                box.set_text(text)
                self._caret_end(box)
                box._on_key_release(SimpleNamespace(keysym='x'))
                self.assertFalse(box.candidates.open, text)
        box.set_text('帮我 /sto 一下')
        self._caret_end(box)
        box.input.mark_set('insert', '1.7')  # 光标落在 /sto 词尾
        box._on_key_release(SimpleNamespace(keysym='o'))
        self.assertTrue(box.candidates.open, '行中 / 同样触发候选')

    def test_midline_slash_stays_plain_text_on_send(self):
        """行中选中的 ``/name `` 是普通文本：parse_command 仍只认开头 ``/``。"""
        box = self._make(stage='script')
        box.set_text('帮我 /sto 一下')
        self._caret_end(box)
        box.input.mark_set('insert', '1.7')
        box._on_key_release(SimpleNamespace(keysym='o'))
        self.assertTrue(box.candidates.open)
        entry = next(e for e in box.candidates.entries if e['name'] == 'storyboard')
        box._apply_candidate(entry)
        self.assertEqual(box.input.get('1.0', 'end-1c'), '帮我 /storyboard 一下')
        self.assertTrue(box.send())
        text, parsed = self.sent[0]
        self.assertIsNone(parsed, '行中 / 命令不执行')

    def test_live_filter_narrows_entries(self):
        box = self._make()
        box.set_text('/')
        self._caret_end(box)
        box._on_key_release(SimpleNamespace(keysym='/'))
        all_count = len(box.candidates.entries)
        box.set_text('/zzz-no-match')
        self._caret_end(box)
        box._on_key_release(SimpleNamespace(keysym='z'))
        self.assertFalse(box.candidates.open, '无命中时浮层收掉')
        box.set_text('/sto')
        self._caret_end(box)
        box._on_key_release(SimpleNamespace(keysym='o'))
        self.assertTrue(box.candidates.open)
        self.assertLess(len(box.candidates.entries), all_count, '继续输入实时过滤')

    def test_keyboard_navigation_and_enter_apply(self):
        box = self._make()
        box.set_text('/')
        self._caret_end(box)
        box._on_key_release(SimpleNamespace(keysym='/'))
        popup = box.candidates
        self.assertTrue(popup.open)
        self.assertGreaterEqual(len(popup.entries), 2)

        class _Event:
            keysym = 'Down'
        self.assertEqual(popup.key(_Event()), 'break')
        self.assertEqual(popup.index, 1, 'Down 移到第二项')
        _Event.keysym = 'Up'
        popup.key(_Event())
        self.assertEqual(popup.index, 0, 'Up 移回第一项')
        _Event.keysym = 'Tab'
        popup.key(_Event())
        self.assertFalse(popup.open, 'Tab 采纳后收掉浮层')
        value = box.input.get('1.0', 'end-1c')
        self.assertTrue(value.startswith('/'), '采纳把候选写回输入框')
        self.assertTrue(value.endswith(' '), '采纳结果带尾空格')

    def test_applied_token_gets_shared_tag(self):
        box = self._make()
        box.set_text('/')
        self._caret_end(box)
        box._on_key_release(SimpleNamespace(keysym='/'))
        box._apply_candidate(box.candidates.entries[0])
        ranges = box.input.tag_ranges('shared_token')
        self.assertTrue(ranges, '插入体应带 shared_token 底色 tag')
        covered = box.input.get(ranges[0], ranges[1])
        self.assertTrue(covered.startswith('/'), 'tag 覆盖 /name 段')

    def test_mention_candidates_and_apply_register_attachment(self):
        """``@`` 仅剧本页弹附件候选；采纳写 ``@显示名 `` 并登记本轮引用。"""
        from unittest import mock
        recorded = []
        fake_path = Path('proj_原始附件_人物设定_20261008.txt')
        with mock.patch('stage_execution_service.stage_idea_attachment_paths',
                        return_value=(fake_path,)):
            box = self._make(stage='script')
            box.desktop.idea_chat_controller = SimpleNamespace(
                add_attachment=lambda value: recorded.append(value))
            box.set_text('@人')
            self._caret_end(box)
            box._on_key_release(SimpleNamespace(keysym='r'))
            self.assertTrue(box.candidates.open)
            entry = box.candidates.entries[0]
            self.assertEqual(entry['kind'], 'attachment')
            self.assertEqual(entry['name'], '人物设定.txt')
            box._apply_candidate(entry)
        self.assertEqual(box.input.get('1.0', 'end-1c'), '@人物设定.txt ')
        self.assertEqual(recorded, [str(fake_path)], '@ 采纳登记本轮引用')
        # 非剧本页不弹 @ 候选。
        with mock.patch('stage_execution_service.stage_idea_attachment_paths',
                        return_value=(fake_path,)):
            box.set_stage('storyboard')
            box.set_text('@')
            self._caret_end(box)
            box._on_key_release(SimpleNamespace(keysym='@'))
            self.assertFalse(box.candidates.open, '其他阶段页 @ 不弹菜单')

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
        """面板开着时输入 / ：收掉图标面板、照常弹候选。"""
        box = self._make()
        box.open_skill_list()
        self.assertTrue(box.skill_panel.is_open())
        box.set_text('/')
        self._caret_end(box)
        box._on_key_release(SimpleNamespace(keysym='/'))
        self.win.update()
        self.assertFalse(box.skill_panel.is_open())
        self.assertTrue(box.candidates.open)


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
