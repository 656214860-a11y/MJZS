# -*- coding: utf-8 -*-
"""第 47 期第 1 条：各页内容框的「选中」统一口径（勾选优先，高亮兜底）。

用户报的是「高亮显示和未勾选状态下的删除逻辑冲突」：点了一行看着像是选中的，批量删除
却回一句「请先勾选」。统一之后的规矩：

* 制作／删除这一类动作：勾选优先；一个都没勾时，把高亮那一行当作选中的那一个；
* 查看／定位这一类动作：高亮优先；没高亮时退回第一个勾选行；
* 各页按钮的可用状态与对应动作同一个口径（免得「按钮是灰的，点下去其实也能做」的错配）。

这里既有口径本身的用例，也有白模页／首帧页／剧本准备页三张真表上的行为用例；
白模页顺带盯住第 47 期第 5 条（制作进度那一栏已经撤掉）。

运行：python test_row_targets.py
"""
from skip_reasons import (
    MISSING_NODE,
    PLATFORM_DIRECTORY_LINK,
    PLATFORM_TKINTER,
    PLATFORM_TK_DISPLAY,
    PLATFORM_WORKING_SET,
    REQUIRES_BUNDLED_SKILL,
)
import json, os, sys, tempfile, time, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, PROGRAM); os.chdir(PROGRAM)

from infra.pet_state import PAGE_OF

FFMPEG = r"D:/Tools/ffmpeg/bin/ffmpeg.exe"
FFPROBE = r"D:/Tools/ffmpeg/bin/ffprobe.exe"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8


def shot(sid):
    return {"id": sid, "title": "镜头" + sid[-3:], "duration": 5, "characters": ["CHAR_001"],
            "location": "LOC_001", "frame": "frames/" + sid + ".png", "video_prompt": "画面",
            "frame_prompt": "窗边的猫", "dialogue": []}


def fresh(project, slack=900):
    """把项目里 JSON 的 mtime 顶到将来：storyboard_storage.normalize 只整理 3 秒以上的旧文件。"""
    stamp = time.time() + slack
    for path in Path(project).rglob("*.json"):
        os.utime(path, (stamp, stamp))


def make_project(td, ids=("SH001", "SH002"), frames=False):
    """最小项目：episode 里几镜（可选把首帧文件摆好）＋ 一份已采用的分镜 JSON。"""
    proj = Path(td) / "p"
    (proj / "episode" / "frames").mkdir(parents=True)
    (proj / "episode" / "assets.json").write_text("{}", encoding="utf-8")
    episode = {"episode_id": "EP001", "title": "T", "shots": [shot(sid) for sid in ids]}
    (proj / "episode" / "episode.json").write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")
    (proj / "config.json").write_text(json.dumps({
        "episode_dir": str(proj / "episode"), "episode_file": str(proj / "episode" / "episode.json"),
        "budget_seconds": 0, "reserve_seconds": 0, "live_enabled": False,
        "ffmpeg": FFMPEG, "ffprobe": FFPROBE}), encoding="utf-8")
    if frames:
        # 首帧存在 <项目>/storyboard/frames：storyboard_paths.media_root 对「分镜拆分」下的 JSON
        # 返回 <项目>/storyboard，首帧就落在它下面的 frames。
        (proj / "storyboard" / "frames").mkdir(parents=True, exist_ok=True)
        for sid in ids:
            (proj / "storyboard" / "frames" / (sid + ".png")).write_bytes(PNG)
    folder = proj / "storyboard" / "分镜拆分"; folder.mkdir(parents=True, exist_ok=True)
    adopted = "storyboard/分镜拆分/episode.json"
    (folder / "episode.json").write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")
    (proj / "ui_settings.json").write_text(json.dumps(
        {"adopted_storyboards": [adopted], "frame_json": adopted}, ensure_ascii=False), encoding="utf-8")
    fresh(proj)
    return proj


class FakeTree:
    """内容框的最小替身：行、勾选、高亮。"""

    def __init__(self, rows, checked=(), shown=None):
        self.rows = list(rows); self.checked = set(checked); self.shown = shown

    def get_children(self):
        return tuple(self.rows)

    def selection(self):
        return (self.shown,) if self.shown else ()

    def focus(self, row=None):
        return self.shown or ""

    def exists(self, row):
        return row in self.rows


class ThinTree:
    """只实现「有没有高亮」的替身（自检里真有这种只答几个查询的假表）。"""

    def __init__(self, shown=None):
        self.shown = shown

    def selection(self):
        return (self.shown,) if self.shown else ()


class RuleTests(unittest.TestCase):
    """口径本身：responsive_ui 那一组函数。"""

    def setUp(self):
        import responsive_ui
        self.ui = responsive_ui

    @staticmethod
    def is_checked(tree):
        return lambda row: row in tree.checked

    def test_checked_rows_follow_the_table_order(self):
        tree = FakeTree(["A", "B", "C"], checked=("C", "A"))
        self.assertEqual(self.ui.checked_rows(tree, self.is_checked(tree)), ["A", "C"])

    def test_work_rows_prefers_the_checked_rows(self):
        tree = FakeTree(["A", "B", "C"], checked=("B",), shown="C")
        self.assertEqual(self.ui.work_rows(tree, self.is_checked(tree)), (["B"], "checked"))

    def test_work_rows_falls_back_to_the_highlighted_row(self):
        tree = FakeTree(["A", "B"], shown="B")
        self.assertEqual(self.ui.work_rows(tree, self.is_checked(tree)), (["B"], "shown"))

    def test_work_rows_is_empty_when_nothing_is_picked(self):
        tree = FakeTree(["A", "B"])
        self.assertEqual(self.ui.work_rows(tree, self.is_checked(tree)), ([], ""))

    def test_work_hint_only_speaks_for_the_highlighted_row(self):
        hint = self.ui.work_hint(["B"], "shown")
        self.assertIn("B", hint)
        self.assertIn("高亮", hint)
        self.assertEqual(self.ui.work_hint(["B"], "checked"), "")
        self.assertEqual(self.ui.work_hint([], "shown"), "")

    def test_view_row_prefers_the_highlight_then_the_first_check(self):
        tree = FakeTree(["A", "B"], checked=("A",), shown="B")
        self.assertEqual(self.ui.view_row(tree, self.is_checked(tree)), "B")
        tree.shown = None
        self.assertEqual(self.ui.view_row(tree, self.is_checked(tree)), "A")
        tree.checked = set()
        self.assertEqual(self.ui.view_row(tree, self.is_checked(tree)), "")

    def test_a_thin_table_does_not_blow_up(self):
        thin = ThinTree(shown="B")
        self.assertEqual(self.ui.shown_row(thin), "B")
        self.assertEqual(self.ui.work_rows(thin, lambda row: True), (["B"], "shown"))
        self.assertEqual(self.ui.checked_rows(thin, lambda row: True), [])
        self.assertEqual(self.ui.view_row(ThinTree(), lambda row: True), "")
        self.assertEqual(self.ui.work_rows(thin, lambda row: True)[1], "shown")


class VideoPageTargetTests(unittest.TestCase):
    """视频页（app.py）：模块级的 work_targets 就是那一页的统一口径。"""

    @staticmethod
    def stub(shots, checks, shown=None):
        import app as app_module
        class Tree:
            def selection(self):
                return (shown,) if shown else ()
            def exists(self, row):
                return True
        subject = type("Stub", (), {})()
        subject.tree = Tree()
        subject.edit_checks = dict(checks)
        subject.studio = type("Studio", (), {"episode": {"shots": list(shots)}})()
        return app_module, subject

    def test_checks_win_over_the_highlight(self):
        app_module, subject = self.stub([{"id": "SH001"}, {"id": "SH002"}], {"SH002": True}, shown="SH001")
        self.assertEqual(app_module.work_targets(subject), (["SH002"], "checked"))

    def test_the_highlighted_row_counts_when_nothing_is_checked(self):
        app_module, subject = self.stub([{"id": "SH001"}, {"id": "SH002"}], {}, shown="SH002")
        self.assertEqual(app_module.work_targets(subject), (["SH002"], "shown"))

    def test_an_already_deleted_shot_is_never_a_target(self):
        app_module, subject = self.stub([{"id": "SH001", "video_deleted": True}], {}, shown="SH001")
        self.assertEqual(app_module.work_targets(subject), ([], ""))

    def test_nothing_picked_at_all(self):
        app_module, subject = self.stub([{"id": "SH001"}], {})
        self.assertEqual(app_module.work_targets(subject), ([], ""))

    def test_the_hint_matches_the_fallback(self):
        import app as app_module
        self.assertIn("SH002", app_module.work_hint(["SH002"], "shown"))
        self.assertEqual(app_module.work_hint(["SH002"], "checked"), "")


class PageHelpers(unittest.TestCase):
    """真页面用例共用的东西：建页、找控件、等那 750 毫秒一次的刷新。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            from tkinter import ttk
            cls.tk, cls.ttk = tk, ttk
        except Exception:
            cls.tk = None

    def setUp(self):
        # 第 47 期第 3 条那颗「先去挑模型」的提醒框：自检里一律答「先不配」，不弹真窗。
        import stage_models
        self.asks = []
        stage_models.ASKER = lambda *a, **k: (self.asks.append(a[0] if a else ""), False)[1]
        self.addCleanup(setattr, stage_models, "ASKER", None)

    def page(self, td, frames=False):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import tkinter as tk
        import desktop as desktop_module
        from desktop import Desktop
        from local_video import open_studio
        proj = make_project(td, frames=frames)
        # 关掉「自动打开上次那个项目」：桌面开局的定时器会去认上次的项目，把这一页换成别人的表。
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        win = tk.Tk(); win.withdraw()
        self.addCleanup(win.destroy)
        d = Desktop(win, root=PROGRAM)
        d.root = proj; d.studio = open_studio(proj)
        return d, win, proj

    def show(self, d, win, index):
        """翻到这一页：Desktop 开局的定时器会把页面翻回第 01 页，所以翻两遍——第二遍是最终的。"""
        from catalog_page_test_support import show_catalog_page_ready
        def show_page():
            if index == PAGE_OF['storyboard']:
                show_catalog_page_ready(d, index)
            else:
                d.show(index)
        show_page(); win.update_idletasks()
        win.update()
        show_page(); win.update_idletasks()

    def widgets(self, widget, kinds):
        found = []
        def walk(w):
            if isinstance(w, kinds):
                found.append(w)
            for child in w.winfo_children():
                walk(child)
        walk(widget)
        return found

    def buttons(self, widget):
        found = {}
        for button in self.widgets(widget, (self.ttk.Button, self.tk.Button)):
            found.setdefault(str(button.cget("text")), button)
        return found

    def tables(self, widget):
        return self.widgets(widget, (self.ttk.Treeview,))

    @staticmethod
    def state_of(button):
        """灰不灰：先问 ttk 的 instate，经典 tk.Button 没有它，退回读 state 配置项。"""
        if button is None:
            return "missing"
        try:
            return "disabled" if button.instate(["disabled"]) else "normal"
        except Exception:
            pass
        try:
            return "disabled" if str(button.cget("state")) == "disabled" else "normal"
        except Exception:
            return "missing"

    def button_state(self, desktop, text):
        """这一页那一颗按钮现在的状态（每次现找：页面可能被翻页重建过）。"""
        button = self.buttons(desktop.content).get(text)
        return self.state_of(button) if button is not None else "missing"

    def wait_for(self, win, predicate, deadline=4.0):
        """等那 750 毫秒一次的页面刷新把按钮状态改过来（只在这个期限里转事件循环）。"""
        end = time.time() + deadline
        while time.time() < end:
            win.update(); time.sleep(0.02)
            if predicate():
                return True
        return bool(predicate())


class PrevisPageTests(PageHelpers):
    """白模预演页：高亮那一行也算选中；「制作进度」那一栏已经撤掉。"""

    def test_the_progress_column_is_gone_and_the_highlight_counts(self):
        import previs_routing
        with tempfile.TemporaryDirectory() as td:
            seen = []
            original = previs_routing.dispatch
            # 要在 show() 以前换掉：页面 show 的那一下就把这个名字绑进闭包了。
            previs_routing.dispatch = lambda project, source, ids, state, monitor=False, start_complex=None, *, publish: (
                seen.append((list(ids), monitor)) or {"medium": []})
            self.addCleanup(setattr, previs_routing, "dispatch", original)
            d, win, proj = self.page(td)
            self.show(d, win, PAGE_OF['previs'])
            tree = self.tables(d.content)[0]
            self.assertNotIn("progress", tree["columns"], "第 47 期第 5 条：制作进度那一栏撤掉了")
            self.assertIn("status", tree["columns"])
            state = d.previs_jobs
            state["selected"].clear()                  # 用户取消了默认勾选
            self.assertTrue(self.wait_for(win, lambda: self.button_state(d, "手动制作白模") == "disabled"),
                            "没勾选、也没高亮时这颗按钮是灰的")
            tree = self.tables(d.content)[0]
            tree.selection_set("SH001"); tree.focus("SH001")
            self.assertTrue(self.wait_for(win, lambda: self.button_state(d, "手动制作白模") == "normal"),
                            "第 47 期第 1 条：高亮那一行也算选中")
            self.buttons(d.content)["手动制作白模"].invoke(); win.update()
            self.assertEqual(seen, [(["SH001"], True)], "派发的就是高亮那一行（照样开监视页）")
            self.assertIn(str(proj) + "|SH001", state["selected"], "按高亮算的那一行顺手补上了勾选")
            self.assertEqual(len(self.asks), 1, "点这颗按钮先问过一句「模型配了吗」")


class KeyframePageTests(PageHelpers):
    """首帧页：「批量删除首帧」按统一口径亮起来，点下去删的就是高亮那一行。"""

    def test_the_batch_delete_button_takes_the_highlighted_row(self):
        import desktop as desktop_module
        with tempfile.TemporaryDirectory() as td:
            d, win, proj = self.page(td, frames=True)
            self.show(d, win, PAGE_OF['keyframe'])
            table = [t for t in self.tables(d.content) if "prompt" in t["columns"]][0]
            source = d.current_frame_json()
            checker = d.frame_checks[str(Path(source).resolve())]
            self.assertEqual(checker.checked(["SH001", "SH002"]), [], "首帧已就位的镜头默认不勾选")
            table.selection_set("SH001"); table.focus("SH001"); win.update()
            from tk_test_support import stage_context_menu
            x, y, width, height = table.bbox("SH001", "#1")
            menu = stage_context_menu(table, x=x + width // 2, y=y + height // 2)
            self.assertEqual(str(menu.entrycget("批量删除首帧", "state")), "normal")
            asked = []
            original = desktop_module.confirm
            desktop_module.confirm = lambda _parent, _title, message, **_kw: (asked.append(message), True)[1]
            self.addCleanup(setattr, desktop_module, "confirm", original)
            menu.invoke("批量删除首帧"); win.update()
            self.assertIn("按高亮的那一行 SH001 算", asked[0])
            recycle = Path(proj) / "storyboard" / "工作流任务" / "回收站"
            moved = [p.relative_to(recycle).as_posix() for p in recycle.rglob("*") if p.is_file()]
            self.assertTrue(any(name.endswith("/SH001.png") for name in moved),
                            "删的是高亮那一镜：" + repr(moved))
            self.assertFalse(any(name.endswith("/SH002.png") for name in moved))


class StoryboardPageTests(PageHelpers):
    """初步分镜页（第 03 步）：单编辑器自动打开已采用分镜，右键可取消采用／重新采用。"""

    def test_the_highlighted_file_counts_as_selected(self):
        import desktop as desktop_module
        with tempfile.TemporaryDirectory() as td:
            d, win, proj = self.page(td)
            errors = []
            original_error = desktop_module.messagebox.showerror
            desktop_module.messagebox.showerror = lambda *a, **k: errors.append(a)
            self.addCleanup(setattr, desktop_module.messagebox, "showerror", original_error)
            self.show(d, win, PAGE_OF['storyboard'])
            page = d.storyboard_editor_page
            expected = (Path(proj) / "storyboard" / "分镜拆分" / "episode.json").resolve()
            self.assertEqual(page.active_path, expected, "03 页单编辑器默认加载已采用的分镜 JSON")
            self.assertEqual(page.active_board_json, expected)
            self.assertEqual(self.tables(d.content), [], "03 页不再保留结构剧本／分镜初稿双表")
            d.safe(page.remove_selected); win.update()
            self.assertEqual(errors, [], "当前编辑的分镜可直接取消采用，不报错")
            self.assertIn("已取消所选分镜的采用", d.status.get())


if __name__ == "__main__":
    unittest.main(verbosity=2)
