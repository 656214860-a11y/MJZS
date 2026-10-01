import tempfile
import unittest

import stage_config
from production_model_contract import SEEDREAM_KEYFRAME_MODEL
from stage_model_value import value


class StageModelValueTests(unittest.TestCase):
    def test_reads_the_model_saved_by_stage_config(self):
        with tempfile.TemporaryDirectory() as project:
            stage_config.put(project, 'keyframe', model=SEEDREAM_KEYFRAME_MODEL)
            self.assertEqual(SEEDREAM_KEYFRAME_MODEL, value(project, 'keyframe'))

    def test_unknown_stage_is_rejected(self):
        with tempfile.TemporaryDirectory() as project:
            with self.assertRaisesRegex(ValueError, '没登记'):
                value(project, 'unknown')
