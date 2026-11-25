# -*- coding: utf-8 -*-
"""REL-04B：Inno Setup 安装脚本静态守卫与构建入口测试（全部使用临时目录与假 ISCC）。"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROGRAM = Path(__file__).resolve().parents[1]
SCRIPTS = PROGRAM / 'scripts'
for folder in (str(SCRIPTS), str(PROGRAM)):
    if folder not in sys.path:
        sys.path.insert(0, folder)

from contract import app_metadata  # noqa: E402
import distribution_build  # noqa: E402
import installer_build  # noqa: E402


FAKE_MANIFEST_MD = """# 测试分发清单

## 必须保留

| 路径/模式 | 原因 |
| --- | --- |
| `启动漫剧制作助手.pyw` | 入口 |
| `漫剧制作助手.ico` | 图标 |
| `运行环境/Python/` | 随附解释器 |
| `程序/app.py` | 主程序 |
| `程序/requirements.txt` | 依赖锁 |
| `程序/voice_engine/` | 离线语音锁 |
| `程序/data/skill_note_terms_zh.json` | 随包术语表 |
| `程序/配置/客户端档案.json`、`程序/配置/SKILL/预设.json` | 默认配置种子 |

## 必须排除

| 路径/模式 | 分类 | 原因 |
| --- | --- | --- |
| `程序/distribution_manifest.md` | 开发文档 | 不入包 |
| `程序/external_tools.lock.json` | 治理 | 不入包 |
| `程序/维护记录/**` | 开发记录 | 不入包 |
| `程序/private/**` | 私有 | 不入包 |
"""


def _make_fake_repo(root: Path) -> Path:
    """在临时目录构造可通过 distribution_build.build + verify 的最小假仓库。"""
    files = {
        '启动漫剧制作助手.pyw': 'print("ok")\n',
        '漫剧制作助手.ico': 'ICO',
        '运行环境/Python/python.exe': 'exe',
        '程序/app.py': 'APP = 1\n',
        '程序/requirements.txt': 'requests==2.34.2\n',
        '程序/voice_engine/requirements.lock': 'numpy==1.26.4\n',
        '程序/voice_engine/supply_chain.lock.json': json.dumps({
            'source_template': 'https://pypi.org/project/{name}/{version}/',
            'licenses': {'numpy': 'BSD-3-Clause'},
        }),
        '程序/external_tools.lock.json': json.dumps({
            'tools': {
                '运行环境/Python/python.exe': {
                    'version': 'Python fixture',
                    'sha256': 'a' * 64,
                    'bytes': 3,
                    'source': 'https://python.org/',
                    'license': 'PSF-2.0',
                }
            }
        }),
        '程序/维护记录/外部技能包哈希.json': json.dumps({'packages': {}}),
        '程序/data/skill_note_terms_zh.json': '{"terms": []}\n',
        '程序/配置/客户端档案.json': '{}\n',
        '程序/配置/SKILL/预设.json': '{}\n',
        '程序/distribution_manifest.md': FAKE_MANIFEST_MD,
        '程序/private/secret.txt': 'do-not-ship',
    }
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
    return root


class InstallerScriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def _copy_iss(self, transform=None) -> Path:
        text = installer_build.DEFAULT_ISS.read_text(encoding='utf-8-sig')
        if transform is not None:
            text = transform(text)
        target = self.base / '漫剧制作助手.iss'
        target.write_text(text, encoding='utf-8-sig')
        return target

    def _run_build_with_fake_iscc(self) -> tuple[int, str, list[str], dict]:
        fake_repo = _make_fake_repo(self.base / 'repo')
        fake_bin = self.base / 'bin'
        fake_bin.mkdir(parents=True, exist_ok=True)
        fake_iscc = fake_bin / 'ISCC.exe'
        fake_iscc.write_bytes(b'MZ-fake-iscc')
        dest = self.base / 'out_release'

        captured_cmd: list[str] = []
        observed: dict = {}

        def fake_subprocess_run(cmd, *args, **kwargs):
            if cmd and Path(cmd[0]).name.lower() == 'iscc.exe':
                captured_cmd.extend(str(part) for part in cmd)
                source_dir = None
                out_dir = None
                version_val = None
                for arg in captured_cmd[1:]:
                    if arg.startswith('/DSourceDir='):
                        source_dir = Path(arg.split('=', 1)[1])
                    elif arg.startswith('/O'):
                        out_dir = Path(arg[2:])
                    elif arg.startswith('/DAppVersion='):
                        version_val = arg.split('=', 1)[1]
                observed['source_dir'] = source_dir
                observed['digest_exists'] = bool(
                    source_dir and (source_dir / distribution_build.DIGEST_NAME).is_file()
                )
                observed['version_val'] = version_val
                if out_dir is not None:
                    out_dir.mkdir(parents=True, exist_ok=True)
                    exe_path = out_dir / f'漫剧助手-{version_val}.exe'
                    exe_path.write_bytes(b'FAKE-SETUP-BINARY-PAYLOAD')
                    observed['payload_sha256'] = hashlib.sha256(b'FAKE-SETUP-BINARY-PAYLOAD').hexdigest()
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='Compiled OK\n', stderr='')
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout='', stderr='')

        fake_env = {
            'PATH': str(fake_bin),
            'LOCALAPPDATA': '',
            'ProgramFiles(x86)': '',
            'ProgramFiles': '',
        }
        buf = io.StringIO()
        with mock.patch.dict(os.environ, fake_env, clear=True):
            with mock.patch.object(installer_build.subprocess, 'run', side_effect=fake_subprocess_run):
                with contextlib.redirect_stdout(buf):
                    code = installer_build.main([
                        '--build',
                        '--root', str(fake_repo),
                        '--destination', str(dest),
                    ])
        observed['dest'] = dest
        return code, buf.getvalue(), captured_cmd, observed

    def test_1_default_iss_passes_static_check_and_missing_iss_exits_1(self):
        missing = self.base / 'missing.iss'
        buf_miss = io.StringIO()
        with contextlib.redirect_stdout(buf_miss):
            code_miss = installer_build.main(['--check', '--iss', str(missing)])
        self.assertEqual(code_miss, 1, buf_miss.getvalue())

        buf_ok = io.StringIO()
        with contextlib.redirect_stdout(buf_ok):
            code_ok = installer_build.main(['--check'])
        self.assertEqual(code_ok, 0, buf_ok.getvalue())
        self.assertIn(app_metadata.VERSION, buf_ok.getvalue())

    def test_2_missing_config_json_exclude_fails_with_line_and_name(self):
        iss_copy = self._copy_iss(lambda t: t.replace('config.json,', ''))
        files_line = next(
            idx for idx, line in enumerate(iss_copy.read_text(encoding='utf-8-sig').splitlines(), start=1)
            if installer_build.WHOLE_DIR_SOURCE in line
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = installer_build.main(['--check', '--iss', str(iss_copy)])
        output = buf.getvalue()
        self.assertEqual(code, 1, output)
        self.assertIn('config.json', output)
        self.assertIn(f'第 {files_line} 行', output)

    def test_3_inserted_uninstall_delete_section_fails(self):
        iss_copy = self._copy_iss(
            lambda t: t + '\n[UninstallDelete]\nType: files; Name: "{app}\\程序\\config.json"\n'
        )
        lines = iss_copy.read_text(encoding='utf-8-sig').splitlines()
        bad_line = next(idx for idx, line in enumerate(lines, start=1) if line.strip() == '[UninstallDelete]')
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = installer_build.main(['--check', '--iss', str(iss_copy)])
        output = buf.getvalue()
        self.assertEqual(code, 1, output)
        self.assertIn('UninstallDelete', output)
        self.assertIn(f'第 {bad_line} 行', output)

    def test_4_build_without_iscc_exits_2_and_creates_no_dest(self):
        dest = self.base / '发行包_不应创建'
        empty_env = {
            'PATH': '',
            'LOCALAPPDATA': '',
            'ProgramFiles(x86)': '',
            'ProgramFiles': '',
        }
        buf = io.StringIO()
        with mock.patch.dict(os.environ, empty_env, clear=True):
            with contextlib.redirect_stdout(buf):
                code = installer_build.main(['--build', '--destination', str(dest)])
        output = buf.getvalue()
        self.assertEqual(code, 2, output)
        self.assertIn('本机未安装 Inno Setup 6', output)
        self.assertFalse(dest.exists(), '找不到 ISCC 时不得创建发行包目录')

    def test_5_build_with_fake_iscc_runs_verify_and_passes_defines(self):
        code, output, cmd, observed = self._run_build_with_fake_iscc()
        self.assertEqual(code, 0, output)
        self.assertIn(f'/DAppVersion={app_metadata.VERSION}', cmd)
        self.assertTrue(any(arg.startswith('/DSourceDir=') for arg in cmd), cmd)
        self.assertTrue(observed.get('digest_exists'), 'ISCC 调用前 SourceDir 下必须已有 分发清单.json')
        expected_exe = observed['dest'] / f'漫剧助手-{app_metadata.VERSION}.exe'
        self.assertTrue(expected_exe.is_file(), f'产物未复制到目标目录：{expected_exe}')
        self.assertIn(observed['payload_sha256'], output)

    def test_6_build_version_matches_contract_app_metadata(self):
        code, output, _cmd, observed = self._run_build_with_fake_iscc()
        self.assertEqual(code, 0, output)
        self.assertEqual(observed.get('version_val'), app_metadata.VERSION)
        self.assertEqual(installer_build.app_version(), app_metadata.VERSION)

    def test_7_signtool_unguarded_and_appversion_hardcode_rejected(self):
        bad_sign = self._copy_iss(
            lambda t: t.replace('#ifdef Signed\n', '').replace('#endif\n', '', 1)
        )
        errors_sign = installer_build.check_iss(bad_sign)
        self.assertTrue(any('SignTool' in err and '#ifdef Signed' in err for err in errors_sign), errors_sign)

        bad_ver = self._copy_iss(lambda t: t.replace('AppVersion={#AppVersion}', 'AppVersion=V0.7'))
        errors_ver = installer_build.check_iss(bad_ver)
        self.assertTrue(any('AppVersion' in err for err in errors_ver), errors_ver)


if __name__ == '__main__':
    unittest.main()
