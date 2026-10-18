#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核对 AIGC 创作全流程外部包的更新，不修改包内容。

默认读取 ``程序/维护记录/AIGC包阶段归属.json`` 的 ``absorbed_commit``，比较包内
``absorbed_commit..HEAD`` 的 Markdown、Python 与 JSON 变化，并报告阶段 SKILL 的引用
断链风险与完全未引用的引擎目录。

``--accept`` 是唯一写文件动作，且只更新归属表中的 ``absorbed_commit``。
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit


SCRIPT = Path(__file__).resolve()
PROGRAM_ROOT = SCRIPT.parents[2]
DEFAULT_PACKAGE = PROGRAM_ROOT / 'skills' / '00全流程SKILL' / 'AIGC创作全流程'
DEFAULT_OWNERSHIP = PROGRAM_ROOT / '维护记录' / 'AIGC包阶段归属.json'
DEFAULT_SKILLS_ROOT = PROGRAM_ROOT / 'skills'

INTERESTING_SUFFIXES = {'.md', '.py', '.json'}
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg',
                  '.tif', '.tiff', '.ico', '.avif', '.heic', '.psd'}
_LINK_RE = re.compile(r'\]\(\s*(<[^>]+>|[^)]+)\s*\)')
_REFERENCE_TARGETS = None


def _fallback_reference_targets(text):
    """skill_registry 不可用时的最小 Markdown 链接解析。"""
    out = []
    for match in _LINK_RE.finditer(text or ''):
        link = match.group(1).strip()
        if link.startswith('<'):
            link = link[1:-1]
        else:
            link = re.sub(r'''\s+["'][^"']*["']\s*$''', '', link)
        parts = urlsplit(link.replace('\\', '/'))
        if parts.scheme or parts.netloc or not parts.path:
            continue
        out.append({'raw': link, 'path': Path(unquote(parts.path)),
                    'fragment': parts.fragment})
    return out


def _reference_targets(text):
    """复用 skill_registry.reference_targets；失败时退回本地最小实现。"""
    global _REFERENCE_TARGETS
    if _REFERENCE_TARGETS is None:
        sys.path.insert(0, str(PROGRAM_ROOT))
        try:
            import skill_registry
            _REFERENCE_TARGETS = skill_registry.reference_targets
        except Exception:
            _REFERENCE_TARGETS = _fallback_reference_targets
        finally:
            try:
                sys.path.remove(str(PROGRAM_ROOT))
            except ValueError:
                pass
    return _REFERENCE_TARGETS(text)


def _inside_package(base, raw_path, package):
    """把相对／绝对路径解析为包内 POSIX 相对路径，不要求在磁盘上存在。"""
    candidate = Path(raw_path)
    paths = [candidate] if candidate.is_absolute() else [base / candidate]
    package_root = package.resolve()
    for path in paths:
        try:
            rel = path.resolve(strict=False).relative_to(package_root)
        except (OSError, ValueError):
            continue
        if rel.parts and rel.parts[0] == '.git':
            return None
        return rel.as_posix()
    return None


def _source_record(source, skills_root, json_source=False):
    if json_source:
        return {'stage': '总控', 'source': 'skills/00全流程SKILL/总控.json'}
    try:
        rel = source.relative_to(skills_root)
    except ValueError:
        rel = source
    top = rel.parts[0] if rel.parts else source.parent.name
    match = re.match(r'^(\d{2})', top)
    stage = match.group(1) if match else top
    return {'stage': stage, 'source': rel.as_posix()}


def _add_source(link_index, target, source):
    if not target:
        return
    rows = link_index[target]
    key = (source['stage'], source['source'])
    if key not in {(row['stage'], row['source']) for row in rows}:
        rows.append(source)


def _skill_links(skills_root, package):
    links = defaultdict(list)
    for source_path in sorted(skills_root.rglob('*.skill.md')):
        if not source_path.is_file():
            continue
        try:
            text = source_path.read_text(encoding='utf-8')
        except OSError:
            continue
        source = _source_record(source_path, skills_root)
        for item in _reference_targets(text):
            raw = item.get('path')
            if raw is None:
                continue
            target = _inside_package(source_path.parent, raw, package)
            _add_source(links, target, source)
    return links


def _json_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _json_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _json_strings(item)


def _json_links(skills_root, package):
    links = defaultdict(list)
    manifest = skills_root / '00全流程SKILL' / '总控.json'
    if not manifest.is_file():
        return links
    try:
        data = json.loads(manifest.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return links
    source = _source_record(manifest, skills_root, json_source=True)
    for text in _json_strings(data):
        text = str(text or '').strip()
        if not text or len(text) > 1000:
            continue
        parsed = [item.get('path') for item in _reference_targets(text)
                  if item.get('path') is not None]
        if not parsed:
            parts = urlsplit(text.replace('\\', '/'))
            if parts.scheme or parts.netloc or not parts.path:
                continue
            parsed = [Path(unquote(parts.path))]
        for raw in parsed:
            for base in (skills_root.parent, manifest.parent):
                target = _inside_package(base, raw, package)
                if target:
                    _add_source(links, target, source)
                    break
    return links


def _link_index(skills_root, package):
    links = _skill_links(skills_root, package)
    for target, sources in _json_links(skills_root, package).items():
        for source in sources:
            _add_source(links, target, source)
    return dict(links)


def _git(package, args):
    return subprocess.run(['git', *args], cwd=str(package), shell=False,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=60, check=False)


def _git_text(package, args):
    result = _git(package, args)
    if result.returncode != 0:
        return None, result.stderr.decode('utf-8', 'replace').strip()
    return result.stdout.decode('utf-8', 'replace').strip(), ''


def _inspect_package(package):
    if not package.is_dir():
        return None, '包目录不存在：%s' % package
    top, error = _git_text(package, ['rev-parse', '--show-toplevel'])
    if error:
        return None, '包目录不是 Git 仓库：%s' % package
    try:
        same_root = Path(top).resolve() == package.resolve()
    except OSError:
        same_root = False
    if not same_root:
        return None, '包目录不是独立 Git 仓库：%s' % package
    head, error = _git_text(package, ['rev-parse', 'HEAD'])
    if error or not head:
        return None, '无法读取包 HEAD：%s' % (error or '未知错误')
    return {'head': head}, None


def _read_ownership(path):
    if not path.is_file():
        return None, '归属表不存在：%s' % path
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        return None, '归属表无法读取或不是有效 JSON：%s' % type(exc).__name__
    if not isinstance(data, dict):
        return None, '归属表根节点必须是 JSON 对象'
    return data, None


def _check_baseline(package, baseline):
    if not str(baseline or '').strip():
        return '归属表缺少 absorbed_commit'
    commit = str(baseline).strip()
    result = _git(package, ['cat-file', '-e', commit + '^{commit}'])
    if result.returncode != 0:
        return 'absorbed_commit 不在包的历史中：%s' % commit
    result = _git(package, ['merge-base', '--is-ancestor', commit, 'HEAD'])
    if result.returncode != 0:
        return 'absorbed_commit 不是 HEAD 的祖先：%s' % commit
    return None


def _parse_diff(payload):
    fields = [item for item in payload.split(b'\0') if item]
    rows = []
    index = 0
    while index < len(fields):
        status = fields[index].decode('utf-8', 'replace').strip()
        index += 1
        if not status:
            continue
        change = status[0]
        if change in {'R', 'C'}:
            if index + 1 >= len(fields):
                break
            old_path = fields[index].decode('utf-8', 'replace')
            path = fields[index + 1].decode('utf-8', 'replace')
            index += 2
        else:
            if index >= len(fields):
                break
            old_path = None
            path = fields[index].decode('utf-8', 'replace')
            index += 1
        if change in {'A', 'M', 'D', 'R'}:
            rows.append({'change': change, 'status': status,
                         'path': path.replace('\\', '/'), 'old_path': old_path})
    return rows


def _relevant(path):
    if not path:
        return False
    pure = Path(path)
    if pure.parts and pure.parts[0] in {'.git', 'assets'}:
        return False
    suffix = pure.suffix.lower()
    return suffix in INTERESTING_SUFFIXES and suffix not in IMAGE_SUFFIXES


def _engine_of(path):
    parts = Path(path).parts
    return parts[0] if len(parts) > 1 else '(包根)'


def _stage_text(stages, note=''):
    labels = [str(item) for item in (stages or []) if str(item)]
    if note:
        labels.append(str(note))
    return '、'.join(labels) if labels else '待定'


def _linked_stages(sources):
    stages = []
    for source in sources or []:
        stage = str(source.get('stage') or '未归类')
        if stage not in stages:
            stages.append(stage)
    return stages


def _existing_files(engine_dir):
    for root, dirs, files in os.walk(engine_dir):
        dirs[:] = [name for name in dirs if name != '.git']
        for name in files:
            yield Path(root) / name


def _build_report(package, head, baseline, ownership, skills_root):
    table = ownership.get('engines') if isinstance(ownership, dict) else {}
    if not isinstance(table, dict):
        table = {}
    diff_result = _git(package, ['diff', '--name-status', '-z', '--find-renames',
                                 baseline + '..HEAD', '--'])
    if diff_result.returncode != 0:
        detail = diff_result.stderr.decode('utf-8', 'replace').strip()
        raise RuntimeError(detail or 'git diff 失败')
    parsed = _parse_diff(diff_result.stdout)
    links = _link_index(skills_root, package)

    changes = []
    for row in parsed:
        if not (_relevant(row['path']) or _relevant(row.get('old_path'))):
            continue
        sources = links.get(row['path'], [])
        engine = _engine_of(row['path'])
        meta = table.get(engine) if isinstance(table.get(engine), dict) else {}
        changes.append({
            'change': row['change'],
            'status': row['status'],
            'path': row['path'],
            'old_path': row.get('old_path'),
            'engine': engine,
            'stages': list(meta.get('stages') or []),
            'note': str(meta.get('note') or ''),
            'linked': bool(sources),
            'linked_by': sources,
        })

    broken = []
    for row in parsed:
        if row['change'] == 'D':
            targets = [(row['path'], '已删除')]
        elif row['change'] == 'R' and row.get('old_path'):
            targets = [(row['old_path'].replace('\\', '/'), '已改名')]
        else:
            continue
        for path, reason in targets:
            sources = links.get(path, [])
            if sources:
                broken.append({'file': path, 'reason': reason,
                               'status': row['status'],
                               'new_path': row['path'] if row['change'] == 'R' else None,
                               'linked_by': sources})

    unlinked = []
    engine_dirs = sorted(path for path in package.iterdir()
                         if path.is_dir() and path.name != '.git')
    for engine_dir in engine_dirs:
        linked_file = None
        for file_path in _existing_files(engine_dir):
            try:
                rel = file_path.relative_to(package).as_posix()
            except ValueError:
                continue
            if rel in links:
                linked_file = rel
                break
        if linked_file is None:
            meta = table.get(engine_dir.name) if isinstance(table.get(engine_dir.name), dict) else {}
            unlinked.append({'engine': engine_dir.name,
                             'stages': list(meta.get('stages') or []),
                             'note': str(meta.get('note') or '')})

    return {'ok': True,
            'baseline': {'absorbed_commit': baseline, 'head': head,
                         'is_current': baseline == head},
            'changes': changes,
            'broken_links': broken,
            'unlinked_engines': unlinked,
            'engines': table}


def _print_text(report, accepted=False):
    baseline = report['baseline']
    print('AIGC 创作全流程包核对')
    print('当前基线 commit：%s' % baseline['absorbed_commit'])
    print('包 HEAD：%s' % baseline['head'])
    if accepted:
        print('已把归属表基线更新为包 HEAD。')

    changes = report['changes']
    print('\n变动清单（%d）' % len(changes))
    if not changes:
        print('  无')
    for row in changes:
        stages = _stage_text(row.get('stages'), row.get('note'))
        linked = '是（%s）' % '、'.join(_linked_stages(row.get('linked_by'))) \
            if row.get('linked') else '否'
        line = '  [%s] %s | 引擎: %s | 建议阶段: %s | 当前被链接: %s' % (
            row['status'], row['path'], row['engine'], stages, linked)
        if row.get('old_path'):
            line += ' | 旧名: %s' % row['old_path']
        print(line)

    broken = report['broken_links']
    print('\n断链风险（%d）' % len(broken))
    if not broken:
        print('  无')
    for row in broken:
        sources = '、'.join('%s:%s' % (item.get('stage'), item.get('source'))
                            for item in row.get('linked_by') or [])
        extra = '，新名: %s' % row['new_path'] if row.get('new_path') else ''
        print('  [断链风险] %s（%s%s）仍被 %s 链接' % (
            row['file'], row['reason'], extra, sources))

    unlinked = report['unlinked_engines']
    print('\n未链接引擎（%d）' % len(unlinked))
    if not unlinked:
        print('  无')
    for row in unlinked:
        stages = _stage_text(row.get('stages'), row.get('note'))
        print('  - %s | 建议阶段: %s' % (row['engine'], stages))


def _emit_error(message, as_json=False):
    if as_json:
        print(json.dumps({'ok': False, 'error': message}, ensure_ascii=False, indent=2))
    else:
        print('错误：%s' % message)


def _default_program_root(skills_root):
    return skills_root.parent if skills_root.name == 'skills' else PROGRAM_ROOT


def main(argv=None):
    parser = argparse.ArgumentParser(description='只读核对 AIGC 创作全流程包的更新')
    parser.add_argument('--json', action='store_true', help='输出机器可读 JSON')
    parser.add_argument('--baseline-show', action='store_true',
                        help='只打印当前基线 commit 与包 HEAD')
    parser.add_argument('--accept', action='store_true',
                        help='把 absorbed_commit 更新为包当前 HEAD（唯一写入动作）')
    parser.add_argument('--package', type=Path, default=DEFAULT_PACKAGE,
                        help='包目录（测试／替代安装用）')
    parser.add_argument('--ownership', type=Path, default=DEFAULT_OWNERSHIP,
                        help='阶段归属表路径（测试／替代安装用）')
    parser.add_argument('--skills-root', type=Path, default=DEFAULT_SKILLS_ROOT,
                        help='阶段 SKILL 根目录（测试／替代安装用）')
    args = parser.parse_args(argv)

    package = args.package.expanduser().resolve()
    ownership_path = args.ownership.expanduser().resolve()
    skills_root = args.skills_root.expanduser().resolve()

    try:
        ownership, ownership_error = _read_ownership(ownership_path)
        state, package_error = _inspect_package(package)

        if args.baseline_show:
            baseline_value = None
            if ownership is not None:
                baseline_value = ownership.get('absorbed_commit')
            payload = {'ok': package_error is None and ownership_error is None,
                       'baseline_commit': baseline_value,
                       'head': state.get('head') if state else None}
            if ownership_error:
                payload['baseline_error'] = ownership_error
            if package_error:
                payload['package_error'] = package_error
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print('当前基线 commit：%s' % (baseline_value or '（缺失）'))
                print('包 HEAD：%s' % ((state or {}).get('head') or '（不可用）'))
                if ownership_error:
                    print('基线提示：%s' % ownership_error)
                if package_error:
                    print('包提示：%s' % package_error)
            return 0

        if package_error:
            _emit_error(package_error, args.json)
            return 0
        if ownership_error:
            _emit_error(ownership_error, args.json)
            return 0

        head = state['head']
        accepted = False
        if args.accept:
            ownership['absorbed_commit'] = head
            try:
                ownership_path.write_text(
                    json.dumps(ownership, ensure_ascii=False, indent=2) + '\n',
                    encoding='utf-8', newline='\n')
            except OSError as exc:
                _emit_error('无法写入归属表：%s' % type(exc).__name__, args.json)
                return 0
            accepted = True

        baseline = str(ownership.get('absorbed_commit') or '').strip()
        baseline_error = _check_baseline(package, baseline)
        if baseline_error:
            _emit_error(baseline_error, args.json)
            return 0

        report = _build_report(package, head, baseline, ownership, skills_root)
        if args.json:
            report['accepted'] = accepted
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            _print_text(report, accepted=accepted)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        _emit_error('核对失败：%s' % (str(exc) or type(exc).__name__), args.json)
    except Exception as exc:  # 报告脚本不把异常变成非零退出码
        _emit_error('核对失败：%s: %s' % (type(exc).__name__, exc), args.json)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
