"""R2893 轮 3：共享输入框组件——布局、``/`` 补全、发送门禁与模型快照（真 Tk 隐藏桌面）。"""
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace

import desktop_shared_input as shared_input
import desktop_shared_send as shared_send
import ui.desktop_shared_input_extras as input_extras
from contract import pet_bus
from ui_shortcuts import ShortcutRegistry
from unittest import mock


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
                   'on_upstream_error': shared_send.upstream_send_error,
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

    def test_send_art_is_filled_circle_and_matches_icon_row(self):
        """REQ-S01-62/REQ-S01-112：发送键仍是与图标行同高的圆形底图——
        契约变更（UX-CHAT-INPUT-EXTRAS）：由「无图元描边圆环」改为
        ``element_photo`` 实心圆＋居中 MDL2 字形（``compound='center'``）。"""
        from tkinter import ttk
        from ui_tokens import COLORS
        box = self._make()
        self.win.deiconify()
        self.win.update()
        button = box.send_button
        input_extras.sync_send_art(box)
        self.assertTrue(str(button.cget('image')), '发送键应有实心圆底图（契约变更）')
        self.assertEqual(str(button.cget('compound')), 'center')
        style = ttk.Style(self.win)
        name = str(button.cget('style'))
        self.assertAlmostEqual(button.winfo_width(), button.winfo_height(), delta=2)
        self.assertAlmostEqual(button.winfo_rooty() + button.winfo_height() / 2,
                               box.voice_button.winfo_rooty() + box.voice_button.winfo_height() / 2,
                               delta=3)
        # REQ-S01-112 契约变更：实心圆底图上字形走 on_accent，禁用仍 disabled_text。
        self.assertEqual(style.lookup(name, 'foreground', ('active',)), COLORS['on_accent'])
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
        self.win.update()
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
                self.win.update()
                self.assertFalse(box.candidates.open, text)
        box.set_text('帮我 /sto 一下')
        self._caret_end(box)
        box.input.mark_set('insert', '1.7')  # 光标落在 /sto 词尾
        box._on_key_release(SimpleNamespace(keysym='o'))
        self.win.update()
        self.assertTrue(box.candidates.open, '行中 / 同样触发候选')

    def test_midline_slash_stays_plain_text_on_send(self):
        """行中选中的 ``/name `` 是普通文本：parse_command 仍只认开头 ``/``。"""
        box = self._make(stage='script')
        box.set_text('帮我 /sto 一下')
        self._caret_end(box)
        box.input.mark_set('insert', '1.7')
        box._on_key_release(SimpleNamespace(keysym='o'))
        self.win.update()
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
        self.win.update()
        all_count = len(box.candidates.entries)
        box.set_text('/zzz-no-match')
        self._caret_end(box)
        box._on_key_release(SimpleNamespace(keysym='z'))
        self.win.update()
        self.assertFalse(box.candidates.open, '无命中时浮层收掉')
        box.set_text('/sto')
        self._caret_end(box)
        box._on_key_release(SimpleNamespace(keysym='o'))
        self.win.update()
        self.assertTrue(box.candidates.open)
        self.assertLess(len(box.candidates.entries), all_count, '继续输入实时过滤')

    def test_keyboard_navigation_and_enter_apply(self):
        box = self._make()
        box.set_text('/')
        self._caret_end(box)
        box._on_key_release(SimpleNamespace(keysym='/'))
        self.win.update()
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
        self.win.update()
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
            self.win.update()
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
            self.win.update()
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
                   'on_upstream_error': shared_send.upstream_send_error,
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
        self.assertEqual(shared_send.upstream_send_error(None, 'script'), '')
        self.assertEqual(shared_send.upstream_send_error(None, ''), '')
        self.assertEqual(shared_send.upstream_send_error(None, 'not-a-stage'), '')

    def test_gated_stage_upstream_ready_passes(self):
        from unittest import mock
        import stage_parallel
        ready = {'verdict': stage_parallel.PASS, 'ok': True, 'from': 'animatic'}
        with mock.patch.object(stage_parallel, 'evaluate', return_value=ready):
            self.assertEqual(shared_send.upstream_send_error(object(), 'assets'), '')

    def test_gated_stage_blocked_reports_reason(self):
        from unittest import mock
        import stage_parallel
        blocked = {'verdict': stage_parallel.BLOCKED, 'ok': False, 'from': 'animatic',
                   'detail': '预演未确认', 'reject': '先确认预演'}
        with mock.patch.object(stage_parallel, 'evaluate', return_value=blocked):
            error = shared_send.upstream_send_error(object(), 'assets')
        self.assertTrue(error)

    def test_ungated_stage_upstream_complete_passes(self):
        from unittest import mock
        with mock.patch('stage_completion_service.completion_evidence', return_value=(True, '')), \
                mock.patch('stage_parallel.stage_state', return_value=''):
            self.assertEqual(shared_send.upstream_send_error(object(), 'audio'), '')

    def test_ungated_stage_upstream_blank_rejected(self):
        from unittest import mock
        with mock.patch('stage_completion_service.completion_evidence',
                        return_value=(False, '没有视频成果')), \
                mock.patch('stage_parallel.stage_state', return_value=''):
            error = shared_send.upstream_send_error(object(), 'audio')
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
        notes = []
        status = SimpleNamespace(set=notes.append)
        error = shared_send.upstream_send_error(root, 'storyboard', status)
        self.assertEqual(error, '', '有可用结构稿时 S03 发送门禁必须放行')
        self.assertEqual(script_contract.structure_manifest_problems(root), [])
        self.assertFalse(any('未能' in note for note in notes),
                         '不应向状态栏输出「未能自动生成」类报错：%r' % notes)

    def test_s03_without_script_blocks_with_guidance(self):
        """REQ-S03-55：没有可用结构稿才拦截，文案指引去「剧本结构」页确认。"""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / 'project'
        root.mkdir()
        error = shared_send.upstream_send_error(root, 'storyboard')
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
        """模型按集／分场写的稿自动从分场与出场角色派生清单；纯叙述稿无名单也静默放行，不报未能自动生成。"""
        self._script(self.EPISODIC)
        sendable, note, filled = self.readiness(self.root)
        self.assertTrue(sendable)
        self.assertTrue(filled, '分场式结构稿应自动提取角色与场景补全清单')
        self.assertNotIn('未能', note)
        self.assertEqual(self.contract.structure_manifest_problems(self.root), [])
        # 纯叙述且无任何可提取条目：静默放行，不向状态栏报红字「未能自动生成」。
        self._script('# 第1集\n\n一段没有场次标题与角色标注的概要正文。\n')
        for path in self.contract.structure_manifest_dir(self.root).glob('*.json'):
            path.unlink()
        sendable, note, filled = self.readiness(self.root)
        self.assertTrue(sendable)
        self.assertFalse(filled)
        self.assertEqual(note, '')
        self.assertNotIn('未能', note)

    def test_llm_formatted_archives_auto_derive_manifests(self):
        """模型生成的变体标题／加粗键／列表／表格结构稿也能自动补全三份清单，不再报未能自动生成。"""
        self._script(
            '# 结构剧本\n\n'
            '## 一、角色清单\n\n'
            '### 林夏\n'
            '- **别名**：小夏\n'
            '- **默认服装**：白色风衣\n\n'
            '## 2. 场景设定\n\n'
            '- 咖啡馆：靠窗木桌、午后斜阳\n\n'
            '## 道具表\n\n'
            '| 道具 | 说明 |\n'
            '| --- | --- |\n'
            '| 旧怀表 | 银壳裂纹 |\n'
        )
        sendable, note, filled = self.readiness(self.root)
        self.assertTrue(sendable)
        self.assertTrue(filled)
        self.assertIn('补全清单', note)
        self.assertEqual(self.contract.structure_manifest_problems(self.root), [])

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


class CandidateHintCardTests(unittest.TestCase):
    """REQ-S01-106（UX-SLASH-HINT 轮）：``/`` 候选同行用途卡。

    整行（名称、徽标、留白）悬停与上下键都驱动同一张被动说明卡；进卡不闪、
    离开约 200ms 延迟收；右侧不足翻左并钳当前显示器；采纳／Esc／切页／销毁
    关卡并取消计时器；说明只取 hint，绝不进入发送正文。真 Tk 隐藏桌面量几何。
    """

    def setUp(self):
        self.win = tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        self.root.mkdir()
        self.desktop = SimpleNamespace(root=self.root,
                                       status=tk.StringVar(master=self.win, value=''),
                                       win=self.win)
        self.sent = []

    def _make(self, skills=None):
        options = {'on_send': lambda text, parsed: self.sent.append((text, parsed)) or True,
                   'on_upstream_error': shared_send.upstream_send_error,
                   'skills': skills if skills is not None else [
                       SimpleNamespace(name='mine-skill', stage='storyboard', description='用途甲')],
                   'engines': ()}
        filler = tk.Frame(self.win)
        filler.pack(fill='both', expand=True)
        box = shared_input.SharedStageInput(self.win, desktop=self.desktop, options=options)
        box.pack(side='bottom', fill='x')
        self.win.deiconify()
        self.win.geometry('1000x800+40+40')
        for _ in range(6):
            self.win.update_idletasks()
            self.win.update()
        self.addCleanup(lambda: box.destroy() if box.winfo_exists() else None)
        self.win.focus_force()
        box.input.focus_set()
        self.win.update()
        return box

    def _open(self, box, text='/'):
        box.set_text(text)
        box.input.mark_set('insert', 'end-1c')
        box._on_key_release(SimpleNamespace(keysym='x'))
        self.win.update()

    def _hover(self, widget):
        widget.event_generate('<Enter>', x=2, y=2)
        self.win.update()

    def _row(self, box, index=0):
        return box.candidates._rows[index]['widgets'][0]

    def _name_label(self, box, index=0):
        return next(w for w in box.candidates._rows[index]['widgets']
                    if w.winfo_class() == 'Label' and str(w.cget('text') or '').startswith('/'))

    def _badge(self, box, index=0):
        from ui.desktop_shared_menus import KIND_BADGES
        row = box.candidates._rows[index]
        text = KIND_BADGES.get(str(row['entry'].get('kind') or ''), '')
        return next(w for w in row['widgets']
                    if w.winfo_class() == 'Label' and str(w.cget('text') or '') == text)

    def _card_text(self, box):
        card = getattr(box, '_skill_card', None)
        if card is None:
            return None
        labels = [w for w in _descendants(card) if isinstance(w, tk.Label)]
        return '\n'.join(str(w.cget('text')) for w in labels)

    def _pump(self, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.win.update()
            time.sleep(0.01)

    def test_hover_name_badge_and_blank_show_single_side_card(self):
        box = self._make()
        self._open(box)
        self.assertTrue(box.candidates.open)
        row = self._row(box)
        box.input.focus_set()
        self.win.update()
        focus_before = self.win.focus_get()
        # 名称段悬停：右侧同行出现一张用途卡。
        self._hover(self._name_label(box))
        card = box._skill_card
        self.assertIsNotNone(card, '悬停名称应出现用途卡')
        self.assertEqual(self._card_text(box), '用途甲')
        self.assertGreaterEqual(card.winfo_rootx(),
                                row.winfo_rootx() + row.winfo_width() - 1,
                                '用途卡锚在行右侧')
        row_cy = row.winfo_rooty() + row.winfo_height() / 2
        card_cy = card.winfo_rooty() + card.winfo_height() / 2
        self.assertAlmostEqual(card_cy, row_cy, delta=2, msg='用途卡与行纵向居中')
        self.assertIs(self.win.focus_get(), focus_before, '说明卡不抢输入焦点')
        # 徽标悬停：替换旧卡，同一时刻只有一张。
        self._hover(self._badge(box))
        self.assertIsNotNone(box._skill_card)
        self.assertFalse(card.winfo_exists(), '旧卡销毁，只留一张')
        self.assertEqual(self._card_text(box), '用途甲')
        # 行框留白悬停同样出卡。
        self._hover(row)
        self.assertEqual(self._card_text(box), '用途甲')
        self.assertIs(self.win.focus_get(), focus_before)

    def test_keyboard_navigation_syncs_card(self):
        box = self._make()
        self._open(box)
        popup = box.candidates
        self.assertGreaterEqual(len(popup.entries), 2)
        box.input.focus_set()
        self.win.update()
        focus_before = self.win.focus_get()

        class _Event:
            keysym = 'Down'
        self.assertEqual(popup.key(_Event()), 'break')
        self.win.update()
        self.assertEqual(popup.index, 1)
        # 第二项是阶段别名（无注册描述）→ 显示「暂无用途说明」，不编造。
        self.assertEqual(self._card_text(box), '暂无用途说明')
        self.assertIs(self.win.focus_get(), focus_before)
        _Event.keysym = 'Up'
        popup.key(_Event())
        self.win.update()
        self.assertEqual(popup.index, 0)
        self.assertEqual(self._card_text(box), '用途甲')
        self.assertIs(self.win.focus_get(), focus_before)

    def test_enter_card_no_flash_and_leave_delayed_hide(self):
        box = self._make()
        self._open(box)
        row = self._row(box)
        self._hover(row)
        card = box._skill_card
        self.assertIsNotNone(card)
        # 离开行：排定延迟收，不立即消失。
        row.event_generate('<Leave>')
        self.win.update()
        self.assertIsNotNone(getattr(box, '_skill_card_hide_id', None))
        self.assertIsNotNone(box._skill_card)
        # 移入卡：取消待收，不闪退。
        card.event_generate('<Enter>', x=2, y=2)
        self.win.update()
        self.assertIsNone(getattr(box, '_skill_card_hide_id', None))
        self.assertTrue(card.winfo_exists())
        # 移出卡：重新计时，约 200ms 后收。
        card.event_generate('<Leave>')
        self.win.update()
        self.assertIsNotNone(box._skill_card, '离开不立即收')
        self._pump(0.4)
        self.assertIsNone(box._skill_card, '延迟到点收掉')

    def test_close_on_adopt_escape_stage_and_destroy(self):
        box = self._make()
        # 采纳关卡。
        self._open(box)
        self._hover(self._row(box))
        self.assertIsNotNone(box._skill_card)
        box._apply_candidate(box.candidates.entries[0])
        self.win.update()
        self.assertIsNone(box._skill_card)
        self.assertFalse(box.candidates.open)
        self.assertIsNone(getattr(box, '_skill_card_hide_id', None))
        # Esc 关卡。
        self._open(box)
        self._hover(self._row(box))
        self.assertIsNotNone(box._skill_card)
        box.close_completion()
        self.win.update()
        self.assertIsNone(box._skill_card)
        # 切页关卡。
        self._open(box)
        self._hover(self._row(box))
        self.assertIsNotNone(box._skill_card)
        box.set_stage('assets')
        self.win.update()
        self.assertIsNone(box._skill_card)
        # 销毁：清卡、取消迟到回调，不留幽灵窗口。
        self._open(box)
        self._hover(self._row(box))
        card = box._skill_card
        self._row(box).event_generate('<Leave>')
        self.win.update()
        self.assertIsNotNone(box._skill_card_hide_id)
        errors = []
        self.win.report_callback_exception = lambda exc, val, tb: errors.append(val)
        box.destroy()
        self.win.update()
        self.assertFalse(card.winfo_exists(), '销毁后用途卡不留幽灵窗口')
        self.assertIsNone(box._skill_card_hide_id, '销毁取消延迟计时器')
        self._pump(0.3)
        self.assertEqual(errors, [], '销毁后不得有迟到回调触发')

    def test_flip_left_and_clamp_to_monitor(self):
        from unittest import mock
        from ui_tokens import SPACING
        box = self._make()
        self._open(box)
        row = self._row(box)
        self.win.update()
        row_left = row.winfo_rootx()
        row_right = row_left + row.winfo_width()
        screen_h = self.win.winfo_screenheight()
        # 注入右侧不足的显示器矩形 → 翻到行左侧并钳在该显示器内。
        fake = (row_left - 600, 0, row_right + SPACING['xs'], screen_h)
        with mock.patch.object(shared_input, 'monitor_bounds', return_value=fake):
            self._hover(row)
        card = box._skill_card
        self.assertIsNotNone(card)
        self.win.update()
        # 建卡可能触发候选浮层重排，按行的最终位置断言翻转结果。
        row_left = row.winfo_rootx()
        self.assertLessEqual(card.winfo_rootx() + card.winfo_width(), row_left + 1,
                             '右侧不足翻到行左侧')
        self.assertGreaterEqual(card.winfo_rootx(), fake[0], '钳在当前显示器左界内')
        self.assertLessEqual(card.winfo_rootx() + card.winfo_width(), fake[2])
        self.assertGreaterEqual(card.winfo_rooty(), 0)
        self.assertLessEqual(card.winfo_rooty() + card.winfo_height(), screen_h)
        # 窗口缩小后重悬停：仍钳在真实屏幕内，不截断。
        self.win.geometry('500x400+40+40')
        for _ in range(4):
            self.win.update_idletasks()
            self.win.update()
        self._hover(row)
        card = box._skill_card
        self.assertIsNotNone(card)
        self.assertGreaterEqual(card.winfo_rootx(), 0)
        self.assertLessEqual(card.winfo_rootx() + card.winfo_width(),
                             self.win.winfo_screenwidth())

    def test_hint_never_in_send_body_and_enter_adopts(self):
        box = self._make()
        self._open(box, '/mine')
        popup = box.candidates
        self.assertTrue(popup.open)
        entry = next(e for e in popup.entries if e['name'] == 'mine-skill')
        self.assertEqual(entry['hint'], '用途甲')

        class _Return:
            state = 0
        self.assertEqual(box._on_return(_Return()), 'break')
        self.assertEqual(self.sent, [], '候选开着 Enter 只采纳不发送')
        value = box.input.get('1.0', 'end-1c')
        self.assertEqual(value, '/mine-skill ', '采纳只替换触发词并补空格')
        self.assertNotIn('用途甲', value)
        # 续写后发送：说明永不进入正文。
        box.input.insert('end-1c', '写一段开场')
        box.input.mark_set('insert', 'end-1c')
        self.assertTrue(box.send())
        self.assertEqual(self.sent[0][0], '/mine-skill 写一段开场')
        self.assertNotIn('用途甲', self.sent[0][0])

    def test_slash_and_skill_panel_show_descriptions_and_stage_placeholders(self):
        """第 7／8 项：各阶段输入框都有 Agent 风格占位提示；/ 与 ✦ 默认展示行内简述与右侧说明卡。"""
        import desktop_shared_send as shared_send
        box = self._make()
        for stage in ('script', 'script_structure', 'storyboard', 'assets'):
            shared_send.sync_stage_placeholder(box, stage)
            self.assertTrue(bool(box.input._placeholder), f'{stage} 阶段应设置输入框提示文字')
            self.assertIn('/', box.input._placeholder)
        # / 唤出即展示首项右侧说明卡，且行内包含简述标签。
        self._open(box, '/')
        self.assertIsNotNone(box._skill_card, '输入 / 后应立即显示右侧技能说明卡')
        self.assertEqual(self._card_text(box), '用途甲')
        row_texts = [str(w.cget('text')) for w in box.candidates._rows[0]['widgets']
                     if 'text' in w.keys()]
        self.assertTrue(any('用途甲' in t for t in row_texts), f'/ 候选行应带行内说明：{row_texts}')
        box.close_completion()
        self.win.update()
        # ✦ 面板展开后同样具备行内简述并自动展示首行右侧说明卡。
        box.open_skill_list()
        self._pump(0.15)
        self.assertTrue(box.skill_panel.is_open())
        first_item = box._skill_list_items()[0]
        first_desc = box._skill_description(first_item)
        self.assertTrue(first_desc, '首行注册技能应带 description')
        panel_texts = [str(w.cget('text')) for w in _descendants(box.skill_panel)
                       if 'text' in w.keys()]
        self.assertTrue(any(first_desc[:10] in t for t in panel_texts),
                        f'✦ 列表行应带行内说明：{panel_texts}')
        self.assertIsNotNone(box._skill_card, '展开 ✦ 面板后应默认弹出右侧说明卡')
        self.assertEqual(self._card_text(box), first_desc)


class SharedInputFlowDefectTests(unittest.TestCase):
    """UX-INPUT-FLOW（REQ-S01-107）：连续输入、候选选择、多行编辑、防误发与草稿不丢。

    全部真 Tk 隐藏桌面＋临时项目目录；Windows 拼音组词不在自动化覆盖内，
    人工验收项见结果文件（此处只钉「组词中事件不消费」的接口行为）。
    """

    def setUp(self):
        self.win = tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        self.root.mkdir()
        self.desktop = SimpleNamespace(root=self.root,
                                       status=tk.StringVar(master=self.win, value=''),
                                       win=self.win)
        self.sent = []

    def _options(self, **over):
        options = {'on_send': lambda text, parsed: self.sent.append((text, parsed)) or True,
                   'on_upstream_error': shared_send.upstream_send_error,
                   'skills': [SimpleNamespace(name='mine-skill', stage='storyboard',
                                              description='用途甲')],
                   'engines': ()}
        options.update(over)
        return options

    def _make(self, **kwargs):
        options = self._options(**kwargs.pop('options', {}))
        box = shared_input.SharedStageInput(self.win, desktop=self.desktop,
                                            options=options, **kwargs)
        box.pack(fill='x')
        self.win.update_idletasks()
        self.addCleanup(box.destroy)
        return box

    def _make_bottom(self, **kwargs):
        """输入框贴窗口底部（与 Desktop 排布同构），供真实几何断言。"""
        options = self._options(**kwargs.pop('options', {}))
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

    def _caret_end(self, box):
        box.input.mark_set('insert', 'end-1c')

    def _settle(self, times=4):
        for _ in range(times):
            self.win.update()

    def _open_candidates(self, box, text='/'):
        box.set_text(text)
        self._caret_end(box)
        box._on_key_release(SimpleNamespace(keysym='/'))
        self._settle()

    # ── 撤销／重做／全选与多行编辑 ─────────────────────────────────────

    def test_native_undo_redo_and_select_all(self):
        """隐藏桌面投递不了 Control/字母 KeyPress（同 test_script_undo_shortcuts）：
        键位投递由 Tk 负责，这里断言控件真实绑定串＋直调处理入口。"""
        box = self._make()
        self.assertTrue(box.input.bind('<Control-Key-z>'), 'Ctrl+Z 须真实绑到输入框')
        self.assertTrue(box.input.bind('<Control-Key-y>'), 'Ctrl+Y 须真实绑到输入框')
        self.assertTrue(box.input.bind('<Control-Key-a>'), 'Ctrl+A 须真实绑到输入框')
        box.set_text('第一段草稿')
        box.input.edit_undo()
        self._settle()
        self.assertEqual(box.input.get('1.0', 'end-1c'), '', 'Ctrl+Z 应撤销输入')
        box.input.edit_redo()
        self._settle()
        self.assertEqual(box.input.get('1.0', 'end-1c'), '第一段草稿')
        box.input._do_select_all()
        ranges = box.input.tag_ranges('sel')
        self.assertTrue(ranges, 'Ctrl+A 应全选')
        self.assertEqual(box.input.get(ranges[0], ranges[1]), '第一段草稿')

    def test_candidate_adopt_is_one_undoable_step(self):
        box = self._make(stage='storyboard')
        self._open_candidates(box)
        self.assertTrue(box.candidates.open)
        box._apply_candidate(box.candidates.entries[0])
        applied = box.input.get('1.0', 'end-1c')
        self.assertTrue(applied.startswith('/') and applied.endswith(' '))
        box.input.edit_undo()
        self.assertEqual(box.input.get('1.0', 'end-1c'), '/',
                         '候选采纳（删 token＋插 /name ）应是一次可撤销动作')

    def test_multiline_insert_and_paste_never_send(self):
        box = self._make()
        box.input.insert('1.0', '第一行\n第二行\n第三行')
        self._settle()
        self.assertEqual(self.sent, [], '多行插入不得触发发送')
        self.assertEqual(box.input.get('1.0', 'end-1c'), '第一行\n第二行\n第三行')
        try:
            self.win.clipboard_clear()
            self.win.clipboard_append('剪贴一\n剪贴二')
            self._caret_end(box)
            box.input.event_generate('<<Paste>>')
            self._settle()
            self.assertIn('剪贴一\n剪贴二', box.input.get('1.0', 'end-1c'))
        except tk.TclError:
            pass  # 隐藏桌面无剪贴板时，多行不发送已由直接插入覆盖
        self.assertEqual(self.sent, [], '多行粘贴不得触发发送')

    def test_rewind_overwrite_is_undoable(self):
        import desktop_idea_bubbles as bubbles
        box = self._make()
        box.set_text('手头的稿子')
        host = SimpleNamespace(idea_input=box.input,
                               _idea_display_rows=lambda: ({'text': '回退那条'},),
                               status=self.desktop.status)
        bubbles.IdeaBubblesMixin.rewind_bubble_message(host, 0)
        self.assertEqual(box.input.get('1.0', 'end-1c'), '回退那条')
        box.input.edit_undo()
        self.assertEqual(box.input.get('1.0', 'end-1c'), '手头的稿子',
                         '回退覆盖前须把原稿压进撤销栈，一次 Ctrl+Z 找回')

    # ── 高度随可见软换行 ────────────────────────────────────────────

    def test_height_follows_display_lines_sm_to_xl(self):
        from ui_tokens import TEXT_ROWS
        box = self._make_bottom()
        self.assertEqual(int(box.input.cget('height')), TEXT_ROWS['sm'])
        box.set_text('\n'.join('第%d行' % i for i in range(6)))
        self._settle()
        self.assertEqual(int(box.input.cget('height')), 6, '6 行正文应撑到 6 行高')
        box.set_text('\n'.join('第%d行' % i for i in range(30)))
        self._settle()
        self.assertEqual(int(box.input.cget('height')), TEXT_ROWS['xl'],
                         '超出上限停在 xl=10，框内滚动')
        box.set_text('')
        self._settle()
        self.assertEqual(int(box.input.cget('height')), TEXT_ROWS['sm'],
                         '删空回最小高度')

    def test_short_window_keeps_tool_row_visible(self):
        box = self._make_bottom()
        self.win.geometry('760x280')
        box.set_text('\n'.join('第%d行' % i for i in range(40)))
        self._settle(6)
        win_bottom = self.win.winfo_rooty() + self.win.winfo_height()
        icon_bottom = box.icon_row.winfo_rooty() + box.icon_row.winfo_height()
        self.assertGreaterEqual(box.icon_row.winfo_height(), 10, '图标行有真实高度')
        self.assertLessEqual(icon_bottom, win_bottom + 2, '工具行底边必须留在窗口内')

    # ── 候选浮层：不重建、保持选择、全量可达 ─────────────────────────

    def test_refresh_same_data_keeps_selection_and_rows(self):
        box = self._make()
        self._open_candidates(box)
        popup = box.candidates
        popup.move(1)
        rows_before = popup._rows
        widget_before = popup._rows[0]['widgets'][0]
        popup.refresh(popup.entries, query=popup.query)
        self.assertEqual(popup.index, 1, '同 token/query/数据不得重置高亮')
        self.assertIs(popup._rows, rows_before, '同数据不得销毁重建行')
        self.assertIs(popup._rows[0]['widgets'][0], widget_before)

    def test_selection_follows_same_kind_name_or_first(self):
        box = self._make()
        self._open_candidates(box)
        popup = box.candidates
        self.assertGreaterEqual(len(popup.entries), 3)
        popup.move(1)
        target = popup.selected()
        popup.refresh((popup.entries[0], target, popup.entries[2]), query=popup.query)
        self.assertIs(popup.selected(), target, '原 (kind,name) 仍在列表里时保持选中')
        popup.refresh((popup.entries[0],), query=popup.query)
        self.assertEqual(popup.index, 0, '原项消失才回落首项')

    def test_candidates_beyond_first_page_reachable(self):
        skills = [SimpleNamespace(name='skill-%02d' % i, stage='script')
                  for i in range(20)]
        box = self._make(options={'skills': skills})
        self._open_candidates(box)
        popup = box.candidates
        from ui.desktop_shared_menus import CANDIDATE_MAX_ROWS
        self.assertGreater(len(popup.entries), CANDIDATE_MAX_ROWS,
                           '测试前提：候选要超过首屏 12 行')
        for _ in range(len(popup.entries) - 1):
            popup.key(SimpleNamespace(keysym='Down'))
        self.assertEqual(popup.index, len(popup.entries) - 1,
                         '键盘必须能选到首屏之外的项')
        self.assertTrue(any(r['index'] == popup.index for r in popup._rows),
                        '高亮项必须滚进可见区')
        self.assertEqual(popup.selected()['name'], popup.entries[-1]['name'])
        popup._scroll(-len(popup.entries))
        self.assertEqual(popup._top, 0, '滚轮一路回顶')

    # ── 草稿不丢：按（项目, 阶段）分仓 ──────────────────────────────

    def test_stage_drafts_are_isolated_and_restored(self):
        box = self._make()
        box.set_text('剧本页的草稿')
        box.set_stage('storyboard')
        self.assertEqual(box.input.get('1.0', 'end-1c'), '',
                         '剧本草稿不得带进分镜页')
        box.set_text('分镜页的草稿')
        box.set_stage('script')
        self.assertEqual(box.input.get('1.0', 'end-1c'), '剧本页的草稿',
                         '切回剧本页恢复自己的草稿')
        box.set_stage('storyboard')
        self.assertEqual(box.input.get('1.0', 'end-1c'), '分镜页的草稿')

    def test_send_or_manual_clear_drops_stage_draft(self):
        box = self._make()
        box.set_text('发出去的')
        self.assertTrue(box.send())
        box.end_request()
        box.set_stage('storyboard')
        box.set_stage('script')
        self.assertEqual(box.input.get('1.0', 'end-1c'), '', '发送成功不回灌旧稿')
        box.set_text('删掉的')
        box.clear()
        box.set_stage('storyboard')
        box.set_stage('script')
        self.assertEqual(box.input.get('1.0', 'end-1c'), '', '手动删空同样清稿')

    def test_pick_skill_inserts_at_cursor_keeps_draft(self):
        box = self._make()
        box.set_text('先写了一半 ')
        self._caret_end(box)
        box._pick_skill({'name': 'mine-skill'})
        self.assertEqual(box.input.get('1.0', 'end-1c'), '先写了一半 /mine-skill ',
                         '点技能在光标处插入 /名，不得整框覆盖')

    def test_ref_block_sync_keeps_lines_user_extended(self):
        import desktop_idea_attachments as idea_attach_mixin
        box = self._make()
        box.input.delete('1.0', 'end')
        box.input.insert('1.0', '@a.txt\n@a.txt 我的补充\n正文行\n')
        box.input.tag_add('idea_ref', '1.0', '4.0')
        host = idea_attach_mixin.IdeaAttachmentsMixin()
        host.idea_input = box.input
        host.idea_attachment_paths = (Path('a.txt'),)
        host._idea_cursor_ref_names = set()
        host.shared_input = box
        host._sync_idea_ref_block()
        text = box.input.get('1.0', 'end-1c')
        self.assertIn('我的补充', text, '标签被用户扩写后不得误删')
        self.assertIn('正文行', text)
        self.assertEqual(text.splitlines()[0], '@a.txt', '引用区仍按本轮引用重建')

    # ── 防误发：IME、Esc 分层、在途防重 ─────────────────────────────

    def test_escape_consumes_one_layer_only(self):
        box = self._make()
        box.set_text('别动我')
        self.assertIsNone(box._on_escape(SimpleNamespace()),
                          '无浮层时 Esc 放行给宿主（运行中停止等）')
        self.assertEqual(box.input.get('1.0', 'end-1c'), '别动我', '空闲 Esc 不清草稿')
        box.open_add_menu()
        self.assertTrue(box.add_panel.is_open())
        self.assertEqual(box._on_escape(SimpleNamespace()), 'break')
        self.assertFalse(box.add_panel.is_open())
        self._open_candidates(box)
        self.assertEqual(box._on_escape(SimpleNamespace()), 'break')
        self.assertFalse(box.candidates.open)

    def test_ime_composing_events_are_not_consumed(self):
        box = self._make()
        box.set_text('组词中')
        box._ime_composing = lambda: True
        self.assertIsNone(box._on_return(SimpleNamespace(state=0)),
                          '输入法组词中 Enter 不发任务')
        self.assertEqual(self.sent, [])
        box._ime_composing = lambda: False
        self._open_candidates(box)
        box._ime_composing = lambda: True
        self.assertIsNone(box._on_return(SimpleNamespace(state=0)),
                          '输入法组词中 Enter 不采纳候选')
        self.assertTrue(box.candidates.open)
        self.assertIsNone(box._on_escape(SimpleNamespace()),
                          '输入法组词中 Esc 先交给输入法')
        self.assertTrue(box.candidates.open)

    def test_enter_flushes_pending_refresh_before_deciding(self):
        box = self._make()
        box.set_text('/')
        self._caret_end(box)
        box._on_key_release(SimpleNamespace(keysym='/'))
        self.assertEqual(box._on_return(SimpleNamespace(state=0)), 'break')
        self.assertEqual(self.sent, [], '刚弹出的候选开着时 Enter 只采纳')
        self.assertTrue(box.input.get('1.0', 'end-1c').startswith('/'))
        self.assertFalse(box.candidates.open)

    def test_send_rejected_while_in_flight_and_not_reentrant(self):
        box = self._make()
        box.set_text('一次')
        self.assertTrue(box.send())
        self.assertTrue(box.in_flight)
        box.set_text('又一次')
        self.assertFalse(box.send(), '在途请求未结束不得再受理')
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(box.input.get('1.0', 'end-1c'), '又一次', '拒绝后保留草稿')
        box.end_request()
        self.assertTrue(box.send())
        self.assertEqual(len(self.sent), 2)

    def test_send_is_not_reentrant(self):
        box = self._make()
        calls, inner = [], []

        def reentrant(text, parsed):
            calls.append(1)
            if len(calls) > 1:
                return True
            inner.append(box.send())
            return True

        box.on_send = reentrant
        box.set_text('外层')
        self.assertTrue(box.send())
        self.assertEqual(inner, [False], 'on_send 内重入 send() 必须被拒')

    # ── 刷新合并、按键无扫描、销毁回收 ───────────────────────────────

    def test_burst_edits_merge_into_one_idle_refresh(self):
        box = self._make()
        runs = []
        original = box._refresh_candidates
        box._refresh_candidates = lambda: runs.append(1) or original()
        for _ in range(5):
            box.input.insert('end-1c', '字')
            box._on_key_release(SimpleNamespace(keysym='x'))
        self._settle()
        self.assertEqual(len(runs), 1, '一波输入与几何变化合并单个 after_idle 重扫')

    def test_mention_scan_cached_per_project_stage(self):
        calls = []
        fake = Path('proj_素材_x.txt')
        with mock.patch('stage_execution_service.stage_idea_attachment_paths',
                        side_effect=lambda project: calls.append(1) or (fake,)):
            box = self._make(stage='script')
            for text in ('@', '@素', '@素材'):
                box.set_text(text)
                self._caret_end(box)
                box._on_key_release(SimpleNamespace(keysym='x'))
                self._settle()
        self.assertEqual(len(calls), 1, '同项目同阶段的 @ 附件扫描不得每键重扫')

    def test_pending_refresh_cancelled_on_destroy(self):
        box = self._make()
        runs = []
        box._refresh_candidates = lambda *a, **k: runs.append(1)
        box._on_trigger_key(SimpleNamespace(keysym='/'))
        box.destroy()
        self._settle()
        self.assertEqual(runs, [], '销毁后不得再执行已排队的刷新回调')


class ComposerExtrasTests(unittest.TestCase):
    """REQ-S01-112/113/114（UX-CHAT-INPUT-EXTRAS）：占位统一前缀、附件明确文案、
    续写提示条、快捷答复胶囊栏、发送键三态圆形视觉。"""

    def setUp(self):
        self.win = tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        self.root.mkdir()
        self.desktop = SimpleNamespace(root=self.root,
                                       status=tk.StringVar(master=self.win, value=''),
                                       win=self.win)
        self.sent = []

    def _make(self, stage='script', **kwargs):
        options = kwargs.pop('options', {})
        base = {'on_send': lambda text, parsed: self.sent.append(text) or True,
                'on_upstream_error': shared_send.upstream_send_error}
        base.update(options)
        box = shared_input.SharedStageInput(self.win, desktop=self.desktop,
                                            stage=stage, options=base)
        box.pack(fill='x')
        self.win.update_idletasks()
        self.addCleanup(box.destroy)
        return box

    # ── REQ-S01-114：占位统一前缀 ────────────────────────────────────────
    def test_placeholders_share_base_prefix_across_13_stages(self):
        """REQ-S01-114：十三阶段占位都以 ``COMPOSER_BASE_PLACEHOLDER`` 开头。"""
        for stage in pet_bus.STAGES:
            with self.subTest(stage=stage):
                text = input_extras.stage_placeholder(stage)
                self.assertTrue(text.startswith(input_extras.COMPOSER_BASE_PLACEHOLDER))
                self.assertIn('/', text)
        self.assertEqual(shared_send.STORYBOARD_PLACEHOLDER,
                         input_extras.stage_placeholder('storyboard'))
        self.assertEqual(shared_send.DEFAULT_STAGE_PLACEHOLDER,
                         input_extras.stage_placeholder(''))
        for stage in pet_bus.STAGES:
            with self.subTest(stage=stage):
                box = self._make(stage=stage)
                shared_send.sync_stage_placeholder(box.input, stage)
                self.assertTrue(str(box.input._placeholder).startswith(
                    input_extras.COMPOSER_BASE_PLACEHOLDER),
                    f'{stage} 阶段占位缺统一前缀')

    # ── REQ-S01-113：附件明确文案 ────────────────────────────────────────
    def test_attachment_unsupported_hint_on_non_script_stages(self):
        """REQ-S01-113：非剧本阶段点「添加附件」状态栏明确「本阶段暂不支持附件」。"""
        for index, stage in enumerate(pet_bus.STAGES):
            if stage == 'script':
                continue
            with self.subTest(stage=stage):
                desktop = SimpleNamespace(page_index=index, status=self.desktop.status)
                shared_send._attachments(desktop)
                self.assertEqual(self.desktop.status.get(),
                                 input_extras.ATTACHMENT_UNSUPPORTED)
                self.assertIn('暂不支持附件', self.desktop.status.get())

    def test_open_attachments_without_callback_uses_same_hint(self):
        """REQ-S01-113：输入框「添加附件」无回调兜底与分流同一文案。"""
        box = self._make(stage='storyboard')
        box.open_attachments()
        self.assertEqual(self.desktop.status.get(), input_extras.ATTACHMENT_UNSUPPORTED)

    def test_skill_and_add_icons_stay_available_on_all_stages(self):
        """REQ-S01-113：十三阶段共用同一套 ✦/＋ 入口，切阶段不消失。"""
        box = self._make(stage='script')
        for stage in pet_bus.STAGES:
            with self.subTest(stage=stage):
                box.set_stage(stage)
                self.assertEqual(box.stage, stage)
                self.assertEqual(box.skill_button.winfo_manager(), 'pack')
                self.assertEqual(box.attachment_button.winfo_manager(), 'pack')

    # ── REQ-S01-112：自动接入续写条 ──────────────────────────────────────
    def test_continue_state_only_for_script_with_can_continue(self):
        """REQ-S01-112：数据源＝剧本页＋``can_continue``；文案取 ``continue_plan``
        显式键，缺省回默认指令；纯判定不碰 Tk。"""
        controller = SimpleNamespace(can_continue=True,
                                     continue_plan=lambda: {'prompt': '从断点继续写'})
        self.assertEqual(input_extras.continue_state('script', controller),
                         {'text': '从断点继续写'})
        controller.can_continue = False
        self.assertIsNone(input_extras.continue_state('script', controller))
        controller.can_continue = True
        self.assertIsNone(input_extras.continue_state('storyboard', controller))
        self.assertIsNone(input_extras.continue_state('script', None))
        self.assertEqual(input_extras.continue_state(
            'script', SimpleNamespace(can_continue=True, continue_plan=lambda: None))['text'],
            input_extras.CONTINUE_PROMPT)

    def _continue_box(self, controller):
        return self._make(options={'continue_state': lambda b: input_extras.continue_state(
            getattr(b, 'stage', ''), controller)})

    def test_continue_bar_shows_and_click_sends_then_hides(self):
        """REQ-S01-112：``can_continue`` 为真才出现提示条；点击发出续写消息即收。"""
        controller = SimpleNamespace(can_continue=True, continue_plan=lambda: {})
        box = self._continue_box(controller)
        self.win.update()
        self.assertEqual(box.extras.continue_bar.winfo_manager(), 'pack')
        button = next(w for w in box.extras.continue_bar.winfo_children()
                      if w.winfo_class() == 'TButton')
        button.invoke()
        self.win.update()
        self.assertEqual(self.sent, [input_extras.CONTINUE_PROMPT])
        self.assertEqual(box.extras.continue_bar.winfo_manager(), '')

    def test_continue_bar_follows_source_and_stage(self):
        """REQ-S01-112：数据源转假收起；切到非剧本阶段恒收起。"""
        controller = SimpleNamespace(can_continue=True, continue_plan=lambda: {})
        box = self._continue_box(controller)
        self.win.update()
        self.assertEqual(box.extras.continue_bar.winfo_manager(), 'pack')
        controller.can_continue = False
        box.set_stage('script')
        self.win.update()
        self.assertEqual(box.extras.continue_bar.winfo_manager(), '')
        controller.can_continue = True
        box.set_stage('storyboard')
        self.win.update()
        self.assertEqual(box.extras.continue_bar.winfo_manager(), '')
        box.set_stage('script')
        self.win.update()
        self.assertEqual(box.extras.continue_bar.winfo_manager(), 'pack')

    # ── REQ-S01-112：快捷答复胶囊栏 ──────────────────────────────────────
    def test_quick_replies_fill_input_without_sending(self):
        """REQ-S01-112：胶囊点击只填入输入框不自动发送；最多 3 条。"""
        box = self._make(options={'on_quick_replies': lambda b: ('甲方案', '乙方案', '丙方案', '丁方案')})
        self.win.update()
        buttons = [w for w in _descendants(box.extras.quick_bar)
                   if w.winfo_class() == 'TButton']
        self.assertEqual(len(buttons), input_extras.QUICK_REPLY_LIMIT)
        buttons[0].invoke()
        self.win.update()
        self.assertEqual(box.input.get('1.0', 'end-1c'), '甲方案')
        self.assertEqual(self.sent, [])

    def test_quick_replies_hide_on_typing_and_return_on_clear(self):
        """REQ-S01-112：输入框有正文胶囊隐藏；清空后按需恢复。"""
        box = self._make(options={'on_quick_replies': lambda b: ('继续',)})
        self.win.update()
        self.assertEqual(box.extras.quick_bar.winfo_manager(), 'pack')
        box.input.insert('1.0', '自己写')
        self.win.update()
        self.assertEqual(box.extras.quick_bar.winfo_manager(), '')
        box.clear()
        self.win.update()
        self.assertEqual(box.extras.quick_bar.winfo_manager(), 'pack')

    def test_quick_reply_rules_are_local_and_capped(self):
        """REQ-S01-112：规则表纯本地判定——无项目/无法制锁提示/缺自然剧本建议。"""
        self.assertEqual(input_extras.quick_reply_rules('script', {}), ())
        rules = input_extras.quick_reply_rules(
            'script', {'has_project': True, 'missing_locks': ('交付形态', '赛道'),
                       'has_natural_script': False})
        self.assertLessEqual(len(rules), input_extras.QUICK_REPLY_LIMIT)
        self.assertTrue(any('制作锁' in text for text in rules))
        self.assertIn(input_extras.QUICK_REPLY_SCRIPT, rules)
        stage_rules = input_extras.quick_reply_rules(
            'storyboard', {'has_project': True})
        self.assertIn('按结构剧本生成分镜', stage_rules)

    # ── REQ-S01-112：发送键三态圆形视觉 ──────────────────────────────────
    def test_send_button_circular_art_three_states(self):
        """REQ-S01-112：实心圆底图＋居中字形；禁用换低对比圆面，运行中仍强调色。"""
        from tkinter import ttk
        from ui_tokens import COLORS
        box = self._make(stage='edit')
        button = box.send_button
        style = ttk.Style(box.winfo_toplevel())
        name = str(button.cget('style'))
        input_extras.sync_send_art(box)
        self.assertTrue(str(button.cget('image')))
        self.assertEqual(str(button.cget('compound')), 'center')
        self.assertEqual(style.lookup(name, 'foreground'), COLORS['on_accent'])
        self.assertEqual(style.lookup(name, 'foreground', ('disabled',)),
                         COLORS['disabled_text'])
        idle_image = str(button.cget('image'))
        button.state(['disabled'])
        input_extras.sync_send_art(box)
        self.assertNotEqual(str(button.cget('image')), idle_image)
        button.state(['!disabled'])
        box._send_interrupt = True
        input_extras.sync_send_art(box)
        self.assertEqual(str(button.cget('image')), idle_image)


if __name__ == '__main__':
    unittest.main()
