"""只读工作树台账；--plan 仅输出待逐条确认的 PowerShell 命令。"""
from __future__ import annotations

import argparse
import json
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def git(root, *args):
    result = subprocess.run(["git", "--no-optional-locks", "-C", str(root), *args],
                            capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    return result.stdout.decode("utf-8", "replace").strip()


def worktrees(root):
    rows, row = [], {}
    for field in git(root, "worktree", "list", "--porcelain", "-z").split("\0"):
        key, _, value = field.partition(" ")
        if key == "worktree":
            row = {"path": value}
            rows.append(row)
        elif key:
            row[key] = value or True
    return rows


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed.replace(tzinfo=timezone.utc).timestamp() if parsed.tzinfo is None else parsed.timestamp()
    except (ValueError, TypeError):
        return 0


def classify(row):
    if row.get("detached") or row.get("orphan"):
        return "BLOCK", "游离 HEAD 或孤儿提交：先落分支"
    if row.get("error"):
        return "BLOCK", "读取失败，不能证明可回收"
    if row.get("main") or row.get("locked"):
        return "KEEP", "主树或 Git 锁定树"
    if row.get("dirty"):
        return "KEEP", "存在未提交内容，先裁定并保存"
    if row.get("leases"):
        return "KEEP", "活跃租约保护"
    if row.get("ahead") == 0:
        return "RECYCLE", "ahead=0，空转树当日回收（须确认）"
    if row.get("behind", 0) > 20 and row.get("idle_hours", 0) >= 48:
        return "RECYCLE", "落后超过20提交且48小时无可见活动；分支引用保留"
    return "KEEP", "存在独有提交且未过期；behind>20 时须 rebase 或归档"


def active_leases(common, now):
    path = common / "maintenance-queue.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [item for item in data["items"] if item.get("status") == "claimed"
            and timestamp(item.get("lease_until")) > now]


def scan_residuals(scan_root, known):
    """仅列显式容器的下一层及条目名，不跟随符号链接或 Windows junction。"""
    rows = []
    if not scan_root.is_dir() or is_link(scan_root):
        return rows
    for child in sorted(scan_root.iterdir()):
        if is_link(child):
            rows.append({"path": str(child), "kind": "unregistered-directory", "action": "KEEP",
                         "reason": "链接/重解析点，需人工核验，未跟随"})
            continue
        if not child.is_dir() or child.resolve() in known:
            continue
        if any(child.resolve() in path.parents for path in known):
            continue
        entries = list(child.iterdir())
        rows.append({"path": str(child), "kind": "unregistered-directory",
                     "entries": [entry.name for entry in entries],
                     "action": "KEEP" if entries else "RECYCLE",
                     "reason": "需人工核验内容/链接，未删除" if entries else "空目录，可移除但尚未获逐条确认"})
    return rows


def is_link(path):
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def collect(root=ROOT, *, scan_roots=(), now=None):
    root = Path(root).resolve()
    now = datetime.now().timestamp() if now is None else now
    common = Path(git(root, "rev-parse", "--git-common-dir"))
    common = common.resolve() if common.is_absolute() else (root / common).resolve()
    lease_error = ""
    try:
        leases = active_leases(common, now)
    except (OSError, ValueError, KeyError, TypeError) as error:
        leases, lease_error = [], str(error)
    rows, known = [], set()
    for record in worktrees(root):
        path = Path(record["path"])
        known.add(path.resolve())
        row = {"path": str(path), "head": record.get("HEAD", ""),
               "branch": str(record.get("branch", "")).removeprefix("refs/heads/"),
               "detached": bool(record.get("detached")), "locked": bool(record.get("locked")),
               "main": path.resolve() == common.parent, "status": "", "leases": []}
        try:
            row["status"] = git(path, "status", "--porcelain")
            row["dirty"] = bool(row["status"])
            # symbolic-ref 是 detached 判定的第二份现场证据，而非只依赖 porcelain。
            try:
                row["symbolic_ref"] = git(path, "symbolic-ref", "HEAD")
            except RuntimeError:
                row["symbolic_ref"], row["detached"] = "", True
            head = row["head"]
            row["containing_branches"] = git(root, "branch", "--contains", head,
                                             "--format=%(refname:short)").splitlines()
            row["orphan"] = not row["containing_branches"]
            ref = row["branch"] or head
            row["behind"] = int(git(root, "rev-list", "--count", ref + "..master"))
            row["ahead"] = int(git(root, "rev-list", "--count", "master.." + ref))
            gitdir = Path(git(path, "rev-parse", "--absolute-git-dir"))
            activity = [float(git(path, "show", "-s", "--format=%ct", "HEAD"))]
            for candidate in (path, gitdir / "index", gitdir / "logs" / "HEAD"):
                if candidate.exists():
                    activity.append(candidate.stat().st_mtime)
            row["last_activity"] = datetime.fromtimestamp(max(activity), timezone.utc).isoformat()
            row["idle_hours"] = round(max(0, now - max(activity)) / 3600, 3)
            for lease in leases:
                location = lease.get("worktree") or lease.get("path")
                branch = lease.get("branch")
                # 队列旧数据没有路径关联时不能证明无租约：保守保护，并明确提示映射缺失。
                unmapped = not location and not branch
                if unmapped or (location and Path(location).resolve() == path.resolve()) or branch == row["branch"]:
                    row["leases"].append({"id": lease["id"], "owner": lease.get("owner"),
                                          "lease_until": lease["lease_until"], "unmapped": unmapped})
            if lease_error:
                row["error"] = "租约读取失败：" + lease_error
        except (OSError, RuntimeError, ValueError) as error:
            row["error"] = str(error)
        row["action"], row["reason"] = classify(row)
        rows.append(row)
    residuals = []
    management = common / "worktrees"
    if management.is_dir():
        for entry in sorted(management.iterdir()):
            link = entry / "gitdir"
            if not link.is_file():
                residuals.append({"path": str(entry), "kind": "management", "action": "BLOCK",
                                  "reason": "缺少 gitdir，需人工核查"})
                continue
            destination = Path(link.read_text(encoding="utf-8").strip())
            if not destination.is_absolute():
                destination = (entry / destination).resolve()
            if not destination.parent.is_dir():
                residuals.append({"path": str(entry), "target": str(destination.parent),
                                  "kind": "management", "action": "RECYCLE",
                                  "reason": "对应目录不存在；先审阅 prune dry-run"})
    for scan_root in scan_roots:
        residuals.extend(scan_residuals(Path(scan_root).absolute(), known))
    return {"at": datetime.fromtimestamp(now, timezone.utc).isoformat(), "common_dir": str(common),
            "activity_basis": "HEAD提交时间、工作树目录、index与HEAD reflog mtime；不探查用户数据",
            "worktrees": rows, "residuals": residuals}


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def plan(data, root):
    commands = ["# 仅计划：逐条确认后才执行；不使用 --force，不删除分支引用。"]
    for row in data["worktrees"]:
        if row["action"] == "RECYCLE":
            commands.append("git -C %s worktree remove %s" % (quote(root), quote(row["path"])))
    if any(row["kind"] == "management" and row["action"] == "RECYCLE" for row in data["residuals"]):
        commands.extend(["git -C %s worktree prune --dry-run --verbose" % quote(root),
                         "# 确认 dry-run 每条目标后：git -C %s worktree prune --verbose" % quote(root)])
    for row in data["residuals"]:
        if row["kind"] == "unregistered-directory":
            commands.append("# 未登记目录仅人工处置，禁止对链接目标递归删除：" + row["path"])
    return commands


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--scan-root", type=Path, action="append", default=[],
                        help="显式工作树容器，可重复；只列一层残差，不扫描普通用户目录")
    parser.add_argument("--format", choices=("table", "json", "both"), default="both")
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args(argv)
    data = collect(args.root, scan_roots=args.scan_root)
    if args.plan:
        data["plan"] = plan(data, args.root)
    if args.format in ("table", "both"):
        print("| 工作树 | 分支/HEAD | ahead | behind | 建议 | 原因 |")
        print("|---|---|---:|---:|---|---|")
        for row in data["worktrees"]:
            print("| %s | %s | %s | %s | %s | %s |" %
                  (row["path"], row["branch"] or row["head"], row.get("ahead", "?"),
                   row.get("behind", "?"), row["action"], row["reason"]))
        for row in data["residuals"]:
            print("| %s | %s | — | — | %s | %s |" %
                  (row["path"], row["kind"], row["action"], row["reason"]))
        for command in data.get("plan", []):
            print(command)
    if args.format in ("json", "both"):
        print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
