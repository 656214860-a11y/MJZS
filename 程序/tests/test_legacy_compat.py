# -*- coding: utf-8 -*-
"""历史只读兼容门面的回归。"""
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator import legacy_compat


class LegacyCompatTests(unittest.TestCase):
    def test_alias_resolution_delegates_to_single_compatibility_seam(self):
        project = Path('project')
        path = Path('old/episode.json')
        with patch('storyboard_storage.resolved_alias', return_value=Path('new/episode.json')) as resolve:
            self.assertEqual(legacy_compat.resolved_storyboard_alias(project, path), Path('new/episode.json'))
        resolve.assert_called_once_with(project, path)

    def test_canonical_stage_name_keeps_unknown_and_maps_legacy(self):
        self.assertEqual(legacy_compat.canonical_stage_name('00_script'), '01剧本准备')
        self.assertEqual(legacy_compat.canonical_stage_name('unrecognized'), 'unrecognized')
        self.assertEqual(legacy_compat.RETIRE_AFTER, '2027-03-31')

    def test_optional_workflow_model_name_delegates_and_normalizes_empty(self):
        with patch('workflow_settings.model_name', return_value='DeepSeek V4 Flash') as model:
            self.assertEqual(legacy_compat.optional_workflow_model_name(Path('project'), 'previs'), 'DeepSeek V4 Flash')
        model.assert_called_once_with(Path('project'), 'previs')

    def test_optional_model_identity_centralizes_pool_lookup_and_fallback(self):
        records = {'deepseek': {'label': 'DeepSeek V4 Flash', 'provider': 'DeepSeek'}}
        with patch('model_pool.pool', return_value=records), \
             patch('model_pool.options', return_value=['DeepSeek V4 Flash']), \
             patch('model_pool.id_of_label', return_value='deepseek'), \
             patch('model_pool.provider_name', return_value='DeepSeek'):
            self.assertEqual(
                legacy_compat.optional_model_identity('DeepSeek V4 Flash', Path('program')),
                ('DeepSeek', 'DeepSeek V4 Flash'))

    def test_optional_asset_counts_uses_state_service_and_registry_reader(self):
        with patch('asset_batch_state_service.ready_asset_ids', return_value={'CHAR_001'}):
            self.assertEqual(legacy_compat.optional_asset_counts(Path('project'),
                             lambda path: {'CHAR_001': {}, 'LOC_001': {}}), (2, 1))


if __name__ == '__main__':
    unittest.main()
