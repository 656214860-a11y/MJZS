# -*- coding: utf-8 -*-
"""项目阶段目录树（第 61 期 v0.8 任务 2／9／11）的自检。运行：python test_stage_layout.py

盯住四件事：① ensure 只建缺的、绝不覆盖已有文件；② 每个阶段目录都是「input／output／assets／
docs／skills／logs ＋ README.md」七件套；③ README 就是那一阶段的输入输出契约（交付物 1／8／11）；
④ 老目录只做对照（legacy_map）与归位（adopt_legacy：只建目录联接，绝不搬动、绝不删除）。
断言全用临时目录，绝不碰真安装目录。
"""
from skip_reasons import (
    MISSING_NODE,
    PLATFORM_DIRECTORY_LINK,
    PLATFORM_TKINTER,
    PLATFORM_TK_DISPLAY,
    PLATFORM_WORKING_SET,
    REQUIRES_BUNDLED_SKILL,
)
import os, sys, tempfile, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import stage_layout
from stage_contract_report import contract_rows

SUBDIRS = ('input', 'output', 'assets', 'docs', 'skills', 'logs')


class TreeTests(unittest.TestCase):
    """目录树本体：建得全、不覆盖、能重跑。"""

    def test_ensure_builds_every_stage_and_shared_dir(self):
        with tempfile.TemporaryDirectory() as td:
            created = stage_layout.ensure(td)
            self.assertTrue(created, "第一次必须真的建了东西")
            for name in stage_layout.names():
                root = Path(td) / name
                self.assertTrue(root.is_dir(), name)
                for sub in SUBDIRS:
                    self.assertTrue((root / sub).is_dir(), name + "/" + sub)
                self.assertTrue((root / "README.md").is_file(), name + "/README.md")
            for sub in ("schema", "anchors", "triplets"):
                self.assertTrue((Path(td) / "_shared" / sub).is_dir(), "_shared/" + sub)
            self.assertTrue((Path(td) / "_archive" / "logs").is_dir())

    def test_readme_is_a_file_not_a_directory(self):
        """ensure 曾经把 README.md 当目录 mkdir 出来（paths() 里 'readme' 是文件路径）。"""
        with tempfile.TemporaryDirectory() as td:
            stage_layout.ensure(td)
            for name in stage_layout.names():
                self.assertFalse((Path(td) / name / "README.md").is_dir(), name)
                self.assertGreater((Path(td) / name / "README.md").stat().st_size, 0)

    def test_ensure_is_idempotent_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as td:
            stage_layout.ensure(td)
            readme = Path(td) / "01剧本准备" / "README.md"
            readme.write_text("人工改过的说明", encoding="utf-8")
            keep = Path(td) / "05资产管理" / "docs" / "character_brief.md"
            keep.write_text("人写的角色创意", encoding="utf-8")
            self.assertEqual(stage_layout.ensure(td), [], "第二次不该再建东西")
            self.assertEqual(readme.read_text(encoding="utf-8"), "人工改过的说明")
            self.assertEqual(keep.read_text(encoding="utf-8"), "人写的角色创意")
            self.assertTrue(stage_layout.ready(td))

    def test_ready_is_false_before_and_true_after(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertFalse(stage_layout.ready(td))
            stage_layout.ensure(td)
            self.assertTrue(stage_layout.ready(td))


class ContractTests(unittest.TestCase):
    """输入输出契约与两份清单（交付物 1／7／8／10／11）。"""

    def test_readme_is_the_input_output_contract(self):
        with tempfile.TemporaryDirectory() as td:
            stage_layout.ensure(td)
            text = (Path(td) / "07分镜定稿" / "README.md").read_text(encoding="utf-8")
            self.assertIn("storyboard_final.json", text)
            self.assertIn("input/", text)
            self.assertIn("docs/", text)
            self.assertIn("JSON 为唯一机器输入", text)

    def test_tree_text_lists_every_stage_and_shared(self):
        text = stage_layout.tree_text()
        for name in stage_layout.names():
            self.assertIn(name + "/", text)
        self.assertIn("_shared/", text)
        self.assertIn("_archive/", text)
        self.assertIn("README.md", text)

    def test_the_tree_draws_readme_as_the_last_branch(self):
        text = stage_layout.tree_text()
        self.assertNotIn("└── logs/", text, "logs 后面还有 README，不该是最后一个分支")
        self.assertEqual(text.count("└── README.md"), 13)
        self.assertEqual(text.count("├── logs/"), 13)

    def test_contract_rows_pair_stages_with_gates_and_docs(self):
        rows = contract_rows()
        self.assertEqual(len(rows), 13)
        by_folder = {row["folder"]: row for row in rows}
        self.assertIn("G-07", by_folder["07分镜定稿"]["gates"])
        self.assertIn("G-08", by_folder["06连贯性清单"]["gates"])
        self.assertEqual(by_folder["01剧本准备"]["input"], ())
        self.assertTrue(by_folder["05资产管理"]["docs"])

    def test_names_and_dirs_agree(self):
        for name in stage_layout.names():
            row = stage_layout.stage_dir(name)
            self.assertIsNotNone(row, name)
            self.assertEqual(row[0], name)
            self.assertEqual(stage_layout.paths(".", name)["output"].name, "output")
        self.assertEqual(stage_layout.dirname_of("video"), "10视频生成")
        self.assertEqual(stage_layout.dirname_of("assets"), "05资产管理", "一个阶段 id 取第一个目录")
        self.assertEqual(stage_layout.dirname_of("没有这个"), "")
        with self.assertRaises(ValueError):
            stage_layout.paths(".", "没有这个目录")

    def test_every_stage_has_a_chinese_name_and_a_docs_list(self):
        self.assertEqual(len(stage_layout.stage_names()), 13)
        self.assertTrue(all(stage_layout.stage_names()))
        folders = {row[0] for row in stage_layout.docs_rows()}
        for name in stage_layout.names():
            self.assertIn(name, folders, name + " 该有 docs 清单")

    def test_runtime_and_directory_stage_contracts_have_the_same_order(self):
        """运行时阶段和用户目录阶段不能各自扩容后悄悄漂移。"""
        self.assertEqual(stage_layout.stage_contract_errors(), ())
        self.assertTrue(stage_layout.validate_stage_contract())

    def test_dead_fields_and_skill_dedupe_are_populated(self):
        self.assertEqual(len(stage_layout.DEAD_FIELDS), 6)
        self.assertEqual(len(stage_layout.skill_rows()), 5)
        for old, owner, reason in stage_layout.DEAD_FIELDS:
            self.assertTrue(old and owner and reason)

    def test_json_md_rows_keep_machine_and_human_inputs_apart(self):
        rows = stage_layout.json_md_rows()
        self.assertTrue(rows)
        for json_side, md_side, _note in rows:
            self.assertTrue(json_side.strip(), "机器那一侧要有出处")
            self.assertTrue(md_side.endswith(".md"), md_side)
            self.assertNotEqual(json_side, md_side)
            folder, separator, relative = md_side.partition('/')
            self.assertIn(folder, stage_layout.names(), md_side)
            self.assertEqual(separator, '/', md_side)
            self.assertTrue(relative.startswith('docs/'), md_side)


class LegacyTests(unittest.TestCase):
    """老目录只做对照，一个都不搬、也不新建（legacy_map 是只读的）。"""

    def test_legacy_map_is_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            rows = stage_layout.legacy_map(td)
            self.assertEqual(len(rows), len(stage_layout.LEGACY))
            self.assertTrue(all(row[3] is False for row in rows), "临时目录里当然都不存在")
            self.assertFalse((Path(td) / "episode").exists(), "只读：不许顺手把老目录建出来")

    def test_a_legacy_folder_is_linked_into_its_stage(self):
        """第 64 期任务 3：老目录在阶段树里多一个同名入口，文件一个字节都不搬走。"""
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"
            (proj / "writing" / "创意_1").mkdir(parents=True)
            (proj / "writing" / "创意_1" / "创意与剧本.md").write_text("原稿", encoding="utf-8")
            (proj / "episode" / "frames").mkdir(parents=True)
            (proj / "episode" / "frames" / "SH001.png").write_text("图", encoding="utf-8")
            stage_layout.ensure(proj)
            result = stage_layout.adopt_legacy(proj)
            link = proj / "01剧本准备" / "writing"
            if link not in result["made"]:
                self.skipTest(PLATFORM_DIRECTORY_LINK)
            self.assertTrue(link.is_symlink() or link.is_junction(), "落脚点是一条约接")
            self.assertEqual((link / "创意_1" / "创意与剧本.md").read_text(encoding="utf-8"), "原稿",
                             "从阶段目录里照样读得到老目录那份文件")
            self.assertTrue((proj / "writing" / "创意_1").is_dir(), "老目录一个字节都没搬走")
            self.assertIn(proj / "08首帧管理" / "frames", result["made"])
            self.assertEqual(stage_layout.adopt_legacy(proj)["made"], [], "再归位一次什么都不做")

    def test_an_existing_stage_folder_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"
            (proj / "writing").mkdir(parents=True)
            stage_layout.ensure(proj)
            occupied = proj / "01剧本准备" / "writing"
            occupied.mkdir()
            (occupied / "我自己的.md").write_text("x", encoding="utf-8")
            result = stage_layout.adopt_legacy(proj)
            self.assertNotIn(occupied, result["made"])
            self.assertIn((occupied, "already"), result["skipped"])
            self.assertFalse(occupied.is_symlink(), "落脚点上本来就有东西，绝不改成链接")
            self.assertTrue((occupied / "我自己的.md").is_file())

    def test_a_dry_run_only_reports(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"
            (proj / "writing").mkdir(parents=True)
            stage_layout.ensure(proj)
            planned = stage_layout.adopt_legacy(proj, dry=True)
            self.assertIn(proj / "01剧本准备" / "writing", planned["made"])
            self.assertFalse((proj / "01剧本准备" / "writing").exists(), "试跑不落盘")

    def test_legacy_stage_name_resolves_to_current_directory(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(stage_layout.paths(td, "03_continuity")["root"],
                             Path(td) / "06连贯性清单")
            self.assertEqual(stage_layout.stage_dir("00_script")[0], "01剧本准备")

    def test_nothing_happens_without_a_legacy_folder(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"
            stage_layout.ensure(proj)
            result = stage_layout.adopt_legacy(proj)
            self.assertEqual(result, {"made": [], "skipped": []})

    def test_a_link_is_never_a_legacy_source(self):
        """老目录本身就是一条链接时不再接一条：接出来的链到链，删源就断。"""
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"
            proj.mkdir(parents=True)
            real = Path(td) / "真身"
            real.mkdir()
            if not stage_layout.link_dir(real, proj / "writing"):
                self.skipTest(PLATFORM_DIRECTORY_LINK)
            stage_layout.ensure(proj)
            self.assertEqual(stage_layout.adopt_legacy(proj)["made"], [])

    def test_shared_paths_are_under_shared(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(stage_layout.anchors_path(td).parent.name, "anchors")
            self.assertEqual(stage_layout.triplets_path(td).name, "triplets.json")
            self.assertEqual(stage_layout.schema_path(td, "shot").name, "shot.schema.json")


if __name__ == "__main__":
    unittest.main(verbosity=2)
