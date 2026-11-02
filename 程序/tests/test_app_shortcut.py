# -*- coding: utf-8 -*-
"""第 21 期：桌面图标与快捷方式（app_shortcut）——纯标准库可验，不碰真的 WScript。运行：python test_app_shortcut.py"""
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import app_icon
import app_shortcut


class PsTextTests(unittest.TestCase):
    def test_every_char_becomes_a_code(self):
        self.assertEqual(app_shortcut.ps_text('米多'), '(-join ([char[]]@(0x7C73, 0x591A)))')

    def test_the_result_is_pure_ascii(self):
        for value in ('三虎', 'D:\\漫剧制作助手\\启动漫剧制作助手.pyw', 'a b'):
            with self.subTest(value=value):
                self.assertTrue(all(ord(ch) < 128 for ch in app_shortcut.ps_text(value)))

    def test_an_empty_string_is_still_well_formed(self):
        self.assertEqual(app_shortcut.ps_text(''), '(-join ([char[]]@()))')

    def test_a_number_is_tolerated(self):
        self.assertEqual(app_shortcut.ps_text(12), '(-join ([char[]]@(0x31, 0x32)))')

    def test_non_windows_does_not_probe_for_powershell(self):
        with mock.patch.object(app_shortcut.os, 'name', 'posix'):
            self.assertIsNone(app_shortcut.powershell())


class ScriptTests(unittest.TestCase):
    def payload(self):
        return app_shortcut.script('C:\\桌面\\x.lnk', 'D:\\py\\pythonw.exe',
                                   '-I "D:\\启动.pyw"', 'D:\\根', 'D:\\图.ico', '说明')

    def test_the_script_is_pure_ascii(self):
        self.assertTrue(all(ord(ch) < 128 for ch in self.payload()))

    def test_every_shortcut_property_is_assigned(self):
        body = self.payload()
        for name in ('TargetPath', 'Arguments', 'WorkingDirectory', 'IconLocation', 'Description'):
            with self.subTest(name=name):
                self.assertIn('$lnk.%s = ' % name, body)
        self.assertIn('$lnk.Save()', body)
        self.assertIn('WScript.Shell', body)

    def test_the_chinese_paths_are_spelled_out_not_written_plain(self):
        body = self.payload()
        self.assertNotIn('桌面', body)
        self.assertIn(app_shortcut.ps_text('C:\\桌面\\x.lnk'), body)

    def test_a_blank_description_falls_back_to_the_name(self):
        body = app_shortcut.script('C:\\x.lnk', 'D:\\p.exe', '', 'D:\\根', 'D:\\图.ico')
        self.assertIn(app_shortcut.ps_text(app_shortcut.NAME), body)


class LayoutTests(unittest.TestCase):
    """自带的目录长什么样：根目录放启动器与设计图，程序目录在下面一层。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.program = self.root / '程序'
        self.program.mkdir()
        (self.root / app_shortcut.LAUNCHER).write_text('x', encoding='utf-8')
        self.icon = self.root / app_shortcut.ICON_NAME

    def test_root_dir_is_the_parent_of_the_program_folder(self):
        self.assertEqual(app_shortcut.root_dir(self.program), self.root)

    def test_the_launcher_sits_in_the_root_not_the_program_folder(self):
        self.assertEqual(app_shortcut.launcher_path(self.program),
                         self.root / app_shortcut.LAUNCHER)

    def test_runner_points_at_the_bundled_interpreter_and_the_root_launcher(self):
        pythonw = self.root / '运行环境' / 'Python' / 'pythonw.exe'
        pythonw.parent.mkdir(parents=True)
        pythonw.write_bytes(b'')
        exe, arguments, workdir = app_shortcut.runner(self.program)
        self.assertEqual(exe, pythonw)
        self.assertEqual(arguments, '-I "%s"' % (self.root / app_shortcut.LAUNCHER))
        self.assertEqual(workdir, self.root, '工作目录要落在根目录，启动器才找得到程序')

    def test_a_missing_interpreter_falls_back_to_this_python(self):
        exe, _arguments, _workdir = app_shortcut.runner(self.program)
        self.assertEqual(exe, Path(sys.executable))

    def test_a_missing_launcher_leaves_the_arguments_empty(self):
        (self.root / app_shortcut.LAUNCHER).unlink()
        _exe, arguments, _workdir = app_shortcut.runner(self.program)
        self.assertEqual(arguments, '')

    def test_the_designed_icon_wins_over_the_computed_one(self):
        self.icon.write_bytes(b'ico')
        self.assertEqual(app_shortcut.icon_file(self.program), self.icon)

    def test_without_the_designed_icon_the_computed_one_is_used(self):
        self.assertEqual(app_shortcut.icon_file(self.program), app_icon.icon_path())

    def test_the_desktop_folder_is_a_path(self):
        self.assertIsInstance(app_shortcut.desktop_dir(), Path)

    def test_install_icon_copies_the_computed_one_into_the_root(self):
        """第 25 期：快捷方式认的是根目录那张设计图——重画之后要复制过去。"""
        source = self.root / 'src.ico'
        source.write_bytes(b'ico-bytes')
        with mock.patch.object(app_shortcut.app_icon, 'ensure', return_value=source):
            made = app_shortcut.install_icon(self.program)
        self.assertEqual(made, self.icon)
        self.assertEqual(self.icon.read_bytes(), b'ico-bytes')

    def test_install_icon_is_quiet_when_there_is_nothing_to_copy(self):
        with mock.patch.object(app_shortcut.app_icon, 'ensure', return_value=None):
            self.assertIsNone(app_shortcut.install_icon(self.program))

    def test_the_digest_follows_the_content(self):
        """第 26 期第 9 条：指纹只跟内容走——同一份图永远同一个名字。"""
        self.assertEqual(app_shortcut.icon_digest(b'x'), app_shortcut.icon_digest(b'x'))
        self.assertNotEqual(app_shortcut.icon_digest(b'x'), app_shortcut.icon_digest(b'y'))
        self.assertEqual(len(app_shortcut.icon_digest(b'x')), 8)

    def test_the_icon_is_written_under_a_content_tagged_name_too(self):
        """同名文件换了内容，资源管理器拿缓存照样画旧图——所以再写一份带指纹的。"""
        source = self.root / 'src.ico'
        source.write_bytes(b'ico-bytes')
        with mock.patch.object(app_shortcut.app_icon, 'ensure', return_value=source):
            app_shortcut.install_icon(self.program)
        tagged = self.root / app_shortcut.tagged_icon_name(b'ico-bytes')
        self.assertTrue(tagged.is_file(), '带指纹的那份要写出来')
        self.assertEqual(tagged.read_bytes(), b'ico-bytes')
        self.assertEqual(app_shortcut.icon_file(self.program), tagged,
                         '快捷方式要指向带指纹的那张，路径一变缓存就失效')

    def test_a_new_icon_drops_the_old_fingerprint(self):
        first, second = self.root / 'a.ico', self.root / 'b.ico'
        first.write_bytes(b'one')
        second.write_bytes(b'two')
        with mock.patch.object(app_shortcut.app_icon, 'ensure', return_value=first):
            app_shortcut.install_icon(self.program)
        older = self.root / app_shortcut.tagged_icon_name(b'one')
        self.assertTrue(older.is_file())
        with mock.patch.object(app_shortcut.app_icon, 'ensure', return_value=second):
            app_shortcut.install_icon(self.program)
        self.assertFalse(older.is_file(), '旧指纹那一份留着没用')
        self.assertTrue((self.root / app_shortcut.tagged_icon_name(b'two')).is_file())

    def test_refresh_shell_answers_with_a_yes_or_no(self):
        self.assertIn(app_shortcut.refresh_shell(), (True, False))


class FakeShell(object):
    """替下 subprocess：记下跑过的脚本，按需把 .lnk 造出来。"""

    PIPE = object()
    DEVNULL = object()

    def __init__(self, link=None, make_link=True, code=0):
        self.link = link
        self.make_link = make_link
        self.code = code
        self.scripts = []
        self.calls = []

    def run(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        script_path = Path(cmd[cmd.index('-File') + 1])
        self.scripts.append(script_path.read_bytes())
        if self.make_link and self.code == 0 and self.link is not None:
            Path(self.link).write_bytes(b'lnk')
        return types.SimpleNamespace(returncode=self.code)


class MakeShortcutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.link = self.base / '桌面' / (app_shortcut.NAME + '.lnk')

    def patched(self, shell, fake):
        return mock.patch.multiple(app_shortcut,
                                   powershell=mock.Mock(return_value=shell),
                                   subprocess=fake)

    def test_a_shortcut_is_written_and_the_script_is_ascii(self):
        fake = FakeShell(self.link)
        with self.patched('powershell.exe', fake):
            made = app_shortcut.make_shortcut(self.link, 'D:\\py\\pythonw.exe',
                                              '-I "D:\\启动.pyw"', 'D:\\根', 'D:\\图.ico')
        self.assertEqual(made, self.link)
        self.assertTrue(self.link.is_file())
        self.assertEqual(len(fake.scripts), 1)
        self.assertTrue(all(byte < 128 for byte in fake.scripts[0]))

    def test_the_parent_folder_is_created_for_us(self):
        fake = FakeShell(self.link)
        with self.patched('powershell.exe', fake):
            app_shortcut.make_shortcut(self.link, 'x')
        self.assertTrue(self.link.parent.is_dir())

    def test_no_powershell_means_no_shortcut_and_no_crash(self):
        with mock.patch.object(app_shortcut, 'powershell', return_value=None):
            self.assertIsNone(app_shortcut.make_shortcut(self.link, 'x'))

    def test_a_failed_shell_reports_none(self):
        fake = FakeShell(self.link, code=1)
        with self.patched('powershell.exe', fake):
            self.assertIsNone(app_shortcut.make_shortcut(self.link, 'x'))

    def test_a_shell_that_writes_nothing_reports_none(self):
        fake = FakeShell(self.link, make_link=False)
        with self.patched('powershell.exe', fake):
            self.assertIsNone(app_shortcut.make_shortcut(self.link, 'x'))

    def test_the_temporary_script_is_cleaned_up(self):
        fake = FakeShell(self.link)
        with self.patched('powershell.exe', fake):
            app_shortcut.make_shortcut(self.link, 'x')
        script_path = fake.calls[0][-1]
        self.assertTrue(script_path.endswith('.ps1'))
        self.assertFalse(os.path.exists(script_path))


class EnsureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / '根'
        self.program = self.root / '程序'
        self.program.mkdir(parents=True)
        (self.root / app_shortcut.LAUNCHER).write_text('x', encoding='utf-8')
        self.icon_home = self.base / 'icons'
        patcher = mock.patch.object(app_shortcut, 'ICON_HOME', self.icon_home)
        patcher.start()
        self.addCleanup(patcher.stop)

    def writer(self, seen):
        def fake(link, target, arguments='', workdir=None, icon=None, description=''):
            seen.append((Path(link), target, arguments, workdir, icon, description))
            Path(link).parent.mkdir(parents=True, exist_ok=True)
            Path(link).write_bytes(b'lnk')
            return Path(link)
        return fake

    def test_only_the_root_folder_gets_a_shortcut(self):
        seen = []
        with mock.patch.object(app_shortcut, 'make_shortcut', side_effect=self.writer(seen)):
            made = app_shortcut.ensure(program=self.program)
        self.assertEqual([path.parent for path in made], [self.root])
        self.assertEqual(len(seen), 1)
        self.assertEqual({row[2] for row in seen},
                         {'-I "%s"' % (self.root / app_shortcut.LAUNCHER)})
        self.assertEqual({row[3] for row in seen}, {str(self.root)})

    def test_the_name_and_the_design_icon_are_used(self):
        icon = self.root / app_shortcut.ICON_NAME
        icon.write_bytes(b'ico')
        seen = []
        with mock.patch.object(app_shortcut, 'make_shortcut', side_effect=self.writer(seen)):
            app_shortcut.ensure(program=self.program)
        self.assertEqual({row[0].name for row in seen}, {app_shortcut.NAME + '.lnk'})
        # 中文路径的图标资源管理器画不出来：快捷方式指向复制到英文目录、内容相同的那一份
        [used] = {row[4] for row in seen}
        self.assertEqual(Path(used).parent, self.icon_home)
        self.assertEqual(Path(used).read_bytes(), b'ico')

    def test_the_script_stamps_the_window_app_id_on_the_link(self):
        body = app_shortcut.script('C:/x.lnk', 'D:/p.exe', '', 'D:/r', 'D:/i.ico')
        self.assertIn('[LinkAppId]::Set(', body)
        self.assertIn(app_shortcut.ps_text(app_icon.APP_ID), body)
        self.assertTrue(body.isascii())

    def test_an_ascii_icon_path_is_used_as_is(self):
        icon = Path('C:/plain/app.ico')
        self.assertEqual(app_shortcut.shell_icon(icon, self.icon_home), icon)

    def test_a_non_ascii_icon_is_copied_with_a_content_tag(self):
        icon = self.root / app_shortcut.ICON_NAME
        icon.write_bytes(b'first')
        first = app_shortcut.shell_icon(icon, self.icon_home)
        icon.write_bytes(b'second')
        second = app_shortcut.shell_icon(icon, self.icon_home)
        self.assertNotEqual(first, second, '换了图就换文件名，绕开图标缓存')
        self.assertEqual(second.read_bytes(), b'second')

    def test_an_unreadable_icon_falls_back_to_the_original_path(self):
        missing = self.root / '不存在.ico'
        self.assertEqual(app_shortcut.shell_icon(missing, self.icon_home), missing)

    def test_a_folder_that_cannot_be_written_yields_nothing(self):
        with mock.patch.object(app_shortcut, 'make_shortcut', return_value=None):
            made = app_shortcut.ensure(program=self.program)
        self.assertEqual(made, [])

    def test_main_says_why_when_nothing_could_be_built(self):
        with mock.patch.object(app_shortcut, 'ensure', return_value=[]):
            self.assertEqual(app_shortcut.main(), [])

    def test_main_installs_the_icon_and_refreshes_the_shell(self):
        with mock.patch.object(app_shortcut, 'install_icon', return_value=Path('x.ico')) as icon:
            with mock.patch.object(app_shortcut, 'ensure', return_value=[]) as make:
                with mock.patch.object(app_shortcut, 'refresh_shell', return_value=True) as moved:
                    self.assertEqual(app_shortcut.main(), [])
        self.assertTrue(icon.called, '换图标这一步得走')
        self.assertTrue(moved.called, '换完要让资源管理器重画')
        self.assertTrue(make.called)

    def test_a_missing_design_icon_is_healed_on_ensure(self):
        """设计图被删了（重装／误删）也要能自己补回来，否则快捷方式就成了白板。"""
        self.assertFalse((self.root / app_shortcut.ICON_NAME).is_file())
        with mock.patch.object(app_shortcut, 'install_icon', return_value=self.root / app_shortcut.ICON_NAME) as heal:
            with mock.patch.object(app_shortcut, 'make_shortcut', side_effect=self.writer([])):
                app_shortcut.ensure(program=self.program)
        self.assertTrue(heal.called, '缺了就补一张')

    def test_an_existing_design_icon_is_left_alone(self):
        icon = self.root / app_shortcut.ICON_NAME
        icon.write_bytes(b'ico')
        with mock.patch.object(app_shortcut, 'install_icon') as heal:
            with mock.patch.object(app_shortcut, 'make_shortcut', side_effect=self.writer([])):
                app_shortcut.ensure(program=self.program)
        self.assertFalse(heal.called, '有一张就不动它（用户自己换过的图别给人盖掉）')


class ShellTests(unittest.TestCase):
    def test_powershell_is_either_a_command_or_none(self):
        found = app_shortcut.powershell()
        self.assertTrue(found is None or isinstance(found, str))


if __name__ == '__main__':
    unittest.main()
