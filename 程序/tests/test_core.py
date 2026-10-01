# -*- coding: utf-8 -*-
"""核心逻辑自检（纯逻辑，不依赖网络与外部工具）。运行：python test_core.py"""
import json, os, sys, tempfile, unittest
from unittest import mock
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import writing
import projects as projects_mod
import engine as engine_mod
import storyboard_files as sf
import storyboard_storage as sstorage
import seedream_api
import workflow_settings as ws
from desktop import Desktop
from agent.core import read, save, file_hash


def valid_episode(n=1, start=1):
    shots = []
    for i in range(n):
        sid = f"SH{start + i:03d}"
        shots.append({"id": sid, "title": "镜头", "duration": 5,
                      "characters": ["CHAR_001"], "location": "LOC_001",
                      "frame": f"frames/{sid}.png", "video_prompt": "画面与对白要求", "dialogue": []})
    return {"episode_id": "EP001", "title": "测试集", "shots": shots}


class WritingTests(unittest.TestCase):
    def test_relative_ok(self):
        self.assertEqual(writing.relative("frames/SH001.png").as_posix(), "frames/SH001.png")

    def test_relative_reject_absolute(self):
        with self.assertRaises(ValueError):
            writing.relative("D:/x/frames/SH001.png")

    def test_relative_reject_dotdot(self):
        with self.assertRaises(ValueError):
            writing.relative("../frames/SH001.png")

    def test_relative_reject_empty(self):
        with self.assertRaises(ValueError):
            writing.relative("")


class ResidualProjectTests(unittest.TestCase):
    def test_missing_episode_error_is_not_misclassified_as_deleted_project(self):
        error=ValueError('项目里找不到镜头 JSON（episode.json）：D:/项目/episode.json')
        self.assertFalse(projects_mod.needs_cleanup_after_open_error(error))
        self.assertTrue(projects_mod.is_missing_storyboard_open_error(error))

    def test_missing_project_directory_still_goes_to_cleanup(self):
        error=ValueError('项目目录不存在或已被移动：D:/项目')
        self.assertTrue(projects_mod.needs_cleanup_after_open_error(error))
        self.assertFalse(projects_mod.is_missing_storyboard_open_error(error))

    def test_other_open_error_is_not_misclassified_as_missing_storyboard(self):
        self.assertFalse(projects_mod.needs_cleanup_after_open_error(ValueError('权限不足')))

    def test_script_stage_project_loads_without_storyboard_json(self):
        """剧本阶段还没有分镜时，Desktop.load 只能延迟 Studio，不能阻止进入项目。"""
        with tempfile.TemporaryDirectory() as td:
            project=Path(td)
            (project/'config.json').write_text('{}',encoding='utf-8')
            desk=Desktop.__new__(Desktop)
            desk.flush_brief=lambda:None
            desk.projects=type('Projects',(),{'activate':lambda self,path:None})()
            desk.list=type('ProjectList',(),{'selection_set':lambda self,path:None,
                                              'see':lambda self,path:None})()
            desk.show=lambda page:None
            desk.sync_stage_models=lambda:None
            desk._schedule_stage_model_sync=lambda project:None
            desk.import_generated_assets=lambda:None
            desk.prune_asset_leftovers=lambda:None
            desk.restore_asset_resume=lambda:None
            with mock.patch('desktop.open_studio',side_effect=ValueError(
                    '项目里找不到镜头 JSON（episode.json）：'+str(project/'episode.json'))):
                desk.load(project)
            self.assertEqual(desk.root,project)
            self.assertIsNone(desk.studio)

    def test_asset_cleanup_failure_does_not_block_opening_but_is_visible(self):
        """打开项目后的可选清理失败不能伪装成“没有重复原图”。"""
        desk=Desktop.__new__(Desktop)
        desk.root=Path(tempfile.gettempdir())
        desk.asset_base=lambda:Path(tempfile.gettempdir())
        desk.status=type('Status',(),{'value':'', 'set':lambda self,value:setattr(self,'value',value)})()
        with mock.patch('asset_batch_state_service.prune_raw_outputs',side_effect=OSError('回收站不可写')):
            self.assertEqual(desk.prune_asset_leftovers(),[])
        self.assertIn('重复原始取回图未清理',desk.status.value)

    def test_generated_asset_check_failure_is_visible_without_blocking_open(self):
        """启动后的可选生成图检查失败不能静默成“没有待导入图片”。"""
        desk=Desktop.__new__(Desktop)
        desk.root=Path(tempfile.gettempdir())
        desk.asset_base=lambda:Path(tempfile.gettempdir())
        desk.status=type('Status',(),{'value':'', 'set':lambda self,value:setattr(self,'value',value)})()
        with mock.patch('asset_generated_import_service.pending_generated',side_effect=OSError('生成目录不可读')):
            self.assertIsNone(desk.import_generated_assets())
        self.assertIn('生成资产检查未完成',desk.status.value)

    def test_generated_asset_import_queue_failure_is_visible(self):
        """发现待导入图片后，后台任务排队失败也不能静默。"""
        desk=Desktop.__new__(Desktop)
        desk.root=Path(tempfile.gettempdir())
        desk.asset_base=lambda:Path(tempfile.gettempdir())
        desk.async_=mock.Mock(side_effect=RuntimeError('后台队列已关闭'))
        desk.status=type('Status',(),{'value':'', 'set':lambda self,value:setattr(self,'value',value)})()
        with mock.patch('asset_generated_import_service.pending_generated',return_value=['待导入.png']):
            self.assertIsNone(desk.import_generated_assets())
        self.assertIn('生成资产导入未启动',desk.status.value)

    def test_asset_resume_read_failure_is_visible_without_blocking_open(self):
        """续跑台账读坏时仍可打开项目，但不能伪装成没有待续跑任务。"""
        desk=Desktop.__new__(Desktop)
        desk.root=Path(tempfile.gettempdir())
        desk.status=type('Status',(),{'value':'', 'set':lambda self,value:setattr(self,'value',value)})()
        with mock.patch('desktop.asset_resume.attempts',side_effect=OSError('续跑台账不可读')):
            self.assertIsNone(desk.restore_asset_resume())
        self.assertEqual(desk.auto_asset_attempt,0)
        self.assertIn('自动补资产续跑记录未恢复',desk.status.value)

    def test_stage_model_sync_failure_is_visible_without_blocking_open(self):
        """启动后的模型对账失败不能被误判为项目没有可同步模型。"""
        desk=Desktop.__new__(Desktop)
        desk.root=Path(tempfile.gettempdir())
        desk._stage_model_sync_generation=0
        desk._stage_model_sync_results=__import__('queue').Queue()
        desk.status=type('Status',(),{'value':'', 'set':lambda self,value:setattr(self,'value',value)})()
        with mock.patch('skill_panel.program_of',return_value=object()), \
             mock.patch('skill_panel.sync_models',side_effect=OSError('模型配置不可读')), \
             mock.patch('desktop.threading.Thread',side_effect=lambda *,target,daemon:type('Immediate',(),{'start':staticmethod(target)})()):
            self.assertIsNone(desk._schedule_stage_model_sync(desk.root))
        desk._tick_stage_model_sync_result()
        self.assertIn('项目模型同步未完成',desk.status.value)

    def test_legacy_adoption_record_failure_is_visible(self):
        """旧目录已归位但审计记录未写入，不能静默伪装为可追溯。"""
        desk=Desktop.__new__(Desktop)
        desk.root=Path(tempfile.gettempdir())
        desk.status=type('Status',(),{'value':'', 'set':lambda self,value:setattr(self,'value',value)})()
        with mock.patch('legacy_adoption_service.record_legacy_adoption',side_effect=OSError('归档目录不可写')):
            self.assertIsNone(desk.record_legacy_adoption([desk.root/'writing']))
        self.assertIn('旧目录归位记录未写入',desk.status.value)


class DailyProjectChoiceTests(unittest.TestCase):
    def test_today_choice_is_saved_and_returned_without_touching_project_files(self):
        with tempfile.TemporaryDirectory() as td:
            app=Path(td);choice=app/'当日项目';choice.mkdir()
            desk=Desktop.__new__(Desktop)
            desk.settings_file=app/'desktop_settings.json';desk.settings={}
            desk.projects=type('Registry',(),{'info':{'projects':[{'path':str(choice)}]}})()
            desk.remember_daily_project_choice(choice)
            self.assertEqual(desk.daily_project_choice(),str(choice))
            self.assertEqual(read(desk.settings_file)['project_choice_path'],str(choice))

    def test_deleted_or_unregistered_choice_is_not_reopened(self):
        with tempfile.TemporaryDirectory() as td:
            app=Path(td);choice=app/'已删除项目'
            desk=Desktop.__new__(Desktop)
            desk.settings_file=app/'desktop_settings.json'
            desk.settings={'project_choice_day':__import__('datetime').date.today().isoformat(),
                           'project_choice_path':str(choice)}
            desk.projects=type('Registry',(),{'info':{'projects':[]}})()
            self.assertIsNone(desk.daily_project_choice())

    def test_sidebar_open_remembers_today_choice_after_successful_load(self):
        with tempfile.TemporaryDirectory() as td:
            choice=Path(td)/'侧栏项目';choice.mkdir()
            desk=Desktop.__new__(Desktop)
            desk.load=mock.Mock()
            desk.remember_daily_project_choice=mock.Mock()
            self.assertTrue(desk.open_project_or_cleanup(choice))
            desk.load.assert_called_once_with(choice)
            desk.remember_daily_project_choice.assert_called_once_with(choice)

    def test_main_window_can_clear_a_missing_project_registration_without_recycling(self):
        with tempfile.TemporaryDirectory() as td:
            missing=Path(td)/'已移走项目'
            desk=Desktop.__new__(Desktop)
            desk.root=None;desk.reload=mock.Mock()
            desk.status=type('Status',(),{'set':mock.Mock()})()
            desk.projects=type('Registry',(),{'clear_missing_registration':mock.Mock()})()
            self.assertTrue(desk.clear_missing_project({'path':str(missing)},confirmed=True))
            desk.projects.clear_missing_registration.assert_called_once_with(str(missing))
            desk.reload.assert_called_once()

    def test_missing_project_registration_write_failure_is_visible(self):
        """清理登记写盘失败不可静默；两个入口共用的桌面方法须留下可重试提示。"""
        with tempfile.TemporaryDirectory() as td:
            missing=Path(td)/'已移走项目'
            desk=Desktop.__new__(Desktop)
            desk.root=None;desk.reload=mock.Mock()
            desk.status=type('Status',(),{'set':mock.Mock()})()
            desk.projects=type('Registry',(),{'clear_missing_registration':mock.Mock(side_effect=OSError('访问被拒绝'))})()
            self.assertFalse(desk.clear_missing_project({'path':str(missing)},confirmed=True))
            desk.reload.assert_not_called()
            desk.status.set.assert_called_once_with('清除失效项目登记失败，请稍后重试：访问被拒绝')

    def test_auto_gate_write_failure_is_not_silently_swallowed(self):
        """自动采用失败必须交给调度器显示和节流，不能假装该条已处理。"""
        import stage_flow
        desk=Desktop.__new__(Desktop)
        desk.root=Path(tempfile.gettempdir())
        desk.gate_level=lambda:next(iter(stage_flow.AUTO_LEVELS))
        desk.pending_gate_asks=lambda:[{'key':'G-05','candidates':['候选'], 'recommended':0}]
        with mock.patch('asset_plan.apply_gate_choice',side_effect=OSError('磁盘已满')):
            with self.assertRaisesRegex(OSError,'磁盘已满'):
                desk.auto_decide_gates()

    def test_auto_gate_scheduler_failure_is_visible_and_retryable(self):
        """门禁自动写入失败有明确状态，且仍沿用既有 20 秒节流重试。"""
        class Scheduler:
            def run_due(self,**kwargs):
                try:kwargs['poll']()
                except kwargs['handled_exceptions'] as exc:
                    kwargs['on_error'](exc)
                return False
        desk=Desktop.__new__(Desktop)
        desk.root=Path(tempfile.gettempdir());desk.gate_auto_due=0;desk.gate_auto_error=''
        desk.automation_scheduler=Scheduler();desk.auto_decide_gates=mock.Mock(side_effect=OSError('磁盘已满'))
        desk.status=type('Status',(),{'set':mock.Mock()})()
        desk._tick_auto_gates()
        self.assertEqual(desk.gate_auto_error,'磁盘已满')
        desk.status.set.assert_called_once_with('自动处理待办暂缓（将在约 20 秒后重试）：磁盘已满')

    def test_desktop_pet_report_failure_is_not_silently_swallowed(self):
        """阶段报告器故障不能伪装成已完成。"""
        desk=Desktop.__new__(Desktop)
        desk.pet=type('Pet',(),{'report_done':mock.Mock(side_effect=RuntimeError('总线不可用'))})()
        with self.assertRaisesRegex(RuntimeError,'总线不可用'):
            desk.pet_report('keyframe','首帧完成')

    def test_pet_ui_report_done_failure_is_not_silently_swallowed(self):
        """异步首帧接缝使用的适配器也不能吞掉报告器故障。"""
        import pet_ui
        host=type('Host',(),{'pet_report':mock.Mock(side_effect=RuntimeError('总线不可用'))})()
        with self.assertRaisesRegex(RuntimeError,'总线不可用'):
            pet_ui.report_done(host,'keyframe','首帧完成')

    def test_validate_valid(self):
        with tempfile.TemporaryDirectory() as td:
            r = writing.validate_episode(valid_episode(), td, {"CHAR_001": {}, "LOC_001": {}})
            self.assertEqual(r["shot_count"], 1)

    def test_validate_bad_duration(self):
        with tempfile.TemporaryDirectory() as td:
            ep = valid_episode(); ep["shots"][0]["duration"] = 1
            with self.assertRaises(ValueError):
                writing.validate_episode(ep, td, None)

    def test_validate_duplicate_id(self):
        with tempfile.TemporaryDirectory() as td:
            ep = valid_episode(2); ep["shots"][1]["id"] = "SH001"
            with self.assertRaises(ValueError):
                writing.validate_episode(ep, td, None)

    def test_validate_missing_asset(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                writing.validate_episode(valid_episode(), td, {"CHAR_001": {}})

    def test_validate_non_string_speaker_no_crash(self):
        with tempfile.TemporaryDirectory() as td:
            ep = valid_episode()
            ep["shots"][0]["dialogue"] = [{"speaker": 123, "text": "你好"}]
            r = writing.validate_episode(ep, td, {"CHAR_001": {}, "LOC_001": {}})
            self.assertEqual(r["shot_count"], 1)


class SeedreamTests(unittest.TestCase):
    def test_validate_ok(self):
        v = seedream_api.validate("https://ark.cn-beijing.volces.com/api/v3", "doubao-seedream", "sk-abc123")
        self.assertEqual(v["base_url"], "https://ark.cn-beijing.volces.com/api/v3")

    def test_validate_http_rejected(self):
        with self.assertRaises(ValueError):
            seedream_api.validate("http://ark.cn-beijing.volces.com/api/v3", "m", "sk-abc123")

    def test_validate_bad_key(self):
        with self.assertRaises(ValueError):
            seedream_api.validate("https://ark.cn-beijing.volces.com/api/v3", "m", "")

    def test_validate_bad_model(self):
        with self.assertRaises(ValueError):
            seedream_api.validate("https://ark.cn-beijing.volces.com/api/v3", "模型 带空格", "sk-abc123")

    def test_validate_strips_generations_suffix(self):
        v = seedream_api.validate("https://ark.cn-beijing.volces.com/api/v3/images/generations", "m", "sk-abc123")
        self.assertEqual(v["base_url"], "https://ark.cn-beijing.volces.com/api/v3")

    def test_read_settings_corrupt_falls_back(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "seedream_profiles.json"
            p.write_text("{bad json", encoding="utf-8")
            with patch.object(seedream_api, "settings_path", return_value=p):
                self.assertEqual(seedream_api.read_settings(), {"active": "", "profiles": {}})

    def test_read_settings_non_object_falls_back(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "seedream_profiles.json"
            p.write_text("[1,2,3]", encoding="utf-8")
            with patch.object(seedream_api, "settings_path", return_value=p):
                self.assertEqual(seedream_api.read_settings(), {"active": "", "profiles": {}})


class WorkflowSettingsTests(unittest.TestCase):
    def test_defaults_all_stages(self):
        for stage in ws.FLOWS:
            d = ws.defaults(stage)
            self.assertEqual(d["engine"], "codex")
            self.assertEqual(set(d["profiles"]), set(ws.ENGINES))

    def test_writing_output_contract_allows_only_skill_process_documents(self):
        """过程 Markdown 可落 docs/，但不得稀释原稿与结构稿边界。"""
        contract = ws.stage_output_contract('writing')
        self.assertIn('唯一可交付内容是完整的自然语言剧本原稿', contract)
        self.assertIn('剧本正文中禁止出现结构化剧本', contract)
        self.assertIn('角色／场景／道具档案、字段表、JSON／YAML、镜头或分镜表', contract)
        self.assertIn('仍属下一阶段“02剧本结构”', contract)
        self.assertIn('过程文档（分集大纲、情节节点表、节奏／逻辑／合规审查报告、确认清单', contract)
        self.assertIn('docs/ 子目录', contract)
        self.assertIn('不得并入剧本原稿，不得替代“02剧本结构”的结构化剧本', contract)
        self.assertIn('五类 manifest JSON 仍按 script_contract.PRODUCERS 的归属产出，本阶段对话不生成', contract)
        self.assertIn('只返回剧本正文与 SKILL 要求的确认清单，不解释创作过程', contract)
        self.assertNotIn('禁止输出或保存', contract)

    def test_defaults_bad_stage(self):
        with self.assertRaises(ValueError):
            ws.defaults("nope")


class StoryboardStorageTests(unittest.TestCase):
    def test_canonical_name_sanitizes(self):
        self.assertEqual(sstorage.canonical_name({"episode_id": "EP001", "title": "测试集"}), "EP001_测试集_分镜.json")
        # forbidden filename characters are replaced one-to-one
        self.assertEqual(sstorage.canonical_name({"episode_id": "EP002", "title": "测试/集"}), "EP002_测试_集_分镜.json")

    def test_snapshot_rejects_non_storyboard(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.json"; p.write_text(json.dumps({"a": 1}), encoding="utf-8")
            with self.assertRaises(ValueError):
                sstorage.snapshot(p)


class StoryboardPathsTests(unittest.TestCase):
    def test_is_final_dir(self):
        from storyboard_paths import is_final_dir
        self.assertTrue(is_final_dir("定稿_EP001"))
        self.assertTrue(is_final_dir("EP001_分镜定稿_2020"))
        self.assertFalse(is_final_dir("EP001_分镜"))

    def test_media_root_split(self):
        from storyboard_paths import media_root
        self.assertEqual(media_root(Path("D:/p/storyboard/分镜拆分/EP001/episode.json")), Path("D:/p/storyboard"))
        self.assertEqual(media_root(Path("D:/p/03初步分镜/分镜拆分/EP001/episode.json")), Path("D:/p/03初步分镜"))

    def test_storyboard_document_directory_is_separate_from_json_working_directory(self):
        from storyboard_files import document_dir, working_dir
        project=Path('D:/p')
        self.assertEqual(document_dir(project), Path('D:/p/03初步分镜/分镜文档'))
        self.assertEqual(working_dir(project), Path('D:/p/03初步分镜/分镜拆分'))

    def test_media_root_fallback(self):
        from storyboard_paths import media_root
        self.assertEqual(media_root(Path("D:/p/episode/episode.json")), Path("D:/p/episode"))


class StoryboardFilesTests(unittest.TestCase):

    def test_resolve_source_relative(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; (proj / "storyboard" / "分镜拆分").mkdir(parents=True)
            (proj / "storyboard" / "分镜拆分" / "EP001_标题_分镜.json").write_text(json.dumps({"episode_id": "EP001", "shots": []}), encoding="utf-8")
            p = sf.resolve_source(proj, "storyboard/分镜拆分/EP001_标题_分镜.json")
            self.assertTrue(p.is_file())

    def test_resolve_source_episode_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; (proj / "storyboard" / "分镜拆分").mkdir(parents=True)
            (proj / "storyboard" / "分镜拆分" / "EP001_标题_分镜.json").write_text(json.dumps({"episode_id": "EP001", "shots": []}), encoding="utf-8")
            p = sf.resolve_source(proj, "storyboard/episode.json")
            self.assertEqual(p.name, "EP001_标题_分镜.json")

    def test_is_deliverable_storyboard_json(self):
        self.assertTrue(sf.is_deliverable(Path("a.json"), "storyboard"))

    def test_is_deliverable_script_episode(self):
        self.assertTrue(sf.is_deliverable(Path("第3集_剧本.md"), "script"))

    def test_is_deliverable_structured_script(self):
        self.assertTrue(sf.is_deliverable(Path("结构剧本_正稿_20260926.md"), "script"))
        self.assertFalse(sf.is_deliverable(Path("writing/script.md"), "script"))

    def test_is_deliverable_script_idea_rejected(self):
        self.assertFalse(sf.is_deliverable(Path("创意_xx.md"), "script"))

    def test_file_order(self):
        order = sf.file_order(Path("x.json"), {"episode_id": "EP002", "shots": [{"id": "SH003"}, {"id": "SH001"}]})
        self.assertEqual(order[0], 2)
        self.assertEqual(order[1], 1)


class ProjectsEngineTests(unittest.TestCase):
    def test_create_then_open_studio(self):
        with tempfile.TemporaryDirectory() as td:
            t = Path(td); app = t / "app"; app.mkdir()
            (app / "config.json").write_text(json.dumps({"downloads_root": str(t / "downloads")}), encoding="utf-8")
            (app / "projects.json").write_text(json.dumps({"active": None, "projects": []}), encoding="utf-8")
            P = projects_mod.Projects(app)
            p = P.create("测试项目")
            self.assertRegex(p.name, r'^测试项目_\d{8}(?:_\d+)?$')
            self.assertTrue((p / "config.json").is_file())
            self.assertTrue((p / "03初步分镜" / "分镜拆分" / "episode.json").is_file())
            for d in ("01剧本准备", "10配音与字幕", "11后期剪辑", "12质检交付"):
                self.assertTrue((p / d).is_dir(), d)
            st = engine_mod.Studio(p)
            self.assertEqual(len(st.episode["shots"]), 1)
            # registry now has one project
            self.assertEqual(len(P.info["projects"]), 1)

    def test_prepare_task_brief_uses_project_title(self):
        with tempfile.TemporaryDirectory() as td:
            t = Path(td); proj = t / "p"; (proj / "episode").mkdir(parents=True)
            (proj / "episode" / "episode.json").write_text(json.dumps(valid_episode(), ensure_ascii=False), encoding="utf-8")
            (proj / "episode" / "assets.json").write_text("{}", encoding="utf-8")
            (proj / "config.json").write_text(json.dumps({"episode_dir": str(proj / "episode"), "episode_file": str(proj / "episode" / "episode.json")}), encoding="utf-8")
            from stage_execution_service import publish_writing_preparation
            out = writing.prepare(proj, "一个创意", "Step 0 需求整理", 60,
                                  publish=publish_writing_preparation)
            txt = (out / "编剧任务书.md").read_text(encoding="utf-8")
            from project_stages import writing as script_stage
            self.assertEqual(out.parent, script_stage(proj))
            self.assertFalse((proj / 'writing' / out.name).exists())
            self.assertIn("《测试集》", txt)
            self.assertNotIn("摄像头侠", txt)

    def test_projects_corrupt_registry_falls_back(self):
        with tempfile.TemporaryDirectory() as td:
            t = Path(td); app = t / "app"; app.mkdir()
            (app / "config.json").write_text(json.dumps({"downloads_root": str(t / "downloads")}), encoding="utf-8")
            (app / "projects.json").write_text("[]", encoding="utf-8")
            P = projects_mod.Projects(app)
            self.assertEqual(P.info.get("projects"), [])
            self.assertEqual(P.info.get("active"), None)


class AgentCoreTests(unittest.TestCase):
    def test_save_read_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sub" / "x.json"
            save(p, {"a": [1, 2], "b": "中文"})
            self.assertEqual(read(p), {"a": [1, 2], "b": "中文"})

    def test_save_text_replaces_the_whole_document(self):
        """剧本类文本也必须复用 JSON 设置的原子替换语义。"""
        from agent.core import save_text
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "剧本.md"
            target.write_text("旧剧本", encoding="utf-8")
            save_text(target, "新剧本\n第二场")
            self.assertEqual(target.read_text(encoding="utf-8"), "新剧本\n第二场")
            self.assertFalse(Path(str(target) + ".tmp").exists())

    def test_atomic_publish_emits_cache_invalidation(self):
        """原子发布成功后，已缓存的正式成果不能继续留在读取缓存中。"""
        import file_cache
        from agent.core import save_text
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / '剧本.md'
            target.write_text('旧剧本', encoding='utf-8')
            file_cache.read_text(target, encoding='utf-8')
            save_text(target, '新剧本')
            self.assertNotIn((file_cache._key(target), 'utf-8', None), file_cache._TEXT_CACHE)

    def test_save_bytes_replaces_binary_artifact(self):
        from agent.core import save_bytes
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "asset.png"
            save_bytes(target, b'\x89PNG\r\n\x1a\ncontent')
            self.assertEqual(target.read_bytes(), b'\x89PNG\r\n\x1a\ncontent')

    def test_save_bytes_new_never_replaces_existing_artifact(self):
        from agent.core import save_bytes_new
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "frame.png"
            target.write_bytes(b"original")
            with self.assertRaises(FileExistsError):
                save_bytes_new(target, b"replacement")
            self.assertEqual(target.read_bytes(), b"original")
            save_bytes_new(Path(td) / "new.png", b"complete")
            self.assertEqual((Path(td) / "new.png").read_bytes(), b"complete")

    def test_concurrent_saves_use_distinct_temporary_files(self):
        """并发后台任务不能因共享 *.tmp 而互相删掉对方的成果。"""
        from concurrent.futures import ThreadPoolExecutor
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'stage.json'
            def write(index):
                save(target, {'writer': index, 'payload': 'x' * 2000})
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(write, range(24)))
            result = read(target)
            self.assertIn(result['writer'], range(24))
            self.assertEqual(result['payload'], 'x' * 2000)
            self.assertEqual(list(Path(td).glob('stage.json.*.tmp')), [])

    def test_save_retries_while_a_reader_holds_the_target(self):
        """Windows 上「另一个线程正读着目标」会让 os.replace 报 WinError 5：保存要重试，不能直接失败。"""
        from agent import core
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "ui_settings.json"
            target.write_text('{"old": 1}', encoding="utf-8")
            real = os.replace
            calls = []
            def flaky(src, dst, *args, **kwargs):
                calls.append(str(dst))
                if len(calls) <= 2:                     # 前两次模拟界面线程还握着读句柄
                    raise PermissionError(5, "拒绝访问")
                return real(src, dst, *args, **kwargs)
            with mock.patch("agent.core.os.replace", flaky):
                core.save(target, {"new": 2})
            self.assertEqual(read(target), {"new": 2})
            self.assertEqual(len(calls), 3)             # 第三次才真正换过去
            self.assertFalse(Path(str(target) + ".tmp").exists())

    def test_save_gives_up_when_the_target_stays_locked(self):
        """真的被锁住时仍要抛出并保留原文件：重试是有界的，不能变成静默丢数据。"""
        from agent import core
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "ui_settings.json"
            target.write_text('{"old": 1}', encoding="utf-8")
            with mock.patch("agent.core.os.replace", side_effect=PermissionError(5, "拒绝访问")) as failing:
                with self.assertRaises(PermissionError):
                    core.save(target, {"new": 2})
            self.assertEqual(failing.call_count, 5)     # 5 次后放弃，不做无界重试
            self.assertEqual(read(target), {"old": 1})
            self.assertFalse(Path(str(target) + ".tmp").exists())

    def test_file_hash_stable(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "f.bin"; p.write_bytes(b"hello")
            self.assertEqual(file_hash(p), file_hash(p))

    def test_download_rejects_http_url(self):
        from agent.core import download
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                download("http://example.com/video.mp4", Path(td) / "out.mp4")

    def test_request_timeout_clear_error(self):
        from agent.core import request
        from unittest.mock import patch
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            with self.assertRaises(RuntimeError) as ctx:
                request("https://example.com/api")
            self.assertIn("超时", str(ctx.exception))

    def test_download_failure_cleans_partial(self):
        from agent.core import download
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "out.mp4"
            class FakeResp:
                def geturl(self):
                    return "http://redirected"
                def read(self, n):
                    return b"x"
                def __enter__(self):
                    return self
                def __exit__(self, *a):
                    return False
            with patch("urllib.request.urlopen", return_value=FakeResp()):
                with self.assertRaises(ValueError):
                    download("https://example.com/v.mp4", dest)
            self.assertFalse(dest.with_suffix(".download").exists())

    def test_download_publishes_only_after_complete_file_is_written(self):
        """下载完成使用统一原子发布，而不是直接替换正式成果。"""
        from agent.core import download
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "nested" / "out.mp4"
            class FakeResp:
                def geturl(self): return "https://example.com/v.mp4"
                def read(self, n):
                    if getattr(self, "done", False): return b""
                    self.done = True; return b"complete-video"
                def __enter__(self): return self
                def __exit__(self, *a): return False
            with patch("urllib.request.urlopen", return_value=FakeResp()), patch("agent.core.replace", wraps=__import__("agent.core", fromlist=["replace"]).replace) as publish:
                download("https://example.com/v.mp4", dest)
            self.assertEqual(dest.read_bytes(), b"complete-video")
            self.assertEqual(publish.call_count, 1)
            self.assertFalse(list(dest.parent.glob("*.partial.mp4")))


class EngineTests(unittest.TestCase):
    def make(self, td, shots):
        t = Path(td); proj = t / "p"
        (proj / "episode" / "frames").mkdir(parents=True)
        (proj / "episode" / "assets.json").write_text("{}", encoding="utf-8")
        ep = {"episode_id": "EP001", "title": "T", "shots": shots}
        (proj / "episode" / "episode.json").write_text(json.dumps(ep, ensure_ascii=False), encoding="utf-8")
        (proj / "config.json").write_text(json.dumps({"episode_dir": str(proj / "episode"), "episode_file": str(proj / "episode" / "episode.json"), "budget_seconds": 0, "reserve_seconds": 0}), encoding="utf-8")
        return proj

    def shot(self, sid="SH001", dur=5, prompt="画面"):
        return {"id": sid, "title": "镜头", "duration": dur, "characters": [], "location": "LOC_001",
                "frame": f"frames/{sid}.png", "video_prompt": prompt, "dialogue": []}

    def test_shot_folder_rejects_path_chars(self):
        with tempfile.TemporaryDirectory() as td:
            st = engine_mod.Studio(self.make(td, [self.shot()]))
            with self.assertRaises(ValueError):
                st.shot_folder("SH/../x")

    def test_validate_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                engine_mod.Studio(self.make(td, [self.shot("SH001"), self.shot("SH001")]))

    def test_validate_bad_duration(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                engine_mod.Studio(self.make(td, [self.shot("SH001", dur=1)]))

    def test_state_has_all_shots(self):
        with tempfile.TemporaryDirectory() as td:
            st = engine_mod.Studio(self.make(td, [self.shot("SH001"), self.shot("SH002")]))
            self.assertEqual(set(st.state()["shots"]), {"SH001", "SH002"})

    def test_state_recovers_corrupt_list(self):
        with tempfile.TemporaryDirectory() as td:
            st = engine_mod.Studio(self.make(td, [self.shot("SH001"), self.shot("SH002")]))
            st.db.write_text("[]", encoding="utf-8")
            self.assertEqual(set(st.state()["shots"]), {"SH001", "SH002"})

    def test_state_recovers_invalid_json(self):
        with tempfile.TemporaryDirectory() as td:
            st = engine_mod.Studio(self.make(td, [self.shot("SH001")]))
            st.db.write_text("{bad json", encoding="utf-8")
            self.assertEqual(set(st.state()["shots"]), {"SH001"})

    def test_used_and_remaining(self):
        with tempfile.TemporaryDirectory() as td:
            st = engine_mod.Studio(self.make(td, [self.shot("SH001", dur=5), self.shot("SH002", dur=6)]))
            st.cfg["budget_seconds"] = 100; st.cfg["reserve_seconds"] = 10
            state = st.state()
            state["shots"]["SH001"].append({"version": 1, "seconds": 5, "charged": True, "state": "downloaded"})
            state["shots"]["SH002"].append({"version": 1, "seconds": 6, "charged": False, "state": "downloaded"})
            save(st.db, state)
            self.assertEqual(st.used(), 5)
            self.assertEqual(st.remaining(), 85)

    def test_review_pass_requires_downloaded(self):
        with tempfile.TemporaryDirectory() as td:
            st = engine_mod.Studio(self.make(td, [self.shot()]))
            with self.assertRaises(ValueError):
                st.review("SH001", "pass", "")

    def test_review_pass_ok_and_invalid_value(self):
        with tempfile.TemporaryDirectory() as td:
            st = engine_mod.Studio(self.make(td, [self.shot()]))
            state = st.state()
            state["shots"]["SH001"].append({"version": 1, "state": "downloaded", "qc_pass": True, "seconds": 5})
            save(st.db, state)
            st.review("SH001", "pass", "ok")
            self.assertEqual(st.state()["shots"]["SH001"][-1]["review"], "pass")
            with self.assertRaises(ValueError):
                st.review("SH001", "maybe", "")

    def test_attach_recovers_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            st = engine_mod.Studio(self.make(td, [self.shot()]))
            state = st.state()
            state["shots"]["SH001"].append({"version": 1, "state": "unknown", "seconds": 5, "charged": True})
            save(st.db, state)
            st.attach("SH001", "task_1234567890")
            v = st.state()["shots"]["SH001"][-1]
            self.assertEqual(v["task_id"], "task_1234567890")
            self.assertEqual(v["state"], "queued")

    def test_attach_bad_format(self):
        with tempfile.TemporaryDirectory() as td:
            st = engine_mod.Studio(self.make(td, [self.shot()]))
            with self.assertRaises(ValueError):
                st.attach("SH001", "short")

    def test_attach_no_version(self):
        with tempfile.TemporaryDirectory() as td:
            st = engine_mod.Studio(self.make(td, [self.shot()]))
            with self.assertRaises(ValueError):
                st.attach("SH001", "task_1234567890")
    def test_shot_missing_sid_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as td:
            st = engine_mod.Studio(self.make(td, [self.shot("SH001")]))
            with self.assertRaises(ValueError):
                st.shot("SH999")
    def test_frame_out_of_base_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            st = engine_mod.Studio(self.make(td, [self.shot("SH001")]))
            shot = st.shot("SH001"); shot["frame"] = "../outside.png"
            with self.assertRaises(ValueError):
                st.frame(shot, required=False)
    def test_remaining_clamps_to_zero(self):
        with tempfile.TemporaryDirectory() as td:
            st = engine_mod.Studio(self.make(td, [self.shot("SH001", dur=5)]))
            st.cfg["budget_seconds"] = 3; st.cfg["reserve_seconds"] = 0
            state = st.state()
            state["shots"]["SH001"].append({"version": 1, "seconds": 10, "charged": True, "state": "downloaded"})
            save(st.db, state)
            self.assertEqual(st.remaining(), 0)
    def test_validate_reserve_exceeds_budget(self):
        with tempfile.TemporaryDirectory() as td:
            proj = self.make(td, [self.shot("SH001")])
            cfg = read(proj / "config.json"); cfg["reserve_seconds"] = 10; cfg["budget_seconds"] = 0
            save(proj / "config.json", cfg)
            with self.assertRaises(ValueError):
                engine_mod.Studio(proj)
    def test_task_folder_output_dir(self):
        with tempfile.TemporaryDirectory() as td:
            st = engine_mod.Studio(self.make(td, [self.shot("SH001")]))
            v = {"output_dir": "data/SH001/v001", "version": 1}
            self.assertEqual(st.task_folder("SH001", v), (st.root / "data/SH001/v001").resolve())
    def test_cloud_index_noop_for_local(self):
        with tempfile.TemporaryDirectory() as td:
            st = engine_mod.Studio(self.make(td, [self.shot("SH001")]))
            self.assertIsNone(st.cloud_index())
    def test_lock_prevents_concurrent(self):
        with tempfile.TemporaryDirectory() as td:
            st = engine_mod.Studio(self.make(td, [self.shot("SH001")]))
            with st.lock():
                with self.assertRaises(ValueError):
                    with st.lock():
                        pass
    def test_client_missing_key_raises(self):
        with tempfile.TemporaryDirectory() as td:
            st = engine_mod.Studio(self.make(td, [self.shot("SH001")]))
            with self.assertRaises(ValueError):
                st.client()
    def test_attach_duplicate_task_id_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            st = engine_mod.Studio(self.make(td, [self.shot("SH001"), self.shot("SH002")]))
            state = st.state()
            state["shots"]["SH001"].append({"version": 1, "state": "downloaded", "task_id": "task_1234567890", "seconds": 5})
            state["shots"]["SH002"].append({"version": 1, "state": "unknown", "seconds": 5, "charged": True})
            save(st.db, state)
            with self.assertRaises(ValueError):
                st.attach("SH002", "task_1234567890")
    def test_validate_string_dialogue_warns(self):
        with tempfile.TemporaryDirectory() as td:
            ep = valid_episode(); ep["shots"][0]["dialogue"] = ["卡梅隆：你好"]
            r = writing.validate_episode(ep, td, None)
            self.assertTrue(any("尚未标注" in w for w in r["warnings"]))
    def test_validate_empty_string_dialogue_errors(self):
        with tempfile.TemporaryDirectory() as td:
            ep = valid_episode(); ep["shots"][0]["dialogue"] = ["   "]
            with self.assertRaises(ValueError):
                writing.validate_episode(ep, td, None)
    def test_validate_empty_prompt_raises(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                engine_mod.Studio(self.make(td, [self.shot("SH001", prompt="  ")]))
    def test_review_revise_ok(self):
        with tempfile.TemporaryDirectory() as td:
            st = engine_mod.Studio(self.make(td, [self.shot("SH001")]))
            state = st.state()
            state["shots"]["SH001"].append({"version": 1, "state": "downloaded", "qc_pass": False, "seconds": 5})
            save(st.db, state)
            st.review("SH001", "revise", "需要修改")
            self.assertEqual(st.state()["shots"]["SH001"][-1]["review"], "revise")
    def test_used_tolerates_missing_seconds(self):
        with tempfile.TemporaryDirectory() as td:
            st = engine_mod.Studio(self.make(td, [self.shot("SH001")]))
            state = st.state()
            state["shots"]["SH001"].append({"version": 1, "state": "downloaded", "charged": True})
            save(st.db, state)
            self.assertEqual(st.used(), 0)
    def test_config_missing_budget_defaults_zero(self):
        with tempfile.TemporaryDirectory() as td:
            proj = self.make(td, [self.shot("SH001")])
            cfg = read(proj / "config.json"); cfg.pop("budget_seconds"); cfg.pop("reserve_seconds")
            save(proj / "config.json", cfg)
            st = engine_mod.Studio(proj)
            self.assertEqual(st.remaining(), 0)

    def test_config_non_dict_clear_error(self):
        with tempfile.TemporaryDirectory() as td:
            proj = self.make(td, [self.shot("SH001")])
            (proj / "config.json").write_text("[]", encoding="utf-8")
            with self.assertRaises(ValueError):
                engine_mod.Studio(proj)

    def test_config_corrupt_json_clear_error(self):
        with tempfile.TemporaryDirectory() as td:
            proj = self.make(td, [self.shot("SH001")])
            (proj / "config.json").write_text("{bad", encoding="utf-8")
            with self.assertRaises(ValueError):
                engine_mod.Studio(proj)

class ProjectsDeleteTests(unittest.TestCase):
    def make_projects(self, td):
        t = Path(td); app = t / "app"; app.mkdir()
        (app / "config.json").write_text(json.dumps({"downloads_root": str(t / "downloads")}), encoding="utf-8")
        (app / "projects.json").write_text(json.dumps({"active": None, "projects": []}), encoding="utf-8")
        return projects_mod.Projects(app)

    def test_deletion_target_registered(self):
        with tempfile.TemporaryDirectory() as td:
            P = self.make_projects(td)
            p = P.create("测试项目")
            self.assertEqual(P.deletion_target(str(p)), Path(p).resolve())

    def test_deletion_target_unregistered(self):
        with tempfile.TemporaryDirectory() as td:
            P = self.make_projects(td)
            with self.assertRaises(ValueError):
                P.deletion_target(str(Path(td) / "nope"))

    def test_deletion_target_outside_base(self):
        with tempfile.TemporaryDirectory() as td:
            P = self.make_projects(td)
            outside = Path(td) / "elsewhere" / "p"; outside.mkdir(parents=True)
            P.info["projects"].append({"name": "X", "path": str(outside)})
            with self.assertRaises(ValueError):
                P.deletion_target(str(outside))

    def test_registered_project_can_be_deleted_after_its_script_is_removed(self):
        with tempfile.TemporaryDirectory() as td:
            P = self.make_projects(td)
            project = P.create("已删剧本")
            (project / "03初步分镜" / "分镜拆分" / "episode.json").unlink()
            P.delete(str(project))
            self.assertFalse(project.exists())
            self.assertEqual(P.info["projects"], [])

    def test_delete_removes_internal_directory_link_without_touching_its_target(self):
        with tempfile.TemporaryDirectory() as td:
            P = self.make_projects(td)
            project = P.create("带链接项目")
            outside = Path(td) / "outside"; outside.mkdir()
            keep = outside / "keep.txt"; keep.write_text("保留", encoding="utf-8")
            link = project / "遗留目录链接"
            try:
                os.symlink(outside, link, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("当前环境不允许创建目录链接")
            P.delete(str(project))
            self.assertFalse(project.exists())
            self.assertTrue(keep.exists(), "只删除项目内的链接节点，绝不删除链接目标")
            self.assertEqual(P.info["projects"], [])

    def test_linked_project_is_rejected_by_recursive_delete(self):
        with tempfile.TemporaryDirectory() as td:
            P = self.make_projects(td)
            project = P.create("链接项目")
            with self.assertRaises(ValueError):
                P.unlink_registered_project(str(project))

class ValidateProfileTests(unittest.TestCase):
    def vp(self, profile):
        from workflow_settings import validate_profile
        return validate_profile(profile)

    def test_empty_ok(self):
        v = self.vp({"program": "", "model": "", "skill": "", "instructions": ""})
        self.assertEqual(v["program"], "")

    def test_bad_model(self):
        with self.assertRaises(ValueError):
            self.vp({"program": "", "model": "bad model", "skill": "", "instructions": ""})

    def test_relative_program_rejected(self):
        with self.assertRaises(ValueError):
            self.vp({"program": "codex.exe", "model": "", "skill": "", "instructions": ""})

    def test_non_exe_program_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.txt"; p.write_text("x", encoding="utf-8")
            with self.assertRaises(ValueError):
                self.vp({"program": str(p), "model": "", "skill": "", "instructions": ""})

    def test_skill_must_be_md(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.txt"; p.write_text("x", encoding="utf-8")
            with self.assertRaises(ValueError):
                self.vp({"program": "", "model": "", "skill": str(p), "instructions": ""})


    def test_stage_profile_empty_skill_ok(self):
        from workflow_settings import validate_stage_profile
        v = validate_stage_profile({"program": "", "model": "", "skill": "", "instructions": ""}, "storyboard")
        self.assertEqual(v["skill"], "")

    def test_stage_profile_wrong_preset_rejected(self):
        from workflow_settings import validate_stage_profile, preset_skill
        skill = preset_skill("create-blender-story-video")
        if not skill.is_file():
            self.skipTest("bundled skill not present")
        with self.assertRaises(ValueError):
            validate_stage_profile({"program": "", "model": "", "skill": str(skill), "instructions": ""}, "storyboard")

    def test_validate_edit_duration_ok(self):
        with tempfile.TemporaryDirectory() as td:
            ep = valid_episode(); ep["shots"][0]["duration"] = 5
            ep["shots"][0]["edit_duration"] = 3
            ep["shots"][0]["trim_in"] = 0; ep["shots"][0]["trim_out"] = 3
            ep["duration"] = 3
            r = writing.validate_episode(ep, td, None)
            self.assertIn("edit_duration", str(r.get("warnings", "")))

    def test_validate_edit_duration_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            ep = valid_episode(); ep["shots"][0]["duration"] = 5
            ep["duration"] = 10  # 与单镜5秒不一致
            with self.assertRaises(ValueError):
                writing.validate_episode(ep, td, None)

    def test_validate_duration_message_names_both_numbers(self):
        """第 62 期任务 12：报错写清「整集多少秒、镜头合计多少秒」，别只说一句「不一致」。"""
        with tempfile.TemporaryDirectory() as td:
            ep = valid_episode(2); ep["duration"] = 120  # 两镜各 5 秒，合计 10
            with self.assertRaises(ValueError) as caught:
                writing.validate_episode(ep, td, None)
            text = str(caught.exception)
            self.assertIn("整集时长120秒", text)
            self.assertIn("各镜时长合计10秒", text)

    def test_duration_gap_numbers_and_skip_rules(self):
        """第 62 期任务 12：02 初步分镜的「时长不符」标记与采用校验共用这一条判定。"""
        ep = valid_episode(2); ep["duration"] = 10
        self.assertIsNone(writing.duration_gap(ep))
        ep["duration"] = 12
        self.assertEqual(writing.duration_gap(ep), (12, 10))
        self.assertIsNone(writing.duration_gap({"shots": []}), "没有 duration 时不判定")
        self.assertIsNone(writing.duration_gap(None))
        edited = valid_episode(1); shot = edited["shots"][0]
        shot["duration"] = 5; shot["edit_duration"] = 3; shot["trim_in"] = 0; shot["trim_out"] = 3
        edited["duration"] = 3
        self.assertIsNone(writing.duration_gap(edited), "按剪辑字段折算后对得上就算对得上")

    def test_prepare_invalid_stage_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; proj.mkdir()
            with self.assertRaises(ValueError):
                writing.prepare(proj, "创意", "不存在的阶段", 60)

    def test_prepare_empty_brief_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; proj.mkdir()
            with self.assertRaises(ValueError):
                writing.prepare(proj, "   ", "Step 0 需求整理", 60)

    def test_prepare_requires_l3_publisher_after_validating_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; proj.mkdir()
            with self.assertRaises(TypeError):
                writing.prepare(proj, "创意", "Step 0 需求整理", 60)

    def test_episode_dir_reads_config(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; proj.mkdir()
            (proj / "config.json").write_text(json.dumps({"episode_dir": str(proj / "ep")}), encoding="utf-8")
            self.assertEqual(writing.episode_dir(proj), (proj / "ep").resolve())

    def test_episode_dir_corrupt_config_falls_back(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; proj.mkdir()
            (proj / "config.json").write_text("[]", encoding="utf-8")
            self.assertEqual(writing.episode_dir(proj), (proj / "episode").resolve())


    def test_preset_paths_cached_for_bundled_skills(self):
        first = ws._preset_paths()
        self.assertIs(ws._preset_paths(), first)

    def test_preset_paths_and_candidates_ignore_codex_home(self):
        with tempfile.TemporaryDirectory() as td:
            self.addCleanup(ws._PRESET_PATHS.clear)
            before = ws._preset_paths()
            with mock.patch.dict(os.environ, {"CODEX_HOME": td}):
                after = ws._preset_paths()
                self.assertIs(after, before)
                self.assertEqual(ws.preset_skill("short-drama-storyboard"),
                                 ws._bundled_skill("short-drama-storyboard"))

    def test_preset_label_round_trips_through_preset_folder(self):
        skill = ws.preset_skill("short-drama-storyboard")
        if not skill.is_file():
            self.skipTest("bundled skill not present")
        self.assertEqual(ws.preset_folder(str(skill)), "short-drama-storyboard")
        self.assertEqual(ws.preset_label(str(skill)), "Drama 分镜")

    def test_preset_label_empty(self):
        from workflow_settings import preset_label
        self.assertEqual(preset_label(""), "不使用 Skill")


if __name__ == "__main__":
    unittest.main(verbosity=2)
