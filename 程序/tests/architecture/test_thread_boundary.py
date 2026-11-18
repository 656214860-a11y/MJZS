"""I10-4／FL-08：L2、L3 直接建线程的棘轮门禁。

口径（与 I0 F11 实测一致）：``threading.Thread(...)``、裸 ``Thread(...)``、
``ThreadPoolExecutor(...)``（含 ``concurrent.futures`` 属性形式）、``threading.Timer``
及 ``class X(threading.Thread)`` 基类写法，按「文件:计数」登记棘轮，只减不增；
I11 迁移进执行器后逐文件下调，末批归零。坏样本自审保证检测器不失效。
"""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from tests.architecture import _layers, _scan

# I0（R3386 F11）实测：L2 3 文件＋L3 9 文件，共 15 个建线程位点。
THREAD_SITE_BASELINE = {
    'domain/offline_asr_client.py': 2,
    'domain/offline_asr_setup.py': 1,
    'domain/speech_api.py': 3,
    'orchestrator/agent_skill_sync.py': 1,
    'orchestrator/codex_skill_sync.py': 1,
    'orchestrator/desktop_automation_service.py': 1,
    'orchestrator/idea_chat_controller.py': 1,
    'orchestrator/previs_automation.py': 1,
    'orchestrator/previs_monitor.py': 1,
    'orchestrator/qwen_adapter.py': 1,
    'orchestrator/stage_parallel.py': 1,
    'orchestrator/storyboard_direct_api.py': 1,
}

_THREAD_TAILS = frozenset({'Thread', 'ThreadPoolExecutor', 'Timer'})


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return (base + '.' + node.attr) if base else node.attr
    return ''


def _is_thread_factory(dotted: str) -> bool:
    """``threading.Thread``/``Thread``/``ThreadPoolExecutor``/``Timer`` 及属性形式。"""
    tail = dotted.rsplit('.', 1)[-1] if dotted else ''
    return tail in _THREAD_TAILS


def thread_sites_in_path(path) -> int:
    """返回文件内直接建线程的位点数（Call＋ClassDef 基类两种形态）。"""
    tree = _scan.parse(Path(path))
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_thread_factory(_dotted(node.func)):
            count += 1
        elif isinstance(node, ast.ClassDef):
            for base in node.bases:
                if _dotted(base).rsplit('.', 1)[-1] == 'Thread':
                    count += 1
    return count


def thread_sites_by_module() -> dict:
    """L2、L3 登记模块的实体文件 → 建线程位点数（0 计数不收）。"""
    sites = {}
    for name, layer in _layers.LAYERS.items():
        if layer not in (2, 3):
            continue
        entity = _scan.entity_file(name)
        if not entity.is_file():
            continue
        count = thread_sites_in_path(entity)
        if count:
            sites[entity.relative_to(_scan.ROOT).as_posix()] = count
    return sites


class ThreadBoundaryTests(unittest.TestCase):
    """I10-4：L2/L3 直接建线程计数不得高于 I0 基线；坏样本自审。"""

    def test_thread_sites_within_baseline(self):
        sites = thread_sites_by_module()
        regressions = []
        for path, count in sorted(sites.items()):
            limit = THREAD_SITE_BASELINE.get(path, 0)
            if count > limit:
                regressions.append('%s：实测 %d > 基线 %d' % (path, count, limit))
        self.assertEqual(regressions, [],
                         'L2/L3 新增直接建线程，请改经 infra.executors：\n'
                         + '\n'.join(regressions))
        stale = sorted(set(THREAD_SITE_BASELINE) - set(sites))
        if stale:
            print('[棘轮提示] 以下登记点已清零，请从 THREAD_SITE_BASELINE 移除：'
                  + '\n'.join(stale))

    def test_baseline_covers_current_modules(self):
        """基线登记的每个文件当前确实还有位点（防基线虚高掩盖回升）。"""
        sites = thread_sites_by_module()
        for path, baseline in THREAD_SITE_BASELINE.items():
            self.assertEqual(sites.get(path, 0), baseline,
                             '%s：基线 %d 与实测 %d 不一致（迁移后请同步下调）'
                             % (path, baseline, sites.get(path, 0)))

    def test_detector_catches_all_thread_forms(self):
        """坏样本自审：四种写法＋Thread 子类都被计数；executors.submit 不误报。"""
        source = (
            'import threading\n'
            'from concurrent.futures import ThreadPoolExecutor\n'
            'from threading import Thread\n'
            'def f():\n'
            '    threading.Thread(target=g).start()\n'
            '    Thread(target=g).start()\n'
            '    ThreadPoolExecutor(1).submit(g)\n'
            '    threading.Timer(1, g).start()\n'
            'class Job(Thread):\n'
            '    pass\n'
            'def ok(executors):\n'
            '    executors.submit("io", g)\n'
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'sample.py'
            path.write_text(source, encoding='utf-8')
            self.assertEqual(thread_sites_in_path(path), 5)

    def test_detector_ignores_executor_submit(self):
        source = 'import infra.executors as executors\nexecutors.submit("io", fn)\n'
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'sample.py'
            path.write_text(source, encoding='utf-8')
            self.assertEqual(thread_sites_in_path(path), 0)


if __name__ == '__main__':
    unittest.main()
