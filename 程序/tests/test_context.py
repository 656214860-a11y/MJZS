# -*- coding: utf-8 -*-
"""项目上下文快照与集成工具的独立测试。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROGRAM_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM_ROOT))

from workflow_context import snapshot, instruction, continuation_instruction, request_instruction
from agent.core import save as save_json
from stage_execution_service import project_context


def make_project(td):
    proj = Path(td) / "p"
    (proj / "writing").mkdir(parents=True)
    (proj / "storyboard" / "分镜拆分").mkdir(parents=True)
    (proj / "episode" / "assets" / "资产清单").mkdir(parents=True)
    (proj / "episode" / "assets.json").write_text(json.dumps({"CHAR_001": {"name": "卡梅隆"}}, ensure_ascii=False), encoding="utf-8")
    (proj / "episode" / "assets" / "资产清单" / "assets.json").write_text("{}", encoding="utf-8")
    shot = {"id": "SH001", "title": "镜头", "duration": 5, "characters": ["CHAR_001"], "location": "LOC_001", "frame": "frames/SH001.png", "video_prompt": "x", "dialogue": []}
    (proj / "episode" / "episode.json").write_text(json.dumps({"episode_id": "EP001", "title": "T", "shots": [shot]}, ensure_ascii=False), encoding="utf-8")
    (proj / "writing" / "第3集_剧本.md").write_text("剧本正文", encoding="utf-8")
    sb = {"episode_id": "EP001", "title": "T", "shots": [shot], "source_script": "writing/第3集_剧本.md"}
    (proj / "storyboard" / "分镜拆分" / "EP001_T_分镜.json").write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
    (proj / "config.json").write_text(json.dumps({"episode_dir": str(proj / "episode")}), encoding="utf-8")
    return proj


class SnapshotTests(unittest.TestCase):
    def test_snapshot_consumes_l3_context(self):
        with tempfile.TemporaryDirectory() as td:
            context = project_context(make_project(td))
            data = snapshot(context)
            self.assertEqual(data['next_episode_number'], 4)
            self.assertEqual(len(data['storyboards']), 1)

    def test_snapshot_rejects_uninjected_root(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(TypeError, 'ProjectContext'):
                snapshot(Path(td))

    def test_snapshot_counts(self):
        with tempfile.TemporaryDirectory() as td:
            data = snapshot(project_context(make_project(td)))
            self.assertEqual(len(data["scripts"]), 1)
            self.assertEqual(data["scripts"][0]["episode_number"], 3)
            self.assertEqual(len(data["storyboards"]), 1)
            self.assertEqual(data["next_episode_number"], 4)
            self.assertIn("CHAR_001", [a["id"] for a in data["assets"]])

    def test_snapshot_ignores_non_string_asset_keys(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            plan = proj / "episode" / "assets" / "资产清单" / "assets.json"
            plan.write_text(json.dumps({123: {"name": "数字键"}}, ensure_ascii=False), encoding="utf-8")
            self.assertIn("CHAR_001", [a["id"] for a in snapshot(project_context(proj))["assets"]])

    def test_snapshot_prefers_current_asset_stage(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            current = proj / "04资产管理" / "assets.json"
            current.parent.mkdir(parents=True)
            current.write_text(json.dumps({"CHAR_001": {"name": "当前资产"}}, ensure_ascii=False), encoding="utf-8")
            data = snapshot(project_context(proj))
            self.assertEqual(data["assets"][0]["name"], "当前资产")
            self.assertEqual(Path(data["asset_manifest"]), current)


class InstructionTests(unittest.TestCase):
    def test_l3_entry_points_can_build_snapshot_from_injected_context(self):
        from workflow_context_controller import request_stage_instruction, publish_writing_context
        with tempfile.TemporaryDirectory() as td:
            context = project_context(make_project(td))
            text, strategy = request_stage_instruction(context, 'storyboard')
            self.assertEqual(strategy, 'stage_summary')
            self.assertIn('已有剧本 1 份，分镜 1 份，独立资产 1 项', text)
            self.assertTrue((context.root / 'data' / '项目接续.json').is_file())
            self.assertIn('项目接续要求', publish_writing_context(context, 'writing'))
            self.assertIn('项目续接摘要', continuation_instruction(context, 'writing'))

    def test_instruction_maps_only_disk_failure_to_controlled_result(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            result = instruction(proj, 'writing', snapshot(project_context(proj)),
                                 publish=lambda _path, _data: (_ for _ in ()).throw(OSError('disk')))
            self.assertFalse(result.ok)
            self.assertIn('未能保存', result.reason)
            with self.assertRaises(TypeError):
                instruction(proj, 'writing', snapshot(project_context(proj)),
                            publish=lambda _path, _data: (_ for _ in ()).throw(TypeError('bug')))

    def test_instruction_writes_and_contains_stage(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            result = instruction(proj, "writing", snapshot(project_context(proj)), publish=lambda path, data: save_json(path, data))
            self.assertTrue(result.ok)
            text = result.data
            self.assertIn("当前阶段：writing", text)
            self.assertIn("项目进度文件", text)
            self.assertTrue((proj / "data" / "项目接续.json").is_file())

    def test_continuation_instruction_is_short_and_preserves_actionable_summary(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            data = snapshot(project_context(proj))
            full = instruction(proj, "writing", data, publish=lambda path, value: save_json(path, value)).data
            summary = continuation_instruction(proj, "writing", data)
            self.assertIn("项目续接摘要", summary)
            self.assertIn("当前阶段：writing", summary)
            self.assertIn("项目进度文件", summary)
            self.assertIn("已有剧本 1 份，分镜 1 份，独立资产 1 项", summary)
            self.assertLess(len(summary), len(full))

    def test_continuation_instruction_reports_read_errors_without_expanding_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            data = snapshot(project_context(make_project(td)))
            data['read_errors'] = [{'path': '坏.json', 'issue': '无法读取'}]
            summary = continuation_instruction(Path(td) / 'p', 'storyboard', data)
            self.assertIn('读取异常', summary)
            self.assertNotIn('坏.json', summary)

    def test_non_script_stage_uses_summary_policy_and_refreshes_progress_file(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            data = snapshot(project_context(proj))
            result = request_instruction(proj, 'storyboard', data, publish=lambda path, value: save_json(path, value))
            self.assertTrue(result.ok)
            text, strategy = result.data
            self.assertEqual(strategy, 'stage_summary')
            self.assertIn('项目续接摘要', text)
            self.assertIn('当前阶段：storyboard', text)
            self.assertTrue((proj / 'data' / '项目接续.json').is_file())
            self.assertLess(len(text), len(instruction(proj, 'storyboard', data, publish=lambda path, value: save_json(path, value)).data))

    def test_script_stage_retains_full_index_policy(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            result = request_instruction(proj, 'writing', snapshot(project_context(proj)), publish=lambda path, value: save_json(path, value))
            self.assertTrue(result.ok)
            text, strategy = result.data
            self.assertEqual(strategy, 'script_full_index')
            self.assertIn('项目接续要求', text)


class ScriptTextTests(unittest.TestCase):
    def test_md_utf8(self):
        from integrations import script_text
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "剧本.md"; p.write_text("正文内容", encoding="utf-8")
            self.assertEqual(script_text(p), "正文内容")

    def test_unsupported_suffix_rejected(self):
        from integrations import script_text
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.bin"; p.write_bytes(b"x")
            with self.assertRaises(ValueError): script_text(p)

    def test_utf16_bom_decoded(self):
        from integrations import script_text
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "剧本.md"; p.write_bytes("正文内容".encode("utf-16"))
            self.assertEqual(script_text(p), "正文内容")

    def test_gb18030_decoded(self):
        from integrations import script_text
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "剧本.txt"; p.write_bytes("正文内容".encode("gb18030"))
            self.assertEqual(script_text(p), "正文内容")

    def test_unknown_encoding_clear_error(self):
        from integrations import script_text
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "剧本.md"; p.write_bytes(b"\x81")
            with self.assertRaises(ValueError): script_text(p)

    def test_corrupt_docx_clear_error(self):
        from integrations import script_text
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "剧本.docx"; p.write_bytes(b"not a zip")
            with self.assertRaises(ValueError): script_text(p)


class SkillFileTests(unittest.TestCase):
    def test_skill_file_found(self):
        from integrations import skill_file
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            (home / "short-drama-storyboard").mkdir(parents=True)
            (home / "short-drama-storyboard" / "SKILL.md").write_text("", encoding="utf-8")
            self.assertTrue(skill_file("drama-skills", skill_home=home).is_file())

    def test_skill_file_missing(self):
        from integrations import skill_file
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError): skill_file("drama-skills", skill_home=Path(td))


class ToolPathTests(unittest.TestCase):
    def test_lookup_cached_per_tool(self):
        import integrations
        from unittest.mock import patch
        integrations._TOOL_CACHE.clear(); self.addCleanup(integrations._TOOL_CACHE.clear)
        with patch("shutil.which", return_value=r"X:/tools/ffmpeg.exe") as which:
            self.assertEqual(integrations.tool_path("ffmpeg", "fallback"), r"X:/tools/ffmpeg.exe")
            integrations.tool_path("ffmpeg", "fallback"); integrations.tool_path("ffprobe", "fallback")
            self.assertEqual(which.call_count, 2)

    def test_fallback_used_when_missing(self):
        import integrations
        from unittest.mock import patch
        integrations._TOOL_CACHE.clear(); self.addCleanup(integrations._TOOL_CACHE.clear)
        with patch("shutil.which", return_value=None):
            self.assertEqual(integrations.tool_path("ffmpeg", "D:/Tools/ffmpeg.exe"), "D:/Tools/ffmpeg.exe")
            self.assertIsNone(integrations.tool_path("ffprobe"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
