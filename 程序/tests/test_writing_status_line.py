# -*- coding: utf-8 -*-
"""R1673 修复轮：剧本准备状态栏只留摘要，完整说明保留在悬停提示。"""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

HERE = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, HERE)
os.chdir(HERE)

import idea_chat
import writing_api
from agent.core import save
from contract.project_stages import writing as writing_dir
from script_contract import natural_script_selection_path
from tests.test_idea_chat import _Harness
from tests.ui_edges_support import make_minimal_project


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
    def test_usage_summary_lands_in_unified_bar_and_session_line_is_gone(self):
        """R2989 P1：页内状态行删除；用量摘要入统一底栏左区段（截断+悬停全文）。"""
        import infra.model_pool as model_pool
        import stage_config
        # 不依赖本机全局模型配置：全量里其他用例留下的缓存会让默认模型解析为空。
        self.enterContext(patch('model_pool.pool', return_value=model_pool.default_pool()))
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            stage_config.put(proj, 'script', model='deepseek-v4-flash',
                             skills=['pipeline-script-preparation'])
            d, win = self.desktop(proj)
            self.sync_async(d)
            d.show(0)
            self.settle_script_page(win)
            # 会话说明已按用户裁定删除；页内标签也不再存在。
            self.assertIsNone(getattr(d, 'idea_session_label', None))
            self.assertIsNone(getattr(d, 'idea_usage_label', None))
            # 用量摘要落在统一底栏左区的 usage 段：可见文本紧凑、悬停全文。
            segment = d.status_bar._segments['usage'][1]
            self.assertEqual(segment.full_text, '本模型暂无用量记录')
            self.assertIn('本模型暂无用量记录', segment.tooltip.text)

    def test_notifier_and_legacy_status_bridge_into_unified_bar(self):
        """R2989 P1：错误经总线进右区消息并镜像回 StringVar；旧 StringVar 写入也进右区。"""
        import infra.model_pool as model_pool
        import stage_config
        self.enterContext(patch('model_pool.pool', return_value=model_pool.default_pool()))
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            stage_config.put(proj, 'script', model='deepseek-v4-flash',
                             skills=['pipeline-script-preparation'])
            d, win = self.desktop(proj)
            self.sync_async(d)
            d.show(0)
            self.settle_script_page(win)

            def pump(span):
                import time as _t
                until = _t.monotonic() + span
                while _t.monotonic() < until:
                    win.update()
                    _t.sleep(.01)
                win.update()

            d.notifier.error('生成失败')
            pump(.2)
            self.assertEqual(d.status_bar.message.full_text, '✕ 生成失败')
            self.assertEqual(d.status.get(), '生成失败')
            d.status.set('路径已切换 D:/x')
            pump(.2)
            self.assertEqual(d.status_bar.message.full_text, '路径已切换 D:/x')
            self.assertEqual(d.status_bus.current.level, 'info')

    def test_notifier_error_is_logged(self):
        """R3029 P3：错误必落盘——通知错误写入应用日志（含脱敏过滤的轮转日志）。"""
        import infra.model_pool as model_pool
        import stage_config
        self.enterContext(patch('model_pool.pool', return_value=model_pool.default_pool()))
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            stage_config.put(proj, 'script', model='deepseek-v4-flash',
                             skills=['pipeline-script-preparation'])
            d, win = self.desktop(proj)
            self.sync_async(d)
            d.show(0)
            self.settle_script_page(win)
            with self.assertLogs('ui_widgets', level='ERROR') as captured:
                d.notifier.error('记录日志')
            self.assertTrue(any('记录日志' in line for line in captured.output))


if __name__ == '__main__':
    unittest.main(verbosity=2)