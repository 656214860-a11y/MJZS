"""无人值守分镜采用轮询的纯决策回归。"""
import unittest


class AutomaticPollDecisionTests(unittest.TestCase):
    def test_decision_distinguishes_final_wait_repeat_skip_and_scan(self):
        from domain.storyboard_adoption_service import automatic_poll_decision
        self.assertEqual(automatic_poll_decision(('tree',), None, False, True)['action'], 'wait')
        self.assertEqual(automatic_poll_decision(('tree',), ('tree',), False, False)['action'], 'skip')
        self.assertEqual(automatic_poll_decision(('tree',), ('tree',), True, False)['action'], 'scan')
        self.assertEqual(automatic_poll_decision(('tree',), None, False, False)['action'], 'scan')


if __name__ == '__main__':
    unittest.main()
