"""仅以 AST 读取程序根目录生产模块的架构扫描辅助函数。"""
from __future__ import annotations
import ast
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
EXCLUDED_PARTS = frozenset({"tests", "tasks_round", "维护记录", ".git", ".wt", ".selftmp", "__pycache__"})


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

# 非产品目录：技能随附脚本、开发／维护脚本、参考资料、构建产物与外部附加工具。
# 它们是独立工具，不属于产品运行时，不参与「正式资源目标」类审计的扫描范围。
NON_PRODUCT_PARTS = frozenset({"skills", "scripts", "reference", "outputs", "附加工具"})


def production_runtime_files() -> tuple[Path, ...]:
    """产品运行时生产模块：递归口径再排除非产品目录。

    与根目录口径相比，这里补上 agent/ 等被产品模块实际导入的运行时子包；
    与递归口径相比，去掉 skills/／scripts/／reference/／outputs/／附加工具/ 这些非产品目录。
    """
    return tuple(path for path in production_files_recursive()
                 if not NON_PRODUCT_PARTS.intersection(path.relative_to(ROOT).parts))

def module_name(path: Path) -> str:
    return path.stem

def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


# R1480／R1490：Desktop 的方法分散在 desktop.py 与两个原样迁出的 Mixin 模块里；检查 Desktop 源码
# 行为（调用、方法体）的门禁用下面两个入口，别再直接读 desktop.py，否则迁出的方法会"消失"。
DESKTOP_PARTS = ("desktop.py", "desktop_auto_flows.py", "desktop_idea_chat.py", "desktop_idea_bubbles.py",
                 "desktop_idea_attachments.py", "desktop_writing_page.py",
                 "desktop_storyboard_page.py",
                 "desktop_idea_menus.py", "desktop_asset_pages.py", "desktop_script_pages.py", "desktop_media_pages.py", "desktop_project_pages.py",
                 "desktop_layout.py", "desktop_pet_bridge.py", "desktop_async_tasks.py", "desktop_page_nav.py", "desktop_lifecycle.py")


def desktop_text() -> str:
    return chr(10).join((ROOT / name).read_text(encoding="utf-8") for name in DESKTOP_PARTS)


PET_UI_PARTS = ("pet_ui.py", "pet_ui_support.py", "pet_ui_stages.py", "pet_ui_settings.py", "pet_ui_voice.py", "pet_ui_view.py", "pet_ui_popup.py")


def pet_ui_text() -> str:
    """Pet 的方法分布在 pet_ui.py 与迁出的 Mixin／support 模块里（R1506）。"""
    return chr(10).join((ROOT / name).read_text(encoding="utf-8") for name in PET_UI_PARTS)


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
    return "\n\n".join((ROOT / (name + ".py")).read_text(encoding="utf-8") for name in STAGE_EXECUTION_MODULES)
