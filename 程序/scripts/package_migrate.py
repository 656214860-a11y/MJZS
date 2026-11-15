"""T10 包化搬家工具：git mv + 同名薄门面 + 生产侧 import 改写为包路径。

只做机械搬家，不改产品行为：
- ``git mv <mod>.py <pkg>/<mod>.py``（保留历史）；
- 顶层留同名门面 ``from <pkg>.<mod> import *``（与旧扁平模块导出面一致）；
- 生产运行时文件里的 ``import <mod>``／``from <mod> import`` 改写为包路径；
  tests／scripts／维护记录 等不在 ``production_runtime_files()`` 口径内，
  继续按扁平名命中门面（与用户拍板的测试口径一致）；
- 动态字符串（``import_module('<mod>')``、注册表字面量）只报告不改，
  由轮次人工核对 ``ui_plugin_registry``／``stage_handler_registry`` 等。

用法（工作目录＝程序）：
  python -B scripts/package_migrate.py --package contract --modules model_protocol script_brief ...
  python -B scripts/package_migrate.py --package contract --modules ... --dry-run
"""
from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))
from tests.architecture._scan import production_runtime_files  # noqa: E402


def _git(*args: str) -> None:
    subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=PROGRAM, check=True)


def _bound_names(tree: ast.Module) -> set[str]:
    """收集模块顶层绑定的公开名（近似 ``import *`` 的导出面；__all__ 优先）。"""
    for node in tree.body:
        if (isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)
                and isinstance(node.value, (ast.List, ast.Tuple))):
            return {e.value for e in node.value.elts
                    if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    names: set[str] = set()

    def targets_of(target):
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                targets_of(element)
        elif isinstance(target, ast.Starred):
            targets_of(target.value)

    def scan(stmts):
        for node in stmts:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    targets_of(target)
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets_of(node.target)
            elif isinstance(node, ast.AugAssign):
                targets_of(node.target)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module == "__future__":
                    continue
                for alias in node.names:
                    if alias.name != "*":
                        names.add(alias.asname or alias.name)
            elif isinstance(node, (ast.If, ast.While)):
                scan(node.body)
                scan(node.orelse)
            elif isinstance(node, ast.Try):
                scan(node.body)
                scan(node.orelse)
                scan(node.finalbody)
                for handler in node.handlers:
                    scan(handler.body)
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                targets_of(node.target)
                scan(node.body)
                scan(node.orelse)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    if item.optional_vars is not None:
                        targets_of(item.optional_vars)
                scan(node.body)

    scan(tree.body)
    return {name for name in names if not name.startswith("_")}


def _imported_modules(tree: ast.Module) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def migrate(package: str, modules: list[str], dry_run: bool = False) -> int:
    pkg_dir = PROGRAM / package
    moved, facades, rewritten, dyn_hits = [], [], [], []
    targets = set(modules)

    # 1) 校验：顶层 .py 存在、未重复搬家
    for mod in modules:
        if not (PROGRAM / f"{mod}.py").is_file():
            print(f"!! 缺少顶层模块 {mod}.py", file=sys.stderr)
            return 2
        if (pkg_dir / f"{mod}.py").exists():
            print(f"!! {package}/{mod}.py 已存在", file=sys.stderr)
            return 2

    # 2) 动态字符串预检（搬家前扫，搬家后字面量仍在）
    for path in production_runtime_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        tree = None
        for mod in modules:
            for match in re.finditer(rf"""['"]{re.escape(mod)}['"]""", text):
                line = text.count("\n", 0, match.start()) + 1
                dyn_hits.append(f"{path.relative_to(PROGRAM).as_posix()}:{line}: '{mod}'")

    if dry_run:
        print(f"[dry-run] 将搬 {len(modules)} 个模块 → {package}/")
        for hit in dyn_hits:
            print("  动态引用:", hit)
        return 0

    # 3) 建包与 __init__.py（只放 docstring，不再导出）
    pkg_dir.mkdir(exist_ok=True)
    init = pkg_dir / "__init__.py"
    if not init.exists():
        init.write_text(f'"""T10 包化：{package} 包（分层见 architecture.md 第 3 节）。"""\n',
                        encoding="utf-8")
        _git("add", "--", str(init.relative_to(PROGRAM)))

    # 4) git mv + 门面（显式再导出，test_no_star_imports 禁止 import *）
    for mod in modules:
        _git("mv", f"{mod}.py", f"{package}/{mod}.py")
        moved.append(f"{package}/{mod}.py")
        facade = PROGRAM / f"{mod}.py"
        tree = ast.parse((pkg_dir / f"{mod}.py").read_text(encoding="utf-8"))
        names = sorted(_bound_names(tree))
        body = (f'"""历史入口：实体已迁至 ``{package}.{mod}``（T10 包化）。\n\n'
                '测试与未改写的消费方仍按扁平名导入；生产侧一律用包路径。\n'
                '门面清除轮统一改写测试导入后删除本文件。\n"""\n'
                f"from {package}.{mod} import (\n")
        body += "".join(f"    {name},\n" for name in names)
        body += ")\n"
        facade.write_text(body, encoding="utf-8")
        facades.append(f"{mod}.py")

    # 5) 生产侧 import 改写：先 AST 定位真实 import 的文件，再行级正则改写
    for path in production_runtime_files():
        rel = path.relative_to(PROGRAM).as_posix()
        if rel.startswith(f"{package}/") and rel.count("/") == 1:
            pass  # 包内文件同样要改写（它们可能 import 本批其他模块）
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text)
        except (SyntaxError, UnicodeDecodeError):
            continue
        imported = _imported_modules(tree)
        hits = targets & {name.split(".")[0] for name in imported}
        hits |= {name for name in imported if name in targets}
        if not hits:
            continue
        new = text
        for mod in sorted(hits, key=len, reverse=True):
            pkg_mod = f"{package}.{mod}"
            new = re.sub(rf"(?m)^([ \t]*)from {re.escape(mod)} import\b",
                         rf"\1from {pkg_mod} import", new)
            # ``import mod`` 原绑定名是 mod；改写成 ``import pkg.mod as mod``
            # 才保持 ``mod.attr`` 可用（裸 ``import pkg.mod`` 会绑定 pkg）。
            new = re.sub(
                rf"(?m)^([ \t]*)import {re.escape(mod)}(?![\w.])(\s+as\s+(\w+))?",
                lambda m: f"{m.group(1)}import {pkg_mod} as {m.group(4) or mod}",
                new)
        if new != text:
            ast.parse(new)  # 改写后语法自检
            path.write_text(new, encoding="utf-8")
            rewritten.append(rel)

    # 6) 汇总
    print(f"搬家 {len(moved)} 个模块 → {package}/")
    for item in moved:
        print("  mv", item)
    print(f"门面 {len(facades)} 个")
    print(f"改写 import 的生产文件 {len(rewritten)} 个")
    for item in rewritten:
        print("  rw", item)
    if dyn_hits:
        print(f"!! 动态字符串引用 {len(dyn_hits)} 处，需人工核对：")
        for hit in dyn_hits:
            print("  ", hit)
    return 0


def fix_facades(package: str) -> int:
    """把 ``from <pkg>.<mod> import *`` 薄门面改写为显式再导出（test_no_star_imports）。"""
    pkg_dir = PROGRAM / package
    fixed = []
    star = re.compile(rf"from {re.escape(package)}\.(\w+) import \*")
    for path in sorted(PROGRAM.glob("*.py")):
        if path.name.startswith(("test", "smoke_test", "run_selftests")):
            continue
        text = path.read_text(encoding="utf-8")
        match = star.search(text)
        if not match:
            continue
        mod = match.group(1)
        tree = ast.parse((pkg_dir / f"{mod}.py").read_text(encoding="utf-8"))
        names = sorted(_bound_names(tree))
        head = text[:match.start()]
        tail = text[match.end():]
        body = head
        body += f"from {package}.{mod} import (\n"
        body += "".join(f"    {name},\n" for name in names)
        body += ")" + tail
        ast.parse(body)
        path.write_text(body, encoding="utf-8")
        fixed.append(path.name)
    print(f"门面改写 {len(fixed)} 个：{' '.join(fixed)}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--package", required=True, help="目标包名（contract/infra/domain/orchestrator/ui）")
    parser.add_argument("--modules", nargs="*", default=[], help="顶层模块名（不带 .py）")
    parser.add_argument("--fix-facades", action="store_true", help="把包内星号门面改写为显式再导出")
    parser.add_argument("--dry-run", action="store_true", help="只报告，不改动")
    args = parser.parse_args(argv)
    if args.fix_facades:
        return fix_facades(args.package)
    if not args.modules:
        parser.error("--modules 不能为空（除非 --fix-facades）")
    return migrate(args.package, args.modules, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
