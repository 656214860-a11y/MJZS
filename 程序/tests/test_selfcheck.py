"""contract.selfcheck／diagnostics：启动自检类型、注入式运行器与甲类分级（任务书轮 3A D3）。"""
from __future__ import annotations

import unittest
from unittest import mock

from contract import selfcheck
from contract.diagnostics import Diagnostic, Severity, StartupPhase


def _diag(severity=Severity.WARN, scope='scope', code='code', message='msg'):
    return Diagnostic(severity=severity, scope=scope, code=code,
                      message=message, remedy=' remedy ')


class TypeContractTests(unittest.TestCase):
    def test_severity_is_a_closed_set_of_four_levels(self):
        self.assertEqual({item.value for item in Severity},
                         {'fatal', 'error', 'warn', 'degraded'})
        self.assertEqual(Severity.FATAL.value, 'fatal')
        self.assertEqual(Severity.DEGRADED.value, 'degraded')

    def test_startup_phase_covers_the_launch_sequence(self):
        self.assertEqual({item.value for item in StartupPhase},
                         {'contract', 'config', 'resource', 'ui_shell', 'ready'})
        self.assertLess(list(StartupPhase).index(StartupPhase.CONTRACT),
                        list(StartupPhase).index(StartupPhase.READY))

    def test_diagnostic_carries_comfyui_style_fields(self):
        item = Diagnostic(severity=Severity.FATAL, scope='contract', code='c',
                          message='what', remedy='fix', escape_hint='way out')
        self.assertEqual(item.escape_hint, 'way out')
        self.assertEqual(item.remedy, 'fix')
        # escape_hint 可空（§3c-1：一条逃生通道，可空）
        self.assertEqual(_diag().escape_hint, '')
        # severity 收字符串也归一到枚举，非法值拒绝
        self.assertIs(Diagnostic(severity='fatal', scope='s', code='c',
                                 message='m').severity, Severity.FATAL)
        with self.assertRaises(ValueError):
            Diagnostic(severity='bogus', scope='s', code='c', message='m')


class RunContractTests(unittest.TestCase):
    def test_empty_and_passing_checks_yield_empty_list(self):
        self.assertEqual(selfcheck.run(()), [])
        self.assertEqual(selfcheck.run((lambda: None, lambda: ())), [])

    def test_single_and_multiple_diagnostics_are_collected_in_order(self):
        first = _diag(Severity.WARN, code='a')
        second = _diag(Severity.ERROR, code='b')
        third = _diag(Severity.DEGRADED, code='c')
        found = selfcheck.run((lambda: first,
                               lambda: [second, third],
                               lambda: None))
        self.assertEqual(found, [first, second, third])

    def test_injected_check_keeps_its_declared_severity(self):
        declared = _diag(Severity.ERROR, code='env-disk')
        found = selfcheck.run((lambda: declared,))
        self.assertEqual(found, [declared])
        self.assertIs(found[0].severity, Severity.ERROR)

    def test_check_exception_becomes_degraded_and_does_not_stop_others(self):
        def boom():
            raise RuntimeError('check exploded')

        later = _diag(Severity.WARN, code='later')
        found = selfcheck.run((boom, lambda: later))
        self.assertEqual(len(found), 2)
        self.assertIs(found[0].severity, Severity.DEGRADED)
        self.assertIn('boom', found[0].message)
        self.assertIn('自身异常', found[0].message)
        self.assertEqual(found[1], later)

    def test_check_exception_is_never_upgraded_to_fatal(self):
        def bad():
            raise ValueError('x')
        found = selfcheck.run((bad,))
        self.assertEqual(len(found), 1)
        self.assertIs(found[0].severity, Severity.DEGRADED)
        self.assertIsNot(found[0].severity, Severity.FATAL)

    def test_malformed_return_value_becomes_degraded(self):
        def returns_text():
            return 'not a diagnostic'

        def returns_mixed():
            return [_diag(), 'oops']

        found = selfcheck.run((returns_text, returns_mixed))
        self.assertEqual(len(found), 2)
        self.assertTrue(all(item.severity is Severity.DEGRADED for item in found))
        self.assertIn('returns_text', found[0].message)
        self.assertIn('returns_mixed', found[1].message)

    def test_generator_checks_are_accepted(self):
        def gen():
            yield lambda: _diag(code='g1')
            yield lambda: _diag(code='g2')
        found = selfcheck.run(gen())
        self.assertEqual([item.code for item in found], ['g1', 'g2'])


class DefaultChecksTests(unittest.TestCase):
    """L0 自带检查：阶段契约撕裂与产物登记不自洽都是 Q6 甲类 → FATAL。"""

    def test_default_checks_pass_on_healthy_tree(self):
        self.assertEqual(selfcheck.run(selfcheck.default_checks()), [])

    def test_stage_contract_tear_is_fatal(self):
        with mock.patch('contract.stage_layout.stage_contract_errors',
                        return_value=('阶段目录顺序与 pet_bus.STAGES 不一致',)):
            found = selfcheck.run(selfcheck.default_checks())
        fatal = [item for item in found if item.severity is Severity.FATAL]
        self.assertEqual(len(fatal), 1)
        self.assertIn('pet_bus.STAGES', fatal[0].message)
        self.assertTrue(fatal[0].remedy)

    def test_artifact_registry_inconsistency_is_fatal(self):
        broken = {'desktop_queue': {'version': 1, 'required': ('tasks',)}}  # 缺 owner
        with mock.patch('contract.artifact_schema.REGISTRY', broken):
            found = selfcheck.run(selfcheck.default_checks())
        fatal = [item for item in found if item.severity is Severity.FATAL]
        self.assertTrue(fatal)
        self.assertTrue(any('desktop_queue' in item.message for item in fatal))

    def test_artifact_registry_reports_each_inconsistency_kind(self):
        cases = {
            'not_a_dict': {'bad': 5},
            'bad_version': {'bad': {'version': 0, 'required': (), 'owner': 'x'}},
            'bad_required': {'bad': {'version': 1, 'required': 'tasks', 'owner': 'x'}},
            'empty_owner': {'bad': {'version': 1, 'required': (), 'owner': ''}},
        }
        for label, registry in cases.items():
            with self.subTest(case=label):
                with mock.patch('contract.artifact_schema.REGISTRY', registry):
                    found = selfcheck.run((selfcheck._artifact_registry_check,))
                fatal = [item for item in found if item.severity is Severity.FATAL]
                self.assertEqual(len(fatal), 1, label)
                self.assertIn('bad', fatal[0].message)

    def test_check_without_dunder_name_is_still_reported(self):
        class Callable:
            def __call__(self):
                raise RuntimeError('no name')
        found = selfcheck.run((Callable(),))
        self.assertEqual(len(found), 1)
        self.assertIs(found[0].severity, Severity.DEGRADED)
        self.assertIn('Callable', found[0].message)

    def test_default_checks_are_injectable_alongside_foreign_checks(self):
        foreign = _diag(Severity.DEGRADED, scope='resource', code='disk-low')
        found = selfcheck.run(tuple(selfcheck.default_checks()) + (lambda: foreign,))
        self.assertEqual(found[-1], foreign)


if __name__ == '__main__':
    unittest.main()
