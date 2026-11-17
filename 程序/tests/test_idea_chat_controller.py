"""无 Tk 的剧本准备对话控制器回归。"""
import sys
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.idea_chat_controller import IdeaChatController


class IdeaChatControllerTests(unittest.TestCase):
    def test_request_cleanup_runs_once_and_old_token_cannot_cancel_new_request(self):
        controller = IdeaChatController()
        cleaned = []
        old, cancelled = controller.begin_request(cancellable=True)
        controller.set_request_cleanup(old, lambda: cleaned.append('old'))
        controller.cancel_request()
        controller.cancel_request()
        self.assertTrue(cancelled.is_set())
        new, _ = controller.begin_request(cancellable=True)
        controller.set_request_cleanup(new, lambda: cleaned.append('new'))
        self.assertFalse(controller.finish_request(old))
        self.assertTrue(controller.request_is_current(new))
        self.assertEqual(cleaned, ['old'])
        self.assertTrue(controller.finish_request(new))
        self.assertFalse(controller.finish_request(new))
        self.assertEqual(cleaned, ['old', 'new'])

    def test_cancelled_request_can_delete_upload_after_mode_switch(self):
        from domain.idea_attachments import archive_pair
        from stage_execution_service import archive_idea_attachments, stage_idea_attachment_paths
        from storage_maintenance import restore_latest_recycled_path
        for local_mode in (True, False):
            with self.subTest(local_mode=local_mode), tempfile.TemporaryDirectory() as td, \
                 patch('stage_execution_service.idea_attachment_local_mode', return_value=local_mode) as mode:
                root = Path(td)
                source = root / '人物.txt'
                source.write_text('保留原始人物设定', encoding='utf-8')
                selected = archive_idea_attachments(root, (source,))[0]
                pair = archive_pair(selected)
                other = archive_idea_attachments(root, (source,))[0]
                controller = IdeaChatController()
                controller.replace_attachments(pair + (other,), tuple((p.name, 8) for p in pair + (other,)))
                self.assertIn(selected, stage_idea_attachment_paths(root))
                token, cancelled = controller.begin_request(cancellable=True)
                controller.cancel_request()
                mode.return_value = not local_mode
                self.assertNotIn(selected, stage_idea_attachment_paths(root))
                controller.delete_attachment(root, selected)
                self.assertTrue(cancelled.is_set())
                self.assertFalse(controller.finish_request(token))
                self.assertTrue(source.is_file())
                self.assertTrue(all(p.is_file() for p in archive_pair(other)))
                self.assertEqual(controller.attachment_paths, (str(other),))
                self.assertEqual(controller.attachment_details, ((other.name, 8),))
                for path in pair:
                    self.assertFalse(path.exists())
                    restore_latest_recycled_path(root, path)
                    self.assertIn('保留原始人物设定', path.read_text(encoding='utf-8'))

    def test_deleted_upload_is_recoverable_and_no_longer_referenced(self):
        from stage_execution_service import archive_idea_attachments, stage_idea_attachment_reference
        from storage_maintenance import restore_latest_recycled_path
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / '角色.xlsx.txt'
            source.write_text('测试角色', encoding='utf-8')
            archived = archive_idea_attachments(root, (source,))[0]
            controller = IdeaChatController()
            controller.replace_attachments((archived,), ((archived.name, 4),))
            controller.delete_attachment(root, archived)
            self.assertTrue(source.is_file())
            self.assertFalse(archived.exists())
            self.assertEqual(controller.attachment_paths, ())
            self.assertEqual(controller.attachment_details, ())
            self.assertEqual(stage_idea_attachment_reference(root)['context'], '')
            restore_latest_recycled_path(root, archived)
            self.assertEqual(archived.read_text(encoding='utf-8').strip(), '测试角色')

    def test_attachment_delete_rejects_source_foreign_project_and_busy_state(self):
        from stage_execution_service import archive_idea_attachments
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / '原文件.txt'
            source.write_text('保留', encoding='utf-8')
            archived = archive_idea_attachments(root / 'project', (source,))[0]
            controller = IdeaChatController()
            for project, path in ((root / 'project', source), (root / 'other', archived)):
                with self.subTest(project=project), self.assertRaises(ValueError):
                    controller.delete_attachment(project, path)
            for flag in ('attachment_preparing', 'requesting', 'script_agent_launching'):
                setattr(controller, flag, True)
                with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, '进行中'):
                    controller.delete_attachment(root / 'project', archived)
                setattr(controller, flag, False)
            self.assertTrue(source.is_file())
            self.assertTrue(archived.is_file())

    def test_failed_recycle_keeps_attachment_state(self):
        controller = IdeaChatController()
        path = Path('project/故事创意_1.md')
        controller.replace_attachments((path,), ((path.name, 2),))
        with patch('stage_execution_service.stage_idea_attachment_paths', return_value=(path,)), \
             patch('storage_maintenance.recycle_paths', return_value=[]):
            with self.assertRaises(OSError):
                controller.delete_attachment('project', path)
        self.assertEqual(controller.attachment_paths, (str(path),))
        self.assertEqual(controller.attachment_details, ((path.name, 2),))

    def test_attachment_injection_keeps_existing_visible_marker(self):
        controller = IdeaChatController()
        controller.replace_attachments(('D:/idea.md',))
        referenced = {'context': '[附件]\n创意内容', 'names': ('idea.md',)}
        with patch('domain.idea_attachments.referenced', return_value=referenced):
            result = controller.prepare_submission(Path('D:/project'), '请参考 @idea.md', is_example=False)
        self.assertEqual(result['submission'], '请参考 @idea.md\n\n[附件]\n创意内容')
        self.assertEqual(result['visible_value'], '请参考 @idea.md\n【已引用：idea.md】')

    def test_send_debounce_uses_injected_clock(self):
        now = [10.0]
        controller = IdeaChatController(clock=lambda: now[0])
        controller.mark_sent()
        now[0] += 0.2
        with self.assertRaisesRegex(ValueError, '发送过于频繁'):
            controller.mark_sent()
        now[0] += 0.11
        controller.mark_sent()

    def test_cancelled_request_drops_late_progress(self):
        controller = IdeaChatController()
        token, cancelled = controller.begin_request(cancellable=True)
        events = []
        report = controller.progress_callback(token, 7, lambda *event: events.append(event))
        report('writer', 1)
        controller.cancel_request()
        report('writer', 2)
        self.assertTrue(cancelled.is_set())
        self.assertEqual(events, [(7, 'writer', 1)])

    def test_attachment_preparation_runs_off_the_submission_path(self):
        controller = IdeaChatController()
        prepared = {
            'paths': ('D:/project/01剧本准备/输入/故事创意_1.md',),
            'names': ('故事创意_1.md',),
            'details': (('故事创意_1.md', 4),),
            'context': '[附档：故事创意_1.md]\n内容',
        }
        with patch('stage_execution_service.archive_idea_attachments', return_value=prepared['paths']), \
             patch('domain.idea_attachments.prepare', return_value=prepared):
            controller.start_attachment_preparation(Path('D:/project'), ('D:/source.md',))
            with self.assertRaisesRegex(ValueError, '附档正在入库和校验'):
                controller.prepare_submission(Path('D:/project'), '请参考附档', is_example=False)
            result = None
            deadline = time.monotonic() + 1
            while result is None and time.monotonic() < deadline:
                result = controller.poll_attachment_preparation()
                if result is None:
                    time.sleep(0.01)
        self.assertEqual(result, {'ok': True, 'value': prepared})
        self.assertEqual(controller.attachment_paths, prepared['paths'])
        self.assertEqual(controller.attachment_details, prepared['details'])


if __name__ == '__main__':
    unittest.main()
