# -*- coding: utf-8 -*-
"""剧本页／资产页首绘性能的根因回归（SLOWPAGE 车道）。

两条根因各有证据：
1. 建页当拍同步回填附件行与聊天历史，会把输入区／聊天框几何拖进画布布局
   收敛，真实项目上 page.paint.script 从约 0.5s 涨到约 1.4s；回填必须等布局稳定。
2. 已采用分镜多对同一份 source_script 时，逐集重复递归扫描 writing，
   真实项目 11 集只有 2 份剧本却走了 11 次 discover。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import tkinter as tk

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.chdir(HERE)

from skip_reasons import PLATFORM_TK_DISPLAY

from domain import asset_reference_prompts
import pet_state
import stage_execution_service
from desktop_idea_chat import IdeaChatMixin
from desktop_idea_deferred import IDEA_UPDATE_TIMEOUT_SECONDS


def _write_episode_project(root):
    """两集已采用分镜共用一份剧本的最小项目。"""
    project = Path(root) / '项目'
    (project / 'episode' / 'frames').mkdir(parents=True)
    (project / 'episode' / 'assets.json').write_text('{}', encoding='utf-8')
    (project / 'episode' / 'episode.json').write_text(json.dumps({
        'episode_id': 'EP001', 'title': 'T', 'shots': [
            {'id': 'SH001', 'title': '镜头', 'duration': 5, 'characters': ['CHAR_001'],
             'location': 'LOC_001', 'frame': 'frames/SH001.png',
             'video_prompt': '画面', 'dialogue': []}],
    }, ensure_ascii=False), encoding='utf-8')
    (project / 'config.json').write_text(json.dumps({
        'episode_dir': str(project / 'episode'),
        'episode_file': str(project / 'episode' / 'episode.json'),
        'budget_seconds': 0, 'reserve_seconds': 0, 'live_enabled': False,
    }, ensure_ascii=False), encoding='utf-8')
    script = project / '01剧本准备' / '输入' / '故事.md'
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text('# 故事\n', encoding='utf-8')
    boards = project / 'storyboards'
    boards.mkdir()
    for index in (1, 2):
        (boards / ('sb%d.json' % index)).write_text(json.dumps({
            'episode_id': 'EP00%d' % index, 'source_script': str(script), 'shots': [
                {'id': 'SH%03d' % index, 'title': '镜头', 'duration': 5,
                 'characters': ['CHAR_001'], 'location': 'LOC_001',
                 'frame': 'frames/SH%03d.png' % index,
                 'video_prompt': '画面', 'dialogue': []}],
        }, ensure_ascii=False), encoding='utf-8')
    (project / 'ui_settings.json').write_text(json.dumps({
        'adopted_storyboards': ['storyboards/sb1.json', 'storyboards/sb2.json'],
    }, ensure_ascii=False), encoding='utf-8')
    return project, [boards / 'sb1.json', boards / 'sb2.json']


class _IdeaPageStub:
    """只暴露 defer_idea_page_updates 需要的状态与方法。"""

    def __init__(self, window):
        self.win = window
        self.page_index = pet_state.PAGE_OF['script']
        self._fit_pending = True
        self.shutting_down = False
        self._idea_page_update_job = None
        self.calls = []

    def update_idea_attachment_status(self):
        self.calls.append('attachments')

    def show_conversation(self):
        self.calls.append('chat')


class SlowPageFirstPaintTests(unittest.TestCase):
    def _tk_root(self):
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError as exc:
            self.skipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))
        return root

    @staticmethod
    def _destroy_desktop(window, desktop):
        try:
            desktop.cancel_timers()
        except Exception:
            pass
        try:
            window.destroy()
        except Exception:
            pass

    def _desktop_for_writing(self, temporary):
        """建一个能直接调用 ``writing()`` 的真 Tk Desktop。"""
        from desktop import Desktop
        app = Path(temporary) / 'app'
        app.mkdir()
        (app / 'config.json').write_text(json.dumps({
            'downloads_root': str(Path(temporary) / 'downloads'),
        }), encoding='utf-8')
        (app / 'projects.json').write_text(json.dumps({
            'active': None, 'projects': [],
        }), encoding='utf-8')
        window = self._tk_root()
        desktop = Desktop(window, root=app)
        desktop.startup_controller.cancel()
        self.addCleanup(self._destroy_desktop, window, desktop)
        project, _boards = _write_episode_project(temporary)
        desktop.root = project
        desktop.ensure_stage_layout()
        # 固定模型缓存，避免首绘后的后台模型解析再触发一次聊天重绘；这里只守护
        # ``writing()`` 的延迟接线，不测模型发现。
        desktop._idea_view_model_cache = (project, '')
        for child in desktop.content.winfo_children():
            child.destroy()
        return desktop

    def test_idea_updates_wait_until_layout_settles(self):
        """布局未稳定时不回填附件／聊天，稳定后才各执行一次。"""
        root = self._tk_root()
        try:
            page = _IdeaPageStub(root)
            IdeaChatMixin.defer_idea_page_updates(page)
            deadline = time.monotonic() + 0.25
            while time.monotonic() < deadline:
                root.update()
                time.sleep(0.005)
            self.assertEqual(page.calls, [], '布局仍在收敛时不得回填')
            page._fit_pending = False
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline and len(page.calls) < 2:
                root.update()
                time.sleep(0.005)
            self.assertEqual(page.calls, ['attachments', 'chat'])
        finally:
            try:
                root.destroy()
            except tk.TclError:
                pass

    def test_writing_defers_idea_updates_and_shows_example_first(self):
        """REQ-S01-22：``writing()`` 首绘只放示例，附件／聊天等布局稳定后再各补一次。"""
        with tempfile.TemporaryDirectory(prefix='slowpage-writing-') as temporary:
            desktop = self._desktop_for_writing(temporary)
            with mock.patch.object(
                    desktop, 'update_idea_attachment_status',
                    wraps=desktop.update_idea_attachment_status) as attachments, \
                 mock.patch.object(
                    desktop, 'show_conversation',
                    wraps=desktop.show_conversation) as conversation:
                desktop.writing()
                self.assertEqual(attachments.call_count, 0,
                                 '建页当拍不得回填附件')
                self.assertEqual(conversation.call_count, 0,
                                 '建页当拍不得重绘真实聊天历史')
                self.assertIn('bubble_example', desktop._bubble_full,
                              '首绘必须已经放好示例气泡')

                deadline = time.monotonic() + IDEA_UPDATE_TIMEOUT_SECONDS + 1.0
                while (time.monotonic() < deadline
                       and (attachments.call_count < 1 or conversation.call_count < 1)):
                    desktop.win.update()
                    time.sleep(0.005)
                self.assertEqual(attachments.call_count, 1,
                                 '布局稳定后附件回填应恰好执行一次')
                self.assertEqual(conversation.call_count, 1,
                                 '布局稳定后聊天重绘应恰好执行一次')

    def test_adopted_storyboards_share_one_reference_scan(self):
        """共用同一 source_script 的已采用分镜只扫描一次 writing 文档。"""
        with tempfile.TemporaryDirectory() as temporary:
            project, boards = _write_episode_project(temporary)
            calls = []
            real_discover = asset_reference_prompts.discover

            def counting(project_path, source_script=None):
                calls.append(source_script)
                return real_discover(project_path, source_script)

            with mock.patch.object(asset_reference_prompts, 'discover', counting):
                rows = stage_execution_service.sync_asset_plan(
                    project, project / 'episode', boards, scope='adopted')
            self.assertEqual(sorted(rows), ['CHAR_001', 'LOC_001'])
            self.assertEqual(len(calls), 1, '同一份剧本被逐集重复扫描：%r' % (calls,))


if __name__ == '__main__':
    unittest.main()
