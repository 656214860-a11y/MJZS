"""AGENTS 规则必须有登记的守卫测试，或在“暂无”上限里（只许减少）（对应 C3，规则 26）。"""
from __future__ import annotations

import importlib.util
import sys
import unittest

from tests.architecture._scan import ROOT

SPEC = importlib.util.spec_from_file_location('rule_guard_map_for_tests', ROOT / 'scripts' / 'rule_guard_map.py')
MAP = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MAP
SPEC.loader.exec_module(MAP)

# 以下是流程性规则，没有可执行的守卫；补了守卫就从这里删掉，不得新增。降为建议须经用户确认。
UNGUARDED_CEILING = frozenset({'16', '25', '26', '30a', '32'})


class RuleGuardMapTests(unittest.TestCase):
    def setUp(self):
        self.rows = MAP.build()

    def test_every_rule_is_guarded_or_inside_the_ceiling(self):
        extra = set(MAP.unguarded(self.rows)) - UNGUARDED_CEILING
        self.assertEqual(extra, set(), '这些规则没有守卫测试：%s。补测试并登记到 维护记录/规则守卫基线.json（规则 26）' % sorted(extra))

    def test_ceiling_has_no_stale_entries(self):
        stale = UNGUARDED_CEILING - set(MAP.unguarded(self.rows))
        self.assertEqual(stale, set(), '已有守卫的规则请从 UNGUARDED_CEILING 删除：%s' % sorted(stale))

    def test_registered_guard_files_exist(self):
        missing = [f for _, _, files in self.rows for f in files if not (ROOT / f).is_file()]
        self.assertEqual(missing, [], '登记的守卫测试不存在：%s' % missing)

    def test_registry_only_names_rules_that_exist_in_agents(self):
        known = {number for number, _, _ in self.rows}
        self.assertEqual(set(MAP.load_guards()) - known, set(), '基线里有 AGENTS 已不存在的规则编号')

    def test_generated_report_is_in_sync(self):
        self.assertEqual(MAP.REPORT.read_text(encoding='utf-8'), MAP.render(self.rows),
                         '规则守卫对照.md 已过期：运行 python -B scripts/rule_guard_map.py --write')

    def test_parser_reads_numbers_and_ignores_other_sections(self):
        text = '## 2.5 轮次\n25. **范围**：x\n30a. **欠账**：y\n## 3. 其他\n99. **不算**：z\n### 2.3 硬约束\n11. 无粗体标题\n'
        self.assertEqual([n for n, _ in MAP.parse_rules(text)], ['25', '30a', '11'])

    def test_rule_without_registration_is_reported_as_unguarded(self):
        self.assertEqual(MAP.unguarded([('1', 't', []), ('2', 't', ['a.py'])]), ['1'])


if __name__ == '__main__':
    unittest.main()
