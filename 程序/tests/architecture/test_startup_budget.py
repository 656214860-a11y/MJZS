"""启动链不得重新在 Tk 主线程递归扫描目录。"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

from tests.architecture._scan import entity_file


ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_DIRECTORY_CALLS = frozenset({'rglob', 'glob', 'walk'})
STARTUP_CHAIN = {
    'app.py': (None, ('<module>',)),
    'desktop.py': ('Desktop', ('__init__', 'load')),
    'desktop_page_nav.py': ('PageNavMixin', ('show',)),  # 自 desktop.py 迁出，仍在启动链上，照样受检
    # R1505：choose_project 原样迁到 ProjectPagesMixin，仍在启动链上，照样受检。
    'desktop_project_pages.py': ('ProjectPagesMixin', ('choose_project',)),
    # R1499：writing（剧本准备页构建）原样迁到 WritingPageMixin，仍在启动链上，照样受检。
    'desktop_writing_page.py': ('WritingPageMixin', ('writing',)),
    'projects.py': ('Projects', ('__init__', 'refresh_registry')),
    'pet_ui.py': (None, ('attach', 'watch_status', 'start')),
    # 轮 3B：建 Tk 前的启动自检同属启动链——乙类检查与崩溃预算入口一并受检，
    # 自检期间禁止 rglob/glob/walk（任务书 D3-n②，运行期计数见 test_startup_selfcheck）。
    'diagnostic_capture.py': (None, (
        'run_startup_selfcheck', 'startup_checks', 'startup_guard', 'startup_gate',
        'record_startup_ready', 'record_startup_closed',
        '_check_data_writable', '_check_disk_space', '_check_model_pool',
        '_check_bundled_tools', '_check_dependency_lock', '_check_settings_corrupt',
        '_installed_distributions', '_parse_dependency_lock',
    )),
}


def _function_nodes(path: Path, class_name: str | None, names: tuple[str, ...]):
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    if names == ('<module>',):
        return (tree,)
    scope = tree
    if class_name is not None:
        scope = next(node for node in tree.body
                     if isinstance(node, ast.ClassDef) and node.name == class_name)
    return tuple(node for node in scope.body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names)


def _directory_calls(nodes):
    calls = []
    for node in nodes:
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                if child.func.attr in FORBIDDEN_DIRECTORY_CALLS:
                    calls.append('%s:%d %s()' % (node.filename, child.lineno, child.func.attr))
    return calls


class StartupBudgetTests(unittest.TestCase):
    def test_startup_call_chain_never_recursively_scans_directories(self) -> None:
        """R538：自动打开项目之前必须把主线程还给 Tk，而非同步扫描目录。"""
        violations = []
        for filename, (class_name, names) in STARTUP_CHAIN.items():
            nodes = _function_nodes(entity_file(Path(filename).stem), class_name, names)
            self.assertEqual(len(nodes), len(names), '启动函数缺失，需更新本门禁：' + filename)
            violations.extend(_directory_calls(nodes))
        self.assertEqual(violations, [], '启动调用链禁止 rglob/glob/walk：' + '; '.join(violations))
