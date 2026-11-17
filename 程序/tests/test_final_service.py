"""无人值守自动定稿的纯决策回归（REQ-S07-05 自动入口遇忙等待、REQ-S07-31 同签名去重）。"""
import unittest


class AutomaticFinalizeDecisionTests(unittest.TestCase):
    def test_decision_distinguishes_repeat_wait_and_dispatch(self):
        """REQ-S07-31：同一签名只定稿一次（skip）；REQ-S07-05：制作批次忙时等待而不是抢跑。"""
        from domain.final_service import automatic_finalize_decision
        self.assertEqual(automatic_finalize_decision(('source', 'hash'), ('source', 'hash'), False)['action'], 'skip')
        self.assertEqual(automatic_finalize_decision(('source', 'hash'), ('source', 'hash'), True)['action'], 'skip')
        self.assertEqual(automatic_finalize_decision(('source', 'hash'), None, True)['action'], 'wait')
        decision = automatic_finalize_decision(('source', 'hash'), None, False)
        self.assertEqual(decision['action'], 'dispatch')
        self.assertEqual(decision['signature'], ('source', 'hash'))


if __name__ == '__main__':
    unittest.main()
