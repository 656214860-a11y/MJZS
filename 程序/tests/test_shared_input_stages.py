"""R2898 轮 4：13 阶段共享输入框接入、发送分流与单一创意对话目录（契约变更测试）。"""
import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import desktop_shared_send as shared_send
import desktop_shared_input as shared_input
import idea_chat
from contract import pet_bus
from desktop_page_nav import PageNavMixin
from stage_execution_service import idea_chat_gateway, project_context
from tests.ui_edges_support import make_minimal_project


class StageMappingTests(unittest.TestCase):
    def test_stage_for_index_covers_only_13_stage_pages(self):
        self.assertEqual(shared_send.stage_for_index(0), 'script')
        self.assertEqual(shared_send.stage_for_index(6), 'final')
        self.assertEqual(shared_send.stage_for_index(12), 'delivery')
        for index in (13, 14, -1, None, 'x'):
            self.assertEqual(shared_send.stage_for_index(index), '')

    def test_flow_map_is_subset_of_pet_stages(self):
        self.assertTrue(set(shared_send.FLOW_FOR_STAGE) <= set(pet_bus.STAGES))
        self.assertEqual(set(shared_send.FLOW_FOR_STAGE),
                         {'script', 'storyboard', 'assets', 'keyframe',
                          'previs', 'video', 'audio'})


class _Desktop:
    """最小桌面替身：只实现分流真正调用到的入口。"""

    def __init__(self, win, root, **kwargs):
        self.win = win
        self.root = root
        self.status = tk.StringVar(master=win, value='')
        self.page_index = 0
        self.projects = SimpleNamespace(info={'projects': []})
        self.opened = []
        self.open_flow_agent = lambda *args, **kw: self.opened.append(args)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def safe(self, fn):
        return fn()

    def show_stage(self, stage):
        self.navigated = getattr(self, 'navigated', []) + [stage]
        self.page_index = pet_bus.STAGES.index(stage)


class SendDispatchTests(unittest.TestCase):
    def setUp(self):
        self.win = tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        self.root.mkdir()

    def _desktop(self, **kwargs):
        return _Desktop(self.win, self.root, **kwargs)

    def test_script_free_text_goes_through_send_message(self):
        sent = Mock()
        desktop = self._desktop(send_message=sent, draft_text=lambda: '')
        self.assertTrue(shared_send.send(desktop, 'script', '我的新创意', None))
        sent.assert_called_once_with()

    def test_script_early_return_keeps_input(self):
        # 简报缺项等早退路径不清空草稿：send_message 没消费输入 → 受理返回 False。
        desktop = self._desktop(send_message=Mock(), draft_text=lambda: '未发送的字')
        self.assertFalse(shared_send.send(desktop, 'script', '我的新创意', None))

    def test_storyboard_free_text_launches_flow_agent(self):
        desktop = self._desktop(page_index=2)
        self.assertTrue(shared_send.send(desktop, 'storyboard', '按这个节奏分镜', None))
        self.assertEqual(desktop.opened[0][:3], ('storyboard', '初步分镜', '按这个节奏分镜'))

    def test_non_flow_stage_gets_hint_not_chat(self):
        desktop = self._desktop(page_index=pet_bus.STAGES.index('edit'))
        self.assertFalse(shared_send.send(desktop, 'edit', '随便聊聊', None))
        self.assertIn('暂无对话入口', desktop.status.get())
        self.assertEqual(desktop.opened, [])

    def test_stage_command_navigates_then_sends_rest(self):
        desktop = self._desktop(page_index=0)
        desktop.open_flow_agent = Mock(side_effect=lambda *a, **k: desktop.opened.append(a))
        parsed = {'kind': 'stage', 'name': 'storyboard', 'stage': 'storyboard', 'rest': '出分镜'}
        self.assertTrue(shared_send.send(desktop, 'script', '/分镜 出分镜', parsed))
        self.assertEqual(desktop.navigated, ['storyboard'])
        self.assertEqual(desktop.opened[0][0], 'storyboard')

    def test_skill_command_dispatches_with_skill_prompt(self):
        skill = SimpleNamespace(name='分镜技法', stage='storyboard',
                                path=Path('skills') / 'x' / '分镜技法.skill.md')
        desktop = self._desktop(page_index=0,
                                shared_input=SimpleNamespace(skill_items=lambda: [skill]))
        parsed = {'kind': 'skill', 'name': '分镜技法', 'stage': 'script', 'rest': '做三版'}
        self.assertTrue(shared_send.send(desktop, 'script', '/分镜技法 做三版', parsed))
        self.assertEqual(desktop.navigated, ['storyboard'])
        prompt = desktop.opened[0][2]
        self.assertIn('分镜技法', prompt)
        self.assertIn('做三版', prompt)

    def test_unknown_skill_is_rejected_with_hint(self):
        desktop = self._desktop(page_index=0,
                                shared_input=SimpleNamespace(skill_items=lambda: []))
        parsed = {'kind': 'skill', 'name': '不存在', 'stage': 'script', 'rest': ''}
        self.assertFalse(shared_send.send(desktop, 'script', '/不存在', parsed))
        self.assertIn('没有这个技能', desktop.status.get())

    def test_account_gate_blocks_paid_stage(self):
        desktop = self._desktop(page_index=2,
                                account=SimpleNamespace(stage_gate=lambda stage: '需要会员'))
        self.assertFalse(shared_send.send(desktop, 'storyboard', '文本', None))
        self.assertEqual(desktop.opened, [])
        self.assertIn('需要会员', desktop.status.get())

    def test_open_flow_failure_returns_false_keeps_draft(self):
        def boom(*args, **kwargs):
            raise ValueError('引擎没装')
        desktop = self._desktop(page_index=2, open_flow_agent=boom)
        self.assertFalse(shared_send.send(desktop, 'storyboard', '文本', None))


class SharedInputHostTests(unittest.TestCase):
    """宿主接线：同一实例跨页 set_stage；非阶段页隐藏；/命令落到分流。"""

    def setUp(self):
        self.win = tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        self.root.mkdir()
        self.status_label = tk.Label(self.win)
        self.status_label.pack()
        self.sent = []
        desktop = _Desktop(self.win, self.root,
                           shared_input=None)
        options = shared_send.host_options(desktop)
        self.box = shared_input.SharedStageInput(
            self.win, desktop=desktop, options=dict(options, on_send=None))
        # host_options 的 on_send 已含分流；直接用它验证端到端。
        self.box.on_send = options['on_send']
        desktop.shared_input = self.box
        self.desktop = desktop
        self.addCleanup(self.box.destroy)

    def test_set_stage_switches_context_without_rebuild(self):
        self.box.set_stage('storyboard')
        self.assertEqual(self.box.stage, 'storyboard')
        self.assertEqual(self.box.input.winfo_class(), 'Text')

    def test_sync_shared_input_maps_page_index(self):
        stub = SimpleNamespace(shared_input=self.box, page_index=0,
                               status_label=self.status_label)
        PageNavMixin._sync_shared_input(stub)
        self.assertEqual(self.box.stage, 'script')
        self.assertEqual(self.box.winfo_manager(), 'pack')
        stub.page_index = pet_bus.STAGES.index('video')
        PageNavMixin._sync_shared_input(stub)
        self.assertEqual(self.box.stage, 'video')
        stub.page_index = 13  # 参考网站
        PageNavMixin._sync_shared_input(stub)
        self.assertEqual(self.box.winfo_manager(), '')

    def test_enter_send_routes_through_dispatch(self):
        self.desktop.send_message = Mock()
        self.box.set_text('你好')
        self.assertTrue(self.box.send())
        self.desktop.send_message.assert_called_once_with()
        class _Event:
            state = 0
        self.box.set_text('再发一次')
        self.assertEqual(self.box._on_return(_Event()), 'break')
        self.assertEqual(self.desktop.send_message.call_count, 2)

    # ── R2980／REQ-S01-92：/ 与 @ 光标级候选浮层（自绘行＋光标锚定翻转） ──

    def _caret_end(self):
        self.box.input.mark_set('insert', 'end-1c')

    def _open_completion(self):
        self.box.set_text('/')
        self._caret_end()
        self.box._refresh_candidates()
        self.win.update_idletasks()
        self.win.update()

    def _show_window(self):
        self.win.geometry('1000x700+40+40')
        self.win.deiconify()
        self.win.update_idletasks()
        self.win.update()

    def test_completion_anchors_to_cursor_and_flips_above(self):
        """候选卡锚在文本光标：输入框贴窗口底部时下方空间不足，翻到光标上方。"""
        self.box.pack(side='bottom', fill='x')
        self._show_window()
        self._open_completion()
        popup = self.box.candidates
        self.assertTrue(popup.open)
        panel = popup.frame
        self.assertEqual(panel.winfo_manager(), 'place', '候选层用 place 浮层')
        self.assertIs(panel.master, self.win, '浮层挂顶层窗：光标上方空间也画得出')
        cursor_x, cursor_top, cursor_bottom = popup._cursor_anchor()
        panel_bottom = panel.winfo_rooty() + panel.winfo_height()
        panel_right = panel.winfo_rootx() + panel.winfo_width()
        # 输入框在窗口底部：光标下方放不下 → 浮层整体翻到光标上方。
        self.assertLessEqual(panel_bottom, cursor_top + 1,
                             '底部空间不足时候选卡翻到光标上方')
        # 横向锚在光标附近且不出可视区。
        self.assertGreaterEqual(panel.winfo_rootx(), 0)
        self.assertLessEqual(panel_right, self.win.winfo_screenwidth())
        self.assertEqual(popup.index, 0, '默认高亮第一项')
        self.assertEqual(self.box.input.get('1.0', 'end-1c'), '/', '高亮不得误采纳候选')

    def test_completion_up_down_tab_and_enter_accept(self):
        self.box.pack(side='bottom', fill='x')
        self._show_window()
        self._open_completion()
        popup = self.box.candidates
        self.assertGreaterEqual(len(popup.entries), 2)

        class _Event:
            keysym = 'Down'
        self.assertEqual(popup.key(_Event()), 'break')
        self.assertEqual(popup.index, 1, 'Down 移到第二项')
        _Event.keysym = 'Up'
        popup.key(_Event())
        self.assertEqual(popup.index, 0, 'Up 移回第一项')
        # Enter 走宿主 _on_return：候选开着时采纳当前项而不是发送。
        class _Return:
            state = 0
        self.assertEqual(self.box._on_return(_Return()), 'break')
        self.assertFalse(popup.open, 'Enter 采纳后收掉浮层')
        value = self.box.input.get('1.0', 'end-1c')
        self.assertTrue(value.startswith('/'), '采纳把候选写回输入框')
        self.assertTrue(value.endswith(' '), '采纳结果带尾空格')
        self.assertEqual(getattr(self.desktop, 'navigated', []), [],
                         '行首 /name 之外 Enter 不得触发发送分流')

    def test_completion_hover_highlights_but_click_applies(self):
        self.box.pack(side='bottom', fill='x')
        self._show_window()
        self._open_completion()
        popup = self.box.candidates
        self.assertGreaterEqual(len(popup.entries), 2)
        row = popup._rows[1]
        label = next(w for w in row['widgets']
                     if w.winfo_class() == 'Label' and str(w.cget('text') or ''))
        label.event_generate('<Enter>')
        self.win.update()
        self.assertEqual(popup.index, 1, '悬停跟随高亮')
        self.assertEqual(self.box.input.get('1.0', 'end-1c'), '/', '悬停不自动采纳')
        self.assertTrue(popup.open)
        label.event_generate('<Button-1>', x=2, y=2)
        self.win.update()
        self.assertFalse(popup.open, '点击采纳后收掉')
        self.assertTrue(self.box.input.get('1.0', 'end-1c').startswith('/'))

    def test_completion_closes_when_focus_leaves_input(self):
        self.box.pack(side='bottom', fill='x')
        other = tk.Label(self.win, text='别处')
        other.pack()
        self.win.update()
        self._open_completion()
        popup = self.box.candidates
        self.assertTrue(popup.open)
        original = self.win.focus_get
        try:
            self.win.focus_get = lambda: other
            popup.close_if_focus_away()
            self.assertFalse(popup.open, '焦点移走即收掉候选层')
            self._open_completion()
            self.win.focus_get = lambda: self.box.input
            popup.close_if_focus_away()
            self.assertTrue(popup.open, '焦点还在输入框就不收')
        finally:
            self.win.focus_get = original

    def test_input_icons_carry_hover_tooltips(self):
        from unittest.mock import patch
        captured = []
        def fake_tooltip(widget, text, **kwargs):
            captured.append((widget, text))
            return widget
        with patch('desktop_shared_input.Tooltip', side_effect=fake_tooltip):
            box = shared_input.SharedStageInput(self.win, desktop=self.desktop,
                                                options={'on_send': None})
            self.addCleanup(box.destroy)
        by_widget = {str(widget): text for widget, text in captured}
        for widget, head in ((box.skill_button, '技能'), (box.attachment_button, '添加'),
                             (box.voice_button, '语音输入'), (box.send_button, '发送'),
                             (box.model_picker, '选择模型')):
            with self.subTest(widget=widget):
                self.assertTrue(by_widget[str(widget)].startswith(head),
                                '图标必须挂悬停提示卡（Tooltip）')

    def test_skill_and_engine_lists_are_cached_until_stage_or_import(self):
        first = self.box.skill_items()
        self.assertIs(self.box.skill_items(), first, '技能清单按实例缓存，不每次按键重读')
        engines = self.box.engine_names()
        self.assertIs(self.box.engine_names(), engines, '子引擎名单同样缓存')
        self.box.set_stage('storyboard')
        self.assertIsNone(self.box._skills_cache, '切阶段后技能缓存失效')
        self.assertIsNot(self.box.skill_items(), first, '切阶段后重新取技能清单')


class SingleThreadTranscriptTests(unittest.TestCase):
    """任务书轮 4 契约：模型会话目录 → 单一创意对话目录，旧目录首次读取迁移。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.proj = make_minimal_project(self.tmp.name)
        self.ctx = project_context(self.proj)

    def _gw(self):
        return idea_chat_gateway()

    def test_model_history_path_is_one_file_for_all_models(self):
        first = idea_chat.model_history_path(self.ctx, '模型甲')
        second = idea_chat.model_history_path(self.ctx, '模型乙')
        self.assertEqual(first, second)
        self.assertEqual(first, idea_chat.history_path(self.ctx))
        self.assertTrue(first.name == '对话.json' and first.parent.name == '创意对话')

    def test_appends_from_two_models_share_one_file(self):
        idea_chat.append(self.ctx, 'user', '甲的创意', model='模型甲', gateway=self._gw())
        idea_chat.append(self.ctx, 'user', '乙的创意', model='模型乙', gateway=self._gw())
        unified = idea_chat.load(self.ctx, model='', gateway=self._gw())
        self.assertEqual([row['text'] for row in unified], ['甲的创意', '乙的创意'])
        self.assertEqual(idea_chat.load(self.ctx, model='模型甲', gateway=self._gw())[-1]['text'], '甲的创意')

    def test_legacy_model_dirs_merge_once_and_keep_files(self):
        from contract.project_stages import writing
        legacy = (writing(self.proj) / '模型会话' / 'm1--deadbeef' / '创意对话' / '对话.json')
        legacy.parent.mkdir(parents=True)
        legacy.write_text(json.dumps({'messages': [
            {'role': 'user', 'text': '旧模型甲的创意', 'model': '模型甲', 'at': '20200101_000000_000000'},
            {'role': 'assistant', 'text': '旧模型乙的回复', 'model': '模型乙', 'at': '20200101_000001_000000'},
        ]}, ensure_ascii=False), encoding='utf-8')
        idea_chat.append(self.ctx, 'user', '新的创意', model='模型丙', gateway=self._gw())
        rows = idea_chat.load(self.ctx, model='', gateway=self._gw())
        self.assertEqual([row['text'] for row in rows],
                         ['旧模型甲的创意', '旧模型乙的回复', '新的创意'])
        # 只迁移不删：旧目录文件原样保留。
        self.assertTrue(legacy.is_file())
        self.assertEqual(len(json.loads(legacy.read_text(encoding='utf-8'))['messages']), 2)
        # 第二次读取不再重复合并。
        again = idea_chat.load(self.ctx, model='', gateway=self._gw())
        self.assertEqual(len(again), 3)


if __name__ == '__main__':
    unittest.main()
