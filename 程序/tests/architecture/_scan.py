"""仅以 AST 读取程序根目录生产模块的架构扫描辅助函数。"""
from __future__ import annotations
import ast
import symtable
import re
import sys
from dataclasses import dataclass
from importlib.util import resolve_name
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[2]
_EXCLUDED_STEMS = frozenset({"smoke_test", "run_selftests", "selftest_sandbox",
                           "selftest_env", "selftest_discovery", "selftest_receipts",
                           "selftest_scheduling", "selftest_reporting"})

# 递归生产模块口径（R922／R1381 起确立）：覆盖 batch_frames_tool／agent／scripts 等子目录；
# 测试、轮次记录、维护记录与字节码缓存不参与生产门禁。
# `.wt` 是本仓库的干净检出区（后台全量在 `.wt/ci` 上跑），里面是同一份生产模块的副本，
# 不能算成第二批模块；`.selftmp` 是自检临时区（gitignored、随时被清），探针脚本不是产品模块。
# R1693 之前这两处要么不存在、要么没人往里放 .py，才没暴露这个问题。
# `voice_asr_venv` 是离线 ASR 运行时按需创建的第三方 venv（data/voice_asr_venv/，
# pip 装出的 jieba/_yaml/cffi 等约 7700 个 .py）：不是本仓产品代码，任何生产门禁
# 都不该把它当模块扫（R2990 合并阻断修复）。
# `logs`／`data`／`outputs` 是 .gitignore 忽略的运行目录（日志、运行数据、可共享输出），
# 运行期落进去的 .py（调试脚本、探针等）不是产品模块，不计入生产门禁计数（R2-G4）。
EXCLUDED_PARTS = frozenset({"tests", "tasks_round", "维护记录", ".git", ".wt", ".selftmp", "__pycache__",
                            "voice_asr_venv", "logs", "data", "outputs"})


def production_files_recursive() -> tuple[Path, ...]:
    """返回递归生产 Python 文件，供用户可见入口门禁核对子目录模块。

    与 `production_files()` 同口径：仍排除自检器（smoke_test／run_selftests／
    selftest_sandbox）与以 `test` 开头的文件，只是把扫描范围扩到子目录。
    """
    return tuple(sorted(path for path in ROOT.rglob("*.py")
                        if not any(part in EXCLUDED_PARTS
                                   for part in path.relative_to(ROOT).parts)
                        and path.stem not in _EXCLUDED_STEMS
                        and not path.stem.startswith("test")))


def production_files() -> tuple[Path, ...]:
    """返回程序根目录的生产 Python 文件，不递归扫描子目录。"""
    return tuple(sorted(path for path in ROOT.glob("*.py")
                        if not path.stem.startswith("test") and path.stem not in _EXCLUDED_STEMS))


# T10 包化：contract/infra/domain/orchestrator/ui 五个分层包的实体模块以扁平名
# 参与分层／环／规模棘轮；顶层同名门面只做再导出，不产生依赖边，扫描时排除。
# R3246+：agent/ 是第六个分层包（core/media/publication 等子模块按 _layers 实际
# 依赖登记 L1–L4），同样以扁平名入扫描集；agent/__init__.py 为空，不产生依赖边。
PACKAGE_NAMES = ("contract", "infra", "domain", "orchestrator", "ui", "agent")


def package_entity_files(*, qualified: bool = False) -> tuple[Path, ...]:
    """旧口径为单层非初始化实体；限定身份口径含递归子包与初始化实体。"""
    files: list[Path] = []
    for package in PACKAGE_NAMES:
        directory = ROOT / package
        if directory.is_dir():
            candidates = directory.rglob("*.py") if qualified else directory.glob("*.py")
            files.extend(path for path in sorted(candidates)
                         if (qualified or path.stem != "__init__")
                         and not EXCLUDED_PARTS.intersection(path.relative_to(ROOT).parts))
    return tuple(files)


def _is_main_guard(test: ast.expr) -> bool:
    """``__name__ == '__main__'``（含反向书写）的入口守卫。"""
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return False
    sides = [test.left, *test.comparators]
    names = [side.id for side in sides if isinstance(side, ast.Name)]
    literals = [side.value for side in sides
                if isinstance(side, ast.Constant) and isinstance(side.value, str)]
    return ('__name__' in names and '__main__' in literals
            and (isinstance(test.ops[0], ast.Eq)))


def is_package_facade(path: Path) -> bool:
    """顶层同名门面，两种薄形态：

    ① 名单再导出（contract/ 存量）：除 docstring 外只含
       ``from <包>.<同名模块> import ...``；
    ② 模块别名（infra/ 起）：``import sys``＋``from <包> import <同名模块>``
       ＋``sys.modules[__name__] = <实体名>``——``import <扁平名>`` 直接返回
       包内实体模块，私有名、模块级状态与 ``mock.patch('<扁平名>.…')`` 补丁面
       与包路径完全一致。
    """
    if path.parent != ROOT:
        return False
    try:
        tree = parse(path)
    except (SyntaxError, UnicodeDecodeError):
        return False
    sys_names: set[str] = set()
    entity_names: set[str] = set()
    saw_legacy_export = False
    saw_alias = False
    for node in tree.body:
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            continue  # 模块 docstring
        if isinstance(node, ast.Import):
            sys_names.update(alias.asname or alias.name for alias in node.names
                             if alias.name == 'sys')
            continue
        if isinstance(node, ast.ImportFrom) and node.module:
            package, _, tail = node.module.partition(".")
            if package not in PACKAGE_NAMES:
                return False
            if tail == path.stem:
                saw_legacy_export = True
                continue
            if not tail:
                entity_names.update(alias.asname or alias.name for alias in node.names
                                    if alias.name == path.stem)
                continue
            return False
        if (isinstance(node, ast.If) and _is_main_guard(node.test)
                and not any(isinstance(inner, (ast.Import, ast.ImportFrom))
                            for inner in ast.walk(node))):
            continue  # __main__ 转发块：入口壳可执行实体 main()，不产生依赖边
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Subscript)
                and isinstance(node.targets[0].slice, ast.Name)
                and node.targets[0].slice.id == '__name__'
                and isinstance(node.targets[0].value, ast.Attribute)
                and node.targets[0].value.attr == 'modules'
                and isinstance(node.targets[0].value.value, ast.Name)
                and node.targets[0].value.value.id in sys_names
                and isinstance(node.value, ast.Name)
                and node.value.id in entity_names):
            saw_alias = True
            continue
        return False
    return saw_alias or saw_legacy_export or bool(entity_names)


def module_scan_files(*, qualified: bool = False) -> tuple[Path, ...]:
    """分层／环／规模棘轮的扫描集：顶层生产文件（去门面）＋包实体文件。

    实体与门面同干系名；排除门面后每个原始模块恰有一个扫描代表，
    棘轮登记键（path.name／path.stem）与搬家前一致。
    qualified=True 额外扫描包初始化及嵌套实体，供严格影子消费者使用；
    门面仍沿用既有排除谓词，保留下来的同 stem 文件不能合并。
    """
    return (tuple(path for path in production_files() if not is_package_facade(path))
            + package_entity_files(qualified=qualified))


def registry_key(path: Path) -> str:
    """棘轮登记键：分层包实体归一为 ``<模块名>.py``（与搬家前顶层路径一致），
    其余文件保持相对 ``程序/`` 的 posix 路径（如 ``scripts/dev.py``）。"""
    parts = path.relative_to(ROOT).parts
    if len(parts) > 1 and parts[0] in PACKAGE_NAMES:
        return parts[-1]
    return "/".join(parts)


def _package_target(dotted: str) -> str:
    """``contract.x``／``agent.x`` 归一化为扁平登记名 ``x``；非分层包名取首段（同 import_rows）。"""
    parts = dotted.split(".")
    if len(parts) > 1 and parts[0] in PACKAGE_NAMES:
        return parts[1]
    return parts[0]


def _from_module(path: Path, node: ast.ImportFrom) -> str:
    """按源文件所在包解析相对前缀；仅计算名称，不加载模块。"""
    if not node.level:
        return node.module or ""
    package = path.relative_to(ROOT).parts[:-1]
    if node.level > len(package):
        raise ValueError(f"{path}:{node.lineno}: relative import beyond top-level package")
    parent = package[:len(package) - node.level + 1]
    return ".".join((*parent, node.module) if node.module else parent)


def module_import_rows(path: Path) -> Iterator[tuple[int, str]]:
    """现行扁平环图口径；完整包子模块边的启用须先消除 A1 已知新环。

    分层守卫使用 resolved_module_import_rows；本入口保留已有消费者契约。
    """
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, _package_target(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.lineno, _package_target(node.module)


def resolved_module_import_rows(path: Path, *, qualified: bool = False) -> Iterator[tuple[int, str]]:
    """静态导入含包子模块及相对导入；默认输出现行扁平登记名。

    ``from p import x`` 仅在本地存在 p/x.py 或 p/x/__init__.py 时添加子模块边，
    保留 p 本身的边，不将普通导出符号或 as 别名误当模块。
    qualified=True 保留完整名称，并列出本地父包初始化依赖；不执行被扫代码。
    """
    def targets(dotted: str) -> Iterator[str]:
        if not qualified:
            yield _package_target(dotted)
            return
        parts = dotted.split(".")
        for end in range(1, len(parts)):
            if (ROOT.joinpath(*parts[:end]) / "__init__.py").is_file():
                yield ".".join(parts[:end])
        yield dotted

    for node in ast.walk(parse(path)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for target in targets(alias.name):
                    yield node.lineno, target
        elif isinstance(node, ast.ImportFrom):
            base = _from_module(path, node)
            if not base:
                continue
            for target in targets(base):
                yield node.lineno, target
            directory = ROOT.joinpath(*base.split("."))
            if not (directory / "__init__.py").is_file():
                continue
            for alias in node.names:
                child = directory / alias.name
                if child.with_suffix(".py").is_file() or (child / "__init__.py").is_file():
                    for target in targets(f"{base}.{alias.name}"):
                        yield node.lineno, target


def module_dynamic_import_rows(path: Path) -> Iterator[tuple[int, str]]:
    """package-aware 版 dynamic_import_rows。"""
    for node in ast.walk(parse(path)):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
        first = node.args[0]
        if name in ("import_module", "__import__") and isinstance(first, ast.Constant) and isinstance(first.value, str):
            yield node.lineno, _package_target(first.value)


def module_imports_of(path: Path) -> frozenset[str]:
    return frozenset(name for _, name in module_import_rows(path))


def module_imports_with_dynamic_of(path: Path) -> frozenset[str]:
    return frozenset(name for _, name in (*module_import_rows(path), *module_dynamic_import_rows(path)))

# 非产品目录：技能随附脚本、开发／维护脚本、参考资料、构建产物与外部附加工具。
# 它们是独立工具，不属于产品运行时，不参与「正式资源目标」类审计的扫描范围。
NON_PRODUCT_PARTS = frozenset({"skills", "scripts", "reference", "outputs", "附加工具", "governance"})


def production_runtime_files() -> tuple[Path, ...]:
    """产品运行时生产模块：递归口径再排除非产品目录。

    与根目录口径相比，这里补上 agent/ 等被产品模块实际导入的运行时子包；
    与递归口径相比，去掉 skills/／scripts/／reference/／outputs/／附加工具/ 这些非产品目录。
    """
    return tuple(path for path in production_files_recursive()
                 if not NON_PRODUCT_PARTS.intersection(path.relative_to(ROOT).parts))

def entity_file(module: str) -> Path:
    """扁平登记名对应的实体源文件：分层包实体优先，顶层文件（门面或未迁移）兜底。

    读「模块源码行为」的门禁必须经本函数取径，否则搬家后读到的是同名薄门面，
    门禁对象被静默换成 9 行转发壳。
    """
    for package in PACKAGE_NAMES:
        candidate = ROOT / package / (module + ".py")
        if candidate.is_file():
            return candidate
    return ROOT / (module + ".py")


def module_name(path: Path, *, qualified: bool = False) -> str:
    if not qualified:
        return path.stem
    parts = path.relative_to(ROOT).with_suffix("").parts
    # Python 导入包名执行其 __init__.py；不是名为 __init__ 的公共模块。
    return ".".join(parts[:-1] if len(parts) > 1 and parts[-1] == "__init__" else parts)

def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


# R1480／R1490：Desktop 的方法分散在 desktop.py 与两个原样迁出的 Mixin 模块里；检查 Desktop 源码
# 行为（调用、方法体）的门禁用下面两个入口，别再直接读 desktop.py，否则迁出的方法会"消失"。
DESKTOP_PARTS = ("desktop.py", "desktop_auto_flows.py", "desktop_idea_chat.py", "desktop_idea_bubbles.py",
                 "desktop_idea_attachments.py", "desktop_writing_page.py",
                 "desktop_storyboard_page.py",
                 "desktop_idea_menus.py", "desktop_asset_pages.py", "desktop_script_pages.py", "desktop_script_edit_session.py", "desktop_media_pages.py", "desktop_project_pages.py",
                 "desktop_layout.py", "desktop_pet_bridge.py", "desktop_async_tasks.py", "desktop_page_nav.py", "desktop_lifecycle.py", "desktop_files_panel.py")


def desktop_text() -> str:
    return chr(10).join(entity_file(Path(name).stem).read_text(encoding="utf-8") for name in DESKTOP_PARTS)


PET_UI_PARTS = ("pet_ui.py", "pet_ui_support.py", "pet_ui_stages.py", "pet_ui_settings.py", "pet_ui_voice.py", "pet_ui_view.py", "pet_ui_popup.py")


def pet_ui_text() -> str:
    """Pet 的方法分布在 pet_ui.py 与迁出的 Mixin／support 模块里（R1506）。"""
    return chr(10).join(entity_file(Path(name).stem).read_text(encoding="utf-8") for name in PET_UI_PARTS)


def parse_desktop() -> ast.Module:
    return ast.parse(desktop_text(), filename="desktop*.py")

def import_rows(path: Path) -> Iterator[tuple[int, str]]:
    """产出顶层导入包名及行号，供分层和环依赖检查复用。"""
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name.split(".", 1)[0]
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.lineno, node.module.split(".", 1)[0]

def dynamic_import_rows(path: Path) -> Iterator[tuple[int, str]]:
    """产出常量字符串形式的动态导入（import_module／__import__）的顶层包名及行号。

    只认第一个参数是字符串常量的调用；变量名拼出来的模块名在静态扫描里不可知，不在此列。
    动态导入曾被用来绕开静态环检测，所以环依赖门禁要把它们并进图里。
    """
    for node in ast.walk(parse(path)):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
        first = node.args[0]
        if name in ("import_module", "__import__") and isinstance(first, ast.Constant) and isinstance(first.value, str):
            yield node.lineno, first.value.split(".", 1)[0]

def imports_of(path: Path) -> frozenset[str]:
    return frozenset(name for _, name in import_rows(path))

def imports_with_dynamic_of(path: Path) -> frozenset[str]:
    """静态导入加常量字符串动态导入；环依赖门禁用，分层门禁仍只看静态口径。"""
    return frozenset(name for _, name in (*import_rows(path), *dynamic_import_rows(path)))


# stage_execution_service 拆分后，门面与各拆出模块合起来才是原来的「阶段执行编排」。
STAGE_EXECUTION_MODULES = ("stage_execution_service", "stage_asset_gateways", "stage_animatic_gateways",
                           "stage_previs_gateways", "stage_gate_gateways", "stage_handoff_gateways")


def stage_execution_source() -> str:
    """门面与拆出模块的源码拼接；源码文本与 AST 类门禁按它读，不因函数搬家而漏检。"""
    parts = []
    for name in STAGE_EXECUTION_MODULES:
        entity = ROOT / "orchestrator" / (name + ".py")
        parts.append((entity if entity.exists() else ROOT / (name + ".py")).read_text(encoding="utf-8"))
    return "\n\n".join(parts)


def ui_registry_targets(path: Path) -> Iterator[tuple[int, str | None]]:
    """AST-only UI registry calls; unresolved arguments/escaped loaders fail closed.

    Import aliases are recognized conservatively across scopes. Variables are not
    evaluated; conditional literals enumerate both branches, including dead ones.
    """
    tree = parse(path)
    modules = {"ui_plugin_registry", "infra.ui_plugin_registry"}
    loaders = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in modules:
                    modules.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module in ("ui_plugin_registry", "infra.ui_plugin_registry"):
                for alias in node.names:
                    if alias.name == "module":
                        loaders.add(alias.asname or alias.name)
                    elif alias.name == "*":
                        yield node.lineno, None
            elif node.module == "infra":
                for alias in node.names:
                    if alias.name == "ui_plugin_registry":
                        modules.add(alias.asname or alias.name)

    def dotted(node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{dotted(node.value)}.{node.attr}"
        return ""

    def values(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value.strip()
        elif isinstance(node, ast.IfExp):
            yield from values(node.body)
            yield from values(node.orelse)
        else:
            yield None

    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    for node in ast.walk(tree):
        name = dotted(node)
        if name in modules:
            parent = parents.get(node)
            if not (isinstance(parent, ast.Attribute) and parent.attr == "module"):
                yield node.lineno, None
            continue
        if name not in loaders and name not in {f"{module}.module" for module in modules}:
            continue
        parent = parents.get(node)
        if not isinstance(parent, ast.Call) or parent.func is not node:
            yield node.lineno, None  # assignment/return of loader is an unresolved escape
            continue
        if len(parent.args) == 1 and not parent.keywords:
            yield from ((parent.lineno, value) for value in values(parent.args[0]))
        elif not parent.args and len(parent.keywords) == 1 and parent.keywords[0].arg == "name":
            yield from ((parent.lineno, value) for value in values(parent.keywords[0].value))
        else:
            yield parent.lineno, None


def ui_registry_declaration(path: Path) -> frozenset[str]:
    """Read the literal frozenset declaration without importing production code."""
    declarations = [node.value for node in parse(path).body
                    if isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "UI_PLUGINS" for t in node.targets)]
    if len(declarations) != 1:
        raise ValueError("UI_PLUGINS must have one literal declaration")
    value = declarations[0]
    if (not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name)
            or value.func.id != "frozenset" or len(value.args) != 1 or value.keywords):
        raise ValueError("UI_PLUGINS must be a literal frozenset")
    entries = ast.literal_eval(value.args[0])
    if not isinstance(entries, (set, list, tuple)) or not all(isinstance(x, str) and x for x in entries):
        raise ValueError("UI_PLUGINS must contain nonempty strings")
    return frozenset(entries)


def literal_string_keys(path: Path, name: str) -> frozenset[str]:
    """Read one authoritative literal sequence; never import the scanned module."""
    values = [n.value for n in parse(path).body if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)]
    if len(values) != 1:
        raise ValueError(f'{name}: expected one literal declaration')
    value = ast.literal_eval(values[0])
    if not isinstance(value, (tuple, list, set)) or not all(isinstance(x, str) for x in value):
        raise ValueError(f'{name}: expected string keys')
    if len(value) != len(set(value)) or not value:
        raise ValueError(f'{name}: duplicate or empty keys')
    return frozenset(value)


def stage_registry_audit(path: Path, keys: frozenset[str], layers: dict,
                         *, registry: bool = False, source_layer: int = 4) -> dict:
    """Conservative AST closure of stage conditions, dispatch and injected callbacks.

    No evaluation, inference from directory names, variable allowlist or fallback
    exemption. Every unresolved call in a reachable local handler is evidence,
    including object methods: resolving an attribute's spelling is not proof of
    its runtime owner. Imported targets retain their module identity.
    """
    tree = parse(path)
    rows = {'keys': [], 'calls': [], 'branches': [], 'targets': [], 'errors': []}
    symbols, local, ambiguous = {}, {}, set()
    parents = {c: n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
    registry_names = {'stage_handler_registry', 'orchestrator.stage_handler_registry'}

    def dotted(node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = dotted(node.value)
            return f'{base}.{node.attr}' if base else ''
        return ''

    def bind(name, target):
        if name in symbols and symbols[name] != target:
            ambiguous.add(name)
        symbols[name] = target

    builtin_calls = {'getattr', 'isinstance', 'callable', 'str', 'len', 'RuntimeError',
                     'ValueError', 'KeyError', 'TypeError', 'set', 'dict', 'tuple', 'list'}
    builtin_methods = {'dict.get', 'str.join', 'str.strip'}
    # These two audited functions read the validated stage key for lock and
    # configuration policy. Arbitrary callables in conditions remain unresolved.
    stage_condition_arguments = {'contract.script_contract.lock_stage': 0,
                                 'orchestrator.stage_flow.unchecked': 1}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bind(alias.asname or alias.name.split('.')[0],
                     alias.name if alias.asname else alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            module = _from_module(path, node) if node.level else (node.module or '')
            for alias in node.names:
                if alias.name == '*' and (registry or module in registry_names):
                    rows['errors'].append((node.lineno, 'unresolved-star-import', module))
                elif alias.name != '*':
                    bind(alias.asname or alias.name, f'{module}.{alias.name}')
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parent = parents.get(node)
            if isinstance(parent, ast.Module):
                if node.name in local:
                    ambiguous.add(node.name)
                local[node.name] = node
            elif isinstance(parent, ast.ClassDef):
                local[f'{parent.name}.{node.name}'] = node
    ambiguous.update(set(symbols) & set(local))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            ambiguous.add(node.id)
        elif isinstance(node, ast.arg):
            if node.arg in symbols or node.arg in local or node.arg in builtin_calls:
                ambiguous.add(node.arg)

    def resolve(node):
        name = dotted(node)
        head, _, tail = name.partition('.')
        if not name or head in ambiguous:
            return None
        if name in local:
            return name
        if head == 'self':
            parent = node
            while parent in parents and not isinstance(parent, ast.ClassDef):
                parent = parents[parent]
            target = f'{parent.name}.{tail}' if isinstance(parent, ast.ClassDef) else ''
            return target if target in local else None
        return symbols[head] + ('.' + tail if tail else '') if head in symbols else None

    def values(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return [node.value]  # start() does not strip its keys
        if isinstance(node, ast.Starred) and resolve(node.value) == 'contract.pet_bus.STAGES':
            return values(node.value)
        if isinstance(node, ast.IfExp):
            return values(node.body) + values(node.orelse)
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return [v for item in node.elts for v in values(item)]
        if resolve(node) == 'contract.pet_bus.STAGES':
            return sorted(literal_string_keys(ROOT / 'contract/pet_bus.py', 'STAGES'))
        return [None]

    def error(node, reason, target=''):
        rows['errors'].append((node.lineno, reason, target))

    def guarded_domain(node):
        if not isinstance(node, ast.Name):
            return [None]
        child = node
        function = parents.get(child)
        scope_nodes = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef,
                       ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
        while function is not None and not isinstance(function, scope_nodes):
            child, function = function, parents.get(function)
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return [None]
        args = function.args
        if node.id not in {arg.arg for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs)}:
            return [None]
        body = function.body[1:] if ast.get_docstring(function) is not None else function.body
        first = body[0] if body else None
        guard = first.test if isinstance(first, ast.If) else None
        if (not isinstance(guard, ast.Compare) or dotted(guard.left) != node.id
                or len(guard.ops) != 1 or not isinstance(guard.ops[0], ast.NotIn)
                or first.orelse or len(first.body) != 1 or not isinstance(first.body[0], ast.Raise)
                or child not in body[1:]):
            return [None]
        domain = guard.comparators[0]
        if (not isinstance(domain, (ast.Tuple, ast.List, ast.Set))
                and resolve(domain) != 'contract.pet_bus.STAGES'):
            return [None]
        if isinstance(domain, (ast.Tuple, ast.List, ast.Set)) and any(
                not (isinstance(item, ast.Constant) and isinstance(item.value, str))
                and not (isinstance(item, ast.Starred)
                         and resolve(item.value) == 'contract.pet_bus.STAGES')
                for item in domain.elts):
            return [None]
        # Only prove a parameter whose sole binding is the function signature.
        try:
            scope = symtable.symtable(ast.unparse(function), str(path), 'exec').get_children()[-1]
            parameter = scope.lookup(node.id)
        except (KeyError, SyntaxError):
            return [None]
        if (parameter.is_assigned() or parameter.is_imported()
                or any(isinstance(item, ast.Nonlocal) and node.id in item.names
                       for item in ast.walk(function))):
            return [None]
        return values(domain)

    def check_keys(node, *, guarded=False):
        domain = values(node)
        if guarded and domain == [None]:
            domain = guarded_domain(node)
        for key in domain:
            rows['keys'].append((node.lineno, key))
            if key is None or key not in keys:
                error(node, 'unresolved-key' if key is None else 'unknown-key', key)

    visited = set()
    def target(node, resolved, ceiling):
        rows['targets'].append((node.lineno, resolved))
        if resolved in local:
            walk_handler(local[resolved], ceiling)
        elif resolved is None:
            error(node, 'unresolved-target', dotted(node))
        else:
            module = resolved
            while module not in layers and '.' in module:
                module = module.rsplit('.', 1)[0]
            layer = layers.get(module)
            if type(layer) not in (int, float) or layer not in range(6):
                error(node, 'unregistered-target', resolved)
            elif layer > ceiling:
                error(node, 'upward-target', resolved)

    def walk_handler(function, ceiling):
        if function in visited:
            return
        visited.add(function)
        if function.decorator_list:
            error(function, 'unresolved-decorated-callback', function.name)
        for node in ast.walk(function):
            if isinstance(node, ast.If) and any(isinstance(n, ast.Name) and n.id == 'stage'
                                                for n in ast.walk(node.test)):
                rows['branches'].append((node.lineno, ast.unparse(node.test),
                    [n.lineno for statement in [*node.body, *node.orelse]
                     for n in ast.walk(statement) if isinstance(n, ast.Call)]))
                for name in ast.walk(node.test):
                    if isinstance(name, ast.Name) and name.id == 'stage':
                        comparison = parents.get(name)
                        if isinstance(comparison, ast.Call):
                            argument = stage_condition_arguments.get(resolve(comparison.func))
                            if (argument is not None and len(comparison.args) > argument
                                    and comparison.args[argument] is name):
                                continue
                        if (not isinstance(comparison, ast.Compare)
                                or not all(isinstance(op, (ast.Eq, ast.NotEq, ast.In, ast.NotIn))
                                           for op in comparison.ops)):
                            error(node, 'unresolved-condition', ast.unparse(node.test))
            if isinstance(node, ast.Compare):
                operands = [node.left, *node.comparators]
                if any(isinstance(x, ast.Name) and x.id == 'stage' for x in operands):
                    for operand in operands:
                        if not (isinstance(operand, ast.Name) and operand.id == 'stage'):
                            check_keys(operand)
            if isinstance(node, ast.Call):
                name = dotted(node.func)
                owner = name.partition('.')[0]
                if (name in builtin_calls or name in builtin_methods) and (
                        owner not in ambiguous and owner not in symbols and owner not in local):
                    continue
                injected_action = (name in ('skip_action', 'run_action')
                                   and function is local.get('start')
                                   and any(arg.arg == name for arg in function.args.kwonlyargs)
                                   and name not in ambiguous and name not in symbols and name not in local)
                if registry and (name == 'fallback' or injected_action):
                    rows['targets'].append((node.lineno, f'<injected:{name}>'))
                    continue  # the caller must prove the injected callable separately
                target(node.func, resolve(node.func), ceiling)

    if registry:
        start = local.get('start')
        if start is None:
            rows['errors'].append((1, 'missing-start', 'start'))
        else:
            # A sufficient, deliberately narrow entry guard: unknown keys raise
            # before side effects, callbacks or exception handlers can consume them.
            body = [n for n in start.body if not (isinstance(n, ast.Expr)
                    and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str))]
            first = body[0] if body else None
            guard = first.test if isinstance(first, ast.If) else None
            closed = (isinstance(guard, ast.Compare) and len(guard.ops) == 1
                      and isinstance(guard.ops[0], ast.NotIn) and dotted(guard.left) == 'stage'
                      and set(values(guard.comparators[0])) == set(keys)
                      and len(first.body) == 1 and isinstance(first.body[0], ast.Raise)
                      and first.body[0].exc is not None)
            if not closed:
                error(start, 'unvalidated-stage-domain', 'start')
            walk_handler(start, 3)
    else:
        endpoints = {n.name for n in parse(ROOT / 'orchestrator/stage_handler_registry.py').body
                     if isinstance(n, ast.FunctionDef)}
        for node in ast.walk(tree):
            resolved = resolve(node)
            raw = dotted(node)
            head, _, tail = raw.partition('.')
            imported = symbols.get(head, '') + ('.' + tail if tail else '')
            if head in ambiguous and (imported in registry_names or
                                      imported in {f'{name}.start' for name in registry_names}):
                error(node, 'unresolved-registry-binding', imported)
                continue
            is_start = resolved in {f'{name}.start' for name in registry_names}
            if not is_start and resolved not in registry_names:
                continue
            parent = parents.get(node)
            if resolved in registry_names and isinstance(parent, ast.Attribute):
                if parent.attr == 'start':
                    continue
                call = parents.get(parent)
                if isinstance(call, ast.Call) and call.func is parent and parent.attr in endpoints:
                    target(parent, f'{resolved}.{parent.attr}', source_layer)
                    continue
            if not is_start or not isinstance(parent, ast.Call) or parent.func is not node:
                error(node, 'unresolved-registry-escape', resolved)
                continue
            call = parent
            rows['calls'].append(call.lineno)
            target(node, resolved, source_layer)
            kwargs = {kw.arg: kw.value for kw in call.keywords}
            key = call.args[1] if len(call.args) > 1 else kwargs.get('stage')
            if key is None:
                error(call, 'unresolved-key')
            else:
                check_keys(key, guarded=True)
            if any(isinstance(arg, ast.Starred) for arg in call.args) or None in kwargs:
                error(call, 'unresolved-arguments')
            if (len(call.args) > 4 or (len(call.args) > 1 and 'stage' in kwargs)
                    or (len(call.args) > 3 and 'fallback' in kwargs)
                    or len(kwargs) != len(call.keywords)):
                error(call, 'unresolved-arguments')
            callback = call.args[3] if len(call.args) > 3 else kwargs.get('fallback')
            for action in (callback, kwargs.get('skip_action'), kwargs.get('run_action')):
                if action is not None and not (isinstance(action, ast.Constant) and action.value is None):
                    for option in ([action.body, action.orelse] if isinstance(action, ast.IfExp) else [action]):
                        target(option, resolve(option), source_layer)
    # Deterministic evidence without suppressing different reasons at one site.
    rows['errors'] = sorted(set(rows['errors']), key=repr)
    return rows


def require_stage_registry_closure(audits: dict) -> None:
    """Strict consumer: no production baseline/exemption can turn a refusal green."""
    rejected = {name: row['errors'] for name, row in audits.items() if row['errors']}
    if rejected:
        raise AssertionError(f'Stage registry closure rejected: {rejected}')


@dataclass(frozen=True)
class RuntimeTool:
    role: str
    entries: dict[str, tuple[str, ...]]
    support: tuple[str, ...] = ()
    layer: int | None = None


def _tool_import_rows(tree: ast.Module, source: str, root: Path, *,
                      namespace: str | None = None) -> Iterator[tuple[int, str | None]]:
    """保留限定身份及 namespace 子模块，函数内导入也计入。"""
    package = ".".join(Path(source).parts[:-1])
    nodes = tuple(ast.walk(tree))
    dynamic = {"__import__", "import_module"}
    dynamic.update(alias.asname or alias.name for node in nodes
                   if isinstance(node, ast.ImportFrom) and node.module == "importlib"
                   for alias in node.names if alias.name == "import_module")
    for node in nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                try:
                    base = resolve_name("." * node.level + base, package)
                except ImportError:
                    yield node.lineno, None
                    continue
            yield node.lineno, base
            for alias in node.names:
                child = f"{base}.{alias.name}"
                if base == namespace and alias.name == "*":
                    yield node.lineno, None
                elif base == namespace or _tool_import_file(root, child):
                    yield node.lineno, child
        elif isinstance(node, ast.Call):
            function = node.func
            name = function.id if isinstance(function, ast.Name) else getattr(function, "attr", "")
            if name in dynamic:
                arg = node.args[0] if node.args else None
                yield node.lineno, arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else None


def _tool_import_file(root: Path, name: str) -> str | None:
    parts = name.split(".")
    if not all(part.isidentifier() for part in parts):
        return None
    base = root.joinpath(*parts)
    for file in (base / "__init__.py", base.with_suffix(".py")):
        if file.is_file():
            return file.relative_to(root).as_posix()
    return None


def _tool_entry_points(tree: ast.Module) -> set[str]:
    entries = {node.name for node in tree.body
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    if any(isinstance(node, ast.If) and _is_main_guard(node.test) and
           any(not isinstance(statement, ast.Pass) for statement in node.body) for node in tree.body):
        entries.add("__main__")
    if any(isinstance(node, (ast.Assign, ast.Expr)) and
           any(isinstance(child, ast.Call) and getattr(child.func, "attr", "") == "mainloop"
               for child in ast.walk(node)) for node in tree.body):
        entries.add("mainloop")
    return entries


def _isolated_tool_imports(root: Path, namespace: str, entry_files: set[str],
                           support: tuple[str, ...], issues: set) -> tuple[set[str], set[tuple]]:
    """从进程入口递归审计本地导入和独立环境声明，保留每条诊断的源位置。"""
    dependency_names = set()
    for relative in support:
        path = root / relative
        if path.name == "requirements.txt" and path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                name = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)(?=\s*(?:[<>=!~;@\[#]|$))", line)
                if name:
                    dependency_names.add(re.sub(r"[-_.]+", "_", name[1]).lower())
    visited, edges = set(), set()
    pending = set(entry_files)
    while pending:
        source = pending.pop()
        if source in visited or not (root / source).is_file():
            continue
        visited.add(source)
        # 直接执行脚本和 python -m 都会经过本地包初始化，且工具的导入也可能递归加载它。
        for parent in Path(source).parents:
            initializer = (parent / "__init__.py").as_posix()
            if initializer not in visited and (root / initializer).is_file():
                pending.add(initializer)
        for line, name in _tool_import_rows(parse(root / source), source, root, namespace=namespace):
            location = f"{source}:{line}"
            if not name:
                issues.add(("process-unresolved-import", location, namespace))
                continue
            target = _tool_import_file(root, name)
            top = name.split(".")[0]
            edges.add((source, line, name, target))
            if target and top == namespace:
                pending.add(target)
            elif target:
                issues.add(("process-import", location, name))
            elif top == namespace:
                issues.add(("process-missing-module", location, name))
            elif top not in sys.stdlib_module_names and top.lower() not in dependency_names:
                issues.add(("process-dependency", location, name))
    return visited, edges


def tool_runtime_audit(root: Path, sources, legacy_tools, components: dict[str, RuntimeTool],
                       kept, layers: dict, references: dict, *, generated=()) -> dict:
    """对账工具登记、源位置、运行入口、独立导入闭包和实际分发计划。"""
    issues, tool_edges = set(), set()
    closure, process_edges = {}, {}
    owned = {}
    callers = {name: {entry: set(references.get(name, {}).get(entry, ())) for entry in tool.entries}
               for name, tool in components.items()}
    for name in set(legacy_tools) - components.keys():
        issues.add(("unclassified-registration", name, "TOOLS"))
    for name, tool in components.items():
        files = {*tool.entries, *tool.support}
        if tool.role not in {"runtime", "process", "generator", "development"}:
            issues.add(("invalid-role", name, tool.role))
        if not tool.entries:
            issues.add(("missing-entry", name, tool.role))
        if tool.role == "process":
            imported, edges = _isolated_tool_imports(root, name, set(tool.entries), tool.support, issues)
            files.update(imported)
            process_edges[name] = sorted(edges)
        closure[name] = sorted(files)
        for relative in files:
            if relative in owned:
                issues.add(("duplicate-owner", relative, name))
            owned[relative] = name
            path = root / relative
            if not path.is_file():
                issues.add(("missing-file", relative, name))
                continue
            symbols = tool.entries.get(relative, ())
            if symbols:
                for symbol in sorted(set(symbols) - _tool_entry_points(parse(path))):
                    issues.add(("missing-entry", relative, symbol))
            if tool.role != "development" and relative not in kept:
                issues.add(("release-missing", relative, name))
            if tool.role == "development" and relative in kept:
                issues.add(("release-development", relative, name))
    for item in set(generated) & set(kept):
        issues.add(("release-generated-data", item, "local runtime data"))

    application = set(sources) - owned.keys()
    runtime_layers = {entry: tool.layer for tool in components.values()
                      if tool.role == "runtime" for entry in tool.entries}
    layer_by_file = {**layers, **runtime_layers}
    for source in sorted(application | runtime_layers.keys()):
        if not (root / source).is_file():
            continue
        tree = parse(root / source)
        for line, imported in _tool_import_rows(tree, source, root):
            target = _tool_import_file(root, imported) if imported else None
            if imported and source.endswith(".pyw"):
                # 执行脚本时其所在目录先于程序根参与模块查找。
                sibling = ".".join((*Path(source).parts[:-1], imported))
                target = _tool_import_file(root, sibling) or target
            if not target:
                continue
            owner = owned.get(target)
            if not owner and target in application and source not in runtime_layers:
                continue
            tool_edges.add((source, line, target))
            location = f"{source}:{line}"
            if owner and components[owner].role != "runtime":
                issues.add(("nonruntime-import", location, target))
            elif not owner and target not in application:
                issues.add(("unclassified-import", location, target))
            else:
                if owner and target in callers[owner] and owned.get(source) != owner:
                    callers[owner][target].add((source, line, "import"))
                source_layer, target_layer = layer_by_file.get(source), layer_by_file.get(target)
                if source_layer is None or target_layer is None:
                    issues.add(("unclassified-layer", location, target))
                elif source_layer < target_layer:
                    issues.add(("upward-import", location, target))
    for name, tool in components.items():
        if tool.role != "development" and not any(callers[name].values()):
            issues.add(("no-production-consumer", name, tool.role))
        if tool.role == "development":
            for entry, rows in callers[name].items():
                for source, line, _ in rows:
                    if source in application:
                        issues.add(("development-launch", f"{source}:{line}", entry))
        if tool.role == "process":
            for entry, rows in callers[name].items():
                if not rows:
                    issues.add(("no-process-launch", entry, name))
    return {
        "callers": {name: {entry: sorted(rows) for entry, rows in entries.items()}
                    for name, entries in callers.items()},
        "closure": closure,
        "process_imports": process_edges,
        "tool_imports": sorted(tool_edges),
        "issues": sorted(issues),
    }


def require_tool_runtime_closure(audit: dict) -> None:
    """严格入口不使用默认回归中的已知诊断作为放行条件。"""
    if audit["issues"]:
        raise AssertionError(f"Tool runtime closure rejected: {audit['issues']}")
