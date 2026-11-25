r"""Inno Setup 安装脚本静态守卫与个人通道单文件安装包构建入口（REL-04B）。

默认 ``--check`` 模式纯静态解析 ``scripts/installer/漫剧制作助手.iss``，不依赖
Inno Setup、不联网、不写任何文件；``--build`` 模式先经 ``distribution_build``
在临时目录构建并校验正式分发副本，再调用本机 ``ISCC.exe`` 编译安装包并复制到
``--destination``（默认仓库根上一级的 ``发行包\``，不落进仓库）。

用法（随附解释器，在 程序\ 下）::

    python.exe -B scripts\installer_build.py --check
    python.exe -B scripts\installer_build.py --build
    python.exe -B scripts\installer_build.py --build --destination D:\out\发行包
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

PROGRAM = Path(__file__).resolve().parents[1]
ROOT = PROGRAM.parent
DEFAULT_ISS = PROGRAM / 'scripts' / 'installer' / '漫剧制作助手.iss'
DEFAULT_DESTINATION = ROOT.parent / '发行包'

NO_ISCC_EXIT = 2
NO_ISCC_MESSAGE = '本机未安装 Inno Setup 6，无法编译安装包；请用户安装后重跑'

APPID_GUID_RE = re.compile(
    r'^\{\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}$'
)
SECTION_RE = re.compile(r'^\[([^\]]+)\]\s*(?:;.*)?$')
FORBIDDEN_SECTIONS = frozenset({'installdelete', 'uninstalldelete'})

REQUIRED_SETUP = (
    ('AppName', '漫剧制作助手', True),
    ('AppVersion', '{#AppVersion}', True),
    ('DefaultDirName', r'{localappdata}\漫剧制作助手', True),
    ('PrivilegesRequired', 'lowest', False),
    ('WizardStyle', 'modern dark', False),
    ('Compression', 'lzma2', False),
    ('SolidCompression', 'yes', False),
    ('CloseApplications', 'yes', False),
    ('RestartApplications', 'no', False),
)

REQUIRED_DEV_EXCLUDES = (
    r'.git\*',
    r'__pycache__\*',
    '*.pyc',
)
REQUIRED_USER_DATA_EXCLUDES = (
    'config.json',
    'desktop_settings.json',
    'projects.json',
    r'private\*',
    r'data\*',
    r'配置\*',
    'app.log*',
    r'tasks_round\evidence\*',
)
REQUIRED_EXCLUDES = REQUIRED_DEV_EXCLUDES + REQUIRED_USER_DATA_EXCLUDES

WHOLE_DIR_SOURCE = r'{#SourceDir}\*'
SKILL_TERMS_SOURCE = r'{#SourceDir}\程序\data\skill_note_terms_zh.json'
SKILL_TERMS_DESTDIR = r'{app}\程序\data'
LAUNCHER_REF = r'{app}\启动漫剧制作助手.pyw'

PROTECTED_USER_ITEMS = (
    'config.json',
    'desktop_settings.json',
    'projects.json',
    'private',
    'data',
    '配置',
)

try:
    from scripts import distribution_build
except ImportError:  # direct ``python scripts/installer_build.py``
    import distribution_build


def app_version() -> str:
    """从唯一权威源 contract.app_metadata.VERSION 读取版本号。"""
    if str(PROGRAM) not in sys.path:
        sys.path.insert(0, str(PROGRAM))
    from contract.app_metadata import VERSION
    return str(VERSION)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_params(line: str) -> dict[str, str]:
    """解析 Inno Setup 分号分隔的 ``Key: Value`` 行（尊重双引号与转义双引号）。"""
    parts: list[str] = []
    buf: list[str] = []
    in_quote = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '"':
            if in_quote and i + 1 < len(line) and line[i + 1] == '"':
                buf.append('"')
                i += 2
                continue
            in_quote = not in_quote
            buf.append(ch)
        elif ch == ';' and not in_quote:
            parts.append(''.join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    if buf:
        parts.append(''.join(buf))

    params: dict[str, str] = {}
    for item in parts:
        chunk = item.strip()
        if not chunk or ':' not in chunk:
            continue
        key, val = chunk.split(':', 1)
        val = val.strip()
        if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
            val = val[1:-1]
        params[key.strip().lower()] = val
    return params


def _in_signed_guard(pp_stack: list[tuple[str, bool]]) -> bool:
    return any(kind == 'ifdef' and is_signed for kind, is_signed in pp_stack)


def _handle_preprocessor(lineno: int, stripped: str, pp_stack: list[tuple[str, bool]],
                         errors: list[str]) -> None:
    lower = stripped.lower()
    if lower.startswith('#ifdef'):
        ident = stripped[6:].strip().split()[0] if stripped[6:].strip() else ''
        pp_stack.append(('ifdef', ident == 'Signed'))
    elif lower.startswith('#ifndef'):
        pp_stack.append(('ifndef', False))
    elif lower.startswith('#if'):
        pp_stack.append(('if', False))
    elif lower.startswith('#else'):
        if pp_stack:
            kind, _ = pp_stack[-1]
            pp_stack[-1] = (kind, False)
        else:
            errors.append(f'第 {lineno} 行：多余的 #else')
    elif lower.startswith('#endif'):
        if pp_stack:
            pp_stack.pop()
        else:
            errors.append(f'第 {lineno} 行：多余的 #endif')
    elif re.match(r'^#define\s+AppVersion\b', stripped, re.IGNORECASE):
        errors.append(f'第 {lineno} 行：禁止在 .iss 内 #define AppVersion，必须由 /DAppVersion 传入')


def _parse_iss(text: str) -> tuple[dict, list[str]]:
    """逐行扫描 .iss 文本，返回结构化记录与词法/预处理级错误列表。"""
    errors: list[str] = []
    pp_stack: list[tuple[str, bool]] = []
    section: str | None = None
    section_lines: dict[str, int] = {}
    setup: dict[str, tuple[int, str, str]] = {}
    files_rows: list[tuple[int, dict[str, str]]] = []
    icons_rows: list[tuple[int, dict[str, str]]] = []
    run_rows: list[tuple[int, dict[str, str]]] = []
    code_rows: list[tuple[int, str]] = []
    signed_tools: list[tuple[int, str]] = []

    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith('#'):
            _handle_preprocessor(lineno, stripped, pp_stack, errors)
            continue
        sec_match = SECTION_RE.match(stripped)
        if sec_match:
            sec_name = sec_match.group(1).strip()
            section = sec_name.lower()
            section_lines.setdefault(section, lineno)
            if section in FORBIDDEN_SECTIONS:
                errors.append(f'第 {lineno} 行：禁止出现 [{sec_name}] 段（不得在安装/卸载段删除用户数据）')
            continue
        if section == 'code':
            code_rows.append((lineno, raw))
            continue
        if stripped.startswith(';'):
            continue

        # 任何非注释行里若出现 AppVersion，只能是 [Setup] 的 AppVersion={#AppVersion} 或 {#AppVersion}
        if 'appversion' in stripped.lower():
            without_macro = stripped.replace('{#AppVersion}', '')
            if not (section == 'setup' and re.fullmatch(r'AppVersion\s*=\s*', without_macro, re.IGNORECASE)):
                if 'appversion' in without_macro.lower():
                    errors.append(f'第 {lineno} 行：AppVersion 只允许以 {{#AppVersion}} 出现')

        if section == 'setup':
            if '=' not in stripped:
                continue
            key, val = (part.strip() for part in stripped.split('=', 1))
            key_low = key.lower()
            if key_low.startswith('signtool') or key_low == 'signeduninstaller':
                if not _in_signed_guard(pp_stack):
                    errors.append(f'第 {lineno} 行：{key} 必须包在 #ifdef Signed … #endif 之间')
                else:
                    signed_tools.append((lineno, key))
            setup[key_low] = (lineno, key, val)
        elif section == 'files':
            files_rows.append((lineno, _parse_params(stripped)))
        elif section == 'icons':
            icons_rows.append((lineno, _parse_params(stripped)))
        elif section == 'run':
            run_rows.append((lineno, _parse_params(stripped)))
        else:
            if re.match(r'^SignTool\b', stripped, re.IGNORECASE) and not _in_signed_guard(pp_stack):
                errors.append(f'第 {lineno} 行：SignTool 必须包在 #ifdef Signed … #endif 之间')

    if pp_stack:
        errors.append('第 0 行：存在未闭合的 #ifdef/#ifndef/#if 预处理块')

    parsed = {
        'section_lines': section_lines,
        'setup': setup,
        'files': files_rows,
        'icons': icons_rows,
        'run': run_rows,
        'code': code_rows,
        'signed_tools': signed_tools,
    }
    return parsed, errors


def _check_setup(parsed: dict, errors: list[str]) -> None:
    setup = parsed['setup']
    setup_line = parsed['section_lines'].get('setup', 0)
    if setup_line == 0:
        errors.append('第 0 行：缺少 [Setup] 段')
        return

    appid = setup.get('appid')
    if not appid:
        errors.append(f'第 {setup_line} 行：[Setup] 缺少固定 GUID 的 AppId')
    elif not APPID_GUID_RE.match(appid[2]):
        errors.append(f'第 {appid[0]} 行：AppId 必须为 Inno Setup 固定 GUID 格式 {{{{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}}，实际为 {appid[2]!r}')

    for key, expected, case_sensitive in REQUIRED_SETUP:
        entry = setup.get(key.lower())
        if not entry:
            errors.append(f'第 {setup_line} 行：[Setup] 缺少 {key}={expected}')
            continue
        actual = entry[2]
        matched = (actual == expected) if case_sensitive else (actual.lower() == expected.lower())
        if not matched:
            errors.append(f'第 {entry[0]} 行：[Setup] {key} 应为 {expected!r}，实际为 {actual!r}')

    if not any(key.lower() == 'signtool' for _, key in parsed['signed_tools']):
        errors.append(f'第 {setup_line} 行：[Setup] 缺少包在 #ifdef Signed … #endif 内的 SignTool 预留行')


def _check_files(parsed: dict, errors: list[str]) -> None:
    files_line = parsed['section_lines'].get('files', 0)
    if files_line == 0:
        errors.append('第 0 行：缺少 [Files] 段')
        return

    whole_line = None
    whole_params = None
    terms_line = None
    terms_params = None
    for lineno, params in parsed['files']:
        source = params.get('source', '')
        if source == WHOLE_DIR_SOURCE and whole_line is None:
            whole_line, whole_params = lineno, params
        elif source == SKILL_TERMS_SOURCE:
            terms_line, terms_params = lineno, params

    if whole_line is None or whole_params is None:
        errors.append(f'第 {files_line} 行：[Files] 缺少整目录行 Source: "{WHOLE_DIR_SOURCE}"')
    else:
        if whole_params.get('destdir', '') != '{app}':
            errors.append(f'第 {whole_line} 行：[Files] 整目录行 DestDir 应为 "{{app}}"')
        flags = {tok.lower() for tok in whole_params.get('flags', '').split()}
        for required_flag in ('ignoreversion', 'recursesubdirs', 'createallsubdirs'):
            if required_flag not in flags:
                errors.append(f'第 {whole_line} 行：[Files] 整目录行 Flags 缺少 {required_flag}')
        excludes = {item.strip() for item in whole_params.get('excludes', '').split(',') if item.strip()}
        for pattern in REQUIRED_EXCLUDES:
            if pattern not in excludes:
                errors.append(f'第 {whole_line} 行：[Files] 整目录行 Excludes 缺少必须排除项 "{pattern}"')

    if terms_line is None or terms_params is None:
        errors.append(f'第 {files_line} 行：[Files] 缺少随包覆盖行 Source: "{SKILL_TERMS_SOURCE}"')
    else:
        if whole_line is not None and terms_line <= whole_line:
            errors.append(f'第 {terms_line} 行：skill_note_terms_zh.json 放回行必须位于整目录行（第 {whole_line} 行）之后')
        if terms_params.get('destdir', '') != SKILL_TERMS_DESTDIR:
            errors.append(f'第 {terms_line} 行：skill_note_terms_zh.json 的 DestDir 应为 "{SKILL_TERMS_DESTDIR}"')
        terms_flags = {tok.lower() for tok in terms_params.get('flags', '').split()}
        if 'ignoreversion' not in terms_flags:
            errors.append(f'第 {terms_line} 行：skill_note_terms_zh.json 放回行 Flags 缺少 ignoreversion')


def _check_icons_and_run(parsed: dict, errors: list[str]) -> None:
    icons_line = parsed['section_lines'].get('icons', 0)
    if icons_line == 0:
        errors.append('第 0 行：缺少 [Icons] 段')
    else:
        has_desktop = False
        has_programs = False
        for lineno, params in parsed['icons']:
            name = params.get('name', '').lower()
            target_blob = params.get('filename', '') + ' ' + params.get('parameters', '')
            if LAUNCHER_REF not in target_blob:
                errors.append(f'第 {lineno} 行：[Icons] 快捷方式必须指向 {LAUNCHER_REF}')
            if params.get('workingdir', '') != '{app}':
                errors.append(f'第 {lineno} 行：[Icons] WorkingDir 必须为 "{{app}}"')
            if '{autodesktop}' in name or '{userdesktop}' in name:
                has_desktop = True
            if '{autoprograms}' in name or '{group}' in name:
                has_programs = True
        if not has_desktop:
            errors.append(f'第 {icons_line} 行：[Icons] 缺少桌面快捷方式')
        if not has_programs:
            errors.append(f'第 {icons_line} 行：[Icons] 缺少开始菜单快捷方式')

    run_line = parsed['section_lines'].get('run', 0)
    if run_line == 0:
        errors.append('第 0 行：缺少 [Run] 段')
    else:
        matched_run = False
        for _, params in parsed['run']:
            flags = {tok.lower() for tok in params.get('flags', '').split()}
            if 'postinstall' in flags and '启动漫剧制作助手' in params.get('description', ''):
                matched_run = True
        if not matched_run:
            errors.append(f'第 {run_line} 行：[Run] 缺少带 postinstall 标志的「启动漫剧制作助手」勾选项')


def _check_code(parsed: dict, errors: list[str]) -> None:
    code_line = parsed['section_lines'].get('code', 0)
    if code_line == 0:
        errors.append('第 0 行：缺少 [Code] 段（需要升级前用户数据备份与卸载保留配置提示）')
        return
    code_text = '\n'.join(line for _, line in parsed['code'])
    if '_upgrade_backup' not in code_text:
        errors.append(f'第 {code_line} 行：[Code] 缺少升级前备份目录 _upgrade_backup')
    if 'filecopy(' not in code_text.lower():
        errors.append(f'第 {code_line} 行：[Code] 升级前备份必须使用 FileCopy 只复制不移动')
    if 'msgbox(' not in code_text.lower():
        errors.append(f'第 {code_line} 行：[Code] 缺少备份失败或卸载保留配置的 MsgBox 提示')
    if 'curuninstallstepchanged' not in code_text.lower():
        errors.append(f'第 {code_line} 行：[Code] 缺少卸载保留配置回调 CurUninstallStepChanged')
    for lineno, line in parsed['code']:
        stripped = line.strip()
        if stripped.startswith('//'):
            continue
        low = stripped.lower()
        if 'deltree(' in low or 'deletefile(' in low or 'renamefile(' in low:
            for item in PROTECTED_USER_ITEMS:
                if item in stripped:
                    errors.append(f'第 {lineno} 行：[Code] 禁止删除或移动用户数据 "{item}"')


def check_iss(iss_path: Path | str = DEFAULT_ISS) -> list[str]:
    """静态检查 .iss 脚本是否满足 REL-04B 契约；返回错误清单（空为通过）。"""
    path = Path(iss_path)
    if not path.is_file():
        return [f'第 0 行：找不到安装脚本文件 {path}']
    text = path.read_text(encoding='utf-8-sig')
    parsed, errors = _parse_iss(text)
    _check_setup(parsed, errors)
    _check_files(parsed, errors)
    _check_icons_and_run(parsed, errors)
    _check_code(parsed, errors)
    return errors


def find_iscc(env=None) -> Path | None:
    """按 PATH → %LOCALAPPDATA% → Program Files (x86) → Program Files 查找 ISCC.exe。"""
    env_map = os.environ if env is None else env
    path_var = env_map.get('PATH') or env_map.get('Path') or ''
    if path_var:
        for name in ('ISCC.exe', 'ISCC'):
            found = shutil.which(name, path=path_var)
            if found and Path(found).is_file():
                return Path(found).resolve()
    candidates: list[Path] = []
    local_app = env_map.get('LOCALAPPDATA', '')
    if local_app:
        candidates.append(Path(local_app) / 'Programs' / 'Inno Setup 6' / 'ISCC.exe')
    for key in ('ProgramFiles(x86)', 'ProgramFiles'):
        base = env_map.get(key, '')
        if base:
            candidates.append(Path(base) / 'Inno Setup 6' / 'ISCC.exe')
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def build_installer(
    destination: Path | str = DEFAULT_DESTINATION,
    *,
    iss_path: Path | str = DEFAULT_ISS,
    root: Path | str = ROOT,
    env=None,
    runner=None,
) -> dict:
    """用 distribution_build 备好并校验分发副本，再调 ISCC 编译单文件安装包。"""
    iscc = find_iscc(env=env)
    if iscc is None:
        return {'ok': False, 'exit_code': NO_ISCC_EXIT, 'message': NO_ISCC_MESSAGE}

    base = Path(root).resolve()
    dest = Path(destination).resolve()
    if dest == base or base in dest.parents:
        return {'ok': False, 'exit_code': 1, 'message': f'输出目录不能落在仓库目录内部：{dest}'}

    errors = check_iss(iss_path)
    if errors:
        return {'ok': False, 'exit_code': 1, 'message': '安装脚本静态自检未通过', 'errors': errors}

    version = app_version()
    if not version:
        return {'ok': False, 'exit_code': 1, 'message': '无法读取 contract.app_metadata.VERSION'}

    manifest_path = base / '程序' / 'distribution_manifest.md'
    manifest = distribution_build.parse_manifest(
        manifest_path if manifest_path.is_file() else distribution_build.MANIFEST
    )
    run = subprocess.run if runner is None else runner

    with tempfile.TemporaryDirectory(prefix='installer_build_') as tmp:
        tmp_path = Path(tmp)
        stage_dir = tmp_path / 'dist'
        out_dir = tmp_path / 'out'
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            distribution_build.build(stage_dir, root=base, manifest=manifest)
        except ValueError as exc:
            return {'ok': False, 'exit_code': 1, 'message': f'构建分发副本失败：{exc}'}
        verify_report = distribution_build.verify(stage_dir, root=base, manifest=manifest)
        if not verify_report.get('ok', False):
            return {'ok': False, 'exit_code': 1, 'message': '分发副本校验未通过', 'verify': verify_report}

        cmd = [
            str(iscc),
            f'/DAppVersion={version}',
            f'/DSourceDir={stage_dir}',
            f'/O{out_dir}',
            str(Path(iss_path).resolve()),
        ]
        done = run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)
        if done.returncode != 0:
            return {
                'ok': False,
                'exit_code': 1,
                'message': f'ISCC 编译失败（退出码 {done.returncode}）',
                'stdout': done.stdout,
                'stderr': done.stderr,
            }
        produced = sorted(out_dir.glob('*.exe'))
        if not produced:
            return {'ok': False, 'exit_code': 1, 'message': 'ISCC 编译完成但未找到产出的 .exe 安装包'}

        dest.mkdir(parents=True, exist_ok=True)
        artifacts = []
        for exe in produced:
            target = dest / exe.name
            shutil.copy2(exe, target)
            artifacts.append({
                'path': str(target),
                'name': target.name,
                'bytes': target.stat().st_size,
                'sha256': _sha256(target),
            })
        return {
            'ok': True,
            'exit_code': 0,
            'version': version,
            'iscc': str(iscc),
            'artifacts': artifacts,
        }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Inno Setup 安装脚本静态自检与安装包构建入口。')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='纯静态解析并检查 .iss 契约（默认）')
    mode.add_argument('--build', action='store_true', help='构建分发副本并调用 ISCC.exe 编译安装包')
    parser.add_argument('--destination', default=str(DEFAULT_DESTINATION), help='安装包输出目录（默认仓库根上一级 发行包\\）')
    parser.add_argument('--iss', default=str(DEFAULT_ISS), help='指定 .iss 安装脚本路径')
    parser.add_argument('--root', default=str(ROOT), help='仓库根目录')
    args = parser.parse_args(argv)

    if args.build:
        result = build_installer(args.destination, iss_path=args.iss, root=args.root)
        code = int(result['exit_code'])
        if code == 0:
            print(f'[安装包构建] 成功（版本 {result["version"]}）')
            for item in result['artifacts']:
                print(f'  产物：{item["path"]}')
                print(f'  大小：{item["bytes"]} bytes')
                print(f'  sha256：{item["sha256"]}')
            return 0
        print(result['message'])
        for err in result.get('errors', ()):
            print('  ' + err)
        if result.get('stderr'):
            print(result['stderr'])
        return code

    errors = check_iss(args.iss)
    if errors:
        print(f'[安装脚本自检] 未通过（共 {len(errors)} 项）：{args.iss}')
        for err in errors:
            print('  - ' + err)
        return 1
    version = app_version()
    print(f'[安装脚本自检] 通过：{args.iss}')
    print(f'  版本权威源：{version}（.iss 中仅以 {{#AppVersion}} 引用）')
    print(f'  用户数据保护 Excludes：{len(REQUIRED_USER_DATA_EXCLUDES)} 项全覆盖，skill_note_terms_zh.json 随包放回')
    print('  安全边界：无 [InstallDelete]/[UninstallDelete]，SignTool 仅位于 #ifdef Signed 内')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
