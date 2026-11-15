# -*- coding: utf-8 -*-
"""UI 边界回归（页面构建与布局域）：自 test_ui_edges.py 拆出，断言原样。"""
import json, re, tempfile, time, unittest
from skip_reasons import (
    PLATFORM_TKINTER,
)
from ui_edges_support import (
    UiEdgeCase,
    PROGRAM,
    PAGE,
    storyboard_stage,
    idea_chat,
    show_catalog_page_ready,
    widget_texts,
    make_minimal_project,
    adopt_storyboard_fixture,
    keep_storyboard_fresh,
    make_adopted_project,
    PNG,
    make_populated_project,
)

class UiEdgePagesTests(UiEdgeCase):
    """UI 边界回归（页面构建与布局域）。"""

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
            # REQ-S01-62：框上方标签改为框内占位提示，仍说明附件入口与 Enter 发送。
            self.assertIn("输入想法，Enter 发送，点 + 上传附件", texts,
                          "输入区提示应包含附件入口以及 Enter 提交方式")
            self.assertNotIn("输入想法/上传附件---->enter/发送", texts)
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
            # 聊天记录按窗口剩余空间自适应；下方发送框在空白时保留两行（契约有意变更：原一行），输入后再撑开。
            lines = int(box.cget("height"))
            self.assertGreaterEqual(lines, desktop_module.TALK_MIN_LINES, "再挤也留着下限那些行")
            self.assertLessEqual(lines, desktop_module.TALK_MAX_LINES, "字再多也不超过上限")
            self.assertEqual(int(d.idea_input.cget("height")), 2, "空白发送框两行，不再多占聊天区")
            self.assertEqual(str(d.idea_send.master), str(d.idea_row), "「发送」在内容框下面那一行")
            # REQ-S01-62：「+」在输入区下方的框内左侧，发送／终止键在框内右侧。
            frame=d.idea_composer_frame
            self.assertLessEqual(abs(d.idea_attachment_button.winfo_rootx()-d.idea_input.winfo_rootx()), 2,
                                 "上传文件图标应位于输入框内左侧")
            self.assertGreaterEqual(d.idea_attachment_button.winfo_rooty(),
                                    d.idea_input.winfo_rooty()+d.idea_input.winfo_height(), "「+」在输入区下方")
            for widget in (d.idea_attachment_button, d.idea_submit):
                self.assertGreaterEqual(widget.winfo_rootx(), frame.winfo_rootx())
                self.assertLessEqual(widget.winfo_rootx()+widget.winfo_width(), frame.winfo_rootx()+frame.winfo_width())
                self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(), frame.winfo_rooty()+frame.winfo_height())
            self.assertGreater(d.idea_submit.winfo_rootx(), d.idea_attachment_button.winfo_rootx())
            self.assertFalse(d.idea_uploaded_panel.winfo_ismapped(),
                             "未附档时不应留下空白附件行")
            frame_bottom=frame.winfo_rooty()+frame.winfo_height()
            from ui_tokens import SPACING
            self.assertEqual(d.idea_send.winfo_rooty()-frame_bottom, SPACING["xs"],
                             "发送按钮与输入框保留设计系统规定的微小防误触间距")
            d.idea_input.event_generate('<FocusOut>'); win.update()
            hint_info = d.idea_input_hint.place_info()
            # 契约有意变更：输入框空框两行后，提示对齐首行，不再按中线居中。
            self.assertEqual(hint_info.get('relx'), '0', "空闲提示应从输入框左侧定位")
            self.assertEqual(hint_info.get('anchor'), 'nw', "静态提示应左上对齐")
            self.assertAlmostEqual(
                d.idea_input_hint.winfo_rooty(),
                d.idea_input.winfo_rooty() + d.idea_input.bbox('1.0')[1],
                delta=3, msg="提示文字应与输入框首行顶边对齐")
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
            # 互相挤压到裁掉按钮文字。素材来源不适用时只有采风隐藏不占位（REQ-S01-46）。
            hidden = d.idea_row.hidden_children
            self.assertTrue(all(str(child.cget("text")) == "采风" for child in hidden))
            self.assertTrue(all(child.winfo_manager() == 'place'
                                for child in d.idea_row.winfo_children() if child not in hidden))
            actions = [str(child.cget("text")) for child in d.idea_row.winfo_children()
                       if hasattr(child, "cget") and str(child.winfo_class()).endswith("Button")]
            self.assertIn("添加剧本", actions)
            self.assertIn("质检报告", actions)
            # REQ-S01-76：删除改由表格多选后右键，底栏不再有「删除」「下载文件」。
            self.assertNotIn("删除", actions)
            self.assertNotIn("下载文件", actions)
            self.assertEqual(str(d.script_box.winfo_class()), "TFrame")
            self.assertTrue(d.script_box.winfo_ismapped(),
                            "发现已有剧本文件时，三列表容器与列头必须保持可见")
            # R1862：四类文件复原为四张并排表，每张表头即分类名；REQ-S01-76 去掉勾选列，改为 Ctrl／Shift 多选。
            titles = {"setting": "项目设定", "outline": "项目大纲", "character": "角色卡", "script": "项目剧本"}
            self.assertEqual(tuple(d.script_trees), tuple(titles))
            names = {}
            for category, tree in d.script_trees.items():
                self.assertEqual(str(tree.heading("name", "text")), titles[category])
                self.assertEqual(tuple(tree["columns"]), ("name",))
                self.assertNotIn("time", tuple(tree["columns"]), "剧本准备文件表不显示修改日期列")
                self.assertEqual(int(tree.cget("height")), len(tree.get_children()),
                                 "表高按行数收紧")
                self.assertEqual(tuple(map(str, win.tk.splitlist(tree.cget("show")))), ("headings",),
                                 "剧本文件表不再显示勾选列，只有文件名一列")
                self.assertEqual(str(tree.cget("selectmode")), "extended", "剧本文件表支持 Ctrl／Shift 多选")
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
            session = d.script_structure_source_preview_edit_session
            d.script_structure_source_preview.insert("end", "\n新增修订。")
            original = d.script_structure_source_preview.get("1.0", "1.4")
            d.script_structure_source_preview.delete("1.0", "1.4")
            session.undo_step(); win.update()
            self.assertEqual(d.script_structure_source_preview.get("1.0", "1.4"), original)
            session.save_now(); win.update()
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
        self.assertFalse(hasattr(d, 'start_bubble_edit'))
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
        shown = ''
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            win.update()
            shown = str(d.idea_log.get("1.0", "end-1c"))
            if "我的创意：一只会说话的猫。" in shown:
                break
            time.sleep(.01)
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
