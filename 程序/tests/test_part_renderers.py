# -*- coding: utf-8 -*-
"""消息 part 分派渲染器（R3115）：注册表、折叠思考卡、产物/工具行、skip_text。

运行：python tests/test_part_renderers.py（真 Tk；运行器会切隐藏桌面）
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain import message_parts
from skip_reasons import PLATFORM_TKINTER
from ui import ui_part_renderers


class _Host:
    def __init__(self):
        self.opened = []

    def open_artifact(self, artifact):
        self.opened.append(artifact.identifier)


class PartRendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        self.win = self.tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.box = self.tk.Text(self.win)
        self.host = _Host()

    def text(self):
        return self.box.get('1.0', 'end-1c')

    def test_registry_covers_all_part_types(self):
        for value in ('text', 'reasoning', 'tool_call', 'tool_result', 'source', 'file', 'artifact', 'data'):
            self.assertIn(value, ui_part_renderers.registered_types())

    def test_reasoning_collapses_and_expands(self):
        part = message_parts.reasoning_part('想三步')
        self.assertTrue(ui_part_renderers.render_parts(self.box, 'b1', [part], self.host))
        self.assertIn('思考过程', self.text())
        self.assertNotIn('想三步', self.text())
        self.assertTrue(ui_part_renderers.toggle_reasoning(self.box, 'b1'))
        self.assertIn('想三步', self.text())
        self.assertFalse(ui_part_renderers.toggle_reasoning(self.box, 'b1'))
        self.assertNotIn('想三步', self.text())

    def test_artifact_renders_title_and_kind(self):
        part = message_parts.part(message_parts.PartType.ARTIFACT,
                                  {'kind': 'image', 'identifier': 'st-001', 'title': '分镜1'})
        self.assertTrue(ui_part_renderers.render_parts(self.box, 'b2', [part], self.host))
        self.assertIn('分镜1', self.text())
        self.assertIn('image', self.text())

    def test_tool_call_renders_name_state_and_elapsed(self):
        part = message_parts.part(message_parts.PartType.TOOL_CALL,
                                  {'name': 'ComfyUI', 'elapsed': 1.5}, state='done')
        self.assertTrue(ui_part_renderers.render_parts(self.box, 'b3', [part], self.host))
        self.assertIn('ComfyUI', self.text())
        self.assertIn('done', self.text())
        self.assertIn('1.5s', self.text())

    def test_skip_text_keeps_text_out(self):
        parts = [message_parts.text_part('正文'), message_parts.reasoning_part('想')]
        rendered = ui_part_renderers.render_parts(self.box, 'b4', parts, self.host, skip_text=True)
        self.assertEqual(rendered, 1)
        self.assertNotIn('正文', self.text())
        self.assertIn('思考过程', self.text())

    def test_unknown_type_is_skipped(self):
        self.assertEqual(ui_part_renderers.render_parts(self.box, 'b5', [{'type': 'nope'}], self.host), 0)


if __name__ == '__main__':
    unittest.main()
