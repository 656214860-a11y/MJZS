"""轮次证据：凭据扫描与定向测试由门禁产出，结果文件里的措辞不再算证据（对应 G3）。"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parent.parent
SCRIPT = PROGRAM / '维护记录' / '基准脚本' / 'round_evidence.py'
spec = importlib.util.spec_from_file_location('round_evidence_for_tests', SCRIPT)
evidence = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = evidence
spec.loader.exec_module(evidence)

FAKE_KEY = 'sk-' + 'a1B2c3D4e5F6g7H8i9J0k1L2'


def _repo(root: Path):
    subprocess.run(['git', 'init', '--quiet'], cwd=root, check=True)


def _stage(root: Path, name: str, text: str):
    (root / name).parent.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(text, encoding='utf-8')
    subprocess.run(['git', 'add', name], cwd=root, check=True)


def _green(keywords):
    return {'cmd': 'x', 'exit': 0, 'passed': 3, 'failed': 0}


class CredentialScanTests(unittest.TestCase):
    def test_staged_key_shape_is_a_hit_without_storing_the_value(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _stage(root, 'a.py', 'KEY = "%s"\n' % FAKE_KEY)
            result = evidence.credential_scan(root)
        self.assertTrue(result['ran'])
        self.assertEqual(result['hits'], ['a.py:1:openai-style-key'])
        self.assertNotIn(FAKE_KEY, json.dumps(result))

    def test_clean_staged_change_has_no_hits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _repo(root)
            _stage(root, 'a.py', 'value = 1\n')
            self.assertEqual(evidence.credential_scan(root), {'ran': True, 'hits': []})


class JudgeTests(unittest.TestCase):
    def test_prose_in_result_file_without_evidence_file_is_red(self):
        """旧漏洞反例：只在结果文件写“凭据扫描无命中”，没有证据文件。"""
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / 'tasks_round_9999_result.md').write_text('凭据扫描：无命中。定向 0 红。', encoding='utf-8')
            scan_ok, tests_ok, _ = evidence.judge(9999, directory)
        self.assertFalse(scan_ok)
        self.assertFalse(tests_ok)

    def test_complete_evidence_is_green(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, directory = Path(temporary), Path(temporary) / 'ev'
            _repo(root)
            _stage(root, 'a.py', 'value = 1\n')
            evidence.write_evidence(9999, ['x'], directory, root, run_tests=_green)
            self.assertEqual(evidence.judge(9999, directory)[:2], (True, True))

    def test_hit_or_failed_tests_make_it_red(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, directory = Path(temporary), Path(temporary) / 'ev'
            _repo(root)
            _stage(root, 'a.py', 'KEY = "%s"\n' % FAKE_KEY)
            evidence.write_evidence(9999, ['x'], directory, root, run_tests=lambda k: {
                'cmd': 'x', 'exit': 1, 'passed': 3, 'failed': 1})
            self.assertEqual(evidence.judge(9999, directory)[:2], (False, False))

    def test_code_change_without_keywords_means_tests_were_not_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, directory = Path(temporary), Path(temporary) / 'ev'
            _repo(root)
            _stage(root, '程序/a.py', 'value = 1\n')
            evidence.write_evidence(9999, [], directory, root)
            self.assertEqual(evidence.judge(9999, directory)[:2], (True, False))

    def test_docs_only_change_needs_no_targeted_tests(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, directory = Path(temporary), Path(temporary) / 'ev'
            _repo(root)
            _stage(root, '程序/note.md', '文档\n')
            evidence.write_evidence(9999, [], directory, root)
            self.assertEqual(evidence.judge(9999, directory)[:2], (True, True))

    def test_merge_skip_is_allowed_but_unknown_skip_reasons_are_not(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, directory = Path(temporary), Path(temporary) / 'ev'
            _repo(root)
            _stage(root, '程序/a.py', 'value = 1\n')
            evidence.write_evidence(9999, [], directory, root, skip='merge-ci-exit')
            self.assertEqual(evidence.judge(9999, directory)[:2], (True, True))
            evidence.write_evidence(9999, [], directory, root, skip='trust-me')
            self.assertEqual(evidence.judge(9999, directory)[:2], (True, False))

    def test_rounds_before_the_cutoff_are_exempt(self):
        self.assertEqual(evidence.judge(evidence.EVIDENCE_REQUIRED_FROM - 1, Path('missing'))[:2], (True, True))


if __name__ == '__main__':
    unittest.main()
