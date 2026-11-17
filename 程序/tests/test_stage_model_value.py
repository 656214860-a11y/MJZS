import tempfile
import unittest

import stage_config
from contract.production_model_contract import SEEDREAM_KEYFRAME_MODEL
from stage_model_value import value


class StageModelValueTests(unittest.TestCase):
    def test_reads_the_model_saved_by_stage_config(self):
        with tempfile.TemporaryDirectory() as project:
            stage_config.put(project, 'keyframe', model=SEEDREAM_KEYFRAME_MODEL)
            self.assertEqual(SEEDREAM_KEYFRAME_MODEL, value(project, 'keyframe'))

    def test_production_locks_support_flat_and_legacy_workflow(self):
        from agent.core import save
        from contract.stage_layout import skill_config_path
        from stage_model_value import production_locks
        with tempfile.TemporaryDirectory() as project:
            path = skill_config_path(project)
            self.assertEqual(production_locks(project), {})
            save(path, {'production_locks': {'aspect_ratio': '16:9'}})
            self.assertEqual(production_locks(project), {'aspect_ratio': '16:9'})
            save(path, {'workflow': {'name': '旧流程', 'lock': {'旧流程': {'画幅': '9:16'}}}})
            self.assertEqual(production_locks(project)['aspect_ratio'], '9:16')
            save(path, {'workflow': {'name': '无锁'}})
            self.assertEqual(production_locks(project), {})

    def test_missing_model_and_invalid_json_return_empty_value(self):
        from agent.core import save, save_text
        from contract.stage_layout import skill_config_path
        with tempfile.TemporaryDirectory() as project:
            self.assertEqual(value(project, 'script'), '')
            save(skill_config_path(project), [])
            self.assertEqual(value(project, 'script'), '')
            save_text(skill_config_path(project), '{损坏')
            self.assertEqual(value(project, 'script'), '')

    def test_unknown_stage_is_rejected(self):
        with tempfile.TemporaryDirectory() as project:
            with self.assertRaisesRegex(ValueError, '没登记'):
                value(project, 'unknown')
