# -*- coding: utf-8 -*-
"""UI 边界回归（表格与缩略图域）：自 test_ui_edges.py 拆出，断言原样。"""
import json, sys, tempfile, time, unittest
from skip_reasons import (
    PLATFORM_TKINTER,
)
from ui_edges_support import (
    UiEdgeCase,
    PROGRAM,
    PAGE,
    storyboard_stage,
    show_catalog_page_ready,
    desktop_doc,
    popup_windows,
    make_minimal_project,
    adopt_storyboard_fixture,
    keep_storyboard_fresh,
    make_adopted_project,
    PNG,
    real_png,
    make_populated_project,
)

class UiEdgeTablesTests(UiEdgeCase):
    """UI 边界回归（表格与缩略图域）。"""

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

class AutoHeightScrollbarTests(unittest.TestCase):
    """auto_height 算行数时要把露着的横向滚动条一起扣掉。

    页面放不下时，容器拿到的高度就是表格自己请求的高度。padding 只够表头、不够「表头＋滚动条」时，
    算回来的行数与现在一样：表格收不回去，排在它后面的按钮被挤出可视区；再叠上请求高度的传播延迟，
    两个在途的行数互相追着改，资产页在窄窗口里整窗卡死（主题下表头 43＋滚动条 8，比默认的 48 多 3）。
    """

    def test_the_table_gives_room_back_when_the_page_gets_short(self):
        from tkinter import ttk
        import tk_test_support
        from responsive_ui import auto_height, row_height_of
        from ui_widgets import DataTable
        win = tk_test_support.make_root()
        self.addCleanup(win.destroy)
        page = ttk.Frame(win, width=420, height=200)
        page.pack_propagate(False)
        page.pack()
        box = ttk.Frame(page)
        box.pack(fill='both', expand=True)
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)
        shell = DataTable(box, columns=[('name', '名称', 160), ('note', '说明', 200)])
        shell.grid(row=0, column=0, sticky='nsew')
        tree, bar = shell.tree, shell.horizontal_scrollbar
        for index in range(12):
            tree.insert('', 'end', values=('第 %d 行' % (index + 1), ''))
        shell.refresh_empty_state()
        row = row_height_of(tree)
        footer = ttk.Frame(page, width=10, height=row)      # 排在表格后面的那排按钮
        footer.pack(fill='x')
        tk_test_support.pump(win, .1)
        self.assertTrue(bar.winfo_manager(), '这张表的横向滚动条一直露着')
        header = tree.winfo_reqheight() - int(tree.cget('height')) * row
        fixed = header + bar.winfo_reqheight()
        # 与页面上的情形一样：padding 比表头多 5 像素，但没把滚动条算在内。
        auto_height(tree, box, padding=header + 5)
        page.configure(height=8 * row + fixed + row + 60)
        tk_test_support.pump(win, .3)
        self.assertGreater(int(tree.cget('height')), 3, '页面够高时表格跟着长高')
        # 变矮到「三行差半行放不下」：表格得收到两行，把底下那排的位置让出来。
        page.configure(height=3 * row + fixed + row - row // 2)
        tk_test_support.pump(win, .3)
        self.assertEqual(int(tree.cget('height')), 2, '表格没收回最少行数')
        self.assertTrue(footer.winfo_ismapped(), '底下那排被整个挤没了')
        self.assertEqual(footer.winfo_height(), row, '底下那排被挤掉了一截')


class GrowableScopeTests(unittest.TestCase):
    """整页定高只收回「正在显示的这一页」里表格多出来的行。

    登记表是整个程序共用的一张：整页缓存收起来的那几页、弹出来的对话框，表格都还活着。把它们多出来的
    行也从这一页的请求高度里扣掉，这一页就被定得比自己的内容还矮——窗口小的时候表格被压扁、
    底下的按钮被裁掉，而且滚不到。
    """

    ROW = 10        # 登记给表格的行高：只参与算术，不必等于主题里的真实行高

    def setUp(self):
        from unittest import mock
        import responsive_ui
        import tk_test_support
        self.ui = responsive_ui
        patcher = mock.patch.object(responsive_ui, '_growables', [])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.win = tk_test_support.make_root()
        def quiet_destroy():
            try:
                self.win.destroy()
            except Exception:
                pass
        self.addCleanup(quiet_destroy)

    def table(self, parent, rows):
        from tkinter import ttk
        tree = ttk.Treeview(parent, height=rows)
        tree.pack()
        self.ui.register_growable(tree, self.ROW, 0)
        return tree

    def extra(self, rows):
        return (rows - self.ui.GROWABLE_FLOOR) * self.ROW

    def test_only_tables_under_the_scope_are_counted(self):
        from tkinter import ttk
        shown, cached = ttk.Frame(self.win), ttk.Frame(self.win)
        self.table(ttk.Frame(shown), 10)
        self.table(cached, 30)
        self.assertEqual(self.ui.growable_extra(shown), self.extra(10), '隔了一层也算在这一页里')
        self.assertEqual(self.ui.growable_extra(cached), self.extra(30))
        self.assertEqual(self.ui.growable_extra(), self.extra(10) + self.extra(30), '不给范围时照旧全数')

    def test_a_sibling_whose_name_starts_the_same_is_outside(self):
        from tkinter import ttk
        page, other = ttk.Frame(self.win, name='page'), ttk.Frame(self.win, name='page2')
        self.table(other, 12)
        self.assertEqual(self.ui.growable_extra(page), 0, '.page2 不在 .page 底下，不能按字符串前缀算进去')
        self.assertEqual(self.ui.growable_extra(other), self.extra(12))

    def test_destroyed_tables_are_dropped_whatever_the_scope(self):
        from tkinter import ttk
        shown, cached = ttk.Frame(self.win), ttk.Frame(self.win)
        kept = self.table(shown, 6)
        self.table(cached, 9).destroy()
        self.assertEqual(self.ui.growable_extra(shown), self.extra(6))
        self.assertEqual([entry[0] for entry in self.ui._growables], [kept],
                         '销毁了的表格要从登记表里清掉，哪怕它不在这一次的范围里')

    def test_page_fit_ignores_tables_on_pages_that_are_put_away(self):
        import tkinter as tk
        from tkinter import ttk
        from desktop_layout import LayoutMixin
        win = self.win
        win.geometry('800x300')
        canvas = tk.Canvas(win, highlightthickness=0)
        canvas.pack(fill='both', expand=True)
        shown, cached = ttk.Frame(canvas), ttk.Frame(canvas)
        for page, rows in ((shown, 10), (cached, 30)):
            ttk.Frame(page, width=10, height=600).pack()     # 这一页里收不回去的那部分，比窗口高
            self.table(page, rows)

        class Layout(LayoutMixin):
            def align_header(self):
                pass

        d = Layout()
        d.win, d.canvas, d.content, d.page_index = win, canvas, shown, -1
        d.content_id = canvas.create_window(0, 0, window=shown, anchor='nw')
        win.update()
        width, req, target = d._fit_content_now()
        self.assertGreater(req - self.extra(10), canvas.winfo_height(), '用例前提：收回自己的表格后这一页仍比窗口高')
        self.assertEqual(target, req - self.extra(10), '收起来的那一页的表格不该从这一页的高度里扣')
        # 换到收着的那一页（整页缓存就是这样换的）：轮到它自己的表格算数，原来那一页的不算。
        d.content = cached
        canvas.itemconfigure(d.content_id, window=cached)
        win.update()
        width, req, target = d._fit_content_now()
        self.assertGreater(req - self.extra(30), canvas.winfo_height(), '用例前提同上')
        self.assertEqual(target, req - self.extra(30))

    def test_a_real_page_keeps_its_height_after_the_storyboard_page_is_put_away(self):
        """真实界面：大窗口里看过初步分镜（整页缓存），换到结构剧本再把窗口拉矮。

        收起来的初步分镜页不再跟着窗口改行数，它的表格一直留着大窗口时的那么多行；这些行要是从
        结构剧本页的高度里扣，结构剧本页就被定得比自己的内容矮、底下一截看不到也滚不到。
        """
        import desktop as desktop_module
        import tk_test_support
        from desktop import Desktop
        from local_video import open_studio
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            folder = storyboard_stage(proj) / "分镜文档"
            body = (folder / "episode.json").read_text(encoding="utf-8")
            listed = ["03初步分镜/分镜文档/episode.json"]
            for index in range(2, 8):          # 分镜文件够多：大窗口里表格会长到好几行
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
            win = self.win
            d = Desktop(win, root=PROGRAM)
            d.root = proj
            d.studio = open_studio(proj)
            tk_test_support.pump(win, .3)
            win.geometry("1008x900+40+40")
            tk_test_support.pump(win, .5)
            show_catalog_page_ready(d, PAGE["storyboard"])
            tk_test_support.pump(win, .8)
            storyboard = d.content
            d.go_page(PAGE["script_structure"])      # 侧栏换页：初步分镜页整页收进缓存
            tk_test_support.pump(win, 1.2)
            win.geometry("1008x700+40+40")
            tk_test_support.pump(win, 1.2)
            self.assertEqual(d.page_index, PAGE["script_structure"])
            self.assertTrue(storyboard.winfo_exists() and d.content is not storyboard, '用例前提：初步分镜页收在缓存里')
            self.assertGreater(self.ui.growable_extra(storyboard), 0, '用例前提：收着的那一页里表格还留着多出来的行')
            needed = d.content.winfo_reqheight() - self.ui.growable_extra(d.content)
            self.assertGreater(needed, d.canvas.winfo_height(), '用例前提：窗口拉矮后这一页比窗口高')
            region = [int(float(value)) for value in str(d.canvas.cget('scrollregion')).split()]
            self.assertEqual(region[3], needed, '结构剧本页被定矮了：收着的初步分镜页的表格不该从这一页的高度里扣')
