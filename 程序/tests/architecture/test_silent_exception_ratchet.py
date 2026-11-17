"""生产代码不得再出现 ``except Exception: pass``：吞异常必须经 ``app_logging.swallowed()`` 留痕。

只管最宽的 ``Exception``；``tk.TclError``、``queue.Empty``、``OSError`` 等窄异常的静默处理
属于预期控制流，不在此列。登记表里的文件是已知例外（日志基础设施自身不能递归记日志、
开发脚本和 agent 子包），只允许数量下降。
"""
import ast
import unittest
from pathlib import Path

from tests.architecture._scan import PACKAGE_NAMES

PROGRAM = Path(__file__).resolve().parents[2]
# R2600（T5 核销）：run_selftests、smoke_test、scripts/auto_full_safe 已改经
# app_logging.swallowed() 留痕；扫描面同步扩到 scripts/。剩余登记位：
# app_logging 自身（日志基建不能递归记日志）与 agent/volcengine（agent 子包
# 不引 app_logging，且错误路径随后仍 raise）。
# platform_tools（R2669）：底层平台适配引 app_logging 构成越层（test_layers 实证），
# 流式回调失败按注释语义降噪豁免一处。T10 包化后实体在 contract/ 下。
ALLOWED = {
    'infra/app_logging.py': 10,
    'agent/volcengine.py': 1,
    'contract/platform_tools.py': 1,
}


def _scanned_files():
    files = list(PROGRAM.glob('*.py'))
    files += list((PROGRAM / 'agent').rglob('*.py'))
    files += list((PROGRAM / 'scripts').glob('*.py'))
    for package in PACKAGE_NAMES:
        directory = PROGRAM / package
        if directory.is_dir():
            files += list(directory.rglob('*.py'))
    return files


def silent_exception_sites():
    found = {}
    for path in _scanned_files():
        tree = ast.parse(path.read_text(encoding='utf-8', errors='replace'))
        rows = [n.lineno for n in ast.walk(tree)
                if isinstance(n, ast.ExceptHandler) and n.type is not None
                and ast.unparse(n.type) == 'Exception'
                and len(n.body) == 1 and isinstance(n.body[0], ast.Pass)]
        if rows:
            found[path.relative_to(PROGRAM).as_posix()] = rows
    return found


class SilentExceptionRatchet(unittest.TestCase):
    def test_no_new_silent_exception_handlers(self):
        problems = []
        for name, rows in silent_exception_sites().items():
            allowed = ALLOWED.get(name, 0)
            if len(rows) > allowed:
                problems.append(f'{name}: {len(rows)} 处（登记 {allowed}），行 {rows}')
        self.assertEqual(problems, [], '请改用 app_logging.swallowed()，不要新增 except Exception: pass')

    def test_allowlist_has_no_stale_entries(self):
        found = silent_exception_sites()
        stale = [n for n, cap in ALLOWED.items() if len(found.get(n, ())) < cap]
        self.assertEqual(stale, [], '登记数量高于实际，请同步下调')

    def test_no_bare_except_anywhere(self):
        bare = {}
        for path in _scanned_files():
            tree = ast.parse(path.read_text(encoding='utf-8', errors='replace'))
            rows = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler) and n.type is None]
            if rows:
                bare[path.relative_to(PROGRAM).as_posix()] = rows
        self.assertEqual(bare, {}, '禁止裸 except:（会吞掉 KeyboardInterrupt／SystemExit），至少写 except Exception')

    def test_swallowed_helper_is_used_widely(self):
        hits = sum(p.read_text(encoding='utf-8', errors='replace').count('app_logging.swallowed()')
                   for p in _scanned_files())
        self.assertGreaterEqual(hits, 100)


if __name__ == '__main__':
    unittest.main()
