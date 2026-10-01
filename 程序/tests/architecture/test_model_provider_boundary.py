"""P2：供应商适配器只依赖模型基础设施，不得反向依赖三虎客户端。"""
import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROVIDER_ADAPTERS = ('seedream_api.py', 'qwen_adapter.py')


def imported_modules(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


class ModelProviderBoundaryTests(unittest.TestCase):
    def test_provider_adapters_do_not_import_pet_llm(self):
        offenders = [name for name in PROVIDER_ADAPTERS
                    if 'pet_llm' in imported_modules(ROOT / name)]
        self.assertEqual(offenders, [], '供应商只可依赖协议/密钥接口：' + ', '.join(offenders))

    def test_shared_protocol_does_not_depend_on_clients_or_providers(self):
        imports = imported_modules(ROOT / 'model_protocol.py')
        self.assertFalse({'pet_llm', 'model_pool', 'seedream_api', 'qwen_adapter'} & imports)

