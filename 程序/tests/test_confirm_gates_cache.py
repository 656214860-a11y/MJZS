"""确认门禁的正式 JSON 读取必须复用缓存。"""
import tempfile
import unittest

import confirm_gates
import stage_layout


class ConfirmationCacheTests(unittest.TestCase):
    def test_atomic_confirmation_updates_invalidate_cached_read(self):
        with tempfile.TemporaryDirectory() as project:
            stage_layout.ensure(project)
            confirm_gates.record(project, 'anchor:CHAR_001', '候选一')
            self.assertEqual(
                confirm_gates.confirmations(project)['anchor:CHAR_001']['choice'], '候选一')
            confirm_gates.record(project, 'anchor:CHAR_001', '候选二')
            self.assertEqual(
                confirm_gates.confirmations(project)['anchor:CHAR_001']['choice'], '候选二')


if __name__ == '__main__':
    unittest.main()
