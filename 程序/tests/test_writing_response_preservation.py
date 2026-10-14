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

    def test_api_decides_colloquial_confirmation_and_receives_original_input(self):
        restart_writing_preparation(self.project, '项目设定')
        self.call('# 项目设定\n新的设定。\n待确认')
        with patch('writing_api.PoolAdapter.chat', return_value={
                'ok': True, 'text': '# 剧本大纲\n新的大纲。\n待确认'}) as chat:
            result = writing_api.reply(self.project, '确认项目通过\n附件补充材料',
                                       user_message='确认项目通过', publish=publish_stage_text)
        self.assertTrue(result['ok'])
        self.assertEqual(result['preparation_stage'], '剧本大纲')
        self.assertEqual(chat.call_count, 1)
        prompt = chat.call_args.args[0][0]['content']
        self.assertIn('确认项目通过', prompt)
        self.assertIn('附件补充材料', prompt)
        self.assertIn('新的设定。', prompt)
        state = json.loads(self.target.read_text(encoding='utf-8'))
        self.assertTrue(state['documents'][0]['confirmed'])
        self.assertFalse(state['documents'][1]['confirmed'])

    def test_api_can_keep_current_stage_even_for_local_confirmation_word(self):
        restart_writing_preparation(self.project, '项目设定')
        self.call('# 项目设定\n需要澄清的设定。\n待确认')
        result = self.call('# 项目设定\n补全后的设定。\n待确认', '确认')
        self.assertTrue(result['ok'])
        state = json.loads(self.target.read_text(encoding='utf-8'))
        self.assertFalse(state['revision']['documents'][0]['confirmed'])

    def call(self, text, creative='重写', **extra):
        with patch('writing_api.PoolAdapter.chat', return_value={'ok': True, 'text': text, **extra}) as chat:
            result = writing_api.reply(self.project, creative, publish=publish_stage_text)
            self.assertEqual(chat.call_count, 1)
            return result

    def test_explicit_confirmation_advances_only_to_next_stage(self):
        for confirmation in ('确定', '确认，输出项目大纲', '确认并输出项目大纲', '输出大纲', '生成项目大纲'):
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
                self.assertEqual(result['response_text'], body)
                self.assertEqual(Path(result['response_path']).read_bytes(), body.encode('utf-8'))
                self.assertIn(result['response_path'], result['error'])
                self.assertEqual(result['preparation_status'], '原始响应已保存')
                self.assertEqual(result['preparation_reject'], '截断' if extra else '格式不合格')
                message = writing_api.preparation_reply_message(result)
                self.assertIn('responses/', message)
                self.assertIn('不等于正式采用', message)
                self.assertEqual(self.target.read_bytes(), before)

    def test_version_conflict_preserves_body_and_rejects_publication(self):
        restart_writing_preparation(self.project, '项目设定')
        body = '# 项目设定\n迟到的正文。\n待确认'
        before = self.target.read_bytes()
        def changed(*args, **kwargs):
            stage_config.put(self.project, 'script', model='deepseek-v4-flash')
            return {'ok': True, 'text': body}
        with patch('writing_api.PoolAdapter.chat', side_effect=changed):
            with self.assertRaisesRegex(ValueError, '本次结果未采用.*原始响应已保存'):
                writing_api.reply(self.project, '重写', publish=publish_stage_text)
        saved = list((self.target.parent / 'responses').glob('*.txt'))
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].read_text(encoding='utf-8'), body)
        self.assertEqual(self.target.read_bytes(), before)

    def test_publication_failure_returns_visible_body_through_service(self):
        from stage_execution_service import reply_to_writing
        restart_writing_preparation(self.project, '项目设定')
        body = '# 项目设定\n可见正文。\n待确认'
        def changed(*args, **kwargs):
            stage_config.put(self.project, 'script', model='deepseek-v4-flash')
            return {'ok': True, 'text': body}
        with patch('writing_api.PoolAdapter.chat', side_effect=changed):
            result = reply_to_writing(self.project, '重写')
        self.assertFalse(result['ok'])
        self.assertEqual(result['response_text'], body)
        self.assertNotIn('preparation_path', result)
        self.assertEqual(result['preparation_status'], '因版本变化未采用')
        self.assertIn('不等于正式采用', writing_api.preparation_reply_message(result))

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
        from writing_api import WritingCancelledError
        restart_writing_preparation(self.project, '项目设定')
        before = self.target.read_bytes()
        stopped = False
        def returned(*args, **kwargs):
            nonlocal stopped
            stopped = True
            return {'ok': True, 'text': '# 项目设定\n已返回的正文。\n待确认'}
        with patch('writing_api.PoolAdapter.chat', side_effect=returned):
            with self.assertRaisesRegex(WritingCancelledError, '原始响应已保存'):
                writing_api.reply(self.project, '重写', publish=publish_stage_text,
                                  cancelled=lambda: stopped)
        self.assertEqual(self.target.read_bytes(), before)
        self.assertEqual(len(list((self.target.parent / 'responses').glob('*.txt'))), 1)

    def test_explanatory_wrapper_and_confirmation_section_are_accepted(self):
        restart_writing_preparation(self.project, '项目设定')
        body = ('项目设定已按本轮资料重整。\n\n# 项目设定\n\n完整设定。\n\n'
                '## 待确认\n请确认以上项目设定是否通过。\n确认通过后进入剧本大纲。')
        result = self.call(body)
        self.assertTrue(result['ok'])
        published = Path(result['preparation_path']).read_text(encoding='utf-8')
        self.assertTrue(published.startswith('# 项目设定\n'))
        self.assertTrue(published.rstrip().endswith('待确认'))
        self.assertIn('完整设定。', published)
        self.assertEqual(Path(result['response_path']).read_text(encoding='utf-8'), body)

    def test_wrong_stage_multiple_documents_and_truncation_still_rejected(self):
        for body, meta in (
            ('# 剧本大纲\n错阶段。\n待确认', {}),
            ('# 项目设定\n设定。\n# 剧本大纲\n大纲。\n待确认', {}),
            ('说明。\n# 项目设定\n设定。\n## 待确认\n请确认。', {'finish_reason': 'max_tokens'}),
            ('# 项目设定\n正文没有结束标记。', {}),
        ):
            with self.subTest(body=body):
                restart_writing_preparation(self.project, '项目设定')
                result = self.call(body, response_meta=meta)
                self.assertFalse(result['ok'])
                self.assertNotIn('preparation_path', result)
                self.assertTrue(Path(result['response_path']).is_file())

    def test_rejected_next_stage_does_not_confirm_current_document(self):
        restart_writing_preparation(self.project, '项目设定')
        self.assertTrue(self.call('# 项目设定\n当前设定。\n待确认')['ok'])
        before = self.target.read_bytes()
        result = self.call('# 剧本大纲\n未完成的大纲。\n待确认',
                           response_meta={'finish_reason': 'max_tokens'})
        self.assertFalse(result['ok'])
        self.assertEqual(self.target.read_bytes(), before)
        self.assertIn('未完成的大纲', result['response_text'])


class PreparationReplyStateTests(unittest.TestCase):
    setUp = test_writing_restart.WritingRestartTests.setUp

    def call(self, text, creative='重写', **extra):
        with patch('writing_api.PoolAdapter.chat', return_value={'ok': True, 'text': text, **extra}) as chat:
            result = writing_api.reply(self.project, creative, publish=publish_stage_text)
            self.assertEqual(chat.call_count, 1)
            return result

    def test_state_helper_distinguishes_the_four_reply_classes(self):
        self.assertEqual(writing_api.preparation_reply_state(
            {'ok': False, 'response_path': '/x/r.txt'})['state'], '原始响应已保存')
        self.assertEqual(writing_api.preparation_reply_state(
            {'ok': True, 'preparation_path': '/x/s.md'})['state'], '阶段稿待确认')
        self.assertEqual(writing_api.preparation_reply_state(
            {'ok': True, 'natural_script_path': '/x/n.md'})['state'], '已采用')
        self.assertEqual(writing_api.preparation_reply_state(
            {'ok': False, 'preparation_status': '因版本变化未采用', 'response_path': '/x/r.txt'})['state'],
            '因版本变化未采用')
        self.assertEqual(writing_api.preparation_reply_state({'ok': False, 'error': 'x'})['state'], '')
        self.assertEqual(writing_api.preparation_reply_message({'ok': False, 'error': 'x'}), '')

    def test_confirmation_success_reports_pending_stage_draft(self):
        restart_writing_preparation(self.project, '项目设定')
        result = self.call('# 项目设定\n完整设定。\n待确认', '确认')
        self.assertTrue(result['ok'])
        info = writing_api.preparation_reply_state(result)
        self.assertEqual(info['state'], '阶段稿待确认')
        self.assertEqual(info['file'], result['preparation_path'])
        message = writing_api.preparation_reply_message(result)
        self.assertIn('待确认', message)
        self.assertIn('确认', message)

    def test_late_reply_after_cancel_reports_archive_in_error(self):
        from writing_api import WritingCancelledError
        restart_writing_preparation(self.project, '项目设定')
        before = self.target.read_bytes()
        stopped = False
        def returned(*args, **kwargs):
            nonlocal stopped
            stopped = True
            return {'ok': True, 'text': '# 项目设定\n取消后迟到的正文。\n待确认'}
        with patch('writing_api.PoolAdapter.chat', side_effect=returned):
            with self.assertRaises(WritingCancelledError) as caught:
                writing_api.reply(self.project, '重写', publish=publish_stage_text,
                                  cancelled=lambda: stopped)
        message = str(caught.exception)
        self.assertIn('原始响应已保存', message)
        self.assertIn('不等于正式采用', message)
        saved = list((self.target.parent / 'responses').glob('*.txt'))
        self.assertEqual(len(saved), 1)
        self.assertIn(str(saved[0]), message)
        self.assertEqual(self.target.read_bytes(), before)

