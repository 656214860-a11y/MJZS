"""启动器 .pyw 引用的程序符号必须真实存在。"""
import ast
import importlib
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
LAUNCHERS = (PROGRAM.parent / '启动漫剧制作助手.pyw', PROGRAM / 'h3_launcher.pyw')


def _program_imports(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            if (PROGRAM / (node.module.split('.')[0] + '.py')).is_file():
                for alias in node.names:
                    yield node.module, alias.name


class LauncherImportTest(unittest.TestCase):
    def test_every_program_symbol_used_by_launchers_exists(self):
        checked = 0
        for launcher in LAUNCHERS:
            if not launcher.is_file():
                continue
            for module, name in _program_imports(launcher):
                with self.subTest(launcher=launcher.name, symbol=module + '.' + name):
                    self.assertTrue(hasattr(importlib.import_module(module), name))
                    checked += 1
        self.assertGreater(checked, 0)

    def test_main_launcher_has_no_animated_startup_window(self):
        self.assertNotIn(('ui_widgets', 'Splash'), set(_program_imports(LAUNCHERS[0])))
        self.assertFalse((PROGRAM / 'ui/ui_splash.py').exists())


if __name__ == '__main__':
    unittest.main()
