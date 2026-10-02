# -*- coding: utf-8 -*-
"""候选图墙自检：默认勾选、阈值、图墙行内容与「确认入库」交出的那批候选。运行：python test_reference_wall.py"""
from skip_reasons import (
    MISSING_NODE,
    PLATFORM_DIRECTORY_LINK,
    PLATFORM_TKINTER,
    PLATFORM_TK_DISPLAY,
    PLATFORM_WORKING_SET,
    REQUIRES_BUNDLED_SKILL,
)
import base64, json, os, sys, tempfile, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import asset_reference_search as search
import reference_wall

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")

ASSET = {'id': 'CHAR_001', 'name': '银发少女', 'image_prompt': '银发长大衣少女，正面全身立绘，冷色调'}


def png(size=4096):
    body = b'\x00' * max(0, size - len(PNG))
    return PNG[:-12] + body + PNG[-12:]


def candidate(url='https://img.example.com/a.png', **values):
    item = {'url': url, 'page': 'https://example.com/a', 'title': '银发少女 立绘', 'author': '张三',
            'license': 'CC BY', 'width': 1200, 'height': 1600, 'tags': ['银发', '长发']}
    item.update(values)
    return item


class RowTests(unittest.TestCase):
    def test_commercial_candidates_are_checked_by_default(self):
        self.assertTrue(reference_wall.rows([candidate()], ASSET)[0]['checked'])

    def test_non_commercial_is_left_for_the_user(self):
        self.assertFalse(reference_wall.rows([candidate(license='CC BY-NC')], ASSET)[0]['checked'])

    def test_candidate_without_license_is_not_checked(self):
        self.assertFalse(reference_wall.rows([candidate(license='')], ASSET)[0]['checked'])

    def test_weak_candidates_are_below_the_threshold(self):
        self.assertEqual(reference_wall.rows([candidate(width=600, height=800)], ASSET), [])
        self.assertTrue(reference_wall.rows([candidate(width=600, height=800)], ASSET, threshold=40))

    def test_limit_is_honoured(self):
        items = reference_wall.rows([candidate(url=f'https://a/{index}.png', width=2048, height=2048 + index * 64)
                                     for index in range(5)], ASSET, limit=2)
        self.assertEqual(len(items), 2)

    def test_rows_keep_score_and_reasons(self):
        item = reference_wall.rows([candidate()], ASSET)[0]
        self.assertGreater(item['score'], 0)
        self.assertTrue(item['reasons'])

    def test_picks_returns_only_the_checked(self):
        items = reference_wall.rows([candidate(url='https://a/1.png'), candidate(url='https://b/2.png', license='CC BY-NC')], ASSET)
        self.assertEqual([item['url'] for item in reference_wall.picks(items)], ['https://a/1.png'])

    def test_unchecked_rows_are_not_picked(self):
        items = reference_wall.rows([candidate(license='CC BY-NC')], ASSET)
        self.assertEqual(reference_wall.picks(items), [])


class _Popup:
    """替掉 tk.Menu：只记下摆过哪些项，不真的开窗。"""

    def __init__(self, *args, **kwargs):
        self.items = []

    def add_command(self, label=None, command=None, **kwargs):
        self.items.append((label, command))

    def add_separator(self, **kwargs):
        self.items.append(('---', None))

    def index(self, where):
        return None if not self.items else len(self.items) - 1

    def tk_popup(self, x, y):
        self.popped = (x, y)

    def grab_release(self):
        pass


class FakeApp:
    def __init__(self, win, root):
        import tkinter as tk
        self.win = win
        self.root = root
        self.calls = []
        self.status = tk.StringVar(master=win, value='')

    def asset_base(self):
        return Path(self.root) / 'library'

    def show(self, index):
        self.calls.append(('show', index))

    def async_(self, fn, done=None):
        self.calls.append(('async', fn, done))


class WallDialogTests(unittest.TestCase):
    """真窗口：候选清单 → 图墙行 → 勾选 → 「确认入库」交出的那批候选。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.win = self.tk.Tk(); self.win.withdraw()
        self.addCleanup(self.destroy)
        self.win._tick_images = (self.tk.PhotoImage(width=1, height=1), self.tk.PhotoImage(width=1, height=1))
        self.app = FakeApp(self.win, self.tmp.name)

    def destroy(self):
        try:
            self.win.destroy()
        except Exception:
            pass

    def library(self, payload):
        base = Path(self.tmp.name) / 'library'
        file = base / 'assets/资产清单/assets.json'
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        return base

    def walk(self, widget, kinds):
        found = [widget] if isinstance(widget, kinds) else []
        for child in widget.winfo_children():
            found.extend(self.walk(child, kinds))
        return found

    def table(self, win):
        from tkinter import ttk
        return self.walk(win, ttk.Treeview)[0]

    def buttons(self, win):
        from tkinter import ttk
        return {str(button.cget('text')): button for button in self.walk(win, ttk.Button)}

    def open_wall(self, candidates, base=None):
        win = reference_wall.show(self.app, aid='CHAR_001', parent=self.win,
                                  assets={'CHAR_001': ASSET}, base=base or self.library({'CHAR_001': {'name': '银发少女'}}),
                                  candidates=list(candidates), fetch=lambda url: png())
        self.addCleanup(win.destroy)
        self.win.update()
        return win

    def test_wall_lists_the_ranked_candidates(self):
        win = self.open_wall([candidate()])
        table = self.table(win)
        rows = table.get_children()
        self.assertEqual(len(rows), 1)
        self.assertEqual(table.item(rows[0], 'image'), (str(self.win._tick_images[1]),))
        values = table.item(rows[0], 'values')
        self.assertEqual(str(values[1]), 'CC BY 署名')
        self.assertEqual(str(values[2]), '可商用')
        self.assertEqual(str(values[3]), '银发少女 立绘')

    def test_weak_candidate_is_filtered_until_the_threshold_drops(self):
        from tkinter import ttk
        win = self.open_wall([candidate(width=600, height=800)])
        table = self.table(win)
        self.assertEqual(len(table.get_children()), 0)
        spinboxes = self.walk(win, ttk.Spinbox)
        threshold = next(box for box in spinboxes if str(box.cget('from')) == '0')
        threshold.set('30')
        self.buttons(win)['重新打分'].invoke(); self.win.update()
        self.assertEqual(len(table.get_children()), 1)

    def test_confirm_hands_over_exactly_the_checked_candidates(self):
        base = self.library({'CHAR_001': {'name': '银发少女'}})
        win = self.open_wall([candidate(), candidate(url='https://b/2.png', title='银发少女 设定集', license='CC BY-NC')], base=base)
        table = self.table(win)
        rows = table.get_children()
        self.assertEqual(len(rows), 2)
        self.assertEqual(table.item(rows[1], 'image'), (str(self.win._tick_images[0]),))
        self.buttons(win)['确认入库'].invoke(); self.win.update()
        kind, work, _done = self.app.calls[-1]
        self.assertEqual(kind, 'async')
        result = work()
        self.assertEqual(len(result['adopted']), 1)
        self.assertEqual(result['skipped'], [])
        plan = json.loads((base / 'assets/资产清单/assets.json').read_text(encoding='utf-8'))
        self.assertEqual(len(plan['CHAR_001']['reference_images']), 1)
        credits = json.loads((base / search.CREDITS).read_text(encoding='utf-8'))
        self.assertEqual(credits[plan['CHAR_001']['reference_images'][0]]['license'], 'CC BY 署名')

    def test_right_click_views_the_source_page_and_drops_only_that_row(self):
        """第 46 期第 1／9 条：右键＝查看（开来源页）＋删除（只剔右键那一行）。"""
        from unittest.mock import patch as mock
        import cell_hover, webbrowser
        win = self.open_wall([candidate(), candidate(url='https://b/2.png', title='第二张')])
        table = self.table(win)
        rows = table.get_children()
        self.assertEqual(len(rows), 2)
        # bbox 要窗口真的摆出来了才给坐标（其余用例只读行内容，不点格子）。
        self.win.deiconify(); win.deiconify(); self.win.update()
        made = []; opened = []
        with mock.object(cell_hover.tk, 'Menu', lambda *a, **k: (made.append(_Popup()), made[-1])[1]), \
             mock.object(webbrowser, 'open', lambda url: opened.append(str(url))):
            x, y, width, height = table.bbox(rows[0], '#5')
            table.event_generate('<Button-3>', x=int(x + width // 2), y=int(y + height // 2))
            self.win.update()
            self.assertEqual([label for label, _ in made[-1].items], ['查看', '删除'])
            made[-1].items[0][1]()
            self.assertEqual(opened, ['https://example.com/a'])      # 开的是这一行的来源页
            made[-1].items[1][1]()
        self.win.update()
        left = list(table.get_children())
        self.assertEqual(left, [rows[1]])                            # 只剔掉右键那一行
        self.assertEqual(left, ['https://b/2.png'])

    def test_confirm_without_a_pick_shows_a_warning(self):
        import tkinter.messagebox as box
        warnings = []
        original = box.showerror
        box.showerror = lambda *a, **k: warnings.append(a[1] if len(a) > 1 else a)
        wall = sys.modules['reference_wall']
        self.addCleanup(setattr, wall.messagebox, 'showerror', original)
        win = self.open_wall([candidate(license='CC BY-NC')])
        self.buttons(win)['确认入库'].invoke(); self.win.update()
        self.assertEqual(len(warnings), 1)
        self.assertIn('勾选', str(warnings[0]))


if __name__ == '__main__':
    unittest.main(verbosity=1)
