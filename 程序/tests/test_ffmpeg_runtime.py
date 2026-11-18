"""工作树复用已确认随包解释器的 FFmpeg，且图片校验不得跳过真实解码。"""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from contract import platform_tools as tools
from domain import keyframe_evidence as evidence
from tests.image_fixtures import png


class BundledRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.local = self.root / 'checkout' / '运行环境' / 'ffmpeg' / 'bin'
        self.executable = self.root / 'installation' / '运行环境' / 'Python' / 'python.exe'
        self.runtime = self.executable.parent.parent / 'ffmpeg' / 'bin'
        self.addCleanup(tools._TOOL_CACHE.clear)
        tools._TOOL_CACHE.clear()

    def touch(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'fixture')
        return str(path)

    def locate(self, name, *, executable=None, which=None, **kwargs):
        with patch.object(tools, '_BUNDLED_BIN_DIR', self.local), \
                patch.object(tools.sys, 'executable', str(executable or self.executable)), \
                patch.object(tools.shutil, 'which', return_value=which) as lookup:
            result = tools.tool_path(name, **kwargs)
        return result, lookup

    def test_current_installation_bundle_precedes_interpreter_bundle_and_path(self):
        local = self.touch(self.local / 'ffmpeg.exe')
        self.touch(self.runtime / 'ffmpeg.exe')
        result, lookup = self.locate('ffmpeg', which='PATH-ffmpeg')
        self.assertEqual(result, local)
        lookup.assert_not_called()

    def test_confirmed_bundled_interpreter_supplies_ffmpeg_and_ffprobe(self):
        for name in ('ffmpeg', 'ffprobe'):
            with self.subTest(name=name):
                expected = self.touch(self.runtime / (name + '.exe'))
                result, lookup = self.locate(name, which='PATH-' + name)
                self.assertEqual(result, expected)
                lookup.assert_not_called()

    def test_confirmed_layout_is_case_insensitive_for_python_directory(self):
        executable = self.executable.parent.with_name('PYTHON') / 'python.exe'
        expected = self.touch(self.runtime / 'ffmpeg.exe')
        self.assertEqual(self.locate('ffmpeg', executable=executable)[0], expected)

    def test_generic_python_never_claims_adjacent_ffmpeg_as_our_runtime(self):
        for executable in (self.root / 'generic' / 'Python' / 'python.exe',
                           self.root / '运行环境' / 'Other' / 'python.exe'):
            with self.subTest(executable=executable):
                self.touch(executable.parent.parent / 'ffmpeg' / 'bin' / 'ffmpeg.exe')
                tools._TOOL_CACHE.clear()
                result, lookup = self.locate('ffmpeg', executable=executable, which='PATH-ffmpeg')
                self.assertEqual(result, 'PATH-ffmpeg')
                lookup.assert_called_once_with('ffmpeg')

    def test_missing_interpreter_binary_preserves_path_and_explicit_fallback(self):
        result, lookup = self.locate('ffmpeg', which='PATH-ffmpeg', fallback='fallback')
        self.assertEqual(result, 'PATH-ffmpeg')
        lookup.assert_called_once_with('ffmpeg')
        tools._TOOL_CACHE.clear()
        self.assertEqual(self.locate('ffmpeg', fallback='fallback')[0], 'fallback')
        self.assertIsNone(self.locate('ffprobe')[0])

    def test_explicit_existing_file_or_command_precedes_both_bundles(self):
        self.touch(self.local / 'ffmpeg.exe')
        self.touch(self.runtime / 'ffmpeg.exe')
        explicit = self.touch(self.root / 'configured' / 'ffmpeg.exe')
        for configured in (explicit, 'custom-ffmpeg'):
            with self.subTest(configured=configured):
                result, lookup = self.locate('ffmpeg', configured=configured)
                self.assertEqual(result, configured)
                lookup.assert_not_called()


class DecoderBoundaryTests(unittest.TestCase):
    def setUp(self):
        evidence._DECODED.clear()
        self.addCleanup(evidence._DECODED.clear)

    def test_missing_decoder_has_actionable_error_and_never_starts_process(self):
        with patch.object(evidence, 'tool_path', return_value=None), \
                patch.object(evidence, 'run_process') as run:
            with self.assertRaisesRegex(ValueError, '未找到.*FFmpeg.*配置'):
                evidence.image_facts(png())
            run.assert_not_called()
        self.assertEqual(evidence._DECODED, {})

    def test_worktree_decodes_real_fixture_with_authorized_bundled_ffmpeg(self):
        image = png((16, 9))
        decoder = tools.tool_path('ffmpeg')
        self.assertIsNotNone(decoder, '本验收使用真实随包 FFmpeg，不以 mock 代替解码')
        self.assertTrue(Path(decoder).is_file())
        facts = evidence.image_facts(image)
        self.assertEqual(facts, {'sha256': hashlib.sha256(image).hexdigest(), 'width': 16, 'height': 9})

    def test_truncated_png_is_rejected_before_decoder_launch(self):
        with patch.object(evidence, 'run_process') as run:
            with self.assertRaises(ValueError):
                evidence.image_facts(png()[:-8])
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
