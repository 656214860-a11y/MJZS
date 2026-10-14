"""逐笔用量落请求台账：视频下载成功、配音逐句合成；记账失败不影响制作。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import engine
import pet_llm
import stage_execution_service as ses
import tts_api


def rows(project):
    return pet_llm.RequestLedger(project).load().report()['kinds']


class RecordRequestTests(unittest.TestCase):
    def test_records_are_idempotent_per_id_and_kind(self):
        with tempfile.TemporaryDirectory() as folder:
            pet_llm.record_request(folder, 'r1', 'videos', 1)
            pet_llm.record_request(folder, 'r1', 'videos', 1)           # 重复调用只覆盖
            pet_llm.record_request(folder, 'r1', 'seconds', 5.0, mode='estimated')
            kinds = rows(folder)
            self.assertEqual((kinds['videos']['count'], kinds['videos']['settled']), (1, 1))
            self.assertEqual((kinds['seconds']['count'], kinds['seconds']['settled']), (1, 5.0))

    def test_failure_never_raises(self):
        with tempfile.TemporaryDirectory() as folder:
            blocker = Path(folder) / 'file'
            blocker.write_text('x', encoding='utf-8')
            self.assertIsNone(pet_llm.record_request(blocker, 'r1', 'videos', 1))   # 项目路径其实是文件
            self.assertIsNone(pet_llm.record_request(folder, 'r2', 'videos', 'abc'))


class VideoRecordingTests(unittest.TestCase):
    def test_downloaded_video_records_count_and_estimated_seconds(self):
        with tempfile.TemporaryDirectory() as folder:
            class Fake:
                root = Path(folder)
                shot = engine.Studio.shot
                episode = {'shots': [{'id': 'SH001', 'duration': 6}]}
                record_video_usage = engine.Studio.record_video_usage
            studio = Fake()
            studio.record_video_usage('SH001', {'version': 2})
            studio.record_video_usage('SH001', {'version': 2})
            kinds = rows(folder)
            self.assertEqual(kinds['videos']['settled'], 1)
            self.assertEqual(kinds['seconds']['settled'], 6)
            studio.record_video_usage('NOPE', {'version': 1})   # 镜头不存在：只记次数
            self.assertEqual(rows(folder)['videos']['count'], 2)
            self.assertEqual(rows(folder)['seconds']['count'], 1)


SETTINGS = {'model': 'm', 'voice': 'v', 'base_url': 'http://tts.invalid', 'voices': [], 'speeds': []}


@patch.object(tts_api, 'read_settings', return_value=SETTINGS)
class TtsRecordingTests(unittest.TestCase):
    def test_only_synthesized_lines_are_recorded_and_reused_lines_are_not(self, _settings):
        with tempfile.TemporaryDirectory() as folder:
            project, out = Path(folder), Path(folder) / 'audio'
            lines = [{'shot_id': 'S1', 'text': '你好', 'speed': 1.0}, {'shot_id': 'S2', 'text': '再见', 'speed': 1.0}]
            counter = {'n': 0}

            def generate(text, speed=1.0, voice=None):
                counter['n'] += 1
                return b'audio-%d-' % counter['n'] + text.encode()
            first = ses.run_tts_lines(lines, out, generate, episode='E1', project=project)
            self.assertEqual(first, (2, 0, 0))
            self.assertEqual(rows(project)['requests']['count'], 2)
            again = ses.run_tts_lines(lines, out, generate, episode='E1', project=project)
            self.assertEqual(again, (2, 2, 0))
            self.assertEqual(rows(project)['requests']['count'], 2)         # 沿用不重复记
            ses.run_tts_lines(lines[:1], out / 'other', generate, episode='E1')   # 不传 project：不记账
            self.assertEqual(rows(project)['requests']['count'], 2)

    def test_on_line_hook_is_optional_in_tts_api(self, _settings):
        with tempfile.TemporaryDirectory() as folder:
            seen = []
            tts_api.run_lines([{'shot_id': 'S1', 'text': 'a', 'speed': 1.0}], folder,
                              lambda text, speed=1.0, voice=None: b'x', gateway=ses.tts_gateway(),
                              on_line=lambda index, line, entry: seen.append((index, entry['state'])))
            self.assertEqual(seen, [(1, 'ok')])


if __name__ == '__main__':
    unittest.main()
