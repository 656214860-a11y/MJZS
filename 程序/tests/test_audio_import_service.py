import tempfile
import unittest
import ast
from pathlib import Path
from unittest.mock import Mock, patch

import audio_import_service
from service_contract import UserError, SystemError, success


class AudioImportServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'input.wav'
        self.source.write_bytes(b'audio bytes')

    def test_imports_audio_to_the_numbered_audio_stage(self):
        def publish(target, data, validate, update_index):
            self.assertTrue(validate(data)); target.write_bytes(data); update_index(target)
        with patch('audio_import_service.uuid.uuid4') as created:
            created.return_value.hex = 'abcdef123456'
            result = audio_import_service.import_audio(self.root, self.source, publish=publish)
        self.assertTrue(result.ok)
        target = result.data
        self.assertEqual(target, self.root / '10配音与字幕' / '音频' / 'input_abcdef.wav')
        self.assertEqual(target.read_bytes(), b'audio bytes')
        self.assertTrue(self.source.is_file())

    def test_rejects_empty_or_unsupported_input_before_writing(self):
        empty = self.root / 'empty.mp3'
        empty.touch()
        publisher = Mock()
        result = audio_import_service.import_audio(self.root, empty, publish=publisher)
        self.assertIsInstance(result, UserError)
        self.assertIn('音频文件为空', result.reason)
        unsupported = self.root / 'input.txt'
        unsupported.write_bytes(b'content')
        result = audio_import_service.import_audio(self.root, unsupported, publish=publisher)
        self.assertIsInstance(result, UserError)
        self.assertIn('WAV、MP3、M4A 或 AAC', result.reason)
        publisher.assert_not_called()
        self.assertFalse((self.root / '10配音与字幕').exists())

    def test_accepts_injected_publisher_for_formal_release(self):
        calls = []

        def publish(target, data, validate, update_index):
            calls.append((target, data, validate(data)))
            target.write_bytes(data)
            update_index(target)

        with patch('audio_import_service.uuid.uuid4') as created:
            created.return_value.hex = 'abcdef123456'
            result = audio_import_service.import_audio(self.root, self.source, publish=publish)
        self.assertTrue(result.ok)
        target = result.data

        self.assertEqual(target.read_bytes(), b'audio bytes')
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1:], (b'audio bytes', True))

    def test_read_or_publish_failure_returns_system_error(self):
        publisher = Mock(side_effect=OSError('private detail'))
        with self.assertLogs('audio_import_service', level='ERROR'):
            result = audio_import_service.import_audio(self.root, self.source, publish=publisher)
        self.assertIsInstance(result, SystemError)
        self.assertNotIn('private detail', result.reason)
        self.assertIsNone(result.data)
        self.assertEqual(self.source.read_bytes(), b'audio bytes')
        publisher = Mock()
        with patch.object(Path, 'read_bytes', side_effect=OSError('private detail')):
            with self.assertLogs('audio_import_service', level='ERROR'):
                result = audio_import_service.import_audio(self.root, self.source, publish=publisher)
        self.assertIsInstance(result, SystemError)
        publisher.assert_not_called()

    def test_programming_errors_propagate(self):
        for publisher in [None, Mock(side_effect=TypeError('bug'))]:
            with self.assertRaises(TypeError):
                audio_import_service.import_audio(self.root, self.source, publish=publisher)
        with self.assertRaises(ValueError):
            audio_import_service.import_audio(self.root, self.source, publish=Mock(side_effect=ValueError('bug')))

    def test_desktop_import_failure_success_and_cancel(self):
        source = Path(__file__).resolve().parents[1] / 'desktop.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        methods = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'import_audio']
        self.assertEqual(len(methods), 1)
        dialog = Mock()
        namespace = {'FileDialog': dialog}
        exec(compile(ast.Module(body=methods, type_ignores=[]), str(source), 'exec'), namespace)
        with patch('stage_workspace_service.ensure_audio_workspace', return_value=(self.root, self.root)):
            for result in [SystemError('导入失败'), success(self.source)]:
                app = Mock()
                dialog.return_value.open_file.return_value = str(self.source)
                with patch('stage_execution_service.import_stage_audio', return_value=result):
                    if result.ok:
                        namespace['import_audio'](app)
                        app.status.set.assert_called_once_with('音频已导入：' + str(self.source))
                    else:
                        with self.assertRaisesRegex(ValueError, '导入失败'):
                            namespace['import_audio'](app)
                        app.status.set.assert_not_called()
            dialog.return_value.open_file.return_value = ''
            with patch('stage_execution_service.import_stage_audio') as service:
                namespace['import_audio'](Mock())
            service.assert_not_called()
