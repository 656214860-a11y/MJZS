# -*- coding: utf-8 -*-
"""自检公共基座：路径、常量、Git common-dir 与 PID/锁文件原语。

路径与抑制环境变量必须最先生效：任何 selftest_* 子模块被导入时都先经这里把
程序根与 tests/ 挂进 sys.path，并给子进程关掉模态框/托盘/联网/诊断写入。"""

import gc
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

# 自检子进程继承：通知分发器不弹系统模态框，避免无人值守时卡住（见 ui_widgets.SUPPRESS_MODAL_ENV）。
os.environ.setdefault("DRAMA_SUPPRESS_MODAL", "1")
# 同理：测试里构造 Desktop 不起真实托盘线程（见 desktop_tray.SUPPRESS_TRAY_ENV）。
os.environ.setdefault("DRAMA_SUPPRESS_TRAY", "1")
# 同理：自检环境不真联网（账号、总控包更新等网络探测一律跳过，见 account_client.SUPPRESS_NETWORK_ENV）。
os.environ.setdefault("DRAMA_SUPPRESS_NETWORK", "1")
# 同理：自检派生的全部子进程（工作单元、隐藏桌面、用例自起的 git/python）一律 UTF-8 模式——
# cp936 本地化下 text=True 的 subprocess 会把 git/工具的 UTF-8 输出按 GBK 解码，
# reader 线程抛 UnicodeDecodeError 使 stdout/stderr 变 None（R3315）。
os.environ.setdefault("PYTHONUTF8", "1")
# 同理：测试里故意触发的报错不写进程序自己的诊断记录（见 diagnostic_capture.SUPPRESS_DIAGNOSTICS_ENV）。
os.environ.setdefault("DRAMA_SUPPRESS_DIAGNOSTICS", "1")
os.environ.setdefault("DRAMA_REDUCE_MOTION", "0")  # 自检固定保留动效，不随本机系统设置漂移


def configure_utf8_stdio(line_buffering=None):
    """将当前进程的 stdout/stderr 切到 UTF-8 + replace，避免 Windows GBK 终端遇 ✗ 等符号抛错。"""
    kwargs = {'encoding': 'utf-8', 'errors': 'replace'}
    if line_buffering is not None:
        kwargs['line_buffering'] = bool(line_buffering)
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        try:
            stream.reconfigure(**kwargs)
        except (AttributeError, OSError, ValueError, TypeError):
            pass


def safe_write(text, stream=None, flush=False):
    """安全写入流：若流未切 UTF-8 且遇非 GBK 字符，按该流编码以 replace 降级而不抛错。"""
    target = sys.stdout if stream is None else stream
    if target is None:
        return
    content = str(text)
    try:
        target.write(content)
    except UnicodeEncodeError:
        encoding = getattr(target, 'encoding', None) or 'utf-8'
        sanitized = content.encode(encoding, errors='replace').decode(encoding, errors='replace')
        target.write(sanitized)
    if flush:
        target.flush()


def safe_print(text='', stream=None, flush=False):
    """按 safe_write 输出一行文本。"""
    safe_write(str(text) + '\n', stream=stream, flush=flush)


def utf8_subprocess_env(base=None, **overrides):
    """为自检子进程强制注入 UTF-8 标准流环境，覆盖调用端可能遗留的 GBK 配置。"""
    merged = dict(os.environ if base is None else base)
    merged['PYTHONIOENCODING'] = 'utf-8'
    merged['PYTHONUTF8'] = '1'
    merged.update(overrides)
    return merged



HERE = os.path.dirname(os.path.abspath(__file__))

_LEASE_DIR = os.path.join(HERE, "维护记录", "基准脚本")
if _LEASE_DIR not in sys.path:
    sys.path.append(_LEASE_DIR)
import lock_lease  # noqa: E402


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


SAFE_GUI_JOBS = 4       # R968 全量 A/B 候选；须以最终树连续两轮 ≤420 秒且 0 红验收


SAFE_UNIT_TIMEOUT = 180 # 安全串行性能用例的一小段最长允许三分钟，避免模态窗永久占住门禁


HEARTBEAT_SECONDS = 30  # 并行全量久未完成时仍需给出活跃心跳，方便定位是否只是慢


SLOW_UNITS_LIMIT = 10   # 汇总只保留最慢若干工作单元，避免全量输出淹没结论


SKIP_REPORT_LIMIT = 40  # 实际跳过清单最多打印这么多条；总数始终打印，避免把登记位读成已跳过


PID_REUSE_TOLERANCE_SECONDS = 120


CACHE_NAME = 'selftest-incremental.json'


INCREMENTAL_RULES = 2


FULL_SAFE_LOCK_NAME = 'full-safe-selftest.lock'  # 只拦 master/main 提交；超长全量不再创建它
FULL_SAFE_RUNNER_LOCK_NAME = 'full-safe-runner.lock'  # 同一时刻一份全量，不拦车道提交与合并


GUI_LOCK_NAME = 'gui-selftest.lock'


GUI_QUEUE_NAME = 'gui-selftest.queue'


GUI_QUEUE_SUFFIX = '.ticket'


GUI_WAIT_SECONDS = 300    # P1-1：跨树排队最多等 5 分钟；30 分钟占队是全量锁卡死主因，超时按 DEFERRED 记
GUI_FULL_SUITE_WAIT_SECONDS = 60   # 别人正在跑全量时，本会话最多再等一分钟，不等完整段 Tk


GUI_WAIT_NOTICE_SECONDS = 30.0


GUI_LOCK_POLL_SECONDS = 0.1


LAYER_BASELINE_NAME = os.path.join('维护记录', '测试分层基线.json')


FULL_SAFE_TREE_TTL = timedelta(days=7)


FULL_SAFE_ROUND_INTERVAL = 8


FULL_SAFE_AUTO_LEAD = 2


FULL_SAFE_RISK_GRACE = 2


AUTO_FULL_LOCK_NAME = 'auto-full-safe.lock'


AUTO_FULL_STALE_SECONDS = 3 * 3600


NON_SOURCE_DIRS = ('tests/', 'tasks_round/', '维护记录/', 'docs/', 'governance/', 'resources/', 'logs/')


_ROUND_SUBJECT = re.compile(r'^R(\d+)(?:-FAIL)?[:：]')


DATA_GLOBS = ('skills/*.skill.md', 'skills/*/*.md', 'skills/*/*/*.md')


TEST_LAYERS = ('architecture', 'service', 'gui', 'gui-short', 'gui-e2e')


GUI_E2E_MODULES = frozenset({
    'test_pet_ui', 'test_pet_ui_view', 'test_pet_ui_popup',
    'test_pet_ui_voice', 'test_pet_ui_stages', 'test_pet_ui_settings',
    'test_ui_edges_autopilot', 'test_ui_edges_pages',
    'test_ui_edges_tables', 'test_ui_edges_controls',
})


PERFORMANCE_MODULES = frozenset({'test_desktop_startup_perf', 'test_soak_light'})


def _digest(path):
    """一个文件的指纹（读不出来就当空串——空串永远算「变了」，宁可多跑不许漏跑）。"""
    try:
        with open(path, 'rb') as handle:
            return hashlib.sha1(handle.read()).hexdigest()
    except OSError:
        return ''


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
    # abspath 统一斜杠：git 给 D:/…，mkstemp 给 D:\…，队列按字符串比对队首。
    return os.path.abspath(path if os.path.isabs(path) else os.path.join(HERE, path))


def _process_created_at(pid):
    """取 PID 当前进程的创建时间（epoch 秒）；不支持或取不到时返回 None，由调用方退回只看 PID。"""
    try:
        pid = int(pid)
    except (ValueError, TypeError):
        return None
    if pid <= 0:
        return None
    if os.name != 'nt':
        # 非 Windows 已用 kill(0) 判死；不引入 /proc 等平台专属探测。
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class FileTime(ctypes.Structure):
            _fields_ = [('low', wintypes.DWORD), ('high', wintypes.DWORD)]

        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.POINTER(FileTime),
                                             ctypes.POINTER(FileTime), ctypes.POINTER(FileTime),
                                             ctypes.POINTER(FileTime)]
        kernel32.GetProcessTimes.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return None
        try:
            created = FileTime()
            empty = [FileTime() for _ in range(3)]
            if not kernel32.GetProcessTimes(handle, created, empty[0], empty[1], empty[2]):
                return None
            ticks = (created.high << 32) | created.low
            return ticks / 10000000.0 - 11644473600
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return None


def _record_is_reused(pid, started_at):
    """持有者记录的发起早于该 PID 当前进程创建时间，说明 PID 已被别的进程复用。"""
    if started_at is None or started_at is False:
        return False
    try:
        started_at = float(started_at)
    except (TypeError, ValueError):
        return False
    created_at = _process_created_at(pid)
    if created_at is None or started_at >= created_at - PID_REUSE_TOLERANCE_SECONDS:
        return False
    # 未来时间不按复用处理：时钟回拨或伪造记录不应把活锁误清。
    return started_at <= time.time() + PID_REUSE_TOLERANCE_SECONDS


def _pid_is_alive(pid, started_at=None):
    try:
        pid = int(pid)
    except (ValueError, TypeError):
        return False
    if _record_is_reused(pid, started_at):
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


def lock_holder(path):
    try:
        with io.open(path, encoding='utf-8') as handle:
            text = handle.read()
        if not text.strip():
            return {}
        # 心跳原地覆盖后，文件尾部可能留下上一次更长的内容。
        value, _end = json.JSONDecoder().raw_decode(text)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def holder_is_live(holder, now=None):
    """有心跳时只看 3 分钟静默；旧锁没有心跳，仍按 PID。"""
    return lock_lease.is_live(holder, now=now, legacy_pid_alive=_pid_is_alive)


def _holder_stalled(holder, now=None, stale=lock_lease.LOCK_STALE_SECONDS):
    """持有者超过 stale 秒没有心跳 → 卡死，与 lock_lease.is_live 同一静默口径。

    心跳字段兼容 heartbeat_at／heartbeat；没有心跳的旧锁退回 started_at／created_at
    的年龄；时间戳在未来不按卡死处理；空或非法 holder 按不活跃处理（True）。
    """
    moment = time.time() if now is None else now
    if not isinstance(holder, dict) or not holder:
        return True
    beat = holder.get('heartbeat_at')
    if beat is None:
        beat = holder.get('heartbeat')
    if beat is not None:
        try:
            return (moment - float(beat)) >= stale
        except (TypeError, ValueError):
            return True
    for key in ('started_at', 'created_at'):
        if holder.get(key) is None:
            continue
        try:
            return (moment - float(holder[key])) >= stale
        except (TypeError, ValueError):
            return True
    return True


def inspect_lock(path):
    return lock_lease.inspect(path, legacy_pid_alive=_pid_is_alive)


def reclaim_stale_lock(path):
    """心跳已停、或旧锁的进程已不在，并且文件身份未变时删除。"""
    return lock_lease.reclaim(path, legacy_pid_alive=_pid_is_alive)


def arm_lock(path):
    lock_lease.arm(path)


def disarm_lock(path):
    lock_lease.release(path)


# ── 自检临时目录沙盒 ────────────────────────────────────────────────
# 用例大量用 tempfile.mkdtemp()/TemporaryDirectory()；Windows 上文件句柄晚一步释放就删不掉，
# 每跑一次全量在 %TEMP% 留一批空 tmp 目录（实测上万个，拖慢资源管理器与临时目录扫描）。
# 这里给每次自检一个带前缀的本轮根：子进程把 tempfile 落点指过去，父进程跑完整根删掉；
# 删不掉的留到下一轮按超期回收。只认本模块前缀，其它程序的临时目录一律不碰。

TEST_TEMP_PREFIX = 'drama-test-'
TEST_TEMP_ENV = 'DRAMA_TEST_TEMP'
TEST_TEMP_STALE_SECONDS = 24 * 60 * 60
TEST_TEMP_RETRIES = 6
TEST_TEMP_RETRY_PAUSE = 0.25


def _force_remove(function, target, _error):
    """rmtree 兜底：Windows 的只读属性会让删除失败，去掉只读位再试一次。"""
    try:
        os.chmod(target, stat.S_IWRITE)
    except OSError:
        pass
    function(target)


def _tree_bytes(folder):
    total = 0
    for current, _dirs, files in os.walk(folder):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(current, name))
            except OSError:
                continue
    return total


def sweep_stale_temp(base=None, *, max_age=TEST_TEMP_STALE_SECONDS, now=None):
    """回收 base 下「本模块前缀 + 超期」的临时根，返回 {base, removed, failed, bytes}。"""
    root = Path(base) if base is not None else Path(tempfile.gettempdir())
    moment = time.time() if now is None else now
    report = {'base': str(root), 'removed': 0, 'failed': 0, 'bytes': 0}
    try:
        entries = sorted(root.iterdir())
    except OSError:
        return report
    for entry in entries:
        if not entry.name.startswith(TEST_TEMP_PREFIX):
            continue
        try:
            if entry.is_symlink() or entry.is_junction() or not entry.is_dir():
                continue
            age = moment - entry.stat().st_mtime
        except OSError:
            continue
        if age < max_age:
            continue
        size = _tree_bytes(entry)
        try:
            shutil.rmtree(entry, onexc=_force_remove)
        except OSError:
            report['failed'] += 1
            continue
        report['removed'] += 1
        report['bytes'] += size
    return report


def install_temp_sandbox(root=None):
    """子进程用：把本进程 tempfile 落点指到本轮根；没有根就什么都不做并返回 None。"""
    target = root if root is not None else os.environ.get(TEST_TEMP_ENV)
    if not target:
        return None
    path = Path(str(target))
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    tempfile.tempdir = str(path)
    return path


def begin_temp_run(base=None, *, now=None):
    """自检开跑前调用：先回收超期残留，再建本轮根并把路径交给子进程。"""
    root = Path(base) if base is not None else Path(tempfile.gettempdir())
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    swept = sweep_stale_temp(root, now=now)
    folder = Path(tempfile.mkdtemp(prefix=TEST_TEMP_PREFIX, dir=str(root)))
    os.environ[TEST_TEMP_ENV] = str(folder)
    tempfile.tempdir = str(folder)
    return {'root': folder, 'swept': swept}


def finish_temp_run(folder=None, *, retries=TEST_TEMP_RETRIES):
    """删本轮根；句柄可能晚一步释放，重试几次，仍不行就留给下一轮按超期回收。"""
    target = folder if folder is not None else os.environ.get(TEST_TEMP_ENV)
    if not target:
        return True
    path = Path(str(target))
    if os.environ.get(TEST_TEMP_ENV) == str(path):
        os.environ.pop(TEST_TEMP_ENV, None)
    if tempfile.tempdir == str(path):
        tempfile.tempdir = None
    for attempt in range(max(1, int(retries))):
        try:
            shutil.rmtree(path, onexc=_force_remove)
            return True
        except FileNotFoundError:
            return True
        except OSError:
            gc.collect()
            time.sleep(TEST_TEMP_RETRY_PAUSE * (attempt + 1))
    return not path.exists()
