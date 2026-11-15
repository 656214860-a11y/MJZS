# -*- coding: utf-8 -*-
"""自检的凭据与台账：增量台账、分层基线、全量绿凭据读写与欠账/风险判定（只读写机器状态，不跑用例）。"""

import glob
import io
import json
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime, timedelta

import line_endings

import selftest_env as env
import selftest_discovery as discovery


def cache_path():
    """多 worktree 共用增量台账；无法定位仓库时保持旧的本地降级行为。"""
    common = env.git_common_dir()
    if common and os.path.isdir(common):
        return os.path.join(common, env.CACHE_NAME)
    return os.path.join(env.HERE, '维护记录', '自检增量.json')


def load_cache():
    try:
        with io.open(cache_path(), encoding='utf-8') as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_cache(state):
    target = cache_path()
    temporary = ''
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix='.selftest-', suffix='.tmp',
                                                 dir=os.path.dirname(target))
        os.close(descriptor)
        line_endings.write_text(temporary, json.dumps(state, ensure_ascii=False, indent=1,
                                                      sort_keys=True) + '\n')
        # 并发写入至多让另一 worktree 多跑用例，原子替换绝不能制造假跳过。
        os.replace(temporary, target)
    except (OSError, ValueError) as exc:
        print('增量台账写不出来（不影响结果）：' + str(exc))
        return ''
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return target


def record_elapsed(cache, state, elapsed):
    """把最近五轮成功自检时长留在增量台账，并给出抗抖动的中位基线。"""
    previous = cache.get('timings') if isinstance(cache.get('timings'), dict) else {}
    old_runs = previous.get('recent_seconds') if isinstance(previous.get('recent_seconds'), list) else []
    runs = []
    for value in old_runs:
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if value >= 0:
            runs.append(round(value, 3))
    runs = (runs + [round(float(elapsed), 3)])[-5:]
    ordered = sorted(runs)
    middle = len(ordered) // 2
    median = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2.0
    state['timings'] = {'recent_seconds': runs, 'median_seconds': round(median, 3)}
    return state['timings']


def layer_baseline_path():
    return os.path.join(env.HERE, env.LAYER_BASELINE_NAME)


def content_tree():
    """返回 HEAD 中程序目录的内容树；未提交改动不应拿旧树替代验证。"""
    try:
        if checkout_dirty_entries()[1]:
            return ''
        root = env._git_text('rev-parse', '--show-toplevel')
        relative = os.path.relpath(env.HERE, root).replace(os.sep, '/')
        return env._git_text('rev-parse', 'HEAD:' + relative)
    except (OSError, ValueError, subprocess.SubprocessError):
        return ''


def checkout_dirty_entries():
    """返回 content_tree 同一口径下的当前树脏文件，供全量凭据前置断言复用。"""
    try:
        root = env._git_text('rev-parse', '--show-toplevel')
        status = env._git_text('status', '--porcelain', '--untracked-files=normal', '--', ':/')
        return root, [line for line in status.splitlines() if line.strip()]
    except (OSError, ValueError, subprocess.SubprocessError):
        return '', ['<无法读取 git status>']


def full_safe_preflight(allow_dirty_diagnostic=False):
    """在持有全量锁后、启动子进程前检查凭据所需的干净内容树。"""
    root, dirty = checkout_dirty_entries()
    if dirty:
        print('拒绝全量测量：脏树不会产凭据；以下文件尚未收口：')
        for entry in dirty:
            print('  %s: %s' % (root or '<当前工作树>', entry))
        if not allow_dirty_diagnostic:
            return False, ''
        print('[NO_RECEIPT] --allow-dirty-diagnostic：仅诊断，不写入绿凭据或测试台账。')
        return True, ''
    tree = content_tree()
    if not tree:
        print('拒绝全量测量：无法确认内容树；脏树不会产凭据。')
        return False, ''
    return True, tree


def is_master_checkout():
    try:
        return env._git_text('branch', '--show-current') == 'master'
    except (OSError, subprocess.SubprocessError):
        return False


def is_source_change(path, prefix):
    """路径是否算「改了源码」：程序目录内、非测试／记录／说明目录、非普通文档（skills 下的 md 是 SKILL 源）。"""
    path = path.replace(chr(92), '/')
    if not path.startswith(prefix):
        return False
    rel = path[len(prefix):]
    if rel.startswith(env.NON_SOURCE_DIRS):
        return False
    return not (rel.endswith('.md') and not rel.startswith('skills/'))


def count_source_rounds(commits, last_full_round, latest_round, prefix):
    """commits 为 [(轮次, [路径])]；返回 (last_full, latest] 内至少改过一处源码的不同轮次数。"""
    counted = set()
    for number, paths in commits:
        if last_full_round < number <= latest_round and any(is_source_change(p, prefix) for p in paths):
            counted.add(number)
    return len(counted)


def _round_commits():
    """读 git 历史：返回 ([(轮次, [路径])], 程序目录相对仓库根的前缀)；读不出来返回 None。"""
    try:
        root = env._git_text('rev-parse', '--show-toplevel')
        prefix = os.path.relpath(env.HERE, root).replace(os.sep, '/') + '/'
        log = env._git_text('-c', 'core.quotepath=false', 'log', '-n', '800', '--name-only', '--format=%x01%s')
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    commits = []
    for chunk in log.split(chr(1)):
        lines = [line for line in chunk.splitlines() if line.strip()]
        matched = env._ROUND_SUBJECT.match(lines[0]) if lines else None
        if matched:
            commits.append((int(matched.group(1)), lines[1:]))
    return commits, prefix


def source_rounds_since(last_full_round, latest_round):
    """读 git 历史得到源码轮次数；读不出来返回 None，由调用方退回保守的全部轮次计数。"""
    loaded = _round_commits()
    if loaded is None:
        return None
    commits, prefix = loaded
    return count_source_rounds(commits, last_full_round, latest_round, prefix)


def risk_paths(prefix):
    """AGENTS §5 里能按路径静态判定的升级条件；Tk 控件生命周期无法静态判定，仍由人工把关。"""
    return frozenset(('启动漫剧制作助手.pyw', '开发者工具/启动助手.cmd', prefix + 'storage_maintenance.py',
                      prefix + 'tests/architecture/_layers.py'))


def has_risk_change(commits, last_full_round, latest_round, prefix):
    """(last_full, latest] 内是否有轮次改过启动入口、删除语义或层级登记表。"""
    watched = risk_paths(prefix)
    return any(last_full_round < number <= latest_round
               and any(path.replace(chr(92), '/') in watched for path in paths)
               for number, paths in commits)


def risk_overdue(commits, last_full_round, latest_round, prefix):
    """风险改动已过宽限：自最早一次风险改动之后又积累了 FULL_SAFE_RISK_GRACE 个源码轮次仍无凭据。"""
    watched = risk_paths(prefix)
    first = min((number for number, paths in commits
                 if last_full_round < number <= latest_round
                 and any(path.replace(chr(92), '/') in watched for path in paths)), default=None)
    if first is None:
        return False
    return count_source_rounds(commits, first, latest_round, prefix) >= env.FULL_SAFE_RISK_GRACE


def risk_overdue_since(last_full_round, latest_round):
    loaded = _round_commits()
    if loaded is None:
        return False
    commits, prefix = loaded
    return risk_overdue(commits, last_full_round, latest_round, prefix)


def auto_full_running():
    """后台自动全量（scripts/auto_full_safe.py）是否正在运行：锁文件存在、未过期、持有进程还活着。"""
    common = env.git_common_dir()
    if not common:
        return False
    path = os.path.join(common, env.AUTO_FULL_LOCK_NAME)
    try:
        age = time.time() - os.stat(path).st_mtime
        with io.open(path, encoding='utf-8') as handle:
            pid = int(handle.read().strip() or 0)
    except (OSError, ValueError):
        return False
    return age < env.AUTO_FULL_STALE_SECONDS and bool(pid) and env._pid_is_alive(pid)


def risk_changed_since(last_full_round, latest_round):
    loaded = _round_commits()
    if loaded is None:
        return False
    commits, prefix = loaded
    return has_risk_change(commits, last_full_round, latest_round, prefix)


def receipt_checkout_allowed():
    """能否把本次全量写成凭据：主干检出，或 auto_full_safe 在主干 HEAD 的干净分离检出上跑。

    后者无法检出 master 分支（已被主工作树占用），由脚本把它验证过的 HEAD 放进环境变量。"""
    if is_master_checkout():
        return True
    expected = os.environ.get('AUTO_FULL_SAFE_HEAD', '')
    try:
        return bool(expected) and expected == env._git_text('rev-parse', 'HEAD')
    except (OSError, subprocess.SubprocessError):
        return False


def full_safe_required(latest_round, last_full_round, master_checkout, source_rounds=None, risk=False):
    """欠账只属于主干提交序列，worktree 分支不产生全量欠账。

    ``source_rounds`` 缺省时按全部轮次保守计数；传入则只数改过源码的轮次。``risk`` 为真（风险路径改动已过宽限，见
    ``risk_overdue``）时不等计数，欠一次全量。"""
    count = latest_round - last_full_round if source_rounds is None else source_rounds
    return bool(master_checkout and (risk or count >= env.FULL_SAFE_ROUND_INTERVAL))


def full_safe_auto_due(latest_round, last_full_round, master_checkout):
    """后台自动补跑的触发点：比门禁提前 FULL_SAFE_AUTO_LEAD 个源码轮次。"""
    if not master_checkout:
        return False
    count = source_rounds_since(last_full_round, latest_round)
    count = latest_round - last_full_round if count is None else count
    return risk_changed_since(last_full_round, latest_round) or count >= env.FULL_SAFE_ROUND_INTERVAL - env.FULL_SAFE_AUTO_LEAD


def participating_full_safe_run(round_number):
    """Only the full-run lock owner and its workers may defer receipt checking."""
    common = env.git_common_dir()
    if not common:
        return False
    try:
        with io.open(os.path.join(common, env.FULL_SAFE_LOCK_NAME), encoding='utf-8') as handle:
            holder = json.load(handle)
        return (isinstance(holder, dict)
                and holder.get('round') == round_number
                and holder.get('pid') in (os.getpid(), os.getppid())
                and env._pid_is_alive(holder.get('pid')))
    except (OSError, ValueError):
        return False


def measurement_unchanged(head, tree):
    """相同内容树也不能掩盖测量期间发生的提交。"""
    return bool(head and tree and env._git_text('rev-parse', 'HEAD') == head
                and content_tree() == tree)


def verified_tree_record(records, tree, now=None):
    """找出七日内可引用的同内容树全量绿记录。"""
    if not tree:
        return None
    now = now or datetime.now()
    for record in records if isinstance(records, list) else []:
        if not isinstance(record, dict) or record.get('tree') != tree:
            continue
        try:
            verified_at = datetime.fromisoformat(str(record['at']))
        except (KeyError, TypeError, ValueError):
            continue
        age = now - verified_at
        if timedelta(0) <= age <= env.FULL_SAFE_TREE_TTL:
            return record
    return None


def load_layer_document():
    try:
        with io.open(layer_baseline_path(), encoding='utf-8') as handle:
            document = json.load(handle)
    except (OSError, ValueError):
        document = {}
    document = document if isinstance(document, dict) else {}
    # 台账是可追溯的分层配置，不是全量凭据的后备来源；旧工作树遗留字段也不能回退凭据。
    document.pop('full_safe_verified_trees', None)
    document.pop('last_full_safe_all_round', None)
    receipts = {}
    try:
        with io.open(full_safe_receipts_path(), encoding='utf-8') as handle:
            receipts = json.load(handle)
    except (OSError, ValueError):
        receipts = {}
    if isinstance(receipts, dict):
        document['full_safe_verified_trees'] = receipts.get('full_safe_verified_trees', [])
        document['last_full_safe_all_round'] = receipts.get('last_full_safe_all_round', 0)
        # 兼容 R962/R963 只写树凭据、没有同步 last_full 字段的真实绿记录。
        rounds = [item.get('round', 0) for item in document['full_safe_verified_trees']
                  if isinstance(item, dict) and isinstance(item.get('round'), int)]
        document['last_full_safe_all_round'] = max([document['last_full_safe_all_round']] + rounds)
    else:
        document['full_safe_verified_trees'] = []
        document['last_full_safe_all_round'] = 0
    return document


def full_safe_receipts_path():
    common = env.git_common_dir()
    return os.path.join(common, 'full-safe-receipts.json') if common else layer_baseline_path()


def record_verified_tree(document, tree, round_number, seconds, at=None):
    records = [item for item in document.get('full_safe_verified_trees', [])
               if isinstance(item, dict) and item.get('tree') != tree]
    records.append({'tree': tree, 'round': int(round_number), 'seconds': round(float(seconds), 3),
                    'at': at or datetime.now().isoformat(timespec='seconds')})
    document['full_safe_verified_trees'] = records[-30:]
    document['last_full_safe_all_round'] = int(round_number)
    return document


def invalidate_verified_tree(document, tree):
    """任一增量/定向红都撤销本树的免跑资格，下一次须重新全量验证。"""
    records = document.get('full_safe_verified_trees', [])
    kept = [item for item in records if not isinstance(item, dict) or item.get('tree') != tree]
    if len(kept) == len(records):
        return False
    document['full_safe_verified_trees'] = kept
    try:
        line_endings.write_text(full_safe_receipts_path(), json.dumps(document, ensure_ascii=False,
                                                                    indent=1, sort_keys=True) + '\n')
    except (OSError, ValueError):
        return False
    return True


def latest_completed_round():
    numbers = []
    for path in glob.glob(os.path.join(env.HERE, 'tasks_round', '**', 'tasks_round_*_result.md'), recursive=True):
        matched = re.search(r'tasks_round_(\d+)_result\.md$', path)
        if matched:
            numbers.append(int(matched.group(1)))
    return max(numbers, default=0)


def save_layer_baseline(layer, results, elapsed):
    """记录一次分层门禁的可比较结果，不保存报错堆栈或任何业务内容。"""
    if not layer:
        return ''
    target = layer_baseline_path()
    document = load_layer_document()
    failed = sorted({item[1] for item in results if item[3]})
    document[layer] = {
        'updated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'test_count': sum(item[2] for item in results),
        'unit_count': len(results),
        'elapsed_seconds': round(elapsed, 3),
        'failed_modules': failed,
    }
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        line_endings.write_text(target, json.dumps(document, ensure_ascii=False, indent=1,
                                                    sort_keys=True) + '\n')
    except (OSError, ValueError) as exc:
        print('分层基线写不出来（不影响结果）：' + str(exc))
        return ''
    return target


def save_full_safe_verification(tree, round_number, elapsed):
    # A run may overlap edits or a commit; never certify a different checkout.
    if not tree or content_tree() != tree:
        return ''
    document = load_layer_document()
    record_verified_tree(document, tree, round_number, elapsed)
    target = full_safe_receipts_path()
    try:
        line_endings.write_text(target, json.dumps(document, ensure_ascii=False, indent=1,
                                                    sort_keys=True) + '\n')
    except (OSError, ValueError) as exc:
        print('内容树全量凭据写不出来（不影响结果）：' + str(exc))
        return ''
    return target


def incremental(names, cache):
    """这一趟真要跑哪些测试文件（第 36 期第 14 条：没改过的功能不重跑）。

    判据两条，任一成立就必须跑：
    1. 这个测试文件自己变了（指纹与台账里的不一样）；
    2. 它依赖的东西变了——它（连同传递依赖）import 的本项目模块，或者 skills 里的说明文件。
    台账里没记过的测试文件一律照跑（宁可多跑，不许漏检）。返回 (要跑的, 跳过的, 新台账)。
    """
    old_modules = cache.get('modules') if isinstance(cache.get('modules'), dict) else {}
    old_data = cache.get('data') if isinstance(cache.get('data'), dict) else {}
    known = cache.get('tests') if isinstance(cache.get('tests'), dict) else {}
    if cache.get('rules') != env.INCREMENTAL_RULES:
        known = {}                             # 旧口径记下的依赖清单不可信：本趟全部照跑
    modules_now = {name: env._digest(path) for name, path in discovery.project_modules().items()}
    data_now = {rel: env._digest(path) for rel, path in discovery.data_files().items()}
    data_moved = sorted(rel for rel, value in data_now.items() if old_data.get(rel) != value)
    todo, skipped, tests_now = [], [], {}
    for name in names:
        path = discovery.test_path(name)
        fingerprint = env._digest(path)
        entry = known.get(name) if isinstance(known.get(name), dict) else None
        if entry and entry.get('digest') == fingerprint:
            deps = [str(item) for item in (entry.get('deps') or [])]
        else:
            deps = sorted(discovery.dependency_closure(discovery.imports_of(path) | {name}))
        tests_now[name] = {'digest': fingerprint, 'deps': deps}
        if not entry:
            todo.append(name)                  # 台账里没见过：照跑
            continue
        if entry.get('digest') != fingerprint:
            todo.append(name)                  # 测试文件自己改了
            continue
        if data_moved:
            todo.append(name)                  # SKILL 说明那类数据文件改了：都跑一遍
            continue
        if any(old_modules.get(dep) != modules_now.get(dep) for dep in deps):
            todo.append(name)                  # 它依赖的模块改了
            continue
        skipped.append(name)
    state = {'rules': env.INCREMENTAL_RULES, 'modules': modules_now, 'data': data_now, 'tests': tests_now}
    return todo, skipped, state
