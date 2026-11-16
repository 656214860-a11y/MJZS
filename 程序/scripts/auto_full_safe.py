"""后台自动补跑安全全量：在干净的分离工作树（根目录 ``.wt/ci``）上跑，不占用也不依赖用户正在编辑的工作树。

用法（随附解释器，``-I`` 也可）：

* ``--status``  只打印欠账状态，不跑任何东西。
* ``--notice``  上次后台全量未通过时打印一句话；post-commit 钩子每次提交先跑它，红了会在提交输出里看到。
* ``--wait-run`` 防抖等待者：等「安静」15 分钟（期间有新提交就重新计时）再跑一次；欠账已让门禁报红或等满 60 分钟则立即跑。
* ``--spawn``   由 git post-commit 钩子调用：master 上欠账达到触发点（门禁线提前 2 个源码轮次）
  且没有同类任务在跑时，起一个脱离终端的后台等待者（``--wait-run``，同一时刻只有一个）；否则静默退出。钩子绝不阻塞提交。
* ``--run``     前台执行：把 ``.wt/ci`` 对齐到当前 HEAD，跑 ``run_selftests.py --all --safe``。
  绿了凭据由执行器写进 git common-dir 的 ``full-safe-receipts.json``，门禁凭内容树放行。

欠账规则与阈值唯一权威是 ``run_selftests``（``FULL_SAFE_ROUND_INTERVAL`` 等），本脚本不另立数字。
日志写 ``程序/logs/auto_full_safe.log``（UTF-8，被 gitignore）。
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))
import app_logging  # noqa: E402
import file_cache  # noqa: E402
import run_selftests  # noqa: E402

LOG = PROGRAM / "logs" / "auto_full_safe.log"
LOCK_NAME = "auto-full-safe.lock"
# 防抖：连续提交期间（如 desktop.py 分步拆分系列）不逐轮补跑，等「安静」一段时间再跑一次；
# 但门禁已经会报红（欠账成立）时立即跑，不再等。
QUIET_SECONDS = 15 * 60
MAX_WAIT_SECONDS = 60 * 60
POLL_SECONDS = 60
WAITER_LOCK_NAME = "auto-full-waiter.lock"
STALE_SECONDS = 3 * 3600       # 全量最长按小时计；超过即视为崩溃遗留的锁
# 红后冷却：上次后台全量是真红（非「环境不允许」）时，同一 HEAD 不再重跑（内容没变，结果必同）；
# 换了 HEAD 也要等这么久才自动补跑，给修复留时间。门禁已因欠账报红（required）时才越过冷却。
RED_COOLDOWN_SECONDS = 4 * 3600
# 「环境不允许派生工作进程」的可靠特征：沙箱会话里提交时，钩子继承了同一限制，
# 全量会在 78 秒左右崩在进程池上。这类失败不是测试红，不能记成「未通过」。
BLOCKED_MARKERS = ('BrokenProcessPool', 'process pool is not usable',
                   'A child process terminated abruptly', 'Access is denied')
BLOCKED_CODE = -1


def _git(*args, cwd=None):
    out = subprocess.check_output(["git", *args], cwd=cwd or PROGRAM, stderr=subprocess.DEVNULL)
    return out.decode("utf-8", "replace").strip()


def repo_root() -> Path:
    return Path(_git("rev-parse", "--show-toplevel"))


def red_cooldown(result: dict, head: str, now: float) -> str:
    """红后冷却（纯函数）：返回 ``'head'``（同 HEAD 已红）、``'time'``（冷却期内）或空串（不冷却）。

    只认真红：通过（0）、环境受阻（BLOCKED_CODE）、没跑过都不冷却。"""
    code = result.get("returncode")
    if not result or code in (0, BLOCKED_CODE) or not isinstance(code, int):
        return ""
    if head and result.get("head") == head:
        return "head"
    try:
        finished = time.mktime(time.strptime(str(result.get("finished_at", "")), "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, OverflowError):
        return ""
    return "time" if 0 <= now - finished < RED_COOLDOWN_SECONDS else ""


def current_cooling() -> str:
    """门禁视角的红后冷却：对当前 HEAD 取 ``red_cooldown`` 的原始判定（'head'／'time'／''）。

    ``status()`` 会在 required 时把 'time' 抹掉，那是给补跑决策用的；合并门禁要看未加工的冷却，
    因为「同 HEAD 已红」是唯一无法靠等时间消除、必须靠新提交推进 HEAD 才能解锁的状态。"""
    try:
        head = _git("rev-parse", "HEAD")
    except (OSError, subprocess.SubprocessError):
        head = ""
    return red_cooldown(last_result(), head, time.time())


def status() -> dict:
    document = run_selftests.load_layer_document()
    last_full = int(document.get("last_full_safe_all_round", 0))
    latest = run_selftests.latest_completed_round()
    counted = run_selftests.source_rounds_since(last_full, latest)
    master = run_selftests.is_master_checkout()
    required = run_selftests.full_safe_required(
        latest, last_full, master, counted, run_selftests.risk_overdue_since(last_full, latest))
    try:
        head = _git("rev-parse", "HEAD")
    except (OSError, subprocess.SubprocessError):
        head = ""
    cooling = red_cooldown(last_result(), head, time.time())
    if required and cooling == "time":
        cooling = ""
    return {
        "last_full": last_full, "latest": latest, "master": master,
        "source_rounds": counted,
        "gate_at": run_selftests.FULL_SAFE_ROUND_INTERVAL,
        "cooling": cooling,
        "auto_due": not cooling and run_selftests.full_safe_auto_due(latest, last_full, master),
        "required": required,
    }


RESULT_NAME = "auto-full-safe-result.json"


def _result_path() -> Path:
    return Path(run_selftests.git_common_dir() or PROGRAM) / RESULT_NAME


HISTORY_NAME = "full-safe-history.jsonl"


def _history_path() -> Path:
    return Path(run_selftests.git_common_dir() or PROGRAM) / HISTORY_NAME


def append_history(head: str, returncode: int, seconds: float, red: list[str], blocked: str = '') -> None:
    """每次真实的全量结果追加一行（红灯起止时间的原始数据）；环境受阻不算，写失败不影响主流程。"""
    if blocked:
        return
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "head": head, "ok": returncode == 0,
           "seconds": round(seconds), "failed_files": red}
    try:
        with _history_path().open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def red_modules(log_text: str) -> list[str]:
    """从全量日志里取出有红的测试文件名（``### 名称（N 条红）`` 行），去重保序。"""
    found = []
    for match in re.finditer(r"^### (\S+?)（\d+ 条红）", log_text, re.M):
        if match.group(1) not in found:
            found.append(match.group(1))
    return found


def write_result(head: str, returncode: int, seconds: float, blocked: str = '') -> None:
    try:
        text = LOG.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    payload = {"head": head, "returncode": returncode, "seconds": round(seconds),
               "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "red": red_modules(text), "log": str(LOG)}
    if blocked:
        payload["blocked"] = str(blocked)
    _result_path().write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    append_history(head, returncode, seconds, payload["red"], blocked)


def last_result() -> dict:
    try:
        value = file_cache.read_json(_result_path())
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def blocked_reason(text: str) -> str:
    """从日志判断这是「环境不允许派生工作进程」而不是测试失败（纯函数）。"""
    haystack = str(text or "")
    for marker in BLOCKED_MARKERS:
        if marker in haystack:
            return marker
    return ""


def spawn_problem(run=None) -> str:
    """能不能派生工作进程：不能就返回原因，空串表示可用。

    沙箱会话里提交时钩子继承了同一限制，全量必然崩在进程池上；与其跑 78 秒再假装「未通过」，
    不如先花零点几秒问一句。`run` 是自检注入点。
    """
    probe = run or _probe_pool
    try:
        return str(probe() or '')
    except Exception as exc:            # 探测本身崩了也算不可用，但绝不让它冒泡
        return '%s：%s' % (type(exc).__name__, exc)


def _probe_pool():
    with concurrent.futures.ProcessPoolExecutor(max_workers=1) as pool:
        if pool.submit(int, '1').result(timeout=30) != 1:
            return '进程池返回值异常'
    return ''


def failure_notice() -> str:
    """上次后台全量没通过时的一句话提示；通过、没跑过或读不出来都返回空串。"""
    result = last_result()
    if not result:
        return ""
    blocked = str(result.get("blocked") or "")
    if not blocked and result.get("returncode") != 0:
        try:
            blocked = blocked_reason(LOG.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            blocked = ""
    if blocked:
        return ("[自动全量] 上次未能测量：环境不允许派生工作进程（多见于沙箱会话里提交，钩子继承同一限制），"
                "不是测试失败。请在非沙箱会话手动跑 `run_selftests.py --all --safe`；原因：%s" % blocked[:160])
    if result.get("returncode") == 0:
        return ""
    red = "、".join(result.get("red") or []) or "见日志"
    return ("[自动全量] 上次后台全量未通过（HEAD %s，%s，退出码 %s）：%s；日志 %s"
            % (str(result.get("head", ""))[:7], result.get("finished_at", ""),
               result.get("returncode"), red, result.get("log", LOG)))


def _lock_path() -> Path:
    return Path(run_selftests.git_common_dir() or PROGRAM) / LOCK_NAME


def _already_running() -> bool:
    lock = _lock_path()
    try:
        age = time.time() - lock.stat().st_mtime
        pid = int(lock.read_text(encoding="utf-8").strip() or 0)
    except (OSError, ValueError):
        return False
    return age < STALE_SECONDS and bool(pid) and run_selftests._pid_is_alive(pid)


def decide(info: dict, commit_age: float, waited: float) -> str:
    """防抖决策（纯函数）：stop＝已不需要补跑；run＝现在跑；wait＝继续等安静期。"""
    if not info.get("auto_due"):
        return "stop"
    if info.get("required") or commit_age >= QUIET_SECONDS or waited >= MAX_WAIT_SECONDS:
        return "run"
    return "wait"


def _waiter_lock_path() -> Path:
    return Path(run_selftests.git_common_dir() or PROGRAM) / WAITER_LOCK_NAME


def _waiter_running() -> bool:
    lock = _waiter_lock_path()
    try:
        age = time.time() - lock.stat().st_mtime
        pid = int(lock.read_text(encoding="utf-8").strip() or 0)
    except (OSError, ValueError):
        return False
    return age < MAX_WAIT_SECONDS + 600 and bool(pid) and run_selftests._pid_is_alive(pid)


def _last_commit_age() -> float:
    return time.time() - int(_git("log", "-1", "--format=%ct"))


def wait_run(sleep=time.sleep, clock=time.monotonic) -> int:
    """等安静期再跑一次后台全量：期间每次有新提交都会让安静期重新计时，只会有这一个等待者。"""
    if _waiter_running():
        return 0
    lock = _waiter_lock_path()
    lock.write_text(str(os.getpid()), encoding="utf-8")
    started = clock()
    try:
        while True:
            verdict = decide(status(), _last_commit_age(), clock() - started)
            if verdict == "stop":
                return 0
            if verdict == "run":
                break
            sleep(POLL_SECONDS)
    finally:
        try:
            lock.unlink()
        except OSError:
            pass
    return run()


def spawn() -> int:
    info = status()
    if not info["auto_due"] or _already_running() or _waiter_running():
        return 0
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008 | 0x08000000   # DETACHED | NO_WINDOW
    # 钩子运行时 git 会导出 GIT_INDEX_FILE／GIT_DIR 等变量，指向正在提交的那份索引；
    # 子进程若继承，它对 .wt/ci 的 checkout 会作用到错误的索引上并静默失败。
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()), "--wait-run"],
                     cwd=PROGRAM, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, creationflags=flags, close_fds=True)
    return 0


def _remove_worktree(root: Path, target: Path) -> None:
    """删掉半成品检出：锁着要先解锁，最后 prune 一次，失败一律不抛（下一句 add 才是判据）。"""
    for args in (("worktree", "unlock", str(target)),
                 ("worktree", "remove", "--force", str(target)),
                 ("worktree", "prune")):
        try:
            _git(*args, cwd=root)
        except (OSError, subprocess.SubprocessError):
            pass
    shutil.rmtree(target, ignore_errors=True)


def _lock_worktree(target: Path) -> None:
    """锁住 ``.wt/ci``：仓库卫生只回收「已并净且干净」的 ``.wt`` 工作树，不锁的话
    应用退出后它随时可能被删，后台全量随即以「找不到 run_selftests.py」假红收场。"""
    try:
        _git("worktree", "lock", "--reason", "auto full safe", str(target))
    except (OSError, subprocess.SubprocessError):
        pass        # 已锁或旧版 git 不认 --reason，都不影响本轮运行


def _sync_clean_worktree(root: Path, head: str) -> Path:
    """让 ``.wt/ci`` 成为 HEAD 的干净分离检出；已存在就强制对齐，坏掉就重建。"""
    target = root / ".wt" / "ci"
    script = target / PROGRAM.name / "run_selftests.py"
    if (target / ".git").exists() and script.is_file():
        _git("checkout", "-f", "--detach", head, cwd=target)
        _git("clean", "-fdq", cwd=target)
    else:
        # 半成品（上次被清掉／中途中断）不能直接对齐：没有脚本的检出跑起来只会再假红一次。
        _remove_worktree(root, target)
        target.parent.mkdir(parents=True, exist_ok=True)
        _git("worktree", "add", "--detach", "-f", str(target), head, cwd=root)
    _fill_embedded_repos(root, target)
    _fill_ignored_inputs(root, target)
    _lock_worktree(target)
    if not (target / PROGRAM.name / "run_selftests.py").is_file():
        raise RuntimeError("干净检出缺少 程序/run_selftests.py：%s" % target)
    return target / PROGRAM.name


# 测试要读、却被 .gitignore 排除的本地输入：干净检出里天然没有，只能从主工作树补。
# R1693 实测：`test_agents_md` 要核对 基准历史.json 是否被声明为「仅历史」，缺了就是 1 条红。
IGNORED_INPUTS = ("维护记录/基准历史.json",)


def _fill_ignored_inputs(root: Path, target: Path) -> None:
    """把显式清单里的被忽略输入补进检出；不整体拷 维护记录/，避免把日志与私有数据带进去。"""
    for relative in IGNORED_INPUTS:
        source = root / PROGRAM.name / relative
        destination = target / PROGRAM.name / relative
        if not source.is_file() or destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _fill_embedded_repos(root: Path, target: Path) -> None:
    """本仓库把 SKILL 包等嵌套仓库登记为 gitlink（无 .gitmodules），干净检出里只是空目录。

    测试需要它们的正文，所以从主工作树逐个连 .git 一起拷过去（体量十几 MB；带 .git 才不会让检出显示为脏）；目标目录已有内容时只把它对齐到外层登记的提交（外层指针升级后不能留旧版）。"""
    listing = _git("-c", "core.quotepath=false", "ls-files", "-s", cwd=root)
    for line in listing.splitlines():
        meta, _, path = line.partition(chr(9))
        if not meta.startswith("160000"):
            continue
        source, destination = root / path, target / path
        if not source.is_dir():
            continue
        if destination.is_dir() and any(destination.iterdir()):
            _align_embedded_repo(destination, source, meta.split()[1])
        else:
            shutil.copytree(source, destination, dirs_exist_ok=True)


def _align_embedded_repo(destination: Path, source: Path, sha: str) -> None:
    """已拷过的嵌套仓库要和外层登记的提交一致：外层指针升级后，旧副本会让检出显示为脏而拒绝产凭据。"""
    try:
        if _git("rev-parse", "HEAD", cwd=destination) == sha:
            return
    except (OSError, subprocess.SubprocessError):
        pass
    _git("fetch", "--quiet", str(source), cwd=destination)
    _git("checkout", "-f", "--detach", sha, cwd=destination)


def run() -> int:
    lock = _lock_path()
    if _already_running():
        print("[自动全量] 已有任务在跑，退出")
        return 0
    lock.write_text(str(os.getpid()), encoding="utf-8")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        return _run_locked()
    except Exception:
        import traceback
        LOG.write_text("[自动全量] 启动失败\n" + traceback.format_exc(), encoding="utf-8")
        return 1
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


def _run_locked() -> int:
    root = repo_root()
    head = _git("rev-parse", "HEAD")
    # 先问一句能不能派生工作进程：不能就别建工作树、别跑 78 秒、更别记成「测试未通过」。
    blocked = spawn_problem()
    if blocked:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.write_text("[自动全量] 环境不允许派生工作进程，本轮未测（未建工作树、未写凭据）\n%s\n"
                       % blocked, encoding="utf-8")
        write_result(head, BLOCKED_CODE, 0.0, blocked=blocked)
        return 0
    program = _sync_clean_worktree(root, head)
    # 主干检出才能产凭据；本检出是分离的，用这个变量告诉执行器「此 HEAD 取自 master」。
    env = dict(os.environ, DRAMA_SUPPRESS_MODAL="1", DRAMA_SUPPRESS_NETWORK="1", PYTHONIOENCODING="utf-8", AUTO_FULL_SAFE_HEAD=head,
               GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="safe.directory", GIT_CONFIG_VALUE_0="*")
    with LOG.open("w", encoding="utf-8") as log:
        log.write("[自动全量] 开始 %s HEAD=%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), head[:10]))
        log.flush()
        started = time.perf_counter()
        # 本进程是 DETACHED 起的、没有控制台；子进程 python.exe 会自己新开一个可见控制台窗口，
        # 任务栏上多出一个 Python 图标（看着像助手图标变了）。
        quiet = {"creationflags": 0x08000000} if os.name == "nt" else {}   # CREATE_NO_WINDOW
        cmd = [sys.executable, "-B", "run_selftests.py", "--all", "--safe"]
        hidden = PROGRAM.parent / "工作流任务" / "gui_hidden.py"
        if hidden.is_file():
            # 全量会建大量 Tk 窗口；放进隐藏桌面跑，不弹到用户屏幕上抢焦点。
            run_log = LOG.with_name("auto_full_safe.run.log")
            log.write("[自动全量] 在隐藏桌面运行\n")
            log.flush()
            result = subprocess.run([sys.executable, "-B", str(hidden), str(run_log), str(program), "--", *cmd],
                                    env=env, stdout=log, stderr=subprocess.STDOUT, check=False, **quiet)
            if run_log.is_file():
                log.write(run_log.read_text(encoding="utf-8", errors="replace"))
        else:
            result = subprocess.run(cmd, cwd=program, env=env, stdout=log, stderr=subprocess.STDOUT, check=False, **quiet)
        elapsed = time.perf_counter() - started
        log.write("\n[自动全量] 退出码 %d，用时 %.0f 秒（0＝绿且凭据已写入）\n"
                  % (result.returncode, elapsed))
    write_result(head, result.returncode, elapsed)
    return result.returncode


def main(argv=None) -> int:
    # .git 是 gitfile 时，git 给钩子导出绝对 GIT_DIR 而不带 GIT_WORK_TREE；在程序目录里调 git 会把程序目录
    # 当成仓库顶层：前缀算空、源码轮次算 0，--spawn 永远判成「没到」而静默退出。本脚本只看自己所在的检出，
    # 入口先摘掉继承来的 GIT_*，返回时原样还原，进程内调用方不受影响。
    inherited = {key: os.environ.pop(key) for key in [key for key in os.environ if key.startswith("GIT_")]}
    try:
        return _dispatch(list(sys.argv[1:] if argv is None else argv))
    finally:
        os.environ.update(inherited)


def _dispatch(args: list) -> int:
    if "--wait-run" in args:
        return wait_run()
    if "--run" in args:
        return run()
    if "--notice" in args:
        try:
            text = failure_notice()
            if text:
                print(text)
        except Exception:      # 提示是附加信息，任何异常都不能影响提交
            app_logging.swallowed('--notice 附加提示')
        return 0
    if "--spawn" in args:
        try:
            return spawn()
        except Exception:      # 钩子里任何异常都不能影响提交
            return 0
    info = status()
    print("上次全量 R%(last_full)d；最新 R%(latest)d；其间改过源码的轮次 %(source_rounds)s"
          "（门禁线 %(gate_at)d）；主干 %(master)s；后台触发 %(auto_due)s"
          "；红后冷却 %(cooling)s" % dict(info, cooling=info.get("cooling") or "无"))
    print(failure_notice() or "上次后台全量：通过或尚未运行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
