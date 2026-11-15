"""外部技能包完整性：登记表与主仓库固定的提交一致，已检出的包没有被改过（对应 E1）。"""
from __future__ import annotations

import importlib.util
import sys
import unittest

from tests.architecture._scan import ROOT

SPEC = importlib.util.spec_from_file_location('skill_package_pins_for_tests', ROOT / 'scripts' / 'skill_package_pins.py')
PINS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PINS
SPEC.loader.exec_module(PINS)

COMMIT, TREE = 'a' * 40, 'b' * 40
STATE = {'head': COMMIT, 'tree': TREE, 'clean': True, 'source': 'https://x/y.git'}
ENTRY = {'p': {'source': 'https://x/y.git', 'commit': COMMIT, 'tree': TREE}}


class SkillPackagePinTests(unittest.TestCase):
    def test_registry_matches_the_commits_the_repository_pins(self):
        pinned = PINS.pinned_packages()
        self.assertTrue(pinned, '没有找到被固定的外部技能包')
        self.assertEqual(PINS.verify(PINS.load_registry(), pinned, {}), [])

    def test_checked_out_packages_are_unmodified(self):
        pinned = PINS.pinned_packages()
        states = {path: PINS.checkout_state(ROOT / path) for path in pinned}
        self.assertEqual(PINS.verify(PINS.load_registry(), pinned, {p: s for p, s in states.items() if s}), [])

    def test_every_entry_names_a_source_and_full_hashes(self):
        for path, entry in PINS.load_registry().items():
            with self.subTest(path=path):
                self.assertTrue(entry['source'].startswith('https://'))
                self.assertEqual((len(entry['commit']), len(entry['tree'])), (40, 40))

    def test_clean_matching_package_passes(self):
        self.assertEqual(PINS.verify(ENTRY, {'p': COMMIT}, {'p': STATE}), [])

    def test_uninitialised_checkout_is_checked_only_against_the_pin(self):
        self.assertEqual(PINS.verify(ENTRY, {'p': COMMIT}, {}), [])

    def test_drift_cases_are_reported(self):
        cases = {
            '与主仓库固定的': (ENTRY, {'p': 'c' * 40}, {}),
            '不是登记提交': (ENTRY, {'p': COMMIT}, {'p': dict(STATE, head='c' * 40)}),
            '内容树哈希': (ENTRY, {'p': COMMIT}, {'p': dict(STATE, tree='d' * 40)}),
            '未提交的改动': (ENTRY, {'p': COMMIT}, {'p': dict(STATE, clean=False)}),
            '登记表里没有': ({}, {'p': COMMIT}, {}),
            '不再固定它': (ENTRY, {}, {}),
        }
        for fragment, (registry, pinned, states) in cases.items():
            with self.subTest(case=fragment):
                problems = PINS.verify(registry, pinned, states)
                self.assertTrue(any(fragment in line for line in problems), problems)


if __name__ == '__main__':
    unittest.main()
