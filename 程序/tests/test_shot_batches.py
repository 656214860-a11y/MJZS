# -*- coding: utf-8 -*-
"""批次划分与分镜 JSON 契约（第 61 期 v0.8 任务 4／10）的自检。运行：python test_shot_batches.py

盯住三件事：① 老分镜 JSON 只有 id／characters／location／duration 也能补出那九个必填字段；
② 切分算法（三元组一变、满 4 镜、累计超 18 秒就切）与预期完全一致；③ 交付物 3 的规则表、
伪代码与交付物 6 的 Schema 都在。
"""
import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import shot_batches as sb


def shot(index, seconds=3, chars=("CHAR_001",), location="LOC_001", costume=""):
    """一镜的最小老写法：只有 id／characters／location／duration。"""
    return {"id": "SH%03d" % index, "title": "镜头", "duration": seconds,
            "characters": list(chars), "location": location}


class NumbersTests(unittest.TestCase):
    def test_number_ignores_booleans_and_junk(self):
        self.assertEqual(sb.number(4), 4)
        self.assertEqual(sb.number(4.7), 4)
        self.assertEqual(sb.number(True), 0)
        self.assertEqual(sb.number("5"), 0)
        self.assertEqual(sb.number(None, 3), 3)

    def test_duration_prefers_the_estimate(self):
        self.assertEqual(sb.duration({"duration": 5}), 5)
        self.assertEqual(sb.duration({"duration": 5, "estimated_duration": 2}), 2)
        self.assertEqual(sb.duration({"duration": 5, "estimated_duration": ""}), 5)
        self.assertEqual(sb.duration({}), sb.DEFAULT_SECONDS)
        self.assertEqual(sb.duration(None), sb.DEFAULT_SECONDS)


class NormalizeTests(unittest.TestCase):
    def test_the_nine_fields_come_from_the_old_ones(self):
        data = sb.normalize(shot(1, 4), 0)
        self.assertEqual(data["shot_id"], "SH001")
        self.assertEqual(data["scene_id"], "LOC_001")
        self.assertEqual(data["character_ids"], ["CHAR_001"])
        self.assertEqual(data["costume_id"], "")
        self.assertEqual(data["batch_id"], "")
        self.assertEqual(data["character_refs"], ["@图片1"])
        self.assertEqual(data["reference_roles"]["@图片1"]["responsibility"], sb.DEFAULT_RESPONSIBILITY)
        self.assertEqual(data["reference_roles"]["@图片1"]["exclude"], sb.DEFAULT_EXCLUDE)
        self.assertEqual(data["continuity_flags"], [])
        self.assertEqual(data["estimated_duration"], 4)
        self.assertEqual(data["characters"], ["CHAR_001"], "老键一个都不动")

    def test_shot_id_falls_back_to_the_position(self):
        self.assertEqual(sb.normalize({}, 2)["shot_id"], "S03")

    def test_existing_new_fields_are_kept(self):
        data = sb.normalize({"id": "SH001", "character_refs": ["@图片9"],
                             "reference_roles": {"@图片9": {"responsibility": "只负责脸",
                                                            "exclude": "一切别的"}},
                             "continuity_flags": ["耳环不可变"]}, 0)
        self.assertEqual(data["character_refs"], ["@图片9"])
        self.assertEqual(data["reference_roles"]["@图片9"]["responsibility"], "只负责脸")
        self.assertEqual(data["continuity_flags"], ["耳环不可变"])

    def test_refs_follow_the_character_count(self):
        data = sb.normalize(shot(1, chars=("CHAR_001", "CHAR_002")), 0)
        self.assertEqual(data["character_refs"], ["@图片1", "@图片2"])
        self.assertEqual(sorted(data["reference_roles"]), ["@图片1", "@图片2"])

    def test_triplet_is_scene_chars_costume(self):
        self.assertEqual(sb.triplet(sb.normalize(shot(1), 0)),
                         ("LOC_001", ("CHAR_001",), ""))


class GroupTests(unittest.TestCase):
    def test_a_triplet_change_starts_a_new_batch(self):
        shots = [shot(1), shot(2), shot(3, chars=("CHAR_002",)), shot(4, chars=("CHAR_002",))]
        batches = sb.group(shots)
        self.assertEqual([len(batch) for batch in batches], [2, 2])

    def test_a_batch_never_exceeds_four_shots(self):
        shots = [shot(index) for index in range(1, 9)]
        batches = sb.group(shots)
        self.assertEqual([len(batch) for batch in batches], [4, 4])
        self.assertTrue(all(len(batch) <= sb.BATCH_MAX_SHOTS for batch in batches))

    def test_a_batch_never_exceeds_eighteen_seconds(self):
        shots = [shot(index, 5) for index in range(1, 7)]
        batches = sb.group(shots)
        self.assertEqual([len(batch) for batch in batches], [3, 3], "5 秒一镜，18 秒最多放 3 个")
        for batch in batches:
            self.assertLessEqual(sum(sb.duration(item) for item in batch), sb.BATCH_SECONDS)

    def test_long_batches_allow_twenty_five_seconds(self):
        shots = [shot(index, 5) for index in range(1, 7)]
        batches = sb.group(shots, long=True)
        self.assertEqual([len(batch) for batch in batches], [4, 2])

    def test_assign_fills_batch_ids_in_order(self):
        shots = [shot(1), shot(2)]
        filled = sb.assign(shots)
        self.assertEqual([item["batch_id"] for item in filled], ["B01", "B01"])
        shots = [shot(1), shot(2, chars=("CHAR_002",))]
        self.assertEqual([item["batch_id"] for item in sb.assign(shots)], ["B01", "B02"])
        self.assertEqual(sb.assign(shots, start=3)[0]["batch_id"], "B03")

    def test_batches_group_by_the_stored_batch_id(self):
        shots = [dict(shot(1), batch_id="B02"), dict(shot(2), batch_id="B01")]
        grouped = sb.batches(shots)
        self.assertEqual(list(grouped), ["B01", "B02"])
        self.assertEqual(len(grouped["B01"]), 1)


class AdviseAndCheckTests(unittest.TestCase):
    def test_advise_flags_off_range_designs(self):
        notes = sb.advise([shot(index, 9) for index in range(1, 4)])
        self.assertTrue(any("设计区间" in note for note in notes))
        self.assertEqual(sb.advise([]), ["还没有镜头"])

    def test_advise_stays_quiet_on_a_good_episode(self):
        # 20 个镜头、5 个批次、每批 4 镜 12 秒：六条设计区间一条都不该踩。
        shots = [shot(index, 3, chars=("CHAR_%03d" % ((index - 1) // 4 + 1),))
                 for index in range(1, 21)]
        self.assertEqual(sb.advise(sb.assign(shots)), [])

    def test_check_batches_rejects_over_long_batches(self):
        shots = [dict(shot(index, 5), batch_id="B01") for index in range(1, 5)]
        problems = sb.check_batches(shots)
        self.assertTrue(any("20 秒" in text or "超过每批" in text for text in problems))
        shots = [dict(shot(index), batch_id="B01") for index in range(1, 6)]
        self.assertTrue(any("超过每批 4 个" in text for text in sb.check_batches(shots)))
        self.assertEqual(sb.check_batches(sb.assign([shot(1), shot(2)])), [])

    def test_check_batches_rejects_mixed_triplets(self):
        # 三元组读的是 scene_id／character_ids／costume_id，喂进来的必须是补过字段的镜头。
        shots = [dict(sb.normalize(shot(1), 0), batch_id="B01"),
                 dict(sb.normalize(shot(2, chars=("CHAR_002",)), 1), batch_id="B01")]
        self.assertTrue(any("三元组不一致" in text for text in sb.check_batches(shots)))


class ValidateTests(unittest.TestCase):
    def test_a_normalized_shot_with_costume_and_scene_passes(self):
        data = sb.normalize(shot(1), 0)
        data["costume_id"] = "CST-01"
        data["batch_id"] = "B01"
        self.assertEqual(sb.validate(data, 0), [])

    def test_problems_are_reported_in_plain_words(self):
        problems = sb.validate({"id": "X1", "characters": ["CHAR_001"], "duration": 1}, 0)
        self.assertTrue(any("shot_id" in text for text in problems))
        self.assertTrue(any("scene_id" in text for text in problems))
        self.assertTrue(any("costume_id" in text for text in problems))
        self.assertTrue(any("2–15" in text for text in problems))

    def test_costume_and_batch_id_formats(self):
        data = sb.normalize(shot(1), 0)
        data["costume_id"] = "C01"
        self.assertTrue(any("CST-##" in text for text in sb.validate(data, 0)))
        data = sb.normalize(shot(1), 0)
        data["batch_id"] = "1"
        self.assertTrue(any("B01" in text for text in sb.validate(data, 0)))

    def test_refs_must_match_characters(self):
        data = sb.normalize(shot(1, chars=("CHAR_001", "CHAR_002")), 0)
        data["character_refs"] = ["@图片1"]
        self.assertTrue(any("一一对应" in text for text in sb.validate(data, 0)))

    def test_a_missing_role_declaration_is_reported(self):
        data = sb.normalize(shot(1), 0)
        data["reference_roles"] = {"@图片1": {"responsibility": "", "exclude": ""}}
        self.assertTrue(any("职责声明" in text for text in sb.validate(data, 0)))

    def test_non_dict_shot(self):
        self.assertEqual(sb.validate("不是对象", 1), ["第 2 镜不是对象"])


class DeliveryTests(unittest.TestCase):
    def test_rule_table_covers_the_six_lines(self):
        rows = sb.rules_rows()
        self.assertEqual(len(rows), 6)
        text = "".join(row[0] for row in rows)
        for key in ("单镜", "单批", "单集", "100 集"):
            self.assertIn(key, text)
        self.assertIn("%d–%d" % sb.SHOT_SECONDS, rows[0][1])

    def test_pseudocode_writes_batch_ids(self):
        text = sb.pseudocode()
        self.assertIn("batch_id", text)
        self.assertIn("18", text)
        self.assertIn("triplet", text)

    def test_schema_requires_the_nine_fields(self):
        schema = sb.schema()
        shot = schema["properties"]["shots"]["items"]
        for key in ("shot_id", "scene_id", "character_ids", "costume_id", "batch_id",
                    "character_refs", "reference_roles", "continuity_flags", "estimated_duration"):
            self.assertIn(key, shot["required"], key)
        self.assertEqual(schema["required"], ["episode_id", "title", "duration", "shots"])

    def test_field_table_names_its_default_source(self):
        sources = {row[0]: row[1] for row in sb.SHOT_FIELDS}
        self.assertEqual(sources["character_ids"], "characters")
        self.assertEqual(sources["scene_id"], "location")
        self.assertEqual(sources["estimated_duration"], "duration")
        self.assertEqual(sources["batch_id"], "")


if __name__ == "__main__":
    unittest.main(verbosity=2)