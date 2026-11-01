# -*- coding: utf-8 -*-
"""逐句配音的用户可见音频与时间轴登记必须经发布入口。"""
import ast
import os
import unittest
from tests.architecture._scan import stage_execution_source

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _function(tree, name):
    return next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == name)


def _names(node):
    return {call.func.id for call in ast.walk(node) if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)}


class TtsPublicationBoundaryTests(unittest.TestCase):
    def test_run_lines_delegates_successful_audio_and_manifest_publication(self):
        path = os.path.join(ROOT, 'tts_api.py')
        with open(path, encoding='utf-8') as handle: tree = ast.parse(handle.read(), path)
        self.assertIn('publish_line', _names(_function(tree, 'run_lines')))
        published = _function(tree, 'publish_line')
        self.assertIn('_require_gateway', _names(published))
        self.assertIn('_save', _names(published))

    def test_l2_has_no_direct_core_publisher_and_l3_owns_gateway(self):
        source = open(os.path.join(ROOT, 'tts_api.py'), encoding='utf-8').read()
        self.assertNotIn('from agent.core import read_json, save', source)
        service = stage_execution_source()
        self.assertIn('def tts_gateway()', service)

    def test_full_track_publication_and_desktop_delegation_share_tts_service(self):
        service_path = os.path.join(ROOT, 'tts_api.py')
        with open(service_path, encoding='utf-8') as handle: service_tree = ast.parse(handle.read(), service_path)
        published = _function(service_tree, 'publish_full_track')
        self.assertIn('_require_gateway', _names(published))
        from tests.architecture._scan import parse_desktop  # R1505：generate_tts 已迁到 MediaPagesMixin
        desktop_tree = parse_desktop()
        desktop = ast.Module(body=[member for cls in desktop_tree.body if isinstance(cls, ast.ClassDef) for member in cls.body], type_ignores=[])
        method = next(item for item in desktop.body if isinstance(item, ast.FunctionDef) and item.name == 'generate_tts')
        calls = {call.func.id for call in ast.walk(method) if isinstance(call, ast.Call)
                 and isinstance(call.func, ast.Name)}
        self.assertIn('reusable_tts_full_track', calls)
        self.assertIn('publish_tts_full_track', calls)
        direct = [call.lineno for call in ast.walk(method) if isinstance(call, ast.Call)
                  and isinstance(call.func, ast.Name) and call.func.id in {'save', 'save_bytes', 'read'}]
        self.assertEqual(direct, [])


if __name__ == '__main__': unittest.main()
