"""统一快捷键登记的无 Tk 回归。"""
from __future__ import annotations

import unittest

from ui_shortcuts import ShortcutRegistry


class _Widget:
    def __init__(self): self.calls = []
    def bind(self, sequence, handler, add=None):
        self.calls.append((sequence, handler, add))
        return 'bind-%d' % len(self.calls)


class ShortcutRegistryTests(unittest.TestCase):
    def test_registers_one_semantic_action_with_its_case_variants(self):
        widget, registry = _Widget(), ShortcutRegistry()
        handler = object()
        tokens = registry.bind(widget, ('<Control-c>', '<Control-C>'), handler,
                               scope='剧本准备·聊天记录', name='复制选中气泡文本')
        self.assertEqual(tokens, ('bind-1', 'bind-2'))
        self.assertEqual([call[0] for call in widget.calls], ['<Control-c>', '<Control-C>'])
        self.assertEqual(registry.registered()[0]['name'], '复制选中气泡文本')

    def test_rejects_duplicate_shortcut_in_the_same_scope_but_not_another_scope(self):
        registry, widget = ShortcutRegistry(), _Widget()
        registry.bind(widget, ('<Control-c>',), object(), scope='剧本准备', name='复制')
        with self.assertRaisesRegex(ValueError, '快捷键冲突'):
            registry.bind(widget, ('<Control-C>',), object(), scope='剧本准备', name='另一复制')
        registry.bind(widget, ('<Control-C>',), object(), scope='资产管理', name='复制')

    def test_repeat_build_of_the_same_widget_action_is_idempotent(self):
        registry, widget = ShortcutRegistry(), _Widget()
        first = registry.bind(widget, ('<Control-c>',), object(), scope='剧本准备', name='复制')
        repeated = registry.bind(widget, ('<Control-c>',), object(), scope='剧本准备', name='复制')
        self.assertEqual(repeated, first)
        self.assertEqual(len(widget.calls), 1)

    def test_rebuild_replaces_the_old_widget_for_the_same_semantic_action(self):
        registry, old, new = ShortcutRegistry(), _Widget(), _Widget()
        registry.bind(old, ('<Control-c>',), object(), scope='剧本准备', name='复制')
        registry.bind(new, ('<Control-c>',), object(), scope='剧本准备', name='复制')
        self.assertEqual(len(old.calls), 1)
        self.assertEqual(len(new.calls), 1)
