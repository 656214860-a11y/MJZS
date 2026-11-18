"""门禁自审计：关键棘轮对“已知坏样本”必须失败、对好样本必须通过（对应 G7）。

只看“当前树通过”的门禁，被改坏（扫描范围缩小、条件写反）时仍然是绿的；这里给 5 个关键门禁各一组坏／好样本，
门禁本身失效时这组测试先红。样本全在临时目录里，不碰仓库文件。
"""
from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from tests.architecture import test_layers, test_path_authority, test_remove_authority
from tests.architecture import test_secret_sink_audit, test_silent_exception_ratchet
from tests.architecture import test_layer_relations


def _write(folder: Path, name: str, source: str) -> Path:
    path = folder / name
    path.write_text(textwrap.dedent(source), encoding='utf-8')
    return path


class PathAuthoritySelfAuditTests(unittest.TestCase):
    def run_gate(self, path):
        case = test_path_authority.PathAuthorityTests('test_path_rules_are_owned_by_authority_modules')
        with mock.patch.object(test_path_authority, 'module_scan_files', return_value=(path,)):
            case.test_path_rules_are_owned_by_authority_modules()

    def test_bad_sample_fails_and_good_samples_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            bad = _write(folder, 'sample_violation.py', 'from pathlib import Path\nX = Path("a") / "writing/foo"\n')
            with self.assertRaises(AssertionError):
                self.run_gate(bad)
            self.run_gate(_write(folder, 'sample_clean.py', 'X = 1\n'))
            self.run_gate(_write(folder, 'stage_layout.py', 'from pathlib import Path\nX = Path("a") / "writing/foo"\n'))


class RemoveAuthoritySelfAuditTests(unittest.TestCase):
    def run_gate(self, folder, path):
        case = test_remove_authority.RemoveAuthorityTests('test_file_removal_is_owned_by_lifecycle_modules')
        with mock.patch.object(test_remove_authority, 'ROOT', folder), \
                mock.patch.object(test_remove_authority, 'production_files_recursive', return_value=(path,)):
            case.test_file_removal_is_owned_by_lifecycle_modules()

    def test_bad_sample_fails_and_good_samples_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            bad = _write(folder, 'sample_violation.py', 'import shutil\nshutil.rmtree("x")\n')
            with self.assertRaises(AssertionError):
                self.run_gate(folder, bad)
            self.run_gate(folder, _write(folder, 'sample_clean.py', 'X = 1\n'))
            self.run_gate(folder, _write(folder, 'storage_maintenance.py', 'import shutil\nshutil.rmtree("x")\n'))


class SilentExceptionSelfAuditTests(unittest.TestCase):
    def test_bad_sample_is_found_and_trips_the_ratchet(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            _write(folder, 'sample_violation.py', 'try:\n    pass\nexcept Exception:\n    pass\n')
            with mock.patch.object(test_silent_exception_ratchet, 'PROGRAM', folder):
                self.assertEqual(test_silent_exception_ratchet.silent_exception_sites(), {'sample_violation.py': [3]})
                case = test_silent_exception_ratchet.SilentExceptionRatchet('test_no_new_silent_exception_handlers')
                with self.assertRaises(AssertionError):
                    case.test_no_new_silent_exception_handlers()

    def test_narrow_or_logged_handlers_are_not_flagged(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            _write(folder, 'sample_clean.py', 'try:\n    pass\nexcept OSError:\n    pass\n'
                                              'try:\n    pass\nexcept Exception:\n    print("x")\n')
            with mock.patch.object(test_silent_exception_ratchet, 'PROGRAM', folder):
                self.assertEqual(test_silent_exception_ratchet.silent_exception_sites(), {})


class SecretSinkSelfAuditTests(unittest.TestCase):
    def test_key_flowing_into_a_log_is_reported_and_clean_code_is_not(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            bad = _write(folder, 'sample_violation.py',
                         'def f():\n    token = os.getenv("FAKE_API_KEY")\n    print(token)\n')
            good = _write(folder, 'sample_clean.py', 'def f():\n    token = os.getenv("FAKE_API_KEY")\n    return bool(token)\n')
            self.assertEqual(test_secret_sink_audit.audit([bad]), {'sample_violation.py:3:log'})
            self.assertEqual(test_secret_sink_audit.audit([good]), set())


class LayerSelfAuditTests(unittest.TestCase):
    def test_upward_import_is_reported_and_downward_is_not(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            low = _write(folder, 'low.py', 'import high\n')
            high = _write(folder, 'high.py', 'import low\n')
            with mock.patch.object(test_layers, 'LAYERS', {'low': 0, 'high': 4}):
                with mock.patch.object(test_layers, 'module_scan_files', return_value=(low,)):
                    self.assertEqual(test_layers._upward_pairs(), {('low.py', 'low', 'high')})
                with mock.patch.object(test_layers, 'module_scan_files', return_value=(high,)):
                    self.assertEqual(test_layers._upward_pairs(), set())


class LayerRelationsSelfAuditTests(unittest.TestCase):
    """I1（LR-01~LR-10）：层间关系门禁对坏样本必须报出、对好样本不报。"""

    def _scan_with(self, files, layers):
        with mock.patch.object(test_layer_relations, 'module_scan_files', return_value=tuple(files)), \
                mock.patch.object(test_layer_relations, 'LAYERS', dict(layers)):
            return test_layer_relations._scan()['_detail']

    def test_unregistered_same_layer_edge_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            a = _write(folder, 'aaa_mod.py', 'import bbb_mod\n')
            b = _write(folder, 'bbb_mod.py', 'X = 1\n')
            detail = self._scan_with([a, b], {'aaa_mod': 1, 'bbb_mod': 1})
            self.assertIn(('aaa_mod', 'bbb_mod'), detail['unregistered'])
            # 好样本：同层边已登记 SAME_LAYER_EDGES 时不再报未登记
            with mock.patch.object(test_layer_relations, 'SAME_LAYER_EDGES',
                                   frozenset({('aaa_mod', 'bbb_mod')})):
                with mock.patch.object(test_layer_relations, 'module_scan_files', return_value=(a, b)), \
                        mock.patch.object(test_layer_relations, 'LAYERS', {'aaa_mod': 1, 'bbb_mod': 1}):
                    detail2 = test_layer_relations._scan()['_detail']
            self.assertNotIn(('aaa_mod', 'bbb_mod'), detail2['unregistered'])

    def test_mutual_same_layer_dependency_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            a = _write(folder, 'aaa_mod.py', 'import bbb_mod\n')
            b = _write(folder, 'bbb_mod.py', 'import aaa_mod\n')
            detail = self._scan_with([a, b], {'aaa_mod': 2, 'bbb_mod': 2})
            self.assertIn(('aaa_mod', 'bbb_mod'), detail['mutual'])
            # 好样本：单向同层边不算互依赖
            c = _write(folder, 'ccc_mod.py', 'X = 1\n')
            detail2 = self._scan_with([a, c], {'aaa_mod': 2, 'ccc_mod': 2})
            self.assertNotIn(('aaa_mod', 'ccc_mod'), detail2['mutual'])

    def test_nonliteral_dynamic_import_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            bad = _write(folder, 'aaa_mod.py',
                         'from importlib import import_module\n'
                         'def f(name):\n    return import_module(name)\n')
            detail = self._scan_with([bad], {'aaa_mod': 3})
            self.assertTrue(any(x[0] == 'aaa_mod' and x[2] == 'import_module'
                                for x in detail['nonliteral']), detail['nonliteral'])
            # 好样本：字面量动态导入不算非字面量
            good = _write(folder, 'bbb_mod.py',
                          'from importlib import import_module\n'
                          'X = import_module("os")\n')
            detail2 = self._scan_with([good], {'bbb_mod': 3})
            self.assertEqual(detail2['nonliteral'], [])

    def test_l1_importing_l2_is_reported_as_upward(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            low = _write(folder, 'aaa_mod.py', 'import bbb_mod\n')
            high = _write(folder, 'bbb_mod.py', 'X = 1\n')
            detail = self._scan_with([low, high], {'aaa_mod': 1, 'bbb_mod': 2})
            self.assertIn(('aaa_mod', 'bbb_mod'), detail['upward'])
            # 好样本：L1 依赖 L0 不算上行
            zero = _write(folder, 'ccc_mod.py', 'X = 1\n')
            detail2 = self._scan_with([low, zero], {'aaa_mod': 1, 'ccc_mod': 0})
            self.assertNotIn(('aaa_mod', 'ccc_mod'), detail2['upward'])


if __name__ == '__main__':
    unittest.main()
