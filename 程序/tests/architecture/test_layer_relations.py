"""层间关系规范守卫（L1 任务书 §5，LR-01~LR-10）。

读 ``维护记录/层间合规清单.json`` 的棘轮基线，逐条实测当前违规数：
实测高于基线即红（不许新增违规），低于基线时提示同步下调基线。
同层边登记见 ``_layers.SAME_LAYER_EDGES``（LR-03）。
"""
from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

from tests.architecture._layers import LAYERS, SAME_LAYER_EDGES
from tests.architecture._scan import ROOT, module_name, module_scan_files, parse, PACKAGE_NAMES

CHECKLIST = ROOT / '维护记录' / '层间合规清单.json'
AGENT_CORE_DIR = ROOT / 'agent'

# LR-05 端口模块：框架回调原语本身，登记为合法回调承载点。
CALLBACK_PORT_MODULES = frozenset({'tk_timers', 'app_logging'})
CALLBACK_ATTRS = frozenset({'after', 'after_idle', 'bind', 'bind_all', 'protocol',
                             'trace_add', 'trace_remove', 'after_cancel'})
# LR-06：访问 L1 私有名的白名单（门面自引用等）。
PRIVATE_ACCESS_KNOWN = frozenset()
# LR-08：9 项横切能力 → 守卫测试文件（存在即算覆盖）。
CROSSCUT_GUARDS = {
    'http': 'tests/architecture/test_http_boundary.py',
    'json_io': 'tests/architecture/test_json_io_boundary.py',
    'deletion': 'tests/architecture/test_deletion_gateway.py',
    'subprocess': 'tests/architecture/test_platform_process_boundary.py',
    'thread': 'tests/architecture/test_thread_boundary.py',
    'logging': 'tests/architecture/test_log_sink_boundary.py',
    'secret': 'tests/architecture/test_secret_sink_audit.py',
    'disk': 'tests/architecture/test_resources.py',
    'clock': 'tests/architecture/test_clock_boundary.py',
}


def _rules() -> dict[str, dict]:
    data = json.loads(CHECKLIST.read_text(encoding='utf-8'))
    return {rule['id']: rule for rule in data['rules']}


def _import_targets(tree: ast.AST):
    " produce (lineno, target) for static imports, alias-aware. """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split('.')
                yield node.lineno, (parts[1] if len(parts) > 1 and parts[0] in PACKAGE_NAMES else parts[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split('.')
            if len(parts) > 1 and parts[0] in PACKAGE_NAMES:
                yield node.lineno, parts[1]
            elif len(parts) == 1 and parts[0] in PACKAGE_NAMES:
                for alias in node.names:
                    yield node.lineno, alias.name
            else:
                yield node.lineno, parts[0]


def _dynamic_calls(tree: ast.AST):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else '')
        if name in ('import_module', '__import__'):
            first = node.args[0]
            yield node.lineno, name, first


def _scan():
    """单次全仓扫描，返回各规则实测明细。"""
    same_edges = set()
    upward = set()
    dyn_upward = set()
    nonliteral_dyn = []
    dyn_same = set()
    l1_private = []
    callbacks = []
    cjk_raises = 0
    l1_names = {n for n, l in LAYERS.items() if l == 1}
    l1_has_all = set()
    trees = {}
    for path in module_scan_files():
        name = module_name(path)
        layer = LAYERS.get(name)
        if layer is None:
            continue
        try:
            tree = parse(path)
        except Exception:
            continue
        trees[name] = (path, layer, tree)
        if layer == 1 and _has_all((path, layer, tree)):
            l1_has_all.add(name)
        for _line, target in _import_targets(tree):
            t_layer = LAYERS.get(target)
            if t_layer is None or target == name:
                continue
            if t_layer == layer:
                same_edges.add((name, target))
            elif t_layer > layer:
                upward.add((name, target))
        for line, dname, first in _dynamic_calls(tree):
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                parts = first.value.split('.')
                target = parts[1] if len(parts) > 1 and parts[0] in PACKAGE_NAMES else parts[0]
                t_layer = LAYERS.get(target)
                if t_layer is not None and target != name:
                    if t_layer == layer:
                        same_edges.add((name, target))
                        dyn_same.add((name, target))
                    elif t_layer > layer:
                        upward.add((name, target))
                        dyn_upward.add((name, target))
            else:
                nonliteral_dyn.append((name, line, dname))
        # LR-05：L0–L3 的 Tk 框架回调注册（排除端口模块）
        if layer <= 3 and name not in CALLBACK_PORT_MODULES:
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr in CALLBACK_ATTRS:
                    callbacks.append((name, node.attr, node.lineno))
        # LR-06：非 L1 访问 L1 私有名
        if layer != 1:
            aliases = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        parts = alias.name.split('.')
                        target = parts[1] if len(parts) > 1 and parts[0] in PACKAGE_NAMES else parts[0]
                        if target in l1_names:
                            aliases[alias.asname or parts[-1]] = target
                elif isinstance(node, ast.ImportFrom) and node.module:
                    parts = node.module.split('.')
                    target = parts[1] if len(parts) > 1 and parts[0] in PACKAGE_NAMES else parts[0]
                    if target in l1_names:
                        for alias in node.names:
                            if alias.name.startswith('_') and not (alias.name.startswith('__') and alias.name.endswith('__')):
                                l1_private.append((name, target + '.' + alias.name, node.lineno))
                    if len(parts) == 1 and parts[0] in PACKAGE_NAMES:
                        for alias in node.names:
                            if alias.name in l1_names:
                                aliases[alias.asname or alias.name] = alias.name
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr.startswith('_') and isinstance(node.value, ast.Name):
                    base = node.value.id
                    if base in aliases and not (node.attr.startswith('__') and node.attr.endswith('__')):
                        l1_private.append((name, aliases[base] + '.' + node.attr, node.lineno))
        # LR-07：L1 中文文案 raise
        if layer == 1:
            for node in ast.walk(tree):
                if isinstance(node, ast.Raise) and node.exc is not None:
                    for sub in ast.walk(node.exc):
                        if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and any('一' <= ch <= '鿿' for ch in sub.value):
                            cjk_raises += 1
                            break
    # LR-03：未登记同层边＋互依赖对
    unregistered = same_edges - set(SAME_LAYER_EDGES)
    mutual = {(a, b) for a, b in same_edges if (b, a) in same_edges and a < b}
    # LR-04：非字面量动态导入（登记表模块 ui_plugin_registry 的变量导入属登记表本体，
    # 但其层级低于被加载模块，计入登记表层级违规）＋上行动态边＋登记表层级违规
    registry_layer_violations = 0
    plugin_layers = set()
    registry_name = 'ui_plugin_registry'
    reg_layer = LAYERS.get(registry_name)
    if reg_layer is not None:
        try:
            reg_tree = parse(ROOT / 'infra' / 'ui_plugin_registry.py')
            for node in ast.walk(reg_tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == 'UI_PLUGINS' and isinstance(node.value, ast.Call):
                            pass
            # UI_PLUGINS frozenset 字面量成员
            for node in ast.walk(reg_tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == 'UI_PLUGINS':
                            for elt in ast.walk(node.value):
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    plugin_layers.add(LAYERS.get(elt.value.split('.')[0] if '.' in elt.value else elt.value))
            higher = {l for l in plugin_layers if l is not None and l > reg_layer}
            if higher:
                registry_layer_violations = 1
        except Exception:
            pass
    nonliteral_outside_registry = [x for x in nonliteral_dyn if x[0] != registry_name]
    # LR-08：9 项横切能力守卫覆盖
    missing_guards = [name for name, rel in CROSSCUT_GUARDS.items() if not (ROOT / rel).is_file()]
    return {
        'LR-01': len(upward),
        'LR-02': 6,  # KNOWN_STATIC_CYCLES 1＋KNOWN_DYNAMIC_CYCLES 5，由 test_no_circular_import 细管
        'LR-03': len(unregistered) + len(mutual),
        'LR-04': len(nonliteral_outside_registry) + len(dyn_upward) + registry_layer_violations,
        'LR-05': len(callbacks),
        'LR-06': len({x[:2] for x in l1_private} - PRIVATE_ACCESS_KNOWN),
        'LR-07': cjk_raises,
        'LR-08': len(missing_guards),
        'LR-09': sum(1 for n in l1_names if n not in l1_has_all),
        'LR-10': sum(1 for n in l1_names if n not in l1_has_all),
        '_detail': {'upward': sorted(upward), 'same_edges': len(same_edges),
                    'unregistered': sorted(unregistered), 'mutual': sorted(mutual),
                    'nonliteral': nonliteral_dyn, 'dyn_upward': sorted(dyn_upward),
                    'callbacks': callbacks, 'l1_private': l1_private,
                    'missing_guards': missing_guards},
    }


_REAL_SCAN = None


def real_scan():
    """真实仓库的单次扫描结果（门禁测试共享，避免每条规则重复全仓解析）。"""
    global _REAL_SCAN
    if _REAL_SCAN is None:
        _REAL_SCAN = _scan()
    return _REAL_SCAN


def _has_all(entry):
    if entry is None:
        return False
    _path, _layer, tree = entry
    return any(isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '__all__' for t in node.targets)
               for node in tree.body)


class LayerRelationsTests(unittest.TestCase):
    """逐条比对清单基线：超标红、达标提示下调。"""

    def test_compliance_ledger_matches_measured_violations(self):
        rules = _rules()
        measured = real_scan()
        regressions = []
        stale = []
        for rid, rule in rules.items():
            current = measured[rid]
            baseline = rule['baseline']
            if current > baseline:
                regressions.append('%s %s：实测 %d > 基线 %d' % (rid, rule['title'], current, baseline))
            elif current < baseline:
                stale.append('%s %s：实测 %d < 基线 %d，请同步下调 层间合规清单.json' % (rid, rule['title'], current, baseline))
        self.assertEqual(regressions, [], '层间关系违规新增：\n' + '\n'.join(regressions))
        if stale:
            # 低于基线不判红（棘轮方向正确），但提示同步，避免基线虚高。
            print('\n[棘轮提示] 以下规则实测低于基线，请下调 层间合规清单.json：\n' + '\n'.join(stale))

    def test_lr03_unregistered_same_layer_edge_is_red(self):
        measured = real_scan()
        detail = measured['_detail']
        unregistered = detail['unregistered']
        self.assertEqual(unregistered, [],
                         '未登记的同层依赖边，请登记 _layers.SAME_LAYER_EDGES 或调整分层：%s' % unregistered[:10])

    def test_lr03_mutual_same_layer_dependency_is_red(self):
        # 同层互依赖为存量违规，棘轮只降不升；新增互依赖对即红。
        measured = real_scan()
        mutual = measured['_detail']['mutual']
        baseline = _rules()['LR-03']['baseline']
        self.assertLessEqual(len(mutual), baseline,
                             '同层互相依赖禁止（基线 %d 对，只降不升）：实测 %d 对 %s'
                             % (baseline, len(mutual), mutual))

    def test_lr04_nonliteral_dynamic_import_outside_registry_is_red(self):
        measured = real_scan()
        detail = measured['_detail']
        offenders = [x for x in detail['nonliteral'] if x[0] != 'ui_plugin_registry']
        self.assertEqual(offenders, [],
                         '非字面量动态导入须改字面量或登记插件表：%s' % offenders)

    def test_lr01_l1_has_no_unexempted_upward_import(self):
        measured = real_scan()
        upward = {(a, b) for a, b in measured['_detail']['upward'] if LAYERS.get(a) == 1}
        # L1 上行边必须全部落在豁免台账（架构统一基数.json「层级」items）。
        ledger = json.loads((ROOT / '维护记录' / '架构统一基数.json').read_text(encoding='utf-8'))['层级']
        exempt = {(i['importer'], i['imported']) for i in ledger['items']}
        bad = upward - exempt
        self.assertEqual(bad, set(), 'L1 未登记上行依赖：%s' % sorted(bad))


if __name__ == '__main__':
    unittest.main()
