# -*- coding: utf-8 -*-
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import previs_batch_service


class PrevisBatchServiceTests(unittest.TestCase):
    def test_prepare_batch_writes_only_selected_shots_to_atomic_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / '项目'
            source = project / 'episode.json'
            project.mkdir()
            source.write_text(json.dumps({'shots': [
                {'id': 'SH001', 'title': '第一镜'}, {'id': 'SH002', 'title': '第二镜'},
            ]}, ensure_ascii=False), encoding='utf-8')
            captured = {}
            def prompt_with_settings(prompt, config):
                captured['prompt'] = prompt
                captured['config'] = config
                return prompt
            with patch('white_model_service.find_blender', return_value=Path('D:/Blender/blender.exe')), \
                 patch('agent.shot_assets.assets', return_value=[]), \
                 patch('workflow_engines.prompt_with_settings', prompt_with_settings):
                prompt = previs_batch_service.prepare_batch(project, source, ['SH002'], {'engine': 'codex'})

            manifest = next((project / '工作流任务' / '白模批量任务').rglob('勾选镜头.json'))
            data = json.loads(manifest.read_text(encoding='utf-8'))
            self.assertEqual(['SH002'], [shot['storyboard']['id'] for shot in data['shots']])
            self.assertIn(str(manifest), prompt)
            self.assertEqual({'engine': 'codex'}, captured['config'])

    def test_prepare_batch_rejects_missing_or_changed_selected_shot(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            source = project / 'episode.json'
            source.write_text(json.dumps({'shots': [{'id': 'SH001'}]}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '镜头清单发生变化'):
                previs_batch_service.prepare_batch(project, source, ['SH404'], {'engine': 'codex'})

    def test_prepare_batch_observes_episode_republished_after_cached_read(self):
        """分镜正式 JSON 原子重发后，批处理不得继续使用旧选镜。"""
        from agent.core import save
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            source = project / 'episode.json'
            save(source, {'shots': [{'id': 'SH001', 'title': '第一镜'}]})
            with patch('white_model_service.find_blender', return_value=None), \
                 patch('agent.shot_assets.assets', return_value=[]), \
                 patch('workflow_engines.prompt_with_settings', side_effect=lambda prompt, _config: prompt):
                previs_batch_service.prepare_batch(project, source, ['SH001'], {'engine': 'codex'})
                save(source, {'shots': [{'id': 'SH002', 'title': '第二镜'}]})
                with self.assertRaisesRegex(ValueError, '镜头清单发生变化'):
                    previs_batch_service.prepare_batch(project, source, ['SH001'], {'engine': 'codex'})


if __name__ == '__main__':
    unittest.main()
