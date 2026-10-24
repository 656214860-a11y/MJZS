"""总控包在线更新（R1996）：检测、按阶段归类、确认后覆盖、失败不动旧包。

全程用临时目录和注入的 ``fetch``，不联网、不碰真实总控包。
"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import desktop_master_update
import master_skill
import master_skill_update as update
import workflow_settings

OLD_SHA, NEW_SHA = 'a' * 40, 'b' * 40
PRESET = {'package': 'skills/x/short-drama-director/SKILL.md',
          'stage_skills': {'storyboard': ['s1'], 'delivery': ['s2']}}


def _zip(files, top='repo-' + NEW_SHA[:7]):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for rel, text in files.items():
            archive.writestr(top + '/' + rel, text)
    return buffer.getvalue()


REMOTE = {
    'README.md': '![v](版本-V1.1.0)\n- **V1.1.0 新增预演故事板**\n- **V1.0.0 初版**\n',
    'short-drama-director/SKILL.md': 'entry\n',
    'sd-storyboard-engine/SKILL.md': 'storyboard v2\n',
    'sd-qc-engine/SKILL.md': 'qc\n',
    'scripts/new.py': 'print(1)\n',
}


class MasterSkillUpdateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.program = Path(tmp.name)
        self.pkg = self.program / 'skills' / 'x'
        old = {'README.md': '![v](版本-V1.0.0)\n- **V1.0.0 初版**\n',
               'short-drama-director/SKILL.md': 'entry\n',
               'sd-storyboard-engine/SKILL.md': 'storyboard v1\n',
               'sd-qc-engine/SKILL.md': 'qc\n', 'legacy.md': 'gone\n'}
        for rel, text in old.items():
            path = self.pkg / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            # qc 用 CRLF 落盘：与远端 LF 内容相同，不能被算成“修改”。
            path.write_bytes(text.replace('\n', '\r\n').encode('utf-8') if rel.startswith('sd-qc') else text.encode('utf-8'))
        for patcher in (mock.patch.object(update, 'package_dir', lambda program=None: self.pkg),
                        mock.patch.dict(workflow_settings.WORKFLOW_PRESETS, {update.PRESET: PRESET}),
                        mock.patch.object(master_skill, 'stage_skill_files', lambda preset, registry=None: {
                            'storyboard': [self.pkg / 'sd-storyboard-engine' / 'SKILL.md'],
                            'delivery': [self.pkg / 'sd-qc-engine' / 'SKILL.md']})):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.remote_zip = _zip(REMOTE)

    def fetch(self, url, limit):
        if url == update.API_COMMITS:
            return json.dumps([{'sha': NEW_SHA, 'commit': {'message': 'feat: V1.1.0\n详情'}},
                               {'sha': OLD_SHA, 'commit': {'message': 'old'}}]).encode('utf-8')
        if url == update.ZIP_URL % NEW_SHA:
            return self.remote_zip
        raise AssertionError(url)

    def check(self):
        return update.check(self.program, fetch=self.fetch)

    def test_check_groups_changes_by_stage(self):
        result = self.check()
        self.assertEqual(result['level'], update.AVAILABLE)
        self.assertEqual((result['old_version'], result['new_version']), ('V1.0.0', 'V1.1.0'))
        self.assertEqual(result['counts'], {'added': 1, 'removed': 1, 'changed': 2})
        self.assertEqual(result['stages'], {'storyboard': ['sd-storyboard-engine/SKILL.md']})
        self.assertIn('README.md', result['common'] + list(result['stages']))  # README 属公共文件
        self.assertTrue(any('V1.1.0' in line for line in result['features']))
        self.assertNotIn('V1.0.0', ''.join(result['features']))
        text = update.describe(result)
        self.assertIn('V1.0.0 → V1.1.0', text)
        self.assertIn('初步分镜', text)
        self.assertNotIn('质检与交付：', text)

    def test_no_difference_records_baseline_without_notice(self):
        self.remote_zip = _zip({rel: ('storyboard v1\n' if 'storyboard' in rel else text)
                                for rel, text in REMOTE.items() if rel != 'scripts/new.py'} | {
            'README.md': '![v](版本-V1.0.0)\n- **V1.0.0 初版**\n', 'legacy.md': 'gone\n'})
        self.assertEqual(self.check()['level'], update.NONE)
        self.assertEqual(update.load_state(self.program)['sha'], NEW_SHA)

    def test_same_recorded_sha_skips_download(self):
        self.check()
        update.save_json(update.state_path(self.program), {'sha': NEW_SHA})
        calls = []
        result = update.check(self.program, fetch=lambda url, limit: calls.append(url) or self.fetch(url, limit))
        self.assertEqual(result['level'], update.NONE)
        self.assertEqual(calls, [update.API_COMMITS])

    def test_apply_swaps_package_and_recycles_old(self):
        result = self.check()
        outcome = update.apply(result, self.program)
        self.assertTrue(outcome['ok'], outcome)
        self.assertEqual((self.pkg / 'sd-storyboard-engine' / 'SKILL.md').read_text(encoding='utf-8'), 'storyboard v2\n')
        self.assertTrue((self.pkg / 'scripts' / 'new.py').is_file())
        self.assertFalse((self.pkg / 'legacy.md').exists())
        self.assertFalse(self.pkg.with_name('x.old').exists())
        self.assertEqual([p.name for p in self.pkg.parent.iterdir() if '.new.' in p.name], [])
        self.assertTrue((self.program / '工作流任务' / '回收站').is_dir())
        self.assertEqual(update.load_state(self.program)['sha'], NEW_SHA)
        self.assertEqual(self.check()['level'], update.NONE)

    def test_apply_without_entry_keeps_old_package(self):
        broken = {rel: text for rel, text in REMOTE.items() if rel != 'short-drama-director/SKILL.md'}
        self.remote_zip = _zip(broken)
        outcome = update.apply(self.check(), self.program)
        self.assertFalse(outcome['ok'])
        self.assertEqual((self.pkg / 'sd-storyboard-engine' / 'SKILL.md').read_text(encoding='utf-8'), 'storyboard v1\n')
        self.assertEqual([p.name for p in self.pkg.parent.iterdir() if '.new.' in p.name], [])
        self.assertNotIn('sha', update.load_state(self.program))

    def test_git_checkout_is_notice_only(self):
        (self.pkg / '.git').write_text('gitdir: ../../.git/modules/x', encoding='utf-8')
        result = self.check()
        self.assertEqual(result['level'], update.AVAILABLE)
        self.assertFalse(result['can_apply'])
        self.assertFalse(update.apply(result, self.program)['ok'])
        self.assertEqual((self.pkg / 'sd-storyboard-engine' / 'SKILL.md').read_text(encoding='utf-8'), 'storyboard v1\n')

    def test_unsafe_archive_path_is_rejected(self):
        self.remote_zip = _zip(dict(REMOTE, **{'../evil.py': 'x'}))
        result = self.check()
        self.assertEqual(result['level'], update.ERROR)
        self.assertFalse((self.program / 'skills' / 'evil.py').exists())

    def test_network_failure_is_reported_not_raised(self):
        def broken(url, limit):
            raise OSError('offline')
        self.assertEqual(update.check(self.program, fetch=broken)['level'], update.ERROR)


class _Status:
    def __init__(self):
        self.text = ''

    def set(self, text):
        self.text = text


class _Notifier:
    def __init__(self):
        self.calls = []

    def info(self, message, title=''):
        self.calls.append(('info', message))

    def warning(self, message, title=''):
        self.calls.append(('warning', message))


class _Host(desktop_master_update.MasterUpdateMixin):
    """不带 Tk 的桌面替身：后台线程改成同步执行。"""
    shutting_down = False

    def __init__(self):
        self.status, self.notifier = _Status(), _Notifier()
        self.win = None

    def _account_background(self, work, done, label):
        done(work())


class ManualCheckTests(unittest.TestCase):
    def run_check(self, result, manual):
        host = _Host()
        with mock.patch.object(update, 'check', lambda *a, **k: result):
            host.start_master_update_check(manual=manual)
        return host

    def test_manual_check_reports_up_to_date(self):
        host = self.run_check({'level': update.NONE}, True)
        self.assertEqual(host.notifier.calls, [('info', '总控包已是最新版本。')])
        self.assertEqual(host.status.text, '总控包已是最新版本。')

    def test_manual_check_reports_failure(self):
        host = self.run_check({'level': update.ERROR, 'reason': 'OSError：offline'}, True)
        self.assertEqual(host.notifier.calls[0][0], 'warning')
        self.assertIn('offline', host.notifier.calls[0][1])

    def test_automatic_check_stays_silent_when_nothing_new(self):
        host = self.run_check({'level': update.NONE}, False)
        self.assertEqual((host.notifier.calls, host.status.text), ([], ''))

    def test_manual_check_shows_notice_for_notice_only_checkout(self):
        result = {'level': update.AVAILABLE, 'can_apply': False, 'blocked_reason': '开发检出', 'counts': {}}
        host = self.run_check(result, True)
        self.assertEqual(host.notifier.calls[0][0], 'info')
        self.assertIn('开发检出', host.status.text)

    def test_busy_flag_is_released_after_check(self):
        host = self.run_check({'level': update.NONE}, True)
        self.assertFalse(host._master_update_busy)


if __name__ == '__main__':
    unittest.main()
