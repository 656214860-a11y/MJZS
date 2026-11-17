"""云朵定位重试登记（R1983 J6）：三个字段只由 CloudPlaceMixin 写，计时 Mixin 经 _take_position_job 取消。"""
from __future__ import annotations

import unittest

from ui import pet_cloud


class _Parent:
    def __init__(self):
        self.queued, self.cancelled = [], []

    def after(self, delay, callback):
        self.queued.append((delay, callback))
        return 'job-%d' % len(self.queued)

    def after_cancel(self, job):
        self.cancelled.append(job)

    def winfo_exists(self):
        return True


def _cloud():
    cloud = object.__new__(pet_cloud.Cloud)
    cloud.parent, cloud.errors = _Parent(), []
    cloud._reset_position_state()
    return cloud


class PositionStateTests(unittest.TestCase):
    def test_reset_state(self):
        cloud = _cloud()
        self.assertEqual((cloud._position_job, cloud._position_callback, cloud._position_retries), (None, None, 0))

    def test_arm_registers_once_and_counts(self):
        cloud = _cloud()
        cloud._arm_position_retry()
        cloud._arm_position_retry()
        self.assertEqual(cloud._position_job, 'job-1')
        self.assertIsNotNone(cloud._position_callback)
        self.assertEqual((cloud._position_retries, len(cloud.parent.queued)), (1, 1))

    def test_arm_stops_at_the_retry_cap(self):
        cloud = _cloud()
        cloud._position_retries = pet_cloud.POSITION_RETRY_MAX
        cloud._arm_position_retry()
        self.assertIsNone(cloud._position_job)

    def test_take_returns_job_and_clears_pair(self):
        cloud = _cloud()
        cloud._arm_position_retry()
        self.assertEqual(cloud._take_position_job(), 'job-1')
        self.assertEqual((cloud._position_job, cloud._position_callback), (None, None))
        self.assertIsNone(cloud._take_position_job())

    def test_cancel_goes_through_the_owner_and_cancels_the_handle(self):
        cloud = _cloud()
        cloud._arm_position_retry()
        cloud._cancel_position()
        self.assertEqual(cloud.parent.cancelled, ['job-1'])
        self.assertIsNone(cloud._position_job)

    def test_fired_ticket_clears_registration_then_places(self):
        cloud = _cloud()
        placed = []
        cloud._place_window = lambda: placed.append(1) or 'placed'
        cloud._arm_position_retry()
        _delay, retry = cloud.parent.queued[0]
        self.assertEqual(retry(), 'placed')
        self.assertEqual((cloud._position_job, cloud._position_callback, placed), (None, None, [1]))

    def test_stale_ticket_does_nothing(self):
        cloud = _cloud()
        cloud._place_window = lambda: self.fail('不该定位')
        cloud._arm_position_retry()
        _delay, retry = cloud.parent.queued[0]
        cloud._take_position_job()
        self.assertIsNone(retry())


if __name__ == '__main__':
    unittest.main()
