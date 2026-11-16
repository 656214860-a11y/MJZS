# -*- coding: utf-8 -*-
"""文本复制必须集中到可锁定、可反馈、可脱敏的唯一入口。"""
import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXCLUDED_PARTS = {"tests", "tasks_round", "维护记录", "skills", ".git", "__pycache__", "voice_asr_venv"}


class CopyEntryBoundaryTests(unittest.TestCase):
    VISIBLE_COPY_FAILURE = '复制失败：'
    BANNED_SUCCESS_TERMS = ('复制成功', '成功复制')

    def test_clipboard_writes_only_live_in_the_shared_copy_entry(self):
        offenders = []
        for path in ROOT.rglob('*.py'):
            if (path.name == 'prompt_window.py'
                    or any(part in EXCLUDED_PARTS for part in path.parts)):
                continue
            if 'clipboard_append' in path.read_text(encoding='utf-8'):
                offenders.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(offenders, [])

    def test_shared_entry_locks_writes_and_masks_status_preview(self):
        source = (ROOT / 'prompt_window.py').read_text(encoding='utf-8')
        self.assertIn('with hold_clipboard()', source)
        self.assertIn('def copy_preview(', source)
        self.assertIn('_SECRET_VALUE', source)

    @staticmethod
    def _docstring_nodes(tree):
        """收集模块／类／函数首行的文档字符串节点；说明性文字不算用户可见文案。"""
        nodes = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                body = getattr(node, 'body', None)
                if (body and isinstance(body[0], ast.Expr)
                        and isinstance(body[0].value, ast.Constant)
                        and isinstance(body[0].value.value, str)):
                    nodes.add(id(body[0].value))
        return nodes

    def test_copy_feedback_uses_the_fixed_terms(self):
        """复制反馈固定术语：成功「已复制…」、失败「复制失败：…」；页面不得自创不可检索的文案。"""
        offenders = []
        for path in ROOT.rglob('*.py'):
            if any(part in EXCLUDED_PARTS for part in path.parts):
                continue
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            docstrings = self._docstring_nodes(tree)
            rel = path.relative_to(ROOT).as_posix()
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Constant) and isinstance(node.value, str)
                        and id(node) not in docstrings):
                    continue
                text = node.value
                if '复制失败' in text and self.VISIBLE_COPY_FAILURE not in text:
                    offenders.append(f'{rel}:{node.lineno}: 失败反馈须用「复制失败：…」')
                for term in self.BANNED_SUCCESS_TERMS:
                    if term in text:
                        offenders.append(f'{rel}:{node.lineno}: 成功反馈须用「已复制…」，不得用「{term}」')
        self.assertEqual(offenders, [])
