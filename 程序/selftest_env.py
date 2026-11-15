# -*- coding: utf-8 -*-
"""自检公共基座：路径、常量、Git common-dir 与 PID/锁文件原语。

路径与抑制环境变量必须最先生效：任何 selftest_* 子模块被导入时都先经这里把
程序根与 tests/ 挂进 sys.path，并给子进程关掉模态框/托盘/联网/诊断写入。"""

import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
from datetime import timedelta

# 自检子进程继承：通知分发器不弹系统模态框，避免无人值守时卡住（见 ui_widgets.SUPPRESS_MODAL_ENV）。
os.environ.setdefault("DRAMA_SUPPRESS_MODAL", "1")
# 同理：测试里构造 Desktop 不起真实托盘线程（见 desktop_tray.SUPPRESS_TRAY_ENV）。
os.environ.setdefault("DRAMA_SUPPRESS_TRAY", "1")
# 同理：首帧自动检查总控包更新不真联网，也不会因“有新版本”弹确认窗卡住（见 master_skill_update.SUPPRESS_NETWORK_ENV）。
os.environ.setdefault("DRAMA_SUPPRESS_NETWORK", "1")
# 同理：测试里故意触发的报错不写进程序自己的诊断记录（见 diagnostic_capture.SUPPRESS_DIAGNOSTICS_ENV）。
os.environ.setdefault("DRAMA_SUPPRESS_DIAGNOSTICS", "1")
os.environ.setdefault("DRAMA_REDUCE_MOTION", "0")  # 自检固定保留动效，不随本机系统设置漂移



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


SAFE_GUI_JOBS = 4       # R968 全量 A/B 候选；须以最终树连续两轮 ≤420 秒且 0 红验收


SAFE_UNIT_TIMEOUT = 180 # 安全串行性能用例的一小段最长允许三分钟，避免模态窗永久占住门禁


HEARTBEAT_SECONDS = 30  # 并行全量久未完成时仍需给出活跃心跳，方便定位是否只是慢


SLOW_UNITS_LIMIT = 10   # 汇总只保留最慢若干工作单元，避免全量输出淹没结论


SKIP_REPORT_LIMIT = 40  # 实际跳过清单最多打印这么多条；总数始终打印，避免把登记位读成已跳过


PID_REUSE_TOLERANCE_SECONDS = 120


CACHE_NAME = 'selftest-incremental.json'


INCREMENTAL_RULES = 2


FULL_SAFE_LOCK_NAME = 'full-safe-selftest.lock'


GUI_LOCK_NAME = 'gui-selftest.lock'


GUI_QUEUE_NAME = 'gui-selftest.queue'


GUI_QUEUE_SUFFIX = '.ticket'


GUI_WAIT_SECONDS = 900


GUI_WAIT_NOTICE_SECONDS = 30.0


GUI_LOCK_POLL_SECONDS = 0.1


LAYER_BASELINE_NAME = os.path.join('维护记录', '测试分层基线.json')


FULL_SAFE_TREE_TTL = timedelta(days=7)


FULL_SAFE_ROUND_INTERVAL = 5


FULL_SAFE_AUTO_LEAD = 2


FULL_SAFE_RISK_GRACE = 2


AUTO_FULL_LOCK_NAME = 'auto-full-safe.lock'


AUTO_FULL_STALE_SECONDS = 3 * 3600


NON_SOURCE_DIRS = ('tests/', 'tasks_round/', '维护记录/', '说明/', 'logs/')


_ROUND_SUBJECT = re.compile(r'^R(\d+)(?:-FAIL)?[:：]')


DATA_GLOBS = ('skills/*.skill.md', 'skills/*/*.md', 'skills/*/*/*.md')


TEST_LAYERS = ('architecture', 'service', 'gui', 'gui-short', 'gui-e2e')


GUI_E2E_MODULES = frozenset({'test_pet_ui', 'test_ui_edges_autopilot', 'test_ui_edges_pages',
                             'test_ui_edges_tables', 'test_ui_edges_controls'})


PERFORMANCE_MODULES = frozenset({'test_desktop_startup_perf'})


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
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}
