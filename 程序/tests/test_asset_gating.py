# -*- coding: utf-8 -*-
"""资产勾选门禁回归：
1) 资产管理页（第 05 步）资产编号列勾选框；无勾选时禁用资产表下方的
   制作/导入按钮（参考图目录/打开 ComfyUI 及顶部
   检查提示词/识别背景人物不受限）；
2) 资产图片制作窗口：只剩「启动并检测／取消检测」，随勾选禁用，紧邻进度条下方；
   检测通过就自动开跑（第 65 期任务 1：手动制作资产／桌面打开 ComfyUI 撤掉，
   强制关闭 ComfyUI／制作记录搬到主界面阶段配置旁）。运行：python test_asset_gating.py"""
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
sys.path.insert(0, HERE)
os.chdir(HERE)

from pet_state import PAGE_OF
from ui_widgets import DataTable

FFMPEG = r"D:/Tools/ffmpeg/bin/ffmpeg.exe"
FFPROBE = r"D:/Tools/ffmpeg/bin/ffprobe.exe"


def make_project(td):
    proj = Path(td) / "p"
    (proj / "episode" / "frames").mkdir(parents=True)
    (proj / "episode" / "assets.json").write_text("{}", encoding="utf-8")
    (proj / "episode" / "episode.json").write_text(json.dumps({
        "episode_id": "EP001", "title": "T", "shots": [
            {"id": "SH001", "title": "镜头", "duration": 5, "characters": ["CHAR_001"],
             "location": "LOC_001", "frame": "frames/SH001.png", "video_prompt": "画面",
             "dialogue": []}]}, ensure_ascii=False), encoding="utf-8")
    (proj / "config.json").write_text(json.dumps({
        "episode_dir": str(proj / "episode"),
        "episode_file": str(proj / "episode" / "episode.json"),
        "budget_seconds": 0, "reserve_seconds": 0, "live_enabled": False,
        "ffmpeg": FFMPEG, "ffprobe": FFPROBE}), encoding="utf-8")
    return proj


def button_state(button):
    return "disabled" if button.instate(["disabled"]) else "normal"


# 一张真能解码的 1×1 PNG：缩略图那条链只有真图才走得通（假的 PhotoImage 会抛）。
PNG_ONE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


def adopted_project(td, shots=None):
    """一份「已采用分镜」的项目。

    第 55 期那几条用例要看资产表里的行，而 asset_plan.sync_plan 只按「当前分镜里用到的
    资产」出行：项目没有已采用的分镜，这一页就是一张空表（一行都没有，断言全落空）。
    """
    from test_ui_edges import adopt_storyboard_fixture, make_minimal_project
    proj = make_minimal_project(td)
    if shots is not None:
        source = proj / "episode" / "episode.json"
        episode = json.loads(source.read_text(encoding="utf-8"))
        episode["shots"] = shots
        source.write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")
    return adopt_storyboard_fixture(proj)


def many_assets_project(td, count=30):
    """N 项「已导入」资产的项目（每项一张真 PNG）：看「打开这一页解了几张图」用它。

    行数 = count 个角色 ＋ 所有镜头共用的那一个 LOC_001；图片登记表（episode/assets.json）
    里写进 image 才算「已导入」——只写进资产清单不算。
    """
    shots = [{"id": "SH%03d" % index, "title": "镜头", "duration": 5,
              "characters": ["CHAR_%03d" % index], "location": "LOC_001",
              "frame": "frames/SH%03d.png" % index, "video_prompt": "画面", "dialogue": []}
             for index in range(1, count + 1)]
    proj = adopted_project(td, shots)
    base = proj / "episode"
    folder = base / "assets" / "characters"
    folder.mkdir(parents=True, exist_ok=True)
    plan = {}
    for index in range(1, count + 1):
        aid = "CHAR_%03d" % index
        (folder / (aid + ".png")).write_bytes(PNG_ONE)
        plan[aid] = {"name": "角色%d" % index, "image": "assets/characters/%s.png" % aid}
    (base / "assets.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return proj


class _TkHarness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            from tkinter import ttk
            cls.tk, cls.ttk = tk, ttk
        except Exception:
            cls.tk = cls.ttk = None

    def desktop(self, td):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        proj = make_project(td)
        win = self.tk.Tk(); win.withdraw()
        from desktop import Desktop
        from local_video import open_studio
        d = Desktop(win, root=Path(td) / "app")
        d.root = proj
        d.studio = open_studio(proj)
        self.addCleanup(win.destroy)
        return d, proj


class AssetPageContentTests(_TkHarness):
    """第 55 期第 3／4／5／6 条：资产表那几栏的字、参考图（类目）、少解的那些图。"""

    def open_assets(self, proj, geometry="1180x760+40+40"):
        # Desktop.__init__ 末尾挂了个 after(150, choose_project)：win.update() 一旦让那个定时器
        # 到期，它就会照用户机器上「唯一在建项目」把整页换掉（资产表跟着销毁），断言就全打在
        # 死控件上。自测里一律把它换成空函数（test_ui_edges 同款做法）。
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        win = self.tk.Tk(); win.geometry(geometry)
        def quiet_destroy():
            try:
                win.destroy()
            except Exception:
                pass
        self.addCleanup(quiet_destroy)
        from desktop import Desktop
        from local_video import open_studio
        d = Desktop(win, root=proj.parent / "app")
        d.root = proj
        d.studio = open_studio(proj)
        # 首帧只排空布局/绘制；update() 还执行到期计时器，慢机上会越过渐进插行边界。
        d.show(PAGE_OF['assets']); win.update_idletasks()
        return d, win

    def page_buttons(self, widget):
        found = []
        if isinstance(widget, self.ttk.Button):
            found.append(str(widget.cget("text")))
        for child in widget.winfo_children():
            found.extend(self.page_buttons(child))
        return found

    def first_of(self, widget, kind):
        if isinstance(widget, kind):
            return widget
        for child in widget.winfo_children():
            found = self.first_of(child, kind)
            if found is not None:
                return found
        return None

    def buttons_of(self, widget):
        found = []
        if isinstance(widget, self.ttk.Button):
            found.append(widget)
        for child in widget.winfo_children():
            found.extend(self.buttons_of(child))
        return found

    def reference_window(self, win):
        """「查看参考图」那一扇窗（标题认它，别的一概不算）。"""
        return [w for w in win.winfo_children()
                if isinstance(w, self.tk.Toplevel) and str(w.title()).startswith("参考图 ·")][-1]

    def test_the_columns_and_the_reference_categories(self):
        """第 55 期第 4／5／6 条：两栏去掉「(点击查看)」、参考图那一栏写类目、「资产目录」删掉。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = adopted_project(td)
            # 参考图存在资产清单里（asset_reference_images 那几扇窗读写的是这一份）：
            # 「参考图（类目）」那一格与「查看参考图」那一窗必须是同一个真相。
            d, _win = self.open_assets(proj)          # 先建一次页：资产清单是这一页同步出来的
            store = proj / "episode" / "assets" / "资产清单"
            plan = json.loads((store / "assets.json").read_text(encoding="utf-8"))
            plan["CHAR_001"] = {"name": "主角",
                                "reference_images": ["assets/参考图/角色/长相/CHAR_001/a.png",
                                                     "assets/参考图/角色/长相/CHAR_001/b.png",
                                                     "assets/参考图/角色/表情/CHAR_001/c.png"],
                                "reference_roles": {"assets/参考图/角色/长相/CHAR_001/a.png": "长相",
                                                    "assets/参考图/角色/长相/CHAR_001/b.png": "长相",
                                                    "assets/参考图/角色/表情/CHAR_001/c.png": "表情"}}
            (store / "assets.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            d.show(PAGE_OF['assets']); _win.update()  # 再重建一次：这回读得到上面的参考图
            table = d.asset_table
            self.assertEqual(str(table.heading("note", "text")), "外观要求")
            self.assertEqual(str(table.heading("prompt", "text")), "资产提示词")
            self.assertEqual(str(table.heading("references", "text")), "参考图（类目）")
            self.assertEqual(str(table.set("CHAR_001", "references")), "3 张 · 长相2 表情1",
                             "参考图那一栏要说清「几张、哪几类」")
            self.assertEqual(str(table.set("LOC_001", "references")), "—", "没有参考图就是「—」")
            buttons = self.page_buttons(d.content)
            # 第 57 期第 6 条：这一行按钮重新排过——「查看参考图」删掉（参考图那一格单击
            # 打开的就是它）、「批量删除图片」改名「批量删除资产」、「生成图目录」改名
            # 「资产目录」并改开 episode 根目录，所以它现在该在。
            self.assertIn("资产目录", buttons)
            self.assertIn("批量删除资产", buttons)
            self.assertNotIn("查看参考图", buttons, "第 57 期第 6 条：这一颗删了")
            self.assertNotIn("批量删除图片", buttons)

    def test_the_reference_window_reads_the_same_list_as_the_column(self):
        """第 55 期第 6 条：「查看参考图」那一窗与「参考图（类目）」那一格必须同一个真相。

        参考图登记的资产清单（assets/资产清单/assets.json）与图片登记表（episode/assets.json）
        是两份：资产表那一格是两边合起来读的，那一窗只认资产清单。写错一份，页面上说「3 张」、
        点进去说「还没有参考图」——这条用例就是钉住这一点。
        """
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            proj = adopted_project(td)
            d, win = self.open_assets(proj)          # 先建一次页：资产清单是这一页同步出来的
            store = proj / "episode" / "assets" / "资产清单"
            plan = json.loads((store / "assets.json").read_text(encoding="utf-8"))
            plan["CHAR_001"] = {"name": "主角",
                                "reference_images": ["assets/参考图/角色/长相/CHAR_001/a.png",
                                                     "assets/参考图/角色/长相/CHAR_001/b.png",
                                                     "assets/参考图/角色/表情/CHAR_001/c.png"],
                                "reference_roles": {"assets/参考图/角色/长相/CHAR_001/a.png": "长相",
                                                    "assets/参考图/角色/长相/CHAR_001/b.png": "长相",
                                                    "assets/参考图/角色/表情/CHAR_001/c.png": "表情"}}
            (store / "assets.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            d.show(PAGE_OF['assets']); win.update()   # 再重建一次：这回读得到上面的参考图
            self.assertEqual(str(d.asset_table.set("CHAR_001", "references")), "3 张 · 长相2 表情1")
            d.view_reference_images("CHAR_001"); win.update(); win.update_idletasks()
            window = self.reference_window(win)
            # R818 起参考图表经 DataTable 统一承载，业务断言仍针对其底层
            # Treeview 的行与筛选行为。
            table_shell = self.first_of(window, DataTable)
            self.assertIsNotNone(table_shell, "参考图列表必须经 DataTable 构建")
            table = table_shell.tree
            self.assertEqual(len(table.get_children()), 3, "这一窗要真列出那 3 张")
            box = self.first_of(window, self.ttk.Combobox)
            self.assertEqual(tuple(box.cget("values")), ("全部", "长相", "服饰", "画风", "色调",
                                                          "氛围", "姿态动作", "表情", "其他", "待分类"),
                             "第 55 期第 6 条：筛选按这一类的类目摆（角色这一档）")
            box.set("长相"); box.event_generate("<<ComboboxSelected>>"); win.update()
            said = [table.set(row, "file") for row in table.get_children()]
            self.assertEqual(len(said), 2, "按类目筛：只留「长相」那两张")
            # 底下那行按钮得真在窗口里。原来那一窗的请求高度（518）超过窗口高度（480），
            # 按「先摆内容框、后摆按钮」的顺序排下去，三颗按钮整个被挤出窗外——一个没分到
            # 地方的控件在 Tk 里就是「没映射」，所以这一条的判据落在「摆的顺序」上：
            #   1) 三颗按钮各就各位，而且各自请求到了高度；
            #   2) 按钮行与状态行都是 side='bottom'，内容框最后 pack——先 pack 的先分到地方，
            #      内容框只吃剩下的，窗口再矮也是内容框先让步；
            # 三条都与窗口管理器无关，任何机器上都作数（并行整跑里窗口映射能滞后十几秒，
            # 拿 ismapped 当判据会偶发见红，这一版不再这么判）。
            for label in ("查看图片", "导入参考图", "打开参考图目录"):
                found = [b for b in self.buttons_of(window) if str(b.cget("text")) == label]
                self.assertEqual(len(found), 1, "这一窗少了「%s」" % label)
                self.assertGreater(int(found[0].winfo_reqheight()), 0, "「%s」没请求到高度" % label)
            bar = found[0].master
            self.assertEqual(str(bar.pack_info().get("side")), "bottom",
                             "按钮行要 side='bottom' 先落位：内容框最后 pack，窗口矮也是它先让步")
            slaves = window.pack_slaves()
            self.assertIsInstance(slaves[-1], DataTable,
                                  "内容框要最后 pack，别抢在按钮前头把地方吃完")
            status_row = [w for w in slaves if isinstance(w, self.ttk.Label)][-1]
            self.assertEqual(str(status_row.pack_info().get("side")), "bottom",
                             "底下那行状态（共 N 张参考图…）也要先落位")
            # 窗口真映射出来了（多数时候一建就是映射的）再顺手量一遍实际位置：三颗按钮的底边
            # 都不许落到窗口外。映射的事归窗口管理器管，整跑里能滞后十几秒，滞后就不量——
            # 上面那几条已经把「关得进来」钉死了。
            import time
            deadline = time.monotonic() + 5.0
            while not window.winfo_ismapped() and time.monotonic() < deadline:
                win.update(); win.update_idletasks(); time.sleep(0.02)
            if window.winfo_ismapped():
                limit = window.winfo_rooty() + window.winfo_height() + 2
                for label in ("查看图片", "导入参考图", "打开参考图目录"):
                    found = [b for b in self.buttons_of(window) if str(b.cget("text")) == label][0]
                    self.assertTrue(found.winfo_ismapped(), "「%s」被挤出窗外了" % label)
                    self.assertLessEqual(found.winfo_rooty() + found.winfo_height(), limit,
                                         "「%s」整个落在窗口外" % label)

    def test_only_the_visible_rows_decode_a_picture(self):
        """第 55 期第 3 条：打开这一页只为可视区那几行解图，不是为整库每一项。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import asset_thumbs
        with tempfile.TemporaryDirectory() as td:
            proj = many_assets_project(td, 30)
            real = asset_thumbs.thumbnail
            decoded = []

            def counted(master, path, size=asset_thumbs.DEFAULT_SIZE):
                decoded.append(str(path))
                return real(master, path, size)

            asset_thumbs.thumbnail = counted
            self.addCleanup(setattr, asset_thumbs, "thumbnail", real)
            d, _win = self.open_assets(proj)
            table = d.asset_table
            # 首帧只同步插入三屏余量；整库行由下一帧继续补齐。这里测的是“打开页只
            # 解可视区图片”，不能再把性能契约倒逼回一次性插完 31 行。
            from desktop import ASSET_FIRST_ROWS
            self.assertEqual(len(table.get_children()), ASSET_FIRST_ROWS,
                             "首帧只建渐进加载的首批资产行")
            # 覆盖层只能在 Treeview 已映射、能取到 bbox 后落图；整套并跑时窗口管理器
            # 可能比首次 update 晚一拍。等这一份已注册的首帧刷新完成，而不是把空标签误判为
            # 「没有为可视区解图」。
            import time
            deadline = time.monotonic() + 5.0
            while not table.cell_images.labels and time.monotonic() < deadline:
                _win.update(); _win.update_idletasks()
                table.cell_images.refresh()
                time.sleep(0.02)
            self.assertTrue(table.cell_images.labels, "可视区那几行要真盖上缩略图，用例才不是空跑")
            self.assertLessEqual(len(set(decoded)), 12,
                                 "解了 %d 张：只该解可视区那几行，不是整库 30 项" % len(set(decoded)))


class AssetCellDeleteTests(_TkHarness):
    """第 57 期第 3 条：右键落在「参考图」那一栏删的是这一项的参考图，落在别的栏删的才是资产图片。

    两样东西记在两份文件里——参考图在资产清单（assets/资产清单/assets.json），已导入的资产图片
    在图片登记表（episode/assets.json）。原来那一颗「删除」不看落点、一律删资产图片，用户在参考图
    那一格上右键，被删掉的是自己导入的图。
    """

    # 建页那一套（含 choose_project 打桩）原样借用，别再抄一遍。
    open_assets = AssetPageContentTests.open_assets

    def prepared(self, td):
        """一项「资产图片 ＋ 两张参考图」都在的角色：删哪一样，都看得见另一样还在不在。"""
        proj = adopted_project(td)
        d, win = self.open_assets(proj)
        base = proj / "episode"
        folder = base / "assets" / "characters"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "CHAR_001.png").write_bytes(PNG_ONE)
        images = json.loads((base / "assets.json").read_text(encoding="utf-8"))
        images["CHAR_001"] = {"name": "主角", "image": "assets/characters/CHAR_001.png"}
        (base / "assets.json").write_text(json.dumps(images, ensure_ascii=False), encoding="utf-8")
        store = base / "assets" / "资产清单"
        plan = json.loads((store / "assets.json").read_text(encoding="utf-8"))
        plan["CHAR_001"] = {"name": "主角",
                            "reference_images": ["assets/参考图/角色/长相/CHAR_001/a.png",
                                                 "assets/参考图/角色/表情/CHAR_001/b.png"],
                            "reference_roles": {"assets/参考图/角色/长相/CHAR_001/a.png": "长相",
                                                "assets/参考图/角色/表情/CHAR_001/b.png": "表情"}}
        (store / "assets.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        d.show(PAGE_OF['assets']); win.update()
        return d, proj

    def both_files(self, proj, aid="CHAR_001"):
        """两份文件里这一项资产的登记：图片登记表那一条 ＋ 资产清单那一条。"""
        base = proj / "episode"
        images = json.loads((base / "assets.json").read_text(encoding="utf-8"))
        plan = json.loads((base / "assets" / "资产清单" / "assets.json").read_text(encoding="utf-8"))
        return images.get(aid, {}), plan.get(aid, {})

    def quiet_messagebox(self, answer=True):
        """替用户按下确认框；顺手记下有没有弹过错误框——真出岔子就该让用例红，不是弹个框。"""
        import desktop as desktop_module
        errors = []

        class Fake:
            def askyesno(self, *args, **kwargs):
                return answer

            def showerror(self, *args, **kwargs):
                errors.append(" ".join(str(item) for item in args))

            def showinfo(self, *args, **kwargs):
                return None

            def showwarning(self, *args, **kwargs):
                return None

        original = desktop_module.messagebox
        desktop_module.messagebox = Fake()
        self.addCleanup(setattr, desktop_module, "messagebox", original)
        original_confirm = desktop_module.confirm
        desktop_module.confirm = lambda *args, **kwargs: answer
        self.addCleanup(setattr, desktop_module, "confirm", original_confirm)
        return errors

    def test_the_reference_column_deletes_the_reference_only(self):
        """右键落在「参考图」那一格：解除这一项的参考图绑定，已导入的资产图片原封不动。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            d, proj = self.prepared(td)
            errors = self.quiet_messagebox()
            self.assertEqual(d.asset_field_column("references"), "#4",
                             "「参考图」是第 4 栏，删除的落点要按字段名现算")
            hover = d.asset_table.cell_hover
            self.assertIsNotNone(hover.delete, "资产表的右键菜单该挂着「删除」")
            hover.delete("CHAR_001", d.asset_field_column("references"))
            self.assertEqual(errors, [], "删参考图不该弹错误框")
            image, plan = self.both_files(proj)
            self.assertEqual(plan.get("reference_images", []), [], "参考图该解除绑定")
            self.assertEqual(plan.get("reference_roles", {}), {}, "类目登记要跟着一起清")
            self.assertEqual(image.get("image"), "assets/characters/CHAR_001.png",
                             "删参考图不许动已导入的资产图片")
            self.assertTrue((proj / "episode" / "assets" / "characters" / "CHAR_001.png").is_file())

    def test_another_column_deletes_the_asset_image_only(self):
        """右键落在别的格（「名称」那一栏）：删的是已导入的资产图片，参考图一张不少。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            d, proj = self.prepared(td)
            errors = self.quiet_messagebox()
            d.asset_table.cell_hover.delete("CHAR_001", d.asset_field_column("name"))
            self.assertEqual(errors, [], "删资产图片不该弹错误框")
            image, plan = self.both_files(proj)
            self.assertNotIn("image", image, "资产图片该移进项目回收站，资产恢复为待导入")
            self.assertEqual(len(plan.get("reference_images", [])), 2, "删资产图片不许动参考图")

    def test_deleted_asset_image_restores_from_recycle_service(self):
        """恢复动作按资产目录和 ID 定位，不依赖已经移除的图片登记。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            d, proj = self.prepared(td)
            errors = self.quiet_messagebox()
            d.delete_asset_image("CHAR_001")
            self.assertNotIn("image", self.both_files(proj)[0])
            self.assertTrue(d.restore_asset_image("CHAR_001"))
            self.assertEqual(errors, [])
            image, _plan = self.both_files(proj)
            self.assertEqual(image.get("image"), "assets/characters/CHAR_001.png")
            self.assertTrue((proj / "episode" / image["image"]).is_file())


class AssetPageGatingTests(_TkHarness):
    def test_gated_buttons_match_contract(self):
        with tempfile.TemporaryDirectory() as td:
            d, _ = self.desktop(td)
            d.show(PAGE_OF['assets']); d.win.update_idletasks()
            texts = [b.cget("text") for b in d.asset_gated_buttons]
            self.assertIn("手动制作资产", texts)
            self.assertIn("导入参考图", texts)
            self.assertIn("批量删除资产", texts)
            # 第 57 期第 6 条：「查看参考图」删了（参考图那一格单击打开的就是它），
            # 「批量删除图片」改名「批量删除资产」。
            self.assertNotIn("查看参考图", texts)
            self.assertNotIn("批量删除图片", texts)
            for exempt in ("参考图目录", "桌面打开 ComfyUI"):
                self.assertNotIn(exempt, texts)

    def test_buttons_disabled_when_none_checked(self):
        with tempfile.TemporaryDirectory() as td:
            d, _ = self.desktop(td)
            d.show(PAGE_OF['assets']); d.win.update_idletasks()
            d.asset_checked_count = 0
            d.update_asset_buttons()
            self.assertTrue(all(b.instate(["disabled"]) for b in d.asset_gated_buttons))

    def test_buttons_enabled_when_checked(self):
        with tempfile.TemporaryDirectory() as td:
            d, _ = self.desktop(td)
            d.show(PAGE_OF['assets']); d.win.update_idletasks()
            d.asset_checked_count = 3
            d.asset_has_pending = True
            d.update_asset_buttons()
            self.assertTrue(all(not b.instate(["disabled"]) for b in d.asset_gated_buttons))



    def test_toolbar_checks_remain_enabled_without_selection(self):

        with tempfile.TemporaryDirectory() as td:

            d, _ = self.desktop(td)

            d.show(PAGE_OF['assets']); d.win.update_idletasks()

            d.asset_checked_count = 0

            d.update_asset_buttons()

            buttons = []

            def walk(w):

                if isinstance(w, self.ttk.Button):

                    buttons.append(w)

                for c in w.winfo_children():

                    walk(c)

            walk(d.content)

            states = {b.cget("text"): button_state(b) for b in buttons}

            for exempt in ("检查提示词", "识别背景人物", "参考图目录", "资产目录", "桌面打开 ComfyUI"):
                self.assertEqual(states.get(exempt), "normal")
            # 第 55 期第 5 条：「资产目录」删掉了（打开的是「生成图目录」那一个库）；
            # 第 57 期第 6 条：它又以新身份回来了——「生成图目录」改名「资产目录」，
            # 改开上一级的 episode 根目录，所以这一条从「不该有」翻成「该有且不用选中」。





class NativeAssetsGatingTests(_TkHarness):
    def attach(self, d, proj, selection):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        win = self.tk.Toplevel(d.win); win.withdraw()
        form = self.ttk.Frame(win); form.pack()
        footer = self.ttk.Frame(win); footer.pack(side="bottom")
        status = self.tk.StringVar()
        from native_assets import attach_controls
        attach_controls(d, win, form, footer, proj, d.asset_base(),
                        selection=selection, status=status,
                        reload_rows=lambda: None, context_matches=lambda: True)
        d.win.update_idletasks()
        return form

    def _buttons(self, form):
        out = []
        def walk(w):
            if isinstance(w, self.ttk.Button):
                out.append(w)
            for c in w.winfo_children():
                walk(c)
        walk(form)
        return out

    def test_progressbar_directly_above_action_buttons(self):
        with tempfile.TemporaryDirectory() as td:
            d, proj = self.desktop(td)
            form = self.attach(d, proj, selection=lambda: [])
            kinds = [type(w).__name__ for w in form.winfo_children()]
            self.assertEqual(kinds, ["Card", "Progressbar", "ProgressLabel", "FlowBar"])
            bar = form.winfo_children()[3]
            texts = [b.cget("text") for b in bar.winfo_children()]
            self.assertEqual(texts, ["启动并检测", "预估费用", "取消检测"])

    def test_the_main_page_owns_the_comfy_housekeeping_buttons(self):
        """第 65 期任务 1：「强制关闭 ComfyUI」「制作记录」搬到主界面「阶段配置」右边。

        这两颗与制作窗口无关，原来摆在弹窗里等于同一件事两个入口。
        """
        with tempfile.TemporaryDirectory() as td:
            d, _ = self.desktop(td)
            d.show(PAGE_OF['assets']); d.win.update_idletasks()
            # 自动模式下按钮显示实际会调用的引擎，而非固定的“阶段配置”。
            from skill_panel import stage_button_label
            config_label = stage_button_label(d, 'assets')
            buttons = []
            def walk(w):
                if isinstance(w, (self.tk.Button, self.ttk.Button)):
                    buttons.append(w)
                for c in w.winfo_children():
                    walk(c)
            walk(d.content)
            texts = [str(b.cget("text")) for b in buttons]
            self.assertIn("强制关闭 ComfyUI", texts)
            self.assertIn("制作记录", texts)
            self.assertIn(config_label, texts)
            order = [t for t in texts if t in ("手动制作资产", config_label, "强制关闭 ComfyUI", "制作记录")]
            self.assertEqual(order, ["手动制作资产", config_label, "强制关闭 ComfyUI", "制作记录"],
                             "就摆在阶段配置右边，顺序别乱")

    def test_kill_comfy_runs_off_the_ui_thread(self):
        """「强制关闭 ComfyUI」在主界面阶段配置旁，后台线程执行：按下时 ComfyUI 往往已经卡住，界面不能跟着僵。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import threading, time as clock
        import native_apps
        with tempfile.TemporaryDirectory() as td:
            d, proj = self.desktop(td)
            d.show(PAGE_OF['assets']); d.win.update_idletasks()
            def label_text():
                return str(d.status.get())
            seen = {}
            def fake(settings=None):
                seen["thread"] = threading.current_thread().name
                clock.sleep(0.6)                       # taskkill 卡住时的耗时
                return "已强制关闭 ComfyUI：fake"
            original = native_apps.force_close_comfy
            native_apps.force_close_comfy = fake
            self.addCleanup(setattr, native_apps, "force_close_comfy", original)
            found = []
            def walk(w):
                if isinstance(w, self.ttk.Button):
                    found.append(w)
                for c in w.winfo_children():
                    walk(c)
            walk(d.content)
            button = [b for b in found if b.cget("text") == "强制关闭 ComfyUI"][0]
            started = clock.perf_counter()
            button.invoke()
            self.assertLess(clock.perf_counter() - started, 0.3)      # 点击本身立刻返回
            self.assertIn("正在强制关闭", label_text())
            deadline = clock.time() + 10
            while "thread" not in seen and clock.time() < deadline:
                d.win.update(); clock.sleep(0.02)
            self.assertIn("thread", seen)
            self.assertNotEqual(seen["thread"], threading.main_thread().name)
            deadline = clock.time() + 10
            while "已强制关闭" not in label_text() and clock.time() < deadline:
                d.win.update(); clock.sleep(0.02)
            self.assertIn("已强制关闭 ComfyUI：fake", label_text())

    def test_start_and_check_disabled_without_selection(self):
        with tempfile.TemporaryDirectory() as td:
            d, proj = self.desktop(td)
            form = self.attach(d, proj, selection=lambda: [])
            states = {b.cget("text"): button_state(b) for b in self._buttons(form)}
            self.assertEqual(states["启动并检测"], "disabled")
            self.assertNotIn("手动制作资产", states, "那一颗已经撤掉，检测通过就自动开跑")

    def test_start_and_check_enabled_with_selection(self):
        with tempfile.TemporaryDirectory() as td:
            d, proj = self.desktop(td)
            form = self.attach(d, proj, selection=lambda: [("CHAR_001", {"name": "主角"})])
            states = {b.cget("text"): button_state(b) for b in self._buttons(form)}
            self.assertEqual(states["启动并检测"], "normal")

    def test_generation_is_dispatched_through_the_desktop_async_boundary(self):
        """检测通过后，含轮询 sleep 的制图工作只能交给 Desktop.async_，不能留在按钮回调。"""
        with tempfile.TemporaryDirectory() as td:
            d, proj = self.desktop(td)
            d.launch_comfy = lambda silent=True: True
            submitted = []
            d.async_ = lambda fn, done=None, **kwargs: submitted.append((fn, done, kwargs))
            form = self.attach(d, proj, selection=lambda: [("CHAR_001", {"name": "主角"})])
            buttons = {button.cget("text"): button for button in self._buttons(form)}
            buttons["启动并检测"].invoke()
            self.assertEqual(len(submitted), 1, "检测本身先经异步入口")
            submitted[0][1]("ComfyUI 已连接，检测通过。正在自动开始制图…")
            self.assertEqual(len(submitted), 2, "制图工作也必须经异步入口")
            work, _done, kwargs = submitted[1]
            self.assertTrue(callable(work))
            self.assertFalse(kwargs["show_progress"])
            form.winfo_children()[1].stop()  # 本测试不交付 worker 结果，别留下 Tk 自动步进回调。


class ForceCloseComfyTests(unittest.TestCase):
    """第 65 期任务 1：「强制关闭 ComfyUI」要真的关得掉。

    Comfy Desktop 起来的服务是 `python -s ComfyUI/main.py` 跑的，原来那两颗镜像
    （Comfy Desktop.exe／ComfyUI.exe）盖不到它，用户按了没反应；但也不能见 python 就杀
    ——助手自己也是 python。
    """

    def fake_subprocess(self, calls, returncode=0):
        class Fake:
            SubprocessError = __import__("subprocess").SubprocessError
            def run(self, args, **kwargs):
                calls.append(list(args))
                class Result:
                    pass
                result = Result()
                result.returncode = returncode
                result.stdout = b""
                result.stderr = b""
                return result
        return Fake()

    def test_it_also_kills_the_python_that_runs_the_service(self):
        import native_apps
        calls = []
        original = native_apps.subprocess
        native_apps.subprocess = self.fake_subprocess(calls)
        native_apps.comfy_server_pids = lambda: [4321]
        self.addCleanup(setattr, native_apps, "subprocess", original)
        self.addCleanup(setattr, native_apps, "comfy_server_pids", native_apps.comfy_server_pids)
        text = native_apps.force_close_comfy({})
        self.assertIn(["taskkill", "/PID", "4321", "/F", "/T"], calls,
                      "服务进程要按进程号单独关掉")
        self.assertIn("4321", text)

    def test_the_assistant_never_kills_its_own_python(self):
        import os
        import native_apps
        self.assertNotIn(os.getpid(), native_apps.comfy_server_pids(),
                         "助手自己也是 python，绝不能把自己算进名单")


if __name__ == "__main__":
    unittest.main(verbosity=2)
