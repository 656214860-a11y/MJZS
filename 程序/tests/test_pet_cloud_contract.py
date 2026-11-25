# -*- coding: utf-8 -*-
"""pet_cloud 保留的无界面公共几何入口契约。"""
import unittest

from ui import pet_cloud


class PetCloudContractTests(unittest.TestCase):
    def test_unknown_shape_uses_cloud_defaults(self):
        unknown = 'unknown-shape'
        self.assertEqual(pet_cloud.shape_colors(unknown), pet_cloud.shape_colors(pet_cloud.SHAPE_CLOUD))
        self.assertEqual(pet_cloud.shape_width(unknown), pet_cloud.shape_width(pet_cloud.SHAPE_CLOUD))
        self.assertEqual(pet_cloud.shape_min_body(unknown), pet_cloud.shape_min_body(pet_cloud.SHAPE_CLOUD))
        self.assertEqual(pet_cloud.shape_min_width(unknown), pet_cloud.shape_min_width(pet_cloud.SHAPE_CLOUD))

    def test_public_shape_geometry_remains_consistent(self):
        parts = pet_cloud.shape_parts(pet_cloud.SHAPE_PUFF, 200, 100)
        root = pet_cloud.shape_root(pet_cloud.SHAPE_PUFF, 200, 100)
        self.assertEqual(len(parts), 6)
        self.assertTrue(pet_cloud.inside_shape(pet_cloud.SHAPE_PUFF, 200, 100, 100, 50))
        self.assertEqual(root, (172.0, 86.0))

    def test_public_tail_and_drawing_helpers_are_reexported(self):
        self.assertEqual(pet_cloud.rounded_parts(0, 0, 10, 10, 2)[0], ('rect', 2.0, 0, 8.0, 10))
        self.assertEqual(pet_cloud.tail_points((0, 0), (2, 0), (1, 2), steps=1)[-1], (2.0, 0.0))
        self.assertEqual(pet_cloud.inflate(('rect', 1, 1, 2, 2), 1), ('rect', 0, 0, 3, 3))

    def test_popup_origin_follows_a_secondary_monitor_parent_center(self):
        self.assertEqual(pet_cloud.centered_popup_origin((2000, 500, 800, 600), (400, 300),
                                                          (1920, 0, 3840, 1080)), (2200, 650))

    def test_popup_origin_keeps_primary_monitor_center(self):
        self.assertEqual(pet_cloud.centered_popup_origin((100, 80, 800, 600), (400, 300),
                                                          (0, 0, 1920, 1080)), (300, 230))

    def test_popup_origin_defers_when_parent_has_not_laid_out(self):
        self.assertIsNone(pet_cloud.centered_popup_origin((0, 0, 1, 600), (400, 300), (0, 0, 1920, 1080)))

    def test_place_window_retries_after_50ms_when_parent_has_not_laid_out(self):
        class Parent:
            def __init__(self): self.retries = []
            def winfo_rootx(self): return 0
            def winfo_rooty(self): return 0
            def winfo_width(self): return 1
            def winfo_height(self): return 600
            def after(self, delay, callback): self.retries.append((delay, callback)); return 'retry-job'
        class Window:
            def winfo_width(self): return 400
            def winfo_height(self): return 300
        cloud = object.__new__(pet_cloud.Cloud)
        cloud.parent, cloud.win, cloud.errors = Parent(), Window(), []
        cloud._position_job, cloud._position_retries = None, 0
        self.assertIsNone(cloud._place_window())
        self.assertEqual(cloud._position_job, 'retry-job')
        self.assertEqual(cloud._position_retries, 1)
        self.assertEqual([delay for delay, _callback in cloud.parent.retries], [50])

    def test_place_window_stops_retrying_after_ten_unlaid_out_attempts(self):
        class Parent:
            def winfo_rootx(self): return 0
            def winfo_rooty(self): return 0
            def winfo_width(self): return 1
            def winfo_height(self): return 1
            def after(self, delay, callback): raise AssertionError('不应继续安排第 11 次重试')
        class Window:
            def winfo_width(self): return 400
            def winfo_height(self): return 300
        cloud = object.__new__(pet_cloud.Cloud)
        cloud.parent, cloud.win, cloud.errors = Parent(), Window(), []
        cloud._position_job, cloud._position_retries = None, pet_cloud.POSITION_RETRY_MAX
        self.assertIsNone(cloud._place_window())

    def test_place_window_uses_the_pet_anchor_instead_of_parent_center(self):
        class Parent:
            def winfo_rootx(self): return 2000
            def winfo_rooty(self): return 500
            def winfo_width(self): return 800
            def winfo_height(self): return 600
        class Window:
            def __init__(self): self.positions = []
            def geometry(self, value): self.positions.append(value)
        cloud = object.__new__(pet_cloud.Cloud)
        cloud.parent, cloud.win, cloud.errors = Parent(), Window(), []
        cloud._position_job, cloud._position_retries = None, 0
        cloud._origin = lambda: (2380, 410)
        self.assertEqual(cloud._place_window(), (2380, 410))
        self.assertEqual(cloud.win.positions, ['+2380+410'])

    def test_place_window_retries_when_the_pet_canvas_is_not_mapped(self):
        class Parent:
            def __init__(self): self.retries = []
            def winfo_rootx(self): return 1200
            def winfo_rooty(self): return 300
            def winfo_width(self): return 800
            def winfo_height(self): return 600
            def after(self, delay, callback): self.retries.append((delay, callback)); return 'retry-job'
        class Canvas:
            def winfo_width(self): return 64
            def winfo_height(self): return 64
            def winfo_rootx(self): return 0
            def winfo_rooty(self): return 0
            def winfo_ismapped(self): return False
        class Pet: canvas = Canvas()
        class Window: pass
        cloud = object.__new__(pet_cloud.Cloud)
        cloud.parent, cloud.pet, cloud.win, cloud.errors = Parent(), Pet(), Window(), []
        cloud._position_job, cloud._position_retries = None, 0
        self.assertIsNone(cloud._place_window())
        self.assertEqual(cloud._position_job, 'retry-job')
        self.assertEqual([delay for delay, _callback in cloud.parent.retries], [50])

    def test_close_cancels_pending_place_retry(self):
        class Parent:
            def __init__(self): self.cancelled = []
            def after_cancel(self, job): self.cancelled.append(job)
        cloud = object.__new__(pet_cloud.Cloud)
        cloud.parent, cloud._position_job = Parent(), 'place-retry'
        cloud.visible = False
        cloud.cancel_deferred_render = cloud._cancel_hold = cloud._cancel_fade = cloud._hint_stop = lambda: None
        cloud.trim = lambda: None
        cloud._hide_now = lambda: None
        cloud.close()
        self.assertEqual(cloud.parent.cancelled, ['place-retry'])
        self.assertIsNone(cloud._position_job)

    def test_popup_origin_clamps_an_oversized_popup_to_the_work_area(self):
        self.assertEqual(pet_cloud.centered_popup_origin((100, 100, 200, 100), (2400, 1200),
                                                          (0, 0, 1920, 1080)), (0, 0))

    def test_propose_remembers_the_command_stage(self):
        """SANHU-FIX-2 S-03：三虎问的那件事带着阶段——空回车派发时照它路由。"""
        cloud = object.__new__(pet_cloud.Cloud)
        cloud.errors = []
        self.assertEqual(cloud.propose('执行选中', stage='video'), '执行选中')
        self.assertEqual(cloud.choice_stage, 'video')
        cloud.propose('')
        self.assertIsNone(cloud.choice_stage, '只是通知的问句把记下的阶段一并清掉')

    def test_dispatch_hands_the_stage_to_a_sink_that_knows_it(self):
        """S-03：agent.dispatch 签名认 stage 就传过去；没记阶段的句子照常不带。"""
        seen = []

        class Agent:
            def dispatch(self, text, at=None, confirmed=False, stage=None):
                seen.append((text, confirmed, stage))
                return {'plan': {'stage': stage}, 'decision': {'run': True}}

        class Pet:
            agent = Agent()

        cloud = object.__new__(pet_cloud.Cloud)
        cloud.pet, cloud.errors = Pet(), []
        cloud.dispatch('执行选中', stage='video')
        self.assertEqual(seen, [('执行选中', True, 'video')])
        cloud.dispatch('手打一句')
        self.assertEqual(seen[-1], ('手打一句', True, None))

    def test_dispatch_to_a_sink_without_the_parameter_still_works(self):
        """S-03：stage 是新参数——老签名（老接口、假宠物）不认它，照旧只吃一句话。"""
        seen = []

        class Agent:
            def dispatch(self, text):
                seen.append(text)
                return {'plan': {}, 'decision': {}}

        class Pet:
            agent = Agent()

        cloud = object.__new__(pet_cloud.Cloud)
        cloud.pet, cloud.errors = Pet(), []
        self.assertIsInstance(cloud.dispatch('执行选中', stage='video'), dict)
        self.assertEqual(seen, ['执行选中'])


if __name__ == '__main__':
    unittest.main()
