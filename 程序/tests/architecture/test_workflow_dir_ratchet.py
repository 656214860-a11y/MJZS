"""项目内 `工作流任务` 目录名只许越写越少：路径应由路径权威产出，不在各模块手拼（AGENTS §2.3 第 12 条）。

R1854 登记：`stage_layout`／`stage_path_service` 至今没有这个目录的入口，它散落在下面这些模块里，
有的拼写入路径（交互任务、回收站、白模批量），有的拿它做跳过判断。登记值是每个模块里
含该名称的字符串常量个数（不计 docstring），只许下降；降到 0 的模块必须从登记表删除，
新模块出现即红。收口时在路径权威里加入口，再逐模块改用。
"""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from tests.architecture._scan import ROOT, parse, production_runtime_files

DIR_NAME = '工作流任务'
AUTHORITY = 'stage_layout.py'      # 路径权威自己产出该目录名（R2260 J22），不计入棘轮
REGISTERED = {
    'download_inbox.py': 1,
    'previs_automation.py': 1,
    'previs_batch_service.py': 1,
    'previs_routing.py': 2,
    'projects.py': 4,
    'qwen_adapter.py': 2,
    'shot_numbering.py': 3,
    'skill_budget.py': 1,
    'skill_tools.py': 1,
    'stage_download_inbox_service.py': 1,
    'storage_maintenance.py': 1,
    'storyboard_recycle_service.py': 2,
    'white_model_service.py': 1,
    'workflow_engines.py': 4,
}


def _count(path: Path) -> int:
    tree = parse(path)
    docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                  if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                  and node.body and isinstance(node.body[0], ast.Expr)
                  and isinstance(node.body[0].value, ast.Constant)}
    return sum(1 for node in ast.walk(tree)
               if isinstance(node, ast.Constant) and isinstance(node.value, str)
               and DIR_NAME in node.value and id(node) not in docstrings)


class WorkflowDirRatchetTests(unittest.TestCase):
    def test_hand_built_workflow_dir_only_shrinks(self):
        counts = {}
        for path in production_runtime_files():
            found = _count(path)
            if found and path.name != AUTHORITY:
                counts[path.relative_to(ROOT).as_posix()] = found
        bad = ['%s: %d 处 > 登记 %d 处' % (name, actual, REGISTERED.get(name, 0))
               for name, actual in sorted(counts.items()) if actual > REGISTERED.get(name, 0)]
        bad += ['%s: 已无手拼，请从登记表删除' % name for name in sorted(set(REGISTERED) - set(counts))]
        self.assertEqual(bad, [], '“工作流任务”路径请由路径权威产出，不要新增手拼：' + '; '.join(bad))

    def test_counter_ignores_docstrings_and_counts_path_parts(self):
        with tempfile.TemporaryDirectory() as folder:
            sample = Path(folder) / 'sample.py'
            sample.write_text('"""写到 工作流任务 下。"""\n'
                              "A = ('工作流任务', 'x')\n"
                              "def f(p):\n    '''工作流任务'''\n    return p / '工作流任务/交互任务'\n",
                              encoding='utf-8')
            self.assertEqual(_count(sample), 2)


if __name__ == '__main__':
    unittest.main()
