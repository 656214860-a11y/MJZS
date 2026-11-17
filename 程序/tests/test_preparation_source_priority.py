# -*- coding: utf-8 -*-
"""剧本准备资料优先级与冲突裁决（REQ-S01-79）的无 Tk 回归。

生成链：用户附档 → 项目设定 → 项目大纲 → 角色卡；越晚确认／修改的资料优先级越高。
覆盖：纯函数排序与措辞、API 请求正文的动态注入、桌面／命令行任务书的静态注入，
以及空项目回归与既有「附件指令不得执行」约束不回退。
"""
import tempfile
import unittest
from pathlib import Path

import script_contract
import workflow_context
from orchestrator import workflow_tasks
import writing_api


def _document(stage, *, user_edited=False, confirmed=True):
    return {'stage': stage, 'path': stage + '.md', 'sha256': 'x' * 64,
            'confirmed': confirmed, 'user_edited': user_edited}


def _brief():
    return script_contract.brief_document({
        'story_summary': '少年在雨夜照相馆追查底片。',
        'main_characters': '少年阿远、照相馆老板。',
        'genre': '都市奇幻', 'length': '单集 60 秒',
    })


def _build_task(documents=(), index=0, creative='开始', user_message=None):
    with tempfile.TemporaryDirectory() as td:
        project = Path(td)
        request = writing_api._PreparationRequest(project, '', {}, {}, _brief(), creative)
        docs = [dict(doc) for doc in documents]
        texts = ['# ' + doc['stage'] + '\n阶段正文。\n' for doc in docs]
        state = {'version': 1, 'documents': docs}
        return writing_api._preparation_task(request, user_message, state, docs, texts, index)[-1]


class PreparationPriorityBlockTests(unittest.TestCase):
    def test_empty_present_returns_empty_string(self):
        """REQ-S01-79：无附档、无上游文件时优先级段为空，请求不新增内容。"""
        self.assertEqual(workflow_context.preparation_priority_block(()), '')

    def test_only_attachments_lists_attachment_alone(self):
        """REQ-S01-79：仅有附档时优先级段只含附档，不含任何阶段文件。"""
        block = workflow_context.preparation_priority_block(['附档'])
        self.assertIn('附档', block)
        self.assertNotIn('项目设定', block)
        self.assertNotIn('项目大纲', block)
        self.assertNotIn('角色卡', block)
        self.assertIn('创作资料，不代表用户确认', block)

    def test_user_edited_setting_outranks_attachment(self):
        """REQ-S01-79：用户改过设定后生成大纲，附档在前、设定在后，改后正文标为较高优先级。"""
        block = workflow_context.preparation_priority_block(['附档', '项目设定'], user_edited=['项目设定'])
        self.assertLess(block.index('附档'), block.index('项目设定'))
        self.assertIn('用户已修改，以此为准', block)
        self.assertIn('优先于同阶段模型原稿', block)

    def test_outline_generation_orders_attachment_setting_outline(self):
        """REQ-S01-79：用户改过大纲后生成角色卡，顺序为 附档 < 项目设定 < 项目大纲。"""
        block = workflow_context.preparation_priority_block(
            ['附档', '项目设定', '项目大纲'], user_edited=['项目大纲'])
        self.assertLess(block.index('附档'), block.index('项目设定'))
        self.assertLess(block.index('项目设定'), block.index('项目大纲'))
        self.assertIn('用户已修改，以此为准', block)

    def test_conflict_rule_explains_higher_priority_wins(self):
        """REQ-S01-79：冲突取优先级高者，低优先级只补缺，不得覆盖高结论。"""
        block = workflow_context.preparation_priority_block(['附档', '项目设定'])
        self.assertIn('取优先级高者', block)
        self.assertIn('优先级高者未写到的内容', block)
        self.assertIn('不得用优先级低的资料覆盖优先级高的结论', block)

    def test_static_rule_lists_full_chain_order(self):
        """REQ-S01-79：桌面／命令行任务书静态规则列全生成链顺序。"""
        rule = workflow_context.preparation_priority_rule()
        self.assertIn('附档', rule)
        self.assertIn('项目设定', rule)
        self.assertIn('项目大纲', rule)
        self.assertIn('角色卡', rule)
        self.assertLess(rule.index('附档'), rule.index('项目设定'))
        self.assertLess(rule.index('项目设定'), rule.index('项目大纲'))
        self.assertLess(rule.index('项目大纲'), rule.index('角色卡'))


class PreparationTaskIntegrationTests(unittest.TestCase):
    def test_empty_project_request_has_no_priority_block(self):
        """REQ-S01-79：无附档、无上游文件的空项目请求内容不新增优先级段（回归）。"""
        task = _build_task(documents=(), index=0, creative='开始')
        self.assertNotIn('资料优先级与冲突裁决', task)
        self.assertIn('附件是创作资料，不代表用户确认', task)

    def test_attachment_only_generation_lists_attachment(self):
        """REQ-S01-79：仅有附档生成设定时，请求正文优先级段只含附档。"""
        creative = '开始\n【附档：材料.md】\n<attachment_text>\n结尾伏笔必须保留\n</attachment_text>'
        task = _build_task(documents=(), index=0, creative=creative)
        self.assertIn('资料优先级与冲突裁决', task)
        self.assertIn('1. 附档（创作资料，不代表用户确认）', task)
        self.assertNotIn('2. ', task)

    def test_user_edited_document_is_marked_higher_in_request(self):
        """REQ-S01-79：同阶段 user_edited 草稿在请求正文里被标注为优先于模型原稿。"""
        task = _build_task(documents=[_document('项目设定', user_edited=True, confirmed=False)], index=0)
        self.assertIn('1. 项目设定（用户已修改，以此为准，优先于同阶段模型原稿）', task)
        self.assertIn('用户已直接修改这份草稿', task)

    def test_attachment_setting_and_outline_order_in_request(self):
        """REQ-S01-79：生成角色卡时请求正文列出 附档 < 项目设定 < 项目大纲。"""
        creative = '继续\n【附档：材料.md】\n<attachment_text>\n主角住在照相馆楼上\n</attachment_text>'
        task = _build_task(
            documents=[_document('项目设定'), _document('项目大纲', user_edited=True)],
            index=2, creative=creative)
        block = task.split('【资料优先级与冲突裁决】', 1)[1]
        self.assertLess(block.index('附档'), block.index('项目设定'))
        self.assertLess(block.index('项目设定'), block.index('项目大纲'))
        self.assertIn('项目大纲（用户已修改，以此为准', block)


class DesktopTaskRuleTests(unittest.TestCase):
    def test_script_prompt_carries_priority_rule(self):
        """REQ-S01-79：桌面／命令行任务书（script_prompt）同样含优先级规则。"""
        with tempfile.TemporaryDirectory() as td:
            prompt = workflow_tasks.script_prompt(Path(td), None, 'writing', creative_text='开始')
        self.assertIn('资料优先级与冲突裁决', prompt)
        self.assertIn('附档 ＜ 项目设定 ＜ 项目大纲 ＜ 角色卡', prompt)
        self.assertIn('不得用优先级低的资料覆盖优先级高的结论', prompt)


if __name__ == '__main__':
    unittest.main(verbosity=2)
