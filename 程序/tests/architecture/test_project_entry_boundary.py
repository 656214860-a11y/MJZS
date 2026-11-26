"""项目进入路径覆盖门禁（UI 路线图 v1 §三 第 4 项）。

完成判据：「所有项目进入路径可由同一控制器与设置服务审计」。
本门禁以静态方式冻结 `desktop.py` 中直接装载项目（`self.load(<项目路径>)`）
的入口集合，并核对：首帧首次选择必经 `DesktopStartupController`、每条进入
路径都经「当天选择」记忆、当日记忆与设置写入委托 `desktop_settings_service`。
新增或改名进入路径必须先在此登记，避免绕过控制器与设置服务。
"""
import ast
import unittest
from pathlib import Path

from tests.architecture._scan import desktop_text, entity_file, parse_desktop

ROOT = Path(__file__).resolve().parents[2]
DESKTOP = ROOT / 'desktop.py'  # R1505：进入路径分布在 desktop.py 与迁出的 Mixin 模块，下面统一读合并源码
CONTROLLER = entity_file('desktop_startup_service')

# 直接调用 `self.load(<非 None>)` 的「项目进入」路径（冻结，只增需登记）。
ENTERING_ENTRYPOINTS = frozenset({
    'open_project_or_cleanup',  # 侧栏 `switch` 与项目首页选中项目
    '_choose_project_impl',     # 自动续开
    '_open_startup_choice',     # 主窗口内单击选择后记录每周确认
    'new',                      # 新建项目
    'create_practice_project',   # 隔离练习副本，沿用创建器与当天选择记忆
    'import_json',              # 导入分镜 JSON 建项
    'enter',                    # 项目选择窗双击／回车
})
# 直接调用 `self.load(None)` 的「关闭当前项目」路径（删除后收尾，非进入）。
CLOSING_ENTRYPOINTS = frozenset({'gone', 'completed'})


def _tree(path):
    return ast.parse(path.read_text(encoding='utf-8'), filename=str(path))


def _parent_map(tree):
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _owning_function(node, parents):
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current
    return None


def _load_calls(tree):
    """产出 `self.load(...)` 调用：`(行号, 宿主函数节点, 首参是否 None 字面量)`。"""
    parents = _parent_map(tree)
    rows = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'load' and isinstance(node.func.value, ast.Name)
                and node.func.value.id == 'self'):
            first = node.args[0] if node.args else None
            rows.append((node.lineno, _owning_function(node, parents),
                         isinstance(first, ast.Constant) and first.value is None))
    return rows


class ProjectEntryBoundaryTests(unittest.TestCase):
    def test_project_load_calls_sit_in_frozen_entrypoints(self):
        rows = _load_calls(parse_desktop())
        entering = {func.name for _, func, is_none in rows if not is_none}
        closing = {func.name for _, func, is_none in rows if is_none}
        self.assertEqual(entering, set(ENTERING_ENTRYPOINTS),
                         '新增／改名的项目进入路径必须先登记，避免绕过控制器与设置服务')
        self.assertEqual(closing, set(CLOSING_ENTRYPOINTS),
                         '关闭当前项目只允许出现在删除收尾路径')

    def test_every_entering_path_remembers_daily_choice(self):
        source = desktop_text()
        for _, func, is_none in _load_calls(parse_desktop()):
            if is_none:
                continue
            segment = ast.get_source_segment(source, func) or ''
            self.assertTrue('remember_daily_project_choice(' in segment
                            or '_startup_project_to_open(' in segment,
                            func.name + ' 进入项目后必须经当天选择的记忆入口')

    def test_first_choice_is_scheduled_by_startup_controller(self):
        source = desktop_text()
        tree = parse_desktop()
        builds = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name)
                  and node.func.id == 'DesktopStartupController']
        self.assertEqual(len(builds), 1, '首帧启动控制器只允许装配一次')
        keywords = {kw.arg: ast.get_source_segment(source, kw.value).strip()
                    for kw in builds[0].keywords}
        self.assertEqual(keywords.get('choose_project'), 'self.choose_project')
        self.assertEqual(keywords.get('before_project_choice'), 'self._after_first_paint')
        starts = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'start'
                  and isinstance(node.func.value, ast.Attribute)
                  and node.func.value.attr == 'startup_controller'
                  and isinstance(node.func.value.value, ast.Name)
                  and node.func.value.value.id == 'self']
        self.assertEqual(len(starts), 1, '首帧启动控制器只允许启动一次')
        expected_start = ast.parse(
            'self.startup_controller.start(*((10,) if self._startup_window_held() else ()))',
            mode='eval').body
        self.assertEqual(ast.dump(starts[0]), ast.dump(expected_start),
                         '托管启动窗口时延迟 10ms，否则使用控制器默认延迟')
        self.assertIn("getattr(self,'startup_controller',None)", source)
        self.assertIn('controller.cancel()', source)

    def test_daily_choice_memory_delegates_to_settings_service(self):
        source = desktop_text()
        tree = parse_desktop()
        methods = {node.name: node for node in ast.walk(tree)
                   if isinstance(node, ast.FunctionDef)}
        remember = ast.get_source_segment(source, methods['remember_daily_project_choice'])
        weekly = ast.get_source_segment(source, methods['_startup_project_to_open'])
        self.assertIn('publish_desktop_preferences(', remember)
        self.assertNotIn('save(self.settings_file', remember)
        self.assertIn('project_startup_choice_day', weekly)
        self.assertIn('project_choice_path', weekly)
        service = entity_file('desktop_settings_service').read_text(encoding='utf-8')
        self.assertIn('def publish_desktop_settings(', service)

    def test_startup_controller_module_stays_tk_free(self):
        for node in ast.walk(_tree(CONTROLLER)):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or '']
            else:
                continue
            for name in names:
                self.assertNotEqual(name.split('.')[0], 'tkinter',
                                    '首帧启动控制器须保持无 Tk，便于独立审计')


if __name__ == '__main__':
    unittest.main()
