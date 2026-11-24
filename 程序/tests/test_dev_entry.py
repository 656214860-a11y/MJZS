"""scripts/dev.py 只是调度表：每个子命令指向的脚本必须真实存在，未知子命令返回 2。

REL-02 追加发布门禁聚合 release_gate 的判定用例：临时目录与假收据造情形，
覆盖收据树不符／日期过旧／缺 NOTICE／版本不一致／CI 收据早于提交／
证书告警不阻断／--run 命令清单（桩）与 dist --release 必须有 --release 实跑证据。
"""
import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))
sys.path.insert(0, str(PROGRAM / 'scripts'))
import dev  # noqa: E402
from scripts import release_gate  # noqa: E402


class DevEntryTests(unittest.TestCase):
    def test_every_command_target_exists(self):
        for name, (target, note) in dev.COMMANDS.items():
            self.assertTrue((PROGRAM / target[0]).is_file(), f'{name} -> {target[0]}')
            self.assertTrue(note)

    def test_unknown_command_is_rejected_and_listing_is_ok(self):
        self.assertEqual(dev.main(['nope']), 2)
        self.assertEqual(dev.main([]), 0)

    def test_claude_md_documents_the_entry(self):
        text = (PROGRAM.parent / 'CLAUDE.md').read_text(encoding='utf-8')
        self.assertIn(r'scripts\dev.py', text)


def _release_gate_env(root):
    """全部阻断项都能通过的最小假环境；所有输入显式注入，不碰真实仓库。"""
    tool = root / 'tool.bin'
    tool.write_bytes(b'tool')
    digest = hashlib.sha256(b'tool').hexdigest()
    now = datetime.now()
    tree = 'a' * 40
    ci_log = '\n'.join([
        '[CI] 开始 %s' % now.strftime('%Y-%m-%d %H:%M:%S'),
        '[CI] === 默认冒烟 ===', '[CI] 默认冒烟 退出码 0，用时 0.1 秒',
        '[CI] === 静态门禁 ===', '[CI] 静态门禁 退出码 0，用时 0.1 秒',
        '[CI] === 架构门禁 ===', '[CI] 架构门禁 退出码 0，用时 0.1 秒',
        '[CI] === 分发自检 ===', '[CI] 分发自检 退出码 0，用时 0.1 秒',
        '[CI] 通过', ''])
    return {
        'program': root, 'now': now, 'commit': 'abc1234',
        'tools_lock': {'tools': {'运行环境/ffmpeg/bin/ffmpeg.exe': {'sha256': digest},
                                 '运行环境/ffmpeg/bin/ffprobe.exe': {'sha256': digest}}},
        'bundle_resolver': lambda _name: tool,
        'ci_log': ci_log,
        'head_time': (now - timedelta(hours=1)).astimezone(),
        'receipts': {'full_safe_verified_trees': [
            {'tree': tree, 'round': 4000, 'seconds': 900.0,
             'at': now.isoformat(timespec='seconds')}]},
        'content_tree': tree,
        'version_text': "VERSION = 'V9.9'\n",
        'changelog': '# 更新记录\n\n## V9.9\n\n- 条目\n',
        'readme': '标题 **V9.9** 说明\n',
        'notice_files': [('NOTICE', 'third-party notices\nMIT License\n')],
        'upgrade_modules': ['test_upgrade_preserve'],
        'cert_status': lambda: (release_gate.PASS, '距到期超过 60 天'),
    }


def _release_gate_item(report, item_id):
    return next(item for item in report['items'] if item['id'] == item_id)


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = _release_gate_env(Path(self.tmp.name))

    def test_release_gate_all_green_is_releasable(self):
        report = release_gate.evaluate(self.env, run=True, runner=lambda _cmd: 0)
        self.assertTrue(report['releasable'], json.dumps(report, ensure_ascii=False))
        self.assertEqual([item['status'] for item in report['items']],
                         [release_gate.PASS] * len(report['items']))

    def test_release_gate_main_exit_zero_and_json_when_releasable(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = release_gate.main(['--run'], env=self.env, runner=lambda _cmd: 0)
        self.assertEqual(code, 0)
        report = json.loads(buffer.getvalue())
        self.assertTrue(report['releasable'])
        self.assertEqual(len(report['items']), 8)
        for item in report['items']:
            self.assertIn(item['status'], (release_gate.PASS, release_gate.FAIL,
                                           release_gate.SKIP, release_gate.WARN))
            self.assertTrue(item['reason'])

    def test_release_gate_receipt_for_other_tree_fails(self):
        self.env['content_tree'] = 'b' * 40
        report = release_gate.evaluate(self.env)
        self.assertEqual(_release_gate_item(report, 'full-safe')['status'], release_gate.FAIL)
        self.assertFalse(report['releasable'])

    def test_release_gate_stale_receipt_date_fails(self):
        old = (self.env['now'] - timedelta(days=30)).isoformat(timespec='seconds')
        self.env['receipts']['full_safe_verified_trees'][0]['at'] = old
        report = release_gate.evaluate(self.env)
        self.assertEqual(_release_gate_item(report, 'full-safe')['status'], release_gate.FAIL)
        self.assertFalse(report['releasable'])

    def test_release_gate_missing_notice_is_not_run_not_pass(self):
        self.env['notice_files'] = []
        report = release_gate.evaluate(self.env)
        self.assertEqual(_release_gate_item(report, 'notice')['status'], release_gate.SKIP)
        self.assertFalse(report['releasable'])

    def test_release_gate_version_mismatch_fails(self):
        self.env['readme'] = '标题 **V9.8** 说明\n'
        report = release_gate.evaluate(self.env)
        item = _release_gate_item(report, 'version-consistency')
        self.assertEqual(item['status'], release_gate.FAIL)
        self.assertIn('V9.8', item['reason'])
        self.assertFalse(report['releasable'])

    def test_release_gate_ci_log_older_than_head_fails(self):
        self.env['head_time'] = (self.env['now'] + timedelta(hours=1)).astimezone()
        report = release_gate.evaluate(self.env)
        self.assertEqual(_release_gate_item(report, 'ci-exit')['status'], release_gate.FAIL)
        self.assertFalse(report['releasable'])

    def test_release_gate_missing_ci_log_is_not_run(self):
        self.env['ci_log'] = None
        report = release_gate.evaluate(self.env)
        self.assertEqual(_release_gate_item(report, 'ci-exit')['status'], release_gate.SKIP)
        self.assertFalse(report['releasable'])

    def test_release_gate_cert_warning_does_not_block(self):
        self.env['cert_status'] = lambda: (release_gate.WARN, '钉死证书 5 天后到期')
        report = release_gate.evaluate(self.env, run=True, runner=lambda _cmd: 0)
        self.assertEqual(_release_gate_item(report, 'cert-expiry')['status'], release_gate.WARN)
        self.assertTrue(report['releasable'])

    def test_release_gate_run_invokes_expected_commands(self):
        calls = []

        def runner(command):
            calls.append(list(command))
            return 0

        report = release_gate.evaluate(self.env, run=True, runner=runner)
        expected = [
            ['scripts/local_ci.py', 'exit'],
            ['run_selftests.py', '--all', '--safe'],
            ['scripts/distribution_selfcheck.py', '--release'],
            ['run_selftests.py', '-k', 'test_upgrade_preserve'],
        ]
        self.assertEqual([command[2:] for command in calls], expected)
        self.assertTrue(report['releasable'])

    def test_release_gate_dist_release_needs_release_flag_receipt(self):
        """卡面第 4 项要 SBOM release_blockers 为空：CI 的「分发自检」不带 --release，不算数。"""
        report = release_gate.evaluate(self.env)
        item = _release_gate_item(report, 'dist-release')
        self.assertEqual(item['status'], release_gate.SKIP)
        self.assertIn('--release', item['reason'])
        self.assertFalse(report['releasable'])

    def test_release_gate_dev_registers_release_gate(self):
        self.assertIn('release-gate', dev.COMMANDS)
        self.assertEqual(dev.COMMANDS['release-gate'][0], ['scripts/release_gate.py'])

    def test_release_gate_detects_upgrade_cases_inside_other_test_files(self):
        """REL-04 用例内嵌在文件名不含 upgrade 的模块里也算落地（现例：test_distribution_build.py）。"""
        tests_dir = Path(self.tmp.name) / 'tests'
        tests_dir.mkdir()
        (tests_dir / 'test_distribution_build.py').write_text(
            'class T:\n    def test_upgrade_preserves_user_data_byte_for_byte(self):\n        pass\n',
            encoding='utf-8')
        (tests_dir / 'test_unrelated.py').write_text(
            'def test_plain():\n    pass\n', encoding='utf-8')
        self.assertEqual(release_gate._upgrade_test_modules(tests_dir),
                         ['test_distribution_build'])


if __name__ == '__main__':
    unittest.main()
