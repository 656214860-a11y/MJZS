import tempfile
import unittest

import stage_config
from keyframe_model_service import current_model, production_choices
from production_model_contract import SEEDREAM_KEYFRAME_MODEL


class KeyframeModelServiceTests(unittest.TestCase):
    def test_stage_configuration_is_the_model_source_of_truth(self):
        with tempfile.TemporaryDirectory() as td:
            stage_config.put(td, 'keyframe', model=SEEDREAM_KEYFRAME_MODEL)
            self.assertEqual(current_model(td), SEEDREAM_KEYFRAME_MODEL)

    def test_production_choices_always_include_the_two_native_models(self):
        values = [value for value, _label in production_choices('unused-project')]
        self.assertIn(SEEDREAM_KEYFRAME_MODEL, values)


if __name__ == '__main__':
    unittest.main(verbosity=2)
