"""单个生产函数行数上限：新函数 ≤ 150 行；超限的老函数登记上限，只许下降。

与 `test_module_size_ratchet` 同一治理口径：超限函数只能随拆分变小。
登记上限比实际高出 SLACK 行以上时必须下调；降到 ≤ 150 行必须从登记表删除。
新增逻辑应拆进模块级辅助函数或 *_service／*_controller，不要继续堆进下列长函数。
"""
import ast
import unittest

from tests.architecture._scan import production_files

LIMIT = 150
SLACK = 15
OVERSIZE_CAPS = {
    ('keyframe_comfy.py', 'show'): 626,
    ('desktop_writing_page.py', 'writing'): 531,
    ('pet_models_ui.py', 'open_manager'): 493,
    ('storyboard_files.py', 'show_final'): 401,
    ('storyboard_files.py', 'show'): 335,
    ('desktop_storyboard_page.py', 'storyboard'): 321,
    ('desktop_idea_chat.py', 'open_flow_agent'): 252,
    ('local_previs.py', 'show'): 252,
    ('desktop_script_pages.py', 'script_structure'): 244,
    ('asset_batch.py', 'show'): 243,
    ('desktop_asset_pages.py', 'assets'): 223,
    ('ui_theme.py', 'install_window_placement'): 224,
    ('cloud_video.py', 'settings_window'): 204,
    ('reference_wall.py', 'show'): 193,
    ('desktop_script_pages.py', 'content_box'): 181,
    ('writing_api.py', '_preparation_step'): 181,
    ('desktop.py', '__init__'): 165,
    ('desktop_idea_chat.py', 'send_message'): 171,
    ('native_assets.py', 'attach_controls'): 167,
    ('desktop.py', 'show'): 152,
}


def _lengths():
    out = {}
    for path in production_files():
        tree = ast.parse(path.read_text(encoding='utf-8', errors='replace'))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out[(path.name, node.name)] = getattr(node, 'end_lineno', node.lineno) - node.lineno + 1
    return out


class FunctionSizeRatchet(unittest.TestCase):
    def test_no_function_exceeds_its_cap(self):
        over = []
        for (name, func), count in sorted(_lengths().items()):
            cap = OVERSIZE_CAPS.get((name, func), LIMIT)
            if count > cap:
                over.append('%s::%s %d 行 > 上限 %d' % (name, func, count, cap))
        self.assertEqual(over, [], '请拆分为模块级辅助函数，不要抬高上限')

    def test_registry_tracks_real_sizes(self):
        sizes = _lengths()
        stale = []
        for (name, func), cap in OVERSIZE_CAPS.items():
            actual = sizes.get((name, func))
            if actual is None:
                stale.append('%s::%s 已不存在或改名，请更新登记' % (name, func))
            elif actual <= LIMIT:
                stale.append('%s::%s 实际 %d 行，已不超限，请从登记表删除' % (name, func, actual))
            elif cap - actual > SLACK:
                stale.append('%s::%s 实际 %d 行，登记 %d，请下调到 %d 以内'
                             % (name, func, actual, cap, actual + SLACK))
        self.assertEqual(stale, [])


if __name__ == '__main__':
    unittest.main()