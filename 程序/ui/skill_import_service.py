# -*- coding: utf-8 -*-
"""阶段配置「新增 SKILL」的稳定导入（L3，无 Tk）。

旧做法只把选中的那一个文件 ``copy2`` 进阶段目录：外部包的 references／assets／scripts
全部丢失，同名清单在扫描时被静默丢弃，覆盖不留旧版，引用断链要等到发送时才报。

本模块把一次导入拆成「预检 → 暂存 → 换入 → 试冻结 → 登记」：

- 选中 ``SKILL.md`` 视为外部包，整个包目录一并导入（跳过 ``.git``／``__pycache__``）；
  选中 ``*.skill.md`` 视为单文件清单。
- 硬性拦截（不给"仍要导入"）：读不出、重名、换入后按真实发送流程冻结失败
  （正文为空、引用缺失、引用越界、超过内联上限）。
- 软性问题（字段缺失、声明阶段不一致、目标已存在）仍交给界面二次确认。
- 目标已存在时旧版先经 ``storage_maintenance.recycle_paths`` 移入程序回收站，可恢复；
  试冻结失败则把新版撤回暂存区并恢复旧版，阶段目录回到导入前的样子。
- 暂存目录以 ``.`` 开头，注册表不会在换入前把它当成 SKILL 扫进来；用完同样经回收服务收走。
- 每次成功导入写一行导入台账（来源、内容摘要、时间），供以后检测来源是否更新。
- R2073：用户导入落在 ``程序/data/skills/<阶段>/``（升级保留），台账也在那里；与内置
  SKILL 同名不再硬拦，改为软提示「将覆盖内置版」，删除用户版后内置版恢复。
  ``migrate_legacy_imports`` 把旧版导进 ``程序/skills/`` 并记在旧台账里的条目迁过去。
- R2881：仓库导入 ``import_from_repo`` 对齐 skill-mgr 生命周期——``install``／
  ``update`` 同为「克隆（或本地目录直读）→ 扫描 → 逐候选走上面的预检→暂存→换入→
  试冻结→登记管线」；``uninstall`` 经回收站移除，``validate`` 即试冻结，``list``
  就是 ``skill_registry.getAll()``。薄 git 层只用 ``git clone --depth 1``，
  不引第三方；仓库地址支持 ``owner/repo`` 简写、完整 URL（可带 ``@分支``）与本地目录。
"""
from __future__ import annotations

import app_logging
import hashlib
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import NamedTuple

import skill_project_layer
import orchestrator.skill_registry as skill_registry
from agent.core import replace, save
from contract.pet_bus import read_json
from contract import platform_tools
from skill_security_service import (  # T9 安全提示助手；re-export 供调用方走本模块名
    ALERT_DIR_NAMES, EXECUTABLE_ALERT_SUFFIXES, import_alerts, package_alerts,
    untrusted_source_notice)
from storage_maintenance import recycle_paths, restore_recycle_batch

LEDGER_NAME = '导入台账.json'
STAGING_PREFIX = '.导入中-'
IGNORED_PARTS = ('.git', '__pycache__', '.DS_Store')
# 导入体积护栏：防止超大包拖垮磁盘、巨型单文件占满内存、符号链接把包外文件读进来。
SINGLE_MAX_BYTES = 20 * 1024 * 1024
PACKAGE_MAX_FILES = 2000
PACKAGE_MAX_BYTES = 200 * 1024 * 1024


def _is_link(path):
    return path.is_symlink() or bool(getattr(path, 'is_junction', lambda: False)())


def _check_package_bounds(package_root):
    """包导入的体积与链接护栏；违规抛 ImportBlocked，调用方原样展示。"""
    root = Path(package_root)
    if _is_link(root):
        raise ImportBlocked('包根是链接，已拒绝导入')
    total = 0
    count = 0
    for path in root.rglob('*'):
        if _is_link(path):
            raise ImportBlocked('包内含链接「%s」，已拒绝导入' % path.relative_to(root).as_posix())
        if not path.is_file():
            continue
        count += 1
        if count > PACKAGE_MAX_FILES:
            raise ImportBlocked('包内文件数超过 %d 个上限' % PACKAGE_MAX_FILES)
        total += path.stat().st_size
        if total > PACKAGE_MAX_BYTES:
            raise ImportBlocked('包总体积超过 %d MB 上限' % (PACKAGE_MAX_BYTES // 1024 // 1024))


class ImportBlocked(ValueError):
    """导入被硬性拦截；消息可直接展示给用户。"""


_PACKAGE_ENTRY_NAMES = {skill_registry.PACKAGE_SKILL_FILENAME.casefold()} | {
    name.casefold() for name in skill_registry.PACKAGE_README_FILENAMES}


def _kind(source):
    """包入口口径与 ``Registry._package_source`` 一致：SKILL.md 优先，README 兜底。"""
    return 'package' if Path(source).name.casefold() in _PACKAGE_ENTRY_NAMES else 'manifest'


def _tree_digest(path):
    """单文件取内容摘要；包取「相对路径＋内容」的整体摘要，顺序稳定。"""
    path = Path(path)
    digest = hashlib.sha256()
    files = [path] if path.is_file() else sorted(
        (item for item in path.rglob('*') if item.is_file()
         and not (set(item.relative_to(path).parts) & set(IGNORED_PARTS))),
        key=lambda item: item.relative_to(path).as_posix())
    for item in files:
        if path.is_dir():
            digest.update(item.relative_to(path).as_posix().encode('utf-8') + b'\0')
        digest.update(item.read_bytes())
    return digest.hexdigest()


def plan_import(source, target_dir, stage, registry):
    """只读预检：返回导入计划；读不出或重名直接抛 ImportBlocked。"""
    source = Path(source)
    if target_dir is None:
        raise ImportBlocked('未找到本阶段注册目录')
    target_dir = Path(target_dir)
    project_skills = getattr(registry, 'project_skills', None)
    scope = ('project' if isinstance(project_skills, (str, Path)) and
             target_dir.resolve().is_relative_to(Path(project_skills).resolve())
             else 'user')
    kind = _kind(source)
    target = (target_dir / source.parent.name / source.name
              if kind == 'package' else target_dir / source.name)
    if kind == 'manifest' and source.is_file() and source.stat().st_size > SINGLE_MAX_BYTES:
        raise ImportBlocked('源文件超过 %d MB 上限' % (SINGLE_MAX_BYTES // 1024 // 1024))
    try:
        raw = source.read_text(encoding='utf-8-sig')
    except (OSError, UnicodeError) as exc:
        raise ImportBlocked('读不出源文件（%s）' % exc) from exc
    meta, body = skill_registry.parse(raw, source=str(source))
    problems = []
    if kind == 'package':
        # 外部包由注册表补默认元数据，只检查可显示名称。
        if not (str(meta.get('displayName') or '').strip() or skill_registry.markdown_heading(body)):
            problems.append('未找到可显示的技能名称')
        name = skill_registry.imported_package_meta(meta, body, target.parent, target)['name']
    else:
        skill = skill_registry.Skill(meta, body, path=source)
        known = {item.name for item in registry.getAll()}
        problems.extend(skill_registry.validate_skill(skill, known=known))
        name = skill.name
    declared = skill_registry.stage_id(meta.get('stage', ''))
    if declared and declared != stage:
        problems.append('frontmatter 声明阶段「%s」与本阶段不一致' % declared)
    replaced = Path(os.path.normcase(str(target.resolve())))
    user_root = getattr(registry, 'user_root', None)
    into_user = isinstance(user_root, (str, Path)) and target.resolve().is_relative_to(Path(user_root).resolve())
    into_project = scope == 'project'
    layer_labels = skill_registry.LAYER_LABELS
    for item in registry.getAll():
        other = getattr(item, 'path', None)
        if not name or item.name != name or other is None:
            continue
        if Path(os.path.normcase(str(Path(other).resolve()))) == replaced:
            continue                     # 重新导入同一位置＝更新，不算重名
        item_layer = getattr(item, 'layer', '')
        if into_project and item_layer in ('user', 'builtin'):
            higher = layer_labels.get(item_layer, item_layer)
            problems.append('将覆盖%s SKILL「%s」（%s版保留，删除项目版后恢复）'
                            % (higher, name, higher))
            continue
        if into_user and item_layer == 'builtin':
            problems.append('将覆盖内置 SKILL「%s」（内置版保留，删除用户版后恢复）' % name)
            continue
        raise ImportBlocked('与已有 SKILL「%s」重名（%s）；同名 SKILL 扫描时会被丢弃。'
                            '请先改名或删除旧的那份再导入。' % (name, other))
    if target.exists():
        problems.append('目标 %s 已存在，继续将覆盖（旧版移入程序回收站，可恢复）' % target.name)
    return {'source': source, 'kind': kind, 'target': target, 'target_dir': target_dir,
            'name': name, 'problems': problems, 'scope': scope,
            'project': (str(getattr(registry, 'project_root', '') or '')
                        if scope == 'project' and
                        isinstance(getattr(registry, 'project_root', None), (str, Path))
                        else '')}


def _verify(target):
    """按真实发送流程冻结一次：正文为空、引用缺失／越界、超出上限都在此暴露。"""
    import orchestrator.workflow_settings as workflow_settings
    try:
        workflow_settings._inline_skill_report(target, strict=True)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ImportBlocked('导入后试冻结失败，已撤回：%s' % exc) from exc


def program_of(target_dir):
    """阶段目录 → 程序目录：用户层 程序/data/skills/<阶段>，无用户层时 程序/skills/<阶段>。"""
    target_dir = Path(target_dir)
    return target_dir.parents[2] if target_dir.parents[1].name == 'data' else target_dir.parents[1]


def ledger_path(program):
    """导入台账随用户层放在 data/skills 下，升级安装不覆盖。"""
    return skill_registry.default_user_root(program) / LEDGER_NAME


def _legacy_ledger_path(program):
    return skill_registry.default_root(program) / LEDGER_NAME


def _read_items(path):
    data = read_json(path) if Path(path).is_file() else {}
    data = data if isinstance(data, dict) else {}
    return dict(data.get('items')) if isinstance(data.get('items'), dict) else {}


def _frontmatter_version(target):
    """台账 ``version`` 字段：取已安装入口文件 frontmatter 的 ``version``，没有记空串。"""
    try:
        meta, _body = skill_registry.parse(
            Path(target).read_text(encoding='utf-8-sig'), source=str(target))
    except (OSError, UnicodeError, ValueError):
        return ''
    value = meta.get('version')
    return value.strip() if isinstance(value, str) and value.strip() else ''


def record(program, plan, digest, now=None):
    """导入台账：按目标相对路径记一行，同一目标再次导入时覆盖该行。

    T3 起每行带 ``source_url``／``source_ref``（远程可更新坐标，本地来源为空串）
    与 ``version``（入口文件 frontmatter，无则空串）；读取侧 ``_read_items``
    对旧行缺字段天然容忍。
    """
    path = ledger_path(program)
    items = _read_items(path)
    target = (plan['target'].parent if plan['kind'] == 'package' else plan['target']).resolve()
    key = str(target)
    for root in (skill_registry.default_user_root(program), skill_registry.default_root(program)):
        if target.is_relative_to(root.resolve()):
            key = target.relative_to(root.resolve()).as_posix()
            break
    items[key] = {'source': str(plan.get('ledger_source')
                              or (plan['source'].parent if plan['kind'] == 'package' else plan['source'])),
                  'kind': plan['kind'], 'name': plan['name'], 'sha256': digest,
                  'source_kind': plan.get('source_kind')
                                 or ('dir' if plan['kind'] == 'package' else 'file'),
                  'source_url': str(plan.get('source_url') or ''),
                  'source_ref': str(plan.get('source_ref') or ''),
                  'version': _frontmatter_version(plan['target']),
                  'scope': str(plan.get('scope') or 'user'),
                  'project': str(plan.get('project') or ''),
                  'imported_at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now or time.time()))}
    save(path, {'version': 1, 'items': items})
    return path


def perform_import(plan, program, now=None):
    """暂存 → 换入 → 试冻结 → 登记；任一步失败都回到导入前状态并抛出。"""
    program = Path(program)
    target_dir = plan['target_dir']
    target_dir.mkdir(parents=True, exist_ok=True)
    staging = target_dir / (STAGING_PREFIX + uuid.uuid4().hex[:8])
    staging.mkdir()
    package = plan['kind'] == 'package'
    final = plan['target'].parent if package else plan['target']
    staged = staging / final.name
    batch = None
    try:
        if package:
            _check_package_bounds(plan['source'].parent)
            shutil.copytree(plan['source'].parent, staged, ignore=shutil.ignore_patterns(*IGNORED_PARTS))
        else:
            shutil.copy2(plan['source'], staged)
        digest = _tree_digest(staged)
        if final.exists():
            records = recycle_paths(program, [final], '新增 SKILL 替换旧版：' + final.name, now=now)
            if not records:
                raise ImportBlocked('旧版 %s 未能移入回收站，已取消导入，原文件未改动。' % final.name)
            batch = _batch_of(program, records)
        os.replace(staged, final)
        try:
            _verify(plan['target'])
        except ImportBlocked:
            os.replace(final, staged)
            if batch is not None:
                restore_recycle_batch(program, batch)
            raise
        ledger = record(program, plan, digest, now=now)
        return {'target': plan['target'], 'digest': digest, 'ledger': ledger, 'replaced_batch': batch}
    finally:
        # 暂存区（含撤回的新版）只移走、不永久删除。
        if staging.exists():
            recycle_paths(program, [staging], '新增 SKILL 暂存区收尾', now=now)


def _batch_of(root, records):
    """由回收记录反推批次目录：recycle_path＝批次/原相对路径，去掉原路径的层数即批次。"""
    item = records[0]
    full = Path(root) / str(item['recycle_path'])
    return full.parents[len(Path(str(item['source'])).parts) - 1]


def _legacy_key_ok(key):
    """旧台账键必须是「阶段目录/条目」形式的相对路径，防止台账被改写后搬动任意文件。"""
    parts = Path(str(key)).parts
    return (len(parts) == 2 and not Path(str(key)).is_absolute() and '..' not in parts
            and not parts[1].startswith(STAGING_PREFIX)
            and bool(skill_registry.stage_from_path(Path(parts[0]) / parts[1])))


def migrate_legacy_imports(program=None, now=None):
    """把旧版导入到 ``程序/skills/`` 的 SKILL 迁到 ``程序/data/skills/``（后台维护，幂等）。

    只迁旧台账里登记过的条目：用户手动放进 skills/ 的文件与内置文件分不开，留在原处。
    每项迁移后按真实发送流程试冻结一次，失败就搬回原处并保留旧台账行；目标已存在
    （用户层已有同名条目）时不覆盖，同样保留。全部迁完后旧台账经回收服务收走。
    """
    program = Path(program or Path(__file__).resolve().parents[1])
    report = {'moved': [], 'kept': []}
    old_path = _legacy_ledger_path(program)
    old_items = _read_items(old_path)
    if not old_items:
        return report
    builtin = skill_registry.default_root(program)
    user = skill_registry.default_user_root(program)
    remaining, moved = {}, {}
    for key, row in old_items.items():
        source, target = builtin / str(key), user / str(key)
        if not _legacy_key_ok(key) or not source.exists() or target.exists():
            remaining[key] = row
            report['kept'].append(str(key))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        replace(source, target)
        skill_file = target / skill_registry.PACKAGE_SKILL_FILENAME if target.is_dir() else target
        try:
            _verify(skill_file)
        except ImportBlocked:
            replace(target, source)
            remaining[key] = row
            report['kept'].append(str(key))
            continue
        moved[key] = row
        report['moved'].append(str(key))
    if moved:
        items = _read_items(ledger_path(program))
        items.update(moved)
        save(ledger_path(program), {'version': 1, 'items': items})
    if remaining:
        if moved:
            save(old_path, {'version': 1, 'items': remaining})
    else:
        recycle_paths(program, [old_path], '旧导入台账已迁到 data/skills', now=now)
    return report


# ── 仓库（git）导入：install／update 同一入口，uninstall／validate／list 见下 ──

REPO_CLONE_TIMEOUT = 180
REPO_CLONE_PREFIX = '.仓库克隆-'
REPO_MAX_CANDIDATES = 100
_REF_TAIL = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._/-]*$')
_SCP_LIKE = re.compile(r'^[^/@\s:]+@[^/\s:]+:.+')


def _split_ref(spec):
    """从末尾剥 ``@ref``：只在头部仍像合法仓库地址时认；userinfo 里的 @ 不会被误剥。"""
    head, sep, tail = spec.rpartition('@')
    if sep and _REF_TAIL.match(tail) and head:
        if '://' in head:
            # URL：头部必须仍带非空路径，避免把 https://user:pass@host 的 @ 当成 ref。
            rest = head.split('://', 1)[1]
            if '/' in rest.split('@', 1)[-1]:
                return head, tail
        elif ':' not in head:
            return head, tail
    return spec, ''


def parse_repo_ref(text):
    """解析仓库来源 → ``{'kind': 'url'|'local', 'url'/'path': ..., 'ref': ..., 'label': ...}``。

    支持 ``owner/repo`` 简写（默认 github.com）、``https://``／``git@`` 完整地址、
    已存在的本地目录；``@分支`` 后缀可带在简写与 https URL 上。
    """
    raw = str(text or '').strip().strip('"').strip("'")
    if not raw:
        raise ImportBlocked('仓库地址为空')
    head, ref = _split_ref(raw)
    # 本地目录优先：先剥掉可能的 @ref 再判存在，带 ref 的本地路径不支持（clone 语义才有 ref）。
    local = Path(head)
    try:
        if local.is_dir():
            return {'kind': 'local', 'path': local, 'ref': ref, 'label': str(local)}
    except OSError:
        pass
    if _SCP_LIKE.match(raw):
        return {'kind': 'url', 'url': raw, 'ref': '', 'label': raw}
    if '://' in head:
        return {'kind': 'url', 'url': head, 'ref': ref, 'label': repo_label(head, ref)}
    if re.match(r'^[\w.-]+/[\w.-]+$', head):
        url = 'https://github.com/' + head
        return {'kind': 'url', 'url': url, 'ref': ref, 'label': repo_label(url, ref)}
    if re.match(r'^[A-Za-z]:[\\/]|^[~/\\.]', raw):
        # 盘符、用户目录、当前目录开头的一定是本地路径；不存在与否交给导入方报错。
        return {'kind': 'local', 'path': Path(raw), 'ref': ref, 'label': repo_label(str(raw))}
    if Path(raw).exists():
        raise ImportBlocked('「%s」存在但不是目录，仓库导入只接受目录或仓库地址' % raw)
    raise ImportBlocked('无法识别的仓库地址「%s」：支持 owner/repo、完整 URL（可带 @分支）或本地目录' % raw)


def repo_label(url, ref=''):
    """台账与界面用的来源标签：去掉 userinfo，不回显可能夹带的凭据。"""
    text = str(url or '')
    text = re.sub(r'://[^/@\s]+@', '://***@', text)
    host_path = text.split('://', 1)[-1]
    return host_path + ('@' + str(ref) if ref else '')


def _sanitize_git_error(text):
    """clone 失败信息脱敏：屏蔽 URL userinfo，截断长度。"""
    message = re.sub(r'://[^/@\s]+@', '://***@', str(text or ''))
    return message.strip()[-400:]


def _git_clone(url, ref, dest):
    """薄 git 层唯一动作：``git clone --depth 1 [--branch ref]``；失败抛 ImportBlocked。"""
    git = shutil.which('git')
    if not git:
        raise ImportBlocked('未找到 git 可执行文件，无法克隆仓库')
    args = [git, 'clone', '--depth', '1']
    if ref:
        args += ['--branch', ref]
    args += [url, str(dest)]
    try:
        done = platform_tools.run_process(args, capture_output=True, text=True,
                                          timeout=REPO_CLONE_TIMEOUT, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired as exc:
        raise ImportBlocked('git clone 超时（%d 秒）' % REPO_CLONE_TIMEOUT) from exc
    except OSError as exc:
        raise ImportBlocked('无法启动 git：%s' % exc) from exc
    if done.returncode != 0:
        detail = _sanitize_git_error(done.stderr or done.stdout)
        raise ImportBlocked('git clone 失败：%s' % (detail or '退出码 %d' % done.returncode))


def _repo_candidates(root):
    """扫描仓库内容：含 ``SKILL.md`` 的目录＝外部包（不再向内递归），
    其余位置的 ``*.skill.md``＝单文件清单。点开头目录与 ``.git`` 一律跳过。"""
    root = Path(root)
    candidates = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames
                             if not d.startswith('.') and d != '__pycache__')
        current = Path(dirpath)
        if skill_registry.PACKAGE_SKILL_FILENAME in filenames:
            candidates.append({'source': current / skill_registry.PACKAGE_SKILL_FILENAME,
                               'kind': 'package'})
            dirnames[:] = []          # 包是整体，一包内不再找第二个包或清单
            continue
        for name in sorted(filenames):
            if name.endswith(skill_registry.SKILL_SUFFIX):
                candidates.append({'source': current / name, 'kind': 'manifest'})
    if len(candidates) > REPO_MAX_CANDIDATES:
        raise ImportBlocked('仓库内 SKILL 候选超过 %d 个上限' % REPO_MAX_CANDIDATES)
    return candidates


def _candidate_stage(source, clone_root, stage_hint):
    """阶段判定顺序：frontmatter ``stage`` → 仓库内 ``NN`` 目录 → 面板当前阶段提示。"""
    try:
        meta, _body = skill_registry.parse(
            Path(source).read_text(encoding='utf-8-sig'), source=str(source))
    except (OSError, UnicodeError):
        meta = {}
    sid = skill_registry.stage_id(meta.get('stage', ''))
    if not sid:
        try:
            relative = Path(source).relative_to(Path(clone_root))
        except ValueError:
            relative = Path(source)
        sid = skill_registry.stage_from_path(relative)
    return sid or str(stage_hint or '')


def _stage_dir_for(registry, stage, layer='user'):
    """按层取阶段写入目录；轻量 registry 替身没有 ``stage_directory_for`` 时退回用户层口径。"""
    fn = getattr(registry, 'stage_directory_for', None)
    if fn is not None:
        return fn(stage, layer)
    return registry.user_stage_directory_for(stage) if layer == 'user' else None


def _candidate_plans(candidates, root, registry, stage_hint, layer='user'):
    """候选 → ``(plans, problems, errors)``：阶段判定与 ``plan_import`` 只读预检；同目标去重。

    仓库导入与压缩包导入共用：``root`` 是候选所在的本地树（克隆目录或解压目录）；
    ``layer`` 是导入目标层（``'user'`` 全局／``'project'`` 项目级）。
    """
    plans, problems, errors = [], [], []
    seen_targets = set()
    for candidate in candidates:
        source = candidate['source']
        stage = _candidate_stage(source, root, stage_hint)
        if not stage:
            errors.append('%s：无法识别阶段（frontmatter stage、NN 目录与阶段提示都没有）'
                          % source.name)
            continue
        try:
            plan = plan_import(source, _stage_dir_for(registry, stage, layer),
                               stage, registry)
        except ImportBlocked as exc:
            errors.append('%s：%s' % (source.name, exc))
            continue
        key = (str(plan['target'].parent if plan['kind'] == 'package' else plan['target']).casefold(),)
        if key in seen_targets:
            errors.append('%s：与另一候选目标重复，跳过' % source.name)
            continue
        seen_targets.add(key)
        plans.append(plan)
        problems.extend('%s：%s' % (plan['name'], problem) for problem in plan['problems'])
    return plans, problems, errors


class _InstallSource(NamedTuple):
    """``_install_candidate_plans`` 的来源信息：台账来源、界面标签、来源类别与提示称谓。

    ``source_url``／``source_ref`` 是 T3 远程来源的可更新坐标（仓库地址、ref），
    写进每行台账供 T4 更新检测；本地文件／文件夹／压缩包来源留空。
    """
    ledger_source: str
    label: str
    source_kind: str = ''
    origin: str = '仓库'
    source_url: str = ''
    source_ref: str = ''


def _install_candidate_plans(plans, problems, errors, program, confirm, source):
    """问题汇总 → 确认 → 逐候选换入 → 报告；``confirm`` 收到汇总文本返回真才继续。

    ``source`` 是 :class:`_InstallSource`：``origin`` 是来源称谓（仓库／压缩包），
    只进提示文案；``ledger_source`` 与 ``source_kind`` 写进每行台账（T4 更新检测
    按它分辨本地目录／压缩包／仓库源）。T9：确认框统一带 ``untrusted_source_notice``
    来源与注入警示；包内可执行内容（``import_alerts``）在无字段问题时同样触发确认。
    """
    alerts = import_alerts(plans)
    if problems or (confirm is not None and alerts):
        parts = [untrusted_source_notice(source.label or source.origin, plans=plans)]
        if problems:
            parts.append('%s导入前发现以下问题：\n\n' % source.origin
                         + '\n'.join('· ' + item for item in problems))
        if errors:
            parts.append('以下条目将跳过：\n' + '\n'.join('· ' + item for item in errors))
        parts.append('仍要导入吗？')
        if confirm is None or not confirm('\n\n'.join(parts)):
            raise ImportBlocked('已取消%s导入' % source.origin)
    elif errors and not plans:
        raise ImportBlocked('没有可导入的 SKILL：\n' + '\n'.join('· ' + e for e in errors))
    installed, failed = [], []
    for plan in plans:
        plan['ledger_source'] = source.ledger_source
        if source.source_kind:
            plan['source_kind'] = source.source_kind
        if source.source_url:
            plan['source_url'] = source.source_url
        if source.source_ref:
            plan['source_ref'] = source.source_ref
        try:
            perform_import(plan, program)
            installed.append({'name': plan['name'], 'kind': plan['kind'],
                              'stage': plan.get('stage', ''), 'target': str(plan['target'])})
        except (ImportBlocked, OSError, ValueError) as exc:
            failed.append({'name': plan['name'], 'error': str(exc)})
    if not installed and not failed:
        raise ImportBlocked('没有可导入的 SKILL：\n' + '\n'.join('· ' + e for e in errors))
    return {'label': source.label, 'installed': installed, 'failed': failed,
            'skipped': errors, 'candidates': len(plans) + len(errors)}


def import_from_repo(text, program, registry, stage_hint='', confirm=None, layer='user'):
    """仓库导入主入口（install／update 同一实现）：解析 → 取源码 → 扫描 → 逐候选预检
    → 确认 → 逐候选换入。任一候选失败只影响该候选，已成功的不回滚。

    ``confirm`` 收到汇总问题文本，返回真才继续换入；``None`` 时有问题即中止。
    返回 ``{'label', 'installed', 'failed', 'skipped', 'candidates'}``。
    """
    program = Path(program)
    spec = parse_repo_ref(text)
    staging = None
    try:
        if spec['kind'] == 'local':
            root = Path(spec['path'])
            if root.exists() and not root.is_dir():
                raise ImportBlocked('「%s」存在但不是目录，仓库导入只接受目录或仓库地址' % root)
            if not root.is_dir():
                raise ImportBlocked('本地目录不存在：%s' % root)
            label = repo_label(str(root))
        else:
            staging = (skill_registry.default_user_root(program)
                       / (REPO_CLONE_PREFIX + uuid.uuid4().hex[:8]))
            staging.parent.mkdir(parents=True, exist_ok=True)
            _git_clone(spec['url'], spec.get('ref', ''), staging)
            root = staging
            label = spec['label']
        candidates = _repo_candidates(root)
        if not candidates:
            raise ImportBlocked('仓库中没有找到 SKILL.md 或 *.skill.md')
        plans, problems, errors = _candidate_plans(candidates, root, registry, stage_hint,
                                                 layer=layer)
        remote = spec['kind'] == 'url'
        return _install_candidate_plans(
            plans, problems, errors, program, confirm,
            _InstallSource(ledger_source=label, label=label,
                           source_kind='repo', origin='仓库',
                           source_url=spec['url'] if remote else '',
                           source_ref=spec.get('ref', '') if remote else ''))
    finally:
        if staging is not None and staging.exists():
            recycle_paths(program, [staging], 'SKILL 仓库克隆暂存收尾')


def update_from_repo(text, program, registry, stage_hint='', confirm=None, layer='user'):
    """skill-mgr ``update``：同来源刷新＝重新取最新内容走同一导入管线，旧版进回收站。"""
    return import_from_repo(text, program, registry, stage_hint=stage_hint, confirm=confirm,
                            layer=layer)


def uninstall_skill(program, registry, name):
    """skill-mgr ``uninstall``：按注册名回收站移除；整包收目录、清单收文件。"""
    program = Path(program)
    matches = [skill for skill in registry.getAll() if skill.name == str(name or '').strip()]
    if not matches:
        raise ImportBlocked('注册表中没有 SKILL「%s」' % name)
    skill = matches[0]
    path = getattr(skill, 'path', None)
    if path is None:
        raise ImportBlocked('SKILL「%s」没有可定位的文件' % name)
    path = Path(path)
    roots = list(skill_registry.skill_roots(program))
    project_skills = getattr(registry, 'project_skills', None)
    if isinstance(project_skills, (str, Path)):
        roots.append(Path(project_skills).resolve())
    if not path.is_file() or not any(path.resolve().is_relative_to(root) for root in roots):
        raise ImportBlocked('SKILL「%s」不在可卸载目录' % name)
    target = path.parent if skill.get(skill_registry.IMPORTED_PACKAGE_FLAG, False) else path
    records = recycle_paths(program, [target], '卸载 SKILL：' + skill.name)
    if not records:
        raise ImportBlocked('SKILL「%s」未能移入回收站' % name)
    forget_ledger_targets(program, [target])
    return {'name': skill.name, 'target': str(target)}


def validate_skill(path):
    """skill-mgr ``validate``：与导入同一道试冻结闸；返回 ``(True, '')`` 或 ``(False, 原因)``。"""
    try:
        _verify(Path(path))
    except ImportBlocked as exc:
        return False, str(exc)
    return True, ''


# ── 台账消费（T4）：更新检测与删除闭环 ──

UPDATE_STATES = ('unchanged', 'source-newer', 'local-modified', 'source-missing')


def ledger_items(program):
    """导入台账行（只读）：``{key: row}``；更新检测与界面展示共用同一读取口径。"""
    return _read_items(ledger_path(Path(program)))


def forget_ledger_targets(program, targets):
    """删除闭环：已回收的安装目标同步摘除台账行；返回摘除行数（幂等）。

    台账键是目标相对用户层／内置层根的路径；目标不在两层根下或没有对应行时跳过。
    与 ``migrate_legacy_imports`` 同一 ``save()`` 入口写回。
    """
    program = Path(program)
    items = _read_items(ledger_path(program))
    if not items:
        return 0
    roots = (skill_registry.default_user_root(program).resolve(),
             skill_registry.default_root(program).resolve())
    doomed = set()
    for target in targets:
        path = Path(target).resolve()
        doomed.add(str(path))          # 项目层台账键是绝对路径，直接命中
        for root in roots:
            if path.is_relative_to(root):
                doomed.add(path.relative_to(root).as_posix())
                break
    removed = [key for key in doomed if key in items]
    if removed:
        for key in removed:
            items.pop(key, None)
        save(ledger_path(program), {'version': 1, 'items': items})
    return len(removed)


def _resolve_ledger_target(program, key):
    """台账键 → 已安装目标：绝对键（项目层）直用；相对键先用户层后内置层。"""
    candidate = Path(str(key))
    if candidate.is_absolute() and candidate.exists():
        return candidate
    for root in (skill_registry.default_user_root(program).resolve(),
                 skill_registry.default_root(program).resolve()):
        candidate = root / str(key)
        if candidate.exists():
            return candidate
    return None


def registry_for_ledger_row(program, row, base=None):
    """台账行 → 对应层的注册表：``scope=='project'`` 的行用行内 ``project`` 建项目层注册表，
    其余返回 ``base``（调用方给的全局注册表）。更新检测与探针共用同一口径。"""
    if isinstance(row, dict) and str(row.get('scope') or '') == 'project':
        project = str(row.get('project') or '') or None
        return skill_registry.Registry(
            skill_registry.default_root(program),
            user_root=skill_registry.default_user_root(program),
            project_root=project)
    return base


def _row_layer(row):
    return 'project' if isinstance(row, dict) and str(row.get('scope') or '') == 'project' else 'user'


def _candidate_ledger_key(candidate, root, registry, layer='user'):
    """候选 → 台账键：用户层 ``<阶段目录名>/<条目名>``；项目层为安装目标绝对路径。
    阶段判不出返回 None（不猜）。"""
    stage = _candidate_stage(candidate['source'], root, '')
    if not stage:
        return None
    entry = (candidate['source'].parent.name if candidate['kind'] == 'package'
             else candidate['source'].name)
    if layer == 'project':
        stage_dir = getattr(registry, 'project_stage_directory_for', lambda sid: None)(stage)
        if stage_dir is None:
            return None
        target = (stage_dir / candidate['source'].parent.name / entry
                  if candidate['kind'] == 'package' else stage_dir / entry)
        return str(target.resolve())
    stage_dir = getattr(registry, 'user_stage_directory_for', lambda sid: None)(stage)
    if stage_dir is None:
        return None
    return Path(stage_dir).name + '/' + entry


def _entry_signatures(root, registry, layer='user'):
    """候选树 → ``({台账键: 内容摘要}, {台账键: frontmatter version})``；与安装同口径。"""
    digests, versions = {}, {}
    for candidate in _repo_candidates(Path(root)):
        key = _candidate_ledger_key(candidate, root, registry, layer)
        if not key:
            continue
        content = (candidate['source'].parent if candidate['kind'] == 'package'
                   else candidate['source'])
        try:
            digests[key] = _tree_digest(content)
            versions[key] = _frontmatter_version(candidate['source'])
        except OSError:
            continue
    return digests, versions


def _entry_digests(root, registry, layer='user'):
    """兼容包装：``skill_archive``／``skill_remote_service`` 探针只取摘要半边。"""
    return _entry_signatures(root, registry, layer)[0]


def _version_key(text):
    """版本串 → 可比较元组：数字段按数值、其余按字符串（``1.10`` 大于 ``1.9``）。"""
    key = []
    for part in re.split(r'[.\-+_]', str(text or '').strip()):
        if part:
            key.append((0, int(part)) if part.isdigit() else (1, part))
    return tuple(key)


def _version_compare(candidate, current):
    """候选版本 vs 台账版本 → -1/0/1；任一侧缺版本返回 ``None`` 交摘要判定。"""
    if not candidate or not current:
        return None
    left, right = _version_key(candidate), _version_key(current)
    return (left > right) - (left < right)


def _source_version(row):
    """file/dir 来源的入口 ``version``：文件取自身，目录取包根 ``SKILL.md``。"""
    source = Path(str(row.get('source') or ''))
    if not source.exists():
        return ''
    entry = source if source.is_file() else source / skill_registry.PACKAGE_SKILL_FILENAME
    return _frontmatter_version(entry) if entry.is_file() else ''


def _entry_status(key, row, digests, versions=None):
    """候选签名表 → 行状态：候选消失→``source-missing``；版本可比时先比版本再比摘要。"""
    if not digests:
        return 'source-missing'
    digest = digests.get(key)
    if digest is None:
        return 'source-missing'
    verdict = _version_compare((versions or {}).get(key, ''),
                               str(row.get('version') or ''))
    if verdict is not None:
        if verdict > 0:
            return 'source-newer'
        if verdict < 0:
            return 'unchanged'
    return 'unchanged' if digest == str(row.get('sha256') or '') else 'source-newer'


def _clone_entry_signatures(url, ref, program, registry, layer='user'):
    """远程仓库行：重新 ``git clone --depth 1`` 到暂存（用后回收）取候选签名。"""
    program = Path(program)
    staging = (skill_registry.default_user_root(program)
               / (REPO_CLONE_PREFIX + uuid.uuid4().hex[:8]))
    staging.parent.mkdir(parents=True, exist_ok=True)
    try:
        _git_clone(url, ref, staging)
        try:
            return _entry_signatures(staging, registry, layer)
        except ImportBlocked:
            return None
    except ImportBlocked:
        return None
    finally:
        if staging.exists():
            recycle_paths(program, [staging], 'SKILL 更新检测克隆暂存收尾')


def _default_source_status(key, row, program, registry, cache, layer='user'):
    """默认来源判定：file/dir 本地路径、repo 本地目录与远程克隆；其余返回 None 交探针。"""
    kind = str(row.get('source_kind') or
               ('dir' if row.get('kind') == 'package' else 'file'))
    if kind in ('file', 'dir'):
        source = Path(str(row.get('source') or ''))
        if not source.exists():
            return 'source-missing'
        verdict = _version_compare(_source_version(row), str(row.get('version') or ''))
        if verdict is not None:
            if verdict > 0:
                return 'source-newer'
            if verdict < 0:
                return 'unchanged'
        return ('unchanged' if _tree_digest(source) == str(row.get('sha256') or '')
                else 'source-newer')
    if kind != 'repo':
        return None
    if row.get('source_url'):
        signature = (str(row['source_url']), str(row.get('source_ref') or ''), layer,
                     str(row.get('project') or ''))
        if signature not in cache:
            cache[signature] = _clone_entry_signatures(
                signature[0], signature[1], program, registry, layer)
        pair = cache[signature]
        digests, versions = pair if pair else ({}, {})
    else:
        source = Path(str(row.get('source') or ''))
        try:
            digests, versions = (_entry_signatures(source, registry, layer)
                                 if source.is_dir() else ({}, {}))
        except ImportBlocked:
            digests, versions = {}, {}
    return _entry_status(key, row, digests, versions)


def _installed_status(target, row):
    """已安装目标完整性 → ``'local-modified'``／``'missing'``／``None``（与台账一致）。

    ``check_updates`` 与 ``local_modifications`` 共用同一判定：目标 ``_tree_digest``
    与台账 ``sha256`` 不一致即 ``local-modified``（用户手改），读不出按缺失处理。
    """
    try:
        installed = _tree_digest(target)
    except OSError:
        return 'missing'
    return 'local-modified' if installed != str(row.get('sha256') or '') else None


def local_modifications(program):
    """用户层台账行的本地完整性体检 → ``{SKILL 名: 台账键}``；只含被手改过的行。

    与 ``check_updates`` 同一判定函数（``_installed_status``），不重算来源状态、
    不碰项目层行；目标缺失／不可读不算手改（归 ``source-missing`` 口径）。
    """
    modified = {}
    for key, row in ledger_items(Path(program)).items():
        if not isinstance(row, dict) or _row_layer(row) != 'user':
            continue
        target = _resolve_ledger_target(program, key)
        if target is None or _installed_status(target, row) != 'local-modified':
            continue
        leaf = Path(str(key).replace('\\', '/')).name
        name = str(row.get('name') or '') or (
            leaf[:-len(skill_registry.SKILL_SUFFIX)]
            if leaf.endswith(skill_registry.SKILL_SUFFIX) else leaf)
        if name:
            modified[name] = key
    return modified


def program_of_registry(registry):
    """注册表 → 程序根：``user_root``（``<程序>/data/skills``）上溯两级；形状不符返回 ``None``。"""
    root = getattr(registry, 'user_root', None)
    if not root:
        return None
    root = Path(root).resolve()
    if root.parent.name != 'data' or root.name != 'skills':
        return None
    return root.parent.parent


def check_updates(program, *, probe=None, project=None):
    """遍历导入台账做更新体检 → ``{台账键: UPDATE_STATES 之一}``。

    判定顺序：已安装目标缺失→``source-missing``；已安装内容摘要与台账 ``sha256``
    不一致→``local-modified``（用户手改过，不提示覆盖）；其余按来源重算：
    ``file``／``dir`` 本地路径直读、``repo`` 本地目录重扫候选、``repo`` 远程
    重新克隆；``archive`` 与 T3 远程链接行交给 ``probe(key, row)``（返回同组
    状态或 ``None`` 表示不接管）；探针缺省、拒绝、出错或来源不可用→
    ``source-missing``。只读不写：不改台账、不动已安装内容。

    T5：``scope=='project'`` 的台账行按行内 ``project`` 各自建项目层注册表求
    候选摘要（跨项目互不串扰）；给了 ``project`` 时只评估该项目的行与用户层行，
    其他项目的行不出现在结果里。
    """
    program = Path(program)
    wanted = Path(project).resolve() if project else None
    base_registry = skill_registry.Registry(
        skill_registry.default_root(program),
        user_root=skill_registry.default_user_root(program))
    project_registries = {}

    def _registry_for(row):
        layer = _row_layer(row)
        if layer != 'project':
            return base_registry
        owner = str(row.get('project') or '')
        if owner not in project_registries:
            project_registries[owner] = skill_registry.Registry(
                skill_registry.default_root(program),
                user_root=skill_registry.default_user_root(program),
                project_root=owner or None)
        return project_registries[owner]

    statuses = {}
    cache = {}
    for key, row in ledger_items(program).items():
        if not isinstance(row, dict):
            statuses[key] = 'source-missing'
            continue
        layer = _row_layer(row)
        if wanted is not None:
            if layer == 'project':
                owner = str(row.get('project') or '')
                if not owner or Path(owner).resolve() != wanted:
                    continue
            # 用户层行任何项目视图都评估
        registry = _registry_for(row)
        target = _resolve_ledger_target(program, key)
        if target is None:
            statuses[key] = 'source-missing'
            continue
        installed = _installed_status(target, row)
        if installed == 'missing':
            statuses[key] = 'source-missing'
            continue
        if installed == 'local-modified':
            statuses[key] = 'local-modified'
            continue
        kind = str(row.get('source_kind') or
                   ('dir' if row.get('kind') == 'package' else 'file'))
        status = None
        if probe is not None and (kind == 'archive'
                                  or (kind == 'repo' and bool(row.get('source_url')))):
            try:
                status = probe(key, row)
            except Exception:
                app_logging.swallowed('skill_import_service 更新探针失败')
                status = None
        if status is None:
            status = _default_source_status(key, row, program, registry, cache, layer)
        statuses[key] = status or 'source-missing'
    return statuses

