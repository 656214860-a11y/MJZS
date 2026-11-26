"""K4：三虎的自动和手动阶段命令必须统一经 L3 入口。"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import desktop
import stage_config
import workflow_settings
from contract import pet_bus
from orchestrator import stage_handler_registry
from ui.desktop_pet_bridge import PetBridgeMixin
from ui.pet_ui import Pet
from ui.pet_ui_stages import PetStagesMixin, stage_run_action, skip_unchecked


class RegistryCallbackContractTests(unittest.TestCase):
    def test_registry_failure_uses_injected_publisher_and_preserves_original_error(self):
        host = Mock(root=None)
        publish = Mock(side_effect=[None, None, RuntimeError('事件处理异常')])
        with patch.object(stage_handler_registry, '_workflow_lock_error', return_value='制作锁缺失'):
            self.assertEqual(stage_handler_registry.start(
                host, 'storyboard', 'manual', run_action=publish), '制作锁缺失')
            publish.assert_called_once_with(host, 'storyboard', 'manual')
            self.assertEqual(stage_handler_registry.start(
                host, 'storyboard', 'auto', run_action=publish), '制作锁缺失')
        self.assertEqual(publish.call_count, 3)
        publish.assert_called_with(host, 'storyboard', 'auto', error='制作锁缺失')
        host.pet._emit.assert_not_called()

    def test_storyboard_input_failures_emit_once_per_registered_auto_run(self):
        bus = pet_bus.Bus()
        host = object.__new__(desktop.Desktop)
        host.root = Path('.')
        host._account_controller = Mock(stage_gate=Mock(return_value=''))
        host.pet = Mock(bus=bus, errors=[])
        host.pet._emit.side_effect = Pet._emit.__get__(host.pet, Pet)
        host.open_storyboard_skill = Mock()
        host.pet_report = Mock()
        view = Mock(desktop=host, errors=[])
        view.agent.level = 'auto'
        view.agent.approve.return_value = {'run': True}
        deliveries = []
        bus.subscribe('*', deliveries.append)
        with patch.object(stage_handler_registry, '_workflow_lock_error', return_value=''), \
                patch.object(stage_handler_registry.stage_flow, 'unchecked', return_value=False), \
                patch.object(stage_handler_registry, 'storyboard_work_plan',
                             side_effect=[{'scripts': []}, OSError('读取失败'), {'scripts': []}]):
            self.assertEqual(host.pet_storyboard_batch(), '')
            self.assertEqual(bus.current_run('storyboard'), 1)
            self.assertIn('读取失败', PetStagesMixin.start_stage(view, 'storyboard'))
            self.assertEqual(bus.current_run('storyboard'), 2)
            self.assertIn('未选择结构剧本', PetStagesMixin.start_stage(view, 'storyboard'))
            self.assertEqual(bus.current_run('storyboard'), 3)
            bus.pump()
        self.assertEqual([(event['kind'], event['run']) for event in deliveries],
                         [('stage.failed', 2), ('stage.failed', 3)])
        host.open_storyboard_skill.assert_not_called()
        host.pet_report.assert_not_called()
        view.advance_stage.assert_not_called()
        view._emit.assert_not_called()

    def test_fallback_false_and_exception_pass_through_once(self):
        from unittest.mock import Mock

        host = Mock(root=None, pet=None, account=None)
        fallback = Mock(return_value=False)
        self.assertIs(stage_handler_registry.start(host, 'script', 'manual', fallback), False)
        fallback.assert_called_once_with('script', 'manual')
        fallback.reset_mock()
        error = RuntimeError('callback failed')
        fallback.side_effect = error
        with self.assertRaises(RuntimeError) as caught:
            stage_handler_registry.start(host, 'script', 'manual', fallback)
        self.assertIs(caught.exception, error)
        fallback.assert_called_once_with('script', 'manual')

    def test_account_condition_failure_does_not_dispatch(self):
        from unittest.mock import Mock

        host = Mock(root=None, pet=None)
        host.account.stage_gate.return_value = 'blocked'
        fallback = Mock()
        self.assertEqual(stage_handler_registry.start(
            host, 'script', 'manual', fallback, run_action=stage_run_action,
        ), 'blocked')
        fallback.assert_not_called()

    def test_account_denial_precedes_run_registration(self):
        from unittest.mock import Mock

        gate = Mock(return_value='需要登录')
        begin = Mock()
        host = Mock(root=None, account=Mock(stage_gate=gate), pet=Mock(bus=Mock(begin_run=begin)))
        fallback = Mock()
        self.assertEqual(stage_handler_registry.start(
            host, 'keyframe', 'manual', fallback, run_action=stage_run_action,
        ), '需要登录')
        gate.assert_called_once_with('keyframe')
        begin.assert_not_called()
        fallback.assert_not_called()
        host.pet._emit.assert_not_called()

    def test_allowed_run_checks_membership_before_registering_and_dispatching(self):
        actions = Mock()
        actions.gate.return_value = ''
        actions.begin.return_value = 1
        actions.dispatch.return_value = '已派发'
        host = Mock(root=None, account=Mock(stage_gate=actions.gate),
                    pet=Mock(bus=Mock(begin_run=actions.begin)))
        self.assertEqual(stage_handler_registry.start(
            host, 'keyframe', 'manual', actions.dispatch, run_action=stage_run_action,
        ), '已派发')
        self.assertEqual([(entry[0], entry.args) for entry in actions.mock_calls], [
            ('gate', ('keyframe',)), ('begin', ('keyframe',)), ('dispatch', ('keyframe', 'manual')),
        ])

    def test_begin_failure_stops_dispatch_and_is_observable(self):
        from unittest.mock import Mock

        fallback = Mock()
        begin = Mock(return_value=False)
        host = Mock(root=None, account=None, pet=Mock(bus=Mock(begin_run=begin)))
        self.assertIs(stage_handler_registry.start(
            host, 'keyframe', 'manual', fallback, run_action=stage_run_action,
        ), False)
        begin.assert_called_once_with('keyframe')
        begin.reset_mock()
        error = RuntimeError('run registration failed')
        begin.side_effect = error
        with self.assertRaises(RuntimeError) as caught:
            stage_handler_registry.start(host, 'keyframe', 'manual', fallback, run_action=stage_run_action)
        self.assertIs(caught.exception, error)
        begin.assert_called_once_with('keyframe')
        fallback.assert_not_called()

    def test_repeated_auto_denials_do_not_reuse_last_run_or_report_success(self):
        bus = pet_bus.Bus()
        old_run = bus.begin_run('keyframe')
        pet = Mock(bus=bus)
        pet._emit.side_effect = bus.emit
        host = Mock(root=None, account=Mock(stage_gate=Mock(return_value='需要登录')), pet=pet)
        fallback = Mock()
        deliveries = []
        bus.subscribe('*', deliveries.append)
        for _ in range(2):
            self.assertEqual(stage_handler_registry.start(
                host, 'keyframe', fallback=fallback, run_action=stage_run_action,
            ), '需要登录')
            bus.pump()
        self.assertEqual(bus.current_run('keyframe'), old_run)
        self.assertEqual([(item['kind'], item['run']) for item in deliveries], [('stage.failed', 0)] * 2)
        fallback.assert_not_called()

    def test_auto_start_registration_failure_does_not_advance(self):
        for failure in (False, RuntimeError('登记失败')):
            with self.subTest(failure=failure):
                host = object.__new__(desktop.Desktop)
                host.root = None
                host._account_controller = Mock(stage_gate=Mock(return_value=''))
                host.pet = Mock()
                if isinstance(failure, Exception):
                    host.pet.bus.begin_run.side_effect = failure
                else:
                    host.pet.bus.begin_run.return_value = failure
                host._start_unattended_stage = Mock()
                view = Mock(desktop=host, errors=[])
                view.agent.level = 'auto'
                view._authorize_paid_stage.return_value = (True, '')
                with patch('orchestrator.stage_flow.unchecked', return_value=False):
                    errors = [PetStagesMixin.start_stage(view, 'assets') for _ in range(2)]
                self.assertTrue(all(error.startswith('阶段未派发：') for error in errors), errors)
                host._start_unattended_stage.assert_not_called()
                view.advance_stage.assert_not_called()
                calls = view._emit.call_args_list
                self.assertEqual(len(calls), 2)
                self.assertEqual(len({call.kwargs['key'] for call in calls}), 2)
                for call, error in zip(calls, errors, strict=True):
                    self.assertEqual(call.args, ('stage.failed',))
                    self.assertEqual(call.kwargs['stage'], 'assets')
                    self.assertEqual(call.kwargs['error'], error)


class DesktopBridgeActionTests(unittest.TestCase):
    def setUp(self):
        self.host = PetBridgeMixin()
        self.host.root = Path('project')
        self.host.pet_advance = Mock(return_value='advanced')
        self.enterContext(patch.object(stage_handler_registry, '_workflow_lock_error', return_value=''))
        self.enterContext(patch.object(stage_handler_registry.stage_flow, 'unchecked', return_value=False))

    def test_unknown_stage_is_rejected_before_registration(self):
        self.host.pet = Mock()
        with self.assertRaisesRegex(ValueError, 'unknown_stage'):
            self.host.pet_start('unknown_stage')
        self.assertEqual(self.host.pet.mock_calls, [])

    def test_direct_actions_preserve_false_and_exception(self):
        for stage, name, options in (
            ('script_structure', 'pet_script_structure_batch', {'trigger': 'auto'}),
            ('continuity', 'pet_continuity_ledger', {}),
            ('keyframe', 'pet_frame_batch', {'trigger': 'auto'}),
        ):
            with self.subTest(stage=stage):
                action = Mock(return_value=False)
                setattr(self.host, name, action)
                self.assertIs(self.host.pet_start(stage), False)
                action.assert_called_once_with(**options)
                action.reset_mock(side_effect=True)
                action.side_effect = RuntimeError('dispatch failed')
                with self.assertRaisesRegex(RuntimeError, 'dispatch failed'):
                    self.host.pet_start(stage)
                action.assert_called_once_with(**options)
        self.host.pet_advance.assert_not_called()

    def test_poll_switch_runs_once_before_wake(self):
        from orchestrator.desktop_auto_state import UNATTENDED_SWITCH_SETTERS

        for awakened, expected in (
            ('advanced', '已自动开始'),
            ('', '已经在跑'),
        ):
            with self.subTest(awakened=awakened):
                self.host.pet = Mock()
                self.host.pet_advance.reset_mock()
                setter = Mock()

                def wake(stage):
                    setter.assert_called_once_with(self.host.root, True)
                    return awakened

                self.host.pet_advance.side_effect = wake
                with patch.dict(UNATTENDED_SWITCH_SETTERS, {'auto_asset': setter}):
                    self.assertIn(expected, self.host.pet_start('assets'))
                self.host.pet_advance.assert_called_once_with('assets')
                self.host.pet.bus.begin_run.assert_called_once_with('assets')
                self.host.pet._emit.assert_not_called()

    def test_poll_switch_write_failure_stops_wake_and_reports_undispatched(self):
        from orchestrator.desktop_auto_state import UNATTENDED_SWITCH_SETTERS

        self.host.pet = Mock()
        self.host.pet_advance.reset_mock()
        setter = Mock(side_effect=OSError('write failed'))
        with patch.dict(UNATTENDED_SWITCH_SETTERS, {'auto_asset': setter}):
            result = self.host.pet_start('assets')
        self.assertEqual(result, '阶段未派发：write failed')
        setter.assert_called_once_with(self.host.root, True)
        self.host.pet_advance.assert_not_called()
        self.host.pet.bus.begin_run.assert_called_once_with('assets')
        self.host.pet._emit.assert_not_called()


class StageCommandContractTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.original = stage_handler_registry.start

        def record(host, stage, trigger='auto', fallback=None, *, skip_action=None,
                   run_action=None):
            self.assertIs(skip_action, skip_unchecked)
            self.assertIs(run_action, stage_run_action)
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


class StoryboardSendRegistryContractTests(unittest.TestCase):
    def test_manual_send_reuses_the_storyboard_batch_entry(self):
        host = object.__new__(desktop.Desktop)
        host.status = Mock()
        host.pet_storyboard_batch = Mock(return_value='')

        self.assertFalse(host.start_storyboard_send(
            object(), '补充要求', ['A'], ('snapshot', {})))

        host.pet_storyboard_batch.assert_called_once_with(trigger='manual')

    def test_storyboard_presentation_uses_the_send_snapshot(self):
        host = object.__new__(desktop.Desktop)
        host.root = object()
        host.shutting_down = False
        host.open_storyboard_skill = Mock(return_value=17)
        context = {
            'project': host.root,
            'request_text': '补充要求',
            'named': ['A'],
            'model_snapshot': ('snapshot', {}),
            'started': [],
        }
        host._storyboard_send_context = context

        result = desktop.Desktop.present_stage(
            host, stage_handler_registry.StagePresentation.OPEN_STORYBOARD, '')

        self.assertEqual(result, 17)
        host.open_storyboard_skill.assert_called_once_with(
            None, request_text='补充要求', only=['A'],
            model_snapshot=('snapshot', {}))
        self.assertEqual(context['started'], [17])


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
            stage_handler_registry.start(auto_host, 'storyboard', 'auto', run_action=stage_run_action),
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
                auto, 'script', 'auto', lambda stage, trigger: called.append((stage, trigger)),
                run_action=stage_run_action)
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
                host, 'assets', 'auto', skip_action=skip_unchecked,
                fallback=lambda stage, trigger: calls.append((stage, trigger)) or 'ran')
            self.assertIn('跳过', text)
            self.assertEqual(calls, [], '未勾选的阶段不得进入自动派发')
            self.assertEqual(pet.machine.skipped, [('assets', '未勾选 SKILL')])
            self.assertEqual(pet.machine.saved, 1)
            self.assertEqual(pet.auto.done_calls, [('assets', True)])
            self.assertTrue(any('跳过' in line for line in pet.broadcasts))
            self.assertFalse(any(kind == 'stage.failed' for kind, _ in pet.events))

    def test_desktop_and_pet_entrypoints_each_apply_one_skip(self):
        from unittest.mock import Mock

        for entry in ('desktop', 'pet'):
            with self.subTest(entry=entry), tempfile.TemporaryDirectory() as td:
                host, pet = self._host(td, [])
                host._start_unattended_stage = Mock()
                host.pet_start = Mock()
                if entry == 'desktop':
                    text = PetBridgeMixin.pet_start(host, 'assets')
                else:
                    view = Mock(desktop=host)
                    view.agent.level = 'auto'
                    text = PetStagesMixin.start_stage(view, 'assets')
                    view.agent.approve.assert_not_called()
                self.assertIn('跳过', text)
                self.assertEqual(pet.machine.skipped, [('assets', '未勾选 SKILL')])
                self.assertEqual(pet.machine.saved, 1)
                self.assertEqual(pet.auto.done_calls, [('assets', True)])
                self.assertEqual(len(pet.broadcasts), 1)
                self.assertEqual(pet.events, [])
                host.pet_start.assert_not_called()
                host._start_unattended_stage.assert_not_called()

    def test_skip_order_and_failure_isolation(self):
        from unittest.mock import Mock, call, patch

        host = Mock()
        actions = Mock()
        actions.attach_mock(host.pet.machine.skip, 'skip')
        actions.attach_mock(host.pet.machine.save, 'save')
        actions.attach_mock(host.pet.auto.done, 'done')
        actions.attach_mock(host.pet.broadcast, 'broadcast')
        for failing_step in (None, 'skip', 'save', 'done', 'broadcast'):
            with self.subTest(failing_step=failing_step):
                actions.reset_mock(side_effect=True)
                if failing_step:
                    getattr(actions, failing_step).side_effect = RuntimeError(failing_step)
                with patch('ui.pet_ui_stages.app_logging.swallowed') as ignored:
                    text = skip_unchecked(host, 'assets')
                expected = [call.skip('assets', '未勾选 SKILL')]
                if failing_step != 'skip':
                    expected.append(call.save())
                expected.extend([call.done('assets', True),
                                 call.broadcast('【警告】' + text + '（阶段配置里勾选后可重跑）')])
                self.assertEqual(actions.mock_calls, expected)
                self.assertEqual(ignored.call_count, int(failing_step is not None))
                host.pet._emit.assert_not_called()

    def test_injected_skip_action_runs_once_and_blocks_fallback(self):
        from unittest.mock import Mock

        with tempfile.TemporaryDirectory() as td:
            host, pet = self._host(td, [])
            skip_action = Mock(return_value='skipped')
            fallback = Mock()
            self.assertEqual(stage_handler_registry.start(
                host, 'assets', fallback=fallback, skip_action=skip_action), 'skipped')
            skip_action.assert_called_once_with(host, 'assets')
            fallback.assert_not_called()
            self.assertEqual(pet.events, [])

    def test_missing_skip_action_with_pet_cannot_report_success(self):
        from unittest.mock import Mock

        with tempfile.TemporaryDirectory() as td:
            host, pet = self._host(td, [])
            fallback = Mock()
            with self.assertRaisesRegex(RuntimeError, '跳过动作'):
                stage_handler_registry.start(host, 'assets', fallback=fallback)
            fallback.assert_not_called()
            self.assertEqual(pet.machine.skipped, [])
            self.assertEqual(pet.events, [])

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

    def test_unknown_key_does_not_dispatch_or_emit(self):
        from unittest.mock import Mock

        with tempfile.TemporaryDirectory() as td:
            host, pet = self._host(td, [])
            for trigger in ('manual', 'auto'):
                with self.subTest(trigger=trigger):
                    fallback = Mock(return_value='ran')
                    with self.assertRaisesRegex(ValueError, '未知阶段'):
                        stage_handler_registry.start(host, 'unknown_stage', trigger, fallback=fallback)
                    fallback.assert_not_called()
            self.assertEqual(pet.events, [])
            self.assertEqual(pet.machine.skipped, [])
