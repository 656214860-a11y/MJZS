# -*- coding: utf-8 -*-
"""REQ-S01-75：模型管理删除模型时，确认框列出指向它的 SKILL 预设，删除后这些预设的模型改回「自动」。"""
import tempfile
import unittest
from pathlib import Path

import infra.model_pool as model_pool
import infra.model_router as model_router
import stage_config
from pet_ui_settings import PetSettingsMixin

SKILLS = ['pipeline-script-preparation']


class FakePet(PetSettingsMixin):
    def __init__(self, program):
        self.program = program
        self.notice = ''

    def apply_agent_models(self):
        return None

    def _refresh_model_choices(self):
        return 0

    def speak(self):
        return None


class ModelDeletePresetTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.program = Path(temp.name)
        data = {'models': {}}
        for model_id, label, model in (('gemini-argon', 'Google Gemini 4 Argon', 'shared-name'),
                                       ('Google Gemini', 'Google Gemini', 'shared-name')):
            data = model_pool.upsert(data, {'label': label, 'model': model}, model_id)
        model_pool.store(data, self.program)
        stage_config._save_preset_groups({
            'script': {'Gemini 4': {'model': 'google gemini 4 argon', 'skills': SKILLS},
                       '按 ID': {'model': 'gemini-argon', 'skills': SKILLS},
                       '别的模型': {'model': 'Google Gemini', 'skills': SKILLS},
                       '共用名': {'model': 'shared-name', 'skills': SKILLS},
                       '自动': {'model': model_router.AUTO, 'skills': SKILLS}}}, self.program)
        self.pet = FakePet(self.program)

    def test_req_s01_75_confirm_lists_presets_pointing_to_the_model(self):
        self.assertEqual(self.pet.pool_model_presets('gemini-argon'),
                         [('剧本准备', 'Gemini 4'), ('剧本准备', '按 ID')])

    def test_req_s01_75_delete_releases_only_dangling_preset_models(self):
        self.pet.delete_pool_model('gemini-argon')
        self.assertNotIn('gemini-argon', model_pool.pool(program=self.program))
        presets = stage_config.presets(self.program, 'script')
        self.assertEqual(presets['Gemini 4'], {'model': model_router.AUTO, 'skills': SKILLS})
        self.assertEqual(presets['按 ID']['model'], model_router.AUTO)
        # 仍有别的模型用这个名字时不动：预设并没有失效。
        self.assertEqual(presets['别的模型']['model'], 'Google Gemini')
        self.assertEqual(presets['共用名']['model'], 'shared-name')
        self.assertEqual(presets['自动']['model'], model_router.AUTO)
        self.assertIn('2 个预设的模型已改为「自动」', self.pet.notice)

    def test_req_s01_75_no_reference_leaves_preset_file_untouched(self):
        before = stage_config.preset_path(self.program).read_bytes()
        self.pet.delete_pool_model('不存在的模型')
        self.assertEqual(stage_config.preset_path(self.program).read_bytes(), before)
        self.assertNotIn('预设', self.pet.notice)


if __name__ == '__main__':
    unittest.main()
