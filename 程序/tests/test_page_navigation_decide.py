"""J20：换页决策一次吃状态快照、吐完整计划，Tk 侧只按 route 摆控件。"""
import unittest

from orchestrator import page_navigation_controller as nav

PAGE = {'script': 0, 'script_structure': 1, 'assets': 4, 'keyframe': 7, 'previs': 8, 'video': 9,
        'audio': 10, 'edit': 11, 'delivery': 12}
FREE = (100, 101)
CACHED = (1, 4)


def snap(**changes):
    base = {'lock_reason': '', 'has_root': True, 'video_mode': None, 'adopted': lambda: ['x'],
            'asset_detail': None, 'asset_roster': False, 'loading_project': False}
    base.update(changes)
    return base


def decide(index, **changes):
    return nav.decide(index, PAGE, snap(**changes), free_pages=FREE, cached_pages=CACHED)


class DecideTests(unittest.TestCase):
    def test_lock_wins_over_everything(self):
        plan = decide(PAGE['video'], lock_reason='未登录', has_root=False)
        self.assertEqual((plan.route, plan.reason), ('locked', '未登录'))

    def test_free_pages_and_home_do_not_need_a_project(self):
        self.assertEqual(decide(100, has_root=False).route, 'free')
        self.assertEqual(decide(PAGE['edit'], has_root=False).route, 'home')

    def test_adopted_gate_blocks_only_gated_pages_and_reads_prefs_lazily(self):
        calls = []
        def adopted():
            calls.append(1)
            return []
        self.assertEqual(decide(PAGE['keyframe'], adopted=adopted).route, 'blocked')
        self.assertEqual(decide(PAGE['video'], video_mode='cloud', adopted=adopted).route, 'blocked')
        calls.clear()
        self.assertEqual(decide(PAGE['script'], adopted=adopted).route, 'builder')
        self.assertEqual(calls, [])
        self.assertEqual(decide(PAGE['video'], adopted=adopted).route, 'builder')   # 选方式那一屏不拦
        self.assertTrue(decide(PAGE['video'], adopted=adopted).choosing)

    def test_selector_and_align_flags(self):
        self.assertTrue(decide(PAGE['previs']).selector)
        self.assertFalse(decide(PAGE['script']).selector)
        self.assertFalse(decide(PAGE['assets'], asset_roster=True).selector)
        self.assertTrue(decide(PAGE['edit']).align)
        self.assertTrue(decide(PAGE['delivery']).align)
        self.assertFalse(decide(PAGE['audio']).align)

    def test_routes_for_script_shell_and_asset_subroutes(self):
        self.assertEqual(decide(PAGE['script'], loading_project=True).route, 'startup_shell')
        self.assertEqual(decide(PAGE['assets'], asset_roster=True).route, 'roster')
        self.assertEqual(decide(PAGE['assets'], asset_detail='A1').route, 'detail')
        self.assertEqual(decide(PAGE['assets']).route, 'builder')

    def test_cached_only_for_builder_route_of_cached_pages(self):
        self.assertTrue(decide(PAGE['script_structure']).cached)
        self.assertTrue(decide(PAGE['assets']).cached)
        self.assertFalse(decide(PAGE['assets'], asset_roster=True).cached)
        self.assertFalse(decide(PAGE['audio']).cached)


if __name__ == '__main__':
    unittest.main()
