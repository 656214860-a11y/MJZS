"""剧本准备页输入框与对话区（仿 Claude Code 桌面版）：REQ-S01-62/63/64/65/66/67/71。

- 62：发送／终止合一按钮随运行状态切换图标和命令；附件准备期间不可点。
- 63（R3060 改版）：本轮引用的附件以「@原名」行显示在输入框顶部引用区；右键 @ 行可删除副本。
- 64：运行中在输入框按 Esc 等同终止；空闲时不拦截。
- 65／66：消息不铺底色；悬停才显出左下角复制／删除图标，点图标转调整条复制／删除。
- 67／71：麦克风是听写开关，打开后边说边把文字写进输入框光标处，再点关闭；失败只在状态栏说明。
"""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from skip_reasons import PLATFORM_TKINTER
from ui_tokens import COLORS
from test_idea_chat import idea_chat, make_minimal_project
import desktop_idea_chat

try:
    import tkinter as tk
    _probe = tk.Tk(); _probe.destroy()
except Exception:  # pragma: no cover - 无图形环境
    tk = None


@unittest.skipIf(tk is None, PLATFORM_TKINTER)
class ScriptComposerTests(unittest.TestCase):
    def desktop(self, proj):
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, 'choose_project', original)
        win = tk.Tk(); win.geometry('1100x760+40+40')
        self.addCleanup(lambda: win.winfo_exists() and win.destroy())
        d = desktop_module.Desktop(win, root=str(Path(__file__).resolve().parents[1]))
        d.root = proj
        d.show(0); win.deiconify(); win.update()
        return d, win

    def test_submit_switches_between_send_and_stop(self):
        from ui_tokens import ICON_SEND, ICON_STOP
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            # REQ-S01-86：简报必填未齐时发送置灰；本测关注发送/终止切换，先落一份完整简报。
            from contract import project_stages
            from agent.core import save
            from test_writing_api import WritingApiTests
            save(project_stages.writing(proj) / 'brief_complete.json', WritingApiTests.complete_brief())
            d, win = self.desktop(proj)
            d._apply_idea_send_state()
            win.update()
            button = d.shared_input.send_button
            self.assertEqual(button.cget('text'), ICON_SEND)
            self.assertFalse(button.instate(['disabled']))
            d.idea_input.insert('1.0', '继续')
            with patch.object(d, 'send_message') as sent:
                button.invoke()
            sent.assert_called_once()
            d._idea_requesting = True
            d.update_script_interrupt_button()
            self.assertEqual(button.cget('text'), ICON_STOP)
            with patch.object(d, 'interrupt_script_agent') as stopped:
                button.invoke()
            stopped.assert_called_once()
            d._idea_requesting = False
            # 必填缺失时共享发送键置灰（REQ-S01-86）。
            with patch.object(d, '_idea_live_missing', return_value=('故事梗概',)):
                d.update_script_interrupt_button()
            self.assertEqual(button.cget('text'), ICON_SEND)
            self.assertTrue(button.instate(['disabled']))

    def test_escape_in_input_stops_only_while_running(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            d.idea_input.focus_force(); win.update()
            with patch.object(d, 'interrupt_script_agent') as stopped:
                d.idea_input.event_generate('<Escape>'); win.update()
                stopped.assert_not_called()
                d._idea_requesting = True
                d.idea_input.event_generate('<Escape>'); win.update()
                stopped.assert_called_once()
            d._idea_requesting = False

    def test_referenced_attachments_show_as_at_lines_at_top(self):
        """REQ-S01-63（R3060）：本轮引用的附件以「@原名」逐行显示在输入框顶部。"""
        from stage_execution_service import archive_idea_attachments
        from domain.idea_attachments import display_name
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            sources = [Path(td) / name for name in ('设定.txt', '大纲.txt')]
            for source in sources:
                source.write_text(source.stem, encoding='utf-8')
            archived = archive_idea_attachments(proj, sources)
            d, win = self.desktop(proj)
            d.idea_input.insert('1.0', '先写一句创意')
            d.idea_attachment_paths = (archived[1], archived[0])
            d.update_idea_attachment_status(); win.update_idletasks(); win.update()
            box = d.idea_input
            self.assertEqual(box.get('1.0', 'end-1c').splitlines(),
                             ['@' + display_name(archived[1]), '@' + display_name(archived[0]),
                              '先写一句创意'],
                             '引用区在文本最顶、每附件一行、已有内容整体下移')
            # 附件不再占卡片独立行：图标行仍在输入区下方。
            shared = d.shared_input
            for widget in (shared.attachment_button, shared.send_button):
                self.assertGreaterEqual(widget.winfo_rooty(),
                                        box.winfo_rooty() + box.winfo_height() - 2)

    def test_composer_shows_single_outer_border(self):
        """R3060：输入区与图标行共用一条外框——TextArea 无内边框、图标行同卡片底色、聚焦外框变色。"""
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            shared = d.shared_input
            self.assertEqual(int(shared.input.cget('highlightthickness')), 0,
                             '输入区不再画内框线')
            row = shared.send_button.master
            self.assertEqual(str(row.cget('style')), 'Composer.TFrame',
                             '图标行与卡片同底色，不再形成内部分隔带')
            # 外框=包裹层 input_ring 的 1px 底色边（ttk 主题不支持 -highlight*，用底色边保证可见）。
            ring = shared.input_ring
            self.assertEqual(str(ring.cget('bg')), COLORS['border_default'])
            shared.input.focus_force(); win.update()
            self.assertEqual(str(ring.cget('bg')), COLORS['border_input_hover'],
                             '聚焦时外框描边变主题色')
            win.focus_set()
            try:
                d.canvas.focus_set()   # R3016 起 title_row 已删，改用画布移走焦点
            except tk.TclError:
                pass
            win.update()
            self.assertEqual(str(ring.cget('bg')), COLORS['border_default'], '失焦外框恢复')

    def wait_for_tag(self, win, box, tag):
        for _ in range(100):
            win.update()
            if box.tag_ranges(tag):return
            time.sleep(0.02)
        self.fail('聊天记录没有渲染出 %s' % tag)

    def test_message_icons_show_on_hover_and_act_on_the_whole_message(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            idea_chat.append(proj, 'user', '这条由用户发送')
            d, win = self.desktop(proj)
            box = d.idea_log
            self.wait_for_tag(win, box, 'bubble_0_copy')
            # 参考 DeepSeek 对话：正文铺浅灰底框，background 是框底色而非透明。
            self.assertEqual(str(box.tag_cget('bubble_0', 'background')), COLORS['surface_hover'])
            hidden = box.cget('bg')
            self.assertEqual(box.tag_cget('bubble_0_copy', 'foreground'), hidden)
            # 图标行与正文同属一条消息：底框的左边沿（left）与图标行左边距一致；
            # 正文文字在框内再缩进一个 BUBBLE_PAD，所以正文 tag 的 lmargin1 比图标行大一个内边距。
            self.assertEqual(int(float(box.tag_cget('bubble_0', 'lmargin1'))),
                             int(float(box.tag_cget('bubble_0_actions', 'lmargin1'))) + desktop_idea_chat.BUBBLE_PAD)
            self.assertEqual(box.index(box.tag_ranges('bubble_0')[-1]), box.index(box.tag_ranges('bubble_0_time')[0]))
            self.assertEqual(box.index(box.tag_ranges('bubble_0_time')[-1]), box.index(box.tag_ranges('bubble_0_actions')[0]))
            d.show_bubble_actions(box, 'bubble_0', True)
            self.assertEqual(box.tag_cget('bubble_0_copy', 'foreground'), COLORS['text_muted'])
            self.assertEqual(box.tag_cget('bubble_0_delete', 'foreground'), COLORS['text_muted'])
            d.show_bubble_actions(box, 'bubble_0', False)
            self.assertEqual(box.tag_cget('bubble_0_delete', 'foreground'), hidden)
            box.see(box.tag_ranges('bubble_0_copy')[0]); win.update()
            for tag, method in (('bubble_0_copy', 'copy_bubble_message'), ('bubble_0_delete', 'delete_bubble_message')):
                x, y, w, h = box.bbox(box.tag_ranges(tag)[0])
                with patch.object(d, method) as action:
                    box.event_generate('<Motion>', x=x + w // 2, y=y + h // 2); win.update()
                    box.event_generate('<Button-1>', x=x + w // 2, y=y + h // 2); win.update()
                action.assert_called_once_with(0)

    def test_microphone_dictates_live_into_input(self):
        import queue
        import contract.platform_tools as platform_tools
        from domain import speech_api

        class FakeRecorder:
            instances = []
            def __init__(self, max_seconds=180, on_chunk=None):
                self.on_chunk, self.peak, self.seconds, self.level, self.error = on_chunk, 2000, 2.0, 0.3, ''
                self.finished, self.stopped = False, False
                FakeRecorder.instances.append(self)
            def start(self):
                return FakeRecorder.next_reason
            def stop(self):
                self.stopped = True
                return b'', self.peak
        FakeRecorder.next_reason = ''

        class FakeSession:
            instances = []
            def __init__(self, settings):
                self.events, self.sent, self.started, self.finished, self.cancelled = queue.Queue(), [], False, False, False
                FakeSession.instances.append(self)
            def start(self):
                self.started = True
            def send(self, pcm):
                self.sent.append(pcm)
            def finish(self):
                self.finished = True
            def cancel(self):
                self.cancelled = True

        with tempfile.TemporaryDirectory() as td, patch.object(platform_tools, 'MicrophoneRecorder', FakeRecorder), \
                patch.object(speech_api, 'missing_reason', return_value=''), \
                patch.object(speech_api, 'create_session',
                             side_effect=lambda settings, **kw: FakeSession(settings)):
            d, win = self.desktop(make_minimal_project(td))
            button, box = d.shared_input.voice_button, d.idea_input
            shared = d.shared_input
            self.assertGreater(button.winfo_rootx(), shared.attachment_button.winfo_rootx())
            self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                 shared.winfo_rooty() + shared.winfo_height())
            box.delete('1.0', 'end'); box.insert('1.0', '开头：')
            button.invoke(); win.update()
            voice = d.shared_voice
            recorder, session = FakeRecorder.instances[-1], FakeSession.instances[-1]
            self.assertTrue(session.started)
            self.assertEqual(recorder.on_chunk, session.send, '录音块直接推给实时会话')
            self.assertEqual(str(button.cget('style')), 'Tokens.Composer.Listening.TButton', '听写中按钮高亮')
            self.assertIs(win.focus_get(), box)
            self.assertIn('正在听写', d.status.get())
            # 中间结果浅色写在光标处并随结果替换，定稿后变正常文字；下一句接在后面。
            session.events.put(('partial', 'a', '主角'))
            voice.poll(); win.update()
            self.assertEqual(box.get('1.0', 'end-1c'), '开头：主角')
            self.assertTrue(box.tag_ranges(voice.PARTIAL_TAG))
            session.events.put(('partial', 'a', '主角走进雨'))
            session.events.put(('final', 'a', '主角走进雨夜。'))
            session.events.put(('partial', 'b', '回头'))
            voice.poll(); win.update()
            self.assertEqual(box.get('1.0', 'end-1c'), '开头：主角走进雨夜。回头')
            self.assertEqual(box.get(*box.tag_ranges(voice.PARTIAL_TAG)), '回头')
            self.assertEqual(box.index('insert'), box.index('end-1c'), '光标跟着新字走')
            # 再点麦克风：停录、通知收尾，等最后一句定稿和会话关闭。
            button.invoke(); win.update()
            self.assertTrue(recorder.stopped)
            self.assertTrue(session.finished)
            self.assertEqual(str(button.cget('style')), 'Tokens.Composer.Icon.TButton')
            self.assertTrue(voice.closing)
            session.events.put(('final', 'b', '回头看了一眼。'))
            session.events.put(('closed', '', ''))
            voice.poll(); win.update()
            self.assertEqual(box.get('1.0', 'end-1c'), '开头：主角走进雨夜。回头看了一眼。')
            self.assertFalse(box.tag_ranges(voice.PARTIAL_TAG))
            self.assertFalse(voice.closing)
            self.assertIn('已关闭', d.status.get())
            # 第二次打开照常可用；长时间没声音时状态栏指向麦克风隐私设置。
            button.invoke(); win.update()
            self.assertEqual(len(FakeSession.instances), 2)
            FakeRecorder.instances[-1].peak, FakeRecorder.instances[-1].seconds = 0, 4.0
            voice.poll(); win.update()
            self.assertIn('没听到声音', d.status.get())
            # 服务端报错：停录、说明原因、按钮复原。
            # 发送门禁的 250ms 防抖可能在 win.update() 里落进来覆盖语音状态，先撤掉 pending 刷新。
            pending = getattr(d, '_idea_send_state_after', None)
            if pending is not None:
                win.after_cancel(pending)
                d._idea_send_state_after = None
            FakeSession.instances[-1].events.put(('error', '', '密钥无效'))
            voice.poll(); win.update()
            self.assertTrue(FakeRecorder.instances[-1].stopped)
            self.assertIn('密钥无效', d.status.get())
            self.assertEqual(str(button.cget('style')), 'Tokens.Composer.Icon.TButton')
            # 录满上限自动关麦。
            button.invoke(); win.update()
            FakeRecorder.instances[-1].finished = True
            voice.poll(); win.update()
            self.assertTrue(FakeRecorder.instances[-1].stopped)
            self.assertTrue(FakeSession.instances[-1].finished)
            FakeSession.instances[-1].events.put(('closed', '', ''))
            voice.poll(); win.update()
            self.assertFalse(voice.closing)
            FakeRecorder.next_reason = '没有找到麦克风'
            button.invoke(); win.update()
            self.assertIn('没有找到麦克风', d.status.get())
            self.assertEqual(str(button.cget('style')), 'Tokens.Composer.Icon.TButton')

    def test_microphone_without_key_explains_in_status(self):
        import contract.platform_tools as platform_tools
        from domain import speech_api
        with tempfile.TemporaryDirectory() as td, \
                patch.object(speech_api, 'missing_reason', return_value='没有配置语音识别密钥 DASHSCOPE_API_KEY'), \
                patch.object(platform_tools, 'MicrophoneRecorder', side_effect=AssertionError('不应开麦')):
            d, win = self.desktop(make_minimal_project(td))
            # 本测只验缺密钥提示；隔离发送门禁尚未执行的防抖回调，
            # 与上面的语音错误用例一致，避免 win.update 覆盖语音状态。
            pending = getattr(d, '_idea_send_state_after', None)
            if pending:
                win.after_cancel(pending); d._idea_send_state_after = None
            button = d.shared_input.voice_button
            button.invoke(); win.update()
            self.assertIn('DASHSCOPE_API_KEY', d.status.get())
            self.assertEqual(str(button.cget('style')), 'Tokens.Composer.Icon.TButton')


if __name__ == '__main__':
    unittest.main()
