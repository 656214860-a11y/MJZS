"""无 Tk 的剧本准备对话控制器回归。"""
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from idea_chat_controller import IdeaChatController


class IdeaChatControllerTests(unittest.TestCase):
    def test_attachment_injection_keeps_existing_visible_marker(self):
        controller = IdeaChatController()
        controller.replace_attachments(('D:/idea.md',))
        referenced = {'context': '[附件]\n创意内容', 'names': ('idea.md',)}
        with patch('idea_attachments.referenced', return_value=referenced):
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
             patch('idea_attachments.prepare', return_value=prepared):
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
