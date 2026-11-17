# -*- coding: utf-8 -*-
"""聊天消息 typed parts 契约（R3102）。

覆盖：parts 数据模型与 schema_version、旧扁平对话 → parts 迁移（thinking 保留为
REASONING、正文不丢）、set_text 同步、has_content 保留「只有思考」的行、
写入落盘带 ``schema_version`` 与 ``parts``。
运行：python tests/test_message_parts.py
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import idea_chat
from domain import idea_transcript
from domain import message_parts
from contract.project_stages import writing
from stage_execution_service import idea_chat_gateway, project_context


class MessagePartsTests(unittest.TestCase):
    def test_part_shape_and_schema_version(self):
        self.assertEqual(message_parts.SCHEMA_VERSION, 2)
        self.assertEqual(message_parts.VERSION_KEY, 'schema_version')
        self.assertEqual(message_parts.text_part('正文'),
                         {'type': 'text', 'payload': {'text': '正文'}, 'state': 'done'})
        self.assertEqual(message_parts.reasoning_part('想')['type'], 'reasoning')

    def test_flat_row_derives_reasoning_then_text(self):
        row = {'role': 'assistant', 'text': '正文', 'thinking': '思考'}
        parts = message_parts.derive_parts(row)
        self.assertEqual([item['type'] for item in parts], ['reasoning', 'text'])
        self.assertEqual(message_parts.reasoning_of(parts), '思考')
        self.assertEqual(message_parts.text_of(parts), '正文')

    def test_ensure_parts_is_idempotent_and_preserves_existing(self):
        row = {'role': 'assistant', 'text': '正文'}
        first = message_parts.ensure_parts(row)
        second = message_parts.ensure_parts(first)
        self.assertEqual(first['parts'], second['parts'])
        existing = {'role': 'assistant', 'text': '正文', 'parts': [message_parts.text_part('正文')]}
        self.assertEqual(message_parts.ensure_parts(existing)['parts'], existing['parts'])

    def test_has_content_keeps_reasoning_only_row(self):
        self.assertTrue(message_parts.has_content(
            {'text': '', 'parts': [message_parts.reasoning_part('只有思考')]}))
        self.assertFalse(message_parts.has_content({'text': '', 'parts': []}))

    def test_set_text_only_replaces_text_part(self):
        row = {'role': 'assistant', 'text': '旧正文', 'thinking': '旧思考'}
        updated = message_parts.set_text(row, '新正文')
        self.assertEqual(updated['text'], '新正文')
        self.assertEqual(message_parts.text_of(updated['parts']), '新正文')
        self.assertEqual(message_parts.reasoning_of(updated['parts']), '旧思考')

    def test_message_row_round_trip(self):
        row = {'role': 'assistant', 'text': '正文', 'at': '20260101_000000_000000'}
        message = message_parts.message_from_row(row)
        rebuilt = message_parts.row_from_message(message)
        self.assertEqual(rebuilt['text'], '正文')
        self.assertEqual(rebuilt['role'], 'assistant')
        self.assertEqual(rebuilt['parts'], message_parts.ensure_parts(row)['parts'])


class TranscriptMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = project_context(self.tmp.name)
        self.gateway = idea_chat_gateway()

    def _path(self):
        return writing(Path(self.tmp.name)) / idea_transcript.FOLDER / idea_transcript.CHAT_NAME

    def test_old_flat_dialog_migrates_to_parts_on_read(self):
        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        legacy = {'version': 1, 'messages': [
            {'role': 'user', 'text': '旧问题', 'at': '20260101_000000_000000'},
            {'role': 'assistant', 'text': '旧回答', 'thinking': '旧思考',
             'at': '20260101_000001_000000'}]}
        path.write_text(json.dumps(legacy, ensure_ascii=False), encoding='utf-8')
        idea_transcript._history_cache.clear()
        rows = idea_chat.load(self.root, gateway=self.gateway)
        self.assertEqual([row['text'] for row in rows], ['旧问题', '旧回答'], '迁移不能丢正文')
        self.assertEqual([item['type'] for item in rows[1]['parts']], ['reasoning', 'text'])
        self.assertEqual(message_parts.reasoning_of(rows[1]['parts']), '旧思考')

    def test_saved_dialog_carries_schema_version_and_parts(self):
        idea_chat.append(self.root, 'user', '新问题', gateway=self.gateway)
        idea_transcript._history_cache.clear()
        payload = json.loads(self._path().read_text(encoding='utf-8'))
        self.assertEqual(payload.get('schema_version'), 2)
        self.assertTrue(payload['messages'])
        self.assertTrue(all(row.get('parts') for row in payload['messages']),
                        '写入必须带 parts')


if __name__ == '__main__':
    unittest.main()
