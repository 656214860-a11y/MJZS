import tempfile
import unittest
import inspect
from pathlib import Path

import skill_tools
from stage_execution_service import export_stage_dialogue_script, export_stage_srt
from subtitle_export_service import export_dialogue_script, export_srt, publish_srt_text


EPISODE = {'shots': [{'id': 'SH001', 'title': '初见', 'duration': 3,
                       'dialogue': [{'speaker': 'A', 'text': '你好', 'start': 0, 'end': 2}]}]}


class SubtitleExportServiceTests(unittest.TestCase):
    def test_publish_srt_text_uses_validated_atomic_writer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / 'nested' / 'skill.srt'
            result = publish_srt_text(target, '1\n00:00:00,000 --> 00:00:01,000\n台词\n')

            self.assertEqual(result, target)
            self.assertTrue(target.exists())
            self.assertEqual(target.read_text(encoding='utf-8'), '1\n00:00:00,000 --> 00:00:01,000\n台词\n')

    def test_skill_tool_delegates_srt_publication_to_service(self):
        source = inspect.getsource(skill_tools._subtitle_generate)

        self.assertIn('from subtitle_export_service import publish_srt_text', source)
        self.assertNotIn('line_endings.write_text', source)

    def test_desktop_delegates_exports_to_service(self):
        source = (Path(__file__).resolve().parents[1] / 'desktop.py').read_text(encoding='utf-8')
        self.assertIn('from stage_execution_service import export_stage_srt', source)
        self.assertIn('from stage_execution_service import export_stage_dialogue_script', source)
        self.assertNotIn("p=subtitles(self.root)/('对白_", source)
        self.assertNotIn("p=subtitles(self.root)/('对白脚本_", source)

    def test_exports_srt_atomically_under_the_stage_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            target, estimated = export_stage_srt(folder, EPISODE)
            self.assertFalse(estimated)
            self.assertTrue(target.is_file())
            self.assertIn('00:00:00,000 --> 00:00:02,000', target.read_text(encoding='utf-8-sig'))

    def test_exports_dialogue_script_with_asset_name(self):
        with tempfile.TemporaryDirectory() as folder:
            target, estimated = export_stage_dialogue_script(folder, EPISODE, {'A': {'name': '阿明'}})
            self.assertFalse(estimated)
            self.assertTrue(target.is_file())
            self.assertIn('SH001  初见', target.read_text(encoding='utf-8-sig'))
            self.assertIn('阿明（0.0-2.0秒）：你好', target.read_text(encoding='utf-8-sig'))

    def test_rejects_empty_dialogue(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, '没有对白'):
                export_stage_srt(Path(folder), {'shots': []})

    def test_l2_export_only_uses_the_injected_publisher(self):
        published = []

        def publish(target, text, validate, update_index, encoding='utf-8'):
            published.append((target, text, validate(text), encoding))
            return target

        target, estimated = export_srt('project', EPISODE, publish=publish)
        self.assertFalse(estimated)
        self.assertEqual(target, published[0][0])
        self.assertTrue(published[0][2])
        self.assertEqual(published[0][3], 'utf-8-sig')


if __name__ == '__main__':
    unittest.main()
