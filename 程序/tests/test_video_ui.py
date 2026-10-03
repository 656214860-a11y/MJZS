# -*- coding: utf-8 -*-
"""视频页切换镜头时的提示词自动保存回归。运行：python test_video_ui.py"""
from skip_reasons import (
    MISSING_NODE,
    PLATFORM_DIRECTORY_LINK,
    PLATFORM_TKINTER,
    PLATFORM_TK_DISPLAY,
    PLATFORM_WORKING_SET,
    REQUIRES_BUNDLED_SKILL,
)
import json, os, sys, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace

from pet_state import PAGE_OF as PAGE

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, PROGRAM)
os.chdir(PROGRAM)

FFMPEG = r"D:/Tools/ffmpeg/bin/ffmpeg.exe"
FFPROBE = r"D:/Tools/ffmpeg/bin/ffprobe.exe"


def make_project(td):
    proj = Path(td) / "p"
    (proj / "episode" / "frames").mkdir(parents=True)
    (proj / "episode" / "assets.json").write_text("{}", encoding="utf-8")
    shots = [
        {"id": "SH001", "title": "一", "duration": 5, "characters": ["CHAR_001"], "location": "LOC_001",
         "frame": "frames/SH001.png", "video_prompt": "旧提示词一", "dialogue": []},
        {"id": "SH002", "title": "二", "duration": 5, "characters": ["CHAR_001"], "location": "LOC_001",
         "frame": "frames/SH002.png", "video_prompt": "旧提示词二", "dialogue": []},
    ]
    (proj / "episode" / "episode.json").write_text(
        json.dumps({"episode_id": "EP001", "title": "T", "shots": shots}, ensure_ascii=False), encoding="utf-8")
    (proj / "config.json").write_text(json.dumps({
        "episode_dir": str(proj / "episode"), "episode_file": str(proj / "episode" / "episode.json"),
        "budget_seconds": 100, "reserve_seconds": 0, "live_enabled": False,
        "ffmpeg": FFMPEG, "ffprobe": FFPROBE}), encoding="utf-8")
    return proj


class FlushPromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            from app import App
            cls.tk, cls.App = tk, App
        except Exception:
            cls.tk = None

    def make_app(self, td):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        proj = make_project(td)
        win = self.tk.Tk(); win.withdraw()
        from ui_theme import apply as _apply
        _apply(win)
        app = self.App(win, str(proj))
        win.update_idletasks()
        self.addCleanup(win.destroy)
        return app, proj

    def prompt_of(self, proj, sid):
        from agent.core import read
        ep = read(proj / "episode" / "episode.json")
        return next(s["video_prompt"] for s in ep["shots"] if s["id"] == sid)

    def test_saves_editing_shot_prompt_on_switch(self):
        with tempfile.TemporaryDirectory() as td:
            app, proj = self.make_app(td)
            app.editing_sid = "SH001"
            app.prompt.delete("1.0", "end"); app.prompt.insert("1.0", "新提示词一")
            app.flush_prompt("SH002")
            self.assertEqual(self.prompt_of(proj, "SH001"), "新提示词一")
            self.assertEqual(self.prompt_of(proj, "SH002"), "旧提示词二")

    def test_skips_empty_prompt(self):
        with tempfile.TemporaryDirectory() as td:
            app, proj = self.make_app(td)
            app.editing_sid = "SH001"
            app.prompt.delete("1.0", "end")
            app.flush_prompt("SH002")
            self.assertEqual(self.prompt_of(proj, "SH001"), "旧提示词一")

    def test_skips_unchanged_prompt(self):
        with tempfile.TemporaryDirectory() as td:
            app, proj = self.make_app(td)
            app.editing_sid = "SH001"
            app.prompt.delete("1.0", "end"); app.prompt.insert("1.0", "旧提示词一")
            app.flush_prompt("SH002")
            self.assertEqual(self.prompt_of(proj, "SH001"), "旧提示词一")
            # 未变化时不应产生新的提示词文件
            folder = proj / "episode" / "video_prompts"
            self.assertFalse((folder / "SH001.json").exists())

    def test_skips_when_busy(self):
        with tempfile.TemporaryDirectory() as td:
            app, proj = self.make_app(td)
            app.editing_sid = "SH001"
            app.busy = True
            app.prompt.delete("1.0", "end"); app.prompt.insert("1.0", "新提示词一")
            app.flush_prompt("SH002")
            self.assertEqual(self.prompt_of(proj, "SH001"), "旧提示词一")

    def test_overlong_not_saved(self):
        with tempfile.TemporaryDirectory() as td:
            app, proj = self.make_app(td)
            app.editing_sid = "SH001"
            app.prompt.delete("1.0", "end"); app.prompt.insert("1.0", "字" * 1501)
            app.flush_prompt("SH002")
            self.assertEqual(self.prompt_of(proj, "SH001"), "旧提示词一")


class ActionButtonStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            from app import App
            cls.tk, cls.App = tk, App
        except Exception:
            cls.tk = None

    def make_app(self, td):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        proj = make_project(td)
        win = self.tk.Tk(); win.withdraw()
        from ui_theme import apply as _apply
        _apply(win)
        app = self.App(win, str(proj))
        win.update_idletasks()
        self.addCleanup(win.destroy)
        return app, proj

    def state(self, button):
        return "disabled" if button.instate(["disabled"]) else "normal"

    def test_progress_text_skips_identical_rewrites(self):
        """进度栏文字没变就不再写一次：带 wraplength 的标签每写一次都要重新折行排版。"""
        import tkinter
        from responsive_ui import QuietVar
        with tempfile.TemporaryDirectory() as td:
            app, _ = self.make_app(td)
            self.assertIsInstance(app.progress_text, QuietVar)
            writes = []
            original = tkinter.Variable.set
            def counting(self, value=None):
                writes.append(value)
                return original(self, value)
            tkinter.Variable.set = counting
            self.addCleanup(setattr, tkinter.Variable, "set", original)
            for text in ("同一句话", "同一句话", "换一句", "换一句"):
                app.progress_text.set(text)
            # 四次写只落两次：重复的同一句话不再触发折行排版
            self.assertEqual(writes, ["同一句话", "换一句"])
            self.assertEqual(app.progress_text.get(), "换一句")

    def test_actions_gated_by_selection_and_checks(self):
        """第 47 期第 1 条：统一「选中」口径——勾选优先，一个都没勾时高亮那一行也算选中。

        所以「批量生成勾选镜头」「删除勾选镜头」跟「手动制作视频」一样，只要内容框里
        有一行是高亮的就亮着（点了就按那一行做）；一行都不高亮也没勾选时才是灰的。
        """
        with tempfile.TemporaryDirectory() as td:
            app, _ = self.make_app(td)
            app.update_prompt_controls()
            self.assertTrue(app.tree.selection(), "进页面时内容框已经高亮了一行")
            self.assertEqual(self.state(app.generate_button), "normal")
            self.assertEqual(self.state(app.generate_checked_button), "normal")
            self.assertEqual(self.state(app.delete_checked_button), "normal")
            self.assertEqual(self.state(app.play_button), "disabled")
            # 第 39 期第 2 条：「批量通过勾选」连按钮带处理函数一起删了。
            self.assertFalse(hasattr(app, "review_checked_button"))
            # 一行都不高亮、也没勾选 → 两颗批量按钮一起灰掉
            app.tree.selection_remove(*app.tree.selection())
            app.update_prompt_controls()
            self.assertEqual(self.state(app.generate_checked_button), "disabled")
            self.assertEqual(self.state(app.delete_checked_button), "disabled")
            app.edit_checks["SH001"] = True
            app.update_prompt_controls()
            self.assertEqual(self.state(app.generate_checked_button), "normal")

    def test_auto_review_switch_is_not_rendered_by_the_page(self):
        """自动验收由三虎写入变量；视频页面不再保留独立勾选框。"""
        with tempfile.TemporaryDirectory() as td:
            app, proj = self.make_app(td)
            from tkinter import ttk
            boxes = []
            def walk(widget):
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Checkbutton) and str(child.cget("text")) == "自动验收":
                        boxes.append(child)
                    walk(child)
            walk(app.window)
            self.assertEqual(boxes, [])

    def test_busy_disables_actions(self):
        with tempfile.TemporaryDirectory() as td:
            app, _ = self.make_app(td)
            app.edit_checks["SH001"] = True
            app.busy = True
            app.update_prompt_controls()
            self.assertEqual(self.state(app.generate_button), "disabled")
            self.assertEqual(self.state(app.generate_checked_button), "disabled")



class AutoSubmitTests(unittest.TestCase):
    """无人值守自动提交：开启后不再逐次弹确认框，但绝不超出剩余预算；关闭时仍弹窗询问。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            from app import App
            cls.tk, cls.App = tk, App
        except Exception:
            cls.tk = None

    def make_app(self, td, auto=False):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        proj = make_project(td)
        # 自动提交只对云端后端生效（本地 ComfyUI 不弹确认框），所以这里先切成联网＋万相。
        cfg = json.loads((proj / "config.json").read_text(encoding="utf-8"))
        cfg.update(live_enabled=True, video_backend="wan", cloud_provider="wan")
        (proj / "config.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        win = self.tk.Tk(); win.withdraw()
        from ui_theme import apply as _apply
        _apply(win)
        app = self.App(win, str(proj))
        win.update_idletasks()
        self.addCleanup(win.destroy)
        import app as app_module
        # 页面只读自动状态；三虎是唯一写入方。测试在边界上提供它的只读判定。
        app.pet = SimpleNamespace(should_auto_run=lambda stage: auto and stage == "auto_submit")
        self.dialogs = []
        real = app_module.ask_confirmation
        app_module.ask_confirmation = lambda *a, **k: (self.dialogs.append(a[1]), False)[1]
        self.addCleanup(setattr, app_module, "ask_confirmation", real)
        return app, proj

    def test_skips_confirmation_within_budget(self):
        with tempfile.TemporaryDirectory() as td:
            app, proj = self.make_app(td, auto=True)
            self.assertTrue(app.confirm_submit("提交预览", "文案", 5))
            self.assertEqual(self.dialogs, [])
            self.assertIn("无人值守自动提交", app.log.get("1.0", "end"))

    def test_refuses_to_exceed_budget_without_dialog(self):
        with tempfile.TemporaryDirectory() as td:
            app, proj = self.make_app(td, auto=True)
            with self.assertRaises(ValueError) as ctx:
                app.confirm_submit("批量提交预览", "文案", 500)
            self.assertIn("超过可用预算", str(ctx.exception))
            self.assertEqual(self.dialogs, [])          # 超预算不弹窗、不提交，直接报错

    def test_off_still_asks(self):
        with tempfile.TemporaryDirectory() as td:
            app, proj = self.make_app(td, auto=False)
            self.assertFalse(app.confirm_submit("提交预览", "文案", 5))
            self.assertEqual(self.dialogs, ["提交预览"])

    def test_batch_generate_submits_without_dialog(self):
        with tempfile.TemporaryDirectory() as td:
            app, proj = self.make_app(td, auto=True)
            app.edit_checks = {"SH001": True, "SH002": True}
            submitted, results = [], []
            app.studio.submit = lambda sid, **kw: (submitted.append(sid), "已提交 " + sid)[1]
            app.run = lambda fn, **kw: results.append(fn())
            app.generate_checked()
            self.assertEqual(self.dialogs, [])
            self.assertEqual(submitted, ["SH001", "SH002"])
            self.assertIn("批量提交结束", results[0])

    def test_scan_submits_unsubmitted_shot_with_ready_frame(self):
        with tempfile.TemporaryDirectory() as td:
            app, proj = self.make_app(td, auto=True)
            submitted = []
            app.studio.submit = lambda sid, **kw: (submitted.append(sid), "已提交 " + sid)[1]
            app.run = lambda fn, **kw: fn()
            app.auto_submit_scan()
            self.assertEqual(submitted, [])                      # 首帧还没就绪：不提交
            (proj / "episode" / "frames" / "SH001.png").write_bytes(b"png")
            app.auto_submit_scan()
            self.assertEqual(submitted, ["SH001"])
            self.assertIn("无人值守自动提交：SH001", app.log.get("1.0", "end"))
            app.auto_submit_scan()
            self.assertEqual(submitted, ["SH001"])               # 同一镜头一轮只自动提交一次

    def test_scan_stops_at_budget(self):
        with tempfile.TemporaryDirectory() as td:
            app, proj = self.make_app(td, auto=True)
            (proj / "episode" / "frames" / "SH001.png").write_bytes(b"png")
            app.studio.cfg["budget_seconds"] = 1
            submitted = []
            app.run = lambda fn, **kw: submitted.append(fn)
            app.auto_submit_scan()
            self.assertEqual(submitted, [])
            self.assertIn("超过剩余预算", app.log.get("1.0", "end"))

    def test_scan_does_nothing_when_switch_off(self):
        with tempfile.TemporaryDirectory() as td:
            app, proj = self.make_app(td, auto=False)
            (proj / "episode" / "frames" / "SH001.png").write_bytes(b"png")
            submitted = []
            app.run = lambda fn, **kw: submitted.append(fn)
            app.auto_submit_scan()
            self.assertEqual(submitted, [])

    def test_page_does_not_render_or_write_auto_submit_switch(self):
        with tempfile.TemporaryDirectory() as td:
            app, proj = self.make_app(td)
            from tkinter import ttk
            boxes = []
            def walk(widget):
                for child in widget.winfo_children():
                    # 第 35 期第 5 条：勾选框改名「自动提交（不超预算）」，并从行尾挪到「阶段配置」右边。
                    if isinstance(child, ttk.Checkbutton) and str(child.cget("text")) == "自动提交（不超预算）":
                        boxes.append(child)
                    walk(child)
            walk(app.window)
            self.assertEqual(boxes, [])


def make_adopted(proj):
    """在测试项目里放一份「已采用」的分镜，并把首帧目录建好（07 步的落地页要数这两样）。"""
    sb = proj / "storyboard" / "分镜拆分"; sb.mkdir(parents=True, exist_ok=True)
    episode = json.loads((proj / "episode" / "episode.json").read_text(encoding="utf-8"))
    target = sb / "episode.json"
    target.write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")
    (proj / "ui_settings.json").write_text(json.dumps({
        "adopted_storyboards": ["storyboard/分镜拆分/episode.json"],
        "frame_json": "storyboard/分镜拆分/episode.json"}, ensure_ascii=False), encoding="utf-8")
    return target


def widget_texts(widget, kinds):
    """递归收集某几类控件的 text（顺序即打包顺序）。"""
    found = []
    for child in widget.winfo_children():
        if isinstance(child, kinds):
            found.append(str(child.cget("text")))
        found.extend(widget_texts(child, kinds))
    return found


class AssetCheckTableTests(unittest.TestCase):
    """第 30 期第 2／5 条：镜头资产栏改名并做成带勾选框的表格。

    第 33 期第 1 条：那四个字不再单独占一行，改成表头第一列。
    第 41 期第 1 条：整栏并进上方的镜头内容框（「内容」右边那一栏），一格一镜、点一下弹出
    可勾选的下拉框——原来单摆的那张表只跟「正在编辑的那一镜」走，全选镜头号之后整栏还是
    只有一镜的资产亮着（用户报的那条 BUG）。
    """

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            from tkinter import ttk
            from app import App
            cls.tk, cls.ttk, cls.App = tk, ttk, App
        except Exception:
            cls.tk = None

    def make_app(self, td, cloud=True, select=True):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        proj = make_project(td)
        cfg = json.loads((proj / "config.json").read_text(encoding="utf-8"))
        if cloud:
            cfg.update(live_enabled=True, video_backend="wan", cloud_provider="wan")
        else:
            cfg.update(live_enabled=False, video_backend="comfy")
        (proj / "config.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        # 资产库：一个角色 ＋ 一个场景，两张图都在盘上（ready）
        base = proj / "episode"
        (base / "assets" / "characters").mkdir(parents=True, exist_ok=True)
        (base / "assets" / "scenes").mkdir(parents=True, exist_ok=True)
        (base / "assets" / "characters" / "CHAR_001.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (base / "assets" / "scenes" / "LOC_001.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (base / "assets.json").write_text(json.dumps({
            "CHAR_001": {"name": "主角", "image": "assets/characters/CHAR_001.png"},
            "LOC_001": {"name": "场景", "image": "assets/scenes/LOC_001.png"}}, ensure_ascii=False),
            encoding="utf-8")
        win = self.tk.Tk(); win.withdraw()
        from ui_theme import apply as _apply
        _apply(win)
        app = self.App(win, str(proj))
        if select:
            app.tree.selection_set("SH001")
            win.update()
            app.select()
            win.update()
        self.addCleanup(win.destroy)
        return app, proj, win

    def walk(self, widget, kind):
        """递归找出某一类控件（顺序即摆放顺序）。"""
        found = [widget] if isinstance(widget, kind) else []
        for child in widget.winfo_children():
            found.extend(self.walk(child, kind))
        return found

    def quiet_destroy(self, win):
        try:
            win.destroy()
        except Exception:
            pass

    def picker(self, app, sid="SH001"):
        """第 57 期第 5 条：点「选择资产」那一格开出来的那扇窗——交出窗体、表格、按钮与说明。"""
        from tkinter import ttk
        win = app.open_asset_picker(sid)
        win.update()
        self.addCleanup(self.quiet_destroy, win)
        table = self.walk(win, ttk.Treeview)[0]
        buttons = {str(b.cget("text")): b for b in self.walk(win, ttk.Button)}
        labels = [str(l.cget("text")) for l in self.walk(win, ttk.Label)]
        return win, table, buttons, labels

    def click_pick(self, win, table, aid):
        """在那张表的首列勾选框上单击一下（列号、区域与行号照真实布局认）。

        第 59 期第 11 条：勾选那一列从「选择」那一栏（写字符）换成各页通用的首列勾选图元。
        """
        table.identify_column = lambda x: "#0"
        table.identify_region = lambda x, y: "tree"
        table.identify_row = lambda y: aid
        table.event_generate("<Button-1>", x=5, y=5)
        win.update()

    def test_the_asset_column_lives_in_the_shot_table(self):
        """第 41 期第 1 条：「选择资产」是镜头内容框里的一栏，镜头表下面不再单摆一张表。"""
        with tempfile.TemporaryDirectory() as td:
            app, _proj, win = self.make_app(td)
            self.assertEqual(list(app.tree["columns"])[2], "assets", "「选择资产」就在「内容」右边")
            self.assertEqual(str(app.tree.heading("assets", "text")), "选择资产")
            self.assertNotIn("资产编号", widget_texts(win, (self.ttk.Label,)),
                             "原来单摆的那张表整栏并进镜头表了")

    def test_the_shot_table_names_the_shot_id_column(self):
        """第 33 期第 2 条：镜头表第二栏（勾选框之后那一栏）补上列头「镜头号」。"""
        with tempfile.TemporaryDirectory() as td:
            app, _proj, _win = self.make_app(td)
            self.assertEqual(str(app.tree.heading("id", "text")), "镜头号")
            self.assertEqual(str(app.tree["columns"][0]), "id", "「镜头号」就是第二栏那一格")

    def test_the_sound_row_is_local_generation_only(self):
        """第 33 期第 5 条：线上生成按秒计费、音轨不在这条链路上——这一栏只在本地生成留着。"""
        from local_video import LocalStudio
        with tempfile.TemporaryDirectory() as td:
            app, _proj, win = self.make_app(td, cloud=False, select=False)
            self.assertIsInstance(app.studio, LocalStudio, "本地生成这一份工作台")
            self.assertIn("生成声音 / 音轨", widget_texts(win, (self.ttk.Label,)))
        with tempfile.TemporaryDirectory() as td:
            app, _proj, win = self.make_app(td, cloud=True, select=False)
            self.assertNotIsInstance(app.studio, LocalStudio, "线上生成这一份工作台")
            self.assertNotIn("生成声音 / 音轨", widget_texts(win, (self.ttk.Label,)))

    def test_every_asset_gets_its_own_checkbox_row(self):
        """第 57 期第 5 条：那一格弹出来的窗里一个资产一行，勾选状态就是首列那个勾选框。

        第 59 期第 11 条：勾选那一列改成各页通用的那一套（首列勾选图元＋缩略图另一栏），
        这里按窗上那两张勾选图元认它勾没勾。
        """
        with tempfile.TemporaryDirectory() as td:
            app, _proj, _win = self.make_app(td)
            _picker, table, buttons, _labels = self.picker(app)
            self.assertEqual(list(table["columns"]), ["thumb", "name", "state"])
            self.assertEqual(table.get_children(), ("CHAR_001", "LOC_001"), "一个资产一行")
            self.assertEqual([str(table.set(aid, "name")) for aid in table.get_children()],
                             ["CHAR_001 主角", "LOC_001 场景"])
            on = list(app.scheduler._tick_images)[1]
            self.assertEqual([str(table.item(aid, "image")[0]) for aid in table.get_children()],
                             [str(on), str(on)], "默认全勾，状态就摆在这一列")
            self.assertTrue(table.cell_hover is not None and table.cell_images is not None,
                            "缩略图那一栏另盖一层（树只有首列摆得了图）")
            self.assertEqual(set(buttons), {"全选", "全不选", "查看图片", "关闭"})

    def test_each_shot_cell_keeps_its_own_choice(self):
        """第 41 期第 1 条：一格一镜——改一镜的勾选不会牵动别的镜头那一格。"""
        with tempfile.TemporaryDirectory() as td:
            app, _proj, _win = self.make_app(td)
            self.assertEqual(app.tree.set("SH001", "assets"), "CHAR_001、LOC_001（2/2） ▾")
            self.assertEqual(app.tree.set("SH002", "assets"), "CHAR_001、LOC_001（2/2） ▾")
            app.set_all_assets("SH001", False)
            self.assertEqual(app.tree.set("SH001", "assets"), "未选资产 ▾")
            self.assertEqual(app.tree.set("SH002", "assets"), "CHAR_001、LOC_001（2/2） ▾",
                             "别的镜头那一格照旧写它自己的勾选")

    def test_the_picker_writes_the_choice_back(self):
        """第 57 期第 5 条：在窗里取消一项，写回的就是那一镜的 upload_asset_ids。"""
        with tempfile.TemporaryDirectory() as td:
            app, proj, _win = self.make_app(td)
            picker, table, _buttons, _labels = self.picker(app)
            self.click_pick(picker, table, "LOC_001")
            from agent.core import read
            episode = read(proj / "episode" / "episode.json")
            shot = next(s for s in episode["shots"] if s["id"] == "SH001")
            self.assertEqual(shot["upload_asset_ids"], ["CHAR_001"])
            self.assertTrue(shot["upload_assets"], "还留着一个勾选的资产：上传开关照旧开着")
            off = list(app.scheduler._tick_images)[0]
            self.assertEqual(str(table.item("LOC_001", "image")[0]), str(off), "那一列跟着翻过来")
            self.assertEqual(app.tree.set("SH001", "assets"), "CHAR_001（1/2） ▾")

    def test_unclear_declared_assets_keep_the_cell_readable(self):
        """第 57 期第 5 条：清单读不出来时那一格写一句话，窗里只有一句说明、一行都没有。"""
        with tempfile.TemporaryDirectory() as td:
            app, proj, win = self.make_app(td)
            (proj / "episode" / "assets.json").unlink()
            app.refresh()
            win.update()
            self.assertEqual(app.tree.set("SH001", "assets"), "未声明资产")
            _picker, table, _buttons, labels = self.picker(app)
            self.assertEqual(table.get_children(), (), "一个资产都读不出来就不摆行")
            self.assertIn("没有声明资产", " ".join(labels))

    def test_unchecking_an_asset_is_written_back(self):
        """勾选状态照旧写进 upload_asset_ids／upload_assets（口径一个字没动）。"""
        with tempfile.TemporaryDirectory() as td:
            app, proj, _win = self.make_app(td)
            self.assertEqual(sorted(app.asset_choices), ["CHAR_001", "LOC_001"])
            app.asset_choices["LOC_001"].set(False)
            app.save_options()
            from agent.core import read
            episode = read(proj / "episode" / "episode.json")
            shot = next(s for s in episode["shots"] if s["id"] == "SH001")
            self.assertEqual(shot["upload_asset_ids"], ["CHAR_001"])
            self.assertTrue(shot["upload_assets"], "还留着一个勾选的资产：上传开关照旧开着")

    def test_unchecking_everything_turns_the_upload_off(self):
        """第 57 期第 5 条：窗里的「全不选」＝一个都没勾，上传开关跟着关上。"""
        with tempfile.TemporaryDirectory() as td:
            app, proj, _win = self.make_app(td)
            picker, table, buttons, _labels = self.picker(app)
            buttons["全不选"].invoke(); picker.update()
            from agent.core import read
            episode = read(proj / "episode" / "episode.json")
            shot = next(s for s in episode["shots"] if s["id"] == "SH001")
            self.assertEqual(shot["upload_asset_ids"], [])
            self.assertFalse(shot["upload_assets"], "一个都没勾：上传开关跟着关上")
            off = list(app.scheduler._tick_images)[0]
            self.assertEqual([str(table.item(aid, "image")[0]) for aid in table.get_children()],
                             [str(off), str(off)])
            self.assertEqual(app.tree.set("SH001", "assets"), "未选资产 ▾")

    def test_clicking_the_cell_opens_the_picker(self):
        """第 57 期第 5 条：点那一格＝开会窗；本行没勾先补勾选，已勾的不取消。"""
        with tempfile.TemporaryDirectory() as td:
            app, _proj, _win = self.make_app(td)
            opened = []
            app.open_asset_picker = lambda sid: opened.append(sid)
            app.tree.identify_row = lambda y: "SH001"
            app.tree.bbox = lambda sid, column=None: (100, 20, 227, 34)
            self.assertFalse(app.asset_cell_click(SimpleNamespace(x=90, y=30)),
                             "格子左边沿之外不归它管")
            self.assertEqual(opened, [])
            inside = SimpleNamespace(x=150, y=30)
            self.assertTrue(app.asset_cell_click(inside))
            self.assertEqual(opened, ["SH001"])
            self.assertTrue(app.edit_checks.get("SH001"), "没勾的行先补上勾选")
            self.assertTrue(app.asset_cell_click(inside))
            self.assertEqual(opened, ["SH001", "SH001"])
            self.assertTrue(app.edit_checks.get("SH001"), "已勾选的行不会被取消勾选")

    def test_a_running_shot_keeps_the_picker_read_only(self):
        """第 57 期第 5 条：镜头正在生成时勾选改不动。

        第 57 期第 2 条：原因写在窗里那行小字上——不许再弹一个模态错误框（用户看到的
        「BUG 提示」就是原来那一下 showerror），也不许把这一窗拦在原地。
        """
        from unittest.mock import patch as mock
        import app as app_module
        with tempfile.TemporaryDirectory() as td:
            app, _proj, _win = self.make_app(td)
            app.submitting_sid = "SH001"
            boxes = []
            with mock.object(app_module.messagebox, "showerror",
                             lambda *a, **k: boxes.append(a)):
                picker, table, buttons, labels = self.picker(app)
                self.assertIn("正在制作", " ".join(labels), "先把原因说明白")
                on = list(app.scheduler._tick_images)[1]
                self.click_pick(picker, table, "LOC_001")
                self.assertEqual(str(table.item("LOC_001", "image")[0]), str(on), "改不动的还是原样")
                self.assertTrue(app.asset_choices["LOC_001"].get())
                buttons["全不选"].invoke(); picker.update()
                self.assertEqual([str(table.item(aid, "image")[0]) for aid in table.get_children()],
                                 [str(on), str(on)], "整栏一个都改不动")
                from tkinter import ttk as _ttk
                self.assertIn(app_module.LOCKED_SAY, " ".join(
                    str(w.cget("text")) for w in self.walk(picker, _ttk.Label)),
                    "改不动就写在窗里那行小字上")
                self.assertEqual(boxes, [], "一个模态错误框都不许弹")


    def test_the_picker_really_shows_the_table(self):
        """第 57 期第 5 条：那一窗里真摆着那张表。

        原来漏了 `table.pack(...)`：窗里只剩上头两句说明与底下那排按钮，一行资产都看不见
        （别的用例只看 `table.get_children()`，表摆没摆进窗里它们一句话都不说）。
        判据照第 55 期那套——不看 `winfo_ismapped()`（映射归窗口管理器管），看**摆的顺序**：
        内容框归 pack 管、按钮行先按 side='bottom' 落位、内容框最后 pack。
        """
        with tempfile.TemporaryDirectory() as td:
            app, _proj, _win = self.make_app(td)
            picker, table, buttons, _labels = self.picker(app)
            from ui_widgets import DataTable
            shell = table.master
            self.assertIsInstance(shell, DataTable, "资产选择器必须使用统一 DataTable")
            self.assertEqual(str(shell.winfo_manager()), "pack", "那张表得真摆进窗里")
            self.assertGreater(int(shell.winfo_reqheight()), 0, "得请求到高度")
            self.assertEqual(str(shell.pack_info().get("fill")), "both",
                             "内容框吃掉剩下的地方")
            self.assertEqual(str(buttons["关闭"].master.pack_info().get("side")), "bottom",
                             "底下那排按钮先落位")
            self.assertIs(picker.pack_slaves()[-1], shell,
                          "内容框最后 pack：窗口再矮也是它先让步")


class FooterLayoutTests(unittest.TestCase):
    """第 39 期第 2 条：线上生成页底部的按钮按用户给的位置重排。

    两行各归各的 FlowBar（第二行整行落在主动作那一行下面），「打开剪辑成片目录」单占一行、
    摆在 SH0XX 那句状态的正上方，两颗自动勾选框在右边一列摞着。
    """

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            from tkinter import ttk
            from app import App
            cls.tk, cls.ttk, cls.App = tk, ttk, App
        except Exception:
            cls.tk = None

    def make_app(self, td, prompt_stage=None):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        proj = make_project(td)
        cfg = json.loads((proj / "config.json").read_text(encoding="utf-8"))
        cfg.update(live_enabled=True, video_backend="wan", cloud_provider="wan")
        (proj / "config.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        win = self.tk.Tk(); win.withdraw()
        from ui_theme import apply as _apply
        _apply(win)
        # 第 59 期第 7 条：提示词那一颗弹的是另一扇面板（宿主传进来），两颗都要有、各开各的。
        app = self.App(win, str(proj), stage_callback=lambda: None,
                       prompt_stage_callback=None if prompt_stage is None else prompt_stage)
        win.update_idletasks()
        self.addCleanup(win.destroy)
        return app

    def buttons(self, app, text):
        """按文字找按钮：这一页既有 ttk 的按钮，也有「阶段配置」那种 tk.Button。"""
        return [w for w in widget_list(app.window, (self.ttk.Button, self.tk.Button))
                if str(w.cget("text")) == text]

    def button(self, app, text):
        found = self.buttons(app, text)
        self.assertEqual(len(found), 1, "找「" + text + "」这一颗")
        return found[0]

    def row_texts(self, row):
        """这一行里按排版次序排出来的按钮：FlowBar 按建控件的先后摆。"""
        return [str(child.cget("text")) for child in row.winfo_children()
                if child.winfo_class() in ("TButton", "Button")]

    def test_each_manual_action_keeps_its_own_stage_config(self):
        """第 59 期第 7 条：两行各有一颗「阶段配置」，各配各的阶段。

        提示词那一步走的是另一条路（Agent 出提示词），与出视频那一步不是同一份配置：
        两颗按钮各弹各的面板，桌面端认的是视频那一颗（它才是这一页的阶段：08 视频生成）。
        """
        with tempfile.TemporaryDirectory() as td:
            opened = []
            app = self.make_app(td, prompt_stage=lambda: opened.append("prompt"))
            row = self.button(app, "手动制作提示词").master
            self.assertEqual(self.row_texts(row),
                             ["手动制作提示词", "阶段配置", "MCP 优化", "MCP 设置",
                              "保存提示词", "导入提示词", "当前提示词目录"],
                             "「阶段配置」紧挨主动作右边，其余照旧")
            video_row = self.button(app, "手动制作视频").master
            self.assertIsNot(video_row, row, "「手动制作视频」另起一行")
            self.assertEqual(self.row_texts(video_row)[:2], ["手动制作视频", "阶段配置"],
                             "视频那一颗就在它右边")
            both = self.buttons(app, "阶段配置")
            self.assertEqual(len(both), 2, "两行各一颗")
            self.assertIs(app.stage_button, [b for b in both if b.master is video_row][0],
                          "桌面端认的是视频那一颗（08 视频生成）")
            self.assertIs(app.prompt_stage_button, [b for b in both if b.master is row][0],
                          "提示词那一颗是宿主传进来的那扇面板")
            app.prompt_stage_button.invoke(); app.window.update_idletasks()
            self.assertEqual(opened, ["prompt"], "点它开的是提示词那一步的面板")

    def test_the_prompt_row_falls_back_to_the_page_stage_without_a_host_callback(self):
        """第 59 期第 7 条：宿主没给提示词面板时，那一颗照旧开本页阶段面板。"""
        with tempfile.TemporaryDirectory() as td:
            app = self.make_app(td)
            row = self.button(app, "手动制作提示词").master
            self.assertIn("阶段配置", self.row_texts(row))
            video_row = self.button(app, "手动制作视频").master
            self.assertIs(app.stage_button, [b for b in self.buttons(app, "阶段配置")
                                             if b.master is video_row][0])
            self.assertIs(app.prompt_stage_button, [b for b in self.buttons(app, "阶段配置")
                                                    if b.master is row][0])

    def test_the_main_row_keeps_the_manual_action_and_the_common_ones(self):
        with tempfile.TemporaryDirectory() as td:
            app = self.make_app(td)
            main = self.button(app, "手动制作视频").master
            self.assertEqual(self.row_texts(main),
                             ["手动制作视频", "阶段配置", "播放视频", "查看全部版本"],
                             "第一行：主动作右边是它自己的「阶段配置」，其余是常用动作")
            for moved in ("通过", "需修改", "批量生成勾选镜头", "打开素材目录", "恢复任务编号"):
                self.assertIsNot(self.button(app, moved).master, main, moved + " 不在第一行")

    def test_pass_starts_the_row_under_the_manual_action(self):
        with tempfile.TemporaryDirectory() as td:
            app = self.make_app(td)
            main = self.button(app, "手动制作视频").master
            row = self.button(app, "通过").master
            self.assertIsNot(row, main, "「通过」另起一行")
            self.assertGreater(int(row.grid_info()["row"]), int(main.grid_info()["row"]),
                               "那一行就在主动作这一行下面")
            self.assertEqual(self.row_texts(row),
                             ["通过", "打开素材目录", "恢复任务编号", "打开视频目录",
                              "需修改", "批量生成勾选镜头", "删除勾选镜头"],
                             "「通过」打头，其余按用户给的次序排；批量删除紧跟批量生成（第 46 期第 9 条）")
            self.assertIs(self.button(app, "批量生成勾选镜头").master, row)
            self.assertIs(self.button(app, "批量生成勾选镜头"),
                          app.generate_checked_button, "勾选后批量生成那颗还是同一个入口")

    def test_the_note_entry_follows_the_revise_button(self):
        with tempfile.TemporaryDirectory() as td:
            app = self.make_app(td)
            row = self.button(app, "需修改").master
            order = row.winfo_children()
            self.assertIs(app.note.master, row, "验收备注也挪到了这一行")
            self.assertLess(order.index(self.button(app, "需修改")), order.index(app.note),
                            "跟在「需修改」后面")
            self.assertIs(self.button(app, "批量生成勾选镜头").master, row)

    def test_the_clip_folder_button_sits_just_above_the_shot_status(self):
        with tempfile.TemporaryDirectory() as td:
            app = self.make_app(td)
            clip = self.button(app, "打开剪辑成片目录")
            status = [w for w in widget_list(app.footer, self.ttk.Label)
                      if str(w.cget("textvariable")) == str(app.progress_text)]
            self.assertEqual(len(status), 1, "SH0XX 那句状态就一条")
            band = app.footer.pack_slaves()
            self.assertLess(band.index(clip.master), band.index(status[0].master),
                            "「打开剪辑成片目录」落在 SH0XX 那句的正上方")
            self.assertEqual([str(w.cget("text")) for w in clip.master.winfo_children()],
                             ["打开剪辑成片目录"], "这一行就这一颗按钮")

    def test_the_page_has_no_auto_switches(self):
        with tempfile.TemporaryDirectory() as td:
            app = self.make_app(td)
            boxes = [w for w in widget_list(app.window, self.ttk.Checkbutton)
                     if str(w.cget("text")) in ("自动提交（不超预算）", "自动验收")]
            self.assertEqual(boxes, [])

    def test_the_two_deleted_buttons_are_gone(self):
        with tempfile.TemporaryDirectory() as td:
            app = self.make_app(td)
            texts = [str(w.cget("text"))
                     for w in widget_list(app.window, (self.ttk.Button, self.tk.Button))]
            for gone in ("批量通过勾选", "自动剪辑勾选镜头"):
                self.assertNotIn(gone, texts, "第 39 期第 2 条：这颗按钮删掉")
            self.assertFalse(hasattr(app, "review_checked_button"))
            self.assertFalse(hasattr(app, "assemble_checked"), "处理函数跟着按钮一起删")


class SharedProgressLineTests(unittest.TestCase):
    """第 38 期第 1 条：进度那一行只报本页自己那一侧。

    本地生成页原来顶着一句「线上：0 进行中 / 0 已下载」，线上页反过来——两种方式各占一份
    状态文件，另一侧的数字在这一页永远是 0，写着只是噪音。
    """

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            from app import App
            cls.tk, cls.App = tk, App
        except Exception:
            cls.tk = None

    def make_app(self, td, cloud):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        proj = make_project(td)
        cfg = json.loads((proj / "config.json").read_text(encoding="utf-8"))
        if cloud:
            cfg.update(live_enabled=True, video_backend="wan", cloud_provider="wan")
        else:
            cfg.update(live_enabled=False, video_backend="comfy")
        (proj / "config.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        win = self.tk.Tk(); win.withdraw()
        from ui_theme import apply as _apply
        _apply(win)
        app = self.App(win, str(proj))
        win.update_idletasks()
        self.addCleanup(win.destroy)
        return app

    def test_the_local_workbench_reports_local_progress_only(self):
        from local_video import LocalStudio
        with tempfile.TemporaryDirectory() as td:
            app = self.make_app(td, cloud=False)
            self.assertIsInstance(app.studio, LocalStudio, "本地生成那一份工作台")
            text = app.shared_progress.get()
            self.assertIn("本地：", text)
            self.assertNotIn("线上", text, "本地页不再写线上那一半")

    def test_the_cloud_workbench_reports_cloud_progress_only(self):
        from local_video import LocalStudio
        with tempfile.TemporaryDirectory() as td:
            app = self.make_app(td, cloud=True)
            self.assertNotIsInstance(app.studio, LocalStudio, "线上生成那一份工作台")
            text = app.shared_progress.get()
            self.assertIn("线上：", text)
            self.assertNotIn("本地", text, "线上页不再写本地那一半")


def widget_list(widget, kinds):
    found = []
    for child in widget.winfo_children():
        if isinstance(child, kinds):
            found.append(child)
        found.extend(widget_list(child, kinds))
    return found


class VideoHomeFactsTests(unittest.TestCase):
    """07 步「选择生成方式」这一页先摆出来的事实（第 26 期第 3 条）。"""

    def rows(self, proj, source=None):
        import types
        import video_navigation
        stub = types.SimpleNamespace(root=proj, current_frame_json=lambda: source)
        return dict(video_navigation.confirm_rows(stub))

    def test_rows_report_storyboards_frames_and_models(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            source = make_adopted(proj)
            frames = proj / "storyboard" / "frames"; frames.mkdir(parents=True, exist_ok=True)
            (frames / "SH001.png").write_bytes(b"PNG")
            rows = self.rows(proj, source)
            self.assertEqual(rows["分镜"], "已采用 1 份，共 2 镜")
            self.assertEqual(rows["首帧"], "当前分镜已就绪 1 / 2 镜")
            self.assertIn("MiniMax H3", rows["本地模型"])
            self.assertIn("尚未配置", rows["线上模型"])

    def test_missing_storyboards_are_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            rows = self.rows(proj, None)
            self.assertIn("尚未采用分镜", rows["分镜"])
            self.assertEqual(rows["首帧"], "当前分镜没有镜头")

    def test_a_broken_frame_pointer_still_gets_rows(self):
        """current_frame_json 抛异常时也不能白屏：这一页是进工作台之前的地图。"""
        import types
        import video_navigation
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            def boom():
                raise ValueError("还没有项目")
            stub = types.SimpleNamespace(root=proj, current_frame_json=boom)
            rows = dict(video_navigation.confirm_rows(stub))
            self.assertEqual(rows["首帧"], "当前分镜没有镜头")
            self.assertIn("分镜", rows)

    def test_local_model_follows_the_configured_workflow(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            cfg = json.loads((proj / "config.json").read_text(encoding="utf-8"))
            cfg["local_video"] = {"workflow": "workflows/h3_我的工作流.json"}
            (proj / "config.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
            rows = self.rows(proj, None)
            self.assertEqual(rows["本地模型"], "h3_我的工作流（本机 ComfyUI，免费）")

    def test_cloud_model_follows_the_saved_workspace(self):
        """偏好里记住的那个线上任务目录优先于「最近改过的那个」。"""
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            wanted = proj / "cloud_video" / "火山引擎_doubao-seedance-2-0-mini-260615_20260918_2232"
            other = proj / "cloud_video" / "阿里云_wan2.6-i2v-flash_20260918_2232"
            wanted.mkdir(parents=True); other.mkdir(parents=True)
            (wanted / "config.json").write_text(json.dumps({
                "cloud_provider": "volcengine", "base_url": "https://ark.cn-beijing.volces.com/api/v3",
                "model": "doubao-seedance-2-0-mini-260615"}, ensure_ascii=False), encoding="utf-8")
            (other / "config.json").write_text(json.dumps({
                "cloud_provider": "wan", "base_url": "https://dashscope.aliyuncs.com/api/v1",
                "model": "wan2.6-i2v-flash"}, ensure_ascii=False), encoding="utf-8")
            (proj / "ui_settings.json").write_text(json.dumps({
                "cloud_video_workspace": "cloud_video/火山引擎_doubao-seedance-2-0-mini-260615_20260918_2232"},
                ensure_ascii=False), encoding="utf-8")
            rows = self.rows(proj, None)
            self.assertEqual(rows["线上模型"], "火山引擎 · Seedance · doubao-seedance-2-0-mini-260615")


class VideoHomePageTests(unittest.TestCase):
    """07 步还没选生成方式时那扇门：不摆「选择分镜」，两个入口做成主色按钮。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def test_the_choose_page_hides_the_storyboard_picker(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            # 故意一份分镜都没采用：未选生成方式前这一页照样要开，选定方式后才回到「先采用分镜」的闸门。
            (proj / "ui_settings.json").write_text(json.dumps(
                {"adopted_storyboards": [], "frame_json": ""}, ensure_ascii=False), encoding="utf-8")
            win = self.tk.Tk(); win.geometry("1180x760+40+40")
            def quiet_destroy():
                try:
                    win.destroy()
                except Exception:
                    pass
            self.addCleanup(quiet_destroy)
            from desktop import Desktop
            from local_video import open_studio
            d = Desktop(win, root=PROGRAM)
            d.root = proj
            d.studio = open_studio(proj)      # 选定方式之后工作台要用它，这一步只验闸门
            d.show(PAGE['video']); win.update()
            labels = widget_texts(d.content, ttk.Label)
            self.assertNotIn("选择分镜", labels)
            self.assertFalse([text for text in labels if "然后按步骤" in text])
            self.assertIn("开工前先确认", widget_texts(d.content, ttk.LabelFrame))
            self.assertTrue([text for text in labels if "尚未采用分镜" in text])
            entries = [b for b in widget_list(d.content, ttk.Button)
                       if str(b.cget("text")) in ("进入本地生成", "进入线上生成")]
            self.assertEqual(len(entries), 2)
            for button in entries:
                self.assertEqual(str(button.cget("style")), "Primary.TButton")
            # 自动补视频由三虎统一控制；选择页不再渲染独立勾选框。
            self.assertFalse([box for box in widget_list(d.content, ttk.Checkbutton)
                              if "自动补视频" in str(box.cget("text"))])
            # 选定方式之后才回到「先采用分镜」那道闸门：一份都没采用时不给进工作台
            d.show(PAGE['video'], video_mode="local"); win.update()
            self.assertTrue([text for text in widget_texts(d.content, ttk.Label)
                             if "请先在第2步采用" in text])


class VideoHomeLeadTests(unittest.TestCase):
    """第 38 期第 2 条：「线上走」「API（按秒计费）」之间不许断行。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def test_the_lead_line_binds_the_cloud_phrase_together(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            win = self.tk.Tk(); win.geometry("1180x760+40+40")
            def quiet_destroy():
                try:
                    win.destroy()
                except Exception:
                    pass
            self.addCleanup(quiet_destroy)
            from desktop import Desktop
            from local_video import open_studio
            d = Desktop(win, root=PROGRAM)
            d.root = proj
            d.studio = open_studio(proj)
            d.show(PAGE['video']); win.update()
            leads = [text for text in widget_texts(d.content, ttk.Label) if "本地走" in text]
            self.assertEqual(len(leads), 1, "这一页只有一句说明两种方式的引言")
            lead = leads[0]
            self.assertIn("线上走\u00a0API（按秒计费）", lead)
            self.assertNotIn("线上走 API", lead, "普通空格正是原来断行的位置")
            self.assertEqual(lead.count(chr(10)), 1, "在句号处自己断句：两种方式各占一行")


class VideoEntryTests(unittest.TestCase):
    """第 48 期第 3 条：侧栏「视频生成」的入口逻辑——先选方式，之后记住那一侧。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def page(self, td):
        import desktop as desktop_module
        from desktop import Desktop
        from local_video import open_studio
        proj = make_project(td)
        make_adopted(proj)
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        win = self.tk.Tk(); win.geometry("1180x760+40+40")
        def quiet_destroy():
            try:
                win.destroy()
            except Exception:
                pass
        self.addCleanup(quiet_destroy)
        d = Desktop(win, root=PROGRAM)
        d.root = proj
        d.studio = open_studio(proj)
        return d, win, proj

    def click_video(self, d, win):
        """点侧栏那一颗「08  视频生成」。"""
        d.nav[PAGE['video']].invoke()
        for _ in range(3):
            win.update(); win.update_idletasks()

    def prefs(self, proj):
        path = proj / "ui_settings.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    def test_the_first_click_shows_the_choose_page(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        with tempfile.TemporaryDirectory() as td:
            d, win, proj = self.page(td)
            self.click_video(d, win)
            self.assertIsNone(d.video_mode, "第一次点：先摆「选择生成方式」")
            entries = widget_texts(d.content, ttk.Button)
            self.assertIn("进入本地生成", entries)
            self.assertIn("进入线上生成", entries)

    def test_the_next_click_goes_straight_back_to_the_chosen_side(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        with tempfile.TemporaryDirectory() as td:
            d, win, proj = self.page(td)
            self.click_video(d, win)
            d.show(PAGE['video'], video_mode="local"); win.update()          # 用户选了本地那一侧
            self.assertEqual(d.video_mode, "local")
            self.assertEqual(self.prefs(proj).get("last_video_mode"), "local", "盘上也记住了")
            self.click_video(d, win)
            self.assertEqual(d.video_mode, "local", "再点一次直接回本地那一侧")
            self.assertNotIn("进入线上生成", widget_texts(d.content, ttk.Button), "不再拦在选择页上")

    def test_the_way_back_to_the_choose_page_still_works(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        with tempfile.TemporaryDirectory() as td:
            d, win, proj = self.page(td)
            d.show(PAGE['video'], video_mode="cloud"); win.update()
            self.assertEqual(d.video_mode, "cloud")
            # 第 48 期：返回按钮是经典 tk.Button，不是 ttk，两种都要算。
            self.assertIn("返回生成方式", widget_texts(d.title_row, (self.tk.Button, ttk.Button)),
                          "想换一侧：页里那颗还是摆着")
            d.show(PAGE['video'], video_mode="choose"); win.update()
            self.assertIsNone(d.video_mode)
            self.assertIn("进入本地生成", widget_texts(d.content, ttk.Button))

    def test_a_fresh_start_still_asks_first(self):
        """上次记着「线上」也一样：新的一次启动，第一次点还是要先问选哪一侧。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            d, win, proj = self.page(td)
            prefs = self.prefs(proj)
            prefs["last_video_mode"] = "cloud"
            (proj / "ui_settings.json").write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
            self.click_video(d, win)
            self.assertIsNone(d.video_mode, "新的一次启动：第一次点先摆选择页")

    def test_manual_prompt_stage_config_opens_prompt_render_stage(self):
        """线上/本地共用工作台的提示词按钮必须配置分镜定稿，而非初步分镜。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import skill_panel
        with tempfile.TemporaryDirectory() as td:
            d, win, _proj = self.page(td)
            d.show(PAGE['video'], video_mode="local")
            for _ in range(3):
                win.update(); win.update_idletasks()
            opened = []
            original = skill_panel.show
            skill_panel.show = lambda desktop, stage, **_kwargs: opened.append((desktop, stage))
            self.addCleanup(setattr, skill_panel, 'show', original)
            d.video.prompt_stage_button.invoke()
            self.assertEqual(opened, [(d, 'final')])


class PromptBoxHeightTests(unittest.TestCase):
    """第 48 期第 4 条：线上生成的提示词框跟内容走，不再写死 7 行。

    用户的原话是「根据文字内容的多少自动调整内容框的高度，节省页面空间」，
    所以两头都要管：空框只留 3 行，写得多了自己长高。

    第 58 期第 1 条改了上限的口径：提示词框**优先把全部文字显示出来**（原来 12 行就
    封顶，1500 字的提示词得在框里自己滚）；最下面那块动态日志跟着自己的内容长高，
    但排在提示词后面：地方不够先压日志。
    """

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def page(self, td):
        import desktop as desktop_module
        from desktop import Desktop
        proj = make_project(td)
        make_adopted(proj)
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        win = self.tk.Tk(); win.geometry("1180x760+40+40")
        self.addCleanup(lambda: win.winfo_exists() and win.destroy())
        d = Desktop(win, root=PROGRAM)
        d.root = proj
        d.show(PAGE['video'], video_mode="local")
        for _ in range(3):
            win.update(); win.update_idletasks()
        return d, win

    def write(self, d, win, text):
        d.video.prompt.delete("1.0", "end")
        d.video.prompt.insert("1.0", text)
        for _ in range(3):
            win.update(); win.update_idletasks()
        return int(d.video.prompt.cget("height"))

    def taller(self, win):
        """把窗口撑高一点：日志框要长高得先有地方（主窗口默认那一档就 740 高）。"""
        win.geometry("1180x1040+20+20")
        for _ in range(3):
            win.update(); win.update_idletasks()

    def test_an_empty_box_only_keeps_the_minimum(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            d, win = self.page(td)
            self.assertEqual(int(d.video.prompt.cget("height")), 3,
                             "空提示词框只留 3 行，别再白占页面")

    def test_more_words_make_a_taller_box(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            d, win = self.page(td)
            short = self.write(d, win, "推近，主角回头")
            tall = self.write(d, win, "\n".join("镜头 %d：主角沿走廊往前走" % i for i in range(1, 9)))
            self.assertEqual(short, 3, "一句话就 3 行")
            self.assertEqual(tall, 8, "8 行字就摆 8 行高")

    def test_a_very_long_prompt_stops_at_the_backstop(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            d, win = self.page(td)
            rows = self.write(d, win, "推近，主角回头，灯光扫过脸" * 300)
            self.assertEqual(rows, d.video.PROMPT_ROWS_MAX,
                             "极长的一条才封顶（上限只是兜底）")

    def test_the_whole_prompt_shows_without_an_inner_scrollbar(self):
        """第 58 期第 1 条：提示词有多少就摆多少行，不在框里面留滚动条。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            d, win = self.page(td)
            rows = self.write(d, win, "\n".join("镜头 %d：主角沿走廊往前走" % i for i in range(1, 15)))
            self.assertEqual(rows, 14, "14 行字就摆 14 行高，用户不用在框里自己滚")

    def test_the_log_grows_with_its_content(self):
        """第 58 期第 1 条：动态日志跟着日志内容长高（地方够的时候）。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            d, win = self.page(td)
            v = d.video
            self.assertEqual(int(v.log.cget("height")), v.LOG_ROWS_MIN, "空日志只占最小那几行")
            self.taller(win)
            for i in range(30):
                v.write("日志第 %d 行" % i)
            for _ in range(3):
                win.update(); win.update_idletasks()
            self.assertGreater(int(v.log.cget("height")), v.LOG_ROWS_MIN, "日志多了，框跟着长高")
            self.assertLessEqual(int(v.log.cget("height")), v.LOG_ROWS_MAX, "再长也封顶")
            v.clear_log()
            for _ in range(3):
                win.update(); win.update_idletasks()
            self.assertEqual(int(v.log.cget("height")), v.LOG_ROWS_MIN, "清空以后缩回去")

    def test_the_log_yields_to_the_prompt(self):
        """第 58 期第 1 条：地方先给提示词；提示词一长，日志就退回最小那几行。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            d, win = self.page(td)
            v = d.video
            self.taller(win)
            for i in range(30):
                v.write("日志第 %d 行" % i)
            for _ in range(3):
                win.update(); win.update_idletasks()
            self.assertGreater(int(v.log.cget("height")), v.LOG_ROWS_MIN, "先长起来一截")
            rows = self.write(d, win, "\n".join("镜头 %d：主角沿走廊往前走" % i for i in range(1, 13)))
            self.assertEqual(rows, 12, "提示词还是摆满 12 行")
            self.assertEqual(int(v.log.cget("height")), v.LOG_ROWS_MIN, "日志让路，退回最小")

    def test_clearing_it_shrinks_back(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            d, win = self.page(td)
            self.write(d, win, "推近" * 2000)
            self.assertEqual(self.write(d, win, ""), 3, "清空以后要缩回来")

    def test_switching_shots_refits_the_box(self):
        """列表里换个镜头会把提示词整段换掉，高度也得跟着换。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        source = (Path(PROGRAM) / "app.py").read_text(encoding="utf-8")
        self.assertIn("def fit_prompt_height(self):", source)
        self.assertIn("self.prompt.bind('<<Modified>>',self.prompt_edited)", source)
        self.assertEqual(
            source.count("self.prompt.delete('1.0','end');self.prompt.insert('1.0',s['video_prompt']);"
                         "self.editing_sid=s['id'];self.fit_prompt_height()"), 1,
            "select() 换镜头以后要重算一次高度")
        self.assertNotIn("height=7", source, "写死的 7 行已经改成跟内容走了")


class PromptAgentLabelTests(unittest.TestCase):
    """第 27 期第 1 条、第 32 期第 4 条、第 54 期附件二第 3 条：视频页两颗主动作叫
    「手动制作提示词」「手动制作视频」。"""

    def test_the_button_is_named_generation_now(self):
        try:
            import tkinter as tk
            from tkinter import ttk
            from app import App
        except Exception:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            win = tk.Tk(); win.withdraw()
            from ui_theme import apply as _apply
            _apply(win)
            App(win, str(proj))
            win.update_idletasks()
            self.addCleanup(win.destroy)
            texts = widget_texts(win, (ttk.Button,))
            self.assertIn("手动制作提示词", texts)
            self.assertIn("手动制作视频", texts)
            self.assertNotIn("分镜提示词agent", texts)
            # 第 32 期第 4 条：两颗主动作用主色按钮突出
            primary = [str(b.cget("text")) for b in widget_list(win, ttk.Button)
                       if str(b.cget("style")) == "Tokens.Primary.TButton"]
            self.assertIn("手动制作提示词", primary)
            self.assertIn("手动制作视频", primary)

    def test_the_optimize_button_is_highlighted(self):
        """第 45 期：用户要「按钮 MCP 优化醒目提示」——琥珀色那一档，与手动制作提示词分得开。"""
        try:
            import tkinter as tk
            from tkinter import ttk
            from app import App
        except Exception:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            win = tk.Tk(); win.withdraw()
            from ui_theme import apply as _apply
            _apply(win)
            App(win, str(proj))
            win.update_idletasks()
            self.addCleanup(win.destroy)
            styles = {str(b.cget("text")): str(b.cget("style"))
                      for b in widget_list(win, ttk.Button)}
            self.assertEqual(styles.get("MCP 优化"), "Highlight.TButton",
                             "这一档是琥珀色，一眼看得出是要花钱的那一步")
            self.assertEqual(styles.get("手动制作提示词"), "Tokens.Primary.TButton",
                             "主色还是留给主动作，两颗不是同一档")
            self.assertIn("MCP 设置", styles, "配它用的设置入口就在旁边")


class WritingSheetExampleTests(unittest.TestCase):
    """第 45 期：剧本准备窗的创意栏里，示例默认置灰（只是提示，不是内容）。"""

    def sheet(self):
        try:
            import tkinter as tk
            from app import App
        except Exception:
            self.skipTest(PLATFORM_TKINTER)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        proj = make_project(self.tmp.name)
        win = tk.Tk()
        from ui_theme import apply as _apply
        _apply(win)
        self.addCleanup(win.destroy)
        app = App(win, str(proj))
        win.update()
        app.writing_setup()
        win.update()
        sheets = [w for w in win.winfo_children()
                  if isinstance(w, tk.Toplevel) and "剧本准备" in str(w.title())]
        self.assertEqual(len(sheets), 1, "剧本准备窗应当开出来")
        sheet = sheets[0]
        box = [w for w in sheet.winfo_children() if isinstance(w, tk.Text)][0]
        return win, sheet, box

    def walk(self, widget, kind):
        found = []
        if isinstance(widget, kind):
            found.append(widget)
        for child in widget.winfo_children():
            found.extend(self.walk(child, kind))
        return found

    def test_the_example_is_grey_and_tagged(self):
        win, sheet, box = self.sheet()
        import app as app_module
        self.assertEqual(str(box.cget("fg")), app_module.PLACEHOLDER_INK, "示例默认置灰")
        self.assertTrue(box.tag_ranges("example"), "整段示例都挂着灰标签")
        self.assertEqual(str(box.tag_cget("example", "foreground")), app_module.PLACEHOLDER_INK)

    def test_the_grey_example_is_refused_at_the_door(self):
        win, sheet, box = self.sheet()
        import app as app_module
        import writing
        from tkinter import ttk
        seen = []
        original_prepare = writing.prepare
        original_error = app_module.messagebox.showerror
        writing.prepare = lambda *args, **kwargs: seen.append("prepare")
        app_module.messagebox.showerror = lambda title, text, **kwargs: seen.append((title, text))
        self.addCleanup(setattr, writing, "prepare", original_prepare)
        self.addCleanup(setattr, app_module.messagebox, "showerror", original_error)
        button = [w for w in self.walk(sheet, ttk.Button)
                  if str(w.cget("text")).startswith("生成编剧任务书")][0]
        button.invoke()
        win.update()
        self.assertEqual(len(seen), 1, "灰色示例被拦下，没有真去准备任务书")
        self.assertEqual(seen[0][0], "无法准备")
        self.assertIn("示例", seen[0][1])

    def test_typing_away_the_example_and_an_empty_box_brings_it_back(self):
        win, sheet, box = self.sheet()
        import app as app_module
        sheet.deiconify()                 # 键盘事件发给焦点窗口，先让这一扇真显示出来
        sheet.lift()
        win.update()
        box.focus_set(); win.update()
        box.event_generate("<KeyPress>", keysym="a")
        win.update()
        self.assertNotIn("本次希望制作的故事", str(box.get("1.0", "end-1c")),
                         "示例不是真内容：一动键盘就整段让位")
        self.assertEqual(str(box.cget("fg")), "#243247", "腾出地方以后写的是正文黑字")
        box.delete("1.0", "end")
        box.event_generate("<FocusOut>")
        win.update()
        self.assertTrue(str(box.get("1.0", "end-1c")).strip(), "空栏离开焦点时把示例放回来")
        self.assertEqual(str(box.cget("fg")), app_module.PLACEHOLDER_INK)


if __name__ == "__main__":
    unittest.main(verbosity=2)
