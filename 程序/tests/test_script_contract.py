# -*- coding: utf-8 -*-
"""剧本阶段产出契约（第 70 期任务 5／6／7）的自检。运行：python test_script_contract.py

盯住五件事：① 五类 manifest 都声明了、产出者对得上真注册表；② 物理特征整句自然语言要拆成五件，
拆不出去的片段不丢；③ ID 唯一性——重复的报得出来、重发的号不撞；④ 校验规则（编号格式、强度、场号、
角色编号）；⑤ Schema 覆盖五类、示例过得去自己的校验，完整性检查认得缺哪一份。
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, HERE)
os.chdir(HERE)

import script_contract as sc


class NaturalScriptSaveTests(unittest.TestCase):
    def test_save_is_atomic_and_normalizes_final_newline(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / '自然剧本.md'
            self.assertEqual(sc.save_natural_script(target, '阿远：我回来了'), target)
            self.assertEqual(target.read_text(encoding='utf-8'), '阿远：我回来了\n')

    def test_save_rejects_structured_content_and_non_markdown_target(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / '自然剧本.md'
            with self.assertRaisesRegex(ValueError, '结构化内容'):
                sc.save_natural_script(target, '# 结构化剧本\n## 分场剧本')
            with self.assertRaisesRegex(ValueError, 'Markdown'):
                sc.save_natural_script(target.with_suffix('.txt'), '自然剧本')

    def test_beat_table_is_not_a_forbidden_field_table(self):
        """REQ-S01-16：自然剧本每集正文前必带本集节拍表，节拍表是合法字段表格，不能误伤。

        「字段表格」拦截只针对分镜表／镜头表等结构化阶段产物；节拍表以
        ``场次／节拍＃／情绪关键词／服务的剧本动作／权重／强度`` 六列为准，
        是剧本准备阶段的正式交付，必须放行。
        """
        beat_table = (
            '# 第1集：咔咔的超能力\n'
            '## 本集节拍表\n'
            '| 场次 | 节拍＃ | 情绪关键词 | 服务的剧本动作 | 权重 | 强度 |\n'
            '|---|---|---|---|---|---|\n'
            '| 场景 1 | 1 | 心算十楼两秒 | 咔咔抬头从一楼看到十楼，心算时间 | 主 | 5.0 |\n'
            '| 场景 1 | 2 | 仰头喊跳 | 咔咔双手拢在嘴边仰头大喊「跳！」 | 峰值 | 6.0 |\n'
            '\n'
            '## 正文\n\n咔咔骑电动车冲进画面，一脚急刹。\n'
        )
        self.assertEqual(sc.natural_script_violations(beat_table), ())
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / '自然剧本.md'
            sc.save_natural_script(target, beat_table)

    def test_foreign_pipe_table_is_still_rejected(self):
        """节拍表豁免不得放大到其它字段表格：分镜表／镜头表仍是结构化阶段产物。"""
        self.assertIn('字段表格', sc.natural_script_violations(
            '# 自然剧本\n## 正文\n| 镜头编号 | 景别 | 画面内容 |\n|---|---|---|\n| 1 | 特写 | 咔咔 |\n'))

    def test_beat_table_with_blank_separated_rows_is_still_natural(self):
        """桌面工具落盘的 ``\\r\\r\\n`` 双重回车在 ``splitlines`` 下变成行间伪空行，
        节拍表整块豁免必须跨过空行，但不能放行空行之后的异列字段表格。"""
        header = '| 场次 | 节拍＃ | 情绪关键词 | 服务的剧本动作 | 权重 | 强度 |'
        separator = '|---|---|---|---|---|---|'
        row = '| 场景 1 | 1 | 心算十楼两秒 | 咔咔抬头心算时间 | 主 | 5.0 |'
        # 与真实文件一致：每行以 \r\r\n 结尾，read_text 通用换行后是行间空行。
        text = '# 第1集\r\r\n## 本集节拍表\r\r\n' + '\r\r\n'.join(
            (header, separator, row)) + '\r\r\n\r\r\n## 正文\r\r\n\r\r\n咔咔急刹。\r\r\n'
        self.assertEqual(sc.natural_script_violations(text), ())
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / '01剧本准备' / '自然剧本.md'
            target.parent.mkdir(parents=True)
            target.write_bytes(text.encode('utf-8'))
            self.assertIn(target.resolve(),
                          {Path(p).resolve() for p in sc.natural_script_paths(folder)})
            # 伪空行豁免以节拍表六列为界；空行之后接异列字段表格仍拦截。
            self.assertIn('字段表格', sc.natural_script_violations(
                text + '| 镜头编号 | 景别 | 画面内容 |\r\r\n'))


class StructuredScriptPublicationTests(unittest.TestCase):
    def test_empty_explicit_structured_content_is_not_published(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / '01剧本准备' / '原稿.md'
            source.parent.mkdir(parents=True)
            source.write_text('阿远：我回来了', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '正文不能为空'):
                sc.write_structured_script(root, content=' \n', source=source)
            self.assertFalse(sc.canonical_structured_script_path(root).exists())


def character(**extra):
    item = {"name": "林小满", "physical_features": "肤色冷白，黑色短发，杏眼，左眉一道浅疤，身形修长"}
    item.update(extra)
    return item


class AuditTests(unittest.TestCase):
    """任务 1～4：审计表从真注册表读，剧本阶段的 SKILL 一个都不落。"""

    def test_the_five_manifests_and_their_producers(self):
        self.assertEqual(len(sc.MANIFESTS), 5)
        self.assertEqual(sorted(sc.KINDS), sorted(sc.KIND_OF_MANIFEST.values()))
        for name in sc.MANIFESTS:
            self.assertIn(name, sc.PRODUCERS, name)
        self.assertEqual(sc.PRODUCERS["character_manifest.json"][0], "script-character-extraction")
        self.assertEqual(sc.PRODUCERS["scene_breakdown.json"][0], "storyboard-scene-breakdown",
                         "场次拆分那个 SKILL 归在初步分镜，别归错")

    def test_brief_contract_requires_only_the_declared_mandatory_fields(self):
        brief = sc.brief_document({'story_summary': '故事', 'main_characters': '角色',
                                   'genre': '悬疑', 'length': '12集'})
        self.assertEqual(brief['contract'], 'script_brief')
        self.assertEqual(brief['recommended_missing'], ['physical_features', 'production_locks'])
        with self.assertRaisesRegex(ValueError, '题材类型'):
            sc.brief_document({'story_summary': '故事', 'main_characters': '角色', 'length': '12集'})

    def test_brief_requirement_levels_and_coordinator_defined_locks(self):
        source = {'story_summary': '故事', 'main_characters': '角色', 'genre': '悬疑', 'length': '12集',
                  'production_locks': {'world_period': '民国', 'cast_limit': 8}}
        brief = sc.normalize_brief(source)
        self.assertEqual(brief['production_locks'], source['production_locks'])
        self.assertEqual(sc.missing_brief_fields(brief), ())
        self.assertEqual(sc.missing_brief_fields(brief, include_recommended=True),
                         ('physical_features',))
        self.assertEqual(sc.missing_brief_fields(brief, include_recommended=True,
                                                 include_optional=True),
                         ('physical_features', 'special_requirements'))

    def test_workflow_lock_projection_keeps_each_coordinator_namespace(self):
        projection = sc.normalize_workflow_projection({'workflow': {
            'name': '短剧统筹', 'skill_ref': 'short-drama-coordinator',
            'lock': {'旧统筹': {'ratio': '16:9'}, '短剧统筹': {'episode_count': 12}},
        }})
        self.assertEqual(projection['workflow']['lock']['旧统筹'], {'ratio': '16:9'})
        self.assertEqual(projection['workflow']['lock']['短剧统筹'], {'episode_count': 12})

    def test_every_producer_skill_exists_in_the_registry(self):
        from skill_registry import default_registry
        registry = default_registry(HERE)
        for skill, _folder in sc.PRODUCERS.values():
            self.assertIsNotNone(registry.getById(skill), skill)

    def test_the_stage_layout_prints_the_five_outputs(self):
        import stage_layout
        for name in sc.MANIFESTS:
            folder = sc.PRODUCERS[name][1]
            self.assertIn(name, stage_layout.stage_dir(folder)[5], name)
        outputs = stage_layout.stage_dir("00_script")[5]
        self.assertEqual([n for n in sc.MANIFESTS if n in outputs], ["emotion_curve.json"],
                         "REQ-S02-25：旧名 00_script 只剩别名，不再堆放全部 manifest")
        self.assertIn("episode.json", outputs, "老的三份一个都不动")

    def test_the_audit_covers_every_script_skill(self):
        rows = sc.manifest_rows(HERE)
        self.assertEqual([row["skill"] for row in rows],
                         ["screenplay-production-line", "screenplay-writer",
                          "script-character-extraction", "script-dialogue-polish",
                          "script-forging", "script-structured-generation",
                          "script-worldbuilding", "短剧编剧搭子", "编剧技能集"])
        self.assertEqual(sc.unlisted_skills(HERE), (), "剧本阶段的 SKILL 都要有审计行")

    def test_every_row_has_a_legal_category_and_action(self):
        for row in sc.audit_rows(HERE):
            self.assertIn(row["category"], sc.CATEGORIES, row["skill"])
            self.assertEqual(row["action"], sc.CATEGORIES[row["category"]])
            self.assertTrue(row["reason"], row["skill"])
            self.assertTrue(row["path"].startswith("skills/"), row["path"])
            self.assertTrue(row["display"], row["skill"])

    def test_the_categories_are_the_four_the_attachment_asked_for(self):
        self.assertEqual(sorted(sc.CATEGORIES),
                         sorted(["核心", "支撑", "重叠", "冗余"]))
        by_skill = dict((row["skill"], row["category"]) for row in sc.audit_rows(HERE))
        for skill in ("script-structured-generation", "script-character-extraction"):
            self.assertEqual(by_skill[skill], "核心", skill)
        self.assertEqual(by_skill["script-dialogue-polish"], "重叠")
        self.assertEqual(by_skill["script-worldbuilding"], "支撑")
        for skill in ("screenplay-production-line", "screenplay-writer", "短剧编剧搭子"):
            self.assertEqual(by_skill[skill], "支撑", skill)


class FeatureTests(unittest.TestCase):
    """任务 6：physical_features 必须字段化。"""

    def test_a_sentence_is_split_into_the_five_fields(self):
        features = sc.split_features("肤色冷白，黑色短发，杏眼，左眉一道浅疤，身形修长")
        self.assertEqual(features["skin_tone"], "肤色冷白")
        self.assertEqual(features["hair"], "黑色短发")
        self.assertEqual(features["eyes"], "杏眼")
        self.assertEqual(features["distinctive_marks"], "左眉一道浅疤")
        self.assertEqual(features["body_type"], "身形修长")
        self.assertEqual(features.get("raw", ""), "", "五件都认出来了，不该留 raw")

    def test_the_longer_word_wins(self):
        """「短发」比「发」长，黑短发进 hair，不会被别的键抢走。"""
        self.assertEqual(sc.split_features("银发")["hair"], "银发")
        self.assertEqual(sc.split_features("古铜色皮肤")["skin_tone"], "古铜色皮肤")

    def test_two_pieces_of_one_field_are_joined(self):
        self.assertEqual(sc.split_features("黑色短发、银色发梢")["hair"], "黑色短发、银色发梢")

    def test_what_cannot_be_classified_is_kept_in_raw(self):
        features = sc.split_features("黑色短发，笑起来有小虎牙")
        self.assertEqual(features["hair"], "黑色短发")
        self.assertEqual(features.get("raw"), "笑起来有小虎牙", "认不出来的不丢")

    def test_a_dict_gets_all_five_keys(self):
        features = sc.field_features({"hair": "银发"})
        self.assertEqual(sorted(features), sorted(sc.PHYSICAL_KEYS))
        self.assertEqual(features["hair"], "银发")

    def test_a_sentence_stuffed_into_one_key_is_split(self):
        features = sc.field_features({"description": "备注", "hair": "黑色短发，杏眼"})
        self.assertEqual(features["hair"], "黑色短发")
        self.assertEqual(features["eyes"], "杏眼")
        self.assertEqual(features["description"], "备注", "别的键一个都不动")

    def test_an_empty_value_gives_five_empty_strings(self):
        blank = dict((key, "") for key in sc.PHYSICAL_KEYS)
        self.assertEqual(sc.field_features(""), blank)
        self.assertEqual(sc.field_features(None), blank)
        self.assertEqual(sc.field_features({}), blank)

    def test_normalize_fields_the_features_of_a_character(self):
        data = sc.normalize("character", character())
        self.assertEqual(data["physical_features"]["eyes"], "杏眼")
        self.assertEqual(data["character_id"], "CHAR_001")


class IdTests(unittest.TestCase):
    """任务 7：ID 唯一性。"""

    def test_a_manifest_mints_ids_in_order(self):
        data = sc.manifest("character", [{"name": "A"}, {"name": "B"}])
        self.assertEqual([item["character_id"] for item in data["items"]],
                         ["CHAR_001", "CHAR_002"])
        self.assertEqual(data["manifest"], "character_manifest.json")
        self.assertEqual(data["kind"], "character")

    def test_kind_of_id_reads_the_prefix(self):
        self.assertEqual(sc.kind_of_id("LOC_012"), "scene")
        self.assertEqual(sc.kind_of_id("EC_002"), "emotion_curve")
        self.assertEqual(sc.kind_of_id("SH001"), "")

    def test_duplicates_are_reported_within_and_across_manifests(self):
        data = {"character_manifest.json": sc.manifest("character", [
                    {"name": "A", "character_id": "CHAR_001"},
                    {"name": "B", "character_id": "CHAR_001"}]),
                "scene_manifest.json": [{"scene_id": "CHAR_001", "name": "C"}, {"name": "D"}]}
        problems = sc.duplicate_ids(data)
        self.assertTrue(any("撞号" in text for text in problems), problems)
        self.assertTrue(any("还没有编号" in text for text in problems), problems)
        self.assertFalse(sc.unique_ids(data))

    def test_a_clean_set_is_unique(self):
        data = {"character_manifest.json": sc.manifest("character", [{"name": "A"}]),
                "prop_manifest.json": sc.manifest("prop", [{"name": "怀表"}])}
        self.assertEqual(sc.duplicate_ids(data), [])
        self.assertTrue(sc.unique_ids(data))

    def test_reassign_keeps_the_first_and_renumbers_the_rest(self):
        data = {"character_manifest.json": sc.manifest("character", [
                    {"name": "A", "character_id": "CHAR_001"},
                    {"name": "B", "character_id": "CHAR_001"},
                    {"name": "C", "character_id": "CHAR_002"}]),
                "scene_manifest.json": [{"scene_id": "CHAR_002", "name": "D"}]}
        fixed, changes = sc.reassign_ids(data)
        self.assertEqual([item["character_id"] for item in fixed["character_manifest.json"]["items"]],
                         ["CHAR_001", "CHAR_002", "CHAR_003"], "先出现的号留着")
        self.assertEqual(fixed["scene_manifest.json"][0]["scene_id"], "LOC_001", "换类别就换前缀")
        self.assertEqual(len(changes), 3, changes)
        self.assertTrue(sc.unique_ids(fixed))
        self.assertIsInstance(fixed["character_manifest.json"], dict, "带抬头的改完还是对象")
        self.assertIsInstance(fixed["scene_manifest.json"], list, "数组改完还是数组")

    def test_items_of_reads_both_shapes(self):
        self.assertEqual(sc.items_of([{"a": 1}]), [{"a": 1}])
        self.assertEqual(sc.items_of({"items": [{"a": 1}]}), [{"a": 1}])
        self.assertEqual(sc.items_of({"items": "不是数组"}), [])
        self.assertEqual(sc.manifest_name({"manifest": "x.json"}), "x.json")
        self.assertEqual(sc.manifest_name([], "y.json"), "y.json")


class ValidateTests(unittest.TestCase):
    """规则：编号格式、必填、强度与场号。"""

    def test_a_good_character_passes(self):
        self.assertEqual(sc.validate("character", sc.normalize("character", character())), [])

    def test_a_natural_language_feature_line_is_not_accepted(self):
        problems = sc.validate("character", character(physical_features="黑短发、杏眼"))
        self.assertTrue(any("字段化" in text for text in problems), problems)

    def test_empty_features_are_reported(self):
        problems = sc.validate("character", {"character_id": "CHAR_001", "name": "A"})
        self.assertTrue(any("空的" in text for text in problems), problems)

    def test_a_wrong_prefix_is_reported(self):
        problems = sc.validate("scene", {"scene_id": "SC_001", "name": "咖啡馆"})
        self.assertTrue(any("不合规" in text for text in problems), problems)

    def test_a_beat_needs_a_scene_and_an_intensity(self):
        self.assertEqual(sc.validate("emotion_curve", {"beat_id": "EC_001", "scene_id": "LOC_001",
                                                       "intensity": 5, "order": 1}), [])
        problems = sc.validate("emotion_curve", {"beat_id": "EC_001", "scene_id": "咖啡馆",
                                                 "intensity": 11})
        self.assertTrue(any("scene_id" in text for text in problems), problems)
        self.assertTrue(any("intensity" in text for text in problems), problems)

    def test_breakdown_characters_must_be_ids(self):
        item = {"breakdown_id": "SC_001", "scene_id": "LOC_001", "order": 1,
                "characters": ["CHAR_001", "林小满"]}
        problems = sc.validate("scene_breakdown", item)
        self.assertTrue(any("characters" in text for text in problems), problems)

    def test_a_junk_item_is_reported_not_raised(self):
        self.assertEqual(sc.validate("character", "不是对象"), ["条目必须是对象"])
        self.assertIsNone(sc.normalize("character", "不是对象"))


class SchemaTests(unittest.TestCase):
    """交付物 2：五类 JSON Schema。"""

    def test_there_is_one_schema_per_manifest(self):
        boxes = sc.schema()
        self.assertEqual(sorted(boxes), sorted(sc.MANIFESTS))
        for name, box in boxes.items():
            self.assertEqual(box["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertEqual(box["required"], list(sc.HEADER))
            self.assertEqual(box["properties"]["manifest"]["const"], name)
            self.assertEqual(box["properties"]["kind"]["const"], sc.KIND_OF_MANIFEST[name])

    def test_the_character_schema_needs_the_fielded_features(self):
        item = sc.schema()["character_manifest.json"]["properties"]["items"]["items"]
        self.assertIn("physical_features", item["required"])
        for key in sc.PHYSICAL_KEYS:
            self.assertIn(key, item["properties"]["physical_features"]["properties"], key)

    def test_the_emotion_schema_pins_the_intensity_range(self):
        item = sc.schema()["emotion_curve.json"]["properties"]["items"]["items"]
        self.assertEqual(item["properties"]["intensity"]["minimum"], 1)
        self.assertEqual(item["properties"]["intensity"]["maximum"], 10)

    def test_the_breakdown_schema_asks_for_character_ids(self):
        item = sc.schema()["scene_breakdown.json"]["properties"]["items"]["items"]
        self.assertEqual(item["properties"]["characters"]["items"]["pattern"],
                         sc.PATTERN["character"])
        for key in ("breakdown_id", "scene_id", "order"):
            self.assertIn(key, item["required"], key)

    def test_the_sample_passes_its_own_validation(self):
        data = sc.sample_character_manifest()
        self.assertEqual(sc.duplicate_ids({"character_manifest.json": data}), [])
        for item in data["items"]:
            self.assertEqual(sc.validate("character", item), [], item["name"])
        self.assertEqual(data["items"][0]["physical_features"]["body_type"], "身形修长")
        self.assertEqual(data["items"][0]["physical_features"]["eyes"], "杏眼")
        self.assertEqual(json.loads(json.dumps(data, ensure_ascii=False))["items"][1]["name"],
                         "陆时")


class CompletenessTests(unittest.TestCase):
    """交付物 5：剧本阶段产出的完整性检查。"""

    def test_an_empty_folder_reports_all_five_missing(self):
        with tempfile.TemporaryDirectory() as td:
            rows = sc.completeness(td)
            self.assertEqual([row[0] for row in rows], list(sc.MANIFESTS))
            self.assertTrue(all(row[1] == "缺失" for row in rows))

    def test_a_written_manifest_is_reported_as_produced(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "character_manifest.json").write_text(
                json.dumps(sc.sample_character_manifest(), ensure_ascii=False), encoding="utf-8")
            rows = dict((row[0], row[1:]) for row in sc.completeness(td))
            self.assertEqual(rows["character_manifest.json"][0], "已产出")
            self.assertIn("2 条", rows["character_manifest.json"][1])
            self.assertEqual(rows["emotion_curve.json"][0], "缺失")

    def test_a_broken_manifest_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "scene_manifest.json").write_text("{不是 JSON", encoding="utf-8")
            rows = dict((row[0], row[1]) for row in sc.completeness(td))
            self.assertEqual(rows["scene_manifest.json"], "有问题")
            (Path(td) / "emotion_curve.json").write_text(
                json.dumps({"manifest": "emotion_curve.json", "kind": "emotion_curve",
                            "items": [{"beat_id": "EC_001", "scene_id": "LOC_001",
                                       "intensity": 99}]}, ensure_ascii=False), encoding="utf-8")
            rows = dict((row[0], row[1:]) for row in sc.completeness(td))
            self.assertEqual(rows["emotion_curve.json"][0], "有问题")
            self.assertIn("intensity", rows["emotion_curve.json"][1])


class MergeTests(unittest.TestCase):
    """任务 3 的收口（第 8 轮）：重叠／支撑的那两个并回正稿的哪一段、产物落在哪。"""

    def test_the_two_support_skills_share_one_owner(self):
        rows = sc.support_rows(HERE)
        self.assertEqual(sorted(row["skill"] for row in rows), sorted(sc.MERGED_SKILLS))
        for row in rows:
            self.assertEqual(row["owner"], sc.MERGE_OWNER, row["skill"])
            self.assertTrue(row["part"], row["skill"])
            self.assertTrue(row["landing"], row["skill"])
        by_skill = dict((row["skill"], row["category"]) for row in rows)
        self.assertEqual(by_skill["script-dialogue-polish"], "重叠")
        self.assertEqual(by_skill["script-worldbuilding"], "支撑")

    def test_the_audit_row_names_the_same_owner(self):
        for row in sc.audit_rows(HERE):
            if row["skill"] in sc.MERGED_SKILLS:
                self.assertIn(sc.MERGE_OWNER, row["owner"], row["skill"])

    def test_the_owner_skill_declares_both_sub_steps(self):
        from skill_registry import default_registry
        owner = default_registry(HERE).getById("script-structured-generation")
        self.assertIsNotNone(owner, "归属 SKILL 必须仍由注册表发现")
        text = owner.path.read_text(encoding="utf-8-sig")
        for skill, part, _landing in sc.MERGED:
            self.assertIn(skill, text, skill)
            self.assertIn(part, text, part)
        self.assertIn("子步骤", text, "归属者要说清这是它的子步骤")

    def test_merging_did_not_delete_a_skill(self):
        from skill_registry import default_registry
        registry = default_registry(HERE)
        for skill in sc.MERGED_SKILLS:
            self.assertIsNotNone(registry.getById(skill), skill)
        script_names = {skill.name for skill in registry.getByStage("script")}
        structure_names = {skill.name for skill in registry.getByStage("script_structure")}
        self.assertIn("pipeline-script-preparation", script_names)
        self.assertTrue({"script-character-extraction", "script-dialogue-polish",
                         "script-structured-generation", "script-worldbuilding"} <= structure_names)

    def test_the_human_readable_landing_is_a_declared_doc(self):
        import stage_layout
        landing = [row["landing"] for row in sc.support_rows(HERE)
                   if row["skill"] == "script-worldbuilding"][0]
        self.assertEqual(landing, "docs/world_bible.md")
        stage_name = stage_layout.stage_dir(sc.STAGE)[0]
        names = [name for name, _text in stage_layout.DOCS[stage_name]]
        self.assertIn("world_bible.md", names, "落点要写进剧本准备/docs 的清单")

    def test_merge_problems_is_clean(self):
        self.assertEqual(sc.merge_problems(HERE), ())


class EpisodeIncrementalTests(unittest.TestCase):
    """阶段④分集解析与增量账本：标题容错、首次退化、只看改动集。"""

    def project(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name)

    def test_split_is_tolerant_and_falls_back_to_one_unsplit_block(self):
        text = ('# 第1集：起风\n第一集正文\n\n'
                '# 第02集: 雨后\n第二集正文\n\n'
                '# 第3集\n第三集正文\n')
        episodes = sc.split_script_episodes(text)
        self.assertEqual(list(episodes), [1, 2, 3])
        self.assertIn('第一集正文', episodes[1])
        self.assertIn('第二集正文', episodes[2])
        self.assertIn('第三集正文', episodes[3])
        self.assertEqual(sc.split_script_episodes('   '), {})
        plain = '没有分集标题的整篇正文'
        self.assertEqual(sc.split_script_episodes(plain), {sc.UNSPLIT_EPISODE_KEY: plain})
        block = sc.episode_reference_block(plain, None)
        self.assertIn(plain, block)

    def test_missing_ledger_degrades_to_full_reference(self):
        text = '# 第1集：起风\n第一集正文\n\n# 第2集：雨后\n第二集正文\n'
        block = sc.episode_reference_block(text, None)
        self.assertIn('第一集正文', block)
        self.assertIn('第二集正文', block)
        self.assertIn('首次记录', block)

    def test_only_changed_episodes_keep_their_text(self):
        project = self.project()
        original = '# 第1集：起风\n第一集正文\n\n# 第2集：雨后\n第二集正文\n'
        sc.record_episode_ledger(project, original)
        edited = '# 第1集：起风\n第一集正文\n\n# 第2集：雨后\n第二集改过的正文\n'
        block = sc.episode_reference_block(edited, sc.read_episode_ledger(project))
        self.assertIn('第二集改过的正文', block)
        self.assertNotIn('第一集正文', block)
        self.assertIn('第1集', block)
        self.assertIn('第2集已修改', block)

    def test_ledger_records_other_episode_snapshot(self):
        project = self.project()
        first = '# 第1集：起风\n甲\n\n# 第2集：雨后\n乙\n'
        sc.record_episode_ledger(project, first)
        second = '# 第1集：起风\n甲\n\n# 第2集：雨后\n乙改\n'
        sc.record_episode_ledger(project, second, previous_text=first)
        ledger = sc.read_episode_ledger(project)
        self.assertEqual(sorted(ledger['episodes']), ['1', '2'])
        self.assertEqual(ledger['episodes']['1']['sha256'],
                         sc.episode_digest(sc.split_script_episodes(second)[1]))
        self.assertEqual(ledger['episodes']['2']['based_on'],
                         {'1': sc.episode_digest(sc.split_script_episodes(first)[1])})
        self.assertTrue(sc.episode_ledger_path(project).is_file())

    def test_broken_ledger_does_not_break_the_reference(self):
        project = self.project()
        path = sc.episode_ledger_path(project)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{not json', encoding='utf-8')
        self.assertEqual(sc.read_episode_ledger(project), {'version': 1, 'episodes': {}})
        text = '# 第1集：起风\n第一集正文\n'
        self.assertIn('第一集正文', sc.episode_reference_block(text, sc.read_episode_ledger(project)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
