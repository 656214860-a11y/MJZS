# -*- coding: utf-8 -*-
"""第 61 期 v0.8 的接线自检：目录树在打开项目时补齐、资产页多出正典板折叠区、分镜定稿回填批次编号。
第 62 期任务 11：「连贯性清单」升成独立的一页。运行：python test_stage_wiring.py

接线这一类改动最容易「模块写好了却没接上」：这里既跑真界面（折叠区真的能展开、真的落盘），
也用一条源码锁钉住 load()／finalize() 里那两行调用。断言全在临时项目里，绝不碰真安装目录。
"""
from tests.architecture._scan import desktop_text  # R1505：Desktop 方法分布在 desktop.py 与迁出的 Mixin 模块
from skip_reasons import (
    MISSING_NODE,
    PLATFORM_DIRECTORY_LINK,
    PLATFORM_TKINTER,
    PLATFORM_TK_DISPLAY,
    PLATFORM_WORKING_SET,
    REQUIRES_BUNDLED_SKILL,
)
import json, os, sys, tempfile, unittest
from unittest import mock
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, PROGRAM)
sys.path.insert(1, HERE)
os.chdir(PROGRAM)

import stage_layout
from ui_edges_support import adopt_storyboard_fixture, make_minimal_project


class _Harness(unittest.TestCase):
    """建一个真 Desktop（Tk），但不让它去挑项目——自测里那个定时器会把页换掉。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            from tkinter import ttk
            cls.tk, cls.ttk = tk, ttk
        except Exception:
            cls.tk = cls.ttk = None

    def desktop(self, proj):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        win = self.tk.Tk()
        win.withdraw()
        self.addCleanup(self._quiet, win)
        from desktop import Desktop
        from local_video import open_studio
        d = Desktop(win, root=PROGRAM)
        d.root = proj
        d.studio = open_studio(proj)
        return d, win

    @staticmethod
    def _quiet(win):
        try:
            win.destroy()
        except Exception:
            pass

    def texts(self, widget):
        """整棵控件树上所有文字（Label／Button／Checkbutton 都算）。"""
        found = []
        for cls in (self.ttk.Label, self.ttk.LabelFrame, self.ttk.Button, self.ttk.Checkbutton):
            if isinstance(widget, cls):
                try:
                    found.append(str(widget.cget("text")))
                except Exception:
                    pass
                break
        for child in widget.winfo_children():
            found.extend(self.texts(child))
        return found

    def buttons(self, widget, text):
        """按文字找按钮（ttk.Button 与 tk.Button 都算）。"""
        found = []
        for cls in (self.ttk.Button, self.tk.Button):
            if isinstance(widget, cls):
                try:
                    if str(widget.cget("text")) == text:
                        found.append(widget)
                except Exception:
                    pass
                break
        for child in widget.winfo_children():
            found.extend(self.buttons(child, text))
        return found


class LayoutWiringTests(_Harness):
    """任务 2：打开项目就把阶段目录树补齐。"""

    def test_ensure_stage_layout_builds_the_tree(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, _win = self.desktop(proj)
            created = d.ensure_stage_layout()
            self.assertTrue(created)
            for name in stage_layout.names():
                self.assertTrue((proj / name / "output").is_dir(), name)
                self.assertTrue((proj / name / "README.md").is_file(), name)
            self.assertTrue((proj / "_shared" / "anchors").is_dir())
            self.assertEqual(d.ensure_stage_layout(), [], "再跑一次不该再建东西")

    def test_ensure_stage_layout_is_quiet_without_a_project(self):
        with tempfile.TemporaryDirectory() as td:
            d, _win = self.desktop(make_minimal_project(td))
            d.root = None
            self.assertEqual(d.ensure_stage_layout(), [])

    def test_ensure_stage_layout_failure_is_visible_without_blocking(self):
        """目录建不出来仍可继续，但不能让用户误以为阶段树已经补齐。"""
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, _win = self.desktop(proj)
            with mock.patch('contract.stage_layout.ensure', side_effect=OSError('阶段目录无写入权限')):
                try:
                    self.assertEqual(d.ensure_stage_layout(), [])
                except Exception as exc:
                    self.fail("必须吞掉异常，不该抛：" + str(exc))
            self.assertIn("阶段目录未补齐", d.status.get())

    def test_legacy_adoption_failure_is_visible_without_blocking(self):
        """旧目录归位失败也不能静默伪装成没有待归位目录。"""
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, _win = self.desktop(proj)
            with mock.patch('contract.stage_layout.adopt_legacy', side_effect=OSError('目录联接不可用')):
                self.assertEqual(d.adopt_legacy_layout(), {})
            self.assertIn("旧目录未归入新架构", d.status.get())

    def test_load_defers_empty_stage_layout_creation(self):
        """项目打开不能再预建阶段空目录；真实产物目录按阶段实际使用时创建。"""
        source = desktop_text()
        load_body = source.split('    def load(self,path,*,defer_page=False):', 1)[1].split(chr(10) + '    def ', 1)[0]  # R1505：load 的方法体到下一个 def 为止
        self.assertNotIn("self.ensure_stage_layout()", load_body)
        self.assertIn("self._complete_project_recovery(self.root)", load_body)

    def test_script_structure_page_shows_its_input_and_output_contract(self):
        """REQ-S02-38：唯一编辑器默认显示来源稿；有了对应结构稿后默认换成结构稿。"""
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            (proj / 'writing').mkdir(exist_ok=True)
            (proj / 'writing' / 'script_raw.md').write_text('原稿', encoding='utf-8')
            d, win = self.desktop(proj)
            d.show(d.page_of('script_structure')); win.update()
            preview = d.script_structure_editor_preview
            box = d.script_structure_editor_preview_content_box
            self.assertIn('原稿', preview.get('1.0', 'end-1c'))
            self.assertEqual(box.active['path'], (proj / 'writing' / 'script_raw.md').resolve())
            import script_contract
            target = script_contract.write_structured_script(proj)
            d.show(d.page_of('script_structure')); win.update()
            self.assertIn('## 分场剧本', d.script_structure_editor_preview.get('1.0', 'end-1c'))
            self.assertEqual(d.script_structure_editor_preview_content_box.active['path'],
                             target.resolve())


class AssetDetailRoutingTests(_Harness):
    """第 64 期任务 13（附件 v3.0 任务 2.1／2.3／4.1）：资产详情页是资产管理页的子路由。

    主页面那张表一个像素都不动，只在「资产编号」那一格加了进详情的入口；原来嵌在「外观要求」
    弹窗里的正典板折叠区整个删掉了（附件任务 4.1 的「旧的正典板嵌入代码已删除」）。
    """

    def test_the_main_page_keeps_the_table_and_gains_the_entry(self):
        with tempfile.TemporaryDirectory() as td:
            proj = adopt_storyboard_fixture(make_minimal_project(td))
            d, win = self.desktop(proj)
            d.show(d.page_of("assets")); win.update()
            self.assertIsNotNone(d.asset_table, "主页面布局没变，还是那张资产表")
            self.assertIsNone(d.asset_detail_id, "没进详情时摆的是主页面")
            source = desktop_text()
            self.assertIn("self.page.open_asset_detail(aid)", source, "资产编号那一格是入口")  # R1816：assets 改写成 _AssetPage
            self.assertIn("'#1'", source, "入口那一格进了可点列的清单")

    def test_entering_the_detail_page_swaps_the_subroute_in(self):
        with tempfile.TemporaryDirectory() as td:
            proj = adopt_storyboard_fixture(make_minimal_project(td))
            d, win = self.desktop(proj)
            d.show(d.page_of("assets")); win.update()
            d.open_asset_detail("CHAR_001"); win.update()
            self.assertEqual(d.asset_detail_id, "CHAR_001")
            texts = self.texts(d.content)
            for label in ("正典板", "锚点字符串", "参考职责声明", "状态变体"):
                self.assertTrue(any(label in text for text in texts), (label, texts))
            self.assertTrue(any("返回资产管理" in text for text in texts), "返回按钮在")

    def test_back_button_returns_to_the_table(self):
        with tempfile.TemporaryDirectory() as td:
            proj = adopt_storyboard_fixture(make_minimal_project(td))
            d, win = self.desktop(proj)
            d.open_asset_detail("CHAR_001"); win.update()
            buttons = self.buttons(d.content, "← 返回资产管理")
            self.assertEqual(len(buttons), 1)
            buttons[0].invoke(); win.update()
            self.assertIsNone(d.asset_detail_id)
            self.assertIsNotNone(d.asset_table, "回到主页面还是那张表")

    def test_an_unknown_id_is_reported_and_keeps_a_way_back(self):
        with tempfile.TemporaryDirectory() as td:
            proj = adopt_storyboard_fixture(make_minimal_project(td))
            d, win = self.desktop(proj)
            d.open_asset_detail("CHAR_777"); win.update()
            texts = self.texts(d.content)
            self.assertTrue(any("资产不存在" in text for text in texts), texts)
            self.assertTrue(any("返回资产管理" in text for text in texts))

    def test_the_old_embedded_board_is_gone(self):
        source = desktop_text()
        self.assertNotIn("canon_board_section", source, "附件任务 4.1：旧的正典板嵌入代码已删除")
        self.assertNotIn("open_asset_relative", source)
        self.assertIn("asset_detail_page(self,self.asset_detail_id)", source)


class ContinuityWiringTests(_Harness):
    """第 62 期任务 11：「连贯性清单」从资产页底部的折叠区升成独立的一页——资产管理之后、
    分镜定稿之前；按下页面上那颗按钮就把台账落盘。"""

    def test_the_page_writes_the_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            proj = adopt_storyboard_fixture(make_minimal_project(td))
            d, win = self.desktop(proj)
            d.show(d.page_of("continuity")); win.update()
            d.shared_input.stage_action("continuity")(); win.update()
            file = stage_layout.paths(proj, "03_continuity")["output"] / "continuity_ledger.json"
            self.assertTrue(file.is_file(), "一按就该把台账落盘")
            data = json.loads(file.read_text(encoding="utf-8"))
            self.assertIn("summary", data)
            self.assertEqual(data["summary"]["shots"], 1)
            self.assertTrue((stage_layout.paths(proj, "03_continuity")["docs"]
                             / "continuity_ledger.md").is_file())
            texts = self.texts(d.content)
            self.assertTrue(any("批次" in text for text in texts), texts)

    def test_the_asset_page_no_longer_carries_it(self):
        """它升成独立一页之后，资产页不再重复一个入口（原有的按钮一颗都没少）。"""
        with tempfile.TemporaryDirectory() as td:
            proj = adopt_storyboard_fixture(make_minimal_project(td))
            d, win = self.desktop(proj)
            d.show(d.page_of("assets")); win.update()
            self.assertNotIn("手动生成连贯性清单", self.texts(d.content), "资产页不再重复这个入口")
            self.assertNotIn("连贯性清单（展开）", self.texts(d.content), "折叠区整个撤掉了")
            from test_board_assets_buttons import _asset_menu, _menu_labels
            self.assertIn("打开资产目录", _menu_labels(_asset_menu(d)))

    def test_pick_gate_records_the_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            proj = adopt_storyboard_fixture(make_minimal_project(td))
            d, _win = self.desktop(proj)
            d.pick_gate("conflict:B01", "候选一")
            from domain import confirm_gates
            self.assertEqual(confirm_gates.confirmations(proj)["conflict:B01"]["choice"], "候选一")


class FinalizeWiringTests(unittest.TestCase):
    """任务 10：分镜定稿切批次并回填 batch_id。"""

    def test_finalize_calls_assign(self):
        source = Path(PROGRAM, "orchestrator/storyboard_final.py").read_text(encoding="utf-8")
        self.assertIn("from contract.shot_batches import assign", source)
        self.assertIn("episode['shots']=list(assign(episode['shots']))", source)

    def test_the_batch_step_puts_ids_in_and_keeps_validate_episode_happy(self):
        from contract import shot_batches
        from writing import validate_episode
        episode = {"episode_id": "EP001", "title": "T", "duration": 3,
                   "shots": [{"id": "SH001", "title": "镜头", "duration": 3,
                              "characters": ["CHAR_001"], "location": "LOC_001",
                              "frame": "frames/SH001.png", "video_prompt": "画面",
                              "dialogue": []}]}
        assets = {"CHAR_001": {"name": "主角"}, "LOC_001": {"name": "咖啡馆"}}
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "frames").mkdir()
            validate_episode(episode, base, assets)
            episode["shots"] = list(shot_batches.assign(episode["shots"]))
            validate_episode(episode, base, assets)
            shot = episode["shots"][0]
            self.assertEqual(shot["batch_id"], "B01")
            self.assertEqual(shot["estimated_duration"], 3)
            self.assertEqual(shot["character_ids"], ["CHAR_001"])
            self.assertEqual(shot["scene_id"], "LOC_001")
            self.assertEqual(shot["reference_roles"]["@图片1"]["responsibility"],
                             shot_batches.DEFAULT_RESPONSIBILITY)


if __name__ == "__main__":
    unittest.main(verbosity=2)
