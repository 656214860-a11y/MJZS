# -*- coding: utf-8 -*-
"""UI 边界回归：无分镜/无资产的最小项目下，11 个页面均能构建不崩溃。运行：python test_ui_edges.py"""
from skip_reasons import (
    MISSING_NODE,
    PLATFORM_DIRECTORY_LINK,
    PLATFORM_TKINTER,
    PLATFORM_TK_DISPLAY,
    PLATFORM_WORKING_SET,
    REQUIRES_BUNDLED_SKILL,
)
import inspect, json, os, re, sys, tempfile, time, unittest
from pathlib import Path

HERE = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, HERE)
os.chdir(HERE)

import idea_chat
from catalog_page_test_support import show_catalog_page_ready
from widget_test_support import widget_texts as _widget_texts

PROGRAM = HERE
FFMPEG = r"D:/Tools/ffmpeg/bin/ffmpeg.exe"
FFPROBE = r"D:/Tools/ffmpeg/bin/ffprobe.exe"

from pet_state import PAGE_OF as PAGE
from project_stages import storyboard as storyboard_stage, stage as stage_dir, editing as editing_stage, exports as export_stage


def final_storyboard_dir(project):
    """定稿属于 06 分镜定稿；03 只保留可编辑的分镜工作稿。"""
    return stage_dir(project, 'final') / '分镜'


def final_dirs(project):
    """尚未产生定稿时目录可以不存在；读取端必须把它视为零份。"""
    root = final_storyboard_dir(project)
    return [path for path in root.iterdir() if path.is_dir() and '定稿' in path.name] if root.is_dir() else []


def popup_windows(win, tk):
    """主窗口下的真弹窗：三虎的云朵框是常驻浮窗（无边框、置顶），不算弹窗。"""
    return [w for w in win.winfo_children()
            if isinstance(w, tk.Toplevel) and not getattr(w, "_drama_cloud", False)]


def widget_texts(widget):
    """递归收起一棵控件树里所有按钮的字（按页找「还有没有那颗入口」用）。"""
    return _widget_texts(widget, ("TButton", "Button"))


class StartupFirstPaintTests(unittest.TestCase):
    """启动控制器必须让 Tk 先完成首窗绘制。"""
    def test_project_choice_is_deferred_to_idle_after_startup_delay(self):
        from desktop_startup_service import DesktopStartupController

        class Window:
            def __init__(self):
                self.delayed = None
                self.callback = None
            def after(self, delay, callback):
                self.delayed = (delay, callback)
                return 'startup-delay'
            def after_idle(self, callback):
                self.callback = callback
                return 'idle-project-choice'
            def after_cancel(self, timer):
                pass

        class Status:
            value = ''
            def set(self, value):
                self.value = value

        win=Window();status=Status();chosen=[];timers=[]
        controller=DesktopStartupController(
            schedule_after=win.after, schedule_idle=win.after_idle,
            cancel_scheduled=win.after_cancel, is_stopping=lambda:False,
            before_project_choice=lambda:status.set('正在打开今日项目…'),
            choose_project=lambda:chosen.append(True),
            remember_timer=timers.append,
        )
        self.assertEqual(controller.start(),'startup-delay')
        self.assertEqual(win.delayed[0],150)
        win.delayed[1]()
        self.assertEqual(timers[-1],'idle-project-choice')
        self.assertEqual(status.value,'正在打开今日项目…')
        win.callback()
        self.assertEqual(chosen,[True])

    def test_stopping_window_skips_idle_project_choice(self):
        from desktop_startup_service import DesktopStartupController

        class Window:
            def after(self, delay, callback):
                self.callback=callback;return 'startup-delay'
            def after_idle(self, callback):
                raise AssertionError('stopping window must not schedule idle work')
            def after_cancel(self, timer):
                pass

        win=Window();controller=DesktopStartupController(
            schedule_after=win.after, schedule_idle=win.after_idle,
            cancel_scheduled=win.after_cancel, is_stopping=lambda:True,
            before_project_choice=lambda:None, choose_project=lambda:None,
            remember_timer=lambda timer:None,
        )
        controller.start();win.callback()


def make_minimal_project(td):
    proj = Path(td) / "p"
    (proj / "episode" / "frames").mkdir(parents=True)
    (proj / "episode" / "assets.json").write_text("{}", encoding="utf-8")
    (proj / "episode" / "episode.json").write_text(json.dumps({"episode_id": "EP001", "title": "T", "shots": [
        {"id": "SH001", "title": "镜头", "duration": 5, "characters": ["CHAR_001"], "location": "LOC_001",
         "frame": "frames/SH001.png", "video_prompt": "画面", "frame_prompt": "窗边的猫", "dialogue": []}]}, ensure_ascii=False), encoding="utf-8")
    (proj / "config.json").write_text(json.dumps({
        "episode_dir": str(proj / "episode"), "episode_file": str(proj / "episode" / "episode.json"),
        "budget_seconds": 0, "reserve_seconds": 0, "live_enabled": False,
        "ffmpeg": FFMPEG, "ffprobe": FFPROBE}), encoding="utf-8")
    return proj


def adopt_storyboard_fixture(proj):
    """在项目里放一份「已采用」的分镜：分镜拆分/episode.json ＋ ui_settings.json。

    顺手把这份 JSON 的 mtime 顶到将来一点 —— storyboard_storage.normalize 只整理 3 秒以上的旧文件
    （把 episode.json 收敛成 EP001_T_分镜.json）。用例建窗那一会儿一旦超过 3 秒，文件名就会在按钮
    点下去之前被悄悄换掉，断言随即读到不存在的文件：随机红，而且红的样子跟被测功能没有关系。
    """
    sb_dir = storyboard_stage(proj) / "分镜文档"; sb_dir.mkdir(parents=True, exist_ok=True)
    episode = json.loads((proj / "episode" / "episode.json").read_text(encoding="utf-8"))
    target = sb_dir / "episode.json"
    target.write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")
    canonical = target.relative_to(proj).as_posix()
    (proj / "ui_settings.json").write_text(json.dumps({"adopted_storyboards": [canonical], "frame_json": canonical}, ensure_ascii=False), encoding="utf-8")
    keep_storyboard_fresh(proj)
    return proj


def keep_storyboard_fresh(project, slack=900):
    """把分镜目录里所有 JSON 的 mtime 顶到将来一点（理由见 adopt_storyboard_fixture）。

    slack 给得宽：8 路并行的全量自检里，从 fixture 摆好到页面真正读它可能耗掉一分钟以上，
    顶得太近就会过期——normalize 随后把这些 JSON 改名，断言读到的就是「不存在的文件」（随机红）。
    """
    stamp = time.time() + slack
    folder = storyboard_stage(project) / "分镜文档"
    for path in folder.glob("*.json"):
        try:
            os.utime(path, (stamp, stamp))
        except OSError:
            pass
    return folder


def make_adopted_project(td):
    return adopt_storyboard_fixture(make_minimal_project(td))


def settle_workers(d, win, timeout=15):
    """等 Desktop 的后台制作线程收尾，返回是否在超时前收尾。

    无人值守步骤（补资产/补首帧/补白模/补视频/粗剪/交接包）都是 daemon 线程在干活，它们会
    继续往项目目录里写文件。用例若在文件还在复制时就退出，`with tempfile.TemporaryDirectory()`
    的清理会随机撞上「目录不是空的」（WinError 145），表现为随机失败——不是功能坏了。
    """
    flags = ("asset_busy", "final_busy", "keyframe_busy", "video_busy",
             "edit_busy", "handoff_busy")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        win.update()
        if not any(getattr(d.auto, name, False) for name in flags):
            return True
        time.sleep(0.05)
    return False


def with_dialogue(proj, lines):
    """把对白写进工作稿与工作集（两处保持同一份），供 08 配音用例使用。"""
    source = storyboard_stage(proj) / "分镜文档" / "episode.json"
    episode = json.loads(source.read_text(encoding="utf-8"))
    episode["shots"][0]["dialogue"] = lines
    for target in (source, proj / "episode" / "episode.json"):
        target.write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")
    return source


# 页面只做路径拼接与列表渲染，缩略图解码走的是换页之后的懒加载，所以页头 PNG 用魔数即可，
# 不必造真实位图（假的 PhotoImage 反而会抛异常或刷满 stderr）。
PNG = b"\x89PNG\r\n\x1a\n"


import desktop as desktop_doc


def real_png(width=8, height=8):
    """真能解码的 PNG（几块纯色）——第 52 期第 3 条那条缩略图链要它才走得通。"""
    import struct, zlib
    raw = b"".join(b"\x00" + b"".join(bytes((x * 30 % 256, y * 30 % 256, 140))
                                       for x in range(width)) for y in range(height))

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def make_populated_project(td):
    """跑通全流程的项目：定稿目录、资产图、首帧、已验收镜头、粗剪成片、交接包、字幕都在。

    「有数据」时页面才会走到的分支（清单、缩略图、路径拼接、目录枚举）必须和空项目一样不崩。
    """
    from agent.core import file_hash, save
    proj = make_adopted_project(td)
    base = proj / "episode"                      # minimal 项目已有 episode/assets.json，资产库就是它
    (base / "assets" / "characters").mkdir(parents=True, exist_ok=True)
    (base / "assets" / "scenes").mkdir(parents=True, exist_ok=True)
    (base / "assets" / "characters" / "CHAR_001.png").write_bytes(PNG)
    (base / "assets" / "scenes" / "LOC_001.png").write_bytes(PNG)
    (base / "assets.json").write_text(json.dumps({
        "CHAR_001": {"name": "主角", "image": "assets/characters/CHAR_001.png"},
        "LOC_001": {"name": "场景", "image": "assets/scenes/LOC_001.png"}}, ensure_ascii=False), encoding="utf-8")
    frame = storyboard_stage(proj) / "frames" / "SH001.png"      # 首帧落在共享素材根
    frame.parent.mkdir(parents=True, exist_ok=True); frame.write_bytes(PNG)
    clip = proj / "data" / "clips" / "SH001.mp4"              # 已下载＋质检通过＋已验收
    clip.parent.mkdir(parents=True, exist_ok=True); clip.write_bytes(b"fake-video")
    save(proj / "data" / "state.json", {"schema": 1, "shots": {"SH001": [{
        "version": 1, "state": "downloaded", "qc_pass": True, "review": "pass",
        "file": "data/clips/SH001.mp4", "sha256": file_hash(clip)}]}})
    final = storyboard_stage(proj) / "分镜文档" / "定稿_20260101_000000_000000"
    final.mkdir(parents=True, exist_ok=True)
    (final / "episode.json").write_text((storyboard_stage(proj) / "分镜文档" / "episode.json").read_text(encoding="utf-8"), encoding="utf-8")
    (final / "assets.json").write_text((base / "assets.json").read_text(encoding="utf-8"), encoding="utf-8")
    (final / "assets" / "characters").mkdir(parents=True, exist_ok=True)
    (final / "assets" / "scenes").mkdir(parents=True, exist_ok=True)
    (final / "assets" / "characters" / "CHAR_001.png").write_bytes(PNG)
    (final / "assets" / "scenes" / "LOC_001.png").write_bytes(PNG)
    export = export_stage(proj) / "粗剪_20260101_000000"
    export.mkdir(parents=True, exist_ok=True)
    (export / "SH001.mp4").write_bytes(b"fake-clip")
    (export / "MASTER.mp4").write_bytes(b"fake-master")
    (export / "concat.txt").write_text("file 'SH001.mp4'\n", encoding="utf-8")
    save(export / "qc.json", {"errors": [], "warnings": []})
    save(export / "edit_manifest.json", [{"shot": "SH001", "version": 1}])
    save(editing_stage(proj) / "自动粗剪.json", {"digest": "d", "master": str(export / "MASTER.mp4"), "at": time.time()})
    pack = editing_stage(proj) / "自动交接包"
    pack.mkdir(parents=True, exist_ok=True)
    (pack / "001_SH001.mp4").write_bytes(b"fake-clip")
    save(pack / "镜头顺序.json", [{"shot": "SH001", "file": "001_SH001.mp4", "review": "pass", "seconds": 5}])
    (pack / "导入剪映说明.txt").write_text("说明\n", encoding="utf-8")
    (pack / "对白.srt").write_text("1\n00:00:00,000 --> 00:00:05,000\n台词\n", encoding="utf-8")
    save(pack / "交接包标记.json", {"kind": "auto", "built_at": "2026-01-01 00:00:00"})
    (proj / "subtitles").mkdir(exist_ok=True)
    (proj / "subtitles" / "对白.srt").write_text("1\n", encoding="utf-8")
    for name in ("audio", "delivery", "writing", "workflows"):
        (proj / name).mkdir(exist_ok=True)
    return proj


class UiEdgeTests(unittest.TestCase):
    def setUp(self):
        """第 32 期第 2 条：无人值守的勾选框现在勾上就先弹一次确认——用例里默认放行，
        确认逻辑本身由 test_unattended_switch_asks_first 单独盯着。"""
        import project_settings
        real = project_settings.confirm_unattended
        self.addCleanup(setattr, project_settings, "confirm_unattended", real)
        project_settings.confirm_unattended = lambda *a, **k: True

    def enable_sanhu_auto(self, desktop, *enabled_variables):
        """通过三虎的公开模式接口启动无人值守，避免测试绕过实际门禁。"""
        import pet_ui
        desktop.pet.arm_auto = lambda: None
        desktop.pet.set_mode("auto")
        for variable_name in pet_ui.AUTO_VARIABLE_NAMES:
            desktop.pet.auto_variable(variable_name).set(False)
        for variable_name in enabled_variables:
            desktop.pet.auto_variable(variable_name).set(True)

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def test_all_pages_build_without_storyboard(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            win = self.tk.Tk(); win.withdraw()
            try:
                from desktop import Desktop
                from local_video import open_studio
                d = Desktop(win, root=PROGRAM)
                d.root = proj
                d.studio = open_studio(proj)
                for idx in range(12):
                    try:
                        d.show(idx); win.update_idletasks()
                    except Exception as exc:
                        self.fail(f"page {idx} 构建失败: {type(exc).__name__}: {exc}")
            finally:
                win.destroy()

    def test_editing_actions_disabled_without_downloads(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            win = self.tk.Tk(); win.withdraw()
            try:
                from desktop import Desktop
                from local_video import open_studio
                from tkinter import ttk
                d = Desktop(win, root=PROGRAM)
                d.root = proj
                d.studio = open_studio(proj)
                d.show(PAGE["edit"]); win.update_idletasks()
                states = {}
                def walk(w):
                    if isinstance(w, ttk.Button):
                        states[w.cget("text")] = "disabled" if w.instate(["disabled"]) else "normal"
                    for c in w.winfo_children():
                        walk(c)
                labels = []
                def walk_text(w):
                    if isinstance(w, ttk.Label):
                        labels.append(str(w.cget("text")))
                    for c in w.winfo_children():
                        walk_text(c)
                walk(d.content); walk_text(d.content)
                self.assertEqual(states.get("自动粗剪整集（跳过未验收镜头）"), "disabled")
                self.assertEqual(states.get("整理剪映素材交接包"), "disabled")
                # 按钮禁用时必须写明原因，不能只把按钮变灰。
                self.assertIn("还没有已下载的镜头视频", d.status.get())
            finally:
                win.destroy()

    def test_all_pages_build_with_storyboard(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            win = self.tk.Tk(); win.withdraw()
            try:
                from desktop import Desktop
                from local_video import open_studio
                d = Desktop(win, root=PROGRAM)
                d.root = proj
                d.studio = open_studio(proj)
                for idx in range(12):
                    try:
                        d.show(idx); win.update_idletasks()
                    except Exception as exc:
                        self.fail(f"adopted page {idx} 构建失败: {type(exc).__name__}: {exc}")
            finally:
                win.destroy()

    def test_all_pages_build_with_populated_project(self):
        """全流程跑过一遍的项目（定稿、资产图、首帧、已验收镜头、成片、交接包）也要能构建 11 个页面。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = make_populated_project(td)
            win = self.tk.Tk(); win.withdraw()
            try:
                from desktop import Desktop
                from local_video import open_studio
                d = Desktop(win, root=PROGRAM)
                d.root = proj
                d.studio = open_studio(proj)
                for idx in range(12):
                    try:
                        d.show(idx); win.update_idletasks()
                    except Exception as exc:
                        self.fail(f"populated page {idx} 构建失败: {type(exc).__name__}: {exc}")
                # 夹具必须真的被页面读到：09 交付页逐镜列出状态，空项目下这一栏全是「未提交」。
                d.show(PAGE["delivery"]); win.update_idletasks()
                boxes = []
                def walk(w):
                    if isinstance(w, self.tk.Text):
                        boxes.append(w.get("1.0", "end"))
                    for child in w.winfo_children():
                        walk(child)
                walk(d.content)
                self.assertTrue(any("技术QC 通过" in box and "验收 通过" in box for box in boxes), boxes)
                # O27：质量面板加「采用」列，把技术合格／内容验收／实际采用版本分开。
                self.assertTrue(any("采用 v1" in box for box in boxes), boxes)
            finally:
                win.destroy()

    def test_audio_actions_disabled_without_dialogue(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            adopt_storyboard_fixture(proj)
            win = self.tk.Tk(); win.withdraw()
            try:
                from desktop import Desktop
                from local_video import open_studio
                from tkinter import ttk
                d = Desktop(win, root=PROGRAM)
                d.root = proj
                d.studio = open_studio(proj)
                d.show(PAGE["audio"]); win.update_idletasks()
                states = {}
                def walk(w):
                    if isinstance(w, ttk.Button):
                        states[w.cget("text")] = "disabled" if w.instate(["disabled"]) else "normal"
                    for c in w.winfo_children():
                        walk(c)
                labels = []
                def walk_text(w):
                    if isinstance(w, ttk.Label):
                        labels.append(str(w.cget("text")))
                    for c in w.winfo_children():
                        walk_text(c)
                walk(d.content); walk_text(d.content)
                self.assertEqual(states.get("生成配音（TTS）"), "disabled")
                self.assertEqual(states.get("逐句配音（分句）"), "disabled")
                self.assertEqual(states.get("导出对白字幕 SRT"), "disabled")
                self.assertEqual(states.get("导出对白脚本 TXT"), "disabled")
                # 按钮禁用时必须写明原因，不能只把按钮变灰。
                self.assertTrue(any("暂不可用" in text for text in labels), labels)
            finally:
                win.destroy()

    def test_final_storyboard_split_viewer(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            win = self.tk.Tk(); win.withdraw()
            try:
                from desktop import Desktop
                from local_video import open_studio
                d = Desktop(win, root=PROGRAM)
                d.root = proj
                d.studio = open_studio(proj)
                show_catalog_page_ready(d, PAGE["final"]); win.update_idletasks()
                texts = []
                def walk(w):
                    if isinstance(w, self.tk.Text):
                        texts.append(w.get("1.0", "end-1c"))
                    for c in w.winfo_children():
                        walk(c)
                walk(d.content)
                self.assertTrue(any("SH001" in text for text in texts))
            finally:
                win.destroy()

    def test_script_box_above_storyboard_json_box(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            win = self.tk.Tk(); win.withdraw()
            try:
                from desktop import Desktop
                from local_video import open_studio
                from tkinter import ttk
                d = Desktop(win, root=PROGRAM)
                d.root = proj
                d.studio = open_studio(proj)
                show_catalog_page_ready(d, PAGE["storyboard"]); win.update_idletasks()
                def first_tree(w):
                    for c in w.winfo_children():
                        if isinstance(c, ttk.Treeview):
                            return c
                        found = first_tree(c)
                        if found is not None:
                            return found
                    return None
                def style_of(widget):
                    try:
                        return str(widget.cget("style"))
                    except Exception:
                        return ""
                # 内容框是设计系统卡片；无标签行，不应留出 Labelframe 的标题高度。
                # 空的 TLabelframe 会为标签行留出约 19 像素，白白把按钮行和内容框撑开。
                boxes = [w for w in d.content.winfo_children() if style_of(w) == "Tokens.Card.TFrame"]
                self.assertEqual(len(boxes), 2)
                self.assertEqual(first_tree(boxes[0]).heading("#0")["text"], "")
                self.assertEqual(first_tree(boxes[0]).heading("#1")["text"], "结构剧本")
                self.assertEqual(first_tree(boxes[1]).heading("#0")["text"], "")
                self.assertEqual(first_tree(boxes[1]).heading("#1")["text"], "分镜初稿")
            finally:
                win.destroy()

    def test_step2_rows_hug_their_content_boxes(self):
        """第 31 期第 4/5 条：03 初步分镜页，「刷新列表」那一行与「手动制作分镜」都要紧贴下方内容框。

        内容框改用了没有标签行的 Tokens.Card.TFrame（空 TLabelframe 会白留约 19 像素），
        所以按钮行到表格顶端的距离要落在十几像素以内（改前分别是 30 / 36 像素）。
        """
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            win = self.tk.Tk(); win.geometry("1100x760+40+40")
            def quiet_destroy():
                try:
                    win.destroy()
                except Exception:
                    pass
            self.addCleanup(quiet_destroy)
            from desktop import Desktop
            from local_video import open_studio
            from tkinter import ttk
            d = Desktop(win, root=PROGRAM)
            d.root = proj
            d.studio = open_studio(proj)
            d.cancel_timers()
            import desktop as desktop_module
            original = desktop_module.Desktop.choose_project
            desktop_module.Desktop.choose_project = lambda self: None
            self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
            from desktop import Desktop
            from local_video import open_studio
            d = Desktop(win, root=PROGRAM)
            d.root = proj
            d.studio = open_studio(proj)
            show_catalog_page_ready(d, PAGE["storyboard"]); win.update()
            d.cancel_timers(); d.pet.arm_auto = lambda: None
            buttons = {}; boxes = []
            def style_of(widget):
                try:
                    return str(widget.cget("style"))
                except Exception:
                    return ""
            def walk(w):
                if w.winfo_class() in ("TButton", "Button"):      # 「手动制作分镜」是 tk.Button
                    buttons[str(w.cget("text"))] = w
                if style_of(w) == "Tokens.Card.TFrame":
                    boxes.append(w)
                for child in w.winfo_children():
                    walk(child)
            walk(d.content)
            storyboard_actions = [button for text, button in buttons.items() if "分镜" in text]
            self.assertTrue(storyboard_actions, "初步分镜页需要保留一个分镜工作流入口")
            self.assertEqual(len(boxes), 2)
            def first_tree(w):
                for c in w.winfo_children():
                    if isinstance(c, ttk.Treeview):
                        return c
                    found = first_tree(c)
                    if found is not None:
                        return found
                return None
            toolbar = buttons["刷新列表"].master
            agent = storyboard_actions[0]
            win.update()
            gap_top = first_tree(boxes[0]).winfo_rooty() - (toolbar.winfo_rooty() + toolbar.winfo_height())
            gap_mid = first_tree(boxes[1]).winfo_rooty() - (agent.winfo_rooty() + agent.winfo_height())
            self.assertGreaterEqual(gap_top, 0, "内容框不能压到按钮行上")
            self.assertGreaterEqual(gap_mid, 0, "内容框不能压到「手动制作分镜」上")
            self.assertLessEqual(gap_top, 14, "「刷新列表」那一行到内容框的距离要收紧（改前 30 像素）")
            self.assertLessEqual(gap_mid, 16, "「手动制作分镜」到内容框的距离要收紧（改前 36 像素）")

    def test_previs_actions_follow_the_default_selection(self):
        """第 42 期第 1 条：进页面默认勾上需要白模的镜头；用户取消过就不再替他勾回来。

        原来一个都不勾，两颗主动作永远是灰的，用户得逐镜点一遍。
        """
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            adopt_storyboard_fixture(proj)
            win = self.tk.Tk(); win.withdraw()
            try:
                from desktop import Desktop
                from local_video import open_studio
                from tkinter import ttk
                d = Desktop(win, root=PROGRAM)
                d.root = proj
                d.studio = open_studio(proj)
                def states():
                    found = {}
                    def walk(w):
                        if isinstance(w, ttk.Button):
                            found[w.cget("text")] = "disabled" if w.instate(["disabled"]) else "normal"
                        for c in w.winfo_children():
                            walk(c)
                    walk(d.content)
                    return found
                d.show(PAGE["previs"]); win.update_idletasks()
                # 这一镜没有复杂度标注 → 自动判成中等动作 → 算「需要白模」，进页面就该勾上
                self.assertEqual(len(d.previs_jobs["selected"]), 1, "需要白模的镜头默认勾选")
                first = states()
                self.assertEqual(first.get("手动制作白模"), "normal")
                self.assertEqual(first.get("线上白模入口"), "normal")
                d.previs_jobs["selected"].clear()                 # 用户自己取消勾选
                d.show(PAGE["previs"]); win.update_idletasks()
                self.assertEqual(d.previs_jobs["selected"], set(), "取消过就不许再勾回来")
                again = states()
                self.assertEqual(again.get("手动制作白模"), "disabled")
                self.assertEqual(again.get("线上白模入口"), "disabled")
            finally:
                win.destroy()


    def test_file_table_click_rules(self):
        """初步分镜页内容框点击：文本格单击勾选、再点取消；带链接的格子先勾选再打开，已勾选只打开不取消。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None  # 关掉自动打开上次项目，避免切走项目
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            win = self.tk.Tk(); win.geometry("1000x700+40+40")
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
            show_catalog_page_ready(d, PAGE["storyboard"]); win.update()
            trees = []
            def walk(w):
                if isinstance(w, ttk.Treeview):
                    trees.append(w)
                for child in w.winfo_children():
                    walk(child)
            walk(d.content)
            storyboard_tables = [t for t in trees if 'status' in list(t['columns'])]
            self.assertEqual(len(storyboard_tables), 2, '初稿与 JSON 定稿各有一张状态表')
            for status_table in storyboard_tables:
                for item in status_table.get_children():
                    self.assertEqual(list(status_table.item(item, 'tags')), [],
                                     '03 初步分镜不应用整行已制作／已采用高亮')
            table = [t for t in trees if t.get_children()][0]
            row = table.get_children()[0]
            on, off = str(d.win._tick_images[1]), str(d.win._tick_images[0])
            opened = []
            real_startfile = os.startfile
            os.startfile = lambda path, *a, **k: opened.append(str(path))
            self.addCleanup(setattr, os, "startfile", real_startfile)
            def click(column):
                x, y, width, height = table.bbox(row, column)
                table.event_generate("<Button-1>", x=int(x + width // 2), y=int(y + height // 2))
                win.update()
            self.assertEqual(table.item(row, "image")[0], off)
            click("#1")                                            # 文本格
            self.assertEqual(table.item(row, "image")[0], on)      # 单击：勾选本行
            click("#1")
            self.assertEqual(table.item(row, "image")[0], off)     # 再次单击：取消勾选
            click("#5")
            self.assertEqual(table.item(row, "image")[0], on)      # 另一文本格同样可勾选
            click("#3")                                            # 带链接的「文件内容」格
            self.assertEqual(table.item(row, "image")[0], on)      # 未勾选 → 先勾选
            self.assertEqual(len(opened), 1)                       # 再打开对应文件
            click("#3")
            self.assertEqual(table.item(row, "image")[0], on)      # 已勾选 → 不取消
            self.assertEqual(len(opened), 2)                       # 直接打开

    def test_launch_comfy_does_not_block_on_a_starting_service(self):
        """ComfyUI 正在启动（端口已开、还没应答）时启动判断立刻返回，也不再索要桌面程序路径。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import socket
        import native_apps
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
            def quiet_destroy():
                try:
                    win.destroy()
                except Exception:
                    pass
            self.addCleanup(quiet_destroy)
            from desktop import Desktop
            d = Desktop(win, root=PROGRAM)
            d.root = proj
            d.settings.pop("comfy_exe", None)
            launched = []
            asked = []
            original_open = native_apps.open_comfy
            native_apps.open_comfy = lambda settings=None: (launched.append(settings), None)[1]
            import ui_dialogs
            original_ask = ui_dialogs.filedialog.askopenfilename
            ui_dialogs.filedialog.askopenfilename = lambda **kwargs: asked.append(kwargs) or ""
            self.addCleanup(setattr, native_apps, "open_comfy", original_open)
            self.addCleanup(setattr, ui_dialogs.filedialog, "askopenfilename", original_ask)
            # 只接受连接、永不回应的端口＝ComfyUI 正在启动
            server = socket.socket()
            server.bind(("127.0.0.1", 0)); server.listen(1)
            self.addCleanup(server.close)
            d.settings["comfy_url"] = "http://127.0.0.1:%d" % server.getsockname()[1]
            started = time.perf_counter()
            self.assertTrue(d.launch_comfy())
            elapsed = time.perf_counter() - started
            self.assertLess(elapsed, 0.5)                  # 旧实现会在这里等满 3 秒
            self.assertEqual(launched, [])                 # 已在运行就不重复拉起
            self.assertEqual(asked, [])                    # 已在运行时不该再索要桌面程序路径
            self.assertIn("已在运行", d.status.get())
            # 端口没人听：照旧拉起桌面程序
            probe = socket.socket()
            probe.bind(("127.0.0.1", 0)); free_port = probe.getsockname()[1]; probe.close()
            d.settings["comfy_url"] = "http://127.0.0.1:%d" % free_port
            self.assertFalse(d.comfy_listening())
            with tempfile.TemporaryDirectory() as stub:
                # 桩写进临时目录：写进 d.app（＝程序目录）的话，每跑一次自检就在程序目录里
                # 留一个 2 字节的 fake_comfy_desktop.exe（第 23 期清理时发现的）。
                exe = Path(stub) / "fake_comfy_desktop.exe"
                exe.write_bytes(b"MZ")
                d.settings["comfy_exe"] = str(exe)
                self.assertTrue(d.launch_comfy())
                self.assertEqual(len(launched), 1)
                self.assertIn("已打开", d.status.get())

    def test_launch_comfy_is_silent_in_the_production_chain(self):
        """第 62 期任务 8：「手动制作资产／首帧」自动拉起 ComfyUI 时不弹「选择程序」对话框。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import socket
        import native_apps
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
            def quiet_destroy():
                try:
                    win.destroy()
                except Exception:
                    pass
            self.addCleanup(quiet_destroy)
            from desktop import Desktop
            d = Desktop(win, root=PROGRAM)
            d.root = proj
            asked = []
            launched = []
            original_open = native_apps.open_comfy
            native_apps.open_comfy = lambda settings=None: (launched.append(settings), None)[1]
            import ui_dialogs
            original_ask = ui_dialogs.filedialog.askopenfilename
            ui_dialogs.filedialog.askopenfilename = lambda **kwargs: asked.append(kwargs) or ""
            original_exe = desktop_module.comfy_executable
            desktop_module.comfy_executable = lambda settings: None
            self.addCleanup(setattr, native_apps, "open_comfy", original_open)
            self.addCleanup(setattr, ui_dialogs.filedialog, "askopenfilename", original_ask)
            self.addCleanup(setattr, desktop_module, "comfy_executable", original_exe)
            probe = socket.socket()
            probe.bind(("127.0.0.1", 0)); free_port = probe.getsockname()[1]; probe.close()
            d.settings["comfy_url"] = "http://127.0.0.1:%d" % free_port
            # 制作链路：静默拉起，找不到程序也不弹选择框，只写一句人话
            self.assertFalse(d.launch_comfy(silent=True))
            self.assertEqual(asked, [])
            self.assertEqual(launched, [])
            self.assertIn("没找到", d.status.get())
            # 用户自己点「桌面打开 ComfyUI」：照旧弹选择框让他选一次
            self.assertIsNone(d.launch_comfy())
            self.assertEqual(len(asked), 1)

    def test_frame_page_batch_row_moved_below_table(self):
        """04 首帧页：「选中镜头」行贴内容框下方，批量/Skill/导入新首帧等按钮删除。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            # 多几镜才能观察内容框高度随窗口变化
            frame_json = storyboard_stage(proj) / "分镜文档" / "episode.json"
            data = json.loads(frame_json.read_text(encoding="utf-8"))
            base = data["shots"][0]
            data["shots"] = [dict(base, id="SH%03d" % index) for index in range(1, 17)]
            frame_json.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            win = self.tk.Tk(); win.geometry("1100x760+40+40")
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
            d.show(PAGE["keyframe"]); win.update()
            buttons = []; trees = []
            def walk(w):
                if isinstance(w, ttk.Button):
                    buttons.append(w)
                if isinstance(w, ttk.Treeview):
                    trees.append(w)
                for child in w.winfo_children():
                    walk(child)
            walk(d.content)
            found = {str(b.cget("text")): b for b in buttons}
            for gone in ("单个首帧Agent", "ComfyUI 单个首帧", "ComfyUI 批量首帧", "批量首帧Agent",
                         "Skill 调用设置", "SKILL说明", "导入新首帧", "打开镜头 JSON", "恢复为待生成",
                         "查看选中首帧", "选择镜头 JSON"):
                self.assertNotIn(gone, found)
            for kept in ("手动制作首帧", "刷新首帧列表", "查看首帧提示词",
                         "查看镜头资产", "导入 / 替换选中首帧", "批量删除首帧", "恢复删除的首帧"):
                self.assertIn(kept, found)
            # DataTable 是统一表格壳；Treeview 的直接父级是壳本身，页面内容框在再上一层。
            table_box = [t for t in trees if "prompt" in t["columns"]][0].master.master
            target_row = found["刷新首帧列表"].master
            actions_row = found["手动制作首帧"].master
            self.assertIsNot(target_row, actions_row)
            win.update()
            # 视觉顺序：内容框 → 选中镜头行 → 生成行（贴底行先 pack，不能再用 pack 顺序判断）
            self.assertLess(table_box.winfo_rooty(), target_row.winfo_rooty())
            self.assertLess(target_row.winfo_rooty(), actions_row.winfo_rooty())
            # 下拉框在行内最左，六个按钮依次排在其右侧
            children = target_row.winfo_children()
            self.assertIsInstance(children[1], ttk.Combobox)
            texts = [str(w.cget("text")) for w in children if isinstance(w, (ttk.Label, ttk.Button))]
            self.assertEqual(texts, ["选中镜头", "刷新首帧列表", "查看首帧提示词", "查看镜头资产",
                                     "导入 / 替换选中首帧", "批量删除首帧", "恢复删除的首帧"])
            # 「手动制作首帧」用主色按钮突出
            self.assertEqual(str(found["手动制作首帧"].cget("style")), "Tokens.Primary.TButton")
            # 底部两行先贴底占位，内容框最后填充剩余高度：缩窗时按钮/下拉框不会被挤出可视区
            self.assertEqual(str(target_row.pack_info()["side"]), "bottom")
            self.assertEqual(str(actions_row.pack_info()["side"]), "bottom")
            self.assertEqual(str(table_box.pack_info()["side"]), "top")
            table = [t for t in trees if "prompt" in t["columns"]][0]
            tall = int(table.cget("height"))
            win.geometry("1100x520+40+40")
            for _ in range(3):
                win.update(); win.update_idletasks()
            self.assertLess(int(table.cget("height")), tall)          # 内容框随窗口变矮
            self.assertEqual(tuple(d.canvas.yview()), (0.0, 1.0))     # 整页无需滚动即可看全
            limit = win.winfo_rooty() + win.winfo_height() + 2
            for name in ("刷新首帧列表", "导入 / 替换选中首帧", "手动制作首帧"):
                widget = found[name]
                self.assertTrue(widget.winfo_ismapped())
                self.assertGreater(int(widget.winfo_height()), 0)
                self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(), limit)
            errors = []
            real_error = desktop_module.messagebox.showerror
            desktop_module.messagebox.showerror = lambda *a, **k: errors.append(a[1] if len(a) > 1 else a)
            self.addCleanup(setattr, desktop_module.messagebox, "showerror", real_error)
            found["手动制作首帧"].invoke(); win.update()
            dialogs = popup_windows(win, self.tk)
            self.assertEqual(errors, [])
            self.assertEqual(len(dialogs), 1, "第 54 期起这一颗按钮只剩它自己那一扇窗")
            self.assertIn("首帧制作", dialogs[0].title())
            dialogs[0].destroy(); win.update()

    def test_page_level_model_and_skill_entries_are_gone(self):
        """第 29 期第 1／4 条、第 32 期第 6 条：重复的「Model ＋ SKILL」「配置线上视频 API」入口删掉；
        「阶段配置」不再集中在剧本准备页，改到各阶段页「手动XX」右边各一颗。

        面板里的接口一个都不少，那一头由 test_skills.PanelTests.test_the_panel_keeps_the_interfaces 盯着。
        """
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            win = self.tk.Tk(); win.geometry("1100x760+40+40")
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
            self.assertFalse(hasattr(d, "flow_controls"), "重复的控制行整个删掉")
            self.assertFalse(hasattr(d, "flow_help"), "「SKILL说明」那颗按钮与实现一起删")
            self.assertTrue(hasattr(d, "flow_settings"), "首帧页的 Skill 调用设置 还要用它，不许误删")
            gone = ("设置 Model + SKILL", "设置model+SKILL", "设置model+skill",
                    "SKILL 说明", "SKILL说明", "调用设置")
            for index in (PAGE["script"], PAGE["storyboard"], PAGE["previs"], PAGE["video"], PAGE["audio"]):
                d.show(index); win.update()
                texts = widget_texts(d.content)
                for label in gone:
                    self.assertNotIn(label, texts, "第 %02d 页还留着重复入口：%s" % (index + 1, label))
            # 各阶段页：主动作＋紧跟它右边那颗「阶段配置」。剧本页的「发送」会启动
            # 写作 Agent 工作流；其它阶段保留各自的手动制作动作。窗口映射会滞后，
            # 所以判据看结构（FlowBar 会把子控件从 pack 换成 place 自己排，见 responsive_ui.FlowBar.layout），
            # 不盯 winfo_ismapped。
            # 第 54 期附件二第 3 条：按钮名按「手动制作{阶段简称}」统一；剧本页例外，
            # 用户在固定发送框填写创意后由「发送」启动唯一工作流。
            manual = {PAGE["script"]: "发送", PAGE["storyboard"]: "手动制作分镜",
                      PAGE["assets"]: "手动制作资产", PAGE["keyframe"]: "手动制作首帧",
                      PAGE["previs"]: "手动制作白模"}
            for index, label in sorted(manual.items()):
                with self.subTest(page=index + 1):
                    d.show(index)
                    for _ in range(3):
                        win.update(); win.update_idletasks()
                    texts = widget_texts(d.content)
                    self.assertIn(label, texts, "第 %02d 页的主动作叫「%s」" % (index + 1, label))
                    self.assertTrue(d.stage_button.winfo_exists(), "「阶段配置」按钮真的建出来了")
                    self.assertIn(str(d.stage_button.cget('text')), texts,
                                  "第 %02d 页的配置入口应显示当前实际模型或阶段配置" % (index + 1))
                    self.assertIn(d.stage_button.winfo_manager(), ("pack", "place"),
                                  "它默认就摆在这一行里")
                    self.assertGreater(int(d.stage_button.winfo_reqheight()), 0, "按钮有真实高度，不是空壳")
            # 第 68 期任务 6：07 分镜定稿补上了主动作「手动同步资产」，阶段配置跟着挪到那一行
            # （原来挂在页标题右边），页标题旁不再重复摆一颗。
            show_catalog_page_ready(d, PAGE["final"])
            for _ in range(3):
                win.update(); win.update_idletasks()
            self.assertTrue(d.stage_button.winfo_exists(), "05 页的「阶段配置」建在主动作那一行")
            self.assertIn(d.stage_button.winfo_manager(), ("pack", "place"),
                          "它默认就摆在那一行里")
            self.assertGreater(int(d.stage_button.winfo_reqheight()), 0, "按钮有真实高度")
            self.assertIn(str(d.stage_button.cget('text')), widget_texts(d.content), "05 页行内就有配置入口")
            self.assertIsNone(d.header_stage_button, "05 页标题旁不再重复摆一颗")
            for index in (PAGE["script"], PAGE["storyboard"], PAGE["assets"],
                          PAGE["keyframe"], PAGE["previs"]):
                with self.subTest(page=index + 1):
                    d.show(index); win.update()
                    self.assertIsNone(d.header_stage_button,
                                      "第 %02d 页的阶段配置挂在主动作那一行里" % (index + 1))
            # 没有旧式「手动XX」的下游页也必须保留唯一配置入口。入口文案会显示实际
            # 模型（例如 Codex），不能再把「阶段配置」四个字写死。
            for index in (PAGE["audio"], PAGE["edit"], PAGE["delivery"]):
                with self.subTest(page=index + 1):
                    d.show(index); win.update()
                    self.assertIsNotNone(d.stage_button,
                                         "第 %02d 页必须有阶段配置入口" % (index + 1))
            # 第 54 期附件二第 3 条：09／10 两页原来一个「手动XX」都没有，这一轮补上
            # 「手动制作剪辑／手动制作交付」；阶段配置的位置照旧（页标题右边），没有第二颗。
            for index, label in ((PAGE["edit"], "手动制作剪辑"),
                                 (PAGE["delivery"], "手动制作交付")):
                with self.subTest(page=index + 1):
                    d.show(index)
                    for _ in range(3):
                        win.update(); win.update_idletasks()
                    texts = widget_texts(d.content)
                    self.assertIn(label, texts, "第 %02d 页补上了「%s」" % (index + 1, label))
                    self.assertEqual(int(d.stage_button.winfo_exists()), 1,
                                     "阶段配置入口必须存在且唯一")
            d.show(PAGE["video"], video_mode="choose"); win.update()
            self.assertIsNone(d.header_stage_button, "第 08 页选生成方式那一屏不再重复摆一颗")
            d.show(0); win.update()
            self.assertNotIn("▼  剧本创作 Agent  ▼", widget_texts(d.content))
            # 视频页的工作台本地与线上共用同一份：两颗主动作与阶段配置均由视频阶段提供。
            d.show(PAGE["video"], video_mode="local")
            for _ in range(3):
                win.update(); win.update_idletasks()
            texts = widget_texts(d.content)
            self.assertIn("手动制作提示词", texts, "视频页主动作改名「手动制作提示词」")
            self.assertIn("手动制作视频", texts, "视频页主动作改名「手动制作视频」")
            self.assertIn("阶段配置", texts, "视频页也有一颗「阶段配置」")
            d.show(PAGE["video"], video_mode="choose"); win.update()
            self.assertIn("进入线上生成", widget_texts(d.content))
            self.assertNotIn("配置线上视频 API", widget_texts(d.content),
                             "选生成方式那一屏不再重复摆一颗接口设置按钮")
            d.show(PAGE["video"], video_mode="cloud"); win.update()
            self.assertIn("配置线上视频 API", widget_texts(d.content),
                         "还没配线上接口时，工作台那一屏仍留一处能配（面板的接口里也有一份）")

    def test_unattended_switch_is_not_rendered_by_the_page(self):
        """自动状态只由三虎写入；页面不得保留用户可点的自动制作勾选框。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            win = self.tk.Tk(); win.geometry("1100x760+40+40")
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
            d.show(PAGE["keyframe"]); win.update()
            found = []
            def walk(widget):
                if isinstance(widget, ttk.Checkbutton):
                    found.append(widget)
                for child in widget.winfo_children():
                    walk(child)
            walk(d.content)
            self.assertEqual(found, [], "首帧页不渲染自动补首帧开关；由三虎模式统一控制")

    def test_writing_page_first_line_and_removed_labels(self):
        """第 31 期第 1 条＋第 69 期任务 4：01 剧本准备页不再摆那一长句说明，四处多余文字也删掉。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            import desktop as desktop_module
            original = desktop_module.Desktop.choose_project
            desktop_module.Desktop.choose_project = lambda self: None
            self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
            win = self.tk.Tk(); win.geometry("1100x760+40+40")
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
            d.show(0); win.update()
            texts = []
            def walk_text(w):
                try:
                    value = str(w.cget("text"))
                except Exception:
                    value = ""
                if value:
                    texts.append(value)
                for child in w.winfo_children():
                    walk_text(child)
            walk_text(d.content)
            joined = "\n".join(texts)
            self.assertNotIn("对话AI", texts, "独立标题应移除，让聊天框上移")
            self.assertEqual(d.idea_log.master.master.winfo_class(), "TFrame",
                             "使用无标题容器，避免 LabelFrame 保留标题行高度")
            self.assertIn("输入想法/上传附件---->enter/发送", texts,
                          "输入区提示应包含附件入口以及 Enter/发送两种提交方式")
            for gone in ("当前剧本目录", "创作入口", "文件操作",
                         "在下面的对话框写想法", "对话框（在这里写"):
                self.assertNotIn(gone, joined, "这一处文字要删掉：%s" % gone)

    def test_the_brief_example_never_lands_in_the_project(self):
        """第 37 期第 2 条：创意栏那份预置示例随程序打包，用户不改就一个字都不进项目文件。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            win = self.tk.Tk(); win.geometry("1100x760+40+40")
            self.addCleanup(lambda: win.winfo_exists() and win.destroy())
            from desktop import Desktop
            import desktop as desktop_module
            original = desktop_module.Desktop.choose_project
            desktop_module.Desktop.choose_project = lambda self: None
            self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
            d = Desktop(win, root=PROGRAM)
            d.root = proj
            d.show(0); win.update()
            example = d.idea_example()
            self.assertTrue(example.strip(), "程序里那份示例要打包带上")
            from desktop import IDEA_FIELDS
            self.assertIn(IDEA_FIELDS[0], example, "示例里要有字段名，灰色字段名那一层才认得出")
            self.assertEqual(example, d.idea_example(), "读一次就记着，不反复读盘")
            self.assertEqual(d.draft_text(), '', "下方发送框初始为空")
            self.assertEqual(idea_chat.strip_inline_required_markers(d._bubble_full['bubble_example']['text']), example)
            self.assertTrue(d.idea_log.tag_ranges('bubble_example'), "软件示例显示为只读气泡")
            brief_path = d.brief_editor[0]
            self.assertFalse(list((proj / "writing").glob("创意与剧本*.md")), "一个字都没落盘")
            with self.assertRaises(ValueError):
                d.save_brief(brief_path, example)          # 没改动：拒收
            with self.assertRaises(ValueError):
                d.save_brief(brief_path, example + "\n  ")  # 只多几个空白也算没改
            d.flush_brief()                                        # 翻页时的自动保存同样不落盘
            self.assertFalse(list((proj / "writing").glob("创意_*")), "翻页也不许偷偷落盘")
            saved = d.save_brief(brief_path, example + "\n我的补充：一只会说话的猫。")
            self.assertTrue(saved.is_file(), "用户真的改了才另存新版本")
            self.assertIn("我的补充", saved.read_text(encoding="utf-8"))
            self.assertNotIn(example.strip(), saved.read_text(encoding="utf-8"),
                             "软件示例只能辅助填写，不能混入项目创意")

    def test_the_writing_page_gives_the_brief_more_room(self):
        """第 37 期第 3 条＋第 69 期任务 2：内容框加高，下面那格对话框并进来，按钮围着它摆。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            win = self.tk.Tk(); win.geometry("1100x760+40+40")
            self.addCleanup(lambda: win.winfo_exists() and win.destroy())
            from desktop import Desktop
            import desktop as desktop_module
            original = desktop_module.Desktop.choose_project
            desktop_module.Desktop.choose_project = lambda self: None
            self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
            d = Desktop(win, root=PROGRAM)
            d.root = proj
            d.show(0); win.update()
            box = d.idea_log
            d.idea_input.delete('1.0', 'end'); win.update()
            # 聊天记录按窗口剩余空间自适应；下方发送框在空白时仅保留一行，输入后再撑开。
            lines = int(box.cget("height"))
            self.assertGreaterEqual(lines, desktop_module.TALK_MIN_LINES, "再挤也留着下限那些行")
            self.assertLessEqual(lines, desktop_module.TALK_MAX_LINES, "字再多也不超过上限")
            self.assertEqual(int(d.idea_input.cget("height")), 1, "空白发送框不挤占聊天区")
            self.assertEqual(str(d.idea_send.master), str(d.idea_row), "「发送」在内容框下面那一行")
            self.assertLess(d.idea_attachment_button.winfo_rootx(), d.idea_input.winfo_rootx(),
                            "上传文件图标应位于输入框左侧")
            self.assertFalse(d.idea_attachment_status_label.winfo_ismapped(),
                             "未附档时不应留下空白状态行")
            input_bottom=d.idea_input.winfo_rooty()+d.idea_input.winfo_height()
            from ui_tokens import SPACING
            self.assertEqual(d.idea_send.winfo_rooty()-input_bottom, SPACING["xs"],
                             "发送按钮与输入框保留设计系统规定的微小防误触间距")
            d.idea_input.event_generate('<FocusOut>'); win.update()
            hint_info = d.idea_input_hint.place_info()
            self.assertEqual(hint_info.get('rely'), '0.5', "空闲提示应以输入框中线垂直居中")
            self.assertEqual(hint_info.get('relx'), '0', "空闲提示应从输入框左侧定位")
            self.assertEqual(hint_info.get('anchor'), 'w', "静态提示应左对齐")
            self.assertAlmostEqual(
                d.idea_input_hint.winfo_rootx(),
                d.idea_input.winfo_rootx() + d.idea_input.bbox('1.0')[0],
                delta=2, msg="提示文字应沿输入框的文字内边距对齐")

    def test_the_writing_page_wraps_the_box_with_buttons(self):
        """第 69 期任务 2／3：创作入口在内容框上方，「发送」在它左下角，文件操作在右下角。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            from project_stages import writing
            writing = writing(proj)
            writing.mkdir(exist_ok=True)
            creative = writing / "测试Provider" / "测试模型" / "创意_20260926"
            for folder in ("项目设定", "项目大纲", "角色卡", "项目剧本"):
                (creative / folder).mkdir(parents=True, exist_ok=True)
            (creative / "项目设定" / "项目设定_测试.md").write_text("设定", encoding="utf-8")
            (creative / "项目大纲" / "项目大纲_测试.md").write_text("大纲", encoding="utf-8")
            (creative / "角色卡" / "角色卡_测试.md").write_text("角色卡", encoding="utf-8")
            (creative / "项目剧本" / "项目剧本_测试.md").write_text("剧本", encoding="utf-8")
            (writing / "script.md").write_text("后续的结构化剧本", encoding="utf-8")
            (writing / "brief_raw.md").write_text("用户发送的信息", encoding="utf-8")
            (writing / "聊天记录.md").write_text("模型闲聊", encoding="utf-8")
            win = self.tk.Tk(); win.geometry("1100x760+40+40")
            self.addCleanup(lambda: win.winfo_exists() and win.destroy())
            from desktop import Desktop
            import desktop as desktop_module
            original = desktop_module.Desktop.choose_project
            desktop_module.Desktop.choose_project = lambda self: None
            self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
            d = Desktop(win, root=PROGRAM)
            d.root = proj
            d.show(0); win.update()
            box = d.idea_log
            talk = d.idea_row.master
            self.assertEqual(str(box.master.master), str(talk), "聊天内容框摆在对话区容器内")
            self.assertEqual(str(d.idea_input.master.master.master), str(talk), "发送框固定在同一对话区底部")
            # 剧本页与其他阶段共用 FlowBar：窄窗口时允许分行，不能再以左右 pack
            # 互相挤压到裁掉按钮文字。
            self.assertTrue(all(child.winfo_manager() == 'place'
                                for child in d.idea_row.winfo_children()))
            actions = [str(child.cget("text")) for child in d.idea_row.winfo_children()
                       if hasattr(child, "cget") and str(child.winfo_class()).endswith("Button")]
            self.assertIn("添加剧本", actions)
            self.assertIn("删除", actions)
            self.assertEqual(str(d.script_box.winfo_class()), "TFrame")
            self.assertTrue(d.script_box.winfo_ismapped(),
                            "发现已有剧本文件时，三列表容器与列头必须保持可见")
            # R1862：四类文件复原为四张并排表，每张表头即分类名，各自一个勾选列。
            titles = {"setting": "项目设定", "outline": "项目大纲", "character": "角色卡", "script": "项目剧本"}
            self.assertEqual(tuple(d.script_trees), tuple(titles))
            names = {}
            for category, tree in d.script_trees.items():
                self.assertEqual(str(tree.heading("name", "text")), titles[category])
                self.assertEqual(tuple(tree["columns"]), ("name",))
                self.assertNotIn("time", tuple(tree["columns"]), "剧本准备文件表不显示修改日期列")
                self.assertEqual(int(tree.cget("height")), len(tree.get_children()),
                                 "表高按行数收紧")
                self.assertEqual(int(tree.column("#0")["width"]), 28,
                                 "剧本文件表首列应复用分镜页的勾选列宽度")
                names[category] = [tree.item(item, "values")[0] for item in tree.get_children()]
                for item in tree.get_children():
                    self.assertEqual(d.script_row_category[item], category)
                    self.assertEqual(len(tree.item(item, "values")), 1,
                                     "剧本准备文件表每行只显示文件名")
            roots = [tree.winfo_rootx() for tree in d.script_trees.values()]
            self.assertEqual(roots, sorted(roots), "四张表从左到右并排")
            self.assertEqual(len({tree.winfo_rooty() for tree in d.script_trees.values()}), 1, "四张表同一行")
            self.assertEqual(names["setting"], ["项目设定_测试.md"])
            self.assertEqual(names["outline"], ["项目大纲_测试.md"])
            self.assertEqual(names["character"], ["角色卡_测试.md"])
            self.assertEqual(names["script"], ["项目剧本_测试.md"])
            self.assertNotIn("script.md", names["script"], "剧本结构阶段产物不应出现在剧本准备页")

    def test_script_structure_page_shows_source_and_output_in_separate_boxes(self):
        """剧本结构页上看剧本准备来源、下看结构化输出，手动制作和阶段配置夹在中间。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            writing = proj / "writing"; writing.mkdir(exist_ok=True)
            (writing / "script_raw.md").write_text("第 1 集\n镜头号：SH001\n阿远：我回来了。\n" + "\n".join("原稿行%d" % i for i in range(50)) + "\n镜头号：SH002\n" + "\n".join("原稿后段%d" % i for i in range(50)), encoding="utf-8")
            structured = writing / "结构剧本" / "script.md"; structured.parent.mkdir()
            structured.write_text("# 结构化剧本\n\n## 分场剧本\n镜头号：SH001\n" + "\n".join("正稿行%d" % i for i in range(10)) + "\n镜头号：SH002\n" + "\n".join("正稿后段%d" % i for i in range(90)), encoding="utf-8")
            long_line = "中文长行正文" * 2048
            for path in (writing / "script_raw.md", structured):
                with path.open("a", encoding="utf-8") as stream:
                    stream.write("\n" + long_line)
            win = self.tk.Tk(); win.geometry("1100x760+40+40")
            self.addCleanup(lambda: win.winfo_exists() and win.destroy())
            from desktop import Desktop
            import desktop as desktop_module
            original = desktop_module.Desktop.choose_project
            desktop_module.Desktop.choose_project = lambda self: None
            self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
            d = Desktop(win, root=PROGRAM)
            d.root = proj
            d.show(__import__('pet_state').PAGE_OF['script_structure']); win.update()
            self.assertIn("阿远：我回来了", d.script_structure_source_preview.get("1.0", "end"))
            self.assertIn("## 分场剧本", d.script_structure_output_preview.get("1.0", "end"))
            # R1690 起：正文按词换行（超过 20 万字符才退回横向滚动），全文仍逐字保留；
            # 换行阈值与横向滚动条的联动由 test_script_view_style 覆盖，这里只管两个框的排版位置。
            previews = (d.script_structure_source_preview, d.script_structure_output_preview)
            for preview in previews:
                self.assertEqual(str(preview.cget("wrap")), "word")
                self.assertIn(long_line, preview.get("1.0", "end"))
                preview.xview_moveto(0); win.update()
            self.assertEqual(str(d.script_structure_manual_button.cget("text")), "手动制作结构剧本")
            source_rows = d.script_structure_source_preview_files.get_children()
            output_rows = d.script_structure_output_preview_files.get_children()
            self.assertEqual(len(source_rows), 1)
            self.assertEqual(len(output_rows), 1)
            # 文件栏只显示文件名；完整位置不应挤占用户的文件选择区域。
            self.assertEqual(tuple(d.script_structure_source_preview_files.item(source_rows[0], "values")),
                             ("script_raw.md",))
            self.assertEqual(tuple(d.script_structure_output_preview_files.item(output_rows[0], "values")),
                             ("script.md",))
            self.assertFalse(hasattr(d, "script_structure_files_table"), "底部重复剧本表不应继续创建")
            self.assertEqual(str(d.script_structure_source_box.winfo_class()), "TFrame")
            self.assertEqual(str(d.script_structure_output_box.winfo_class()), "TFrame")
            self.assertEqual(
                d.script_structure_source_box.winfo_children()[0].winfo_class(),
                "TFrame",
            )
            self.assertEqual(
                d.script_structure_output_box.winfo_children()[0].winfo_class(),
                "TFrame",
            )
            self.assertIs(d.script_structure_info_label, d.header_status, "说明文字放在页头右上角（R1862）")
            self.assertEqual(str(d.script_structure_info_label.cget("justify")), "right")
            self.assertIn("本地规则整理，不调用模型", str(d.script_structure_info_label.cget("text")))
            self.assertTrue(d.stage_button.winfo_exists(), "阶段配置按钮应在两内容框之间的操作行")
            output_position = d.script_structure_output_preview.yview()[0]
            d.script_structure_source_preview.yview_moveto(0.62); win.update()
            self.assertEqual(d.script_structure_output_preview.yview()[0], output_position,
                             "上下剧本框应可独立滚动")
            d.script_structure_source_preview_edit_button.invoke(); win.update()
            d.script_structure_source_preview.insert("end", "\n新增修订。")
            original = d.script_structure_source_preview.get("1.0", "1.4")
            d.script_structure_source_preview.delete("1.0", "1.4")
            d.script_structure_source_preview_restore_button.invoke(); win.update()
            self.assertEqual(d.script_structure_source_preview.get("1.0", "1.4"), original)
            d.script_structure_source_preview_controller.save_now(); win.update()
            self.assertIn("新增修订。", (writing / "script_raw.md").read_text(encoding="utf-8"))

    def test_frame_checks_follow_the_frame_state(self):
        """04 首帧页：勾选与首帧状态双向同步，弹窗提交的那一批回写页面。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        import desktop as desktop_module
        import frame_checks as checks_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            frame_json = storyboard_stage(proj) / "分镜文档" / "episode.json"
            data = json.loads(frame_json.read_text(encoding="utf-8"))
            base = data["shots"][0]
            data["shots"] = [dict(base, id="SH%03d" % index, frame="frames/SH%03d.png" % index)
                             for index in range(1, 4)]
            frame_json.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            win = self.tk.Tk(); win.geometry("1100x760+40+40")
            def quiet_destroy():
                d.shutting_down = True
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
            d.show(PAGE["keyframe"]); win.update()
            ids = ["SH001", "SH002", "SH003"]
            checked = d.frame_checks[str(frame_json.resolve())]
            self.assertIsInstance(checked, checks_module.FrameChecks)
            self.assertEqual(checked.checked(ids), ids)          # 三镜都缺首帧，默认全勾
            frame = storyboard_stage(proj) / "frames" / "SH002.png"
            frame.parent.mkdir(parents=True, exist_ok=True); frame.write_bytes(PNG)
            buttons = []; trees = []
            def walk(w):
                if isinstance(w, ttk.Button):
                    buttons.append(w)
                if isinstance(w, ttk.Treeview):
                    trees.append(w)
                for child in w.winfo_children():
                    walk(child)
            walk(d.content)
            found = {str(b.cget("text")): b for b in buttons}
            found["刷新首帧列表"].invoke(); win.update()
            self.assertEqual(checked.checked(ids), ["SH001", "SH003"])   # 首帧就位的那一镜自动取消勾选
            self.assertIn("1 镜首帧已就位", d.status.get())
            table = [t for t in trees if "prompt" in t["columns"]][0]
            self.assertEqual(table.item("SH002", "image"), (str(d.win._tick_images[0]),))
            self.assertEqual(table.item("SH001", "image"), (str(d.win._tick_images[1]),))
            checked.toggle("SH001")                              # 用户手动取消
            found["刷新首帧列表"].invoke(); win.update()
            self.assertEqual(checked.checked(ids), ["SH003"])    # 刷新不会把它勾回来
            # 「首帧制作」弹窗提交的那一批回写：页面、下拉框与弹窗共用同一份勾选状态
            self.assertEqual(d.frame_checks_apply(frame_json, ["SH001"]), ["SH001"])
            self.assertEqual(checked.checked(ids), ["SH001"])

    def test_final_page_nav_rows_and_headers(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            sb = storyboard_stage(proj) / "分镜文档" / "episode.json"
            data = json.loads(sb.read_text(encoding="utf-8"))
            base = data["shots"][0]
            data["shots"] = [dict(base, id="SH00%d" % index) for index in range(1, 5)]
            sb.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            win = self.tk.Tk(); win.withdraw()
            try:
                from desktop import Desktop
                from local_video import open_studio
                from tkinter import ttk
                d = Desktop(win, root=PROGRAM)
                d.root = proj
                d.studio = open_studio(proj)
                show_catalog_page_ready(d, PAGE["final"]); win.update_idletasks()
                buttons = []; labels = []; frames = []; trees = []
                def walk(w):
                    if isinstance(w, ttk.Button):
                        buttons.append(w)
                    if isinstance(w, ttk.Label):
                        labels.append(w)
                    if isinstance(w, ttk.LabelFrame):
                        frames.append(w)
                    if isinstance(w, ttk.Treeview):
                        trees.append(w)
                    for c in w.winfo_children():
                        walk(c)
                walk(d.content)
                self.assertNotIn("采用选中定稿", [str(b.cget("text")) for b in buttons])
                nav = [b for b in buttons if re.fullmatch(r"SH\d+", str(b.cget("text")))]
                self.assertEqual(len(nav), 4)
                self.assertEqual(len({b.grid_info().get("row") for b in nav}), 2)
                nav[0].invoke(); win.update_idletasks()
                styles = [str(b.cget("style")) for b in nav]
                self.assertEqual(styles.count("Tokens.Primary.TButton"), 1)
                self.assertEqual(styles[0], "Tokens.Primary.TButton")
                nav[3].invoke(); win.update_idletasks()
                styles = [str(b.cget("style")) for b in nav]
                self.assertEqual(styles.count("Tokens.Primary.TButton"), 1)
                self.assertEqual(styles[3], "Tokens.Primary.TButton")
                texts = [str(w.cget("text")) for w in labels]
                self.assertIn("镜头目录", texts)
                self.assertNotIn("已同步资产的分镜", texts)
                self.assertNotIn("目录：", texts)
                self.assertNotIn("分镜稿内容", [str(w.cget("text")) for w in frames])
                # 第 40 期第 2 条：第一栏改名「同步资产分镜」，创建时间前面多一栏「是否同步」。
                table = [w for w in trees if list(w["columns"]) == ["file", "sync", "time", "location"]]
                self.assertEqual(len(table), 1)
                self.assertEqual(table[0].heading("file", "text"), "同步资产分镜")
                self.assertEqual(table[0].heading("sync", "text"), "是否同步")
                self.assertEqual(table[0].heading("time", "text"), "创建时间")
                row = table[0].item(table[0].get_children()[0], "values")
                self.assertTrue(str(row[0]).endswith("·未同步"), "第一栏的格子里带着同步状态：%s" % row[0])
                self.assertEqual(str(row[1]), "未同步", "这一份还没同步资产")
                self.assertRegex(str(row[2]), r"^\d{2}-\d{2} \d{2}:\d{2}$")
                self.assertEqual(str(row[3]), "03初步分镜/分镜文档/episode.json")
            finally:
                win.destroy()

    def test_final_page_marks_the_synced_final(self):
        """第 40 期第 2 条：同步过资产的那一份（同目录里有 assets.json）写「已同步」与「·同步」。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            final_dir = storyboard_stage(proj) / "分镜文档" / "EP001_分镜定稿_20260921_101438"
            final_dir.mkdir(parents=True, exist_ok=True)
            source = storyboard_stage(proj) / "分镜文档" / "episode.json"
            (final_dir / "episode.json").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            (final_dir / "assets.json").write_text("{}", encoding="utf-8")     # 定稿＝分镜 ＋ 资产清单同目录
            (proj / "ui_settings.json").write_text(json.dumps({
                "adopted_storyboards": ["03初步分镜/分镜文档/episode.json",
                                        "03初步分镜/分镜文档/EP001_分镜定稿_20260921_101438/episode.json"],
                "frame_json": "03初步分镜/分镜文档/episode.json"}, ensure_ascii=False), encoding="utf-8")
            keep_storyboard_fresh(proj)
            win = self.tk.Tk(); win.withdraw()
            try:
                from desktop import Desktop
                from local_video import open_studio
                from tkinter import ttk
                d = Desktop(win, root=PROGRAM)
                d.root = proj
                d.studio = open_studio(proj)
                show_catalog_page_ready(d, PAGE["final"]); win.update_idletasks()
                trees = []
                def walk(w):
                    if isinstance(w, ttk.Treeview):
                        trees.append(w)
                    for c in w.winfo_children():
                        walk(c)
                walk(d.content)
                table = [w for w in trees if list(w["columns"]) == ["file", "sync", "time", "location"]][0]
                rows = [table.item(item, "values") for item in table.get_children()]
                self.assertEqual(len(rows), 2, "已采用的这一份工作稿与那一份定稿都在表里")
                state = {str(row[1]): str(row[0]) for row in rows}
                self.assertEqual(sorted(state), ["已同步", "未同步"])
                self.assertTrue(state["已同步"].endswith("·同步"), state["已同步"])
                self.assertTrue(state["未同步"].endswith("·未同步"), state["未同步"])
                # 第 65 期任务 5：只有同步过的那一行上高亮，未同步的初稿保持普通底色。
                tagged = {str(table.item(item, "values")[1]): list(table.item(item, "tags"))
                          for item in table.get_children()}
                self.assertEqual(tagged["已同步"], ["completed"], "已同步的行才有高亮")
                self.assertEqual(tagged["未同步"], [], "没同步的初稿不高亮")
            finally:
                win.destroy()


    def test_storyboard_switch_never_inflates_the_footer_row(self):
        """切换分镜重建页面时，底部按钮行不能先按「宽度 1」排一遍。

        FlowBar 在控件还没被几何管理器映射时 winfo_width() 是 1，按 1 像素排版会把每个按钮
        各占一行：底部行瞬间从 38 长到 258 像素，内容框被挤扁再弹回来——用户看到的就是
        「鼠标向下滑动、文件切换时内容抖动」。这里逐次记录底部行被排成的高度，要求任何一次
        过渡都不高于它最终的高度。
        """
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        import storyboard_selection
        import responsive_ui
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            sb_dir = storyboard_stage(proj) / "分镜文档"
            template = json.loads((sb_dir / "episode.json").read_text(encoding="utf-8"))
            for name, count in (("第二集", 19), ("第三集", 3)):
                episode = json.loads(json.dumps(template))
                episode["episode_id"] = name
                episode["shots"] = [dict(episode["shots"][0], id="SH%03d" % index) for index in range(1, count + 1)]
                path = sb_dir / (name + ".json")
                path.write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")
                storyboard_selection.adopt(proj, [path])
            win = self.tk.Tk()
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
            d.show(PAGE["keyframe"]); win.update()
            original_layout = responsive_ui.FlowBar.layout
            heights = {}
            def layout(bar):
                original_layout(bar)
                heights.setdefault(str(bar), []).append(int(bar.cget("height")))
            responsive_ui.FlowBar.layout = layout
            self.addCleanup(setattr, responsive_ui.FlowBar, "layout", original_layout)
            def selector():
                found = []
                def walk(widget):
                    if isinstance(widget, ttk.Combobox):
                        found.append(widget)
                    for child in widget.winfo_children():
                        walk(child)
                walk(d.content.winfo_children()[0])      # 选择分镜行是页面的第一个子控件
                return found[0]
            before = d.current_frame_json()
            combo = selector()
            target_index = next(index for index in range(len(combo.cget("values"))) if index != combo.current())
            heights.clear()
            combo.current(target_index)
            combo.event_generate("<<ComboboxSelected>>")
            for _ in range(10):
                win.update()
            self.assertNotEqual(d.current_frame_json(), before)          # 确实换了文件并重建
            self.assertGreaterEqual(len(heights), 2)                     # 底部两行都重排过
            for path, values in heights.items():
                self.assertEqual(max(values), values[-1], path)          # 没有比最终高度更高的过渡


    def test_source_selector_wheel_does_not_switch_episode(self):
        """下游页「选择分镜」下拉框：页面重建后仍带滚轮标签，滚轮只滚页面、不切换分镜。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        import storyboard_selection
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            sb_dir = storyboard_stage(proj) / "分镜文档"
            template = json.loads((sb_dir / "episode.json").read_text(encoding="utf-8"))
            for name, count in (("第二集", 6), ("第三集", 3)):
                episode = json.loads(json.dumps(template))
                episode["episode_id"] = name
                episode["shots"] = [dict(episode["shots"][0], id="SH%03d" % index) for index in range(1, count + 1)]
                path = sb_dir / (name + ".json")
                path.write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")
                storyboard_selection.adopt(proj, [path])
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
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
            d.show(PAGE["keyframe"]); win.update()
            def selector():
                found = []
                def walk(widget):
                    if isinstance(widget, ttk.Combobox):
                        found.append(widget)
                    for child in widget.winfo_children():
                        walk(child)
                walk(d.content.winfo_children()[0])      # 选择分镜行是页面的第一个子控件
                return found[0]
            selector().current(2)
            selector().event_generate("<<ComboboxSelected>>")
            for _ in range(3):
                win.update()
            rebuilt = selector()
            # 页面重建后新下拉框必须重新补挂滚轮标签，否则滚轮会落到 TCombobox 自己的绑定上
            self.assertIn("DramaPageWheel", rebuilt.bindtags())
            before = d.current_frame_json()
            rebuilt.current(2)
            rebuilt.event_generate("<MouseWheel>", delta=120, x=5, y=5)
            for _ in range(3):
                win.update()
            self.assertEqual(d.current_frame_json(), before)
            self.assertEqual(selector().current(), 2)
            # 就算页面滚轮标签万一没补上（历史 BUG 场景），下拉框自身的绑定也拦得住滚轮改选
            bare = selector()
            bare.bindtags(tuple(tag for tag in bare.bindtags() if tag != "DramaPageWheel"))
            shows = []
            original_show = desktop_module.Desktop.show
            desktop_module.Desktop.show = lambda self, index, video_mode=None: (shows.append(index), original_show(self, index, video_mode))[1]
            self.addCleanup(setattr, desktop_module.Desktop, "show", original_show)
            bare.event_generate("<MouseWheel>", delta=-120, x=5, y=5)
            for _ in range(3):
                win.update()
            self.assertEqual(selector().current(), 2)
            self.assertEqual(d.current_frame_json(), before)
            self.assertEqual(shows, [])


    def test_source_selector_display_snaps_back_when_switch_is_blocked(self):
        """后台任务占用时切换分镜：只提示不切换，下拉框必须回到真实文件，不能停在新文件名上。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        from unittest.mock import patch
        import storyboard_selection
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            sb_dir = storyboard_stage(proj) / "分镜文档"
            template = json.loads((sb_dir / "episode.json").read_text(encoding="utf-8"))
            second = dict(template, episode_id="第二集", shots=[dict(template["shots"][0], id="SH010")])
            path = sb_dir / "第二集.json"
            path.write_text(json.dumps(second, ensure_ascii=False), encoding="utf-8")
            storyboard_selection.adopt(proj, [path])
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
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
            d.show(PAGE["keyframe"]); win.update()
            def selector():
                found = []
                def walk(widget):
                    if isinstance(widget, ttk.Combobox):
                        found.append(widget)
                    for child in widget.winfo_children():
                        walk(child)
                walk(d.content.winfo_children()[0])
                return found[0]
            start = selector().current()
            before = d.current_frame_json()
            errors = []
            d.worker = True                                   # 模拟后台任务正在跑：safe 只提示不切换
            with patch.object(desktop_module.messagebox, "showerror", lambda *a, **k: errors.append(a[1] if len(a) > 1 else "")):
                selector().current(1 - start)
                selector().event_generate("<<ComboboxSelected>>")
                for _ in range(3):
                    win.update()
            d.worker = False
            # UI 批次 2：可恢复错误默认非模态（产品裁决 2026-10-18）
            self.assertEqual(errors, [], "可恢复错误默认非模态：不得弹系统模态框")
            self.assertEqual(d.status.get(), "当前操作尚未结束，请稍后",
                             "同一条错误文本必须落在非模态状态栏")
            self.assertEqual(d.current_frame_json(), before)   # 当前分镜没有被切换
            self.assertEqual(selector().current(), start)      # 下拉框显示也回到真实文件


    def test_frame_prompt_window_copies_and_closes(self):
        """首帧图片提示词窗口：点「复制提示词」写入剪贴板并关窗（与资产提示词窗口同一行为）。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
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
            d.show(PAGE["keyframe"]); win.update()
            widgets = []
            def walk(widget):
                widgets.append(widget)
                for child in widget.winfo_children():
                    walk(child)
            walk(d.content)
            table = [w for w in widgets if isinstance(w, ttk.Treeview) and "prompt" in w["columns"]][0]
            table.selection_set(table.get_children()[0])
            win.update()
            buttons = {str(w.cget("text")): w for w in widgets if isinstance(w, ttk.Button)}
            buttons["查看首帧提示词"].invoke(); win.update()
            popups = popup_windows(win, self.tk)
            self.assertEqual(len(popups), 1)
            popup = popups[0]
            expected = [w for w in popup.content.winfo_children() if isinstance(w, self.tk.Text)][0].get("1.0", "end-1c")
            import clipboard_lock
            with clipboard_lock.hold():                             # 第 65 期第 12 条：剪贴板是全机器共用的一块，几路并行要排队用
                [w for w in popup.actions.winfo_children() if isinstance(w, ttk.Button) and str(w.cget("text")) == "复制提示词"][0].invoke()
                win.update()
                self.assertFalse(popup.winfo_exists())          # 复制成功后关窗
                self.assertEqual(win.clipboard_get(), expected)
            self.assertIn("已复制", d.status.get())



    def test_frame_prompt_window_disables_copy_when_empty(self):
        """没有首帧提示词时：窗口保持打开，复制按钮禁用，剪贴板不被写入。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            source = storyboard_stage(proj) / "分镜文档" / "episode.json"
            episode = json.loads(source.read_text(encoding="utf-8"))
            for shot in episode["shots"]:
                shot.pop("frame_prompt", None)
            source.write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
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
            d.show(PAGE["keyframe"]); win.update()
            widgets = []
            def walk(widget):
                widgets.append(widget)
                for child in widget.winfo_children():
                    walk(child)
            walk(d.content)
            table = [w for w in widgets if isinstance(w, ttk.Treeview) and "prompt" in w["columns"]][0]
            table.selection_set(table.get_children()[0])
            win.update()
            buttons = {str(w.cget("text")): w for w in widgets if isinstance(w, ttk.Button)}
            buttons["查看首帧提示词"].invoke(); win.update()
            popups = popup_windows(win, self.tk)
            self.assertEqual(len(popups), 1)
            popup = popups[0]
            import clipboard_lock                                     # # 第 65 期第 12 条：剪贴板是全机器共用的一块，几路并行要排队用
            guard = clipboard_lock.hold(); guard.__enter__()
            self.addCleanup(lambda: guard.__exit__(None, None, None))
            win.clipboard_clear(); win.clipboard_append("哨兵"); win.update()
            button = [w for w in popup.actions.winfo_children() if isinstance(w, ttk.Button) and str(w.cget("text")) == "复制提示词"][0]
            self.assertEqual(str(button.cget("state")), "disabled")
            button.invoke(); win.update()
            self.assertTrue(popup.winfo_exists())
            self.assertEqual(win.clipboard_get(), "哨兵")
            self.assertIn("还没有首帧图片提示词", d.status.get())
            hints = [str(w.cget("text")) for w in popup.content.winfo_children() if isinstance(w, ttk.Label)]
            self.assertTrue(any("没有可复制的首帧图片提示词" in text for text in hints))   # 窗口内写明原因


    def test_asset_prompt_window_copies_and_closes(self):
        """资产提示词窗口：与首帧图片提示词窗口同一套实现，复制成功后关窗。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
            def quiet_destroy():
                try:
                    win.destroy()
                except Exception:
                    pass
            self.addCleanup(quiet_destroy)
            from desktop import Desktop
            from local_video import open_studio
            from asset_reference_prompts import show_prompt, display_prompt
            d = Desktop(win, root=PROGRAM)
            d.root = proj
            d.studio = open_studio(proj)
            d.show(PAGE["assets"]); win.update()
            asset = {"name": "测试角色", "image_prompt": "一只猫在窗边", "negative_prompt": "模糊"}
            show_prompt(d, "CHAR_001", asset); win.update()
            popups = popup_windows(win, self.tk)
            self.assertEqual(len(popups), 1)
            popup = popups[0]
            import clipboard_lock
            with clipboard_lock.hold():                             # 第 65 期第 12 条：剪贴板是全机器共用的一块，几路并行要排队用
                [w for w in popup.actions.winfo_children() if isinstance(w, ttk.Button) and str(w.cget("text")) == "复制提示词"][0].invoke()
                win.update()
                self.assertFalse(popup.winfo_exists())          # 复制成功后关窗
                self.assertEqual(win.clipboard_get(), display_prompt(asset))
            self.assertIn("已复制", d.status.get())

    def test_the_asset_table_shows_thumbnails_only_in_the_import_column(self):
        """第 53 期第 3 条：缩略图只留在「资产图片」那一列，同一行的「名称」列退回纯文字。

        第 52 期把「名称」「资产图片」两列都盖上了同一张图——用户判它重复，点名删掉「名称」
        列的那张；「资产图片」列照旧摆缩略图（解不开图就退回原来写的文字）。
        第 57 期第 6 条：这一列改名「资产图片」（原来叫「导入图片」）。
        """
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        # 开机那个 after(150) 的「接着上次的项目」回调：这一页建得慢（要解真 PNG 缩略图），
        # 回调会在 update() 里到期、把内容重建回第 1 步——与相邻几个用例一样先掐掉它。
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_populated_project(td)
            win = self.tk.Tk(); win.withdraw()
            try:
                from desktop import Desktop
                from local_video import open_studio
                d = Desktop(win, root=PROGRAM)
                d.root = proj
                d.studio = open_studio(proj)
                base = d.asset_base()
                # 只把 CHAR_001 换成真能解码的 PNG；LOC_001 留着那种只有魔数的假图，
                # 正好把「解不开就退回文字」这条退路一起盯住。
                (base / "assets" / "characters" / "CHAR_001.png").write_bytes(real_png())
                d.show(PAGE["assets"])
                win.deiconify(); win.update()
                table = d.asset_table
                self.assertEqual(str(table.heading("name", "text")), "名称")
                self.assertEqual(str(table.heading("status", "text")), "资产图片")
                self.assertNotIn("点击修改", str(table.heading("name", "text")))
                self.assertEqual(int(ttk.Style(table).lookup("Asset.Treeview", "rowheight")),
                                 desktop_doc.ASSET_ROW_HEIGHT)
                covered = table.cell_images.refresh()
                rows = table.get_children()
                self.assertTrue(rows, "这个项目里得有资产，用例才测得着")
                for row in rows:
                    # CHAR_001 是真能解码的 PNG（盖得上），LOC_001 那块只有魔数（盖不上）。
                    # 第 54 期第 3 条起，盖上的那一格连状态文字都不写了——所以这里按行名算，
                    # 不再拿格子里的文字当判据。
                    should = row == "CHAR_001"
                    self.assertNotIn((row, "#2"), covered, "「名称」列不再盖缩略图：" + row)
                    self.assertEqual((row, "#3") in covered, should, row)
                self.assertIn(("CHAR_001", "#3"), covered, "已导入且有真图的那一行得盖上缩略图")
                label = table.cell_images.labels[("CHAR_001", "#3")]
                self.assertTrue(str(label.cget("image")), "「导入图片」那一格盖的是缩略图")
                self.assertEqual(str(label.cget("text")), "", "导入图片那一格只盖图")
                self.assertEqual(str(table.set("CHAR_001", "name")), "主角", "「名称」列留着原来的文字")
                self.assertEqual(str(table.set("CHAR_001", "status")), "",
                                 "第 54 期第 3 条：盖上图的格子不再写「已导入」")
                self.assertEqual(str(table.set("LOC_001", "status")), "已导入",
                                 "没图上来的格子照旧写状态文字")
                # 第 57 期第 5 条：资产图片那一格停上去也放大（这一页是另外几页的样板）。
                self.assertTrue(callable(table.cell_images.zoom), "资产图片那一格要能停上去放大")
                big = table.cell_images.zoom("CHAR_001", "#3")
                self.assertTrue(big is not None and int(big.width()) > 0, "放大图得解得出来")
            finally:
                win.destroy()

    def _open_page_with_real_frame(self, td, index, width=1180, height=760, video_mode=None):
        """按真 PNG 首帧开一页：缩略图那一链只有能解码的图才测得着。"""
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        proj = make_adopted_project(td)
        frames = storyboard_stage(proj) / "frames"
        frames.mkdir(parents=True, exist_ok=True)
        (frames / "SH001.png").write_bytes(real_png(90, 60))
        win = self.tk.Tk(); win.geometry("%dx%d+40+40" % (width, height))
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
        if video_mode is None:
            d.show(index)
        else:
            d.show(index, video_mode=video_mode)
        win.update()
        return d, proj, win

    def test_the_video_table_highlights_the_asset_and_frame_columns(self):
        """第 53 期第 1 条：07 镜头内容框的「选择资产」「首帧」两格要能悬停高亮。

        高亮那一层是盖在格子上的 Label，鼠标因此落不到树上——单击／右键得原样重发给树
        （切勾选、点开「选择资产」下拉框、弹本页的镜头菜单全是树自己在管）。
        """
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            d, proj, win = self._open_page_with_real_frame(td, PAGE["video"], video_mode="local")
            app = d.video
            self.assertEqual(sorted(app.tree.cell_hover.columns), ["#3", "#5"],
                             "#3 是「选择资产」、#5 是「首帧」")
            self.assertTrue(app.tree.cell_hover.hover_only, "这一页只借它高亮，不借它打开")
            self.assertTrue(app.tree.cell_hover.forward_bind_ids, "单击／右键要能重发给树")
            for column, want in (("#3", "CHAR_001"),):
                box = app.tree.bbox("SH001", column)
                self.assertTrue(box, "内容框得真摆出来才谈得上悬停：" + column)
                app.tree.cell_hover.at(box[0] + box[2] // 2, box[1] + box[3] // 2)
                self.assertEqual(app.tree.cell_hover.active, ("SH001", column))
                self.assertIn(want, str(app.tree.cell_hover.overlay.cget("text")),
                              "高亮那一层要带着这一格的内容：" + column)
            # 第 54 期第 3 条：「首帧」那一格盖了缩略图就只留图，原来写的「已就绪」不再显示。
            self.assertEqual(str(app.tree.set("SH001", "#5")), "",
                             "盖上缩略图之后，格子里不再写「已就绪」")
            # 第 55 期第 2 条：「首帧」那一格归盖图那一层，不再走高亮——原来高亮层也带着
            # 缩略图，两层叠在同一格上互相顶掉（用户看到的就是「显示不对」）。
            self.assertIn("#5", app.tree.cell_hover.plain, "「首帧」这一列交给盖图那一层")
            self.assertIn(("SH001", "#5"), app.cell_images.labels, "首帧那一格盖的是缩略图")
            box = app.tree.bbox("SH001", "#5")
            app.tree.cell_hover.at(box[0] + box[2] // 2, box[1] + box[3] // 2)
            self.assertIsNone(app.tree.cell_hover.active, "盖着缩略图的格子不再高亮")

    def test_the_video_table_shows_the_first_frame_thumbnail(self):
        """第 53 期第 5 条：07 镜头内容框的「首帧」列摆缩略图（行高跟着放大）。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        import app as app_module
        with tempfile.TemporaryDirectory() as td:
            d, proj, win = self._open_page_with_real_frame(td, PAGE["video"], video_mode="local")
            app = d.video
            self.assertEqual(tuple(app.cell_images.columns), ("#5",), "缩略图只盖「首帧」那一列")
            self.assertEqual(int(ttk.Style(app.tree).lookup("Shot.Treeview", "rowheight")),
                             app_module.SHOT_ROW_HEIGHT, "行高要放到装得下缩略图")
            covered = app.cell_images.refresh()
            self.assertIn(("SH001", "#5"), covered, "已就绪的首帧要在那一列盖上缩略图")
            label = app.cell_images.labels[("SH001", "#5")]
            self.assertTrue(str(label.cget("image")), "盖上去的得是图")
            self.assertEqual(str(label.cget("text")), "", "那一格只盖图")
            self.assertGreaterEqual(int(label.place_info().get("height") or 0),
                                    app_module.SHOT_THUMB_SIZE, "格子得留得下一整张缩略图")
            # 第 57 期第 5 条：鼠标停上去另解一张大图（够看清人物与背景），不是把小图拉大。
            self.assertTrue(callable(app.cell_images.zoom), "首帧那一格要能停上去放大")
            big = app.cell_images.zoom("SH001", "#5")
            self.assertTrue(big is not None and int(big.width()) > 0, "放大图得解得出来")

    def test_the_previs_table_highlights_every_cell(self):
        """第 53 期第 2 条：白模预演那张镜头内容框的每一格都能悬停高亮。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            adopt_storyboard_fixture(proj)
            win = self.tk.Tk(); win.geometry("1180x760+40+40")
            def quiet_destroy():
                try:
                    win.destroy()
                except Exception:
                    pass
            self.addCleanup(quiet_destroy)
            import desktop as desktop_module
            original = desktop_module.Desktop.choose_project
            desktop_module.Desktop.choose_project = lambda self: None
            self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
            from desktop import Desktop
            from local_video import open_studio
            d = Desktop(win, root=PROGRAM)
            d.root = proj
            d.studio = open_studio(proj)
            d.show(PAGE["previs"]); win.update()
            trees = []
            def walk(w):
                if isinstance(w, ttk.Treeview):
                    trees.append(w)
                for child in w.winfo_children():
                    walk(child)
            walk(d.content)
            table = [t for t in trees
                     if list(t["columns"]) == ["id", "title", "duration", "complexity", "route", "status"]]
            self.assertEqual(len(table), 1, "白模预演那张表")
            tree = table[0]
            hover = getattr(tree, "cell_hover", None)
            self.assertIsNotNone(hover, "这一页的每一格都要挂上悬停高亮")
            self.assertEqual(hover.columns, {"#1", "#2", "#3", "#4", "#5", "#6"})
            self.assertTrue(hover.forward_bind_ids, "单击／右键要能重发给树（打勾选那条路）")
            row = tree.get_children()[0]
            for index, want in enumerate(tree.item(row, "values"), 1):
                box = tree.bbox(row, "#%d" % index)
                self.assertTrue(box, "内容框得真摆出来：" + "#%d" % index)
                hover.at(box[0] + box[2] // 2, box[1] + box[3] // 2)
                self.assertEqual(hover.active, (row, "#%d" % index))
                self.assertEqual(str(hover.overlay.cget("text")), str(want))

    def test_the_frame_table_shows_thumbnails_in_the_file_column(self):
        """第 53 期第 5 条：08 首帧管理「图片文件(点击查看)」那一列摆首帧缩略图。

        解不开的图（jpg 等 Tk 不认的）照旧退回原来写的文件名——这一条一并盯住。
        """
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        import desktop as desktop_doc
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_populated_project(td)
            (storyboard_stage(proj) / "frames" / "SH001.png").write_bytes(real_png(90, 60))
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
            d.show(PAGE["keyframe"]); win.update()
            trees = []
            def walk(w):
                if isinstance(w, ttk.Treeview):
                    trees.append(w)
                for child in w.winfo_children():
                    walk(child)
            walk(d.content)
            table = [t for t in trees if getattr(t, "cell_images", None) is not None
                     and list(t["columns"]) == ["id", "title", "duration", "status", "file", "prompt"]]
            self.assertEqual(len(table), 1, "首帧管理那张表")
            table = table[0]
            self.assertEqual(tuple(table.cell_images.columns), ("#5",), "缩略图盖在「图片文件」那一列")
            self.assertEqual(int(ttk.Style(table).lookup("Frame.Treeview", "rowheight")),
                             desktop_doc.ASSET_ROW_HEIGHT, "行高要放到装得下缩略图")
            covered = table.cell_images.refresh()
            self.assertIn(("SH001", "#5"), covered, "有真首帧的那一镜要盖上缩略图")
            label = table.cell_images.labels[("SH001", "#5")]
            self.assertTrue(str(label.cget("image")))
            self.assertEqual(str(label.cget("text")), "")
            # 第 54 期第 3 条：盖上了图，格子里那行文件名就不再显示（用户点名删掉）。
            self.assertEqual(str(table.set("SH001", "file")), "",
                             "盖上缩略图之后，格子里不再写文件名")
            # 第 57 期第 5 条：缩略图停上去同样放大（所有缩略图一套规矩）。
            self.assertTrue(callable(table.cell_images.zoom), "首帧那一格要能停上去放大")
            big = table.cell_images.zoom("SH001", "#5")
            self.assertTrue(big is not None and int(big.width()) > 0, "放大图得解得出来")
            # 解不开的图（只有魔数）退回文字：assets 那一页的 CHAR_001 就是这么一块假图。
            # 行是在建表时按「这张图能不能解开」写好的，所以按页面自己的「刷新首帧列表」重建一遍。
            (storyboard_stage(proj) / "frames" / "SH001.png").write_bytes(PNG)
            def walk_buttons(w):
                found = []
                for child in w.winfo_children():
                    if isinstance(child, ttk.Button) and str(child.cget("text")) == "刷新首帧列表":
                        found.append(child)
                    found.extend(walk_buttons(child))
                return found
            refresh_button = walk_buttons(d.content)
            self.assertEqual(len(refresh_button), 1, "得找得到「刷新首帧列表」那颗按钮")
            refresh_button[0].invoke(); win.update()
            self.assertNotIn(("SH001", "#5"), table.cell_images.refresh(),
                             "图解不开就不盖，退回原来写的文件名")
            self.assertIn("SH001.png", str(table.set("SH001", "file")),
                          "盖不上图的格子照旧写文件名")

    def test_the_final_table_columns_follow_the_window(self):
        """第 53 期第 4 条：分镜定稿「同步资产分镜」那四列的宽度跟着内容框的宽度走。

        改前只有「项目内位置」那一列动，前三列卡在写死的初值上；现在四列一起收放，
        加宽时先把被裁掉的内容补回来，再有富余按比例分掉。
        """
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
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
            def widths():
                # 每一轮 show() 都会把上一张表拆掉重建，所以宽度要在这一轮里当场读下来。
                show_catalog_page_ready(d, PAGE["final"]); win.update()
                trees = []
                def walk(w):
                    if isinstance(w, ttk.Treeview):
                        trees.append(w)
                    for child in w.winfo_children():
                        walk(child)
                walk(d.content)
                table = [t for t in trees
                         if list(t["columns"]) == ["file", "sync", "time", "location"]]
                self.assertEqual(len(table), 1, "分镜定稿那张表")
                tree = table[0]
                far = tree.bbox(tree.get_children()[0], "#4")       # 最后一列「项目内位置」
                return (int(tree.winfo_width()),
                        [int(tree.column(c, "width")) for c in tree["columns"]],
                        far[0] + far[2])
            win.geometry("820x760+40+40")
            narrow_box, narrow_widths, narrow_edge = widths()
            win.geometry("1420x760+40+40")
            wide_box, wide_widths, _ = widths()
            self.assertEqual(narrow_edge, narrow_box - 2,
                             "四列正好铺满内容框（右边不留空白带，也不顶出去）")
            self.assertGreater(wide_box, narrow_box, "窗口真被放大了，后面的断言才算数")
            changed = [index for index, pair in enumerate(zip(narrow_widths, wide_widths))
                       if pair[0] != pair[1]]
            self.assertEqual(len(changed), 4,
                             "窗口一变，四列都得跟着动（实测改前只有最后一列动）：%r → %r"
                             % (narrow_widths, wide_widths))
            self.assertTrue(all(wide_widths[i] > narrow_widths[i] for i in range(4)),
                            "窗口变宽每一列都要更宽：%r → %r" % (narrow_widths, wide_widths))

    def test_readonly_combobox_ignores_mouse_wheel(self):
        """只读下拉框不再被滚轮改选：TCombobox 类级补丁拦下改值，可编辑下拉框保持 Tk 默认行为。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            win = self.tk.Tk(); win.geometry("900x600+40+40")
            def quiet_destroy():
                try:
                    win.destroy()
                except Exception:
                    pass
            self.addCleanup(quiet_destroy)
            from desktop import Desktop
            d = Desktop(win, root=PROGRAM)
            d.root = proj
            # 补丁只装一次，并且改名必须留在同一命名空间：原过程内部调用 SelectEntry 等非限定名命令。
            self.assertEqual(win.tk.eval("info commands ::ttk::combobox::ScrollOriginal"),
                             "::ttk::combobox::ScrollOriginal")
            popup = self.tk.Toplevel(win); popup.geometry("320x140+300+300")
            values = ["第%d集" % index for index in range(20)]
            readonly = ttk.Combobox(popup, values=values, state="readonly"); readonly.current(3); readonly.pack()
            editable = ttk.Combobox(popup, values=values); editable.current(3); editable.pack()
            win.update()
            readonly.event_generate("<MouseWheel>", delta=-120, x=5, y=5)
            editable.event_generate("<MouseWheel>", delta=-120, x=5, y=5)
            win.update()
            self.assertEqual(readonly.current(), 3)
            self.assertEqual(editable.current(), 4)


    def test_open_combobox_wheel_scrolls_list_without_rebuild(self):
        """「选择分镜」展开后滚轮只滚动列表：不换选项、不重建页面。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        import storyboard_selection
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            sb_dir = storyboard_stage(proj) / "分镜文档"
            template = json.loads((sb_dir / "episode.json").read_text(encoding="utf-8"))
            episode = json.loads(json.dumps(template)); episode["episode_id"] = "第二集"
            path = sb_dir / "第二集.json"
            path.write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")
            storyboard_selection.adopt(proj, [path])
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
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
            d.show(PAGE["keyframe"]); win.update()
            found = []
            def walk(widget):
                if isinstance(widget, ttk.Combobox):
                    found.append(widget)
                for child in widget.winfo_children():
                    walk(child)
            walk(d.content.winfo_children()[0])
            combo = found[0]
            combo.configure(values=["第%d集" % index for index in range(30)]); combo.current(3); win.update()
            shows = []
            original_show = desktop_module.Desktop.show
            desktop_module.Desktop.show = lambda self, index, video_mode=None: (shows.append(index), original_show(self, index, video_mode))[1]
            self.addCleanup(setattr, desktop_module.Desktop, "show", original_show)
            win.tk.call("ttk::combobox::Post", str(combo)); win.update()
            listbox = str(win.tk.call("ttk::combobox::PopdownWindow", str(combo))) + ".f.l"
            before = win.tk.call(listbox, "yview")
            for _ in range(3):
                combo.event_generate("<MouseWheel>", delta=-120, x=5, y=5)
            win.update()
            self.assertEqual(combo.current(), 3)
            self.assertNotEqual(win.tk.call(listbox, "yview"), before)
            self.assertEqual(shows, [])
            # 事件直接落在 Tk 创建的下拉列表上（事件里的控件名是路径字符串）也要能滚动。
            scrolled = win.tk.call(listbox, "yview")
            win.tk.call("event", "generate", listbox, "<MouseWheel>", "-delta", 120, "-x", 5, "-y", 5)
            win.update()
            self.assertNotEqual(win.tk.call(listbox, "yview"), scrolled)
            self.assertEqual(combo.current(), 3)
            # 一格滚轮只走 Tk 类绑定那一次：再叠一次会一档跳两倍，看着就是内容抖动。
            win.tk.call(listbox, "yview", "moveto", 0); win.update()
            top = float(win.tk.call(listbox, "yview")[0])
            win.tk.call("event", "generate", listbox, "<MouseWheel>", "-delta", -120, "-x", 5, "-y", 5)
            win.update()
            moved = float(win.tk.call(listbox, "yview")[0]) - top
            native = float(win.tk.call(listbox, "yview")[0])
            win.tk.call(listbox, "yview", "scroll", 4, "units")
            one_native_step = float(win.tk.call(listbox, "yview")[0]) - native
            win.tk.call(listbox, "yview", "scroll", -4, "units")
            self.assertGreater(moved, 0)                            # 仍然滚得动
            self.assertLessEqual(moved, one_native_step + 1e-6)     # 不叠加第二次滚动
            self.assertEqual(combo.current(), 3)
            win.tk.call("ttk::combobox::Unpost", str(combo))



    def test_source_selector_skips_rebuild_for_same_choice(self):
        """选中同一份分镜不再重建整页；换一份时等下拉收起（after_idle）后再重建。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        import storyboard_selection
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            sb_dir = storyboard_stage(proj) / "分镜文档"
            template = json.loads((sb_dir / "episode.json").read_text(encoding="utf-8"))
            episode = json.loads(json.dumps(template)); episode["episode_id"] = "第二集"
            path = sb_dir / "第二集.json"
            path.write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")
            storyboard_selection.adopt(proj, [path])
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
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
            d.show(PAGE["keyframe"]); win.update()
            shows = []
            original_show = desktop_module.Desktop.show
            desktop_module.Desktop.show = lambda self, index, video_mode=None: (shows.append(index), original_show(self, index, video_mode))[1]
            self.addCleanup(setattr, desktop_module.Desktop, "show", original_show)
            def selector():
                found = []
                def walk(widget):
                    if isinstance(widget, ttk.Combobox):
                        found.append(widget)
                    for child in widget.winfo_children():
                        walk(child)
                walk(d.content.winfo_children()[0])
                return found[0]
            combo = selector()
            current = combo.current()
            combo.current(current)
            combo.event_generate("<<ComboboxSelected>>"); win.update()
            self.assertEqual(shows, [])
            other = 0 if current != 0 else 1
            combo.current(other)
            combo.event_generate("<<ComboboxSelected>>")
            self.assertEqual(shows, [])            # 不能在事件处理里同步重建整页
            win.update()
            self.assertEqual(shows, [PAGE["keyframe"]])




    def test_sanhu_auto_mode_persists_and_polls_auto_adopt(self):
        """全自动模式由三虎写入开关，主循环再把新分镜推进后续流程。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import project_settings, storyboard_selection
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            template = json.loads((storyboard_stage(proj) / "分镜文档" / "episode.json").read_text(encoding="utf-8"))
            episode = json.loads(json.dumps(template)); episode["episode_id"] = "EP002"
            fresh = storyboard_stage(proj) / "分镜文档" / "EP002_T_分镜.json"
            fresh.write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
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
            show_catalog_page_ready(d, PAGE["storyboard"]); win.update()
            self.assertFalse(project_settings.auto_adopt(proj))
            # 建窗这一段在 8 路并行的全量自检里可能拖过 10 秒，而 10 秒正是 adopt_pending
            # 判「文件刚写入」的等待窗口：一超时，下面那条「先等写入完成」的断言就会随机红成
            # 「已经采用」。把写入时间重新顶到当下，让这条用例量的是新鲜度逻辑，不是机器快慢。
            os.utime(fresh, None)
            d.pet.set_mode('auto'); win.update()
            for name in __import__('pet_ui').AUTO_VARIABLE_NAMES:
                d.pet.auto_variable(name).set(False)
            d.pet.auto_variable('auto_adopt_var').set(True)
            self.assertTrue(project_settings.auto_adopt(proj))
            self.assertTrue(d.pet.should_auto_run('auto_adopt'))
            self.assertEqual(d.pet.mode, 'auto')
            # 资产先补齐：采用之后状态栏要能指出下一道人工闸口（分镜定稿页）
            (proj / "episode" / "assets").mkdir(exist_ok=True)
            (proj / "episode" / "assets.json").write_text(json.dumps({
                "CHAR_001": {"image": "assets/CHAR_001.png"},
                "LOC_001": {"image": "assets/LOC_001.png"}}, ensure_ascii=False), encoding="utf-8")
            for aid in ("CHAR_001", "LOC_001"):
                (proj / "episode" / "assets" / (aid + ".png")).write_bytes(b"\x89PNG\r\n\x1a\n")
            # 刚写入的分镜先等写入完成：本轮不采用，但记住它在等
            self.assertNotIn(fresh, storyboard_selection.adopted(proj))
            d.poll_auto_adopt()
            self.assertTrue(d.auto.adopt_pending)
            d.poll_auto_adopt()
            self.assertNotIn(fresh, storyboard_selection.adopted(proj))
            os.utime(fresh, (time.time() - 60, time.time() - 60))
            d.poll_auto_adopt(); win.update()
            self.assertIn(fresh, storyboard_selection.adopted(proj))
            self.assertIn(fresh.name, d.status.get())
            # 两份分镜都从 SH001 开始，编号与剧本顺序不一致：无人值守时只靠状态栏这句提示
            self.assertIn("重排镜头编号", d.status.get())
            # 采用之后资产已齐：状态栏必须指出下一道人工闸口（分镜定稿页），否则无人值守会静默停住
            self.assertIn("第07步", d.status.get())
            self.assertFalse(d.auto.adopt_pending)
            # 切回手动后主循环不再扫描：「手动采用分镜」保持手动。
            d.pet.set_mode('manual')
            d.poll_auto_adopt()
            self.assertIsNone(d.auto.adopt_signature)

    def test_startup_reconciliation_pulls_the_working_episode_back(self):
        """第 62 期任务 7：强制关闭后重开，第一拍把已完成的分镜同步回工作集。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import project_settings
        import storyboard_selection
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            target = storyboard_selection.adopted(proj)[-1]
            cfg = proj / "config.json"
            data = json.loads(cfg.read_text(encoding="utf-8")) if cfg.is_file() else {}
            data["episode_file"] = str(proj / "episode" / "episode.json")   # 崩在同步前后的那一份旧指针
            data["episode_dir"] = str(proj / "episode")
            cfg.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            keep_storyboard_fresh(proj)
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
            def quiet_destroy():
                try:
                    win.destroy()
                except Exception:
                    pass
            self.addCleanup(quiet_destroy)
            from desktop import Desktop
            from local_video import open_studio
            d = Desktop(win, root=PROGRAM)
            # 项目选择改为首帧后的 idle 调度；本用例只核验启动对账，
            # 不让尚未到期的启动提示覆盖对账结果。
            d.startup_controller.cancel()
            d.root = proj
            d.studio = open_studio(proj)
            self.assertTrue(d.auto.adopt_startup)
            d.poll_auto_adopt(); win.update()
            self.assertFalse(d.auto.adopt_startup, "对账一拍就该收工，不反复做")
            self.assertEqual(json.loads(cfg.read_text(encoding="utf-8"))["episode_file"], str(target))
            self.assertIn("同步到工作集", d.status.get())


    def test_sanhu_auto_mode_assembles_once_per_approval(self):
        """三虎全自动模式写入粗剪开关，整集验收后只自动拼接一次。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from agent.core import file_hash, save
        import engine as engine_module
        import project_settings
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
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
            d.show(PAGE["edit"]); win.update()
            d.cancel_timers(); d.pet.arm_auto = lambda: None
            self.assertFalse(project_settings.auto_edit(proj))
            d.pet.set_mode('auto'); win.update()
            for name in __import__('pet_ui').AUTO_VARIABLE_NAMES:
                d.pet.auto_variable(name).set(False)
            d.pet.auto_variable('auto_edit_var').set(True)
            self.assertTrue(project_settings.auto_edit(proj))
            self.assertTrue(d.pet.should_auto_run('edit'))
            started = []
            real_assemble = engine_module.Studio.assemble
            from project_stages import editing, exports
            engine_module.Studio.assemble = lambda self, **kw: (started.append(1), str(exports(proj) / "MASTER.mp4"))[1]
            self.addCleanup(setattr, engine_module.Studio, "assemble", real_assemble)
            d.poll_auto_edit()
            self.assertEqual(started, [])                    # 还有镜头没验收：不会启动拼接
            clip = proj / "data" / "clips" / "SH001.mp4"
            clip.parent.mkdir(parents=True, exist_ok=True); clip.write_bytes(b"fake-video")
            save(proj / "data" / "state.json", {"schema": 1, "shots": {"SH001": [{
                "version": 1, "state": "downloaded", "qc_pass": True, "review": "pass",
                "file": "data/clips/SH001.mp4", "sha256": file_hash(clip)}]}})
            d.poll_auto_edit()
            for _ in range(80):
                win.update()
                if not d.auto.edit_busy:
                    break
                time.sleep(0.05)
            d._tick_once()
            self.assertEqual(started, [1])
            self.assertIn("自动粗剪完成", d.status.get())
            marker = json.loads((editing(proj) / "自动粗剪.json").read_text(encoding="utf-8"))
            self.assertEqual(marker.get("master"), str(exports(proj) / "MASTER.mp4"))
            # 同一批验收结果只拼接一次：即便缓存被清掉，成片指纹也会拦下重复拼接
            d.auto.edit_signature = None
            d.poll_auto_edit()
            self.assertEqual(started, [1])


    def test_sanhu_auto_mode_persists_and_polls_handoff(self):
        """三虎全自动模式写入交接开关，整集验收后只整理一次。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import time
        from agent.core import file_hash, save
        import project_settings
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
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
            d.show(PAGE["edit"]); win.update()
            d.cancel_timers(); d.pet.arm_auto = lambda: None
            self.assertFalse(project_settings.auto_handoff(proj))
            d.pet.set_mode('auto'); win.update()
            for name in __import__('pet_ui').AUTO_VARIABLE_NAMES:
                d.pet.auto_variable(name).set(False)
            d.pet.auto_variable('auto_handoff_var').set(True)
            self.assertTrue(project_settings.auto_handoff(proj))
            self.assertTrue(d.pet.should_auto_run('delivery'))
            def settle():
                for _ in range(80):
                    win.update()
                    if not d.auto.handoff_busy:
                        break
                    time.sleep(0.05)
            from project_stages import editing
            folder = editing(proj) / "自动交接包"
            d.poll_auto_handoff()
            settle()
            self.assertFalse(folder.exists())              # 还有镜头没验收：不会动手
            clip = proj / "data" / "clips" / "SH001.mp4"
            clip.parent.mkdir(parents=True, exist_ok=True); clip.write_bytes(b"fake-video")
            save(proj / "data" / "state.json", {"schema": 1, "shots": {"SH001": [{
                "version": 1, "state": "downloaded", "qc_pass": True, "review": "pass",
                "file": "data/clips/SH001.mp4", "sha256": file_hash(clip)}]}})
            d.poll_auto_handoff()
            settle()
            d._tick_once()
            self.assertIn("自动交接包已整理", d.status.get())
            self.assertEqual(sorted(p.name for p in folder.iterdir()),
                             ["001_SH001.mp4", "交接包标记.json", "交接包清单.json", "导入剪映说明.txt", "镜头顺序.json"])
            manifest = json.loads((folder / "镜头顺序.json").read_text(encoding="utf-8"))
            self.assertEqual([row["shot"] for row in manifest], ["SH001"])
            marker = json.loads((editing(proj) / "自动交接.json").read_text(encoding="utf-8"))
            self.assertEqual(marker.get("folder"), str(folder))
            self.assertEqual(len(marker.get("digest")), 64)     # 成片指纹，用于「同一批验收只整理一次」
            # 同一批验收结果只整理一次：清掉签名缓存也由成片指纹拦下，目录不会被重建
            before = (folder / "镜头顺序.json").stat().st_mtime_ns
            d.auto.handoff_signature = None
            d.poll_auto_handoff()
            settle()
            self.assertEqual((folder / "镜头顺序.json").stat().st_mtime_ns, before)
            # 同名目录不是自动生成的：报错并保留用户目录，不覆盖也不删除
            (folder / "交接包标记.json").unlink()
            (editing(proj) / "自动交接.json").unlink()
            d.auto.handoff_signature = None
            d.poll_auto_handoff()
            settle()
            d._tick_once()
            self.assertTrue(folder.is_dir())
            self.assertEqual(sorted(p.name for p in folder.iterdir()),
                             ["001_SH001.mp4", "交接包清单.json", "导入剪映说明.txt", "镜头顺序.json"])
            self.assertIn("自动整理交接包未完成", d.status.get())


    def test_renumber_shots_button_fixes_script_order(self):
        """03 初步分镜「重排镜头编号」：批量分镜按完成顺序编号（EP002 拿到 SH020…）时，
        预览确认后按集号顺序重排，只改编号；编号本来就连续时只提示不改文件。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import messagebox, ttk
        import desktop as desktop_module
        original_choose = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original_choose)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            folder = storyboard_stage(proj) / "分镜文档"
            first = json.loads((folder / "episode.json").read_text(encoding="utf-8"))
            def episode(episode_id, ids):
                return dict(first, episode_id=episode_id,
                            shots=[dict(first["shots"][0], id=sid) for sid in ids])
            second = folder / "EP002.json"; second.write_text(json.dumps(episode("EP002", ["SH020", "SH021"]), ensure_ascii=False), encoding="utf-8")
            third = folder / "EP003.json"; third.write_text(json.dumps(episode("EP003", ["SH010"]), ensure_ascii=False), encoding="utf-8")
            keep_storyboard_fresh(proj)          # 三份分镜都得是「刚写的」，否则 normalize 会先改名
            win = self.tk.Tk(); win.geometry("1400x900+20+20")
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
            show_catalog_page_ready(d, PAGE["storyboard"]); win.update()
            buttons = []
            def walk(widget):
                if isinstance(widget, ttk.Button):
                    buttons.append(widget)
                for child in widget.winfo_children():
                    walk(child)
            walk(d.content)
            button = [w for w in buttons if str(w.cget("text")) == "重排镜头编号"]
            self.assertEqual(len(button), 1)
            asked = []
            import storyboard_files
            original_ask = storyboard_files.confirm
            storyboard_files.confirm = lambda _parent, title, message, **_kw: (asked.append((title, message)), True)[1]
            self.addCleanup(setattr, storyboard_files, "confirm", original_ask)
            original_async = d.async_                           # 后台任务换成同步执行，便于断言
            d.async_ = lambda fn, done=None: done(fn()) if done else fn()
            self.addCleanup(setattr, d, "async_", original_async)
            self.assertIn("重排镜头编号", d.shot_numbering_hint())   # 采用后/重排前都能被提示到
            button[0].invoke(); win.update()
            self.assertEqual(len(asked), 1)
            self.assertIn("镜头编号", asked[0][1])
            ids = json.loads((folder / "EP002.json").read_text(encoding="utf-8"))["shots"]
            self.assertEqual([shot["id"] for shot in ids], ["SH002", "SH003"])
            self.assertEqual([shot["id"] for shot in json.loads((folder / "EP003.json").read_text(encoding="utf-8"))["shots"]],
                             ["SH004"])
            self.assertEqual([shot["id"] for shot in json.loads((folder / "episode.json").read_text(encoding="utf-8"))["shots"]],
                             ["SH001"])
            self.assertIn("编号连续", d.status.get())
            self.assertEqual(d.shot_numbering_hint(), "")          # 修好后不再提示
            # 编号已经连续：不再弹确认框，也不动文件
            asked.clear()
            button[0].invoke(); win.update()
            self.assertEqual(asked, [])
            self.assertIn("无需重排", d.status.get())


    def test_page_build_failure_reports_instead_of_blank_page(self):
        """侧栏导航遇到页面构建失败要弹出原因：.pyw 启动没有控制台，空白页等于没有提示。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import messagebox
        import desktop as desktop_module
        original_choose = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original_choose)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            win = self.tk.Tk(); win.withdraw()
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
            shown = []
            original_error = messagebox.showerror
            messagebox.showerror = lambda title, message, **kw: shown.append((title, message))
            self.addCleanup(setattr, messagebox, "showerror", original_error)
            original_storyboard = Desktop.storyboard
            Desktop.storyboard = lambda self: (_ for _ in ()).throw(ValueError("分镜数据坏了"))
            self.addCleanup(setattr, Desktop, "storyboard", original_storyboard)
            d.go(PAGE["keyframe"])                   # Desktop.storyboard 当前对应首帧页
            # UI 批次 2：可恢复错误默认非模态（产品裁决 2026-10-18）
            self.assertEqual(shown, [], "可恢复错误默认非模态：不得弹系统模态框")
            self.assertEqual(d.status.get(), "分镜数据坏了",
                             "同一条错误文本必须落在非模态状态栏")
            with self.assertRaises(ValueError):
                d.show(PAGE["keyframe"])             # 程序内调用仍抛异常，测试不会漏掉真故障
            self.assertEqual(shown, [])


    def test_handoff_prefers_approved_take(self):
        """交接包取「已验收」的那一版：重新生成但还没验收的新版本不能混进包里，否则和成片对不上。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from agent.core import file_hash, save
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
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
            clips = proj / "data" / "clips"; clips.mkdir(parents=True, exist_ok=True)
            approved = clips / "SH001.mp4"; approved.write_bytes(b"approved-take")
            newer = clips / "SH001_v2.mp4"; newer.write_bytes(b"unapproved-take")
            def versions(*items):
                return {"schema": 1, "shots": {"SH001": list(items)}}
            take_v1 = {"version": 1, "state": "downloaded", "qc_pass": True, "review": "pass",
                       "file": "data/clips/SH001.mp4", "sha256": file_hash(approved)}
            take_v2 = {"version": 2, "state": "downloaded", "qc_pass": True, "review": "pending",
                       "file": "data/clips/SH001_v2.mp4", "sha256": file_hash(newer)}
            save(proj / "data" / "state.json", versions(take_v1, take_v2))
            out = d.handoff()
            self.assertEqual((out / "001_SH001.mp4").read_bytes(), b"approved-take")
            manifest = json.loads((out / "镜头顺序.json").read_text(encoding="utf-8"))
            self.assertEqual([row["review"] for row in manifest], ["pass"])
            # 一个已验收版本都没有时，该镜不进交接包（与成片同一口径，不再退回最新未验收版）；
            # 单镜全缺时 publish_bundle 如实报「没有已下载视频」。
            save(proj / "data" / "state.json", versions(take_v2))
            with self.assertRaisesRegex(ValueError, "没有已下载视频"):
                d.handoff()
            # 手动整理仍是一事一目录
            save(proj / "data" / "state.json", versions(take_v1))
            out2 = d.handoff()
            self.assertNotEqual(out, out2)
            # 就绪判定带上分镜文件：镜头编号与版本完全相同的另一份分镜不能沿用同一签名，
            # 否则第二集会被「签名没变」直接跳过，永远不粗剪也不整理交接包
            save(proj / "data" / "state.json", versions(take_v1))
            first_signature, first_digest = d.edit_ready()
            source = Path(d.studio.episode_path)
            copy = source.parent / "episode_copy.json"
            copy.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            d.studio.episode_path = copy
            second_signature, second_digest = d.edit_ready()
            self.assertNotEqual(first_signature, second_signature)
            self.assertEqual(first_digest, second_digest)   # 成片没用变，指纹本身可以相同


    def test_readiness_check_is_shared_between_auto_edit_and_handoff(self):
        """自动粗剪与自动交接共用一次整集哈希校验：同一批验收结果不该把整集成片哈希两遍。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from agent.core import file_hash, save
        import engine as engine_module
        import project_settings
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
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
            self.enable_sanhu_auto(d, "auto_edit_var", "auto_handoff_var")
            clip = proj / "data" / "clips" / "SH001.mp4"
            clip.parent.mkdir(parents=True, exist_ok=True); clip.write_bytes(b"fake-video")
            save(proj / "data" / "state.json", {"schema": 1, "shots": {"SH001": [{
                "version": 1, "state": "downloaded", "qc_pass": True, "review": "pass",
                "file": "data/clips/SH001.mp4", "sha256": file_hash(clip)}]}})
            real_assemble = engine_module.Studio.assemble
            engine_module.Studio.assemble = lambda self, **kw: str(export_stage(proj) / "MASTER.mp4")
            self.addCleanup(setattr, engine_module.Studio, "assemble", real_assemble)
            counts = [0]
            real_hash = engine_module.file_hash
            def counting(path):
                counts[0] += 1
                return real_hash(path)
            engine_module.file_hash = counting
            self.addCleanup(setattr, engine_module, "file_hash", real_hash)
            project_settings.set_auto_edit(proj, True)
            project_settings.set_auto_handoff(proj, True)
            d.edit_ready_signature = None
            d.poll_auto_edit()
            self.assertEqual(counts[0], 1, "同一批验收结果被整集哈希了 %d 次" % counts[0])
            # 粗剪与交接包都是 daemon 线程在写盘：先把这两步等到收尾，否则临时目录会在复制途中
            # 被清理，`with TemporaryDirectory()` 报 WinError 145「目录不是空的」——与功能对错无关。
            # 断言放在等待之前：这里要测的是「两个 poll 只算一次整集指纹」，等待不参与判断。
            self.assertTrue(settle_workers(d, win), "自动粗剪后台线程没有收尾")
            d.poll_auto_handoff()
            self.assertTrue(settle_workers(d, win), "自动交接包后台线程没有收尾")


    def test_auto_keyframe_sanhu_mode_persists_and_polls(self):
        """05 首帧自动链路由三虎模式启用，轮询只对缺首帧的镜头排队一次。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from unittest.mock import patch
        import keyframe_comfy
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
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
            d.show(PAGE["keyframe"]); win.update()
            self.assertFalse(d.pet.should_auto_run('keyframe'))
            d.poll_auto_keyframe()
            self.assertFalse(d.auto.keyframe_busy)
            # 只通过三虎模式入口开启自动制作，不让页面组件写入变量。
            d.pet.set_level = lambda *args, **kwargs: None
            d.pet.broadcast = lambda *args, **kwargs: None
            d.pet.refresh_menu_labels = lambda: None
            d.pet.set_mode('auto')
            self.assertTrue(d.pet.should_auto_run('keyframe'))
            # 自动模式下但这一镜还缺参考资产：整批都会被引擎逐镜跳过，所以不派发
            # （否则要白连一次、必要时还要启动 ComfyUI 等两分钟），只把原因写进状态栏
            started = []
            def fake_batch(source, log, stop=None):
                started.append(str(source)); log("批次日志")
                return "无人值守首帧批次结束：处理 1 镜，已生成 1 镜"
            with patch.object(keyframe_comfy, "auto_batch", fake_batch):
                d.poll_auto_keyframe()
                self.assertFalse(d.auto.keyframe_busy)
            self.assertEqual(started, [])
            # 签名同时记下「这一镜还缺几张参考图」：参考图补齐后清单变了，会自动再跑一轮
            self.assertEqual(d.auto.keyframe_signature[0], str(storyboard_stage(proj) / "分镜文档" / "episode.json"))
            self.assertEqual([sid for sid, _ in d.auto.keyframe_signature[1]], ["SH001"])
            self.assertEqual(d.auto.keyframe_signature[1][0][1], 2)
            self.assertIn("都无法生成", d.status.get())
            self.assertIn("缺少资产图片", d.status.get())      # 原因与引擎逐镜跳过时同一句话
            # 同一批缺参考资产镜头不重复提示，也不重复排队
            d.status.set("哨兵")
            with patch.object(keyframe_comfy, "auto_batch", fake_batch):
                d.poll_auto_keyframe()
            self.assertEqual(d.status.get(), "哨兵")
            self.assertEqual(started, [])
            # 参考图由无人值守批量资产补齐后清单就变了：同一镜自动再跑一轮，不会被缺参考图永久卡住
            assets = proj / "episode" / "assets" / "characters"; assets.mkdir(parents=True, exist_ok=True)
            for aid in ("CHAR_001", "LOC_001"):
                (assets / (aid + ".png")).write_bytes(b"PNG")
            (proj / "episode" / "assets.json").write_text(json.dumps({
                "CHAR_001": {"name": "主角", "image": "assets/characters/CHAR_001.png"},
                "LOC_001": {"name": "场景", "image": "assets/characters/LOC_001.png"}}, ensure_ascii=False), encoding="utf-8")
            with patch.object(keyframe_comfy, "auto_batch", fake_batch):
                d.poll_auto_keyframe()
                self.assertTrue(d.auto.keyframe_busy)
                again = d.auto.keyframe_queue.get(timeout=20)
            self.assertTrue(again[1]); self.assertEqual(again[3][1][0][1], 0)
            self.assertEqual(len(started), 1)     # 缺参考资产那次没派发，只在资产补齐后跑了一次
            baseline = len(started)   # 后段只关心「参考图齐了就不再空跑」
            d.auto.keyframe_busy = False; d.auto.keyframe_signature = again[3]
            frames = storyboard_stage(proj) / "frames"; frames.mkdir(exist_ok=True)
            (frames / "SH001.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            d.auto.keyframe_signature = None
            d.poll_auto_keyframe()
            self.assertFalse(d.auto.keyframe_busy)
            # 批次进行中（或有别的操作在跑）不重复排队
            (frames / "SH001.png").unlink()
            with patch.object(keyframe_comfy, "auto_batch", fake_batch):
                d.auto.keyframe_busy = True
                d.poll_auto_keyframe()
                self.assertEqual(len(started), baseline)
                d.auto.keyframe_busy = False
                d.worker = True
                d.poll_auto_keyframe()
                self.assertEqual(len(started), baseline)
                d.worker = False
            # 三虎切回手动后轮询直接返回并清掉已跑过的清单
            d.pet.set_mode('manual')
            d.poll_auto_keyframe()
            self.assertIsNone(d.auto.keyframe_signature)


    def test_auto_previs_sanhu_mode_dispatches_complex_once(self):
        """06 白模自动链路由三虎模式启用；复杂未就绪镜头只派一次，中等动作不代办。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from unittest.mock import patch
        import previs_routing, previs_automation
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
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
            d.show(PAGE["previs"]); win.update()
            d.poll_auto_previs()                                    # 开关关闭：什么都不做
            self.assertFalse(d.previs_jobs["busy"])
            d.pet.set_level = lambda *args, **kwargs: None
            d.pet.broadcast = lambda *args, **kwargs: None
            d.pet.refresh_menu_labels = lambda: None
            d.pet.set_mode('auto')
            # 本用例只覆盖白模派发；关闭三虎持有的首帧变量，避免命中另一用例专测的前置等待。
            d.pet.auto_variable('auto_first_frame_var').set(False)
            self.assertTrue(d.pet.should_auto_run('previs'))
            started = []
            def fake_start(project, source, ids, state, **_lifecycle):
                started.append([str(project), str(source), list(ids)])
                state["busy"] = True
            groups = {"simple": [], "medium": ["SH002"], "complex": ["SH001"]}
            ready_state = {"value": False}
            with patch.object(previs_routing, "partition", lambda project, source, ids: (dict(groups), {})), \
                 patch.object(previs_routing, "ready", lambda project, sid, source=None: ready_state["value"]), \
                 patch.object(previs_automation, "start", fake_start):
                d.auto.previs_due = 0
                d._tick_once()                                  # 主循环必须自己把这一批派出去
                self.assertEqual([row[2] for row in started], [["SH001"]])   # 中等动作不代办
                self.assertTrue(d.previs_jobs["busy"])
                self.assertIn("使用", d.status.get())
                # 任务跑完后，同一批「复杂未就绪」镜头不再重复派发
                d.previs_jobs["busy"] = False
                d.poll_auto_previs()
                self.assertEqual(len(started), 1)
                # 中等动作数量变化，不能让同一批复杂镜头被重复派发
                groups["medium"] = ["SH002", "SH003"]
                d.poll_auto_previs()
                self.assertEqual(len(started), 1)
                # 全部就绪后签名清空；日后把某个镜头的白模删掉（重新变成未就绪）要能再派一次
                ready_state["value"] = True
                d.poll_auto_previs()
                self.assertIsNone(d.auto.previs_signature)
                ready_state["value"] = False
                d.poll_auto_previs()
                self.assertEqual(len(started), 2)
            d.pet.set_mode('manual')
            d.poll_auto_previs()
            self.assertIsNone(d.auto.previs_signature)


    def test_auto_previs_waits_for_first_frame_stage(self):
        """无人值守顺序：首帧阶段也在跑时，白模要等这一镜首帧落盘再派发；首帧由人管的项目不被拦住。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from unittest.mock import patch
        import previs_routing, previs_automation
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
            def quiet_destroy():
                try:
                    win.destroy()
                except Exception:
                    pass
            self.addCleanup(quiet_destroy)
            from desktop import Desktop
            from local_video import open_studio
            from storyboard_paths import media_root
            d = Desktop(win, root=PROGRAM)
            d.root = proj
            d.studio = open_studio(proj)
            d.show(PAGE["previs"]); win.update()
            d.pet.set_level = lambda *args, **kwargs: None
            d.pet.broadcast = lambda *args, **kwargs: None
            d.pet.refresh_menu_labels = lambda: None
            d.pet.set_mode('auto')
            source = storyboard_stage(proj) / "分镜文档" / "episode.json"
            episode = json.loads(source.read_text(encoding="utf-8"))
            frame_path = media_root(source) / episode["shots"][0]["frame"]
            frame_path.unlink(missing_ok=True)
            started = []
            def fake_start(project, src, ids, state, **_lifecycle):
                started.append(list(ids)); state["busy"] = True
            groups = {"simple": [], "medium": [], "complex": ["SH001"]}
            with patch.object(previs_routing, "partition", lambda project, source, ids: (dict(groups), {})), \
                 patch.object(previs_routing, "ready", lambda project, sid, source=None: False), \
                 patch.object(previs_automation, "start", fake_start):
                d.poll_auto_previs()                      # 首帧还缺：先不建白模
                self.assertEqual(started, [])
                self.assertIn("待首帧", d.status.get())
                frame_path.parent.mkdir(parents=True, exist_ok=True)
                frame_path.write_bytes(b"\x89PNG\r\n\x1a\n")
                d.poll_auto_previs()                      # 首帧落盘：这一镜才派出去
                self.assertEqual(started, [["SH001"]])
                # 首帧自动变量关掉后，白模不应再被首帧阶段拦住。
                d.pet.auto_variable('auto_first_frame_var').set(False)
                d.auto.previs_signature = None
                d.previs_jobs["busy"] = False
                frame_path.unlink()
                d.poll_auto_previs()
                self.assertEqual(started, [["SH001"], ["SH001"]])


    def test_final_storyboard_hint_points_to_step07(self):
        """工作稿引用的资产都已导入时提示可到分镜定稿页生成定稿；资产没齐或已经是定稿时不提示。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from unittest.mock import patch
        import asset_batch_state_service
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
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
            source = storyboard_stage(proj) / "分镜文档" / "episode.json"
            with patch.object(asset_batch_state_service, "ready_asset_ids", lambda base: {"CHAR_001", "LOC_001"}):
                hint = d.final_storyboard_hint()
            self.assertIn("第07步", hint)
            self.assertIn("回收站", hint)                      # 提示里写明会移动工作稿
            with patch.object(asset_batch_state_service, "ready_asset_ids", lambda base: set()):
                self.assertEqual(d.final_storyboard_hint(), "")   # 资产没齐：先补资产
            final_dir = storyboard_stage(proj) / "分镜文档" / "定稿_EP001_测试"
            final_dir.mkdir(parents=True)
            final_source = final_dir / "episode.json"
            final_source.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            with patch.object(asset_batch_state_service, "ready_asset_ids", lambda base: {"CHAR_001", "LOC_001"}):
                self.assertEqual(d.final_storyboard_hint(final_source), "")   # 已经是定稿


    def test_unattended_labels_show_the_current_model(self):
        """四个页面的勾选框共用一句文案（第 35 期第 3 条起按钮上不写「无人值守」）：括号里写当前模型／引擎，不再写死「本地 ComfyUI」。"""
        import project_settings, asset_batch, keyframe_comfy, workflow_settings, local_video
        from cloud_assets import MODELS
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            settings_file = proj / "ui_settings.json"
            prefs = json.loads(settings_file.read_text(encoding="utf-8"))
            prefs["asset_batch"] = {"backend": MODELS[0]}
            prefs["frame_production"] = {"model": MODELS[0]}
            settings_file.write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
            # 资产与首帧各读自己窗口保存的模型；白模读调用设置里的引擎；视频读本地工作流
            self.assertEqual(asset_batch.current_model(proj), MODELS[0])
            self.assertEqual(keyframe_comfy.current_model(proj), MODELS[0])
            asset_text = project_settings.unattended_label("自动补资产", asset_batch.current_model(proj))
            frame_text = project_settings.unattended_label("自动补首帧", keyframe_comfy.current_model(proj))
            previs_text = project_settings.unattended_label("自动补白模", workflow_settings.model_name(proj, "previs"))
            video_text = project_settings.unattended_label("自动补视频", local_video.model_name(None))
            self.assertEqual(asset_text, "自动补资产（" + MODELS[0] + "）")
            self.assertEqual(frame_text, "自动补首帧（" + MODELS[0] + "）")
            self.assertEqual(previs_text, "自动补白模（ChatGPT / Codex）")
            self.assertEqual(video_text, "自动补视频（MiniMax H3）")
            for text in (asset_text, frame_text, previs_text, video_text):
                self.assertNotIn("本地 ComfyUI", text)
            # 没保存过设置的项目按各自的本地默认显示，而不是空括号
            fresh = make_adopted_project(tempfile.mkdtemp())
            self.assertEqual(asset_batch.current_model(fresh), "本地 FLUX.2 Klein / 自定义工作流")
            self.assertEqual(keyframe_comfy.current_model(fresh), "本地 FLUX.2 Klein（ComfyUI）")

    def test_auto_asset_sanhu_mode_persists_and_polls(self):
        """03 资产自动链路由三虎模式启用；缺图且清单已补齐的资产才排队。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from unittest.mock import patch
        import asset_batch
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
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
            d.show(PAGE["assets"]); win.update()
            d.poll_auto_asset()
            self.assertFalse(d.auto.asset_busy)                 # 手动模式：轮询什么都不做
            d.pet.set_level = lambda *args, **kwargs: None
            d.pet.broadcast = lambda *args, **kwargs: None
            d.pet.refresh_menu_labels = lambda: None
            d.pet.set_mode('auto')
            self.assertTrue(d.pet.should_auto_run('assets'))
            # 还没用过批量窗口：给出可读原因（主循环捕获后提示「自动补资产暂缓」），不静默排队
            with self.assertRaises(ValueError) as ctx:
                d.poll_auto_asset()
            self.assertIn("批量资产", str(ctx.exception))
            store = proj / "episode" / "assets" / "资产清单"; store.mkdir(parents=True, exist_ok=True)
            (store / "assets.json").write_text(json.dumps({
                "CHAR_001": {"name": "主角", "description": "", "image_prompt": "一只猫坐在窗边", "negative_prompt": ""},
                "LOC_001": {"name": "", "description": "", "image_prompt": ""}}, ensure_ascii=False), encoding="utf-8")
            prefs = json.loads((proj / "ui_settings.json").read_text(encoding="utf-8"))
            prefs["asset_batch"] = {"url": "http://127.0.0.1:8189", "backend": "local", "model": "flux.safetensors",
                                    "CHAR": True, "LOC": True, "PROP": False}
            (proj / "ui_settings.json").write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
            planned, skipped, _saved = asset_batch.auto_plan(proj, d.asset_base(), d.asset_sources(), "adopted")
            self.assertEqual([aid for aid, _ in planned], ["CHAR_001"])    # 场景清单没补齐：只跳过不排队
            self.assertEqual([aid for aid, _ in skipped], ["LOC_001"])
            started = []
            def fake_batch(project, base, sources, scope="adopted", log=None, stop=None):
                started.append(scope); log("批量资产日志")
                return "无人值守批量资产结束：成功 1，未完成 0"
            import asset_auto_batch_service
            with patch.object(asset_auto_batch_service, "auto_batch", fake_batch):
                d.poll_auto_asset()
                self.assertTrue(d.auto.asset_busy)
                self.assertIn("准备处理 1 项", d.status.get())
                ticket, ok, value, signature = d.auto.asset_queue.get(timeout=20)
                self.assertEqual(d.auto.asset_messages.get(timeout=20), (ticket, "批量资产日志"))
            self.assertTrue(ok)
            self.assertEqual(signature[0], ("CHAR_001",))
            self.assertEqual(started, ["adopted"])
            # 同一批缺图资产不再重复排队
            d.auto.asset_busy = False; d.auto.asset_signature = signature
            d.poll_auto_asset()
            self.assertEqual(started, ["adopted"])
            # 三虎切回手动就清掉已跑过的清单
            d.pet.set_mode('manual')
            d.poll_auto_asset()
            self.assertIsNone(d.auto.asset_signature)


    def test_unattended_asset_batch_retries_when_nothing_landed(self):
        """第 62 期任务 10：一轮跑完却一张图都没做出来时，不能记成完成——要提示并自动重试。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from unittest.mock import patch
        import asset_auto_batch_service
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
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
            store = proj / "episode" / "assets" / "资产清单"; store.mkdir(parents=True, exist_ok=True)
            (store / "assets.json").write_text(json.dumps({
                "CHAR_001": {"name": "主角", "description": "", "image_prompt": "一只猫坐在窗边", "negative_prompt": ""}},
                ensure_ascii=False), encoding="utf-8")
            prefs = json.loads((proj / "ui_settings.json").read_text(encoding="utf-8"))
            prefs["asset_batch"] = {"url": "http://127.0.0.1:8189", "backend": "local", "model": "flux.safetensors",
                                    "CHAR": True, "LOC": True, "PROP": False}
            (proj / "ui_settings.json").write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
            d.pet.set_level = lambda *args, **kwargs: None
            d.pet.broadcast = lambda *args, **kwargs: None
            d.pet.refresh_menu_labels = lambda: None
            d.pet.set_mode('auto')
            def fake_batch(project, base, sources, scope="adopted", log=None, stop=None):
                log("批量资产日志")
                return "批量完成：成功 0，未完成 1"
            with patch.object(asset_auto_batch_service, "auto_batch", fake_batch):
                d.poll_auto_asset()
                self.assertTrue(d.auto.asset_busy)
                item = d.auto.asset_queue.get(timeout=20)
            self.assertEqual(item[1], True)
            # 主循环收尾：把结果放回队列，让真实路径处理这一拍
            now = time.monotonic()
            d.auto.adopt_startup = False
            d.auto.adopt_due = d.auto.final_due = d.auto.edit_due = d.auto.keyframe_due = now + 9999
            d.auto.previs_due = d.auto.asset_due = d.auto.video_due = d.auto.handoff_due = now + 9999
            d.cloud_monitor_due = now + 9999
            d.auto.asset_queue.put(item)
            d._tick_once()
            self.assertIsNone(d.auto.asset_signature, "没成果就不算完成，不能把这一批永久划掉")
            self.assertEqual(d.auto.asset_attempt, 1)
            self.assertGreater(d.auto.asset_due, now, "要排一次重试")
            self.assertIn("自动重试", d.status.get())
            # 重建页面会重置状态栏，这里只保证提示本身说清楚了。
            # 第 64 期任务 2 把这句文案统一了：「跑完没成果」与「中途出错」都走
            # 「自动补资产没做完（…）；第 N 次尝试，稍后自动重试」。
            self.assertIn("没做完", d.status.get())

    def test_pet_storyboard_batch_dispatches_the_selected_scripts(self):
        """三虎只派有输入的分镜任务；结构化正稿同步后也必须成为可派发输入。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        # 本用例只验派单逻辑；会员闸门（真实账号状态）另有 test_account_* 覆盖，这里隔离，免得结果随本机登录态变化。
        import entitlement_service
        from unittest import mock
        gate = mock.patch.object(entitlement_service, "GATE_ENFORCED", False)
        gate.start()
        self.addCleanup(gate.stop)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
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
            calls = []
            d.open_storyboard_skill = lambda key=None: calls.append(key)
            self.assertEqual(d.pet_storyboard_batch(), "", "没有选中的剧本就不派单")
            self.assertEqual(calls, [])
            script = proj / "writing" / "第02集.md"
            script.parent.mkdir(parents=True, exist_ok=True)
            script.write_text("# 第02集 剧本", encoding="utf-8")
            prefs = json.loads((proj / "ui_settings.json").read_text(encoding="utf-8"))
            prefs["storyboard_scripts"] = ["writing/第02集.md"]
            (proj / "ui_settings.json").write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
            text = d.pet_storyboard_batch()
            self.assertEqual(calls, [None], "有要做的剧本就派一次")
            self.assertIn("已经在准备分镜任务", text)
            calls.clear()
            from storyboard_files import sync_structured_script
            from script_contract import structured_script_path
            structured = structured_script_path(proj)
            structured.parent.mkdir(parents=True, exist_ok=True)
            structured.write_text("# 结构化剧本", encoding="utf-8")
            sync_structured_script(proj)
            text = d.pet_storyboard_batch()
            self.assertEqual(calls, [None], "结构化完成同步的正稿必须能派发分镜")
            self.assertIn(structured.resolve(), __import__('storyboard_files').selected_many(proj, "script"))
            self.assertIn("已经在准备分镜任务", text)

    def test_studio_follows_selected_storyboard(self):
        """工作集跟随当前选择的分镜：切换分镜或自动采用后，08 剪辑、自动粗剪和交付不能还按旧分镜执行。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import project_settings
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            first = proj / "episode" / "episode.json"        # 工作集指针原本指向这里（config.json）
            episode = json.loads(first.read_text(encoding="utf-8"))
            second = dict(episode, episode_id="EP002")
            second["shots"] = [dict(shot, id="SH%03d" % (index + 31)) for index, shot in enumerate(episode["shots"])]
            target = storyboard_stage(proj) / "分镜文档" / "episode2.json"
            target.write_text(json.dumps(second, ensure_ascii=False), encoding="utf-8")
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
            def quiet_destroy():
                try:
                    win.destroy()
                except Exception:
                    pass
            self.addCleanup(quiet_destroy)
            from desktop import Desktop
            from local_video import open_studio
            from storyboard_selection import adopt
            d = Desktop(win, root=PROGRAM)
            d.root = proj
            d.studio = open_studio(proj)
            self.enable_sanhu_auto(d, "auto_edit_var")
            adopt(proj, [target])                     # 采用 EP002：当前分镜变了，工作集指针仍停在 EP001
            self.assertEqual(d.current_frame_json().resolve(), target.resolve())
            self.assertEqual(Path(d.studio.episode_path).resolve(), first.resolve())
            d.worker = True                           # 有任务在跑时不切换，避免打断批次
            self.assertFalse(d.align_studio())
            self.assertEqual(Path(d.studio.episode_path).resolve(), first.resolve())
            base = d.asset_base()
            d.worker = False
            self.assertTrue(d.align_studio())
            self.assertEqual(d.asset_base(), base)          # 资产库不跟着工作集换地方
            self.assertEqual(Path(d.studio.episode_path).resolve(), target.resolve())
            self.assertEqual([shot["id"] for shot in d.studio.episode["shots"]], ["SH031"])
            # 08 剪辑页直接读工作集：重建页面时会先对齐到当前分镜
            d.studio = open_studio(proj)
            d.show(PAGE["edit"]); win.update()
            self.assertEqual(Path(d.studio.episode_path).resolve(), target.resolve())
            # 自动粗剪同理：先对齐再判断，不必等用户进页面
            project_settings.set_auto_edit(proj, True)
            d.studio = open_studio(proj)
            d.poll_auto_edit()
            self.assertEqual(Path(d.studio.episode_path).resolve(), target.resolve())
            project_settings.set_auto_edit(proj, False); d.auto.edit_signature = None
            # 新分镜暂时不合规：保留原工作集并写明原因，不静默按错的分镜拼接
            broken = storyboard_stage(proj) / "分镜文档" / "episode3.json"
            broken.write_text(json.dumps(dict(second, episode_id="EP003", shots=[dict(second["shots"][0], duration=1)]), ensure_ascii=False), encoding="utf-8")
            settings_file = proj / "ui_settings.json"
            prefs = json.loads(settings_file.read_text(encoding="utf-8"))
            prefs["frame_json"] = "03初步分镜/分镜文档/episode3.json"
            settings_file.write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
            self.assertFalse(d.align_studio())
            self.assertEqual(Path(d.studio.episode_path).resolve(), target.resolve())
            self.assertIn("工作集未切换", d.status.get())


    def test_auto_video_sanhu_mode_persists_and_polls(self):
        """07 本地视频自动链路由三虎模式启用；缺视频的镜头只排队一次。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from unittest.mock import patch
        import local_video
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            frames = storyboard_stage(proj) / "frames"; frames.mkdir(parents=True, exist_ok=True)
            (frames / "SH001.png").write_bytes(b"PNG")
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
            def quiet_destroy():
                try:
                    win.destroy()
                except Exception:
                    pass
            self.addCleanup(quiet_destroy)
            from desktop import Desktop
            from local_video import LocalStudio, open_studio
            d = Desktop(win, root=PROGRAM)
            d.root = proj
            d.studio = open_studio(proj)
            self.assertIsInstance(d.studio, LocalStudio)
            d.show(PAGE["video"], video_mode="local"); win.update()
            d.poll_auto_video()
            self.assertFalse(d.auto.video_busy)             # 手动模式：轮询什么都不做
            d.pet.set_level = lambda *args, **kwargs: None
            d.pet.broadcast = lambda *args, **kwargs: None
            d.pet.refresh_menu_labels = lambda: None
            d.pet.set_mode('auto')
            self.assertTrue(d.pet.should_auto_run('video'))
            started = []
            def fake_batch(project, source, log=None, stop=None, studio=None):
                started.append(str(source)); log("批量视频日志")
                return "无人值守本地视频：已提交 1 镜：SH001"
            with patch.object(local_video, "auto_batch", fake_batch):
                d.poll_auto_video()
                self.assertTrue(d.auto.video_busy)
                self.assertIn("准备提交 1 镜", d.status.get())
                ticket, ok, value, signature = d.auto.video_queue.get(timeout=20)
                log_ticket, log_text = d.auto.video_messages.get(timeout=20)
                self.assertEqual((log_ticket, log_text), (ticket, "批量视频日志"))
                self.assertTrue(ok)
                self.assertEqual(signature, ("SH001",))
                self.assertEqual(started, [str(storyboard_stage(proj) / "分镜文档" / "episode.json")])
                # 同一批待提交镜头不再重复排队：已提交的下一轮只在待查询里出现
                d.auto.video_busy = False; d.auto.video_signature = signature
                d.poll_auto_video()
                self.assertEqual(len(started), 1)
            # 全部镜头都被跳过（首帧被删）时以前什么都不写：无人值守看起来像卡死，现在要写明原因。
            # 两个镜头、两种原因：状态栏只有一行，必须把两种原因都报出来，否则用户补齐首帧后
            # 仍停着，也不知道另一个镜头是上次生成失败。
            (frames / "SH001.png").unlink()
            episode = json.loads((storyboard_stage(proj) / "分镜文档" / "episode.json").read_text(encoding="utf-8"))
            episode["shots"].append(dict(episode["shots"][0], id="SH002", frame="frames/SH002.png"))
            (storyboard_stage(proj) / "分镜文档" / "episode.json").write_text(
                json.dumps(episode, ensure_ascii=False), encoding="utf-8")
            (proj / "data").mkdir(exist_ok=True)
            (proj / "data" / "state.json").write_text(json.dumps(
                {"schema": 1, "shots": {"SH002": [{"version": 1, "state": "failed"}]}}, ensure_ascii=False), encoding="utf-8")
            d.studio = open_studio(proj)                      # 重新打开：新加的镜头要进工作集
            d.auto.video_busy = False; d.auto.video_signature = None
            with patch.object(local_video, "auto_batch", fake_batch):
                d.poll_auto_video()
            self.assertFalse(d.auto.video_busy)
            self.assertEqual(len(started), 1)                 # 没有可做的镜头就不派发
            self.assertIn("自动补视频暂缓", d.status.get())
            self.assertIn("2 镜跳过", d.status.get())
            self.assertIn("尚无首帧", d.status.get())          # 第一条原因：缺首帧
            self.assertIn("上次本地生成未完成", d.status.get())   # 第二条原因不能被第一条盖掉
            d.status.set("哨兵")                               # 同一批跳过原因只提示一次
            d.poll_auto_video()
            self.assertEqual(d.status.get(), "哨兵")
            (frames / "SH001.png").write_bytes(b"PNG")         # 复原，后面的断言按原样继续
            # 三虎切回手动就清掉已跑过的清单
            d.pet.set_mode('manual')
            d.poll_auto_video()
            self.assertIsNone(d.auto.video_signature)


    def test_per_line_tts_asks_before_paying(self):
        """08 逐句配音按句计费：确认框取消时一句都不提交，确认后按预览的句数提交，重跑沿用不重复扣费。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from unittest.mock import patch
        import tts_api
        import desktop as desktop_module
        original_choose = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original_choose)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            with_dialogue(proj, [{"speaker": "CHAR_001", "text": "第一句"},
                                 {"speaker": "CHAR_001", "text": "第二句"}])
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
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
            d.show(PAGE["audio"]); win.update()
            # 正式路径把工作函数丢给后台线程；用例内同步执行，好在断言里看结果
            original_async = desktop_module.Desktop.async_
            self.addCleanup(setattr, desktop_module.Desktop, "async_", original_async)
            def sync(self, fn, done=None, show_progress=True):
                value = fn()
                if done is None:
                    self.status.set(value)
                else:
                    done(value)
            desktop_module.Desktop.async_ = sync
            calls = []
            def fake_synthesize(text, speed=1.0, voice=None, **_kwargs):
                calls.append(text); return b"audio"
            asked = []
            def refuse(_parent, title, message, **kwargs):
                asked.append((title, message)); return False
            with patch.object(desktop_module, "confirm", refuse), patch.object(tts_api, "synthesize", fake_synthesize), \
                 patch.object(tts_api, "load_key", lambda: "sk-fixed-test-key"):
                d.generate_tts_per_line()
            self.assertEqual(calls, [])                       # 取消：一句都不提交，也不产生费用
            self.assertIn("未提交", d.status.get())
            self.assertIn("2 句", asked[0][1])                # 确认框先把要付多少摊开
            self.assertIn("6 字", asked[0][1])
            self.assertIn("价格版本", asked[0][1])
            self.assertIn("本批预计", asked[0][1])
            with patch.object(desktop_module, "confirm", lambda *a, **k: True), patch.object(tts_api, "synthesize", fake_synthesize), \
                 patch.object(tts_api, "load_key", lambda: "sk-fixed-test-key"):
                d.generate_tts_per_line()
            self.assertEqual(calls, ["第一句", "第二句"])      # 确认后按预览的句数提交
            self.assertIn("逐句配音完成", d.status.get())
            with patch.object(desktop_module, "confirm", refuse), patch.object(tts_api, "synthesize", fake_synthesize), \
                 patch.object(tts_api, "load_key", lambda: "sk-fixed-test-key"):
                d.generate_tts_per_line()                     # 同一批再点：全部沿用，连确认框都不弹
            self.assertEqual(calls, ["第一句", "第二句"])
            self.assertIn("都已有成品", d.status.get())
            self.assertEqual(len(asked), 1)


    def test_whole_script_tts_reuses_unchanged_audio(self):
        """08 整段配音：台词与音色都没变时第二次点击直接沿用文件，不重复扣费；换了音色才重新合成。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from unittest.mock import patch
        import tts_api
        import desktop as desktop_module
        original_choose = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original_choose)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            with_dialogue(proj, [{"speaker": "CHAR_001", "text": "只有这一句台词"}])
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
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
            original_async = desktop_module.Desktop.async_
            self.addCleanup(setattr, desktop_module.Desktop, "async_", original_async)
            def sync(self, fn, done=None, show_progress=True):
                value = fn()
                if done is None:
                    self.status.set(value)
                else:
                    done(value)
            desktop_module.Desktop.async_ = sync
            calls = []
            def fake_synthesize(text, speed=1.0, voice=None, **_kwargs):
                calls.append(text); return b"audio"
            with patch.object(tts_api, "synthesize", fake_synthesize):
                d.generate_tts()
            self.assertEqual(len(calls), 1)
            self.assertIn("配音已生成", d.status.get())
            from project_stages import audio
            made = audio(proj) / "整段配音.json"
            self.assertTrue(made.is_file())
            with patch.object(tts_api, "synthesize", fake_synthesize):
                d.generate_tts()                     # 同台词同音色再点：沿用，不再付费
            self.assertEqual(len(calls), 1)
            self.assertIn("未重复扣费", d.status.get())
            with patch.object(tts_api, "synthesize", fake_synthesize), \
                 patch.object(tts_api, "read_settings", lambda: {"model": "m", "voice": "换了音色"}):
                d.generate_tts()                     # 换音色：指纹变了，重新合成
            self.assertEqual(len(calls), 2)


    def test_auto_final_switch_generates_final_and_retires_working_json(self):
        """04「自动生成定稿」：资产没齐只提示缺什么；资产齐了自动定稿、工作稿移入回收站，随后自动停下。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import time
        import desktop as desktop_module
        original_choose = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original_choose)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            from project_stages import storyboard, stage
            storyboard_dir = storyboard(proj) / "分镜文档"
            final_dir = stage(proj, 'final') / '分镜'
            source = storyboard_dir / "episode.json"
            win = self.tk.Tk(); win.geometry("1200x780+40+40")
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
            show_catalog_page_ready(d, PAGE["final"]); win.update()
            # 自动制作勾选框已从页面移除；唯一写入权归三虎的全自动模式。
            self.enable_sanhu_auto(d, "auto_final_var")
            self.assertTrue(d.pet.should_auto_run('final'))
            d.auto.final_due = 0
            d.poll_auto_final()
            # 资产还没导入：不动工作稿，只说明缺什么，并留着开关等资产补齐
            self.assertIn("暂缓", d.status.get())
            self.assertIn("CHAR_001", d.status.get())
            self.assertTrue(source.is_file())
            self.assertEqual([p for p in storyboard_dir.iterdir() if "定稿" in p.name], [])
            # 资产补齐后：主循环自己把定稿做出来
            (proj / "episode" / "assets").mkdir(exist_ok=True)
            for aid in ("CHAR_001", "LOC_001"):
                (proj / "episode" / "assets" / (aid + ".png")).write_bytes(b"\x89PNG\r\n\x1a\n")
            (proj / "episode" / "assets.json").write_text(json.dumps({
                "CHAR_001": {"name": "主角", "image": "assets/CHAR_001.png"},
                "LOC_001": {"name": "场景", "image": "assets/LOC_001.png"}}, ensure_ascii=False), encoding="utf-8")
            d.auto.final_due = 0
            d.poll_auto_final()
            self.assertTrue(d.auto.final_busy)
            for _ in range(200):
                win.update(); d._tick_once()
                if not d.auto.final_busy:
                    break
                time.sleep(0.05)
            self.assertFalse(d.auto.final_busy)
            finals = [p for p in final_dir.iterdir() if p.is_dir() and "定稿" in p.name]
            self.assertEqual(len(finals), 1)
            self.assertTrue((finals[0] / "episode.json").is_file())
            self.assertFalse(source.is_file())                            # 工作稿已移入回收站
            self.assertEqual(len(list((proj / "工作流任务" / "回收站").glob("*"))), 1)
            self.assertIn("已自动生成定稿", d.status.get())
            # 定稿接管后当前分镜就是定稿目录：轮询自然停下，不会再定一次
            d.auto.final_signature = None
            d.auto.final_due = 0
            d.poll_auto_final()
            self.assertIsNone(d.auto.final_signature)
            self.assertFalse(d.auto.final_busy)
            self.assertEqual(len([p for p in final_dir.iterdir() if p.is_dir() and "定稿" in p.name]), 1)


    def test_final_page_offers_visible_retry_for_unsynced_storyboard(self):
        """Round 5「分镜定稿未同步分镜的可见重试」：04 页上看得见「还缺什么」，也点得动。

        原来这两条只写状态栏——切到别的页面就再也看不到，资产补齐了也不知道要不要动手
        （「无人值守走完采用分镜就静默停住」）。现在页面上有提示条 ＋ 一颗「立即重试」：
        点一下立刻重扫资产、重跑一轮，不必等下一个 30 秒轮询周期。
        """
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import time
        import project_settings
        import desktop as desktop_module
        original_choose = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original_choose)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            source = storyboard_stage(proj) / "分镜文档" / "episode.json"
            win = self.tk.Tk(); win.geometry("1200x780+40+40")
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
            self.enable_sanhu_auto(d, "auto_final_var")
            self.assertTrue(project_settings.set_auto_final(proj, True))
            show_catalog_page_ready(d, PAGE["final"]); win.update()
            def retry_buttons():
                """这一页上那颗「立即重试」（列表刷新不重建页面，但每次还是重新找一次）。"""
                found = []
                def walk(widget):
                    for child in widget.winfo_children():
                        try:
                            label = str(child.cget("text"))
                        except Exception:
                            label = ""
                        if label == "立即重试":
                            found.append(child)
                        walk(child)
                walk(d.content)
                return found
            # ① 看得见：还没同步的那一份、还缺哪几项资产，都写在页面上（不是只在状态栏）
            self.assertIn("没同步成定稿", d.auto_final_banner.get())
            self.assertIn("CHAR_001", d.auto_final_banner.get())
            self.assertEqual(d.auto_final_state()["kind"], "missing")
            # ② 点得动：资产没齐也能点，点完在提示条与状态栏上说清「还缺什么」，工作稿一动不动
            buttons = retry_buttons()
            self.assertEqual(len(buttons), 1, "04 页上有且只有一颗「立即重试」")
            self.assertEqual(str(buttons[0].cget("state")), "normal")
            buttons[0].invoke(); win.update()
            self.assertIn("还缺 2 项资产图片", d.auto_final_banner.get())
            self.assertIn("还缺 2 项资产图片", d.status.get())
            self.assertTrue(source.is_file(), "资产没补齐：工作稿一动不动")
            self.assertEqual(final_dirs(proj), [])
            # ③ 资产补齐后点一下：立刻出定稿，不必等下一个 30 秒轮询周期
            (proj / "episode" / "assets").mkdir(exist_ok=True)
            for aid in ("CHAR_001", "LOC_001"):
                (proj / "episode" / "assets" / (aid + ".png")).write_bytes(b"\x89PNG\r\n\x1a\n")
            (proj / "episode" / "assets.json").write_text(json.dumps({
                "CHAR_001": {"name": "主角", "image": "assets/CHAR_001.png"},
                "LOC_001": {"name": "场景", "image": "assets/LOC_001.png"}}, ensure_ascii=False), encoding="utf-8")
            again = retry_buttons()
            self.assertEqual(len(again), 1)
            again[0].invoke()
            for _ in range(200):
                win.update(); d._tick_once()
                if not d.auto.final_busy:
                    break
                time.sleep(0.05)
            self.assertFalse(d.auto.final_busy)
            finals = final_dirs(proj)
            self.assertEqual(len(finals), 1)
            self.assertTrue((finals[0] / "episode.json").is_file())
            self.assertFalse(source.is_file(), "工作稿已移入回收站")
            self.assertEqual(d.auto_final_state()["kind"], "done")
            self.assertIn("没有要同步的分镜", d.auto_final_banner.get())


    def test_asset_resume_ledger_carries_the_backoff_across_restart(self):
        """第 6 轮：退避的次数与「下次什么时候接着试」落进项目台账，重启后接着数、到顶就停下等人。

        原来这两样只在内存里：助手一关就全没了，重开项目又从第 1 次开始——同一批做不出图的
        资产每次开机都白跑一轮，用户既看不到「已经试过几次」，也等不到那句「已停下等您处理」。
        """
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from unittest.mock import patch
        import asset_auto_batch_service, asset_resume
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            win = self.tk.Tk(); win.geometry("1100x740+40+40")
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
            store = proj / "episode" / "assets" / "资产清单"; store.mkdir(parents=True, exist_ok=True)
            (store / "assets.json").write_text(json.dumps({
                "CHAR_001": {"name": "主角", "description": "", "image_prompt": "一只猫坐在窗边", "negative_prompt": ""}},
                ensure_ascii=False), encoding="utf-8")
            prefs = json.loads((proj / "ui_settings.json").read_text(encoding="utf-8"))
            prefs["auto_asset"] = True
            prefs["asset_batch"] = {"url": "http://127.0.0.1:8189", "backend": "local", "model": "flux.safetensors",
                                    "CHAR": True, "LOC": True, "PROP": False}
            (proj / "ui_settings.json").write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
            self.enable_sanhu_auto(d, "auto_asset_var")
            ledger = asset_resume.path(proj)
            self.assertFalse(ledger.is_file(), "还没试过就不该有台账")
            def fake_batch(project, base, sources, scope="adopted", log=None, stop=None):
                log("批量资产日志")
                return "批量完成：成功 0，未完成 1"
            with patch.object(asset_auto_batch_service, "auto_batch", fake_batch):
                for expected in (1, 2, 3):
                    d.poll_auto_asset()
                    item = d.auto.asset_queue.get(timeout=20)
                    self.assertEqual(item[1], True)
                    now = time.monotonic()
                    d.auto.adopt_startup = False
                    d.auto.adopt_due = d.auto.final_due = d.auto.edit_due = d.auto.keyframe_due = now + 9999
                    d.auto.previs_due = d.auto.asset_due = d.auto.video_due = d.auto.handoff_due = now + 9999
                    d.cloud_monitor_due = now + 9999
                    d.auto.asset_queue.put(item)
                    d._tick_once()
                    self.assertEqual(d.auto.asset_attempt, expected)
            self.assertIsNotNone(d.auto.asset_signature, "到顶的那一批不再自动重排")
            self.assertTrue(ledger.is_file(), "次数与下次该重试的时刻要落在项目里，不能只活在内存")
            saved = json.loads(ledger.read_text(encoding="utf-8"))
            self.assertEqual(saved["CHAR_001"]["attempts"], 3)
            self.assertEqual(saved["CHAR_001"]["state"], "stopped")
            # 「重启」：另开一个 Desktop（内存全清零），只认盘上这份台账
            win2 = self.tk.Tk(); win2.geometry("1100x740+60+60")
            def quiet_destroy2():
                try:
                    win2.destroy()
                except Exception:
                    pass
            self.addCleanup(quiet_destroy2)
            fresh = Desktop(win2, root=PROGRAM)
            fresh.root = proj
            fresh.studio = open_studio(proj)
            self.enable_sanhu_auto(fresh, "auto_asset_var")
            fresh.restore_asset_resume()               # 打开项目（load）走的就是这一步
            self.assertEqual(fresh.auto.asset_attempt, 3, "重启后接着上一次的次数，不是从 1 开始")
            with patch.object(asset_auto_batch_service, "auto_batch", fake_batch):
                fresh.poll_auto_asset()
            self.assertEqual(len(fresh.auto.asset_queue), 0, "到顶的那一批重启后不再自动重排")
            self.assertIn("停下", fresh.status.get())


    def test_unattended_chain_runs_asset_final_keyframe_in_order(self):
        """无人值守链路连续推进：03 补齐资产 → 04 自动定稿 → 05 自动补首帧，中途不需要人工点按钮。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import time
        from unittest.mock import patch
        import asset_auto_batch_service, keyframe_comfy, project_settings
        import desktop as desktop_module
        original_choose = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original_choose)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            source = storyboard_stage(proj) / "分镜文档" / "episode.json"
            # 资产清单已补齐提示词但还没有图片，批量设置也已保存：03 有活可干
            store = proj / "episode" / "assets" / "资产清单"; store.mkdir(parents=True, exist_ok=True)
            (store / "assets.json").write_text(json.dumps({
                "CHAR_001": {"name": "主角", "description": "", "image_prompt": "一只猫坐在窗边", "negative_prompt": ""},
                "LOC_001": {"name": "场景", "description": "", "image_prompt": "傍晚的房间", "negative_prompt": ""}},
                ensure_ascii=False), encoding="utf-8")
            prefs = json.loads((proj / "ui_settings.json").read_text(encoding="utf-8"))
            prefs["asset_batch"] = {"url": "http://127.0.0.1:8189", "backend": "local", "model": "flux.safetensors",
                                    "CHAR": True, "LOC": True, "PROP": False}
            (proj / "ui_settings.json").write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
            win = self.tk.Tk(); win.geometry("1200x780+40+40")
            def quiet_destroy():
                try:
                    win.destroy()
                except Exception:
                    pass
            self.addCleanup(quiet_destroy)
            from desktop import Desktop
            from local_video import open_studio
            from storyboard_paths import media_root
            d = Desktop(win, root=PROGRAM)
            d.root = proj
            d.studio = open_studio(proj)
            self.enable_sanhu_auto(d, "auto_asset_var", "auto_final_var", "auto_first_frame_var")
            events = []; seen = []; lines = []
            # 状态栏每一步都会被覆盖：按写入顺序整轮记录，采样会漏掉同一轮里被覆盖的那一句。
            d.status.trace_add("write", lambda *a: lines.append(str(d.status.get())))
            def fake_asset_batch(project, base, sources, scope="adopted", log=None, stop=None):
                events.append("asset")
                base = Path(base)
                (base / "assets").mkdir(exist_ok=True)
                registry = {}
                for aid in ("CHAR_001", "LOC_001"):
                    (base / "assets" / (aid + ".png")).write_bytes(b"\x89PNG\r\n\x1a\n")
                    registry[aid] = {"name": aid, "image": "assets/%s.png" % aid}
                (base / "assets.json").write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")
                log("批量资产日志")
                return "无人值守批量资产结束：成功 2，未完成 0"
            def fake_keyframe_batch(path, log, stop=None):
                events.append("keyframe"); seen.append(Path(path))
                episode = json.loads(Path(path).read_text(encoding="utf-8-sig"))
                base = media_root(path)
                for shot in episode["shots"]:
                    target = base / shot["frame"]; target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(b"\x89PNG\r\n\x1a\nFRAME")
                log("批量首帧日志")
                return "无人值守首帧批次结束：处理 1 镜，已生成 1 镜"
            self.assertTrue(project_settings.set_auto_asset(proj, True))
            self.assertTrue(project_settings.set_auto_final(proj, True))
            self.assertTrue(project_settings.set_auto_keyframe(proj, True))
            frames = storyboard_stage(proj) / "frames" / "SH001.png"
            with patch.object(asset_auto_batch_service, "auto_batch", fake_asset_batch), \
                 patch.object(keyframe_comfy, "auto_batch", fake_keyframe_batch):
                for _ in range(400):
                    d.auto.asset_due = d.auto.final_due = d.auto.keyframe_due = 0
                    win.update(); d._tick_once()
                    if frames.is_file() and not d.auto.keyframe_busy and not d.auto.asset_busy:
                        break
                    time.sleep(0.03)
            # 收尾：等三个无人值守轮询都停下来再退出临时目录（后台线程还在写项目时清理会报「目录不是空的」）
            for _ in range(60):
                win.update(); d._tick_once()
                if not (d.auto.asset_busy or d.auto.final_busy or d.auto.keyframe_busy):
                    break
                time.sleep(0.05)
            d.cancel_timers(); time.sleep(0.1)
            # 每一步都真的发生过，且顺序是 资产 → 定稿 → 首帧
            self.assertEqual(events, ["asset", "keyframe"])
            finals = final_dirs(proj)
            self.assertEqual(len(finals), 1)
            self.assertFalse(source.is_file())                      # 工作稿已移入回收站
            self.assertTrue((finals[0] / "frames" / "SH001.png").is_file())
            self.assertEqual(len(seen), 1)
            self.assertEqual(seen[0].parent.name, finals[0].name)    # 05 轮询的是定稿，不是旧工作稿
            # 状态栏按顺序报过这两步（后一步会覆盖前一步，所以看整轮记录）
            self.assertTrue(any("已自动生成定稿" in text for text in lines))
            self.assertTrue(any("首帧批次结束" in text for text in lines))


    def test_downstream_keyframe_never_runs_ahead_of_a_ready_final_step(self):
        """资产已写盘但批次还没收尾时，定稿要让路，首帧批次也必须跟着等。

        这是全量自测里偶发失败的那条竞态的确定性版本：假资产批次先把资产写好、再挂着不收尾，
        于是「定稿就绪 + 别的批次在跑」这个窗口被钉在原地。这时首帧轮询一等资产可用就会立刻
        开工——给一份马上要被定稿归档的工作稿出图，定稿接管后又得重来一遍。窗口里反复 tick，
        只要首帧批次抢跑，断言立刻失败（不依赖机器负载）。
        """
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import time, threading
        from unittest.mock import patch
        import asset_auto_batch_service, keyframe_comfy, project_settings
        import desktop as desktop_module
        original_choose = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original_choose)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            source = storyboard_stage(proj) / "分镜文档" / "episode.json"
            store = proj / "episode" / "assets" / "资产清单"; store.mkdir(parents=True, exist_ok=True)
            (store / "assets.json").write_text(json.dumps({
                "CHAR_001": {"name": "主角", "description": "", "image_prompt": "一只猫坐在窗边", "negative_prompt": ""},
                "LOC_001": {"name": "场景", "description": "", "image_prompt": "傍晚的房间", "negative_prompt": ""}},
                ensure_ascii=False), encoding="utf-8")
            prefs = json.loads((proj / "ui_settings.json").read_text(encoding="utf-8"))
            prefs["asset_batch"] = {"url": "http://127.0.0.1:8189", "backend": "local", "model": "flux.safetensors",
                                    "CHAR": True, "LOC": True, "PROP": False}
            (proj / "ui_settings.json").write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
            win = self.tk.Tk(); win.geometry("1200x780+40+40")
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
            self.enable_sanhu_auto(d, "auto_asset_var", "auto_final_var", "auto_first_frame_var")
            events = []
            written = threading.Event(); release = threading.Event()
            def stalled_asset_batch(project, base, sources, scope="adopted", log=None, stop=None):
                # 先把资产写全（定稿这轮已经就绪），再挂着不收尾：批次仍在读这份工作稿。
                events.append("asset")
                base = Path(base)
                (base / "assets").mkdir(exist_ok=True)
                registry = {}
                for aid in ("CHAR_001", "LOC_001"):
                    (base / "assets" / (aid + ".png")).write_bytes(b"\x89PNG\r\n\x1a\n")
                    registry[aid] = {"name": aid, "image": "assets/%s.png" % aid}
                (base / "assets.json").write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")
                written.set(); release.wait(20)
                log("批量资产日志")
                return "无人值守批量资产结束：成功 2，未完成 0"
            def keyframe_batch(path, log, stop=None):
                # 记下这一批看到的是不是「已经交接给定稿的那份」：抢跑时工作稿还在原地。
                events.append(("keyframe", not source.is_file()))
                log("批量首帧日志")
                return "无人值守首帧批次结束：处理 1 镜，已生成 1 镜"
            self.assertTrue(project_settings.set_auto_asset(proj, True))
            self.assertTrue(project_settings.set_auto_final(proj, True))
            self.assertTrue(project_settings.set_auto_keyframe(proj, True))
            with patch.object(asset_auto_batch_service, "auto_batch", stalled_asset_batch), \
                 patch.object(keyframe_comfy, "auto_batch", keyframe_batch):
                for _ in range(20):
                    d.auto.asset_due = d.auto.final_due = d.auto.keyframe_due = 0
                    win.update(); d._tick_once()
                    if d.auto.asset_busy and written.is_set():
                        break
                    time.sleep(0.03)
                self.assertTrue(d.auto.asset_busy, "假资产批次没被拉起来")
                self.assertIn("asset", events)
                # 窗口里反复 tick：定稿在等这批资产收尾，首帧批次一次都不许开跑
                for _ in range(10):
                    d.auto.asset_due = d.auto.final_due = d.auto.keyframe_due = 0
                    win.update(); d._tick_once()
                self.assertEqual(events, ["asset"])
                self.assertFalse(d.auto.keyframe_busy)
                self.assertFalse(d.auto.final_busy)
                release.set()                                    # 资产批次收尾，定稿可以动手了
                for _ in range(200):
                    d.auto.asset_due = d.auto.final_due = d.auto.keyframe_due = 0
                    win.update(); d._tick_once()
                    if len(events) > 1 and not (d.auto.asset_busy or d.auto.final_busy or d.auto.keyframe_busy):
                        break
                    time.sleep(0.03)
            for _ in range(60):
                win.update(); d._tick_once()
                if not (d.auto.asset_busy or d.auto.final_busy or d.auto.keyframe_busy):
                    break
                time.sleep(0.05)
            d.cancel_timers(); time.sleep(0.1)
            kinds = [event[0] if isinstance(event, tuple) else event for event in events]
            self.assertEqual(kinds, ["asset", "keyframe"])
            self.assertTrue(events[1][1], "首帧批次跑在工作稿上：定稿还没接管就出图了")
            finals = final_dirs(proj)
            self.assertEqual(len(finals), 1)
            self.assertFalse(source.is_file())                   # 工作稿已移入回收站


    def test_unattended_chain_runs_video_edit_handoff_in_order(self):
        """无人值守链路后半段连续推进：07 补齐视频 → 09 自动粗剪 → 10 自动整理交接包。

        10 只复制本地已下载成片，不依赖 09 的整集成片，所以这两步的先后不作要求；
        真正的连锁关系是「07 的成片通过验收」同时是 09 与 10 的前提。
        """
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import time
        from unittest.mock import patch
        from agent.core import file_hash, save
        import engine as engine_module, local_video, project_settings
        import desktop as desktop_module
        original_choose = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original_choose)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            source = storyboard_stage(proj) / "分镜文档" / "episode.json"
            frames = storyboard_stage(proj) / "frames"
            frames.mkdir(parents=True, exist_ok=True)
            (frames / "SH001.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            win = self.tk.Tk(); win.geometry("1200x780+40+40")
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
            self.enable_sanhu_auto(d, "auto_video_var", "auto_edit_var", "auto_handoff_var")
            events = []; lines = []; assembled = []
            # 状态栏每一步都会被覆盖，所以按写入顺序整轮记录（trace 不丢中间状态）。
            d.status.trace_add("write", lambda *a: lines.append(str(d.status.get())))
            def fake_video_batch(project, source, log=None, stop=None, studio=None):
                events.append("video"); log("批量视频日志")
                clip = proj / "data" / "clips" / "SH001.mp4"
                clip.parent.mkdir(parents=True, exist_ok=True); clip.write_bytes(b"fake-video")
                save(proj / "data" / "state.json", {"schema": 1, "shots": {"SH001": [{
                    "version": 1, "state": "downloaded", "qc_pass": True, "review": "pass",
                    "file": "data/clips/SH001.mp4", "sha256": file_hash(clip)}]}})
                return "无人值守本地视频：处理 1 镜"
            real_assemble = engine_module.Studio.assemble
            def fake_assemble(self, **kw):
                assembled.append(1)
                master = export_stage(proj) / "MASTER.mp4"
                master.parent.mkdir(parents=True, exist_ok=True); master.write_bytes(b"fake-master")
                return str(master)
            engine_module.Studio.assemble = fake_assemble
            self.addCleanup(setattr, engine_module.Studio, "assemble", real_assemble)
            self.assertTrue(project_settings.set_auto_video(proj, True))
            self.assertTrue(project_settings.set_auto_edit(proj, True))
            self.assertTrue(project_settings.set_auto_handoff(proj, True))
            folder = editing_stage(proj) / "自动交接包"
            settled = lambda: not (d.auto.video_busy or d.auto.edit_busy or d.auto.handoff_busy)
            with patch.object(local_video, "auto_batch", fake_video_batch):
                for _ in range(400):
                    d.auto.video_due = d.auto.edit_due = d.auto.handoff_due = 0
                    win.update(); d._tick_once()
                    if (folder / "镜头顺序.json").is_file() and (editing_stage(proj) / "自动粗剪.json").is_file() and settled():
                        break
                    time.sleep(0.03)
            for _ in range(60):
                win.update(); d._tick_once()
                if settled():
                    break
                time.sleep(0.05)
            d.cancel_timers(); time.sleep(0.1)
            self.assertEqual(events, ["video"])                       # 视频批次只派发一次
            self.assertEqual(assembled, [1])                          # 同一批验收只粗剪一次
            self.assertTrue((editing_stage(proj) / "自动粗剪.json").is_file())
            self.assertEqual(sorted(p.name for p in folder.iterdir()),
                             ["001_SH001.mp4", "交接包标记.json", "交接包清单.json", "导入剪映说明.txt", "镜头顺序.json"])
            self.assertEqual(Path(d.studio.episode_path).resolve(), source.resolve())   # 工作集一路跟随当前分镜
            steps = [next((i for i, text in enumerate(lines) if needle in text), None)
                     for needle in ("无人值守自动补视频", "自动粗剪完成", "自动交接包已整理")]
            self.assertNotIn(None, steps)                             # 三步都报过
            self.assertLess(steps[0], steps[1])                       # 07 的成片是 09 的前提
            self.assertLess(steps[0], steps[2])                       # 也是 10 的前提


    def test_unattended_polls_yield_while_finalizing(self):
        """04 定稿正在移走工作稿时，02/03/09 的无人值守轮询这一轮都不动手：否则会拿到正在被替换的路径。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import time
        from unittest.mock import patch
        from agent.core import file_hash, save
        import asset_auto_batch_service, engine as engine_module, project_settings
        import desktop as desktop_module
        original_choose = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original_choose)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            # 03 有活可干：资产清单里只有提示词、还没有图片，批量设置也已保存
            store = proj / "episode" / "assets" / "资产清单"; store.mkdir(parents=True, exist_ok=True)
            (store / "assets.json").write_text(json.dumps({
                "CHAR_001": {"name": "主角", "description": "", "image_prompt": "一只猫坐在窗边", "negative_prompt": ""},
                "LOC_001": {"name": "场景", "description": "", "image_prompt": "傍晚的房间", "negative_prompt": ""}},
                ensure_ascii=False), encoding="utf-8")
            prefs = json.loads((proj / "ui_settings.json").read_text(encoding="utf-8"))
            prefs["asset_batch"] = {"url": "http://127.0.0.1:8189", "backend": "local", "model": "flux.safetensors",
                                    "CHAR": True, "LOC": True, "PROP": False}
            (proj / "ui_settings.json").write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
            # 09 有活可干：整集唯一镜头已验收
            clip = proj / "data" / "clips" / "SH001.mp4"
            clip.parent.mkdir(parents=True, exist_ok=True); clip.write_bytes(b"fake-video")
            save(proj / "data" / "state.json", {"schema": 1, "shots": {"SH001": [{
                "version": 1, "state": "downloaded", "qc_pass": True, "review": "pass",
                "file": "data/clips/SH001.mp4", "sha256": file_hash(clip)}]}})
            win = self.tk.Tk(); win.geometry("1200x780+40+40")
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
            self.enable_sanhu_auto(d, "auto_asset_var", "auto_edit_var", "auto_adopt_var")
            self.assertTrue(project_settings.set_auto_asset(proj, True))
            self.assertTrue(project_settings.set_auto_edit(proj, True))
            self.assertTrue(project_settings.set_auto_adopt(proj, True))
            batches = []; assembled = []
            settled = lambda: not (d.auto.asset_busy or d.auto.edit_busy)
            with patch.object(asset_auto_batch_service, "auto_batch", lambda *a, **k: (batches.append(1), "假资产批次")[1]), \
                 patch.object(engine_module.Studio, "assemble",
                              lambda self, **kw: (assembled.append(1), str(export_stage(proj) / "MASTER.mp4"))[1]):
                d.auto.final_busy = True                       # 定稿正在把工作稿移进回收站
                d.poll_auto_asset(); d.poll_auto_edit(); d.poll_auto_adopt()
                self.assertEqual(batches, [])                  # 03 不派发批次
                self.assertEqual(assembled, [])                # 09 不启动粗剪
                self.assertIsNone(d.auto.adopt_signature)       # 02 连扫描都不做
                self.assertFalse(d.auto.asset_busy or d.auto.edit_busy)
                d.auto.final_busy = False                      # 定稿结束
                d.poll_auto_asset(); d.poll_auto_edit()
                # 派发为异步；等待队列收尾后断言，不能依赖新线程恰好抢先执行。
                for _ in range(60):
                    win.update(); d._tick_once()
                    if settled():
                        break
                    time.sleep(0.05)
                self.assertTrue(settled(), '自动资产与粗剪须在期限内完成')
            d.cancel_timers(); time.sleep(0.1)
            self.assertEqual(len(batches), 1)
            self.assertEqual(assembled, [1])


    def test_unattended_pipeline_runs_end_to_end_without_clicks(self):
        """全链路无人值守一次跑通：03 补资产 → 04 定稿 → 05 补首帧 → 07 补视频 → 09 粗剪 → 10 交接包。

        这是「离开电脑让它自己做完」的验收口径：六条轮询同时打开，中途没有任何点击。
        """
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import time
        from unittest.mock import patch
        from agent.core import file_hash, save
        import asset_auto_batch_service, engine as engine_module, keyframe_comfy, local_video, project_settings
        import desktop as desktop_module
        original_choose = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original_choose)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            source = storyboard_stage(proj) / "分镜文档" / "episode.json"
            # 03 有活可干：清单里只有提示词、还没有图片；批量设置也已保存
            store = proj / "episode" / "assets" / "资产清单"; store.mkdir(parents=True, exist_ok=True)
            (store / "assets.json").write_text(json.dumps({
                "CHAR_001": {"name": "主角", "description": "", "image_prompt": "一只猫坐在窗边", "negative_prompt": ""},
                "LOC_001": {"name": "场景", "description": "", "image_prompt": "傍晚的房间", "negative_prompt": ""}},
                ensure_ascii=False), encoding="utf-8")
            prefs = json.loads((proj / "ui_settings.json").read_text(encoding="utf-8"))
            prefs["asset_batch"] = {"url": "http://127.0.0.1:8189", "backend": "local", "model": "flux.safetensors",
                                    "CHAR": True, "LOC": True, "PROP": False}
            (proj / "ui_settings.json").write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
            win = self.tk.Tk(); win.geometry("1200x780+40+40")
            def quiet_destroy():
                try:
                    win.destroy()
                except Exception:
                    pass
            self.addCleanup(quiet_destroy)
            from desktop import Desktop
            from local_video import open_studio
            from storyboard_paths import media_root
            d = Desktop(win, root=PROGRAM)
            d.root = proj
            d.studio = open_studio(proj)
            self.enable_sanhu_auto(d, "auto_asset_var", "auto_final_var", "auto_first_frame_var", "auto_video_var", "auto_edit_var", "auto_handoff_var")
            events = []; lines = []
            d.status.trace_add("write", lambda *a: lines.append(str(d.status.get())))
            def fake_asset_batch(project, base, sources, scope="adopted", log=None, stop=None):
                events.append("asset")
                base = Path(base)
                (base / "assets").mkdir(exist_ok=True)
                registry = {}
                for aid in ("CHAR_001", "LOC_001"):
                    (base / "assets" / (aid + ".png")).write_bytes(b"\x89PNG\r\n\x1a\n")
                    registry[aid] = {"name": aid, "image": "assets/%s.png" % aid}
                (base / "assets.json").write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")
                log("批量资产日志")
                return "无人值守批量资产结束：成功 2，未完成 0"
            def fake_keyframe_batch(path, log, stop=None):
                events.append("keyframe")
                episode = json.loads(Path(path).read_text(encoding="utf-8-sig"))
                for shot in episode["shots"]:
                    target = media_root(path) / shot["frame"]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(b"\x89PNG\r\n\x1a\nFRAME")
                log("批量首帧日志")
                return "无人值守首帧批次结束：处理 1 镜，已生成 1 镜"
            def fake_video_batch(project, source, log=None, stop=None, studio=None):
                events.append("video"); log("批量视频日志")
                clip = proj / "data" / "clips" / "SH001.mp4"
                clip.parent.mkdir(parents=True, exist_ok=True); clip.write_bytes(b"fake-video")
                # 自动验收打开时，下载完成且技术质检通过的镜头会被直接标记为已验收
                save(proj / "data" / "state.json", {"schema": 1, "shots": {"SH001": [{
                    "version": 1, "state": "downloaded", "qc_pass": True, "review": "pass",
                    "file": "data/clips/SH001.mp4", "sha256": file_hash(clip)}]}})
                return "无人值守本地视频：处理 1 镜"
            def fake_assemble(self, **kw):
                events.append("assemble")
                master = export_stage(proj) / "MASTER.mp4"
                master.parent.mkdir(parents=True, exist_ok=True); master.write_bytes(b"fake-master")
                return str(master)
            for name in ("auto_asset", "auto_final", "auto_keyframe", "auto_video", "auto_edit", "auto_handoff"):
                self.assertTrue(getattr(project_settings, "set_" + name)(proj, True), name)
            folder = editing_stage(proj) / "自动交接包"
            def settled():
                return not (d.auto.asset_busy or d.auto.final_busy or d.auto.keyframe_busy
                            or d.auto.video_busy or d.auto.edit_busy or d.auto.handoff_busy)
            with patch.object(asset_auto_batch_service, "auto_batch", fake_asset_batch), \
                 patch.object(keyframe_comfy, "auto_batch", fake_keyframe_batch), \
                 patch.object(local_video, "auto_batch", fake_video_batch), \
                 patch.object(engine_module.Studio, "assemble", fake_assemble):
                # 不动任何节流：链路必须靠「上一步成功就踢下游」自己往前走，只等轮询周期会拖到几分钟。
                ticks = 0
                for tick in range(400):
                    ticks = tick + 1
                    win.update(); d._tick_once()
                    if (folder / "镜头顺序.json").is_file() and settled():
                        break
                    time.sleep(0.03)
                for _ in range(60):
                    win.update(); d._tick_once()
                    if settled():
                        break
                    time.sleep(0.05)
            d.cancel_timers(); time.sleep(0.1)
            # 六步各自动作一次，顺序是 资产 → 首帧 → 视频 → 粗剪
            self.assertEqual(events, ["asset", "keyframe", "video", "assemble"])
            self.assertLess(ticks, 60)                                           # 每一步都在下一轮就接上
            finals = final_dirs(proj)
            self.assertEqual(len(finals), 1)
            self.assertFalse(source.is_file())                                   # 工作稿已移入回收站
            self.assertTrue((finals[0] / "frames" / "SH001.png").is_file())
            self.assertTrue((proj / "data" / "clips" / "SH001.mp4").is_file())
            self.assertTrue((editing_stage(proj) / "自动粗剪.json").is_file())
            self.assertEqual(sorted(p.name for p in folder.iterdir()),
                             ["001_SH001.mp4", "交接包标记.json", "交接包清单.json", "导入剪映说明.txt", "镜头顺序.json"])
            # 工作集一路跟到定稿：09/10 不能还按旧工作稿执行
            self.assertEqual(Path(d.studio.episode_path).parent.name, finals[0].name)
            for needle in ("已自动生成定稿", "首帧批次结束", "自动补视频", "自动粗剪完成", "自动交接包已整理"):
                self.assertTrue(any(needle in text for text in lines), needle)


    def test_chain_kick_skips_steps_in_failure_backoff(self):
        """链路接力只踢下游，且不抢跑失败后的 5 分钟退避：否则一次成功会把别处失败重试节奏打乱。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import time
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        win = self.tk.Tk(); win.geometry("900x600+40+40")
        def quiet_destroy():
            try:
                win.destroy()
            except Exception:
                pass
        self.addCleanup(quiet_destroy)
        from desktop import Desktop
        d = Desktop(win, root=PROGRAM)
        now = time.monotonic()
        d.auto.edit_due = now + 15            # 正常节流中的下游
        d.auto.handoff_due = now + 300        # 失败退避中的下游
        d.auto.asset_due = now + 60           # 上游步骤
        d.kick_unattended("auto_video")
        self.assertEqual(d.auto.edit_due, 0)                  # 下游立刻赶一轮
        self.assertGreater(d.auto.handoff_due, now + 120)     # 退避不抢跑
        self.assertGreater(d.auto.asset_due, now + 30)        # 不回头踢上游
        d.cancel_timers()


    def test_auto_final_waits_for_running_keyframe_batch(self):
        """定稿会移走工作稿，所以要等在跑的无人值守批次结束：批次收尾会按原路径重读分镜 JSON。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import threading, time
        from unittest.mock import patch
        import keyframe_comfy, project_settings
        import desktop as desktop_module
        original_choose = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original_choose)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            source = storyboard_stage(proj) / "分镜文档" / "episode.json"
            (proj / "episode" / "assets").mkdir(exist_ok=True)
            for aid in ("CHAR_001", "LOC_001"):
                (proj / "episode" / "assets" / (aid + ".png")).write_bytes(b"\x89PNG\r\n\x1a\n")
            (proj / "episode" / "assets.json").write_text(json.dumps({
                "CHAR_001": {"name": "主角", "image": "assets/CHAR_001.png"},
                "LOC_001": {"name": "场景", "image": "assets/LOC_001.png"}}, ensure_ascii=False), encoding="utf-8")
            win = self.tk.Tk(); win.geometry("1200x780+40+40")
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
            self.enable_sanhu_auto(d, "auto_final_var", "auto_first_frame_var")
            started = threading.Event(); release = threading.Event()
            def blocking_batch(path, log, stop=None):
                started.set(); release.wait(10); log("批次日志")
                return "无人值守首帧批次结束：处理 1 镜，已生成 0 镜"
            self.assertTrue(project_settings.set_auto_keyframe(proj, True))
            self.assertTrue(project_settings.set_auto_final(proj, True))
            with patch.object(keyframe_comfy, "auto_batch", blocking_batch):
                d.poll_auto_keyframe()
                self.assertTrue(d.auto.keyframe_busy)
                self.assertTrue(started.wait(10))
                # 批次还在跑：定稿必须让路，不能把批次正在读的工作稿移走
                d.auto.final_due = 0
                d.poll_auto_final()
                self.assertFalse(d.auto.final_busy)
                self.assertEqual(final_dirs(proj), [])
                self.assertTrue(source.is_file())
                release.set()
                for _ in range(100):
                    win.update(); d._tick_once()
                    if not d.auto.keyframe_busy:
                        break
                    time.sleep(0.03)
                self.assertFalse(d.auto.keyframe_busy)
            # 批次结束后定稿才动手。假批次要一直挂着：定稿成功会立刻叫醒首帧轮询，
            # 一旦这里换回真批次，测试会在临时目录里对着 ComfyUI 真的跑起来。
            with patch.object(keyframe_comfy, "auto_batch", blocking_batch):
                d.auto.final_due = 0
                d.poll_auto_final()
                self.assertTrue(d.auto.final_busy)
                for _ in range(200):
                    win.update(); d._tick_once()
                    if not d.auto.final_busy:
                        break
                    time.sleep(0.03)
                for _ in range(60):
                    win.update(); d._tick_once()
                    if not (d.auto.final_busy or d.auto.keyframe_busy):
                        break
                    time.sleep(0.05)
            d.cancel_timers(); time.sleep(0.1)
            finals = final_dirs(proj)
            self.assertEqual(len(finals), 1)
            self.assertFalse(source.is_file())


    def test_table_hover_clears_when_wheel_scrolls(self):
        """滚轮滚动内容框时清掉悬停高亮：高亮浮层按旧坐标贴着表格，不跟着滚动就会停在错行上。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        import storyboard_selection
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            source = storyboard_stage(proj) / "分镜文档" / "episode.json"
            data = json.loads(source.read_text(encoding="utf-8"))
            base = data["shots"][0]
            data["shots"] = [dict(base, id="SH%03d" % index) for index in range(1, 17)]
            source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            win = self.tk.Tk(); win.geometry("1100x700+40+40")
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
            d.show(PAGE["keyframe"]); win.update()
            trees = []
            def walk(widget):
                if isinstance(widget, ttk.Treeview) and "prompt" in widget["columns"]:
                    trees.append(widget)
                for child in widget.winfo_children():
                    walk(child)
            walk(d.content)
            table = trees[0]
            row = table.get_children()[0]
            table.see(row); win.update()
            bounds = table.bbox(row, "#1")
            self.assertTrue(bounds, "表格行没有可显示的格子")
            hover = table.cell_hover
            hover.at(bounds[0] + 2, bounds[1] + 2); win.update()
            # 同上：看它有没有被 place 出来（结构判据），不看映射落地的时机。
            self.assertEqual(hover.overlay.winfo_manager(), "place", "悬停高亮摆出来了")
            table.event_generate("<MouseWheel>", delta=-120, x=bounds[0] + 2, y=bounds[1] + 2)
            win.update()
            self.assertGreater(table.yview()[0], 0)                  # 表格确实滚了
            self.assertFalse(hover.overlay.winfo_ismapped())         # 悬停高亮随滚动清掉


    def test_same_page_rebuild_keeps_scroll_offset(self):
        """同一页重建（刷新列表、切换分镜、自动流程刷新）保留滚动位置；换页才回到顶部。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            source = storyboard_stage(proj) / "分镜文档" / "episode.json"
            data = json.loads(source.read_text(encoding="utf-8"))
            base = data["shots"][0]
            data["shots"] = [dict(base, id="SH%03d" % index, title="镜头内容" * 20) for index in range(1, 25)]
            source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            win = self.tk.Tk(); win.geometry("1000x660+20+20")
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
            d.cancel_timers()
            show_catalog_page_ready(d, PAGE["final"])
            for _ in range(3):
                win.update(); win.update_idletasks()
            self.assertLess(d.canvas.yview()[1], 1.0)                # 这一页确实长到需要滚动
            d.canvas.yview_moveto(0.5); win.update()
            before = d.canvas.canvasy(0)
            self.assertGreater(before, 0)
            show_catalog_page_ready(d, PAGE["final"])
            for _ in range(3):
                win.update(); win.update_idletasks()
            self.assertAlmostEqual(d.canvas.canvasy(0), before, delta=2)
            d.page_index = 1                                         # 换页（等价于点其它导航）
            show_catalog_page_ready(d, PAGE["final"]); win.update()
            self.assertEqual(d.canvas.canvasy(0), 0)

    def test_restored_main_window_recomputes_page_scroll_before_wheel(self):
        """最小化恢复后，第一枚落在页面底部的滚轮也能继续查看被遮挡内容。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            source = storyboard_stage(proj) / "分镜文档" / "episode.json"
            data = json.loads(source.read_text(encoding="utf-8"))
            base = data["shots"][0]
            data["shots"] = [dict(base, id="SH%03d" % index, title="镜头内容" * 20) for index in range(1, 25)]
            source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            win = self.tk.Tk(); win.geometry("1000x660+20+20")
            self.addCleanup(lambda: win.destroy() if win.winfo_exists() else None)
            from desktop import Desktop
            from local_video import open_studio
            d = Desktop(win, root=PROGRAM)
            d.root = proj; d.studio = open_studio(proj); d.cancel_timers()
            show_catalog_page_ready(d, PAGE["final"])
            for _ in range(3):
                win.update(); win.update_idletasks()
            self.assertLess(d.canvas.yview()[1], 1.0)
            # 直接调用与 <Map> 相同的恢复入口，避免 CI/远程桌面系统最小化策略差异。
            d.on_window_map(type("MapEvent", (), {"widget": win})())
            for _ in range(3):
                win.update(); win.update_idletasks()
            before = d.canvas.yview()[0]
            d.canvas.event_generate("<MouseWheel>", delta=-120, x=5, y=5)
            win.update()
            self.assertGreater(d.canvas.yview()[0], before)


class RowHeightTests(unittest.TestCase):
    """第 58 期第 2 条：内容框的行高按格子里最高的那点内容算。

    以前是每张表各写一个数字（镜头表 60、资产表 80、主题里的 34），图尺寸或字体一变
    就对不上了。现在统一算：摆缩略图的按图高，纯文字的按字体量出来的一行字，取高的那个加余地。
    """

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def test_the_height_is_the_tallest_thing_in_the_cell(self):
        from responsive_ui import row_height_for
        self.assertEqual(row_height_for(72), 80, '缩略图 72 像素：行高 72 ＋ 上下余地 8')
        self.assertEqual(row_height_for(54), 62)
        self.assertEqual(row_height_for(0, 19), 30, '纯文字：一行字 19 ＋ 余地 8')
        self.assertEqual(row_height_for(72, 19), 80, '两样都有时取高的那个')
        self.assertEqual(row_height_for(0, 4), 30, '量不出来的一行字不能把行压没')
        self.assertEqual(row_height_for(9, 9, pad=6, floor=20), 26, '余地与下限都认参数')

    def test_the_height_reads_the_widget_font(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk, font as tkfont
        from responsive_ui import row_text_height, row_height_for
        win = self.tk.Tk(); win.withdraw()
        self.addCleanup(win.destroy)
        tree = ttk.Treeview(win)
        line = tkfont.Font(root=win,
                           font=ttk.Style(win).lookup('Treeview', 'font')).metrics('linespace')
        self.assertEqual(row_text_height(tree), line)
        self.assertEqual(row_height_for(0, row_text_height(tree)), row_height_for(0, line))

    def test_fit_row_height_sets_the_style(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        from responsive_ui import fit_row_height, row_height_for, row_text_height
        win = self.tk.Tk(); win.withdraw()
        self.addCleanup(win.destroy)
        tree = ttk.Treeview(win, style='Row.Treeview')
        self.assertEqual(fit_row_height(tree, 72, style='Row.Treeview'), 80)
        self.assertEqual(int(ttk.Style(win).lookup('Row.Treeview', 'rowheight')), 80)
        self.assertEqual(tree._row_height, 80, '设成的行高记在表上，别处还要用')
        self.assertEqual(fit_row_height(tree, 0, style='Row.Treeview'),
                         row_height_for(0, row_text_height(tree)), '不给图就按一行字算')

    def test_the_content_boxes_take_their_height_from_the_thumbnail(self):
        """三张摆缩略图的内容框：常量就是按图高算出来的，不再是拍脑子写的数。"""
        sys.path.insert(0, PROGRAM)
        from responsive_ui import row_height_for
        import app as app_module
        import desktop as desktop_module
        import asset_reference_images
        self.assertEqual(app_module.SHOT_ROW_HEIGHT, row_height_for(app_module.SHOT_THUMB_SIZE))
        self.assertEqual(app_module.PICK_ROW_HEIGHT, row_height_for(app_module.PICK_THUMB_SIZE))
        self.assertEqual(desktop_module.ASSET_ROW_HEIGHT, row_height_for(desktop_module.THUMB_SIZE))
        self.assertEqual(asset_reference_images.REF_ROW_HEIGHT,
                         row_height_for(asset_reference_images.REF_THUMB))


class BatchContinuationTests(unittest.TestCase):
    """批量入口不再弹「是否继续」模态框：已制作分镜的剧本、已导入资产、已采用的 JSON 都直接跳过并写明原因。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def desktop(self, td, proj):
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        win = self.tk.Tk(); win.withdraw()
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
        return d, win

    def no_modal(self):
        """把确认弹窗换成记录器：一旦被调用就记下来，测试用空列表证明「没有弹窗」。"""
        import desktop as desktop_module
        calls = []
        original_confirm = desktop_module.confirm
        original_error = desktop_module.messagebox.showerror
        desktop_module.confirm = lambda _parent, title, *_a, **_k: (calls.append(title), False)[1]
        desktop_module.messagebox.showerror = lambda *a, **k: calls.append(a[0] if a else "")
        self.addCleanup(setattr, desktop_module, "confirm", original_confirm)
        self.addCleanup(setattr, desktop_module.messagebox, "showerror", original_error)
        return calls

    def test_storyboard_agent_continues_past_made_scripts(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import time
        import storyboard_catalog_service, storyboard_selection, workflow_tasks
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            script = proj / "writing" / "第01集.md"
            script.parent.mkdir(parents=True, exist_ok=True)
            script.write_text("# 剧本", encoding="utf-8")
            patches = [(storyboard_selection, "selected_many",
                        lambda project, kind: [script.resolve()] if kind == "script" else []),
                       (storyboard_catalog_service, "produced_scripts", lambda context, entries=None: {script.resolve()}),
                       (workflow_tasks, "storyboard_batch_prompt",
                        lambda project, scripts, existing: ("任务正文", "追加说明"))]
            for module, name, value in patches:
                original = getattr(module, name)
                setattr(module, name, value)
                self.addCleanup(setattr, module, name, original)
            calls = self.no_modal()
            d, win = self.desktop(td, proj)
            recorded = []
            d.open_flow_agent = lambda stage, label, prompt, followup=None: recorded.append((stage, label, prompt, followup))
            d.open_storyboard_skill()
            for _ in range(300):
                win.update()
                if recorded:
                    break
                time.sleep(0.01)
            self.assertEqual(recorded, [("storyboard", "初步分镜", "任务正文", "追加说明")])
            self.assertEqual(calls, [])
            self.assertIn("已跳过 1 个已制作分镜的剧本", d.status.get())

    def asset_page(self, td, status="已导入"):
        """资产页一行、已勾上：下面那几条共用这一套布置。"""
        proj = make_minimal_project(td)
        d, win = self.desktop(td, proj)
        d.asset_requirements = lambda: {"CHAR_001": {"id": "CHAR_001", "name": "角色", "status": status}}
        d.asset_kind = "characters"
        d.show(PAGE["assets"]); win.update()
        d.asset_checks = {str(proj.resolve()): {"CHAR_001": True}}
        d.asset_checked_count = 1
        d.asset_has_pending = True
        d.update_asset_buttons()
        return d, win, proj

    def quiet_batch(self):
        """把批量制作窗换成记录器：用例只看它拿到了哪几项。"""
        import asset_batch
        started = []
        original_show = asset_batch.show
        asset_batch.show = lambda app, engine, selected_ids=None: started.append((engine, list(selected_ids or [])))
        self.addCleanup(setattr, asset_batch, "show", original_show)
        return started

    def answer_modal(self, value):
        """把确认弹窗按下去：返回被问过的标题表。"""
        import desktop as desktop_module
        calls = []
        original_confirm = desktop_module.confirm
        desktop_module.confirm = lambda _parent, title, *_a, **_k: (calls.append(title), value)[1]
        self.addCleanup(setattr, desktop_module, "confirm", original_confirm)
        return calls

    def test_asset_batch_asks_before_remaking_finished_assets(self):
        """第 59 期第 3 条：勾到「已制作」的行，点制作先问一句重不重做；不重做就不开窗口。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            d, win, _proj = self.asset_page(td)
            calls = self.answer_modal(False)
            started = self.quiet_batch()
            [b for b in d.asset_gated_buttons if b.cget("text") == "手动制作资产"][0].invoke()
            win.update()
            self.assertEqual(calls, ["重新制作资产"], "要问一句才能把用户选的行手掉")
            self.assertEqual(started, [], "用户说不重做就不开制作窗口")
            self.assertIn("没有要制作的资产", d.status.get())

    def test_asset_batch_remakes_the_ones_the_user_confirmed(self):
        """确认重做就把旧图移进项目回收站，资产回到待导入。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import json
        with tempfile.TemporaryDirectory() as td:
            d, win, proj = self.asset_page(td)
            base = d.asset_base()
            image = base / "assets/characters/CHAR_001.png"
            image.parent.mkdir(parents=True, exist_ok=True)
            image.write_bytes(b"png")
            (base / "assets.json").write_text(json.dumps(
                {"CHAR_001": {"image": "assets/characters/CHAR_001.png"}}, ensure_ascii=False), encoding="utf-8")
            calls = self.answer_modal(True)
            started = self.quiet_batch()
            [b for b in d.asset_gated_buttons if b.cget("text") == "手动制作资产"][0].invoke()
            win.update()
            self.assertEqual(calls, ["重新制作资产"])
            self.assertFalse(image.exists(), "旧图该挪走")
            self.assertTrue(list((base / "工作流任务" / "回收站").rglob("CHAR_001.png")),
                            "旧图移进项目回收站，删错了还能找回来")
            self.assertEqual(json.loads((base / "assets.json").read_text(encoding="utf-8")).get("CHAR_001", {}).get("image"),
                             None, "登记里那一条也得撑掉")
            self.assertEqual(started, [("workflow", ["CHAR_001"])], "重做的这一项照旧交给批量窗口")

    def test_asset_batch_still_starts_for_the_unfinished_ones(self):
        """第 59 期第 3 条：勾上一项已制作、一项未制作，不重做时只做未制作的那一项。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(td, proj)
            d.asset_requirements = lambda: {"CHAR_001": {"id": "CHAR_001", "name": "角色", "status": "已导入"},
                                            "CHAR_002": {"id": "CHAR_002", "name": "配角", "status": "待导入"}}
            d.asset_kind = "characters"
            d.show(PAGE["assets"]); win.update()
            d.asset_checks = {str(proj.resolve()): {"CHAR_001": True, "CHAR_002": True}}
            d.asset_checked_count = 2
            d.asset_has_pending = True
            d.update_asset_buttons()
            self.answer_modal(False)
            started = self.quiet_batch()
            [b for b in d.asset_gated_buttons if b.cget("text") == "手动制作资产"][0].invoke()
            win.update()
            self.assertEqual(started, [("workflow", ["CHAR_002"])], "只把还没做的那一项交出去")

    def test_the_manual_asset_button_is_grey_when_everything_is_made(self):
        """第 59 期第 3 条：内容框里只剩「已制作」的行时，这颗按钮置灰。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(td, proj)
            d.asset_requirements = lambda: {"CHAR_001": {"id": "CHAR_001", "name": "角色", "status": "已导入"}}
            d.asset_kind = "characters"
            d.show(PAGE["assets"]); win.update()
            start = [b for b in d.asset_gated_buttons if b.cget("text") == "手动制作资产"][0]
            d.asset_checked_count = 1
            d.asset_has_pending = False
            d.update_asset_buttons()
            self.assertTrue(start.instate(["disabled"]), "全都做好了就不能再点制作")
            d.asset_has_pending = True
            d.update_asset_buttons()
            self.assertFalse(start.instate(["disabled"]), "有待导入的行就要能点")

    def test_adopt_skips_adopted_without_confirm(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            adopted_rel = "03初步分镜/分镜文档/episode.json"
            second = storyboard_stage(proj) / "分镜文档" / "episode_2.json"
            second.write_text((storyboard_stage(proj) / "分镜文档" / "episode.json").read_text(encoding="utf-8"), encoding="utf-8")
            second_rel = "03初步分镜/分镜文档/episode_2.json"
            keep_storyboard_fresh(proj)          # 两份分镜都得是「刚写的」，否则 normalize 会先改名
            prefs = json.loads((proj / "ui_settings.json").read_text(encoding="utf-8"))
            prefs["storyboard_files"] = [adopted_rel, second_rel]
            prefs["storyboard_file"] = second_rel
            (proj / "ui_settings.json").write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
            calls = self.no_modal()
            d, win = self.desktop(td, proj)
            show_catalog_page_ready(d, PAGE["storyboard"]); win.update()
            [b for b in self.buttons(d.content) if b.cget("text") == "手动采用分镜"][0].invoke()
            win.update()
            self.assertEqual(calls, [])
            saved = json.loads((proj / "ui_settings.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["adopted_storyboards"], [adopted_rel, second_rel])
            self.assertIn("新增采用 1 份", d.status.get())
            self.assertIn("已采用 2 份分镜", d.status.get())

    def buttons(self, widget):
        from tkinter import ttk
        found = []
        def walk(w):
            if isinstance(w, ttk.Button):
                found.append(w)
            for child in w.winfo_children():
                walk(child)
        walk(widget)
        return found
class WorkerThreadSafetyTests(unittest.TestCase):
    """设置窗口的连通性检测：结果必须由主线程写回状态栏。

    工作线程直接设置 Tk 变量会抛 RuntimeError（main thread is not in main loop），
    被 except 吞掉后状态栏就永远停在「正在测试连接…」。
    """

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            from tkinter import ttk
            cls.tk, cls.ttk = tk, ttk
        except Exception:
            cls.tk = cls.ttk = None

    def widgets(self, widget, kind):
        found = []
        def walk(w):
            if isinstance(w, kind):
                found.append(w)
            for child in w.winfo_children():
                walk(child)
        walk(widget)
        return found

    def probe_status(self, module, results):
        import time
        import api_endpoints
        original = api_endpoints.probe_endpoint
        api_endpoints.probe_endpoint = lambda url: dict(results)
        self.addCleanup(setattr, api_endpoints, "probe_endpoint", original)
        root = self.tk.Tk(); root.withdraw()
        self.addCleanup(root.destroy)
        module.show(root)
        root.update()
        popup = popup_windows(root, self.tk)[-1]
        [b for b in self.widgets(popup, self.ttk.Button) if b.cget("text") == "测试连接"][0].invoke()
        for _ in range(40):
            root.update()
            texts = [str(w.cget("text")) for w in self.widgets(popup, self.ttk.Label)]
            hit = [text for text in texts if "接口可达" in text or "连接失败" in text]
            if hit:
                return hit[0]
            time.sleep(0.05)
        return "\n".join(str(w.cget("text")) for w in self.widgets(popup, self.ttk.Label))

    def test_seedream_probe_reports_reachable(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import seedream_settings
        text = self.probe_status(seedream_settings, {"reachable": True, "code": 401})
        self.assertIn("接口可达", text)
        self.assertIn("需密钥", text)

    def test_tts_probe_reports_connection_failure(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import tts_settings
        text = self.probe_status(tts_settings, {"reachable": False, "error": "超时"})
        self.assertIn("连接失败", text)
        self.assertIn("超时", text)
class PromptWindowSourceGuardTests(unittest.TestCase):
    """源码守卫：「复制提示词」只保留一份实现，两个入口都必须委托 prompt_window。"""

    def program_sources(self):
        sources = {p.name: p.read_text(encoding="utf-8") for p in sorted(Path(PROGRAM).glob("*.py")) if not p.name.startswith("test_")}
        from tests.architecture._scan import desktop_text
        sources["desktop.py"] = desktop_text()  # R1505：Desktop 方法分布在 desktop.py 与迁出的 Mixin 模块
        return sources

    def test_copy_button_lives_only_in_prompt_window(self):
        """页面自带一份复制弹窗，复制后的行为就会再次走偏（历史 BUG：一个关窗一个不关）。"""
        offenders = [name for name, text in self.program_sources().items() if name != "prompt_window.py" and "复制提示词" in text]
        self.assertEqual(offenders, [])

    def test_prompt_entries_share_one_window(self):
        """「查看首帧提示词」与资产提示词两处入口必须共用 prompt_window，不再各写一份弹窗。"""
        sources = self.program_sources()
        for name in ("desktop.py", "asset_reference_prompts.py"):
            self.assertIn("from prompt_window import show", sources[name])

    def test_clipboard_writes_go_through_one_helper(self):
        """全程序只有 prompt_window.copy_text 写剪贴板：提示词窗口与 Codex 任务文本都走它。

        各写一份时出过「一个窗口复制后关、另一个不关」，以及「复制失败没人处理」。
        """
        sources = self.program_sources()
        # desktop 的输入框右键「粘贴」可以直接读取 Tk 剪贴板；所有写入必须走 copy_text。
        offenders = [name for name, text in sources.items()
                     if name != "prompt_window.py" and "clipboard_append" in text]
        self.assertEqual(offenders, [])
        self.assertEqual(sources["prompt_window.py"].count("clipboard_append"), 1)
        self.assertIn("copy_text", sources["local_previs.py"])            # 白模制作说明的复制
        self.assertIn("copy_text", sources["desktop.py"])                 # Codex 任务文本


class ApprovedVersionSourceGuardTests(unittest.TestCase):
    """源码守卫：「已下载＋质检通过＋已验收」只保留一份实现（engine.approved_versions）。"""

    PREDICATE = "v.get('review')=='pass' and v.get('state')=='downloaded' and v.get('qc_pass')"

    def program_sources(self):
        sources = {p.name: p.read_text(encoding="utf-8") for p in sorted(Path(PROGRAM).glob("*.py")) if not p.name.startswith("test_")}
        from tests.architecture._scan import desktop_text
        sources["desktop.py"] = desktop_text()  # R1505：Desktop 方法分布在 desktop.py 与迁出的 Mixin 模块
        return sources

    def test_approval_predicate_lives_only_in_engine(self):
        """口径散在自动粗剪、手动拼装、交接包三处时，改一处就会让成片和交接包取到不同版本。"""
        sources = self.program_sources()
        offenders = [name for name, text in sources.items() if name != "engine.py" and self.PREDICATE in text]
        self.assertEqual(offenders, [])
        self.assertEqual(sources["engine.py"].count(self.PREDICATE), 1)

    def test_approval_consumers_use_the_shared_helper(self):
        """engine 的两处筛选、进度与交付界面都必须走同一个「采用版」助手，别再各挑各的版本。"""
        sources = self.program_sources()
        self.assertRegex(sources["desktop.py"], r"from engine import [^\n]*\bapproved_versions\b")
        self.assertRegex(sources["desktop.py"], r"from engine import [^\n]*\badoption_summary\b")
        # 自动粗剪与手动拼装都收敛到 adopted_edit_version；approved_versions 只留一处实现。
        self.assertEqual(sources["engine.py"].count("adopted_edit_version(st['shots'].get(shot['id'])"), 2)
        self.assertEqual(sources["engine.py"].count("approved_versions(st['shots'].get(shot['id']))"), 0)


class EngineNameFallbackTests(unittest.TestCase):
    """第 14 期：workflow_settings 里没有 model_name 时，白模页不该整页炸在 ImportError 上。

    用户报的 BUG 就是「白模预演 -> cannot import name model_name from workflow_settings」：
    这句提示只该让模型名显示为空，页面照常打开、照样能开始制作。
    """

    def test_the_name_comes_from_the_workflow_settings(self):
        import local_previs, workflow_settings
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            self.assertEqual(local_previs.engine_name(proj), workflow_settings.model_name(proj, "previs"))

    def test_a_settings_module_without_the_name_falls_back_to_empty(self):
        import contextlib, io, types
        import local_previs
        saved = sys.modules.get("workflow_settings")
        sys.modules["workflow_settings"] = types.ModuleType("workflow_settings")   # 有包、没函数

        def restore():
            if saved is None:
                sys.modules.pop("workflow_settings", None)
            else:
                sys.modules["workflow_settings"] = saved
        self.addCleanup(restore)
        with tempfile.TemporaryDirectory() as td, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(local_previs.engine_name(make_adopted_project(td)), "",
                             "读不到名字只该退回空串，不该把异常甩到页面上")

    def test_the_page_asks_the_module_level_helper(self):
        source = (Path(PROGRAM) / "local_previs.py").read_text(encoding="utf-8")
        self.assertIn("def engine_name(project):", source, "取名字的容错逻辑要在模块级，自检才喂得进坏模块")
        self.assertIn("previs_engine=engine_name(self.project)", source)  # R1836：show 改写成类



class StageConfigEntryTests(unittest.TestCase):
    """第 41 期第 2 条：10 个制作页面每页都点得到本阶段的「阶段配置」。

    原先只有剧本准备／初步分镜／资产管理／分镜定稿／首帧管理／白模预演／视频生成七页有，
    配音与字幕、后期剪辑、质检与交付三页一个都没有——10 阶段各自的模型＋SKILL 面板，
    那三块从界面上点不进去。这条用例逐页把按钮按下去，核对弹出的面板抬头就是这一页的阶段。
    """

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def buttons_named(self, widget):
        """阶段入口会显示实际模型名，且复用蓝色主按钮而不依赖旧暖色样式名。"""
        found = []
        if widget.winfo_class() in ("TButton", "Button"):
            if getattr(widget, "_stage_config_entry", False):
                self.assertEqual(str(widget.cget("style")), "Tokens.Primary.TButton",
                                 "阶段配置必须复用设计系统的蓝色主按钮")
                found.append(widget)
        for child in widget.winfo_children():
            found.extend(self.buttons_named(child))
        return found

    def test_buttons_named_rejects_wrong_style_explicitly(self):
        from unittest.mock import Mock
        button = Mock(_stage_config_entry=True)
        button.winfo_class.return_value = "TButton"
        button.winfo_children.return_value = []
        button.cget.return_value = "Wrong.TButton"
        with self.assertRaisesRegex(AssertionError, "阶段配置必须复用设计系统的蓝色主按钮"):
            self.buttons_named(button)

    def test_buttons_named_keeps_valid_entry_and_reports_lookup_errors(self):
        from unittest.mock import Mock
        button = Mock(_stage_config_entry=True)
        button.winfo_class.return_value = "TButton"
        button.winfo_children.return_value = []
        button.cget.return_value = "Tokens.Primary.TButton"
        self.assertEqual(self.buttons_named(button), [button])
        button.cget.side_effect = RuntimeError("style lookup failed")
        with self.assertRaisesRegex(RuntimeError, "style lookup failed"):
            self.buttons_named(button)

    def test_every_page_opens_its_own_panel(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import desktop as desktop_module
        import skill_panel
        # safe() 出错时会弹 messagebox，自检会被那个弹窗卡住：这里只记账，最后断言没人报错。
        errors = []
        for name in ("showerror", "showinfo"):
            real = getattr(desktop_module.messagebox, name)
            self.addCleanup(setattr, desktop_module.messagebox, name, real)
            setattr(desktop_module.messagebox, name, lambda *a, **k: errors.append(a))
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            win = self.tk.Tk(); win.withdraw()
            self.addCleanup(win.destroy)
            from desktop import Desktop
            from local_video import open_studio
            d = Desktop(win, root=PROGRAM)
            d.root = proj
            d.studio = open_studio(proj)
            for index in range(len(PAGE)):
                with self.subTest(page=index):
                    d.show(index); win.update_idletasks()
                    buttons = self.buttons_named(d.content) + self.buttons_named(d.title_row)
                    if index == PAGE["video"]:
                        # 视频页的方式选择屏不摆阶段配置，进入具体工作台后再提供入口。
                        self.assertEqual(len(buttons), 0,
                                         "第 8 页不该再有阶段配置入口")
                        continue
                    self.assertEqual(len(buttons), 1, "第 %d 页没有（或不止一颗）阶段配置入口：%s"
                                     % (index, d.title.cget("text")))
                    buttons[0].invoke(); win.update_idletasks()
                    panels = [w for w in win.winfo_children()
                              if isinstance(w, self.tk.Toplevel)
                              and str(w.title()).startswith("阶段配置 · ")]
                    self.assertEqual(len(panels), 1, "按一次只该开一块面板")
                    self.assertEqual(panels[0].title(),
                                     skill_panel.panel_title(skill_panel.stage_of_page(index)),
                                     "这一页的按钮配的必须是这一页的阶段")
                    panels[0].destroy()
        self.assertEqual(errors, [], "这一步不该靠弹框收场")

class BriefTintTests(unittest.TestCase):
    """剧本准备页：上方简报可编辑，独立追问框初始空白。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def build(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        proj = make_adopted_project(self.tmp.name)
        win = self.tk.Tk()
        win.withdraw()
        self.addCleanup(lambda: win.winfo_exists() and win.destroy())
        from desktop import Desktop
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        d = Desktop(win, root=PROGRAM)
        d.root = proj
        d.show(0)
        win.update()
        return win, d

    def write_brief(self, d, text):
        folder = d.root / "writing"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "创意与剧本_20260101_000000.md"
        path.write_text(text, encoding="utf-8")
        return path

    def test_the_fresh_example_is_shown_in_readonly_bubble(self):
        win, d = self.build()
        self.assertEqual(d.draft_text(), '', "发送框初始空白")
        self.assertEqual(idea_chat.strip_inline_required_markers(d._bubble_full['bubble_example']['text']), d.idea_example())
        self.assertFalse(hasattr(d, 'idea_brief_editor'))
        self.assertEqual(str(d.idea_log.cget("state")), "normal", "聊天正文需要支持直接选择与编辑")

    def test_software_example_is_gray_readonly_and_has_no_edit_entry(self):
        """软件示例只供参考，可复制但不能编辑或落入项目对话。"""
        from ui_tokens import COLORS
        win, d = self.build()
        box = d.idea_log
        original_draft = d.draft_text()
        self.assertTrue(box.tag_ranges('bubble_example'))
        self.assertEqual(box.tag_cget('bubble_example', 'foreground'), COLORS['text_secondary'])
        self.assertFalse(box.tk.call(box._w, 'tag', 'bind', 'bubble_example', '<Button-1>'))
        self.assertEqual(d.start_bubble_edit(None, 'example', 'bubble_example'), 'break')
        self.assertFalse(getattr(d, '_bubble_edit', None))
        self.assertEqual(idea_chat.strip_inline_required_markers(d._bubble_full['bubble_example']['text']), d.idea_example())
        self.assertEqual(d.draft_text(), original_draft)

    def test_a_legacy_saved_example_does_not_repopulate_the_send_box(self):
        """历史示例文件不能在翻页后伪装成用户尚未发送的内容。"""
        win, d = self.build()
        self.write_brief(d, d.idea_example() + "\n  \n")
        d.show(0)
        win.update()
        self.assertEqual(d.draft_text(), '')
        self.assertEqual(idea_chat.strip_inline_required_markers(d._bubble_full['bubble_example']['text']), d.idea_example())

    def test_the_users_own_words_show_up_on_the_display(self):
        """第 65 期任务 9：上次存下的那份创意，显示在上面那格对话展示框里。"""
        win, d = self.build()
        from stage_execution_service import project_context
        idea_chat.append(project_context(d.root), 'user', '我的创意：一只会说话的猫。',
                         model=d.idea_chat_model(), gateway=d.idea_chat_gateway())
        d.show(0)
        win.update()
        shown = str(d.idea_log.get("1.0", "end-1c"))
        self.assertIn("我的创意：一只会说话的猫。", shown, "上次存下的创意要看得见")
        self.assertEqual(d.draft_text(), '')

    def test_typing_keeps_the_send_box_as_user_owned_text(self):
        win, d = self.build()
        box = d.idea_input
        box.insert("1.0", "我的补充：一只会说话的猫。\n")
        win.update()
        self.assertEqual(d.draft_text(), "我的补充：一只会说话的猫。\n")
        from ui_tokens import COLORS
        self.assertEqual(str(box.cget("fg")), COLORS['text_primary'], "用户输入始终使用正文颜色")


class ContentBoxFitTests(unittest.TestCase):
    """第 65 期任务 7：点内容框先看到全部内容——框子按文字撑开，只长不缩。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def build(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        proj = make_adopted_project(tmp.name)
        win = self.tk.Tk()
        win.withdraw()
        self.addCleanup(lambda: win.winfo_exists() and win.destroy())
        from desktop import Desktop
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        d = Desktop(win, root=PROGRAM)
        d.root = proj
        d.show(0)
        win.update()
        return win, d

    def fill(self, win, box, lines):
        box.delete("1.0", "end")
        box.insert("1.0", "\n".join("第%d行 内容" % i for i in range(1, lines + 1)))
        win.update()

    def test_a_long_creative_box_grows_when_clicked(self):
        from responsive_ui import show_all_content
        win, d = self.build()
        box = d.idea_input
        before = int(box.cget("height"))
        self.fill(win, box, 30)
        grown = show_all_content(box)
        self.assertGreaterEqual(grown, 29, "写多少行就撑多少行（末行没有换行符，屏幕上少算一行）")
        self.assertLessEqual(grown, 30)
        self.assertGreater(int(box.cget("height")), before)

    def test_a_short_box_keeps_its_height(self):
        from responsive_ui import show_all_content
        win, d = self.build()
        box = d.idea_input
        self.fill(win, box, 1)
        before = int(box.cget("height"))        # 先放好内容再看这一刻的高度（页面自己会跟着重算）
        self.assertEqual(show_all_content(box), before, "字少的框子不会缩水")

    def test_a_very_long_composer_stays_within_the_responsive_limit(self):
        """长创意不能再把发送操作和文件表挤出当前窗口。"""
        import desktop as desktop_module
        win, d = self.build()
        box = d.idea_input
        self.fill(win, box, 200)
        d._fit_composer()
        win.update()
        fitted_height = int(box.cget("height"))
        self.assertGreaterEqual(fitted_height, desktop_module.TALK_MIN_LINES)
        self.assertLessEqual(fitted_height, desktop_module.TALK_MAX_LINES,
                             "发送框应按既有响应式上限收束，不能把操作区顶出窗口")
        self.assertIn("第200行 内容", str(box.get("1.0", "end-1c")),
                      "高度受限不许丢失用户已经输入的长内容")

    def test_the_content_boxes_keep_focus_and_resize_bindings(self):
        win, d = self.build()
        self.assertTrue(d.brief_editor[1].bind("<<Modified>>"))
        self.assertTrue(d.idea_input.bind("<<Modified>>"))
        self.assertTrue(d.idea_log.bind("<Button-1>"))

    def test_the_other_pages_share_the_same_content_box(self):
        """后期剪辑／质检页的清单框走同一份 self.text()，行为自动同步。"""
        win, d = self.build()
        box = d.text("A\nB\nC", 6)
        self.assertTrue(box.bind("<Button-1>"))
        self.assertTrue(box.bind("<FocusIn>"))


class TalkBoxFitTests(unittest.TestCase):
    """第 71 期任务 5／6：创意框按窗口剩下的地方与框里字数自适应，窗口再小也露出「发送」。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def build(self, geometry):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        proj = make_adopted_project(tmp.name)
        win = self.tk.Tk()
        self.addCleanup(lambda: win.winfo_exists() and win.destroy())
        from desktop import Desktop
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        d = Desktop(win, root=PROGRAM)
        d.root = proj
        d.show(0)
        # Desktop.__init__ 会把窗口按屏幕尺寸摆一次；要在这之后再定这一档尺寸，
        # 否则两次建的窗口实际一样大，量出来的行数也就一样。
        win.geometry(geometry)
        win.update(); win.update_idletasks()
        d._fit_talk(); win.update()
        return win, d

    def test_a_smaller_window_keeps_a_usable_composer(self):
        import desktop as desktop_module
        _big_win, big = self.build("1100x760+40+40")
        tall = int(big.idea_input.cget("height"))
        _small_win, small = self.build("940x640+40+40")
        short = int(small.idea_input.cget("height"))
        self.assertGreaterEqual(short, 1, "再挤也至少保留一行发送框")
        self.assertLessEqual(tall, desktop_module.TALK_MAX_LINES, "再高也不超过上限")
        self.assertLessEqual(short, tall, "窗口缩小时发送框不应反向膨胀")

    def test_the_send_button_stays_on_screen_when_the_window_shrinks(self):
        for geometry in ("1100x760+40+40", "940x640+40+40"):
            win, d = self.build(geometry)
            win.update()
            canvas_bottom = d.canvas.winfo_rooty() + d.canvas.winfo_height()
            row_bottom = d.idea_row.winfo_rooty() + d.idea_row.winfo_height()
            self.assertLessEqual(row_bottom, canvas_bottom + 1, geometry + " 也得看得见「发送」")
            self.assertTrue(d.idea_send.winfo_ismapped(), geometry + " 「发送」得真摆在画面上")

    def test_a_shrunk_box_grows_back_only_up_to_the_window(self):
        """字多了框子长高，但到窗口剩下的地方就到顶；字删回去又矮下来。"""
        win, d = self.build("1100x760+40+40")
        box = d.idea_input
        box.insert("end", "\n" + "\n".join("第%d 行的想法" % i for i in range(1, 26)))
        win.update(); d._fit_talk(); win.update()
        tall = int(box.cget("height"))
        box.delete("1.0", "end"); box.insert("1.0", "一句话的创意")
        win.update(); d._fit_talk(); win.update()
        self.assertLess(int(box.cget("height")), tall, "字少了框子跟着缩回去")


class StoryboardRowLayoutTests(unittest.TestCase):
    """第 67 期任务 2：分镜文件一多，底下那排按钮与那一行说明要先占好自己的位置。

    用户报的是「图片下方的按钮不显示，滑块也不能滑动」——原来表格排在最后，内容超高时它
    把按钮行顶到画布外面；现在按钮行与说明行先占位，该缩的是表格，按钮永远在看得见的地方。
    """

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def buttons(self, widget):
        from tkinter import ttk
        found = []
        def walk(w):
            if isinstance(w, ttk.Button):
                found.append(w)
            for child in w.winfo_children():
                walk(child)
        walk(widget)
        return found

    def test_the_action_row_stays_inside_the_visible_canvas(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import desktop as desktop_module
        from desktop import Desktop
        from local_video import open_studio
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            folder = storyboard_stage(proj) / "分镜文档"
            body = (folder / "episode.json").read_text(encoding="utf-8")
            listed = ["03初步分镜/分镜文档/episode.json"]
            for index in range(2, 8):          # 堆到足够多：表格一定超高
                name = "episode_%d.json" % index
                (folder / name).write_text(body, encoding="utf-8")
                listed.append("03初步分镜/分镜文档/" + name)
            prefs = json.loads((proj / "ui_settings.json").read_text(encoding="utf-8"))
            prefs["storyboard_files"] = listed
            (proj / "ui_settings.json").write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
            keep_storyboard_fresh(proj)
            original = desktop_module.Desktop.choose_project
            desktop_module.Desktop.choose_project = lambda self: None
            self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
            win = self.tk.Tk(); win.geometry("1082x772+40+40")
            def quiet_destroy():
                try:
                    win.destroy()
                except Exception:
                    pass
            self.addCleanup(quiet_destroy)
            d = Desktop(win, root=PROGRAM)
            d.root = proj
            d.studio = open_studio(proj)
            show_catalog_page_ready(d, PAGE["storyboard"])
            for _ in range(10):
                win.update()
            row = [b for b in self.buttons(d.content) if b.cget("text") == "手动采用分镜"]
            self.assertTrue(row, "初步分镜页该有「手动采用分镜」")
            top = row[0].winfo_rooty() - d.canvas.winfo_rooty()
            bottom = top + row[0].winfo_height()
            self.assertGreaterEqual(top, 0, "按钮行不许被顶到画布上边去")
            self.assertLessEqual(bottom, d.canvas.winfo_height(),
                                 "按钮行整个要落在画布可见区里——越过底边就是用户看到的「按钮不显示」")


class PageHintTests(unittest.TestCase):
    """动态页面提示要统一淡绿色，后台资产预读不得污染剧本页。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def test_notes_are_green_and_same_page_duplicates_are_reused(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import desktop as desktop_module
        from desktop import Desktop
        from local_video import open_studio
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            original = Desktop.choose_project
            Desktop.choose_project = lambda self: None
            self.addCleanup(setattr, Desktop, 'choose_project', original)
            win = self.tk.Tk(); win.withdraw(); self.addCleanup(win.destroy)
            d = Desktop(win, root=PROGRAM); d.root=proj; d.studio=open_studio(proj); d.show(0)
            first=d.note('这是一条动态提示'); second=d.note('这是一条动态提示')
            self.assertIs(first,second)
            self.assertEqual(first.cget('style'),'PaleGreenHint.TLabel')

    def test_asset_sync_failure_stays_silent_outside_assets(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import desktop as desktop_module
        from desktop import Desktop
        from local_video import open_studio
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            original_choose = Desktop.choose_project
            import stage_execution_service
            original_sync = stage_execution_service.sync_asset_plan
            Desktop.choose_project = lambda self: None
            stage_execution_service.sync_asset_plan = lambda *a, **k: (_ for _ in ()).throw(ValueError('资产目录超出当前项目'))
            self.addCleanup(setattr, Desktop, 'choose_project', original_choose)
            self.addCleanup(setattr, stage_execution_service, 'sync_asset_plan', original_sync)
            win = self.tk.Tk(); win.withdraw(); self.addCleanup(win.destroy)
            d = Desktop(win, root=PROGRAM); d.root=proj; d.studio=open_studio(proj); d.show(0)
            self.assertEqual(d.asset_requirements(),{})
            labels=[]
            def collect(widget):
                if widget.winfo_class()=='TLabel': labels.append(str(widget.cget('text')))
                for child in widget.winfo_children(): collect(child)
            collect(d.content)
            self.assertFalse(any('资产清单暂未同步' in text for text in labels),labels)


class EditorStartMenuScanTests(unittest.TestCase):
    """「启动剪映」的兜底发现不能占住 Tk 主线程。"""

    def test_launch_editor_only_queues_the_start_menu_scan(self):
        from desktop import Desktop

        class View:
            def __init__(self):
                self.queued = None
            def find_editor(self):
                return None
            def find_editor_shortcut(self):
                raise AssertionError('点击按钮时不应在主线程扫描开始菜单')
            def async_(self, work, done=None, **kwargs):
                self.queued = (work, done, kwargs)

        view = View()
        Desktop.launch_editor(view)
        self.assertIsNotNone(view.queued, '找不到标准安装路径后应把开始菜单扫描交给后台队列')
        work, _done, kwargs = view.queued
        self.assertIs(work.__self__, view)
        self.assertEqual(work.__name__, 'find_editor_shortcut')
        self.assertIn('开始菜单', kwargs.get('label', ''))

    def test_start_menu_worker_retains_the_existing_shortcut_rule(self):
        from desktop import Desktop
        with tempfile.TemporaryDirectory() as td:
            from env_test_support import patched_env
            patched_env(self, APPDATA=td, PROGRAMDATA=Path(td) / 'programdata')
            folder = Path(td) / 'Microsoft/Windows/Start Menu/Programs/剪映'
            folder.mkdir(parents=True)
            ignored = folder / '剪映专业版卸载.lnk'; ignored.write_text('', encoding='utf-8')
            expected = folder / '剪映专业版.lnk'; expected.write_text('', encoding='utf-8')
            from types import SimpleNamespace
            import desktop
            host = SimpleNamespace(media_page_services=desktop.MediaPageServices(
                *(None,) * 5, find_editor_shortcut=desktop._late('find_editor_shortcut')))
            self.assertEqual(Desktop.find_editor_shortcut(host), expected)

    def test_missing_editor_remains_a_controlled_error_after_worker_returns(self):
        from desktop import Desktop

        class View:
            def __init__(self):
                self.error = None
            def find_editor(self):
                return None
            def find_editor_shortcut(self):
                return None
            def async_(self, work, done=None, **_kwargs):
                done(work())
            def safe(self, fn):
                try:
                    fn()
                except ValueError as exc:
                    self.error = str(exc)

        view = View()
        Desktop.launch_editor(view)
        self.assertIn('未自动找到剪映专业版', view.error)


if __name__ == "__main__":
    unittest.main(verbosity=2)
