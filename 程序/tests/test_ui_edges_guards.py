# -*- coding: utf-8 -*-
"""UI 边界回归（源码守卫域，不依赖 Tk）：自 test_ui_edges.py 拆出，断言原样。"""
import sys, tempfile, unittest
from pathlib import Path

from ui_edges_support import PROGRAM, make_adopted_project

class PromptWindowSourceGuardTests(unittest.TestCase):
    """源码守卫：「复制提示词」只保留一份实现，两个入口都必须委托 prompt_window。"""

    def program_sources(self):
        from tests.architecture._scan import desktop_text, entity_file
        sources = {p.name: entity_file(p.stem).read_text(encoding="utf-8") for p in sorted(Path(PROGRAM).glob("*.py")) if not p.name.startswith("test_")}
        sources["desktop.py"] = desktop_text()  # R1505：Desktop 方法分布在 desktop.py 与迁出的 Mixin 模块
        return sources

    def test_copy_button_lives_only_in_prompt_window(self):
        """页面自带一份复制弹窗，复制后的行为就会再次走偏（历史 BUG：一个关窗一个不关）。"""
        offenders = [name for name, text in self.program_sources().items() if name != "prompt_window.py" and "复制提示词" in text]
        self.assertEqual(offenders, [])

    def test_prompt_entries_share_one_window(self):
        """「查看首帧提示词」与资产提示词两处入口必须共用 prompt_window，不再各写一份弹窗。"""
        sources = self.program_sources()
        for name in ("desktop.py", "asset_reference_prompts_dialog.py"):
            self.assertIn("prompt_window import show", sources[name])

    def test_clipboard_writes_go_through_one_helper(self):
        """全程序只有 prompt_window.copy_text 写剪贴板：提示词窗口与 Codex 任务文本都走它。

        各写一份时出过「一个窗口复制后关、另一个不关」，以及「复制失败没人处理」。
        """
        sources = self.program_sources()
        # desktop 的输入框右键「粘贴」可以直接读取 Tk 剪贴板；所有写入必须走 copy_text。
        offenders = [name for name, text in sources.items()
                     if name != "prompt_window.py" and "clipboard_append" in text]
        self.assertEqual(offenders, [])
        self.assertEqual(sources["prompt_window.py"].count("clipboard_append"), 1)
        self.assertIn("copy_text", sources["local_previs.py"])            # 白模制作说明的复制
        self.assertIn("copy_text", sources["desktop.py"])                 # Codex 任务文本

class ApprovedVersionSourceGuardTests(unittest.TestCase):
    """源码守卫：「已下载＋质检通过＋已验收」只保留一份实现（engine.approved_versions）。"""

    PREDICATE = "v.get('review')=='pass' and v.get('state')=='downloaded' and v.get('qc_pass')"

    def program_sources(self):
        from tests.architecture._scan import desktop_text, entity_file
        sources = {p.name: entity_file(p.stem).read_text(encoding="utf-8") for p in sorted(Path(PROGRAM).glob("*.py")) if not p.name.startswith("test_")}
        sources["desktop.py"] = desktop_text()  # R1505：Desktop 方法分布在 desktop.py 与迁出的 Mixin 模块
        return sources

    def test_approval_predicate_lives_only_in_engine(self):
        """口径散在自动粗剪、手动拼装、交接包三处时，改一处就会让成片和交接包取到不同版本。"""
        sources = self.program_sources()
        offenders = [name for name, text in sources.items() if name != "engine.py" and self.PREDICATE in text]
        self.assertEqual(offenders, [])
        self.assertEqual(sources["engine.py"].count(self.PREDICATE), 1)

    def test_approval_consumers_use_the_shared_helper(self):
        """engine 的两处筛选、进度与交付界面都必须走同一个「采用版」助手，别再各挑各的版本。"""
        sources = self.program_sources()
        self.assertRegex(sources["desktop.py"], r"from (?:orchestrator\.)?engine import [^\n]*\bapproved_versions\b")
        self.assertRegex(sources["desktop.py"], r"from (?:orchestrator\.)?engine import [^\n]*\badoption_summary\b")
        # 交付界面消费者已迁至 orchestrator/media_page_controller（不在顶层 glob 内），直接读实体文件。
        consumer = entity_file('media_page_controller').read_text(encoding='utf-8')
        self.assertRegex(consumer, r"from (?:orchestrator\.)?engine import [^\n]*\badopted_edit_version\b")
        self.assertRegex(consumer, r"from (?:orchestrator\.)?engine import [^\n]*\badoption_summary\b")
        # 自动粗剪与手动拼装都收敛到 adopted_edit_version；approved_versions 只留一处实现。
        self.assertEqual(sources["engine.py"].count("adopted_edit_version(st['shots'].get(shot['id'])"), 2)
        self.assertEqual(sources["engine.py"].count("approved_versions(st['shots'].get(shot['id']))"), 0)

class EngineNameFallbackTests(unittest.TestCase):
    """第 14 期：workflow_settings 里没有 model_name 时，白模页不该整页炸在 ImportError 上。

    用户报的 BUG 就是「白模预演 -> cannot import name model_name from workflow_settings」：
    这句提示只该让模型名显示为空，页面照常打开、照样能开始制作。
    """

    def test_the_name_comes_from_the_workflow_settings(self):
        import local_previs, workflow_settings
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            self.assertEqual(local_previs.engine_name(proj), workflow_settings.model_name(proj, "previs"))

    def test_a_settings_module_without_the_name_falls_back_to_empty(self):
        import contextlib, io, types
        import local_previs
        saved = sys.modules.get("orchestrator.workflow_settings")
        sys.modules["orchestrator.workflow_settings"] = types.ModuleType("orchestrator.workflow_settings")   # 有包、没函数

        def restore():
            if saved is None:
                sys.modules.pop("orchestrator.workflow_settings", None)
            else:
                sys.modules["orchestrator.workflow_settings"] = saved
        self.addCleanup(restore)
        with tempfile.TemporaryDirectory() as td, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(local_previs.engine_name(make_adopted_project(td)), "",
                             "读不到名字只该退回空串，不该把异常甩到页面上")

    def test_the_page_asks_the_module_level_helper(self):
        from tests.architecture._scan import entity_file
        source = entity_file("local_previs").read_text(encoding="utf-8")
        self.assertIn("def engine_name(project):", source, "取名字的容错逻辑要在模块级，自检才喂得进坏模块")
        self.assertIn("previs_engine=engine_name(self.project)", source)  # R1836：show 改写成类
