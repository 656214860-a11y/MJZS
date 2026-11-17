# -*- coding: utf-8 -*-
"""Data-driven client profiles for desktop apps and command line clients.

The catalog lives in 配置/客户端档案.json.  A user catalog may be appended in
data/客户端档案.json; a user entry never replaces a built-in entry with the same
id.  Reading both files is the only work done on import or startup.
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import struct
import subprocess
from pathlib import Path

from agent.core import save

PROGRAM = Path(__file__).resolve().parents[1]
BUILTIN_FILE = PROGRAM / '配置' / '客户端档案.json'
USER_FILE = PROGRAM / 'data' / '客户端档案.json'
SCHEMA_VERSION = 1
DESKTOP_KINDS = ('desktop',)
CLI_KINDS = ('cli',)
DELIVERIES = ('paste', 'clipboard', 'cli_file', 'cli_stdin', 'cli_arg')
# R1706b：档案只给既有路由识别不了的新客户端兜底。这些名字在 R1706 之前就有
# 内建路由（内建 CLI 引擎或旧桌面别名），同名桌面项（opencode-desktop 的
# opencode 别名、gemini-desktop 的 gemini 别名）不得抢先改写它们的调用方式。
BUILTIN_MODEL_NAMES = ('codex', 'claude', 'qwen', 'opencode',
                       'codex-desktop', 'gemini', 'google-gemini')
DEFAULT_TIMEOUT = 5
_CACHE = {'stamp': None, 'profiles': {}}


def _plain(value):
    return str(value or '').strip()


def _key(value):
    return re.sub(r'[\s_-]+', '-', _plain(value).casefold()).strip('-')


def _strings(value):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    out = []
    for item in value:
        text = _plain(item)
        if text and text not in out:
            out.append(text)
    return out


def qwen_command(config):
    """Resolve the installed Qwen Code command without importing workflow modules."""
    root = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'qwen-code/qwen-code'
    node = root / 'node/node.exe'
    entry = root / 'lib/cli-entry.js'
    configured = (config or {}).get('program')
    if configured and Path(configured).resolve() not in (node.resolve(), (root / 'bin/qwen.cmd').resolve()):
        return [configured]
    if node.is_file() and entry.is_file():
        return [str(node), str(entry)]
    found = shutil.which('qwen.exe')
    if found:
        return [found]
    raise ValueError('未找到 Qwen Code，请安装后在调用设置中选择程序')


def _store_packages(value):
    out = []
    if not isinstance(value, list):
        return out
    for item in value:
        if not isinstance(item, dict) or not _plain(item.get('package')):
            continue
        out.append({'package': _plain(item['package']),
                    'relative': _plain(item.get('relative'))})
    return out


def normalize_profile(value):
    """Return a tolerated profile, or None when it has no usable id."""
    row = value if isinstance(value, dict) else {}
    profile_id = _key(row.get('id'))
    if not profile_id:
        return None
    detect = row.get('detect') if isinstance(row.get('detect'), dict) else {}
    invoke = _strings(row.get('invoke'))
    delivery = _plain(row.get('delivery')).casefold()
    kind = _plain(row.get('kind')).casefold()
    if kind not in ('desktop', 'cli'):
        kind = 'cli' if invoke or delivery.startswith('cli_') else 'desktop'
    if delivery not in DELIVERIES:
        delivery = 'paste' if kind == 'desktop' else ('cli_arg' if invoke else 'cli_stdin')
    window = row.get('window') if isinstance(row.get('window'), dict) else {}
    return {
        'id': profile_id,
        'kind': kind,
        'display': _plain(row.get('display')) or _plain(row.get('id')),
        'aliases': [_key(item) for item in _strings(row.get('aliases')) if _key(item)],
        'detect': {
            'exe_names': _strings(detect.get('exe_names')),
            'known_dirs': _strings(detect.get('known_dirs')),
            'known_globs': _strings(detect.get('known_globs')),
            'registry': _strings(detect.get('registry')),
            'store_packages': _store_packages(detect.get('store_packages')),
        },
        'process_names': _strings(row.get('process_names')),
        'window': {'titles': _strings(window.get('titles')), 'classes': _strings(window.get('classes'))},
        'delivery': delivery,
        'invoke': invoke,
        'output': _plain(row.get('output')).casefold(),
    }


def _read(path):
    try:
        with Path(path).open('r', encoding='utf-8-sig') as handle:
            data = json.load(handle)
    except (OSError, ValueError, UnicodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _rows(path):
    data = _read(path)
    rows = data.get('profiles')
    return rows if isinstance(rows, list) else []


def _stamp(paths):
    out = []
    for path in paths:
        try:
            stat = Path(path).stat()
        except OSError:
            out.append(None)
        else:
            out.append((stat.st_mtime_ns, stat.st_size))
    return tuple(out)


def load_profiles(builtin_path=None, user_path=None, *, refresh=False):
    """Load built-in then user profiles; duplicate ids keep the built-in row."""
    builtin = Path(builtin_path or BUILTIN_FILE)
    user = Path(user_path or USER_FILE)
    stamp = _stamp((builtin, user))
    if not refresh and stamp == _CACHE['stamp']:
        return dict(_CACHE['profiles'])
    merged = {}
    for path in (builtin, user):
        for row in _rows(path):
            profile = normalize_profile(row)
            if profile and profile['id'] not in merged:
                merged[profile['id']] = profile
    _CACHE['stamp'] = stamp
    _CACHE['profiles'] = merged
    return dict(merged)


def clear_cache():
    _CACHE['stamp'] = None
    _CACHE['profiles'] = {}


def profile(identifier, *, builtin_path=None, user_path=None, refresh=False):
    """Find one profile by id, alias, display name, or executable stem."""
    raw = _plain(identifier)
    target = _key(raw)
    if not target:
        return {}
    stem = _key(Path(raw).stem) if Path(raw).suffix else target
    for item in load_profiles(builtin_path, user_path, refresh=refresh).values():
        names = [item['id'], _key(item['display'])] + [_key(alias) for alias in item['aliases']]
        if target in names or stem in names:
            return dict(item)
        if stem and stem in [_key(Path(name).stem) for name in item['detect']['exe_names']]:
            return dict(item)
    return {}


def profile_for_mode(identifier, mode, *, builtin_path=None, user_path=None, refresh=False):
    """Resolve an ambiguous alias such as ``opencode`` by Desktop/CLI mode."""
    wanted = 'desktop' if _plain(mode).casefold() == 'desktop' else 'cli'
    raw = _plain(identifier)
    target = _key(raw)
    stem = _key(Path(raw).stem) if Path(raw).suffix else target
    if not target:
        return {}
    for item in load_profiles(builtin_path, user_path, refresh=refresh).values():
        names = [item['id'], _key(item['display'])] + [_key(alias) for alias in item['aliases']]
        stems = [_key(Path(name).stem) for name in item['detect']['exe_names']]
        if target in names or stem in names or (stem and stem in stems):
            if item['kind'] == wanted:
                return dict(item)
    return {}


def profile_for_model(model_id='', item=None, *, kind='', refresh=False):
    """Resolve a model-pool record to a profile using id, label, or program.

    ``kind`` (``desktop`` / ``cli``) restricts the result to that call mode so
    an alias shared with a desktop profile cannot leak into the CLI branch.
    ``kind=''`` keeps the historical first-match behavior for other callers.
    """
    record = item if isinstance(item, dict) else {}
    wanted = _plain(kind).casefold()
    if wanted not in ('desktop', 'cli'):
        wanted = ''
    for value in (model_id, record.get('model'), record.get('label'), record.get('program')):
        if wanted:
            found = profile_for_mode(value, wanted, refresh=refresh)
        else:
            found = profile(value, refresh=refresh)
        if found:
            return found
    return {}


def engine_for_model(model_id='', item=None):
    """Profile kind -> engine name; known engines keep their hard-coded branches."""
    found = profile_for_model(model_id, item)
    if not found:
        return ''
    return 'desktop-app' if found['kind'] == 'desktop' else 'client-cli'


def _expand(value):
    return os.path.expandvars(os.path.expanduser(_plain(value).replace('/', os.sep)))


def _existing(paths):
    for candidate in paths:
        try:
            path = Path(candidate)
            if path.is_file():
                return str(path)
        except OSError:
            continue
    return ''


def _registry_candidates(names):
    if not names:
        return []
    try:
        from contract.platform_tools import windows_registry
        registry = windows_registry()
    except Exception:
        return []
    if registry is None:
        return []
    paths = []
    for hive in (registry.HKEY_CURRENT_USER, registry.HKEY_LOCAL_MACHINE):
        for branch in (r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths',
                       r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths'):
            for name in names:
                try:
                    with registry.OpenKey(hive, branch + '\\' + name) as key:
                        paths.append(str(registry.QueryValueEx(key, '')[0]).strip('"'))
                except OSError:
                    continue
    return paths


def _glob_candidates(patterns):
    paths = []
    for raw in patterns:
        try:
            found = [path for path in glob.glob(_expand(raw), recursive=True) if Path(path).is_file()]
        except (OSError, ValueError):
            found = []
        try:
            found.sort(key=lambda text: Path(text).stat().st_mtime, reverse=True)
        except OSError:
            pass
        paths.extend(found)
    return paths


def detect_executable(profile_row, *, which=shutil.which, env=None, store_finder=None):
    """Locate a profile executable.  This never executes the candidate."""
    item = normalize_profile(profile_row) or {}
    detect = item.get('detect') or {}
    names = detect.get('exe_names') or []
    candidates = []
    for name in names:
        try:
            found = which(name, path=(env or os.environ).get('PATH')) if callable(which) else ''
        except TypeError:
            found = which(name) if callable(which) else ''
        if found:
            candidates.append(found)
    for directory in detect.get('known_dirs') or []:
        base = Path(_expand(directory))
        if base.suffix:
            candidates.append(str(base))
        for name in names:
            candidates.append(str(base / name))
    candidates.extend(_glob_candidates(detect.get('known_globs') or []))
    candidates.extend(_registry_candidates(detect.get('registry') or []))
    if callable(store_finder):
        for package in detect.get('store_packages') or []:
            found = store_finder(package['package'], Path(package['relative']))
            if found:
                candidates.append(found)
    return _existing(candidates)


def pe_subsystem(path):
    """Read only the PE header: 'gui', 'console', or '' when unknown."""
    try:
        with Path(path).open('rb') as handle:
            header = handle.read(64)
            if len(header) < 64 or header[:2] != b'MZ':
                return ''
            offset = struct.unpack_from('<I', header, 0x3c)[0]
            handle.seek(offset)
            pe = handle.read(24 + 68 + 2)
            if len(pe) < 24 + 68 + 2 or pe[:4] != b'PE\0\0':
                return ''
            magic = struct.unpack_from('<H', pe, 24)[0]
            if magic not in (0x10b, 0x20b):
                return ''
            subsystem = struct.unpack_from('<H', pe, 24 + 68)[0]
    except (OSError, ValueError, struct.error):
        return ''
    return {2: 'gui', 3: 'console'}.get(subsystem, '')


def _minimal_env(env=None, base=None):
    source = env if env is not None else (base or os.environ)
    keys = ('SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'HOME', 'USERPROFILE')
    return {key: str(source[key]) for key in keys if source.get(key)}


def _probe_text(result):
    return (_plain(getattr(result, 'stdout', '')) + '\n' + _plain(getattr(result, 'stderr', ''))).strip()


def _invocation_from_help(text):
    lower = text.casefold()
    if '--prompt' in lower:
        return ['--prompt', '{prompt}'], 'cli_arg', 'text'
    if re.search(r'(^|\s)-p(\s|,|$)', lower):
        return ['-p', '{prompt}'], 'cli_arg', 'text'
    if '--file' in lower:
        return ['--file', '{task_file}'], 'cli_file', 'text'
    if re.search(r'(^|\s)exec(\s|$)', lower):
        return ['exec', '-'], 'cli_stdin', 'text'
    if re.search(r'(^|\s)run(\s|$)', lower):
        return ['run', '{prompt}'], 'cli_arg', 'text'
    if 'stdin' in lower:
        return [], 'cli_stdin', 'text'
    return [], 'cli_stdin', ''


def probe_cli(command, *, timeout=DEFAULT_TIMEOUT, run=subprocess.run, env=None):
    """Run --help/--version with a timeout and no shell; never used for GUI exes."""
    base = [str(item) for item in command]
    if not base:
        return {'ok': False, 'invoke': [], 'delivery': 'cli_stdin', 'output': '',
                'reason': '没有可探测的命令行程序'}
    if len(base) == 1 and Path(base[0]).suffix.casefold() in ('.cmd', '.bat'):
        base = executable_command({}, base[0])
    last_reason = ''
    for flag in ('--help', '--version'):
        try:
            completed = run(base + [flag], shell=False, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=timeout,
                            env=_minimal_env(env))
        except subprocess.TimeoutExpired:
            last_reason = '检测超时（%s 秒）' % timeout
            continue
        except (OSError, ValueError) as exc:
            return {'ok': False, 'invoke': [], 'delivery': 'cli_stdin', 'output': '',
                    'reason': '检测无法启动：%s' % exc}
        text = _probe_text(completed)
        if completed.returncode == 0 and text:
            invoke, delivery, output = _invocation_from_help(text)
            return {'ok': True, 'invoke': invoke, 'delivery': delivery, 'output': output,
                    'reason': '已读取 %s 输出' % flag}
        last_reason = '检测退出码 %s' % completed.returncode
    return {'ok': False, 'invoke': [], 'delivery': 'cli_stdin', 'output': '', 'reason': last_reason}


def _slug(value):
    text = re.sub(r'[^a-z0-9]+', '-', _plain(value).casefold()).strip('-')
    return text or 'client'


def _unique_id(profile_id, builtin_path=None, user_path=None):
    rows = load_profiles(builtin_path, user_path, refresh=True)
    used = set(rows)
    for row in rows.values():
        used.update(row['aliases'])
        used.add(_slug(row['display']))
    if profile_id not in used:
        return profile_id
    index = 2
    while '%s-%d' % (profile_id, index) in used:
        index += 1
    return '%s-%d' % (profile_id, index)


def adapt_executable(path, display='', *, run=subprocess.run, save_profile=True, probe=True,
                     builtin_path=None, user_path=None, refresh=True):
    """Derive and optionally persist a profile from a .exe path."""
    target = Path(_expand(path))
    if not target.is_file():
        return {'ok': False, 'profile': {}, 'reason': '程序路径不存在：%s' % target}
    subsystem = pe_subsystem(target)
    if not subsystem:
        return {'ok': False, 'profile': {}, 'reason': '无法从 PE 头判断该程序是桌面还是命令行'}
    expected = 'desktop' if subsystem == 'gui' else 'cli'
    existing = profile(str(target)) or profile(target.stem)
    if existing and existing['kind'] == expected:
        return {'ok': True, 'profile': existing, 'reason': '已匹配现有客户端档案：' + existing['display']}
    label = _plain(display) or target.stem
    base = {
        'id': _slug(target.stem), 'display': label,
        'detect': {'exe_names': [target.name], 'known_dirs': [str(target.parent)],
                   'known_globs': [], 'registry': [], 'store_packages': []},
        'process_names': [target.stem], 'window': {'titles': [], 'classes': []},
    }
    if subsystem == 'gui':
        base.update({'kind': 'desktop', 'delivery': 'paste', 'invoke': [], 'output': ''})
        reason = '已按 GUI 子系统识别为桌面程序；不会为探测执行该文件'
    elif probe:
        result = probe_cli([str(target)], run=run)
        base.update({'kind': 'cli', 'delivery': result['delivery'], 'invoke': result['invoke'],
                     'output': result['output']})
        reason = result['reason'] if result['invoke'] else '未识别命令行参数，将用交互式窗口兜底'
    else:
        base.update({'kind': 'cli', 'delivery': 'cli_stdin', 'invoke': [], 'output': ''})
        reason = '已按 Console 子系统识别为命令行程序；未执行探测，将用交互式窗口兜底'
    base['id'] = _unique_id(base['id'], builtin_path, user_path)
    base = normalize_profile(base)
    if save_profile:
        save_user_profile(base, user_path)
    return {'ok': True, 'profile': base, 'reason': reason}


def save_user_profile(profile_row, user_path=None):
    """Append or update one user profile; built-in ids stay authoritative."""
    item = normalize_profile(profile_row)
    if not item:
        raise ValueError('客户端档案缺少 id')
    path = Path(user_path or USER_FILE)
    data = _read(path)
    rows = data.get('profiles') if isinstance(data.get('profiles'), list) else []
    rows = [row for row in rows if not isinstance(row, dict) or _key(row.get('id')) != item['id']]
    rows.append(item)
    save(path, {'schema_version': SCHEMA_VERSION, 'profiles': rows})
    clear_cache()
    return path


def profile_for_config(config):
    """Resolve the profile carried by a workflow engine config."""
    value = config if isinstance(config, dict) else {}
    for key in ('client_profile', 'profile_id', 'display_model', 'model', 'program'):
        candidate = value.get(key)
        if isinstance(candidate, dict):
            found = normalize_profile(candidate) or {}
        else:
            found = profile(candidate)
        if found:
            return found
    return {}


def _replace(values, prompt, task_file, title, model):
    text = [str(item) for item in values]
    replacements = {'{prompt}': prompt, '{task_file}': task_file, '{title}': title, '{model}': model}
    return [replacements.get(item, item) for item in text]


def build_invocation(profile_row, prompt='', task_file='', title='', model=''):
    """Fill an invoke template.  Empty means: open an interactive console."""
    item = normalize_profile(profile_row) or {}
    template = item.get('invoke') or []
    if not template:
        return []
    filled = _replace(template, prompt, task_file, title, model)
    if item.get('delivery') == 'cli_arg' and '{prompt}' not in template and '{task_file}' not in template:
        filled.append(prompt)
    if item.get('delivery') == 'cli_file' and '{task_file}' in template and not task_file:
        return []
    return filled


def stdin_text(profile_row, prompt=''):
    item = normalize_profile(profile_row) or {}
    template = item.get('invoke') or []
    if item.get('delivery') == 'cli_stdin' and (not template or template[-1] == '-'):
        return prompt
    return ''


def executable_command(profile_row, executable):
    """Wrap .cmd/.bat launchers so they can be started without a shell string."""
    exe = str(executable)
    if Path(exe).suffix.casefold() in ('.cmd', '.bat'):
        return [os.environ.get('COMSPEC') or 'cmd.exe', '/c', exe]
    return [exe]
