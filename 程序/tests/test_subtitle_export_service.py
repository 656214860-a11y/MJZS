import tempfile
import unittest
import inspect
import ast
from pathlib import Path
from unittest.mock import Mock, patch

import skill_tools
from stage_execution_service import export_stage_dialogue_script, export_stage_srt
from subtitle_export_controller import publish_stage_srt_text
from subtitle_export_service import export_dialogue_script, export_srt, publish_srt_text
from service_contract import SystemError, UserError, success


EPISODE = {'shots': [{'id': 'SH001', 'title': '初见', 'duration': 3,
                       'dialogue': [{'speaker': 'A', 'text': '你好', 'start': 0, 'end': 2}]}]}


class SubtitleExportServiceTests(unittest.TestCase):
    def test_publish_srt_text_uses_validated_atomic_writer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / 'nested' / 'skill.srt'
            result = publish_srt_text(target, '1\n00:00:00,000 --> 00:00:01,000\n台词\n',
                                      publish=lambda path, value: path.parent.mkdir(parents=True, exist_ok=True)
                                      or path.write_text(value, encoding='utf-8'))

            self.assertTrue(result.ok)
            self.assertEqual(result.data, target)
            self.assertTrue(target.exists())
            self.assertEqual(target.read_text(encoding='utf-8'), '1\n00:00:00,000 --> 00:00:01,000\n台词\n')

    def test_skill_tool_delegates_srt_publication_to_service(self):
        source = inspect.getsource(skill_tools._subtitle_generate)

        self.assertIn('from subtitle_export_controller import publish_stage_srt_text', source)
        self.assertNotIn('line_endings.write_text', source)

    def test_l3_wrapper_publishes_validated_srt_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / 'skill.srt'
            result = publish_stage_srt_text(target, '正文\n')
            self.assertTrue(result.ok)
            self.assertEqual(target, result.data)

    def test_desktop_delegates_exports_to_service(self):
        source = (Path(__file__).resolve().parents[1] / 'desktop.py').read_text(encoding='utf-8')
        self.assertIn('from stage_execution_service import export_stage_srt', source)
        self.assertIn('from stage_execution_service import export_stage_dialogue_script', source)
        self.assertNotIn("p=subtitles(self.root)/('对白_", source)
        self.assertNotIn("p=subtitles(self.root)/('对白脚本_", source)

    def test_exports_srt_atomically_under_the_stage_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            result = export_stage_srt(folder, EPISODE)
            self.assertTrue(result.ok)
            target, report = result.data
            self.assertFalse(report['estimated'])
            self.assertTrue(target.is_file())
            self.assertIn('00:00:00,000 --> 00:00:02,000', target.read_text(encoding='utf-8-sig'))

    def test_exports_dialogue_script_with_asset_name(self):
        with tempfile.TemporaryDirectory() as folder:
            result = export_stage_dialogue_script(folder, EPISODE, {'A': {'name': '阿明'}})
            self.assertTrue(result.ok)
            target, report = result.data
            self.assertFalse(report['estimated'])
            self.assertTrue(target.is_file())
            self.assertIn('SH001  初见', target.read_text(encoding='utf-8-sig'))
            self.assertIn('阿明（0.0-2.0秒）：你好', target.read_text(encoding='utf-8-sig'))

    def test_rejects_empty_dialogue(self):
        with tempfile.TemporaryDirectory() as folder:
            result = export_stage_srt(Path(folder), {'shots': []})
            self.assertIsInstance(result, UserError)
            self.assertIn('没有对白', result.reason)

    def test_l2_export_only_uses_the_injected_publisher(self):
        published = []

        def publish(target, text, validate, update_index, encoding='utf-8'):
            published.append((target, text, validate(text), encoding))
            return target

        result = export_srt('project', EPISODE, publish=publish)
        self.assertTrue(result.ok)
        target, report = result.data
        self.assertFalse(report['estimated'])
        self.assertEqual(target, published[0][0])
        self.assertTrue(published[0][2])
        self.assertEqual(published[0][3], 'utf-8-sig')

    def operations(self, publisher):
        return [lambda: publish_srt_text('target.srt', '台词', publish=publisher),
                lambda: export_srt('project', EPISODE, publish=publisher),
                lambda: export_dialogue_script('project', EPISODE, {}, publish=publisher)]

    def test_all_publish_failures_are_system_results(self):
        for operation in self.operations(Mock(side_effect=OSError('private detail'))):
            with self.assertLogs('subtitle_export_service', level='ERROR'):
                result = operation()
            self.assertIsInstance(result, SystemError)
            self.assertFalse(result.ok)
            self.assertIsNone(result.data)
            self.assertNotIn('private detail', result.reason)

    def test_invalid_publisher_and_programming_errors_propagate(self):
        for publisher in [None, Mock(side_effect=TypeError('bug'))]:
            for operation in self.operations(publisher):
                with self.assertRaises(TypeError):
                    operation()
        for operation in self.operations(Mock(side_effect=ValueError('bug'))):
            with self.assertRaises(ValueError):
                operation()

    def test_empty_exports_never_publish(self):
        publisher = Mock()
        self.assertIsInstance(export_srt('project', {}, publish=publisher), UserError)
        self.assertIsInstance(export_dialogue_script('project', {}, {}, publish=publisher), UserError)
        publisher.assert_not_called()

    def test_skill_failure_cannot_report_success_or_path(self):
        with patch('subtitle_export_controller.publish_stage_srt_text', return_value=SystemError('保存失败')):
            with self.assertRaisesRegex(ValueError, '保存失败'):
                skill_tools._subtitle_generate({'subtitle_file': 'target.srt', 'episode': EPISODE})

    def test_skill_success_uses_result_data(self):
        with patch('subtitle_export_controller.publish_stage_srt_text', return_value=success(Path('target.srt'))):
            result = skill_tools._subtitle_generate({'subtitle_file': 'target.srt', 'episode': EPISODE})
        self.assertTrue(result['ok'])
        self.assertEqual(result['subtitle_file'], 'target.srt')

    def test_desktop_export_methods_handle_success_and_failure(self):
        source = Path(__file__).resolve().parents[1] / 'desktop.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        methods = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                   and node.name in {'subtitles', 'dialogue_script'}}
        self.assertEqual(set(methods), {'subtitles', 'dialogue_script'})
        for name, node in methods.items():
            namespace = {}
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
            app = Mock()
            target = Path('export.txt')
            service = 'export_stage_srt' if name == 'subtitles' else 'export_stage_dialogue_script'
            with patch('stage_execution_service.' + service, return_value=SystemError('保存失败')):
                with self.assertRaisesRegex(ValueError, '保存失败'):
                    namespace[name](app)
            app.status.set.assert_not_called()
            with patch('stage_execution_service.' + service, return_value=success((target, True))):
                self.assertEqual(namespace[name](app), target)
            app.status.set.assert_called_once()


if __name__ == '__main__':
    unittest.main()
