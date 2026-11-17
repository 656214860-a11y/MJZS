"""P2：已迁移的 UI 页面不得重新耦合 Windows ``os.startfile``。"""
import ast
import unittest
from pathlib import Path

from tests.architecture._scan import entity_file


ROOT = Path(__file__).resolve().parents[2]
MIGRATED = (
    'desktop.py', 'storyboard_files.py', 'asset_detail.py', 'asset_batch.py',
    'asset_reference_images.py', 'keyframe_comfy.py', 'local_previs.py',
    'white_model.py', 'shared_video_controls.py', 'app.py', 'comfy_runtime.py',
)


class PlatformOpeningTests(unittest.TestCase):
    def test_migrated_ui_modules_do_not_call_windows_startfile(self):
        offenders = []
        for name in MIGRATED:
            tree = ast.parse(entity_file(Path(name).stem).read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                func = node.func if isinstance(node, ast.Call) else None
                if (isinstance(func, ast.Attribute) and func.attr == 'startfile'
                        and isinstance(func.value, ast.Name) and func.value.id == 'os'):
                    offenders.append(f'{name}:{node.lineno}')
        self.assertEqual(offenders, [], '请改用 platform_tools：' + ', '.join(offenders))
