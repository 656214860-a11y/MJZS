# -*- coding: utf-8 -*-
"""自检的发现与切分：模块清单、import 语法分析、依赖闭包、测试文件分层与工作单元切块。"""

import ast
import glob
import importlib
import io
import json
import os
import unittest
from functools import lru_cache

import selftest_env as env


def split_performance_units(todo):
    """分离必须等并行池退出后测量的单元，保持两组顺序与全部测试。"""
    normal, perf = [], []
    for unit in todo:
        target = perf if unit[1].startswith('test_perf') or unit[1] in env.PERFORMANCE_MODULES else normal
        target.append(unit)
    return normal, perf


def safe_full_options(everything, serial, whole, jobs, safe):
    """安全模式固定为全量、可拆分；Tk 单元的并发度另由 safe_gui_jobs 限制。"""
    if safe:
        return True, False, False, jobs
    return everything, serial, whole, jobs


def safe_gui_jobs(jobs, override=None):
    """默认四路；显式 A/B 测量限制在 1～4 路且不超过总 worker 数。"""
    limit = env.SAFE_GUI_JOBS if override is None else override
    if limit not in (1, 2, 3, 4):
        raise ValueError('--gui-jobs 必须为 1、2、3 或 4')
    return max(1, min(limit, jobs))


def project_modules():
    """本项目里可被导入的模块：模块名 → 文件路径（程序根 ＋ agent 子包）。"""
    out = {}
    for folder in (env.HERE, os.path.join(env.HERE, 'agent')):
        for path in glob.glob(os.path.join(folder, '*.py')):
            out[os.path.basename(path)[:-3]] = path
    # agent 包按点号路径导入（agent.core／from agent import core），包本身是 agent/__init__.py。
    for path in glob.glob(os.path.join(env.HERE, 'agent', '*.py')):
        stem = os.path.basename(path)[:-3]
        out['agent' if stem == '__init__' else 'agent.' + stem] = path
    # tests/ 下的共用辅助模块（widget_test_support 等）：它们变了，用到它们的测试也要重跑。
    for path in glob.glob(os.path.join(env.TESTS_DIR, '*.py')):
        out.setdefault(os.path.basename(path)[:-3], path)
    return out


@lru_cache(maxsize=None)
def imports_of(path):
    """一个 .py 里 import 了哪些顶层模块名（只看语法，不真的导入）。"""
    try:
        with io.open(path, encoding='utf-8', errors='ignore') as handle:
            tree = ast.parse(handle.read())
    except (OSError, SyntaxError):
        return frozenset()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split('.')[0])
                names.add(alias.name)              # 点号全名：agent.core 这类子包模块
        elif isinstance(node, ast.ImportFrom):
            if node.level or not node.module:
                continue                       # 相对导入（agent 包内部）不参与
            names.add(node.module.split('.')[0])
            names.add(node.module)
            names.update(node.module + '.' + alias.name for alias in node.names)   # from agent import core
    # dependency_closure 会被每个测试文件调用；不缓存会重复解析同一批模块数千次，
    # 让 --all 在真正开始跑用例前就长时间占满 CPU。
    return frozenset(names)


def dependency_closure(names):
    """这些模块连带它们 import 的本项目模块，一直展开到底（只认项目里的文件）。"""
    modules = project_modules()
    seen, todo = set(), list(names)
    while todo:
        name = todo.pop()
        if name in seen or name not in modules:
            continue
        seen.add(name)
        todo.extend(imports_of(modules[name]) - seen)
    return seen


def data_files():
    """跟着自检一起变的数据文件（各个 SKILL 的说明 MD）：相对路径 → 绝对路径。"""
    out = {}
    for pattern in env.DATA_GLOBS:
        for path in glob.glob(os.path.join(env.HERE, pattern)):
            out[os.path.relpath(path, env.HERE).replace(os.sep, '/')] = path
    return out


def import_all():
    """把每个模块都导入一遍（语法／导入期错误在这一步就该暴露）。"""
    fails = []
    for f in glob.glob(os.path.join(env.HERE, "*.py")):
        m = os.path.basename(f)[:-3]
        if m in env.SKIP or m.startswith("启动"):
            continue
        try:
            importlib.import_module(m)
        except ModuleNotFoundError as e:
            if e.name == "bpy":
                continue  # Blender-only template, expected outside Blender
            fails.append((m, str(e)))
        except Exception as e:
            fails.append((m, f"{type(e).__name__}: {e}"))
    return fails


def test_modules(keys=()):
    """要跑哪些测试文件（测试统一收拢到 tests/，可带 -k 片段过滤）。"""
    nested = glob.glob(os.path.join(env.TESTS_DIR, "**", "test_*.py"), recursive=True)
    names = sorted({os.path.relpath(f, env.TESTS_DIR)[:-3].replace(os.sep, '.') for f in nested})
    if keys:
        names = [n for n in names if any(k in n for k in keys)]
    return names


def test_path(name):
    """测试模块名对应的唯一源文件。"""
    return os.path.join(env.TESTS_DIR, *name.split('.')) + '.py'


# 这些测试通过共享基类创建真 Tk，文件自身没有直接 tkinter 导入。
INHERITED_TK_TEST_MODULES = frozenset({'test_model_manager_actions'})


def gui_test_module(name):
    """按直接依赖及显式登记的 Tk 夹具使用者识别 GUI 测试。"""
    if name in INHERITED_TK_TEST_MODULES:
        return True
    imports = imports_of(test_path(name))
    return bool({'tkinter', 'desktop', 'pet_ui', 'ui_theme', 'ui.pet_ui', 'ui.pet_ui_stages', 'ui.pet_ui_support', 'ui.pet_ui_settings', 'ui.pet_ui_voice', 'ui.pet_ui_view', 'ui.pet_ui_popup'} & imports)


def modules_for_layer(names, layer):
    """测试分层：架构、无 Tk 服务、短 Tk 与端到端桌面用例互斥。"""
    if not layer:
        return list(names)
    if layer not in env.TEST_LAYERS:
        raise ValueError('未知测试层：%s（可用：%s）' % (layer, '、'.join(env.TEST_LAYERS)))
    architecture = [name for name in names if name.startswith('architecture.test_')]
    if layer == 'architecture':
        return architecture
    non_architecture = [name for name in names if name not in architecture]
    gui = [name for name in non_architecture if gui_test_module(name)]
    if layer == 'gui':
        return gui
    if layer == 'gui-e2e':
        return [name for name in gui if name.rsplit('.', 1)[-1] in env.GUI_E2E_MODULES]
    if layer == 'gui-short':
        return [name for name in gui if name.rsplit('.', 1)[-1] not in env.GUI_E2E_MODULES]
    return [name for name in non_architecture if name not in gui]


def _flat_cases(suite):
    """把一个测试套件里的用例摊平成一张表（类名按发现顺序保留）。"""
    out = []
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            out.extend(_flat_cases(item))
        else:
            out.append(item)
    return out


def split_classes(cases):
    """按类把用例分组：先把同一个类的用例归到一起（发现顺序不变）。"""
    order, groups = [], {}
    for case in cases:
        name = type(case).__name__
        if name not in groups:
            groups[name] = []
            order.append(name)
        groups[name].append(case)
    return [(name, groups[name]) for name in order]


def chunks_of(groups, limit=env.CHUNK_TESTS):
    """把类按顺序装进几个不超过 limit 条的筐子里。

    一个大类（UiEdgeTests 那种几十条、每条都要建整套界面的）自己就超了 limit，会被**拆开**——
    拆的是同一个类的不同用例，安全：setUp／setUpClass 本来就是每路各跑一遍的，用例之间不共享状态。
    筐子里记的是 (类名, 用例方法名表)，跑到哪一路都只跑这几条。
    """
    out, bucket, count = [], [], 0
    for name, cases in groups:
        for start in range(0, len(cases), limit):
            part = cases[start:start + limit]
            if bucket and count + len(part) > limit:
                out.append(bucket)
                bucket, count = [], 0
            bucket.append((name, [case._testMethodName for case in part]))
            count += len(part)
    if bucket:
        out.append(bucket)
    return out


def units(names, whole=False):
    """测试文件 → 工作单元：大文件按类切成几路，小文件一整路。

    单元是 (标签, 文件名, [(类名, 用例方法名表)] 或 None)；标签只给打印和报红用。
    """
    loader = unittest.TestLoader()
    out = []
    for name in names:
        if whole:
            out.append((name, name, None))
            continue
        try:
            cases = _flat_cases(loader.loadTestsFromName(name))
        except Exception:
            out.append((name, name, None))
            continue
        if len(cases) <= env.SPLIT_OVER:
            out.append((name, name, None))
            continue
        for index, group in enumerate(chunks_of(split_classes(cases))):
            out.append(('%s#%d' % (name, index + 1), name, group))
    return out


def split_safe_units(todo):
    """把可能创建 Tk 的单元识别出来，交给受控的 Tk 工作池。"""
    gui, non_gui = [], []
    for unit in todo:
        (gui if gui_test_module(unit[1]) else non_gui).append(unit)
    return non_gui, gui
