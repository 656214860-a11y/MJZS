"""剧本准备页输入框与对话区（仿 Claude Code 桌面版）：REQ-S01-62/63/64/65/66/67/71。

- 62：发送／终止合一按钮随运行状态切换图标和命令；附件准备期间不可点。
- 63：本轮引用的附件卡片用主色边框；× 贴在卡片右上角。
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
        from ui_tokens import ICON_STOP
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            # REQ-S01-86：简报必填未齐时发送置灰；本测关注发送/终止切换，先落一份完整简报。
            import project_stages
            from agent.core import save
            from test_writing_api import WritingApiTests
            save(project_stages.writing(proj) / 'brief_complete.json', WritingApiTests.complete_brief())
            d, win = self.desktop(proj)
            d._apply_idea_send_state()
            win.update()
            # 轮 3 契约：内联发送／终止键统一到共享输入框发送键，空闲态文字「发送」。
            self.assertEqual(d.idea_submit.cget('text'), '发送')
            self.assertFalse(d.idea_submit.instate(['disabled']))
            d.idea_input.delete('1.0', 'end'); d.idea_input.insert('1.0', '写一个开场')
            with patch.object(d, 'send_message') as sent:
                d.idea_submit.invoke()
            sent.assert_called_once()
            d._idea_requesting = True
            d.update_script_interrupt_button()
            self.assertEqual(d.idea_submit.cget('text'), ICON_STOP)
            with patch.object(d, 'interrupt_script_agent') as stopped:
                d.idea_submit.invoke()
            stopped.assert_called_once()
            d._idea_requesting = False
            d.idea_send.state(['disabled'])  # 附件入库校验期间底栏发送不可点
            d.update_script_interrupt_button()
            self.assertEqual(d.idea_submit.cget('text'), '发送')
            self.assertTrue(d.idea_submit.instate(['disabled']))

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

    def test_referenced_chip_is_highlighted_and_close_sits_top_right(self):
        from stage_execution_service import archive_idea_attachments
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            sources = [Path(td) / name for name in ('设定.txt', '大纲.txt')]
            for source in sources:
                source.write_text(source.stem, encoding='utf-8')
            archived = archive_idea_attachments(proj, sources)
            d, win = self.desktop(proj)
            d.idea_attachment_paths = (archived[1],)
            d.update_idea_attachment_status(); win.update_idletasks(); win.update()
            chips = {chip.attachment_path: chip for chip in d.idea_uploaded_panel.winfo_children()
                     if hasattr(chip, 'attachment_path')}
            self.assertEqual(str(chips[archived[0]].cget('style')), 'Tokens.Chip.TFrame')
            self.assertEqual(str(chips[archived[1]].cget('style')), 'Tokens.Chip.Selected.TFrame')
            for chip in chips.values():
                close = chip.close_button
                self.assertEqual(close.place_info().get('anchor'), 'ne')
                self.assertLessEqual(abs(close.winfo_rootx() + close.winfo_width()
                                         - chip.winfo_rootx() - chip.winfo_width()), 2)
                self.assertLessEqual(abs(close.winfo_rooty() - chip.winfo_rooty()), 2)
            frame = d.idea_composer_frame
            self.assertGreaterEqual(d.idea_uploaded_panel.winfo_rooty(), frame.winfo_rooty())
            self.assertLessEqual(d.idea_uploaded_panel.winfo_rooty() + d.idea_uploaded_panel.winfo_height(),
                                 frame.winfo_rooty() + frame.winfo_height())
            # 轮 3 契约：附件／发送入口在共享输入条内，不在 composer 卡片里。
            shared = d.shared_input
            for widget in (d.idea_attachment_button, d.idea_submit):
                self.assertGreaterEqual(widget.winfo_rooty(), shared.winfo_rooty())
                self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                     shared.winfo_rooty() + shared.winfo_height())

    def test_chip_content_keeps_off_the_border(self):
        """图标和文件名不贴卡片外沿，否则白底会盖断圆角边框（选中时主色框断成几截）。"""
        from stage_execution_service import archive_idea_attachments
        from ui_tokens import SPACING
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            source = Path(td) / '人物.txt'
            source.write_text('人物', encoding='utf-8')
            archived = archive_idea_attachments(proj, [source])
            d, win = self.desktop(proj)
            d.idea_attachment_paths = (archived[0],)
            d.update_idea_attachment_status(); win.update_idletasks(); win.update()
            chip = next(chip for chip in d.idea_uploaded_panel.winfo_children()
                        if hasattr(chip, 'attachment_path'))
            for widget in chip.pack_slaves():
                self.assertGreaterEqual(widget.winfo_x(), SPACING['sm'])
                self.assertGreaterEqual(widget.winfo_y(), SPACING['xs'])
                self.assertLessEqual(widget.winfo_y() + widget.winfo_height(),
                                     chip.winfo_height() - SPACING['xs'])

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
        import speech_api

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
            button, box, voice = d.idea_voice_button, d.idea_input, d.idea_voice_input
            # 轮 3 契约：麦克风入口在共享输入条左簇（附件右侧），听写会话绑定共享 Text。
            self.assertIs(button, d.shared_input.mic_button)
            self.assertIs(voice, d.shared_input.voice_input)
            self.assertIs(box, d.shared_input.input)
            self.assertGreater(button.winfo_rootx(), d.idea_attachment_button.winfo_rootx())
            self.assertGreaterEqual(button.winfo_rooty(), d.shared_input.winfo_rooty())
            self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                 d.shared_input.winfo_rooty() + d.shared_input.winfo_height())
            box.delete('1.0', 'end'); box.insert('1.0', '开头：')
            button.invoke(); win.update()
            recorder, session = FakeRecorder.instances[-1], FakeSession.instances[-1]
            self.assertTrue(session.started)
            self.assertEqual(recorder.on_chunk, session.send, '录音块直接推给实时会话')
            self.assertEqual(str(button.cget('style')), 'Tokens.Primary.TButton', '听写中按钮高亮')
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
            self.assertEqual(str(button.cget('style')), 'Tokens.Secondary.TButton')
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
            self.assertEqual(str(button.cget('style')), 'Tokens.Secondary.TButton')
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
            self.assertEqual(str(button.cget('style')), 'Tokens.Secondary.TButton')

    def test_microphone_without_key_explains_in_status(self):
        import contract.platform_tools as platform_tools
        import speech_api
        with tempfile.TemporaryDirectory() as td, \
                patch.object(speech_api, 'missing_reason', return_value='没有配置语音识别密钥 DASHSCOPE_API_KEY'), \
                patch.object(platform_tools, 'MicrophoneRecorder', side_effect=AssertionError('不应开麦')):
            d, win = self.desktop(make_minimal_project(td))
            d.idea_voice_button.invoke(); win.update()
            self.assertIn('DASHSCOPE_API_KEY', d.status.get())
            self.assertEqual(str(d.idea_voice_button.cget('style')), 'Tokens.Secondary.TButton')


if __name__ == '__main__':
    unittest.main()
