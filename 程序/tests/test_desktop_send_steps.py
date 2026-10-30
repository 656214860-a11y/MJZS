# -*- coding: utf-8 -*-
"""REQ-S01-71：桌面续发的项目材料按写作步骤取，不把下游成果塞进上游任务；确认件优先。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import desktop_send_ledger as ledger
from workflow_tasks import creative_source

DISPLAY = 'Google Gemini 4 Argon'
OUTLINE_REQUEST = '查看附件项目大纲: 分析分集大纲的逻辑矛盾\n【附档：剧本.md】\n第一集 自然剧本正文'


class RequestStepTests(unittest.TestCase):
    def test_req_s01_71_named_step_ignores_attachment_text(self):
        self.assertEqual(ledger.request_step(OUTLINE_REQUEST), 1)
        self.assertEqual(ledger.request_step('请修改剧本大纲第三集'), 1)
        self.assertEqual(ledger.request_step('角色卡里主角年龄改成 30'), 2)
        self.assertEqual(ledger.request_step('写第 2 集自然剧本'), 3)
        self.assertEqual(ledger.request_step('先改设定'), 0)
        self.assertIsNone(ledger.request_step('请继续'))
        self.assertIsNone(ledger.request_step(''))

    def test_req_s01_71_unnamed_step_follows_confirmed_progress(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(ledger, '_confirmed_documents', return_value={}):
                self.assertEqual(ledger.current_step(td, '请继续'), 3)
            with patch.object(ledger, '_confirmed_documents', return_value={'项目设定': Path(td) / 'a.md'}):
                self.assertEqual(ledger.current_step(td, '请继续'), 1)
            both = {'项目设定': Path(td) / 'a.md', '项目大纲': Path(td) / 'b.md'}
            with patch.object(ledger, '_confirmed_documents', return_value=both):
                self.assertEqual(ledger.current_step(td, '请继续'), 2)
                self.assertEqual(ledger.current_step(td, '再看一下设定'), 0)

    def test_req_s01_71_creative_source_takes_last_user_block(self):
        task = '规则\n<剧本正文>\n旧素材\n</剧本正文>\n中间\n<剧本正文>\n' + OUTLINE_REQUEST + '\n</剧本正文>\n尾'
        self.assertEqual(creative_source(task), OUTLINE_REQUEST)
        self.assertEqual(creative_source('没有素材块'), '')


class StepMaterialTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name) / '摄影侠'
        self.project.mkdir()
        self.confirmed = Path(temp.name) / '别的模型' / '项目设定.md'
        self.adopted = Path(temp.name) / '当前剧本.md'

    def targets(self, request):
        with patch.object(ledger, '_confirmed_documents', return_value={'项目设定': self.confirmed}), \
                patch('script_contract.script_baseline_path', return_value=self.adopted):
            return dict(ledger.material_targets(self.project, DISPLAY, request))

    def test_req_s01_71_outline_step_excludes_character_cards_and_script(self):
        items = self.targets(OUTLINE_REQUEST)
        self.assertEqual(list(items), ['已确认简报', '项目设定', '项目大纲'])
        self.assertEqual(items['项目设定'], self.confirmed)

    def test_req_s01_71_falls_back_to_latest_outline_from_other_model_folder(self):
        from stage_path_service import write_dir
        outline = write_dir(self.project, 'script') / 'Google' / DISPLAY / '创意_20261018' / '项目大纲' / '大纲.md'
        outline.parent.mkdir(parents=True)
        outline.write_text('# 项目大纲\n分集大纲正文', encoding='utf-8')
        items = self.targets(OUTLINE_REQUEST)
        self.assertEqual(Path(items['项目大纲']).resolve(), outline.resolve())
        self.assertEqual(items['项目设定'], self.confirmed)

    def test_req_s01_71_script_step_keeps_all_materials(self):
        items = self.targets('写第 2 集自然剧本')
        self.assertEqual(list(items), ['已确认简报', '项目设定', '项目大纲', '角色卡', '自然剧本', '当前采用的自然剧本'])
        self.assertEqual(items['当前采用的自然剧本'], self.adopted)
        self.assertEqual(items['项目设定'], self.confirmed)


if __name__ == '__main__':
    unittest.main()
