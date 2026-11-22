# -*- coding: utf-8 -*-
"""合入前预览开发工具（scripts/preview_app.py）的用例：只用临时目录，不开真实预览窗口。"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

PROGRAM = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
sys.path.insert(0, str(PROGRAM / 'scripts'))
from skip_reasons import PLATFORM_TK_DISPLAY  # noqa: E402
import tk_test_support  # noqa: E402
import tkinter as tk  # noqa: E402
import preview_app  # noqa: E402

TEMP_INSIDE_WORKTREE = preview_app._worktree_root(Path(tempfile.gettempdir())) is not None


def setUpModule():
    print('[preview_app 测试] tempfile.gettempdir()=%s；落在 git 工作树内=%s'
          % (tempfile.gettempdir(), TEMP_INSIDE_WORKTREE))


def _out_of_worktree():
    """系统临时目录落在工作树内时，屏蔽「不能放在代码仓库里」一条，只测其余规则。"""
    if TEMP_INSIDE_WORKTREE:
        return mock.patch.object(preview_app, '_worktree_root', return_value=None)
    return contextlib.nullcontext()


class DefaultDataDirTests(unittest.TestCase):
    def test_branch_name_is_sanitized(self):
        expected = Path(tempfile.gettempdir()) / 'manju-preview' / 'codex-dev-preview'
        self.assertEqual(preview_app.default_data_dir('codex/dev-preview'), expected)


class CheckDataDirTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)

    def test_missing_directory_is_accepted(self):
        with _out_of_worktree():
            target = self.base / '不存在' / '预览数据'
            self.assertEqual(preview_app.check_data_dir(target), target.resolve())

    def test_empty_directory_is_accepted(self):
        with _out_of_worktree():
            self.assertEqual(preview_app.check_data_dir(self.base), self.base.resolve())

    def test_marked_nonempty_directory_is_accepted(self):
        (self.base / preview_app.MARKER).write_text('mark', encoding='utf-8')
        (self.base / '旧数据').mkdir()
        with _out_of_worktree():
            self.assertEqual(preview_app.check_data_dir(self.base), self.base.resolve())

    def test_nonempty_without_marker_is_rejected(self):
        (self.base / '别人的文件.txt').write_text('x', encoding='utf-8')
        with _out_of_worktree(), self.assertRaisesRegex(ValueError, '不是预览工具建的目录'):
            preview_app.check_data_dir(self.base)

    def test_file_path_is_rejected(self):
        file_path = self.base / '只是个文件'
        file_path.write_text('x', encoding='utf-8')
        with _out_of_worktree(), self.assertRaises(ValueError):
            preview_app.check_data_dir(file_path)

    def test_path_inside_worktree_is_rejected_without_writes(self):
        with self.assertRaisesRegex(ValueError, '不能放在代码仓库里'):
            preview_app.check_data_dir(PROGRAM)
        ghost = PROGRAM / '预览不存在的子目录'
        with self.assertRaisesRegex(ValueError, '不能放在代码仓库里'):
            preview_app.check_data_dir(ghost)
        self.assertFalse(ghost.exists())
        self.assertFalse((PROGRAM / preview_app.MARKER).exists())
        self.assertFalse((PROGRAM / 'app').exists())


class BuildSampleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.data = Path(temporary.name) / 'data'

    def test_builds_minimal_app_data(self):
        with _out_of_worktree():
            built = preview_app.build_sample(self.data)
        app, project = built['app'], built['project']
        self.assertTrue((self.data / preview_app.MARKER).is_file())
        self.assertTrue((app / 'config.json').is_file())
        self.assertTrue((app / 'projects.json').is_file())
        self.assertTrue((app / 'desktop_settings.json').is_file())
        info = json.loads((app / 'projects.json').read_text(encoding='utf-8'))
        self.assertEqual(info['active'], str(project))
        self.assertTrue(project.is_dir())
        self.assertTrue((project / '01剧本准备' / '输入').is_dir())
        self.assertFalse((app / 'private').exists())
        self.assertFalse((self.data / 'private').exists())

    def test_second_call_keeps_projects_json_and_refreshes_choice(self):
        with _out_of_worktree():
            built = preview_app.build_sample(self.data)
            projects_file = built['app'] / 'projects.json'
            info = json.loads(projects_file.read_text(encoding='utf-8'))
            info['custom_flag'] = 'keep'
            projects_file.write_text(json.dumps(info, ensure_ascii=False), encoding='utf-8')
            rebuilt = preview_app.build_sample(self.data)
            self.assertEqual(json.loads(projects_file.read_text(encoding='utf-8'))['custom_flag'], 'keep')
            settings = json.loads((built['app'] / 'desktop_settings.json').read_text(encoding='utf-8'))
            self.assertEqual(settings['project_choice_day'], date.today().isoformat())
            self.assertEqual(settings['project_choice_path'], info['active'])
            self.assertEqual(rebuilt['project'], Path(info['active']))

    def test_existing_data_pointing_outside_is_refused(self):
        """已建过的数据再用之前要复查：项目库位置丢了、指到外面，或登记了数据目录之外的项目，都不带着继续开。"""
        outside = self.data.parent / '数据目录之外的项目'
        outside.mkdir()
        with _out_of_worktree():
            built = preview_app.build_sample(self.data)
            config_file, projects_file = built['app'] / 'config.json', built['app'] / 'projects.json'
            good_config = config_file.read_text(encoding='utf-8')
            good_projects = projects_file.read_text(encoding='utf-8')
            for broken in ({}, {'downloads_root': str(outside)}):
                with self.subTest(config=broken):
                    config_file.write_text(json.dumps(broken, ensure_ascii=False), encoding='utf-8')
                    with self.assertRaisesRegex(ValueError, 'downloads_root'):
                        preview_app.build_sample(self.data)
            config_file.write_text(good_config, encoding='utf-8')
            listed = json.loads(good_projects)
            listed['projects'].append({'name': '外面的项目', 'path': str(outside)})
            activated = dict(json.loads(good_projects), active=str(outside))
            for broken in (listed, activated):
                with self.subTest(projects=broken):
                    projects_file.write_text(json.dumps(broken, ensure_ascii=False), encoding='utf-8')
                    with self.assertRaisesRegex(ValueError, '登记的项目'):
                        preview_app.build_sample(self.data)
            projects_file.write_text(good_projects, encoding='utf-8')
            self.assertEqual(preview_app.build_sample(self.data)['app'], built['app'])


USER_ENV = ('LOCALAPPDATA', 'APPDATA', 'USERPROFILE')


class IsolateUserEnvTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.data = Path(temporary.name) / 'data'
        # patch.dict 退出时把整个环境还原，用例不会把改指后的取值留给同进程的其他测试。
        patcher = mock.patch.dict(os.environ, {
            'CODEX_HOME': str(Path(temporary.name) / '真实的助手目录'),
            'CLAUDE_CONFIG_DIR': str(Path(temporary.name) / '真实的配置目录'),
            'PREVIEW_CANARY_API_KEY': 'canary', 'PREVIEW_CANARY_TOKEN': 'canary',
            'PREVIEW_CANARY_PLAIN': 'keep'})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_user_level_folders_point_into_the_data_dir(self):
        before = {name: os.environ.get(name) for name in USER_ENV}
        values = preview_app.isolate_user_env(self.data)
        user = self.data / 'user'
        for name in USER_ENV + ('HOME',):
            with self.subTest(name=name):
                current = Path(os.environ[name])
                self.assertEqual(os.environ[name], values[name])
                self.assertTrue(current.is_dir())
                self.assertTrue(current == user or user in current.parents,
                                name + ' 没有落在预览数据目录里：' + str(current))
                self.assertNotEqual(os.environ[name], before.get(name))
        self.assertEqual(Path.home(), user)
        self.assertEqual(Path(os.path.expanduser('~')), user)

    def test_config_overrides_and_credential_like_variables_are_dropped(self):
        dropped = ('CODEX_HOME', 'CLAUDE_CONFIG_DIR', 'PREVIEW_CANARY_API_KEY', 'PREVIEW_CANARY_TOKEN')
        for name in dropped:
            self.assertIn(name, os.environ)
        preview_app.isolate_user_env(self.data)
        for name in dropped:
            with self.subTest(name=name):
                self.assertNotIn(name, os.environ)
        self.assertEqual(os.environ.get('PREVIEW_CANARY_PLAIN'), 'keep')
        self.assertIn('PATH', os.environ)


class BlockRegistryTests(unittest.TestCase):
    def test_bound_references_report_no_registry_and_can_be_restored(self):
        program = str(PROGRAM)
        if program not in sys.path:
            sys.path.insert(0, program)
        import contract.platform_tools as platform_tools
        from infra import account_store          # 模块顶层就绑定了入口函数：先导入，验证「已绑定的引用也换掉」
        from ui.pet_ui_support import Autostart
        original = platform_tools.windows_registry
        self.assertIs(account_store.windows_registry, original)
        restore = preview_app.block_registry()
        self.addCleanup(restore)
        self.assertIsNone(platform_tools.windows_registry())
        self.assertIsNone(account_store.windows_registry())
        self.assertFalse(account_store.clock_backup_available(), '登录时钟基线不得再读写注册表')
        self.assertFalse(Autostart().available, '开机自启在预览里必须是「不可用」')
        home = Path(tempfile.gettempdir()) / '预览的主目录'
        with mock.patch.object(Path, 'home', return_value=home):
            self.assertEqual(platform_tools.downloads_directory(), home / 'Downloads')
        restore()
        self.assertIs(platform_tools.windows_registry, original)
        self.assertIs(account_store.windows_registry, original)


class BlockExitCleanupTests(unittest.TestCase):
    def test_close_time_cleanup_is_replaced_and_can_be_restored(self):
        program = str(PROGRAM)
        if program not in sys.path:
            sys.path.insert(0, program)
        import orchestrator.exit_maintenance as exit_maintenance
        original = exit_maintenance.launch_cleanup
        restore = preview_app.block_exit_cleanup()
        self.addCleanup(restore)
        with mock.patch('infra.storage_maintenance.launch_cleanup') as storage, \
                mock.patch('infra.log_maintenance.launch_cleanup') as logs, \
                mock.patch('infra.workspace_maintenance.launch_cleanup') as workspace, \
                contextlib.redirect_stdout(io.StringIO()) as printed:
            result = exit_maintenance.launch_cleanup(PROGRAM, forced=False, temporary_projects=('某个项目',))
        for launcher in (storage, logs, workspace):
            launcher.assert_not_called()
        self.assertEqual(set(result.values()), {'preview-disabled'})
        self.assertIn('关窗清理已关闭', printed.getvalue())
        restore()
        self.assertIs(exit_maintenance.launch_cleanup, original)


class LinkedWorktreeTests(unittest.TestCase):
    def test_only_a_lane_counts(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            lane = base / '车道' / '程序'
            lane.mkdir(parents=True)
            (base / '车道' / '.git').write_text('gitdir: 别处\n', encoding='utf-8')
            trunk = base / '主工作区' / '程序'
            trunk.mkdir(parents=True)
            (base / '主工作区' / '.git').mkdir()
            self.assertTrue(preview_app.in_linked_worktree(lane))
            self.assertFalse(preview_app.in_linked_worktree(trunk))
            with mock.patch.object(preview_app, '_worktree_root', return_value=None):
                self.assertFalse(preview_app.in_linked_worktree(lane), '不在任何仓库里也不算车道')


class MainTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.data = Path(temporary.name) / '预览数据'

    def test_print_only_builds_and_returns_zero(self):
        with _out_of_worktree():
            code = preview_app.main(['--data', str(self.data), '--print-only'])
        self.assertEqual(code, 0)
        self.assertTrue((self.data / 'app' / 'projects.json').is_file())

    def test_print_only_leaves_the_environment_alone(self):
        watched = USER_ENV + ('HOME', 'HOMEDRIVE', 'HOMEPATH')
        before = {name: os.environ.get(name) for name in watched}
        with _out_of_worktree():
            self.assertEqual(preview_app.main(['--data', str(self.data), '--print-only']), 0)
        self.assertEqual({name: os.environ.get(name) for name in watched}, before)
        self.assertFalse((self.data / 'user').exists())

    def test_window_path_isolates_user_folders_before_opening(self):
        seen = {}

        class _Window:
            def mainloop(self):
                seen['looped'] = True

        def fake_open(app_dir, label):
            seen['app'] = Path(app_dir)
            seen['env'] = {name: os.environ.get(name) for name in USER_ENV}
            seen['home'] = Path.home()
            seen['registry_blocked'] = blocked.called
            seen['cleanup_blocked'] = cleanup_blocked.called
            return _Window(), None

        real = {name: os.environ.get(name) for name in USER_ENV}
        with _out_of_worktree(), mock.patch.dict(os.environ), \
                mock.patch.object(preview_app, 'in_linked_worktree', return_value=True), \
                mock.patch.object(preview_app, 'block_registry') as blocked, \
                mock.patch.object(preview_app, 'block_exit_cleanup') as cleanup_blocked, \
                mock.patch.object(preview_app, 'open_window', side_effect=fake_open):
            code = preview_app.main(['--data', str(self.data)])
        self.assertEqual(code, 0)
        self.assertTrue(seen.get('looped'))
        self.assertTrue(seen['registry_blocked'], '注册表入口要在开窗口之前换掉')
        self.assertTrue(seen['cleanup_blocked'], '关窗清理要在开窗口之前关掉')
        user = self.data.resolve() / 'user'
        self.assertEqual(seen['app'], self.data.resolve() / 'app')
        for name, value in seen['env'].items():
            with self.subTest(name=name):
                self.assertNotEqual(value, real[name], '打开窗口时 ' + name + ' 还指着真实的用户目录')
                self.assertTrue(Path(value) == user or user in Path(value).parents,
                                name + ' 没有落在预览数据目录里：' + str(value))
        self.assertEqual(seen['home'], user)
        self.assertEqual({name: os.environ.get(name) for name in USER_ENV}, real)

    def test_window_is_refused_outside_a_lane(self):
        """主工作区的代码目录里放着正式应用的数据：不在车道里就不开窗口，也不建数据、不改环境。"""
        before = {name: os.environ.get(name) for name in USER_ENV}
        with _out_of_worktree(), mock.patch.object(preview_app, 'in_linked_worktree', return_value=False), \
                mock.patch.object(preview_app, 'block_registry') as blocked, \
                mock.patch.object(preview_app, 'open_window') as opened:
            self.assertEqual(preview_app.main(['--data', str(self.data)]), 2)
        opened.assert_not_called()
        blocked.assert_not_called()
        self.assertFalse(self.data.exists())
        self.assertEqual({name: os.environ.get(name) for name in USER_ENV}, before)

    def test_window_is_refused_when_existing_data_points_outside(self):
        with _out_of_worktree():
            self.assertEqual(preview_app.main(['--data', str(self.data), '--print-only']), 0)
            (self.data / 'app' / 'config.json').write_text('{}', encoding='utf-8')
            before = {name: os.environ.get(name) for name in USER_ENV}
            with mock.patch.object(preview_app, 'in_linked_worktree', return_value=True), \
                    mock.patch.object(preview_app, 'open_window') as opened:
                self.assertEqual(preview_app.main(['--data', str(self.data)]), 2)
        opened.assert_not_called()
        self.assertEqual({name: os.environ.get(name) for name in USER_ENV}, before)

    def test_print_only_still_works_outside_a_lane(self):
        with _out_of_worktree(), mock.patch.object(preview_app, 'in_linked_worktree', return_value=False):
            self.assertEqual(preview_app.main(['--data', str(self.data), '--print-only']), 0)
        self.assertTrue((self.data / 'app' / 'projects.json').is_file())

    def test_copying_a_real_project_is_not_offered(self):
        """真实项目的配置里记着指向原项目的绝对路径；没有路径改写之前，这个选项不能悄悄加回来。"""
        source = self.data.parent / '源项目'
        source.mkdir()
        with _out_of_worktree(), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            preview_app.main(['--data', str(self.data), '--copy-project', str(source), '--print-only'])
        self.assertFalse(self.data.exists())

    def test_program_dir_is_refused_without_writes(self):
        self.assertEqual(preview_app.main(['--data', str(PROGRAM), '--print-only']), 2)
        self.assertFalse((PROGRAM / preview_app.MARKER).exists())
        self.assertFalse((PROGRAM / 'app').exists())

    def test_reset_removes_marked_directory(self):
        with _out_of_worktree():
            self.assertEqual(preview_app.main(['--data', str(self.data), '--print-only']), 0)
            self.assertEqual(preview_app.main(['--data', str(self.data), '--reset']), 0)
            self.assertFalse(self.data.exists())

    def test_reset_refuses_unmarked_nonempty_directory(self):
        self.data.mkdir()
        (self.data / '别人的文件.txt').write_text('x', encoding='utf-8')
        with _out_of_worktree():
            self.assertEqual(preview_app.main(['--data', str(self.data), '--reset']), 2)
        self.assertTrue((self.data / '别人的文件.txt').exists())

    def test_reset_refuses_empty_unmarked_directory(self):
        self.data.mkdir()
        with _out_of_worktree():
            self.assertEqual(preview_app.main(['--data', str(self.data), '--reset']), 2)
        self.assertTrue(self.data.exists())

    def test_reset_missing_directory_returns_zero(self):
        with _out_of_worktree():
            self.assertEqual(preview_app.main(['--data', str(self.data), '--reset']), 0)


# 子进程里照 main 的顺序走一遍：建数据 → 改指用户级目录 → 换掉注册表入口 → 关掉关窗清理 → 开窗 → 按应用自己的
# 关窗路径关闭。关窗期间用审计钩子盯着：谁想起进程就记一笔并拦下（关窗清理没关掉时，这里会记到清理进程）。
# 参数：tests 目录、scripts 目录、数据目录、系统临时目录是否落在工作树内（是则屏蔽「不能放在代码仓库里」一条）。
ISOLATED_WINDOW_SCRIPT = r'''
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2])
import preview_app
import tk_test_support
if sys.argv[4] == '1':
    preview_app._worktree_root = lambda path: None
launched, closing = [], []


def watch(event, args):
    if event == 'subprocess.Popen' and closing:
        launched.append(str(args[1]))
        raise OSError('预览窗口关闭时不该起任何进程')


sys.addaudithook(watch)
built = preview_app.build_sample(Path(sys.argv[3]))
preview_app.isolate_user_env(built['app'].parent)
preview_app.block_registry()
preview_app.block_exit_cleanup()
window, desktop = preview_app.open_window(built['app'], 'child')
try:
    tk_test_support.pump(window, 1.5)
    sys.stdout.write('TITLE=' + window.title() + '\n')
    sys.stdout.write('HOME=' + str(Path.home()) + '\n')
    waited = 0.0
    while desktop.busy_reason() and waited < 20:
        tk_test_support.pump(window, 0.5)
        waited += 0.5
    sys.stdout.write('BUSY=' + desktop.busy_reason() + '\n')
    if not desktop.busy_reason():
        closing.append(True)
        desktop.close()
finally:
    sys.stdout.write('LAUNCHES=%d\n' % len(launched))
    try:
        alive = bool(window.winfo_exists())
    except Exception:
        alive = False
    sys.stdout.write('CLOSED=' + ('no' if alive else 'by-app') + '\n')
    if alive:
        desktop.cancel_timers()
        window.destroy()
'''


class PreviewWindowTests(unittest.TestCase):
    def test_isolated_window_starts_and_closes_in_a_child_process(self):
        """隔离之后真起一次窗再关掉（放在子进程里，不改本进程的环境）。

        用户级目录改指、注册表入口换掉以后应用仍能启动；按应用自己的关窗路径关闭时，走到的是预览换上的空操作，
        没有任何进程被起起来（应用原本会在这时另起项目库清理等后台进程）。
        """
        with tempfile.TemporaryDirectory(prefix='preview-app-') as temporary:
            data = Path(temporary) / 'data'
            done = subprocess.run(
                [sys.executable, '-B', '-c', ISOLATED_WINDOW_SCRIPT, str(TESTS), str(PROGRAM / 'scripts'),
                 str(data), '1' if TEMP_INSIDE_WORKTREE else '0'],
                cwd=str(PROGRAM), env=dict(os.environ, PYTHONIOENCODING='utf-8'), capture_output=True,
                text=True, encoding='utf-8', errors='replace', timeout=240)
            if done.returncode != 0 and 'TclError' in done.stderr:
                raise unittest.SkipTest(PLATFORM_TK_DISPLAY + ': ' + done.stderr.strip().splitlines()[-1])
            self.assertEqual(done.returncode, 0, done.stderr[-2000:])
            user = data.resolve() / 'user'
            self.assertIn('TITLE=' + preview_app.TITLE_PREFIX + 'child · ', done.stdout)
            self.assertIn('HOME=' + str(user) + '\n', done.stdout)
            self.assertTrue((user / 'AppData' / 'Local').is_dir())
            self.assertIn('BUSY=\n', done.stdout, '示例项目起来后不该有拦着关窗的任务：' + done.stdout[-600:])
            self.assertIn('LAUNCHES=0\n', done.stdout, '关窗期间起了进程：' + done.stdout[-600:])
            self.assertIn('CLOSED=by-app\n', done.stdout, '窗口没有按应用自己的关窗路径关掉')
            self.assertIn('关窗清理已关闭', done.stdout, '关窗没有走到预览换上的空操作')

    def test_window_title_carries_preview_prefix(self):
        with tempfile.TemporaryDirectory(prefix='preview-app-') as temporary:
            data = Path(temporary) / 'data'
            with _out_of_worktree():
                built = preview_app.build_sample(data)
                try:
                    window, desktop = preview_app.open_window(built['app'], '测试分支')
                except tk.TclError as exc:
                    raise unittest.SkipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))
            try:
                tk_test_support.pump(window, 1.5)
                self.assertTrue(
                    window.title().startswith(preview_app.TITLE_PREFIX + '测试分支 · '),
                    '窗口标题须带预览前缀，实际：' + window.title())
            finally:
                desktop.cancel_timers()
                try:
                    window.destroy()
                except tk.TclError:
                    pass


if __name__ == '__main__':
    unittest.main()
