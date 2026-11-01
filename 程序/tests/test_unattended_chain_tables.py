"""无人值守链路三张对照表只有一份定义（R2178 J15），且彼此自洽。"""
import unittest

import desktop_auto_flows
import desktop_auto_state
import desktop_pet_bridge


class UnattendedChainTableTests(unittest.TestCase):
    def test_consumers_share_the_single_definition(self):
        self.assertIs(desktop_pet_bridge.PET_STAGE_POLL, desktop_auto_state.PET_STAGE_POLL)
        self.assertIs(desktop_pet_bridge.UNATTENDED_SWITCH, desktop_auto_state.UNATTENDED_SWITCH)
        self.assertIs(desktop_auto_flows.UNATTENDED_NEXT, desktop_auto_state.UNATTENDED_NEXT)

    def test_tables_name_the_same_poll_steps(self):
        polls = set(desktop_auto_state.PET_STAGE_POLL.values())
        self.assertEqual(set(desktop_auto_state.UNATTENDED_SWITCH), polls)
        for source, downstream in desktop_auto_state.UNATTENDED_NEXT.items():
            self.assertLessEqual({source, *downstream}, polls)

    def test_downstream_table_is_acyclic(self):
        table = desktop_auto_state.UNATTENDED_NEXT

        def reach(name, seen):
            for nxt in table.get(name, ()):
                self.assertNotIn(nxt, seen, '下游表出现环：%s' % nxt)
                reach(nxt, seen | {nxt})
        for name in table:
            reach(name, {name})


if __name__ == '__main__':
    unittest.main()
