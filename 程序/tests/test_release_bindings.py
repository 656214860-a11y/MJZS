"""U2／U3／U10：发布出口含分发自检、分发清单绑定提交与轮次、迁移回写前留快照。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM / 'scripts'))
import distribution_build  # noqa: E402
import local_ci  # noqa: E402


class ReleaseBindingTests(unittest.TestCase):
    def test_release_mode_adds_selfcheck_after_exit_steps(self):
        self.assertEqual(local_ci.RELEASE_STEPS[:len(local_ci.EXIT_STEPS)], local_ci.EXIT_STEPS)
        self.assertIn('scripts/distribution_selfcheck.py', local_ci.RELEASE_STEPS[-1][1])
        self.assertNotIn('分发自检', [label for label, _ in local_ci.EXIT_STEPS])

    def test_git_binding_reads_commit_and_round(self):
        with tempfile.TemporaryDirectory() as tmp:
            def git(*args):
                subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *args], cwd=tmp,
                               check=True, capture_output=True)
            git('init', '-q')
            Path(tmp, 'a.txt').write_text('x', encoding='utf-8')
            git('add', 'a.txt')
            git('commit', '-q', '-m', 'R2300: 示例')
            info = distribution_build._git_binding(tmp)
        self.assertEqual(info['round'], 2300)
        self.assertRegex(info['commit'], r'^[0-9a-f]{40}$')

    def test_git_binding_is_empty_outside_a_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            info = distribution_build._git_binding(tmp)
        self.assertEqual(info, {'commit': '', 'round': None})

    def test_config_snapshot_ring_keeps_project_config_copy(self):
        """U10 的快照语义由 config_snapshot 承接：写前把现有配置复制进环形槽位。"""
        import config_snapshot
        with tempfile.TemporaryDirectory() as tmp:
            project, program = Path(tmp, '项目'), Path(tmp, 'prog')
            project.mkdir()
            config = project / 'skill_config.json'
            config.write_text('{"a": 1}', encoding='utf-8')
            saved = config_snapshot.keep(config, program / 'data' / 'config_snapshots', 'proj')
            self.assertIsNotNone(saved)
            self.assertEqual(json.loads(saved.read_text(encoding='utf-8')), {'a': 1})
            self.assertEqual(saved.parent, program / 'data' / 'config_snapshots')
            self.assertIsNone(config_snapshot.keep(project / '无.json', program / 'data' / 'config_snapshots', 'proj'))


if __name__ == '__main__':
    unittest.main()
