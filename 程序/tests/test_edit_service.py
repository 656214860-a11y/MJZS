"""无人值守自动粗剪的纯决策回归。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from service_contract import SystemError


class EditingResultTests(unittest.TestCase):
    def test_write_results_classify_io_without_hiding_programming_errors(self):
        from edit_service import save_editing_checklist, save_automatic_assemble_marker
        calls = [(save_editing_checklist, (Path('project'), 'text')),
                 (save_automatic_assemble_marker, (Path('marker.json'), 'digest', 'master', 1))]
        for function, args in calls:
            with self.subTest(function=function.__name__):
                self.assertTrue(function(*args, publish=Mock()).ok)
                with self.assertLogs('edit_service', level='ERROR'):
                    result = function(*args, publish=Mock(side_effect=OSError('private detail')))
                self.assertIsInstance(result, SystemError)
                self.assertIsNone(result.data)
                self.assertNotIn('private detail', result.reason)
                with self.assertRaises(TypeError):
                    function(*args, publish=Mock(side_effect=TypeError('bug')))

    def test_l3_rejects_failed_writes(self):
        from stage_execution_service import save_stage_editing_checklist, save_automatic_assemble_marker
        for name, function, args in [
                ('save_editing_checklist', save_stage_editing_checklist, ('project', 'text')),
                ('save_automatic_assemble_marker', save_automatic_assemble_marker, ('project', 'digest', 'master', 1))]:
            with self.subTest(name=name), patch('edit_service.' + name, return_value=SystemError('保存失败')):
                with self.assertRaisesRegex(ValueError, '保存失败'):
                    function(*args)


class AutomaticAssembleDecisionTests(unittest.TestCase):
    """REQ-S12-12：同一批验收结果只拼一次（skip／complete），指纹未就绪则等待，重做后重新派发。"""

    def test_decision_distinguishes_repeat_wait_complete_and_dispatch(self):
        from edit_service import automatic_assemble_decision
        self.assertEqual(automatic_assemble_decision(('state',), 'digest', ('state',), {})['action'], 'skip')
        self.assertEqual(automatic_assemble_decision(('state',), None, None, {})['action'], 'wait')
        self.assertEqual(automatic_assemble_decision(('state',), 'digest', None, {'digest': 'digest'})['action'], 'complete')
        self.assertEqual(automatic_assemble_decision(('state',), 'digest', None, {'digest': 'old-digest'})['action'], 'dispatch')
        self.assertEqual(automatic_assemble_decision(('state',), 'digest', None, 'broken-marker')['action'], 'dispatch')
        self.assertEqual(automatic_assemble_decision(('state',), 'digest', None, {})['action'], 'dispatch')


class EditingChecklistPublicationTests(unittest.TestCase):
    """REQ-S12-16：剪辑优化清单由用户维护，可保存、可清空，位于 12后期剪辑/。"""

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
    """REQ-S12-12：自动粗剪完成标记写到 12后期剪辑/自动粗剪.json（同一指纹只拼一次）。"""

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
