"""桌面换页决策与 after 计时器登记表（R1983 J4）：从 Desktop 切出后行为不变。"""
from __future__ import annotations

import unittest

import page_navigation_controller as nav

PAGE = {'script_structure': 1, 'assets': 4, 'keyframe': 7, 'previs': 8, 'video': 9, 'audio': 10}


class _Owner:
    pass


class CancelJobsTests(unittest.TestCase):
    def test_every_registered_job_is_cancelled_and_cleared(self):
        owner = _Owner()
        names = nav.NAV_TIMER_JOBS + nav.STARTUP_TIMER_JOBS
        for position, name in enumerate(names):
            setattr(owner, name, 'after#%d' % position)
        cancelled = []
        nav.cancel_jobs(owner, names, cancelled.append, ValueError)
        self.assertEqual(cancelled, ['after#%d' % position for position in range(len(names))])
        self.assertTrue(all(getattr(owner, name) is None for name in names))

    def test_missing_or_empty_jobs_are_skipped_but_attribute_is_set(self):
        owner = _Owner()
        owner._navigation_job = None
        cancelled = []
        nav.cancel_jobs(owner, ('_navigation_job', '_never_set'), cancelled.append, ValueError)
        self.assertEqual(cancelled, [])
        self.assertIsNone(owner._never_set)

    def test_tolerated_error_does_not_stop_the_rest(self):
        owner = _Owner()
        owner.a, owner.b = 'x', 'y'
        seen = []

        def cancel(job):
            seen.append(job)
            if job == 'x':
                raise ValueError('已失效')
        nav.cancel_jobs(owner, ('a', 'b'), cancel, ValueError)
        self.assertEqual(seen, ['x', 'y'])
        self.assertIsNone(owner.a)

    def test_untolerated_error_propagates(self):
        owner = _Owner()
        owner.a = 'x'

        def cancel(job):
            raise RuntimeError('别的错')
        with self.assertRaises(RuntimeError):
            nav.cancel_jobs(owner, ('a',), cancel, ValueError)

    def test_lifecycles_cancel_only_what_exists(self):
        class Lifecycle:
            def __init__(self):
                self.cancelled = 0

            def cancel(self):
                self.cancelled += 1
        owner = _Owner()
        owner.background_tasks = Lifecycle()
        owner.auto_previs_tasks = Lifecycle()
        owner.auto_edit_tasks = None
        nav.cancel_lifecycles(owner)
        self.assertEqual((owner.background_tasks.cancelled, owner.auto_previs_tasks.cancelled), (1, 1))


class VideoModeTests(unittest.TestCase):
    def test_sidebar_asks_to_choose_until_a_mode_was_picked(self):
        self.assertEqual(nav.sidebar_video_mode(9, PAGE, False), 'choose')
        self.assertIsNone(nav.sidebar_video_mode(9, PAGE, True))
        self.assertIsNone(nav.sidebar_video_mode(4, PAGE, False))

    def test_next_video_mode(self):
        self.assertEqual(nav.next_video_mode('choose', True, 'cloud'), (None, False, False))
        self.assertEqual(nav.next_video_mode('local', False, 'cloud'), ('local', True, True))
        self.assertEqual(nav.next_video_mode('local', False, 'local'), ('local', True, False))
        self.assertEqual(nav.next_video_mode(None, True, 'cloud'), ('cloud', True, False))
        self.assertEqual(nav.next_video_mode(None, False, 'cloud'), (None, False, False))
        self.assertEqual(nav.next_video_mode(None, True, None), (None, True, False))

    def test_choosing_video_until_mode_is_local_or_cloud(self):
        self.assertTrue(nav.choosing_video(9, PAGE, None))
        self.assertFalse(nav.choosing_video(9, PAGE, 'cloud'))
        self.assertFalse(nav.choosing_video(4, PAGE, None))


class GateTests(unittest.TestCase):
    def test_adopted_storyboard_gate_is_lazy_and_only_for_downstream_pages(self):
        calls = []

        def adopted(value):
            def read():
                calls.append(value)
                return value
            return read
        self.assertTrue(nav.needs_adopted_storyboard(7, PAGE, False, adopted([])))
        self.assertTrue(nav.needs_adopted_storyboard(9, PAGE, False, adopted([])))
        self.assertFalse(nav.needs_adopted_storyboard(9, PAGE, True, adopted([])))
        self.assertFalse(nav.needs_adopted_storyboard(7, PAGE, False, adopted(['a'])))
        self.assertFalse(nav.needs_adopted_storyboard(7, PAGE, False, adopted(None)))
        calls.clear()
        self.assertFalse(nav.needs_adopted_storyboard(4, PAGE, False, adopted([])))
        self.assertEqual(calls, [])

    def test_source_selector_range_and_subroutes(self):
        self.assertTrue(nav.needs_source_selector(4, PAGE, False, False))
        self.assertTrue(nav.needs_source_selector(10, PAGE, False, False))
        self.assertFalse(nav.needs_source_selector(11, PAGE, False, False))
        self.assertFalse(nav.needs_source_selector(3, PAGE, False, False))
        self.assertFalse(nav.needs_source_selector(9, PAGE, True, False))
        self.assertFalse(nav.needs_source_selector(4, PAGE, False, True))
        self.assertTrue(nav.needs_source_selector(5, PAGE, False, True))


class PageCacheTests(unittest.TestCase):
    def stale(self, cache, index, **kwargs):
        options = dict(root='P', rebuild=False, alive=lambda entry: True, signature=None)
        options.update(kwargs)
        return nav.stale_cache_keys(cache, index, PAGE, **options)

    def test_project_change_and_dead_holder_drop_the_entry(self):
        cache = {1: {'root': 'P'}, 2: {'root': 'OTHER'}, 3: {'root': 'P', 'dead': True}}
        self.assertEqual(self.stale(cache, 5, alive=lambda entry: not entry.get('dead')), [2, 3])

    def test_target_page_is_rebuilt_only_when_asked(self):
        cache = {2: {'root': 'P'}}
        self.assertEqual(self.stale(cache, 2), [])  # 从侧栏点回来：命中缓存
        self.assertEqual(self.stale(cache, 2, rebuild=True), [2])

    def test_script_structure_signature_only_checked_when_needed(self):
        asked = []

        def signature(root):
            asked.append(root)
            return 'new'
        cache = {1: {'root': 'P', 'signature': 'old'}}
        self.assertEqual(self.stale(cache, 1, signature=signature), [1])
        self.assertEqual(asked, ['P'])
        cache = {1: {'root': 'P', 'signature': 'new'}}
        self.assertEqual(self.stale(cache, 1, signature=signature), [])
        asked.clear()
        self.assertEqual(self.stale(cache, 4, signature=signature), [])
        self.assertEqual(asked, [])

    def test_cache_entry_keeps_note_only_when_it_is_not_the_project_path(self):
        self.assertEqual(nav.cache_entry('h', 'P', 'btn', 'D:/p', 'D:/p')['note'], '')
        self.assertEqual(nav.cache_entry('h', 'P', 'btn', '已加载', 'D:/p'),
                         {'holder': 'h', 'root': 'P', 'stage_button': 'btn', 'note': '已加载'})


if __name__ == '__main__':
    unittest.main()
