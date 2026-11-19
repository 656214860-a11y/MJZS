# -*- coding: utf-8 -*-
"""三处画幅默认均遵循：制作锁 → 已存偏好 → 各自旧默认。"""
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from urllib.error import URLError

from contract import asset_contract


class CloudReferenceUploadTests(unittest.TestCase):
    def test_infra_comfy_consumers_do_not_import_batch_frames_tool(self):
        from tests.architecture._scan import module_import_rows

        infra = Path(__file__).resolve().parents[1] / 'infra'
        edges = [(name, line, target)
                 for name in ('cloud_assets.py', 'comfy_service.py')
                 for line, target in module_import_rows(infra / name)
                 if target.split('.')[0] == 'batch_frames_tool']
        self.assertEqual(edges, [])

    def test_failed_upload_raises_without_retry(self):
        from infra import cloud_assets, http_client
        from contract.infra_errors import NetworkError

        with tempfile.TemporaryDirectory() as td:
            image = Path(td) / 'reference.png'
            image.write_bytes(b'fake png bytes')
            client = SimpleNamespace(url='http://127.0.0.1:8188')
            opener = mock.Mock()
            opener.open.side_effect = URLError('disconnected')
            with mock.patch.object(http_client, '_local_comfy_opener', return_value=opener):
                with self.assertRaisesRegex(NetworkError, '无法连接ComfyUI'):
                    cloud_assets.graph(client, 'CHAR_001', {'reference_images': ['ref']},
                                       '提示词', [image], {'backend': 'Seedream 5.0 Pro'})
            opener.open.assert_called_once()
            request, = opener.open.call_args.args
            self.assertEqual(request.full_url, client.url + '/upload/image')
            self.assertEqual(request.get_method(), 'POST')
            self.assertEqual(opener.open.call_args.kwargs, {'timeout': 30})
            self.assertIsNone(request.get_header('Authorization'))
            self.assertIn(image.read_bytes(), request.data)

    def test_workflow_uses_decoded_upload_names_in_reference_order(self):
        from infra import cloud_assets, http_client

        with tempfile.TemporaryDirectory() as td:
            images = [Path(td) / name for name in ('first.png', 'second.png')]
            for image in images:
                image.write_bytes(image.name.encode())
            opener = mock.Mock()
            opener.open.side_effect = [
                io.BytesIO(b'{"subfolder":"refs","name":"first.png"}'),
                io.BytesIO(b'{"name":"second.png"}'),
            ]
            client = SimpleNamespace(url='http://127.0.0.1:8188')
            asset = {'reference_images': ['a', 'b'], 'reference_roles': {'b': '服饰参考'}}
            with mock.patch.object(http_client, '_local_comfy_opener', return_value=opener):
                graph = cloud_assets.graph(client, 'CHAR_001', asset, '提示词', images,
                                           {'backend': 'Seedream 5.0 Pro'})
            self.assertEqual(opener.open.call_count, 2)
            self.assertEqual(graph['100']['inputs'], {'image': 'refs/first.png', 'role': '综合参考'})
            self.assertEqual(graph['101']['inputs'], {'image': 'second.png', 'role': '服饰参考',
                                                     'previous': ['100', 0]})
            self.assertEqual(graph['30']['inputs']['references'], ['101', 0])


class AspectRatioPriorityTests(unittest.TestCase):
    def test_scene_defaults_use_lock_then_preference_then_legacy_default(self):
        self.assertEqual(asset_contract.defaults('scene', {'aspect_ratio': '9:16'}, '1:1')['aspect_ratio'], '9:16')
        self.assertEqual(asset_contract.defaults('scene', {}, '1:1')['aspect_ratio'], '1:1')
        self.assertEqual(asset_contract.defaults('scene')['aspect_ratio'], '16:9')

    def test_cloud_graph_uses_lock_then_preference_then_legacy_default(self):
        import cloud_assets

        class Client:
            url = 'http://127.0.0.1:8188'
        common = {'backend': 'Seedream 5.0 Pro'}
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
        from tests.image_fixtures import png
        seedream_api.request_image = lambda _profile, payload: captured.append(payload) or png()
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
