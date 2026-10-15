# -*- coding: utf-8 -*-
"""核心生产流程集成自检（用假适配器跑通提交/查询/下载/质检路径，不发真实请求）。运行：python test_integration.py"""
import base64, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import engine
import project_settings
from agent.core import save
from agent.wan import ArkRejected

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
FFMPEG = r"D:/Tools/ffmpeg/bin/ffmpeg.exe"
FFPROBE = r"D:/Tools/ffmpeg/bin/ffprobe.exe"


class FakeAdapter:
    def __init__(self, cfg):
        self.cfg = cfg
        self.submitted = []
    def payload(self, shot, frame):
        return {"model": self.cfg["model"], "prompt": shot["video_prompt"], "duration": shot["duration"]}
    def submit(self, shot, frame, request_id, *, payload=None):
        self.submitted.append((shot["id"], request_id))
        return "fake-task-1234567890abcdef"
    def poll(self, task_id):
        return {"status": "queued", "url": None}


def build_project(td, budget=100, live=True):
    t = Path(td); proj = t / "p"
    (proj / "episode" / "frames").mkdir(parents=True)
    (proj / "episode" / "frames" / "SH001.png").write_bytes(PNG)
    (proj / "episode" / "assets.json").write_text("{}", encoding="utf-8")
    shot = {"id": "SH001", "title": "镜头", "duration": 5, "characters": [], "location": "LOC_001",
            "frame": "frames/SH001.png", "video_prompt": "画面与对白", "dialogue": [],
            "upload_assets": False, "generate_audio": True}
    ep = {"episode_id": "EP001", "title": "T", "shots": [shot]}
    (proj / "episode" / "episode.json").write_text(json.dumps(ep, ensure_ascii=False), encoding="utf-8")
    private = proj / "private"; private.mkdir()
    (private / ".env").write_text("DASHSCOPE_API_KEY=sk-test\n", encoding="utf-8")
    cfg = {"episode_dir": str(proj / "episode"), "episode_file": str(proj / "episode" / "episode.json"),
           "budget_seconds": budget, "reserve_seconds": 0, "live_enabled": live,
           "ffmpeg": FFMPEG, "ffprobe": FFPROBE,
           "base_url": "https://dashscope.aliyuncs.com/api/v1", "model": "wan2.6-i2v-flash",
           "cloud_provider": "wan", "key_env": "DASHSCOPE_API_KEY", "project_dir": str(private)}
    (proj / "config.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    return proj


class SubmitFlowTests(unittest.TestCase):
    def test_submit_reserves_and_queues(self):
        with tempfile.TemporaryDirectory() as td:
            proj = build_project(td)
            st = engine.Studio(proj, factory=FakeAdapter)
            msg = st.submit("SH001")
            self.assertIn("已提交", msg)
            v = st.state()["shots"]["SH001"][-1]
            self.assertEqual(v["state"], "queued")
            self.assertEqual(v["task_id"], "fake-task-1234567890abcdef")
            self.assertTrue((st.root / "data" / "SH001" / "v001" / "request.json").is_file())

    def test_submit_blocks_without_budget(self):
        with tempfile.TemporaryDirectory() as td:
            proj = build_project(td, budget=0)
            st = engine.Studio(proj, factory=FakeAdapter)
            with self.assertRaises(ValueError):
                st.submit("SH001")

    def test_duplicate_downloaded_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            proj = build_project(td)
            st = engine.Studio(proj, factory=FakeAdapter)
            state = st.state()
            state["shots"]["SH001"].append({"version": 1, "state": "downloaded", "seconds": 5, "charged": True})
            save(st.db, state)
            with self.assertRaises(ValueError):
                st.submit("SH001")

    def test_poll_download_and_qc(self):
        with tempfile.TemporaryDirectory() as td:
            proj = build_project(td)
            mp4 = Path(td) / "clip.mp4"
            subprocess.run([FFMPEG, "-y", "-v", "error",
                            "-f", "lavfi", "-i", "color=c=black:s=640x360:d=5",
                            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:d=5",
                            "-c:v", "libx264", "-c:a", "aac", "-shortest", str(mp4)], check=True)

            class Adapter(FakeAdapter):
                def __init__(self, cfg):
                    super().__init__(cfg)
                    self.video = mp4.read_bytes()
                def poll(self, task_id):
                    return {"status": "succeeded", "url": "https://example.com/v.mp4"}
                def download_video(self, task_id, dest):
                    Path(dest).write_bytes(self.video)

            st = engine.Studio(proj, factory=Adapter)
            st.submit("SH001")
            msg = st.poll("SH001")
            self.assertIn("已下载", msg)
            v = st.state()["shots"]["SH001"][-1]
            self.assertEqual(v["state"], "downloaded")
            self.assertTrue(v.get("qc_pass"))


class AutoReviewTests(unittest.TestCase):
    """无人值守自动验收：开启后下载且技术质检通过的版本自动通过，关闭时仍等人工验收。"""

    def run_download(self, td, auto):
        from agent.core import read
        proj = build_project(td)
        if auto:
            project_settings.set_auto_review(proj, True)
        mp4 = Path(td) / "clip.mp4"
        subprocess.run([FFMPEG, "-y", "-v", "error",
                        "-f", "lavfi", "-i", "color=c=black:s=640x360:d=5",
                        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:d=5",
                        "-c:v", "libx264", "-c:a", "aac", "-shortest", str(mp4)], check=True)

        class Adapter(FakeAdapter):
            def __init__(self, cfg):
                super().__init__(cfg)
                self.video = mp4.read_bytes()
            def poll(self, task_id):
                return {"status": "succeeded", "url": "https://example.com/v.mp4"}
            def download_video(self, task_id, dest):
                Path(dest).write_bytes(self.video)

        st = engine.Studio(proj, factory=Adapter)
        st.submit("SH001")
        message = st.poll("SH001")
        return proj, st, message

    def test_auto_review_passes_downloaded_version(self):
        with tempfile.TemporaryDirectory() as td:
            proj, st, message = self.run_download(td, auto=True)
            v = st.state()["shots"]["SH001"][-1]
            self.assertTrue(v.get("qc_pass"))
            self.assertEqual(v.get("review"), "pass")
            self.assertIn("无人值守自动验收", v.get("review_note", ""))
            self.assertIn("自动验收", message)
            # 通过后即可直接自动剪辑，不再要求人工点“通过”。
            master = Path(st.assemble())
            self.assertTrue(master.is_file())
            self.assertEqual(master.suffix, ".mp4")

    def test_auto_review_off_waits_for_human(self):
        with tempfile.TemporaryDirectory() as td:
            proj, st, message = self.run_download(td, auto=False)
            v = st.state()["shots"]["SH001"][-1]
            self.assertTrue(v.get("qc_pass"))
            self.assertEqual(v.get("review"), "pending")
            self.assertIn("等您验收", message)
            with self.assertRaises(ValueError):
                st.assemble()

    def test_auto_review_is_not_content_review(self):
        """技术正确不等于内容审核通过：无人值守只做技术放行，面板必须分开说。"""
        with tempfile.TemporaryDirectory() as td:
            proj, st, _message = self.run_download(td, auto=True)
            v = st.state()["shots"]["SH001"][-1]
            self.assertEqual(engine.review_source(v), "auto")
            self.assertFalse(engine.content_reviewed(v))
            self.assertEqual(engine.review_label(v), "技术自动放行（未做内容审核）")
            # 自动技术放行仍算「已验收」，既有自动拼接默认不被暗改。
            self.assertEqual(len(engine.approved_versions([v])), 1)

    def test_user_review_marks_content_reviewed(self):
        """用户显式点「通过」才算内容审核，并在面板标成已确认。"""
        with tempfile.TemporaryDirectory() as td:
            proj, st, _message = self.run_download(td, auto=True)
            st.review("SH001", "pass", "人工确认内容无误")
            v = st.state()["shots"]["SH001"][-1]
            self.assertEqual(engine.review_source(v), "user")
            self.assertTrue(engine.content_reviewed(v))
            self.assertEqual(engine.review_label(v), "通过（您已确认内容）")

    def test_legacy_records_infer_review_source(self):
        """老记录没有 review_by：按旧前缀认出自动放行，认不出的按真人验收。"""
        self.assertEqual(engine.review_source({"review": "pass", "review_note": "无人值守自动验收：技术质检通过"}), "auto")
        self.assertEqual(engine.review_source({"review": "pass", "review_note": "人工确认"}), "user")
        self.assertEqual(engine.review_source({"review": "pass"}), "user")
        self.assertEqual(engine.review_source({"review": "pending"}), "")

    def test_setting_keeps_other_ui_keys(self):
        with tempfile.TemporaryDirectory() as td:
            proj = build_project(td)
            ui = proj / "ui_settings.json"
            ui.write_text(json.dumps({"adopted_storyboards": ["storyboard/x.json"]}, ensure_ascii=False), encoding="utf-8")
            self.assertFalse(project_settings.auto_review(proj))
            self.assertTrue(project_settings.set_auto_review(proj, True))
            data = json.loads(ui.read_text(encoding="utf-8"))
            self.assertEqual(data.get("adopted_storyboards"), ["storyboard/x.json"])
            self.assertIs(data.get("auto_review"), True)
            self.assertFalse(project_settings.set_auto_review(proj, False))
            self.assertFalse(project_settings.auto_review(proj))
            self.assertEqual(json.loads(ui.read_text(encoding="utf-8")).get("adopted_storyboards"), ["storyboard/x.json"])


class DownloadResumeTests(unittest.TestCase):
    """O28：下载中断后再次查询续取，不重新生成、不重投新版本。"""

    def test_download_failure_resumes_without_resubmitting(self):
        with tempfile.TemporaryDirectory() as td:
            proj = build_project(td)
            mp4 = Path(td) / "clip.mp4"
            subprocess.run([FFMPEG, "-y", "-v", "error",
                            "-f", "lavfi", "-i", "color=c=black:s=640x360:d=5",
                            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:d=5",
                            "-c:v", "libx264", "-c:a", "aac", "-shortest", str(mp4)], check=True)

            attempts = []
            class Adapter(FakeAdapter):
                def __init__(self, cfg):
                    super().__init__(cfg)
                    self.video = mp4.read_bytes()
                def poll(self, task_id):
                    return {"status": "succeeded", "url": "https://example.com/v.mp4"}
                def download_video(self, task_id, dest):
                    attempts.append(dest)
                    if len(attempts) == 1:
                        raise RuntimeError("network reset")
                    Path(dest).write_bytes(self.video)

            st = engine.Studio(proj, factory=Adapter)
            st.submit("SH001")
            with self.assertRaises(RuntimeError):
                st.poll("SH001")
            versions = st.state()["shots"]["SH001"]
            self.assertEqual(len(versions), 1)              # 不重投：没有新版本
            self.assertEqual(versions[-1]["state"], "succeeded")
            self.assertTrue(versions[-1].get("download_error"))
            self.assertTrue(versions[-1].get("charged"))
            # 再次查询：续取成功，仍然只有一个版本，远端任务没有被重发。
            message = st.poll("SH001")
            self.assertIn("已下载", message)
            versions = st.state()["shots"]["SH001"]
            self.assertEqual(len(versions), 1)
            self.assertEqual(versions[-1]["state"], "downloaded")


class AutoEditReadyTests(unittest.TestCase):
    """无人值守自动粗剪：整集验收通过才拼接，同一批验收结果只拼一次，编码期间不占项目锁。"""

    def download(self, td, auto=True):
        from pathlib import Path as _Path
        proj = build_project(td)
        if auto:
            project_settings.set_auto_review(proj, True)
        mp4 = _Path(td) / "clip.mp4"
        subprocess.run([FFMPEG, "-y", "-v", "error",
                        "-f", "lavfi", "-i", "color=c=black:s=640x360:d=5",
                        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:d=5",
                        "-c:v", "libx264", "-c:a", "aac", "-shortest", str(mp4)], check=True)

        class Adapter(FakeAdapter):
            def __init__(self, cfg):
                super().__init__(cfg)
                self.video = mp4.read_bytes()
            def poll(self, task_id):
                return {"status": "succeeded", "url": "https://example.com/v.mp4"}
            def download_video(self, task_id, dest):
                _Path(dest).write_bytes(self.video)

        st = engine.Studio(proj, factory=Adapter)
        st.submit("SH001")
        st.poll("SH001")
        return proj, st

    def test_ready_when_every_shot_is_approved(self):
        with tempfile.TemporaryDirectory() as td:
            proj, st = self.download(td)
            digest, rows = st.auto_edit_ready()
            self.assertIsInstance(digest, str)
            self.assertEqual([row["shot"] for row in rows], ["SH001"])
            self.assertEqual(st.auto_edit_ready()[0], digest)      # 同一批验收结果指纹稳定

    def test_unapproved_shot_waits_with_reason(self):
        with tempfile.TemporaryDirectory() as td:
            proj, st = self.download(td, auto=False)
            digest, waiting = st.auto_edit_ready()
            self.assertIsNone(digest)
            self.assertTrue(any("尚未验收" in item for item in waiting))

    def test_missing_video_waits_with_reason(self):
        with tempfile.TemporaryDirectory() as td:
            proj, st = self.download(td)
            v = st.state()["shots"]["SH001"][-1]
            (proj / v["file"]).unlink()
            digest, waiting = st.auto_edit_ready()
            self.assertIsNone(digest)
            self.assertTrue(any("缺失" in item for item in waiting))

    def test_digest_changes_with_new_approved_version(self):
        with tempfile.TemporaryDirectory() as td:
            from agent.core import file_hash, read, save
            proj, st = self.download(td)
            first, _ = st.auto_edit_ready()
            db = proj / "data" / "state.json"
            state = read(db)
            version = dict(state["shots"]["SH001"][-1])
            clip = proj / version["file"]
            redo = clip.with_name("SH001_重做.mp4")
            redo.write_bytes(clip.read_bytes() + b"v2")
            version.update(version=version["version"] + 1, file=redo.relative_to(proj).as_posix(), sha256=file_hash(redo))
            state["shots"]["SH001"].append(version); save(db, state)
            second, _ = st.auto_edit_ready()
            self.assertNotEqual(first, second)                     # 重做并重新验收后才会再拼一版

    def test_assemble_releases_project_lock_during_encoding(self):
        with tempfile.TemporaryDirectory() as td:
            proj, st = self.download(td)
            other = engine.Studio(proj, factory=FakeAdapter)
            observed = {}
            real = engine.command
            def spy(args, cwd=None):
                if not observed:
                    try:
                        with other.lock(): observed["free"] = True
                    except ValueError:
                        observed["free"] = False
                return real(args, cwd=cwd)
            engine.command = spy
            self.addCleanup(setattr, engine, "command", real)
            master = Path(st.assemble())
            self.assertTrue(master.is_file())
            self.assertTrue(observed.get("free"), "编码期间项目锁应已释放，否则下载／验收会报「另一操作正在运行」")


class FailureFlowTests(unittest.TestCase):
    def test_submit_rejected_4xx(self):
        with tempfile.TemporaryDirectory() as td:
            proj = build_project(td)
            class Reject4xx(FakeAdapter):
                def submit(self, shot, frame, request_id, *, payload=None):
                    raise ArkRejected("HTTP 400 / bad")
            st = engine.Studio(proj, factory=Reject4xx)
            with self.assertRaises(ArkRejected):
                st.submit("SH001")
            v = st.state()["shots"]["SH001"][-1]
            self.assertEqual(v["state"], "rejected")
            self.assertFalse(v.get("charged"))

    def test_submit_5xx_unknown_charged(self):
        with tempfile.TemporaryDirectory() as td:
            proj = build_project(td)
            class Reject5xx(FakeAdapter):
                def submit(self, shot, frame, request_id, *, payload=None):
                    raise ArkRejected("HTTP 500 / server")
            st = engine.Studio(proj, factory=Reject5xx)
            with self.assertRaises(ArkRejected):
                st.submit("SH001")
            v = st.state()["shots"]["SH001"][-1]
            self.assertEqual(v["state"], "unknown")
            self.assertTrue(v.get("charged"))

    def test_submit_connection_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            proj = build_project(td)
            class Drop(FakeAdapter):
                def submit(self, shot, frame, request_id, *, payload=None):
                    raise RuntimeError("boom")
            st = engine.Studio(proj, factory=Drop)
            with self.assertRaises(RuntimeError):
                st.submit("SH001")
            v = st.state()["shots"]["SH001"][-1]
            self.assertEqual(v["state"], "unknown")

    def test_poll_failed(self):
        with tempfile.TemporaryDirectory() as td:
            proj = build_project(td)
            class Fail(FakeAdapter):
                def poll(self, task_id):
                    return {"status": "failed", "error_code": "E1"}
            st = engine.Studio(proj, factory=Fail)
            st.submit("SH001")
            msg = st.poll("SH001")
            self.assertIn("失败", msg)
            self.assertEqual(st.state()["shots"]["SH001"][-1]["state"], "failed")


    def test_poll_succeeded_without_url_asks_for_console(self):
        with tempfile.TemporaryDirectory() as td:
            proj = build_project(td)
            class NoUrl(FakeAdapter):
                def poll(self, task_id):
                    return {"status": "succeeded", "url": None}
            st = engine.Studio(proj, factory=NoUrl)
            st.submit("SH001")
            with self.assertRaises(RuntimeError) as ctx:
                st.poll("SH001")
            self.assertIn("没有返回视频地址", str(ctx.exception))
            self.assertEqual(st.state()["shots"]["SH001"][-1]["state"], "succeeded")


class BatchReviewTests(unittest.TestCase):
    """勾选多镜后一次验收通过：合格镜通过，不合格镜跳过并说明原因。"""

    def test_review_many_passes_and_reports_skips(self):
        with tempfile.TemporaryDirectory() as td:
            proj = build_project(td)
            episode = json.loads((proj / "episode" / "episode.json").read_text(encoding="utf-8"))
            episode["shots"].append({**episode["shots"][0], "id": "SH002"})
            (proj / "episode" / "episode.json").write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")
            st = engine.Studio(proj, factory=FakeAdapter)
            state = st.state()
            state["shots"]["SH001"].append({"version": 1, "state": "downloaded", "seconds": 5, "charged": True, "qc_pass": True})
            state["shots"]["SH002"].append({"version": 1, "state": "downloaded", "seconds": 5, "charged": True, "qc_pass": False})
            save(st.db, state)
            message = st.review_many(["SH001", "SH002", "SH999"], "pass", "批量验收")
            self.assertIn("已通过 1/3 镜", message)
            self.assertIn("SH002", message)
            saved = st.state()["shots"]
            self.assertEqual(saved["SH001"][-1]["review"], "pass")
            self.assertEqual(saved["SH001"][-1]["review_note"], "批量验收")
            self.assertNotIn("review", saved["SH002"][-1])

    def test_review_many_needs_selection(self):
        with tempfile.TemporaryDirectory() as td:
            proj = build_project(td)
            st = engine.Studio(proj, factory=FakeAdapter)
            with self.assertRaises(ValueError):
                st.review_many([], "pass")


class PartialAssembleTests(unittest.TestCase):
    """无人值守自动剪辑：部分镜头未就绪时跳过它们先出成片；全部未就绪仍报错。"""

    def prepare(self, td, count=3, ready=2):
        proj = build_project(td)
        base = {"title": "镜头", "duration": 5, "characters": [], "location": "LOC_001",
                "video_prompt": "画面与对白", "dialogue": [], "upload_assets": False, "generate_audio": True}
        shots = []
        for i in range(1, count + 1):
            sid = "SH%03d" % i
            (proj / "episode" / "frames" / (sid + ".png")).write_bytes(PNG)
            shots.append({**base, "id": sid, "frame": "frames/" + sid + ".png"})
        (proj / "episode" / "episode.json").write_text(
            json.dumps({"episode_id": "EP001", "title": "T", "shots": shots}, ensure_ascii=False), encoding="utf-8")
        mp4 = Path(td) / "clip.mp4"
        subprocess.run([FFMPEG, "-y", "-v", "error",
                        "-f", "lavfi", "-i", "color=c=black:s=640x360:d=5",
                        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:d=5",
                        "-c:v", "libx264", "-c:a", "aac", "-shortest", str(mp4)], check=True)
        st = engine.Studio(proj, factory=FakeAdapter)
        state = st.state()
        folder = proj / "episode" / "videos"
        for i in range(1, ready + 1):
            sid = "SH%03d" % i
            folder.mkdir(parents=True, exist_ok=True)
            dest = folder / (sid + ".mp4")
            dest.write_bytes(mp4.read_bytes())
            state["shots"].setdefault(sid, []).append(
                {"version": 1, "state": "downloaded", "seconds": 5, "charged": True, "qc_pass": True,
                 "review": "pass", "file": "episode/videos/" + sid + ".mp4", "sha256": engine.file_hash(dest)})
        save(st.db, state)
        return proj, st, ["SH%03d" % i for i in range(1, count + 1)]

    def test_partial_assemble_skips_unready_shots(self):
        with tempfile.TemporaryDirectory() as td:
            proj, st, ids = self.prepare(td)
            report = {}
            master = Path(st.assemble(skip_unready=True, report=report))
            self.assertTrue(master.is_file())
            self.assertEqual(master.suffix, ".mp4")
            self.assertEqual([item.split()[0] for item in report["skipped"]], [ids[2]])
            manifest = json.loads((master.parent / "edit_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual([item["shot"] for item in manifest], ids[:2])
            # 粗剪覆盖率写进报告与可恢复清单：包含/缺失镜头与总时长都能被界面和交付核对。
            self.assertEqual(report["included"], ids[:2])
            self.assertEqual(report["expected"], 3)
            self.assertEqual(report["duration"], 10.0)
            bundle = json.loads((master.parent / "edit_bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle["master"], "MASTER.mp4")
            self.assertEqual([item["shot"] for item in bundle["manifest"]], ids[:2])
            self.assertEqual(bundle["coverage"]["included"], ids[:2])
            self.assertEqual(bundle["coverage"]["expected"], 3)

    def test_partial_assemble_needs_at_least_one_shot(self):
        with tempfile.TemporaryDirectory() as td:
            proj, st, ids = self.prepare(td, ready=0)
            with self.assertRaises(ValueError) as ctx:
                st.assemble(skip_unready=True)
            message = str(ctx.exception)
            self.assertIn("没有可剪辑的镜头", message)
            self.assertIn(ids[0], message)
            self.assertFalse((proj / "exports").exists())

    def test_missing_file_is_skipped_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as td:
            proj, st, ids = self.prepare(td)
            (proj / "episode" / "videos" / (ids[0] + ".mp4")).unlink()
            report = {}
            master = Path(st.assemble(skip_unready=True, report=report))
            manifest = json.loads((master.parent / "edit_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual([item["shot"] for item in manifest], [ids[1]])
            self.assertIn("视频文件缺失", report["skipped"][0])

    def test_strict_assemble_still_rejects_partial(self):
        with tempfile.TemporaryDirectory() as td:
            proj, st, ids = self.prepare(td)
            with self.assertRaises(ValueError) as ctx:
                st.assemble()
            self.assertIn(ids[2], str(ctx.exception))
            self.assertIn("缺少已下载", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
