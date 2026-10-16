"""架构统一路线图第 3、4 项的可审计棘轮。"""
from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

from tests.architecture._layers import LAYERS


ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / '维护记录' / '架构统一基数.json'


def _ledger():
    return json.loads(LEDGER.read_text(encoding='utf-8'))


def _json_source_files():
    """固定审计集合；台账的增删绝不影响扫描范围。"""
    files = set(ROOT.glob('*.py'))
    files.update((ROOT / 'agent').glob('*.py'))
    files.update((ROOT / 'batch_frames_tool').glob('*.py'))
    files.update((ROOT / 'scripts').glob('*.py'))
    files.update(ROOT.glob('skills/**/scripts/*.py'))
    files.update(ROOT.glob('skills/**/server.py'))
    return sorted(path for path in files if path.is_file())


def _bare_json_loads():
    found = set()
    for path in _json_source_files():
        source = path.read_text(encoding='utf-8')
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'loads' and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == 'json'):
                found.add(f'{path.relative_to(ROOT).as_posix()}:{node.lineno}')
    return found


def _l2_source_files():
    return [ROOT / f'{name}.py' for name, layer in LAYERS.items()
            if layer == 2 and (ROOT / f'{name}.py').is_file()]


def _is_temporary(node):
    return (isinstance(node, ast.Name) and 'temp' in node.id.lower()) or (
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr in {'with_suffix', 'with_name'}
        and node.args and isinstance(node.args[0], ast.Constant)
        and 'temp' in str(node.args[0].value).lower())


def _formal_publish_fallbacks():
    """L2 中未注入发布器仍可直接写正式路径的函数。"""
    found = set()
    write_names = {'save', 'save_bytes', 'save_text', 'write_text', 'write_bytes', 'dump'}
    for path in _l2_source_files():
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for function in (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)):
            for node in ast.walk(function):
                if not isinstance(node, ast.Call):
                    continue
                attr = node.func.attr if isinstance(node.func, ast.Attribute) else None
                name = node.func.id if isinstance(node.func, ast.Name) else attr
                if name == 'copy2':
                    destination = node.args[1] if len(node.args) > 1 else None
                    if destination is not None and not _is_temporary(destination):
                        found.add(f'{path.name}:{function.name}')
                elif name in write_names:
                    destination = node.args[0] if node.args else None
                    if destination is not None and not _is_temporary(destination):
                        found.add(f'{path.name}:{function.name}')
    return found | _project_config_write_fallbacks()


def _project_config_write_fallbacks():
    """第 3 项扩支：L2 未注入发布器写项目配置／设置／登记表。"""
    found = set()
    targets = {'config.json', 'settings.json', 'projects.json'}
    write_names = {'save', 'save_text', 'write_text', 'write_bytes', 'dump'}
    for path in _l2_source_files():
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for function in (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)):
            literals = {node.value for node in ast.walk(function)
                        if isinstance(node, ast.Constant) and isinstance(node.value, str)}
            writes = any(isinstance(node, ast.Call) and (
                isinstance(node.func, ast.Name) and node.func.id in write_names or
                isinstance(node.func, ast.Attribute) and node.func.attr in write_names)
                for node in ast.walk(function))
            if literals & targets and writes:
                found.add(f'{path.name}:{function.name}')
    return found


def _formal_path_json_reads():
    """第 5 项：L2 之外的生产模块直接读正式登记／配置文件。"""
    targets = {'config.json', 'settings.json', 'projects.json'}
    l2 = {path.resolve() for path in _l2_source_files()}
    found = set()
    for path in _json_source_files():
        if path.resolve() in l2:
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for function in (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)):
            literals = {node.value for node in ast.walk(function)
                        if isinstance(node, ast.Constant) and isinstance(node.value, str)}
            if not literals & targets:
                continue
            reads = any(isinstance(node, ast.Call) and (
                (isinstance(node.func, ast.Attribute) and node.func.attr in {'load', 'loads'}) or
                (isinstance(node.func, ast.Name) and node.func.id == 'open'))
                for node in ast.walk(function))
            if reads:
                found.add(f'{path.relative_to(ROOT).as_posix()}:{function.name}')
    return found


def _projects_direct_storage_calls():
    """已迁移的 projects 不能退回 L2 自行读写、回滚或复制。"""
    path = ROOT / 'projects.py'
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    forbidden_names = {'read', 'save', 'save_bytes', 'restore_bytes'}
    forbidden_attrs = {'read_bytes', 'read_text', 'write_bytes', 'write_text', 'copy2', 'copytree'}
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == 'agent.core':
            found.update(alias.name for alias in node.names if alias.name in forbidden_names)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in forbidden_names:
                found.add(node.func.id)
            if isinstance(node.func, ast.Attribute) and node.func.attr in forbidden_attrs:
                found.add(node.func.attr)
    return found


def _point_exists(item):
    path = ROOT / item['file']
    if not path.is_file():
        return False
    point = str(item['point'])
    if point.isdigit():
        return int(point) <= len(path.read_text(encoding='utf-8').splitlines())
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    return any(isinstance(node, ast.FunctionDef) and node.name == point for node in ast.walk(tree))


class UnificationRatchetTests(unittest.TestCase):
    def _assert_ratchet(self, section, actual):
        record = _ledger()[section]
        items = record['items']
        identities = {f"{item['file']}:{item['point']}" for item in items}
        pending = {f"{item['file']}:{item['point']}" for item in items
                   if item['disposition'] == 'pending'}
        exempt = {f"{item['file']}:{item['point']}" for item in items
                  if item['disposition'] == 'exempt'}
        self.assertTrue(actual <= identities,
                        f'{section} 出现未登记新增债务：{sorted(actual - identities)}')
        self.assertEqual(record['count'], len(pending),
                         f'{section} 的 count 必须等于 pending 项数')
        self.assertLessEqual(len(pending), record['baseline_pending'],
                             f'{section} pending 数不得高于定稿基数')
        self.assertEqual(actual - exempt, pending,
                         f'{section} 只能在真实迁移后减少 pending：现有 {sorted(actual - exempt)}')
        for item in items:
            self.assertIn(item['disposition'], {'pending', 'migrated', 'exempt', 'noise'})
            if item['disposition'] in {'migrated', 'exempt', 'noise'}:
                self.assertTrue(item.get('reason', '').strip(), f'{section} 已处置项必须写 reason')
            self.assertTrue(_point_exists(item), f'{section} 台账项不可定位：{item}')

    def test_l2_formal_publish_debt_is_a_nonincreasing_subset(self):
        self._assert_ratchet('第三项', _formal_publish_fallbacks())

    def test_bare_json_load_debt_is_a_nonincreasing_subset(self):
        self._assert_ratchet('第四项', _bare_json_loads())

    def test_formal_path_reads_outside_l2_are_a_nonincreasing_subset(self):
        self._assert_ratchet('第五项', _formal_path_json_reads())

    def test_migrated_projects_cannot_bypass_its_injected_gateway(self):
        self.assertEqual(_projects_direct_storage_calls(), set())
