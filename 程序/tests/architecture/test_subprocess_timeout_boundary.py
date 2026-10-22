"""生产代码等子进程必须带 timeout：CLI 卡住时不能一直占着阶段槽位或界面线程。

R1853 修了 `workflow_engines`／`qwen_adapter` 的无超时 `communicate()` 与 `codex_tasks` 的无超时
`wait()`；R1854 把它变成门禁。登记时生产运行时代码里已无违规，登记表为空，只许保持为空。

识别口径（AST）：
- `subprocess.run／call／check_call／check_output(...)` 没有 `timeout=`；
- 任何 `.communicate(...)` 没有 `timeout=`；
- 任何零参数、无 `timeout=` 的 `.wait()`（`Popen.wait()`；`Event.wait()` 不带参数同样会永久阻塞）。
"""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from tests.architecture._scan import ROOT, parse, production_runtime_files

_SUBPROCESS_WAITERS = frozenset({'run', 'call', 'check_call', 'check_output'})
# 登记格式 {相对路径: 处数}；只许减少，降到 0 必须删除。
_REGISTERED: dict[str, int] = {}


def _is_untimed_wait(call: ast.Call) -> bool:
    func = call.func
    if not isinstance(func, ast.Attribute) or any(k.arg == 'timeout' for k in call.keywords):
        return False
    if func.attr in _SUBPROCESS_WAITERS:
        return isinstance(func.value, ast.Name) and func.value.id == 'subprocess'
    if func.attr == 'communicate':
        return True
    return func.attr == 'wait' and not call.args and not call.keywords


def _sites(path: Path) -> list[int]:
    return sorted(node.lineno for node in ast.walk(parse(path))
                  if isinstance(node, ast.Call) and _is_untimed_wait(node))


class SubprocessTimeoutBoundaryTests(unittest.TestCase):
    def test_production_waits_carry_timeout(self):
        bad = []
        seen = set()
        for path in production_runtime_files():
            name = path.relative_to(ROOT).as_posix()
            lines = _sites(path)
            if not lines:
                continue
            seen.add(name)
            if len(lines) > _REGISTERED.get(name, 0):
                bad.append('%s:%s' % (name, ','.join(map(str, lines))))
        bad.extend('%s: 已无违规，请从登记表删除' % name for name in sorted(set(_REGISTERED) - seen))
        self.assertEqual(bad, [], '等子进程请带 timeout=，超时后结束进程树（platform_tools.communicate_or_kill）：'
                         + '; '.join(bad))

    def test_detector_catches_each_untimed_form(self):
        source = ('import subprocess\n'
                  'subprocess.run(cmd)\n'
                  'subprocess.check_output(cmd)\n'
                  'process.communicate(data)\n'
                  'process.wait()\n'
                  'subprocess.run(cmd, timeout=5)\n'
                  'process.communicate(data, timeout=5)\n'
                  'process.wait(timeout=3)\n'
                  'stop.wait(1)\n'
                  'asyncio.run(main())\n')
        with tempfile.TemporaryDirectory() as folder:
            sample = Path(folder) / 'sample.py'
            sample.write_text(source, encoding='utf-8')
            self.assertEqual(_sites(sample), [2, 3, 4, 5])


if __name__ == '__main__':
    unittest.main()
