# -*- coding: utf-8 -*-
"""API 适配器纯逻辑自检（不发真实请求）。运行：python test_api.py"""
import base64, json, os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import infra.api_endpoints as api_endpoints
from contract import api_models
from agent.wan import WanAdapter
from agent.volcengine import VolcengineAdapter
from pet_state import PAGE_OF as PAGE

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


def png_file(td):
    p = Path(td) / "frame.png"; p.write_bytes(PNG); return p


class EndpointTests(unittest.TestCase):
    def test_https_ok(self):
        self.assertEqual(api_endpoints.normalize_url("https://dashscope.aliyuncs.com/api/v1/"), "https://dashscope.aliyuncs.com/api/v1")

    def test_local_http_ok(self):
        self.assertEqual(api_endpoints.normalize_url("http://127.0.0.1:8189"), "http://127.0.0.1:8189")

    def test_remote_http_rejected(self):
        with self.assertRaises(ValueError):
            api_endpoints.normalize_url("http://example.com/api")

    def test_query_rejected(self):
        with self.assertRaises(ValueError):
            api_endpoints.normalize_url("https://x.com/api?key=1")

    def test_credentials_rejected(self):
        with self.assertRaises(ValueError):
            api_endpoints.normalize_url("https://user:pw@x.com/api")


class ConfiguredKeyTests(unittest.TestCase):
    def setUp(self):
        from secret_store_support import isolate_secret_store
        isolate_secret_store(self)

    def test_model_pool_provider_reads_encrypted_record_without_env_file(self):
        with patch('model_secrets.load', return_value='sk-encrypted') as load:
            value=api_endpoints.configured_key({'key_provider':'model_pool', 'key_env':'DASHSCOPE_API_KEY'})
        self.assertEqual(value, 'sk-encrypted')
        load.assert_called_once_with('DASHSCOPE_API_KEY')

    def test_reads_env_file(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, ".env").write_text("DASHSCOPE_API_KEY=sk-test123\n", encoding="utf-8")
            self.assertEqual(api_endpoints.configured_key({"project_dir": td, "key_env": "DASHSCOPE_API_KEY"}), "sk-test123")

    def test_missing_key_raises(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                api_endpoints.configured_key({"project_dir": td, "key_env": "NOPE"})

    def test_placeholder_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, ".env").write_text("K=replace_me\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                api_endpoints.configured_key({"project_dir": td, "key_env": "K"})

    def test_non_dict_config_rejected(self):
        with self.assertRaises(ValueError):
            api_endpoints.configured_key(None)
        with self.assertRaises(ValueError):
            api_endpoints.configured_key("不是对象")


class WanPayloadTests(unittest.TestCase):
    def cfg(self):
        return {"base_url": "https://dashscope.aliyuncs.com/api/v1", "model": "wan2.6-i2v-flash"}

    def test_payload_builds_data_url(self):
        with tempfile.TemporaryDirectory() as td:
            a = WanAdapter(self.cfg())
            shot = {"video_prompt": "画面", "duration": 5, "generate_audio": False}
            p = a.payload(shot, png_file(td))
            self.assertEqual(p["model"], "wan2.6-i2v-flash")
            self.assertTrue(p["input"]["img_url"].startswith("data:image/png;base64,"))
            self.assertFalse(p["parameters"]["audio"])
            self.assertEqual(p["parameters"]["duration"], 5)

    def test_payload_rejects_non_png(self):
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "f.bin"; bad.write_bytes(b"hello")
            a = WanAdapter(self.cfg())
            with self.assertRaises(ValueError):
                a.payload({"video_prompt": "x", "duration": 5}, bad)

    def test_poll_status_mapping(self):
        a = WanAdapter(self.cfg())
        a.call = lambda task_id=None, payload=None: {"output": {"task_status": "SUCCEEDED", "video_url": "http://v"}}
        self.assertEqual(a.poll("t")["status"], "succeeded")


class VolcenginePayloadTests(unittest.TestCase):
    def cfg(self, model="doubao-seedance-1-5-pro"):
        return {"base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": model, "resolution": "720p"}

    def test_payload_first_frame(self):
        with tempfile.TemporaryDirectory() as td:
            a = VolcengineAdapter(self.cfg())
            shot = {"video_prompt": "画面", "duration": 5, "generate_audio": True}
            p = a.payload(shot, png_file(td))
            self.assertEqual(p["model"], "doubao-seedance-1-5-pro")
            self.assertEqual(p["content"][0]["type"], "text")
            self.assertEqual(p["content"][1]["role"], "first_frame")
            self.assertTrue(p["generate_audio"])
            self.assertEqual(p["ratio"], "16:9")

    def test_seedance_1_0_no_audio_flag(self):
        with tempfile.TemporaryDirectory() as td:
            a = VolcengineAdapter(self.cfg("seedance-1-0-pro"))
            p = a.payload({"video_prompt": "x", "duration": 5}, png_file(td))
            self.assertNotIn("generate_audio", p)

    def test_poll_status_mapping(self):
        a = VolcengineAdapter(self.cfg())
        a.call = lambda task_id=None, payload=None: {"status": "succeeded", "content": {"video_url": "http://v"}}
        self.assertEqual(a.poll("t")["status"], "succeeded")
        a.call = lambda task_id=None, payload=None: {"status": "cancelled"}
        self.assertEqual(a.poll("t")["status"], "failed")


class ApiModelsTests(unittest.TestCase):
    def test_remember_remove_roundtrip(self):
        cfg = {}
        cfg = api_models.remember(cfg, {"base_url": "https://a.com", "model": "m1", "api_key": "k"})
        self.assertEqual(len(api_models.records(cfg)), 1)
        cfg = api_models.remove(cfg, "https://a.com", "m1")
        self.assertEqual(api_models.records(cfg), [])

    def test_records_non_dict_empty(self):
        self.assertEqual(api_models.records(None), [])
        self.assertEqual(api_models.records("不是对象"), [])


class SeedreamProfileTests(unittest.TestCase):
    def test_public_profile_non_dict_rejected(self):
        from unittest.mock import patch
        import seedream_api
        with patch.object(seedream_api, "read_settings", return_value={"active": "p", "profiles": {"p": "不是对象"}}):
            with self.assertRaises(ValueError):
                seedream_api.public_profile()

    def test_public_profile_ok(self):
        from unittest.mock import patch
        import seedream_api
        with patch.object(seedream_api, "read_settings", return_value={"active": "p", "profiles": {"p": {"base_url": "https://x.com", "model": "m"}}}):
            self.assertEqual(seedream_api.public_profile()["model"], "m")


class QwenSetupTests(unittest.TestCase):
    def test_validate_ok(self):
        from qwen_setup import validate
        v = validate({"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen3.7-plus", "api_key": "sk-abc"})
        self.assertEqual(v["model"], "qwen3.7-plus")

    def test_validate_bad_model(self):
        from qwen_setup import validate
        with self.assertRaises(ValueError):
            validate({"base_url": "https://x.com/v1", "model": "bad model", "api_key": "sk-abc"})

    def test_validate_missing_key_remote(self):
        from qwen_setup import validate
        with self.assertRaises(ValueError):
            validate({"base_url": "https://x.com/v1", "model": "m", "api_key": ""})

    def test_validate_local_allows_empty_key(self):
        from qwen_setup import validate
        v = validate({"base_url": "http://127.0.0.1:8000/v1", "model": "m", "api_key": ""})
        self.assertEqual(v["api_key"], "local")

    def test_load_corrupt_settings_falls_back(self):
        from qwen_setup import load
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "qwen-api.json"
            p.write_text("{bad json", encoding="utf-8")
            with patch("qwen_setup.settings_path", return_value=p), \
                 patch("qwen_setup.unified_key", return_value=""):
                data = load()
                self.assertEqual(data["model"], "qwen3.7-plus")
                self.assertEqual(data["api_key"], "")

    def test_the_key_comes_from_the_unified_env(self):
        """第 65 期任务 1：qwen-api.json 不再存密钥，钥匙从统一那份 .env 取。"""
        from qwen_setup import load
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "qwen-api.json"
            with patch("qwen_setup.settings_path", return_value=p), \
                 patch("qwen_setup.unified_key", return_value="sk-from-env"):
                self.assertEqual(load()["api_key"], "sk-from-env")

    def test_qwen_child_environment_excludes_unrelated_credentials(self):
        """Qwen 子进程只能拿到本次调用显式注入的 OPENAI_API_KEY。"""
        from unittest.mock import patch
        import qwen_setup
        with patch.dict(qwen_setup.os.environ, {"DEEPSEEK_API_KEY": "secret", "PATH": "C:/bin"}, clear=True):
            env = qwen_setup.child_environment()
        self.assertEqual(env.get("PATH"), "C:/bin")
        self.assertNotIn("DEEPSEEK_API_KEY", env)


class ShotAssetsPrepareTests(unittest.TestCase):
    def make_source(self, td):
        from pathlib import Path
        proj = Path(td) / "p"; (proj / "episode").mkdir(parents=True)
        (proj / "episode" / "assets.json").write_text("{}", encoding="utf-8")
        (proj / "config.json").write_text(json.dumps({"episode_dir": str(proj / "episode"), "episode_file": str(proj / "episode" / "episode.json")}), encoding="utf-8")
        return proj / "episode" / "episode.json"

    def shot(self):
        return {"id": "SH001", "title": "镜头", "duration": 5, "characters": [], "location": "LOC_001",
                "frame": "frames/SH001.png", "video_prompt": "画面", "upload_assets": False, "generate_audio": True}

    def test_first_frame_mode(self):
        from agent.shot_assets import prepare
        with tempfile.TemporaryDirectory() as td:
            src = self.make_source(td)
            out = prepare(src, self.shot(), {"model": "wan2.6-i2v-flash", "cloud_provider": "wan"})
            self.assertEqual(out["_reference_mode"], "first_frame")
            self.assertEqual(out["_asset_references"], [])

    def test_seedance_1_0_rejects_audio(self):
        from agent.shot_assets import prepare
        with tempfile.TemporaryDirectory() as td:
            src = self.make_source(td)
            with self.assertRaises(ValueError):
                prepare(src, self.shot(), {"model": "seedance-1-0-pro", "cloud_provider": "volcengine"})

    def test_wan_27_requires_refs(self):
        from agent.shot_assets import prepare
        with tempfile.TemporaryDirectory() as td:
            src = self.make_source(td)
            with self.assertRaises(ValueError):
                prepare(src, self.shot(), {"model": "wan2.7-r2v", "cloud_provider": "wan"})


class QwenWindowTitleTests(unittest.TestCase):
    def title(self, name, stage, page=None):
        from orchestrator.qwen_adapter import window_title
        return window_title(name, stage, page)

    def test_basic(self):
        self.assertEqual(self.title("项目", "writing"), "01 剧本准备｜项目｜Qwen")

    def test_storyboard_video_prompt_page(self):
        self.assertEqual(self.title("项目", "storyboard", PAGE["video"]), "10 视频生成｜项目｜Qwen")

    def test_assets_keyframe_page(self):
        self.assertEqual(self.title("项目", "assets", PAGE["keyframe"]), "08 首帧管理｜项目｜Qwen")

    def test_control_chars_stripped(self):
        self.assertEqual(self.title("项" + "\n" + "目", "writing"), "01 剧本准备｜项 目｜Qwen")


class QwenSetupKeyTests(unittest.TestCase):
    def test_setup_key_deterministic(self):
        from orchestrator.qwen_adapter import setup_key
        cfg = {"model": "qwen3.7-plus", "program": ""}
        self.assertEqual(setup_key(cfg), setup_key(dict(cfg)))
        self.assertNotEqual(setup_key(cfg), setup_key({**cfg, "model": "other"}))


class EnsureCloudModelTests(unittest.TestCase):
    def test_non_cloud_root_noop(self):
        from contract.api_models import ensure_cloud_model
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"; root.mkdir()
            self.assertIsNone(ensure_cloud_model(root, {"base_url": "u", "model": "m", "cloud_provider": "wan"}))

    def test_deleted_cloud_model_raises(self):
        from contract.api_models import ensure_cloud_model, identity
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td); (proj / "cloud_video" / "s1").mkdir(parents=True)
            root = proj / "cloud_video" / "s1"
            cfg = {"base_url": "u", "model": "m", "cloud_provider": "wan"}
            (proj / "ui_settings.json").write_text(json.dumps({"cloud_deleted_models": [identity("u", "m", "wan")]}, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError):
                ensure_cloud_model(root, cfg)


class CloudRemovedTests(unittest.TestCase):
    def make(self, td, deleted):
        from pathlib import Path
        proj = Path(td) / "p"; proj.mkdir()
        (proj / "ui_settings.json").write_text(json.dumps({"cloud_deleted_models": deleted}), encoding="utf-8")
        return proj

    def test_deleted_model_true(self):
        from contract.api_models import cloud_removed, identity
        with tempfile.TemporaryDirectory() as td:
            key = identity("https://x.com", "m1", "wan")
            proj = self.make(td, [key])
            self.assertTrue(cloud_removed(proj, {"base_url": "https://x.com", "model": "m1", "cloud_provider": "wan"}))

    def test_not_deleted_false(self):
        from contract.api_models import cloud_removed
        with tempfile.TemporaryDirectory() as td:
            proj = self.make(td, [])
            self.assertFalse(cloud_removed(proj, {"base_url": "https://x.com", "model": "m1", "cloud_provider": "wan"}))

    def test_non_dict_config_false(self):
        from contract.api_models import cloud_removed
        with tempfile.TemporaryDirectory() as td:
            proj = self.make(td, [])
            self.assertFalse(cloud_removed(proj, None))

    def test_corrupt_prefs_false(self):
        from contract.api_models import cloud_removed
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; proj.mkdir()
            (proj / "ui_settings.json").write_text("[]", encoding="utf-8")
            self.assertFalse(cloud_removed(proj, {"base_url": "https://x.com", "model": "m1", "cloud_provider": "wan"}))


class IdentityTests(unittest.TestCase):
    def test_identity_distinguishes_provider(self):
        from contract.api_models import identity
        a = identity("https://x.com", "m1", "wan")
        b = identity("https://x.com", "m1", "volcengine")
        self.assertNotEqual(a, b)

    def test_identity_normalizes_trailing_slash(self):
        from contract.api_models import identity
        self.assertEqual(identity("https://x.com/", "m1"), identity("https://x.com", "m1"))


class ProbeEndpointTests(unittest.TestCase):
    def test_http_success(self):
        from unittest.mock import patch
        import infra.api_endpoints as api_endpoints
        class Resp:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): return False
        # 第 34 期第 9 条：urlopen 改成函数内 import，patch 目标跟着换成 urllib.request
        with patch("urllib.request.urlopen", return_value=Resp()):
            self.assertEqual(api_endpoints.probe_endpoint("https://x.com")["reachable"], True)

    def test_http_auth_error_still_reachable(self):
        from unittest.mock import patch
        import infra.api_endpoints as api_endpoints, urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("https://x.com", 401, "Unauthorized", {}, None)):
            result = api_endpoints.probe_endpoint("https://x.com")
            self.assertTrue(result["reachable"])
            self.assertEqual(result["code"], 401)

    def test_connection_error_not_reachable(self):
        from unittest.mock import patch
        import infra.api_endpoints as api_endpoints
        with patch("urllib.request.urlopen", side_effect=OSError("down")):
            self.assertFalse(api_endpoints.probe_endpoint("https://x.com")["reachable"])


class ImageUrlTests(unittest.TestCase):
    def test_png_data_url(self):
        from agent.shot_assets import image_url
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "f.png"; p.write_bytes(PNG)
            self.assertTrue(image_url(p).startswith("data:image/png;base64,"))

    def test_invalid_rejected(self):
        from agent.shot_assets import image_url
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "f.png"; p.write_bytes(b"not image")
            with self.assertRaises(ValueError):
                image_url(p)


class DownloadGuardTests(unittest.TestCase):
    def test_non_https_rejected(self):
        from agent.core import download
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                download("http://example.com/v.mp4", Path(td) / "v.mp4")


class CloudAssetsTests(unittest.TestCase):
    def test_get_key_from_env(self):
        from cloud_assets import get_key
        from unittest.mock import patch
        with patch.dict(os.environ, {"COMFY_API_KEY": " sk-test "}), \
             patch("cloud_assets._unified_key", return_value=""):
            self.assertEqual(get_key(), "sk-test")

    def test_get_key_empty_without_env_or_file(self):
        from cloud_assets import get_key
        from unittest.mock import patch
        with patch.dict(os.environ, {}, clear=False), \
             patch("cloud_assets._unified_key", return_value=""), \
             patch("cloud_assets._secret_file", return_value=Path("__nonexistent__.dpapi")):
            os.environ.pop("COMFY_API_KEY", None)
            self.assertEqual(get_key(), "")

    def test_the_unified_env_is_read_when_the_old_file_is_gone(self):
        """第 65 期任务 1：老的本机加密那份不在时，统一那份 .env 里的钥匙照样认。"""
        from cloud_assets import get_key
        from unittest.mock import patch
        with patch.dict(os.environ, {}, clear=False), \
             patch("cloud_assets._unified_key", return_value="sk-unified"), \
             patch("cloud_assets._secret_file", return_value=Path("__nonexistent__.dpapi")):
            os.environ.pop("COMFY_API_KEY", None)
            self.assertEqual(get_key(), "sk-unified")

    def test_a_newly_saved_key_beats_a_stale_environment_variable(self):
        """R2178 J8：旧的同名环境变量不得盖过用户刚保存的密钥（取钥次序与 model_pool.credential 一致）。"""
        from cloud_assets import get_key
        from unittest.mock import patch
        with patch.dict(os.environ, {"COMFY_API_KEY": "sk-stale"}),              patch("cloud_assets._unified_key", return_value="sk-fresh"):
            self.assertEqual(get_key(), "sk-fresh")

    def test_unified_key_reads_the_model_pool_chain(self):
        from cloud_assets import _unified_key, KEY_ENV
        from unittest.mock import patch
        import model_pool
        with patch("model_pool.credential", return_value="sk-chain") as chain:
            self.assertEqual(model_pool.named_key(KEY_ENV), "sk-chain")
            self.assertEqual(_unified_key(), "sk-chain")
        with patch("model_pool.credential", side_effect=ValueError("none")):
            self.assertEqual(_unified_key(), "")

    def test_save_key_goes_to_the_unified_store(self):
        """第 65 期任务 1：保存走统一那份 .env，不再另写一份本机文件。"""
        from cloud_assets import save_key, KEY_ENV
        from unittest.mock import patch
        seen = []
        with patch("model_pool.save_named_key", lambda name, value: seen.append((name, value))):
            save_key(" sk-cloud ")
        self.assertEqual(seen, [(KEY_ENV, "sk-cloud")])
        with self.assertRaises(ValueError):
            save_key("")

    def test_validate_rejects_unknown_model(self):
        from cloud_assets import validate
        with self.assertRaises(ValueError):
            validate(object(), {"backend": "未知模型"}, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
