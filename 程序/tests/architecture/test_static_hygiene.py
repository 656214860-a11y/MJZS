"""静态卫生门禁：无效转义序列、星号导入、生产内建 eval／exec。

本项目零运行时依赖、不装第三方 lint，这三类是 AST／编译期可确定、误报极低、
且未来 Python 版本会升级为硬错误的类别，故固化为架构门禁（R1611／Q1）。
刻意不做"未用导入"等易误报项，避免把说明性代码误判为缺陷。

扫描范围只含本仓自有的 .py：`skills/` 是独立版本化的外部技能包（含 git 子模块），
`data/voice_asr_venv/` 是离线 ASR 运行时按需创建的第三方 venv（pip 装出的
jieba/_yaml/cffi 等，约 7700 个 .py），都不属本仓维护；其它嵌套仓库同理跳过，
避免既检测不属自己的代码、又无法提交修复。
"""
from __future__ import annotations

import ast
import importlib.util
import unittest
import warnings
from pathlib import Path

from tests.architecture import _scan
from tests.architecture._scan import NON_CODE_EXCLUDED_PARTS, ROOT, production_runtime_files

# 非本仓维护目录：复用 _scan.NON_CODE_EXCLUDED_PARTS（保留 tests/ 扫描），另排除外包技能包。
_EXCLUDED_PARTS = NON_CODE_EXCLUDED_PARTS | frozenset({"skills"})


def _nested_repo_dirs() -> frozenset[Path]:
    """返回 ROOT 内所有嵌套 Git 仓库的根目录（含子模块 working tree）。"""
    return frozenset(marker.parent for marker in ROOT.rglob(".git"))


def _all_sources() -> list[Path]:
    nested = _nested_repo_dirs()
    out = []
    for path in sorted(ROOT.rglob("*.py")):
        if _EXCLUDED_PARTS.intersection(path.relative_to(ROOT).parts):
            continue
        if any(root in path.parents for root in nested):
            continue
        out.append(path)
    return out


def _parse_lenient(path: Path) -> ast.Module | None:
    """容错解析：语法错误由逃逸／语法用例统一报告，这里不重复报。"""
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return None


_SUBPROCESS_CAPTURE_FUNCS = frozenset({"run", "call", "check_call", "check_output", "Popen"})
_TEXT_KWARGS = frozenset({"text", "universal_newlines"})


def _tool_script_files() -> list[Path]:
    """工具脚本三处范围（程序根、scripts/、维护记录/基准脚本/），不递归子目录。"""
    files = list(ROOT.glob("*.py"))
    files += (ROOT / "scripts").glob("*.py")
    files += (ROOT / "维护记录" / "基准脚本").glob("*.py")
    return sorted(files)


def _subprocess_bindings(tree: ast.Module) -> tuple[frozenset[str], frozenset[str]]:
    """返回（subprocess 模块别名集, from subprocess import 绑定的捕获函数名集）。"""
    modules = {"subprocess"}
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.asname or alias.name for alias in node.names
                           if alias.name == "subprocess")
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            for alias in node.names:
                if alias.name == "*":
                    names |= set(_SUBPROCESS_CAPTURE_FUNCS)
                elif alias.name in _SUBPROCESS_CAPTURE_FUNCS:
                    names.add(alias.asname or alias.name)
    return frozenset(modules), frozenset(names)


def _is_subprocess_capture_call(node: ast.Call, modules, names) -> bool:
    func = node.func
    if isinstance(func, ast.Attribute):
        return (func.attr in _SUBPROCESS_CAPTURE_FUNCS and isinstance(func.value, ast.Name)
                and func.value.id in modules)
    return isinstance(func, ast.Name) and func.id in names


def _captures_text_without_encoding(node: ast.Call) -> bool:
    """text=True／universal_newlines=True 捕获文本却没显式 encoding。"""
    captures = any(kw.arg in _TEXT_KWARGS and isinstance(kw.value, ast.Constant)
                   and kw.value.value is True for kw in node.keywords)
    return captures and not any(kw.arg == "encoding" for kw in node.keywords)


class StaticHygieneTests(unittest.TestCase):
    def test_no_invalid_escape_sequences(self) -> None:
        offenders = []
        for path in _all_sources():
            rel = path.relative_to(ROOT).as_posix()
            try:
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    compile(path.read_text(encoding="utf-8", errors="replace"), str(path), "exec")
                    offenders += ["%s:%d %s" % (rel, w.lineno, w.message)
                                  for w in caught if issubclass(w.category, SyntaxWarning)]
            except SyntaxError as error:
                offenders.append("%s:%s 语法错误：%s" % (rel, error.lineno, error.msg))
        self.assertEqual(offenders, [],
                         "无效转义序列未来会变成 SyntaxError，请改用原始字符串或双反斜杠")

    def test_no_star_imports(self) -> None:
        offenders = []
        for path in _all_sources():
            tree = _parse_lenient(path)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
                    offenders.append("%s:%d" % (path.relative_to(ROOT).as_posix(), node.lineno))
        self.assertEqual(offenders, [], "禁止 from ... import *：污染命名空间并妨碍静态分析")

    def test_no_builtin_eval_or_exec_in_production(self) -> None:
        offenders = []
        for path in production_runtime_files():
            tree = _parse_lenient(path)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id in ("eval", "exec")):
                    offenders.append("%s:%d %s" % (path.relative_to(ROOT).as_posix(),
                                                   node.lineno, node.func.id))
        self.assertEqual(offenders, [], "生产运行时代码禁止内建 eval/exec；确需请登记并说明理由")


    def test_scan_scope_excludes_non_maintained_skill_packages(self) -> None:
        """`skills/` 是独立版本化的外部技能包，显式排除在本仓静态卫生范围之外（R1649）。

        门禁绿只代表本仓自有的 .py 无此类问题：曾经存在的
        `skills/.../short-drama-director/scripts/check_package.py` 无效转义已在 R1649 修复，
        但 skills/ 下的文件不受本门禁保护，不能把「绿」读成「全仓无此问题」。
        """
        self.assertIn("skills", _EXCLUDED_PARTS, "静态卫生必须显式排除外部技能包")
        leaked = [path.relative_to(ROOT).as_posix() for path in _all_sources()
                  if "skills" in path.relative_to(ROOT).parts]
        self.assertEqual(leaked, [], "外部技能包不得计入本仓静态卫生扫描范围")

    def test_tool_scripts_decode_subprocess_text_as_utf8(self) -> None:
        """R2-G3 T2：工具脚本捕获子进程文本必须显式 encoding。

        本机默认编码 cp936，git／ffmpeg 等输出 UTF-8；text=True 不指定 encoding 时
        读线程抛 UnicodeDecodeError、stdout 变 None，领号与合入工具静默丢数据。"""
        offenders = []
        for path in _tool_script_files():
            tree = _parse_lenient(path)
            if tree is None:
                continue
            modules, names = _subprocess_bindings(tree)
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call)
                        and _is_subprocess_capture_call(node, modules, names)
                        and _captures_text_without_encoding(node)):
                    offenders.append("%s:%d" % (path.relative_to(ROOT).as_posix(), node.lineno))
        self.assertEqual(offenders, [],
                         "捕获子进程文本（text=True）必须显式 encoding=\"utf-8\"")

    def test_scan_scope_excludes_runtime_asr_venv(self) -> None:
        """`data/voice_asr_venv/` 是离线 ASR 运行时创建的第三方 venv（约 7700 个 .py），
        不属本仓自有代码，不得计入静态卫生扫描（R2990 合并阻断修复）。"""
        self.assertIn("voice_asr_venv", _EXCLUDED_PARTS,
                      "静态卫生必须显式排除离线 ASR 运行时 venv")
        leaked = [path.relative_to(ROOT).as_posix() for path in _all_sources()
                  if "voice_asr_venv" in path.relative_to(ROOT).parts]
        self.assertEqual(leaked, [], "离线 ASR venv 不得计入本仓静态卫生扫描范围")


_ALLOWED_VOICE_LITERAL_FUNCS = frozenset({
    ("tests/architecture/test_static_hygiene.py", "test_scan_scope_excludes_runtime_asr_venv"),
    ("tests/architecture/test_static_hygiene.py", "test_scan_defines_composable_single_source_exclude_sets"),
    ("tests/architecture/test_static_hygiene.py", "_duplicate_exclude_violations"),
})


def _enclosing_func_name(tree: ast.AST, target: ast.AST) -> str | None:
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    current = parents.get(target)
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current.name
        current = parents.get(current)
    return None


def _duplicate_exclude_violations(path: Path) -> list[str]:
    tree = _scan.parse(path)
    rel = path.relative_to(ROOT).as_posix()
    shared_markers = NON_CODE_EXCLUDED_PARTS - {"logs", "data", "outputs"}
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == "voice_asr_venv":
            if (rel, _enclosing_func_name(tree, node)) not in _ALLOWED_VOICE_LITERAL_FUNCS:
                violations.append(f"{rel}:{node.lineno}: 硬编码 'voice_asr_venv'，应引用 _scan 排除集合")
        elif isinstance(node, (ast.Set, ast.List, ast.Tuple)):
            strings = {
                elt.value for elt in node.elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
            }
            overlap = strings & shared_markers
            if len(overlap) >= 3:
                violations.append(
                    f"{rel}:{node.lineno}: 重复定义排除目录字面量 {sorted(overlap)}，应引用 _scan 排除集合"
                )
    return violations


class ScanExcludesSingleSourceTests(unittest.TestCase):
    """C17：扫描排除集合单一来源门禁，禁止各架构门禁与覆盖率脚本重复手写排除目录。"""

    def test_scan_defines_composable_single_source_exclude_sets(self) -> None:
        self.assertIn("voice_asr_venv", _scan.NON_CODE_EXCLUDED_PARTS)
        self.assertNotIn("tests", _scan.NON_CODE_EXCLUDED_PARTS)
        self.assertEqual(_scan.EXCLUDED_PARTS, _scan.NON_CODE_EXCLUDED_PARTS | frozenset({"tests"}))

    def test_architecture_tests_and_coverage_script_do_not_duplicate_exclude_sets(self) -> None:
        files = [
            path for path in sorted((ROOT / "tests" / "architecture").glob("*.py"))
            if path.name != "_scan.py"
        ]
        files.append(ROOT / "scripts" / "coverage_report.py")
        violations: list[str] = []
        for path in files:
            violations.extend(_duplicate_exclude_violations(path))
        self.assertEqual(
            violations,
            [],
            "扫描排除集合必须统一引用 tests/architecture/_scan.py，发现重复定义：\n"
            + "\n".join(violations),
        )

    def test_coverage_report_reuses_scan_exclude_sets_and_runtime_scope(self) -> None:
        coverage_script = ROOT / "scripts" / "coverage_report.py"
        spec = importlib.util.spec_from_file_location("coverage_report_single_source", coverage_script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertIs(module.EXCLUDED_PARTS, _scan.EXCLUDED_PARTS)
        self.assertIs(module.NON_PRODUCT_PARTS, _scan.NON_PRODUCT_PARTS)
        self.assertIs(module.SKIP_STEMS, _scan._EXCLUDED_STEMS)
        self.assertEqual(module.production_modules(), _scan.production_runtime_files())


if __name__ == "__main__":
    unittest.main()