"""为共享 Git 仓库的并行工作树分配轮次，并原子认领任务队列。"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _load_lock_lease():
    path = Path(__file__).resolve().parent / "lock_lease.py"
    loaded = sys.modules.get("lock_lease")
    if loaded is not None and Path(getattr(loaded, "__file__", "")).resolve() == path:
        return loaded
    spec = importlib.util.spec_from_file_location("lock_lease", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["lock_lease"] = module
    spec.loader.exec_module(module)
    return module


lock_lease = _load_lock_lease()


PROGRAM = Path(__file__).resolve().parents[2]
ROOT = PROGRAM.parent
RESULT_RE = re.compile(r"tasks_round_(\d+)_result\.md$")
COMMIT_ROUND_RE = re.compile(r"^R(\d+)(?:-FAIL)?:")
LOCK_NAME = "round-claim.lock"
COUNTER_NAME = "round-counter.json"
CLAIMS_NAME = "round-claims.json"
QUEUE_NAME = "maintenance-queue.json"
SNAPSHOT = Path("程序") / "维护记录" / "任务队列.json"


def git_common_dir(root: Path = ROOT) -> Path:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--git-common-dir"],
        text=True, encoding="utf-8", errors="replace", capture_output=True, check=True,
    )
    path = Path(result.stdout.strip())
    return path if path.is_absolute() else (root / path).resolve()


DEFAULT_QUEUE = git_common_dir() / QUEUE_NAME


def seed_queue(common_dir: Path, root: Path = ROOT) -> Path:
    """仅首次发布合并结果；硬链接的独占创建避免覆盖另一进程已发布的队列。"""
    target = common_dir / QUEUE_NAME
    if target.exists():
        return target
    result = subprocess.run(["git", "-C", str(root), "worktree", "list", "--porcelain", "-z"],
                            capture_output=True, check=True)
    roots = [Path(entry[9:].decode("utf-8")) for entry in result.stdout.split(b"\0")
             if entry.startswith(b"worktree ")]
    merged, metadata = {}, {}
    rank = {"pending": 0, "claimed": 1, "completed": 2}
    for tree in roots:
        snapshot = tree / SNAPSHOT
        if not snapshot.is_file():
            continue
        payload = _read_queue(snapshot)
        metadata.update({key: value for key, value in payload.items() if key != "items"})
        for item in payload["items"]:
            key = item["id"]
            prior = merged.get(key)
            if prior is None:
                merged[key] = dict(item)
                continue
            def priority(value):
                lease = _parse_time(value.get("lease_until"))
                return rank.get(value.get("status"), -1), lease.timestamp() if lease else float("-inf")
            winner = dict(max((prior, item), key=priority))
            notes = [str(value.get("note", "")) for value in (prior, item) if value.get("note")]
            winner["note"] = "；".join(notes)
            merged[key] = winner
    metadata["items"] = list(merged.values())
    common_dir.mkdir(parents=True, exist_ok=True)
    import tempfile
    descriptor, temporary = tempfile.mkstemp(prefix="queue-seed-", suffix=".tmp", dir=common_dir)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(metadata, handle, ensure_ascii=False)
            handle.write("\n")
        try:
            os.link(temporary, target)
        except FileExistsError:
            pass
    finally:
        os.unlink(temporary)
    return target


def _load_authority(common_dir: Path, queue_path: Path, root: Path) -> dict:
    if queue_path.resolve() == (common_dir / QUEUE_NAME).resolve():
        seed_queue(common_dir, root)
    return _read_queue(queue_path)


def _write_authority(common_dir: Path, queue_path: Path, payload: dict, root: Path) -> None:
    _atomic_json_write(queue_path, payload)
    if queue_path.resolve() == (common_dir / QUEUE_NAME).resolve():
        snapshot = root / SNAPSHOT
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        _atomic_json_write(snapshot, payload)


def validate_queue(payload: dict, now: datetime | None = None) -> tuple[list[str], list[str]]:
    now = now or datetime.now().astimezone()
    errors, warnings, seen = [], [], set()
    for item in payload["items"]:
        key = item.get("id")
        if not key or key in seen:
            errors.append("重复或缺失 id: %s" % key)
        seen.add(key)
        if item.get("status") != "claimed":
            continue
        owner = item.get("owner")
        if not isinstance(owner, str) or not owner.strip():
            errors.append("claimed 但 owner 为空: %s" % key)
        try:
            lease = _parse_time(item.get("lease_until"))
            minutes = float(item.get("lease_minutes", payload.get("lease_minutes", 60)))
            expected = now + timedelta(minutes=minutes)
            if not lease or minutes <= 0 or abs((lease - expected).total_seconds()) > 300:
                warnings.append("lease 不自洽: %s lease=%s expected=%s" % (key, lease, expected.isoformat()))
        except (ValueError, TypeError, OverflowError):
            warnings.append("lease 无效: %s" % key)
    return errors, warnings


def show_queue(payload: dict, now: datetime | None = None) -> None:
    now = now or datetime.now().astimezone()
    for item in payload["items"]:
        if item.get("status") not in ("pending", "claimed"):
            continue
        lease = _parse_time(item.get("lease_until"))
        status = item["status"]
        if status == "claimed" and (lease is None or lease <= now):
            status = "expired"
        print("%s %s owner=%s lease=%s" % (item["id"], status, item.get("owner", ""), item.get("lease_until", "")))


def latest_result_round(tasks_round: Path = PROGRAM / "tasks_round") -> int:
    values = [int(match.group(1)) for item in tasks_round.rglob("tasks_round_*_result.md")
              if (match := RESULT_RE.search(item.name))]
    return max(values, default=0)


def latest_git_round(root: Path = ROOT) -> int:
    """返回所有可见引用中已使用的最高 R<轮次> 提交号。"""
    result = subprocess.run(
        ["git", "-C", str(root), "log", "--all", "--format=%s"],
        text=True, encoding="utf-8", errors="replace", capture_output=True, check=True,
    )
    values = [int(match.group(1)) for line in result.stdout.splitlines()
              if (match := COMMIT_ROUND_RE.match(line))]
    return max(values, default=0)


def read_counter(counter: Path) -> int:
    try:
        value = json.loads(counter.read_text(encoding="utf-8"))
        return int(value.get("last_claimed", 0)) if isinstance(value, dict) else 0
    except (OSError, ValueError, TypeError):
        return 0


def _read_counter_doc(counter: Path) -> dict:
    try:
        value = json.loads(counter.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _counter_last(doc: dict) -> int:
    try:
        return int(doc.get("last_claimed") or 0)
    except (TypeError, ValueError):
        return 0


def _read_claims_doc(claims_path: Path) -> dict:
    """认领归属登记独立成文件：旧版 claim_next 只重写 round-counter.json，
    混合版本并行时登记不被他车道的旧代码抹掉。"""
    try:
        value = json.loads(claims_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    claims = value.get("claims") if isinstance(value, dict) else None
    return claims if isinstance(claims, dict) else {}


def _write_claims_doc(claims_path: Path, claims: dict) -> None:
    _atomic_json_write(claims_path, {"claims": claims})


def worktree_root(cwd: Path) -> str:
    """``cwd`` 所在工作树的顶层路径；与 commit-msg 钩子核对归属用同一条 git 命令。"""
    result = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        return str(Path(cwd).resolve())
    return result.stdout.strip()


def current_branch(cwd: Path) -> str:
    result = subprocess.run(["git", "-C", str(cwd), "symbolic-ref", "--quiet", "--short", "HEAD"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.stdout.strip() if result.returncode == 0 else ""


def _claim_owner(claimant_dir: Path) -> dict:
    return {"worktree": worktree_root(claimant_dir), "branch": current_branch(claimant_dir),
            "at": datetime.now().astimezone().isoformat(timespec="seconds")}


def _acquire_lock(common_dir: Path, timeout: float = 15.0) -> Path:
    """独占认领锁。心跳静默超过 3 分钟才回收；打不开进程不算死亡。"""
    lock = common_dir / LOCK_NAME
    deadline = time.monotonic() + timeout
    while True:
        try:
            descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if lock_lease.reclaim(lock):
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError("共享认领锁被占用：%s" % lock)
            time.sleep(0.05)
            continue
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(lock_lease.payload(os.getpid()), handle)
            handle.write("\n")
        lock_lease.arm(lock)
        return lock


@contextmanager
def shared_lock(common_dir: Path):
    common_dir.mkdir(parents=True, exist_ok=True)
    lock = _acquire_lock(common_dir)
    try:
        yield
    finally:
        lock_lease.release(lock)
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def _atomic_json_write(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".%s.tmp" % os.getpid())
    temporary.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def claim_next(*, common_dir: Path, tasks_round: Path, root: Path = ROOT,
               claimant_dir: Path | None = None) -> int:
    """在共享 git common-dir 下原子地领取下一个未使用轮次，并记录认领工作树归属。

    ``round-claims.json`` 让 commit-msg 校验「本轮次属于本工作树」而不是「本轮次是全局最新领号」，
    多车道并行时先领号的车道在测试与等待期间不再被后领号车道顶掉提交。"""
    with shared_lock(common_dir):
        counter = common_dir / COUNTER_NAME
        doc = _read_counter_doc(counter)
        claimed = _counter_last(doc)
        git_floor = latest_git_round(root)
        if claimed < git_floor:
            print("计数器已从 %s 追平到 %s" % (claimed, git_floor))
            claimed = git_floor
        next_round = max(claimed, latest_result_round(tasks_round)) + 1
        # 先写计数器再写归属：中途崩溃时新号仍是 last_claimed，旧规则兜底可提交。
        doc.pop("claims", None)  # 早期试装把 claims 写进计数器，迁出到独立文件
        doc["last_claimed"] = next_round
        _atomic_json_write(counter, doc)
        claims_path = common_dir / CLAIMS_NAME
        claims = _read_claims_doc(claims_path)
        claims[str(next_round)] = _claim_owner(Path(claimant_dir) if claimant_dir else Path(root))
        _write_claims_doc(claims_path, claims)
    try:
        import lane_registry
        lane_registry.register(Path(claimant_dir) if claimant_dir else Path(root),
                               common_dir, owner=str(claims[str(next_round)].get("worktree", "")))
    except Exception:
        pass  # 车道登记是观测面，绝不阻断领号
    return next_round


def record_claim(*, common_dir: Path, number: int, claimant_dir: Path) -> dict:
    """为已分配但缺归属记录的轮次补登当前工作树（升级前在途认领的迁移路径）。

    只允许登记 ``last_claimed`` 以内的号；已有他主记录时拒绝，避免抢占他人轮次。"""
    with shared_lock(common_dir):
        counter = common_dir / COUNTER_NAME
        doc = _read_counter_doc(counter)
        last = _counter_last(doc)
        if number < 1 or number > last:
            raise RuntimeError("轮次 R%d 尚未分配（last_claimed=%d），请先 next 领号" % (number, last))
        claims_path = common_dir / CLAIMS_NAME
        claims = _read_claims_doc(claims_path)
        existing = claims.get(str(number))
        owner = existing.get("worktree") if isinstance(existing, dict) else existing
        mine = worktree_root(Path(claimant_dir))
        same = owner and os.path.normcase(os.path.normpath(str(owner))) == \
            os.path.normcase(os.path.normpath(mine))
        # 登记路径已不存在（工作树被移动或删除）时视为失效记录，允许补登新位置。
        stranded = owner and not same and not os.path.isdir(str(owner))
        if owner and not same and not stranded:
            raise RuntimeError("轮次 R%d 已登记属于其他工作树：%s" % (number, owner))
        entry = _claim_owner(Path(claimant_dir))
        claims[str(number)] = entry
        _write_claims_doc(claims_path, claims)
        return dict(entry)


def require_branch(root: Path = ROOT) -> None:
    """领取轮次前验证调用位置；禁止把下一次提交继续留在游离 HEAD。"""
    result = subprocess.run(["git", "-C", str(root), "symbolic-ref", "--quiet", "HEAD"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        root = Path(subprocess.check_output(["git", "-C", str(root), "rev-parse", "--show-toplevel"]).decode("utf-8").strip())
        common = git_common_dir(root)
        number = max(read_counter(common / COUNTER_NAME),
                     latest_result_round(root / "程序" / "tasks_round")) + 1
        raise RuntimeError("拒绝领取轮次：detached HEAD。先执行 git switch -c codex/r%s-main，再领取轮次；"
                           "main 可替换为车道名。" % number)


def require_clean_checkout(root: Path = ROOT) -> None:
    """未落分支的改动不能作为下一轮的隐含起点，避免跨轮写同一文件。"""
    result = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError("无法检查工作树状态：%s" % result.stderr.strip())
    dirty = [line for line in result.stdout.splitlines() if line.strip()]
    if dirty:
        raise RuntimeError("拒绝领取轮次：当前工作树有未提交改动，可能与本轮文件重叠。"
                           "先执行 git switch -c codex/wip-r<轮次> 保存 WIP，再领取轮次；"
                           "脏文件：%s" % ", ".join(dirty))


def require_master_not_dirty(root: Path = ROOT) -> None:
    """master/main 上有未提交改动时拒绝领号：领号会自动切走分支，主目录就会离开 master。"""
    head = subprocess.run(["git", "-C", str(root), "symbolic-ref", "--quiet", "--short", "HEAD"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if head.stdout.strip() not in ("master", "main"):
        return
    status = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    dirty = [line for line in status.stdout.splitlines() if line.strip()]
    if dirty:
        raise RuntimeError("拒绝领取轮次：%s 分支上有未提交改动，领号会把它切走。"
                           "主目录须留在 master；请在工作树（git worktree）里改动并领号。"
                           "脏文件：%s" % (head.stdout.strip(), ", ".join(dirty)))


def validate_new_branch(branch: str) -> str:
    """只校验将要新建的分支；已检出的历史工作树不追溯、不重命名。"""
    if re.fullmatch(r"codex/[a-z0-9]+(?:-[a-z0-9]+)*", branch) is None:
        raise RuntimeError("新建分支名必须为 codex/<lowercase-kebab-task>：%r" % branch)
    return branch


def park_dirty_checkout(number: int, root: Path = ROOT) -> str | None:
    """旧非 codex 脏树领号后停泊到 ``codex/wip-r<号>``；已有 codex 车道保持原样。

    返回新分支名；已有 codex 分支、工作树干净或切换失败时返回 None。
    """
    head = subprocess.run(["git", "-C", str(root), "symbolic-ref", "--quiet", "--short", "HEAD"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if head.stdout.strip().startswith("codex/"):
        return None
    status = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if status.returncode or not status.stdout.strip():
        return None
    branch = validate_new_branch("codex/wip-r%s" % number)
    switched = subprocess.run(["git", "-C", str(root), "switch", "-c", branch], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if switched.returncode:
        print("未能自动切到 %s：%s" % (branch, switched.stderr.strip()), file=sys.stderr)
        return None
    print("工作树有未提交改动，已原样带到新分支 %s" % branch, file=sys.stderr)
    return branch


def require_worktree_fresh(root: Path = ROOT, limit: int = 10) -> None:
    """分支相对 master 领先超过 limit 个提交时拒绝领号（AGENTS.md 规则 27 并行硬规则）。

    领先过深的 WIP 必须先 rebase 或回合主干再领号，避免并行车道长期分叉；
    master/main 自身不触发（其 ahead 表示未推送，属 push 门禁管辖，非本门禁）。"""
    branch = subprocess.run(["git", "-C", str(root), "symbolic-ref", "--quiet", "--short", "HEAD"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    branch = branch.stdout.strip()
    if not branch or branch in ("master", "main"):
        return
    main_branch = "master"
    for candidate in ("master", "main"):
        verify = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "--quiet",
                                 candidate], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if verify.returncode == 0:
            main_branch = candidate
            break
    # B3 源码口径：只数触碰 *.py/*.pyw 的提交；纯文档/结果文件/台账提交 rebase 零成本不计入。
    result = subprocess.run(["git", "-C", str(root), "rev-list", "--count",
                             "%s..%s" % (main_branch, branch), "--",
                             ":(top,glob)**/*.py", ":(top,glob)**/*.pyw"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        result = subprocess.run(["git", "-C", str(root), "rev-list", "--count",
                                 "%s..%s" % (main_branch, branch)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode:
            return  # 无法计算 ahead（主干缺失等）时放行，由 require_branch 兜底
    ahead = int(result.stdout.strip() or 0)
    if ahead > limit:
        raise RuntimeError("拒绝领取轮次：分支 %s 领先 %s %d 个源码提交（>%d，文档/结果提交不计）。"
                           "先 rebase 到最新主干或回合，再领取轮次。" % (branch, main_branch, ahead, limit))


def _read_queue(queue_path: Path) -> dict:
    payload = json.loads(queue_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("任务队列格式无效：%s" % queue_path)
    return payload


def _queue_item(payload: dict, task_id: str) -> dict:
    for item in payload["items"]:
        if isinstance(item, dict) and item.get("id") == task_id:
            return item
    raise KeyError("任务队列不存在：%s" % task_id)


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _note(item: dict, text: str) -> None:
    previous = str(item.get("note", "")).strip()
    item["note"] = (previous + "；" if previous else "") + text


def claim_task(*, common_dir: Path, queue_path: Path, task_id: str, owner: str,
               lease_minutes: int = 60, now: datetime | None = None, root: Path = ROOT) -> dict:
    """认领待办；他人的未过期租约会被拒绝，过期租约可抢占并留痕。"""
    if not owner.strip() or lease_minutes <= 0:
        raise ValueError("owner 不可为空且 lease_minutes 必须为正数")
    now = now or datetime.now().astimezone()
    with shared_lock(common_dir):
        payload = _load_authority(common_dir, queue_path, root)
        item = _queue_item(payload, task_id)
        if item.get("status") == "completed":
            raise RuntimeError("任务 %s 已完成，拒绝重新认领" % task_id)
        prior_owner = str(item.get("owner", ""))
        expires_at = _parse_time(item.get("lease_until"))
        active_other = item.get("status") == "claimed" and prior_owner != owner and expires_at and expires_at > now
        if active_other:
            raise RuntimeError("任务 %s 已由 %s 认领至 %s" % (task_id, prior_owner, expires_at.isoformat()))
        takeover = item.get("status") == "claimed" and prior_owner != owner and (not expires_at or expires_at <= now)
        item["status"] = "claimed"
        item["owner"] = owner
        item["lease_minutes"] = lease_minutes
        item["lease_until"] = (now + timedelta(minutes=lease_minutes)).isoformat(timespec="seconds")
        if takeover:
            _note(item, "%s 过期后由 %s 抢占" % (prior_owner or "未署名认领", owner))
        _write_authority(common_dir, queue_path, payload, root)
        return dict(item)


def renew_task(*, common_dir: Path, queue_path: Path, task_id: str, owner: str,
               lease_minutes: int = 60, now: datetime | None = None, root: Path = ROOT) -> dict:
    """租约心跳：owner 续约 lease_until；他人任务或已释放任务拒绝。"""
    if lease_minutes <= 0:
        raise ValueError("lease_minutes 必须为正数")
    now = now or datetime.now().astimezone()
    with shared_lock(common_dir):
        payload = _load_authority(common_dir, queue_path, root)
        item = _queue_item(payload, task_id)
        if item.get("status") != "claimed" or item.get("owner") != owner:
            raise RuntimeError("任务 %s 不属于 %s 或未处于认领态，拒绝续约" % (task_id, owner))
        item["lease_minutes"] = lease_minutes
        item["lease_until"] = (now + timedelta(minutes=lease_minutes)).isoformat(timespec="seconds")
        _note(item, "%s 心跳续约至 %s" % (owner, item["lease_until"]))
        _write_authority(common_dir, queue_path, payload, root)
        return dict(item)


def release_task(*, common_dir: Path, queue_path: Path, task_id: str, owner: str, root: Path = ROOT) -> dict:
    """释放自己持有的任务，保留释放痕迹以便后续接手。"""
    with shared_lock(common_dir):
        payload = _load_authority(common_dir, queue_path, root)
        item = _queue_item(payload, task_id)
        if item.get("status") != "claimed" or item.get("owner") != owner:
            raise RuntimeError("任务 %s 不由 %s 持有，拒绝释放" % (task_id, owner))
        item["status"] = "pending"
        item["owner"] = ""
        item["lease_until"] = ""
        _note(item, "%s 已释放认领" % owner)
        _write_authority(common_dir, queue_path, payload, root)
        return dict(item)


def complete_task(*, common_dir: Path, queue_path: Path, task_id: str, owner: str, note: str, root: Path = ROOT) -> dict:
    """将自己认领的任务收口，避免手工改队列绕过共享锁。"""
    with shared_lock(common_dir):
        payload = _load_authority(common_dir, queue_path, root)
        item = _queue_item(payload, task_id)
        if item.get("status") != "claimed" or item.get("owner") != owner:
            raise RuntimeError("任务 %s 不由 %s 持有，拒绝收口" % (task_id, owner))
        item["status"] = "completed"
        item["lease_until"] = ""
        _note(item, note)
        _write_authority(common_dir, queue_path, payload, root)
        return dict(item)


def ensure_hooks(common_dir: Path) -> list[str]:
    """协作 Git 钩子缺失或与版本受控源不一致时自动安装；失败只提示，不影响领号。

    新克隆没装钩子就没有提交门禁和全量后台补跑，所以每次领号顺带自愈（钩子是版本受控文件，覆盖安全）。"""
    try:
        import install_git_hooks
        stale = []
        for name in install_git_hooks.HOOKS:
            installed = common_dir / "hooks" / name
            expected = (install_git_hooks.SOURCE / name).read_bytes().replace(bytes((13, 10)), bytes((10,)))
            if not installed.is_file() or installed.read_bytes() != expected:
                stale.append(name)
        if stale:
            install_git_hooks.install(common_dir)
            print("已自动安装／更新 git 钩子：" + "、".join(stale), file=sys.stderr)
        return stale
    except Exception as error:     # 自愈是尽力而为
        print("git 钩子自检失败（不影响领号）：%s" % error, file=sys.stderr)
        return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=False)
    next_parser = subparsers.add_parser("next", help="领取下一个轮次号")
    next_parser.add_argument("--branch", help="领号前新建并切换到 codex/<lowercase-kebab-task> 分支")
    subparsers.add_parser("lanes", help="车道注册表 lanes.json：owner/role/last_seen")
    for command in ("show", "validate"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    record_parser = subparsers.add_parser("record", help="为已分配轮次补登当前工作树归属")
    record_parser.add_argument("number", type=int)
    for command, help_text in (("claim", "认领队列任务"), ("release", "释放队列任务"),
                               ("complete", "收口队列任务"), ("renew", "队列租约心跳续约")):
        sub = subparsers.add_parser(command, help=help_text)
        sub.add_argument("task_id")
        sub.add_argument("--owner", required=True)
        sub.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
        if command in ("claim", "renew"):
            sub.add_argument("--lease-minutes", type=int, default=60)
        if command == "complete":
            sub.add_argument("--note", required=True)
    args = parser.parse_args(argv)
    common_dir = git_common_dir()
    if hasattr(args, "queue") and args.queue.resolve() != (common_dir / QUEUE_NAME).resolve():
        parser.error("--queue 必须指向 Git common-dir/maintenance-queue.json；禁止编辑工作树快照")
    if args.command in (None, "next"):
        try:
            # 校验新名先于领号、切分支及登记；现存分支无须迁移名称。
            branch = getattr(args, "branch", None)
            if branch is not None:
                validate_new_branch(branch)
            # 主树脚本从其他工作树调用时，也必须检查实际 cwd 所在树。
            require_branch(Path.cwd())
            require_master_not_dirty(Path.cwd())
            require_worktree_fresh(Path.cwd())
            if branch is not None:
                switched = subprocess.run(["git", "-C", str(Path.cwd()), "switch", "-c", branch],
                                          capture_output=True, text=True, encoding="utf-8", errors="replace")
                if switched.returncode:
                    raise RuntimeError("无法新建分支 %s：%s" % (branch, switched.stderr.strip()))
        except (RuntimeError, subprocess.CalledProcessError) as error:
            print(str(error), file=sys.stderr)
            return 2
        number = claim_next(common_dir=common_dir, tasks_round=PROGRAM / "tasks_round",
                            root=ROOT, claimant_dir=Path.cwd())
        if park_dirty_checkout(number, Path.cwd()):
            entry = record_claim(common_dir=common_dir, number=number, claimant_dir=Path.cwd())
            try:
                import lane_registry
                lane_registry.register(Path.cwd(), common_dir, owner=str(entry.get("worktree", "")))
            except Exception:
                pass  # 与 claim_next 一致：车道观测失败不阻断已完成的领号
        ensure_hooks(common_dir)
        print(number)
    elif args.command in ("show", "validate"):
        payload = _load_authority(common_dir, args.queue, ROOT)
        if args.command == "show":
            show_queue(payload)
        else:
            errors, warnings = validate_queue(payload)
            for message in errors:
                print("ERROR " + message)
            for message in warnings:
                print("WARN " + message)
            print("validate: %d errors, %d warnings" % (len(errors), len(warnings)))
            return int(bool(errors))
    elif args.command == "record":
        try:
            require_branch(Path.cwd())
        except RuntimeError as error:
            print(str(error), file=sys.stderr)
            return 2
        entry = record_claim(common_dir=common_dir, number=args.number, claimant_dir=Path.cwd())
        print(json.dumps(entry, ensure_ascii=False))
    elif args.command == "renew":
        item = renew_task(common_dir=common_dir, queue_path=args.queue, task_id=args.task_id,
                          owner=args.owner, lease_minutes=args.lease_minutes)
        print(json.dumps(item, ensure_ascii=False))
    elif args.command == "lanes":
        import lane_registry
        for row in lane_registry.list_lanes(common_dir):
            flag = " [STALE]" if row["stale"] else ""
            print("%-24s role=%-5s owner=%-16s idle=%sh last_seen=%s%s" % (
                row["lane"], row["role"], row["owner"] or "-", row["idle_hours"],
                time.strftime("%m-%d %H:%M", time.localtime(row["last_seen"])), flag))
        return 0
    elif args.command == "claim":
        item = claim_task(common_dir=common_dir, queue_path=args.queue, task_id=args.task_id,
                          owner=args.owner, lease_minutes=args.lease_minutes)
        print(json.dumps(item, ensure_ascii=False))
    elif args.command == "release":
        item = release_task(common_dir=common_dir, queue_path=args.queue, task_id=args.task_id, owner=args.owner)
        print(json.dumps(item, ensure_ascii=False))
    else:
        item = complete_task(common_dir=common_dir, queue_path=args.queue, task_id=args.task_id,
                             owner=args.owner, note=args.note)
        print(json.dumps(item, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
