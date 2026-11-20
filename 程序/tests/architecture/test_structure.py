"""目录协议行为测试：身份棘轮、路径边界、归属与分发隔离。"""
from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('structure_checker', ROOT / 'governance/check_structure.py')
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def policy():
    return {
        'schema_version': 1, 'source_root': 'src', 'max_depth': 4,
        'roles': {
            'src': {'role': 'source', 'owner': 'maintainer', 'description': 'application'},
            'src/tests': {'role': 'tests', 'owner': 'maintainer', 'description': 'tests'},
            'legacy': {'role': 'legacy', 'owner': 'maintainer', 'description': 'retired'},
            '.gitignore': {'role': 'tooling', 'owner': 'maintainer', 'description': 'ignore'},
            'manifest.md': {'role': 'docs', 'owner': 'maintainer', 'description': 'distribution'},
            'decision.md': {'role': 'docs', 'owner': 'maintainer', 'description': 'decision'},
        },
        'excludes': {'private': {'category': 'private', 'owner': 'maintainer', 'reason': 'secrets'}},
        'naming_exceptions': {}, 'test_ownership': {},
        'frozen_contract_tests': {'paths': [], 'owner': 'maintainer',
                                  'reason': 'Legacy cross-module contract', 'review_when': 'test changes'},
        'retirement': {},
        'decisions': ['decision.md'],
        'packaging': {'manifest': 'manifest.md', 'exclude_prefixes': ['legacy'],
                      'ignore_patterns': ['/build/'], 'configuration_home': 'packaging',
                      'private_keys': 'outside-repository'},
    }


def baseline(rows=()):
    return {'schema_version': 1, 'source_commit': 'abc', 'inventory_sha256': 'a',
            'policy_sha256': 'b', 'violations': [dict(row, owner='maintainer', reason='old debt', review_when='path changes') for row in rows]}


class StructureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.policy = policy()
        self.run_git('init', '-q')
        self.write('.gitignore', '/build/\n')
        self.write('manifest.md', '## 必须排除\n\n| `legacy/**` | retired |\n\n## Other\n')
        self.write('decision.md', '# Directory decision\n')
        self.write('src/app.py', 'VALUE = 1\n')
        self.run_git('add', '.')

    def run_git(self, *args):
        result = subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, timeout=15, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def inspect(self, candidates=()):
        return checker.check(self.root, checker.validate_policy(self.policy), checker.entries(self.root, candidates, self.policy))

    def test_valid_repository_passes(self):
        self.assertEqual(self.inspect(), [])

    def test_untracked_candidate_is_checked(self):
        self.write('src/Bad.py', '')
        findings = self.inspect(['src/Bad.py'])
        self.assertTrue(any(r['rule_id'] == 'STR003' for r in findings))

    def test_equal_count_replacement_is_not_allowed(self):
        old = checker.violation('STR003', 'src/Old.py', 'code_name', '')
        new = checker.violation('STR003', 'src/New.py', 'code_name', '')
        delta = checker.compare([new], baseline([old]))
        self.assertEqual(len(delta['added']), 1)
        self.assertEqual(len(delta['removed']), 1)

    def test_existing_debt_allowed_and_removal_reported(self):
        row = checker.violation('STR003', 'src/Old.py', 'code_name', '')
        self.assertEqual(checker.compare([row], baseline([row]))['added'], [])
        self.assertEqual(len(checker.compare([], baseline([row]))['removed']), 1)

    def test_hard_rule_cannot_be_baselined(self):
        row = checker.violation('STR009', 'src/app.py', 'import:legacy.old', '')
        with self.assertRaises(ValueError):
            checker.compare([row], baseline([row]))

    def test_policy_change_requires_explicit_baseline_review(self):
        with self.assertRaisesRegex(ValueError, 'policy changed'):
            checker.compare([], baseline(), policy_sha256='new-digest')

    def test_duplicate_baseline_rejected(self):
        row = checker.violation('STR003', 'src/Old.py', 'code_name', '')
        with self.assertRaises(ValueError):
            checker.compare([], baseline([row, row]))

    def test_invalid_policy_fails_closed(self):
        for bad in ({}, {'schema_version': 1}, [], None):
            with self.subTest(policy=bad), self.assertRaises(ValueError):
                checker.validate_policy(bad)
        self.policy['extra'] = True
        with self.assertRaises(ValueError):
            checker.validate_policy(self.policy)

    def test_cannot_exclude_all_source(self):
        self.policy['excludes']['src'] = dict(self.policy['excludes']['private'])
        with self.assertRaises(ValueError):
            checker.validate_policy(self.policy)

    def test_unsafe_candidate_paths_rejected(self):
        for name in ('../escape', 'C:/escape', '//server/share', 'src/../escape', 'src\\bad.py', 'src//bad.py'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                checker.entries(self.root, [name], self.policy)

    def test_private_candidate_does_not_read_content(self):
        self.write('private/secret.json', 'DO_NOT_READ')
        with self.assertRaisesRegex(ValueError, 'boundary'):
            checker.entries(self.root, ['private/secret.json'], self.policy)

    def test_untracked_product_source_candidate_is_not_ignored(self):
        self.write('src/BadSource.py', 'import legacy.old\n')
        findings = self.inspect(['src/BadSource.py'])
        self.assertTrue({'STR003', 'STR009'} <= {row['rule_id'] for row in findings})

    def test_directory_candidate_rejected(self):
        with self.assertRaisesRegex(ValueError, 'regular file'):
            checker.entries(self.root, ['src'], self.policy)

    def test_case_collision_is_error(self):
        self.write('src/APP.py', '')
        with self.assertRaisesRegex(ValueError, 'collision'):
            checker.entries(self.root, ['src/APP.py'], self.policy)

    def test_gitlink_is_atomic_not_recursed(self):
        self.run_git('update-index', '--add', '--cacheinfo', '160000,' + 'a' * 40 + ',src/external')
        self.policy['roles']['src/external'] = {'role': 'vendor', 'owner': 'maintainer', 'description': 'pinned'}
        self.assertEqual(self.inspect(), [])
        self.write('src/external/nested.py', '')
        with self.assertRaisesRegex(ValueError, 'gitlink'):
            checker.entries(self.root, ['src/external/nested.py'], self.policy)

    def test_legacy_static_and_dynamic_references_rejected(self):
        self.write('src/app.py', 'import legacy.old\nimport importlib\nimportlib.import_module("legacy.old")\n')
        findings = self.inspect()
        self.assertTrue({'STR009', 'STR010'} <= {row['rule_id'] for row in findings})

    def test_legacy_requires_retirement_record(self):
        self.write('legacy/old.py', 'raise RuntimeError("do not execute")\n')
        self.run_git('add', 'legacy/old.py')
        self.assertIn('STR008', {row['rule_id'] for row in self.inspect()})
        self.policy['retirement']['legacy/old.py'] = {'source': 'git:abc', 'owner': 'maintainer', 'reason': 'retired', 'last_version': '1'}
        self.assertNotIn('STR008', {row['rule_id'] for row in self.inspect()})

    def test_cross_module_test_ownership_is_supported(self):
        name = 'src/tests/test_contract_pair.py'
        self.write(name, 'import unittest\nclass ContractTest(unittest.TestCase):\n def test_pair(self): self.assertTrue(True)\n')
        self.run_git('add', name)
        self.assertIn('STR006', {row['rule_id'] for row in self.inspect()})
        self.policy['test_ownership'][name] = {'kind': 'contract', 'owner': 'maintainer', 'contract': 'cross-module behavior', 'targets': ['src/app.py']}
        self.assertNotIn('STR006', {row['rule_id'] for row in self.inspect()})
        self.policy['test_ownership'][name]['targets'] = ['src/missing.py']
        self.assertIn('STR006', {row['rule_id'] for row in self.inspect()})

    def test_frozen_legacy_list_does_not_exempt_new_contract_tests(self):
        old = 'src/tests/test_old_contract.py'
        fresh = 'src/tests/test_new_contract.py'
        self.write(old, 'import unittest\nclass A(unittest.TestCase):\n def test_old(self): self.assertTrue(True)\n')
        self.write(fresh, 'import unittest\nclass B(unittest.TestCase):\n def test_new(self): self.assertTrue(True)\n')
        self.run_git('add', old, fresh)
        self.policy['frozen_contract_tests']['paths'] = [old]
        findings = self.inspect()
        self.assertNotIn(old, [row['path'] for row in findings if row['rule_id'] == 'STR006'])
        self.assertIn(fresh, [row['path'] for row in findings if row['rule_id'] == 'STR006'])

    def test_new_unrelated_import_does_not_claim_test_ownership(self):
        name = 'src/tests/test_orphan.py'
        self.write(name, 'import app\nimport unittest\nclass Orphan(unittest.TestCase):\n def test_something(self): self.assertTrue(True)\n')
        self.run_git('add', name)
        self.assertIn('STR006', {row['rule_id'] for row in self.inspect()})

    def test_new_test_without_actual_case_does_not_claim_ownership(self):
        name = 'src/tests/test_app.py'
        self.write(name, 'import app\n')
        self.run_git('add', name)
        self.assertIn('STR006', {row['rule_id'] for row in self.inspect()})

    def test_product_source_directory_cannot_be_disguised_as_vendor(self):
        self.policy['excludes']['src/components'] = {'category': 'vendor', 'owner': 'maintainer', 'reason': 'hide'}
        self.policy['roles']['src/components'] = {'role': 'source', 'owner': 'maintainer', 'description': 'product'}
        with self.assertRaises(ValueError):
            checker.validate_policy(self.policy)

    def test_legacy_package_name_and_resource_path_are_detected(self):
        self.write('src/app.py', 'import src.legacy.old\nfrom src import legacy\nfrom pathlib import Path\nPath("legacy/old.py").read_text()\n')
        findings = self.inspect()
        self.assertTrue({'STR009', 'STR010'} <= {row['rule_id'] for row in findings})

    def test_empty_runtime_directory_is_not_a_source_violation(self):
        self.policy['excludes']['src/data'] = {'category': 'runtime', 'owner': 'maintainer', 'reason': 'generated'}
        (self.root / 'src/data').mkdir()
        self.assertEqual(self.inspect(), [])
        (self.root / 'src/unowned').mkdir()
        self.assertIn('STR002', {row['rule_id'] for row in self.inspect()})

    def test_packaging_and_ignore_rules_required(self):
        self.write('manifest.md', '# No explicit exclusions\n')
        self.write('.gitignore', '# missing\n')
        self.assertTrue({'STR011', 'STR012'} <= {row['rule_id'] for row in self.inspect()})

    def test_check_mode_is_read_only(self):
        policy_path = self.write('policy.json', json.dumps(self.policy))
        record = baseline()
        record['policy_sha256'] = hashlib.sha256(policy_path.read_bytes()).hexdigest()
        base_path = self.write('baseline.json', json.dumps(record))
        before = base_path.read_bytes()
        result = checker.main(['--check', '--root', str(self.root), '--policy', policy_path.name, '--baseline', base_path.name, '--summary'])
        self.assertEqual(result, 0)
        self.assertEqual(base_path.read_bytes(), before)

    def test_real_repository_has_no_new_structure_violations(self):
        repo = ROOT.parent
        config = checker.validate_policy(checker.load_json(ROOT / 'governance/structure.json'))
        candidates = []
        result = subprocess.run(['git', '-C', str(repo), 'ls-files', '--others', '--exclude-standard', '-z'], capture_output=True, timeout=15, check=False)
        self.assertEqual(result.returncode, 0)
        for name in filter(None, result.stdout.decode('utf-8').split('\x00')):
            if not name.startswith('程序/') or checker.excluded(name, config):
                continue
            role = checker.role_for(name, config)
            if role and role['role'] in ('source', 'governance', 'tests', 'docs', 'resources'):
                candidates.append(name)
        findings = checker.check(repo, config, checker.entries(repo, candidates, config))
        policy_path = ROOT / 'governance/structure.json'
        delta = checker.compare(findings, checker.load_json(ROOT / 'governance/structure-baseline.json'),
                                policy_sha256=hashlib.sha256(policy_path.read_bytes()).hexdigest())
        self.assertEqual(delta['added'], [], 'New directory debt: ' + repr(delta['added']))


if __name__ == '__main__':
    unittest.main()
