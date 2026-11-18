"""云端资产模型契约（轮 6B／D7）：节点类型与参考图上限按模型名寻址。

``ASSET_CLOUD_MODELS`` 的顺序只服务于 UI 选项排序；节点类型与参考图上限
是按模型名查的命名映射，往元组中间插一个模型不得错位既有条目。
"""
import importlib
import unittest

import contract.production_model_contract as production_model_contract
import infra.cloud_assets as cloud_assets


class CloudAssetModelCapabilityTests(unittest.TestCase):
    EXPECTED = {
        'Seedream 5.0 Pro': ('ByteDanceSeedreamNode', 10),
        'Nano Banana Pro': ('GeminiImage2Node', 14),
        'GPT Image 2': ('OpenAIGPTImage1', 16),
    }

    def test_named_capability_maps_cover_exactly_the_ordered_models(self):
        contract = production_model_contract
        self.assertEqual(set(contract.ASSET_CLOUD_NODE_TYPES),
                         set(contract.ASSET_CLOUD_MODELS))
        self.assertEqual(set(contract.ASSET_CLOUD_REFERENCE_LIMITS),
                         set(contract.ASSET_CLOUD_MODELS))
        for name, (node_type, limit) in self.EXPECTED.items():
            self.assertEqual(contract.ASSET_CLOUD_NODE_TYPES[name], node_type)
            self.assertEqual(contract.ASSET_CLOUD_REFERENCE_LIMITS[name], limit)

    def test_mid_tuple_insert_keeps_existing_models_node_type_and_limit(self):
        """往 ``ASSET_CLOUD_MODELS`` 中间插一个模型，重建消费端后既有模型的节点类型与上限不变。"""
        original = production_model_contract.ASSET_CLOUD_MODELS
        try:
            production_model_contract.ASSET_CLOUD_MODELS = (
                original[0], '探针云端模型', *original[1:])
            importlib.reload(cloud_assets)
            # 元组仍驱动有序清单（UI 选项顺序），插入项出现在中间
            self.assertEqual(cloud_assets.MODELS,
                             list(production_model_contract.ASSET_CLOUD_MODELS))
            self.assertEqual(cloud_assets.MODELS[1], '探针云端模型')
            # 但节点类型与上限按名字查：既有模型逐项不变
            for name, (node_type, limit) in self.EXPECTED.items():
                self.assertEqual(cloud_assets.NODE_TYPES[name], node_type)
                self.assertEqual(cloud_assets.LIMITS[name], limit)
        finally:
            production_model_contract.ASSET_CLOUD_MODELS = original
            importlib.reload(cloud_assets)


if __name__ == '__main__':
    unittest.main()
