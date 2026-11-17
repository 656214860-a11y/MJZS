"""Visible branding shares one source while existing data paths stay compatible."""
import ast
import os
from pathlib import Path
import unittest
from unittest import mock

from tests.architecture._scan import entity_file
from contract import app_metadata
import app_shortcut
import asset_thumbs
import cloud_assets
import infra.pet_llm as pet_llm
import pet_settings_ui
import ui.pet_ui as pet_ui
import qwen_setup
import seedream_api
from domain import tts_api
import white_model_service


PROGRAM = Path(__file__).resolve().parents[1]
ROOT = PROGRAM.parent
LEGACY_NAME = '漫剧制作助手'
DISPLAY_SOURCES = (
    PROGRAM / 'desktop.py', PROGRAM / 'ui/ui_splash.py', entity_file('pet_ui_settings'),  # 启动画面随 Splash 自 ui_widgets 拆到 ui_splash；R1506：APP_NAME 的用法随设置方法迁到 pet_ui_settings；R1793：启动画面（ui_widgets 的 APP_NAME 用法）被 .pyw 引用，R1788 误删后恢复
    entity_file('pet_settings_ui'), PROGRAM / 'app_shortcut.py',
    entity_file('pet_llm'), PROGRAM / 'scripts' / 'clean_dev.py',
    ROOT / '启动漫剧制作助手.pyw',
)


class AppMetadataTests(unittest.TestCase):
    def test_visible_name_exports_share_metadata(self):
        self.assertEqual(app_metadata.APP_NAME, '漫剧助手')
        self.assertEqual(app_metadata.VERSION, 'V0.7')
        self.assertEqual(app_shortcut.NAME, app_metadata.APP_NAME)
        self.assertEqual(pet_settings_ui.APP_TITLE, app_metadata.APP_NAME)
        for prefix in (pet_llm.SYSTEM_PREFIX, pet_llm.CHAT_PREFIX):
            self.assertIn(app_metadata.APP_NAME, prefix)
            self.assertNotIn(LEGACY_NAME, prefix)

    def test_display_producers_import_the_shared_name(self):
        for path in DISPLAY_SOURCES:
            with self.subTest(path=path.name):
                tree = ast.parse(path.read_text(encoding='utf-8-sig'))
                self.assertTrue(any(
                    isinstance(node, ast.ImportFrom) and node.module == 'contract.app_metadata'
                    and any(alias.name == 'APP_NAME' for alias in node.names)
                    for node in ast.walk(tree)))
                self.assertTrue(any(isinstance(node, ast.Name) and node.id == 'APP_NAME'
                                    and isinstance(node.ctx, ast.Load)
                                    for node in ast.walk(tree)))
                # A literal here would make changing metadata silently miss this surface.
                self.assertFalse(any(isinstance(node, ast.Constant)
                                     and node.value == app_metadata.APP_NAME
                                     for node in ast.walk(tree)))

    def test_legacy_literals_in_display_producers_are_only_identifiers(self):
        allowed = {
            'app_shortcut.py': {LEGACY_NAME + '.ico', '启动' + LEGACY_NAME + '.pyw'},
            'pet_ui_support.py': {LEGACY_NAME + '·宠物助手', '启动' + LEGACY_NAME + '.pyw'},  # R1506：这两个标识符常量随 pet_ui 模块级迁到 support
        }
        for path in DISPLAY_SOURCES + (PROGRAM / 'ui' / 'pet_ui_support.py',):
            with self.subTest(path=path.name):
                tree = ast.parse(path.read_text(encoding='utf-8-sig'))
                docstrings = set()
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                         ast.AsyncFunctionDef)) and node.body:
                        first = node.body[0]
                        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                            docstrings.add(first.value)
                actual = {node.value for node in ast.walk(tree)
                          if isinstance(node, ast.Constant) and isinstance(node.value, str)
                          and LEGACY_NAME in node.value and node not in docstrings}
                self.assertEqual(actual, allowed.get(path.name, set()))

    def test_persistent_identifiers_and_data_paths_keep_their_names(self):
        self.assertEqual(app_shortcut.ICON_NAME, LEGACY_NAME + '.ico')
        self.assertEqual(app_shortcut.LAUNCHER, '启动' + LEGACY_NAME + '.pyw')
        self.assertEqual(pet_ui.AUTOSTART_NAME, LEGACY_NAME + '·宠物助手')
        self.assertEqual(asset_thumbs.CACHE_ROOT.parent.name, 'AI' + LEGACY_NAME)
        # These functions only calculate paths; no user configuration is opened or written.
        base = PROGRAM / '.selftmp' / 'R1446_metadata_paths'
        with mock.patch.dict(os.environ, {'LOCALAPPDATA': str(base)}):
            expected = base / LEGACY_NAME
            self.assertEqual(cloud_assets._secret_file(), expected / 'comfy_cloud_key.dpapi')
            self.assertEqual(qwen_setup.settings_path(), expected / 'qwen-api.json')
            self.assertEqual(seedream_api.settings_path(), expected / 'seedream_profiles.json')
            self.assertEqual(tts_api.settings_path(), expected / 'tts_settings.json')
            self.assertEqual(white_model_service.user_data_dir(), expected)

    def test_user_guide_stage_table_matches_stage_authority(self):
        """使用说明的阶段表必须与 pet_bus／stage_layout 的权威阶段一致，防止文档落后于阶段数。"""
        import pet_bus
        import stage_layout

        text = (ROOT / '使用说明.md').read_text(encoding='utf-8')
        rows = []
        for line in text.splitlines():
            if not line.startswith('|'):
                continue
            cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
            if len(cells) != 3 or not cells[0].isdigit():
                continue
            rows.append((cells[1], cells[2].strip('`').rstrip('/')))
        expected = [(name, folder) for folder, _stage, name, *_rest in stage_layout.STAGES]
        self.assertEqual(expected, rows)
        self.assertIn('%d 个制作阶段' % len(pet_bus.STAGES), text)
        self.assertIn('“%d 参考网站”' % (len(pet_bus.STAGES) + 1), text)

    def test_current_document_titles_use_the_visible_name(self):
        for path in (PROGRAM / 'tasks_round' / '归档' / '2026-11_历史文档' / 'agent-handoff' / 'GLOSSARY.md',
                     ROOT / '使用说明.md', ROOT / '使用说明.txt',
                     PROGRAM / 'README.md', PROGRAM / 'PROJECT_MAP.md',
                     PROGRAM / 'architecture.md', PROGRAM / '说明' / '维护约定.md'):
            with self.subTest(path=path.name):
                title = path.read_text(encoding='utf-8').splitlines()[0]
                self.assertIn(app_metadata.APP_NAME, title)
                self.assertNotIn(LEGACY_NAME, title)


if __name__ == '__main__':
    unittest.main()
