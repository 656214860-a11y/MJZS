"""确认门禁的正式 JSON 读取必须复用缓存。"""
import tempfile
import unittest

from domain import confirm_gates
import stage_layout
from stage_execution_service import record_stage_confirmation


class ConfirmationCacheTests(unittest.TestCase):
    def test_atomic_confirmation_updates_invalidate_cached_read(self):
        with tempfile.TemporaryDirectory() as project:
            stage_layout.ensure(project)
            record_stage_confirmation(project, 'anchor:CHAR_001', '候选一')
            self.assertEqual(
                confirm_gates.confirmations(project)['anchor:CHAR_001']['choice'], '候选一')
            record_stage_confirmation(project, 'anchor:CHAR_001', '候选二')
            self.assertEqual(
                confirm_gates.confirmations(project)['anchor:CHAR_001']['choice'], '候选二')


if __name__ == '__main__':
    unittest.main()
