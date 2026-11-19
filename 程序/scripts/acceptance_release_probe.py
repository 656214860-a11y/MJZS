# -*- coding: utf-8 -*-
"""C 维「发布与回滚」验收探针（桌面与云服务架构及全链路验收任务书）。

在隔离目录 ``<worktree>/../_accept_c/`` 内完成：

1. 两份同机构建的分发制品（``dist_old``＝master 基线 86e863bb、``dist_new``＝本分支
   HEAD）摘要与版本兼容核对；
2. 干净副本「安装」：dist_old 落位 ``install/``，注入用户数据夹具
   （config.json／projects.json／desktop_settings.json／private／data）与
   「旧项目副本」（R3709 真实项目骨架）；
3. 旧版本打开旧项目（``engine.Studio`` 即项目打开代码路径）；
4. 升级前快照 ``snap_pre/``＋全量 sha256 清单；
5. 失败升级演练：dist_new 只覆盖约半数文件即中止 → 摘要核对检出混合态 →
   整体回滚 snap_pre → 复核哈希与打开项目；
6. 成功升级：dist_new 全量覆盖 → 程序文件与新制品摘要逐一致、用户数据与项目
   文件零改动 → 新版本打开旧项目。

证据脱敏导出 ``tasks_round/evidence/<轮次>/release_probe.json``；不触碰
``D:\\漫剧制作助手`` 正式安装与 ``D:\\漫剧下载`` 真实项目。

用法（程序目录下）::

    python -B scripts/acceptance_release_probe.py --round 3749
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
BASE = HERE.parent.parent / '_accept_c'
DIST_OLD = BASE / 'dist_old'
DIST_NEW = BASE / 'dist_new'
INSTALL = BASE / 'install'
SNAP = BASE / 'snap_pre_upgrade'
PROJECTS = BASE / 'projects'
OLD_PROJECT = PROJECTS / '验收旧项目_v1'
DIGEST_NAME = '分发清单.json'

RESULTS = []
OPS = []

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except (AttributeError, ValueError):
    pass


def record(name, ok, detail=''):
    detail = str(detail).replace('�', '?')
    RESULTS.append({'name': name, 'ok': ok, 'detail': detail})
    mark = 'PASS' if ok else ('SKIP' if ok is None else 'FAIL')
    print(f'[{mark}] {name}: {detail}')


def op(text):
    OPS.append({'at': time.strftime('%H:%M:%S'), 'op': text})
    print('  ·', text)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def manifest(root):
    """全量 sha256 清单：{相对路径: {sha256, bytes}}。"""
    root = Path(root)
    out = {}
    for path in sorted(root.rglob('*')):
        if path.is_file() and not path.is_symlink():
            rel = path.relative_to(root).as_posix()
            out[rel] = {'sha256': sha256_file(path), 'bytes': path.stat().st_size}
    return out


def copy_tree(src, dst):
    shutil.copytree(src, dst, dirs_exist_ok=True)


def overlay(src, dst, limit=None):
    """把 src 的文件逐个覆盖到 dst；limit 给定时拷到一半停（模拟升级中断）。"""
    src, dst = Path(src), Path(dst)
    files = sorted(p for p in src.rglob('*') if p.is_file() and not p.is_symlink())
    done = 0
    for path in files:
        rel = path.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        done += 1
        if limit is not None and done >= limit:
            return done, len(files), True
    return done, len(files), False


def load_digest(dist):
    data = json.loads((Path(dist) / DIGEST_NAME).read_text(encoding='utf-8'))
    return data


def check_against_digest(install, digest):
    """install 中每个制品条目哈希须一致；返回 (mismatch[], extra_user_files[])。"""
    install = Path(install)
    mismatch, extra = [], []
    listed = set()
    for item in digest['entries']:
        rel = item['path']
        listed.add(rel)
        target = install / rel
        if not target.is_file() or sha256_file(target) != item['sha256']:
            mismatch.append(rel)
    for path in install.rglob('*'):
        if path.is_file() and not path.is_symlink():
            rel = path.relative_to(install).as_posix()
            if rel not in listed and rel != DIGEST_NAME:
                extra.append(rel)
    return mismatch, sorted(extra)


def run_engine_open(install, project):
    """用安装副本自带解释器跑 engine.Studio（项目打开代码路径）。"""
    prog = Path(install) / '程序'
    py = Path(install) / '运行环境' / 'Python' / 'python.exe'
    code = (
        'import sys, json\n'
        'sys.path.insert(0, sys.argv[1])\n'
        'import engine\n'
        's = engine.Studio(sys.argv[2])\n'
        'print(json.dumps({"episode_path": str(s.episode_path), '
        '"episode_id": s.episode.get("episode_id"), "shots": len(s.episode.get("shots", []))}, '
        'ensure_ascii=False))\n'
    )
    env = dict(__import__('os').environ, PYTHONUTF8='1')
    try:
        done = subprocess.run([str(py), '-I', '-B', '-c', code, str(prog), str(project)],
                              cwd=str(prog), capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=120, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
    out = done.stdout.strip().splitlines()
    payload = None
    for line in reversed(out):
        try:
            payload = json.loads(line)
            break
        except ValueError:
            continue
    if done.returncode != 0 or payload is None:
        return {'ok': False, 'error': (done.stderr or done.stdout)[-300:]}
    return {'ok': True, **payload}


def write_user_fixtures(install, project):
    prog = Path(install) / '程序'
    (prog / 'config.json').write_text(json.dumps({
        'project_dir': '.', 'downloads_root': str(PROJECTS),
        'video_backend': 'comfy', 'live_enabled': False}, ensure_ascii=False), encoding='utf-8')
    (prog / 'projects.json').write_text(json.dumps({
        'active': str(project),
        'projects': [{'name': '验收旧项目', 'path': str(project),
                      'created_at': 1760000000.0}]}, ensure_ascii=False), encoding='utf-8')
    (prog / 'desktop_settings.json').write_text('{}', encoding='utf-8')
    for rel in ('private/账户', 'private/密钥', 'private/桌面续发', 'data'):
        marker = prog / rel / 'C_ACCEPT_KEEP.txt'
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text('keep-me-%s' % rel, encoding='utf-8')


def make_old_project():
    """旧项目副本：R3709 真实项目骨架＋自足 config.json（episode_dir 相对路径）。"""
    src = HERE / 'tasks_round' / 'evidence' / 'R3709' / 'ok' / 'artifacts'
    if OLD_PROJECT.exists():
        shutil.rmtree(OLD_PROJECT)
    OLD_PROJECT.mkdir(parents=True)
    for item in src.iterdir():
        if item.name in ('config.json', 'logs'):
            continue
        if item.is_dir():
            shutil.copytree(item, OLD_PROJECT / item.name)
        else:
            shutil.copy2(item, OLD_PROJECT / item.name)
    (OLD_PROJECT / 'config.json').write_text(
        json.dumps({'episode_dir': 'episode', 'video_backend': 'comfy',
                    'live_enabled': False}, ensure_ascii=False), encoding='utf-8')
    return OLD_PROJECT


def diff_paths(old_digest, new_digest):
    old_map = {e['path']: e['sha256'] for e in old_digest['entries']}
    new_map = {e['path']: e['sha256'] for e in new_digest['entries']}
    added = sorted(set(new_map) - set(old_map))
    removed = sorted(set(old_map) - set(new_map))
    changed = sorted(k for k in set(old_map) & set(new_map) if old_map[k] != new_map[k])
    return {'added': added, 'removed': removed, 'changed': changed}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--round', type=int, required=True, dest='rnd')
    ap.add_argument('--out', default='')
    args = ap.parse_args()
    out = Path(args.out) if args.out else HERE / 'tasks_round' / 'evidence' / f'R{args.rnd}' / 'release_probe.json'
    out.parent.mkdir(parents=True, exist_ok=True)

    # ── 1. 制品摘要与版本 ─────────────────────────────────────────
    op('load digests')
    d_old, d_new = load_digest(DIST_OLD), load_digest(DIST_NEW)
    record('artifact_old_identity', True,
           f"version={d_old['version']} commit={d_old['commit'][:8]} round={d_old['round']} "
           f"files={d_old['files']} bytes={d_old['bytes']}")
    record('artifact_new_identity', True,
           f"version={d_new['version']} commit={d_new['commit'][:8]} round={d_new['round']} "
           f"files={d_new['files']} bytes={d_new['bytes']}")
    delta = diff_paths(d_old, d_new)
    record('version_diff_surface', True,
           f"added={len(delta['added'])} removed={len(delta['removed'])} changed={len(delta['changed'])} "
           f"sample_changed={delta['changed'][:5]}")
    (out.parent / 'version_diff.json').write_text(
        json.dumps(delta, ensure_ascii=False, indent=1), encoding='utf-8')

    # ── 2. 安装（旧版制品＋用户数据夹具＋旧项目）───────────────────
    op('install old artifact -> install/')
    if INSTALL.exists():
        shutil.rmtree(INSTALL)
    copy_tree(DIST_OLD, INSTALL)
    project = make_old_project()
    write_user_fixtures(INSTALL, project)
    op('hash manifests')
    man_pre = manifest(INSTALL)
    man_proj = manifest(project)
    (out.parent / 'manifest_pre_install.json').write_text(
        json.dumps({'install': man_pre, 'project': man_proj}, ensure_ascii=False), encoding='utf-8')
    record('install_fixtures', True,
           f'install_files={len(man_pre)} project_files={len(man_proj)} user_markers=4')

    # ── 3. 旧版本打开旧项目 ───────────────────────────────────────
    op('open project under OLD install')
    r = run_engine_open(INSTALL, project)
    record('open_project_old_version', bool(r.get('ok')),
           json.dumps(r, ensure_ascii=False)[:200])

    # ── 4. 升级前快照 ─────────────────────────────────────────────
    op('snapshot install -> snap_pre/')
    man_at_snap = manifest(INSTALL)
    if SNAP.exists():
        shutil.rmtree(SNAP)
    copy_tree(INSTALL, SNAP)
    man_snap = manifest(SNAP)
    same = man_snap == man_at_snap
    runtime_added = sorted(set(man_snap) - set(man_pre))
    record('snapshot_identical', same,
           f'files={len(man_snap)} identical_to_pre_copy={same} '
           f'runtime_added_by_open={runtime_added[:5]}')

    # ── 5. 失败升级 → 检出 → 回滚 ─────────────────────────────────
    op('failed upgrade: overlay ~50% of new artifact then abort + damage files')
    total_new = len(d_new['entries'])
    done, total_files, aborted = overlay(DIST_NEW, INSTALL, limit=total_new // 2)
    # 模拟升级中断的真实残留：缺文件＋截断文件（新旧制品仅差 7 个文件，
    # 半量覆盖可能恰好盖住全部差异面，必须显式制造损坏才能验证检出能力）
    prog = Path(INSTALL) / '程序'
    (prog / 'app.py').unlink()
    (prog / 'desktop.py').write_bytes(b'corrupted-by-failed-upgrade')
    mismatch_new, _ = check_against_digest(INSTALL, d_new)
    man_mixed = manifest(INSTALL)
    diff_vs_snap = sum(1 for rel in set(man_mixed) | set(man_snap)
                       if man_mixed.get(rel) != man_snap.get(rel))
    record('failed_upgrade_detected', len(mismatch_new) >= 2,
           f'copied={done}/{total_files} aborted={aborted} damaged=app.py+desktop.py '
           f'digest_mismatch_vs_new={len(mismatch_new)} diff_vs_snapshot={diff_vs_snap}')

    op('rollback: restore snap_pre -> install/')
    shutil.rmtree(INSTALL)
    copy_tree(SNAP, INSTALL)
    man_rb = manifest(INSTALL)
    record('rollback_hashes_match', man_rb == man_snap,
           f'files={len(man_rb)} identical_to_snapshot={man_rb == man_snap}')
    r = run_engine_open(INSTALL, project)
    record('open_project_after_rollback', bool(r.get('ok')),
           json.dumps(r, ensure_ascii=False)[:200])

    # ── 6. 成功升级 ───────────────────────────────────────────────
    op('successful upgrade: full overlay of new artifact')
    done, total_files, aborted = overlay(DIST_NEW, INSTALL)
    record('upgrade_overlay_complete', not aborted,
           f'copied={done}/{total_files}')
    mismatch_new, extra = check_against_digest(INSTALL, d_new)
    record('program_files_match_new_digest', not mismatch_new,
           f'mismatch={len(mismatch_new)} extra_non_program={len(extra)}')
    # 用户数据与项目文件零改动
    man_now = manifest(INSTALL)
    changed_user = []
    for rel, info in man_snap.items():
        if rel.startswith('程序/private/') or rel.startswith('程序/data/') or \
                rel in ('程序/config.json', '程序/projects.json', '程序/desktop_settings.json'):
            now = man_now.get(rel)
            if now != info:
                changed_user.append(rel)
    missing_user = [rel for rel in man_snap
                    if (rel.startswith('程序/private/') or rel.startswith('程序/data/')
                        or rel in ('程序/config.json', '程序/projects.json',
                                   '程序/desktop_settings.json'))
                    and rel not in man_now]
    record('user_data_preserved', not changed_user and not missing_user,
           f'changed={changed_user[:5]} missing={missing_user[:5]}')
    man_proj_after = manifest(project)
    changed_proj = sorted(rel for rel in set(man_proj) | set(man_proj_after)
                          if man_proj.get(rel) != man_proj_after.get(rel))
    non_cfg = [rel for rel in changed_proj if rel != 'config.json']
    cfg_note = ''
    if 'config.json' in changed_proj and not non_cfg:
        fixture_keys = {'episode_dir': 'episode', 'video_backend': 'comfy', 'live_enabled': False}
        try:
            now_cfg = json.loads((project / 'config.json').read_text(encoding='utf-8'))
            kept = all(now_cfg.get(k) == v for k, v in fixture_keys.items())
            added = sorted(set(now_cfg) - set(fixture_keys))
            cfg_note = f'config_selfheal kept_fixture={kept} added_keys={added}'
        except (OSError, ValueError) as exc:
            cfg_note = f'config_selfheal_unreadable:{type(exc).__name__}'
    record('old_project_files_untouched', not non_cfg,
           f'changed={changed_proj} non_config_changed={non_cfg} {cfg_note} '
           f'（config.json 指针自愈写回属设计内行为，见 test_project_open.py）')

    # ── 7. 新版本打开旧项目（版本兼容）────────────────────────────
    op('open project under NEW install')
    r = run_engine_open(INSTALL, project)
    record('open_project_new_version', bool(r.get('ok')),
           json.dumps(r, ensure_ascii=False)[:200])
    compat = bool(r.get('ok')) and r.get('episode_id') == 'EP001'
    record('old_project_compatible_with_new', compat,
           f"episode_id={r.get('episode_id')} shots={r.get('shots')}")

    fails = [r for r in RESULTS if r['ok'] is False]
    doc = {
        'round': args.rnd,
        'collected_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'base': str(BASE),
        'artifacts': {
            'old': {'version': d_old['version'], 'commit': d_old['commit'], 'round': d_old['round'],
                    'files': d_old['files'], 'bytes': d_old['bytes']},
            'new': {'version': d_new['version'], 'commit': d_new['commit'], 'round': d_new['round'],
                    'files': d_new['files'], 'bytes': d_new['bytes']},
        },
        'version_diff_summary': {'added': len(delta['added']), 'removed': len(delta['removed']),
                                 'changed': len(delta['changed'])},
        'summary': {'total': len(RESULTS), 'pass': sum(1 for r in RESULTS if r['ok'] is True),
                    'fail': len(fails), 'skip': sum(1 for r in RESULTS if r['ok'] is None)},
        'operations': OPS,
        'results': RESULTS,
    }
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f"\n== {doc['summary']} -> {out}")
    return 1 if fails else 0


if __name__ == '__main__':
    raise SystemExit(main())
