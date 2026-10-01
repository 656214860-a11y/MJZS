# -*- coding: utf-8 -*-
"""提示词生成规则的自检。"""
import unittest

import asset_prompt_rules
import prompt_templates as pt
import storyboard_contract

CHARACTER = {"name": "林小满", "character_anchor": "黑短发、杏眼、米色针织衫",
             "state_variants": [{"state_id": "CST-01", "name": "日常装",
                                 "override": "米色针织衫"}]}
SCENE = {"name": "咖啡馆", "lighting_direction": "右侧落地窗自然光 5600K",
         "spatial_anchors": [{"object": "壁灯", "position": "左侧墙面 1.5 米处"}],
         "scale_reference": "吧台高约 1.1 米"}


class ImagePromptTests(unittest.TestCase):
    def test_anchor_scene_and_composition_are_all_there(self):
        text = pt.image_prompt(CHARACTER, SCENE, "中景、平视")
        self.assertIn("黑短发、杏眼、米色针织衫", text)
        self.assertIn("咖啡馆", text)
        self.assertIn("右侧落地窗自然光", text)
        self.assertIn("壁灯@左侧墙面 1.5 米处", text)
        self.assertIn("中景、平视", text)

    def test_the_anchor_is_copied_verbatim(self):
        text = pt.image_prompt(CHARACTER, SCENE)
        self.assertIn(CHARACTER["character_anchor"], text, "整句原样出现，不重写")

    def test_missing_pieces_leave_a_todo_instead_of_inventing(self):
        text = pt.image_prompt({}, None)
        self.assertIn(pt.ANCHOR_TODO, text)
        self.assertIn(pt.SCENE_TODO, text)
        self.assertIn(pt.DEFAULT_COMPOSITION, text)

    def test_the_state_override_is_folded_in(self):
        text = pt.image_prompt(CHARACTER, SCENE, costume_id="CST-01")
        self.assertIn("状态覆盖", text)

    def test_scene_line_skips_empty_fields(self):
        self.assertEqual(pt.scene_line({"name": "空场景"}), "空场景")
        self.assertEqual(pt.scene_line(None), "")
        self.assertEqual(pt.scene_line({"name": "屋子", "spatial_anchors": [{"object": "门"}]}),
                         "屋子；门")


class VideoPromptTests(unittest.TestCase):
    def test_only_motion_is_written(self):
        text = pt.video_prompt("角色推门", "轻微推进", "门把手转动")
        self.assertEqual(text, "动作：角色推门；运镜：轻微推进；物理交互：门把手转动")

    def test_empty_parts_disappear(self):
        self.assertEqual(pt.video_prompt("角色回头"), "动作：角色回头")
        self.assertEqual(pt.video_prompt(), "")
        self.assertEqual(pt.video_prompt(action="", camera=pt.DEFAULT_CAMERA),
                         "运镜：" + pt.DEFAULT_CAMERA)

    def test_appearance_is_stripped_back_out(self):
        text = "动作：推门；" + CHARACTER["character_anchor"]
        self.assertNotIn("黑短发", pt.strip_appearance(text, CHARACTER))
        self.assertEqual(pt.strip_appearance("动作：推门", {}), "动作：推门")


class RoleTests(unittest.TestCase):
    def test_the_default_sentence(self):
        self.assertEqual(pt.role_line("@图片1"),
                         "@图片1只负责面部、发型、服装，不继承其中的场景、动作、镜头")

    def test_explicit_responsibility_wins(self):
        self.assertEqual(pt.role_line("@图片2", "场景", "人物"),
                         "@图片2只负责场景，不继承其中的人物")

    def test_role_lines_follow_the_refs(self):
        shot = {"character_refs": ["@图片1", "@图片2"],
                "reference_roles": {"@图片2": {"responsibility": "光影", "exclude": "人脸"}}}
        rows = pt.role_lines(shot)
        self.assertEqual([label for label, _text in rows], ["@图片1", "@图片2"])
        self.assertIn("只负责光影", rows[1][1])
        self.assertEqual(pt.role_lines({}), ())


class TemplateTests(unittest.TestCase):
    def test_the_three_templates(self):
        self.assertIn("{anchor}", pt.image_template())
        self.assertIn("{action}", pt.video_template())
        self.assertIn("只负责", pt.role_template())
        rows = pt.rows()
        self.assertEqual([row[0] for row in rows],
                         ["图片提示词", "视频提示词", "参考图职责声明"])

    def test_the_rules_are_inserted_into_the_live_contracts(self):
        self.assertIn("锚点", pt.common_lines()[0])
        for line in pt.common_lines():
            self.assertIn(line, asset_prompt_rules.COMMON, "资产规范里要有这一句")
        for line in pt.contract_lines():
            self.assertIn(line, storyboard_contract.rules(), "分镜契约里要有这一句")
        self.assertIn("逐字复制", asset_prompt_rules.COMMON)
        self.assertIn("视频提示词只写动作", storyboard_contract.rules())

    def test_the_inserted_rules_do_not_break_the_old_ones(self):
        self.assertIn("结构化资产JSON格式规范", asset_prompt_rules.COMMON)
        self.assertIn("【制作 JSON 必须通过助手校验】", storyboard_contract.rules())
        self.assertIn("validate_episode", storyboard_contract.rules())

    def test_both_stages_still_work(self):
        for stage in ("writing", "storyboard"):
            text = asset_prompt_rules.rules(stage)
            self.assertIn("逐字复制", text, stage)
        with self.assertRaises(ValueError):
            asset_prompt_rules.rules("没有这个阶段")


if __name__ == "__main__":
    unittest.main(verbosity=2)
