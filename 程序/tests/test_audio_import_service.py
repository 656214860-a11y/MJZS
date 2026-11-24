from tests.architecture._scan import parse_desktop  # R1505：Desktop 方法分布在 desktop.py 与迁出的 Mixin 模块
import tempfile
import unittest
import ast
from pathlib import Path
from unittest.mock import Mock, patch

from domain import audio_import_service
from contract.service_contract import UserError, SystemError, success


class AudioImportServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'input.wav'
        self.source.write_bytes(b'audio bytes')

    def test_imports_audio_to_the_numbered_audio_stage(self):
        def publish(target, source):
            self.assertEqual(source, self.source)
            target.write_bytes(source.read_bytes())
        with patch('domain.audio_import_service.uuid.uuid4') as created:
            created.return_value.hex = 'abcdef123456'
            result = audio_import_service.import_audio(self.root, self.source, publish=publish)
        self.assertTrue(result.ok)
        target = result.data
        self.assertEqual(target, self.root / '11配音与字幕' / '音频' / 'input_abcdef.wav')
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
        self.assertFalse((self.root / '11配音与字幕').exists())

    def test_accepts_injected_publisher_for_formal_release(self):
        calls = []

        def publish(target, source):
            calls.append((target, source))
            target.write_bytes(source.read_bytes())

        with patch('domain.audio_import_service.uuid.uuid4') as created:
            created.return_value.hex = 'abcdef123456'
            result = audio_import_service.import_audio(self.root, self.source, publish=publish)
        self.assertTrue(result.ok)
        target = result.data

        self.assertEqual(target.read_bytes(), b'audio bytes')
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1:], (self.source,))

    def test_read_or_publish_failure_returns_system_error(self):
        publisher = Mock(side_effect=OSError('private detail'))
        with self.assertLogs('audio_import_service', level='ERROR'):
            result = audio_import_service.import_audio(self.root, self.source, publish=publisher)
        self.assertIsInstance(result, SystemError)
        self.assertNotIn('private detail', result.reason)
        self.assertIsNone(result.data)
        self.assertEqual(self.source.read_bytes(), b'audio bytes')
        publisher = Mock()
        with patch.object(Path, 'stat', side_effect=OSError('private detail')):
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
        tree = parse_desktop()
        methods = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'import_audio']
        self.assertEqual(len(methods), 1)
        namespace = {}
        exec(compile(ast.Module(body=methods, type_ignores=[]), str(source), 'exec'), namespace)
        with patch('domain.stage_workspace_service.ensure_audio_workspace', return_value=success((self.root, self.root))):
            for result in [SystemError('导入失败'), success(self.source)]:
                app = Mock()
                app.async_.side_effect = lambda work, done: done(work())
                app.media_page_services.file_dialog.return_value.open_file.return_value = str(self.source)
                # FIX-S11-E6：页面经 ui.tts_settings 胶水导入，询问控件默认返回对白。
                with patch('stage_execution_service.import_stage_audio', return_value=result), \
                        patch('ui.tts_settings.ask_audio_kind', return_value='dialogue'):
                    if result.ok:
                        namespace['import_audio'](app)
                        app.status.set.assert_called_once_with('音频已导入：' + str(self.source))
                    else:
                        with self.assertRaisesRegex(ValueError, '导入失败'):
                            namespace['import_audio'](app)
                        app.status.set.assert_not_called()
            app = Mock()
            app.media_page_services.file_dialog.return_value.open_file.return_value = ''
            with patch('ui.tts_settings.import_audio_with_kind') as helper:
                namespace['import_audio'](app)
            helper.assert_not_called()


class StageAudioImportKindTests(unittest.TestCase):
    """FIX-S11-E6：L3 把页面所选用途原样传给 L2——非对白落盘名带前缀，默认仍是对白原名。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'song.mp3'
        self.source.write_bytes(b'audio bytes')

    def _import(self, **kwargs):
        def publish(target, source):
            target.write_bytes(source.read_bytes())
        with patch('stage_execution_service.media_import_publisher', return_value=publish), \
                patch('domain.audio_import_service.uuid.uuid4') as created:
            created.return_value.hex = 'abcdef123456'
            from stage_execution_service import import_stage_audio
            return import_stage_audio(self.root, self.source, **kwargs)

    def test_bgm_kind_reaches_domain_and_marks_the_name(self):
        result = self._import(kind='bgm')
        self.assertTrue(result.ok)
        self.assertEqual(result.data.name, 'BGM_song_abcdef.mp3')
        self.assertTrue(result.data.is_file())

    def test_omitted_kind_behaves_exactly_as_before(self):
        result = self._import()
        self.assertTrue(result.ok)
        self.assertEqual(result.data.name, 'song_abcdef.mp3')


class ImportAudioWithKindTests(unittest.TestCase):
    """FIX-S11-E6：ui.tts_settings 导入胶水——问清用途才导入，取消询问不导入。"""

    def _app(self):
        app = Mock()
        app.async_.side_effect = lambda work, done: done(work())
        return app

    def test_selected_kind_is_passed_to_l3(self):
        from ui import tts_settings
        app = self._app()
        with patch('ui.tts_settings.ask_audio_kind', return_value='bgm'), \
                patch('stage_execution_service.import_stage_audio',
                      return_value=success(Path('dest.mp3'))) as service:
            tts_settings.import_audio_with_kind(app, 'song.mp3')
        service.assert_called_once_with(app.root, 'song.mp3', kind='bgm')
        app.status.set.assert_called_once_with('音频已导入：dest.mp3')

    def test_cancelled_choice_imports_nothing(self):
        from ui import tts_settings
        app = self._app()
        with patch('ui.tts_settings.ask_audio_kind', return_value=None), \
                patch('stage_execution_service.import_stage_audio') as service:
            tts_settings.import_audio_with_kind(app, 'song.mp3')
        service.assert_not_called()
        app.async_.assert_not_called()

    def test_failed_import_surfaces_reason_like_before(self):
        from ui import tts_settings
        app = self._app()
        with patch('ui.tts_settings.ask_audio_kind', return_value='dialogue'), \
                patch('stage_execution_service.import_stage_audio', return_value=UserError('导入失败')):
            with self.assertRaisesRegex(ValueError, '导入失败'):
                tts_settings.import_audio_with_kind(app, 'song.mp3')
        app.status.set.assert_not_called()
