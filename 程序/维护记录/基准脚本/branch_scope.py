"""活跃车道范围扫描与提交重叠门禁。

两条并行车道各自实现同一需求时会「新增」同名文件，合入时变 add/add 冲突
（R2542 对 R2538 工程闸门批次4 的重复实现）。本模块提供两层防线：

- ``dev.py scope <路径>...``：开工前把计划触及的路径与各工作树分支相对 master 的
  改动求交，重叠即提示，避免重复开工；``--staged`` 报告当前暂存内容过门禁的结论。
- ``dev.py commit`` 门禁（``commit_round.check_scope_overlap``）：只有与**活跃**车道
  存在**真实文本冲突**或双方新增同名文件时才拒绝提交。R3956 之前按文件名交集
  整文件拒绝，R3919、R3922、R3950 被误拒后只能绕开提交工具。

「车道」＝``git worktree list`` 中带分支引用的工作树，排除主干（master/main）与调用方
当前分支；无工作树的未合并分支视为停放或遗留，不参与比对，其风险由合并轮 CI 兜底。
「活跃」＝分支最新提交或 ``lanes.json`` 的 ``last_seen`` 在 24 小时内；不活跃的车道有
重叠只提示。

真实冲突用 ``git merge-tree`` 三方试合并判断：合并基取 HEAD 与对方分支尖的合并基，
一边是暂存树，一边是对方分支尖。HEAD 与对方此前已经冲突的路径，没有出现新的冲突段
就不算本次新增。改名按「删旧名加新名」比对，冲突落在改名后的路径上同样算。对方分支
带着本分支还没有的主干提交时，暂存内容与那段主干的冲突只提示先变基，不算在车道头上。
试合并在临时对象目录和索引副本上进行，不往仓库写对象，不动索引；结果按（树、合并基、
分支尖、路径）缓存在 common-dir。语义冲突查不出来，由合并时的出口检查兜底。
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lane_registry  # noqa: E402
import worktree_ledger  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
MAIN_BRANCHES = ("master", "main")
ACTIVE_HOURS = 24                      # 分支尖提交或车道心跳在这之内算活跃
CACHE_NAME = "scope-gate-cache.json"   # <git common-dir> 下的试合并结果缓存
CACHE_VERSION = 3                      # 缓存内容的含义一变就加一，旧缓存整份作废（3：记全部冲突路径的指纹）
CACHE_LIMIT = 500
WORKERS = 8
NOTE_NAMES = 3                         # 提示行最多列出的分支名，其余只报条数
GATE_ERRORS = (RuntimeError, OSError, subprocess.SubprocessError)


def git(root, *args):
    """worktree_ledger.git 加 ``core.quotepath=false``：中文路径不转义。"""
    return worktree_ledger.git(root, "-c", "core.quotepath=false", *args)


def _git_raw(root, args, *, env=None, ok=(0,)):
    """要带环境变量、要原始字节或要容忍非零退出码时用；返回 ``(退出码, stdout 字节)``。"""
    done = subprocess.run(["git", "--no-optional-locks", "-c", "core.quotepath=false", "-C", str(root), *args],
                          capture_output=True, env=env, timeout=120)
    if done.returncode not in ok:
        raise RuntimeError(done.stderr.decode("utf-8", "replace").strip()
                           or "git %s 退出码 %d" % (args[0], done.returncode))
    return done.returncode, done.stdout


def _reason(error):
    return str(error).strip() or type(error).__name__


def common_dir(root):
    path = Path(git(root, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    return path if path.is_absolute() else (Path(root) / path).resolve()


def lane_branches(root, exclude=()):
    """工作树分支清单 ``[{branch, path}]``；exclude 为分支名集合。"""
    skip = set(exclude) | set(MAIN_BRANCHES)
    lanes = []
    for record in worktree_ledger.worktrees(root):
        ref = record.get("branch")
        if not isinstance(ref, str):
            continue  # detached 等无分支引用的工作树不算车道
        branch = ref.removeprefix("refs/heads/")
        if branch and branch not in skip:
            lanes.append({"branch": branch, "path": record.get("path", "")})
    return lanes


def branch_snapshot(root):
    """一次 ``for-each-ref`` 取各本地分支的尖、最新提交时间、领先 master 的提交数。

    返回 ``{分支: {"tip", "committed", "ahead"}}``。取不到领先数（没有 master 分支、Git 早于 2.41）时
    ahead 为 None，调用方按「不知道」处理。
    """
    fields = "%(refname)%09%(objectname)%09%(committerdate:unix)"
    try:
        out = git(root, "for-each-ref", "--format=" + fields + "%09%(ahead-behind:master)", "refs/heads")
    except GATE_ERRORS:
        out = git(root, "for-each-ref", "--format=" + fields, "refs/heads")
    snapshot = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        counts = parts[3].split() if len(parts) > 3 else []
        snapshot[parts[0].removeprefix("refs/heads/")] = {
            "tip": parts[1],
            "committed": float(parts[2]) if parts[2].isdigit() else 0.0,
            "ahead": int(counts[0]) if counts and counts[0].isdigit() else None,
        }
    return snapshot


def lane_activity(root, snapshot=None):
    """各本地分支最近一次活动（epoch 秒）：分支尖提交时间与 ``lanes.json`` 心跳取较新者。

    车道注册表读不出来时只按提交时间算。
    """
    snapshot = branch_snapshot(root) if snapshot is None else snapshot
    seen = {branch: info["committed"] for branch, info in snapshot.items()}
    try:
        rows = lane_registry.list_lanes(common_dir(root))
    except (*GATE_ERRORS, ValueError, TypeError):
        rows = []
    for row in rows:
        branch = row.get("branch")
        if branch:
            seen[branch] = max(seen.get(branch, 0.0), float(row.get("last_seen") or 0.0))
    return seen


def changed_files(root, branch, added_only=False, renames=True):
    """分支相对 master 合并基的改动文件集；added_only 时只算新增。

    renames=False 时改名按「删旧名加新名」两条列出，提交门禁靠它发现对方改过名的旧路径。
    """
    flt = (("--diff-filter=A",) if added_only else ()) + (() if renames else ("--no-renames",))
    out = git(root, "diff", "--name-only", *flt, "master..." + branch)
    return {line for line in out.splitlines() if line}


def scan(root, added_only=False, exclude=(), snapshot=None, renames=True):
    """逐分支扫描（并发读取）。返回 ``(found, errors)``：

    found = {branch: {"path": 工作树路径, "files": set}}（files 可为空）；
    errors = {branch: 读取失败原因}。分支尖已经在 master 历史里（领先 0 个提交）的车道没有
    未合入改动，不再逐条问 git。
    """
    lanes = lane_branches(root, exclude=exclude)
    if snapshot is None:
        try:
            snapshot = branch_snapshot(root)
        except GATE_ERRORS:
            snapshot = {}

    def read(lane):
        if snapshot.get(lane["branch"], {}).get("ahead") == 0:
            return set(), None
        try:
            return changed_files(root, lane["branch"], added_only=added_only, renames=renames), None
        except GATE_ERRORS as error:
            return None, _reason(error)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(read, lanes))
    found, errors = {}, {}
    for lane, (changed, error) in zip(lanes, results):
        if error is None:
            found[lane["branch"]] = {"path": lane["path"], "files": changed}
        else:
            errors[lane["branch"]] = error
    return found, errors


def _hit(path, query):
    query = query.replace("\\", "/").rstrip("/")
    return bool(query) and (path == query or path.startswith(query + "/"))


def scope_report(root, queries=(), *, added_only=False, exclude=()):
    """各工作树分支与查询路径的交集。

    返回 ``{"branches": {branch: {"path","matches","total"}}, "errors": {...},
    "scanned": 分支数}``。queries 为空时 matches 为全部改动文件；
    给了 queries 时只保留有命中的分支。
    """
    found, errors = scan(root, added_only=added_only, exclude=exclude)
    branches = {}
    for branch, info in found.items():
        files = info["files"]
        if queries:
            matched = sorted(p for p in files if any(_hit(p, q) for q in queries))
            if not matched:
                continue
        else:
            matched = sorted(files)
        branches[branch] = {"path": info["path"], "matches": matched, "total": len(files)}
    return {"branches": branches, "errors": errors, "scanned": len(found) + len(errors)}


def staged_added_files(root):
    """暂存区相对 HEAD 的新增文件集。"""
    out = git(root, "diff", "--cached", "--diff-filter=A", "--name-only")
    return {line for line in out.splitlines() if line}


def staged_files(root):
    """暂存区相对 HEAD 的全部路径（含修改与删除；改名按删旧名加新名两条算）。"""
    out = git(root, "diff", "--cached", "--name-only", "--no-renames")
    return {line for line in out.splitlines() if line}


def staged_renames(root):
    """暂存区里改了名的文件：``{新路径: 旧路径}``。"""
    fields = git(root, "diff", "--cached", "--name-status", "-M", "--diff-filter=R", "-z").split("\0")
    return {fields[index + 2]: fields[index + 1]
            for index in range(0, len(fields) - 2, 3) if fields[index].startswith("R")}


def _read_cache(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    entries = data.get("entries") if isinstance(data, dict) and data.get("version") == CACHE_VERSION else None
    return entries if isinstance(entries, dict) else {}


def _write_cache(path, fresh):
    """读→并→写，原子替换。并发时丢一次更新只是下次多算一遍；写不进去不影响判定。"""
    entries = _read_cache(path)
    entries.update(fresh)
    if len(entries) > CACHE_LIMIT:
        def age(key):
            return entries[key].get("at", 0) if isinstance(entries[key], dict) else 0
        entries = {key: entries[key] for key in sorted(entries, key=age)[-CACHE_LIMIT:]}
    temporary = path.with_name("%s.%d.tmp" % (path.name, os.getpid()))
    try:
        temporary.write_text(json.dumps({"version": CACHE_VERSION, "entries": entries}, ensure_ascii=False),
                             encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        with contextlib.suppress(OSError):
            temporary.unlink()


def _conflict_regions(root, env, tree, path):
    """合并结果树里这条路径各冲突段的指纹（已排序）。

    指纹只算标记行之间的内容：标记行带树名，两次试合并本来就不同。没有冲突标记的冲突（改/删、
    二进制、改名）用整份内容的指纹；读不到时给一个固定值。
    """
    try:
        blob = _git_raw(root, ["cat-file", "blob", "%s:%s" % (tree, path)], env=env)[1]
    except GATE_ERRORS:
        return ["unreadable"]
    regions, current = [], None
    for line in blob.split(b"\n"):
        if line.startswith(b"<<<<<<< "):
            current = []
        elif line.startswith(b">>>>>>> ") and current is not None:
            regions.append(hashlib.sha256(b"\n".join(current)).hexdigest()[:16])
            current = None
        elif current is not None:
            current.append(line)
    return sorted(regions) or ["whole:" + hashlib.sha256(blob).hexdigest()[:16]]


def _run_merge_tree(root, env, base, tree, tip, paths):
    """一次三方试合并：返回冲突路径 → 冲突指纹。试合并本身失败抛 RuntimeError。

    paths 里的路径给各冲突段的内容指纹；其余冲突路径不另读内容，只给三方版本号的指纹，
    用来发现「有一方改过名，冲突落在别的路径上」。
    """
    code, out = _git_raw(root, ["merge-tree", "--write-tree", "--no-messages", "-z",
                                "--merge-base=" + base, tree, tip], env=env, ok=(0, 1))
    if code == 0:
        return {}
    fields = out.decode("utf-8", "replace").split("\0")
    merged, wanted, stages = fields[0].strip(), set(paths), {}
    for field in fields[1:]:
        meta, tab, name = field.partition("\t")     # 「<模式> <对象> <阶段>\t<路径>」
        if tab and name:
            stages.setdefault(name, []).append(meta)
    found = {}
    for name, versions in stages.items():
        if name in wanted:
            found[name] = _conflict_regions(root, env, merged, name)
        else:
            digest = hashlib.sha256("\n".join(sorted(versions)).encode("utf-8")).hexdigest()[:16]
            found[name] = ["versions:" + digest]
    return found


class _TrialMerge:
    """一次门禁判定用的试合并环境：临时对象目录加索引副本，用完即删，仓库不留痕。

    ``git write-tree`` 不能直接对着真实索引跑：它会锁索引（别的 git 进程占着就失败），还会把
    只存在于临时对象目录里的树写进索引的目录缓存。
    """

    def __init__(self, root):
        self.root = root
        self.common = common_dir(root)
        self._scratch = tempfile.TemporaryDirectory(prefix="scope-gate-", ignore_cleanup_errors=True)
        objects = Path(self._scratch.name) / "objects"
        objects.mkdir()
        alternates = [str(self.common / "objects")]
        if os.environ.get("GIT_ALTERNATE_OBJECT_DIRECTORIES"):
            alternates.append(os.environ["GIT_ALTERNATE_OBJECT_DIRECTORIES"])
        self.env = dict(os.environ, GIT_OBJECT_DIRECTORY=str(objects),
                        GIT_ALTERNATE_OBJECT_DIRECTORIES=os.pathsep.join(alternates))
        self.cache_path = self.common / CACHE_NAME
        self.cache = _read_cache(self.cache_path)
        self.fresh = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self.fresh:
            _write_cache(self.cache_path, self.fresh)
        self._scratch.cleanup()
        return False

    def staged_tree(self):
        index = Path(git(self.root, "rev-parse", "--path-format=absolute", "--git-path", "index"))
        if not index.is_absolute():
            index = Path(self.root) / index
        copy = Path(self._scratch.name) / "index"
        shutil.copyfile(index, copy)
        env = dict(self.env, GIT_INDEX_FILE=str(copy))
        return _git_raw(self.root, ["write-tree"], env=env)[1].decode("ascii", "replace").strip()

    def conflicts(self, tree, base, tip, paths):
        """试合并里 paths 中冲突的路径 → 各冲突段指纹；命中缓存时不重算。"""
        wanted = sorted(paths)
        key = hashlib.sha256("\0".join([tree, base, tip, *wanted]).encode("utf-8")).hexdigest()
        hit = self.cache.get(key)
        cached = hit.get("conflicts") if isinstance(hit, dict) else None
        if isinstance(cached, dict) and all(isinstance(regions, list) for regions in cached.values()):
            return dict(cached)
        found = _run_merge_tree(self.root, self.env, base, tree, tip, wanted)
        self.fresh[key] = {"at": int(time.time()), "conflicts": found}
        return found


def _trunk_conflicts(trial, root, tip, staged_tree, paths):
    """对方分支带着本分支还没有的主干提交时，暂存内容与那段主干单独试合并的冲突；否则为空。

    这类冲突不是车道带来的，本分支变基到最新主干时自己就会遇到。判断不了时返回空，冲突仍算在车道头上。
    """
    try:
        fork = git(root, "merge-base", "master", tip)
        if _git_raw(root, ["merge-base", "--is-ancestor", fork, "HEAD"], ok=(0, 1))[0] == 0:
            return {}
        return trial.conflicts(staged_tree, git(root, "merge-base", "HEAD", fork), fork, paths)
    except GATE_ERRORS:
        return {}


def _lane_verdict(trial, root, branch, tip, paths, added, staged_tree, head_tree, lane_files=(), renamed=None):
    """一条活跃车道的判定。

    added：双方新增的同名文件；conflict：本次暂存新带来的真实冲突；elsewhere：同样是新冲突，但落在
    重叠路径之外（有一方改过名）；existing：HEAD 与对方此前已经冲突，且暂存后的每个冲突段都与此前
    的某一段逐字相同（改动落在已有冲突段里面或紧挨着它时，那一段的内容会变，按新冲突算）；trunk：
    新冲突来自对方分支带着、本分支还没有的主干提交；mergeable：能自动合并；unchecked：试合并没做成，
    failed 是原因。
    """
    verdict = {"added": [], "conflict": [], "elsewhere": [], "existing": [], "trunk": [], "mergeable": [],
               "unchecked": [], "failed": ""}
    rest = sorted(paths)
    try:
        if added & set(paths):
            other_added = changed_files(root, branch, added_only=True)
            verdict["added"] = sorted(path for path in paths if path in added and path in other_added)
            rest = sorted(set(paths) - set(verdict["added"]))
        if not rest:
            return verdict
        if isinstance(trial, str):
            raise RuntimeError(trial)
        tip = tip or git(root, "rev-parse", "--verify", "refs/heads/" + branch)
        base = git(root, "merge-base", "HEAD", tip)
        now_conflicts = trial.conflicts(staged_tree, base, tip, rest)
        before = trial.conflicts(head_tree, base, tip, rest) if now_conflicts else {}
    except GATE_ERRORS as error:
        verdict["unchecked"], verdict["failed"] = rest, _reason(error)
        return verdict
    fresh = {path: set(now_conflicts[path]) - set(before.get(path, ())) for path in now_conflicts}
    trunk = _trunk_conflicts(trial, root, tip, staged_tree, rest) if any(fresh.get(path) for path in rest) else {}
    for path in rest:
        if path not in now_conflicts:
            verdict["mergeable"].append(path)
        elif not fresh[path]:
            verdict["existing"].append(path)
        elif not fresh[path] - set(trunk.get(path, ())):
            verdict["trunk"].append(path)
        else:
            verdict["conflict"].append(path)
    theirs = set(lane_files)
    reachable = theirs | {new for new, old in (renamed or {}).items() if old in theirs}
    verdict["elsewhere"] = sorted(path for path in now_conflicts
                                  if path not in rest and path in reachable and fresh[path])
    if verdict["elsewhere"]:
        verdict["mergeable"] = []      # 冲突落在改名后的路径上：旧路径「没有冲突」不等于能自动合并
    return verdict


def _judge_active(root, active, added, snapshot, lane_files):
    """对路径有交集的活跃车道逐条判定（并发试合并）；返回 ``{branch: verdict}``。"""
    branches = sorted(active)
    with contextlib.ExitStack() as stack:
        try:
            trial = stack.enter_context(_TrialMerge(root))
            staged_tree = trial.staged_tree()
            head_tree = git(root, "rev-parse", "--verify", "HEAD^{tree}")
            renamed = staged_renames(root)
        except GATE_ERRORS as error:
            trial, staged_tree, head_tree, renamed = "试合并环境准备失败：" + _reason(error), "", "", {}
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            verdicts = list(pool.map(
                lambda branch: _lane_verdict(trial, root, branch, snapshot.get(branch, {}).get("tip", ""),
                                             active[branch], added, staged_tree, head_tree,
                                             lane_files.get(branch, ()), renamed),
                branches))
    return dict(zip(branches, verdicts))


def _names(branches, limit=None):
    ordered = sorted(branches)
    if limit and len(ordered) > limit:
        return "%s 等 %d 条" % ("、".join(ordered[:limit]), len(ordered))
    return "、".join(ordered)


def commit_gate_report(root, exclude_branch, *, now=None):
    """提交门禁报告：``{"conflicts": [...], "skipped": [...], "notes": [...]}``。

    conflicts 非空即拒绝：暂存内容与活跃车道的未合入改动重叠且试合并有真实冲突（包括冲突落在
    改名后的路径上），或双方新增了同名文件（沿用 add/add 文案）。notes 只提示：能自动合并的重叠、
    此前已存在且本次没有加重的冲突、与主干新提交的冲突（该先变基）、不活跃车道的重叠。skipped 是
    没能比对的车道（改动清单读取失败、试合并失败），只警告不阻断。now 供测试指定「现在」。
    """
    report = {"conflicts": [], "skipped": [], "notes": []}
    staged = staged_files(root)
    if not staged:
        return report
    try:
        snapshot = branch_snapshot(root)
    except GATE_ERRORS:
        snapshot = {}
    found, errors = scan(root, added_only=False, exclude={exclude_branch}, snapshot=snapshot, renames=False)
    report["skipped"] = ["分支 %s 的改动清单读取失败，本次未纳入比对：%s" % (branch, error)
                         for branch, error in sorted(errors.items())]
    overlaps = {branch: staged & info["files"] for branch, info in found.items()}
    overlaps = {branch: paths for branch, paths in overlaps.items() if paths}
    if not overlaps:
        return report
    now = time.time() if now is None else now
    activity = lane_activity(root, snapshot)
    # 取不到活动时间的车道按活跃处理：宁可多做一次试合并，不把读取失败当成「对方不活跃」。
    active = {branch: paths for branch, paths in overlaps.items()
              if branch not in activity or now - activity[branch] <= ACTIVE_HOURS * 3600}
    by_path = {}
    for branch, paths in overlaps.items():
        if branch not in active:
            for path in paths:
                by_path.setdefault(path, {}).setdefault("idle", []).append(branch)
    lane_files = {branch: found[branch]["files"] for branch in active}
    verdicts = _judge_active(root, active, staged_added_files(root), snapshot, lane_files) if active else {}
    moved = []
    for branch, verdict in sorted(verdicts.items()):
        for kind in ("added", "conflict", "existing", "trunk", "mergeable"):
            for path in verdict[kind]:
                by_path.setdefault(path, {}).setdefault(kind, []).append(branch)
        if verdict["elsewhere"]:
            moved.append((branch, verdict["elsewhere"]))
        if verdict["unchecked"]:
            report["skipped"].append("活跃分支 %s 试合并失败，本次未纳入比对（重叠路径：%s）：%s"
                                     % (branch, "、".join(verdict["unchecked"]), verdict["failed"]))
    for path in sorted(by_path):
        kinds = by_path[path]
        if "added" in kinds:
            report["conflicts"].append(
                "新增文件 %s 与活跃分支 %s 撞名（双方均按新文件添加，合入将成 add/add 冲突；"
                "请改名、协调归属，或待对方合入后再提交）" % (path, _names(kinds["added"])))
        if "conflict" in kinds:
            report["conflicts"].append(
                "路径 %s 与活跃分支 %s 的未合入改动重叠，试合并有真实冲突（合入将冲突；"
                "请错开改动位置，或待对方合入后再提交）" % (path, _names(kinds["conflict"])))
        if "existing" in kinds:
            report["notes"].append("路径 %s 与活跃分支 %s 此前已经冲突，本次提交没有新增或改动冲突段，不拦截"
                                   % (path, _names(kinds["existing"], NOTE_NAMES)))
        if "trunk" in kinds:
            report["notes"].append("路径 %s 与主干上本分支还没有同步的提交冲突（活跃分支 %s 带着这些提交，"
                                   "不是与车道冲突）；合入前需要先变基解决，不拦截"
                                   % (path, _names(kinds["trunk"], NOTE_NAMES)))
        if "mergeable" in kinds:
            report["notes"].append("路径 %s 与活跃分支 %s 的未合入改动重叠，试合并可以自动合并，不拦截"
                                   % (path, _names(kinds["mergeable"], NOTE_NAMES)))
        if "idle" in kinds:
            report["notes"].append("路径 %s 另有超过 %d 小时无活动的分支改过（%s），只提示不拦截"
                                   % (path, ACTIVE_HOURS, _names(kinds["idle"], NOTE_NAMES)))
    for branch, paths in moved:
        report["conflicts"].append(
            "暂存内容与活跃分支 %s 的未合入改动重叠，试合并后 %s 出现新的冲突（有一方移动或改名过文件，"
            "冲突落在改名后的路径上；请与对方协调，或待对方合入后再提交）" % (branch, "、".join(paths)))
    return report


def _current_branch(root):
    try:
        return git(root, "symbolic-ref", "--quiet", "--short", "HEAD").strip()
    except RuntimeError:
        return ""


def _print_gate(report, as_json):
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    for line in report["skipped"]:
        print("警告：" + line)
    for line in report["notes"]:
        print("提示：" + line)
    for line in report["conflicts"]:
        print("拒绝提交：" + line)
    if not report["conflicts"]:
        print("暂存内容可以提交：与活跃车道没有真实冲突，也没有新增撞名。")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--added", action="store_true",
                        help="只比对各分支新增文件（add/add 口径）")
    parser.add_argument("--staged", action="store_true",
                        help="报告当前暂存内容过提交门禁的结论（会被拒绝时退出码 5）")
    parser.add_argument("--json", action="store_true", help="机器可读输出")
    parser.add_argument("--root", type=Path, default=ROOT, help="仓库根（默认本仓库）")
    parser.add_argument("paths", nargs="*",
                        help="repo 相对路径或目录前缀；省略则只显示各分支改动数量")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    current = _current_branch(root)
    if args.staged:
        report = commit_gate_report(root, exclude_branch=current)
        _print_gate(report, args.json)
        return 5 if report["conflicts"] else 0
    exclude = {current} if current else set()
    report = scope_report(root, args.paths, added_only=args.added, exclude=exclude)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    mode = "仅新增文件" if args.added else "全部改动"
    print("车道范围扫描（基线 master，%s；当前分支 %s 已排除）" % (mode, current or "未知"))
    if args.paths:
        for branch in sorted(report["branches"]):
            info = report["branches"][branch]
            print("• %s — %d 个重叠" % (branch, len(info["matches"])))
            for path in info["matches"]:
                print("    " + path)
        clean = report["scanned"] - len(report["branches"]) - len(report["errors"])
        if clean:
            print("（另 %d 个工作树分支无重叠）" % clean)
    else:
        for branch in sorted(report["branches"]):
            info = report["branches"][branch]
            print("• %s — 改动 %d 个文件" % (branch, info["total"]))
        if not report["branches"]:
            print("没有其他工作树分支。")
    for branch, error in sorted(report["errors"].items()):
        print("警告：%s 读取失败已跳过：%s" % (branch, error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
