"""U3: Fluent PNG through IconLoader; MDL2 and emoji icon debt only decreases.

AST counts below are per production file, excluding tests and ui_tokens (the glyph
owner). A new file has an implicit zero baseline. Imports with aliases and uses
through a ui_tokens module alias are resolved before counting. Ordinary prose
is not scanned for emoji; only icon assignments and widget text arguments are.
"""
from __future__ import annotations

import ast
import collections
import unittest

from tests.architecture._scan import ROOT, production_files_recursive

# Count AST glyph reads, not imports or names unrelated to ui_tokens (e.g. app ICON_NAME).
GLYPH_BASELINE = {
    'desktop_shared_input.py': {'ICON_SKILL': 1, 'ICON_ADD': 1, 'ICON_MICROPHONE': 1, 'ICON_SEND': 1},
    'ui/desktop_shared_menus.py': {'ICON_DOCUMENT': 1, 'ICON_FONT': 1},
    'ui/desktop_files_panel.py': {'ICON_CHEVRON_RIGHT': 1},
    'ui/desktop_idea_bubbles.py': {'ICON_FONT': 1, 'ICON_COPY': 2, 'ICON_DELETE': 2, 'ICON_REWIND': 2},
    'ui/desktop_script_pages.py': {'ICON_SEND': 1, 'ICON_STOP': 1},
    'ui/ui_composer_style.py': {'ICON_FONT': 3, 'ICON_FONT_SMALL': 1},
    'ui/workflow_settings_dialog.py': {'ICON_MICROPHONE': 1},
    'ui_widgets.py': {'ICON_FONT': 1},
    'ui/white_model.py': {'ICON_MICROPHONE': 1},
}
# Input icon row/panel and its named style are the only places permitted to keep
# using MDL2; the remaining entries above are frozen historical exceptions.
# Paths follow T10 packaging: entities live under ui/, top-level files are facades.
INPUT_ICON_FILES = frozenset({
    'desktop_shared_input.py', 'ui/desktop_shared_menus.py', 'ui/ui_composer_style.py',
    'ui/workflow_settings_dialog.py',
})
# AST icon-only count: stage rail 13 stages + all=14; media cover fallback=1.
EMOJI_BASELINE = {'ui/desktop_files_panel_filters.py': 14, 'ui/ui_media_player.py': 1}


def glyph_names():
    owner = ast.parse((ROOT / 'ui_tokens.py').read_text(encoding='utf-8'))
    return {name.id for node in owner.body if isinstance(node, (ast.Assign, ast.AnnAssign))
            for name in (node.targets if isinstance(node, ast.Assign) else (node.target,))
            if isinstance(name, ast.Name) and name.id.startswith('ICON_')}


def _emoji(text):
    return any(0x1F000 <= ord(char) <= 0x1FAFF or ord(char) in (0x2702, 0x2705)
               for char in text)


def _icon_assignment(node):
    targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
    return any(isinstance(target, ast.Name) and 'ICON' in target.id.upper()
               for target in targets)


def icon_emoji_count(tree):
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and _icon_assignment(node):
            value = node.value
            if isinstance(value, (ast.Constant, ast.Dict, ast.List, ast.Tuple)):
                count += sum(_emoji(part.value) for part in ast.walk(value)
                             if isinstance(part, ast.Constant) and isinstance(part.value, str))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {
                'Label', 'Button', 'Checkbutton', 'Radiobutton'}:
            count += sum(_emoji(kw.value.value[0]) for kw in node.keywords
                         if kw.arg == 'text' and isinstance(kw.value, ast.Constant)
                         and isinstance(kw.value.value, str) and kw.value.value)
    return count


def glyph_uses(tree, names):
    imported = {}
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == 'ui_tokens':
            imported.update({alias.asname or alias.name: alias.name for alias in node.names
                             if alias.name in names})
        elif isinstance(node, ast.Import):
            modules.update(alias.asname or alias.name for alias in node.names
                           if alias.name == 'ui_tokens')
    counts = collections.Counter()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in imported:
            counts[imported[node.id]] += 1
        elif (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
              and node.value.id in modules and node.attr in names):
            counts[node.attr] += 1
    return counts


def _path_segments(node):
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _path_segments(node.left) + _path_segments(node.right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'Path':
        return _path_segments(node.args[0]) if node.args else []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    return []


def glyph_overages(relative, tree, names):
    baseline = GLYPH_BASELINE.get(relative, {})
    return {name: (count, baseline.get(name, 0)) for name, count in glyph_uses(tree, names).items()
            if count > baseline.get(name, 0)}


def direct_nav_paths(tree):
    """Executable literals and Path joins to assets/nav belong to the shared loader."""
    docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                  if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                  and node.body and isinstance(node.body[0], ast.Expr)
                  and isinstance(node.body[0].value, ast.Constant)
                  and isinstance(node.body[0].value.value, str)}
    direct = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Constant)
              and isinstance(node.value, str) and id(node) not in docstrings
              and ('assets/nav/' in node.value or 'assets\\nav\\' in node.value)]
    joined = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.BinOp)
              and isinstance(node.op, ast.Div) and _path_segments(node)[:2] == ['assets', 'nav']]
    return sorted(set(direct + joined))


class IconSourceBoundaryTests(unittest.TestCase):
    def test_glyph_debt_only_decreases(self):
        names = glyph_names()
        self.assertIn('ICON_FOLDER', names)
        bad = []
        for path in production_files_recursive():
            relative = path.relative_to(ROOT).as_posix()
            if relative == 'ui_tokens.py':
                continue
            for name, (count, cap) in glyph_overages(
                    relative, ast.parse(path.read_text(encoding='utf-8')), names).items():
                bad.append(f'{relative}:{name} {count}>{cap}')
        self.assertEqual(bad, [], '新增 MDL2 字形只能在输入图标行，存量仅减不增')

    def test_emoji_icon_debt_only_decreases(self):
        bad = []
        for path in production_files_recursive():
            relative = path.relative_to(ROOT).as_posix()
            count = icon_emoji_count(ast.parse(path.read_text(encoding='utf-8')))
            if count > EMOJI_BASELINE.get(relative, 0):
                bad.append(f'{relative}: {count}>{EMOJI_BASELINE.get(relative, 0)}')
        self.assertEqual(bad, [], '新图标不得使用 emoji')

    def test_png_paths_use_shared_loader(self):
        bad = []
        for path in production_files_recursive():
            relative = path.relative_to(ROOT).as_posix()
            if relative in ('ui_icons.py', 'ui/ui_icons.py', 'scripts/build_nav_icons.py'):
                continue
            bad.extend(f'{relative}:{line}' for line in direct_nav_paths(
                ast.parse(path.read_text(encoding='utf-8'))))
        self.assertEqual(bad, [], '导航 PNG 只能经 IconLoader.nav_icon')

    def test_new_glyph_import_canary(self):
        names = glyph_names()
        bad = ast.parse('from ui_tokens import ICON_FOLDER as folder\nicon = folder')
        self.assertEqual(glyph_overages('new_page.py', bad, names), {'ICON_FOLDER': (1, 0)})
        module_alias = ast.parse('import ui_tokens as tokens\nicon = tokens.ICON_FOLDER')
        self.assertEqual(glyph_overages('new_page.py', module_alias, names), {'ICON_FOLDER': (1, 0)})
        self.assertEqual(glyph_overages('new_page.py', ast.parse('ICON_NAME = "app.ico"'), names), {})
        self.assertNotIn('new_page.py', GLYPH_BASELINE)

    def test_emoji_scope_canary(self):
        self.assertEqual(icon_emoji_count(ast.parse("STAGE_RAIL_ICONS = {'a': '📦'}")), 1)
        self.assertEqual(icon_emoji_count(ast.parse("tk.Button(root, text='📦')")), 1)
        self.assertEqual(icon_emoji_count(ast.parse("status = '处理成功 ✅'")), 0)
        self.assertEqual(icon_emoji_count(ast.parse("tk.Label(root, text='完成 ✅')")), 0)
        self.assertEqual(icon_emoji_count(ast.parse("tk.Label(root, text='🎬 视频封面')")), 1)

    def test_nav_path_canary(self):
        self.assertEqual(direct_nav_paths(ast.parse("image = 'assets/nav/new.png'")), [1])
        self.assertEqual(direct_nav_paths(ast.parse("image = Path('assets') / 'nav' / 'new.png'")), [1])
        self.assertEqual(direct_nav_paths(ast.parse('"""assets/nav is documented"""\nimage = IconLoader.nav_icon(root, "new")')), [])


if __name__ == '__main__':
    unittest.main()
