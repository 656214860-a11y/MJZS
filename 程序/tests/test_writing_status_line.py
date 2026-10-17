# -*- coding: utf-8 -*-
"""R1673 修复轮：剧本准备状态栏只留摘要，完整说明保留在悬停提示。"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, HERE)
os.chdir(HERE)

import idea_chat
import writing_api
from agent.core import save
from project_stages import writing as writing_dir
from script_contract import natural_script_selection_path
from tests.test_idea_chat import _Harness
from tests.test_ui_edges import make_minimal_project


class SessionSummaryTests(unittest.TestCase):
    def test_compact_summary_keeps_only_essentials(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            compact = writing_api.chat_session_compact(proj, 'gpt-4o')
            self.assertIn('gpt-4o', compact)
            self.assertIn('API 直连', compact)
            self.assertIn('尚未采用自然剧本', compact)
            self.assertNotIn('请求身份', compact)
            self.assertNotIn('按模型隔离', compact)
            self.assertNotIn('不隐藏也不复制', compact)
            self.assertLessEqual(len(compact), 80)

    def test_compact_summary_includes_adopted_and_shared(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            folder = writing_dir(proj)
            (folder / '项目设定').mkdir(parents=True, exist_ok=True)
            save(folder / '项目设定' / '设定.md', '# 项目设定\n内容\n')
            save(folder / 'preparation_state.json', {
                'version': 1, 'brief_hash': 'x',
                'documents': [{'path': '项目设定/设定.md', 'stage': '项目设定',
                               'sha256': 'y', 'confirmed': True}]})
            save(natural_script_selection_path(proj), {'path': '项目设定/设定.md'})
            compact = writing_api.chat_session_compact(proj, 'gpt-4o')
            self.assertIn('已采用自然剧本', compact)
            self.assertIn('共享 1 份', compact)
            detail = writing_api.chat_session_summary(proj, 'gpt-4o')
            self.assertIn('已确认阶段文件 1 份', detail)
            self.assertIn('不隐藏也不复制项目成果', detail)

    def test_lines_return_compact_and_detailed_text(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            visible, detail = writing_api.chat_session_lines(proj, 'gpt-4o')
            self.assertEqual(visible, writing_api.chat_session_compact(proj, 'gpt-4o'))
            self.assertEqual(detail, writing_api.chat_session_summary(proj, 'gpt-4o'))
            self.assertIn('请求身份', detail)
            self.assertNotIn('请求身份', visible)

    def test_usage_compact_is_short_but_tooltip_keeps_detail(self):
        rows = [{'role': 'assistant',
                 'context_budget': {'input_tokens': 123, 'context_limit': 4096,
                                    'output_reserved': 512},
                 'request_usage': {'prompt_tokens': 120, 'completion_tokens': 30,
                                   'cached_tokens': 0}}]
        self.assertEqual(idea_chat.usage_compact(rows), '上次 120/30 token')
        self.assertIn('输入估算 123', idea_chat.usage_summary(rows))
        self.assertEqual(idea_chat.usage_compact([]), '本模型暂无用量记录')


class DesktopStatusLineTests(_Harness):
    def test_visible_label_is_compact_and_tooltip_keeps_detail(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            self.sync_async(d)
            d.show(0)
            self.settle_script_page(win)
            visible = d.idea_session_label.cget('text')
            detail = d.idea_session_tip.text
            self.assertIn('API 直连', visible)
            self.assertNotIn('请求身份', visible)
            self.assertNotIn('不隐藏也不复制', visible)
            self.assertIn('当前会话：', detail)
            self.assertIn('不隐藏也不复制项目成果', detail)


if __name__ == '__main__':
    unittest.main(verbosity=2)