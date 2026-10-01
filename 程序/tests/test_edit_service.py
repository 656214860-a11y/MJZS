"""无人值守自动粗剪的纯决策回归。"""
import tempfile
import unittest
from pathlib import Path


class AutomaticAssembleDecisionTests(unittest.TestCase):
    def test_decision_distinguishes_repeat_wait_complete_and_dispatch(self):
        from edit_service import automatic_assemble_decision
        self.assertEqual(automatic_assemble_decision(('state',), 'digest', ('state',), {})['action'], 'skip')
        self.assertEqual(automatic_assemble_decision(('state',), None, None, {})['action'], 'wait')
        self.assertEqual(automatic_assemble_decision(('state',), 'digest', None, {'digest': 'digest'})['action'], 'complete')
        self.assertEqual(automatic_assemble_decision(('state',), 'digest', None, {'digest': 'old-digest'})['action'], 'dispatch')
        self.assertEqual(automatic_assemble_decision(('state',), 'digest', None, 'broken-marker')['action'], 'dispatch')
        self.assertEqual(automatic_assemble_decision(('state',), 'digest', None, {})['action'], 'dispatch')


class EditingChecklistPublicationTests(unittest.TestCase):
    def test_checklist_is_published_under_the_editing_stage(self):
        from edit_service import CHECKLIST_NAME
        from project_stages import editing
        from stage_execution_service import save_stage_editing_checklist
        with tempfile.TemporaryDirectory() as folder:
            target = save_stage_editing_checklist(folder, '□ 校对字幕')
            self.assertEqual(target, editing(Path(folder)) / CHECKLIST_NAME)
            self.assertEqual(target.read_text(encoding='utf-8'), '□ 校对字幕')

    def test_checklist_can_still_be_explicitly_cleared(self):
        from stage_execution_service import save_stage_editing_checklist
        with tempfile.TemporaryDirectory() as folder:
            target = save_stage_editing_checklist(folder, '')
            self.assertEqual(target.read_text(encoding='utf-8'), '')


class AutomaticAssembleMarkerPublicationTests(unittest.TestCase):
    def test_marker_is_published_under_the_editing_stage(self):
        from edit_service import AUTOMATIC_ASSEMBLE_MARKER_NAME
        from stage_execution_service import save_automatic_assemble_marker
        from project_stages import editing
        with tempfile.TemporaryDirectory() as folder:
            target = save_automatic_assemble_marker(folder, 'digest', 'MASTER.mp4', 123.0)
            self.assertEqual(target, editing(Path(folder)) / AUTOMATIC_ASSEMBLE_MARKER_NAME)
            self.assertEqual(__import__('json').loads(target.read_text(encoding='utf-8')),
                             {'digest': 'digest', 'master': 'MASTER.mp4', 'at': 123.0})


if __name__ == '__main__':
    unittest.main()
