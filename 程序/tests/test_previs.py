# -*- coding: utf-8 -*-
"""白模复杂度分流纯逻辑自检。运行：python test_previs.py"""
import json, os, sys, tempfile, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

from previs_routing import classify
from previs_automation import select_agent_shots


class AgentSelectionTests(unittest.TestCase):
    """Agent 只接复杂动作：简单／中等镜头只写状态跳过，不再让整批失败。"""

    def build(self, td):
        proj = Path(td) / "p"
        (proj / "storyboard").mkdir(parents=True)
        shots = [
            {"id": "SH001", "action": "他站在原地说话", "camera": "固定"},
            {"id": "SH002", "action": "他走到桌边坐下", "camera": "固定"},
            {"id": "SH003", "action": "他追逐并抢夺道具", "camera": "跟拍"},
        ]
        source = proj / "storyboard" / "episode.json"
        source.write_text(json.dumps({"episode_id": "EP001", "title": "T", "shots": shots}, ensure_ascii=False), encoding="utf-8")
        return proj, source

    def test_only_complex_goes_to_agent(self):
        with tempfile.TemporaryDirectory() as td:
            proj, source = self.build(td)
            state = {"busy": False, "status": {}, "progress": {}}
            ids = select_agent_shots(proj, source, ["SH001", "SH002", "SH003"], state)
            self.assertEqual(ids, ["SH003"])
            self.assertEqual(state["status"][str(proj) + "|SH001"], "无需白模，已跳过")
            self.assertIn("线上", state["status"][str(proj) + "|SH002"])

    def test_mixed_batch_does_not_raise(self):
        with tempfile.TemporaryDirectory() as td:
            proj, source = self.build(td)
            state = {"busy": False, "status": {}, "progress": {str(proj) + "|SH001": "queued"}}
            ids = select_agent_shots(proj, source, ["SH001", "SH002"], state)
            self.assertEqual(ids, [])
            # 简单／中等镜头必须清掉旧的进度，页面上的进度条不会一直挂着。
            self.assertNotIn(str(proj) + "|SH001", state["progress"])


class ClassifyTests(unittest.TestCase):
    def test_explicit_simple(self):
        self.assertEqual(classify({"action_complexity": "简单"})[0], "simple")

    def test_explicit_complex_english(self):
        self.assertEqual(classify({"previs_complexity": "high"})[0], "complex")

    def test_explicit_chinese_high_low(self):
        self.assertEqual(classify({"action_complexity": "高"})[0], "complex")
        self.assertEqual(classify({"action_complexity": "低"})[0], "simple")

    def test_chase_is_complex(self):
        self.assertEqual(classify({"action": "他追逐并抢夺道具"})[0], "complex")

    def test_static_is_simple(self):
        self.assertEqual(classify({"action": "他站在原地说话"})[0], "simple")

    def test_move_with_camera_is_complex(self):
        self.assertEqual(classify({"action": "他走向门口", "camera": "环绕跟拍"})[0], "complex")

    def test_move_only_is_medium(self):
        self.assertEqual(classify({"action": "他走到桌边坐下"})[0], "medium")

    def test_long_action_chain_is_complex(self):
        self.assertEqual(classify({"action": "他伸手，然后转身，随后坐下，接着站起，同时说话"})[0], "complex")

    def test_no_info_is_medium(self):
        self.assertEqual(classify({})[0], "medium")

    def test_negated_action_not_complex(self):
        self.assertEqual(classify({"action": "静止站立，不要跑动，不要打斗"})[0], "simple")

    def test_negated_camera_not_complex(self):
        self.assertEqual(classify({"action": "他走向门口", "camera": "不要环绕"})[0], "medium")

    def test_negated_motion_not_complex(self):
        self.assertEqual(classify({"action": "静止站立，不转身，不移动"})[0], "simple")

    def test_zai_ci_not_split(self):
        self.assertEqual(classify({"action": "他再次伸手，随后放下"})[0], "medium")

    def test_zai_jian_not_split(self):
        self.assertEqual(classify({"action": "他挥手说再见，随后转身"})[0], "medium")

    def test_non_dict_shot_is_medium(self):
        self.assertEqual(classify(None)[0], "medium")
        self.assertEqual(classify("不是对象")[0], "medium")

    def test_entries_non_object_returns_empty(self):
        from previs_routing import entries
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; proj.mkdir()
            source = proj / "episode.json"; source.write_text("[]", encoding="utf-8")
            self.assertEqual(entries(proj, source), {})
            source.write_text(json.dumps({"shots": None}, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(entries(proj, source), {})


class StatusValueTests(unittest.TestCase):
    def test_publish_is_available_from_service_and_writes_complete_payload(self):
        from previs_progress_service import publish
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "SH001_进度.json"
            publish(path, "SH001", "render", 3, 12)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")),
                             {"shot_id": "SH001", "stage": "render", "completed": 3, "total": 12})

    def test_queued(self):
        from previs_progress_service import status_value
        self.assertEqual(status_value({"progress": {"p|SH001": "queued"}}, "p", "SH001", "排队中"), ("determinate", 0, "排队"))

    def test_ready(self):
        from previs_progress_service import status_value
        self.assertEqual(status_value({"progress": {}}, "p", "SH001", "已就绪"), ("determinate", 100, "100%"))

    def test_not_running_returns_none(self):
        from previs_progress_service import status_value
        self.assertIsNone(status_value({"progress": {}, "busy": False}, "p", "SH001", "未开始"))

    def test_running_render_percent(self):
        from previs_progress_service import status_value
        with tempfile.TemporaryDirectory() as td:
            log = Path(td); (log / "SH001_进度.json").write_text(json.dumps({"shot_id": "SH001", "stage": "render", "completed": 50, "total": 100}), encoding="utf-8")
            state = {"progress": {"p|SH001": "running"}, "log_dir": str(log), "busy": True}
            self.assertEqual(status_value(state, "p", "SH001", "制作中")[0], "determinate")

    def test_progress_read_uses_cache_and_publish_invalidates_it(self):
        from previs_progress_service import publish, status_value
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "SH001_进度.json"
            state = {"progress": {"p|SH001": "running"}, "log_dir": td, "busy": True}
            publish(path, "SH001", "render", 1, 4)
            self.assertEqual(status_value(state, "p", "SH001", "制作中")[1], 25)
            publish(path, "SH001", "render", 3, 4)
            self.assertEqual(status_value(state, "p", "SH001", "制作中")[1], 75)

    def test_invalid_frames_fall_back(self):
        from previs_progress_service import status_value
        with tempfile.TemporaryDirectory() as td:
            log = Path(td); (log / "SH001_进度.json").write_text(json.dumps({"shot_id": "SH001", "stage": "render", "completed": 120, "total": 100}), encoding="utf-8")
            state = {"progress": {"p|SH001": "running"}, "log_dir": str(log), "busy": True}
            self.assertEqual(status_value(state, "p", "SH001", "制作中")[0], "indeterminate")


class OverrideTests(unittest.TestCase):
    def make(self, td):
        import json
        proj = Path(td) / "p"; proj.mkdir()
        source = proj / "episode.json"
        ep = {"episode_id": "EP001", "title": "T", "shots": [
            {"id": "SH001", "title": "镜头", "action": "站在原地说话", "duration": 5}]}
        source.write_text(json.dumps(ep, ensure_ascii=False), encoding="utf-8")
        return proj, source

    def test_override_applied(self):
        from previs_routing import set_override, entries
        with tempfile.TemporaryDirectory() as td:
            proj, source = self.make(td)
            set_override(proj, source, "SH001", "complex")
            self.assertEqual(entries(proj, source)["SH001"]["level"], "complex")

    def test_auto_removes_override(self):
        from previs_routing import set_override, entries
        with tempfile.TemporaryDirectory() as td:
            proj, source = self.make(td)
            set_override(proj, source, "SH001", "complex")
            set_override(proj, source, "SH001", "auto")
            # 原动作是“站着说话”→ simple
            self.assertEqual(entries(proj, source)["SH001"]["level"], "simple")

    def test_invalid_value_rejected(self):
        from previs_routing import set_override
        with tempfile.TemporaryDirectory() as td:
            proj, source = self.make(td)
            with self.assertRaises(ValueError):
                set_override(proj, source, "SH001", "bad")


class ShotDirectoryTests(unittest.TestCase):
    def test_valid(self):
        from white_model import shot_directory
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            with patch("white_model.workspace", return_value=Path(td)):
                root = shot_directory("proj", "SH001")
                self.assertEqual(root.name, "SH001")

    def test_repeated_lookups_reuse_the_resolved_directory(self):
        """同一个镜头反复取目录只解析一次；换了 workspace 立刻失效，不会拿到旧位置。"""
        import white_model
        from unittest.mock import patch
        for cache in (white_model._WORKSPACE_CACHE, white_model._BASE_CACHE, white_model._DIR_CACHE):
            cache.clear()
            self.addCleanup(cache.clear)
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as other:
            with patch("white_model.workspace", return_value=Path(td)):
                calls = []
                original = Path.resolve
                def counting(self, *args, **kwargs):
                    calls.append(str(self))
                    return original(self, *args, **kwargs)
                with patch.object(Path, "resolve", counting):
                    first = white_model.shot_directory("proj", "SH001")
                    warm = len(calls)
                    self.assertGreater(warm, 0)
                    for _ in range(5):
                        self.assertEqual(white_model.shot_directory("proj", "SH001"), first)
                    self.assertEqual(len(calls), warm)               # 之后一次解析都没有
                self.assertEqual(first, Path(td) / "proj" / "SH001")
            # workspace 变了（测试替换、或用户中途装好 Blender）必须重新解析
            with patch("white_model.workspace", return_value=Path(other)):
                self.assertEqual(white_model.shot_directory("proj", "SH001"), Path(other) / "proj" / "SH001")

    def test_rejects_traversal(self):
        from white_model import shot_directory
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            with patch("white_model.workspace", return_value=Path(td)):
                with self.assertRaises(ValueError):
                    shot_directory("proj", "../x")
                with self.assertRaises(ValueError):
                    shot_directory("proj", "SH/../x")


class ReadRecordTests(unittest.TestCase):
    def test_legacy_preview_blend_migrates_to_project_file(self):
        from white_model import read_record
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "预演记录.json").write_text(json.dumps({"preview": "legacy.blend"}, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(read_record(root), {"project_file": "legacy.blend"})

    def test_preview_video_kept(self):
        from white_model import read_record
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "预演记录.json").write_text(json.dumps({"preview": "a.mp4"}, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(read_record(root)["preview"], "a.mp4")

    def test_corrupt_record_clear_error(self):
        from white_model import read_record
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "预演记录.json").write_text("{bad json", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_record(root)

    def test_invalid_encoding_clear_error(self):
        from white_model import read_record
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "预演记录.json").write_bytes(b"\xff\xfe\xfa")
            with self.assertRaises(ValueError):
                read_record(root)

    def test_service_record_observes_atomic_republish_after_cached_read(self):
        """正式预演记录重发后，下一次读取不得保留旧缓存。"""
        from agent.core import save
        from white_model_service import read_record
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / '预演记录.json'
            save(path, {'preview': 'old.mp4'})
            self.assertEqual(read_record(root)['preview'], 'old.mp4')
            save(path, {'preview': 'new.mp4'})
            self.assertEqual(read_record(root)['preview'], 'new.mp4')


class ImportPrevisMediaTests(unittest.TestCase):
    def test_service_copies_video_and_updates_record(self):
        from white_model_service import import_previs_media, read_record
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source = base / 'source.mp4'
            source.write_bytes(b'preview')
            target = import_previs_media(base / 'shot', 'SH001', source)
            self.assertEqual(target.read_bytes(), b'preview')
            self.assertEqual(read_record(base / 'shot')['preview'], str(target))
            self.assertTrue(source.exists())

    def test_service_rejects_empty_media_without_publication(self):
        from white_model_service import import_previs_media
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source = base / 'empty.mp4'
            source.touch()
            with self.assertRaisesRegex(ValueError, '为空'):
                import_previs_media(base / 'shot', 'SH001', source)
            self.assertFalse((base / 'shot').exists())

    def test_ready_false_on_corrupt_record(self):
        from unittest.mock import patch
        from previs_routing import ready
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch("white_model_service.shot_directory", return_value=root), \
                 patch("white_model_service.read_record", side_effect=ValueError("损坏")):
                self.assertFalse(ready(root, "SH001"))

    def test_automatic_candidates_wait_for_missing_keyframes(self):
        from unittest.mock import patch
        from previs_routing import automatic_candidates
        shots = [{'id': 'SH001'}, {'id': 'SH002'}]
        groups = {'simple': [], 'medium': ['SH002'], 'complex': ['SH001']}
        with patch('previs_routing.partition', return_value=(groups, {})), \
             patch('previs_routing.ready', return_value=False):
            plan = automatic_candidates('project', 'source', shots, True, lambda rows: ['SH001'])
        self.assertEqual(plan, {'pending': [], 'medium': ['SH002'], 'waiting': ['SH001']})

    def test_automatic_notice_keeps_dispatch_signature_and_human_guidance(self):
        from previs_routing import automatic_notice
        notice, notes = automatic_notice('source.json', ['SH001'], ['SH002'], ['SH003'])
        self.assertEqual(notice, ('source.json', ('SH001',), ('SH002',), 1))
        self.assertEqual(len(notes), 2)
        self.assertIn('待首帧', notes[0])
        self.assertIn('线上白模入口', notes[1])

    def test_automatic_signature_normalizes_source_and_shot_order(self):
        from pathlib import Path
        from previs_routing import automatic_signature
        self.assertEqual(automatic_signature(Path('source.json'), ['SH002', 'SH001']),
                         ('source.json', ('SH002', 'SH001')))

    def test_automatic_engine_uses_injected_settings_and_engine_map(self):
        from previs_routing import automatic_engine
        seen = []
        def read_settings(project, stage):
            seen.append((project, stage))
            return {'engine': 'blender'}
        self.assertEqual(automatic_engine('project', read_settings, {'blender': 'Blender'}), 'Blender')
        self.assertEqual(seen, [('project', 'previs')])

    def test_automatic_engine_rejects_unknown_configured_engine(self):
        from previs_routing import automatic_engine
        with self.assertRaises(KeyError):
            automatic_engine('project', lambda *_args: {'engine': 'unknown'}, {'blender': 'Blender'})

    def test_automatic_candidates_ignore_empty_or_invalid_shots(self):
        from previs_routing import automatic_candidates
        self.assertEqual(automatic_candidates('project', 'source', [None, {}, {'name': '无编号'}]),
                         {'pending': [], 'medium': [], 'waiting': []})

    def test_entries_ignores_malformed_saved_shots(self):
        from unittest.mock import patch
        from previs_routing import entries
        with patch('previs_routing.read', return_value={'episode_id': 'EP001', 'shots': [None, {}, {'id': 'SH001'}]}):
            self.assertIn('SH001', entries('project', 'source'))

    def test_entries_treats_non_list_shots_as_empty(self):
        from unittest.mock import patch
        from previs_routing import entries
        with patch('previs_routing.read', return_value={'episode_id': 'EP001', 'shots': None}):
            self.assertEqual(entries('project', 'source'), {})


class BlenderLookupTests(unittest.TestCase):
    def test_path_scan_cached_between_shot_directories(self):
        """镜头目录每次都要定位 Blender；PATH 扫描必须只在首次发生。"""
        import white_model
        from unittest.mock import patch
        white_model._BLENDER_CACHE.clear()
        self.addCleanup(white_model._BLENDER_CACHE.clear)
        with patch("white_model_service.shutil.which", return_value=sys.executable) as which:
            found = white_model.find_blender()
            for _ in range(5):
                white_model.workspace()
                white_model.shot_directory("proj", "SH001")
            self.assertEqual(which.call_count, 1)
            self.assertEqual(found, Path(sys.executable))
            white_model.find_blender(refresh=True)
            self.assertEqual(which.call_count, 2)

    def test_missing_blender_also_cached(self):
        import white_model
        from unittest.mock import patch
        white_model._BLENDER_CACHE.clear()
        self.addCleanup(white_model._BLENDER_CACHE.clear)
        with patch("white_model_service.shutil.which", return_value=None) as which, \
             patch.object(Path, "is_file", lambda self: False):
            self.assertIsNone(white_model.find_blender())
            self.assertIsNone(white_model.find_blender())
            self.assertEqual(which.call_count, 1)


class ForceStopTests(unittest.TestCase):
    """白模制作必须能强制停止：结束正在跑的引擎进程（连同子进程），并让工作线程停掉后续镜头。"""

    def test_terminate_ends_registered_process_only(self):
        import subprocess, time
        import workflow_engines
        project = tempfile.mkdtemp()
        process = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)"], creationflags=0x08000000)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        workflow_engines.register_process(project, process)
        try:
            self.assertEqual([item.pid for item in workflow_engines.running(project)], [process.pid])
            self.assertEqual(workflow_engines.terminate(project), [process.pid])
            deadline = time.monotonic() + 15
            while process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertIsNotNone(process.poll())                    # 进程真的被结束了
            self.assertEqual(workflow_engines.running(project), [])  # 登记表里也已清掉
            self.assertEqual(workflow_engines.terminate(project), [])   # 再点一次是空操作
        finally:
            workflow_engines.forget_process(project, process)

    def test_force_stop_marks_running_shots_and_stops_batch(self):
        from previs_automation import force_stop
        state = {"busy": True, "status": {}, "progress": {"p|SH001": "running", "p|SH002": "queued", "p|SH003": "ready"}}
        self.assertEqual(force_stop("没有这个项目", state), [])
        self.assertTrue(state["stop"])
        self.assertEqual(state["status"]["p|SH001"], "已强制停止")
        self.assertEqual(state["status"]["p|SH002"], "已强制停止")
        self.assertNotIn("p|SH003", state["status"])                # 已就绪的镜头不写状态
        self.assertIn("已请求停止", state["summary"])

    def test_forced_stop_reports_cancelled_not_failed(self):
        """被强制结束的这一镜记「已强制停止」，不算失败；后续镜头也不再继续。"""
        import time
        from unittest.mock import patch
        import previs_automation, white_model_service
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; proj.mkdir()
            source = proj / "episode.json"
            shots = [{"id": "SH001", "action": "他追逐并抢夺道具", "camera": "跟拍", "duration": 5},
                     {"id": "SH002", "action": "他追逐并抢夺道具", "camera": "跟拍", "duration": 5}]
            source.write_text(json.dumps({"episode_id": "EP001", "title": "T", "shots": shots}, ensure_ascii=False), encoding="utf-8")
            state = {"busy": False, "status": {}, "progress": {}, "selected": set()}
            def fake_run(config, project, output, report, logfile, prompt):
                previs_automation.force_stop(project, state)          # 用户在制作过程中按了「强制停止制作」
                raise ValueError("Codex 执行失败，请查看运行日志")
            with patch.object(white_model_service, "find_blender", lambda refresh=False: Path(sys.executable)), \
                 patch("workflow_settings.find_program", lambda config: sys.executable), \
                 patch("workflow_engines.run_background", fake_run), \
                 patch.object(previs_automation, "verify", lambda *a, **k: False), \
                 patch("previs_batch_service.prepare_batch", lambda *a, **k: "测试提示词"), \
                 patch("native_apps.open_blender", lambda *a, **k: None):
                previs_automation.start(proj, source, ["SH001", "SH002"], state)
                deadline = time.monotonic() + 30
                while state["busy"] and time.monotonic() < deadline:
                    time.sleep(0.02)
            self.assertFalse(state["busy"])
            self.assertEqual(state["status"][str(proj) + "|SH001"], "已强制停止")
            self.assertEqual(state["progress"][str(proj) + "|SH001"], "cancelled")
            self.assertEqual(state["status"][str(proj) + "|SH002"], "已停止")
            self.assertIn("已强制停止", state["summary"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
