# -*- coding: utf-8 -*-
"""R2166：模型管理里删掉的模型，打开项目时的「阶段配置同步」不得补回；当前项目里选了它的阶段改回「自动」。"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import infra.model_pool as model_pool
import infra.model_router as model_router
import skill_panel_support
import stage_config
from pet_ui_settings import PetSettingsMixin

API = {'label': '我的 API', 'model': 'my-api', 'base_url': 'https://example.invalid/v1', 'key_env': 'MY_KEY'}


class FakePet(PetSettingsMixin):
    def __init__(self, program, project=None):
        self.program = program
        self.desktop = SimpleNamespace(root=str(project) if project else None)
        self.notice = ''

    def apply_agent_models(self):
        return None

    def _refresh_model_choices(self):
        return 0

    def speak(self):
        return None


class DeletedModelStaysDeletedTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.program = Path(temp.name) / 'program'
        self.project = Path(temp.name) / 'project'
        self.program.mkdir()
        self.project.mkdir()
        model_pool.store(model_pool.upsert({}, API, 'my-api'), self.program)

    def delete(self, model_id):
        model_pool.store(model_pool.remove(model_pool.raw(self.program), model_id), self.program)

    def test_sync_does_not_bring_back_a_deleted_desktop_model(self):
        """用户报的那条：剧本结构还选着 claude-desktop-app，删掉后一开项目就被补成一条缺根地址的 API 记录。"""
        stage_config.put(self.project, 'script_structure', model='claude-desktop-app')
        self.delete('claude-desktop-app')
        self.assertEqual(skill_panel_support.sync_models(self.project, self.program), [])
        self.assertNotIn('claude-desktop-app', model_pool.pool(program=self.program))

    def test_sync_does_not_bring_back_a_deleted_api_model(self):
        stage_config.put(self.project, 'script', model='my-api')
        self.delete('my-api')
        self.assertEqual(skill_panel_support.sync_models(self.project, self.program), [])
        self.assertNotIn('my-api', model_pool.pool(program=self.program))

    def test_saving_it_again_lifts_the_deletion(self):
        self.delete('my-api')
        restored = model_pool.upsert(model_pool.raw(self.program), API, 'my-api')
        self.assertIn('my-api', model_pool.pool(restored))
        self.assertNotIn('my-api', restored.get('deleted_desktop_models', []))

    def test_delete_moves_the_current_project_stages_back_to_auto(self):
        model_pool.store(model_pool.upsert(model_pool.raw(self.program), {'label': '别的', 'model': 'other'}, 'other'),
                         self.program)
        stage_config.put(self.project, 'script_structure', model='my-api')
        stage_config.put(self.project, 'script', model='other')
        pet = FakePet(self.program, self.project)
        self.assertEqual(pet.pool_model_stages('my-api'), ['剧本结构'], '确认框要先列出会改成「自动」的阶段')
        pet.delete_pool_model('my-api')
        self.assertEqual(stage_config.get(self.project, 'script_structure')['model'], model_router.AUTO)
        self.assertEqual(stage_config.get(self.project, 'script')['model'], 'other', '没选它的阶段不动')
        self.assertIn('1 个阶段', pet.notice)
        self.assertNotIn('my-api', model_pool.pool(program=self.program))

    def test_no_open_project_only_touches_the_pool(self):
        pet = FakePet(self.program)
        self.assertEqual(pet.pool_model_stages('my-api'), [])
        pet.delete_pool_model('my-api')
        self.assertNotIn('my-api', model_pool.pool(program=self.program))
        self.assertNotIn('阶段', pet.notice)


if __name__ == '__main__':
    unittest.main()
