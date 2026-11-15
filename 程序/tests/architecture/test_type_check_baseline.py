"""开发期类型检查基线：结构自洽、模块真实存在、比较逻辑只许减少（对应 G6）。

真正跑 pyright 要 Node／联网，只在开发机用 ``scripts/typecheck_baseline.py --check`` 执行；本门禁不依赖外部工具，
只守住基线文件本身不被随手改坏，以及比较逻辑对「变差」必须报警。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

from tests.architecture._scan import ROOT

SPEC = importlib.util.spec_from_file_location('typecheck_baseline_for_tests', ROOT / 'scripts' / 'typecheck_baseline.py')
TB = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = TB
SPEC.loader.exec_module(TB)


class TypeCheckBaselineTests(unittest.TestCase):
    def setUp(self):
        self.data = json.JSONDecoder().decode(TB.BASELINE.read_text(encoding='utf-8'))

    def test_baseline_is_self_consistent(self):
        modules = self.data['modules']
        self.assertEqual(self.data['total'], sum(modules.values()))
        self.assertTrue(all(isinstance(count, int) and count > 0 for count in modules.values()))
        self.assertEqual(self.data['tool'], TB.TOOL)

    def test_every_baselined_module_still_exists(self):
        missing = [name for name in self.data['modules'] if not (ROOT / name).is_file()]
        self.assertEqual(missing, [], '基线里的模块已不存在，请 --update 刷新（只会减少）：%s' % missing)

    def test_excluded_directories_never_appear_in_the_baseline(self):
        banned = ('tests/', 'skills/', 'scripts/', 'tasks_round/', '维护记录/')
        self.assertEqual([name for name in self.data['modules'] if name.startswith(banned)], [])

    def test_compare_flags_growth_and_new_modules_but_not_improvement(self):
        baseline = {'a.py': 3, 'b.py': 2}
        self.assertEqual(TB.compare(baseline, {'a.py': 3, 'b.py': 1}), {})
        self.assertEqual(TB.compare(baseline, {'a.py': 4, 'b.py': 2}), {'a.py': (3, 4)})
        self.assertEqual(TB.compare(baseline, {'c.py': 1}), {'c.py': (0, 1)})

    def test_error_counting_ignores_warnings_and_groups_by_relative_path(self):
        report = {'generalDiagnostics': [
            {'file': str(ROOT / 'a.py'), 'severity': 'error'},
            {'file': str(ROOT / 'a.py'), 'severity': 'error'},
            {'file': str(ROOT / 'agent' / 'b.py'), 'severity': 'error'},
            {'file': str(ROOT / 'c.py'), 'severity': 'warning'},
            {'file': str(ROOT / 'tests' / 'd.py'), 'severity': 'error'},
        ]}
        self.assertEqual(TB.count_errors(report, ROOT), {'a.py': 2, 'agent/b.py': 1})

    def test_config_is_relative_and_pinned(self):
        config = TB.config_for(ROOT, ROOT.parent)
        self.assertFalse(Path(config['include'][0]).is_absolute())
        self.assertEqual((config['typeCheckingMode'], config['pythonVersion']), ('basic', '3.13'))


if __name__ == '__main__':
    unittest.main()
