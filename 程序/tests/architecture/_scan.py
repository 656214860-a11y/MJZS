"""仅以 AST 读取程序根目录生产模块的架构扫描辅助函数。"""
from __future__ import annotations
import ast
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[2]
_EXCLUDED_STEMS = frozenset({"smoke_test", "run_selftests", "selftest_sandbox"})

# 递归生产模块口径（R922／R1381 起确立）：覆盖 batch_frames_tool／agent／scripts 等子目录；
# 测试、轮次记录、维护记录与字节码缓存不参与生产门禁。
EXCLUDED_PARTS = frozenset({"tests", "tasks_round", "维护记录", ".git", "__pycache__"})


def production_files_recursive() -> tuple[Path, ...]:
    """返回递归生产 Python 文件，供用户可见入口门禁核对子目录模块。

    与 `production_files()` 同口径：仍排除自检器（smoke_test／run_selftests／
    selftest_sandbox）与以 `test` 开头的文件，只是把扫描范围扩到子目录。
    """
    return tuple(sorted(path for path in ROOT.rglob("*.py")
                        if not any(part in EXCLUDED_PARTS
                                   for part in path.relative_to(ROOT).parts)
                        and path.stem not in _EXCLUDED_STEMS
                        and not path.stem.startswith("test")))


def production_files() -> tuple[Path, ...]:
    """返回程序根目录的生产 Python 文件，不递归扫描子目录。"""
    return tuple(sorted(path for path in ROOT.glob("*.py")
                        if not path.stem.startswith("test") and path.stem not in _EXCLUDED_STEMS))

def module_name(path: Path) -> str:
    return path.stem

def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

def import_rows(path: Path) -> Iterator[tuple[int, str]]:
    """产出顶层导入包名及行号，供分层和环依赖检查复用。"""
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name.split(".", 1)[0]
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.lineno, node.module.split(".", 1)[0]

def imports_of(path: Path) -> frozenset[str]:
    return frozenset(name for _, name in import_rows(path))
