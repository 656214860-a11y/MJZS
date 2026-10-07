"""R1115：转换稿在应用内解析，不为缺项单独启动模型。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import idea_chat
import script_contract
import workflow_settings
from tests.test_idea_chat import _Harness, idea_chat as injected_chat
from tests.test_ui_edges import make_minimal_project


MATERIAL = '''| 字段 | 内容 |
| --- | --- |
| 故事主线 | 修表师寻找失踪的父亲 |
| 故事人物 | 林青与阿禾 |
| 题材类型 | 冒险喜剧 |
| 篇幅 | 12集，每集120秒 |
| 故事画幅 | 9:16 |
| 视频模型 | MiniMax H3 |
| 交付形态 | markdown文档 |
'''


class LocalBriefTests(unittest.TestCase):
    def test_markdown_table_aliases_share_gate_and_contract(self):
        fields = idea_chat.extract_brief_creation(MATERIAL,
            extra_labels=script_contract.INLINE_REQUIRED_LABELS, include_extra=True)
        self.assertEqual(fields.get('故事角色'), '林青与阿禾')
        self.assertEqual(idea_chat.inline_required_missing(None, '', attachment_fields=fields), ())
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            preset = next(iter(workflow_settings.WORKFLOW_PRESETS.values()))
            result = injected_chat.receive_brief(root, '【附档：输入/材料.md】', inline_text='',
                lock_definitions=preset['locks'], attachment_reference={'brief_texts': [MATERIAL]})
            self.assertEqual(result['missing'], ())
            self.assertEqual(result['fields']['story_summary'], '修表师寻找失踪的父亲')
            self.assertEqual(result['fields']['main_characters'], '林青与阿禾')
            self.assertEqual(result['fields']['production_locks'], {
                'aspect_ratio': '9:16', 'video_model_version': 'MiniMax H3',
                'delivery_format': 'markdown文档'})

    def test_bold_and_heading_fields_do_not_require_model(self):
        fields = idea_chat.extract_brief_creation(
            '## 故事人物\n林青\n阿禾\n**题材类型**：冒险喜剧\n### 故事主线\n寻找父亲')
        self.assertEqual(fields, {'故事角色': '林青\n阿禾',
                                 '故事题材': '冒险喜剧', '故事梗概': '寻找父亲'})


class LocalBriefDesktopTests(_Harness):
    @patch('stage_execution_service.idea_attachment_local_mode', return_value=True)
    def test_complete_table_goes_directly_to_script_workflow(self, _local):
        from stage_execution_service import archive_idea_attachments
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            source = Path(td) / '材料.md'
            source.write_text(MATERIAL, encoding='utf-8')
            paths = archive_idea_attachments(root, [source])
            d, win = self.desktop(root)
            d.show(0); self.settle_script_page(win)
            d.idea_attachment_paths = tuple(paths)
            with patch.object(d, 'start_idea_semantic_brief') as extract, \
                    patch.object(d, 'start_script_workflow', return_value=('Codex', False)) as launch, \
                    patch.object(d.notifier, 'info') as notice:
                d.send_message()
            extract.assert_not_called()
            notice.assert_not_called()
            launch.assert_called_once()
            self.assertIn('【附档：01剧本准备/输入/', launch.call_args.args[0])
            self.assertNotIn('修表师寻找失踪的父亲', launch.call_args.args[0])

    @patch('stage_execution_service.idea_attachment_local_mode', return_value=True)
    def test_missing_field_prompts_without_separate_request(self, _local):
        from stage_execution_service import archive_idea_attachments
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            source = Path(td) / '材料.md'
            source.write_text(MATERIAL.replace('| 交付形态 | markdown文档 |', ''), encoding='utf-8')
            paths = archive_idea_attachments(root, [source])
            d, win = self.desktop(root)
            d.show(0); self.settle_script_page(win)
            d.idea_attachment_paths = tuple(paths)
            with patch.object(d, 'start_idea_semantic_brief') as extract, \
                    patch.object(d, 'start_script_workflow') as launch, \
                    patch.object(d.notifier, 'info') as notice:
                d.send_message()
            extract.assert_not_called()
            launch.assert_not_called()
            self.assertEqual(tuple(d._idea_missing_dialog.brief_fields), ('交付形态',))
            notice.assert_not_called()
            self.assertFalse(injected_chat.brief_raw_path(root).exists())
