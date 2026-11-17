# -*- coding: utf-8 -*-
"""UI 边界回归（控件与选择器域）：自 test_ui_edges.py 拆出，断言原样。"""
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
    show_catalog_page_ready,
    popup_windows,
    make_minimal_project,
    adopt_storyboard_fixture,
    keep_storyboard_fresh,
    make_adopted_project,
)

class UiEdgeControlsTests(UiEdgeCase):
    """UI 边界回归（控件与选择器域）。"""

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
            from infra import clipboard_lock
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
            from infra import clipboard_lock
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
            from domain.asset_reference_prompts import display_prompt
            from asset_reference_prompts_dialog import show_prompt
            d = Desktop(win, root=PROGRAM)
            d.root = proj
            d.studio = open_studio(proj)
            d.show(PAGE["assets"]); win.update()
            asset = {"name": "测试角色", "image_prompt": "一只猫在窗边", "negative_prompt": "模糊"}
            show_prompt(d, "CHAR_001", asset); win.update()
            popups = popup_windows(win, self.tk)
            self.assertEqual(len(popups), 1)
            popup = popups[0]
            from infra import clipboard_lock
            with clipboard_lock.hold():                             # 第 65 期第 12 条：剪贴板是全机器共用的一块，几路并行要排队用
                [w for w in popup.actions.winfo_children() if isinstance(w, ttk.Button) and str(w.cget("text")) == "复制提示词"][0].invoke()
                win.update()
                self.assertFalse(popup.winfo_exists())          # 复制成功后关窗
                self.assertEqual(win.clipboard_get(), display_prompt(asset))
            self.assertIn("已复制", d.status.get())

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
        import infra.project_settings as project_settings
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
