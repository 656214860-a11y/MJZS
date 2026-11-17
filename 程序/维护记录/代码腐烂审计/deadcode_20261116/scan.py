# -*- coding: utf-8 -*-
"""死代码扫描 B0：程序/ 生产运行时文件级 import 图＋分层存活判定（只读 AST，不改任何文件）。

用法（工作目录 任意）：
    python -B scan.py            # 写 scan1.json 并打印分层摘要
"""
from __future__ import annotations

import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

PROG = Path(__file__).resolve().parents[3]
ROOT = PROG
PYW = PROG.parent / "启动漫剧制作助手.pyw"
sys.path.insert(0, str(PROG))

from tests.architecture import _scan  # noqa: E402

OUT = Path(__file__).resolve().parent / "scan1.json"

_NONPRODUCT_DIRS = {"tests", "scripts", "skills", "附加工具", "维护记录", "tasks_round",
                    "data", "logs", "private", "docs", "说明", "配置", "workflows",
                    "assets", "outputs", "reference", "episode", "__pycache__", ".git", ".wt"}


def rel(p: Path) -> str:
    return p.relative_to(PROG).as_posix()


def dotted_of(path: Path) -> str:
    parts = list(path.relative_to(PROG).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def path_of_dotted(dotted: str) -> list[Path]:
    """dotted 模块名 → 候选文件（.py 优先，包 __init__.py 兜底）。"""
    parts = [p for p in dotted.split(".") if p]
    if not parts:
        return []
    base = PROG.joinpath(*parts)
    return [base.with_suffix(".py"), base / "__init__.py"]


_DOTTED_RE = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*(\.[A-Za-z_][A-Za-z_0-9]*)*$")


def resolve(dotted: str, from_file: Path | None = None, level: int = 0) -> Path | None:
    if dotted and not _DOTTED_RE.match(dotted):
        return None
    if level:
        assert from_file is not None
        base = from_file.parent
        for _ in range(level - 1):
            base = base.parent
        parts = [p for p in dotted.split(".") if p]
        if not parts:
            return base / "__init__.py" if (base / "__init__.py").is_file() else None
        cand = base.joinpath(*parts)
        for f in (cand.with_suffix(".py"), cand / "__init__.py"):
            if f.is_file():
                return f
        return None
    for f in path_of_dotted(dotted):
        if f.is_file():
            return f
    return None


def iter_imports(tree: ast.AST):
    """产出 (lineno, kind, dotted, level, names)。kind: import / from / dyn。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, "import", alias.name, 0, []
        elif isinstance(node, ast.ImportFrom):
            names = [a.name for a in node.names]
            yield node.lineno, "from", node.module or "", node.level or 0, names
        elif isinstance(node, ast.Call) and node.args:
            func = node.func
            fname = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            first = node.args[0]
            if fname in ("import_module", "__import__") and isinstance(first, ast.Constant) and isinstance(first.value, str):
                yield node.lineno, "dyn", first.value, 0, []
            elif fname == "module" and isinstance(first, ast.Constant) and isinstance(first.value, str):
                yield node.lineno, "plugin_call", first.value, 0, []


def edges_of(path: Path, tree: ast.AST) -> tuple[set[str], list[str], set[str]]:
    """返回 (内部边 rel 集合, 未解析动态名, 字符串常量集合)。"""
    edges: set[str] = set()
    dyn_unresolved: list[str] = []
    strings: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            strings.add(node.value)
    for _ln, kind, dotted, level, names in iter_imports(tree):
        targets: list[Path] = []
        if kind in ("import", "dyn"):
            t = resolve(dotted, path, level)
            if t is not None:
                targets = [t]
                # import a.b.c 会连带导入父包 __init__
                parts = dotted.split(".")
                for i in range(1, len(parts)):
                    anc = resolve(".".join(parts[:i]), path, level)
                    if anc is not None and anc.name == "__init__.py":
                        targets.append(anc)
        elif kind == "plugin_call":
            t = resolve(dotted, path, level)
            if t is not None:
                targets = [t]
            else:
                dyn_unresolved.append(dotted)
        else:  # from
            if dotted:
                base = resolve(dotted, path, level)
            else:
                pkg = path.parent
                for _ in range(level - 1):
                    pkg = pkg.parent
                base = pkg / "__init__.py"
                if not base.is_file():
                    base = None
            if base is not None:
                targets.append(base)
                # from X import name → name 可能是 X 包下的子模块
                if level:
                    pkg_dir = path.parent
                    for _ in range(level - 1):
                        pkg_dir = pkg_dir.parent
                    if dotted:
                        pkg_dir = pkg_dir.joinpath(*[p for p in dotted.split(".") if p])
                else:
                    pkg_dir = PROG.joinpath(*[p for p in dotted.split(".") if p]) if dotted else None
                if pkg_dir is not None and pkg_dir.is_dir():
                    for nm in names:
                        if nm == "*":
                            continue
                        for f in (pkg_dir / (nm + ".py"), pkg_dir / nm / "__init__.py"):
                            if f.is_file():
                                targets.append(f)
            else:
                dyn_unresolved.append(dotted or "<relative>")
        for t in targets:
            try:
                edges.add(rel(t))
            except ValueError:
                pass
    return edges, dyn_unresolved, strings


def main() -> None:
    # ---------- 节点集 ----------
    nodes: dict[str, Path] = {}
    for p in _scan.production_runtime_files():
        nodes[rel(p)] = p
    # 顶层被 _EXCLUDED_STEMS 排除的自检器/smoke 不是生产节点，但作为消费者处理
    consumers: dict[str, Path] = {}
    consumer_dirs = ["tests", "scripts", "skills", "附加工具", "维护记录"]
    for d in consumer_dirs:
        base = PROG / d
        if base.is_dir():
            for p in base.rglob("*.py"):
                consumers[rel(p)] = p
    for p in PROG.glob("*.py"):
        if p.stem.startswith("test") or p.stem in _scan._EXCLUDED_STEMS or p.stem == "smoke_test":
            consumers[rel(p)] = p
    if PYW.is_file():
        consumers["<entry>.pyw"] = PYW

    # ---------- 解析各文件 ----------
    info: dict[str, dict] = {}
    prod_edges: dict[str, set[str]] = {}
    prod_dyn_unres: dict[str, list[str]] = {}
    prod_strings: dict[str, set[str]] = {}
    for r, p in nodes.items():
        try:
            tree = _scan.parse(p)
        except (SyntaxError, UnicodeDecodeError):
            info[r] = {"error": "parse"}
            continue
        edges, unres, strings = edges_of(p, tree)
        edges.discard(r)
        prod_edges[r] = edges
        prod_dyn_unres[r] = unres
        prod_strings[r] = strings
        try:
            lines = sum(1 for _ in p.open(encoding="utf-8", errors="replace"))
        except OSError:
            lines = 0
        has_main = "__main__" in strings or any(
            isinstance(n, ast.If) for n in ast.walk(tree))
        info[r] = {"lines": lines, "dotted": dotted_of(p)}

    # 消费者边（只为统计谁在引用生产模块）
    ext_edges: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for r, p in consumers.items():
        try:
            tree = _scan.parse(p)
        except (SyntaxError, UnicodeDecodeError):
            continue
        edges, _, _ = edges_of(p, tree)
        if r == "<entry>.pyw":
            cls = "entry"
        elif r.startswith("tests/"):
            cls = "tests"
        elif r.startswith("scripts/"):
            cls = "scripts"
        elif "/" not in r:
            cls = "roottest" if Path(r).stem.startswith("test") else "selftest"
        else:
            cls = r.split("/", 1)[0]
        for e in edges:
            if e in nodes:
                ext_edges[e][cls].add(r)

    # ---------- UI_PLUGINS 插件边 ----------
    plugin_targets: dict[str, str] = {}
    try:
        tree = _scan.parse(PROG / "ui_plugin_registry.py")
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "UI_PLUGINS":
                        for sub in ast.walk(node.value):
                            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                                rp = resolve(sub.value)
                                if rp is not None:
                                    try:
                                        plugin_targets[sub.value] = rel(rp)
                                    except ValueError:
                                        pass
    except Exception:
        pass

    # ---------- BFS 存活闭包（静态边＋常量动态边都算活；UI 插件按需加载但属生产可达） ----------
    seeds: set[str] = set()
    if "<entry>.pyw" in consumers:
        tree = _scan.parse(PYW)
        edges, _, _ = edges_of(PYW, tree)
        seeds = {e for e in edges if e in nodes}
    # 先解析插件目标，再把它们并入种子：插件是懒加载但用户可触发的生产路径
    plugin_seed: set[str] = set()
    try:
        tree = _scan.parse(PROG / "ui_plugin_registry.py")
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "UI_PLUGINS":
                        for sub in ast.walk(node.value):
                            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                                rp = resolve(sub.value)
                                if rp is not None:
                                    try:
                                        plugin_targets[sub.value] = rel(rp)
                                        if rel(rp) in nodes:
                                            plugin_seed.add(rel(rp))
                                    except ValueError:
                                        pass
    except Exception:
        pass
    live: set[str] = set(seeds) | plugin_seed
    stack = list(live)
    while stack:
        cur = stack.pop()
        for nxt in prod_edges.get(cur, ()):
            if nxt in nodes and nxt not in live:
                live.add(nxt)
                stack.append(nxt)

    # ---------- 字符串引用：活文件里出现的、能解析成节点的字符串 ----------
    # 带点的字符串（'agent.shot_assets'/'contract.pet_bus'）几乎必是模块路径→升级 tier；
    # 裸名（'pet_bus'/'app'）大量巧合→只记录不升级。
    string_refs: dict[str, set[str]] = defaultdict(set)       # 点分串 -> 目标节点 <- 活文件
    flat_string_refs: dict[str, set[str]] = defaultdict(set)  # 裸名串 -> 目标节点 <- 活文件
    for r in live:
        for s in prod_strings.get(r, ()):
            if "." not in s and not _DOTTED_RE.match(s):
                continue
            cand = resolve(s)
            if cand is None:
                continue
            try:
                tr = rel(cand)
            except ValueError:
                continue
            if tr in nodes and tr != r:
                (string_refs if "." in s else flat_string_refs)[tr].add(r)

    # ---------- 覆盖率基线 ----------
    coverage: dict[str, float] = {}
    cov_path = PROG / "维护记录" / "覆盖率基线.json"
    if cov_path.is_file():
        try:
            data = json.loads(cov_path.read_text(encoding="utf-8"))
            for m in data.get("modules", []):
                name = m.get("module", "")
                pct = m.get("percent")
                coverage[name] = pct
                coverage[Path(name).stem] = pct
                coverage[name.replace("/", ".").replace("\\", ".")] = pct
        except Exception:
            pass

    # ---------- 分层 ----------
    try:
        from tests.architecture import _layers
        layer_map = dict(_layers.LAYERS)
    except Exception:
        layer_map = {}

    # ---------- 分层判定 ----------
    out_nodes = {}
    for r, p in nodes.items():
        meta = info.get(r, {})
        ext = ext_edges.get(r, {})
        consumers_set = sorted({c for cls in ext.values() for c in cls})
        prod_in = sorted({src for src, tgts in prod_edges.items() if r in tgts})
        in_plugin = any(r == t for t in plugin_targets.values())
        cov = None
        for key in (r, Path(r).name, meta.get("dotted", ""), Path(r).stem):
            if key in coverage:
                cov = coverage[key]
                break
        if r in live:
            tier = "LIVE"
        elif in_plugin:
            tier = "PLUGIN_LAZY"
        elif r in string_refs:
            tier = "STRING_DYN"
        elif "tests" in ext or "selftest" in ext or "roottest" in ext:
            tier = "TEST_ONLY"
        elif ext:
            tier = "TOOL_ONLY"
        else:
            tier = "ORPHAN"
        out_nodes[r] = {
            "tier": tier,
            "lines": meta.get("lines", 0),
            "dotted": meta.get("dotted", ""),
            "layer": layer_map.get(Path(r).stem) or layer_map.get(meta.get("dotted", "")),
            "facade": bool(_scan.is_package_facade(p)) if p.parent == PROG else False,
            "plugin_member": in_plugin,
            "coverage": cov,
            "prod_in": prod_in,
            "dyn_string_refs_from_live": sorted(string_refs.get(r, ()))[:10],
            "flat_string_refs_from_live": sorted(flat_string_refs.get(r, ()))[:10],
            "ext_consumers": {k: sorted(v)[:8] for k, v in sorted(ext.items())},
            "unresolved_dyn_in_file": prod_dyn_unres.get(r, [])[:10],
        }

    result = {
        "node_count": len(nodes),
        "consumer_count": len(consumers),
        "live_count": len(live),
        "plugin_targets": plugin_targets,
        "seeds": sorted(seeds),
        "tiers": {t: sum(1 for n in out_nodes.values() if n["tier"] == t)
                  for t in ("LIVE", "PLUGIN_LAZY", "STRING_DYN", "TEST_ONLY", "TOOL_ONLY", "ORPHAN")},
        "nodes": out_nodes,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    print("nodes:", len(nodes), "consumers:", len(consumers), "live:", len(live))
    print("tiers:", result["tiers"])
    print("plugin targets resolved:", len(plugin_targets))
    unresolved_plugins = [k for k, v in plugin_targets.items() if v not in nodes]
    if unresolved_plugins:
        print("UNRESOLVED plugin targets:", unresolved_plugins)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
