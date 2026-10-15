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

    def test_asset_budget_rejects_and_timeout_retains_reservation(self):
        from unittest.mock import patch
        import native_assets, seedream_api
        from asset_context import generated_dir
        from pet_llm import RequestLedger
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            profile_path = root / 'cost_profile.json'
            config = {'budget_amount': '0', 'price_table': {'currency': 'CNY', 'version': 'test',
                      'model_rates': {'m': {'images': '0.5'}}}}
            profile_path.write_text(json.dumps(config), encoding='utf-8')
            items = [('CHAR_001', {'name': '角色', 'image_prompt': '猫'})]
            profile = {'model': 'm', 'api_key': 'test', 'base_url': 'https://example.invalid'}
            with patch.object(seedream_api, 'load_profile', return_value=profile), patch.object(
                    seedream_api, 'request_image', side_effect=TimeoutError('test timeout')) as send:
                with self.assertRaisesRegex(ValueError, '金额预检未通过'):
                    native_assets._run_seedream_direct(root, root, items, {}, lambda _: None)
                send.assert_not_called()
                record_path = generated_dir(root) / 'seedream_CHAR_001.json'
                self.assertFalse(record_path.exists())
                config['budget_amount'] = '0.5'
                profile_path.write_text(json.dumps(config), encoding='utf-8')
                native_assets._run_seedream_direct(root, root, items, {}, lambda _: None)
                native_assets._run_seedream_direct(root, root, items, {}, lambda _: None)
                self.assertEqual(send.call_count, 1)
            record = json.loads(record_path.read_text(encoding='utf-8'))
            entry = RequestLedger(root).load()._find(record['request_id'])
            self.assertEqual(record['state'], 'uncertain')
            self.assertEqual(entry['money_state'], 'unknown')
            self.assertEqual(entry['budget_cost'], '0.5')

    def test_project_budget_blocks_first_frame_before_transport(self):
        from unittest.mock import patch
        import keyframe_comfy
        from pet_llm import RequestLedger
        calls = self.patch_seedream(_png_bytes())
        with tempfile.TemporaryDirectory() as td:
            source = self.make_project(td)
            (Path(td) / 'cost_profile.json').write_text(json.dumps({
                'budget_amount': '0', 'price_table': {'currency': 'CNY', 'version': 'test',
                'model_rates': {'m': {'images': '0.5'}}}}), encoding='utf-8')
            with patch.object(keyframe_comfy, 'check_shot', return_value=('test', [])), self.assertRaisesRegex(ValueError, '金额预检未通过'):
                keyframe_comfy.run_seedream(source, [{'id': 'SH001'}], {}, lambda _: None, project=td)
            self.assertEqual(calls, [])
            self.assertFalse((source.parent / '首帧任务' / 'seedream_SH001.json').exists())
            self.assertEqual(RequestLedger(td).load().entries, [])

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

    def test_asset_batch_preflight_prices_whole_batch_before_first_send(self):
        import native_assets
        from pet_llm import request_ledger_path
        calls = self.patch_seedream(_png_bytes())
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'cost_profile.json').write_text(json.dumps({'budget_amount': '0.5', 'price_table': {
                'currency': 'CNY', 'version': 'test', 'model_rates': {'m': {'images': '0.5'}}}}), encoding='utf-8')
            items = [(aid, {'name': aid, 'image_prompt': '猫'}) for aid in ('CHAR_001', 'CHAR_002')]
            with self.assertRaisesRegex(ValueError, '超过项目金额预算'):
                native_assets._run_seedream_direct(root, root, items, {}, lambda _: None)
            self.assertEqual(calls, [])
            self.assertFalse(request_ledger_path(root).exists())
            self.assertFalse((root / '生成资产').exists())

    def test_previews_exclude_completed_unknown_and_recoverable_images(self):
        import native_assets, keyframe_comfy
        from asset_context import generated_dir
        from pet_llm import request_ledger_path
        calls = self.patch_seedream(_png_bytes())
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'cost_profile.json').write_text(json.dumps({'budget_amount': '1', 'price_table': {
                'currency': 'CNY', 'version': 'test', 'model_rates': {'m': {'images': '0.5'}}}}), encoding='utf-8')
            folder = generated_dir(root)
            for aid, state in [('CHAR_001', 'completed'), ('CHAR_002', 'uncertain'), ('CHAR_003', 'failed')]:
                (folder / ('seedream_' + aid + '.json')).write_text(json.dumps({'state': state}), encoding='utf-8')
            (folder / 'CHAR_003_seedream.png').write_bytes(_png_bytes())
            items = [(aid, {}) for aid in ('CHAR_001', 'CHAR_002', 'CHAR_003', 'CHAR_004')]
            text = native_assets.seedream_cost_preview(root, root, items, {})
            self.assertIn('至多新增 1 张', text)
            self.assertIn('本批预计：0.5 CNY', text)
            source = self.make_project(td)
            data = json.loads(source.read_text(encoding='utf-8'))
            data['shots'].extend([{'id': 'SH002'}, {'id': 'SH003', 'frame': 'ready.png'}])
            source.write_text(json.dumps(data), encoding='utf-8')
            from storyboard_paths import media_root
            (media_root(source) / 'ready.png').write_bytes(_png_bytes())
            records = source.parent / '首帧任务'; records.mkdir()
            for sid, state in [('SH002', 'uncertain'), ('SH003', 'completed')]:
                (records / ('seedream_' + sid + '.json')).write_text(json.dumps({'state': state}), encoding='utf-8')
            text = keyframe_comfy.seedream_cost_preview(root, source, data['shots'], {})
            self.assertIn('至多新增 1 张', text)
            self.assertIn('本批预计：0.5 CNY', text)
            self.assertFalse(request_ledger_path(root).exists())
            self.assertEqual(calls, [])

    def test_existing_bad_image_or_bad_response_never_triggers_automatic_resend(self):
        import native_assets
        from asset_context import generated_dir
        calls = self.patch_seedream(b'bad image')
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); folder = generated_dir(root)
            (folder / 'seedream_CHAR_001.json').write_text(json.dumps({'state': 'failed'}), encoding='utf-8')
            original = folder / 'CHAR_001_seedream.png'; original.write_bytes(b'broken file')
            items = [('CHAR_001', {'name': '猫', 'image_prompt': '猫'})]
            result = native_assets._run_seedream_direct(root, root, items, {}, lambda _: None)
            self.assertIn('待核实', result)
            self.assertEqual(calls, [])
            self.assertEqual(original.read_bytes(), b'broken file')
            items = [('CHAR_002', {'name': '猫', 'image_prompt': '猫'})]
            native_assets._run_seedream_direct(root, root, items, {}, lambda _: None)
            native_assets._run_seedream_direct(root, root, items, {}, lambda _: None)
            self.assertEqual(len(calls), 1)
            row = json.loads((folder / 'seedream_CHAR_002.json').read_text(encoding='utf-8'))
            self.assertEqual(row['state'], 'uncertain')

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
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            (folder / "seedream_A.json").write_text(json.dumps({"state": "sending"}), encoding="utf-8")
            original = seedream_settings.ask_confirmation
            self.addCleanup(setattr, seedream_settings, "ask_confirmation", original)
            seedream_settings.ask_confirmation = lambda *a, **k: False
            self.assertEqual(seedream_settings.confirm_unsettled(None, folder, ["A"], "镜头"), [])
            self.assertEqual(json.loads((folder / "seedream_A.json").read_text(encoding="utf-8"))["state"], "sending")
            seedream_settings.ask_confirmation = lambda *a, **k: True
            self.assertEqual(seedream_settings.confirm_unsettled(None, folder, ["A"], "镜头"), ["A"])
            self.assertEqual(json.loads((folder / "seedream_A.json").read_text(encoding="utf-8"))["state"], "failed")
            (folder / "seedream_B.json").write_text(json.dumps({"state": "completed"}), encoding="utf-8")
            seedream_settings.ask_confirmation = lambda *a, **k: (_ for _ in ()).throw(AssertionError("没有未确定记录时不应弹窗"))
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
