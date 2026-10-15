"""后台自动补跑安全全量：在干净的分离工作树（根目录 ``.wt/ci``）上跑，不占用也不依赖用户正在编辑的工作树。

用法（随附解释器，``-I`` 也可）：

* ``--status``  只打印欠账状态，不跑任何东西。
* ``--notice``  上次后台全量未通过时打印一句话；post-commit 钩子每次提交先跑它，红了会在提交输出里看到。
* ``--spawn``   由 git post-commit 钩子调用：master 上欠账达到触发点（门禁线提前 2 个源码轮次）
  且没有同类任务在跑时，起一个脱离终端的后台进程；否则静默退出。钩子绝不阻塞提交。
* ``--run``     前台执行：把 ``.wt/ci`` 对齐到当前 HEAD，跑 ``run_selftests.py --all --safe``。
  绿了凭据由执行器写进 git common-dir 的 ``full-safe-receipts.json``，门禁凭内容树放行。

欠账规则与阈值唯一权威是 ``run_selftests``（``FULL_SAFE_ROUND_INTERVAL`` 等），本脚本不另立数字。
日志写 ``程序/logs/auto_full_safe.log``（UTF-8，被 gitignore）。
"""
from __future__ import annotations

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
import file_cache  # noqa: E402
import run_selftests  # noqa: E402

LOG = PROGRAM / "logs" / "auto_full_safe.log"
LOCK_NAME = "auto-full-safe.lock"
STALE_SECONDS = 3 * 3600       # 全量最长按小时计；超过即视为崩溃遗留的锁


def _git(*args, cwd=None):
    out = subprocess.check_output(["git", *args], cwd=cwd or PROGRAM, stderr=subprocess.DEVNULL)
    return out.decode("utf-8", "replace").strip()


def repo_root() -> Path:
    return Path(_git("rev-parse", "--show-toplevel"))


def status() -> dict:
    document = run_selftests.load_layer_document()
    last_full = int(document.get("last_full_safe_all_round", 0))
    latest = run_selftests.latest_completed_round()
    counted = run_selftests.source_rounds_since(last_full, latest)
    master = run_selftests.is_master_checkout()
    return {
        "last_full": last_full, "latest": latest, "master": master,
        "source_rounds": counted,
        "gate_at": run_selftests.FULL_SAFE_ROUND_INTERVAL,
        "auto_due": run_selftests.full_safe_auto_due(latest, last_full, master),
    }


RESULT_NAME = "auto-full-safe-result.json"


def _result_path() -> Path:
    return Path(run_selftests.git_common_dir() or PROGRAM) / RESULT_NAME


def red_modules(log_text: str) -> list[str]:
    """从全量日志里取出有红的测试文件名（``### 名称（N 条红）`` 行），去重保序。"""
    found = []
    for match in re.finditer(r"^### (\S+?)（\d+ 条红）", log_text, re.M):
        if match.group(1) not in found:
            found.append(match.group(1))
    return found


def write_result(head: str, returncode: int, seconds: float) -> None:
    try:
        text = LOG.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    payload = {"head": head, "returncode": returncode, "seconds": round(seconds),
               "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "red": red_modules(text), "log": str(LOG)}
    _result_path().write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def last_result() -> dict:
    try:
        value = file_cache.read_json(_result_path())
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def failure_notice() -> str:
    """上次后台全量没通过时的一句话提示；通过、没跑过或读不出来都返回空串。"""
    result = last_result()
    if not result or result.get("returncode") == 0:
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


def spawn() -> int:
    info = status()
    if not info["auto_due"] or _already_running():
        return 0
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008 | 0x08000000   # DETACHED | NO_WINDOW
    # 钩子运行时 git 会导出 GIT_INDEX_FILE／GIT_DIR 等变量，指向正在提交的那份索引；
    # 子进程若继承，它对 .wt/ci 的 checkout 会作用到错误的索引上并静默失败。
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()), "--run"],
                     cwd=PROGRAM, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, creationflags=flags, close_fds=True)
    return 0


def _sync_clean_worktree(root: Path, head: str) -> Path:
    """让 ``.wt/ci`` 成为 HEAD 的干净分离检出；已存在就强制对齐，不存在就新建。"""
    target = root / ".wt" / "ci"
    if (target / ".git").exists():
        _git("checkout", "-f", "--detach", head, cwd=target)
        _git("clean", "-fdq", cwd=target)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        _git("worktree", "add", "--detach", "-f", str(target), head, cwd=root)
    _fill_embedded_repos(root, target)
    return target / PROGRAM.name


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
    program = _sync_clean_worktree(root, head)
    # 主干检出才能产凭据；本检出是分离的，用这个变量告诉执行器「此 HEAD 取自 master」。
    env = dict(os.environ, DRAMA_SUPPRESS_MODAL="1", PYTHONIOENCODING="utf-8", AUTO_FULL_SAFE_HEAD=head,
               GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="safe.directory", GIT_CONFIG_VALUE_0="*")
    with LOG.open("w", encoding="utf-8") as log:
        log.write("[自动全量] 开始 %s HEAD=%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), head[:10]))
        log.flush()
        started = time.perf_counter()
        result = subprocess.run([sys.executable, "-B", "run_selftests.py", "--all", "--safe"],
                                cwd=program, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
        elapsed = time.perf_counter() - started
        log.write("\n[自动全量] 退出码 %d，用时 %.0f 秒（0＝绿且凭据已写入）\n"
                  % (result.returncode, elapsed))
    write_result(head, result.returncode, elapsed)
    return result.returncode


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--run" in args:
        return run()
    if "--notice" in args:
        try:
            text = failure_notice()
            if text:
                print(text)
        except Exception:      # 提示是附加信息，任何异常都不能影响提交
            pass
        return 0
    if "--spawn" in args:
        try:
            return spawn()
        except Exception:      # 钩子里任何异常都不能影响提交
            return 0
    info = status()
    print("上次全量 R%(last_full)d；最新 R%(latest)d；其间改过源码的轮次 %(source_rounds)s"
          "（门禁线 %(gate_at)d）；主干 %(master)s；后台触发 %(auto_due)s" % info)
    print(failure_notice() or "上次后台全量：通过或尚未运行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
