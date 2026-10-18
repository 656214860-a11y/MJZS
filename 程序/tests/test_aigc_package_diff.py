"""AIGC 包更新核对脚本的临时仓库夹具。"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / '维护记录' / '基准脚本' / 'aigc_package_diff.py'


def _run_git(cwd, *args):
    return subprocess.run(['git', *args], cwd=str(cwd), check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, encoding='utf-8')


class AigcPackageDiffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.program = self.root / 'program'
        self.skills = self.program / 'skills'
        self.package = self.root / 'package'
        self.skills.mkdir(parents=True)
        self.package.mkdir()
        _run_git(self.package, 'init')
        _run_git(self.package, 'config', 'user.name', 'Test')
        _run_git(self.package, 'config', 'user.email', 'test@example.com')

        for rel, text in {
            'engine-one/linked.md': 'linked\n',
            'engine-one/modified.md': 'before\n',
            'engine-one/deleted.md': 'deleted\n',
            'engine-one/old-name.md': 'old\n',
            'engine-two/unlinked.md': 'unlinked\n',
            'assets/ignored.md': 'ignored\n',
        }.items():
            path = self.package / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
        _run_git(self.package, 'add', '.')
        _run_git(self.package, 'commit', '-m', 'baseline')
        self.baseline = _run_git(self.package, 'rev-parse', 'HEAD').stdout.strip()

        self.ownership = self.root / 'ownership.json'
        self.ownership.write_text(json.dumps({
            'schema_version': 1,
            'absorbed_commit': self.baseline,
            '说明': 'fixture',
            'engines': {
                'engine-one': {'role': 'linked', 'stages': ['01'], 'note': ''},
                'engine-two': {'role': 'unlinked', 'stages': [], 'note': '待定'},
                'assets': {'role': 'assets', 'stages': [], 'note': '待定'},
            },
        }, ensure_ascii=False, indent=2), encoding='utf-8')

        skill = self.skills / '01 测试SKILL' / 'demo.skill.md'
        skill.parent.mkdir(parents=True)
        linked = Path(os.path.relpath(self.package / 'engine-one/linked.md', skill.parent)).as_posix()
        deleted = Path(os.path.relpath(self.package / 'engine-one/deleted.md', skill.parent)).as_posix()
        old = Path(os.path.relpath(self.package / 'engine-one/old-name.md', skill.parent)).as_posix()
        skill.write_text('[linked](%s#anchor)\n[deleted](%s#gone)\n[old](%s#old)\n' % (
            linked, deleted, old), encoding='utf-8')
        manifest = self.skills / '00全流程SKILL' / '总控.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({
            'presets': {'fixture': {
                'package': 'skills/00全流程SKILL/AIGC创作全流程/engine-one/linked.md'
            }}
        }, ensure_ascii=False), encoding='utf-8')

        (self.package / 'engine-one/added.md').write_text('added\n', encoding='utf-8')
        (self.package / 'engine-one/modified.md').write_text('after\n', encoding='utf-8')
        (self.package / 'engine-one/deleted.md').unlink()
        _run_git(self.package, 'mv', 'engine-one/old-name.md', 'engine-one/new-name.md')
        _run_git(self.package, 'add', '.')
        _run_git(self.package, 'commit', '-m', 'changes')
        self.head = _run_git(self.package, 'rev-parse', 'HEAD').stdout.strip()

    def tearDown(self):
        self.temp.cleanup()

    def command(self, *args):
        return [sys.executable, '-I', '-B', str(SCRIPT),
                '--package', str(self.package),
                '--ownership', str(self.ownership),
                '--skills-root', str(self.skills), *args]

    def run_script(self, *args):
        return subprocess.run(self.command(*args), cwd=str(self.root),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, encoding='utf-8', check=False)

    def test_diff_statuses_and_rename(self):
        result = self.run_script('--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report['ok'])
        rows = {(row['change'], row['path']): row for row in report['changes']}
        self.assertIn(('A', 'engine-one/added.md'), rows)
        self.assertIn(('M', 'engine-one/modified.md'), rows)
        self.assertIn(('D', 'engine-one/deleted.md'), rows)
        rename = rows[('R', 'engine-one/new-name.md')]
        self.assertEqual(rename['old_path'], 'engine-one/old-name.md')
        self.assertNotIn('assets/ignored.md', {row['path'] for row in report['changes']})

    def test_links_ignore_anchors_and_total_control_path(self):
        result = self.run_script('--json')
        report = json.loads(result.stdout)
        deleted = [row for row in report['broken_links']
                   if row['file'] == 'engine-one/deleted.md'][0]
        self.assertEqual(deleted['linked_by'][0]['stage'], '01')
        linked = [row for row in report['changes']
                  if row['path'] == 'engine-one/added.md'][0]
        self.assertFalse(linked['linked'])

    def test_broken_links_cover_deleted_and_renamed_old_name(self):
        result = self.run_script('--json')
        report = json.loads(result.stdout)
        broken = {row['file']: row for row in report['broken_links']}
        self.assertEqual(broken['engine-one/deleted.md']['reason'], '已删除')
        self.assertEqual(broken['engine-one/old-name.md']['reason'], '已改名')
        self.assertEqual(broken['engine-one/old-name.md']['new_path'],
                         'engine-one/new-name.md')
        self.assertIn('断链风险', self.run_script().stdout)

    def test_unlinked_engine_detection(self):
        result = self.run_script('--json')
        report = json.loads(result.stdout)
        unlinked = {row['engine'] for row in report['unlinked_engines']}
        self.assertIn('engine-two', unlinked)
        self.assertIn('assets', unlinked)
        self.assertNotIn('engine-one', unlinked)

    def test_accept_only_writes_ownership(self):
        before = {}
        for path in self.root.rglob('*'):
            if path.is_file() and path != self.ownership:
                before[path] = hashlib.sha256(path.read_bytes()).hexdigest()
        result = self.run_script('--accept', '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report['accepted'])
        updated = json.loads(self.ownership.read_text(encoding='utf-8'))
        self.assertEqual(updated['absorbed_commit'], self.head)
        after = {}
        for path in self.root.rglob('*'):
            if path.is_file() and path != self.ownership:
                after[path] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(before, after)

    def test_baseline_missing_still_exits_zero(self):
        self.ownership.write_text(json.dumps({'schema_version': 1, 'engines': {}}),
                                  encoding='utf-8')
        result = self.run_script()
        self.assertEqual(result.returncode, 0)
        self.assertIn('absorbed_commit', result.stdout)

    def test_baseline_not_in_history_still_exits_zero(self):
        data = json.loads(self.ownership.read_text(encoding='utf-8'))
        data['absorbed_commit'] = 'f' * 40
        self.ownership.write_text(json.dumps(data), encoding='utf-8')
        result = self.run_script()
        self.assertEqual(result.returncode, 0)
        self.assertIn('不在包的历史中', result.stdout)

    def test_missing_package_still_exits_zero(self):
        result = subprocess.run(
            [sys.executable, '-I', '-B', str(SCRIPT),
             '--package', str(self.root / 'missing'),
             '--ownership', str(self.ownership),
             '--skills-root', str(self.skills)],
            cwd=str(self.root), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', check=False)
        self.assertEqual(result.returncode, 0)
        self.assertIn('包目录不存在', result.stdout)

    def test_baseline_show_and_json_are_machine_readable(self):
        result = self.run_script('--baseline-show', '--json')
        data = json.loads(result.stdout)
        self.assertEqual(data['baseline_commit'], self.baseline)
        self.assertEqual(data['head'], self.head)


if __name__ == '__main__':
    unittest.main()
