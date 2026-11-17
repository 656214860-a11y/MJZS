# -*- coding: utf-8 -*-
"""第 47 期第 3 条：点「手动XX」先问一句「模型配了吗」。

用户的要求：点「手动XX」按钮后弹窗提示用户去配模型，并且配一次各页同步
（模型只存一份，各页读的都是它）。这一份盯住：

* 模型已经挑过（不是「自动」）就不啰嗦；没选项目也不拦；
* 还是「自动」时问一句：答「是」→ 就地弹开底部共享输入框的模型下拉框（R2942 起，
  替代原「阶段配置」面板），这一次不开始制作（返回 False）；答「否」→ 照旧开始；
* 同一个阶段一个会话里只问一次（别每点一下都弹）；
* 六个阶段页的「手动XX」都套了这一层：闸拦下来时那一步真的没动手。

运行：python test_manual_gate.py
"""
import os, sys, tempfile, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); os.chdir(HERE)

from test_row_targets import PageHelpers, make_project
from infra.pet_state import PAGE_OF


class Status:
    def __init__(self):
        self.text = ""

    def set(self, text):
        self.text = str(text)


def stub_desktop(project):
    subject = type("Stub", (), {})()
    subject.root = project
    subject.status = Status()
    subject.win = None
    return subject


class GateTests(unittest.TestCase):
    """before_manual 自己的规矩。"""

    def setUp(self):
        import skill_panel, stage_models
        self.sm = stage_models
        self.asks = []
        self.answer = False
        self.sm.ASKER = lambda *a, **k: (self.asks.append((a, k)), self.answer)[1]
        self.addCleanup(setattr, self.sm, "ASKER", None)
        self.opened = []
        original = skill_panel.show
        skill_panel.show = lambda desktop, stage, function=None: self.opened.append(stage)
        self.addCleanup(setattr, skill_panel, "show", original)
        self.dropped = []
        original_drop = stage_models.open_model_dropdown
        stage_models.open_model_dropdown = lambda desktop: self.dropped.append(desktop)
        self.addCleanup(setattr, stage_models, "open_model_dropdown", original_drop)

    def message(self):
        return str(self.asks[-1][0][1]) if self.asks else ""

    def test_no_project_is_not_our_business(self):
        self.assertTrue(self.sm.before_manual(stub_desktop(None), "previs"))
        self.assertEqual(self.asks, [])

    def test_a_chosen_model_is_not_asked_about(self):
        import stage_config
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; proj.mkdir()
            stage_config.put(proj, "previs", "gpt-5-codex")
            self.assertTrue(self.sm.before_manual(stub_desktop(proj), "previs"))
            self.assertEqual(self.asks, [])
            self.assertEqual(self.opened, [])

    def test_the_auto_model_is_asked_about_once_per_stage(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; proj.mkdir()
            desktop = stub_desktop(proj)
            self.assertTrue(self.sm.before_manual(desktop, "previs"), "答「否」照旧开始")
            self.assertEqual(len(self.asks), 1)
            self.assertTrue(self.sm.before_manual(desktop, "previs"))
            self.assertEqual(len(self.asks), 1, "同一个阶段一个会话里只问一次")
            self.assertTrue(self.sm.before_manual(desktop, "keyframe"))
            self.assertEqual(len(self.asks), 2, "换个阶段还是要问")

    def test_saying_yes_opens_the_panel_and_skips_this_round(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; proj.mkdir()
            desktop = stub_desktop(proj)
            self.answer = True
            self.assertFalse(self.sm.before_manual(desktop, "assets"), "答「是」这一次不开始")
            self.assertEqual(self.dropped, [desktop], "答「是」就弹开共享输入框的模型下拉框")
            self.assertEqual(self.opened, [], "不再打开阶段配置面板")
            self.assertIn("模型下拉框", desktop.status.text)
            self.assertIn("模型", desktop.status.text)

    def test_the_message_points_at_the_stage_config_and_the_shared_setting(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; proj.mkdir()
            self.sm.before_manual(stub_desktop(proj), "previs")
            text = self.message()
            self.assertIn("模型下拉框", text)
            self.assertIn("模型", text)
            self.assertIn("白模预演", text, "说清是哪一步")
            self.assertIn("跟着变", text, "说清「配一次各页同步」")

    def test_default_confirmation_uses_the_l4_presenter_without_reverse_import(self):
        seen = []
        previous_presenter = self.sm._CONFIRMATION_PRESENTER
        previous_self_test = self.sm.SELF_TEST
        self.sm.ASKER = None
        self.sm.SELF_TEST = False
        self.sm.set_confirmation_presenter(
            lambda title, message, parent=None: seen.append((title, message, parent)) or True)
        self.addCleanup(self.sm.set_confirmation_presenter, previous_presenter)
        self.addCleanup(setattr, self.sm, "SELF_TEST", previous_self_test)
        self.assertTrue(self.sm._ask("确认标题", "确认内容", "父窗口"))
        self.assertEqual(seen, [("确认标题", "确认内容", "父窗口")])

    def test_a_broken_config_counts_as_auto_and_the_work_still_goes_on(self):
        """配置写坏了：面板按默认值（模型＝自动）走，这里也一样——问一句，答「否」照旧开工。"""
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; proj.mkdir()
            (proj / "skill_config.json").write_text("不是一份配置", encoding="utf-8")
            self.assertTrue(self.sm.before_manual(stub_desktop(proj), "previs"))
            self.assertEqual(len(self.asks), 1)


class ManualCommandTests(unittest.TestCase):
    """manual_command：闸放行就动手，拦下来就这一次不做。"""

    def setUp(self):
        import stage_models
        self.sm = stage_models

    def test_the_action_runs_when_the_gate_lets_it_through(self):
        import stage_models
        original = stage_models.before_manual
        stage_models.before_manual = lambda desktop, stage, parent=None: True
        self.addCleanup(setattr, stage_models, "before_manual", original)
        ran = []
        run = self.sm.manual_command(stub_desktop(None), "previs", lambda: ran.append("done"))
        self.assertTrue(run())
        self.assertEqual(ran, ["done"])

    def test_the_action_is_skipped_when_the_user_goes_to_configure(self):
        import stage_models
        original = stage_models.before_manual
        stage_models.before_manual = lambda desktop, stage, parent=None: False
        self.addCleanup(setattr, stage_models, "before_manual", original)
        ran = []
        run = self.sm.manual_command(stub_desktop(None), "previs", lambda: ran.append("done"))
        self.assertFalse(run())
        self.assertEqual(ran, [])

    def test_the_gate_gets_the_stage_and_the_parent_window(self):
        import stage_models
        seen = []
        original = stage_models.before_manual
        stage_models.before_manual = lambda desktop, stage, parent=None: (seen.append((stage, parent)), True)[1]
        self.addCleanup(setattr, stage_models, "before_manual", original)
        desktop = stub_desktop(None)
        self.sm.manual_command(desktop, "video", lambda: None, "窗口")()
        self.assertEqual(seen, [("video", "窗口")])


class ManualButtonTests(PageHelpers):
    """十个阶段页的「手动XX」：闸拦下来时那一步真的没动手，放行时照旧。"""

    def setUp(self):
        super().setUp()
        import stage_models
        self.gated = []
        self.allow = False
        original = stage_models.before_manual
        def fake(desktop, stage, parent=None):
            self.gated.append(stage)
            return self.allow
        stage_models.before_manual = fake
        self.addCleanup(setattr, stage_models, "before_manual", original)

    def popups(self, win):
        return [w for w in win.winfo_children() if isinstance(w, self.tk.Toplevel)
                and not getattr(w, "_drama_cloud", False)]

    def test_the_previs_button_asks_before_starting(self):
        import previs_routing
        seen = []
        original = previs_routing.dispatch
        previs_routing.dispatch = lambda project, source, ids, state, monitor=False, start_complex=None, *, publish: (
            seen.append(list(ids)) or {"medium": []})
        self.addCleanup(setattr, previs_routing, "dispatch", original)
        with tempfile.TemporaryDirectory() as td:
            d, win, proj = self.page(td)
            self.show(d, win, PAGE_OF['previs'])
            d.previs_jobs["selected"].clear()          # 用户取消了默认勾选，只剩高亮那一行
            tree = self.tables(d.content)[0]
            tree.selection_set("SH001"); tree.focus("SH001")
            self.assertTrue(self.wait_for(win, lambda: self.button_state(d, "手动制作白模") == "normal"),
                            "高亮那一行也算选中，按钮该亮")
            self.buttons(d.content)["手动制作白模"].invoke(); win.update()
            self.assertEqual(self.gated, ["previs"])
            self.assertEqual(seen, [], "闸拦下来时一步都没派发")
            self.allow = True
            self.buttons(d.content)["手动制作白模"].invoke(); win.update()
            self.assertEqual(seen, [["SH001"]], "闸放行时照旧派发高亮那一行")
            self.assertEqual(self.gated, ["previs", "previs"])

    def test_the_keyframe_button_does_not_open_the_window_when_stopped(self):
        with tempfile.TemporaryDirectory() as td:
            d, win, proj = self.page(td, frames=True)
            self.show(d, win, PAGE_OF['keyframe'])
            self.buttons(d.content)["手动制作首帧"].invoke(); win.update()
            self.assertEqual(self.gated, ["keyframe"])
            self.assertEqual(self.popups(win), [], "闸拦下来时不该冒出「首帧制作」窗口")

    def test_the_asset_button_does_not_open_the_window_when_stopped(self):
        with tempfile.TemporaryDirectory() as td:
            d, win, proj = self.page(td)
            d.asset_requirements = lambda: {"CHAR_001": {"id": "CHAR_001", "name": "角色", "status": "待导入"}}
            d.asset_kind = "characters"
            d.asset_checks = {str(Path(proj).resolve()): {"CHAR_001": True}}
            d.asset_checked_count = 1
            d.asset_has_pending = True
            self.show(d, win, PAGE_OF['assets'])
            d.update_asset_buttons()
            self.buttons(d.content)["手动制作资产"].invoke(); win.update()
            self.assertEqual(self.gated, ["assets"])
            self.assertEqual(self.popups(win), [], "闸拦下来时不该冒出资产制作窗口")

    def test_the_video_button_does_not_submit_when_stopped(self):
        with tempfile.TemporaryDirectory() as td:
            d, win, proj = self.page(td)
            # 10 视频生成：这一页的 App 由桌面建（这一页要先进「本地生成」这一侧）。
            for _ in range(2):
                d.show(PAGE_OF['video'], video_mode="local"); win.update_idletasks(); win.update()
            application = d.video
            self.assertIsNotNone(application, "第 08 页该把镜头工作台建出来")
            before = application.log.get("1.0", "end")
            self.buttons(d.content)["手动制作视频"].invoke(); win.update()
            self.assertEqual(self.gated, ["video"])
            self.assertEqual(application.log.get("1.0", "end"), before, "闸拦下来时什么都没提交")
            self.assertFalse(application.busy)

    def test_the_storyboard_button_does_not_start_the_agent_when_stopped(self):
        from test_row_targets import fresh
        with tempfile.TemporaryDirectory() as td:
            folder = None
            d, win, proj = self.page(td)
            folder = Path(proj) / "storyboard" / "分镜拆分"
            second = folder / "episode_2.json"
            second.write_text((folder / "episode.json").read_text(encoding="utf-8"), encoding="utf-8")
            fresh(proj)                                 # 别让 normalize 把新文件改名
            calls = []
            d.open_storyboard_skill = lambda *a, **k: calls.append(a)
            self.show(d, win, PAGE_OF['storyboard'])
            tree = self.tables(d.content)[1]
            tree.selection_set(str(second)); tree.focus(str(second)); win.update()
            self.assertEqual(self.button_state(d, "手动制作分镜"), "normal",
                             "高亮那份没采用过的分镜也算选中，按钮该亮")
            self.buttons(d.content)["手动制作分镜"].invoke(); win.update()
            self.assertEqual(self.gated, ["storyboard"])
            self.assertEqual(calls, [], "闸拦下来时没启动 agent")

    def test_the_script_page_has_no_legacy_manual_button(self):
        with tempfile.TemporaryDirectory() as td:
            d, win, _proj = self.page(td)
            self.show(d, win, PAGE_OF['script'])
            self.assertNotIn("手动制作剧本", self.buttons(d.content),
                             "剧本页以发送创意作为唯一工作流入口，不恢复废弃手动按钮")


if __name__ == "__main__":
    unittest.main(verbosity=2)
