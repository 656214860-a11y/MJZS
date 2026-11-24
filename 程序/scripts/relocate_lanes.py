r"""把开发车道目录整体从机械盘迁到固态盘（NTFS junction 方案）。

把 ``.agents\worktrees`` 物理搬到 ``C:\dev-lanes``，再在原位置建一个目录
junction 指向新位置。git 登记的绝对路径经 junction 仍然有效，所以不改
``.git/worktrees/*/gitdir``、不用 ``git worktree move``，各窗口的 cwd 也不用改。

用法（验收窗口在停写全部车道后执行；本脚本只读预演是安全的）::

    python.exe -B scripts\relocate_lanes.py --plan        # 默认：只打印预演
    python.exe -B scripts\relocate_lanes.py --apply       # 前置全部通过才搬
    python.exe -B scripts\relocate_lanes.py --rollback    # 删 junction 搬回原位

执行者请在车道目录之外（例如 ``C:\``）运行本脚本；进程自身与祖先进程不占
「车道内 cwd」名额，但其它 python/git/Devin/Cursor 进程 cwd 落在源目录会拒绝 --apply。
不引入新依赖；真实搬迁由验收择机执行，编码轮只交脚本与测试。
"""
from __future__ import annotations

import argparse
import ctypes
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_SOURCE = Path(r"D:\漫剧制作助手\.agents\worktrees")
DEFAULT_TARGET = Path(r"C:\dev-lanes")
FREE_MULTIPLIER = 2          # C 盘余量须 ≥ 源目录大小的倍数
CPA_TIMEOUT = 15             # cpa auto status 最长等待秒数
ROBOCOPY_FAILURE = 8         # robocopy 退出码 ≥8 视为失败
INTERESTING_NAMES = ("python", "git", "devin", "cursor", "windsurf", "code")
QUEUE_NAME = "maintenance-queue.json"


def git(*args: str, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "core.quotepath=false", *args],
                          cwd=str(cwd) if cwd else None, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def disk_free_bytes(anchor) -> int:
    path = Path(anchor)
    drive = Path(path.anchor) if not path.exists() else path
    while not drive.exists() and drive != drive.parent:
        drive = drive.parent
    return shutil.disk_usage(str(drive)).free


def tree_stats(root) -> tuple[int, int, int, int]:
    """(文件数, 目录数, 总字节, junction 数)；os.walk 不跟进链接。"""
    files = dirs = size = junctions = 0
    for base, dirnames, filenames in os.walk(root):
        dirs += len(dirnames)
        for name in dirnames:
            if os.path.isjunction(os.path.join(base, name)):
                junctions += 1
        for name in filenames:
            path = os.path.join(base, name)
            if os.path.islink(path) or os.path.isjunction(path):
                junctions += 1
                continue
            files += 1
            try:
                size += os.path.getsize(path)
            except OSError:
                pass
    return files, dirs, size, junctions


def lanes_of(source) -> list[Path]:
    source = Path(source)
    return sorted(p for p in source.iterdir() if p.is_dir())


def git_lanes(source) -> list[Path]:
    return [p for p in lanes_of(source) if (p / ".git").exists()]


def porcelain_map(source) -> dict[str, str]:
    result = {}
    for lane in git_lanes(source):
        done = git("-C", str(lane), "status", "--porcelain")
        done.check_returncode()
        result[lane.name] = done.stdout
    return result


def worktree_entries(source) -> list[str]:
    """经首个 git 车道取 ``worktree list --porcelain`` 的 worktree 行。"""
    for lane in git_lanes(source):
        done = git("-C", str(lane), "worktree", "list", "--porcelain")
        if done.returncode == 0:
            return [line[9:] for line in done.stdout.splitlines()
                    if line.startswith("worktree ")]
    return []


def prune_preview(source) -> str:
    for lane in git_lanes(source):
        common = git("-C", str(lane), "rev-parse", "--git-common-dir")
        if common.returncode != 0:
            continue
        done = git("--git-dir", common.stdout.strip(),
                   "worktree", "prune", "--dry-run", "-v")
        return (done.stdout + done.stderr).strip() or "（无将清理项）"
    return "（无 git 车道，未执行）"


def toplevel_probe(source) -> str:
    """对一个车道实测 git 解析的顶层路径（junction 后是 D:/ 还是 C:/ 写法）。"""
    for lane in git_lanes(source):
        done = git("-C", str(lane), "rev-parse", "--show-toplevel")
        if done.returncode == 0:
            return "%s → %s" % (lane.name, done.stdout.strip())
    return "（无 git 车道，未实测）"


def dispatch_state(source=None) -> tuple[str, str]:
    """(idle|busy|unknown, 说明)：先 cpa auto status，读不到再看共享队列文件。"""
    try:
        done = subprocess.run("cpa auto status", shell=True, capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=CPA_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        done = None
    if done is not None and done.returncode == 0:
        text = done.stdout.strip()
        low = text.lower()
        busy = any(k in text for k in ("在派", "在途")) or \
            any(k in low for k in ("dispatching", "running", "busy", "in-flight"))
        idle = any(k in text for k in ("空闲", "无在派")) or "idle" in low
        if busy and not idle:
            return "busy", "cpa auto status 报告在派：" + text[:200]
        if idle:
            return "idle", "cpa auto status 空闲"
        return "unknown", "cpa auto status 输出无法判定：" + text[:200]
    queue = _queue_path(source)
    if queue is not None:
        found = _queue_claimed(queue)
        if found is not None:
            return found
    return "unknown", "读不到 cpa auto status，也无共享队列文件可读"


def _queue_claimed(queue) -> tuple[str, str] | None:
    """共享队列是否含 claimed 项：只做 "status":"claimed" 存在性检查，
    不解析整文件——多判 busy 是安全方向，欠检才危险；文件不存在返回 None。"""
    if not queue.is_file():
        return None
    try:
        text = queue.read_text(encoding="utf-8")
    except OSError as exc:
        return "unknown", "队列文件读取失败：%s" % exc
    if not re.search(r'"status"\s*:\s*"claimed"', text):
        return "idle", "cpa 不可用；队列无 claimed 项（%s）" % queue
    ids = re.findall(r'"id"\s*:\s*"([^"]{1,80})"(?=[^}]{0,400}?"status"\s*:\s*"claimed")',
                     text, re.S)
    return "busy", "队列 %s 有 claimed 项：%s" % (
        queue.name, "、".join(ids[:8]) or "（id 未解析）")


def _queue_path(source):
    for lane in git_lanes(source):
        done = git("-C", str(lane), "rev-parse", "--git-common-dir")
        if done.returncode == 0:
            common = Path(done.stdout.strip())
            if not common.is_absolute():
                common = (lane / common).resolve()
            return common / QUEUE_NAME
    return None


# ---- 进程 cwd 探测（Windows：读 PEB，拿不到就如实标记，不装没查） ----

_PROCESS_QUERY_LIMITED = 0x1000
_PROCESS_VM_READ = 0x0010


def _process_names() -> list[tuple[int, str]]:
    if os.name != "nt":
        return []
    done = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    rows = []
    for line in done.stdout.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[1].isdigit():
            rows.append((int(parts[1]), parts[0]))
    return rows


def _read_memory(handle, address: int, size: int) -> bytes:
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t(0)
    ok = ctypes.windll.kernel32.ReadProcessMemory(
        handle, ctypes.c_void_p(address), buf, size, ctypes.byref(got))
    return buf.raw[:got.value] if ok else b""


def _u64(blob: bytes, off: int) -> int:
    return int.from_bytes(blob[off:off + 8], "little") if len(blob) >= off + 8 else 0


def _u32(blob: bytes, off: int) -> int:
    return int.from_bytes(blob[off:off + 4], "little") if len(blob) >= off + 4 else 0


def _u16(blob: bytes, off: int) -> int:
    return int.from_bytes(blob[off:off + 2], "little") if len(blob) >= off + 2 else 0


def _pbi(handle):
    """(peb地址, 父进程pid)；64 位布局。"""
    blob = ctypes.create_string_buffer(48)
    retlen = ctypes.c_ulong(0)
    status = ctypes.windll.ntdll.NtQueryInformationProcess(
        handle, 0, blob, 48, ctypes.byref(retlen))
    if status != 0:
        return None
    raw = blob.raw
    return _u64(raw, 8), _u64(raw, 40)


def _cwd_from_peb(handle, peb: int) -> str | None:
    params = _u64(_read_memory(handle, peb + 0x20, 8), 0)
    if not params:
        return None
    curdir = _read_memory(handle, params + 0x38, 24)
    length, addr = _u16(curdir, 0), _u64(curdir, 8)
    if not length or not addr or length > 8192:
        return None
    raw = _read_memory(handle, addr, length)
    return raw.decode("utf-16-le", errors="replace") if raw else None


def _peb32(handle):
    """Wow64 进程的 32 位 PEB；读不到返回 None。"""
    value = ctypes.c_void_p(0)
    retlen = ctypes.c_ulong(0)
    status = ctypes.windll.ntdll.NtQueryInformationProcess(
        handle, 26, ctypes.byref(value), ctypes.sizeof(value), ctypes.byref(retlen))
    return value.value if status == 0 and value.value else None


def _cwd_from_peb32(handle, peb32: int) -> str | None:
    params = _u32(_read_memory(handle, peb32 + 0x10, 4), 0)
    if not params:
        return None
    curdir = _read_memory(handle, params + 0x24, 12)
    length, addr = _u16(curdir, 0), _u32(curdir, 4)
    if not length or not addr or length > 8192:
        return None
    raw = _read_memory(handle, addr, length)
    return raw.decode("utf-16-le", errors="replace") if raw else None


def process_cwd(pid: int) -> str | None:
    if os.name != "nt":
        return None
    open_process = ctypes.windll.kernel32.OpenProcess
    open_process.restype = ctypes.c_void_p
    handle = open_process(_PROCESS_QUERY_LIMITED | _PROCESS_VM_READ, False, pid)
    if not handle:
        return None
    try:
        info = _pbi(handle)
        if not info:
            return None
        cwd = _cwd_from_peb(handle, info[0])
        if cwd is None:
            peb32 = _peb32(handle)
            if peb32:
                cwd = _cwd_from_peb32(handle, peb32)
        return cwd
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def _own_chain() -> set[int]:
    """自身与祖先 pid：本脚本运行时不占「车道内 cwd」名额。"""
    chain = {os.getpid()}
    open_process = ctypes.windll.kernel32.OpenProcess if os.name == "nt" else None
    if not open_process:
        return chain
    open_process.restype = ctypes.c_void_p
    current = os.getpid()
    for _ in range(16):
        handle = open_process(_PROCESS_QUERY_LIMITED, False, current)
        if not handle:
            break
        try:
            info = _pbi(handle)
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
        if not info or not info[1] or info[1] in chain:
            break
        chain.add(int(info[1]))
        current = int(info[1])
    return chain


def enumerate_cwds() -> list[dict]:
    """受关注进程（python/git/Devin/Cursor 等）的 cwd；读不到 cwd 的记 unreadable。"""
    if os.name != "nt":
        return []
    self_pids = _own_chain()
    result = []
    for pid, name in _process_names():
        low = name.lower()
        if pid in self_pids or not any(k in low for k in INTERESTING_NAMES):
            continue
        cwd = process_cwd(pid)
        result.append({"pid": pid, "name": name,
                       "cwd": cwd, "unreadable": cwd is None})
    return result


def _inside(path: str, root) -> bool:
    try:
        root_norm = os.path.normcase(os.path.abspath(root))
        return os.path.commonpath([
            os.path.normcase(os.path.abspath(path)), root_norm]) == root_norm
    except (OSError, ValueError):
        return False


def occupy_report(source, cwds) -> tuple[list[dict], list[dict]]:
    """(cwd 在源目录内的进程, 读不到 cwd 的受关注进程)。"""
    entries = cwds()
    inside = [e for e in entries if e.get("cwd") and _inside(e["cwd"], source)]
    unreadable = [e for e in entries if e.get("unreadable")]
    return inside, unreadable


def _probes(overrides) -> dict:
    base = {"disk_free": disk_free_bytes, "dispatch": dispatch_state,
            "cwds": enumerate_cwds}
    if overrides:
        base.update({k: v for k, v in overrides.items() if v is not None})
    return base


def preflight(source, target, probes, i_know_lanes_idle, out) -> list[str]:
    """逐条打印预检；返回阻断理由清单（空＝可 --apply）。"""
    problems = []
    state, detail = probes["dispatch"](source)
    out("预检·派工状态：%s（%s）" % (state, detail))
    if state == "busy":
        problems.append("队列里有在派项")
    elif state == "unknown" and not i_know_lanes_idle:
        problems.append("派工状态读不到，需 --i-know-lanes-idle 确认车道空闲")

    inside, unreadable = occupy_report(source, probes["cwds"])
    for entry in inside:
        out("预检·占用：PID %s %s cwd=%s" % (entry["pid"], entry["name"], entry["cwd"]))
    if inside:
        problems.append("%d 个进程 cwd 在源目录内" % len(inside))
    if unreadable:
        out("预检·占用：%d 个受关注进程 cwd 读不到（%s）" % (
            len(unreadable), "、".join(str(e["pid"]) for e in unreadable[:8])))
        if not i_know_lanes_idle:
            problems.append("占用检测不完整，需 --i-know-lanes-idle 确认车道空闲")

    files, dirs, size, junctions = tree_stats(source)
    if junctions:
        problems.append("源目录内含 %d 个 junction/链接，超出本脚本处理范围" % junctions)
    free = probes["disk_free"](target)
    need = size * FREE_MULTIPLIER
    out("预检·余量：目标盘可用 %.1f GB，需要 ≥ %.1f GB（2×源 %.1f GB）" % (
        free / 2**30, need / 2**30, size / 2**30))
    if free < need:
        problems.append("目标盘余量不足 2 倍")
    if target.exists() and any(target.iterdir()):
        problems.append("目标目录已存在且非空")
    if source.is_junction():
        problems.append("源目录已是 junction（已迁移过），请用 --rollback 还原")
    return problems


def robocopy_move(source, target, out) -> bool:
    done = subprocess.run(
        ["robocopy", str(source), str(target), "/E", "/MOVE", "/COPY:DAT",
         "/R:1", "/W:1", "/XJ", "/NP"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = "\n".join((done.stdout or "").splitlines()[-6:])
    if tail:
        out(tail)
    if done.returncode >= ROBOCOPY_FAILURE:
        out("robocopy 失败，退出码 %d" % done.returncode)
        return False
    return True


def make_junction(link, target) -> bool:
    done = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return done.returncode == 0 and os.path.isjunction(str(link))


def drop_junction(link) -> bool:
    """删除 junction 本身（rmdir 只摘链接，不删目标内容）。"""
    try:
        os.rmdir(str(link))
        return True
    except OSError:
        return False


def _restore_from_failure(source, target, out, stage: str) -> int:
    out("失败点：%s；开始回搬" % stage)
    if os.path.isjunction(str(source)) and not drop_junction(source):
        out("警告：junction 删除失败，请手工处理 %s" % source)
    if target.exists():
        if source.exists() and not os.path.isjunction(str(source)):
            out("警告：源目录仍存在真实内容，放弃回搬以免覆盖：%s" % source)
        elif not robocopy_move(target, source, out):
            out("警告：回搬失败，数据仍在 %s，请手工搬回" % target)
    return 3


def apply(source, target, *, i_know_lanes_idle=False, probes=None, out=print) -> int:
    source, target = Path(source), Path(target)
    probes = _probes(probes)
    if not source.is_dir() or source.is_junction():
        out("拒绝 --apply：源目录不存在或已是 junction：%s" % source)
        return 2
    problems = preflight(source, target, probes, i_know_lanes_idle, out)
    if problems:
        for item in problems:
            out("拒绝 --apply：" + item)
        return 2

    files, dirs, size, _ = tree_stats(source)
    try:
        statuses = porcelain_map(source)
        entries = worktree_entries(source)
    except (OSError, subprocess.SubprocessError) as exc:
        out("拒绝 --apply：搬前 git 快照失败：%s" % exc)
        return 2
    out("搬前快照：%d 文件 %d 目录 %d 字节；git 车道 %d 条，worktree %d 条" % (
        files, dirs, size, len(statuses), len(entries)))

    if not robocopy_move(source, target, out):
        return _restore_from_failure(source, target, out, "robocopy /MOVE")
    try:
        after = tree_stats(target)
    except OSError as exc:
        return _restore_from_failure(source, target, out,
                                     "搬后目录统计失败：%s" % exc)
    if after[:3] != (files, dirs, size):
        return _restore_from_failure(source, target, out,
                                     "搬后校验 文件/目录/字节 %s != 搬前 %s" % (after[:3], (files, dirs, size)))

    if not make_junction(source, target):
        return _restore_from_failure(source, target, out, "mklink /J")
    out("junction 已建：%s → %s" % (source, target))

    try:
        after_statuses = porcelain_map(source)
        after_entries = worktree_entries(source)
    except (OSError, subprocess.SubprocessError) as exc:
        return _restore_from_failure(source, target, out,
                                     "搬后 git 校验异常：%s" % exc)
    if after_statuses != statuses:
        return _restore_from_failure(source, target, out, "git status 快照比对")
    if after_entries != entries:
        return _restore_from_failure(source, target, out, "git worktree list 比对")
    out("--apply 完成：%d 条车道已在 %s，原位经 junction 访问" % (len(lanes_of(source)), target))
    return 0


def rollback(source, target, *, probes=None, out=print) -> int:
    source, target = Path(source), Path(target)
    probes = _probes(probes)
    if source.is_junction():
        pass  # 摘 junction 后 robocopy 回搬
    elif source.exists() or not target.exists():
        out("拒绝 --rollback：%s 不是 junction，且 %s 不是待回搬目录" % (source, target))
        return 2
    try:
        files, dirs, size, junctions = tree_stats(target)
    except OSError as exc:
        out("拒绝 --rollback：目标目录统计失败：%s" % exc)
        return 2
    if junctions:
        out("拒绝 --rollback：目标内含 %d 个 junction/链接" % junctions)
        return 2
    statuses = {}
    try:
        for lane in lanes_of(target):
            if (lane / ".git").exists():
                done = git("-C", str(lane), "status", "--porcelain")
                done.check_returncode()
                statuses[lane.name] = done.stdout
    except (OSError, subprocess.SubprocessError) as exc:
        out("拒绝 --rollback：搬前 git 状态读取失败：%s" % exc)
        return 2
    out("回搬前快照：%d 文件 %d 目录 %d 字节" % (files, dirs, size))
    if source.is_junction() and not drop_junction(source):
        out("拒绝 --rollback：junction 删除失败 %s" % source)
        return 2
    if not robocopy_move(target, source, out):
        out("警告：回搬失败，数据仍在 %s，junction 未恢复" % target)
        return 3
    try:
        stats_match = tree_stats(source)[:3] == (files, dirs, size)
    except OSError:
        stats_match = False
    if not stats_match:
        out("警告：回搬后校验不一致，请人工核对 %s 与 %s" % (source, target))
        return 3
    try:
        restored = porcelain_map(source)
    except (OSError, subprocess.SubprocessError) as exc:
        out("警告：回搬后 git status 读取失败（%s），请人工核对" % exc)
        return 3
    if restored != statuses:
        out("警告：回搬后 git status 快照不一致，请人工核对")
        return 3
    out("--rollback 完成：%s 已恢复为普通目录" % source)
    return 0


def plan(source, target, *, probes=None, out=print) -> int:
    source, target = Path(source), Path(target)
    probes = _probes(probes)
    if not source.exists() and not source.is_junction():
        out("源目录不存在：%s" % source)
        return 2
    out("源目录：%s" % source)
    out("目标目录：%s" % target)
    if source.is_junction():
        out("状态：已迁移（junction → %s）" % os.path.realpath(str(source)))
    else:
        out("状态：未迁移（普通目录）")
    files, dirs, size, junctions = tree_stats(source)
    out("目录大小：%d 文件 / %d 目录 / %d 字节（%.2f GB）；内含 junction %d 个" % (
        files, dirs, size, size / 2**30, junctions))
    free = probes["disk_free"](target)
    out("目标盘余量：%.1f GB；需要 ≥ %.1f GB（2×源）" % (free / 2**30, size * 2 / 2**30))
    inside, unreadable = occupy_report(source, probes["cwds"])
    if inside:
        out("占用进程（cwd 在源目录内）：")
        for entry in inside:
            out("  PID %s %s cwd=%s" % (entry["pid"], entry["name"], entry["cwd"]))
    else:
        out("占用进程：未检出 cwd 在源目录内的 python/git/Devin/Cursor 进程")
    if unreadable:
        out("未能检测：%d 个受关注进程 cwd 读不到（PID %s）" % (
            len(unreadable), "、".join(str(e["pid"]) for e in unreadable[:8])))
    state, detail = probes["dispatch"](source)
    out("派工状态：%s（%s）" % (state, detail))
    out("git worktree prune 预演：%s" % prune_preview(source))
    names = [p.name for p in lanes_of(source)]
    out("将搬车道：%d 条%s" % (len(names), "：" + "、".join(names[:10]) if names else ""))
    out("show-toplevel 实测：" + toplevel_probe(source))
    return 0


def main(argv=None, *, probes=None, out=print) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="只预演（默认）")
    mode.add_argument("--apply", action="store_true", help="前置全过才执行搬迁")
    mode.add_argument("--rollback", action="store_true", help="删 junction 并搬回原位")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--i-know-lanes-idle", action="store_true",
                        help="派工/占用读不到时确认全部车道空闲")
    args = parser.parse_args(argv)
    if args.rollback:
        return rollback(args.source, args.target, probes=probes, out=out)
    if args.apply:
        return apply(args.source, args.target,
                     i_know_lanes_idle=args.i_know_lanes_idle,
                     probes=probes, out=out)
    return plan(args.source, args.target, probes=probes, out=out)


if __name__ == "__main__":
    raise SystemExit(main())
