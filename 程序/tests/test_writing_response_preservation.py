"""阶段确认指令与未采用响应的正文保留。"""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import stage_config
import writing_api
from stage_execution_service import publish_stage_text, restart_writing_preparation
import test_writing_restart


class WritingResponsePreservationTests(unittest.TestCase):
    setUp = test_writing_restart.WritingRestartTests.setUp

    def call(self, text, creative='重写', **extra):
        with patch('writing_api.PoolAdapter.chat', return_value={'ok': True, 'text': text, **extra}) as chat:
            result = writing_api.reply(self.project, creative, publish=publish_stage_text)
            self.assertEqual(chat.call_count, 1)
            return result

    def test_explicit_confirmation_advances_only_to_next_stage(self):
        for confirmation in ('确定', '确认，输出项目大纲', '确认并输出项目大纲'):
            with self.subTest(confirmation=confirmation):
                restart_writing_preparation(self.project, '项目设定')
                self.call('# 项目设定\n新的设定。\n待确认')
                result = self.call('# 剧本大纲\n新的大纲。\n待确认', confirmation)
                self.assertTrue(result['ok'])
                state = json.loads(self.target.read_text(encoding='utf-8'))
                self.assertTrue(state['documents'][0]['confirmed'])
                self.assertEqual(state['documents'][1]['stage'], '剧本大纲')

    def test_modified_or_skipped_confirmation_stays_pending(self):
        for message in ('可以，但是把主角改成女的', '确认，但是修改设定', '确认，输出角色卡'):
            with self.subTest(message=message):
                restart_writing_preparation(self.project, '项目设定')
                result = self.call('# 项目设定\n修订设定。\n待确认', message)
                self.assertTrue(result['ok'])
                state = json.loads(self.target.read_text(encoding='utf-8'))
                self.assertFalse(state['revision']['documents'][0]['confirmed'])

    def test_rejected_body_is_preserved_without_adoption(self):
        for extra in ({}, {'response_meta': {'finish_reason': 'max_tokens'}}):
            with self.subTest(extra=extra):
                restart_writing_preparation(self.project, '项目设定')
                before = self.target.read_bytes()
                body = '  模型已返回的正文\r\n尚未写完  '
                result = self.call(body, **extra)
                self.assertFalse(result['ok'])
                self.assertEqual(result['text'], '')
                self.assertEqual(Path(result['response_path']).read_bytes(), body.encode('utf-8'))
                self.assertIn(result['response_path'], result['error'])
                self.assertEqual(self.target.read_bytes(), before)

    def test_version_conflict_preserves_body_and_rejects_publication(self):
        restart_writing_preparation(self.project, '项目设定')
        body = '# 项目设定\n迟到的正文。\n待确认'
        before = self.target.read_bytes()
        def changed(*args, **kwargs):
            stage_config.put(self.project, 'script', model='deepseek-v4-flash')
            return {'ok': True, 'text': body}
        with patch('writing_api.PoolAdapter.chat', side_effect=changed):
            with self.assertRaisesRegex(ValueError, '本次结果未采用.*正文已保存'):
                writing_api.reply(self.project, '重写', publish=publish_stage_text)
        saved = list((self.target.parent / 'responses').glob('*.txt'))
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].read_text(encoding='utf-8'), body)
        self.assertEqual(self.target.read_bytes(), before)

    def test_success_keeps_original_body_and_unique_backups(self):
        restart_writing_preparation(self.project, '项目设定')
        body = '# 项目设定\n完整正文。\n待确认'
        first = self.call(body)
        second = self.call(body)
        self.assertTrue(first['ok'])
        self.assertTrue(second['ok'])
        self.assertNotEqual(first['response_path'], second['response_path'])
        self.assertEqual(Path(first['response_path']).read_text(encoding='utf-8'), body)
        self.assertTrue(Path(second['preparation_path']).is_file())

    def test_empty_response_creates_no_backup(self):
        restart_writing_preparation(self.project, '项目设定')
        result = self.call('')
        self.assertFalse(result['ok'])
        self.assertNotIn('response_path', result)
        self.assertFalse((self.target.parent / 'responses').exists())

    def test_cancel_after_response_preserves_body_without_adoption(self):
        from hollmwood_roles import RoleCancelledError
        restart_writing_preparation(self.project, '项目设定')
        before = self.target.read_bytes()
        stopped = False
        def returned(*args, **kwargs):
            nonlocal stopped
            stopped = True
            return {'ok': True, 'text': '# 项目设定\n已返回的正文。\n待确认'}
        with patch('writing_api.PoolAdapter.chat', side_effect=returned):
            with self.assertRaisesRegex(RoleCancelledError, '正文已保存'):
                writing_api.reply(self.project, '重写', publish=publish_stage_text,
                                  cancelled=lambda: stopped)
        self.assertEqual(self.target.read_bytes(), before)
        self.assertEqual(len(list((self.target.parent / 'responses').glob('*.txt'))), 1)
