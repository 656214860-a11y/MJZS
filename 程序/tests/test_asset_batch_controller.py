"""资产批量窗口控制器的无 Tk 回归。"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.asset_batch_controller import AssetBatchController, WORKFLOW_MODEL


def _rows(*args, **kwargs):
    return {
        'CHAR_01': {'name': '主角', 'image_prompt': 'portrait'},
        'PROP_01': {'name': '道具', 'image_prompt': 'prop', 'status': '已导入'},
    }


class AssetBatchControllerTests(unittest.TestCase):
    def make_controller(self):
        return AssetBatchController('D:/project', 'D:/base', (), 'all', 'comfy', None, {}, _rows)

    def test_form_defaults_and_options_keep_workflow_sentinel_out_of_executor(self):
        controller = self.make_controller()
        fields, aspect, quality, backend = controller.form_defaults('workflow.json', 'local')
        self.assertEqual(fields['model'], WORKFLOW_MODEL)
        self.assertEqual((aspect, quality, backend), ('1:1', 'medium', 'local'))
        options = controller.options(fields, backend, aspect, quality)
        self.assertEqual(options['model'], '')
        self.assertEqual(options['backend'], 'local')

    def test_detection_filters_deleted_model_without_tk(self):
        controller = self.make_controller()
        models = controller.detect(lambda: ['keep', 'hidden'], 'http://localhost', ['http://localhost:hidden'], lambda url, model: url + ':' + model)
        self.assertEqual(models, ['keep'])

    def test_start_decision_reloads_and_enforces_prompt_gate(self):
        controller = self.make_controller()
        decision = controller.start_decision(True, {'CHAR'}, lambda aid, asset: [],
                                             {'workflow': 'x.json', 'model': ''}, 'local', 'local', ['CHAR_01'])
        self.assertEqual([aid for aid, _ in decision.items], ['CHAR_01'])
        self.assertEqual(decision.uncertain_ids, ['CHAR_01'])
        with self.assertRaisesRegex(ValueError, '补齐资产清单'):
            controller.start_decision(True, {'CHAR'}, lambda aid, asset: ['提示词'],
                                      {'workflow': 'x.json', 'model': ''}, 'local', 'local', [])


if __name__ == '__main__':
    unittest.main()
