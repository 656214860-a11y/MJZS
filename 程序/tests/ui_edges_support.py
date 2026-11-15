# -*- coding: utf-8 -*-
"""test_ui_edges 拆分出的共享项目夹具与页面辅助（R2599 结构治理：内容自 test_ui_edges.py 原样迁入）。"""
import json, os, sys, time, unittest
from pathlib import Path

HERE = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, HERE)
os.chdir(HERE)

import idea_chat
from catalog_page_test_support import show_catalog_page_ready
from widget_test_support import widget_texts as _widget_texts
from pet_state import PAGE_OF as PAGE
from project_stages import storyboard as storyboard_stage, stage as stage_dir, editing as editing_stage, exports as export_stage
import desktop as desktop_doc

PROGRAM = HERE
FFMPEG = r"D:/Tools/ffmpeg/bin/ffmpeg.exe"
FFPROBE = r"D:/Tools/ffmpeg/bin/ffprobe.exe"

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

class UiEdgeCase(unittest.TestCase):
    def setUp(self):
        """第 32 期第 2 条：无人值守的勾选框现在勾上就先弹一次确认——用例里默认放行，
        确认逻辑本身由 test_unattended_switch_asks_first 单独盯着。"""
        import project_settings_dialog
        real = project_settings_dialog.confirm_unattended
        self.addCleanup(setattr, project_settings_dialog, "confirm_unattended", real)
        project_settings_dialog.confirm_unattended = lambda *a, **k: True

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

__all__ = [
    'UiEdgeCase', 'HERE', 'PROGRAM', 'FFMPEG', 'FFPROBE',
    'PAGE', 'storyboard_stage', 'stage_dir', 'editing_stage', 'export_stage',
    'idea_chat', 'show_catalog_page_ready', 'desktop_doc',
    'final_storyboard_dir', 'final_dirs', 'popup_windows', 'widget_texts',
    'make_minimal_project', 'adopt_storyboard_fixture', 'keep_storyboard_fresh',
    'make_adopted_project', 'settle_workers', 'with_dialogue', 'PNG',
    'real_png', 'make_populated_project',
]
