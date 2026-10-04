"""无人值守交接包的纯决策与成果登记回归。"""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from service_contract import SystemError, UserError, success


class AutomaticDecisionTests(unittest.TestCase):
    def test_decision_distinguishes_repeat_wait_complete_and_dispatch(self):
        from handoff_service import automatic_decision
        self.assertEqual(automatic_decision(('state',), 'digest', ('state',), {})['action'], 'skip')
        self.assertEqual(automatic_decision(('state',), None, None, {})['action'], 'wait')
        self.assertEqual(automatic_decision(('state',), 'digest', None, {'digest': 'digest'})['action'], 'complete')
        self.assertEqual(automatic_decision(('state',), 'digest', None, {'digest': 'old-digest'})['action'], 'dispatch')
        self.assertEqual(automatic_decision(('state',), 'digest', None, {})['action'], 'dispatch')


class AutomaticMarkerPublicationTests(unittest.TestCase):
    def test_marker_is_published_in_editing_stage(self):
        from handoff_service import AUTOMATIC_HANDOFF_MARKER_NAME
        from project_stages import editing
        from stage_execution_service import save_automatic_handoff_marker
        with tempfile.TemporaryDirectory() as folder:
            target = save_automatic_handoff_marker(Path(folder), 'digest', Path(folder) / 'bundle', 3)
            self.assertEqual(target, editing(Path(folder)) / AUTOMATIC_HANDOFF_MARKER_NAME)
            self.assertEqual(json.loads(target.read_text(encoding='utf-8')), {'digest': 'digest', 'folder': str(Path(folder) / 'bundle'), 'shots': 3})


class BundlePublicationTests(unittest.TestCase):
    def test_bundle_requires_l3_publisher(self):
        from handoff_service import publish_bundle
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            clip = root / 'clip.mp4'; clip.write_bytes(b'clip')
            with self.assertRaises(TypeError):
                publish_bundle(root, [{'id': 'SH001', 'duration': 3}],
                               [({'id': 'SH001', 'duration': 3}, {'file': 'clip.mp4'})])

    def test_l3_publishes_complete_bundle_and_keeps_auto_marker(self):
        from handoff_service import publish_bundle
        from stage_execution_service import publish_handoff_bundle
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            clip = root / 'clip.mp4'; clip.write_bytes(b'clip')
            shot = {'id': 'SH001', 'duration': 3}
            result = publish_bundle(root, [shot], [(shot, {'file': 'clip.mp4', 'review': 'pass'})],
                                    subtitle='1\n00:00:00,000 --> 00:00:01,000\n你好\n'.encode('utf-8'), auto=True,
                                    publish=publish_handoff_bundle)
            self.assertTrue(result.ok)
            output = result.data
            self.assertEqual((output / '001_SH001.mp4').read_bytes(), b'clip')
            self.assertTrue((output / '对白.srt').is_file())
            self.assertEqual(json.loads((output / '镜头顺序.json').read_text(encoding='utf-8'))[0]['shot'], 'SH001')
            self.assertEqual(json.loads((output / '交接包标记.json').read_text(encoding='utf-8'))['kind'], 'auto')


class HandoffResultTests(unittest.TestCase):
    def test_validation_rejects_before_publishing(self):
        from handoff_service import publish_bundle
        publisher = Mock()
        for rows in ([], [({'id': 'SH001'}, {'file': '../outside.mp4'})]):
            result = publish_bundle(Path('project'), [], rows, publish=publisher)
            self.assertIsInstance(result, UserError)
        publisher.assert_not_called()

    def test_write_errors_are_classified(self):
        from handoff_service import publish_bundle, save_automatic_handoff_marker
        shot = {'id': 'SH001', 'duration': 1}
        calls = [(save_automatic_handoff_marker, ('marker.json', 'digest', 'folder', 1)),
                 (publish_bundle, ('project', [shot], [(shot, {'file': 'clip.mp4'})]))]
        for function, args in calls:
            with self.subTest(function=function.__name__):
                with self.assertLogs('handoff_service', level='ERROR'):
                    result = function(*args, publish=Mock(side_effect=OSError('private detail')))
                self.assertIsInstance(result, SystemError)
                self.assertIsNone(result.data)
                self.assertNotIn('private detail', result.reason)
                with self.assertRaises(TypeError):
                    function(*args, publish=Mock(side_effect=TypeError('bug')))

    def test_callers_check_result_before_returning_path(self):
        from desktop import Desktop
        from stage_execution_service import save_automatic_handoff_marker
        desk = SimpleNamespace(root=Path('project'), studio=SimpleNamespace(
            state=lambda: {'shots': {'SH001': []}}, episode={'shots': [{'id': 'SH001'}]}))
        target = Path('bundle')
        with patch('handoff_service.publish_bundle', return_value=success(target)):
            self.assertIs(target, Desktop.handoff(desk))
        with patch('handoff_service.publish_bundle', return_value=SystemError('保存失败')):
            with self.assertRaisesRegex(ValueError, '保存失败'):
                Desktop.handoff(desk)
        with patch('handoff_service.save_automatic_handoff_marker', return_value=SystemError('保存失败')):
            with self.assertRaisesRegex(ValueError, '保存失败'):
                save_automatic_handoff_marker('project', 'digest', 'bundle', 1)


if __name__ == '__main__':
    unittest.main()
