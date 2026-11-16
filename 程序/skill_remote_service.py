# -*- coding: utf-8 -*-
"""SKILL 远程链接导入（L4 服务，无 Tk）：解析 http(s) 链接 → 下载 → ZIP 管线。

支持两种形态，其余一律拒绝：

- ``https://github.com/<owner>/<repo>``：可带 ``#<ref>``（分支／标签／提交）与
  ``/tree/<ref>/<子目录>``（GitHub 页面浏览子目录的链接形态，``#ref`` 优先）；
  按 codeload 端点 ``…/zip/<ref>`` 取整仓 ZIP，``ref`` 缺省为 ``HEAD``（默认分支）。
- ``http(s)://…/*.zip`` 直链：按 URL path 后缀判定，查询串不影响；下载地址保留
  查询串（签名链接需要），展示标签与台账 ``source`` 不含查询串（可能夹带令牌）。

下载唯一出站口径 ``platform_tools.open_https``（与账号客户端同规矩：
``DRAMA_SUPPRESS_NETWORK`` 自检开关下默认入口直接按不联网返回；测试注入
``opener`` 不受开关影响）。二进制 ZIP 不走 ``http_client.request_json``——
那是 JSON API 口径，本模块是文件下载边界（任务书 T3 已注明该决策）。

落盘 ``data/skills/下载缓存/``（用户层内、升级保留、文件名不带阶段编号前缀，
注册表不会扫成 SKILL），随后交给 ``skill_archive.import_archive`` 的安全解包
→候选扫描→预检→确认→换入→试冻结→登记管线；台账经 ``_InstallSource`` 带
``source_url``／``source_ref``，供 T4 更新检测消费。
"""
from __future__ import annotations

import hashlib
import os
import re
import urllib.error
import urllib.parse
from pathlib import Path

import app_logging
from contract import platform_tools
from storage_maintenance import recycle_paths
import skill_archive
import skill_import_service
import skill_registry

SUPPRESS_NETWORK_ENV = 'DRAMA_SUPPRESS_NETWORK'
REMOTE_TIMEOUT = 120
DOWNLOAD_DIR_NAME = '下载缓存'
_CHUNK = 1024 * 1024
_GITHUB_HOSTS = frozenset({'github.com', 'www.github.com'})
_NAME_PART = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$')
_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$')
_UNSAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _reject(message):
    raise skill_import_service.ImportBlocked(message)


def _cache_name(stem):
    """缓存文件名：来源主干 + 来源散列，同名不同链不互相覆盖。"""
    safe = _UNSAFE_NAME.sub('_', str(stem)).strip(' .') or 'skill'
    return safe[:80]


def _github(parts, path, fragment):
    """``github.com/<owner>/<repo>[/tree/<ref>/<子目录>][#<ref>]`` → codeload ZIP 规格。"""
    segments = [seg for seg in path.split('/') if seg]
    if len(segments) < 2:
        _reject('GitHub 链接需要 owner/repo 形式')
    owner, repo = segments[0], segments[1]
    if repo.lower().endswith('.git'):
        repo = repo[:-4]
    if not _NAME_PART.match(owner) or not _NAME_PART.match(repo):
        _reject('GitHub 仓库名不合法')
    ref, scope = '', ''
    rest = segments[2:]
    if rest:
        if rest[0].lower() != 'tree':
            _reject('GitHub 链接只支持仓库首页或 /tree/<ref>/<子目录> 形式')
        if len(rest) > 1:
            ref = rest[1]
        if len(rest) > 2:
            scope = '/'.join(rest[2:])
    if fragment:
        ref = fragment
    if ref and not _REF.match(ref):
        _reject('GitHub 引用「%s」不合法' % ref)
    if scope:
        scope_parts = scope.split('/')
        if any(part in ('.', '..') for part in scope_parts):
            _reject('GitHub 子目录路径不合法')
    label = 'github.com/%s/%s' % (owner, repo)
    if ref:
        label += '@' + ref
    if scope:
        label += '/' + scope
    digest = hashlib.sha256(
        ('github:%s/%s#%s' % (owner, repo, ref)).encode('utf-8')).hexdigest()[:8]
    return {'kind': 'repo',
            'url': 'https://codeload.github.com/%s/%s/zip/%s' % (owner, repo, ref or 'HEAD'),
            'label': label,
            'cache_name': _cache_name('%s-%s-%s-%s' % (owner, repo, ref or 'HEAD', digest)),
            'source_url': 'https://github.com/%s/%s' % (owner, repo),
            'source_ref': ref, 'source_kind': 'repo', 'scope': scope}


def _archive_link(parts, path):
    """``http(s)://…/*.zip`` 直链：下载地址保留查询串，标签去掉查询串。"""
    url = urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, parts.query, ''))
    name = urllib.parse.unquote(path).rstrip('/').rsplit('/', 1)[-1]
    stem = name[:-4] if name.lower().endswith('.zip') else name
    stem = _cache_name(stem) or 'skill'
    digest = hashlib.sha256(url.encode('utf-8')).hexdigest()[:8]
    label = urllib.parse.unquote(parts.path).rstrip('/')
    label = (parts.netloc + label)[:120]
    return {'kind': 'archive', 'url': url, 'label': label or url,
            'cache_name': '%s-%s.zip' % (stem, digest),
            'source_url': url, 'source_ref': '',
            'source_kind': 'archive', 'scope': ''}


def parse_source(text):
    """解析链接来源 → ``{'kind', 'url', 'label', 'cache_name', 'source_url',
    'source_ref', 'source_kind', 'scope'}``；不认识的形态抛 ``ImportBlocked``。"""
    raw = str(text or '').strip().strip('"').strip("'")
    if not raw:
        _reject('链接为空')
    if '://' not in raw:
        # 宽容：裸 github.com/o/r 补 https://；其余裸文本一律拒绝。
        if re.match(r'^(?:www\.)?github\.com/', raw, re.I):
            raw = 'https://' + raw
        else:
            _reject('仅支持 http(s) 链接：GitHub 仓库地址或 .zip 直链')
    try:
        parts = urllib.parse.urlsplit(raw)
    except ValueError as exc:
        raise skill_import_service.ImportBlocked('无法识别的链接「%s」' % raw) from exc
    scheme = parts.scheme.lower()
    if scheme not in ('http', 'https') or not parts.netloc:
        _reject('仅支持 http(s) 链接：GitHub 仓库地址或 .zip 直链')
    if parts.username is not None or parts.password is not None:
        _reject('链接不能包含账号密码')
    host = (parts.hostname or '').lower()
    path = urllib.parse.unquote(parts.path or '')
    fragment = parts.fragment or ''
    if host in _GITHUB_HOSTS:
        return _github(parts, path, fragment)
    if path.lower().endswith('.zip'):
        return _archive_link(parts, path)
    _reject('不支持的链接「%s」：仅收 GitHub 仓库地址或 .zip 直链' % (host or raw))


def _http_error(exc):
    code = getattr(exc, 'code', 0) or 0
    if code == 404:
        return '下载失败：链接不存在或已失效（HTTP 404）'
    if code == 403:
        return '下载失败：被服务器拒绝访问（HTTP 403）'
    return '下载失败：HTTP %d' % code


def _net_reason(exc):
    reason = getattr(exc, 'reason', exc)
    text = str(reason or exc).strip()
    if isinstance(reason, TimeoutError) or 'timed out' in text.lower() or 'timeout' in text.lower():
        return '下载超时（%d 秒）' % REMOTE_TIMEOUT
    return '网络不通（%s）' % (text[:120] or type(exc).__name__)


def _stream(response, dest):
    """分块落盘：Content-Length 预检＋实读双护栏，超 ``PACKAGE_MAX_BYTES`` 即弃。

    失败时半截文件留在 ``dest``，由 ``download`` 按 ``recycle_root`` 经回收站收走
    （物理删除唯一权威 ``storage_maintenance``，本模块不直接 unlink）。
    """
    limit = skill_import_service.PACKAGE_MAX_BYTES
    headers = getattr(response, 'headers', None)
    declared = None
    if headers is not None:
        try:
            declared = headers.get('Content-Length')
        except Exception:
            declared = None
    if declared:
        try:
            declared_size = int(declared)
        except (TypeError, ValueError):
            declared_size = 0
        if declared_size > limit:
            raise skill_import_service.ImportBlocked(
                '远程文件超过 %d MB 上限' % (limit // 1024 // 1024))
    total = 0
    with open(dest, 'wb') as out:
        while True:
            chunk = response.read(_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise skill_import_service.ImportBlocked(
                    '远程文件超过 %d MB 上限' % (limit // 1024 // 1024))
            out.write(chunk)


def _recycle_partial(dest, recycle_root):
    """下载失败的半截文件经回收站收走（只移动不永久删除）；回收失败只留痕不掩盖原错。"""
    try:
        if recycle_root is not None and Path(dest).exists():
            recycle_paths(recycle_root, [dest], 'SKILL 远程下载中断清理')
    except Exception:
        app_logging.swallowed('skill_remote_service 半截下载回收失败')


def download(url, dest, *, opener=None, timeout=REMOTE_TIMEOUT, recycle_root=None):
    """GET ``url`` 落到 ``dest``；超时／HTTP 错／超限／中断抛 ``ImportBlocked``。

    ``recycle_root`` 给出时，失败留下的半截文件经 ``storage_maintenance.recycle_paths``
    移入回收站；不给则原样留在 ``dest``（调用方负责后续处置）。
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if opener is None:
        if os.environ.get(SUPPRESS_NETWORK_ENV):
            raise skill_import_service.ImportBlocked(
                '自检环境不联网（%s）' % SUPPRESS_NETWORK_ENV)
        opener = platform_tools.open_https
    try:
        response = opener(str(url), timeout=timeout)
    except urllib.error.HTTPError as exc:
        raise skill_import_service.ImportBlocked(_http_error(exc)) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise skill_import_service.ImportBlocked(_net_reason(exc)) from exc
    except OSError as exc:
        raise skill_import_service.ImportBlocked('下载失败：%s' % exc) from exc
    try:
        try:
            _stream(response, dest)
        except skill_import_service.ImportBlocked:
            _recycle_partial(dest, recycle_root)
            raise
        except Exception as exc:
            _recycle_partial(dest, recycle_root)
            raise skill_import_service.ImportBlocked('下载中断（%s）' % exc) from exc
    finally:
        close = getattr(response, 'close', None)
        if callable(close):
            try:
                close()
            except Exception:
                app_logging.swallowed('skill_remote_service 响应关闭失败')
    return dest


def cache_dir(program):
    """下载缓存：``data/skills/下载缓存/``——用户层内、升级保留、不被注册表扫描。"""
    return skill_registry.default_user_root(Path(program)) / DOWNLOAD_DIR_NAME


def import_from_url(text, program, registry, stage_hint='', confirm=None, *, opener=None):
    """链接导入主入口：解析 → 下载到缓存 → ``skill_archive`` 解包管线 → 台账登记。

    返回结构与 ``skill_import_service.import_from_repo`` 一致；台账行带
    ``source_url``／``source_ref``／``version``（T4 更新检测消费）。
    """
    program = Path(program)
    spec = parse_source(text)
    zip_path = download(spec['url'], cache_dir(program) / spec['cache_name'],
                        opener=opener, recycle_root=program)
    source = skill_import_service._InstallSource(
        ledger_source=spec['label'], label=spec['label'],
        source_kind=spec['source_kind'], origin='链接',
        source_url=spec['source_url'], source_ref=spec['source_ref'])
    return skill_archive.import_archive(
        zip_path, program, registry, stage_hint=stage_hint, confirm=confirm,
        install_source=source, scope=spec.get('scope', ''))


def _remote_entry_digests(spec, program, registry, *, opener=None, cache=None):
    """下载 → ``skill_archive`` 解包 → ``{台账键: 摘要}``；``cache`` 按下载地址复用。"""
    cache = cache if cache is not None else {}
    if spec['url'] in cache:
        return cache[spec['url']]
    zip_path = download(spec['url'], cache_dir(program) / spec['cache_name'],
                        opener=opener, recycle_root=program)
    digests = skill_archive.archive_entry_digests(
        zip_path, program, registry, scope=spec.get('scope', ''))
    cache[spec['url']] = digests
    return digests


def probe_row(key, row, program, registry, *, opener=None, cache=None):
    """远程台账行的更新探测：``source_url`` 可解析为 GitHub 仓库或 .zip 直链才接管。

    返回 ``'unchanged'|'source-newer'|'source-missing'``；不接管返回 ``None``
    （交给 ``skill_import_service`` 的克隆／本地判定）。下载失败、坏包、候选消失
    一律 ``source-missing``；``cache`` 在同一次检查内按下载地址复用摘要。
    """
    url = str(row.get('source_url') or '')
    if not url:
        return None
    text = url
    if str(row.get('source_kind') or '') == 'repo' and row.get('source_ref'):
        text = url + '#' + str(row['source_ref'])
    try:
        spec = parse_source(text)
    except skill_import_service.ImportBlocked:
        return None
    try:
        digests = _remote_entry_digests(spec, program, registry,
                                        opener=opener, cache=cache)
    except (skill_import_service.ImportBlocked, OSError):
        return 'source-missing'
    return skill_import_service._entry_status(key, row, digests)
