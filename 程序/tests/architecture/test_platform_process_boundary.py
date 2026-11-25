"""P2：可见本地程序必须经平台启动边界，后台进程只能出现在受控模块。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import module_scan_files, parse


_BACKGROUND_BOUNDARIES = frozenset({
    'asset_thumbs', 'codex_tasks', 'storage_maintenance',
    'log_maintenance',
})


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f'{parent}.{node.attr}' if parent else None
    return None


class PlatformProcessBoundaryTests(unittest.TestCase):
    def test_direct_popen_is_limited_to_platform_or_background_boundaries(self):
        offenders = []
        for path in module_scan_files():
            for node in ast.walk(parse(path)):
                if isinstance(node, ast.Call) and _dotted_name(node.func) == 'subprocess.Popen':
                    if path.stem not in _BACKGROUND_BOUNDARIES | {'platform_tools', 'workflow_process_registry'}:
                        offenders.append(f'{path.name}:{node.lineno}')
        self.assertEqual(
            offenders, [],
            '可见本地程序请改用 platform_tools.launch_windows_app()：\n' + '\n'.join(offenders),
        )

    def test_taskkill_is_limited_to_native_or_platform_adapters(self):
        offenders = []
        for path in module_scan_files():
            for node in ast.walk(parse(path)):
                if not isinstance(node, ast.Call) or _dotted_name(node.func) != 'subprocess.run':
                    continue
                if not node.args or not isinstance(node.args[0], (ast.List, ast.Tuple)) or not node.args[0].elts:
                    continue
                first = node.args[0].elts[0]
                if isinstance(first, ast.Constant) and first.value == 'taskkill' and path.stem not in {'platform_tools', 'native_apps'}:
                    offenders.append(f'{path.name}:{node.lineno}')
        self.assertEqual(offenders, [], 'taskkill 请收敛到平台或本地应用适配器：\n' + '\n'.join(offenders))


# ── I8-4／I9-3：进程启动点门禁 ─────────────────────────────────────────
# 识别四种绕过监督器的写法：``(x or subprocess.Popen)(``、``popen=subprocess.Popen``、
# ``subprocess.run(...)``、``platform_tools.launch_*``（含 from-import 裸名）。
# I9-3：长时/媒体启动点棘轮计数为 0——存量全部归入豁免清单并注明类别，只减不增；
# 平台边界与监督器本体豁免。豁免类别：
#   short_probe        短时探测：同步有界调用且带显式 timeout（I0 短探测口径）；
#   os_operation       OS 操作：快捷方式/文件关联/进程表查询等系统级调用；
#   detached           detached/可见应用：必须脱离宿主或用户可见的启动
#                      （自重启、退出后清理、可见 CLI/桌面应用）；
#   background_boundary 已登记的后台边界模块（自带生命周期管理）。

_LAUNCH_NAMES = frozenset({'launch_background', 'launch_text_process', 'launch_windows_app'})
_PROCESS_EXEMPT_STEMS = frozenset({'platform_tools', 'workflow_process_registry'})

SPAWN_SITE_EXEMPT = {
    'short_probe': frozenset({
        'infra/engine_probe.py:140',
        'infra/native_apps.py:42', 'codex_paste.py:34', 'console_submit.py:14',
        'orchestrator/previs_automation.py:23',
    }),
    'os_operation': frozenset({
        'app_shortcut.py:50', 'app_shortcut.py:114', 'app_shortcut.py:243',
        'infra/native_apps.py:75', 'infra/native_apps.py:87',
    }),
    'detached': frozenset({
        'infra/native_apps.py:124', 'orchestrator/qwen_adapter.py:100',
        'orchestrator/workflow_engines.py:456', 'orchestrator/workflow_engines.py:518',
        'ui/desktop_idea_chat.py:964', 'ui/desktop_idea_chat.py:980',
        'ui/desktop_media_pages.py:834', 'ui/desktop_send_choice.py:54',
        'ui/desktop_tray.py:411', 'infra/log_maintenance.py:141',
        'infra/storage_maintenance.py:50', 'infra/workspace_maintenance.py:384',
    }),
    'background_boundary': frozenset({
        'codex_tasks.py:45',
    }),
}
SPAWN_SITE_BASELINE = frozenset().union(*SPAWN_SITE_EXEMPT.values())


def _is_popen_expr(node: ast.AST) -> bool:
    """表达式是否解析到 ``subprocess.Popen``（含 ``(x or subprocess.Popen)`` 布尔组合）。"""
    if isinstance(node, ast.Attribute) and node.attr == 'Popen' and _dotted_name(node.value) == 'subprocess':
        return True
    if isinstance(node, ast.Name) and node.id == 'Popen':
        return True
    if isinstance(node, ast.BoolOp):
        return any(_is_popen_expr(value) for value in node.values)
    return False


def _spawn_sites_in_tree(tree: ast.AST) -> set:
    """返回源码树中绕过监督器的进程启动调用行号集合（四种写法合一去重）。"""
    hits = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        dotted = _dotted_name(node.func)
        if _is_popen_expr(node.func):
            hits.add(node.lineno)
        for keyword in node.keywords:
            if keyword.arg == 'popen' and _is_popen_expr(keyword.value):
                hits.add(node.lineno)
        if dotted == 'subprocess.run':
            hits.add(node.lineno)
        tail = dotted.rsplit('.', 1)[-1] if dotted else ''
        if tail in _LAUNCH_NAMES:
            hits.add(node.lineno)
    return hits


def _spawn_sites_in_path(path) -> set:
    from tests.architecture._scan import ROOT
    rel = path.resolve().relative_to(ROOT).as_posix()
    return {'%s:%d' % (rel, line) for line in _spawn_sites_in_tree(parse(path))}


class ProcessSpawnBoundaryTests(unittest.TestCase):
    """I8-4／I9-3：四种绕过写法按「文件:行」棘轮；非豁免计数为 0，坏样本自审全覆盖。"""

    def test_spawn_sites_within_baseline(self):
        offenders = set()
        for path in module_scan_files():
            if path.stem in _PROCESS_EXEMPT_STEMS:
                continue
            offenders |= _spawn_sites_in_path(path)
        regressions = sorted(offenders - SPAWN_SITE_BASELINE)
        self.assertEqual(regressions, [],
                         '新增绕过监督器的进程启动点，请改经 workflow_process_registry.spawn：'
                         + chr(10) + chr(10).join(regressions))
        stale = sorted(SPAWN_SITE_BASELINE - offenders)
        if stale:
            print('[棘轮提示] 以下登记点已消失，请从豁免清单移除：'
                  + chr(10) + chr(10).join(stale))

    def test_exempt_registry_covers_baseline_exactly(self):
        """I9-3：豁免清单与棘轮基线一一对应——每个登记点恰好归入一个类别。"""
        categorized = [site for group in SPAWN_SITE_EXEMPT.values() for site in group]
        self.assertEqual(len(categorized), len(set(categorized)),
                         '同一启动点被登记进多个豁免类别')
        self.assertEqual(set(categorized), set(SPAWN_SITE_BASELINE))
        for category in ('short_probe', 'os_operation', 'detached', 'background_boundary'):
            self.assertTrue(SPAWN_SITE_EXEMPT[category], '豁免类别为空：' + category)

    def test_bounded_sites_declare_timeout(self):
        """I9-3：短时探测与 OS 操作豁免要求调用显式带 ``timeout``（AST 复核）。"""
        from tests.architecture._scan import ROOT
        for category in ('short_probe', 'os_operation'):
            for site in sorted(SPAWN_SITE_EXEMPT[category]):
                rel, line = site.rsplit(':', 1)
                tree = parse(ROOT / rel)
                calls = [node for node in ast.walk(tree)
                         if isinstance(node, ast.Call) and node.lineno == int(line)]
                self.assertTrue(calls, '%s：找不到登记行的调用节点' % site)
                call = calls[0]
                self.assertTrue(
                    any(keyword.arg == 'timeout' for keyword in call.keywords),
                    '%s：%s 豁免点缺少显式 timeout' % (site, category))

    def test_baseline_sites_wellformed(self):
        import re
        for site in SPAWN_SITE_BASELINE:
            self.assertRegex(site, r'^[\w./-]+\.py:\d+$', site)

    def test_bad_samples_all_four_forms_flagged(self):
        samples = {
            'popen-call': 'import subprocess\np = (getattr(subprocess, "Popen") or subprocess.Popen)(["x"])\n',
            'popen-kwarg': 'import subprocess\nlaunch(command, popen=subprocess.Popen)\n',
            'subprocess.run': 'import subprocess\nsubprocess.run(["x"])\n',
            'platform-launch': 'from contract import platform_tools\nplatform_tools.launch_background(["x"])\n',
            'platform-launch-bare': 'from contract.platform_tools import launch_text_process\nlaunch_text_process(["x"])\n',
        }
        for name, source in samples.items():
            with self.subTest(form=name):
                tree = ast.parse(source)
                self.assertTrue(_spawn_sites_in_tree(tree), '%s 写法未被识别' % name)

    def test_good_samples_not_flagged(self):
        samples = {
            'sanctioned-run-process': 'from contract.platform_tools import run_process\nrun_process(["x"], timeout=5)\n',
            'supervisor-spawn': 'from infra.workflow_process_registry import spawn\nspawn("ffmpeg", ["x"], project=p, stage=s, timeout=60)\n',
            'plain-reference': 'import subprocess\nvalue = subprocess.PIPE\n',
        }
        for name, source in samples.items():
            with self.subTest(form=name):
                tree = ast.parse(source)
                self.assertFalse(_spawn_sites_in_tree(tree), '%s 写法被误判' % name)
