"""主后台任务的忙碌态必须成对经过 BusyState。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse, parse_desktop


PRODUCTION_SKIP = {"tests", "tasks_round", "维护记录", "skills", ".git", "__pycache__", "voice_asr_venv"}


def _production_files():
    for path in sorted(ROOT.rglob('*.py')):
        if set(path.relative_to(ROOT).parts) & PRODUCTION_SKIP:
            continue
        yield path


def _dotted(node):
    """把 self.a.b 这类属性链还原成 ['self', 'a', 'b']；非属性链返回 []。"""
    names = []
    while isinstance(node, ast.Attribute):
        names.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        names.append(node.id)
        return list(reversed(names))
    return []


def _method(tree, name):
    return next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                and node.name == name)


def _calls(node, dotted):
    return [sub for sub in ast.walk(node) if isinstance(sub, ast.Call)
            and _dotted(sub.func) == dotted.split('.')]


def _progressbar_names(tree):
    """模块内绑定到 ttk.Progressbar 的变量名，含 self.attr 形式。"""
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
                and value.func.attr == 'Progressbar'):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
            elif isinstance(target, ast.Attribute):
                names.add(target.attr)
    return names


def _bool_call(call, expected):
    return bool(call.args) and isinstance(call.args[0], ast.Constant) \
        and call.args[0].value is expected


class BusyStateBoundaryTests(unittest.TestCase):
    def test_progress_start_stop_lives_only_in_busy_state(self):
        """业务页面不得直接开关不确定进度条；加载态只能经 BusyState.set_busy。"""
        offenders = []
        for path in _production_files():
            if path.name == 'ui_widgets.py':
                continue
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            names = _progressbar_names(tree)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                        and node.func.attr in {'start', 'stop'}:
                    value = node.func.value
                    label = value.id if isinstance(value, ast.Name) else (
                        value.attr if isinstance(value, ast.Attribute) else None)
                    if label in names:
                        offenders.append(
                            f'{path.relative_to(ROOT).as_posix()}:{node.lineno}:{label}.{node.func.attr}')
        self.assertEqual(offenders, [])

    def test_pages_with_progress_route_through_the_shared_busy_entry(self):
        """app.py／native_assets.py 的加载态必须由同一个 BusyState 成对恢复。"""
        for filename in ('app.py', 'native_assets.py'):
            tree = parse(ROOT / filename)
            imported = {
                alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                and node.module == 'ui_widgets' for alias in node.names
            }
            self.assertIn('BusyState', imported, f'{filename} 必须使用统一忙碌态入口')
            built = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Name) and node.func.id == 'BusyState']
            self.assertEqual(len(built), 1, f'{filename} 只允许一个统一忙碌态实例')
            calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Attribute)
                     and node.func.attr == 'set_busy']
            self.assertTrue(any(_bool_call(call, True) for call in calls),
                            f'{filename} 必须有成对开始')
            self.assertTrue(any(_bool_call(call, False) for call in calls),
                            f'{filename} 必须有成对恢复')

    def test_async_lifecycle_uses_busy_state_for_start_and_finish(self):
        tree = parse_desktop()
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute)
                 and isinstance(node.func.value, ast.Attribute)
                 and node.func.value.attr == 'busy_state'
                 and node.func.attr == 'set_busy']
        values = [node.args[0].value for node in calls
                  if node.args and isinstance(node.args[0], ast.Constant)
                  and isinstance(node.args[0].value, bool)]
        self.assertIn(True, values)
        self.assertGreaterEqual(values.count(False), 2,
                                '完成和中断都必须经 BusyState 恢复界面')

    def test_desktop_submission_pairs_lifecycle_and_busy(self):
        tree = parse_desktop()
        method = _method(tree, 'async_')
        submits = _calls(method, 'self.background_tasks.submit')
        starts = [call for call in _calls(method, 'self.busy_state.set_busy')
                  if _bool_call(call, True)]
        self.assertEqual(len(submits), 1, '提交必须登记到 BackgroundTaskLifecycle')
        self.assertEqual(len(starts), 1, '提交必须同时进入统一忙碌态')

    def test_desktop_result_drain_rejects_late_results_before_restoring_busy(self):
        tree = parse_desktop()
        drain = _method(tree, '_tick_async_result')
        finishes = _calls(drain, 'self.background_tasks.finish')
        restores = [call for call in _calls(drain, 'self.busy_state.set_busy')
                    if _bool_call(call, False)]
        self.assertEqual(len(finishes), 1, '成功／失败收尾必须经生命周期判定')
        self.assertTrue(restores, '收尾必须恢复统一忙碌态')
        self.assertLess(finishes[0].lineno, restores[0].lineno,
                        '必须先判定结果归属，再恢复界面')
        guards = [node for node in ast.walk(drain) if isinstance(node, ast.If)
                  and any(sub is finishes[0] for sub in ast.walk(node.test))]
        self.assertTrue(guards, '迟到结果必须先经 lifecycle.finish 判定')
        self.assertTrue([node for node in ast.walk(guards[0]) if isinstance(node, ast.Return)],
                        '被拒绝或已过期的结果必须直接返回，不触发 UI 回调')

    def test_desktop_cancel_invalidates_ticket_and_restores_busy(self):
        tree = parse_desktop()
        method = _method(tree, 'interrupt_script_agent')
        cancels = _calls(method, 'self.background_tasks.cancel')
        restores = [call for call in _calls(method, 'self.busy_state.set_busy')
                    if _bool_call(call, False)]
        self.assertTrue(cancels, '取消必须经 BackgroundTaskLifecycle')
        self.assertTrue(restores, '取消后必须恢复统一忙碌态')
        bumps = [node for node in ast.walk(method) if isinstance(node, ast.AugAssign)
                 and _dotted(node.target) == ['self', '_async_ticket']]
        self.assertTrue(bumps, '取消必须推进代次，使迟到结果被拒绝')

    def test_production_pages_do_not_build_progressbars(self):
        """忙碌态统一用转圈（ui_motion.Spinner），页面不再构造 ttk.Progressbar。"""
        offenders = []
        for path in _production_files():
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and (
                        (isinstance(node.func, ast.Attribute) and node.func.attr == 'Progressbar')
                        or (isinstance(node.func, ast.Name) and node.func.id == 'Progressbar')):
                    offenders.append(f'{path.relative_to(ROOT)}:{node.lineno}')
        self.assertEqual(offenders, [])

    def test_interrupt_does_not_stop_the_progressbar_directly(self):
        tree = parse_desktop()
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                      and node.name == 'interrupt_script_agent')
        stops = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute)
                 and node.func.attr == 'stop'
                 and isinstance(node.func.value, ast.Attribute)
                 and node.func.value.attr == 'progress']
        self.assertEqual(stops, [])
