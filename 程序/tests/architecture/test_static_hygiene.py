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
import unittest
import warnings
from pathlib import Path

from tests.architecture._scan import ROOT, production_runtime_files

# 非本仓维护目录：字节码缓存、Git 元数据、历史记录、外包技能包、离线 ASR 运行时 venv。
_EXCLUDED_PARTS = frozenset({"__pycache__", ".git", "维护记录", "tasks_round", "skills",
                             "voice_asr_venv"})


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

    def test_scan_scope_excludes_runtime_asr_venv(self) -> None:
        """`data/voice_asr_venv/` 是离线 ASR 运行时创建的第三方 venv（约 7700 个 .py），
        不属本仓自有代码，不得计入静态卫生扫描（R2990 合并阻断修复）。"""
        self.assertIn("voice_asr_venv", _EXCLUDED_PARTS,
                      "静态卫生必须显式排除离线 ASR 运行时 venv")
        leaked = [path.relative_to(ROOT).as_posix() for path in _all_sources()
                  if "voice_asr_venv" in path.relative_to(ROOT).parts]
        self.assertEqual(leaked, [], "离线 ASR venv 不得计入本仓静态卫生扫描范围")

if __name__ == "__main__":
    unittest.main()