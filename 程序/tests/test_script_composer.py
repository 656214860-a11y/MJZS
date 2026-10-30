"""剧本准备页输入框与对话区（仿 Claude Code 桌面版）：REQ-S01-62/63/64/65/66/67。

- 62：发送／终止合一按钮随运行状态切换图标和命令；附件准备期间不可点。
- 63：本轮引用的附件卡片用主色边框；× 贴在卡片右上角。
- 64：运行中在输入框按 Esc 等同终止；空闲时不拦截。
- 65／66：消息不铺底色；悬停才显出左下角复制／删除图标，点图标转调整条复制／删除。
- 67：麦克风按钮先聚焦输入框再调起系统听写，失败只在状态栏说明。
"""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from skip_reasons import PLATFORM_TKINTER
from ui_tokens import COLORS
from test_idea_chat import idea_chat, make_minimal_project

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
            d, win = self.desktop(make_minimal_project(td))
            self.assertEqual(d.idea_submit.cget('text'), ICON_SEND)
            self.assertFalse(d.idea_submit.instate(['disabled']))
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
            self.assertEqual(d.idea_submit.cget('text'), ICON_SEND)
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
            for widget in (d.idea_uploaded_panel, d.idea_attachment_button, d.idea_submit):
                self.assertGreaterEqual(widget.winfo_rooty(), frame.winfo_rooty())
                self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                     frame.winfo_rooty() + frame.winfo_height())

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
            self.assertEqual(str(box.tag_cget('bubble_0', 'background')), '')
            hidden = box.cget('bg')
            self.assertEqual(box.tag_cget('bubble_0_copy', 'foreground'), hidden)
            # 图标行紧跟正文、与正文同一左边距，即正文左下角。
            self.assertEqual(box.tag_cget('bubble_0_actions', 'lmargin1'), box.tag_cget('bubble_0', 'lmargin1'))
            self.assertEqual(box.index(box.tag_ranges('bubble_0')[-1]), box.index(box.tag_ranges('bubble_0_actions')[0]))
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

    def test_microphone_focuses_input_then_starts_voice_typing(self):
        import platform_tools
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            button = d.idea_voice_button
            frame = d.idea_composer_frame
            self.assertGreater(button.winfo_rootx(), d.idea_attachment_button.winfo_rootx())
            self.assertLessEqual(button.winfo_rooty() + button.winfo_height(), frame.winfo_rooty() + frame.winfo_height())
            with patch.object(platform_tools, 'start_voice_typing', return_value='') as voice:
                button.invoke(); win.update()
            voice.assert_called_once_with()
            self.assertIs(win.focus_get(), d.idea_input)
            with patch.object(platform_tools, 'start_voice_typing', return_value='拒绝'):
                button.invoke(); win.update()
            self.assertIn('Win+H', d.status.get())



if __name__ == '__main__':
    unittest.main()
