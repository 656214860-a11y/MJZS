# -*- coding: utf-8 -*-
"""R1949：剧本页有聊天记录时，首绘不再先放示例、再跳成历史。"""
import json
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

import idea_chat
from desktop import Desktop
from desktop_idea_deferred import IDEA_HISTORY_LOADING_TAG
from performance_contract import CHAT_FIRST_TEXT_SECONDS
from stage_execution_service import idea_chat_gateway, project_context

# 模型键慢解析的模拟时长与等待历史出现的上限（秒）。
MODEL_KEY_DELAY_SECONDS = .35
HISTORY_WAIT_SECONDS = 5.0
HISTORY_TEXT = '上一轮聊到的主角设定'
# 历史行带模型名：打开项目时真实模型的迁移不会把这行搬走（只搬无主或同名的行）。
PROBE_MODEL = 'probe'


def _project(temporary):
    project = Path(temporary)
    (project / '01剧本准备' / '输入').mkdir(parents=True)
    (project / 'config.json').write_text('{}', encoding='utf-8')
    return project


def _write_history(project):
    path = idea_chat.history_path(project_context(project))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'messages': [
        {'role': 'user', 'text': HISTORY_TEXT, 'at': '2026-10-23 15:00', 'model': PROBE_MODEL}]},
        ensure_ascii=False), encoding='utf-8')


class HasHistoryTests(unittest.TestCase):
    def test_reports_whether_any_history_exists(self):
        with tempfile.TemporaryDirectory(prefix='idea-has-history-') as temporary:
            project = _project(temporary)
            context = project_context(project)
            self.assertFalse(idea_chat.has_history(context, gateway=idea_chat_gateway()))
            _write_history(project)
            self.assertTrue(idea_chat.has_history(context, gateway=idea_chat_gateway()))


class FirstPaintTests(unittest.TestCase):
    def setUp(self):
        self.window = tk.Tk()
        self.desktop = None
        self.temporary = tempfile.TemporaryDirectory(prefix='idea-first-paint-')
        self.project = _project(self.temporary.name)

    def tearDown(self):
        if self.desktop is not None:
            self.desktop.cancel_timers()
        try:
            self.window.destroy()
        except tk.TclError:
            pass
        self.temporary.cleanup()

    def open_script_page(self):
        self.desktop = Desktop(self.window, root=self.project)
        self.desktop.startup_controller.cancel()
        self.desktop.projects.info['projects'].append({'name': 'first-paint', 'path': str(self.project)})
        self.desktop.reload()
        self.desktop.load(self.project)
        self.window.update()
        return self.desktop

    def tags(self):
        return set(self.desktop.idea_log.tag_names())

    def test_project_with_history_never_shows_the_example_first(self):
        _write_history(self.project)
        desktop = self.open_script_page()
        desktop._idea_view_model_cache = None
        desktop._idea_history_known = {}
        seen_example = []
        with mock.patch.object(desktop, 'idea_chat_model',
                               side_effect=lambda: (time.sleep(MODEL_KEY_DELAY_SECONDS), PROBE_MODEL)[1]):
            desktop.show_example_bubble()
            self.assertIn(IDEA_HISTORY_LOADING_TAG, self.tags())
            self.assertNotIn('bubble_example', desktop._bubble_full)
            desktop.show_conversation()
            self.assertIn(IDEA_HISTORY_LOADING_TAG, self.tags(), '模型键未回来时保留读取提示')
            deadline = time.monotonic() + HISTORY_WAIT_SECONDS
            while time.monotonic() < deadline:
                self.window.update()
                seen_example.append('bubble_example' in desktop._bubble_full)
                if HISTORY_TEXT in desktop.idea_log.get('1.0', 'end'):
                    break
                time.sleep(.01)
        self.assertIn(HISTORY_TEXT, desktop.idea_log.get('1.0', 'end'))
        self.assertNotIn(True, seen_example, '有记录的项目重绘前后都不得出现示例')
        self.assertNotIn(IDEA_HISTORY_LOADING_TAG, self.tags())

    def test_project_without_history_still_shows_the_example_first(self):
        desktop = self.open_script_page()
        desktop._idea_view_model_cache = None
        desktop._idea_history_known = {}
        with mock.patch.object(desktop, 'idea_chat_model',
                               side_effect=lambda: (time.sleep(MODEL_KEY_DELAY_SECONDS), PROBE_MODEL)[1]):
            started = time.perf_counter()
            desktop.show_conversation()
            self.assertIn('bubble_example', desktop._bubble_full)
            self.assertNotIn(IDEA_HISTORY_LOADING_TAG, self.tags())
            self.assertLessEqual(time.perf_counter() - started, CHAT_FIRST_TEXT_SECONDS)


if __name__ == '__main__':
    unittest.main()
