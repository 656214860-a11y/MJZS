# -*- coding: utf-8 -*-
"""本地视频后端纯逻辑自检（不连接 ComfyUI）。运行：python test_video.py"""
import json, os, sys, tempfile, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

from local_video import LocalAPI, prepare_graph


class LocalAPITests(unittest.TestCase):
    def test_valid_local_url(self):
        api = LocalAPI("http://127.0.0.1:8189")
        self.assertEqual(api.url, "http://127.0.0.1:8189")

    def test_reject_https(self):
        with self.assertRaises(ValueError):
            LocalAPI("https://127.0.0.1:8189")

    def test_reject_remote_host(self):
        with self.assertRaises(ValueError):
            LocalAPI("http://example.com:8189")

    def test_reject_path(self):
        with self.assertRaises(ValueError):
                LocalAPI("http://127.0.0.1:8189/api")


class VideoPublicationTests(unittest.TestCase):
    def test_index_is_written_only_after_video_and_qc_exist(self):
        import engine
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); folder = root / 'data' / 'SH001' / 'v001'; folder.mkdir(parents=True)
            dest = folder / 'SH001.mp4'; dest.write_bytes(b'complete-video')
            db = root / 'data' / 'state.json'
            state = {'shots': {'SH001': [{'version': 1, 'state': 'succeeded'}]}}
            class FakeStudio:
                def __init__(self): self.root, self.db = root, db
                def task_folder(self, sid, version): return folder
            studio = FakeStudio(); version = state['shots']['SH001'][0]
            engine.Studio.publish_downloaded_video(studio, state, 'SH001', version, dest, {'errors': []})
            saved = json.loads(db.read_text(encoding='utf-8'))['shots']['SH001'][0]
            self.assertEqual(saved['state'], 'downloaded')
            self.assertTrue((folder / 'qc.json').is_file())
            self.assertEqual(Path(root / saved['file']), dest)

    def test_locate_prompt_matches_client_id(self):
        api = LocalAPI("http://127.0.0.1:8189")
        entry = [3, "PID", {"4": {"class_type": "X", "inputs": {}}}, {"client_id": "abc"}, []]
        api.call = lambda path: ({"queue_running": [entry], "queue_pending": []} if path == "/queue" else {})
        self.assertEqual(api.locate_prompt("abc", attempts=1, wait=0), "PID")

    def test_locate_prompt_ignores_other_jobs(self):
        api = LocalAPI("http://127.0.0.1:8189")
        entry = [3, "PID", {"4": {"class_type": "X", "inputs": {}}}, {"client_id": "别人的"}, []]
        api.call = lambda path: ({"queue_running": [entry], "queue_pending": []} if path == "/queue" else {})
        self.assertIsNone(api.locate_prompt("abc", attempts=1, wait=0))
        self.assertIsNone(api.locate_prompt("", attempts=1, wait=0))


class VideoTaskIdRecoveryTests(unittest.TestCase):
    def test_poll_recovers_missing_task_id_from_saved_graph(self):
        import contextlib
        import local_video
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            graph = {"4": {"class_type": "X", "inputs": {}}}
            folder = root / "data" / "SH001" / "v001"; folder.mkdir(parents=True)
            (folder / "request.json").write_text(json.dumps(graph), encoding="utf-8")
            db = root / "data" / "state.json"
            db.write_text(json.dumps({"shots": {"SH001": [{
                "version": 1, "state": "unknown", "backend": "comfy",
                "endpoint": "http://127.0.0.1:8189", "output_node": "92", "seconds": 5}]}}), encoding="utf-8")
            class FakeAPI(local_video.LocalAPI):
                def call(self, path, payload=None, **kw):
                    if path == "/queue":
                        return {"queue_running": [[1, "PID", graph, {"client_id": "别人"}, []]], "queue_pending": []}
                    if path in ("/history", "/history/PID"): return {}
                    raise AssertionError(path)
            class FakeStudio: pass
            studio = FakeStudio(); studio.root = root; studio.db = db
            studio.lock = lambda: contextlib.nullcontext()
            studio.state = lambda: json.loads(db.read_text(encoding="utf-8"))
            original = local_video.LocalAPI
            local_video.LocalAPI = FakeAPI
            self.addCleanup(setattr, local_video, "LocalAPI", original)
            message = local_video.LocalStudio.poll(studio, "SH001")
            self.assertIn("稍后再查询", message)
            saved = json.loads(db.read_text(encoding="utf-8"))["shots"]["SH001"][0]
            self.assertEqual(saved["task_id"], "PID")
            self.assertEqual(saved["state"], "queued")


class PrepareGraphTests(unittest.TestCase):
    def shot(self):
        return {"video_prompt": "测试画面与对白", "duration": 5}

    def test_default_workflow(self):
        with tempfile.TemporaryDirectory() as td:
            graph, options = prepare_graph(Path(td), {"local_video": {}}, self.shot())
            self.assertIn("92", graph)  # default output node
            self.assertEqual(graph["104"]["inputs"]["prompt"], "测试画面与对白")

    def test_missing_workflow_raises(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = {"local_video": {"workflow": str(Path(td) / "missing.json")}}
            with self.assertRaises(ValueError):
                prepare_graph(Path(td), cfg, self.shot())

    def test_bad_node_mapping_raises(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = {"local_video": {"prompt": "99999.no_such_field"}}
            with self.assertRaises(ValueError):
                prepare_graph(Path(td), cfg, self.shot())


class VideoStateTests(unittest.TestCase):
    def test_poll_delay(self):
        from video_task_state import poll_delay
        self.assertEqual(poll_delay(1), 5.0)
        self.assertEqual(poll_delay(5), 1.0)
        self.assertEqual(poll_delay(20), 1.0)

    def test_elapsed_text(self):
        from video_task_state import elapsed_text
        self.assertEqual(elapsed_text({"created": 100}, 130), " · 已等待 0分30秒")
        self.assertEqual(elapsed_text({}, 130), "")

    def test_display(self):
        from video_progress import display
        self.assertIn("生成中", display({"state": "running", "created": 100}, 100))
        self.assertEqual(display({}, None), "未开始")
        self.assertEqual(display({"state": "downloaded"}, None), "已下载")

    def test_summary(self):
        from video_progress import summary
        local = {"SH001": {"state": "running"}, "SH002": {"state": "downloaded"}}
        cloud = {}
        self.assertIn("1 进行中 / 1 已下载", summary(local, cloud))

    def test_summary_reports_only_the_side_asked_for(self):
        """第 38 期第 1 条：本地工作台只报本地、线上工作台只报线上。"""
        from video_progress import summary
        local = {"SH001": {"state": "running"}, "SH002": {"state": "downloaded"}}
        cloud = {"SH009": {"state": "queued"}}
        self.assertEqual(summary(local, cloud, "local"), "本地：1 进行中 / 1 已下载")
        self.assertEqual(summary(local, cloud, "cloud"), "线上：1 进行中 / 0 已下载")
        self.assertIn("线上：", summary(local, cloud), "不传 side 时仍旧两侧都报（老调用方）")

    def test_latest_picks_last_version(self):
        from video_progress import latest
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            p.write_text(json.dumps({"shots": {"SH001": [{"version": 1, "state": "queued"}, {"version": 2, "state": "downloaded"}]}}), encoding="utf-8")
            self.assertEqual(latest(p)["SH001"]["version"], 2)

    def test_latest_corrupt_state_returns_empty(self):
        from video_progress import latest
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            p.write_text("{bad json", encoding="utf-8")
            self.assertEqual(latest(p), {})
            p.write_text("[]", encoding="utf-8")
            self.assertEqual(latest(p), {})

    def test_snapshot_ignores_corrupt_cloud_config(self):
        from video_progress import snapshot
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; (proj / "cloud_video" / "x").mkdir(parents=True)
            (proj / "cloud_video" / "x" / "config.json").write_text("[]", encoding="utf-8")
            source = proj / "episode.json"; source.write_text("{}", encoding="utf-8")
            local, cloud = snapshot(proj, source)
            self.assertEqual(local, {})
            self.assertEqual(cloud, {})

    def test_broken_cloud_config_only_skips_itself(self):
        """读不出来的 config.json 只跳过它自己：轮询每轮都会扫这里，抛异常等于线上任务再也没人查询。"""
        from video_progress import snapshot, unwatched_pending
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; source = proj / "episode.json"
            source.parent.mkdir(parents=True, exist_ok=True); source.write_text("{}", encoding="utf-8")
            good = proj / "cloud_video" / "good"; (good / "data").mkdir(parents=True)
            (good / "config.json").write_text(json.dumps({"live_enabled": True, "episode_file": str(source)}), encoding="utf-8")
            (good / "data" / "state.json").write_text(json.dumps({"shots": {"SH001": [
                {"version": 1, "state": "running", "created": 5, "task_id": "t-1"}]}}), encoding="utf-8")
            (proj / "cloud_video" / "bad").mkdir(parents=True)
            (proj / "cloud_video" / "bad" / "config.json").write_text("{bad json", encoding="utf-8")
            (proj / "cloud_video" / "wrongtype").mkdir(parents=True)
            (proj / "cloud_video" / "wrongtype" / "config.json").write_text(json.dumps({"episode_file": ["不是路径"]}), encoding="utf-8")
            local, cloud = snapshot(proj, source)
            self.assertEqual(sorted(cloud), ["SH001"])
            self.assertEqual(unwatched_pending(proj, source, []), [(good.resolve(), "SH001")])
            # 已被自己窗口盯着的在线任务不再重复查询
            self.assertEqual(unwatched_pending(proj, source, [good]), [])


class PreflightTests(unittest.TestCase):
    def test_preflight_missing_node(self):
        from local_video import preflight
        class FakeApi:
            def call(self, path):
                return {"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["modelA"]]}}}}
        with self.assertRaises(ValueError):
            preflight(FakeApi(), {"1": {"class_type": "MissingNode", "inputs": {}}})

    def test_preflight_ok(self):
        from local_video import preflight
        class FakeApi:
            def call(self, path):
                return {"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["modelA"]]}}}}
        graph = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "modelA"}}}
        self.assertIn("通过", preflight(FakeApi(), graph))


class GenerationActiveTests(unittest.TestCase):
    class FakeStudio:
        def __init__(self, root, episode_path):
            self.root = root
            self.episode_path = episode_path
        def state(self):
            return {"shots": {"SH001": []}}

    def test_generation_active_ignores_corrupt_cloud_config(self):
        from video_task_state import generation_active
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            (proj / "cloud_video" / "s1").mkdir(parents=True)
            (proj / "cloud_video" / "s1" / "config.json").write_text("{bad json", encoding="utf-8")
            ep = proj / "episode.json"; ep.write_text("{}", encoding="utf-8")
            studio = self.FakeStudio(proj, ep)
            self.assertFalse(generation_active(studio, "SH001"))


class PendingCheckedShotsTests(unittest.TestCase):
    class FakeStudio:
        def __init__(self, shots):
            self._shots = shots
            self.episode = {"shots": [{"id": sid} for sid in shots]}
        def state(self):
            return {"shots": self._shots}

    def test_pending_checked_shots_filters(self):
        from app import pending_checked_shots
        studio = self.FakeStudio({
            "SH001": [],  # 未提交
            "SH002": [{"state": "downloaded"}],  # 已就绪
            "SH003": [{"state": "running"}],  # 生成中
            "SH004": [{"state": "failed"}],  # 可重做
            "SH005": [{"state": "queued"}],  # 排队中
        })
        todo = pending_checked_shots(studio, ["SH001", "SH002", "SH003", "SH004", "SH005"])
        self.assertEqual(todo, ["SH001", "SH004"])

    def test_pending_checked_shots_skips_deleted(self):
        from app import pending_checked_shots
        studio = self.FakeStudio({"SH001": [], "SH002": []})
        todo = pending_checked_shots(studio, ["SH001", "SH002", "SH999"])
        self.assertEqual(todo, ["SH001", "SH002"])


class VideoOutputNodeFailureTests(unittest.TestCase):
    """任务已跑完但指定输出节点没有MP4时标记失败，避免版本永久卡在排队中。"""

    def poll(self, outputs):
        import contextlib
        import local_video
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "data" / "state.json"; db.parent.mkdir(parents=True, exist_ok=True)
            db.write_text(json.dumps({"shots": {"SH001": [{
                "version": 1, "state": "queued", "task_id": "PID", "backend": "comfy",
                "endpoint": "http://127.0.0.1:8189", "output_node": "92", "seconds": 5}]}}), encoding="utf-8")
            class FakeAPI(local_video.LocalAPI):
                def call(self, path, payload=None, **kw):
                    if path == "/history/PID":
                        return {"PID": {"status": {"status_str": "success"}, "outputs": outputs}}
                    raise AssertionError(path)
            class FakeStudio: pass
            studio = FakeStudio(); studio.root = root; studio.db = db
            studio.lock = lambda: contextlib.nullcontext()
            studio.state = lambda: json.loads(db.read_text(encoding="utf-8"))
            original = local_video.LocalAPI
            local_video.LocalAPI = FakeAPI
            self.addCleanup(setattr, local_video, "LocalAPI", original)
            with self.assertRaises(ValueError) as ctx:
                local_video.LocalStudio.poll(studio, "SH001")
            saved = json.loads(db.read_text(encoding="utf-8"))["shots"]["SH001"][0]
            return str(ctx.exception), saved

    def test_missing_video_output_marks_failed(self):
        message, saved = self.poll({"92": {"gifs": [{"filename": "x.png", "type": "output"}]}})
        self.assertEqual(saved["state"], "failed")
        self.assertIn("92", message)

    def test_two_video_outputs_mark_failed(self):
        items = [{"filename": "a.mp4", "type": "output"}, {"filename": "b.mp4", "type": "output"}]
        message, saved = self.poll({"92": {"gifs": items}})
        self.assertEqual(saved["state"], "failed")


class AutoVideoTests(unittest.TestCase):
    """无人值守本地视频：只提交缺视频的镜头、只查询在跑的任务，失败留痕且不反复重提。"""

    def shots(self):
        return [{"id": "SH001", "frame": "frames/SH001.png", "duration": 5, "video_prompt": "一"},
                {"id": "SH002", "frame": "frames/SH002.png", "duration": 5, "video_prompt": "二"},
                {"id": "SH003", "frame": "frames/missing.png", "duration": 5, "video_prompt": "三"},
                {"id": "SH004", "frame": "frames/SH004.png", "duration": 5, "video_prompt": "四"},
                {"id": "SH005", "frame": "frames/SH005.png", "duration": 5, "video_prompt": "五"}]

    def build(self, root, versions=None):
        import local_video
        shots = self.shots()
        frames = root / "frames"; frames.mkdir(parents=True, exist_ok=True)
        for sid in ("SH001", "SH002", "SH004", "SH005"):
            (frames / (sid + ".png")).write_bytes(b"x")
        db = root / "data" / "state.json"; db.parent.mkdir(parents=True, exist_ok=True)
        cfg = {"local_video": {"url": "http://127.0.0.1:8189"}}
        (root / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        db.write_text(json.dumps({"shots": versions if versions is not None else {}}), encoding="utf-8")
        source = root / "episode" / "episode.json"; source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(json.dumps({"episode_id": "EP001", "title": "T", "shots": shots}, ensure_ascii=False), encoding="utf-8")

        class Fake(local_video.LocalStudio):
            def __init__(self):
                self.root = root; self.db = db; self.cfg = cfg
                self.episode_path = source; self.episode_dir = source.parent
                self.episode = json.loads(source.read_text(encoding="utf-8"))
                self.submitted = []; self.polled = []; self.errors = {}
                self.poll_results = {}
            def state(self): return json.loads(db.read_text(encoding="utf-8"))
            def frame(self, shot, required=True):
                return (root / shot.get("frame", "frames/none.png")).resolve()
            def submit(self, sid, progress=None):
                if self.errors.get(sid): raise ValueError(self.errors[sid])
                self.submitted.append(sid)
                if progress: progress(sid + " 提交本地生成")
                st = self.state()
                st.setdefault("shots", {}).setdefault(sid, []).append({"version": 1, "state": "queued", "task_id": "PID"})
                db.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
                return "本地任务已提交"
            def poll(self, sid):
                self.polled.append(sid)
                if self.errors.get(sid): raise ValueError(self.errors[sid])
                state, message = self.poll_results.get(sid, ("downloaded", "本地视频已取回；技术QC通过，待您验收"))
                st = self.state()
                st.setdefault("shots", {}).setdefault(sid, []).append({"version": 1, "state": state})
                db.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
                return message
        return Fake(), source

    def versions(self):
        return {"SH001": [],
                "SH002": [{"version": 1, "state": "queued", "task_id": "PID"}],
                "SH003": [],
                "SH004": [{"version": 1, "state": "failed"}],
                "SH005": [{"version": 1, "state": "downloaded", "file": "data/SH005/v001/SH005.mp4"}]}

    def test_auto_plan_splits_submit_poll_and_skips(self):
        import local_video
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            studio, source = self.build(root, self.versions())
            submit, poll, skipped = local_video.auto_plan(root, source, studio)
            self.assertEqual(submit, ["SH001"])          # 有首帧、还没提交过的才排队
            self.assertEqual(poll, ["SH002"])             # 在跑的任务只查询取回，不重复提交
            self.assertEqual([sid for sid, _ in skipped], ["SH003", "SH004"])
            self.assertIn("尚无首帧", skipped[0][1])
            self.assertIn("未完成", skipped[1][1])
            self.assertEqual(studio.submitted, [])        # 只规划，不动手

    def test_skip_summary_reports_every_reason_not_just_the_first(self):
        """无人值守状态栏只有一行：不同原因要按「原因 + 镜数」一起报，不能只报第一条。"""
        import local_video
        skipped = [("SH003", "尚无首帧，先在第05步生成或导入"),
                   ("SH004", "上次本地生成未完成（failed），请查看 ComfyUI 后手动重做"),
                   ("SH005", "尚无首帧，先在第05步生成或导入")]
        summary = local_video.skip_summary(skipped)
        self.assertIn("尚无首帧，先在第05步生成或导入 2 镜", summary)
        self.assertIn("上次本地生成未完成（failed），请查看 ComfyUI 后手动重做 1 镜", summary)
        self.assertLess(summary.index("尚无首帧"), summary.index("上次本地生成未完成"))   # 多的排前面
        many = [(str(i), "原因%d" % i) for i in range(6)]
        cut = local_video.skip_summary(many, limit=2)
        self.assertIn("另有 4 类原因", cut)
        self.assertEqual(len(cut.split("；")), 3)                                       # 2 类 + 一句「另有」
        self.assertEqual(local_video.skip_summary([]), "")

    def test_auto_skip_notice_has_stable_deduplication_key_and_summary(self):
        from local_video import auto_skip_notice
        skipped = [('SH001', '尚无首帧'), ('SH002', '尚无首帧')]
        notice, message = auto_skip_notice('episode.json', skipped)
        self.assertEqual(notice, ('episode.json', tuple(skipped)))
        self.assertIn('2 镜跳过', message)
        self.assertIn('尚无首帧 2 镜', message)

    def test_auto_poll_decision_separates_notice_repeat_and_dispatch(self):
        from local_video import auto_poll_decision
        self.assertEqual(auto_poll_decision('episode.json', [], [], [], None)['action'], 'idle')
        self.assertEqual(auto_poll_decision('episode.json', [], [], [('SH001', '尚无首帧')], None)['action'], 'notice')
        self.assertEqual(auto_poll_decision('episode.json', ['SH001'], [], [], ('SH001',))['action'], 'skip')
        self.assertEqual(auto_poll_decision('episode.json', [], ['SH001'], [], ())['action'], 'dispatch')

    def test_auto_plan_rejects_cloud_backend(self):
        import local_video
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _, source = self.build(root, self.versions())
            class Cloud: pass
            with self.assertRaises(ValueError) as ctx:
                local_video.auto_plan(root, source, Cloud())
            self.assertIn("本地 ComfyUI", str(ctx.exception))

    def test_auto_batch_submits_polls_and_reports(self):
        import local_video, native_apps
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            studio, source = self.build(root, self.versions())
            logs = []
            with patch.object(native_apps, "wait_comfy", lambda url, report=None, timeout=90: None):
                summary = local_video.auto_batch(root, source, logs.append, studio=studio)
            self.assertEqual(studio.submitted, ["SH001"])
            self.assertEqual(studio.polled, ["SH002"])
            self.assertIn("已提交 1 镜", summary)
            self.assertIn("已取回 1 镜", summary)
            self.assertIn("跳过 2 镜", summary)
            self.assertIn("SH001：提交本地生成", logs)

    def test_failed_submission_is_recorded_and_not_retried(self):
        import local_video, native_apps
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            studio, source = self.build(root, self.versions())
            studio.errors["SH001"] = "本地 ComfyUI 未运行"
            with patch.object(native_apps, "wait_comfy", lambda url, report=None, timeout=90: None):
                summary = local_video.auto_batch(root, source, studio=studio)
            self.assertIn("未完成 1 镜", summary)
            saved = json.loads((root / "data" / "state.json").read_text(encoding="utf-8"))["shots"]["SH001"][-1]
            self.assertEqual(saved["state"], "failed")
            self.assertIn("无人值守自动提交失败", saved["note"])
            # 下一轮：失败镜头只跳过并写明原因，不再重复提交
            studio.errors.pop("SH001")
            submit, _, skipped = local_video.auto_plan(root, source, studio)
            self.assertEqual(submit, [])
            self.assertIn("SH001", [sid for sid, _ in skipped])


    def test_poll_failure_is_reported_as_failed_not_waiting(self):
        """节点报错时 LocalStudio.poll 先把版本标成 failed 再返回文案；无人值守要按状态报失败，
        只按文案猜的话会永远显示「仍在生成」，用户看不出任务已经死掉。"""
        import local_video, native_apps
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            studio, source = self.build(root, self.versions())
            studio.poll_results["SH002"] = ("failed", "本地生成失败，请在ComfyUI查看显存或节点错误")
            with patch.object(native_apps, "wait_comfy", lambda url, report=None, timeout=90: None):
                summary = local_video.auto_batch(root, source, studio=studio)
            self.assertIn("未完成 1 镜", summary)
            self.assertNotIn("仍在生成", summary)

    def test_already_downloaded_poll_counts_as_fetched(self):
        import local_video, native_apps
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            studio, source = self.build(root, self.versions())
            studio.poll_results["SH002"] = ("downloaded", "已下载，不重复取回")
            with patch.object(native_apps, "wait_comfy", lambda url, report=None, timeout=90: None):
                summary = local_video.auto_batch(root, source, studio=studio)
            self.assertIn("已取回 1 镜", summary)
            self.assertNotIn("仍在生成", summary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
