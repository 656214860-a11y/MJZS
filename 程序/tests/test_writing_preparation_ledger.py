# -*- coding: utf-8 -*-
"""剧本准备台账模块迁移回归：确认迁入 orchestrator.writing_preparation_ledger 的函数行为与转发。"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import writing_api
from orchestrator import writing_preparation_ledger as ledger


EXTRACTED_SYMBOLS = (
    'PREPARATION_REPLY_STATES',
    'confirmed_preparation_files',
    'preparation_file_labels',
    'preparation_reply_state',
    'preparation_reply_message',
    '_preparation_state',
    '_preserve_preparation_response',
    '_preparation_task',
    '_preparation_restart_affirmative',
    '_versioned_publisher',
)


def _direct_publish(path, text, validate, update_index):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not validate(text):
        raise ValueError('校验未通过')
    target.write_text(text, encoding='utf-8')
    update_index(target)


class WritingPreparationLedgerTests(unittest.TestCase):
    def test_extracted_symbols_live_in_ledger_and_reexport_from_writing_api(self):
        for name in EXTRACTED_SYMBOLS:
            self.assertTrue(hasattr(ledger, name), f'ledger 缺少迁出符号 {name}')
            self.assertIs(getattr(writing_api, name), getattr(ledger, name),
                          f'writing_api.{name} 必须按同一对象转发')

    def test_preparation_reply_state_and_message_cover_all_statuses(self):
        self.assertEqual(ledger.preparation_reply_state(None)['state'], '')
        self.assertEqual(ledger.preparation_reply_message({}), '')

        adopted = ledger.preparation_reply_state({'natural_script_path': 'script/a.md'})
        self.assertEqual(adopted['state'], '已采用')
        self.assertIn('已采用为正式剧本：script/a.md',
                      ledger.preparation_reply_message({'natural_script_path': 'script/a.md'}))

        draft = {'preparation_path': 'script/setting.md', 'preparation_stage': '项目设定'}
        self.assertEqual(ledger.preparation_reply_state(draft)['state'], '阶段稿待确认')
        self.assertIn('项目设定已保存（待确认，尚未正式采用）：script/setting.md',
                      ledger.preparation_reply_message(draft))

        archived = {'response_path': 'responses/r.txt', 'preparation_reject': '格式不合格'}
        self.assertEqual(ledger.preparation_reply_state(archived)['state'], '原始响应已保存')
        self.assertIn('格式不合格', ledger.preparation_reply_message(archived))

        stale = {'preparation_status': '因版本变化未采用', 'response_path': 'responses/s.txt'}
        self.assertEqual(ledger.preparation_reply_state(stale)['state'], '因版本变化未采用')
        self.assertIn('因版本变化未采用', ledger.preparation_reply_message(stale))

    def test_confirmed_files_and_labels_reflect_adopted_and_revision_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            script_dir = project / '01剧本准备'
            script_dir.mkdir(parents=True, exist_ok=True)
            setting_path = script_dir / 'setting.md'
            outline_path = script_dir / 'outline.md'
            rev_path = script_dir / 'setting_v2.md'
            for path in (setting_path, outline_path, rev_path):
                path.write_text('# 内容\n正文\n', encoding='utf-8')
            state = {
                'version': 1,
                'brief_hash': 'h1',
                'documents': [
                    {'stage': '项目设定', 'path': 'setting.md', 'sha256': 'x', 'confirmed': True},
                    {'stage': '剧本大纲', 'path': 'outline.md', 'sha256': 'y', 'confirmed': False},
                ],
                'revision': {
                    'brief_hash': 'h1',
                    'documents': [
                        {'stage': '项目设定', 'path': 'setting_v2.md', 'sha256': 'z', 'confirmed': False},
                    ],
                },
            }
            (script_dir / 'preparation_state.json').write_text(
                json.dumps(state, ensure_ascii=False), encoding='utf-8')

            confirmed = ledger.confirmed_preparation_files(project)
            self.assertEqual(confirmed, {setting_path.resolve(): '项目设定'})

            labels = ledger.preparation_file_labels(project)
            self.assertEqual(labels[str(setting_path.resolve())], '已确认')
            self.assertEqual(labels[str(outline_path.resolve())], '待确认')
            self.assertEqual(labels[str(rev_path.resolve())], '重写待确认')

    def test_restart_affirmative_and_preserve_response(self):
        self.assertTrue(ledger._preparation_restart_affirmative('确认！\n补充说明'))
        self.assertFalse(ledger._preparation_restart_affirmative('继续'))

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            blank = ledger._preserve_preparation_response(project, {'text': '   '}, _direct_publish)
            self.assertNotIn('response_path', blank)

            kept = ledger._preserve_preparation_response(project, {'text': '第一行\r\n第二行'}, _direct_publish)
            saved = Path(kept['response_path'])
            self.assertTrue(saved.is_file())
            self.assertEqual(saved.read_text(encoding='utf-8'), '第一行\n第二行')

    def test_preparation_state_resets_on_brief_change_while_keeping_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            script_dir = project / '01剧本准备'
            script_dir.mkdir(parents=True, exist_ok=True)
            old_state = {
                'version': 1,
                'brief_hash': 'outdated-hash',
                'documents': [{'stage': '项目设定', 'path': 'setting.md', 'sha256': 'a', 'confirmed': True}],
                'snapshots': [{'stage': '项目设定', 'path': 'setting.md', 'sha256': 'a', 'snapshot': '确认快照/x.md'}],
            }
            (script_dir / 'preparation_state.json').write_text(
                json.dumps(old_state, ensure_ascii=False), encoding='utf-8')
            brief = {'brief': {'title': '新剧名'}}
            expected_hash = hashlib.sha256(
                json.dumps(brief['brief'], ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()

            _target, state, texts = ledger._preparation_state(project, brief)
            self.assertEqual(state['brief_hash'], expected_hash)
            self.assertEqual(state['documents'], [])
            self.assertEqual(state['snapshots'], old_state['snapshots'])
            self.assertEqual(texts, [])

    def test_versioned_publisher_rejects_midflight_ledger_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            script_dir = project / '01剧本准备'
            script_dir.mkdir(parents=True, exist_ok=True)
            ledger_file = script_dir / 'preparation_state.json'
            ledger_file.write_text('{"version": 1, "documents": []}\n', encoding='utf-8')

            with patch('infra.stage_model_value.value', return_value='model-a'):
                guarded = ledger._versioned_publisher(project, _direct_publish)
                ledger_file.write_text('{"version": 1, "documents": [{"stage": "项目设定"}]}\n', encoding='utf-8')
                with self.assertRaisesRegex(ValueError, '生成期间模型或阶段文件已变化'):
                    guarded(script_dir / 'out.md', '正文\n', lambda v: bool(v), lambda _t: None)


if __name__ == '__main__':
    unittest.main()
