# -*- coding: utf-8 -*-
"""资产 JSON 契约（第 61 期 v0.8 任务 3／5／8）的自检。运行：python test_asset_contract.py

盯住四件事：① 老资产 JSON 少新增键照旧读得出来（normalize 只补不改）；② 状态变体按 CST-## 校验、
生成时「基础锚点＋状态覆盖」合并；③ 正典板 7 格（上排全身 4 ＋ 下排头部 3）与转盘图下面那三行；
④ 交付物 5 那份资产 Schema 里这些字段都在。
"""
import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import asset_contract as ac
import script_contract


def character(**extra):
    asset = {"name": "林小满", "character_anchor": "黑短发、杏眼、米色针织衫"}
    asset.update(extra)
    return asset


class DefaultsTests(unittest.TestCase):
    def test_kind_of_reads_the_prefix(self):
        self.assertEqual(ac.kind_of("CHAR_001"), "character")
        self.assertEqual(ac.kind_of("LOC_001"), "scene")
        self.assertEqual(ac.kind_of("PROP_001"), "prop")
        self.assertEqual(ac.kind_of("SH001"), "")

    def test_every_kind_has_defaults(self):
        for kind in ac.KINDS:
            self.assertTrue(ac.defaults(kind), kind)
        self.assertIn("state_variants", ac.defaults("character"))
        self.assertEqual(ac.defaults("scene")["aspect_ratio"], "16:9")
        self.assertEqual(ac.defaults("scene")["resolution"], "1920x1080")
        self.assertIn("holder", ac.defaults("prop"))
        self.assertEqual(ac.defaults("没有这一类"), {})

    def test_normalize_fills_missing_keys_without_touching_the_rest(self):
        old = {"name": "老角色", "image_prompt": "写好的提示词"}
        data = ac.normalize(old, "CHAR_001")
        self.assertEqual(data["name"], "老角色", "老键一个都不动")
        self.assertEqual(data["image_prompt"], "写好的提示词")
        self.assertEqual(data["character_id"], "CHAR_001")
        self.assertEqual(data["character_anchor"], "")
        self.assertEqual(data["state_variants"], [])
        self.assertFalse(data["locked"])
        self.assertEqual(data["reference_role"], ac.DEFAULT_RESPONSIBILITY)
        self.assertNotIn("character_anchor", old, "不就地改原对象")

    def test_normalize_keeps_existing_values(self):
        data = ac.normalize(character(locked=True, canonical_board="a/turnaround.png"), "CHAR_001")
        self.assertTrue(data["locked"])
        self.assertEqual(data["canonical_board"], "a/turnaround.png")

    def test_character_features_are_fielded_too(self):
        """第 70 期任务 6：角色资产的物理特征同样走五件字段化（整句自然语言要拆开）。"""
        self.assertEqual(sorted(ac.defaults("character")["physical_features"]),
                         sorted(script_contract.PHYSICAL_KEYS))
        data = ac.normalize({"name": "林小满", "physical_features": "肤色冷白，黑色短发，杏眼"},
                            "CHAR_001")
        self.assertEqual(data["physical_features"]["skin_tone"], "肤色冷白")
        self.assertEqual(data["physical_features"]["hair"], "黑色短发")
        self.assertEqual(data["physical_features"]["eyes"], "杏眼")
        self.assertEqual(data["physical_features"]["body_type"], "")
        self.assertEqual(data["name"], "林小满", "别的键一个都不动")

    def test_normalize_leaves_unknown_kind_alone(self):
        self.assertEqual(ac.normalize({"name": "x"}, "SH001"), {"name": "x"})


class VariantTests(unittest.TestCase):
    def test_variant_ids_are_generated_in_order(self):
        data = ac.normalize(character(state_variants=[{"name": "日常装", "override": "米色针织衫"},
                                                      {"name": "战损", "override": "衣服破损"}]), "CHAR_001")
        ids = [item["state_id"] for item in data["state_variants"]]
        self.assertEqual(ids, ["CST-01", "CST-02"])
        self.assertTrue(all(item["reference_image"] == "" for item in data["state_variants"]))

    def test_variant_keeps_a_given_id_and_drops_junk(self):
        data = ac.normalize(character(state_variants=[{"state_id": "CST-09", "name": "雨衣",
                                                       "override": "黄色雨衣"}, "不是对象"]), "CHAR_001")
        self.assertEqual([item["state_id"] for item in data["state_variants"]], ["CST-09"])

    def test_variant_lookup_and_merged_anchor(self):
        asset = character(state_variants=[{"state_id": "CST-01", "name": "日常装",
                                           "override": "米色针织衫"}])
        self.assertEqual(ac.variant(asset, "CST-01")["name"], "日常装")
        self.assertIsNone(ac.variant(asset, "CST-88"))
        self.assertIsNone(ac.variant(asset, ""))
        merged = ac.merged_anchor(asset, "CST-01")
        self.assertIn("黑短发", merged)
        self.assertIn("米色针织衫", merged)
        self.assertEqual(ac.merged_anchor(asset, "CST-88"), asset["character_anchor"])
        self.assertEqual(ac.merged_anchor({}, ""), "")

    def test_character_anchor_wins_over_base_anchor(self):
        asset = {"character_anchor": "定稿锚点", "base_anchor": "草稿锚点"}
        self.assertEqual(ac.merged_anchor(asset, ""), "定稿锚点")
        self.assertEqual(ac.merged_anchor({"base_anchor": "只有基础锚点"}, ""), "只有基础锚点")


class CanonBoardTests(unittest.TestCase):
    def test_cells_are_seven_two_rows(self):
        cells = ac.cells(character())
        self.assertEqual(len(cells), 7)
        self.assertEqual([cell["row"] for cell in cells], [0, 0, 0, 0, 1, 1, 1])
        self.assertTrue(all(cell["shape"] == "全身" for cell in cells[:4]))
        self.assertTrue(all(cell["shape"] == "头部" for cell in cells[4:]))
        self.assertFalse(any(cell["ready"] for cell in cells), "没图就是没图")

    def test_view_image_falls_back_to_the_single_board(self):
        asset = character(canonical_board="a/turnaround.png")
        self.assertEqual(ac.view_image(asset, "front"), "a/turnaround.png")
        self.assertEqual(ac.view_image(asset, "back"), "")
        asset["canon_board_views"] = {"front": "a/f.png", "back": "a/b.png"}
        self.assertEqual(ac.view_image(asset, "front"), "a/f.png")
        self.assertEqual(ac.view_image(asset, "back"), "a/b.png")
        cells = ac.cells(asset)
        self.assertEqual(len([cell for cell in cells if cell["ready"]]), 2)

    def test_card_lines_show_anchor_role_and_lock(self):
        lines = ac.card_lines(character(locked=True))
        self.assertEqual(len(lines), 4)
        self.assertTrue(lines[0][0].startswith("锚点字符串"))
        self.assertIn("黑短发", lines[0][1])
        self.assertEqual(lines[1][0], "正典板")
        self.assertIn(ac.DEFAULT_RESPONSIBILITY, lines[2][1])
        self.assertIn(ac.DEFAULT_EXCLUDE, lines[2][1])
        self.assertIn("已锁定", lines[3][1])
        self.assertIn("未锁定", ac.lock_label({}))
        self.assertIn("还没定稿", ac.card_lines({})[0][1])

    def test_a_board_holding_a_scheme_sentence_is_not_mistaken_for_an_image(self):
        """正典板字段也记「4 选 1」的那句方案文字，认不出图片后缀就不当成图（第 64 期任务 13）。"""
        self.assertTrue(ac.looks_like_image("assets/正典板/CHAR_001_front.png"))
        self.assertTrue(ac.looks_like_image("A.JPEG"))
        self.assertFalse(ac.looks_like_image(""))
        self.assertFalse(ac.looks_like_image("方案一：写实骨相＋冷调布光"))
        self.assertEqual(ac.view_image(character(canonical_board="方案一：写实骨相＋冷调布光"), "front"), "")
        self.assertEqual(ac.view_image(character(canonical_board="a/turnaround.png"), "front"),
                         "a/turnaround.png")


class ValidateTests(unittest.TestCase):
    def test_a_complete_character_passes(self):
        asset = character(locked=True, canonical_board="a/turnaround.png",
                          state_variants=[{"state_id": "CST-01", "name": "日常装", "override": "米色针织衫"}])
        self.assertEqual(ac.validate(asset, "CHAR_001"), [])

    def test_locking_without_an_anchor_is_rejected(self):
        problems = ac.validate({"name": "角色", "locked": True}, "CHAR_001")
        self.assertTrue(any("character_anchor" in text for text in problems))

    def test_a_natural_language_feature_line_is_rejected(self):
        problems = ac.validate(character(physical_features="黑短发、杏眼"), "CHAR_001")
        self.assertTrue(any("字段化" in text for text in problems))

    def test_unknown_view_and_bad_variant_ids_are_rejected(self):
        asset = character(canon_board_views={"侧脸": "a/side.png"},
                          state_variants=[{"state_id": "CST-1", "name": "A", "override": "x"},
                                          {"state_id": "CST-1", "name": "B", "override": "y"}])
        problems = ac.validate(asset, "CHAR_001")
        self.assertTrue(any("视角名" in text for text in problems))
        self.assertTrue(any("格式" in text for text in problems))
        self.assertTrue(any("重复" in text for text in problems))

    def test_a_variant_without_override_is_rejected(self):
        problems = ac.validate(character(state_variants=[{"state_id": "CST-01", "name": "空"}]), "CHAR_001")
        self.assertTrue(any("override" in text for text in problems))

    def test_a_malformed_board_field_is_rejected(self):
        problems = ac.validate({"name": "角色", "canon_board_views": "不是对象"}, "CHAR_001")
        self.assertTrue(any("canonical_board" in text for text in problems))

    def test_scene_fields_are_checked(self):
        good = {"name": "咖啡馆", "lighting_direction": "右侧窗自然光",
                "spatial_anchors": [{"object": "壁灯", "position": "左侧墙面 1.5 米"}]}
        self.assertEqual(ac.validate(good, "LOC_001"), [])
        bad = {"name": "咖啡馆", "aspect_ratio": "宽屏", "resolution": "高清",
               "spatial_anchors": [{"object": "壁灯"}]}
        problems = ac.validate(bad, "LOC_001")
        self.assertTrue(any("aspect_ratio" in text for text in problems))
        self.assertTrue(any("resolution" in text for text in problems))
        self.assertTrue(any("空间锚点" in text for text in problems))
        problems = ac.validate({"name": "咖啡馆", "spatial_anchors": "不是数组"}, "LOC_001")
        self.assertTrue(any("数组" in text for text in problems))

    def test_prop_holder_must_be_a_character_id(self):
        self.assertEqual(ac.validate({"name": "怀表", "holder": "CHAR_001"}, "PROP_001"), [])
        self.assertEqual(ac.validate({"name": "怀表", "holder": ""}, "PROP_001"), [])
        problems = ac.validate({"name": "怀表", "holder": "林小满"}, "PROP_001")
        self.assertTrue(any("holder" in text for text in problems))


class MissingAndSchemaTests(unittest.TestCase):
    def test_missing_ids_reports_unknown_and_promptless_assets(self):
        assets = {"CHAR_001": {"name": "主角", "image_prompt": "提示词"}}
        shots = [{"characters": ["CHAR_001"], "location": "LOC_001"},
                 {"characters": ["CHAR_002"], "location": ""}]
        problems = ac.missing_ids(shots, {"CHAR_001": {"name": "主角", "image_prompt": ""},
                                          "CHAR_002": {"name": "配角"}})
        self.assertTrue(any("CHAR_001" in text for text in problems))
        self.assertTrue(any("CHAR_002" in text for text in problems))
        self.assertEqual(ac.missing_ids([{"characters": ["CHAR_001"], "location": "LOC_001"}], assets),
                         ["LOC_001：资产清单里没有这一项"])

    def test_schema_carries_the_new_fields(self):
        schema = ac.schema()
        boxes = schema["patternProperties"]
        character = boxes["^CHAR_[0-9]{3,}$"]["properties"]
        for key in ("canonical_board", "canon_board_views", "character_anchor", "base_anchor",
                    "state_variants", "locked", "reference_role"):
            self.assertIn(key, character, key)
        scene = boxes["^LOC_[0-9]{3,}$"]["properties"]
        for key in ("aspect_ratio", "resolution", "spatial_anchors", "lighting_direction",
                    "scale_reference"):
            self.assertIn(key, scene, key)
        prop = boxes["^PROP_[0-9]{3,}$"]["properties"]
        for key in ("scale", "material", "holder"):
            self.assertIn(key, prop, key)
        variant = character["state_variants"]["items"]
        self.assertEqual(variant["required"], ["state_id", "name", "override", "reference_image"])

    def test_the_component_map_names_both_new_foldouts(self):
        text = ac.panel_text()
        self.assertIn("资产详情页", text)
        self.assertIn("连贯性清单", text)
        self.assertIn("参考职责声明", text)
        for label in ("正面 0°", "右侧 90°", "左侧 -90°", "背面 180°",
                      "3/4 左", "3/4 右"):
            self.assertIn(label, text)
        self.assertIn("锚点字符串", text)
        self.assertIn("状态变体", text)

    def test_the_responsibility_defaults_are_written_down_once(self):
        self.assertEqual(ac.DEFAULT_RESPONSIBILITY, "面部、发型、服装")
        self.assertEqual(ac.DEFAULT_EXCLUDE, "场景、动作、镜头")
        self.assertEqual(ac.STATE_PREFIX, "CST-")


if __name__ == "__main__":
    unittest.main(verbosity=2)