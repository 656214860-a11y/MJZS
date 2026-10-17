"""P1-7：已迁移页面的 UI／服务／本机适配边界不得回退。"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

from tests.architecture._scan import ROOT, parse


SERVICES = frozenset({
    'desktop_startup_service', 'desktop_automation_service',
    'storyboard_final_controller', 'storyboard_page_controller', 'keyframe_page_controller',
    'asset_batch_controller', 'asset_page_controller', 'editing_page_controller',
})
VIEWS = frozenset({'desktop', 'storyboard_files', 'asset_batch'})
FORBIDDEN_VIEW_MODULES = frozenset({'socket', 'webbrowser', 'requests', 'urllib', 'http'})
FORBIDDEN_CALLS_BY_MODULE = {
    'subprocess': frozenset({'Popen', 'run', 'call', 'check_call', 'check_output'}),
    'socket': frozenset({'create_connection'}),
    'os': frozenset({'startfile', 'system'}),
}
ALLOWED_ADAPTER_IMPORTS = {
    'desktop': {
        'platform_tools': frozenset({'launch_windows_app', 'open_path', 'open_target',
                                     'tcp_listener', 'terminate_process_tree',
                                     'find_editor_shortcut', 'open_directory'}),
        'native_apps': frozenset({'open_blender', 'force_close_comfy', 'open_comfy'}),
    },
    'storyboard_files': {'platform_tools': frozenset({'open_path'})},
    'asset_batch': {'platform_tools': frozenset({'open_path', 'open_target'})},
}


def _imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name.split('.', 1)[0], None
        elif isinstance(node, ast.ImportFrom) and node.module:
            module = node.module.split('.', 1)[0]
            for alias in node.names:
                yield node.lineno, module, alias.name


class MigratedServiceBoundaryTests(unittest.TestCase):
    def test_migrated_services_never_import_tk(self):
        violations = []
        for module in SERVICES:
            for line, package, _name in _imports(parse(ROOT / (module + '.py'))):
                if package == 'tkinter':
                    violations.append(f'{module}.py:{line}')
        self.assertEqual(violations, [], '无 Tk 服务不得导入 tkinter：' + ', '.join(violations))


class MigratedViewBoundaryTests(unittest.TestCase):
    def test_views_do_not_directly_call_process_or_network_apis(self):
        violations = []
        for module in VIEWS:
            tree = parse(ROOT / (module + '.py'))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if isinstance(node.func, ast.Attribute):
                    owner = node.func.value
                    if (isinstance(owner, ast.Name) and owner.id in FORBIDDEN_VIEW_MODULES):
                        violations.append(f'{module}.py:{node.lineno} {owner.id}.{node.func.attr}')
                    elif (isinstance(owner, ast.Name)
                          and node.func.attr in FORBIDDEN_CALLS_BY_MODULE.get(owner.id, ())):
                        violations.append(f'{module}.py:{node.lineno} {owner.id}.{node.func.attr}')
        self.assertEqual(violations, [],
                         'view 必须经适配器，禁止直连进程/网络：' + '; '.join(violations))

    def test_adapter_imports_are_limited_to_registered_entrypoints(self):
        violations = []
        for module, allowed_by_package in ALLOWED_ADAPTER_IMPORTS.items():
            for line, package, name in _imports(parse(ROOT / (module + '.py'))):
                if package not in {'platform_tools', 'native_apps'}:
                    continue
                allowed = allowed_by_package.get(package, frozenset())
                if name is None or name not in allowed:
                    violations.append(f'{module}.py:{line} {package}.{name or "*"}')
        self.assertEqual(violations, [],
                         '新增本机适配必须先登记入口：' + '; '.join(violations))

def _catches_tcl_error(node):
    for handler in node.handlers:
        if handler.type is None:
            return True
        names = {child.attr for child in ast.walk(handler.type) if isinstance(child, ast.Attribute)}
        names |= {child.id for child in ast.walk(handler.type) if isinstance(child, ast.Name)}
        if 'TclError' in names:
            return True
    return False


class ViewTimerLifecycleTests(unittest.TestCase):
    """R1649：页面重排 Tk 定时器时，关窗竞态不得逃逸为未捕获的 tk.TclError。

    `desktop_script_pages.py` 是 P2-3 定位到的未保护重排点文件；其它页面改用
    `after_cancel` 在销毁时撤销定时器（另一条等价路径），故本门禁只钉这一处已知回归面。
    """

    GUARDED_FILES = ('desktop_script_pages',)

    def test_timer_reschedules_are_guarded_against_a_destroyed_window(self):
        unguarded = []
        for module in self.GUARDED_FILES:
            tree = parse(ROOT / (module + '.py'))
            guarded = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Try) and _catches_tcl_error(node):
                    guarded.update(id(inner) for inner in ast.walk(node))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in ('after', 'after_idle')
                        and id(node) not in guarded):
                    unguarded.append(module + '.py:' + str(node.lineno))
        self.assertEqual(unguarded, [],
                         '关窗后重排定时器须捕获 tk.TclError：' + ', '.join(unguarded))
