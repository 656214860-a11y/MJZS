"""增量台账不漏检的对抗测试：被依赖的东西变了，依赖它的测试必须被判定为要跑。

覆盖四条依赖路径：函数内 import、agent 子包的点号导入、tests/ 下的共用辅助模块、
`from agent import core` 形式。每条都在临时目录里造一份迁移前后的程序树，
走真实的 `incremental()`，只看结论：目标测试在不在「要跑」里。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_selftests
import selftest_env


class IncrementalDoesNotMissDependencies(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        (self.root / 'agent').mkdir()
        (self.root / 'tests').mkdir()
        (self.root / 'agent' / '__init__.py').write_text('', encoding='utf-8')
        saved = selftest_env.HERE, selftest_env.TESTS_DIR
        self.addCleanup(lambda: setattr(selftest_env, 'HERE', saved[0]) or setattr(selftest_env, 'TESTS_DIR', saved[1]))
        selftest_env.HERE = str(self.root)
        selftest_env.TESTS_DIR = str(self.root / 'tests')
        run_selftests.imports_of.cache_clear()
        self.addCleanup(run_selftests.imports_of.cache_clear)

    def write(self, relative, text):
        path = self.root / relative
        path.write_text(text, encoding='utf-8')
        run_selftests.imports_of.cache_clear()

    def assert_changed_dependency_reschedules(self, test_source, dependency, first, second):
        self.write('tests/test_probe.py', test_source)
        self.write(dependency, first)
        _todo, _skipped, state = run_selftests.incremental(['test_probe'], {})
        self.write(dependency, second)
        todo, skipped, _state = run_selftests.incremental(['test_probe'], state)
        self.assertEqual((todo, skipped), (['test_probe'], []), '依赖变了，测试必须重跑')
        todo, skipped, _state = run_selftests.incremental(['test_probe'], run_selftests.incremental(['test_probe'], state)[2])
        self.assertEqual((todo, skipped), ([], ['test_probe']), '依赖没变就不该重跑')

    def test_import_inside_a_function(self):
        self.write('inner_dep.py', 'X = 1\n')
        self.assert_changed_dependency_reschedules(
            'def test():\n    import inner_dep\n', 'inner_dep.py', 'X = 1\n', 'X = 2\n')

    def test_dotted_import_from_the_agent_package(self):
        self.assert_changed_dependency_reschedules(
            'def test():\n    from agent.core import save\n', 'agent/core.py', 'A = 1\n', 'A = 2\n')

    def test_from_agent_import_submodule(self):
        self.assert_changed_dependency_reschedules(
            'from agent import media\n', 'agent/media.py', 'A = 1\n', 'A = 2\n')

    def test_shared_helper_inside_the_tests_folder(self):
        self.assert_changed_dependency_reschedules(
            'import widget_probe_support\n', 'tests/widget_probe_support.py', 'A = 1\n', 'A = 2\n')

    def test_a_ledger_written_under_older_rules_is_not_trusted(self):
        self.write('tests/test_probe.py', 'import inner_dep\n')
        self.write('inner_dep.py', 'X = 1\n')
        _todo, _skipped, state = run_selftests.incremental(['test_probe'], {})
        state.pop('rules')
        todo, skipped, _state = run_selftests.incremental(['test_probe'], state)
        self.assertEqual((todo, skipped), (['test_probe'], []))


if __name__ == '__main__':
    unittest.main()
