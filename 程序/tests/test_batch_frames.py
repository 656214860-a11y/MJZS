# -*- coding: utf-8 -*-
"""ComfyUI 批量首帧工具纯逻辑自检。运行：python test_batch_frames.py"""
import os, sys, tempfile, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

from batch_frames_tool.batch_frames import inside, Client, graph, attach_prompt
from comfy_service import Comfy


class InsideTests(unittest.TestCase):
    def test_within(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            self.assertTrue(inside(base, "frames/x.png").is_relative_to(base.resolve()))

    def test_parent_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                inside(Path(td), "../x.png")


class ClientUrlTests(unittest.TestCase):
    def test_local_ok(self):
        self.assertEqual(Client("http://127.0.0.1:8189").url, "http://127.0.0.1:8189")

    def test_https_rejected(self):
        with self.assertRaises(ValueError):
            Client("https://127.0.0.1:8189")

    def test_remote_rejected(self):
        with self.assertRaises(ValueError):
            Client("http://example.com:8189")


class GraphTests(unittest.TestCase):
    def test_graph_builds_nodes(self):
        cfg = {"model": "m", "text_encoder": "t", "vae": "v", "width": 768, "height": 768}
        g = graph("p", [], cfg, 42)
        self.assertEqual(g["14"]["class_type"], "SaveImage")
        self.assertEqual(g["1"]["class_type"], "UNETLoader")


class PromptRecoveryTests(unittest.TestCase):
    """提交响应中断后按 client_id 或工作流找回任务编号，不再整批卡死。"""

    def client(self, queue=None, history=None):
        client = Client("http://127.0.0.1:8189")
        def request(path, data=None, raw=False, content_type="application/json"):
            if path == "/queue":
                return {"queue_running": list(queue or []), "queue_pending": []}
            if path == "/history":
                return dict(history or {})
            raise AssertionError(path)
        client.request = request
        return client

    def test_locate_prompt_matches_client_id(self):
        graph = {"14": {"class_type": "SaveImage", "inputs": {}}}
        entry = [3, "PID-1", graph, {"client_id": "abc"}, []]
        self.assertEqual(self.client(queue=[entry]).locate_prompt("abc", attempts=1, wait=0), "PID-1")

    def test_locate_prompt_matches_workflow_after_lost_client_id(self):
        graph = {"14": {"class_type": "SaveImage", "inputs": {}}}
        entry = [3, "PID-2", graph, {"client_id": "旧客户端"}, []]
        self.assertEqual(self.client(queue=[entry]).locate_prompt("", graph, attempts=1, wait=0), "PID-2")

    def test_locate_prompt_ignores_unrelated_jobs(self):
        graph = {"14": {"class_type": "SaveImage", "inputs": {}}}
        entry = [3, "PID-3", {"14": {"class_type": "Other", "inputs": {}}}, {"client_id": "别人"}, []]
        client = self.client(queue=[entry])
        self.assertIsNone(client.locate_prompt("abc", graph, attempts=1, wait=0))

    def test_attach_prompt_writes_recovered_id(self):
        graph = {"14": {"class_type": "SaveImage", "inputs": {}}}
        entry = [3, "PID-4", graph, {"client_id": "abc"}, []]
        job = {"state": "submitting", "workflow": graph}
        self.assertTrue(attach_prompt(self.client(queue=[entry]), job, "abc"))
        self.assertEqual(job["prompt_id"], "PID-4")
        self.assertEqual(job["state"], "queued")

    def test_attach_prompt_reports_failure(self):
        job = {"state": "submitting", "workflow": {"14": {"class_type": "SaveImage", "inputs": {}}}}
        self.assertFalse(attach_prompt(self.client(), job, "abc"))
        self.assertNotIn("prompt_id", job)


class ComfyServiceUrlTests(unittest.TestCase):
    def test_reference_upload_failure_is_propagated_without_retry(self):
        from unittest.mock import patch
        from infra.comfy_service import Comfy
        from contract.infra_errors import NetworkError
        from urllib.error import URLError
        from urllib.request import OpenerDirector

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'reference.png'
            path.write_bytes(b'fixture')
            with patch.object(OpenerDirector, 'open', side_effect=URLError('offline')) as send:
                with self.assertRaisesRegex(NetworkError, '无法连接ComfyUI'):
                    Comfy('http://localhost:8189').reference_graph('prompt', [path], {})
                send.assert_called_once()

    def test_local_ok(self):
        self.assertEqual(Comfy("http://127.0.0.1:8189").url, "http://127.0.0.1:8189")

    def test_https_rejected(self):
        with self.assertRaises(ValueError):
            Comfy("https://127.0.0.1:8189")

    def test_remote_rejected(self):
        with self.assertRaises(ValueError):
            Comfy("http://example.com:8189")


class BatchFailureRecoveryTests(unittest.TestCase):
    """某镜生成失败时不再中断整批；确定的失败标记 failed，下次运行会重新提交。"""

    def png(self, width=768, height=768):
        from tests.image_fixtures import png
        return png((width, height))

    def setup_project(self, td):
        import json
        from pathlib import Path
        source = Path(td) / "storyboard" / "episode.json"
        source.parent.mkdir(parents=True, exist_ok=True)
        shots = [{"id": "SH001", "frame": "frames/SH001.png", "video_prompt": "一", "duration": 5},
                 {"id": "SH002", "frame": "frames/SH002.png", "video_prompt": "二", "duration": 5}]
        source.write_text(json.dumps({"episode_id": "EP001", "shots": shots}, ensure_ascii=False), encoding="utf-8")
        return source

    def run_once(self, source, prompts, history):
        import json
        import threading
        from batch_frames_tool import batch_frames as bf
        cfg = {"url": "http://127.0.0.1:8189", "model": "m", "text_encoder": "t", "vae": "v",
               "width": 768, "height": 768, "shot_ids": ["SH001", "SH002"]}
        shots = json.loads(source.read_text(encoding="utf-8-sig"))["shots"]
        png = self.png()

        class Fake:
            def request(self, path, data=None, raw=False, **kw):
                if path == "/prompt":
                    pid = "PID-%d" % (len(prompts) + 1)
                    prompts.append(pid)
                    return {"prompt_id": pid}
                if path.startswith("/history/"):
                    pid = path.split("/")[-1]
                    return {pid: history[pid]} if pid in history else {}
                if path.startswith("/view?"):
                    return png
                raise AssertionError(path)

            def upload(self, path):
                raise AssertionError("本测试不使用参考图")

        original = (bf.preflight, bf.shot_inputs)
        # 真实 preflight 会跳过已有首帧的镜头；这里照做，否则第二次运行时
        # 已成功的镜头会因 shot 增加了首帧证据字段而被当成新任务重复提交。
        def fake_preflight(src, config):
            rows = json.loads(Path(src).read_text(encoding="utf-8-sig"))["shots"]
            pending = [row for row in rows
                       if not row.get("frame_deleted")
                       and not (Path(src).parent / row["frame"]).is_file()]
            skipped = ["%s：已有首帧，跳过" % row["id"] for row in rows if row not in pending]
            return (src, Fake(), {}, pending, skipped)

        bf.preflight = fake_preflight
        bf.shot_inputs = lambda shot, base, assets: ("提示词 " + shot["id"], [])
        try:
            lines = []
            bf._run(source, cfg, lines.append, threading.Event())
        finally:
            bf.preflight, bf.shot_inputs = original
        return lines

    def test_failure_does_not_stop_batch_and_can_retry(self):
        import json
        import threading
        with tempfile.TemporaryDirectory() as td:
            source = self.setup_project(td)
            history = {
                "PID-1": {"status": {"status_str": "error"}, "outputs": {}},
                "PID-2": {"status": {"status_str": "success"},
                          "outputs": {"14": {"images": [{"filename": "SH002_00001_.png", "type": "output"}]}}},
                "PID-3": {"status": {"status_str": "error"}, "outputs": {}},
            }
            prompts = []
            lines = self.run_once(source, prompts, history)
            log = "\n".join(lines)
            # 第一镜确定的失败：记录标 failed，但整批继续做到第二镜。
            self.assertEqual(prompts, ["PID-1", "PID-2"])
            self.assertIn("SH001：失败", log)
            self.assertIn("SH002：已保存并关联", log)
            self.assertIn("失败 1 镜", log)
            failed = [p for p in (source.parent / "首帧任务").glob("SH001_*.json")]
            self.assertEqual(len(failed), 1)
            self.assertEqual(json.loads(failed[0].read_text(encoding="utf-8"))["state"], "failed")
            self.assertTrue((source.parent / "frames" / "SH002.png").is_file())
            # 再次运行：失败镜重新提交，成功镜不重复提交。
            lines2 = self.run_once(source, prompts, history)
            self.assertEqual(prompts, ["PID-1", "PID-2", "PID-3"])
            self.assertIn("上次生成失败，本次重新提交", "\n".join(lines2))


if __name__ == "__main__":
    unittest.main(verbosity=2)
