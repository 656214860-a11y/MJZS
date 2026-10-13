# -*- coding: utf-8 -*-
"""切页提速：侧栏点回来整页复用（CACHED_PAGES），同页刷新／换项目照旧重建。"""
import os, sys, tempfile, unittest
from pathlib import Path

HERE = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, HERE)
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.chdir(HERE)

from skip_reasons import PLATFORM_TKINTER
from pet_state import PAGE_OF as PAGE


class PageCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def open_desktop(self, td):
        import test_ui_edges
        from desktop import Desktop
        from local_video import open_studio
        win = self.tk.Tk(); win.withdraw()
        self.addCleanup(win.destroy)
        d = Desktop(win, root=HERE)
        d.root = test_ui_edges.make_populated_project(td)
        d.studio = open_studio(d.root)
        return win, d

    def holder(self, d):
        return d._page_cache[PAGE['storyboard']]['holder']

    def test_nav_back_reuses_page_and_restores_stage_button(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            d.go_page(PAGE['storyboard']); win.update_idletasks()
            first, button = self.holder(d), d.stage_button
            self.assertIsNotNone(button)
            d.go_page(PAGE['assets']); win.update_idletasks()
            self.assertTrue(first.winfo_exists())
            self.assertFalse(first.winfo_ismapped())
            d.go_page(PAGE['storyboard']); win.update_idletasks()
            self.assertIs(self.holder(d), first)
            self.assertIs(d.stage_button, button)

    def test_same_page_refresh_and_plain_show_rebuild(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            d.go_page(PAGE['storyboard']); win.update_idletasks()
            first = self.holder(d)
            d.show(PAGE['storyboard']); win.update_idletasks()
            self.assertFalse(first.winfo_exists())
            second = self.holder(d)
            d.go_page(PAGE['assets']); d.show(PAGE['storyboard']); win.update_idletasks()
            self.assertFalse(second.winfo_exists())

    def test_project_change_drops_cache(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import test_ui_edges
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as other:
            win, d = self.open_desktop(td)
            d.go_page(PAGE['storyboard']); d.go_page(PAGE['assets'])
            first = self.holder(d)
            d.root = test_ui_edges.make_populated_project(other)
            d.go_page(PAGE['storyboard']); win.update_idletasks()
            self.assertFalse(first.winfo_exists())
            self.assertEqual(d._page_cache[PAGE['storyboard']]['root'], d.root)

    def test_hidden_page_ignores_clicks_on_other_pages(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            win.deiconify()
            d.go_page(PAGE['storyboard']); d.go_page(PAGE['assets']); win.update()
            d.status.set('别的页')
            d.content.event_generate('<Button-1>', x=1, y=1); win.update()
            self.assertEqual(d.status.get(), '别的页')

    def test_nav_highlight_is_drawn_before_page_builds(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            d.go_page(PAGE['script'])
            seen = []
            real = d.go
            d.go = lambda index, **kw: (seen.append(str(d.nav[index].cget('style'))), real(index, **kw))
            d.go_page(PAGE['assets'])
            self.assertEqual(seen, ['Selected.Nav.TButton'])


if __name__ == '__main__':
    unittest.main()
