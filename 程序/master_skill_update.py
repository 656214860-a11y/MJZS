# -*- coding: utf-8 -*-
"""总控包在线更新（L4，无 Tk）：检测 GitHub 新版本、按阶段汇总变化、用户确认后下载覆盖。

流程（见 R1996 结果文件）：
- ``check``：读 GitHub 最新提交；与上次已装提交不同才下载压缩包到 ``data/总控包更新/<sha>.zip``，
  逐文件与本机总控包比对（换行归一，机器上有没有 git 都一样准），得到新增／修改／删除清单，
  再按各阶段总控 SKILL 的直接引用归类成“每个阶段有哪些变化”。没有任何差异就只记录基线，不打扰用户。
- ``apply``：用户确认后才调用。解压到旁路目录、校验入口、旧包改名后换入新包、旧包进回收站，
  成功后记下提交号，并对当前项目触发 ``master_skill.sync``（其他项目打开时按指纹自动同步）。
- 总控包目录内带 ``.git``（开发检出）时只提示、不覆盖，请在子模块里 ``git pull``。
- 出站只经 ``platform_tools.open_https``；写入只经 ``agent.core``；删除只经 ``storage_maintenance.recycle_paths``。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath

import master_skill
import contract.pet_bus as pet_bus
import contract.platform_tools as platform_tools
import storage_maintenance
import workflow_settings
from agent.core import save as save_json, save_bytes
from file_cache import read_json

PROGRAM = Path(__file__).resolve().parent
REPO = 'lixiaoxiao9888-create/manju-laoli-skill'
BRANCH = 'main'
PRESET = 'AIGC全流程'
ENTRY = 'short-drama-director/SKILL.md'
API_COMMITS = 'https://api.github.com/repos/%s/commits?sha=%s&per_page=20' % (REPO, BRANCH)
ZIP_URL = 'https://codeload.github.com/%s/zip/%%s' % REPO
MAX_ZIP_BYTES = 100 * 1024 * 1024
MAX_FILES = 5000
MAX_UNPACKED_BYTES = 400 * 1024 * 1024
TEXT_SUFFIXES = frozenset({'.md', '.py', '.json', '.txt', '.yml', '.yaml', '.toml'})
NONE, AVAILABLE, ERROR = 'none', 'available', 'error'
_VERSION = re.compile(r'版本-(V\d+(?:\.\d+)*)')
_LOG_LINE = re.compile(r'^\s*-\s+\*\*V\d')
_LOG_HEAD = re.compile(r'^\s*-\s+(V\d+(?:\.\d+)*)\s*(?:（\d{4}-(\d{2}-\d{2})）)?\s*[—-]*\s*(.*)$')
_CJK = re.compile('[\u4e00-\u9fff]')
TITLE_LIMIT = 28
SHOWN_FEATURES = 4


def state_path(program=PROGRAM):
    return Path(program) / 'data' / '总控包更新.json'


def load_state(program=PROGRAM):
    try:
        data = read_json(state_path(program))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def package_dir(program=PROGRAM):
    preset = workflow_settings.refresh_workflow_presets().get(PRESET) or {}
    package = preset.get('package')
    return (Path(program) / package).parent.parent if package else None


def _digest(rel, data):
    if PurePosixPath(rel).suffix.lower() in TEXT_SUFFIXES:
        data = data.replace(b'\r\n', b'\n')
    return hashlib.sha256(data).hexdigest()


def local_digests(pkg):
    """本机总控包逐文件摘要；固定一个目录、跳过 ``.git``，在后台线程里调用。"""
    out = {}
    for base, dirs, files in os.walk(pkg):
        dirs[:] = [name for name in dirs if name != '.git']
        for name in files:
            path = Path(base) / name
            rel = path.relative_to(pkg).as_posix()
            try:
                out[rel] = _digest(rel, path.read_bytes())
            except OSError:
                out[rel] = ''
    return out


def _safe_members(archive):
    """压缩包条目：去掉顶层目录，拒绝绝对路径／上跳／盘符，限制数量与总大小。"""
    members, total = [], 0
    for info in archive.infolist():
        if info.is_dir():
            continue
        parts = PurePosixPath(info.filename.replace('\\', '/')).parts[1:]
        if not parts:
            continue
        if any(part in ('..', '') or ':' in part for part in parts) or info.filename.startswith(('/', '\\')):
            raise ValueError('压缩包含不安全路径：%s' % info.filename)
        total += info.file_size
        members.append((PurePosixPath(*parts).as_posix(), info))
    if len(members) > MAX_FILES or total > MAX_UNPACKED_BYTES:
        raise ValueError('压缩包体量超过上限')
    return members


def remote_digests(zip_path):
    """压缩包内逐文件摘要与 README 文本。"""
    out, readme = {}, ''
    with zipfile.ZipFile(zip_path) as archive:
        for rel, info in _safe_members(archive):
            data = archive.read(info)
            out[rel] = _digest(rel, data)
            if rel == 'README.md':
                readme = data.decode('utf-8', 'replace')
    return out, readme


def diff_digests(local, remote):
    return {'added': sorted(set(remote) - set(local)),
            'removed': sorted(set(local) - set(remote)),
            'changed': sorted(rel for rel in set(local) & set(remote) if local[rel] != remote[rel])}


def version_of(readme):
    found = _VERSION.search(readme or '')
    return found.group(1) if found else ''


def new_log_lines(old_readme, new_readme, limit=6):
    """新版 README 更新日志里本机没有的条目，就是“新功能”的原文。"""
    known = {line.strip() for line in (old_readme or '').splitlines()}
    # README 的更新日志有中英两份，只留中文条目，避免同一个版本列两遍。
    lines = [line.strip() for line in (new_readme or '').splitlines()
             if _LOG_LINE.match(line) and line.strip() not in known and _CJK.search(line)]
    return [line[:220] for line in lines[:limit]]


def stage_changes(changed, pkg, preset, registry=None):
    """{阶段: [变化的包内相对路径]} 与未归入任何阶段的“公共／脚本”文件。"""
    root = Path(pkg).resolve()
    wanted = set(changed)
    per_stage, claimed = {}, set()
    for stage, files in master_skill.stage_skill_files(preset, registry).items():
        hits = []
        for path in files:
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                continue
            if rel in wanted and rel not in hits:
                hits.append(rel)
        if hits:
            per_stage[stage] = hits
            claimed.update(hits)
    return per_stage, sorted(wanted - claimed)


SUPPRESS_NETWORK_ENV = 'DRAMA_SUPPRESS_NETWORK'


def _fetch(url, limit):
    # 自检与本地 CI 设置 DRAMA_SUPPRESS_NETWORK=1：默认联网入口直接按离线处理（check 会返回 error），不碰 GitHub，也不往 data 下写下载缓存。
    if os.environ.get(SUPPRESS_NETWORK_ENV):
        raise OSError('自检环境不联网（%s）' % SUPPRESS_NETWORK_ENV)
    headers = {'User-Agent': 'manju-assistant', 'Accept': 'application/vnd.github+json'}
    with platform_tools.open_https(url, timeout=30, headers=headers) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('下载内容超过上限')
    return data


def check(program=PROGRAM, fetch=None, registry=None):
    """联网检测；返回 ``level`` 为 none／available／error 的字典。联网类失败不抛出。"""
    fetch = fetch or _fetch
    try:
        return _check(Path(program), fetch, registry)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        return {'level': ERROR, 'reason': '%s：%s' % (type(exc).__name__, str(exc)[:120])}


def _check(program, fetch, registry):
    pkg = package_dir(program)
    if pkg is None or not pkg.is_dir():
        return {'level': NONE, 'reason': '本机没有总控包'}
    # 内存里的网络响应，不是项目 JSON 文件，不走 file_cache 读取闸。
    commits = json.JSONDecoder().decode(fetch(API_COMMITS, 2 * 1024 * 1024).decode('utf-8'))
    head = str(commits[0]['sha'])
    state = load_state(program)
    if state.get('sha') == head:
        return {'level': NONE, 'sha': head}
    cache = program / 'data' / '总控包更新' / (head + '.zip')
    if not cache.is_file():
        save_bytes(cache, fetch(ZIP_URL % head, MAX_ZIP_BYTES))
    remote, new_readme = remote_digests(cache)
    changes = diff_digests(local_digests(pkg), remote)
    changed = changes['added'] + changes['changed'] + changes['removed']
    if not changed:
        save_json(state_path(program), {'sha': head, 'at': _stamp()})
        return {'level': NONE, 'sha': head}
    try:
        old_readme = (pkg / 'README.md').read_text(encoding='utf-8', errors='replace')
    except OSError:
        old_readme = ''
    preset = workflow_settings.WORKFLOW_PRESETS.get(PRESET) or {}
    stages, common = stage_changes(changed, pkg, preset, registry)
    known = state.get('sha')
    messages = []
    for item in commits:
        if item['sha'] == known:
            break
        messages.append(str(item['commit']['message']).splitlines()[0][:120])
    blocked = '总控包目录带 .git（开发检出），请在子模块里 git pull。' if (pkg / '.git').exists() else ''
    return {'level': AVAILABLE, 'sha': head, 'zip': str(cache), 'old_version': version_of(old_readme),
            'new_version': version_of(new_readme), 'features': new_log_lines(old_readme, new_readme),
            'commits': messages[:10], 'stages': stages, 'common': common, 'counts': {k: len(v) for k, v in changes.items()},
            'can_apply': not blocked, 'blocked_reason': blocked}


def _stamp(now=None):
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now or time.time()))


def feature_title(line):
    """更新日志一行 → “V7.4.26（10-21） 审计补丁”这样的一句话标题；说明细节一律不带。"""
    found = _LOG_HEAD.match(line.replace('**', ''))
    if not found:
        return line[:TITLE_LIMIT]
    version, day, body = found.groups()
    title = re.split('[：:（(]', body.strip(), maxsplit=1)[0].strip()
    if len(title) > TITLE_LIMIT:
        title = title[:TITLE_LIMIT - 1] + '…'
    return '%s%s %s' % (version, '（%s）' % day if day else '', title)


def describe(result):
    """给弹窗用的中文摘要：版本变化、新功能（每个版本一行）、各阶段变化了几个文件。"""
    head = '总控包有新版本：%s → %s' % (result.get('old_version') or '本机版本',
                                      result.get('new_version') or result.get('sha', '')[:7])
    lines = [head]
    features = result.get('features') or []
    if features:
        lines += ['', '新功能'] + ['· ' + feature_title(item) for item in features[:SHOWN_FEATURES]]
        if len(features) > SHOWN_FEATURES:
            lines.append('· 另有 %d 个版本的更新' % (len(features) - SHOWN_FEATURES))
    elif result.get('commits'):
        lines += ['', '近期提交'] + ['· ' + item for item in result['commits'][:SHOWN_FEATURES]]
    if result.get('stages'):
        lines += ['', '各阶段 SKILL 有变化']
        lines += ['· %s：%d 个文件' % (pet_bus.STAGE_NAMES.get(stage, stage), len(files))
                  for stage, files in result['stages'].items()]
    if result.get('common'):
        lines += ['', '另有公共规则／脚本／文档 %d 个文件变化。' % len(result['common'])]
    if result.get('blocked_reason'):
        lines += ['', result['blocked_reason']]
    return '\n'.join(lines)


def apply(result, program=PROGRAM, project=None, registry=None, now=None):
    """用户确认后覆盖总控包；返回 ``{'ok', 'message'}``，失败时旧包保持原样。"""
    program = Path(program)
    pkg = package_dir(program)
    if result.get('level') != AVAILABLE or pkg is None:
        return {'ok': False, 'message': '没有可用的更新'}
    if not result.get('can_apply'):
        return {'ok': False, 'message': result.get('blocked_reason') or '当前环境不允许自动更新'}
    old = pkg.with_name(pkg.name + '.old')
    try:
        # 旁路目录由 tempfile 管理：任何一步失败（含解压到一半）都由它自己收拾，旧包不受影响。
        with tempfile.TemporaryDirectory(prefix=pkg.name + '.new.', dir=pkg.parent) as scratch:
            staging = Path(scratch) / 'package'
            _extract(Path(result['zip']), staging)
            if old.exists():
                storage_maintenance.recycle_paths(program, [old], '总控包更新残留的旧版本')
            os.rename(pkg, old)
            try:
                os.rename(staging, pkg)
            except OSError:
                os.rename(old, pkg)
                raise
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        return {'ok': False, 'message': '更新失败，旧版本未改动：%s' % exc}
    storage_maintenance.recycle_paths(program, [old], '总控包更新前的旧版本')
    save_json(state_path(program), {'sha': result['sha'], 'version': result.get('new_version', ''), 'at': _stamp(now)})
    message = '总控包已更新到 %s。' % (result.get('new_version') or result['sha'][:7])
    if project:
        try:
            synced = master_skill.sync(project, registry)
            message += synced['message'] or '各阶段勾选无需调整。'
        except (OSError, ValueError, TypeError, KeyError) as exc:
            message += '总控同步未完成：%s' % exc
    return {'ok': True, 'message': message}


def _extract(zip_path, target):
    with zipfile.ZipFile(zip_path) as archive:
        members = _safe_members(archive)
        for rel, info in members:
            save_bytes(target / rel, archive.read(info))
    if not (target / ENTRY).is_file():
        raise ValueError('压缩包缺少总控入口 %s' % ENTRY)
