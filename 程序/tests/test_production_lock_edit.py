"""制作锁附档更新与手动编辑回归。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.core import save
import file_cache
import stage_config
import stage_execution_service as service
import workflow_settings
from idea_chat import brief_complete_path
from project_context_factory import project_context


class ProductionLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.name = next(iter(workflow_settings.WORKFLOW_PRESETS))
        stage_config.put_workflow(self.root, {'name': self.name, 'lock': {
            self.name: {'aspect_ratio': '9:16', 'delivery_format': 'markdown文件'}}})
        self.brief = brief_complete_path(project_context(self.root))
        save(self.brief, {'brief': {'story_summary': '原故事', 'production_locks': {
            'aspect_ratio': '9:16', 'delivery_format': 'markdown文件'}}})

    def test_changed_attachment_updates_both_copies_and_keeps_other_fields(self):
        reference = {'brief_texts': ['故事画幅：16:9']}
        service.sync_writing_attachment_locks(self.root, reference=reference)
        self.assertEqual(stage_config.workflow_lock(self.root)['aspect_ratio'], '16:9')
        brief = file_cache.read_json(self.brief)['brief']
        self.assertEqual(brief['production_locks']['aspect_ratio'], '16:9')
        self.assertEqual(brief['production_locks']['delivery_format'], 'markdown文件')
        self.assertEqual(brief['story_summary'], '原故事')

    def test_unchanged_attachment_does_not_overwrite_manual_edit(self):
        reference = {'brief_texts': ['故事画幅：16:9']}
        service.sync_writing_attachment_locks(self.root, reference=reference)
        service.save_writing_production_locks(self.root, {'aspect_ratio': '4:3'})
        service.sync_writing_attachment_locks(self.root, reference=reference)
        self.assertEqual(stage_config.workflow_lock(self.root)['aspect_ratio'], '4:3')
        service.sync_writing_attachment_locks(self.root, reference={'brief_texts': ['故事画幅：21:9']})
        self.assertEqual(stage_config.workflow_lock(self.root)['aspect_ratio'], '21:9')

    def test_upload_syncs_archived_attachment(self):
        source = self.root / '材料.txt'
        source.write_text('故事画幅：16:9', encoding='utf-8')
        with patch.object(service, 'idea_attachment_local_mode', return_value=False):
            service.archive_idea_attachments(self.root, [source])
        self.assertEqual(stage_config.workflow_lock(self.root)['aspect_ratio'], '16:9')
        self.assertEqual(file_cache.read_json(self.brief)['brief']['production_locks']['aspect_ratio'], '16:9')

    def test_brief_collection_keeps_manual_lock_after_attachment_sync(self):
        from tests.test_idea_chat import idea_chat as injected_chat
        from tests.test_idea_inline_brief import draft
        reference = {'brief_texts': [draft()]}
        service.sync_writing_attachment_locks(self.root, reference=reference)
        service.save_writing_production_locks(self.root, {'aspect_ratio': '16:9'})
        result = injected_chat.receive_brief(self.root, '请创作',
            workflow=stage_config.current_workflow(self.root),
            lock_definitions=workflow_settings.WORKFLOW_PRESETS[self.name]['locks'],
            attachment_reference=reference)
        self.assertEqual(result['fields']['production_locks']['aspect_ratio'], '16:9')
        self.assertEqual(result['missing'], ())

    def test_manual_config_wins_over_saved_draft_but_current_request_wins(self):
        from tests.test_idea_chat import idea_chat as injected_chat
        from tests.test_idea_inline_brief import draft
        injected_chat.save_brief_creation(self.root, draft())
        service.save_writing_production_locks(self.root, {'aspect_ratio': '16:9'})
        for message, expected in [('请创作', '16:9'), ('故事画幅：21:9', '21:9')]:
            result = injected_chat.receive_brief(self.root, message,
                workflow=stage_config.current_workflow(self.root),
                lock_definitions=workflow_settings.WORKFLOW_PRESETS[self.name]['locks'])
            self.assertEqual(result['fields']['production_locks']['aspect_ratio'], expected)

    def test_bundle_failure_restores_both_files(self):
        before = (stage_config.path(self.root).read_bytes(), self.brief.read_bytes())
        from agent.core import save_bytes
        def fail(path, raw):
            if Path(path) == self.brief and raw != before[1]:
                raise OSError('test failure')
            return save_bytes(path, raw)
        with patch('agent.core.save_bytes', side_effect=fail):
            with self.assertRaises(OSError):
                service.save_writing_production_locks(self.root, {'aspect_ratio': '16:9'})
        self.assertEqual(before, (stage_config.path(self.root).read_bytes(), self.brief.read_bytes()))


if __name__ == '__main__':
    unittest.main()
