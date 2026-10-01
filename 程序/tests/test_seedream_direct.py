# -*- coding: utf-8 -*-
import base64, json, struct, tempfile, unittest, zlib
from pathlib import Path
from native_assets import _seedream_payload


def _png_bytes(w=1, h=1):
    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x00\x00\x00" * w for _ in range(h))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class SeedreamPayloadTests(unittest.TestCase):
    def test_text_only(self):
        payload = _seedream_payload("m", "prompt", "1:1", [])
        self.assertEqual(payload["model"], "m")
        self.assertEqual(payload["size"], "2048x2048")
        self.assertNotIn("image", payload)

    def test_single_reference(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "r.png"
            path.write_bytes(_png_bytes())
            payload = _seedream_payload("m", "prompt", "9:16", [path])
            self.assertTrue(payload["image"].startswith("data:image/png;base64,"))

    def test_bad_aspect(self):
        with self.assertRaises(ValueError):
            _seedream_payload("m", "p", "4:3", [])


class SeedreamUnsettledTests(unittest.TestCase):
    """Seedream 请求结果不确定时：不静默重复扣费，也不整批卡死。"""

    def make_project(self, td):
        folder = Path(td) / "storyboard" / "分镜拆分"
        folder.mkdir(parents=True)
        source = folder / "episode.json"
        source.write_text(json.dumps({"episode_id": "E1", "shots": [
            {"id": "SH001", "duration": 5, "frame": "frames/SH001.png", "frame_prompt": "画面"}]},
            ensure_ascii=False), encoding="utf-8")
        return source

    def patch_seedream(self, image=None):
        import seedream_api
        calls = []
        original = (seedream_api.load_profile, seedream_api.request_image)
        seedream_api.load_profile = lambda pid="": {"model": "m", "api_key": "k", "base_url": "http://x"}
        seedream_api.request_image = lambda *a, **k: (calls.append(1), image)[1]
        self.addCleanup(lambda: (setattr(seedream_api, "load_profile", original[0]),
                                 setattr(seedream_api, "request_image", original[1])))
        return calls

    def test_unsettled_lists_only_unresolved_records(self):
        import seedream_api as api
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            for name, state in (("A", "sending"), ("B", "uncertain"), ("C", "completed"), ("D", "failed")):
                (folder / ("seedream_" + name + ".json")).write_text(json.dumps({"state": state}), encoding="utf-8")
            self.assertEqual(api.unsettled(folder, ["A", "B", "C", "D", "E"]), ["A", "B"])

    def test_release_marks_confirmed_and_keeps_other_records(self):
        import seedream_api as api
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            (folder / "seedream_A.json").write_text(json.dumps({"state": "sending", "aid": "A"}), encoding="utf-8")
            (folder / "seedream_B.json").write_text(json.dumps({"state": "completed"}), encoding="utf-8")
            self.assertEqual(api.release(folder, ["A", "B", "C"]), ["A"])
            first = json.loads((folder / "seedream_A.json").read_text(encoding="utf-8"))
            self.assertEqual(first["state"], "failed")
            self.assertEqual(first["aid"], "A")
            self.assertEqual(json.loads((folder / "seedream_B.json").read_text(encoding="utf-8"))["state"], "completed")

    def test_run_seedream_skips_unsettled_without_resubmitting(self):
        import keyframe_comfy
        calls = self.patch_seedream()
        with tempfile.TemporaryDirectory() as td:
            source = self.make_project(td)
            folder = source.parent / "首帧任务"; folder.mkdir()
            (folder / "seedream_SH001.json").write_text(json.dumps({"state": "sending"}), encoding="utf-8")
            logs = []
            message = keyframe_comfy.run_seedream(source, [{"id": "SH001"}], {"aspect_ratio": "9:16"}, logs.append)
            self.assertEqual(calls, [])
            self.assertIn("未重复提交", message)
            self.assertIn("SH001", message)
            self.assertTrue(any("未重复提交" in line for line in logs))
            self.assertEqual(json.loads((folder / "seedream_SH001.json").read_text(encoding="utf-8"))["state"], "sending")

    def test_confirmed_shot_is_submitted_again(self):
        import keyframe_comfy, keyframe_import, seedream_api
        calls = self.patch_seedream(_png_bytes())
        with tempfile.TemporaryDirectory() as td:
            source = self.make_project(td)
            folder = source.parent / "首帧任务"; folder.mkdir()
            record = folder / "seedream_SH001.json"
            record.write_text(json.dumps({"state": "sending"}), encoding="utf-8")
            self.assertEqual(seedream_api.release(folder, ["SH001"]), ["SH001"])
            original = (keyframe_comfy.check_shot, keyframe_import.register)
            keyframe_comfy.check_shot = lambda src, shot: ("提示词", [])
            def fake_register(source_path, item, image):
                dest = Path(source_path).parent / "registered.png"; dest.write_bytes(Path(image).read_bytes()); return dest
            keyframe_import.register = fake_register
            self.addCleanup(lambda: (setattr(keyframe_comfy, "check_shot", original[0]),
                                     setattr(keyframe_import, "register", original[1])))
            message = keyframe_comfy.run_seedream(source, [{"id": "SH001"}], {"aspect_ratio": "9:16"}, lambda text: None)
            self.assertEqual(len(calls), 1)
            self.assertIn("1/1", message)
            self.assertNotIn("未重复提交", message)

    def test_asset_batch_skips_unsettled_without_resubmitting(self):
        import native_assets
        from asset_context import generated_dir
        calls = self.patch_seedream()
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "episode"
            folder = generated_dir(base)
            (folder / "seedream_CHAR_001.json").write_text(json.dumps({"state": "uncertain"}), encoding="utf-8")
            reports = []
            message = native_assets._run_seedream_direct(
                Path(td), base, [("CHAR_001", {"name": "角色", "image_prompt": "一只猫"})],
                {"model": "Seedream 5.0 Pro", "aspect_ratio": "1:1"}, reports.append)
            self.assertEqual(calls, [])
            self.assertIn("未完成", message)
            self.assertIn("未重复提交", message)
            self.assertTrue(any("未重复提交" in line for line in reports))


    def test_confirm_dialog_releases_only_when_user_agrees(self):
        import seedream_settings
        from tkinter import messagebox
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            (folder / "seedream_A.json").write_text(json.dumps({"state": "sending"}), encoding="utf-8")
            original = messagebox.askyesno
            self.addCleanup(setattr, messagebox, "askyesno", original)
            messagebox.askyesno = lambda *a, **k: False
            self.assertEqual(seedream_settings.confirm_unsettled(None, folder, ["A"], "镜头"), [])
            self.assertEqual(json.loads((folder / "seedream_A.json").read_text(encoding="utf-8"))["state"], "sending")
            messagebox.askyesno = lambda *a, **k: True
            self.assertEqual(seedream_settings.confirm_unsettled(None, folder, ["A"], "镜头"), ["A"])
            self.assertEqual(json.loads((folder / "seedream_A.json").read_text(encoding="utf-8"))["state"], "failed")
            (folder / "seedream_B.json").write_text(json.dumps({"state": "completed"}), encoding="utf-8")
            messagebox.askyesno = lambda *a, **k: (_ for _ in ()).throw(AssertionError("没有未确定记录时不应弹窗"))
            self.assertEqual(seedream_settings.confirm_unsettled(None, folder, ["B"], "镜头"), [])

if __name__ == "__main__":
    unittest.main(verbosity=2)


class SeedreamKeyStoreTests(unittest.TestCase):
    """第 65 期任务 1：火山 profile 的密钥也收进统一那份 .env。"""

    def test_the_default_endpoint_shares_the_ark_key(self):
        import seedream_api
        self.assertEqual(seedream_api.key_name_for(seedream_api.DEFAULT_URL), 'ARK_API_KEY')
        self.assertEqual(seedream_api.key_name_for(seedream_api.DEFAULT_URL + '/'), 'ARK_API_KEY')

    def test_a_self_hosted_endpoint_gets_its_own_name(self):
        import seedream_api
        name = seedream_api.key_name_for('https://images.my-host.cn/v1')
        self.assertEqual(name, 'SEEDREAM_IMAGES_MY_HOST_CN_KEY')
        self.assertNotEqual(name, seedream_api.key_name_for('https://other.host.cn/v1'))

    def test_saving_a_profile_stores_the_key_in_the_unified_env(self):
        import seedream_api
        from unittest.mock import patch
        seen = []
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'seedream_profiles.json'
            with patch.object(seedream_api, 'settings_path', return_value=path),                  patch('model_pool.save_named_key', lambda name, value: seen.append((name, value))):
                profile_id = seedream_api.save_profile('https://ark.cn-beijing.volces.com/api/v3',
                                                       'doubao-seedream', 'sk-ark')
            stored = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(seen, [('ARK_API_KEY', 'sk-ark')])
        record = stored['profiles'][profile_id]
        self.assertNotIn('encrypted_key', record)
        self.assertEqual(record['key_env'], 'ARK_API_KEY')

    def test_loading_a_profile_reads_the_unified_env(self):
        import seedream_api
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'seedream_profiles.json'
            path.write_text(json.dumps({'active': 'p1', 'profiles': {
                'p1': {'base_url': 'https://ark.cn-beijing.volces.com/api/v3',
                       'model': 'doubao-seedream', 'key_env': 'ARK_API_KEY'}}}), encoding='utf-8')
            with patch.object(seedream_api, 'settings_path', return_value=path),                  patch('model_pool.named_key',
                        lambda name, program=None: 'sk-from-env' if name == 'ARK_API_KEY' else ''):
                profile = seedream_api.load_profile('p1')
        self.assertEqual(profile['api_key'], 'sk-from-env')
        self.assertEqual(profile['model'], 'doubao-seedream')
