"""REQ-S02-36（R4）：剧本正文字号缩放——Ctrl+=／Ctrl+-／Ctrl+滚轮，步进与限幅。

经真实 ``Desktop`` 的剧本结构页验证：快捷键走 ``ShortcutRegistry``，
缩放只改字号 token、行号槽同步，范围夹在 ``ui_tokens`` 的 8–32 区间。

注意：隐藏桌面里同一进程的第二个及以后 ``tk.Tk()`` 无法合成按键事件
（``event_generate('<Control-…>')`` 不投递），故所有按键断言集中在本文件
按名字排序最前的 ``test_a_…``（它创建本进程第一个 Tk）；滚轮事件不受此限，
独立成 ``test_b_…``。
"""
import sys
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))

import infra.pet_state as pet_state
import ui_tokens


def _settle(widget, iterations=8):
    for _ in range(iterations):
        widget.update_idletasks()
        widget.update()
        time.sleep(0.02)


def _make_project(td):
    project = Path(td) / "project"
    writing = project / "writing"
    writing.mkdir(parents=True)
    lines = ["第 1 集", "", "场景 1：旧站台", ""]
    lines += ["阿远：第%d句台词，内容足够长以便正文可以滚动。" % index
              for index in range(1, 61)]
    (writing / "script_raw.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return project


def _show_script_structure(win, project):
    import desktop as desktop_module

    original = desktop_module.Desktop.choose_project
    desktop_module.Desktop.choose_project = lambda self: None
    try:
        desktop = desktop_module.Desktop(win, root=PROGRAM)
    finally:
        desktop_module.Desktop.choose_project = original
    desktop.root = project
    desktop.show(pet_state.PAGE_OF["script_structure"])
    _settle(win)
    return desktop


def _font_size(widget):
    import tkinter.font as tkfont
    return int(tkfont.Font(font=widget.cget("font")).cget("size"))


class ScriptZoomTests(unittest.TestCase):
    def _page(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        win = tk.Tk()
        win.geometry("1280x800+40+40")
        win.deiconify()
        win.update()

        def _destroy():
            try:
                if win.winfo_exists():
                    win.destroy()
            except tk.TclError:
                pass
        self.addCleanup(_destroy)
        desktop = _show_script_structure(win, _make_project(td.name))
        box = desktop.script_structure_source_preview_content_box
        return win, desktop, box

    def _press_until(self, win, widget, sequence, probe, tries=15):
        """合成按键须落在焦点控件上；高负载下焦点与投递都可能延迟，
        确认焦点后重发直到 ``probe()`` 为真（重复按键对缩放是累加，
        调用方须以目标 zoom_delta 为探针，避免多发造成步进漂移）。"""
        for _ in range(tries):
            widget.focus_set()
            win.update()
            widget.event_generate(sequence, when='now')
            win.update()
            _settle(win, 2)
            if probe():
                return
        self.fail('按键 %s 连发 %d 次仍未生效' % (sequence, tries))

    def test_a_keyboard_zoom_steps_limits_gutter_and_both_readers(self):
        """REQ-S02-36：Ctrl+= 放大、Ctrl+- 缩小 ±1；限幅；行号同步；两框独立。"""
        win, desktop, box = self._page()
        preview = box.preview
        base = ui_tokens.SCRIPT_VIEW_FONT[1]
        self.assertEqual(_font_size(preview), base)
        # 高负载下合成按键可能不投递：重发直到缩放生效（步进目标即探针）。
        self._press_until(win, preview, "<Control-equal>", lambda: box.zoom_delta == 1)
        _settle(win)
        self.assertEqual(_font_size(preview), base + 1)
        self.assertEqual(box.gutter._font_spec[1], base + 1)
        fonts = {box.gutter.itemcget(item, "font") for item in box.gutter.find_all()}
        self.assertTrue(any(str(base + 1) in str(font) for font in fonts),
                        "行号字体未随缩放更新")
        self._press_until(win, preview, "<Control-minus>", lambda: box.zoom_delta == 0)
        _settle(win)
        self.assertEqual(_font_size(preview), base)

        # 上下两个阅读框的缩放互相独立。
        output_box = desktop.script_structure_output_preview_content_box
        self._press_until(win, output_box.preview, "<Control-equal>",
                          lambda: output_box.zoom_delta == 1)
        _settle(win)
        self.assertEqual(box.zoom_delta, 0)

        # 上下限：与按键同一入口 zoom_by（步进已由上面的按键验证）。
        box.aids.zoom_by(100)
        self.assertEqual(_font_size(box.preview), ui_tokens.SCRIPT_VIEW_FONT_MAX)
        self.assertEqual(box.gutter._font_spec[1], ui_tokens.SCRIPT_VIEW_FONT_MAX)
        box.aids.zoom_by(-100)
        self.assertEqual(_font_size(box.preview), ui_tokens.SCRIPT_VIEW_FONT_MIN)
        self.assertEqual(box.gutter._font_spec[1], ui_tokens.SCRIPT_VIEW_FONT_MIN)

    def test_b_ctrl_mousewheel_zooms_and_plain_wheel_scrolls(self):
        """REQ-S02-36：Ctrl+滚轮缩放；不带 Ctrl 的滚轮仍走正常滚动。"""
        win, _desktop, box = self._page()
        preview = box.preview
        preview.focus_set()
        preview.event_generate("<MouseWheel>", state=0, delta=120)
        win.update()
        _settle(win)
        self.assertEqual(box.zoom_delta, 0, "普通滚轮不应触发缩放")
        top_before = preview.yview()[0]
        preview.event_generate("<MouseWheel>", state=4, delta=120)
        win.update()
        _settle(win)
        self.assertEqual(box.zoom_delta, 1)
        preview.event_generate("<MouseWheel>", state=4, delta=-120)
        win.update()
        _settle(win)
        self.assertEqual(box.zoom_delta, 0)
        # 再来一次普通滚轮：仍不缩放且正文实际滚动（scroll_page 未被破坏）。
        preview.event_generate("<MouseWheel>", state=0, delta=-240)
        win.update()
        # 高负载下滚动生效可能滞后：轮询到 yview 变化。
        for _ in range(15):
            _settle(win, 2)
            if preview.yview()[0] != top_before:
                break
        self.assertEqual(box.zoom_delta, 0)
        self.assertNotEqual(preview.yview()[0], top_before,
                            "普通滚轮应照常滚动正文")


if __name__ == "__main__":
    unittest.main()
