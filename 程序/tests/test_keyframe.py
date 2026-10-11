# -*- coding: utf-8 -*-
"""首帧导入路径安全与校验自检。运行：python test_keyframe.py"""
import base64, json, os, sys, tempfile, time, types, unittest
from pathlib import Path
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

from agent.core import read
from keyframe_import import register, fingerprint
from keyframe_evidence import source_evidence

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


def make_source(td):
    t = Path(td); proj = t / "p"
    (proj / "episode" / "frames").mkdir(parents=True)
    ep = {"episode_id": "EP001", "title": "T", "shots": [
        {"id": "SH001", "title": "镜头", "duration": 5, "frame": "frames/SH001.png", "video_prompt": "x"}]}
    src = proj / "episode" / "episode.json"
    src.write_text(json.dumps(ep, ensure_ascii=False), encoding="utf-8")
    return proj, src, ep


class FakeStatus:
    def __init__(self): self.messages = []

    def set(self, value): self.messages.append(value)


class FakeWindow:
    """假窗口：手动触发 tk_timers 登记的定时器，测试里不用真的等 1.5 秒。"""

    def __init__(self):
        self.jobs = {}
        self.seq = 0

    def bind(self, *args, **kwargs): pass

    def winfo_exists(self): return True

    def after(self, interval, callback):
        self.seq += 1
        self.jobs[self.seq] = callback
        return self.seq

    def after_cancel(self, job): self.jobs.pop(job, None)

    def fire(self):
        jobs, self.jobs = list(self.jobs.values()), {}
        for callback in jobs: callback()
        return len(jobs)


class WatchTests(unittest.TestCase):
    def make_manifest(self, proj, src, ep, output):
        folder = proj / "workflows" / "首帧批次" / "批次1"
        folder.mkdir(parents=True)
        (folder / output).write_bytes(PNG)
        manifest = folder / "批次.json"
        manifest.write_text(json.dumps({"source": str(src), "items": [
            {"shot_id": "SH001", "state": "pending", "output": output,
             "shot_signature": fingerprint(ep["shots"][0]),
             "source_evidence": source_evidence(src, ep, ep['shots'][0])}]}, ensure_ascii=False), encoding="utf-8")
        return manifest

    def test_poll_imports_ready_frame_without_reading_whole_file(self):
        from keyframe_import import watch
        with tempfile.TemporaryDirectory() as td:
            proj, src, ep = make_source(td)
            manifest = self.make_manifest(proj, src, ep, "SH001.png")
            app = types.SimpleNamespace(root=proj, win=FakeWindow(), status=FakeStatus(),
                                        keyframe_import_watchers=set())
            reads = [0]
            original = Path.read_bytes

            def counting(path, *args, **kwargs):
                reads[0] += 1
                return original(path, *args, **kwargs)

            Path.read_bytes = counting
            self.addCleanup(setattr, Path, "read_bytes", original)
            watch(app, manifest)
            self.assertEqual(app.win.fire(), 1, "只应登记一个轮询定时器")
            self.assertEqual(reads[0], 0, "第一次轮询只登记文件签名，不该整图读取")
            self.assertEqual(read(manifest)["items"][0]["state"], "pending")
            app.win.fire()
            item = read(manifest)["items"][0]
            self.assertEqual(item["state"], "imported")
            self.assertEqual(reads[0], 1, "只有导入时的 register 需要读整图")
            self.assertTrue(Path(item["file"]).is_file())
            self.assertEqual(app.status.messages, ["SH001 首帧已自动导入"])


class RegisterTests(unittest.TestCase):
    def test_import_valid_frame(self):
        with tempfile.TemporaryDirectory() as td:
            proj, src, ep = make_source(td)
            img = Path(td) / "frame.png"; img.write_bytes(PNG)
            item = {"shot_id": "SH001", "shot_signature": fingerprint(ep["shots"][0]), "source_evidence": source_evidence(src, ep, ep["shots"][0])}
            dest = register(src, item, img)
            self.assertTrue(dest.is_file())
            new_frame = read(src)["shots"][0]["frame"]
            self.assertTrue((proj / "episode" / new_frame).is_file())
            self.assertTrue((proj / "episode" / "历史版本" / "首帧导入").is_dir())

    def test_modified_shot_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            proj, src, ep = make_source(td)
            img = Path(td) / "frame.png"; img.write_bytes(PNG)
            item = {"shot_id": "SH001", "shot_signature": fingerprint({"id": "SH001", "different": True})}
            with self.assertRaises(ValueError):
                register(src, item, img)

    def test_bad_sid_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            proj, src, ep = make_source(td)
            img = Path(td) / "frame.png"; img.write_bytes(PNG)
            item = {"shot_id": "../bad", "shot_signature": fingerprint(ep["shots"][0])}
            with self.assertRaises(ValueError):
                register(src, item, img)

    def test_non_png_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            proj, src, ep = make_source(td)
            img = Path(td) / "frame.png"; img.write_bytes(b"not png")
            item = {"shot_id": "SH001", "shot_signature": fingerprint(ep["shots"][0]), "source_evidence": source_evidence(src, ep, ep["shots"][0])}
            with self.assertRaises(ValueError):
                register(src, item, img)

    def test_association_failure_keeps_old_source_and_published_frame(self):
        with tempfile.TemporaryDirectory() as td:
            proj, src, ep = make_source(td)
            before = src.read_bytes()
            img = Path(td) / "frame.png"; img.write_bytes(PNG)
            item = {"shot_id": "SH001", "shot_signature": fingerprint(ep["shots"][0]), "source_evidence": source_evidence(src, ep, ep["shots"][0])}
            with patch('keyframe_import.save', side_effect=OSError('磁盘已满')):
                with self.assertRaises(OSError): register(src, item, img)
            self.assertEqual(src.read_bytes(), before)
            self.assertEqual(len(list((proj / "episode" / "frames").glob("EP001_SH001_*.png"))), 1)


class BatchSignatureTests(unittest.TestCase):
    def test_signature_tracks_missing_references_for_each_pending_shot(self):
        from keyframe_batch import batch_signature
        pending = [{'id': 'SH001'}, {'id': 'SH002'}]
        refs = lambda shot: [('CHAR', 'C001')] if shot['id'] == 'SH001' else [('PROP', 'P001'), ('LOC', 'L001')]
        self.assertEqual(batch_signature('source.json', pending, {'C001', 'L001'}, refs),
                         ('source.json', (('SH001', 0), ('SH002', 1))))

    def test_signature_changes_when_a_referenced_asset_becomes_ready(self):
        from keyframe_batch import batch_signature
        pending = [{'id': 'SH001'}]
        refs = lambda _shot: [('CHAR', 'C001')]
        missing = batch_signature('source.json', pending, set(), refs)
        ready = batch_signature('source.json', pending, {'C001'}, refs)
        self.assertNotEqual(missing, ready)

    def test_automatic_poll_decision_distinguishes_quiet_skip_and_notice(self):
        from keyframe_batch import automatic_poll_decision
        self.assertEqual(automatic_poll_decision(True, 'done', ('batch',), None)['action'], 'quiet')
        self.assertEqual(automatic_poll_decision(False, '', None, None)['action'], 'quiet')
        self.assertEqual(automatic_poll_decision(False, 'blocked', ('batch',), ('batch',))['action'], 'skip')
        self.assertEqual(automatic_poll_decision(False, 'blocked', ('batch',), None)['action'], 'notice')


class FramePromptTests(unittest.TestCase):
    def fp(self, shot):
        from keyframe_batch import frame_prompt
        return frame_prompt(shot)

    def test_uses_frame_prompt(self):
        self.assertEqual(self.fp({"frame_prompt": "一个男孩"}), "一个男孩")

    def test_falls_back_to_keyframe_prompt(self):
        self.assertEqual(self.fp({"keyframe_prompt": "x"}), "x")

    def test_no_video_prompt_substitution(self):
        self.assertEqual(self.fp({"video_prompt": "动作"}), "")

    def test_appends_ordinary_props(self):
        text = self.fp({"image_prompt": "x", "ordinary_props": [{"name": "杯子", "description": "玻璃杯"}]})
        self.assertIn("杯子", text)


class CandidatesTests(unittest.TestCase):
    def make(self, td, with_frames=()):
        proj = Path(td) / "p"; (proj / "episode" / "frames").mkdir(parents=True)
        shots = []
        for i in (1, 2):
            sid = f"SH{i:03d}"; frame = f"frames/{sid}.png"
            if sid in with_frames:
                (proj / "episode" / frame).write_bytes(PNG)
            shots.append({"id": sid, "title": "x", "duration": 5, "frame": frame, "video_prompt": "x"})
        src = proj / "episode" / "episode.json"
        src.write_text(json.dumps({"episode_id": "EP001", "title": "T", "shots": shots}, ensure_ascii=False), encoding="utf-8")
        return src

    def test_all_pending(self):
        from keyframe_batch import candidates
        with tempfile.TemporaryDirectory() as td:
            src = self.make(td)
            self.assertEqual([s["id"] for s in candidates(src)], ["SH001", "SH002"])

    def test_skips_existing(self):
        from keyframe_batch import candidates
        with tempfile.TemporaryDirectory() as td:
            src = self.make(td, with_frames=("SH001",))
            self.assertEqual([s["id"] for s in candidates(src)], ["SH002"])

    def test_existing_shot_id_raises(self):
        from keyframe_batch import candidates
        with tempfile.TemporaryDirectory() as td:
            src = self.make(td, with_frames=("SH001",))
            with self.assertRaises(ValueError):
                candidates(src, shot_id="SH001")

    def test_empty_ids_raises(self):
        from keyframe_batch import candidates
        with tempfile.TemporaryDirectory() as td:
            src = self.make(td)
            with self.assertRaises(ValueError):
                candidates(src, shot_ids=[])

    def test_non_dict_episode_rejected(self):
        from keyframe_batch import candidates
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; (proj / "episode" / "frames").mkdir(parents=True)
            src = proj / "episode" / "episode.json"; src.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValueError):
                candidates(src)

    def test_non_list_shots_rejected(self):
        from keyframe_batch import candidates
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; (proj / "episode" / "frames").mkdir(parents=True)
            src = proj / "episode" / "episode.json"
            src.write_text(json.dumps({"shots": None}, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError):
                candidates(src)

    def test_candidates_observe_episode_republished_after_cached_read(self):
        from agent.core import save
        from keyframe_batch import candidates
        with tempfile.TemporaryDirectory() as td:
            src = self.make(td)
            self.assertEqual([s['id'] for s in candidates(src)], ['SH001', 'SH002'])
            save(src, {'episode_id': 'EP001', 'title': 'T', 'shots': [
                {'id': 'SH003', 'title': '新镜头', 'duration': 5,
                 'frame': 'frames/SH003.png', 'video_prompt': 'x'}]})
            self.assertEqual([s['id'] for s in candidates(src)], ['SH003'])


def make_pending(td, source="episode/episode.json"):
    from agent.core import save
    proj = Path(td) / "p"; src = proj / source
    src.parent.mkdir(parents=True, exist_ok=True); src.write_text("{}", encoding="utf-8")
    manifest = proj / "workflows/首帧批次/abc/批次.json"
    other = proj / "workflows/首帧批次/def/批次.json"
    save(manifest, {"source": str(src), "items": [
        {"shot_id": "SH001", "state": "pending"}, {"shot_id": "SH002", "state": "imported"}]})
    save(other, {"source": str(proj / "other.json"), "items": [{"shot_id": "SH003", "state": "pending"}]})
    return proj, src, manifest


class PendingTaskTests(unittest.TestCase):
    def test_pending_tasks_only_match_own_source(self):
        from keyframe_import import pending_tasks
        with tempfile.TemporaryDirectory() as td:
            proj, src, manifest = make_pending(td)
            pending = pending_tasks(proj, src)
            self.assertEqual(list(pending), ["SH001"])
            self.assertEqual(pending["SH001"], manifest)

    def test_abandon_releases_shot_for_resubmit(self):
        from keyframe_import import abandon_tasks, pending_tasks
        with tempfile.TemporaryDirectory() as td:
            proj, src, manifest = make_pending(td)
            changed = abandon_tasks({"SH001": manifest})
            self.assertEqual(changed, {manifest})
            self.assertEqual(pending_tasks(proj, src), {})
            data = read(manifest)
            states = {item["shot_id"]: item["state"] for item in data["items"]}
            self.assertEqual(states, {"SH001": "cancelled", "SH002": "imported"})
            self.assertTrue(data["items"][0]["cancelled_at"])

    def test_abandon_keeps_other_shots_pending(self):
        from keyframe_import import abandon_tasks, pending_tasks
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            proj, src, manifest = make_pending(td)
            save(manifest, {"source": str(src), "items": [
                {"shot_id": "SH001", "state": "pending"}, {"shot_id": "SH002", "state": "pending"}]})
            abandon_tasks({"SH001": manifest})
            pending = pending_tasks(proj, src)
            self.assertEqual(list(pending), ["SH002"])


class StaleTaskTests(unittest.TestCase):
    """没有执行记录的旧首帧任务自动放弃，不再阻塞重新提交。"""

    def stale_fixture(self, td, age=600, state=None, output=False):
        from agent.core import save
        proj, src, manifest = make_pending(td)
        save(manifest, {"source": str(src), "items": [{"shot_id": "SH001", "state": "pending", "output": "SH001.png"}]})
        if output:
            (manifest.parent / "SH001.png").write_bytes(b"x")
        if state:
            save(manifest.parent / "执行状态.json", {"state": state, "message": "x", "updated": 0})
        stamp = time.time() - age
        os.utime(manifest, (stamp, stamp))
        return proj, src, manifest

    def test_old_batch_without_execution_record_is_stale(self):
        from keyframe_import import stale_tasks
        with tempfile.TemporaryDirectory() as td:
            proj, src, manifest = self.stale_fixture(td)
            self.assertEqual(stale_tasks(proj, src), {"SH001": manifest})

    def test_recent_batch_is_kept(self):
        from keyframe_import import stale_tasks
        with tempfile.TemporaryDirectory() as td:
            proj, src, _ = self.stale_fixture(td, age=30)
            self.assertEqual(stale_tasks(proj, src), {})

    def test_running_execution_is_kept(self):
        from keyframe_import import stale_tasks
        with tempfile.TemporaryDirectory() as td:
            proj, src, _ = self.stale_fixture(td, state="running")
            self.assertEqual(stale_tasks(proj, src), {})

    def test_failed_execution_is_stale(self):
        from keyframe_import import stale_tasks
        with tempfile.TemporaryDirectory() as td:
            proj, src, manifest = self.stale_fixture(td, age=10, state="failed")
            self.assertEqual(stale_tasks(proj, src), {"SH001": manifest})

    def test_batch_with_output_waits_for_import(self):
        from keyframe_import import stale_tasks
        with tempfile.TemporaryDirectory() as td:
            proj, src, _ = self.stale_fixture(td, output=True)
            self.assertEqual(stale_tasks(proj, src), {})

    def test_live_agent_process_keeps_batch(self):
        from keyframe_import import stale_tasks
        with tempfile.TemporaryDirectory() as td:
            proj, src, _ = self.stale_fixture(td)
            self.assertEqual(stale_tasks(proj, src, agent_running=True), {})

    def test_clear_stale_tasks_abandons_without_asking(self):
        from keyframe_import import clear_stale_tasks, pending_tasks
        with tempfile.TemporaryDirectory() as td:
            proj, src, _ = self.stale_fixture(td)
            class Status:
                def __init__(self): self.texts = []
                def set(self, text): self.texts.append(text)
            class App:
                def __init__(self): self.status = Status()
            app = App()
            waiting = pending_tasks(proj, src)
            self.assertEqual(clear_stale_tasks(app, proj, src, ["SH001"], waiting), [])
            self.assertEqual(pending_tasks(proj, src), {})
            self.assertTrue(any("自动放弃" in line for line in app.status.texts))

    def test_clear_stale_tasks_keeps_recent_batch_for_confirmation(self):
        from keyframe_import import clear_stale_tasks, pending_tasks
        with tempfile.TemporaryDirectory() as td:
            proj, src, _ = self.stale_fixture(td, age=5)
            class App:
                def __init__(self): self.status = type("S", (), {"set": lambda self, text: None})()
            self.assertEqual(clear_stale_tasks(App(), proj, src, ["SH001"], pending_tasks(proj, src)), ["SH001"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
