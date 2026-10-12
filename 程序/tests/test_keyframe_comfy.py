# -*- coding: utf-8 -*-
"""COM: 首帧制作弹窗（内嵌 ComfyUI）回归。运行：python test_keyframe_comfy.py"""
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

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)


def make_project(td, with_frame=("SH001",), deleted=("SH003",)):
    proj = Path(td) / "p"
    (proj / "episode" / "frames").mkdir(parents=True)
    shots = []
    for sid in ("SH001", "SH002", "SH003"):
        shot = {"id": sid, "title": sid + " 内容", "duration": 5, "frame": "frames/" + sid + ".png",
                "frame_prompt": sid + " 的画面提示", "characters": ["CHAR_001"], "location": "LOC_001"}
        if sid in deleted:
            shot["frame_deleted"] = True
        shots.append(shot)
    src = proj / "episode" / "episode.json"
    src.write_text(json.dumps({"episode_id": "EP001", "title": "T", "shots": shots}, ensure_ascii=False), encoding="utf-8")
    for sid in with_frame:
        (proj / "episode" / "frames" / (sid + ".png")).write_bytes(b"\x89PNG\r\n\x1a\n")
    return proj, src


def add_asset_registry(proj):
    """首帧 Agent 提交任务时需要能解析资产登记表。"""
    (proj / "config.json").write_text(json.dumps({
        "episode_dir": str(proj / "episode"), "episode_file": str(proj / "episode" / "episode.json")},
        ensure_ascii=False), encoding="utf-8")
    (proj / "episode" / "assets.json").write_text(json.dumps({
        "CHAR_001": {"name": "角色"}, "LOC_001": {"name": "场景"}}, ensure_ascii=False), encoding="utf-8")
    return proj


class SettingsValidationTests(unittest.TestCase):
    def test_missing_settings_uses_the_auto_batch_required_fields(self):
        from keyframe_comfy import missing_settings
        self.assertEqual(missing_settings({'url': 'http://127.0.0.1:8188', 'model': 'flux'}),
                         ['text_encoder', 'vae'])

    def test_missing_settings_rejects_whitespace_values(self):
        from keyframe_comfy import missing_settings
        self.assertEqual(missing_settings({'url': ' ', 'model': '\t', 'text_encoder': 't5', 'vae': 'ae'}),
                         ['url', 'model'])


class StubApp:
    def __init__(self, win, root, source):
        import tkinter as tk
        self.win = win; self.root = Path(root); self.app = Path(HERE); self.source = Path(source)
        self.settings = {}; self.safe_errors = []
        self.status = tk.StringVar(); self.launched = []; self.worker = False

    def safe(self, fn):
        try:
            return fn()
        except Exception as exc:
            self.safe_errors.append(str(exc)); return None

    def async_(self, fn, done=None):
        value = fn()
        if done: done(value)
        return value

    def launch_comfy(self):
        return True

    def current_frame_json(self):
        return self.source

    def open_flow_agent(self, *args, **kwargs):
        self.launched.append((args, kwargs))

    def flow_settings(self, *args, **kwargs):
        self.settings_opened = (args, kwargs)


class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def open_dialog(self, td, stage_model=None):
        import tkinter as tk
        import keyframe_comfy
        # 隔离真实 batch_frames_tool/config.json，避免自检改动用户设置。
        target = Path(td) / "batch_config.json"
        target.write_text(json.dumps({"url": "http://127.0.0.1:8188", "model": "", "text_encoder": "",
                                      "vae": "", "width": 768, "height": 432}, ensure_ascii=False), encoding="utf-8")
        original = keyframe_comfy.CONFIG_FILE
        keyframe_comfy.CONFIG_FILE = target
        self.addCleanup(setattr, keyframe_comfy, "CONFIG_FILE", original)
        from keyframe_comfy import show
        proj, src = make_project(td)
        if stage_model:                       # 第 46 期第 7 条：模型只在「阶段配置 → 模型」挑
            import stage_config
            stage_config.put(proj, "keyframe", model=stage_model)
        win = tk.Tk(); win.geometry('900x700+30+30')
        win._tick_images = [tk.PhotoImage(width=12, height=12), tk.PhotoImage(width=12, height=12)]
        self.addCleanup(win.destroy)
        app = StubApp(win, proj, src)
        dialog = show(app, src)
        self.addCleanup(dialog.destroy)
        win.update()
        return win, app, dialog, src

    def widgets(self, widget, kind):
        found = [widget] if isinstance(widget, kind) else []
        for child in widget.winfo_children():
            found.extend(self.widgets(child, kind))
        return found

    def test_dialog_lists_only_shots_without_frames(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        with tempfile.TemporaryDirectory() as td:
            win, app, dialog, src = self.open_dialog(td)
            trees = [w for w in self.widgets(dialog, ttk.Treeview)]
            self.assertEqual(len(trees), 1)
            table = trees[0]
            self.assertEqual(list(table.get_children()), ["SH002"])
            # 勾选框独立成列，位于「镜头号」之前；镜头号只放文本。
            self.assertEqual(table.item("SH002", "text"), "")
            self.assertEqual(table.set("SH002", "shot"), "SH002")
            self.assertIn("SH002 的画面提示", table.set("SH002", "prompt"))
            self.assertEqual(table.set("SH002", "references"), "2 个")
            self.assertEqual(table.heading("#0", "text"), "")
            self.assertEqual(table.heading("shot", "text"), "镜头号")
            self.assertEqual(list(table["columns"])[0], "shot")
            self.assertLessEqual(int(table.column("#0", "width")), 40)

    def test_dialog_controls_and_click_toggle(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        from keyframe_comfy import FORMATS
        with tempfile.TemporaryDirectory() as td:
            win, app, dialog, src = self.open_dialog(td)
            labels = [str(w.cget("text")) for w in self.widgets(dialog, (ttk.Button, self.tk.Button))]
            for text in ("开始逐镜生成", "停止后续镜头", "检查参考资产",
                         "保存设置", "启动并检测", "删除模型", "生成记录", "关闭", "Skill 调用设置", "阶段配置"):
                self.assertIn(text, labels)
            notes = [str(w.cget("text")) for w in self.widgets(dialog, ttk.Label)]
            self.assertIn("图片格式", notes)
            boxes = [w for w in self.widgets(dialog, ttk.Combobox)]
            self.assertIn(list(FORMATS), [list(box["values"]) for box in boxes])
            from keyframe_comfy import MODELS, ASPECTS, current_model
            values = [list(box["values"]) for box in boxes]
            self.assertIn(list(ASPECTS), values)                       # 云端画幅
            # 第 46 期第 7 条：模型不再摆第二个下拉框（原本与「阶段配置 → 模型」重复）。
            self.assertEqual([value for value in values if value and value[0] == MODELS[0]], [])
            shown = [w for w in self.widgets(dialog, ttk.Label)
                     if str(w.cget("textvariable")) and dialog.getvar(str(w.cget("textvariable"))) == current_model(app.root)]
            self.assertEqual(len(shown), 1)                            # 「模型」那一行只读显示当前模型
            frames = [str(w.cget("text")) for w in self.widgets(dialog, ttk.Label)]
            self.assertTrue(any("ComfyUI" in text for text in frames))
            self.assertFalse(any("Agent" in text for text in frames))  # 不再有重复的 Agent 接口框
            table = [w for w in self.widgets(dialog, ttk.Treeview)][0]
            off, on = win._tick_images
            self.assertEqual(table.item("SH002", "image")[0], str(on))
            x, y, width, height = table.bbox("SH002", "#1")
            table.event_generate("<Button-1>", x=int(x + width // 2), y=int(y + height // 2))
            win.update()
            self.assertEqual(table.item("SH002", "image")[0], str(off))
            x, y, width, height = table.bbox("SH002", "#1")
            table.event_generate("<Button-1>", x=int(x + width // 2), y=int(y + height // 2))
            win.update()
            self.assertEqual(table.item("SH002", "image")[0], str(on))
            start = [w for w in self.widgets(dialog, ttk.Button) if str(w.cget("text")) == "开始逐镜生成"][0]
            start.invoke()
            self.assertTrue(app.safe_errors)
            self.assertIn("图像模型", app.safe_errors[-1])

    def click_header_check(self, table, win):
        """点表头勾选框（全选/取消）：ttk 表头命令在按下再释放后才触发。"""
        _, top, _, _ = table.bbox(table.get_children()[0], "#0")
        y = max(2, int(top // 2))
        table.event_generate("<Button-1>", x=8, y=y)
        table.event_generate("<ButtonRelease-1>", x=8, y=y)
        win.update()

    def checked_states(self, table, win):
        on = str(win._tick_images[1])
        return [table.item(item, "image")[0] == on for item in table.get_children()]

    def test_header_checkbox_selects_and_clears_all(self):
        """表头勾选框要能全选：此前方向相反，点表头只会全部取消，看起来就是「勾不上」。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        with tempfile.TemporaryDirectory() as td:
            win, app, dialog, src = self.open_dialog(td)
            table = [w for w in self.widgets(dialog, ttk.Treeview)][0]
            self.assertEqual(self.checked_states(table, win), [True])       # 待生成镜头默认勾选
            self.click_header_check(table, win)
            self.assertEqual(self.checked_states(table, win), [False])      # 表头 → 全部取消
            self.click_header_check(table, win)
            self.assertEqual(self.checked_states(table, win), [True])       # 表头 → 重新全选
            x, y, width, height = table.bbox("SH002", "#0")
            table.event_generate("<Button-1>", x=int(x + width // 2), y=int(y + height // 2))
            win.update()
            self.assertEqual(self.checked_states(table, win), [False])      # 单行取消勾选
            self.click_header_check(table, win)
            self.assertEqual(self.checked_states(table, win), [True])       # 部分勾选时点表头 → 全选

    def test_reference_check_stays_local(self):
        """「检查参考资产」只读本地文件：不再占用 app.async_，避免连 ComfyUI 时整机卡住。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from tkinter import ttk
        with tempfile.TemporaryDirectory() as td:
            win, app, dialog, src = self.open_dialog(td)
            background = []
            app.async_ = lambda fn, done=None: background.append(fn)
            check = [w for w in self.widgets(dialog, ttk.Button) if str(w.cget("text")) == "检查参考资产"][0]
            check.invoke()
            win.update()
            self.assertEqual(background, [])                               # 未走后台任务
            self.assertFalse(app.safe_errors)
            log = self.widgets(dialog, self.tk.Text)[0].get("1.0", "end")
            self.assertIn("参考资产检查完成", log)
            self.assertIn("SH002：", log)                                  # 缺参考图的镜头被列出并跳过

    def test_settings_roundtrip_keeps_other_keys(self):
        import keyframe_comfy
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "config.json"
            target.write_text(json.dumps({"url": "http://127.0.0.1:8188", "model": "m", "text_encoder": "t",
                                          "vae": "v", "width": 432, "height": 768, "api_settings_saved": True,
                                          "自定义": 1}, ensure_ascii=False), encoding="utf-8")
            original = keyframe_comfy.CONFIG_FILE
            keyframe_comfy.CONFIG_FILE = target
            self.addCleanup(setattr, keyframe_comfy, "CONFIG_FILE", original)
            settings = keyframe_comfy.initial_settings()
            self.assertEqual((settings["model"], settings["width"], settings["height"]), ("m", 432, 768))
            self.assertEqual(keyframe_comfy.format_of(432, 768), "竖屏 432×768")
            data = keyframe_comfy.write_settings({"url": "http://127.0.0.1:8188", "model": "m2", "text_encoder": "t",
                                                  "vae": "v", "width": 768, "height": 432, "shot_ids": ["SH002"]})
            self.assertNotIn("shot_ids", data)
            self.assertEqual(data["自定义"], 1)
            self.assertTrue(data["api_settings_saved"])
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["model"], "m2")

    def test_merged_selector_runs_first_frame_agent(self):
        """合并后的模型下拉框里选 Agent 引擎，开始按钮把勾选镜头交给首帧 Agent。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import keyframe_comfy
        import stage_models
        from tkinter import ttk
        from keyframe_comfy import MODELS
        with tempfile.TemporaryDirectory() as td:
            agent = [value for value, _label in stage_models.keyframe_choices(Path(td) / "p")
                     if value not in MODELS][0]
            win, app, dialog, src = self.open_dialog(td, stage_model=agent)
            add_asset_registry(Path(app.root))
            # 第 46 期第 7 条：窗口显示的就是阶段配置里那一档（不再有下拉框可切）。
            self.assertEqual(keyframe_comfy.current_model(app.root), agent)
            shown = [w for w in self.widgets(dialog, ttk.Label)
                     if str(w.cget("textvariable")) and dialog.getvar(str(w.cget("textvariable"))) == agent]
            self.assertEqual(len(shown), 1)
            start = [w for w in self.widgets(dialog, ttk.Button) if str(w.cget("text")) == "开始逐镜生成"][0]
            start.invoke()
            win.update()
            self.assertTrue(app.launched)                      # 已交给桌面 Agent 窗口
            log = self.widgets(dialog, self.tk.Text)[0]
            self.assertIn("Agent 窗口提交", log.get("1.0", "end"))
            batch = list((Path(app.root) / "workflows" / "首帧批次").glob("*/批次.json"))
            self.assertEqual(len(batch), 1)
            self.assertEqual([item["shot_id"] for item in json.loads(batch[0].read_text(encoding="utf-8"))["items"]], ["SH002"])
            self.assertFalse(app.safe_errors)                  # 不应有报错弹窗

    def test_pending_shots_skips_existing_and_deleted(self):
        from keyframe_comfy import pending_shots
        with tempfile.TemporaryDirectory() as td:
            proj, src = make_project(td)
            shots = json.loads(src.read_text(encoding="utf-8"))["shots"]
            pending = [shot["id"] for shot in pending_shots(shots, proj / "episode")]
            self.assertEqual(pending, ["SH002"])


class AutoBatchTests(unittest.TestCase):
    """无人值守自动补首帧：沿用首帧制作窗口保存的本地 ComfyUI 设置，缺设置明确报错，未运行时自动拉起 ComfyUI。"""

    def test_auto_batch_requires_saved_local_settings(self):
        import keyframe_comfy
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            proj, src = make_project(td)
            with patch.object(keyframe_comfy, "saved_settings", lambda: {"url": "http://127.0.0.1:8188", "model": "m"}):
                with self.assertRaises(ValueError) as ctx:
                    keyframe_comfy.auto_batch(src, lambda text: None)
        message = str(ctx.exception)
        self.assertIn("text_encoder", message)
        self.assertIn("vae", message)

    def test_auto_batch_starts_comfy_and_reuses_saved_settings(self):
        import keyframe_comfy, native_apps
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            proj, src = make_project(td)
            settings = {"url": "http://127.0.0.1:8188", "model": "flux-klein", "text_encoder": "t5", "vae": "ae",
                        "width": 768, "height": 432, "shot_ids": ["SH001"], "shot_id": "SH001", "model_name": "x"}
            calls = {"waits": []}
            launched = []
            logs = []

            class StubBatch:
                def run(self, source, values, log, stop=None):
                    calls["source"] = source
                    calls["values"] = dict(values)
                    log("批次逐镜日志")
                    # 引擎生成完一镜：写出首帧图片，下一次 pending_shots 就不再有它
                    (proj / "episode" / "frames" / "SH002.png").write_bytes(b"\x89PNG\r\n\x1a\n")

            def wait(url, report=None, timeout=90, cancelled=None):
                calls["waits"].append((url, timeout))
                if len(calls["waits"]) == 1:
                    raise ValueError("本地 ComfyUI 未运行")      # 首次探测：没起来
                return True

            with patch.object(keyframe_comfy, "saved_settings", lambda: dict(settings)), \
                 patch.object(keyframe_comfy, "engine", lambda: StubBatch()), \
                 patch.object(native_apps, "wait_comfy", wait), \
                 patch.object(native_apps, "open_comfy", lambda settings=None: launched.append(settings)):
                summary = keyframe_comfy.auto_batch(src, logs.append)
            self.assertEqual(calls["waits"], [("http://127.0.0.1:8188", 5), ("http://127.0.0.1:8188", 120)])
            self.assertEqual(launched, [None])                    # 探测失败后自动拉起 ComfyUI
            self.assertNotIn("shot_ids", calls["values"])         # 批次范围按缺首帧镜头决定，不带窗口里的勾选
            self.assertNotIn("shot_id", calls["values"])
            self.assertEqual(calls["values"]["model"], "flux-klein")
            self.assertEqual(Path(calls["source"]), src.resolve())
            self.assertIn("批次逐镜日志", logs)
            self.assertIn("处理 1 镜", summary)
            self.assertIn("已生成 1 镜", summary)
            self.assertNotIn("仍未完成", summary)

    def test_auto_batch_keeps_reporting_unfinished_shots(self):
        import keyframe_comfy, native_apps
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            proj, src = make_project(td)
            settings = {"url": "http://127.0.0.1:8188", "model": "m", "text_encoder": "t5", "vae": "ae"}

            class StubBatch:
                def run(self, source, values, log, stop=None):
                    return None                                   # 一镜都没生成（参考图缺失等由引擎逐镜记录）

            with patch.object(keyframe_comfy, "saved_settings", lambda: dict(settings)), \
                 patch.object(keyframe_comfy, "engine", lambda: StubBatch()), \
                 patch.object(native_apps, "wait_comfy", lambda url, report=None, timeout=90, cancelled=None: True), \
                 patch.object(native_apps, "open_comfy", lambda settings=None: self.fail("已就绪时不应再拉起 ComfyUI")):
                summary = keyframe_comfy.auto_batch(src, lambda text: None)
            self.assertIn("处理 1 镜", summary)
            self.assertIn("已生成 0 镜", summary)
            self.assertIn("仍未完成 1 镜", summary)


class ResubmitTests(unittest.TestCase):
    """关闭 Agent 窗口后，未完成的首帧任务可以放弃并重新提交。"""
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def test_confirm_abandons_old_task_and_resubmits(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import tkinter as tk
        import tkinter.messagebox as messagebox
        import keyframe_import
        from agent.core import read, save
        with tempfile.TemporaryDirectory() as td:
            proj, src = make_project(td, with_frame=(), deleted=())
            add_asset_registry(proj)
            shot_ids = ["SH001", "SH002", "SH003"]
            old = proj / "workflows/首帧批次/old/批次.json"
            save(old, {"source": str(src), "items": [
                {"shot_id": sid, "state": "pending", "output": sid + ".png"} for sid in shot_ids]})
            win = self.tk.Tk(); win.withdraw()
            self.addCleanup(win.destroy)
            launched = []
            class App:
                app = Path(HERE)
                def __init__(self):
                    self.win = win; self.root = proj; self.status = tk.StringVar()
                def launch_comfy(self, silent=False):
                    return False
                def open_flow_agent(self, *args, **kwargs):
                    launched.append((args, kwargs))
            real = __import__('ui_widgets').ask_confirmation
            import ui_widgets
            ui_widgets.ask_confirmation = lambda *a, **k: True
            self.addCleanup(setattr, ui_widgets, "ask_confirmation", real)
            keyframe_import.launch(App(), src, shot_ids=shot_ids)
            self.assertTrue(launched)
            old_items = {item["shot_id"]: item["state"] for item in read(old)["items"]}
            self.assertEqual(set(old_items.values()), {"cancelled"})
            pending = keyframe_import.pending_tasks(proj, src)
            self.assertEqual(set(pending), set(shot_ids))          # 新任务已为这些镜头排队
            self.assertNotIn(old, set(pending.values()))          # 排队的是新的批次清单

    def test_declining_keeps_old_task(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import tkinter as tk
        import tkinter.messagebox as messagebox
        import keyframe_import
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            proj, src = make_project(td, with_frame=(), deleted=())
            add_asset_registry(proj)
            shot_ids = ["SH001"]
            old = proj / "workflows/首帧批次/old/批次.json"
            save(old, {"source": str(src), "items": [{"shot_id": "SH001", "state": "pending", "output": "SH001.png"}]})
            win = self.tk.Tk(); win.withdraw()
            self.addCleanup(win.destroy)
            launched = []
            class App:
                app = Path(HERE)
                def __init__(self):
                    self.win = win; self.root = proj; self.status = tk.StringVar()
                def launch_comfy(self, silent=False):
                    return False
                def open_flow_agent(self, *args, **kwargs):
                    launched.append(args)
            real = __import__('ui_widgets').ask_confirmation
            import ui_widgets
            ui_widgets.ask_confirmation = lambda *a, **k: False
            self.addCleanup(setattr, ui_widgets, "ask_confirmation", real)
            keyframe_import.launch(App(), src, shot_ids=shot_ids)
            self.assertEqual(launched, [])
            self.assertEqual(list(keyframe_import.pending_tasks(proj, src)), ["SH001"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
