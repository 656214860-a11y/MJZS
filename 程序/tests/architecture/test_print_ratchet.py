"""生产模块的 print() 只许减少：运行期诊断统一走 app_logging。

R1610 J 第三批 Q9 的后半（R1623 落地）：桌面程序在 pythonw 下 ``sys.stdout`` 为 None，
``print`` 是静默空操作，诊断信息直接丢失；运行期诊断必须经 ``logging``
（``app_logging`` 已在启动时装好 ``logs/app.log`` 的文件处理器，并做脱敏）。

本门禁只登记「本来就是往控制台说话」的入口，其余生产模块出现 ``print`` 即失败：

- 命令行工具（自己就是 console 程序）：``engine_probe``、``shot_numbering``、
  ``workspace_maintenance``、``log_maintenance``、``exit_maintenance``、``app_icon``、
  ``app_shortcut``、``asset_thumbs``（``--worker`` 用法行）；
- 子进程协议：``image_agent_runner``（stdout 是与父进程的 IPC 通道，不是诊断）；
- 控制台提交工具：``console_submit``；
- 双通道播报：``broadcaster``（既 print 给调用端，又写 ``sanhu_progress.log``）。

登记值只许下降；降到 0 的文件必须从登记表删除。
"""
import ast
import unittest

from tests.architecture._scan import module_scan_files

CONSOLE_ENTRIES = {
    'app_icon.py': 2,
    'app_shortcut.py': 3,
    'asset_thumbs.py': 1,
    'broadcaster.py': 1,
    'console_submit.py': 1,
    'engine_probe.py': 9,
    'exit_maintenance.py': 1,
    'image_agent_runner.py': 4,
    'log_maintenance.py': 1,
    'shot_numbering.py': 4,
    'workspace_maintenance.py': 4,
    # R3246 轮 2：agent/ 入分层包扫描后登记。optimizer_mcp_bridge 的 stdout 是
    # MCP stdio 协议通道（与 image_agent_runner 同类）；voice_mcp_server 只写
    # stderr 会话清理诊断，MCP 子进程内 app_logging 未装配。
    'optimizer_mcp_bridge.py': 2,
    'voice_mcp_server.py': 1,
}


def _print_counts():
    counts = {}
    for path in module_scan_files():
        tree = ast.parse(path.read_text(encoding='utf-8', errors='replace'), filename=str(path))
        found = sum(1 for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == 'print')
        if found:
            counts[path.name] = found
    return counts


def _call_sites():
    sites = []
    for path in module_scan_files():
        tree = ast.parse(path.read_text(encoding='utf-8', errors='replace'), filename=str(path))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == 'print'):
                sites.append((path.name, node.lineno))
    return sites


class PrintRatchet(unittest.TestCase):
    def test_no_print_outside_registered_console_entries(self):
        stray = sorted(f'{name}:{line}' for name, line in _call_sites()
                       if name not in CONSOLE_ENTRIES)
        self.assertEqual(
            stray, [],
            '运行期诊断请走 logging（app_logging），即 app.log；只有登记的控制台入口可以 print')

    def test_registered_entries_only_shrink(self):
        counts = _print_counts()
        bad = []
        for name, allowed in sorted(CONSOLE_ENTRIES.items()):
            actual = counts.get(name, 0)
            if actual > allowed:
                bad.append(f'{name}: {actual} 处 > 登记 {allowed} 处')
            elif actual == 0:
                bad.append(f'{name}: 已无 print，请从登记表删除')
        self.assertEqual(bad, [])


if __name__ == '__main__':
    unittest.main()