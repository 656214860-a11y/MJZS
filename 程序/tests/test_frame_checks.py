# -*- coding: utf-8 -*-
"""首帧三入口勾选状态自检：勾选跟随首帧状态、手动选择优先、弹窗回写。运行：python test_frame_checks.py"""
import os, sys, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, PROGRAM)
os.chdir(PROGRAM)

from contract.frame_checks import FrameChecks

ROWS = [('SH001', True, False), ('SH002', False, False), ('SH003', False, True)]


class DictCompatTests(unittest.TestCase):
    def test_get_default(self):
        checks = FrameChecks()
        self.assertFalse(checks.get('SH001', False))
        self.assertIsNone(checks.get('SH001'))

    def test_setitem_is_a_manual_choice(self):
        checks = FrameChecks()
        checks['SH001'] = True
        self.assertTrue(checks.get('SH001'))
        self.assertIn('SH001', checks.manual)

    def test_setdefault_is_not_a_manual_choice(self):
        checks = FrameChecks()
        self.assertFalse(checks.setdefault('SH001', False))
        self.assertNotIn('SH001', checks.manual)

    def test_len_and_contains(self):
        checks = FrameChecks({'SH001': True})
        self.assertEqual(len(checks), 1)
        self.assertIn('SH001', checks)
        self.assertNotIn('SH002', checks)

    def test_truthy_values_are_coerced(self):
        self.assertIs(FrameChecks({'SH001': 1}).get('SH001'), True)

    def test_reads_like_the_old_dict(self):
        checks = FrameChecks({'SH001': True, 'SH002': False})
        self.assertEqual([sid for sid in ('SH001', 'SH002') if checks.get(sid, False)], ['SH001'])


class SyncTests(unittest.TestCase):
    def test_finished_shots_are_not_checked_pending_ones_are(self):
        checks = FrameChecks()
        checks.sync(ROWS)
        self.assertFalse(checks.get('SH001'))
        self.assertTrue(checks.get('SH002'))
        self.assertFalse(checks.get('SH003'))

    def test_reports_what_changed(self):
        checks = FrameChecks()
        self.assertEqual(checks.sync(ROWS), (['SH002'], []))

    def test_a_frame_landing_unchecks_the_shot(self):
        checks = FrameChecks()
        checks.sync(ROWS)
        _, unchecked = checks.sync([('SH001', True, False), ('SH002', True, False), ('SH003', False, True)])
        self.assertEqual(unchecked, ['SH002'])

    def test_new_shot_is_checked_by_default(self):
        self.assertEqual(FrameChecks().sync([('SH009', False, False)])[0], ['SH009'])

    def test_manual_cancel_survives_a_refresh(self):
        checks = FrameChecks()
        checks.sync(ROWS)
        checks.toggle('SH002')
        checks.sync(ROWS)
        self.assertFalse(checks.get('SH002'))

    def test_manual_pick_survives_a_refresh(self):
        checks = FrameChecks()
        checks.sync(ROWS)
        checks.toggle('SH002')
        checks.toggle('SH002')
        checks.sync(ROWS)
        self.assertTrue(checks.get('SH002'))

    def test_deleted_shot_is_never_checked(self):
        checks = FrameChecks({'SH003': True})
        checks.sync(ROWS)
        self.assertFalse(checks.get('SH003'))

    def test_discarded_frame_gets_checked_again(self):
        checks = FrameChecks()
        checks.sync(ROWS)
        checks.sync([('SH002', True, False)])
        self.assertFalse(checks.get('SH002'))
        checks.sync([('SH002', False, True)])
        self.assertEqual(checks.sync([('SH002', False, False)])[0], ['SH002'])

    def test_sync_is_idempotent(self):
        checks = FrameChecks()
        checks.sync(ROWS)
        self.assertEqual(checks.sync(ROWS), ([], []))


class KeepTests(unittest.TestCase):
    def test_only_the_submitted_batch_stays_checked(self):
        checks = FrameChecks()
        checks.sync([('SH001', False, False), ('SH002', False, False), ('SH003', False, False)])
        self.assertEqual(checks.keep(['SH002']), ['SH002'])
        self.assertEqual(checks.checked(['SH001', 'SH002', 'SH003']), ['SH002'])

    def test_write_back_counts_as_a_manual_choice(self):
        checks = FrameChecks()
        checks.keep(['SH002'])
        checks.sync([('SH002', False, False)])
        self.assertTrue(checks.get('SH002'))

    def test_keep_is_idempotent(self):
        checks = FrameChecks()
        self.assertEqual(checks.keep(['SH002']), checks.keep(['SH002']))

    def test_empty_batch_clears_everything(self):
        checks = FrameChecks({'SH001': True, 'SH002': True})
        self.assertEqual(checks.keep([]), [])
        self.assertEqual(checks.checked(['SH001', 'SH002']), [])


class CheckedTests(unittest.TestCase):
    def test_keeps_the_given_order(self):
        checks = FrameChecks({'SH003': True, 'SH001': True})
        self.assertEqual(checks.checked(['SH001', 'SH002', 'SH003']), ['SH001', 'SH003'])

    def test_toggle_flips_twice(self):
        checks = FrameChecks()
        self.assertTrue(checks.toggle('SH001'))
        self.assertFalse(checks.toggle('SH001'))

    def test_toggle_sets_a_manual_mark(self):
        checks = FrameChecks()
        checks.toggle('SH001')
        self.assertIn('SH001', checks.manual)



class WiringTests(unittest.TestCase):
    """模块再好，接不上页面就等于没做：确认两处接线都在。"""

    def test_page_and_dialog_share_one_state(self):
        from tests.architecture._scan import desktop_text  # R1504：首帧管理页已迁到 Mixin 模块
        desktop = desktop_text()
        self.assertIn('frame_checks.FrameChecks()', desktop)
        self.assertIn('checked.sync(', desktop)

    def test_dialog_publishes_the_submitted_batch(self):
        dialog = (Path(PROGRAM) / 'ui' / 'keyframe_comfy.py').read_text(encoding='utf-8')
        self.assertIn("publish(checked['shots'])", dialog)
        self.assertIn('frame_checks_apply', dialog)


if __name__ == '__main__':
    unittest.main(verbosity=1)
