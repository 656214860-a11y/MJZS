# -*- coding: utf-8 -*-
"""第 46 期第 1／9 条：内容框的右键菜单（查看／删除）与逐个／批量删除口径回归。

运行：python test_cell_menu.py
"""
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
sys.path.insert(0, HERE); os.chdir(HERE)


class _Popup:
    """替掉 tk.Menu：只记下摆过哪些项、弹在哪，不真的开窗（自检里没有鼠标去点它）。"""

    def __init__(self, *args, **kwargs):
        self.items = []; self.popped = None

    def add_command(self, label=None, command=None, **kwargs):
        self.items.append((label, command))

    def add_separator(self, **kwargs):
        self.items.append(("---", None))

    def index(self, where):
        return None if not self.items else len(self.items) - 1

    def tk_popup(self, x, y):
        self.popped = (int(x), int(y))

    def grab_release(self):
        pass


class _Event:
    def __init__(self, x, y):
        self.x = x; self.y = y; self.x_root = x + 500; self.y_root = y + 500


class _FakeTree:
    """只实现右键菜单用到的那几个查询，省得为了几条判断去开真窗口。"""

    def __init__(self, regions=None, rows=None, columns=None):
        self.regions = regions or {}; self.rows = rows or {}; self.columns = columns or {}
        self.bound = {}

    def bind(self, sequence, func, add=None):
        self.bound.setdefault(sequence, []).append(func)
        return "func-" + sequence

    def identify_region(self, x, y):
        return self.regions.get((x, y), "nothing")

    def identify_row(self, y):
        return self.rows.get(y, "")

    def identify_column(self, x):
        return self.columns.get(x, "#0")

    def selection_set(self, *rows):
        self.selected = tuple(rows)

    def focus(self, row=None):
        self.focused = row

    def selection(self):
        return getattr(self, "selected", ())


class RowMenuTests(unittest.TestCase):
    """popup_row_menu：菜单里摆什么、交出去的又是哪一行。"""

    def setUp(self):
        import cell_hover
        self.module = cell_hover
        self.made = []
        original = cell_hover.tk.Menu
        cell_hover.tk.Menu = lambda *a, **k: (self.made.append(_Popup(*a, **k)), self.made[-1])[1]
        self.addCleanup(setattr, cell_hover.tk, "Menu", original)

    def test_the_two_labels_are_view_and_delete(self):
        self.assertEqual((self.module.ROW_MENU_VIEW, self.module.ROW_MENU_DELETE), ("查看", "删除"))

    def test_both_items_hand_the_right_clicked_row_to_the_caller(self):
        calls = []
        menu = self.module.popup_row_menu(None, "SH002", "#3",
                                          view=lambda row, column: calls.append(("view", row, column)),
                                          delete=lambda row: calls.append(("delete", row)), x=10, y=20)
        self.assertEqual([label for label, _ in menu.items], ["查看", "删除"])
        self.assertEqual(menu.popped, (10, 20))
        for _label, command in menu.items:
            command()
        self.assertEqual(calls, [("view", "SH002", "#3"), ("delete", "SH002")])

    def test_a_cell_without_view_still_offers_delete(self):
        menu = self.module.popup_row_menu(None, "A", None, view=lambda row, column: None,
                                          delete=lambda row: None, x=1, y=1)
        self.assertEqual([label for label, _ in menu.items], ["删除"])

    def test_nothing_to_show_means_no_menu(self):
        self.assertIsNone(self.module.popup_row_menu(None, "A", None))
        self.assertEqual([menu for menu in self.made if menu.items], [])


class BindRowMenuTests(unittest.TestCase):
    """bind_row_menu：哪一格才弹、勾选列没有「查看」、删的一律是右键那一行。"""

    def setUp(self):
        import cell_hover
        self.module = cell_hover
        self.made = []
        original = cell_hover.tk.Menu
        cell_hover.tk.Menu = lambda *a, **k: (self.made.append(_Popup(*a, **k)), self.made[-1])[1]
        self.addCleanup(setattr, cell_hover.tk, "Menu", original)

    def hook(self, tree, columns=None):
        calls = []
        handler = self.module.bind_row_menu(
            tree,
            view=lambda row, column: calls.append(("view", row, column)),
            delete=lambda row: calls.append(("delete", row)),
            columns=columns)
        return handler, calls

    def test_a_cell_on_a_plain_table_offers_both(self):
        tree = _FakeTree(regions={(5, 5): "cell"}, rows={5: "A"}, columns={5: "#2"})
        handler, calls = self.hook(tree)
        self.assertEqual(handler(_Event(5, 5)), "break")
        self.assertEqual([label for label, _ in self.made[-1].items], ["查看", "删除"])
        for _label, command in self.made[-1].items:
            command()
        self.assertEqual(calls, [("view", "A", "#2"), ("delete", "A")])

    def test_the_header_and_the_empty_space_stay_silent(self):
        tree = _FakeTree(regions={(5, 5): "heading", (9, 9): "nothing"}, rows={5: "A", 9: ""})
        handler, calls = self.hook(tree)
        self.assertIsNone(handler(_Event(5, 5)))
        self.assertIsNone(handler(_Event(9, 9)))
        self.assertEqual(self.made, []); self.assertEqual(calls, [])

    def test_columns_outside_the_link_ones_open_no_menu(self):
        tree = _FakeTree(regions={(5, 5): "cell"}, rows={5: "A"}, columns={5: "#4"})
        handler, calls = self.hook(tree, columns=("#0", "#2"))
        self.assertIsNone(handler(_Event(5, 5)))
        self.assertEqual(self.made, []); self.assertEqual(calls, [])

    def test_the_checkbox_column_opens_no_menu(self):
        """第 52 期第 2 条：勾选列上没有可查看的文件，右键到它身上不再弹菜单。"""
        tree = _FakeTree(regions={(5, 5): "tree"}, rows={5: "A"}, columns={5: "#0"})
        handler, calls = self.hook(tree)
        self.assertIsNone(handler(_Event(5, 5)))
        self.assertEqual(self.made, [])
        self.assertEqual(calls, [])


class CellHoverRightClickTests(unittest.TestCase):
    """CellHover 上的右键：查看认这一格、删除认这一行，跟高亮那一行没关系。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def build(self):
        from tkinter import ttk
        import cell_hover
        from cell_hover import CellHover
        self.made = []
        original = cell_hover.tk.Menu
        cell_hover.tk.Menu = lambda *a, **k: (self.made.append(_Popup(*a, **k)), self.made[-1])[1]
        self.addCleanup(setattr, cell_hover.tk, "Menu", original)
        win = self.tk.Tk(); win.geometry("560x170+40+40")
        self.addCleanup(win.destroy)
        tree = ttk.Treeview(win, columns=("file", "content"), show="tree headings", height=2, selectmode="browse")
        tree.heading("file", text="文件"); tree.heading("content", text="内容(点击查看)")
        tree.column("file", width=160); tree.column("content", width=160)
        tree.pack(fill="both", expand=True)
        for item in ("A", "B"):
            tree.insert("", "end", iid=item, text="", values=(item + ".png", item + " 正文"))
        win.update()
        seen = []
        tree.cell_hover = CellHover(tree, ("#0", "#2"),
                                    lambda row, column: seen.append(("view", row, column)),
                                    delete=lambda row: seen.append(("delete", row)))
        win.update()
        return win, tree, seen

    def cell(self, tree, row, column):
        x, y, width, height = tree.bbox(row, column)
        return int(x + width // 2), int(y + height // 2)

    def test_the_delete_of_a_hovered_row_still_targets_the_right_clicked_row(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        win, tree, seen = self.build()
        # 先把鼠标停在 A 上（A 变成「高亮」那一行），再去右键 B。
        x, y = self.cell(tree, "A", "#2")
        tree.event_generate("<Motion>", x=x, y=y); win.update()
        self.assertEqual(tree.cell_hover.active, ("A", "#2"))
        x, y = self.cell(tree, "B", "#2")
        tree.event_generate("<Button-3>", x=x, y=y); win.update()
        self.assertEqual([label for label, _ in self.made[-1].items], ["查看", "删除"])
        for _label, command in self.made[-1].items:
            command()
        self.assertEqual(seen, [("view", "B", "#2"), ("delete", "B")])

    def test_the_checkbox_column_opens_no_menu(self):
        """第 52 期第 2 条：勾选列（#0）右键不弹菜单，带链接的格子照旧两项都有。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        win, tree, seen = self.build()
        x, y = self.cell(tree, "A", "#0")
        tree.event_generate("<Button-3>", x=x, y=y); win.update()
        self.assertEqual(self.made, [])
        self.assertEqual(seen, [])
        x, y = self.cell(tree, "A", "#2")
        tree.event_generate("<Button-3>", x=x, y=y); win.update()
        self.assertEqual([label for label, _ in self.made[-1].items], ["查看", "删除"])
        for _label, command in self.made[-1].items:
            command()
        self.assertEqual(seen, [("view", "A", "#2"), ("delete", "A")])

    def test_a_right_click_on_a_plain_cell_opens_nothing(self):
        """第 52 期第 2 条：纯文字格（没链接）右键不弹——原来还会兜底到 menu_column 那一格。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        win, tree, seen = self.build()
        x, y = self.cell(tree, "B", "#1")
        tree.event_generate("<Button-3>", x=x, y=y); win.update()
        self.assertEqual(self.made, [])
        self.assertEqual(seen, [])


class AssetDeleteTests(unittest.TestCase):
    """资产管理：逐个删除删的是传进来那一项，批量删除只认勾选行（高亮不算数）。"""

    def make(self, td):
        import desktop
        base = Path(td) / "episode" / "assets"
        (base / "assets" / "characters").mkdir(parents=True)
        registry = {}
        for aid in ("CHAR_001", "CHAR_002", "CHAR_003"):
            image = base / "assets" / "characters" / (aid + ".png")
            image.write_bytes(b"\x89PNG\r\n\x1a\n")
            registry[aid] = {"name": aid, "image": "assets/characters/" + aid + ".png"}
        (base / "assets.json").write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")

        class Status:
            def __init__(self): self.text = ""
            def set(self, text): self.text = str(text)

        class Stub(desktop.Desktop):
            def __init__(self):
                self.root = Path(td); self.asset_base_dir = base; self.win = None
                self.notes = []; self.shown = []; self.status = Status()
            def asset_base(self): return self.asset_base_dir
            def note(self, text): self.notes.append(str(text))
            def show(self, index=None): self.shown.append(index)

        return Stub(), registry, base

    def tree_for(self, ids, checked):
        table = _FakeTree()
        table.children = list(ids)
        table.selection = lambda: tuple(ids[1:2])
        table.get_children = lambda: tuple(table.children)
        table.winfo_exists = lambda: 1
        return table

    def test_batch_delete_falls_back_to_the_highlighted_row(self):
        """第 47 期第 1 条：一行都没勾时，批量删除按高亮那一行算，提示里写明这一点。

        原来这种情形被一句「先在资产表里勾选…」打回去——用户看着那一行明明是选中的。
        """
        import desktop
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            stub, _registry, base = self.make(td)
            stub.asset_table = self.tree_for(["CHAR_001", "CHAR_002", "CHAR_003"], None)   # 高亮 CHAR_002
            stub.asset_checks = {str(Path(td).resolve()): {}}
            asked = []
            with patch.object(desktop, "confirm",
                              lambda *a, **k: (asked.append(a[2] if len(a) > 2 else a), True)[1]):
                done = stub.delete_asset_images()
            self.assertEqual(done, ["CHAR_002"], "没勾选就按高亮那一行算")
            self.assertIn("按高亮的那一行 CHAR_002 算", asked[0])
            saved = json.loads((base / "assets.json").read_text(encoding="utf-8"))
            self.assertNotIn("image", saved["CHAR_002"])
            self.assertIn("image", saved["CHAR_001"])
            self.assertIn("image", saved["CHAR_003"])

    def test_checked_ids_never_looks_at_the_highlight(self):
        import desktop
        with tempfile.TemporaryDirectory() as td:
            stub, _registry, _base = self.make(td)
            stub.asset_table = self.tree_for(["CHAR_001", "CHAR_002", "CHAR_003"], None)
            stub.asset_checks = {str(Path(td).resolve()): {"CHAR_001": True, "CHAR_003": True}}
            self.assertEqual(desktop.Desktop.asset_checked_ids(stub), ["CHAR_001", "CHAR_003"])
            self.assertEqual(desktop.Desktop.asset_selected(stub), "CHAR_002")

    def test_one_row_delete_only_touches_that_row(self):
        with tempfile.TemporaryDirectory() as td:
            stub, _registry, base = self.make(td)
            self.assertTrue(stub.delete_asset_image("CHAR_002", ask=False))
            saved = json.loads((base / "assets.json").read_text(encoding="utf-8"))
            self.assertNotIn("image", saved["CHAR_002"])
            self.assertIn("image", saved["CHAR_001"])
            self.assertIn("image", saved["CHAR_003"])
            self.assertFalse((base / "assets" / "characters" / "CHAR_002.png").is_file())

    def test_batch_delete_follows_the_checked_rows_only(self):
        import desktop
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            stub, _registry, base = self.make(td)
            stub.asset_table = self.tree_for(["CHAR_001", "CHAR_002", "CHAR_003"], None)
            stub.asset_checks = {str(Path(td).resolve()): {"CHAR_001": True}}
            with patch.object(desktop, "confirm", lambda *a, **k: True):
                done = stub.delete_asset_images()
            self.assertEqual(done, ["CHAR_001"])
            saved = json.loads((base / "assets.json").read_text(encoding="utf-8"))
            self.assertNotIn("image", saved["CHAR_001"])
            self.assertIn("image", saved["CHAR_002"])       # 高亮的那一项没被动
            self.assertIn("image", saved["CHAR_003"])

    def test_batch_delete_without_a_check_says_what_to_do(self):
        with tempfile.TemporaryDirectory() as td:
            stub, _registry, _base = self.make(td)
            stub.asset_table = self.tree_for(["CHAR_001"], None)
            stub.asset_checks = {}
            with self.assertRaises(ValueError) as ctx:
                stub.delete_asset_images()
            self.assertIn("勾选", str(ctx.exception))


class VideoShotMenuTests(unittest.TestCase):
    """07 视频页：右键＝查看（首帧／视频）＋删除；批量删除只认勾选行。"""

    def setUp(self):
        import app
        self.app = app
        self.made = []
        original = app.tk.Menu
        app.tk.Menu = lambda *a, **k: (self.made.append(_Popup(*a, **k)), self.made[-1])[1]
        self.addCleanup(setattr, app.tk, "Menu", original)

    class Studio:
        def __init__(self, episode_path, state=None):
            self.episode_path = episode_path
            self.episode = json.loads(Path(episode_path).read_text(encoding="utf-8"))
            self._state = state or {"shots": {}}
        def lock(self):
            import contextlib
            return contextlib.nullcontext()
        def state(self):
            return self._state

    class Node:
        def __init__(self): self.calls = []
        def delete(self, *args): self.calls.append(args)

    def stub(self, td, episodes, state=None):
        source = Path(td) / "episode.json"
        source.write_text(json.dumps(episodes, ensure_ascii=False), encoding="utf-8")
        subject = type("Stub", (), {})()
        subject.busy = False
        subject.window = None
        subject.root = Path(td)
        subject.studio = self.Studio(source, state)
        subject.selected = []
        subject.select = lambda: subject.selected.append("selected")
        subject.safe = lambda fn: fn()
        # 第 54 期第 3 条起右键要认格子：默认点在「首帧」那一列（#5）上。
        subject.tree = _FakeTree(regions={(5, 5): "cell"}, rows={5: "SH002"}, columns={5: "#5"})
        subject.refreshed = []
        subject.refresh = lambda: subject.refreshed.append(True)
        subject.prompt = self.Node(); subject.note = self.Node()
        # 第 48 期第 4 条：清空提示词框要顺手把高度缩回来，假 App 也得有这个方法。
        subject.fit_prompt_height = lambda: None
        subject.written = []
        subject.write = lambda text: subject.written.append(str(text))
        subject.edit_checks = {}
        # 第 54 期第 3 条：右键要认格子，判据搬进了 App.cell_actions——把真实现绑到这个假体上，
        # 测的就是真代码，不是另写一份。
        for name in ("cell_actions", "asset_column", "video_column", "white_model_path"):
            setattr(subject, name, getattr(self.app.App, name).__get__(subject, type(subject)))
        return subject, source

    def test_the_menu_only_lists_the_file_of_the_cell_under_the_pointer(self):
        """第 54 期第 3 条：右键只看鼠标底下那一格——纯文字格不弹，带文件的那格只摆本栏的文件。

        「首帧」列只开（或删）首帧；点了导出用起来的那一格（镜头号／内容／秒数……）什么都不弹。
        """
        with tempfile.TemporaryDirectory() as td:
            subject, source = self.stub(td, {"shots": [{"id": "SH002", "title": "T"}]})
            frame = Path(td) / "frames" / "SH002.png"
            frame.parent.mkdir(parents=True, exist_ok=True)
            frame.write_bytes(b"\x89PNG\r\n\x1a\n")
            picked = []
            opened = []
            subject.studio.frame = lambda shot, required=True: frame
            subject.opened = opened
            subject.asset_column = lambda: "#3"
            subject.video_column = lambda name: {"local_progress": "#7", "cloud_progress": "#8",
                                                 "white_model": "#11"}[name]
            subject.shot_asset_rows = lambda sid: []
            subject.chosen_asset_ids = lambda shot, rows: []
            subject.studio.shot = lambda sid: {"id": sid}
            subject.white_model_path = lambda sid: None
            event = _Event(5, 5); event.x_root = 5; event.y_root = 5
            self.app.open_path = lambda path: opened.append(path)
            # 「首帧」那一格：只剩首帧自己的「查看」（删除首帧只留 06 首帧管理那一页）
            self.app.App.shot_menu(subject, event)
            labels = [label for label, _ in self.made[-1].items]
            self.assertEqual(labels, ["查看首帧图片"])
            self.assertEqual(subject.selected, ["selected"])       # 右键先选中这一行
            for _label, command in self.made[-1].items:
                if command is not None:
                    command()
            self.assertEqual(opened, [frame])
            self.assertEqual(picked, [])
            # 纯文字列（内容＝#2）：一格都不弹
            before = len(self.made)
            subject.tree = _FakeTree(regions={(5, 5): "cell"}, rows={5: "SH002"}, columns={5: "#2"})
            self.app.App.shot_menu(subject, event)
            self.assertEqual(len(self.made), before, "纯文字格上不该弹菜单")
            # 表头／滚动条上也不弹
            subject.tree = _FakeTree(regions={(5, 5): "heading"}, rows={5: "SH002"}, columns={5: "#5"})
            self.app.App.shot_menu(subject, event)
            self.assertEqual(len(self.made), before, "表头上不该弹菜单")

    def test_batch_delete_only_takes_the_checked_shots(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            shots = [{"id": "SH001"}, {"id": "SH002"}, {"id": "SH003", "video_deleted": True}]
            subject, _source = self.stub(td, {"shots": shots}, state={"shots": {}})
            subject.edit_checks = {"SH001": True, "SH002": False, "SH003": True}
            deleted = []
            subject.delete_video_shot = lambda sid=None, **k: deleted.append(sid) or True
            with patch.object(self.app, "ask_confirmation", lambda *a, **k: True):
                self.app.App.delete_checked_shots(subject)
            self.assertEqual(deleted, ["SH001"])                  # 未勾选与已删的都跳过
            self.assertEqual(subject.refreshed, [True])
            self.assertTrue(any("SH001" in text for text in subject.written))

    def test_batch_delete_falls_back_to_the_highlighted_shot(self):
        """第 47 期第 1 条：一镜都没勾时，批量删除按高亮那一镜算（日志里写明白）。"""
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            shots = [{"id": "SH001"}, {"id": "SH002"}]
            subject, _source = self.stub(td, {"shots": shots}, state={"shots": {}})
            subject.edit_checks = {}
            subject.tree.selected = ("SH002",)          # 高亮那一行（_FakeTree 的 selection 读它）
            deleted = []
            subject.delete_video_shot = lambda sid=None, **k: deleted.append(sid) or True
            with patch.object(self.app, "ask_confirmation", lambda *a, **k: True):
                self.app.App.delete_checked_shots(subject)
            self.assertEqual(deleted, ["SH002"], "没勾选就按高亮那一行算")
            self.assertTrue(any("按高亮的那一行 SH002" in text for text in subject.written),
                            "日志里写清楚这一行是按高亮算的：" + repr(subject.written))

    def test_batch_delete_without_a_check_says_what_to_do(self):
        with tempfile.TemporaryDirectory() as td:
            subject, _source = self.stub(td, {"shots": [{"id": "SH001"}]})
            with self.assertRaises(ValueError) as ctx:
                self.app.App.delete_checked_shots(subject)
            self.assertIn("勾选", str(ctx.exception))

    def test_one_row_delete_marks_only_that_shot(self):
        with tempfile.TemporaryDirectory() as td:
            shots = {"shots": {"SH001": [{"state": "downloaded"}], "SH002": [{"state": "downloaded"}]}}
            subject, source = self.stub(td, {"shots": [{"id": "SH001"}, {"id": "SH002"}]}, state=shots)
            self.assertTrue(self.app.App.delete_video_shot(subject, "SH002", ask=False, rebuild=False))
            saved = json.loads(source.read_text(encoding="utf-8"))
            marks = {shot["id"]: bool(shot.get("video_deleted")) for shot in saved["shots"]}
            self.assertEqual(marks, {"SH001": False, "SH002": True})

    def test_a_shot_with_a_running_task_is_not_deleted(self):
        with tempfile.TemporaryDirectory() as td:
            subject, _source = self.stub(td, {"shots": [{"id": "SH002"}]},
                                         state={"shots": {"SH002": [{"state": "running"}]}})
            with self.assertRaises(ValueError) as ctx:
                self.app.App.delete_video_shot(subject, "SH002", ask=False, rebuild=False)
            self.assertIn("未完成", str(ctx.exception))


class ReferenceRowMenuTests(unittest.TestCase):
    """参考图弹窗：右键＝查看这一行的图片／解除这一行的绑定。"""

    PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def build(self):
        from tkinter import ttk
        import cell_hover
        from asset_reference_images import show
        base = Path(self.tmp.name) / "library"
        (base / "assets" / "参考图" / "角色").mkdir(parents=True)
        (base / "assets" / "资产清单").mkdir(parents=True)
        values = []; roles = {}
        for name in ("a.png", "b.png"):
            target = base / "assets" / "参考图" / "角色" / name
            target.write_bytes(self.PNG)
            rel = target.relative_to(base).as_posix()
            values.append(rel); roles[rel] = "长相"
        (base / "assets" / "资产清单" / "assets.json").write_text(json.dumps(
            {"CHAR_001": {"name": "银发少女", "reference_images": values, "reference_roles": roles}},
            ensure_ascii=False), encoding="utf-8")
        win = self.tk.Tk(); win.withdraw()
        self.addCleanup(win.destroy)
        subject = type("Stub", (), {})()
        subject.win = win; subject.root = Path(self.tmp.name)
        subject.shown = []; subject.errors = []
        subject.show = lambda index: subject.shown.append(index)
        subject.asset_base = lambda: base
        def safe(fn):
            try:
                return fn()
            except Exception as exc:
                subject.errors.append(str(exc)); return None
        subject.safe = safe
        show(subject, "CHAR_001")          # show() 只管开窗，返回值是 None——按窗口找它
        dialog = [child for child in win.winfo_children() if isinstance(child, self.tk.Toplevel)][-1]
        self.addCleanup(dialog.destroy)
        win.deiconify(); dialog.deiconify(); win.update()
        table = [w for w in self.walk(dialog, ttk.Treeview)][0]
        opener = []
        original = cell_hover.tk.Menu
        cell_hover.tk.Menu = lambda *a, **k: (self.made.append(_Popup(*a, **k)), self.made[-1])[1]
        self.addCleanup(setattr, cell_hover.tk, "Menu", original)
        original_open = os.startfile
        os.startfile = lambda path: opener.append(str(path))
        self.addCleanup(setattr, os, "startfile", original_open)
        return subject, dialog, table, base, opener

    def walk(self, widget, kind):
        found = [widget] if isinstance(widget, kind) else []
        for child in widget.winfo_children():
            found.extend(self.walk(child, kind))
        return found

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.made = []

    def right_click(self, win, table, row, column):
        x, y, width, height = table.bbox(row, column)
        table.event_generate("<Button-3>", x=int(x + width // 2), y=int(y + height // 2))
        win.update()

    def test_view_opens_that_row_and_delete_unbinds_it(self):
        subject, win, table, base, opener = self.build()
        rows = list(table.get_children())
        self.assertEqual(len(rows), 2)
        dropped = table.set(rows[0], "file"); kept = table.set(rows[1], "file")
        self.right_click(win, table, rows[0], "#1")
        self.assertEqual([label for label, _ in self.made[-1].items], ["查看", "删除"])
        self.made[-1].items[0][1]()                      # 查看
        self.assertEqual(opener, [str((base / dropped).resolve())])
        self.made[-1].items[1][1]()                      # 删除
        win.update()
        plan = json.loads((base / "assets" / "资产清单" / "assets.json").read_text(encoding="utf-8"))
        self.assertEqual(plan["CHAR_001"]["reference_images"], [kept])   # 只解除右键那一行
        self.assertEqual([table.set(row, "file") for row in table.get_children()], [kept])
        self.assertEqual(subject.errors, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

class ReferenceViewThumbTests(unittest.TestCase):
    """第 57 期第 4／5 条：03 资产管理里「参考图」那一格点出来的那一窗。

    用户要的是「分类栏右边增加缩略图栏，显示对应图片」：原来只有分类与路径两列，看的人得
    一行行按路径去认图。缩略图那一列交给盖图那一层（解不开的格式留空），单击那一格＝打开
    这一行的图、停上去放大（与资产页「参考图」那一格同一套）。
    """

    PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')

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
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.opener = []

    def walk(self, widget, kind):
        found = [widget] if isinstance(widget, kind) else []
        for child in widget.winfo_children():
            found.extend(self.walk(child, kind))
        return found

    def build(self):
        from tkinter import ttk
        from asset_reference_images import view_references
        base = Path(self.tmp.name) / "library"
        (base / "assets" / "参考图" / "角色").mkdir(parents=True)
        (base / "assets" / "资产清单").mkdir(parents=True)
        values = []; roles = {}
        for name in ("a.png", "b.png"):
            target = base / "assets" / "参考图" / "角色" / name
            target.write_bytes(self.PNG)
            rel = target.relative_to(base).as_posix()
            values.append(rel); roles[rel] = "长相"
        (base / "assets" / "资产清单" / "assets.json").write_text(json.dumps(
            {"CHAR_001": {"name": "银发少女", "reference_images": values, "reference_roles": roles}},
            ensure_ascii=False), encoding="utf-8")
        win = self.tk.Tk(); win.withdraw()
        self.addCleanup(win.destroy)
        subject = type("Stub", (), {})()
        subject.win = win; subject.root = Path(self.tmp.name)
        subject.shown = []; subject.errors = []
        subject.show = lambda index: subject.shown.append(index)
        subject.asset_base = lambda: base
        def safe(fn):
            try:
                return fn()
            except Exception as exc:
                subject.errors.append(str(exc)); return None
        subject.safe = safe
        original_open = os.startfile
        os.startfile = lambda path: self.opener.append(str(path))
        self.addCleanup(setattr, os, "startfile", original_open)
        win.deiconify()
        view_references(subject, "CHAR_001")
        dialog = [child for child in win.winfo_children() if isinstance(child, self.tk.Toplevel)][-1]
        self.addCleanup(dialog.destroy)
        dialog.deiconify(); win.update()
        table = [w for w in self.walk(dialog, ttk.Treeview) if list(w["columns"]) == ["role", "thumb", "file"]]
        self.assertEqual(len(table), 1, "那一窗只有一张内容框")
        # 对话框关闭前主动撤销缩略图放大层的 after watcher；真实窗口关闭也走同一释放顺序。
        self.addCleanup(table[0].cell_images.destroy)
        return subject, win, table[0], base

    def test_the_category_column_has_a_thumbnail_beside_it(self):
        subject, win, table, base = self.build()
        self.assertEqual(str(table.heading("thumb", "text")), "缩略图")
        rows = list(table.get_children())
        self.assertEqual(len(rows), 2)
        self.assertEqual([str(table.set(row, "role")) for row in rows], ["长相", "长相"])
        covered = table.cell_images.refresh()
        self.assertEqual(sorted(covered), sorted((row, "#2") for row in rows),
                         "每一行都盖上一张缩略图")
        label = table.cell_images.labels[(rows[0], "#2")]
        self.assertTrue(str(label.cget("image")), "盖上去的得是图")
        self.assertTrue(callable(table.cell_images.zoom), "停上去要放大")
        table.cell_hover.open(rows[0], "#2")             # 单击那一格＝打开这一行的图
        win.update()
        self.assertEqual(self.opener, [str((base / table.set(rows[0], "file")).resolve())])
        self.assertEqual(subject.errors, [])

    def test_a_missing_picture_leaves_the_cell_blank(self):
        """解不开的格式与丢了的文件都不盖图：那一格留空，别的行照旧。"""
        subject, win, table, base = self.build()
        rows = list(table.get_children())
        (base / table.set(rows[0], "file")).unlink()
        self.assertEqual(table.cell_images.refresh(), {(rows[1], "#2")}, "少了文件就不盖那一行")
        self.assertEqual(subject.errors, [])


class ForwardToTreeTests(unittest.TestCase):
    """第 53 期第 1／2／5 条：盖在格子上的那两层（高亮／缩略图）把单击与右键重发给树。

    白模预演与 07 镜头内容框这两页的格子底下本来就是树自己在管（切勾选、点开「选择资产」
    下拉框、弹本页的镜头菜单）。高亮层一盖上去鼠标就落不到树上了，所以调用方给一个 forward
    把这一下原样重放一遍——重发只绑这两层，绑到树上会把事件再发一次、绕回自己。
    """

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def build(self):
        from tkinter import ttk
        from cell_hover import CellHover, CellImages
        win = self.tk.Tk(); win.geometry("520x220+30+30"); win.deiconify()
        self.addCleanup(win.destroy)
        tree = ttk.Treeview(win, columns=("name", "status"), show="tree headings", height=3)
        tree.heading("name", text="名称"); tree.heading("status", text="状态")
        tree.pack(fill="both", expand=True)
        tree.insert("", "end", iid="A", text="", values=("甲", "已导入"))
        hits = []
        tree.bind("<Button-1>", lambda event: hits.append(("click", tree.identify_row(event.y))), add="+")
        tree.bind("<Button-3>", lambda event: hits.append(("menu", tree.identify_row(event.y))), add="+")

        def forward(event):
            tree.event_generate("<Button-%d>" % int(event.num),
                                x=event.x_root - tree.winfo_rootx(),
                                y=event.y_root - tree.winfo_rooty())
            return "break"

        hover = CellHover(tree, ("#1",), lambda row, column: None, hover_only=True, forward=forward)
        tree.cell_hover = hover
        image = self.tk.PhotoImage(master=win, width=8, height=8)
        tree.cell_images = CellImages(tree, ("#2",), lambda row, column: (image, ""),
                                      hover=hover, forward=forward)
        self.addCleanup(tree.cell_images.destroy)
        win.update()
        return win, tree, hover, hits

    def spot_of(self, widget, box):
        return dict(x=box[2] // 2, y=box[3] // 2,
                    rootx=widget.winfo_rootx() + box[2] // 2,
                    rooty=widget.winfo_rooty() + box[3] // 2)

    def test_the_highlight_layer_forwards_clicks_to_the_tree(self):
        win, tree, hover, hits = self.build()
        box = tree.bbox("A", "#1")
        hover.at(box[0] + box[2] // 2, box[1] + box[3] // 2)
        win.update()                      # 高亮层刚 place 上去，得等它映射出来才收得到合成事件
        self.assertEqual(hover.active, ("A", "#1"), "只高亮：不打开、不勾选，先把这一格亮起来")
        hover.overlay.event_generate("<Button-1>", **self.spot_of(hover.overlay, box)); win.update()
        self.assertEqual(hits, [("click", "A")], "单击落回树上原样处理")
        hover.overlay.event_generate("<Button-3>", **self.spot_of(hover.overlay, box)); win.update()
        self.assertEqual(hits[-1], ("menu", "A"), "右键也落回树上，弹本页自己的菜单")
        self.assertEqual(len(hover.forward_bind_ids), 2)

    def test_the_cover_layer_forwards_clicks_to_the_tree(self):
        win, tree, hover, hits = self.build()
        self.assertEqual(tree.cell_images.refresh(), {("A", "#2")})
        win.update()
        label = tree.cell_images.labels[("A", "#2")]
        box = tree.bbox("A", "#2")
        label.event_generate("<Button-1>", **self.spot_of(label, box)); win.update()
        self.assertEqual(hits, [("click", "A")], "缩略图那一格上单击也落回树上")

    def test_the_two_layers_do_not_forward_through_the_tree(self):
        """重发只绑这两层：树上再挂一份就会「转发 → 树 → 转发」绕圈。"""
        win, tree, hover, _hits = self.build()
        tree_binds = str(tree.bind("<Button-1>")) + " " + str(tree.bind("<Button-3>"))
        for funcid in hover.forward_bind_ids:
            self.assertNotIn(funcid, tree_binds)
        self.assertIn(("A", "#2"), tree.cell_images.labels,
                      "第 55 期第 1 条：盖图那一层自己跟着视图重排，不必等调用方 refresh")

    def test_the_double_click_opens_and_the_menu_view_does(self):
        """第 64 期任务 12：缩略图**双击打开**这一格的文件（单击只点亮这一行）。

        第 60 期第 3 条原来把左键整条撤了（双击也不打开）：那一下常被当成「先点亮这一行」。
        用户这一轮明确要「双击打开图片」，所以只把单击那条路留着当点亮，双击补回来；
        右键菜单里的「查看」照旧是同一条路（放大图压在别的格子上时也认来路那一格）。
        """
        import cell_hover
        from tkinter import ttk
        from cell_hover import CellHover, CellImages
        win = self.tk.Tk(); win.geometry("520x220+30+30"); win.deiconify()
        self.addCleanup(win.destroy)
        tree = ttk.Treeview(win, columns=("name", "status"), show="tree headings", height=3)
        tree.heading("name", text="名称"); tree.heading("status", text="状态")
        tree.pack(fill="both", expand=True)
        tree.insert("", "end", iid="A", text="", values=("甲", "已导入"))
        seen = []
        tree.cell_hover = CellHover(tree, ("#1",), lambda row, column: seen.append((row, column)),
                                    delete=lambda row: seen.append(("del", row)))
        image = self.tk.PhotoImage(master=win, width=8, height=8)
        tree.cell_images = CellImages(tree, ("#1",), lambda row, column: (image, "甲"),
                                      hover=tree.cell_hover)
        win.update()
        box = tree.bbox("A", "#1")
        tree.cell_images.refresh(); win.update()
        label = tree.cell_images.labels[("A", "#1")]
        spot = self.spot_of(label, box)
        label.event_generate("<Button-1>", **spot); win.update()
        self.assertEqual(seen, [], "第 64 期任务 12：单击只点亮这一行，不打开")
        # 第 64 期任务 12：Tk 不给合成 <Double-1>（event_generate 直接抛「Double … not allowed」），
        # 按 test_pet_ui 的老办法——先确认这一格真接了双击入口，再走同一个处理函数。
        self.assertTrue(label.bind("<Double-1>"), "双击这一格的入口没接上")
        tree.cell_images.view(("A", "#1")); win.update()
        self.assertEqual(seen, [("A", "#1")], "第 64 期任务 12：双击打开这一格的文件")
        del seen[:]
        made = []
        original = cell_hover.popup_row_menu
        cell_hover.popup_row_menu = lambda tree_, row, column, view=None, delete=None, x=None, y=None: made.append((row, column, view, delete))
        self.addCleanup(setattr, cell_hover, "popup_row_menu", original)
        label.event_generate("<Button-3>", **spot); win.update()
        self.assertEqual([(row, column) for row, column, _view, _delete in made], [("A", "#1")],
                         "右键这一格＝这一格的菜单")
        self.assertTrue(made[-1][3], "菜单里照旧带着「删除」（删的是这一行）")
        made[-1][2]("A", "#1")                    # 菜单里的「查看」
        self.assertEqual(seen, [("A", "#1")], "右键菜单里的「查看」也打开这一格")


class CellImagesTests(unittest.TestCase):
    """第 52 期第 3 条：缩略图那层 Label——只盖该盖的格子，鼠标事件转给 CellHover。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def build(self, covers=("A",)):
        from tkinter import ttk
        from cell_hover import CellHover, CellImages
        win = self.tk.Tk(); win.geometry("520x220+30+30"); win.deiconify()
        self.addCleanup(win.destroy)
        tree = ttk.Treeview(win, columns=("name", "status"), show="tree headings", height=3)
        tree.heading("name", text="名称"); tree.heading("status", text="导入图片")
        tree.pack(fill="both", expand=True)
        for item in ("A", "B"):
            tree.insert("", "end", iid=item, text="", values=(item, "已导入"))
        win.update()
        seen = []
        tree.cell_hover = CellHover(tree, ("#1",), lambda row, column: seen.append((row, column)),
                                    delete=lambda row: seen.append(("del", row)))
        image = self.tk.PhotoImage(master=win, width=8, height=8)
        # 第 52 期第 3 条：#2 只盖图、不带文字（资产表「导入图片」那一列就是纯缩略图）。
        tree.cell_images = CellImages(tree, ("#1", "#2"),
                                      lambda row, column: (image, row if column == "#1" else "") if row in covers else None,
                                      hover=tree.cell_hover)
        # 真实页面换页会先释放这一层；测试若直接销毁根窗口，需同样撤掉它的 after watcher。
        self.addCleanup(tree.cell_images.destroy)
        win.update()
        return win, tree, seen

    def test_only_the_rows_with_a_picture_get_a_label(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        win, tree, _seen = self.build()
        covered = tree.cell_images.refresh()
        self.assertEqual(covered, {("A", "#1"), ("A", "#2")}, "只有 A 那一行有图")
        self.assertEqual(sorted(tree.cell_images.labels), [("A", "#1"), ("A", "#2")])
        self.assertEqual(str(tree.cell_images.labels[("A", "#1")].cget("text")), "A",
                         "带文字的那一列是「图 ＋ 名称」")
        self.assertEqual(str(tree.cell_images.labels[("A", "#2")].cget("text")), "")

    def test_the_cover_does_not_highlight_and_the_double_click_opens(self):
        """第 55 期第 2 条：盖着缩略图的格子不再走高亮（原来两层叠在同一格上互相顶掉，
        用户判它显示不对）；第 64 期任务 12：单击只点亮这一行、双击打开这一格的文件。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        win, tree, seen = self.build()
        tree.cell_images.refresh()
        label = tree.cell_images.labels[("A", "#1")]
        width, height = tree.bbox("A", "#1")[2], tree.bbox("A", "#1")[3]
        # 合成事件只带 x／y（窗口内坐标），而 CellHover 是按 x_root／y_root 换算的，得一并给上
        # （真鼠标事件这两个字段本来就有，只有造出来的才缺）。
        win.update()
        spot = dict(x=width // 2, y=height // 2,
                    rootx=label.winfo_rootx() + width // 2, rooty=label.winfo_rooty() + height // 2)
        label.event_generate("<Motion>", **spot); win.update()
        self.assertIsNone(tree.cell_hover.active, "盖住的格子不再走高亮")
        self.assertIn("#1", tree.cell_hover.plain, "这一列已经登记为「归盖图那一层」")
        label.event_generate("<Button-1>", **spot); win.update()
        self.assertEqual(seen, [], "第 64 期任务 12：单击只点亮这一行，不打开")
        self.assertTrue(label.bind("<Double-1>"), "双击缩略图的入口没接上")
        tree.cell_images.view(("A", "#1")); win.update()
        self.assertEqual(seen, [("A", "#1")], "第 64 期任务 12：双击缩略图打开这一格的文件")

    def test_covering_a_cell_takes_its_text_and_gives_it_back(self):
        """第 55 期第 3 条：图上那格不再写字——文字由盖图这一层收着，撤掉图再写回去。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        win, tree, _seen = self.build()
        tree.cell_images.refresh(); win.update()
        self.assertEqual(str(tree.set("A", "#1")), "", "盖上的那一格不再写字（值在图上）")
        self.assertEqual(str(tree.cell_images.labels[("A", "#1")].cget("text")), "A",
                         "文字没丢：改由那层 Label 自己写")
        tree.cell_images.provider = lambda row, column: None
        tree.cell_images.refresh(); win.update()
        # 这一行 value 那一格里本来就是「A」（build() 里 values=(item, "已导入")）
        self.assertEqual(str(tree.set("A", "#1")), "A", "撤掉图，格子里的文字原样写回")
        self.assertEqual(tree.cell_images.texts, {}, "收着的文字交回去了，不留残留")

    def test_view_refresh_reuses_existing_cover_but_explicit_refresh_rechecks(self):
        """滚动只重摆已在屏内的图层；调用方显式刷新仍必须重新询问 provider。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        win, tree, _seen = self.build()
        calls = [0]
        original = tree.cell_images.provider

        def provider(row, column):
            calls[0] += 1
            return original(row, column)

        tree.cell_images.provider = provider
        tree.cell_images.refresh(); win.update()
        initial = calls[0]
        tree.cell_images.refresh(reuse_existing=True); win.update()
        self.assertEqual(calls[0], initial + 2,
                         "只应读取尚未覆盖的 B 行两个格；A 行既有图层只需重摆")
        tree.cell_images.refresh(); win.update()
        self.assertGreater(calls[0], initial, "显式刷新用于数据变更，必须仍重新读取 provider")

    def test_scrolling_and_resizing_drag_the_cover_along(self):
        """第 55 期第 1 条：格子向左走了（横向滚动）或列宽变了，缩略图得跟着走。

        这两条路原来都不通知盖图那一层：调用方只在 xscrollcommand 末尾补一次 refresh，
        而列宽变化连事件都没有——用户看到的就是「格子走了、缩略图还钉在原处」。
        """
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        from cell_hover import CellHover, CellImages
        win = self.tk.Tk(); win.geometry("420x220+30+30"); win.deiconify()
        self.addCleanup(win.destroy)
        tree = ttk.Treeview(win, columns=("a", "b", "c"), show="tree headings", height=3)
        for name in ("a", "b", "c"):
            tree.heading(name, text=name); tree.column(name, width=300, minwidth=60)
        tree.pack(fill="both", expand=True)
        tree.insert("", "end", iid="A", text="", values=("甲", "乙", "丙"))
        bar = ttk.Scrollbar(win, orient="horizontal", command=tree.xview); bar.pack(fill="x")
        # 只装最朴素的那条回调：不给任何 refresh —— 第 55 期第 1 条要的正是这种情形也跟得上
        tree.configure(xscrollcommand=bar.set)
        image = self.tk.PhotoImage(master=win, width=16, height=16)
        tree.cell_hover = CellHover(tree, ("#1",), lambda row, column: None)
        tree.cell_images = CellImages(tree, ("#2",), lambda row, column: (image, ""),
                                     hover=tree.cell_hover)
        win.update()
        label = tree.cell_images.labels[("A", "#2")]
        self.assertEqual(label.winfo_x(), tree.bbox("A", "#2")[0], "先跟格子对齐")
        tree.xview_moveto(1.0); win.update()
        self.assertLess(tree.bbox("A", "#2")[0], 0, "滚到最右：这一格已经落到可视区左边")
        self.assertEqual(label.winfo_x(), tree.bbox("A", "#2")[0], "缩略图跟着格子走")
        tree.column("b", width=120); win.update()
        self.assertEqual(label.winfo_x(), tree.bbox("A", "#2")[0], "列宽变了照样跟着走")
        # 第 57 期第 4 条：用鼠标拖表头那条分隔线改列宽，走的是 ttk 内部的 Tcl——既不经过
        # tree.column()、也不改内容框尺寸，原来那三条来源一个都不响（用户看到的就是「列宽变了、
        # 缩略图还按老宽度摆着，滑一下才跟上」）。这里按「按下—拖动—松开」走一遍。
        box = tree.bbox("A", "#2")
        tree.event_generate("<Button-1>", x=box[0] + box[2], y=2)      # 按在分隔线上
        self.assertTrue(getattr(tree, "_view_resizing", False), "按在分隔线上＝这一趟在拖列宽")
        tree.tk.call(tree, "column", "a", "-width", 200)               # 绕开 tree.column 改列宽
        self.assertNotEqual(label.winfo_x(), tree.bbox("A", "#2")[0], "先制造出「格子走了」")
        tree.event_generate("<B1-Motion>", x=box[0] + box[2] + 40, y=2)
        win.update()
        self.assertEqual(label.winfo_x(), tree.bbox("A", "#2")[0], "拖动途中就重排到新位置")
        self.assertEqual(int(label.place_info()["width"]), tree.bbox("A", "#2")[2], "宽度也跟着重排")
        tree.event_generate("<ButtonRelease-1>", x=box[0] + box[2] + 40, y=2)
        self.assertFalse(getattr(tree, "_view_resizing", False), "松手＝这一趟拖完了")

    def test_the_zoom_hugs_the_top_right_of_the_pointer(self):
        """第 58 期第 3 条：放大图紧贴鼠标右上角——底边压着指针、往右上铺开。

        右边／上头装不下就翻到另一边，怎么摆都不许出窗口。指针位置在这里是造出来的
        （`winfo_pointerxy` 换成固定点），真鼠标在哪一台机器上都不一样。
        """
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        from cell_hover import CellHover, CellImages, ZOOM_NEAR
        win = self.tk.Tk(); win.geometry("520x300+40+40"); win.deiconify()
        self.addCleanup(win.destroy)
        tree = ttk.Treeview(win, columns=("a",), show="tree headings", height=4)
        tree.pack(fill="both", expand=True)
        tree.insert("", "end", iid="A", text="", values=("甲",))
        win.update()
        big = self.tk.PhotoImage(master=win, width=120, height=90)
        tree.cell_hover = CellHover(tree, ("#1",), lambda row, column: None)
        tree.cell_images = CellImages(tree, ("#1",), lambda row, column: (big, ""),
                                      hover=tree.cell_hover, zoom=lambda row, column: big)
        self.addCleanup(tree.cell_images.destroy)
        win.update()
        left0, top0 = win.winfo_rootx(), win.winfo_rooty()

        def place_at(x, y):
            tree.winfo_pointerxy = lambda: (left0 + x, top0 + y)
            tree.cell_images.zoom_hide()
            tree.cell_images.zoom_in(("A", "#1"))
            win.update()
            label = tree.cell_images.zoom_label
            return int(label.place_info()["x"]), int(label.place_info()["y"])

        self.assertEqual(place_at(200, 200), (200 + ZOOM_NEAR, 200 - ZOOM_NEAR - 90),
                         "常规情形：底边压着指针、往右上铺开")
        self.assertEqual(place_at(20, 20), (20 + ZOOM_NEAR, 20 + ZOOM_NEAR),
                         "上头装不下就压到指针下头")
        self.assertEqual(place_at(500, 200), (500 - ZOOM_NEAR - 120, 200 - ZOOM_NEAR - 90),
                         "右边装不下就翻到指针左边")

    def zoom_build(self):
        """一张盖着缩略图的表 ＋ 一份放大图（下面两条盯的就是放大图自己那一层）。"""
        from tkinter import ttk
        from cell_hover import CellHover, CellImages
        win = self.tk.Tk(); win.geometry("520x300+40+40"); win.deiconify()
        self.addCleanup(win.destroy)
        tree = ttk.Treeview(win, columns=("name",), show="tree headings", height=4)
        tree.pack(fill="both", expand=True)
        tree.insert("", "end", iid="A", text="", values=("甲",))
        win.update()
        big = self.tk.PhotoImage(master=win, width=120, height=90)
        seen = []
        tree.cell_hover = CellHover(tree, ("#1",), lambda row, column: seen.append((row, column)),
                                    delete=lambda row: seen.append(("del", row)))
        tree.cell_images = CellImages(tree, ("#1",), lambda row, column: (big, ""),
                                      hover=tree.cell_hover, zoom=lambda row, column: big)
        self.addCleanup(tree.cell_images.destroy)
        win.update(); tree.cell_images.refresh(); win.update()
        return win, tree, seen

    def test_the_zoom_lends_an_ear_to_its_own_leave_and_to_the_watchdog(self):
        """第 60 期第 5 条：鼠标从放大图上挪走，图就收。

        原来这张 Label 一条绑定都没有：从那一格挪到放大图上很容易（两张图只差 ZOOM_NEAR 像素），
        再挪走时那一格早就不管它了（那一眼判的是「指针压在图上，还在看」），放大图这边没人接，
        图就钉在桌面上不走——用户报的「移动鼠标离开缩略图，放大图不会消失」（三虎的聊天框
        一冒出来最容易撞上：置顶窗压在指针上，鼠标先落到放大图上）。
        """
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import time
        win, tree, _seen = self.zoom_build()
        left0, top0 = win.winfo_rootx(), win.winfo_rooty()
        tree.winfo_pointerxy = lambda: (left0 + 200, top0 + 200)
        tree.cell_images.zoom_in(("A", "#1")); win.update()
        zoom = tree.cell_images.zoom_label
        self.assertIsNotNone(zoom, "停在缩略图上就该弹张放大图")
        self.assertIn("<Leave>", zoom.bind(), "放大图自己得认「鼠标走了」")
        tree.winfo_pointerxy = lambda: (left0 + 4, top0 + 4)          # 指针挪到窗口左上角
        zoom.event_generate("<Leave>")
        deadline = time.time() + 2
        while time.time() < deadline and tree.cell_images.zoom_key is not None:
            win.update(); time.sleep(0.02)
        self.assertIsNone(tree.cell_images.zoom_key, "鼠标离开放大图：收起来")
        self.assertFalse(zoom.winfo_ismapped(), "收起来就是看不见")
        # 保险丝：<Leave> 收不到的时候靠它——指针动过了、又不在图上，这一拍就收。
        tree.winfo_pointerxy = lambda: (left0 + 200, top0 + 200)
        tree.cell_images.zoom_in(("A", "#1")); win.update()
        self.assertIsNotNone(tree.cell_images.zoom_key)
        tree.winfo_pointerxy = lambda: (left0 + 4, top0 + 4)
        tree.cell_images.zoom_watchdog()
        self.assertIsNone(tree.cell_images.zoom_key, "指针动了、不在图上：保险丝把图收掉")

    def test_the_menu_on_the_zoom_points_at_the_cell_it_came_from(self):
        """第 60 期第 3 条：放大图压在别的格子上时，右键也要能对着「来路那一格」查看。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import cell_hover
        win, tree, seen = self.zoom_build()
        left0, top0 = win.winfo_rootx(), win.winfo_rooty()
        tree.winfo_pointerxy = lambda: (left0 + 200, top0 + 200)
        tree.cell_images.zoom_in(("A", "#1")); win.update()
        zoom = tree.cell_images.zoom_label
        made = []
        original = cell_hover.popup_row_menu
        cell_hover.popup_row_menu = lambda tree_, row, column, view=None, delete=None, x=None, y=None: made.append((row, column, view, delete))
        self.addCleanup(setattr, cell_hover, "popup_row_menu", original)
        zoom.event_generate("<Button-3>", x=10, y=10, rootx=left0 + 210, rooty=top0 + 190); win.update()
        self.assertEqual([(row, column) for row, column, _view, _delete in made], [("A", "#1")],
                         "放大图上右键：菜单认的是它的来路，不是指针底下那一格")
        made[-1][2]("A", "#1")                    # 菜单里的「查看」
        self.assertEqual(seen, [("A", "#1")], "「查看」打开的正是那一格")

    def test_a_row_without_a_picture_gets_no_label(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        win, tree, _seen = self.build(covers=())
        self.assertEqual(tree.cell_images.refresh(), set())
        self.assertEqual(tree.cell_images.labels, {})


class HoverZoomSizeTests(unittest.TestCase):
    """第 67 期任务 3：悬停放大后的图用户嫌太大——第 57 期的 960 缩回 480（正好一半）。"""

    def test_the_hover_zoom_shrank_by_half(self):
        import cell_hover
        self.assertEqual(cell_hover.ZOOM_SIZE, 480,
                         '悬停放大的长边：960 太大，用户要缩一半')

    def test_the_point_details_zoom_keeps_its_own_size(self):
        """点一下看原分辨率那一处（asset_detail）不是悬停放大，不许跟着一起缩。"""
        import asset_detail
        self.assertNotEqual(asset_detail.ZOOM_SIZE, 480, '那一处按原分辨率显示，与悬停放大无关')
        self.assertGreater(asset_detail.ZOOM_SIZE, 480)
