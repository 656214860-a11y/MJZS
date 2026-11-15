# -*- coding: utf-8 -*-
"""UI 边界回归（无人值守／自动链域）：自 test_ui_edges.py 拆出，断言原样。"""
import json, os, tempfile, time, unittest
from pathlib import Path
from skip_reasons import (
    PLATFORM_TKINTER,
)
from ui_edges_support import (
    UiEdgeCase,
    PROGRAM,
    PAGE,
    storyboard_stage,
    editing_stage,
    export_stage,
    show_catalog_page_ready,
    final_dirs,
    popup_windows,
    make_minimal_project,
    keep_storyboard_fresh,
    make_adopted_project,
    settle_workers,
    with_dialogue,
    PNG,
)

class UiEdgeAutoTests(UiEdgeCase):
    """UI 边界回归（无人值守／自动链域）。"""

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
