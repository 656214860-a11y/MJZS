# -*- coding: utf-8 -*-
"""运行全部自检：导入所有模块 ＋ unittest 用例。

第 25 期：整跑改成**按工作单元并行**（本机 24 核，实测 204 秒 → 87 秒）。
大文件（用例多的那两个）会按 TestCase 类再切成几路——原来一个文件只能占一个进程，
test_pet_ui／test_ui_edges 各自七八十秒，整跑就被它们俩顶住了。
剩下的长尾是 Tk 界面那几条：每例都要建一整套 11 页的界面，单例 3～6 秒，切得再细也下不去；
并行度也是实测出来的——16 路时 GUI 互相争用，单例成本翻三倍，整跑反而 114 秒，所以默认封顶 8 路。
  python run_selftests.py                  # 并行整跑（默认，取 min(8, 核数) 个进程，约 85 秒）
  python run_selftests.py --serial         # 老样子串行（怀疑并行互相干扰时用它对照）
  python run_selftests.py --jobs 4         # 指定并行度
  python run_selftests.py --whole          # 不拆大文件（一个文件一路，出问题时对照用）
  python run_selftests.py --safe           # 无 Tk 并行、Tk 最多 2 路受控并行，性能用例独占串行
  python run_selftests.py --all --safe --force # 忽略同内容树绿凭据，强制再跑一轮全量复核
  python run_selftests.py -k pet keyframe  # 只跑文件名含这些片段的用例（改哪儿跑哪儿）
  python run_selftests.py --list           # 只列会跑哪些文件
  python run_selftests.py --all            # 不管改没改过，全部重跑一遍，并刷新增量台账
  python run_selftests.py --layer architecture --all  # 只跑架构契约层，并记录分层基线
  python run_selftests.py --layer service --all       # 只跑不依赖 Tk 的服务层
  python run_selftests.py --layer gui-short --safe --all # 短生命周期 Tk 用例（最多 2 路）
  python run_selftests.py --layer gui-e2e --safe --all   # 端到端桌面冒烟（最多 2 路）

第 36 期第 14 条：整跑一次两分钟，而一轮改动通常只碰两三个模块——用户要「不检查没改过的
功能、缩短时间」。所以默认走**增量**：上一次跑绿之后，谁（测试文件自己／它 import 的本项目
模块／skills 里的说明文件）一个字节都没动，这一趟就跳过它，只在结尾报一句跳了多少。
台账优先落在仓库共同 Git 目录的 selftest-incremental.json；非 Git 目录才降级到
维护记录/自检增量.json。--all 会忽略台账全跑，跑绿之后重写台账。
怀疑漏检时用 --all 或 --serial 对照，两条路都在。
"""
import ast
import atexit
import glob
import hashlib
import importlib
import io
import json
import line_endings
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.join(HERE, 'tests')
sys.path.insert(0, HERE)
# 迁移期兼容：测试既可以仍在程序根目录，也可以放入 tests/。保留模块短名，避免
# 既有的 -k、增量台账和按类分片标签因目录调整而失效。
if os.path.isdir(TESTS_DIR):
    sys.path.insert(0, TESTS_DIR)

SKIP = {"run_selftests", "test_core", "test_workflow"}
SPLIT_OVER = 20         # 用例超过这么多条的测试文件才拆（小文件拆了反而多付进程启动的钱）
CHUNK_TESTS = 16        # 安全串行仍受 180 秒回收；合并短用例以避免 worktree 的进程寿命上限打断全量回归
JOBS_CAP = 8            # 默认并行度上限：这些用例一半在建整套 Tk 界面，16 路实测反而更慢
SAFE_GUI_JOBS = 2       # C4 性能目标下 Tk 的受控并发上限；超过两路会明显争抢 Windows 图形资源
SAFE_UNIT_TIMEOUT = 180 # 安全串行性能用例的一小段最长允许三分钟，避免模态窗永久占住门禁
HEARTBEAT_SECONDS = 30  # 并行全量久未完成时仍需给出活跃心跳，方便定位是否只是慢
SLOW_UNITS_LIMIT = 10   # 汇总只保留最慢若干工作单元，避免全量输出淹没结论


CACHE_NAME = 'selftest-incremental.json'
FULL_SAFE_LOCK_NAME = 'full-safe-selftest.lock'
LAYER_BASELINE_NAME = os.path.join('维护记录', '测试分层基线.json')
FULL_SAFE_TREE_TTL = timedelta(days=7)
DATA_GLOBS = ('skills/*.skill.md', 'skills/*/*.md', 'skills/*/*/*.md')
TEST_LAYERS = ('architecture', 'service', 'gui', 'gui-short', 'gui-e2e')
# 这两组会连续创建完整桌面、启动后台助手，必须与短生命周期 Tk 用例隔离。
# 名称是测试模块的稳定契约，新增端到端模块时必须显式登记，不能靠耗时猜测。
GUI_E2E_MODULES = frozenset({'test_ui_edges', 'test_pet_ui'})


def safe_full_options(everything, serial, whole, jobs, safe):
    """安全模式固定为全量、可拆分；Tk 单元的并发度另由 safe_gui_jobs 限制。"""
    if safe:
        return True, False, False, jobs
    return everything, serial, whole, jobs


def safe_gui_jobs(jobs):
    """安全模式允许受控的 Tk 并发，但绝不超过经验证的两个 worker。"""
    return max(1, min(SAFE_GUI_JOBS, jobs))


def _digest(path):
    """一个文件的指纹（读不出来就当空串——空串永远算「变了」，宁可多跑不许漏跑）。"""
    try:
        with open(path, 'rb') as handle:
            return hashlib.sha1(handle.read()).hexdigest()
    except OSError:
        return ''


def project_modules():
    """本项目里可被导入的模块：模块名 → 文件路径（程序根 ＋ agent 子包）。"""
    out = {}
    for folder in (HERE, os.path.join(HERE, 'agent')):
        for path in glob.glob(os.path.join(folder, '*.py')):
            out[os.path.basename(path)[:-3]] = path
    return out


@lru_cache(maxsize=None)
def imports_of(path):
    """一个 .py 里 import 了哪些顶层模块名（只看语法，不真的导入）。"""
    try:
        with io.open(path, encoding='utf-8', errors='ignore') as handle:
            tree = ast.parse(handle.read())
    except (OSError, SyntaxError):
        return frozenset()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level or not node.module:
                continue                       # 相对导入（agent 包内部）不参与
            names.add(node.module.split('.')[0])
    # dependency_closure 会被每个测试文件调用；不缓存会重复解析同一批模块数千次，
    # 让 --all 在真正开始跑用例前就长时间占满 CPU。
    return frozenset(names)


def dependency_closure(names):
    """这些模块连带它们 import 的本项目模块，一直展开到底（只认项目里的文件）。"""
    modules = project_modules()
    seen, todo = set(), list(names)
    while todo:
        name = todo.pop()
        if name in seen or name not in modules:
            continue
        seen.add(name)
        todo.extend(imports_of(modules[name]) - seen)
    return seen


def data_files():
    """跟着自检一起变的数据文件（各个 SKILL 的说明 MD）：相对路径 → 绝对路径。"""
    out = {}
    for pattern in DATA_GLOBS:
        for path in glob.glob(os.path.join(HERE, pattern)):
            out[os.path.relpath(path, HERE).replace(os.sep, '/')] = path
    return out


def _git_text(*args):
    """读取 git 的一行输出；非仓库或 git 不可用时交由调用者降级。"""
    output = subprocess.check_output(['git', *args], cwd=HERE, stderr=subprocess.DEVNULL)
    return output.decode('utf-8', 'replace').strip()


def git_common_dir():
    try:
        path = _git_text('rev-parse', '--git-common-dir')
    except (OSError, subprocess.SubprocessError):
        return ''
    if not path:
        return ''
    return path if os.path.isabs(path) else os.path.abspath(os.path.join(HERE, path))


def cache_path():
    """多 worktree 共用增量台账；无法定位仓库时保持旧的本地降级行为。"""
    common = git_common_dir()
    if common and os.path.isdir(common):
        return os.path.join(common, CACHE_NAME)
    return os.path.join(HERE, '维护记录', '自检增量.json')


def _pid_is_alive(pid):
    try:
        pid = int(pid)
    except (ValueError, TypeError):
        return False
    if os.name == 'nt':
        # Windows 的 os.kill(pid, 0) 不可靠地报告 WinError 87；用进程句柄
        # 查询活动持有者，避免把仍在执行的全量回归锁当成过期锁。
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def acquire_full_safe_lock(common_dir=None, round_number=None):
    """领取跨工作树的全量安全回归锁；活跃持有人不得被覆盖。"""
    common = common_dir or git_common_dir()
    if not common:
        raise RuntimeError('无法定位 Git common-dir，拒绝并行全量安全回归')
    path = os.path.join(common, FULL_SAFE_LOCK_NAME)
    payload = {'pid': os.getpid(), 'round': round_number, 'started_at': time.time()}
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            with io.open(path, encoding='utf-8') as handle:
                holder = json.load(handle)
        except (OSError, ValueError):
            holder = {}
        if _pid_is_alive(holder.get('pid')):
            raise RuntimeError('全量安全回归已由 PID %s（R%s）持有' %
                               (holder.get('pid'), holder.get('round', '?')))
        try:
            os.unlink(path)
        except OSError:
            raise RuntimeError('全量安全回归锁无法回收：%s' % path)
        return acquire_full_safe_lock(common, round_number)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle, ensure_ascii=False)
    return path


def release_full_safe_lock(path):
    try:
        os.unlink(path)
    except OSError:
        pass


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
    return os.path.join(HERE, LAYER_BASELINE_NAME)


def content_tree():
    """返回 HEAD 中程序目录的内容树；未提交改动不应拿旧树替代验证。"""
    try:
        if _git_text('status', '--porcelain', '--untracked-files=normal', '--', '.'):
            return ''
        root = _git_text('rev-parse', '--show-toplevel')
        relative = os.path.relpath(HERE, root).replace(os.sep, '/')
        return _git_text('rev-parse', 'HEAD:' + relative)
    except (OSError, ValueError, subprocess.SubprocessError):
        return ''


def is_master_checkout():
    try:
        return _git_text('branch', '--show-current') == 'master'
    except (OSError, subprocess.SubprocessError):
        return False


def full_safe_required(latest_round, last_full_round, master_checkout):
    """三轮计数只属于主干提交序列，worktree 分支不产生全量欠账。"""
    return bool(master_checkout and latest_round - last_full_round >= 3)


def participating_full_safe_run(round_number):
    """Only the full-run lock owner and its workers may defer receipt checking."""
    common = git_common_dir()
    if not common:
        return False
    try:
        with io.open(os.path.join(common, FULL_SAFE_LOCK_NAME), encoding='utf-8') as handle:
            holder = json.load(handle)
        return (isinstance(holder, dict)
                and holder.get('round') == round_number
                and holder.get('pid') in (os.getpid(), os.getppid())
                and _pid_is_alive(holder.get('pid')))
    except (OSError, ValueError):
        return False


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
        if timedelta(0) <= age <= FULL_SAFE_TREE_TTL:
            return record
    return None


def load_layer_document():
    try:
        with io.open(layer_baseline_path(), encoding='utf-8') as handle:
            document = json.load(handle)
    except (OSError, ValueError):
        document = {}
    return document if isinstance(document, dict) else {}


def record_verified_tree(document, tree, round_number, seconds, at=None):
    records = [item for item in document.get('full_safe_verified_trees', [])
               if isinstance(item, dict) and item.get('tree') != tree]
    records.append({'tree': tree, 'round': int(round_number), 'seconds': round(float(seconds), 3),
                    'at': at or datetime.now().isoformat(timespec='seconds')})
    document['full_safe_verified_trees'] = records[-30:]
    return document


def invalidate_verified_tree(document, tree):
    """任一增量/定向红都撤销本树的免跑资格，下一次须重新全量验证。"""
    records = document.get('full_safe_verified_trees', [])
    kept = [item for item in records if not isinstance(item, dict) or item.get('tree') != tree]
    if len(kept) == len(records):
        return False
    document['full_safe_verified_trees'] = kept
    try:
        line_endings.write_text(layer_baseline_path(), json.dumps(document, ensure_ascii=False,
                                                                    indent=1, sort_keys=True) + '\n')
    except (OSError, ValueError):
        return False
    return True


def latest_completed_round():
    numbers = []
    for path in glob.glob(os.path.join(HERE, 'tasks_round', 'tasks_round_*_result.md')):
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
    target = layer_baseline_path()
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
    modules_now = {name: _digest(path) for name, path in project_modules().items()}
    data_now = {rel: _digest(path) for rel, path in data_files().items()}
    data_moved = sorted(rel for rel, value in data_now.items() if old_data.get(rel) != value)
    todo, skipped, tests_now = [], [], {}
    for name in names:
        path = test_path(name)
        fingerprint = _digest(path)
        entry = known.get(name) if isinstance(known.get(name), dict) else None
        if entry and entry.get('digest') == fingerprint:
            deps = [str(item) for item in (entry.get('deps') or [])]
        else:
            deps = sorted(dependency_closure(imports_of(path) | {name}))
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
    state = {'modules': modules_now, 'data': data_now, 'tests': tests_now}
    return todo, skipped, state


def sink_test_windows():
    """自检期间建的窗口一律沉到桌面最底层，别影响用户操作。

    第 31 期第 3 条：整跑要开几十个 Tk 窗口（主界面、云朵框、各种弹窗，三虎那朵云还是
    置顶无边框窗），跑一遍一百秒里用户在自己机器上干活会被反复盖住。这里把「置顶」和
    「抬到最前面」两个动作都拦下来：置顶请求一律改写成 False，抬窗／显示之后立刻压回去。
    只对 Tk／Toplevel 这种真窗口生效，画布之类的子控件不碰（lower 对它们是改同层叠放）。
    """
    import tkinter as tk
    if getattr(tk, '_drama_sunk_windows', False):
        return
    tk._drama_sunk_windows = True
    original_attrs = tk.Wm.wm_attributes
    tk._drama_real_wm_attributes = original_attrs
    wanted = tk._drama_wanted_topmost = {}

    def wm_attributes(self, *args):
        if len(args) == 2 and args[0] == '-topmost':
            # 真窗口一律不置顶（不然盖住用户），但把「代码想要什么」记下来：用例读 attributes
            # 读到的仍是它请求的值，置顶这件事照旧被盯着；真实状态用 real_topmost 看。
            wanted[self] = str(args[1]) not in ('0', 'False', 'false')
            original_attrs(self, '-topmost', False)
            return ''
        if len(args) == 1 and args[0] == '-topmost' and self in wanted:
            return wanted[self]
        return original_attrs(self, *args)

    tk.Wm.wm_attributes = wm_attributes
    tk.Wm.attributes = wm_attributes

    def sink(widget):
        if not isinstance(widget, (tk.Tk, tk.Toplevel)):
            return
        try:
            tk.Misc.lower(widget)
        except Exception:
            pass

    def wrap(cls, name):
        original = getattr(cls, name, None)
        if original is None:
            return

        def wrapper(self, *args, **kwargs):
            outcome = original(self, *args, **kwargs)
            sink(self)
            return outcome

        wrapper.__name__ = name
        setattr(cls, name, wrapper)

    for name in ('lift', 'tkraise'):
        wrap(tk.Misc, name)
    for name in ('deiconify', 'focus_force'):
        wrap(tk.Wm if hasattr(tk.Wm, name) else tk.Misc, name)
    # 不包装 destroy：after_cancel 会提前删除 Tcl 回调命令，随后 Tk 自己销毁控件时
    # 又会删除同一命令，最终将正常 UI 断言伪造成 “can't delete Tcl command”。
    # state 不挂：它既被当取值器用，又在新窗口刚建好时被调（desktop／ui_theme 都写 state('normal')），
    # 那一拍 lower() 会打乱刚建页面的排版反馈（Treeview 按容器高度定行数），实测把内容框高度算飞。
    # deiconify／lift 已经盖住了「窗口冒出来」这条路；真需要最大化时那条路上也还有一次 lift。


def real_topmost(widget):
    """窗口在系统里真实的置顶状态。

    sink_test_windows 会把 attributes('-topmost') 的读值换成「代码请求的值」（用例要盯住
    「云朵框有没有要求置顶」），所以真实状态得走这里看：自检期间它一定是 False。
    """
    import tkinter as tk
    getter = getattr(tk, '_drama_real_wm_attributes', None)
    if getter is None:
        return bool(widget.wm_attributes('-topmost'))
    return bool(getter(widget, '-topmost'))


def protect_tk():
    """自测也要给 Tk 解释器上同一层保护。

    自测进程每例都建 Tk 窗口、还留着常驻 worker 线程：worker 里的一次 GC 就可能把主线程建的窗口
    对象环连同 Tcl 解释器一起回收，Tcl 会直接中止进程（Tcl_AsyncDelete），表现为整跑崩掉、
    一条用例结果都不打印。主程序在 Desktop 启动时装这层保护，自测在发现用例之前装。
    """
    sink_test_windows()          # 第 31 期第 3 条：自检的窗口一律沉到桌面最底层，不打扰用户
    # 第 47 期第 3 条：点「手动XX」时那句「先去阶段配置挑模型」的提醒框，整跑里一律换成
    # 「先不配，照旧开始」——用例点到那颗按钮时不该弹个模态框把整跑卡死。要盯这句话的用例
    # 自己换回来（见 test_manual_gate.py），它验的就是这里的默认值被换掉以后的行为。
    try:
        import stage_models
        stage_models.ASKER = lambda *a, **k: False
        # 第 54 期附件三那扇「手动制作XX」精简窗同理：整跑里一律按「直接执行」，
        # 用例点到那颗按钮时不该冒出一个模态窗把整跑卡死。要盯这一窗的用例自己换回来
        # （见 test_manual_plan.py 与 test_manual_gate.py）。
        stage_models.PLANNER = lambda *a, **k: 'run'
    except Exception as exc:
        print('「先挑模型」提醒未改写成假函数：' + str(exc))
    try:
        from desktop import protect_tk_gc
        protect_tk_gc()
    except Exception as exc:
        print('Tk 保护未安装：' + str(exc))


def import_all():
    """把每个模块都导入一遍（语法／导入期错误在这一步就该暴露）。"""
    fails = []
    for f in glob.glob(os.path.join(HERE, "*.py")):
        m = os.path.basename(f)[:-3]
        if m in SKIP or m.startswith("启动"):
            continue
        try:
            importlib.import_module(m)
        except ModuleNotFoundError as e:
            if e.name == "bpy":
                continue  # Blender-only template, expected outside Blender
            fails.append((m, str(e)))
        except Exception as e:
            fails.append((m, f"{type(e).__name__}: {e}"))
    return fails


def test_modules(keys=()):
    """要跑哪些测试文件（测试统一收拢到 tests/，可带 -k 片段过滤）。"""
    nested = glob.glob(os.path.join(TESTS_DIR, "**", "test_*.py"), recursive=True)
    names = sorted({os.path.relpath(f, TESTS_DIR)[:-3].replace(os.sep, '.') for f in nested})
    if keys:
        names = [n for n in names if any(k in n for k in keys)]
    return names


def test_path(name):
    """测试模块名对应的唯一源文件。"""
    return os.path.join(TESTS_DIR, *name.split('.')) + '.py'


def gui_test_module(name):
    """按测试文件的直接依赖识别 GUI 测试，避免服务层偷偷拉起 Tk。"""
    imports = imports_of(test_path(name))
    return bool({'tkinter', 'desktop', 'pet_ui', 'ui_theme'} & imports)


def modules_for_layer(names, layer):
    """测试分层：架构、无 Tk 服务、短 Tk 与端到端桌面用例互斥。"""
    if not layer:
        return list(names)
    if layer not in TEST_LAYERS:
        raise ValueError('未知测试层：%s（可用：%s）' % (layer, '、'.join(TEST_LAYERS)))
    architecture = [name for name in names if name.startswith('architecture.test_')]
    if layer == 'architecture':
        return architecture
    non_architecture = [name for name in names if name not in architecture]
    gui = [name for name in non_architecture if gui_test_module(name)]
    if layer == 'gui':
        return gui
    if layer == 'gui-e2e':
        return [name for name in gui if name.rsplit('.', 1)[-1] in GUI_E2E_MODULES]
    if layer == 'gui-short':
        return [name for name in gui if name.rsplit('.', 1)[-1] not in GUI_E2E_MODULES]
    return [name for name in non_architecture if name not in gui]


def _flat_cases(suite):
    """把一个测试套件里的用例摊平成一张表（类名按发现顺序保留）。"""
    out = []
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            out.extend(_flat_cases(item))
        else:
            out.append(item)
    return out


def split_classes(cases):
    """按类把用例分组：先把同一个类的用例归到一起（发现顺序不变）。"""
    order, groups = [], {}
    for case in cases:
        name = type(case).__name__
        if name not in groups:
            groups[name] = []
            order.append(name)
        groups[name].append(case)
    return [(name, groups[name]) for name in order]


def chunks_of(groups, limit=CHUNK_TESTS):
    """把类按顺序装进几个不超过 limit 条的筐子里。

    一个大类（UiEdgeTests 那种几十条、每条都要建整套界面的）自己就超了 limit，会被**拆开**——
    拆的是同一个类的不同用例，安全：setUp／setUpClass 本来就是每路各跑一遍的，用例之间不共享状态。
    筐子里记的是 (类名, 用例方法名表)，跑到哪一路都只跑这几条。
    """
    out, bucket, count = [], [], 0
    for name, cases in groups:
        for start in range(0, len(cases), limit):
            part = cases[start:start + limit]
            if bucket and count + len(part) > limit:
                out.append(bucket)
                bucket, count = [], 0
            bucket.append((name, [case._testMethodName for case in part]))
            count += len(part)
    if bucket:
        out.append(bucket)
    return out


def units(names, whole=False):
    """测试文件 → 工作单元：大文件按类切成几路，小文件一整路。

    单元是 (标签, 文件名, [(类名, 用例方法名表)] 或 None)；标签只给打印和报红用。
    """
    loader = unittest.TestLoader()
    out = []
    for name in names:
        if whole:
            out.append((name, name, None))
            continue
        try:
            cases = _flat_cases(loader.loadTestsFromName(name))
        except Exception:
            out.append((name, name, None))
            continue
        if len(cases) <= SPLIT_OVER:
            out.append((name, name, None))
            continue
        for index, group in enumerate(chunks_of(split_classes(cases))):
            out.append(('%s#%d' % (name, index + 1), name, group))
    return out


def _run_unit(payload):
    """子进程里跑一个工作单元；返回 (标签, 文件名, 条数, 坏例, 细节, 秒数, 输出)。"""
    label, module, classes = payload
    os.chdir(HERE)
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    protect_tk()
    stdio_save = sys.stdout, sys.stderr
    buf = io.StringIO()
    sys.stdout = sys.stderr = buf
    started = time.time()
    try:
        loader = unittest.TestLoader()
        if classes:
            mod = importlib.import_module(module)
            suite = unittest.TestSuite()
            for class_name, methods in classes:
                wanted = set(methods)
                for case in _flat_cases(loader.loadTestsFromTestCase(getattr(mod, class_name))):
                    if case._testMethodName in wanted:
                        suite.addTest(case)
        else:
            suite = loader.loadTestsFromName(module)
        result = unittest.TextTestRunner(stream=buf, verbosity=1).run(suite)
        bad = [str(case) for case, _tb in list(result.failures) + list(result.errors)]
        detail = ''
        for case, tb in list(result.failures) + list(result.errors):
            detail += "\n===== %s =====\n%s" % (case, tb)
        return (label, module, result.testsRun, bad, detail, time.time() - started, buf.getvalue())
    except Exception as exc:                     # 这一路起不来（导入期就炸）
        return (label, module, 0, [label], "\n===== %s 起不来 =====\n%s" % (label, exc),
                time.time() - started, buf.getvalue())
    finally:
        # 一路测试可能通过 Desktop → asset_thumbs 启动后台 Tk 解码器；测试进程退出
        # 不会替它收尾，导致全量并行后积累几十个 Python 进程并让 smoke 卡住。
        cleanup_unit_helpers()
        sys.stdout, sys.stderr = stdio_save


def _worker(payload):
    return _run_unit(payload)


def _serial_worker(payload, result_sender):
    """隔离安全串行的单元，使失控的 Tk 模态窗能被父进程超时回收。"""
    try:
        result_sender.send(_run_unit(payload))
    finally:
        result_sender.close()


def cleanup_unit_helpers():
    """回收测试单元启动的后台助手，避免 Windows 留下缩略图孤儿进程。"""
    try:
        import asset_thumbs
        asset_thumbs.forget()
        asset_thumbs.reset_worker()
    except Exception:
        pass                         # 清理失败不能覆盖原测试的报错


def slowest_units(results, limit=SLOW_UNITS_LIMIT):
    """按耗时降序给出有限的工作单元摘要；不影响执行或成功判定。"""
    return sorted(results, key=lambda item: item[5], reverse=True)[:max(0, limit)]


def print_unit_result(item):
    print('  %-26s %5d 条  %6.1f 秒%s' % (item[0], item[2], item[5],
                                          '  ✗ ' + str(len(item[3])) if item[3] else ''))


def run_units(todo, jobs=8):
    """并行跑（Windows 上 spawn：每个子进程自己建 Tk，互不打扰）。"""
    import concurrent.futures as futures
    out = []
    pool = futures.ProcessPoolExecutor(max_workers=max(1, jobs))
    timed_out = False
    try:
        pending = {pool.submit(_worker, payload): payload for payload in todo}
        last_progress = time.time()
        while pending:
            done, waiting = futures.wait(pending, timeout=HEARTBEAT_SECONDS,
                                         return_when=futures.FIRST_COMPLETED)
            if not done:
                print('  … 并行回归仍在执行：%d 路未完成（每 %d 秒心跳）' %
                      (len(waiting), HEARTBEAT_SECONDS), flush=True)
                if time.time() - last_progress < SAFE_UNIT_TIMEOUT:
                    continue
                stalled = [pending[future] for future in waiting]
                labels = [payload[0] for payload in stalled]
                print('  ! 并行池连续 %d 秒无进展，回收 %d 路卡住单元：%s' %
                      (SAFE_UNIT_TIMEOUT, len(labels), ' '.join(labels)), flush=True)
                for process in pool._processes.values():
                    process.terminate()
                now = time.time()
                out.extend((payload[0], payload[1], 0, [payload[0]],
                            '\n===== %s 超时 =====\n并行池连续 %d 秒无进展，已回收。' %
                            (payload[0], SAFE_UNIT_TIMEOUT), now - last_progress, '')
                           for payload in stalled)
                pending = {}
                timed_out = True
                break
            for future in done:
                item = future.result()
                out.append(item)
                print_unit_result(item)
                pending.pop(future)
            last_progress = time.time()
    finally:
        # ``with ProcessPoolExecutor`` always waits in __exit__.  Once a GUI
        # worker is known stuck, that turns the watchdog into another hang.
        pool.shutdown(wait=not timed_out, cancel_futures=timed_out)
    return out


def run_serial(todo, timeout=SAFE_UNIT_TIMEOUT):
    """一次只跑一个单元，并为每段 UI 回归设置可回收的超时边界。"""
    import multiprocessing
    out = []
    for payload in todo:
        print('  → 开始 %-26s' % payload[0], flush=True)
        started = time.time()
        result_reader, result_sender = multiprocessing.Pipe(duplex=False)
        process = multiprocessing.Process(target=_serial_worker, args=(payload, result_sender))
        try:
            process.start()
        except OSError as exc:
            # Windows 在长安全串行运行中可能拒绝复制新子进程的管道句柄。
            # 不能把尚未执行的测试误报为通过；退回当前进程直接运行并保留真实结果。
            result_sender.close()
            result_reader.close()
            print('  ! 安全隔离进程未启动，改为同进程执行：' + str(exc), flush=True)
            item = _run_unit(payload)
            out.append(item)
            print_unit_result(item)
            continue
        result_sender.close()
        try:
            # Pipe.poll 有明确的超时语义；即使 Tk 子进程异常退出而未回传，也不会永久卡在
            # Queue.get。仍须先接收再 join，避免大结果堵住回传管道。
            if not result_reader.poll(timeout):
                raise TimeoutError
            item = result_reader.recv()
        except (EOFError, TimeoutError):
            process.terminate()
            process.join(10)
            item = (payload[0], payload[1], 0, [payload[0]],
                    '\n===== %s 超时 =====\n安全串行单元超过 %d 秒，已回收。' % (payload[0], timeout),
                    time.time() - started, '')
        else:
            process.join(10)
            if process.is_alive():
                process.terminate()
                process.join(10)
        result_reader.close()
        out.append(item)
        print_unit_result(item)
    return out


def run_safe_serial(todo):
    """安全全量在当前进程逐单元执行，规避 Windows 长运行的 spawn 管道句柄限制。

    ``--serial`` 仍保留子进程隔离与超时回收；``--safe`` 的目标是同一时刻只运行一个
    测试单元，直接调用既能满足该目标，也不会在数百次 Windows spawn 后失去结果汇总。
    """
    out = []
    for payload in todo:
        print('  → 开始 %-26s' % payload[0], flush=True)
        item = _run_unit(payload)
        out.append(item)
        print_unit_result(item)
    return out


def split_safe_units(todo):
    """把可能创建 Tk 的单元识别出来，交给受控的 Tk 工作池。"""
    gui, non_gui = [], []
    for unit in todo:
        (gui if gui_test_module(unit[1]) else non_gui).append(unit)
    return non_gui, gui


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    keys, jobs, serial, listing, whole = [], 0, False, False, False
    everything, safe, force, layer = False, False, False, ''
    while argv:
        arg = argv.pop(0)
        if arg == '--serial':
            serial = True
        elif arg == '--list':
            listing = True
        elif arg == '--whole':
            whole = True
        elif arg == '--safe':
            safe = True
        elif arg == '--force':
            force = True
        elif arg == '--all':
            everything = True
        elif arg == '--incremental':
            # 默认就是增量模式；保留显式开关给三虎测试模式与脚本调用，不能把它当成 -k 关键字。
            pass
        elif arg == '--layer':
            layer = argv.pop(0).strip().lower()
        elif arg == '--jobs':
            jobs = int(argv.pop(0))
        elif arg == '-k':
            keys.extend(argv.pop(0).split())
        else:
            keys.append(arg)
    everything, serial, whole, jobs = safe_full_options(everything, serial, whole, jobs, safe)
    all_names = test_modules()
    names = test_modules(keys)
    try:
        all_names = modules_for_layer(all_names, layer)
        names = modules_for_layer(names, layer)
    except ValueError as exc:
        print(str(exc))
        return 2
    if layer:
        print('测试层：%s（%d 个测试文件）' % (layer, len(names)))
    if listing:
        for name in names:
            print(name)
        return 0
    full_safe = everything and safe and not keys and not layer
    tree = content_tree() if full_safe else ''
    verified = verified_tree_record(load_layer_document().get('full_safe_verified_trees', []), tree)
    if full_safe and verified and not force:
        print('内容树同 R%s 已验证(3,698 条/%.3f秒/0 红)' %
              (verified['round'], float(verified['seconds'])))
        return 0
    if full_safe:
        try:
            lock = acquire_full_safe_lock(round_number=latest_completed_round())
        except RuntimeError as exc:
            print(str(exc))
            return 2
        atexit.register(release_full_safe_lock, lock)
    if not serial and not jobs:
        jobs = max(2, min(JOBS_CAP, (os.cpu_count() or 4)))
    protect_tk()
    fails = import_all()
    if fails:
        print("IMPORT FAILURES:")
        for m, e in fails:
            print(f"  {m}: {e}")
    else:
        print("IMPORT OK: all modules imported")
    cache = {} if everything else load_cache()
    todo_names, skipped, state = incremental(names, cache)
    if keys:
        # -k 是显式门禁，不应被增量台账跳过；同时不能因只跑一个用例而抹掉其他用例的缓存。
        old_tests = cache.get('tests') if isinstance(cache.get('tests'), dict) else {}
        selected_tests = state['tests']
        state['tests'] = {name: entry for name, entry in old_tests.items() if name in all_names}
        state['tests'].update(selected_tests)
        todo_names, skipped = list(names), []
        print('定向：忽略增量台账，执行 %d 个匹配测试文件' % len(names))
    elif everything:
        todo_names, skipped = list(names), []
        print('%s：忽略增量台账，%d 个测试文件全跑一遍' %
              ('--safe（全量受控分池）' if safe else '--all', len(names)))
    elif skipped:
        print('增量：跳过 %d 个没改过的测试文件（--all 全跑）：%s' % (len(skipped), ' '.join(skipped)))
    keep = set(todo_names)
    todo = [unit for unit in units(names, whole=whole) if unit[1] in keep]
    # 性能用例（test_perf_*.py）不与别的用例挤并行池：它们量的是墙上时间，而「建 Tk 控件＋
    # 字体量宽」是全机共享的资源，被别的用例抢慢好几倍时，会把自己的抖动判成性能退化
    # （第 72 期实测：并行时资产页打开 3.9～6.8 s，单独跑 0.3～0.5 s）。挑出来等池子空了自己跑。
    perf = [unit for unit in todo if unit[1].startswith('test_perf')]
    todo = [unit for unit in todo if unit not in perf]
    print('跑 %d 个测试文件 / %d 路工作单元（%s）' % (len(todo_names), len(todo),
                                                  '串行' if serial else '%d 路并行' % jobs))
    if perf:
        print('另有 %d 个工作单元是性能用例，排在并行池之后单独串行跑' % len(perf))
    started = time.time()
    if safe:
        non_gui, gui = split_safe_units(todo)
        gui_jobs = safe_gui_jobs(jobs)
        if non_gui or gui:
            print('安全分池：%d 路无 Tk 并行（%d workers），%d 路 Tk 受控并行（%d workers）' %
                  (len(non_gui), jobs, len(gui), gui_jobs))
        got = run_units(non_gui, jobs) if non_gui else []
        got += run_units(gui, gui_jobs) if gui else []
        got += run_safe_serial(perf)
    else:
        got = run_serial(todo) if serial else run_units(todo, jobs)
        got += run_serial(perf)
    elapsed = time.time() - started
    total = sum(item[2] for item in got)
    reds = [(item[1], item[3], item[4]) for item in got if item[3]]
    print('\n共 %d 条用例，%.1f 秒；%d 个文件有红' % (total, elapsed, len(reds)))
    slow = slowest_units(got)
    if slow:
        print('最慢 %d 路工作单元：' % len(slow))
        for item in slow:
            print('  %-26s %6.1f 秒 / %d 条' % (item[0], item[5], item[2]))
    for name, bad, detail in reds:
        print('\n### %s（%d 条红）' % (name, len(bad)))
        print(detail)
    baseline = save_layer_baseline(layer, got, elapsed)
    if baseline:
        print('分层基线已刷新：' + baseline)
    if fails or reds:
        failed_tree = content_tree()
        if failed_tree and invalidate_verified_tree(load_layer_document(), failed_tree):
            print('当前内容树的全量绿凭据已失效：本轮存在红项')
        raise SystemExit(1)
    if full_safe and tree and is_master_checkout():
        saved = save_full_safe_verification(tree, latest_completed_round(), elapsed)
        if saved:
            print('内容树全量凭据已刷新：' + saved)
    timings = record_elapsed(cache, state, elapsed)
    written = save_cache(state)
    if written:
        print('增量台账已刷新：' + written)
        print('最近 %d 轮自检中位基线：%.1f 秒' % (len(timings['recent_seconds']), timings['median_seconds']))
    print("\nALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    main()
