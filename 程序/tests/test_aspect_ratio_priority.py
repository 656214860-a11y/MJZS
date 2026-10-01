# -*- coding: utf-8 -*-
"""三处画幅默认均遵循：制作锁 → 已存偏好 → 各自旧默认。"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import asset_contract


class AspectRatioPriorityTests(unittest.TestCase):
    def test_scene_defaults_use_lock_then_preference_then_legacy_default(self):
        self.assertEqual(asset_contract.defaults('scene', {'aspect_ratio': '9:16'}, '1:1')['aspect_ratio'], '9:16')
        self.assertEqual(asset_contract.defaults('scene', {}, '1:1')['aspect_ratio'], '1:1')
        self.assertEqual(asset_contract.defaults('scene')['aspect_ratio'], '16:9')

    def test_cloud_graph_uses_lock_then_preference_then_legacy_default(self):
        import cloud_assets

        class Client:
            url = 'http://example.invalid'
        class Upload:
            def __init__(self, _url): pass
            def upload(self, value): return str(value)
        common = {'backend': 'Seedream 5.0 Pro'}
        with mock.patch('batch_frames_tool.batch_frames.Client', Upload):
            for lock, preference, expected in (({'aspect_ratio': '9:16'}, '16:9', '9:16'),
                                                ({}, '16:9', '16:9'), ({}, '', '1:1')):
                graph = cloud_assets.graph(Client(), 'CHAR_001', {'name': '甲'}, '提示词', [],
                                           dict(common, workflow_lock=lock, aspect_ratio=preference))
                self.assertEqual(graph['30']['inputs']['aspect_ratio'], expected)

    def test_seedream_uses_lock_then_preference_then_legacy_default(self):
        import keyframe_comfy, keyframe_import, native_assets, seedream_api
        captured = []
        old_profile, old_request = seedream_api.load_profile, seedream_api.request_image
        old_shot, old_register = keyframe_comfy.check_shot, keyframe_import.register
        seedream_api.load_profile = lambda _='': {'model': 'm', 'api_key': 'k', 'base_url': 'http://x'}
        seedream_api.request_image = lambda _profile, payload: captured.append(payload) or b'bad-image'
        keyframe_comfy.check_shot = lambda _source, _shot: ('提示词', [])
        keyframe_import.register = lambda *_args: Path(_args[0]).parent / 'registered.png'
        self.addCleanup(setattr, seedream_api, 'load_profile', old_profile)
        self.addCleanup(setattr, seedream_api, 'request_image', old_request)
        self.addCleanup(setattr, keyframe_comfy, 'check_shot', old_shot)
        self.addCleanup(setattr, keyframe_import, 'register', old_register)
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'episode.json'
            source.write_text('{"shots": [{"id": "SH001"}]}', encoding='utf-8')
            for lock, preference, expected in (({'aspect_ratio': '9:16'}, '1:1', '9:16'),
                                                ({}, '1:1', '1:1'), ({}, '', '9:16')):
                captured.clear()
                keyframe_comfy.run_seedream(source, [{'id': 'SH001'}],
                                             {'workflow_lock': lock, 'aspect_ratio': preference}, lambda _text: None)
                self.assertEqual(captured[0]['size'],
                                 native_assets._seedream_payload('m', '提示词', expected, [])['size'])
