# -*- coding: utf-8 -*-
"""单条消息工具栏（R3115）：复制／删除／编辑重发／引用／重新生成。

运行：python tests/test_message_toolbar.py（真 Tk；运行器会切隐藏桌面）
"""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from skip_reasons import PLATFORM_TKINTER
from tests.ui_edges_support import make_minimal_project


class _Harness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def desktop(self, proj):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import stage_config
        try:
            raw = json.loads(stage_config.path(proj).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            raw = {}
        if not isinstance(raw, dict) or not isinstance(raw.get('script'), dict):
            stage_config.put(proj, 'script', skills=['pipeline-script-preparation'])
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, 'choose_project', original)
        win = self.tk.Tk()
        win.withdraw()
        self.addCleanup(self._quiet, win)
        from desktop import Desktop
        from local_video import open_studio
        d = Desktop(win, root=HERE)
        d.root = proj
        d.studio = open_studio(proj)
        self._settled_desktop = d
        return d, win

    @staticmethod
    def _quiet(win):
        try:
            win.destroy()
        except Exception:
            pass

    def sync_async(self, d):
        def run(fn, done=None, show_progress=True):
            try:
                value = fn()
            except Exception:
                return
            if done is not None:
                done(value)
        d.async_ = run

    def settle(self, win, seconds=.2):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            win.update()
            time.sleep(.01)
        win.update()


class MessageToolbarTests(_Harness):
    def _desktop(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        proj = make_minimal_project(tmp.name)
        from stage_execution_service import idea_chat_gateway, project_context
        import idea_chat
        root = project_context(proj)
        gateway = idea_chat_gateway()
        idea_chat.append(root, 'user', '第一条创意正文', gateway=gateway)
        d, win = self.desktop(proj)
        self.sync_async(d)
        d.show(0)
        self.settle(win)
        d._idea_view_rows = None
        return d, win

    def test_menu_has_message_toolbar_actions(self):
        d, win = self._desktop()
        d._bubble_full = {'bubble_0': {'text': '第一条创意正文', 'expanded': False}}
        event = SimpleNamespace(widget=d.idea_log, x=8, y=8)
        with patch.object(d, 'bubble_target_at', return_value=(0, 'bubble_0')), \
             patch('desktop.ContextMenu.popup', return_value='break'):
            d.open_bubble_menu(event)
        labels = [d._bubble_menu.entrycget(i, 'label')
                  for i in range(d._bubble_menu.index('end') + 1)
                  if d._bubble_menu.type(i) != 'separator']
        for label in ('复制这条', '删除这条', '编辑并重发', '引用到输入框', '重新生成'):
            self.assertIn(label, labels)

    def test_quote_prefixes_input(self):
        d, win = self._desktop()
        self.assertEqual(d.quote_bubble_message(0), '第一条创意正文')
        self.assertTrue(d.idea_input.get('1.0', 'end-1c').startswith('> 第一条创意正文'))

    def test_regenerate_rewinds_and_sends(self):
        d, win = self._desktop()
        sent = []
        d.send_message = lambda: sent.append(True)
        self.assertEqual(d.regenerate_bubble_message(0), '第一条创意正文')
        self.assertEqual(sent, [True])

    def test_edit_rewind_fills_input(self):
        d, win = self._desktop()
        self.assertEqual(d.rewind_bubble_message(0), '第一条创意正文')
        self.assertEqual(d.idea_input.get('1.0', 'end-1c'), '第一条创意正文')


if __name__ == '__main__':
    unittest.main()
