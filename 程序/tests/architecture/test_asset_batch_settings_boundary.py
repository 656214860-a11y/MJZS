"""Asset-batch UI may delegate settings persistence but must not own it."""
import ast
import unittest
from pathlib import Path

from tests.architecture._scan import entity_file


ROOT = Path(__file__).resolve().parents[2]


class AssetBatchSettingsBoundaryTests(unittest.TestCase):
    def test_ui_delegates_settings_persistence_to_service(self):
        tree = ast.parse(entity_file('asset_batch').read_text(encoding='utf-8'))
        imported = {name.name for node in tree.body if isinstance(node, ast.ImportFrom)
                    and node.module == 'stage_execution_service' for name in node.names}
        self.assertEqual(imported, {'remove_asset_batch_model', 'save_asset_batch_settings'})
        direct_save = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Call)
                       and isinstance(node.func, ast.Name) and node.func.id == 'save']
        self.assertEqual(direct_save, [], '资产批处理 UI 不得直接保存批量设置: ' + str(direct_save))

    def test_settings_service_uses_project_settings_reader_and_atomic_save(self):
        tree = ast.parse(entity_file('asset_batch_settings_service').read_text(encoding='utf-8'))
        imported = {(node.module, name.name) for node in tree.body if isinstance(node, ast.ImportFrom)
                    for name in node.names}
        self.assertIn(('project_settings', 'read_prefs'), imported)
        self.assertNotIn(('agent.core', 'save'), imported)
