"""无人值守交接包的纯决策与成果登记回归。"""
import json
import tempfile
import unittest
from pathlib import Path


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
            output = publish_bundle(root, [shot], [(shot, {'file': 'clip.mp4', 'review': 'pass'})],
                                    subtitle='1\n00:00:00,000 --> 00:00:01,000\n你好\n'.encode('utf-8'), auto=True,
                                    publish=publish_handoff_bundle)
            self.assertEqual((output / '001_SH001.mp4').read_bytes(), b'clip')
            self.assertTrue((output / '对白.srt').is_file())
            self.assertEqual(json.loads((output / '镜头顺序.json').read_text(encoding='utf-8'))[0]['shot'], 'SH001')
            self.assertEqual(json.loads((output / '交接包标记.json').read_text(encoding='utf-8'))['kind'], 'auto')


if __name__ == '__main__':
    unittest.main()
