# -*- coding: utf-8 -*-
"""HOLLMWOOD 工作线程到 Tk 主线程的进度队列。"""
import queue
import tempfile
import unittest
from pathlib import Path

from desktop import Desktop


class _Status:
    def __init__(self):
        self.values = []

    def set(self, value):
        self.values.append(value)


class HollmwoodQueueTests(unittest.TestCase):
    def test_current_request_progress_is_rendered_and_logged_on_the_main_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            app = Desktop.__new__(Desktop)
            app.root = Path(folder)
            app.hollmwood_progress = queue.Queue()
            app._async_ticket = 4
            app._idea_requesting = True
            app.shutting_down = True
            app.status = _Status()
            app.hollmwood_progress.put((4, 'director', 1))
            app.poll_hollmwood_progress()
            self.assertEqual(app.status.values, ['导演 正在工作…'])
            log = app.root / 'logs' / 'sanhu_progress.log'
            self.assertIn('【阶段 1/13】HOLLMWOOD：导演 正在工作…', log.read_text(encoding='utf-8'))

    def test_cancelled_request_progress_is_ignored(self):
        app = Desktop.__new__(Desktop)
        app.root = None
        app.hollmwood_progress = queue.Queue()
        app._async_ticket = 5
        app._idea_requesting = True
        app.shutting_down = True
        app.status = _Status()
        app.hollmwood_progress.put((4, 'writer', 2))
        app.poll_hollmwood_progress()
        self.assertEqual(app.status.values, [])


if __name__ == '__main__':
    unittest.main()
