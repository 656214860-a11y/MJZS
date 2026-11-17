"""R1985 Desktop 自动化状态容器：工厂默认值、半成品对象懒建、旧属性名已退役（无 Tk）。"""
import os
import queue
import sys
import unittest
from dataclasses import fields

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from orchestrator.desktop_auto_state import AutoState, AutoStateHolderMixin, create_auto_state
from desktop_automation_service import BackgroundTaskLifecycle

# 原 Desktop._initialize_automation_state 中非 0／None／False／'' 的默认值。
SPECIAL_DEFAULTS = {'adopt_startup': True, 'adopt_errors': {}}
QUEUE_MESSAGES = ('keyframe_messages', 'asset_messages', 'video_messages')
TASK_FLOWS = ('edit', 'keyframe', 'asset', 'video', 'previs', 'handoff')
QUEUE_FLOWS = {'final': True, 'edit': True, 'keyframe': False, 'asset': False,
               'video': True, 'handoff': True}   # 值＝是否把宠物 drain 作为 sink 传入
STAGE_NAMES = {'final': 'final', 'edit': 'edit', 'keyframe': 'keyframe', 'asset': 'assets',
               'video': 'video', 'handoff': 'delivery'}


class _Host(AutoStateHolderMixin):
    pass


def _make():
    calls = []

    def stage_queue(stage, sink=None):
        calls.append((stage, sink))
        return ('queue', stage)

    drain = object()
    return create_auto_state('history.json', stage_queue=stage_queue, drain=drain), calls, drain


class AutoStateFactoryTests(unittest.TestCase):
    def test_field_count_and_names_are_unique(self):
        names = [f.name for f in fields(AutoState)]
        self.assertEqual(len(names), 64)   # R2032：gate_due／gate_error 从 Desktop 迁入
        self.assertEqual(len(set(names)), 64)

    def test_plain_defaults_match_the_old_initializer(self):
        state, _, _ = _make()
        special = set(SPECIAL_DEFAULTS) | set(QUEUE_MESSAGES)
        wired = {f'{flow}_{kind}' for flow in TASK_FLOWS for kind in ('tasks',)}
        wired |= {f'{flow}_queue' for flow in QUEUE_FLOWS}
        for item in fields(AutoState):
            if item.name in special or item.name in wired:
                continue
            value = getattr(state, item.name)
            if item.name.endswith('_due') or item.name.endswith('_ticket') \
                    or item.name == 'asset_attempt':
                self.assertEqual(value, 0, item.name)
            elif item.name.endswith('_busy') or item.name in ('adopt_pending', 'final_blocked'):
                self.assertIs(value, False, item.name)
            elif item.name.endswith('_error') or item.name == 'video_last':
                self.assertEqual(value, '', item.name)
            else:
                self.assertIsNone(value, item.name)
        self.assertIs(state.adopt_startup, True)
        self.assertEqual(state.adopt_errors, {})

    def test_message_queues_are_independent_queue_objects(self):
        first, _, _ = _make()
        second, _, _ = _make()
        for name in QUEUE_MESSAGES:
            self.assertIsInstance(getattr(first, name), queue.Queue)
            self.assertIsNot(getattr(first, name), getattr(second, name))
        self.assertIsNot(first.adopt_errors, second.adopt_errors)

    def test_tasks_and_stage_queues_are_wired_like_before(self):
        state, calls, drain = _make()
        for flow in TASK_FLOWS:
            self.assertIsInstance(getattr(state, f'{flow}_tasks'), BackgroundTaskLifecycle)
        self.assertIsNot(state.edit_tasks, state.video_tasks)
        expected = {(STAGE_NAMES[flow], drain if sink else None)
                    for flow, sink in QUEUE_FLOWS.items()}
        self.assertEqual(set(calls), expected)
        for flow in QUEUE_FLOWS:
            self.assertEqual(getattr(state, f'{flow}_queue'), ('queue', STAGE_NAMES[flow]))


class AutoStateHolderTests(unittest.TestCase):
    def test_fields_read_and_write_on_the_state(self):
        host = _Host()
        host.auto = AutoState()
        host.auto.final_busy = True
        self.assertIs(host.auto.final_busy, True)
        host.auto.keyframe_error = '坏了'
        self.assertEqual(host.auto.keyframe_error, '坏了')
        host.auto.edit_ticket = 5
        self.assertEqual(host.auto.edit_ticket, 5)

    def test_retired_legacy_names_are_gone(self):
        host = _Host()
        host.auto = AutoState()
        for item in fields(AutoState):
            legacy = f'_auto_{item.name}' if item.name.endswith('_ticket') else f'auto_{item.name}'
            with self.subTest(legacy):
                self.assertFalse(hasattr(AutoStateHolderMixin, legacy))
                self.assertFalse(hasattr(host, legacy))

    def test_read_of_an_unknown_name_raises_attribute_error(self):
        host = _Host()
        with self.assertRaises(AttributeError):
            host.nothing
        self.assertIs(getattr(host, 'nothing', False), False)

    def test_first_read_of_auto_on_a_half_built_object_creates_default_state(self):
        host = _Host.__new__(_Host)
        self.assertIsInstance(host.auto, AutoState)
        self.assertIs(host.auto.adopt_startup, True)
        host.auto.adopt_pending = True
        self.assertIs(host.auto.adopt_pending, True)
        self.assertIs(host.auto, host.auto)


if __name__ == '__main__':
    unittest.main()
