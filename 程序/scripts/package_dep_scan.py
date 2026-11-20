"""T10 包化前置：顶层模块依赖扫描（只读 AST，不改任何文件）。

输出每个顶层生产模块的「登记层级、静态/动态出度、被静态/动态引用入度」，
并按文件名前缀聚类给出族内跨层清单，供包化搬家轮排期。

用法（工作目录 程序/）：
    python -B scripts/package_dep_scan.py            # 摘要 + 跨层族
    python -B scripts/package_dep_scan.py --json     # 全量 JSON 到 stdout
    python -B scripts/package_dep_scan.py --family account
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))

from tests.architecture import _layers  # noqa: E402
from tests.architecture._scan import (  # noqa: E402
    dynamic_import_rows,
    import_rows,
    module_name,
    parse,
    production_files,
)

# 与 _scan.production_files 同口径的排除规则（自检器与 test* 不算生产模块）。
_EXCLUDED_STEMS = frozenset({"smoke_test", "run_selftests", "selftest_sandbox",
                             "selftest_env", "selftest_discovery", "selftest_receipts",
                             "selftest_scheduling", "selftest_reporting"})

_PREFIX_RE = re.compile(r"^[A-Za-z]+")


def _prefix(stem: str) -> str:
    """文件名前缀族取首个字母 token：account_store→account、pet_ui_view→pet、ui_tokens→ui。

    族边界只是排期参考，不是包结构；asset_batch_* 与 asset_* 同族、pet_ui_* 与 pet_*
    同族，跨层清单会把它们如实标出。
    """
    match = _PREFIX_RE.match(stem)
    return match.group(0) if match else stem


def _dynamic_string_refs() -> dict[str, set[str]]:
    """非常量动态导入无法静态解析；这里收集『看起来像模块名』的字符串常量引用。

    覆盖 import_module(变量)、getattr 链、JSON/配置里的模块路径等无法静态确认的
    引用形态：把生产文件里所有形如标识符的字符串常量与已知模块名求交集，
    只作人工复核清单，不作为迁移依据。
    """
    known = {module_name(path) for path in production_files()}
    hits: dict[str, set[str]] = defaultdict(set)
    for path in production_files():
        owner = module_name(path)
        try:
            tree = parse(path)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for token in re.findall(r"[A-Za-z_][A-Za-z_0-9]*", node.value):
                    if token in known and token != owner:
                        hits[token].add(owner)
    return hits


_ALL_EXCLUDED_PARTS = frozenset({"tasks_round", "维护记录", ".git", ".wt", ".selftmp",
                                "__pycache__", "data", "skills", "outputs",
                                "工作流任务", "episode", "docs", "governance", "resources", "legacy", "配置",
                                "reference", "assets", "workflows", "附加工具"})


def _consumer_class(rel: Path) -> str:
    parts = rel.parts
    if parts[0] == "tests":
        return "tests"
    if parts[0] == "scripts":
        return "scripts"
    if parts[0] == "agent":
        return "agent"
    if len(parts) == 1:
        return "production"
    return "other:" + parts[0]


def _all_py_files() -> list[Path]:
    """程序/ 下全部 .py（排除记录、缓存与数据目录），供消费者全量统计。"""
    out = []
    for path in sorted(PROGRAM.rglob("*.py")):
        rel = path.relative_to(PROGRAM)
        if any(part in _ALL_EXCLUDED_PARTS for part in rel.parts):
            continue
        if path.stem.startswith("test") or path.stem in _EXCLUDED_STEMS:
            # 顶层 test*.py 与自检器不是生产模块，但 tests/ 下的用例文件要算消费者。
            if rel.parts[0] != "tests":
                continue
        out.append(path)
    return out


def scan() -> dict:
    files = production_files()
    names = {module_name(path) for path in files}
    by_name = {module_name(path): path for path in files}

    static_out: dict[str, set[str]] = {}
    dynamic_out: dict[str, set[str]] = {}
    static_in: dict[str, set[str]] = defaultdict(set)
    dynamic_in: dict[str, set[str]] = defaultdict(set)
    # 非生产消费者：tests/、scripts/、agent/ 等按目录分类计数。
    external_in: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    for path in files:
        owner = module_name(path)
        for _line, target in import_rows(path):
            if target in names:
                static_out.setdefault(owner, set()).add(target)
                static_in[target].add(owner)
        for _line, target in dynamic_import_rows(path):
            if target in names:
                dynamic_out.setdefault(owner, set()).add(target)
                dynamic_in[target].add(owner)

    for path in _all_py_files():
        rel = path.relative_to(PROGRAM)
        cls = _consumer_class(rel)
        if cls == "production":
            continue
        owner = str(rel).replace("\\", "/")
        try:
            tree = parse(path)
        except SyntaxError:
            continue
        seen = set()
        for node in ast.walk(tree):
            target = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    seen.add(alias.name.split(".", 1)[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                seen.add(node.module.split(".", 1)[0])
        for target in seen:
            if target in names:
                external_in[target][cls].add(owner)

    # 层级
    layers = {name: _layers.LAYERS.get(name) for name in names}

    # 按前缀族聚合
    families: dict[str, dict] = defaultdict(lambda: {"modules": [], "layers": set()})
    for name in sorted(names):
        fam = _prefix(name)
        families[fam]["modules"].append(name)
        layer = layers.get(name)
        if layer is not None:
            families[fam]["layers"].add(layer)

    cross_layer = {fam: sorted(info["layers"])
                   for fam, info in families.items() if len(info["layers"]) > 1}

    # 每模块明细
    modules = {}
    for name in sorted(names):
        ext = external_in.get(name, {})
        modules[name] = {
            "file": by_name[name].name,
            "layer": layers.get(name),
            "family": _prefix(name),
            "static_out": sorted(static_out.get(name, ())),
            "dynamic_out": sorted(dynamic_out.get(name, ())),
            "static_in_count": len(static_in.get(name, ())),
            "static_in": sorted(static_in.get(name, ())),
            "dynamic_in_count": len(dynamic_in.get(name, ())),
            "external_in": {cls: sorted(files) for cls, files in sorted(ext.items())},
            "external_in_count": sum(len(v) for v in ext.values()),
        }

    return {
        "module_count": len(names),
        "layer_counts": {str(k): sum(1 for v in layers.values() if v == k)
                         for k in sorted(set(v for v in layers.values() if v is not None))},
        "unregistered": sorted(name for name in names if layers.get(name) is None),
        "families": {fam: {"count": len(info["modules"]),
                           "layers": sorted(info["layers"]),
                           "modules": info["modules"]}
                     for fam, info in sorted(families.items())},
        "cross_layer_families": cross_layer,
        "modules": modules,
        "dynamic_string_refs": {k: sorted(v) for k, v in sorted(_dynamic_string_refs().items())},
    }


def _print_summary(data: dict) -> None:
    print("顶层生产模块：%d 个；登记层级分布：%s" % (data["module_count"], data["layer_counts"]))
    if data["unregistered"]:
        print("未登记层级：%s" % ", ".join(data["unregistered"]))
    print("\n== 跨层族（族内模块分属多个 L 层，搬家需先拆或标层）==")
    for fam, layers in sorted(data["cross_layer_families"].items(),
                              key=lambda kv: -len(kv[1])):
        info = data["families"][fam]
        print("  %-22s 层%s  %d 个模块" % (fam, layers, info["count"]))
    print("\n== 前缀族规模 TOP25 ==")
    for fam, info in sorted(data["families"].items(), key=lambda kv: -kv[1]["count"])[:25]:
        print("  %-22s %2d 个  层%s" % (fam, info["count"], info["layers"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="全量明细 JSON")
    parser.add_argument("--family", help="只看某个前缀族")
    args = parser.parse_args()

    data = scan()
    if args.family:
        fam = args.family
        modules = {n: m for n, m in data["modules"].items() if m["family"] == fam}
        print("族 %s：%d 个模块" % (fam, len(modules)))
        for name, info in sorted(modules.items()):
            ext = info.get("external_in", {})
            ext_text = " 外%d" % info.get("external_in_count", 0)
            if ext:
                ext_text += "(" + ",".join("%s%d" % (k, len(v)) for k, v in ext.items()) + ")"
            print("  %-38s L%s 入%d(动%d)%s 出%d(动%d)" % (
                name, info["layer"], info["static_in_count"], info["dynamic_in_count"],
                ext_text, len(info["static_out"]), len(info["dynamic_out"])))
            if args.json:
                print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    _print_summary(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
