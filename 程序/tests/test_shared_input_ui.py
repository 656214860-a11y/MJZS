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
        # 模型选择器是共享框内右侧的无外框下拉按钮（R2964：ttk.Button＋上方卡片浮层），非模态弹窗。
        from tkinter import ttk
        from ui_tokens import ICON_ADD, ICON_MICROPHONE, ICON_SEND, ICON_SKILL
        for label in (ICON_SKILL, ICON_ADD, ICON_MICROPHONE, ICON_SEND):
            self.assertIn(label, texts)
        picker = getattr(box, 'model_picker', None)
        self.assertIsNotNone(picker, '共享输入框内应有一颗模型下拉按钮')
        self.assertIsInstance(picker.models, ttk.Button, '模型下拉按钮是无外框按钮')
        self.assertTrue(str(picker.model.get()).strip(), '模型下拉按钮显示当前模型名')
        self.assertTrue(str(picker._display.get()).rstrip().endswith('▾'),
                        '模型下拉按钮文案带下拉箭头')
        self.assertIsInstance(box.input, tk.Text)
        # R2923：整个输入盒收进一张 Card——输入框在上、图标行在下（左✦＋🎤，右模型下拉＋发送）。
        self.assertEqual(box.input.master.winfo_class(), 'TFrame')
        row = box.input.master.winfo_children()[-1]
        self.assertEqual(row.winfo_class(), 'TFrame')

    def test_send_outline_is_circular_and_matches_icon_row(self):
        """REQ-S01-62: send/stop use an unfilled circle, not a solid PNG tile."""
        from tkinter import ttk
        from ui_tokens import COLORS
        box = self._make()
        self.win.deiconify()
        self.win.update()
        button = box.send_button
        self.assertFalse(str(button.cget('image')), '发送键只绘制 MDL2 字形，不再加载导航 PNG')
        style = ttk.Style(self.win)
        name = str(button.cget('style'))
        self.assertAlmostEqual(button.winfo_width(), button.winfo_height(), delta=2)
        self.assertAlmostEqual(button.winfo_rooty() + button.winfo_height() / 2,
                               box.voice_button.winfo_rooty() + box.voice_button.winfo_height() / 2,
                               delta=3)
        self.assertEqual(style.lookup(name, 'foreground', ('active',)), COLORS['primary'])
        self.assertEqual(style.lookup(name, 'foreground', ('disabled',)), COLORS['disabled_text'])
        self.assertEqual(str(box.voice_button.cget('style')), 'Tokens.Composer.Icon.TButton')

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

    # ── R2980／REQ-S01-92：光标级 ``/`` 与 ``@`` 候选浮层 ──

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

    # ── R2971／REQ-S01-91：✦／＋ 图标下拉面板（与 / 补全同款浮层） ──

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

    def test_add_menu_drilldown_keeps_panel_open(self):
        """＋下钻与返回后面板保持开：销毁被点行不再被误判成「点到面板外」（R3040）。"""
        box = self._make()
        box.open_add_menu()
        self.win.update_idletasks()
        panel = box.add_panel
        drill = next(w for w in self._panel_labels(panel)
                     if str(w.cget('text')) == '添加技能…')
        self._click(drill)
        self.assertTrue(panel.is_open(), '下钻后面板应保持打开')
        texts = [str(w.cget('text')) for w in self._panel_labels(panel)]
        self.assertEqual(texts, ['‹ 返回', '从仓库导入', '本地安装'])
        back = next(w for w in self._panel_labels(panel)
                    if str(w.cget('text')) == '‹ 返回')
        self._click(back)
        self.assertTrue(panel.is_open(), '返回后面板应保持打开')
        texts = [str(w.cget('text')) for w in self._panel_labels(panel)]
        self.assertEqual(texts, ['添加附件', '添加模型…', '添加技能…'])

    def test_skill_panel_checks_reflect_stage_config(self):
        """勾选框所见即真：打开按 stage_config 预填、点击即时取反写回且面板不关；
        跨阶段技能行不渲染勾选框、名称仍可点插入（R3040）。"""
        import stage_config
        from desktop_shared_menus import CHECK_SIZE
        from ui_icons import IconLoader
        box = self._make(stage='script')
        box._skill_list_items = lambda: [
            {'name': 'pipeline-script-preparation', 'stage': 'script'},
            {'name': 'mine-skill', 'stage': 'storyboard'}]
        box.open_skill_list()
        self.win.update_idletasks()
        panel = box.skill_panel
        self.assertTrue(panel.is_open())
        check = panel._check_rows.get('pipeline-script-preparation')
        self.assertIsNotNone(check, '本阶段技能应渲染勾选框')
        self.assertNotIn('mine-skill', panel._check_rows,
                         '跨阶段技能不渲染勾选框')
        # pipeline-script-preparation 是 script 阶段真实技能 → 默认勾选 → 预填已选。
        checked = IconLoader.check_indicator(panel, size=CHECK_SIZE,
                                             selected=True).name
        unchecked = IconLoader.check_indicator(panel, size=CHECK_SIZE,
                                               selected=False).name
        self.assertEqual(check.cget('image'), checked,
                         '默认技能打开时应预填勾选态')
        # 点击＝从默认移除：配置同步、勾选像翻转、面板保持开。
        self._click(check)
        self.assertTrue(panel.is_open(), '勾选点击后面板应保持打开')
        skills = stage_config.get(box.project, 'script').get('skills') or []
        self.assertNotIn('pipeline-script-preparation', skills)
        self.assertEqual(check.cget('image'), unchecked)
        # 再点加回：勾选像回到已选。
        self._click(check)
        skills = stage_config.get(box.project, 'script').get('skills') or []
        self.assertIn('pipeline-script-preparation', skills)
        self.assertEqual(check.cget('image'), checked)
        # 跨阶段行的名称仍可点插入 /名称。
        target = next(w for w in self._panel_labels(panel)
                      if str(w.cget('text')) == 'mine-skill')
        self._click(target)
        self.assertEqual(box.text(), '/mine-skill')

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

    # ── R3031：✦／＋ 面板与 / 候选浮层的真实几何回归 ──

    def _make_bottom(self, **kwargs):
        """输入框贴窗口底部（与 Desktop ``pack(before=status_label)`` 同构），供 winfo 实尺断言。"""
        options = {'on_send': lambda text, parsed: self.sent.append((text, parsed)) or True,
                   'skills': [SimpleNamespace(name='mine-skill', stage='storyboard')],
                   'engines': ()}
        options.update(kwargs.pop('options', {}))
        filler = tk.Frame(self.win)
        filler.pack(fill='both', expand=True)
        box = shared_input.SharedStageInput(self.win, desktop=self.desktop,
                                            options=options, **kwargs)
        box.pack(side='bottom', fill='x')
        self.win.deiconify()
        self.win.geometry('1000x800')
        for _ in range(6):
            self.win.update_idletasks()
            self.win.update()
        self.addCleanup(box.destroy)
        return box

    @staticmethod
    def _bottom(widget):
        return widget.winfo_rooty() + widget.winfo_height()

    def test_icon_panels_bottom_sits_one_row_above_icon_row(self):
        """✦／＋ 面板底边应在图标行上方一行内——用户定版：不隔着整个输入框。"""
        from ui_tokens import SPACING
        box = self._make_bottom()
        row = box.skill_button.master
        for open_panel, panel in ((box.open_skill_list, box.skill_panel),
                                  (box.open_add_menu, box.add_panel)):
            with self.subTest(panel=panel):
                open_panel()
                self.win.update_idletasks()
                self.assertTrue(panel.is_open())
                gap = row.winfo_rooty() - self._bottom(panel)
                self.assertLessEqual(self._bottom(panel), row.winfo_rooty() + 1,
                                     '面板底边不应压住图标行')
                self.assertLessEqual(gap, SPACING['sm'],
                                     '面板底边距图标行上沿 %dpx，期望≈%dpx（xs 刻度）'
                                     % (gap, SPACING['xs']))
                box.close_completion()

    def test_candidates_clamped_to_cursor_monitor_not_primary_screen(self):
        """副屏（主屏右侧之外）窗口：候选浮层宽度与横向锚点跟随光标所在显示器，
        不得被 ``winfo_screenwidth``（恒为主屏宽）钳成一条窄缝贴到窗口左缘。"""
        from unittest import mock
        import desktop_shared_menus
        from ui_tokens import SPACING
        box = self._make_bottom()
        screen_w = self.win.winfo_screenwidth()
        screen_h = self.win.winfo_screenheight()
        self.win.geometry('1000x800+%d+80' % (screen_w + 400))
        for _ in range(4):
            self.win.update_idletasks()
            self.win.update()
        fake_bounds = (screen_w, 0, screen_w + 2000, screen_h)
        box.set_text('/')
        box.input.mark_set('insert', 'end-1c')
        with mock.patch.object(desktop_shared_menus, 'monitor_bounds',
                               return_value=fake_bounds, create=True):
            box._on_key_release(SimpleNamespace(keysym='/'))
            self.win.update()
        self.assertTrue(box.candidates.open)
        frame = box.candidates.frame
        self.assertGreater(frame.winfo_width(), SPACING['md'] * 8,
                           '副屏上候选浮层被钳成 %dpx 宽' % frame.winfo_width())
        box_pos = box.input.bbox('insert')
        cursor_x = box.input.winfo_rootx() + box_pos[0]
        self.assertAlmostEqual(frame.winfo_rootx(), cursor_x, delta=SPACING['md'],
                               msg='候选浮层应锚在光标处，而非被钳到窗口左缘')


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

    def test_s03_episode_script_does_not_block_send(self):
        """REQ-S03-55：模型按集写的结构稿没有派生清单，S03 发送不再被 S02 核验拦。"""
        import script_contract
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / 'project'
        path = script_contract.canonical_structured_script_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '# 第1集：咖啡馆初遇\n\n'
            '## 分场结构\n\n'
            '### 场景 01：咖啡馆·内景·日\n\n'
            '- 出场角色：林夏、陈默\n\n'
            '陈默：你终于来了。\n', encoding='utf-8')
        error = shared_input.upstream_send_error(root, 'storyboard')
        self.assertEqual(error, '', '有可用结构稿时 S03 发送门禁必须放行')
        notes = []
        status = SimpleNamespace(set=notes.append)
        error = shared_input.upstream_send_error(root, 'storyboard', status)
        self.assertEqual(error, '')
        self.assertTrue(any('不影响分镜制作' in note for note in notes),
                        '清单补不了时应把说明写进状态栏：%r' % notes)

    def test_s03_without_script_blocks_with_guidance(self):
        """REQ-S03-55：没有可用结构稿才拦截，文案指引去「剧本结构」页确认。"""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / 'project'
        root.mkdir()
        error = shared_input.upstream_send_error(root, 'storyboard')
        self.assertTrue(error)
        self.assertIn('结构剧本', error)
        self.assertIn('确认一份结构剧本', error)
        self.assertNotIn('清单未通过核验', error)


class StoryboardSendReadinessTests(unittest.TestCase):
    """REQ-S03-55：S03 发送就绪度——有可用结构稿即可发；清单能派生就补，补不了只提示。"""

    RAW_REL = '01剧本准备/output/script_raw.md'
    RAW_TEXT = '第1场 咖啡馆 内景\n林夏：你好，我是黑发的人。\n陈默：道具：旧怀表\n林夏：走吧。'
    EPISODIC = ('# 第1集：咖啡馆初遇\n\n## 分场结构\n\n### 场景 01：咖啡馆·内景·日\n\n'
                '- 出场角色：林夏、陈默\n\n陈默：你终于来了。\n')

    def setUp(self):
        import script_contract
        import stage_completion_service
        self.contract = script_contract
        self.readiness = stage_completion_service.storyboard_send_readiness
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        self.root.mkdir()
        raw = self.root / self.RAW_REL
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_text(self.RAW_TEXT, encoding='utf-8')

    def _script(self, text):
        path = self.contract.canonical_structured_script_path(self.root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def _standard(self, source=None):
        return self.contract.structure_script(
            self.RAW_TEXT, source if source is not None else self.RAW_REL)

    def test_complete_manifests_send_without_note(self):
        """清单齐全：可发送、无说明、不标已补。"""
        path = self._script(self._standard())
        self.contract.write_structure_manifests(self.root, self._standard())
        self.assertEqual(self.contract.structure_manifest_problems(self.root, path), [])
        self.assertEqual(self.readiness(self.root), (True, '', False))

    def test_missing_manifests_are_derived_and_filled(self):
        """清单缺失但稿可派生：自动补写一次后放行，说明已补全。"""
        self._script(self._standard())
        sendable, note, filled = self.readiness(self.root)
        self.assertTrue(sendable)
        self.assertTrue(filled)
        self.assertIn('补全清单', note)
        folder = self.contract.structure_manifest_dir(self.root)
        for name in self.contract.STRUCTURE_MANIFESTS:
            self.assertTrue((folder / name).is_file(), name)

    def test_stale_manifests_are_rewritten_from_script(self):
        """手改过的清单与稿不一致：按当前稿重写一次后放行。"""
        import json
        path = self._script(self._standard())
        folder = self.contract.write_structure_manifests(self.root, self._standard())
        target = folder / 'scene_manifest.json'
        stale = json.loads(target.read_text(encoding='utf-8'))
        stale['items'][0]['name'] = '别的场景'
        target.write_text(json.dumps(stale, ensure_ascii=False), encoding='utf-8')
        sendable, note, filled = self.readiness(self.root)
        self.assertTrue(sendable)
        self.assertTrue(filled)
        self.assertEqual(self.contract.structure_manifest_problems(self.root, path), [])

    def test_episode_script_notice_does_not_block(self):
        """模型按集写的稿派生不出名单：可发送，说明只进状态栏不拦截。"""
        self._script(self.EPISODIC)
        sendable, note, filled = self.readiness(self.root)
        self.assertTrue(sendable)
        self.assertFalse(filled)
        self.assertIn('未能自动生成', note)
        self.assertIn('不影响分镜制作', note)

    def test_no_usable_script_blocks_with_guidance(self):
        """没有任何结构稿：拦截，文案指引去「剧本结构」页确认。"""
        sendable, note, filled = self.readiness(self.root)
        self.assertFalse(sendable)
        self.assertFalse(filled)
        self.assertIn('结构剧本', note)
        self.assertIn('确认一份结构剧本', note)

    def test_script_with_deleted_source_is_not_usable(self):
        """唯一结构稿的来源原稿已删：不算可用，仍拦截。"""
        self._script(self._standard(source='01剧本准备/output/deleted_raw.md'))
        sendable, note, filled = self.readiness(self.root)
        self.assertFalse(sendable)
        self.assertIn('确认一份结构剧本', note)


if __name__ == '__main__':
    unittest.main()
