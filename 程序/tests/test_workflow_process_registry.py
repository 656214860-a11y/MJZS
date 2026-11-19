# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch


class WorkflowProcessCapacityTests(unittest.TestCase):
    def test_legacy_process_registration_does_not_block_slot_checks(self):
        from types import SimpleNamespace
        from infra import workflow_process_registry as registry

        process = SimpleNamespace()
        registry.register_process('legacy-project', process)
        self.addCleanup(registry.forget_process, 'legacy-project', process)

        self.assertIsNotNone(registry.reserve_process_slot('new-project', 'script'))
        self.assertEqual(registry.processes('legacy-project'), [process])

    def test_exited_process_releases_slot_for_queued_request(self):
        from unittest.mock import Mock
        from infra import workflow_process_registry as registry
        slot = registry.reserve_process_slot('old-project', 'script')
        process = Mock(workflow_process_slot=slot)
        process.poll.return_value = None
        registry.register_process('old-project', process)
        self.addCleanup(registry.forget_process, 'old-project', process)
        waiting = registry.request_process_slot('new-project', 'script')
        self.assertEqual(waiting['state'], 'queued')
        process.poll.return_value = 0
        self.assertEqual(registry.claim_process_slot(waiting['ticket'])['state'], 'granted')
        self.assertEqual(registry.processes('old-project'), [])

    def tearDown(self):
        from infra import workflow_process_registry as registry
        for items in list(registry._slots.values()):
            for token in list(items):
                registry.release_process_slot(token)
        registry._queued[:] = []

    def test_stage_limit_rejects_second_request_and_release_allows_retry(self):
        from infra import workflow_process_registry as registry
        first = registry.reserve_process_slot('project-a', 'script', stage_name='剧本准备')
        with self.assertRaisesRegex(ValueError, '剧本准备已有 1 个模型请求'):
            registry.reserve_process_slot('project-b', 'script', stage_name='剧本准备')
        registry.release_process_slot(first)
        second = registry.reserve_process_slot('project-b', 'script', stage_name='剧本准备')
        self.assertIsNotNone(second)

    def test_chinese_stage_name_uses_same_stage_limit(self):
        from infra import workflow_process_registry as registry
        registry.reserve_process_slot('project-a', 'script', stage_name='剧本准备')
        with self.assertRaisesRegex(ValueError, '剧本准备已有 1 个模型请求'):
            registry.reserve_process_slot('project-b', 'script', stage_name='剧本准备')

    def test_global_limit_blocks_other_stage(self):
        from infra import workflow_process_registry as registry
        registry.reserve_process_slot('project-a', 'script', global_limit=1)
        with self.assertRaisesRegex(ValueError, '全局并发上限 1'):
            registry.reserve_process_slot('project-b', 'keyframe', global_limit=1)

    def test_queued_request_claims_slot_after_running_request_releases(self):
        from infra import workflow_process_registry as registry
        running = registry.reserve_process_slot('project-a', 'script', stage_limit=1)
        waiting = registry.request_process_slot('project-b', 'script', stage_limit=1,
                                                stage_name='剧本准备')
        self.assertEqual(waiting['state'], 'queued')
        self.assertEqual(registry.claim_process_slot(waiting['ticket'])['state'], 'queued')
        registry.release_process_slot(running)
        claimed = registry.claim_process_slot(waiting['ticket'])
        self.assertEqual(claimed['state'], 'granted')
        registry.release_process_slot(claimed['slot'])

    def test_cancelled_project_request_cannot_claim_a_slot(self):
        from infra import workflow_process_registry as registry
        registry.reserve_process_slot('project-a', 'script', stage_limit=1)
        waiting = registry.request_process_slot('project-b', 'script', stage_limit=1)
        self.assertEqual(registry.cancel_project_slot_requests('project-b'), 1)
        self.assertEqual(registry.claim_process_slot(waiting['ticket'])['state'], 'cancelled')

    def test_stage_slot_release_and_cancel_are_registry_adapters(self):
        import workflow_engines as engines
        with patch.object(engines, 'release_process_slot') as release:
            engines.release_stage_process_slot('slot-1')
        release.assert_called_once_with('slot-1')
        with patch.object(engines, 'cancel_project_slot_requests', return_value=2) as cancel:
            self.assertEqual(engines.cancel_stage_slot_requests('project-a'), 2)
        cancel.assert_called_once_with('project-a')


if __name__ == '__main__':
    unittest.main(verbosity=2)
