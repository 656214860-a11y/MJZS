"""剧本准备页输入框（仿 Claude Code 桌面版）：REQ-S01-62/63/64。

- 62：发送／终止合一按钮随运行状态切换图标和命令；附件准备期间不可点。
- 63：本轮引用的附件卡片用主色边框；× 贴在卡片右上角。
- 64：运行中在输入框按 Esc 等同终止；空闲时不拦截。
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from skip_reasons import PLATFORM_TKINTER
from test_idea_chat import make_minimal_project

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


if __name__ == '__main__':
    unittest.main()
