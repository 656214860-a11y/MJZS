# -*- coding: utf-8 -*-
"""分镜采用/资产同步工作流自检。运行：python test_workflow.py"""
import json, os, sys, tempfile, time, unittest
from pathlib import Path
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

from storyboard_selection import adopted, summary, focus, sync_working_episode
from stage_execution_service import (adopt_asset_storyboards as adopt,
                                     poll_asset_storyboard_adoption as adopt_pending,
                                     remove_asset_storyboards as remove,
                                     sync_asset_plan as sync_plan)
from asset_context import library_dir


def valid_episode(episode_id="EP001", title="测试集"):
    return {"episode_id": episode_id, "title": title, "shots": [{
        "id": "SH001", "title": "镜头", "duration": 5,
        "characters": ["CHAR_001"], "location": "LOC_001",
        "frame": "frames/SH001.png", "video_prompt": "画面与对白要求", "dialogue": []}]}


def make_project(td):
    t = Path(td); proj = t / "proj"
    (proj / "episode" / "frames").mkdir(parents=True)
    (proj / "episode" / "assets.json").write_text(json.dumps({
        "CHAR_001": {"name": "角色甲"}, "LOC_001": {"name": "地点甲"}}, ensure_ascii=False), encoding="utf-8")
    (proj / "episode" / "episode.json").write_text(json.dumps(valid_episode(), ensure_ascii=False), encoding="utf-8")
    (proj / "storyboard" / "分镜拆分").mkdir(parents=True)
    (proj / "storyboard" / "分镜拆分" / "episode.json").write_text(json.dumps(valid_episode(), ensure_ascii=False), encoding="utf-8")
    (proj / "config.json").write_text(json.dumps({
        "episode_dir": str(proj / "episode"), "episode_file": str(proj / "episode" / "episode.json")}, ensure_ascii=False), encoding="utf-8")
    return proj


class AdoptTests(unittest.TestCase):
    def test_adopt_then_remove(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            paths = adopt(proj, ["storyboard/分镜拆分/episode.json"])
            self.assertEqual(len(paths), 1)
            self.assertEqual(len(adopted(proj)), 1)
            self.assertIn("1 份", summary(proj))
            focus(proj, "storyboard/分镜拆分/episode.json")
            self.assertEqual(len(remove(proj, ["storyboard/分镜拆分/episode.json"])), 0)
            self.assertEqual(adopted(proj), [])

    def test_adopt_rejects_missing(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            with self.assertRaises(ValueError):
                adopt(proj, ["storyboard/分镜拆分/不存在.json"])

    def test_adopt_error_names_the_file_and_the_gap(self):
        """第 62 期任务 12：时长对不上时，报错要说清是哪一份、差多少。"""
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            source = proj / "storyboard" / "分镜拆分" / "EP001_测试集_分镜.json"
            data = valid_episode(); data["duration"] = 120
            source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                adopt(proj, [source])
            text = str(caught.exception)
            self.assertIn(source.name, text)
            self.assertIn("整集时长120秒", text)
            self.assertIn("各镜时长合计5秒", text)

    def test_check_adoptable_lists_every_bad_file_at_once(self):
        """第 62 期任务 12：采用前一次列清全部不合格的分镜，别让用户改一份、试一次。"""
        from storyboard_files import catalog, check_adoptable
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            folder = proj / "storyboard" / "分镜拆分"
            bad_one = folder / "EP001_甲_分镜.json"
            bad_two = folder / "EP002_乙_分镜.json"
            for path, episode_id, declared in ((bad_one, "EP001", 120), (bad_two, "EP002", 90)):
                data = valid_episode(episode_id); data["duration"] = declared
                path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            good = folder / "EP003_丙_分镜.json"
            good.write_text(json.dumps(valid_episode("EP003"), ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                check_adoptable([bad_one, good, bad_two])
            text = str(caught.exception)
            self.assertIn(bad_one.name, text)
            self.assertIn(bad_two.name, text)
            self.assertNotIn(good.name, text)
            self.assertEqual(text.count("\n"), 2, "一行提示 ＋ 两份各一行")
            titles = {entry["path"]: entry["title"] for entry in catalog(proj, "storyboard")}
            self.assertIn("时长不符", titles[bad_one.resolve()])
            self.assertIn("时长不符", titles[bad_two.resolve()])
            self.assertNotIn("时长不符", titles[good.resolve()])

    def test_corrupt_prefs_treated_empty(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            (proj / "ui_settings.json").write_text("[]", encoding="utf-8")
            self.assertEqual(adopted(proj), [])

    def test_unparseable_prefs_says_what_to_do(self):
        """ui_settings.json 被截断或手工改坏时，给可操作的中文提示，而不是一句 JSONDecodeError。"""
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            settings = proj / "ui_settings.json"
            settings.write_text("{ 坏掉的设置", encoding="utf-8")
            import desktop
            import storyboard_files
            import storyboard_selection
            for label, call in (("prefs", lambda: storyboard_selection.prefs(proj)),
                                ("adopted", lambda: adopted(proj)),
                                ("selected_many", lambda: storyboard_files.selected_many(proj, "storyboard")),
                                ("desktop", lambda: desktop._prefs(settings))):
                with self.assertRaises(ValueError) as caught:
                    call()
                self.assertIn("ui_settings.json", str(caught.exception), label)
                self.assertIn("无法读取", str(caught.exception), label)

    def test_sync_working_episode_switches_config_after_adopt(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            target = proj / "storyboard" / "分镜拆分" / "episode.json"
            adopt(proj, ["storyboard/分镜拆分/episode.json"])
            self.assertEqual(sync_working_episode(proj), target)
            cfg = json.loads((proj / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(Path(cfg["episode_file"]), target)
            self.assertEqual(Path(cfg["episode_dir"]), target.parent)

    def test_sync_working_episode_keeps_config_with_video_tasks(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            adopt(proj, ["storyboard/分镜拆分/episode.json"])
            (proj / "data").mkdir(parents=True)
            (proj / "data" / "state.json").write_text(json.dumps(
                {"schema": 1, "shots": {"SH001": [{"state": "succeeded"}]}}), encoding="utf-8")
            before = (proj / "config.json").read_text(encoding="utf-8")
            self.assertIsNone(sync_working_episode(proj))
            self.assertEqual((proj / "config.json").read_text(encoding="utf-8"), before)


class AdoptPendingTests(unittest.TestCase):
    """无人值守自动采用：新分镜出现即推进后续流程，半成品先等，坏文件只跳过自己。"""

    def project(self, td):
        proj = make_project(td)
        # 只保留测试写入的分镜：fixture 自带的工作稿会按「刚写入」影响等待列表。
        (proj / "storyboard" / "分镜拆分" / "episode.json").unlink()
        return proj

    def write(self, proj, episode_id, age=60, shot_ids=None):
        # 文件名用规范名，避免被测代码在采用途中重命名文件后路径对不上。
        path = proj / "storyboard" / "分镜拆分" / (episode_id + "_测试集_分镜.json")
        data = valid_episode(episode_id)
        ids = shot_ids or ["SH001"]
        data["shots"] = [dict(data["shots"][0], id=value) for value in ids]
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        stamp = time.time() - age
        os.utime(path, (stamp, stamp))
        return path

    def test_settled_json_is_adopted_and_working_config_switched(self):
        with tempfile.TemporaryDirectory() as td:
            proj = self.project(td)
            target = self.write(proj, "EP002")
            result = adopt_pending(proj)
            self.assertEqual(result["adopted"], [target])
            self.assertEqual(result["waiting"], [])
            self.assertEqual(result["failed"], {})
            self.assertIn(target, adopted(proj))
            cfg = json.loads((proj / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(Path(cfg["episode_file"]), target)

    def test_fresh_json_waits_instead_of_being_read_half_written(self):
        with tempfile.TemporaryDirectory() as td:
            proj = self.project(td)
            target = self.write(proj, "EP002", age=0)
            result = adopt_pending(proj)
            self.assertEqual(result["adopted"], [])
            self.assertEqual(result["waiting"], [target])
            self.assertIn("刚写入", result["failed"][str(target)])
            self.assertEqual(adopted(proj), [])

    def test_invalid_json_is_skipped_while_valid_sibling_is_adopted(self):
        with tempfile.TemporaryDirectory() as td:
            proj = self.project(td)
            bad = self.write(proj, "EP002", shot_ids=["X01"])
            good = self.write(proj, "EP003")
            result = adopt_pending(proj)
            self.assertEqual(result["adopted"], [good])
            self.assertIn(str(bad), result["failed"])
            self.assertEqual(adopted(proj), [good])

    def test_repeat_call_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            proj = self.project(td)
            self.write(proj, "EP002")
            first = adopt_pending(proj)
            second = adopt_pending(proj)
            self.assertEqual(len(first["adopted"]), 1)
            self.assertEqual(second["adopted"], [])
            self.assertEqual(second["waiting"], [])
            self.assertEqual(len(adopted(proj)), 1)

    def test_auto_adopt_switch_defaults_off(self):
        with tempfile.TemporaryDirectory() as td:
            proj = self.project(td)
            import project_settings
            self.assertFalse(project_settings.auto_adopt(proj))
            self.assertTrue(project_settings.set_auto_adopt(proj, True))
            self.assertTrue(project_settings.auto_adopt(proj))
            self.assertFalse(project_settings.set_auto_adopt(proj, False))
            self.assertFalse(project_settings.auto_adopt(proj))

    def test_auto_previs_switch_defaults_off(self):
        with tempfile.TemporaryDirectory() as td:
            proj = self.project(td)
            import project_settings
            self.assertFalse(project_settings.auto_previs(proj))
            self.assertTrue(project_settings.set_auto_previs(proj, True))
            self.assertTrue(project_settings.auto_previs(proj))
            self.assertFalse(project_settings.set_auto_previs(proj, False))
            self.assertFalse(project_settings.auto_previs(proj))

    def test_auto_final_switch_defaults_off(self):
        """第04步自动生成定稿默认关闭：它会把工作稿移入回收站，必须由人显式勾选。"""
        with tempfile.TemporaryDirectory() as td:
            proj = self.project(td)
            import project_settings
            self.assertFalse(project_settings.auto_final(proj))
            self.assertTrue(project_settings.set_auto_final(proj, True))
            self.assertTrue(project_settings.auto_final(proj))
            self.assertFalse(project_settings.set_auto_final(proj, False))
            self.assertFalse(project_settings.auto_final(proj))

    def test_auto_handoff_switch_defaults_off(self):
        with tempfile.TemporaryDirectory() as td:
            proj = self.project(td)
            import project_settings
            self.assertFalse(project_settings.auto_handoff(proj))
            self.assertTrue(project_settings.set_auto_handoff(proj, True))
            self.assertTrue(project_settings.auto_handoff(proj))
            self.assertFalse(project_settings.set_auto_handoff(proj, False))
            self.assertFalse(project_settings.auto_handoff(proj))


class SyncPlanTests(unittest.TestCase):
    def test_library_dir_uses_asset_library_dir(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; proj.mkdir()
            (proj / "config.json").write_text(json.dumps({"episode_dir": "episode", "asset_library_dir": "lib"}), encoding="utf-8")
            self.assertEqual(library_dir(proj), (proj / "lib").resolve())

    def test_sync_plan_rows(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            base = library_dir(proj)
            rows = sync_plan(proj, base, ["storyboard/分镜拆分/episode.json"], scope="adopted", _adopting=True)
            self.assertIn("CHAR_001", rows)
            self.assertIn("LOC_001", rows)
            self.assertEqual(rows["CHAR_001"]["name"], "角色甲")

    def test_sync_plan_non_adopted_with_adopting(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            base = library_dir(proj)
            rows = sync_plan(proj, base, ["storyboard/分镜拆分/episode.json"], scope="current", _adopting=True)
            self.assertIn("CHAR_001", rows)
            self.assertIn("LOC_001", rows)


class EpisodeNumberTests(unittest.TestCase):
    def parse(self, name):
        from workflow_context import episode_number
        return episode_number(name)

    def test_ep_arabic(self):
        self.assertEqual(self.parse("EP001_标题_分镜"), 1)

    def test_第_arabic(self):
        self.assertEqual(self.parse("第3集_剧本"), 3)

    def test_chinese_five_and_fifteen(self):
        self.assertEqual(self.parse("第五集"), 5)
        self.assertEqual(self.parse("第十五集"), 15)

    def test_chinese_nine_and_eighteen(self):
        self.assertEqual(self.parse("第九集"), 9)
        self.assertEqual(self.parse("第十八集"), 18)

    def test_chinese_fourteen_and_nineteen(self):
        self.assertEqual(self.parse("第十四集"), 14)
        self.assertEqual(self.parse("第十九集"), 19)

    def test_chinese_teens_common(self):
        for n, name in [(13, "第十三集"), (16, "第十六集"), (17, "第十七集")]:
            self.assertEqual(self.parse(name), n)

    def test_chinese_ten(self):
        self.assertEqual(self.parse("第二十集"), 20)

    def test_chinese_twenty_five(self):
        self.assertEqual(self.parse("第二十五集"), 25)

    def test_chinese_twelve(self):
        self.assertEqual(self.parse("第十二集"), 12)

    def test_chinese_hundred(self):
        self.assertEqual(self.parse("第一百集"), 100)

    def test_chinese_eleven(self):
        self.assertEqual(self.parse("第十一集"), 11)

    def test_chinese_two_hundred(self):
        self.assertEqual(self.parse("第两百集"), 200)

    def test_chinese_five_hundred(self):
        self.assertEqual(self.parse("第五百集"), 500)
        self.assertEqual(self.parse("第三千集"), 3000)

    def test_chinese_three_four_hundred(self):
        self.assertEqual(self.parse("第三百集"), 300)
        self.assertEqual(self.parse("第四百集"), 400)

    def test_chinese_six_eight_hundred(self):
        self.assertEqual(self.parse("第六百集"), 600)
        self.assertEqual(self.parse("第八百集"), 800)

    def test_chinese_two_thousand(self):
        self.assertEqual(self.parse("第两千集"), 2000)

    def test_chinese_qian_alone(self):
        self.assertEqual(self.parse("第千集"), 1000)

    def test_chinese_hundred_five(self):
        self.assertEqual(self.parse("第一百零五集"), 105)

    def test_chinese_hundred_one(self):
        self.assertEqual(self.parse("第百零一集"), 101)

    def test_chinese_bai_alone(self):
        self.assertEqual(self.parse("第百集"), 100)

    def test_chinese_zero(self):
        self.assertEqual(self.parse("第零集"), 0)

    def test_chinese_liang_with_zero(self):
        self.assertEqual(self.parse("第两百零五集"), 205)

    def test_mixed_arabic_chinese_no_crash(self):
        self.assertEqual(self.parse("第10集"), 10)
        self.assertEqual(self.parse("第1十集"), 10)

    def test_mixed_arabic_chinese_bai(self):
        self.assertEqual(self.parse("第1百集"), 100)
        self.assertEqual(self.parse("第2百5十集"), 250)

    def test_fullwidth_digits(self):
        self.assertEqual(self.parse("第１０集"), 10)
        self.assertEqual(self.parse("第１２集"), 12)

    def test_leading_zero_chinese(self):
        self.assertEqual(self.parse("第〇〇一集"), 1)

    def test_bai_shi(self):
        self.assertEqual(self.parse("第百十集"), 110)
        self.assertEqual(self.parse("第百一十集"), 110)

    def test_liang_qian_ling_wu(self):
        self.assertEqual(self.parse("第两千零五集"), 2005)

    def test_liang_qian_ling_yi(self):
        self.assertEqual(self.parse("第两千零一集"), 2001)

    def test_none(self):
        self.assertIsNone(self.parse("项目设定"))
        self.assertIsNone(self.parse("第万集"))


class AudioFlowTests(unittest.TestCase):
    def test_defaults_audio(self):
        import workflow_settings as ws
        d = ws.defaults("audio")
        self.assertEqual(d["engine"], "codex")
        self.assertEqual(set(d["profiles"]), set(ws.ENGINES))

    def test_writing_whale_skill_and_agent_gate_are_in_the_claude_prompt(self):
        """鲸剧被选中时，Claude 实际收到同一份 SKILL 与剧本开工门禁。"""
        import workflow_engines
        import workflow_settings as ws
        from workflow_tasks import script_prompt
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / 'p'; proj.mkdir()
            creative = proj / '创意.md'; creative.write_text('少年在照相馆发现旧底片。', encoding='utf-8')
            config = ws.defaults('writing')['profiles']['claude']
            config['engine'] = 'claude'
            whale_path = proj / 'jingju-skills' / 'SKILL.md'
            whale_path.parent.mkdir()
            whale_path.write_text('---\nname: jingju-skills\n---\n遵循剧本准备门控。', encoding='utf-8')
            whale = str(whale_path)
            ws.set_skills(config, [whale])
            prompt = workflow_engines.prompt_with_settings(script_prompt(proj, creative, 'writing'), config, stage='writing')
            self.assertIn(whale, prompt)
            self.assertIn(f'请先完整读取并遵循本地技能文件 {whale}', prompt)
            self.assertNotIn('遵循剧本准备门控。', prompt)
            self.assertIn('本阶段唯一正式交付物是完整自然语言剧本正文', prompt)
            self.assertIn('不得写入 02剧本结构或任何后续阶段目录', prompt)

    def test_load_corrupt_settings_falls_back(self):
        import workflow_settings as ws
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; proj.mkdir()
            (proj / "工作流任务").mkdir()
            (proj / "工作流任务" / "工作流调用设置.json").write_text("{bad json", encoding="utf-8")
            d = ws.load(proj, "audio")
            self.assertEqual(d["engine"], "codex")
            self.assertEqual(set(d["profiles"]), set(ws.ENGINES))

    def test_audio_prompt_contains_dialogue(self):
        import json
        from workflow_tasks import audio_prompt
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; proj.mkdir()
            src = proj / "episode.json"
            ep = {"episode_id": "EP001", "title": "T", "shots": [{
                "id": "SH001", "title": "开场", "duration": 5,
                "dialogue": [{"speaker": "CHAR_001", "start": 1, "end": 3, "text": "你好"}],
                "video_prompt": "x"}]}
            src.write_text(json.dumps(ep, ensure_ascii=False), encoding="utf-8")
            text = audio_prompt(proj, src)
            self.assertIn("配音与字幕", text)
            self.assertIn("你好", text)
            self.assertIn("CHAR_001", text)

    def test_sync_plan_auto_assign_name(self):
        with tempfile.TemporaryDirectory() as td:
            t = Path(td); proj = t / "p"
            (proj / "episode").mkdir(parents=True)
            (proj / "episode" / "assets.json").write_text("{}", encoding="utf-8")
            (proj / "storyboard" / "分镜拆分").mkdir(parents=True)
            ep = {"episode_id": "EP001", "title": "T", "shots": [{
                "id": "SH001", "title": "镜头", "duration": 5,
                "characters": ["新角色甲"], "location": "新场景",
                "frame": "frames/SH001.png", "video_prompt": "x", "dialogue": []}]}
            (proj / "storyboard" / "分镜拆分" / "episode.json").write_text(json.dumps(ep, ensure_ascii=False), encoding="utf-8")
            (proj / "config.json").write_text(json.dumps({"episode_dir": str(proj / "episode")}), encoding="utf-8")
            rows = sync_plan(proj, proj / "episode", ["storyboard/分镜拆分/episode.json"], scope="adopted", _adopting=True)
            # 名称应自动分配为 CHAR_001 / LOC_001
            char_ids = [aid for aid in rows if aid.startswith("CHAR_") and rows[aid]["name"] == "新角色甲"]
            loc_ids = [aid for aid in rows if aid.startswith("LOC_") and rows[aid]["name"] == "新场景"]
            self.assertEqual(len(char_ids), 1)
            self.assertEqual(len(loc_ids), 1)


class NormalizeTests(unittest.TestCase):
    def test_dedup_identical_json(self):
        from storyboard_storage import normalize, ALIAS_FILE
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; (proj / "storyboard" / "分镜拆分").mkdir(parents=True)
            ep = {"episode_id": "EP001", "title": "T", "shots": [
                {"id": "SH001", "title": "镜头", "duration": 5, "frame": "frames/SH001.png", "video_prompt": "x"}]}
            for name in ("a.json", "b.json"):
                (proj / "storyboard" / "分镜拆分" / name).write_text(json.dumps(ep, ensure_ascii=False), encoding="utf-8")
            old = time.time() - 100
            for f in (proj / "storyboard" / "分镜拆分").glob("*.json"):
                os.utime(f, (old, old))
            from stage_execution_service import storyboard_gateway
            normalize(proj, min_age=0, gateway=storyboard_gateway())
            jsons = [f for f in (proj / "storyboard" / "分镜拆分").glob("*.json") if f.name != ALIAS_FILE]
            self.assertEqual(len(jsons), 1)
            self.assertTrue((proj / "storyboard" / "分镜拆分" / "EP001_T_分镜.json").exists())
            manifests = list((proj / "工作流任务" / "回收站").glob("*/恢复位置.json"))
            self.assertEqual(len(manifests), 1, "重复工作稿必须移入可恢复回收站")
            restored = json.loads(manifests[0].read_text(encoding="utf-8"))
            self.assertEqual(restored["reason"], "合并重复分镜")
            self.assertEqual(len(restored["items"]), 2)

    def test_dedup_current_stage_json_uses_current_stage_and_recycle(self):
        from storyboard_storage import normalize, ALIAS_FILE
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; root = proj / "03初步分镜" / "分镜拆分"
            root.mkdir(parents=True)
            ep = {"episode_id": "EP001", "title": "当前", "shots": [{"id": "SH001"}]}
            for name in ("a.json", "b.json"):
                (root / name).write_text(json.dumps(ep, ensure_ascii=False), encoding="utf-8")
            old = time.time() - 100
            for file in root.glob("*.json"):
                os.utime(file, (old, old))
            from stage_execution_service import storyboard_gateway
            normalize(proj, min_age=0, gateway=storyboard_gateway())
            self.assertTrue((root / "EP001_当前_分镜.json").is_file())
            self.assertFalse((root / "a.json").exists())
            self.assertFalse((root / "b.json").exists())
            self.assertTrue(list((proj / "工作流任务" / "回收站").glob("*/恢复位置.json")))


class WorkingContentTests(unittest.TestCase):
    def test_strips_ui_fields(self):
        from storyboard_lifecycle import working_content
        ep = {"episode_id": "EP001", "title": "T", "missing_assets": [], "assets_ready": True,
              "shots": [{"id": "SH001", "title": "x", "video_prompt": "v",
                         "asset_bindings": {}, "asset_status": "y", "reference_images": []}]}
        out = working_content(ep)
        self.assertNotIn("missing_assets", out)
        self.assertNotIn("asset_bindings", out["shots"][0])
        self.assertNotIn("reference_images", out["shots"][0])
        self.assertEqual(out["shots"][0]["video_prompt"], "v")


class SignatureTests(unittest.TestCase):
    def test_pending_tree_signature_uses_current_storyboard_stage(self):
        from storyboard_selection import tree_signature
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            target = project / '03初步分镜' / '分镜拆分' / 'EP001_测试_分镜.json'
            target.parent.mkdir(parents=True)
            target.write_text('{}', encoding='utf-8')
            count, latest = tree_signature(project)
            self.assertEqual(count, 1)
            self.assertGreater(latest, 0)

    def test_pending_tree_signature_ignores_internal_catalog_directories(self):
        from storyboard_selection import tree_signature
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            root = project / '03初步分镜'
            visible = root / '分镜拆分' / 'EP001_测试_分镜.json'
            hidden = root / '历史版本' / 'EP000_旧版_分镜.json'
            visible.parent.mkdir(parents=True); hidden.parent.mkdir(parents=True)
            visible.write_text('{}', encoding='utf-8'); hidden.write_text('{}', encoding='utf-8')
            self.assertEqual(tree_signature(project)[0], 1)

    def test_signature_with_image(self):
        from storyboard_lifecycle import signature
        with tempfile.TemporaryDirectory() as td:
            base = Path(td); (base / "a.png").write_bytes(b"image-bytes")
            sig = signature({"episode_id": "EP001"}, {"CHAR_001": {"name": "x", "image": "a.png"}}, base)
            self.assertEqual(len(sig), 64)

    def test_signature_missing_image_returns_none(self):
        from storyboard_lifecycle import signature
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            self.assertIsNone(signature({"episode_id": "EP001"}, {"CHAR_001": {"name": "x", "image": "missing.png"}}, base))

    def test_signature_deterministic(self):
        from storyboard_lifecycle import signature
        with tempfile.TemporaryDirectory() as td:
            base = Path(td); (base / "a.png").write_bytes(b"image-bytes")
            ep = {"episode_id": "EP001"}
            assets = {"CHAR_001": {"name": "x", "image": "a.png", "used_in": ["SH001"]}}
            self.assertEqual(signature(ep, assets, base), signature(ep, assets, base))


class StoryboardLifecyclePathTests(unittest.TestCase):
    @staticmethod
    def _context(project):
        from project_context import ProjectContext
        return ProjectContext.snapshot(project, lambda _stage: Path(project))

    def test_retire_rejects_missing_l3_publisher(self):
        from storyboard_lifecycle import retire
        with tempfile.TemporaryDirectory() as td:
            project=Path(td)
            source=project/'03初步分镜'/'分镜拆分'/'EP001.json'
            target=project/'04分镜定稿'/'EP001'/'episode.json'
            source.parent.mkdir(parents=True); target.parent.mkdir(parents=True)
            raw=b'{"episode_id":"EP001"}'; source.write_bytes(raw); target.write_bytes(raw)
            import hashlib
            with self.assertRaisesRegex(TypeError,'L3'):
                retire(self._context(project),source,target,hashlib.sha256(raw).hexdigest())

    def test_current_stage_working_json_is_retired_to_recycle_bin(self):
        from storyboard_lifecycle import retire
        with tempfile.TemporaryDirectory() as td:
            project=Path(td)
            source=project/'03初步分镜'/'分镜拆分'/'EP001.json'
            target=project/'04分镜定稿'/'EP001'/'episode.json'
            source.parent.mkdir(parents=True); target.parent.mkdir(parents=True)
            raw=b'{"episode_id":"EP001"}'; source.write_bytes(raw); target.write_bytes(raw)
            import hashlib
            retire(self._context(project),source,target,hashlib.sha256(raw).hexdigest(), publish=lambda path, data: path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8'))
            self.assertFalse(source.exists())
            manifests=list((project/'工作流任务'/'回收站').glob('*/恢复位置.json'))
            self.assertEqual(len(manifests),1)
            record=json.loads(manifests[0].read_text(encoding='utf-8'))
            self.assertEqual(record['reason'],'定稿替换原始分镜')
            self.assertTrue((project/record['items'][0]['recycle_path']).is_file())


class WorkingEpisodeRepairTests(unittest.TestCase):
    """第 62 期任务 7：强制关闭后重开，工作集指针歪了要拉回来。"""

    def break_pointer(self, proj):
        cfg = proj / "config.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["episode_file"] = str(proj / "episode" / "episode.json")
        data["episode_dir"] = str(proj / "episode")
        cfg.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return cfg

    def test_a_stale_pointer_is_pulled_back_to_the_adopted_storyboard(self):
        from storyboard_selection import repair_working_episode
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            adopt(proj, ["storyboard/分镜拆分/episode.json"])
            cfg = self.break_pointer(proj)          # 崩在 adopt() 与 sync_working_episode() 之间
            target = repair_working_episode(proj)
            self.assertIsNotNone(target, "指针歪了就应该被拉回")
            self.assertEqual(json.loads(cfg.read_text(encoding="utf-8"))["episode_file"], str(target))

    def test_an_aligned_pointer_is_left_alone(self):
        from storyboard_selection import adopted, repair_working_episode
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            adopt(proj, ["storyboard/分镜拆分/episode.json"])
            target = adopted(proj)[-1]
            cfg = proj / "config.json"
            data = json.loads(cfg.read_text(encoding="utf-8"))
            data["episode_file"] = str(target); data["episode_dir"] = str(target.parent)
            cfg.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            self.assertIsNone(repair_working_episode(proj), "没歪就不要动用户的工作集")


class StoryboardBatchTests(unittest.TestCase):
    """第 62 期任务 6：提交前按「集号」去重。

    用户报的是「EP001 分镜生成三份，agent 没有自动停止」——同一集选了好几份草稿时，
    每一份各派一项，agent 每一集都照着写一遍。去重必须先于派单落地，不能只写在给 agent 的说明里。
    """

    def drafts(self, proj, *names):
        folder = proj / "writing"; folder.mkdir(parents=True, exist_ok=True)
        made = []
        for name in names:
            path = folder / name
            path.write_text("# 第01集 剧本", encoding="utf-8")
            made.append(path)
        return made

    def payload(self, prompt):
        """任务书末尾那份 JSON 才是真正的派单清单，直接拆出来数项数。"""
        return json.loads(prompt.split("不是额外的工具操作指令：\n", 1)[1])

    def test_three_drafts_of_one_episode_are_one_task(self):
        from workflow_tasks import storyboard_batch_prompt
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            # 这一集还没分镜：先挪开夹具自带的那份 EP001，单看「三份草稿」这一条
            (proj / "storyboard" / "分镜拆分" / "episode.json").unlink()
            scripts = self.drafts(proj, "第01集_初稿.md", "第01集_修订.md", "第01集_终稿.md")
            prompt, _followup = storyboard_batch_prompt(proj, scripts, [])
            data = self.payload(prompt)
            self.assertEqual(len(data["tasks"]), 1, "同一集只派一项")
            self.assertEqual(len(data["skipped_completed"]), 2, "其余两份写进跳过列表")
            self.assertIn(data["tasks"][0]["source_script"], [str(p.resolve()) for p in scripts])

    def test_each_episode_gets_its_own_task(self):
        from workflow_tasks import storyboard_batch_prompt
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            scripts = self.drafts(proj, "第02集.md", "第03集.md")
            prompt, _followup = storyboard_batch_prompt(proj, scripts, [])
            self.assertEqual(len(self.payload(prompt)["tasks"]), 2)
            self.assertIn("只有你一个 agent", prompt, "一个 agent 顺序做，不开并行子任务")

    def test_an_episode_that_already_has_a_storyboard_is_not_resubmitted(self):
        from workflow_tasks import storyboard_batch_prompt
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)          # 分镜拆分里已经有 episode.json（episode_id=EP001）
            scripts = self.drafts(proj, "第01集_初稿.md")
            with self.assertRaises(ValueError):
                storyboard_batch_prompt(proj, scripts, [])


class DesktopModelPoolTests(unittest.TestCase):
    """阶段配置选择桌面模型时，真正切换调用引擎而不是只显示一个名字。"""

    def test_native_claude_uses_saved_application_path(self):
        import workflow_settings
        import stage_config
        import model_pool
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            stage_config.put(proj, 'script', model='claude-desktop-app')
            records = model_pool.default_pool()
            records['claude-desktop-app']['program'] = str(Path(td) / 'Claude.exe')
            with patch('model_pool.pool', return_value=records):
                config = workflow_settings.current(proj, 'writing')
            self.assertEqual(config['engine'], 'claude-desktop-app')
            self.assertEqual(workflow_settings.find_program(config), records['claude-desktop-app']['program'])

    def test_native_claude_never_falls_back_to_code_cli(self):
        import os
        import workflow_settings
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {'LOCALAPPDATA': td}), \
                patch('workflow_settings.shutil.which', return_value='claude-code.exe') as cli:
            with self.assertRaisesRegex(ValueError, 'Claude Desktop'):
                workflow_settings.find_program({'engine': 'claude-desktop-app', 'program': ''})
            cli.assert_not_called()

    def test_saved_codex_desktop_path_overrides_old_cli_profile(self):
        import stage_config
        import model_pool
        import workflow_settings
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            stage_config.put(proj, 'script', model='chatgpt-desktop')
            records = model_pool.default_pool()
            records['chatgpt-desktop']['program'] = str(Path(td) / 'Codex.exe')
            profile = workflow_settings.defaults('writing')
            profile['profiles']['codex']['model'] = 'old-cli-model'
            with patch('model_pool.pool', return_value=records), patch('workflow_settings.load', return_value=profile):
                config = workflow_settings.current(proj, 'writing')
            self.assertEqual(config['desktop_program'], records['chatgpt-desktop']['program'])
            self.assertEqual(config['program'], '')
            self.assertEqual(config['model'], '')

    def test_native_claude_pastes_full_task_without_cli_or_auto_send(self):
        from desktop import Desktop
        from types import SimpleNamespace
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            desktop = SimpleNamespace(root=proj, worker=False, win=Mock(), status=Mock(),
                projects=SimpleNamespace(info={'projects': []}), async_=lambda fn, done: done(fn()))
            config = {'engine': 'claude-desktop-app', 'program': 'C:/Apps/Claude.exe', 'model': ''}
            with patch('agent_dispatch.claim', return_value={'duplicate': False}), \
                    patch('agent_dispatch.finish') as finish, \
                    patch('prompt_window.copy_text') as copy, \
                    patch('platform_tools.launch_windows_app') as launch, \
                    patch('codex_paste.paste_existing', return_value={'ok': True, 'reason': '已粘贴'}) as paste, \
                    patch('workflow_engines.launch_interactive') as cli, \
                    patch('codex_tasks.prepare_task') as codex:
                Desktop.open_flow_agent(desktop, 'writing', '提取', '提取简报', _config=config, intake_only=True)
            launch.assert_called_once_with('C:/Apps/Claude.exe', 'Claude Desktop')
            clipboard_text = copy.call_args.args[1]
            self.assertEqual(clipboard_text, '提取简报')
            tasks = list((proj / '工作流任务' / 'writing').glob('*.md'))
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0].read_text(encoding='utf-8'), '提取简报')
            self.assertEqual(clipboard_text, tasks[0].read_text(encoding='utf-8'))
            paste.assert_called_once_with(proj.name + ' 提取', clipboard_text, program='C:/Apps/Claude.exe', deadline_seconds=45)
            cli.assert_not_called()
            codex.assert_not_called()
            self.assertEqual(finish.call_args.args[1], 'prepared')

    def test_native_claude_writing_pastes_contract_and_skill_reference_not_skill_body(self):
        from desktop import Desktop
        from types import SimpleNamespace
        from unittest.mock import Mock
        from workflow_settings import stage_output_contract
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            skill = Path(td) / 'test.skill.md'
            skill.write_text('---\nname: test-writing\n---\nSKILL_BODY_NOT_INLINED', encoding='utf-8')
            desktop = SimpleNamespace(root=proj, worker=False, win=Mock(), status=Mock(),
                projects=SimpleNamespace(info={'projects': []}), async_=lambda fn, done: done(fn()))
            config = {'engine': 'claude-desktop-app', 'program': 'C:/Apps/Claude.exe',
                      'model': '', 'stage_skills': [str(skill)]}
            with patch('agent_dispatch.claim', return_value={'duplicate': False}), \
                    patch('agent_dispatch.finish'), \
                    patch('prompt_window.copy_text') as copy, \
                    patch('platform_tools.launch_windows_app'), \
                    patch('codex_paste.paste_existing', return_value={'ok': True, 'reason': '已粘贴'}) as paste:
                Desktop.open_flow_agent(desktop, 'writing', '创作', '用户本轮创作要求', _config=config)
            tasks = list((proj / '工作流任务' / 'writing').glob('*.md'))
            self.assertEqual(len(tasks), 1)
            text = copy.call_args.args[1]
            self.assertEqual(text, tasks[0].read_text(encoding='utf-8'))
            self.assertIn('用户本轮创作要求', text)
            self.assertIn(stage_output_contract('writing'), text)
            self.assertIn(str(skill), text)
            self.assertNotIn('SKILL_BODY_NOT_INLINED', text)
            paste.assert_called_once_with(proj.name + ' 创作', text,
                                          program='C:/Apps/Claude.exe', deadline_seconds=45)

    def test_stage_model_selects_the_matching_desktop_agent(self):
        import stage_config
        import workflow_settings
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            stage_config.put(proj, 'script', model='claude-desktop')
            config = workflow_settings.current(proj, 'writing')
            self.assertEqual(config['engine'], 'claude')
            self.assertTrue(workflow_settings.effective_model(proj, 'writing').startswith(
                            'Claude Code'),
                            '桌面模型名称保持不变，未安装时仅追加状态标注')
            stage_config.put(proj, 'script', model='chatgpt-desktop')
            self.assertEqual(workflow_settings.current(proj, 'writing')['engine'], 'codex')

    def test_claude_stage_configuration_stays_claude_when_read_again(self):
        """重试前后读取同一阶段配置，不能悄悄回退到默认 Codex。"""
        import stage_config
        import workflow_settings
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            stage_config.put(proj, 'script', model='claude-desktop')
            first = workflow_settings.current(proj, 'writing')
            again = workflow_settings.current(proj, 'writing')
            self.assertEqual(first['engine'], 'claude')
            self.assertEqual(again['engine'], 'claude')

    def test_selected_uninstalled_desktop_model_keeps_its_config_and_execution_error(self):
        """展示标注不得改写已选模型，也不得吞掉原有受控启动错误。"""
        import stage_config
        import workflow_engines
        import workflow_settings
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            stage_config.put(proj, 'script', model='chatgpt-desktop')
            self.assertEqual(workflow_settings.current(proj, 'writing')['engine'], 'codex')
            self.assertEqual(stage_config.get(proj, 'script')['model'], 'chatgpt-desktop')
            with patch.object(workflow_engines, 'find_program', side_effect=ValueError('未找到 ChatGPT / Codex 命令行程序')):
                with self.assertRaisesRegex(ValueError, '未找到 ChatGPT / Codex'):
                    workflow_engines.launch_interactive(proj, 'writing', '标题', '提示词', {'engine': 'codex'})

    def test_unexpected_stage_config_error_is_not_silently_routed_to_default_engine(self):
        """配置读取损坏必须可见，不能悄悄继续使用默认引擎。"""
        import stage_config
        import workflow_settings
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            stage_config.put(proj, 'script', model='gpt-4o')
            config_path = proj / 'skill_config.json'
            before = config_path.read_bytes()
            with patch.object(stage_config, 'get', side_effect=RuntimeError('stage config unavailable')):
                with self.assertRaisesRegex(RuntimeError, 'stage config unavailable'):
                    workflow_settings.current(proj, 'writing')
            self.assertEqual(config_path.read_bytes(), before)

    def test_unexpected_model_pool_error_is_not_silently_routed_or_written(self):
        """模型池自身故障必须保留给调用方，不能被误当作 API 回退。"""
        import model_pool
        import stage_config
        import workflow_settings
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            stage_config.put(proj, 'script', model='gpt-4o')
            config_path = proj / 'skill_config.json'
            before = config_path.read_bytes()
            with patch.object(model_pool, 'pool', side_effect=RuntimeError('model pool unavailable')):
                with self.assertRaisesRegex(RuntimeError, 'model pool unavailable'):
                    workflow_settings.current(proj, 'writing')
            self.assertEqual(config_path.read_bytes(), before)

    def test_openai_api_model_prefers_the_available_local_codex_client(self):
        """同厂商本机客户端存在时先走它；API 只保存为启动失败时的兼容回退。"""
        import stage_config
        import workflow_settings
        import model_pool
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            stage_config.put(proj, 'script', model='gpt-4o')
            original = workflow_settings.find_program
            original_pool = model_pool.pool
            workflow_settings.find_program = lambda cfg: 'C:/Apps/codex.exe' if cfg['engine'] == 'codex' else original(cfg)
            self.addCleanup(setattr, workflow_settings, 'find_program', original)
            model_pool.pool = lambda config=None, program=None: model_pool.default_pool()
            self.addCleanup(setattr, model_pool, 'pool', original_pool)
            config = workflow_settings.current(proj, 'writing')
            self.assertEqual(config['engine'], 'codex')
            self.assertEqual(config['program'], 'C:/Apps/codex.exe')
            self.assertEqual(config['model'], '')
            self.assertEqual(config['api_fallback']['model'], 'gpt-4o')

    def test_openai_api_model_uses_configured_api_when_local_client_is_absent(self):
        import stage_config
        import workflow_settings
        import model_pool
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            stage_config.put(proj, 'script', model='gpt-4o')
            config_path = proj / 'skill_config.json'
            before = config_path.read_bytes()
            with patch.object(workflow_settings, 'find_program', side_effect=ValueError('not installed')), \
                    patch.object(model_pool, 'pool', return_value=model_pool.default_pool()):
                config = workflow_settings.current(proj, 'writing')
            self.assertEqual(config['engine'], 'qwen')
            self.assertEqual(config['model'], 'gpt-4o')
            self.assertEqual(config['api']['base_url'], 'https://api.openai.com/v1')
            self.assertEqual(config_path.read_bytes(), before)

    def test_unexpected_local_program_error_is_not_silently_routed_or_written(self):
        """仅“未安装”可回退；探测器故障不得默默改成 API 引擎。"""
        import model_pool
        import stage_config
        import workflow_settings
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            stage_config.put(proj, 'script', model='gpt-4o')
            config_path = proj / 'skill_config.json'
            before = config_path.read_bytes()
            with patch.object(workflow_settings, 'find_program', side_effect=RuntimeError('probe unavailable')), \
                    patch.object(model_pool, 'pool', return_value=model_pool.default_pool()):
                with self.assertRaisesRegex(RuntimeError, 'probe unavailable'):
                    workflow_settings.current(proj, 'writing')
            self.assertEqual(config_path.read_bytes(), before)

    def test_desktop_route_notice_only_describes_available_gpt_or_anthropic_api_without_writing(self):
        import stage_config
        import workflow_settings
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            stage_config.put(proj, 'script', model='gpt-4o')
            saved = (proj / 'skill_config.json').read_bytes()
            with patch.object(workflow_settings, 'find_program', return_value='C:/Apps/codex.exe'):
                notice = workflow_settings.desktop_route_notice(proj, 'writing', 'gpt-4o')
            self.assertIn('本机 GPT 程序', notice)
            self.assertIn('回落到所选 API', notice)
            self.assertEqual((proj / 'skill_config.json').read_bytes(), saved)
            with patch.object(workflow_settings, 'find_program', side_effect=ValueError('not installed')):
                self.assertEqual(workflow_settings.desktop_route_notice(proj, 'writing', 'gpt-4o'), '')
            self.assertEqual(workflow_settings.desktop_route_notice(
                proj, 'writing', 'deepseek-v4-flash'), '')
            anthropic = {'model': 'claude-opus-test', 'provider': 'anthropic'}
            with patch.object(workflow_settings, 'find_program', return_value='C:/Apps/claude.exe'):
                self.assertIn('本机 Claude 程序', workflow_settings.desktop_route_notice(
                    proj, 'writing', 'claude-api-test', anthropic))

    def test_deepseek_api_model_never_falls_back_to_codex(self):
        """阶段配置显示 DeepSeek 时，三虎派发必须使用同一条兼容 API。"""
        import stage_config
        import workflow_settings
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            stage_config.put(proj, 'storyboard', model='deepseek-v4-flash')
            config = workflow_settings.current(proj, 'storyboard')
            self.assertEqual(config['engine'], 'qwen')
            self.assertEqual(config['model'], 'deepseek-v4-flash')
            self.assertEqual(config['api']['base_url'], 'https://api.deepseek.com')
            self.assertEqual(workflow_settings.effective_model(proj, 'storyboard'),
                             'deepseek-v4-flash')

    def test_summary_uses_the_same_stage_model_route_as_dispatch(self):
        import stage_config
        import workflow_settings
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            stage_config.put(proj, 'storyboard', model='deepseek-v4-flash')
            self.assertIn('Qwen Code（阿里云） · deepseek-v4-flash',
                          workflow_settings.summary(proj, 'storyboard'))

    def test_auto_stage_button_names_the_actual_dispatch_engine(self):
        """“自动”不能把实际会启动的 Codex 藏在泛化的“阶段配置”文案后。"""
        from types import SimpleNamespace
        import skill_panel
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            desktop = SimpleNamespace(root=proj, app=None, pet=None)
            self.assertEqual(skill_panel.stage_button_label(desktop, 'storyboard'), 'Codex')

    def test_chat_creative_is_sent_without_creating_a_script_file(self):
        """点击发送只把聊天创意交给工作流；剧本文档留到模型回复后下载时再写。"""
        from workflow_tasks import script_followup, script_prompt
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            creative = '少年在照相馆发现一张会说话的旧底片。'
            prompt = script_prompt(proj, None, 'writing', creative_text=creative)
            followup = script_followup(None, 'writing', project=proj, creative_text=creative)
            self.assertIn(creative, prompt)
            self.assertIn(creative, followup)
            self.assertLess(len(followup), len(prompt))
            self.assertIn('尚未保存为剧本文件', prompt)
            self.assertIn('script_raw.md', prompt)
            self.assertIn('内部工作稿 `script_raw.md` 可继续更新', prompt)
            self.assertIn('回复由应用按既有分类保存规则落盘', prompt)
            self.assertEqual(list((proj / 'writing').glob('创意_*/*.md')), [])


class WorkflowContextBudgetTests(unittest.TestCase):
    def test_prepared_budget_reports_summary_strategy_without_prompt_text(self):
        from workflow_context_budget import prepare_request_context, REQUEST_CONTEXT_MAX_CHARS
        prompt, budget = prepare_request_context('分镜任务', '初步分镜', 'stage_summary')
        self.assertEqual(prompt, '分镜任务')
        self.assertEqual(budget, {
            'stage': '初步分镜', 'strategy': 'stage_summary',
            'characters': len(prompt), 'limit': REQUEST_CONTEXT_MAX_CHARS,
            'remaining': REQUEST_CONTEXT_MAX_CHARS - len(prompt),
        })
        self.assertNotIn('分镜任务', str(budget))

    def test_repeated_large_context_is_compacted_before_budget_check(self):
        from workflow_context_budget import (REQUEST_CONTEXT_MAX_CHARS,
                                             ensure_request_context)
        section = '镜头连续性资料。' * 7_000
        compact = ensure_request_context(
            '任务说明\n\n' + section + '\n\n' + section, '初步分镜')
        self.assertLess(len(compact), REQUEST_CONTEXT_MAX_CHARS)
        self.assertEqual(compact.count(section), 1)
        self.assertIn('上下文去重摘要', compact)

    def test_codex_task_writer_rejects_oversized_prompt_before_creating_artifacts(self):
        """桌面内置 Codex 路径也必须在写入任务书或连接 RPC 前预检。"""
        import codex_tasks
        from workflow_context_budget import REQUEST_CONTEXT_MAX_CHARS
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'p'
            with self.assertRaisesRegex(ValueError, '剧本准备请求上下文超过'):
                codex_tasks.prepare_task(
                    project, '测试任务', '剧本准备',
                    'x' * (REQUEST_CONTEXT_MAX_CHARS + 1))
            self.assertFalse((project / '工作流任务').exists())
            self.assertFalse((project / 'codex_tasks.json').exists())

    def test_background_engine_rejects_oversized_prompt_before_launch(self):
        import workflow_engines
        from workflow_context_budget import REQUEST_CONTEXT_MAX_CHARS
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'p'
            with self.assertRaisesRegex(ValueError, '初步分镜请求上下文超过'):
                workflow_engines.run_background(
                    {'engine': 'qwen', 'stage': '初步分镜'}, project, project / 'out',
                    project / 'report.txt', project / 'log.txt', 'x' * (REQUEST_CONTEXT_MAX_CHARS + 1))

    def test_interactive_engine_rejects_oversized_prompt_before_launch(self):
        import workflow_engines
        from workflow_context_budget import REQUEST_CONTEXT_MAX_CHARS
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'p'
            with self.assertRaisesRegex(ValueError, '初步分镜请求上下文超过'):
                workflow_engines.launch_interactive(
                    project, '初步分镜', '测试任务', 'x' * (REQUEST_CONTEXT_MAX_CHARS + 1),
                    {'engine': 'qwen'})

    def test_interactive_engine_uses_platform_process_boundary(self):
        import workflow_engines
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            executable = project / 'codex.exe'
            executable.write_bytes(b'')
            class Process:
                pass
            process = Process()
            with patch.object(workflow_engines, 'find_program', return_value=str(executable)), \
                 patch.object(workflow_engines, 'launch_windows_app', return_value=process) as launch, \
                 patch('codex_tasks.prepare_task', return_value={'mode': 'new', 'prompt': '开始'}):
                result = workflow_engines.launch_interactive(
                    project, 'writing', '标题', '提示词', {'engine': 'codex'})
            self.assertIs(result['process'], process)
            self.assertEqual(launch.call_args.args, (str(executable), workflow_engines.ENGINES['codex']))
            self.assertEqual(launch.call_args.kwargs['cwd'], project)
            self.assertEqual(launch.call_args.kwargs['args'][:1], [str(executable)])
            from workflow_process_registry import forget_process
            forget_process(project, process)


if __name__ == "__main__":
    unittest.main(verbosity=2)
