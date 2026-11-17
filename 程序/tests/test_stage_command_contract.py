"""K4：三虎的自动和手动阶段命令必须统一经 L3 入口。"""
import json
import tempfile
import unittest
from pathlib import Path

import desktop
import stage_config
from orchestrator import stage_handler_registry
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
            stage_config.put_production_locks(project, {'aspect_ratio': '9:16'})
            auto = self._Host()
            auto.root = project
            called = []
            error = stage_handler_registry.start(
                auto, 'script', 'auto', lambda stage, trigger: called.append((stage, trigger)))
            self.assertIn('发送框内写明制作锁', error)
            self.assertIn('交付形态', error)
            self.assertEqual(called, [])
            self.assertEqual(auto.pet.events, [('stage.failed', {'stage': 'script', 'error': error})])

            manual = self._Host()
            manual.root = project
            result = stage_handler_registry.start(manual, 'script', 'manual',
                                                  lambda stage, trigger: 'manual-started')
            self.assertEqual(result, 'manual-started')
            self.assertEqual(manual.pet.events, [])


class AutoSkillGateTests(unittest.TestCase):
    """R2905：自动档下未勾选 SKILL 的阶段跳过并提示，不进 fallback、不发失败事件。"""

    class _Machine:
        def __init__(self):
            self.skipped = []
            self.saved = 0

        def skip(self, stage, reason=''):
            self.skipped.append((stage, reason))

        def save(self):
            self.saved += 1

    class _Auto:
        def __init__(self):
            self.done_calls = []

        def done(self, stage, ok=True, reason=''):
            self.done_calls.append((stage, ok))

    class _Pet:
        def __init__(self):
            self.machine = AutoSkillGateTests._Machine()
            self.auto = AutoSkillGateTests._Auto()
            self.broadcasts = []
            self.events = []

        def broadcast(self, text, **kw):
            self.broadcasts.append(text)
            return text

        def _emit(self, kind, **payload):
            self.events.append((kind, payload))

    def _host(self, td, skills):
        proj = Path(td) / 'p'
        proj.mkdir(parents=True, exist_ok=True)
        (proj / 'skill_config.json').write_text(json.dumps(
            {'assets': {'model': 'auto', 'skills': skills}}, ensure_ascii=False),
            encoding='utf-8')
        pet = self._Pet()
        host = type('Host', (), {})()
        host.root = proj
        host.pet = pet
        return host, pet

    def test_auto_skips_a_stage_with_no_checked_skills(self):
        with tempfile.TemporaryDirectory() as td:
            host, pet = self._host(td, [])
            calls = []
            text = stage_handler_registry.start(
                host, 'assets', 'auto',
                fallback=lambda stage, trigger: calls.append((stage, trigger)) or 'ran')
            self.assertIn('跳过', text)
            self.assertEqual(calls, [], '未勾选的阶段不得进入自动派发')
            self.assertEqual(pet.machine.skipped, [('assets', '未勾选 SKILL')])
            self.assertEqual(pet.machine.saved, 1)
            self.assertEqual(pet.auto.done_calls, [('assets', True)])
            self.assertTrue(any('跳过' in line for line in pet.broadcasts))
            self.assertFalse(any(kind == 'stage.failed' for kind, _ in pet.events))

    def test_auto_runs_normally_when_skills_are_checked(self):
        import skill_registry
        name = skill_registry.default_registry().getByStage('assets')[0].name
        with tempfile.TemporaryDirectory() as td:
            host, pet = self._host(td, [name])
            calls = []
            result = stage_handler_registry.start(
                host, 'assets', 'auto',
                fallback=lambda stage, trigger: calls.append((stage, trigger)) or 'ran')
            self.assertEqual(result, 'ran')
            self.assertEqual(calls, [('assets', 'auto')])
            self.assertEqual(pet.machine.skipped, [])
            self.assertEqual(pet.auto.done_calls, [])

    def test_manual_trigger_is_not_gated_by_the_skill_selection(self):
        with tempfile.TemporaryDirectory() as td:
            host, pet = self._host(td, [])
            calls = []
            result = stage_handler_registry.start(
                host, 'assets', 'manual',
                fallback=lambda stage, trigger: calls.append((stage, trigger)) or 'ran')
            self.assertEqual(result, 'ran')
            self.assertEqual(calls, [('assets', 'manual')])
            self.assertEqual(pet.machine.skipped, [])

    def test_non_stage_commands_are_never_gated(self):
        with tempfile.TemporaryDirectory() as td:
            host, pet = self._host(td, [])
            # pet_test 不在制作阶段表里：门禁不设，直接走到原有的会话启动路径
            # （此处宿主缺 program 字段，真实派发会抛 RuntimeError——能抛出就说明没被门禁拦）。
            with self.assertRaises(RuntimeError):
                stage_handler_registry.start(host, 'pet_test', 'auto', text='x')
            self.assertEqual(pet.machine.skipped, [])
