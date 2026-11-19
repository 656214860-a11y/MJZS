# -*- coding: utf-8 -*-
"""I12-2／FL-09：L2 及以上诊断日志写盘的棘轮门禁。

口径（与 I0-5 实测一致）：L2–L5 登记模块里，以追加/覆写模式打开「日志样」目标的
位点——目标是 ``.log``/``.txt`` 字面量、名字含 ``log`` 的变量或调用
（``logfile``、``EMPTY_RESPONSE_LOG``、``log_path()`` 等），或外层函数名是
``log`` 记号（如 ``log_write`` 内的间接 ``path.open``）。只减不增。

排除（I0-5 已区分，单独登记产物白名单）：
- 引擎 stdout/stderr 捕获 ``logfile`` 与响应产物 ``response_temp``
  （``qwen_adapter``／``workflow_engines``）——引擎工件边界，由 I9 进程监督器
  的标准错误输出采集统一接管，不是诊断日志；
- 功能性期录（``pet_agent`` 事件日志.jsonl，与 ``pet_bus`` 共用的幂等台账）——
  不是诊断日志，目标名不含 log 记号，本就不在口径内；
- 锁文件（``*.lock``）、``os.devnull``、``webbrowser.open(url)``、媒体/归档
  产物写入——目标名不含 log 记号或被显式排除。

I12-1 验收：迁移后的诊断信息经命名记录器落 ``logs/app.log`` 并脱敏。
坏样本自审保证检测器不失效。
"""
from __future__ import annotations

import ast
import faulthandler
import json
import logging
import re
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from tests.architecture import _layers, _scan

import infra.app_logging as app_logging

# I0-5 排除项：引擎 stdout/stderr 捕获与响应产物属引擎工件边界（I9 进程监督器
# 接管），登记为产物白名单，只许减不许增。值为该模块当前被口径命中的位点数。
LOG_SINK_PRODUCT_WHITELIST = {
    'qwen_adapter': 1,        # run_background: Path(logfile).open('w') 引擎日志捕获
    'workflow_engines': 3,    # _run_opencode/run_background: Path(logfile).open('w') ×3
}

_LOG_TOKEN = re.compile(r'(?<![a-z])log(?![a-z])', re.IGNORECASE)


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return (base + '.' + node.attr) if base else node.attr
    return ''


def _mode_arg(call: ast.Call, index: int) -> str:
    if len(call.args) > index and isinstance(call.args[index], ast.Constant) \
            and isinstance(call.args[index].value, str):
        return call.args[index].value
    for kw in call.keywords:
        if kw.arg == 'mode' and isinstance(kw.value, ast.Constant) \
                and isinstance(kw.value.value, str):
            return kw.value.value
    return ''


def _open_write_target(call: ast.Call):
    """``x.open(mode)`` 的目标是 ``func.value``；``open(file, mode)`` 的目标是
    ``args[0]``。返回 (目标节点, 是否写模式)；非写打开返回 None。"""
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr == 'open':
        if _dotted(func.value) == 'webbrowser' or _dotted(func.value).endswith('.webbrowser'):
            return None
        mode = _mode_arg(call, 0)
        return (func.value, mode) if mode else None
    if isinstance(func, ast.Name) and func.id == 'open':
        mode = _mode_arg(call, 1)
        return (call.args[0] if call.args else None, mode) if mode else None
    return None


def _is_write_mode(mode: str) -> bool:
    return any(ch in mode for ch in 'wax')


def _logish(target: ast.AST, func_names: list) -> bool:
    if target is None:
        return False
    blob = ast.dump(target).lower()
    if 'devnull' in blob or 'webbrowser' in blob:
        return False
    if '.log' in blob or '.txt' in blob or 'log' in blob:
        return True
    return any(_LOG_TOKEN.search(name) for name in func_names)


def log_sink_sites_in_path(path) -> list:
    """返回文件内 L2+ 口径的诊断日志写盘位点行号列表。"""
    tree = _scan.parse(Path(path))
    sites = []

    def visit(node, func_names):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, func_names + [child.name])
                continue
            if isinstance(child, ast.Call):
                found = _open_write_target(child)
                if found is not None:
                    target, mode = found
                    if _is_write_mode(mode) and _logish(target, func_names):
                        sites.append(child.lineno)
            visit(child, func_names)

    visit(tree, [])
    return sites


def log_sink_sites_by_module() -> dict:
    """L2 及以上登记模块 → 被口径命中的诊断日志写盘位点数（0 计数不收）。"""
    sites = {}
    for name, layer in _layers.LAYERS.items():
        if layer < 2:
            continue
        entity = _scan.entity_file(name)
        if not entity.is_file():
            continue
        count = len(log_sink_sites_in_path(entity))
        if count:
            sites[name] = count
    return sites


class LogSinkBoundaryTests(unittest.TestCase):
    """I12-2：L2+ 诊断写盘只减不增，产物白名单单独登记。"""

    def test_l2_plus_log_writes_within_whitelist(self):
        sites = log_sink_sites_by_module()
        for name, count in sorted(sites.items()):
            allowed = LOG_SINK_PRODUCT_WHITELIST.get(name, 0)
            self.assertLessEqual(
                count, allowed,
                '%s 诊断日志写盘 %d 处 > 白名单 %d（I12 后非白名单模块应为 0）'
                % (name, count, allowed))

    def test_detector_catches_log_targets_and_ignores_products(self):
        sample = '''\
import webbrowser
def log_write(path):
    with path.open('a', encoding='utf-8') as h:
        h.write('{}')
EMPTY = 'x.log'
with open('run.log', 'a') as a, Path('out.txt').open('w') as b:
    pass
with open('state.json', 'w') as c, open('data', 'rb') as d:
    pass
with Path('image_agent.lock').open('a+b') as lock:
    pass
webbrowser.open('https://example.com/')
with open(os.devnull, 'w') as err:
    pass
'''
        with tempfile.TemporaryDirectory() as td:
            good = Path(td) / 'sample.py'
            good.write_text(sample, encoding='utf-8')
            lines = log_sink_sites_in_path(good)
        # 命中：log_write 内 path.open（函数名 log 记号）、run.log、out.txt —— 共 3 处
        self.assertEqual(len(lines), 3, lines)

    def test_detector_ignores_read_and_non_log_writes(self):
        sample = '''\
def work(path):
    with path.open('r', encoding='utf-8') as h:
        h.read()
    with path.open('a', encoding='utf-8') as h:
        h.write('x')
    with open('report.json', 'w') as f:
        f.write('{}')
'''
        with tempfile.TemporaryDirectory() as td:
            good = Path(td) / 'sample.py'
            good.write_text(sample, encoding='utf-8')
            lines = log_sink_sites_in_path(good)
        # 只命中 work 内的 path.open('a') 之外的 0 处？path 无 log 记号、函数名 work 无 → 0 处
        self.assertEqual(lines, [])


class MigratedDiagnosticsSinkTests(unittest.TestCase):
    """I12-1：迁移后的诊断信息落 logs/app.log 且脱敏。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.saved = (sys.excepthook, threading.excepthook,
                      list(logging.getLogger().handlers),
                      logging.getLogger().level, app_logging._installed)
        for patcher in (mock.patch.object(app_logging, 'LOGS', self.tmp),
                        mock.patch.object(app_logging, 'APP_LOG', self.tmp / 'app.log'),
                        mock.patch.object(app_logging, 'FAULT_LOG', self.tmp / 'faulthandler.log')):
            patcher.start()
            self.addCleanup(patcher.stop)
        app_logging._installed = False

    def tearDown(self):
        root = logging.getLogger()
        for handler in list(root.handlers):
            if handler not in self.saved[2]:
                root.removeHandler(handler)
                handler.close()
        root.setLevel(self.saved[3])
        sys.excepthook, threading.excepthook = self.saved[0], self.saved[1]
        app_logging._installed = self.saved[4]
        faulthandler.disable()
        if app_logging._fault_stream:
            app_logging._fault_stream.close()
            app_logging._fault_stream = None

    def _flush(self):
        for handler in logging.getLogger().handlers:
            handler.flush()

    def _app_log(self):
        return (self.tmp / 'app.log').read_text(encoding='utf-8')

    def test_image_agent_events_reach_app_log_redacted(self):
        app_logging.install()
        import image_agent_runner
        batch = self.tmp / '批次'
        batch.mkdir()
        image_agent_runner.Events(batch / 'manifest.json').put('执行 api_key=sk-FAKE-12345 完成')
        self._flush()
        text = self._app_log()
        self.assertIn('执行', text)
        self.assertIn('[已脱敏]', text)
        self.assertNotIn('sk-FAKE-12345', text)

    def test_writing_api_empty_meta_reaches_app_log(self):
        app_logging.install()
        import writing_api
        writing_api._record_empty_response(
            {'ok': True, 'status': 200,
             'data': {'content': [{'type': 'text', 'text': 'x'}]}, 'usage': {}})
        self._flush()
        self.assertIn('block_types', self._app_log())

    def test_stage_parallel_log_write_reaches_app_log(self):
        app_logging.install()
        from orchestrator import stage_parallel
        stage_parallel.log_write(None, 'video', 'dispatch', 'start', '批次 B01', at=0)
        self._flush()
        text = self._app_log()
        self.assertIn('video', text)
        self.assertIn('dispatch', text)
        self.assertIn('批次 B01', text)


if __name__ == '__main__':
    unittest.main()
