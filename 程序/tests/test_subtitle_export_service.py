from tests.architecture._scan import parse_desktop, desktop_text  # R1505：Desktop 方法分布在 desktop.py 与迁出的 Mixin 模块
import json
import tempfile
import unittest
import inspect
import ast
from pathlib import Path
from unittest.mock import Mock, patch

import skill_tools
from stage_execution_service import export_stage_dialogue_script, export_stage_srt
from orchestrator.subtitle_export_controller import publish_stage_srt_text
from domain.subtitle_export_service import export_dialogue_script, export_srt, publish_srt_text
from contract.service_contract import SystemError, UserError, success


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
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / 'delegated.srt'
            publisher = Mock(return_value=success(target))
            with patch('orchestrator.subtitle_export_controller.publish_stage_srt_text', publisher):
                result = skill_tools._subtitle_generate({'subtitle_file': str(target), 'episode': EPISODE})
            # 发布只经 service 一次，且 skill 工具自己不落盘（publisher 被替身时目标文件不该出现）。
            publisher.assert_called_once()
            self.assertEqual(publisher.call_args.args[0], str(target))
            self.assertFalse(target.exists())
            self.assertEqual(result['subtitle_file'], str(target))

    def test_l3_wrapper_publishes_validated_srt_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / 'skill.srt'
            result = publish_stage_srt_text(target, '正文\n')
            self.assertTrue(result.ok)
            self.assertEqual(target, result.data)

    def test_desktop_delegates_exports_to_service(self):
        source = desktop_text()
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

    def test_export_srt_rejects_invalid_author_times(self):
        bad = {'shots': [{'id': 'SH001', 'title': '初见', 'duration': 3,
                          'dialogue': [{'speaker': 'A', 'text': '你好', 'start': 3, 'end': 1}]}]}
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, r'SH001 第 1 句'):
                export_srt(folder, bad, publish=Mock())

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
        with patch('orchestrator.subtitle_export_controller.publish_stage_srt_text', return_value=SystemError('保存失败')):
            with self.assertRaisesRegex(ValueError, '保存失败'):
                skill_tools._subtitle_generate({'subtitle_file': 'target.srt', 'episode': EPISODE})

    def test_skill_success_uses_result_data(self):
        with patch('orchestrator.subtitle_export_controller.publish_stage_srt_text', return_value=success(Path('target.srt'))):
            result = skill_tools._subtitle_generate({'subtitle_file': 'target.srt', 'episode': EPISODE})
        self.assertTrue(result['ok'])
        self.assertEqual(result['subtitle_file'], 'target.srt')

    def test_desktop_export_methods_handle_success_and_failure(self):
        source = Path(__file__).resolve().parents[1] / 'desktop.py'
        tree = parse_desktop()
        methods = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                   and node.name in {'subtitles', 'dialogue_script'}}
        self.assertEqual(set(methods), {'subtitles', 'dialogue_script'})
        for name, node in methods.items():
            from orchestrator import media_page_controller
            namespace = {'media_logic': media_page_controller}  # R2058：方法迁到 desktop_media_pages 后用模块级别名 media_logic
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


class StageSrtLineAudioTests(unittest.TestCase):
    """FIX-S11-E9：导出字幕前查最近一批逐句配音成品，有真实音频就按它校准。"""

    def _episode(self, texts, episode_id='EP01'):
        return {'episode_id': episode_id, 'title': '集',
                'shots': [{'id': 'SH001', 'title': '初见', 'duration': 10,
                           'dialogue': [{'speaker': 'A', 'text': text} for text in texts]}]}

    def _line(self, shot, text, file='', state='failed'):
        return {'shot_id': shot, 'speaker': 'A', 'name': '角色', 'text': text,
                'start': 0.0, 'end': 1.0, 'file': file, 'state': state}

    def _batch(self, project, name, entries, episode=None):
        from contract.project_stages import audio
        folder = audio(Path(project)) / '配音分句' / name
        folder.mkdir(parents=True, exist_ok=True)
        meta = {'signature': 'sig', 'lines': len(entries)}
        if episode is not None:
            meta['episode'] = episode
        (folder / '批次.json').write_text(json.dumps(meta, ensure_ascii=False), encoding='utf-8')
        (folder / '时间轴.json').write_text(json.dumps(entries, ensure_ascii=False), encoding='utf-8')
        for entry in entries:
            if entry.get('file'):
                (folder / entry['file']).write_bytes(b'audio')
        return folder

    def test_export_uses_measured_line_durations(self):
        with tempfile.TemporaryDirectory() as folder:
            episode = self._episode(['你好', '再见'])
            self._batch(folder, '配音批次_20260101', [
                self._line('SH001', '你好', file='001.mp3', state='ok'),
                self._line('SH001', '再见', file='002.mp3', state='ok')], episode='EP01')
            durations = {'001.mp3': 1.2, '002.mp3': 3.4}
            result = export_stage_srt(folder, episode,
                                      probe_duration=lambda path: durations[Path(path).name])
            self.assertTrue(result.ok)
            target, report = result.data
            self.assertEqual(report['mode'], 'audio')
            self.assertEqual(report['audio'], 2)
            text = target.read_text(encoding='utf-8-sig')
            self.assertIn('00:00:00,000 --> 00:00:01,200', text)
            self.assertIn('00:00:01,200 --> 00:00:04,600', text)

    def test_partial_finished_lines_export_mixed_report(self):
        with tempfile.TemporaryDirectory() as folder:
            episode = self._episode(['你好', '再见'])
            self._batch(folder, '配音批次_20260101', [
                self._line('SH001', '你好', file='001.mp3', state='ok'),
                self._line('SH001', '再见')], episode='EP01')
            result = export_stage_srt(folder, episode, probe_duration=lambda path: 2.0)
            self.assertTrue(result.ok)
            _target, report = result.data
            self.assertEqual(report['mode'], 'mixed')
            self.assertEqual(report['audio'], 1)
            self.assertEqual(len(report['uncalibrated']), 1)
            self.assertEqual(report['uncalibrated'][0]['text'], '再见')

    def test_no_line_batch_keeps_length_estimate(self):
        with tempfile.TemporaryDirectory() as folder:
            probe = Mock(return_value=9.9)
            result = export_stage_srt(folder, self._episode(['你好']), probe_duration=probe)
            self.assertTrue(result.ok)
            _target, report = result.data
            self.assertEqual(report['mode'], 'length')
            self.assertEqual(report['audio'], 0)
            probe.assert_not_called()

    def test_finished_lines_without_ffprobe_fall_back_with_reason(self):
        with tempfile.TemporaryDirectory() as folder:
            episode = self._episode(['你好'])
            self._batch(folder, '配音批次_20260101', [
                self._line('SH001', '你好', file='001.mp3', state='ok')], episode='EP01')
            with patch('contract.platform_tools.tool_path', return_value=None):
                result = export_stage_srt(folder, episode)
            self.assertTrue(result.ok)
            _target, report = result.data
            self.assertEqual(report['mode'], 'length')
            self.assertEqual(report['audio_skip_reason'], '未配置 FFprobe')
            self.assertEqual(report['source']['audio_skip_reason'], '未配置 FFprobe')
            from orchestrator import media_page_controller
            status = media_page_controller.subtitle_status(report)
            self.assertIn('未配置 FFprobe', status)
            self.assertIn('估算', status)

    def test_other_episode_batch_is_not_mismatched(self):
        with tempfile.TemporaryDirectory() as folder:
            episode = self._episode(['你好'], episode_id='EP01')
            self._batch(folder, '配音批次_20260102', [
                self._line('SH001', '你好', file='001.mp3', state='ok')], episode='EP02')
            result = export_stage_srt(folder, episode, probe_duration=lambda path: 7.0)
            self.assertTrue(result.ok)
            _target, report = result.data
            self.assertEqual(report['mode'], 'length')
            self.assertEqual(report['audio'], 0)
            self._batch(folder, '配音批次_20260101', [
                self._line('SH001', '你好', file='001.mp3', state='ok')], episode='EP01')
            seen = []
            result = export_stage_srt(
                folder, episode,
                probe_duration=lambda path: seen.append(Path(path).parent.name) or 7.0)
            self.assertTrue(result.ok)
            _target, report = result.data
            self.assertEqual(report['mode'], 'audio')
            self.assertEqual(seen, ['配音批次_20260101'], '只能配对本集批次，不是更新的别集批次')

    def test_legacy_batch_without_episode_still_applies(self):
        with tempfile.TemporaryDirectory() as folder:
            episode = self._episode(['你好'])
            self._batch(folder, '配音批次_20260101', [
                self._line('SH001', '你好', file='001.mp3', state='ok')])
            result = export_stage_srt(folder, episode, probe_duration=lambda path: 2.5)
            self.assertTrue(result.ok)
            _target, report = result.data
            self.assertEqual(report['mode'], 'audio')
            self.assertEqual(report['audio'], 1)


if __name__ == '__main__':
    unittest.main()
