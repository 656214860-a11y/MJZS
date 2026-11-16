# -*- coding: utf-8 -*-
"""资产详情页（第 64 期任务 13）的自检；对应附件 v3.0 阶段五的测试门禁。

运行：python test_asset_detail.py

附件要的 8 项单功能（主页面→详情页跳转、7 面板转盘图、转盘图放大、锚点复制、锚点编辑、
状态变体折叠／展开、状态变体新增、锁定／解锁）＋ 数据一致性 ＋ 端到端 ＋ 回归，逐项跑真界面
（Tk），断言全在临时项目里，绝不碰真安装目录。
"""
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
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import contract.asset_contract as ac
import asset_detail
import asset_plan
import confirm_gates
from stage_execution_service import apply_asset_plan_gate_choice as apply_gate_choice
from test_asset_thumbs import png
from widget_test_support import widget_list, widget_texts
from ui_edges_support import adopt_storyboard_fixture, make_minimal_project

ANGLE_LABELS = ("正面 0°", "右侧 90°", "左侧 -90°", "背面 180°", "3/4 左", "3/4 右")


def shot(sid, chars, loc, props=()):
    return {"id": sid, "title": "镜头", "duration": 3, "characters": list(chars), "location": loc,
            "props": [{"id": value, "name": value} for value in props],
            "frame": "frames/%s.png" % sid, "video_prompt": "画面", "dialogue": []}


BIG_SHOTS = [shot("SH001", ["CHAR_001"], "LOC_001", ["PROP_001"]),
             shot("SH002", ["CHAR_002"], "LOC_002", ["PROP_002"]),
             shot("SH003", ["CHAR_003"], "LOC_001")]


def project_with(td, shots=None, names=None):
    """摆一个已采用分镜的临时项目；names 给资产清单里那几项的显示名。"""
    proj = make_minimal_project(td)
    episode = {"episode_id": "EP001", "title": "T", "shots": shots or BIG_SHOTS}
    (proj / "episode" / "episode.json").write_text(
        json.dumps(episode, ensure_ascii=False), encoding="utf-8")
    if names:
        folder = proj / "episode" / "assets" / "资产清单"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "assets.json").write_text(json.dumps(
            {aid: {"name": value} for aid, value in names.items()}, ensure_ascii=False), encoding="utf-8")
    return adopt_storyboard_fixture(proj)


def plan_of(proj, aid):
    file = proj / "episode" / "assets" / "资产清单" / "assets.json"
    return json.loads(file.read_text(encoding="utf-8")).get(aid)


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
        d = Desktop(win, root=HERE)
        d.root = proj
        d.studio = open_studio(proj)
        d.ensure_stage_layout()
        return d, win

    @staticmethod
    def _quiet(win):
        try:
            win.destroy()
        except Exception:
            pass
    def texts(self, widget):
        return widget_texts(widget, (self.ttk.Label, self.ttk.LabelFrame, self.ttk.Button, self.ttk.Checkbutton))

    def buttons(self, widget, text):
        return [w for w in widget_list(widget, (self.ttk.Button, self.tk.Button))
                if str(w.cget("text")) == text]

class TextHierarchyTests(_Harness):
    def test_five_description_sites_keep_long_text_and_token_styles_at_scaling(self):
        from types import SimpleNamespace
        from tkinter import font
        from ui_widgets import DescriptionBlock
        from ui_tokens import TEXT_DESC
        win = self.tk.Tk(); win.withdraw()
        self.addCleanup(win.destroy)
        original_scaling = float(win.tk.call('tk', 'scaling'))
        # Tk scaling is shared across interpreters in a reused test worker.
        self.addCleanup(win.tk.call, 'tk', 'scaling', original_scaling)
        long_text = '这是需要完整保留并自动换行的资产说明。' * 18
        with tempfile.TemporaryDirectory() as td:
            for scaling in (1.0, 1.5, 2.0):
                with self.subTest(scaling=scaling):
                    win.tk.call('tk', 'scaling', scaling)
                    content = self.ttk.Frame(win)
                    d = SimpleNamespace(content=content, root=Path(td), asset_base=lambda:Path(td),
                                        asset_requirements=lambda:{}, safe=lambda callback:callback())
                    asset = {'canonical_board':long_text, 'reference_role':long_text,
                             'reference_exclude':long_text}
                    gate = {'key':'anchor:CHAR_001', 'title':'待确认', 'candidates':['候选'],
                            'reason':long_text}
                    with mock.patch.object(confirm_gates, 'run', side_effect=[{'ask':[gate]}, {'ask':[]}]), \
                         mock.patch.object(ac, 'cells', return_value=[]), \
                         mock.patch.object(ac, 'card_lines', return_value=[('细节', long_text)]):
                        asset_detail._gates_block(d, 'CHAR_001')
                        asset_detail._board_block(d, 'CHAR_001', asset)
                        asset_detail._anchor_block(d, 'CHAR_001', asset)
                        asset_detail._role_block(d, 'CHAR_001', asset)
                    def labels(widget):
                        return ([widget] if isinstance(widget, DescriptionBlock) else []) + [
                            label for child in widget.winfo_children() for label in labels(child)]
                    descriptions = labels(content)
                    self.assertEqual(sorted(str(label.cget('text')) for label in descriptions), sorted([
                        prefix + long_text for prefix in ('理由：', '当前方案：', '细节：', '负责：', '不继承：')]))
                    win.update_idletasks()
                    for label in descriptions:
                        self.assertEqual(str(label.cget('foreground')), TEXT_DESC['foreground'])
                        self.assertEqual(int(label.cget('wraplength')), TEXT_DESC['wraplength'])
                        self.assertEqual(label.linespace, TEXT_DESC['linespace'])
                        self.assertLessEqual(label.winfo_reqwidth(), TEXT_DESC['wraplength'] + 10)
                        self.assertGreater(label.winfo_reqheight(),
                                           font.Font(root=win, font=label.cget('font')).metrics('linespace') * 2)
                    self.assertIn('（还没定稿：用下面的候选点一下，或点「编辑」自己写）', self.texts(content))
                    content.destroy()

    def test_asset_hints_and_empty_states_use_shared_text_components(self):
        from types import SimpleNamespace
        from ui_tokens import TEXT_DESC, TEXT_HINT
        from ui_widgets import DescriptionBlock, HintLabel
        win = self.tk.Tk(); win.withdraw()
        self.addCleanup(win.destroy)
        content = self.ttk.Frame(win)
        content.pack()
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / 'front.png').write_bytes(png(8, 8))
            d = SimpleNamespace(content=content, root=base, asset_base=lambda: base,
                                safe=lambda callback: callback(),
                                open_asset_detail=lambda _aid: None)
            with mock.patch.object(ac, 'cells', return_value=[
                    {'label': '正面', 'ready': True, 'image': 'front.png', 'view': 'front'}]), \
                 mock.patch.object(asset_detail.asset_thumbs, 'thumbnail', return_value=None):
                asset_detail._board_block(d, 'CHAR_001', {'name': '主角'})
            asset_detail._variants_block(d, 'CHAR_001', {'name': '主角'})
            asset_detail._roster_role(d, 'CHAR_001', {'name': '主角'})
            win.update_idletasks()

        def collect(widget, cls):
            found = [widget] if isinstance(widget, cls) else []
            for child in widget.winfo_children():
                found.extend(collect(child, cls))
            return found

        hints = collect(content, HintLabel)
        descriptions = collect(content, DescriptionBlock)
        hint_texts = [str(widget.cget('text')) for widget in hints]
        description_texts = [str(widget.cget('text')) for widget in descriptions]
        self.assertIn('（缩略图暂不可用）', hint_texts)
        self.assertIn('（缺图）', hint_texts)
        self.assertIn('还没有：剧本有换装需求时再新增（编号自动排 CST-01、CST-02…）', description_texts)
        self.assertIn('还没有状态变体：剧本有换装需求时，在详情页新增（编号自动排 CST-01…）', description_texts)
        self.assertIn('正典板 0/7 格已绑定 · 状态变体 0 个', description_texts)
        for widget in hints:
            self.assertEqual(str(widget.cget('foreground')), TEXT_HINT['foreground'])
            self.assertEqual(widget.linespace, TEXT_HINT['linespace'])
        for widget in descriptions:
            self.assertEqual(str(widget.cget('foreground')), TEXT_DESC['foreground'])
            self.assertEqual(widget.linespace, TEXT_DESC['linespace'])
        content.destroy()


class ScalingIsolationTests(_Harness):
    def test_text_hierarchy_restores_shared_tk_scaling(self):
        win = self.tk.Tk(); win.withdraw()
        self.addCleanup(win.destroy)
        original = float(win.tk.call('tk', 'scaling'))
        self.addCleanup(win.tk.call, 'tk', 'scaling', original)
        result = unittest.TestResult()
        unittest.defaultTestLoader.loadTestsFromTestCase(TextHierarchyTests).run(result)
        self.assertTrue(result.wasSuccessful(), result.failures + result.errors)
        self.assertAlmostEqual(float(win.tk.call('tk', 'scaling')), original, places=5)


class EntryTests(_Harness):
    """单功能 1：主页面 → 详情页跳转；返回。"""

    def test_the_table_row_opens_its_detail_page(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            d, win = self.desktop(proj)
            d.show(d.page_of("assets")); win.update()
            self.assertIn("CHAR_001", d.asset_table.get_children())
            d.asset_table.selection_set("CHAR_001")
            self.assertEqual(d.open_asset_detail(), "CHAR_001")
            win.update()
            self.assertEqual(d.asset_detail_id, "CHAR_001")
            self.assertTrue(any("返回资产管理" in text for text in self.texts(d.content)))

    def test_back_returns_to_the_main_page(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            d, win = self.desktop(proj)
            d.open_asset_detail("CHAR_002"); win.update()
            self.buttons(d.content, "← 返回资产管理")[0].invoke(); win.update()
            self.assertIsNone(d.asset_detail_id)
            self.assertIn("CHAR_002", d.asset_table.get_children())

    def test_an_unknown_id_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            d, win = self.desktop(proj)
            d.open_asset_detail("CHAR_777"); win.update()
            self.assertTrue(any("资产不存在" in text for text in self.texts(d.content)))


class BoardTests(_Harness):
    """单功能 2／3：7 面板转盘图展示与放大。"""

    def test_image_actions_are_keyboard_buttons(self):
        from ui_widgets import SecondaryButton
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            d, win = self.desktop(proj)
            path = d.asset_base() / 'keyboard.png'
            path.write_bytes(png(24, 32))
            asset = {'canon_board_views': {'front': 'keyboard.png'},
                     'state_variants': [{'state_id': 'CST-01', 'reference_image': 'keyboard.png'},
                                        {'state_id': 'CST-02', 'reference_image': 'keyboard.png'}]}
            asset_detail._board_block(d, 'CHAR_001', asset)
            asset_detail._variants_block(d, 'CHAR_001', asset)
            self.buttons(d.content, '状态变体（2 个）（展开）')[0].invoke()
            win.deiconify(); win.update()
            for title in ('CHAR_001 · 正面 0°', 'CHAR_001 · CST-01', 'CHAR_001 · CST-02'):
                with self.subTest(title=title):
                    buttons = self.buttons(d.content, '放大：' + title)
                    self.assertEqual(len(buttons), 1)
                    button = buttons[0]
                    self.assertIsInstance(button, SecondaryButton)
                    self.assertEqual(str(button.cget('takefocus')), '1')
                    self.assertEqual(button.tk_focusPrev().tk_focusNext(), button)
                    button.focus_force(); win.update()
                    with mock.patch.object(asset_detail, '_open_zoom') as opened:
                        button.event_generate('<Return>'); win.update()
                        self.assertEqual(opened.call_count, 1)
                        self.assertEqual(opened.call_args.args[:3], (d, path.resolve(), title))
                        opened.reset_mock()
                        button.event_generate('<space>'); win.update()
                        self.assertEqual(opened.call_count, 1)

    def test_zoom_focus_and_both_close_routes(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            d, win = self.desktop(proj)
            path = proj / 'preview.png'; path.write_bytes(png(24, 32))
            trigger = self.ttk.Button(d.content, text='source'); trigger.pack()
            win.deiconify(); win.update()
            for route in ('escape', 'button'):
                with self.subTest(route=route):
                    trigger.focus_force(); win.update()
                    zoom = asset_detail._open_zoom(d, path, 'preview')
                    win.update()
                    close = self.buttons(zoom, '关闭')[0]
                    self.assertEqual(zoom.focus_get(), close)
                    if route == 'escape':
                        close.event_generate('<Escape>')
                    else:
                        close.invoke()
                    win.update()
                    self.assertFalse(zoom.winfo_exists())
                    self.assertEqual(win.focus_get(), trigger)

    def test_reload_restores_focus_to_detail_navigation(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(project_with(td))
            d.open_asset_detail('CHAR_001'); win.deiconify(); win.update()
            old = self.buttons(d.content, '锁定')[0]
            old.focus_force(); win.update()
            old.invoke(); win.update()
            self.assertFalse(old.winfo_exists())
            self.assertEqual(win.focus_get(), self.buttons(d.content, '← 返回资产管理')[0])

    def test_seven_cells_with_angle_labels(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            d, win = self.desktop(proj)
            d.open_asset_detail("CHAR_001"); win.update()
            texts = self.texts(d.content)
            for label in ANGLE_LABELS:
                self.assertTrue(any(label in text for text in texts), label)
            self.assertEqual(len(ac.cells({})), 7)

    def test_a_bound_view_shows_up_and_zooms(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            folder = proj / "episode" / "assets" / "正典板"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "CHAR_001_front.png").write_bytes(png(240, 320))
            d, win = self.desktop(proj)
            d.asset_requirements()               # 先把资产清单落盘，再往那一项上绑图
            plan = proj / "episode" / "assets" / "资产清单" / "assets.json"
            data = json.loads(plan.read_text(encoding="utf-8"))
            data["CHAR_001"]["canon_board_views"] = {"front": "assets/正典板/CHAR_001_front.png"}
            plan.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            registry = d.asset_requirements()
            self.assertEqual(ac.view_image(registry["CHAR_001"], "front"),
                             "assets/正典板/CHAR_001_front.png")
            d.open_asset_detail("CHAR_001"); win.update()
            self.assertTrue(any("CHAR_001_front.png" in text for text in self.texts(d.content)))
            zoom = asset_detail._open_zoom(d, folder / "CHAR_001_front.png", "放大")
            self.assertIsNotNone(zoom)
            self.assertEqual(str(zoom.winfo_class()), "Toplevel")

    def test_a_bound_image_with_no_thumbnail_is_explained(self):
        """已绑定文件解不开时，不能谎报成“还没绑定”。"""
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            folder = proj / "episode" / "assets" / "正典板"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "CHAR_001_front.png").write_bytes(png(240, 320))
            d, win = self.desktop(proj)
            d.asset_requirements()
            plan = proj / "episode" / "assets" / "资产清单" / "assets.json"
            data = json.loads(plan.read_text(encoding="utf-8"))
            data["CHAR_001"]["canon_board_views"] = {"front": "assets/正典板/CHAR_001_front.png"}
            plan.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with mock.patch.object(asset_detail.asset_thumbs, "thumbnail", return_value=None):
                d.open_asset_detail("CHAR_001"); win.update()
            texts = self.texts(d.content)
            self.assertTrue(any("缩略图暂不可用" in text for text in texts))
            self.assertTrue(any("CHAR_001_front.png（可重新选择图片）" in text for text in texts))


class OperationCompletionTests(unittest.TestCase):
    """通过现行交互入口验证顺序与失败；不需要真实 Tk 窗口。"""

    def test_completion_refreshes_before_success_feedback(self):
        from types import SimpleNamespace
        events = []
        desktop = SimpleNamespace(status=SimpleNamespace(set=lambda text: events.append(text)))
        with mock.patch.object(asset_detail, '_reload', side_effect=lambda *_: events.append('refresh')):
            asset_detail._complete(desktop, 'CHAR_001', 'success')
        self.assertEqual(events, ['refresh', 'success'])

    def test_refresh_failure_does_not_publish_success(self):
        from types import SimpleNamespace
        status = mock.Mock()
        with mock.patch.object(asset_detail, '_reload', side_effect=RuntimeError('refresh failed')):
            with self.assertRaisesRegex(RuntimeError, 'refresh failed'):
                asset_detail._complete(SimpleNamespace(status=status), 'CHAR_001', 'success')
        status.set.assert_not_called()

    def test_pick_second_step_failure_never_counts_as_confirmed(self):
        """O10：第二步失败只留 failed，不许留「已确认」，页面也不许报成功。"""
        from types import SimpleNamespace
        import stage_execution_service as execution
        events = []
        desktop = SimpleNamespace(root=object(), status=mock.Mock())
        def fail(*args):
            events.append('apply')
            raise OSError('apply failed')
        with mock.patch.object(execution, 'record_stage_confirmation',
                               side_effect=lambda *args, **kwargs: events.append('record')), \
                mock.patch.object(execution, 'apply_asset_plan_gate_choice', side_effect=fail), \
                mock.patch.object(asset_detail, '_reload') as refresh:
            with self.assertRaisesRegex(RuntimeError, 'apply failed'):
                asset_detail._pick(desktop, 'anchor:CHAR_001', 'choice', 'CHAR_001')
        self.assertEqual(events, ['record', 'apply', 'record'], '待办→落盘→失败')
        refresh.assert_not_called()
        desktop.status.set.assert_not_called()

    def test_pick_first_step_failure_stops_before_applying(self):
        from types import SimpleNamespace
        import stage_execution_service as execution
        desktop = SimpleNamespace(root=object(), status=mock.Mock())
        with mock.patch.object(execution, 'record_stage_confirmation', side_effect=OSError('record failed')), \
                mock.patch.object(execution, 'apply_asset_plan_gate_choice') as apply, \
                mock.patch.object(asset_detail, '_reload') as refresh:
            with self.assertRaisesRegex(RuntimeError, 'record failed'):
                asset_detail._pick(desktop, 'anchor:CHAR_001', 'choice', 'CHAR_001')
        apply.assert_not_called()
        refresh.assert_not_called()
        desktop.status.set.assert_not_called()


class AnchorTests(_Harness):
    def test_picking_a_candidate_records_and_keeps_success_feedback(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            d, win = self.desktop(proj)
            d.open_asset_detail('CHAR_001'); win.update()
            asset_detail._pick(d, 'anchor:CHAR_001', '候选锚点', 'CHAR_001')
            self.assertIn('anchor:CHAR_001', confirm_gates.confirmations(proj))
            self.assertEqual(plan_of(proj, 'CHAR_001')['character_anchor'], '候选锚点')
            self.assertEqual(d.status.get(), '已采用：候选锚点（已写进资产 JSON）')

    def test_regenerate_reopens_confirmations_through_existing_gateway(self):
        from stage_execution_service import record_stage_confirmation
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            d, win = self.desktop(proj)
            d.open_asset_detail('CHAR_001'); win.update()
            keys = ['canon:CHAR_001', 'anchor:CHAR_001']
            for key in keys:
                record_stage_confirmation(proj, key, 'chosen')
            self.assertEqual(asset_detail.regenerate(d, 'CHAR_001'), keys)
            saved = confirm_gates.confirmations(proj)
            self.assertTrue(all(key not in saved for key in keys))
            self.assertTrue(d.status.get().startswith('已重新摆出候选：CHAR_001'))

    def test_regenerate_partial_failure_does_not_claim_success(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(project_with(td))
            d.open_asset_detail('CHAR_001'); win.update()
            with mock.patch.object(confirm_gates, 'forget', side_effect=[None, OSError('denied')]) as forget, \
                    mock.patch.object(asset_detail, '_reload') as reload_page:
                with self.assertRaisesRegex(OSError, 'denied'):
                    asset_detail.regenerate(d, 'CHAR_001')
                self.assertEqual(forget.call_count, 2)
                reload_page.assert_not_called()
                self.assertNotIn('已重新摆出候选', d.status.get())

    """单功能 4／5 ＋ 数据一致性：锚点展示、复制、编辑、与 JSON 逐字核对。"""

    def test_apply_choice_writes_the_anchor_and_the_board(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            apply_gate_choice(proj, "anchor:CHAR_001", "黑短发、杏眼、米色针织衫")
            apply_gate_choice(proj, "canon:CHAR_001", "方案一：写实骨相＋冷调布光")
            row = plan_of(proj, "CHAR_001")
            self.assertEqual(row["character_anchor"], "黑短发、杏眼、米色针织衫")
            self.assertEqual(row["base_anchor"], "黑短发、杏眼、米色针织衫")
            self.assertEqual(row["canonical_board"], "方案一：写实骨相＋冷调布光")
            self.assertIsNone(apply_gate_choice(proj, "conflict:B01", "候选一"),
                              "裁决那种 key 不写资产")

    def test_the_gate_stops_asking_after_the_choice_is_written(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            d, _win = self.desktop(proj)
            registry = d.asset_requirements()
            self.assertEqual(len(confirm_gates.run("G-05", project=proj, assets=registry)["ask"]), 3)
            from stage_execution_service import record_stage_confirmation
            record_stage_confirmation(proj, "anchor:CHAR_001", "黑短发、杏眼、米色针织衫")
            apply_gate_choice(proj, "anchor:CHAR_001", "黑短发、杏眼、米色针织衫")
            asked = confirm_gates.run("G-05", project=proj, assets=d.asset_requirements())["ask"]
            self.assertNotIn("anchor:CHAR_001", [item["key"] for item in asked])

    def test_editing_the_anchor_is_checked_against_the_json(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            d, win = self.desktop(proj)
            d.open_asset_detail("CHAR_001"); win.update()
            with mock.patch.object(asset_detail, "ask_string", return_value="  定稿锚点  "):
                self.assertEqual(asset_detail.edit_anchor(d, "CHAR_001"), "定稿锚点")
            self.assertEqual(plan_of(proj, "CHAR_001")["character_anchor"], "定稿锚点")
            self.assertEqual(d.status.get(), '锚点已保存并与资产 JSON 核对一致')

    def test_an_empty_anchor_is_refused(self):
        """空白输入不许写进资产清单。

        第 65 期：三虎在「半自动／全自动」档时，桌面那一拍（desktop.auto_decide_gates）会自己
        把待办里的推荐锚点采用掉——那是另一条路，不该混进这条用例。这里把档位钉在「只提示」，
        断言的就只剩「手动填空白 → 拒绝写入」这一件事，结果与用户存档里的档位无关。
        """
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            d, win = self.desktop(proj)
            import desktop as desktop_module
            original = desktop_module.Desktop.gate_level
            desktop_module.Desktop.gate_level = lambda self: "hint"
            self.addCleanup(setattr, desktop_module.Desktop, "gate_level", original)
            d.open_asset_detail("CHAR_001"); win.update()
            with mock.patch.object(asset_detail, "ask_string", return_value="   "):
                with mock.patch.object(asset_detail, "notify", wraps=asset_detail.notify) as notice, \
                        mock.patch.object(asset_detail.messagebox, "showerror") as modal_error:
                    self.assertIsNone(asset_detail.edit_anchor(d, "CHAR_001"))
                    self.assertEqual(notice.call_count, 1, "必须提示一句「不能为空」")
                    args, kwargs = notice.call_args
                    self.assertIn("不能为空", args[1], "提示文字必须说清哪里不能为空")
                    self.assertFalse(kwargs.get("modal", True), "可恢复错误必须走非模态通道")
                    modal_error.assert_not_called()
            self.assertIn("不能为空", d.status.get(), "用户必须能在状态栏看到这句提示")
            self.assertFalse(plan_of(proj, "CHAR_001").get("character_anchor"),
                             "空锚点不许写进去")

    def test_the_copy_button_copies_the_anchor(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            apply_gate_choice(proj, "anchor:CHAR_001", "黑短发、杏眼")
            d, win = self.desktop(proj)
            d.open_asset_detail("CHAR_001"); win.update()
            self.assertEqual(len(self.buttons(d.content, "复制")), 1)
            self.buttons(d.content, "复制")[0].invoke(); win.update()
            self.assertIn("已复制", str(d.status.get() if hasattr(d.status, "get") else ""))


class VariantTests(_Harness):
    """单功能 6／7／8：状态变体折叠、新增，以及锁定／解锁。"""

    def test_the_foldout_lists_the_variants(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            plan = proj / "episode" / "assets" / "资产清单" / "assets.json"
            folder = plan.parent; folder.mkdir(parents=True, exist_ok=True)
            data = json.loads(plan.read_text(encoding="utf-8")) if plan.is_file() else {}
            data.setdefault("CHAR_001", {})["state_variants"] = [
                {"state_id": "CST-01", "name": "日常装", "override": "米色针织衫"}]
            plan.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            d, win = self.desktop(proj)
            d.open_asset_detail("CHAR_001"); win.update()
            texts = self.texts(d.content)
            self.assertTrue(any("状态变体（1 个）" in text for text in texts), texts)
            self.buttons(d.content, "状态变体（1 个）（展开）")[0].invoke(); win.update()
            texts = self.texts(d.content)
            self.assertTrue(any("CST-01" in text and "日常装" in text for text in texts), texts)

    def test_adding_a_variant_writes_the_json(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            d, win = self.desktop(proj)
            d.open_asset_detail("CHAR_001"); win.update()
            with mock.patch.object(asset_detail, "ask_string",
                                   side_effect=["雨夜装", "深色雨衣"]):
                asset_detail.add_variant(d, "CHAR_001")
            rows = plan_of(proj, "CHAR_001")["state_variants"]
            self.assertEqual([item["state_id"] for item in rows], ["CST-01"])
            self.assertEqual(rows[0]["name"], "雨夜装")
            self.assertEqual(rows[0]["override"], "深色雨衣")
            self.assertEqual(d.status.get(), '已新增状态变体：雨夜装')

    def test_deleting_a_variant_asks_first(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            plan = proj / "episode" / "assets" / "资产清单" / "assets.json"
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text(json.dumps({"CHAR_001": {"state_variants": [
                {"state_id": "CST-01", "name": "日常装", "override": "米色针织衫"}]}},
                ensure_ascii=False), encoding="utf-8")
            d, win = self.desktop(proj)
            d.open_asset_detail("CHAR_001"); win.update()
            with mock.patch.object(asset_detail, "ask_confirmation", return_value=False) as ask:
                self.assertIsNone(asset_detail.delete_variant(d, "CHAR_001", "CST-01"))
                self.assertTrue(ask.called, "先问一句再动手")
            self.assertEqual(len(plan_of(proj, "CHAR_001")["state_variants"]), 1)
            with mock.patch.object(asset_detail, "ask_confirmation", return_value=True):
                asset_detail.delete_variant(d, "CHAR_001", "CST-01")
            self.assertEqual(plan_of(proj, "CHAR_001")["state_variants"], [])
            self.assertEqual(d.status.get(), '已删除状态变体：日常装')

    def test_locking_writes_the_json(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            d, win = self.desktop(proj)
            d.open_asset_detail("CHAR_001"); win.update()
            self.assertTrue(asset_detail.toggle_lock(d, "CHAR_001"))
            self.assertTrue(plan_of(proj, "CHAR_001")["locked"])
            asset_detail.toggle_lock(d, "CHAR_001")
            self.assertFalse(plan_of(proj, "CHAR_001")["locked"])

    def test_the_role_declaration_is_editable(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            d, win = self.desktop(proj)
            d.open_asset_detail("CHAR_001"); win.update()
            with mock.patch.object(asset_detail, "ask_string",
                                   side_effect=["面部、发型", "场景、动作"]):
                asset_detail.edit_role(d, "CHAR_001")
            row = plan_of(proj, "CHAR_001")
            self.assertEqual(row["reference_role"], "面部、发型")
            self.assertEqual(row["reference_exclude"], "场景、动作")


class EndToEndTests(_Harness):
    """附件任务 5.2／5.3／5.4：数据一致性、端到端（3 角色＋2 场景＋2 道具）、回归。"""

    def test_the_contract_fields_land_in_the_asset_json(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            d, _win = self.desktop(proj)
            registry = d.asset_requirements()
            self.assertEqual(sorted(registry), ["CHAR_001", "CHAR_002", "CHAR_003",
                                                "LOC_001", "LOC_002", "PROP_001", "PROP_002"])
            for aid in ("CHAR_001", "LOC_001", "PROP_001"):
                row = plan_of(proj, aid)
                for key in ac.defaults(ac.kind_of(aid)):
                    self.assertIn(key, row, (aid, key))

    def test_the_whole_flow_over_seven_assets(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            d, win = self.desktop(proj)
            for aid in ("CHAR_001", "CHAR_002", "CHAR_003"):
                from stage_execution_service import record_stage_confirmation
                record_stage_confirmation(proj, "anchor:" + aid, aid + " 的定稿锚点")
                apply_gate_choice(proj, "anchor:" + aid, aid + " 的定稿锚点")
                apply_gate_choice(proj, "canon:" + aid, aid + " 的正典板方案一")
                with mock.patch.object(asset_detail, "ask_string",
                                       side_effect=["日常装", "米色针织衫"]):
                    d.open_asset_detail(aid); win.update()
                    asset_detail.add_variant(d, aid)
                asset_detail.toggle_lock(d, aid)
            for aid in ("CHAR_001", "CHAR_002", "CHAR_003"):
                row = plan_of(proj, aid)
                self.assertEqual(row["character_anchor"], aid + " 的定稿锚点")
                self.assertEqual(row["canonical_board"], aid + " 的正典板方案一")
                self.assertEqual(len(row["state_variants"]), 1)
                self.assertTrue(row["locked"])
            d.close_asset_detail(); win.update()
            self.assertIsNotNone(d.asset_table)
            for aid in ("CHAR_001", "LOC_002", "PROP_002"):
                self.assertIn(aid, d.asset_table.get_children())

    def test_the_main_table_shows_what_the_detail_page_shows(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td, names={"CHAR_001": "摄像头侠"})
            d, win = self.desktop(proj)
            d.show(d.page_of("assets")); win.update()
            shown = d.asset_table.set("CHAR_001", "name")
            d.open_asset_detail("CHAR_001"); win.update()
            self.assertTrue(any("摄像头侠" in text for text in self.texts(d.content)), "两处同名")
            self.assertEqual(shown, "摄像头侠")
            d.close_asset_detail(); win.update()
            self.assertEqual(d.asset_table.set("CHAR_001", "name"), "摄像头侠")

    def test_regression_the_table_still_filters_by_kind(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            d, win = self.desktop(proj)
            d.show(d.page_of("assets")); win.update()
            self.assertEqual(sorted(d.asset_table.get_children()),
                             ["CHAR_001", "CHAR_002", "CHAR_003",
                              "LOC_001", "LOC_002", "PROP_001", "PROP_002"])
            d.asset_kind = "characters"
            d.show(d.page_of("assets")); win.update()
            self.assertEqual(sorted(d.asset_table.get_children()),
                             ["CHAR_001", "CHAR_002", "CHAR_003"])
            for label in ("全部", "角色", "场景", "道具", "检查提示词", "识别背景人物",
                          "导入参考图", "批量删除资产", "资产目录", "手动制作资产"):
                self.assertTrue(self.buttons(d.content, label), label)


class RosterTests(_Harness):
    """第 71 期任务 2：侧栏「资产清单」二级入口 → 资产清单页（正典板＋换状态面板）。"""

    def test_the_rows_sort_roles_then_scenes_then_props(self):
        """排序：角色 → 场景 → 道具，同一类按编号；认不出的类目排最后。"""
        registry = {"PROP_002": {}, "LOC_001": {}, "CHAR_002": {}, "CHAR_001": {},
                    "LOC_002": {}, "PROP_001": {}, "MYSTERY_001": {}, "junk": 5}
        rows = [aid for aid, _asset in asset_detail.roster_rows(registry)]
        self.assertEqual(rows, ["CHAR_001", "CHAR_002", "LOC_001", "LOC_002",
                                "PROP_001", "PROP_002", "MYSTERY_001"],
                         "非字典的条目不上榜")

    def test_the_sidebar_entry_opens_the_roster_page(self):
        """第 R2946 期：资产清单是「05 资产管理」图标的二级入口——点图标弹选择层，层里点「资产清单」。"""
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            d, win = self.desktop(proj)
            index = d.page_of("assets")
            d.show(index); win.update()
            d.nav[index].invoke(); win.update()
            top = getattr(d, "_sidebar_popup_win", None)
            self.assertIsNotNone(top, "点资产管理图标要弹出二级选择层")
            entries = [w for w in widget_list(top, (self.ttk.Button, self.tk.Button))
                       if str(w.cget("text")) == "资产清单"]
            self.assertEqual(len(entries), 1, "选择层里只有「资产清单」一项")
            entries[0].invoke(); win.update()
            self.assertTrue(d.asset_roster)
            self.assertIsNone(d.asset_detail_id)
            texts = self.texts(d.content)
            self.assertTrue(any("资产清单" in t for t in texts), "页头写着资产清单")
            self.assertTrue(any("正典板" in t for t in texts), "每个角色都有正典板")
            self.assertTrue(any("换状态" in t for t in texts), "角色还有换状态面板")
            self.assertTrue(self.buttons(d.content, "编辑这一项"), "改内容还得能进详情页")
            self.assertEqual(d.nav[index]._nav_icon_name, "asset_list",
                             "清单页激活时资产管理图标换成清单字形")
            # 选择层开着时再点图标回资产管理主页，图标换回常态。
            d.nav[index].invoke(); win.update()
            d.nav[index].invoke(); win.update()
            self.assertFalse(d.asset_roster, "再点一次图标回资产管理主页")
            self.assertEqual(d.nav[index]._nav_icon_name, "assets")

    def test_leaving_the_page_drops_the_roster_route(self):
        """翻到别的页就回主页面，资产管理图标也换回常态字形。"""
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            d, win = self.desktop(proj)
            index = d.page_of("assets")
            d.open_asset_roster(); win.update()
            self.assertTrue(d.asset_roster)
            self.assertEqual(d.nav[index]._nav_icon_name, "asset_list")
            d.show(d.page_of("script")); win.update()
            self.assertFalse(d.asset_roster, "翻到别的页就回主页面")
            self.assertIsNone(d.asset_detail_id)
            self.assertEqual(d.nav[index]._nav_icon_name, "assets")

    def test_back_returns_to_the_asset_main_page(self):
        """清单页的「返回资产管理」回资产管理主页面。"""
        with tempfile.TemporaryDirectory() as td:
            proj = project_with(td)
            d, win = self.desktop(proj)
            d.open_asset_roster(); win.update()
            self.buttons(d.content, "← 返回资产管理")[0].invoke(); win.update()
            self.assertFalse(d.asset_roster)
            self.assertIsNone(d.asset_detail_id)
            self.assertTrue(self.buttons(d.content, "手动制作资产"), "回到资产管理主页")


if __name__ == "__main__":
    unittest.main(verbosity=2)
