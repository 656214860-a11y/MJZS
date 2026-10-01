"""K4：三虎的自动和手动阶段命令必须统一经 L3 入口。"""
import tempfile
import unittest

import desktop
import stage_config
import stage_handler_registry
import workflow_settings


class StageCommandContractTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.original = stage_handler_registry.start

        def record(host, stage, trigger='auto', fallback=None):
            self.calls.append((host, stage, trigger, fallback))
            return stage + ':' + trigger

        stage_handler_registry.start = record
        self.addCleanup(setattr, stage_handler_registry, 'start', self.original)
        self.host = object.__new__(desktop.Desktop)

    def test_auto_pet_start_uses_the_l3_command(self):
        self.assertEqual(self.host.pet_start('assets'), 'assets:auto')
        self.assertEqual(len(self.calls), 1)
        host, stage, trigger, fallback = self.calls[0]
        self.assertIs(host, self.host)
        self.assertEqual((stage, trigger), ('assets', 'auto'))
        self.assertEqual(fallback.__self__, self.host)
        self.assertEqual(fallback.__func__, desktop.Desktop._start_unattended_stage)

    def test_manual_storyboard_uses_the_same_l3_command(self):
        self.assertEqual(self.host.pet_storyboard_batch(), 'storyboard:manual')
        self.assertEqual(self.calls, [(self.host, 'storyboard', 'manual', None)])

    def test_auto_storyboard_uses_the_same_l3_command(self):
        self.assertEqual(self.host.pet_storyboard_batch(trigger='auto'), 'storyboard:auto')
        self.assertEqual(self.calls, [(self.host, 'storyboard', 'auto', None)])


class StageCommandEventContractTests(unittest.TestCase):
    class _Pet:
        def __init__(self):
            self.events = []

        def _emit(self, event, **payload):
            self.events.append((event, payload))

    class _Host:
        def __init__(self):
            self.root = object()
            self.pet = StageCommandEventContractTests._Pet()

    def setUp(self):
        self.original_plan = stage_handler_registry.storyboard_work_plan
        stage_handler_registry.storyboard_work_plan = (
            lambda host: {'scripts': [], 'todo': [], 'adopted': []}
        )
        self.addCleanup(
            setattr,
            stage_handler_registry,
            'storyboard_work_plan',
            self.original_plan,
        )

    def test_auto_failure_emits_a_stage_event_but_manual_remains_a_command_result(self):
        auto_host = self._Host()
        self.assertEqual(
            stage_handler_registry.start(auto_host, 'storyboard', 'auto'),
            '未选择结构剧本，无法制作分镜',
        )
        self.assertEqual(auto_host.pet.events[0][0], 'stage.failed')
        self.assertEqual(auto_host.pet.events[0][1]['stage'], 'storyboard')

        manual_host = self._Host()
        self.assertEqual(stage_handler_registry.start(manual_host, 'storyboard', 'manual'), '')
        self.assertEqual(manual_host.pet.events, [])

    def test_missing_workflow_locks_block_only_unattended_script_start(self):
        with tempfile.TemporaryDirectory() as project:
            preset = workflow_settings.WORKFLOW_PRESETS['AIGC全流程']
            stage_config.put_workflow(project, {
                'name': 'AIGC全流程', 'skill_ref': preset['package'],
                'lock': {'AIGC全流程': {'aspect_ratio': '9:16'}},
            })
            auto = self._Host()
            auto.root = project
            called = []
            error = stage_handler_registry.start(
                auto, 'script', 'auto', lambda stage, trigger: called.append((stage, trigger)))
            self.assertIn('填写创作信息', error)
            self.assertIn('交付形态', error)
            self.assertEqual(called, [])
            self.assertEqual(auto.pet.events, [('stage.failed', {'stage': 'script', 'error': error})])

            manual = self._Host()
            manual.root = project
            result = stage_handler_registry.start(manual, 'script', 'manual',
                                                  lambda stage, trigger: 'manual-started')
            self.assertEqual(result, 'manual-started')
            self.assertEqual(manual.pet.events, [])
