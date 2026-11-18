# -*- coding: utf-8 -*-
"""O26：白模成果目录可配置、与工具安装目录分离，并在首次配置给出可执行提示。

验收对应（R1267 清单 O26）：无 E 盘、无管理员权限、中文/空格路径、移动安装位置都要
给出可执行提示，不把作品写进程序安装区（Blender 的 Program Files 目录）。
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import white_model_service as wm


class _Result:
    def __init__(self, stdout=b'', returncode=0):
        self.stdout = stdout
        self.returncode = returncode


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for cache in (wm._WORKSPACE_CACHE, wm._SETTINGS_CACHE, wm._VERSION_CACHE, wm._BLENDER_CACHE):
            cache.clear()
            self.addCleanup(cache.clear)

    def env(self, **extra):
        base = {'LOCALAPPDATA': str(self.root), 'MANJU_WHITE_MODEL_SETTINGS': '',
                'MANJU_WHITE_MODEL_WORKSPACE': '', 'MANJU_BLENDER_EXE': ''}
        base.update(extra)
        return patch.dict(os.environ, base)


class WorkspaceResolutionTests(_Base):
    def test_default_workspace_is_a_user_directory_not_the_blender_install(self):
        """默认成果目录在用户数据目录下，不再落在 Blender 安装目录旁（Program Files）。"""
        with self.env():
            expected = (self.root / '漫剧制作助手' / '白模项目').resolve()
            self.assertEqual(wm.default_workspace(), expected)
            self.assertEqual(wm.workspace(), expected)
            self.assertTrue(str(wm.workspace()).startswith(str(self.root)))
            self.assertNotEqual(wm.workspace(), Path('E:/Blender/白模项目'))

    def test_workspace_env_override_wins(self):
        custom = self.root / '自定义 白模 成果'
        with self.env(MANJU_WHITE_MODEL_WORKSPACE=str(custom)):
            self.assertEqual(wm.workspace(), custom.resolve())

    def test_settings_file_can_configure_workspace_and_blender(self):
        settings = self.root / 'settings' / 'white_model_settings.json'
        settings.parent.mkdir(parents=True, exist_ok=True)
        custom = self.root / '成果目录'
        settings.write_text(json.dumps({'workspace': str(custom), 'blender': 'X:/Blender/blender.exe'}),
                            encoding='utf-8')
        with self.env(MANJU_WHITE_MODEL_SETTINGS=str(settings)):
            self.assertEqual(wm.workspace(), custom.resolve())
            self.assertEqual(wm.blender_candidates()[0], Path('X:/Blender/blender.exe'))

    def test_workspace_cache_follows_the_resolved_target(self):
        with self.env(MANJU_WHITE_MODEL_WORKSPACE=str(self.root / 'a')):
            self.assertEqual(wm.workspace(), (self.root / 'a').resolve())
        with self.env(MANJU_WHITE_MODEL_WORKSPACE=str(self.root / 'b')):
            self.assertEqual(wm.workspace(), (self.root / 'b').resolve())


class WriteCheckTests(_Base):
    def test_user_directory_with_chinese_and_spaces_is_writable(self):
        target = self.root / '中文 目录' / '白模 项目'
        ok, reason = wm.write_check(target)
        self.assertTrue(ok, reason)
        self.assertTrue(target.is_dir())
        self.assertEqual(list(target.iterdir()), [])           # 探针文件随即删除

    def test_permission_error_is_reported_with_hint(self):
        with patch.object(Path, 'mkdir', side_effect=PermissionError(13, 'Permission denied')):
            ok, reason = wm.write_check(self.root / 'blocked')
        self.assertFalse(ok)
        self.assertIn('权限', reason)

    def test_missing_drive_is_reported_without_creating(self):
        with patch.object(Path, 'exists', lambda self: False):
            ok, reason = wm.write_check(Path('Z:/nope/白模项目'), create=False)
        self.assertFalse(ok)
        self.assertIn('盘符', reason)

    def test_lightweight_check_uses_nearest_existing_parent(self):
        target = self.root / '尚不存在' / '白模项目'
        ok, reason = wm.write_check(target, create=False)
        self.assertTrue(ok, reason)
        self.assertFalse(target.exists())                      # 轻量检查不建目录


class BlenderVersionTests(_Base):
    def test_reads_version_and_caches_it(self):
        calls = []
        def run(command, **kwargs):
            calls.append(command)
            return _Result(stdout=b'Blender 4.2.0\n\tbuild platform: Windows\n')
        exe = Path('X:/Blender/blender.exe')
        self.assertEqual(wm.blender_version(exe, run=run), '4.2.0')
        self.assertEqual(wm.blender_version(exe, run=run), '4.2.0')
        self.assertEqual(len(calls), 1)

    def test_unreadable_version_returns_empty(self):
        def run(command, **kwargs):
            raise OSError('boom')
        self.assertEqual(wm.blender_version(Path('X:/blender.exe'), run=run), '')

    def test_missing_executable_returns_empty_without_running(self):
        called = []
        def run(command, **kwargs):
            called.append(command); return _Result()
        self.assertEqual(wm.blender_version(None, run=run), '')
        self.assertEqual(called, [])


class BlenderDiscoveryTests(_Base):
    def test_configured_blender_path_wins(self):
        exe = self.root / 'Blender 5.0' / 'blender.exe'
        exe.parent.mkdir(parents=True, exist_ok=True); exe.write_bytes(b'MZ')
        settings = self.root / 'white_model_settings.json'
        settings.write_text(json.dumps({'blender': str(exe)}), encoding='utf-8')
        with self.env(MANJU_WHITE_MODEL_SETTINGS=str(settings)), \
             patch('white_model_service.shutil.which', return_value=None):
            self.assertEqual(wm.find_blender(), exe)

    def test_candidates_have_no_fixed_drive_letter_fallbacks(self):
        """R3320 规则 12：候选清单不再内置 D:/E: 盘符兜底，只来自配置/PATH/Program Files。"""
        exe = self.root / 'tools' / 'blender.exe'
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.write_bytes(b'MZ')
        with self.env(),              patch('white_model_service.shutil.which', return_value=str(exe)),              patch.dict(os.environ, {'ProgramFiles': str(self.root / 'no-pf'),
                                     'ProgramFiles(x86)': str(self.root / 'no-pf-x86')}):
            candidates = wm.blender_candidates()
        self.assertEqual(candidates, [Path(str(exe))])
        self.assertNotIn(Path('D:/Blender/blender.exe'), candidates)
        self.assertNotIn(Path('E:/Blender/blender.exe'), candidates)

    def test_path_discovery_finds_blender_without_drive_letters(self):
        """PATH 上的 blender 照常被探测（不再依赖盘符兜底）。"""
        exe = self.root / 'tools' / 'blender.exe'
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.write_bytes(b'MZ')
        with self.env(),              patch('white_model_service.shutil.which', return_value=str(exe)),              patch.dict(os.environ, {'ProgramFiles': str(self.root / 'no-pf'),
                                     'ProgramFiles(x86)': str(self.root / 'no-pf-x86')}):
            self.assertEqual(wm.find_blender(refresh=True), Path(str(exe)))

    def test_program_files_discovery_finds_blender_without_drive_letters(self):
        """Program Files 下的 Blender Foundation 版本目录照常被 glob 探测。"""
        pf = self.root / 'Program Files'
        exe = pf / 'Blender Foundation' / '4.2' / 'blender.exe'
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.write_bytes(b'MZ')
        with self.env(),              patch('white_model_service.shutil.which', return_value=None),              patch.dict(os.environ, {'ProgramFiles': str(pf),
                                     'ProgramFiles(x86)': str(self.root / 'no-pf-x86')}):
            candidates = wm.blender_candidates()
            self.assertEqual(wm.find_blender(refresh=True), exe)
        self.assertNotIn(Path('D:/Blender/blender.exe'), candidates)
        self.assertNotIn(Path('E:/Blender/blender.exe'), candidates)

    def test_path_scan_runs_once_between_refreshes(self):
        with self.env(), patch('white_model_service.shutil.which', return_value=None) as which:
            wm.find_blender(); wm.find_blender()
        self.assertEqual(which.call_count, 1)


class LegacyWorkspaceTests(_Base):
    def test_old_directory_next_to_blender_is_discovered_read_only(self):
        legacy = self.root / 'D' / 'Blender' / '白模项目'
        legacy.mkdir(parents=True, exist_ok=True)
        exe = self.root / 'D' / 'Blender' / 'blender.exe'
        with patch.object(wm, 'blender_candidates', lambda: [exe]):
            self.assertEqual(wm.legacy_workspaces(self.root / 'current'), [legacy.resolve()])

    def test_current_workspace_is_not_reported_as_legacy(self):
        current = self.root / 'D' / 'Blender' / '白模项目'
        current.mkdir(parents=True, exist_ok=True)
        exe = self.root / 'D' / 'Blender' / 'blender.exe'
        with patch.object(wm, 'blender_candidates', lambda: [exe]):
            self.assertEqual(wm.legacy_workspaces(current), [])


class DiagnoseTests(_Base):
    def test_missing_blender_gives_actionable_hint(self):
        with patch.object(wm, 'blender_candidates', lambda: []):
            report = wm.diagnose(workspace_path=self.root / 'workspace')
        self.assertFalse(report['blender'])
        self.assertIn('未检测到 Blender', report['issues'])
        self.assertTrue(any('blender' in hint for hint in report['hints']))
        self.assertTrue(report['writable'])

    def test_unwritable_workspace_gives_user_directory_hint(self):
        with patch.object(wm, 'blender_candidates', lambda: []), \
             patch.object(wm, 'write_check', lambda path, create=True: (False, '目录不可写：没有写入权限')):
            report = wm.diagnose(blender=Path('X:/blender.exe'), workspace_path=self.root / 'workspace')
        self.assertIn('成果目录不可写', ''.join(report['issues']))
        self.assertTrue(any('workspace' in hint for hint in report['hints']))
        self.assertIn('不可写', wm.diagnose_text(report))

    def test_report_mentions_legacy_directory(self):
        legacy = self.root / 'D' / 'Blender' / '白模项目'
        legacy.mkdir(parents=True, exist_ok=True)
        exe = self.root / 'D' / 'Blender' / 'blender.exe'
        with patch.object(wm, 'blender_candidates', lambda: [exe]):
            report = wm.diagnose(blender=exe, workspace_path=self.root / 'workspace')
        self.assertEqual(report['legacy'], [str(legacy.resolve())])
        self.assertIn(str(legacy.resolve()), wm.diagnose_text(report))

    def test_version_is_reported(self):
        def run(command, **kwargs):
            return _Result(stdout=b'Blender 3.6.5\n')
        with patch.object(wm, 'blender_candidates', lambda: []):
            report = wm.diagnose(blender=Path('X:/blender.exe'), workspace_path=self.root / 'ws', run=run)
        self.assertEqual(report['blender_version'], '3.6.5')
        self.assertIn('3.6.5', wm.diagnose_text(report))


class EnvironmentSummaryTests(_Base):
    def test_summary_names_the_workspace_and_writability(self):
        with self.env(), patch.object(wm, 'blender_candidates', lambda: []):
            text = wm.environment_summary()
        self.assertIn('成果目录', text)
        self.assertIn('可写', text)
        self.assertIn('未检测到 Blender', text)
        self.assertFalse((self.root / '漫剧制作助手').exists())   # 轻量检查不建目录


if __name__ == '__main__':
    unittest.main()