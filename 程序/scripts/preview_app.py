r"""合入前预览（开发工具，不进分发副本）：本工作树代码配隔离示例数据，开一扇带「预览」字样的窗口。

用当前工作树里的代码（sys.path 指向 PROGRAM）起一个真实 Tk/Desktop 窗口；数据目录放系统临时目录
``manju-preview\<分支名>`` 下，里面只有一个空的示例项目。窗口标题始终保持「预览 · <分支> · 」前缀，
可与正式应用同时开着。预览不该碰到正式应用的任何东西，靠下面五层：

* 应用数据：config.json/projects.json/desktop_settings.json 都建在数据目录的 ``app`` 下，不建 private，
  不读任何已登记项目；项目库位置（downloads_root）也指在数据目录里。已建过的数据再用之前复查一遍，
  项目库位置或登记的项目指到了数据目录之外就拒绝启动（见 _check_stays_inside）。
* 只在车道里开窗口：主工作区的 ``程序`` 目录同时放着正式应用的数据，在那里开预览，任何按代码目录找文件
  的模块都会碰到它；所以代码目录不在 git 附加工作树（车道）里时拒绝开窗口（见 in_linked_worktree）。
* 用户级目录：应用把配音、生图、云端等设置和密钥存在 ``%LOCALAPPDATA%\漫剧制作助手`` 下，命令行助手的
  登录和技能目录在用户主目录下。开窗口前把本进程的 LOCALAPPDATA、APPDATA、USERPROFILE 等环境变量改指到
  数据目录的 ``user`` 下，并去掉名字像密钥、令牌的环境变量（见 isolate_user_env）：预览里没有登录、没有模型密钥。
* 注册表：开机自启、登录时钟基线、「下载」文件夹位置都经同一个注册表入口，预览进程里把它换成「不可用」
  （见 block_registry）。
* 关窗清理：应用关窗时会另起后台进程清理项目库（把各项目的历史版本挪进回收站）、日志和工作树。项目库清理按
  代码目录里的 config.json 找项目库，车道里没有这份文件就退回写死的默认位置——用户真实的项目库。预览进程里
  把这个派发入口换成空操作（见 block_exit_cleanup）。

还共用的：系统临时目录里的缩略图缓存（只是缓存）；PATH 不动，所以本机装的命令行助手和工具链仍能被找到，只是
没有登录；网络照常（标准库会去读系统代理设置，只读，不经应用的注册表入口）。车道代码目录里的 outputs、logs
等运行时目录照常会写，它们不进版本库。

暂不提供「复制真实项目来预览」：真实项目的 config.json 里记着指向原项目的绝对路径（episode_dir、
episode_file），原样复制后预览会顺着这些路径读写原项目；等补上路径改写和残留检查再开放。

用法（随附解释器，在车道的 程序\ 下）::

    python.exe -B scripts\dev.py preview                          # 建/刷新隔离数据并打开预览窗口
    python.exe -B scripts\preview_app.py --data <目录>             # 指定数据目录（缺省按分支名取）
    python.exe -B scripts\preview_app.py --reset                   # 删除本工具建的预览数据目录
    python.exe -B scripts\preview_app.py --print-only              # 只建数据打印路径，不开窗口
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]

MARKER = ".manju-preview"
TITLE_PREFIX = "预览 · "
# 名字像凭据的环境变量（应用和命令行助手都认这类变量）与「配置目录另有所指」的覆盖项，预览进程里一律去掉。
CREDENTIAL_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL", re.IGNORECASE)
CONFIG_OVERRIDES = frozenset({
    "CODEX_HOME", "CLAUDE_CONFIG_DIR", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"})


def _branch_name() -> str:
    """当前分支名：优先复用 round_claim.current_branch，取不到再 git rev-parse，最后 'worktree'。"""
    try:
        maintenance = str(PROGRAM / "维护记录" / "基准脚本")
        if maintenance not in sys.path:
            sys.path.insert(0, maintenance)
        import round_claim
        name = round_claim.current_branch(PROGRAM)
        if name:
            return name
    except (ImportError, OSError, subprocess.SubprocessError):
        pass
    try:
        result = subprocess.run(
            ["git", "-C", str(PROGRAM), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
        if result.returncode == 0:
            name = result.stdout.strip()
            if name and name != "HEAD":
                return name
    except (OSError, subprocess.SubprocessError):
        pass
    return "worktree"


def _safe_name(name: str) -> str:
    """目录安全名：字母、数字、点、下划线、连字符以外的字符一律换成连字符。"""
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "-", name)
    return cleaned if cleaned not in {"", ".", ".."} else "worktree"


def default_data_dir(name=None) -> Path:
    """预览数据目录：<系统临时目录>/manju-preview/<名字>；name 为 None 时取当前分支名。"""
    return Path(tempfile.gettempdir()) / "manju-preview" / _safe_name(name or _branch_name())


def _worktree_root(path):
    """path（不存在则从最近的已存在上级）逐级向上找含 .git 文件或目录的一级；到盘符根都没有返回 None。"""
    current = Path(path)
    while not current.exists():
        parent = current.parent
        if parent == current:
            return None
        current = parent
    while True:
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def in_linked_worktree(program=None) -> bool:
    """代码目录是否在车道（git 的附加工作树）里：附加工作树根目录的 .git 是文件，主工作区的是目录。"""
    root = _worktree_root(Path(program) if program else PROGRAM)
    return root is not None and (root / ".git").is_file()


def check_data_dir(path) -> Path:
    """预览数据目录安全校验；合格返回解析后的绝对路径，不合格抛 ValueError。"""
    candidate = Path(path)
    if _worktree_root(candidate) is not None:
        raise ValueError(f"预览数据目录不能放在代码仓库里：{candidate}")
    if candidate.exists() and not candidate.is_dir():
        raise ValueError(f"预览数据目录指向的是文件而不是目录：{candidate}")
    if not candidate.exists():
        return candidate.resolve()
    if (candidate / MARKER).is_file():
        return candidate.resolve()
    if not any(candidate.iterdir()):
        return candidate.resolve()
    raise ValueError(f"{candidate} 不是预览工具建的目录：换个空目录，或先确认里面没有要留的东西")


def _inside(path, parent) -> bool:
    """path 解析后是否落在 parent 里（含 parent 本身）；解析不了算不在。"""
    try:
        return Path(path).resolve().is_relative_to(Path(parent).resolve())
    except (OSError, ValueError):
        return False


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _read_json(path: Path):
    """读一份 UTF-8 JSON 文件；读不出（不存在、损坏或类型不符）返回 None。"""
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, ValueError):
        return None


def _remember_choice(app: Path, project) -> None:
    """把当日项目选择刷成今天并指向 project，启动时直接进这个项目；读不出原设置就整份重写。"""
    settings = _read_json(app / "desktop_settings.json")
    if not isinstance(settings, dict):
        settings = {}
    settings["project_choice_day"] = date.today().isoformat()
    settings["project_choice_path"] = str(project)
    _write_json(app / "desktop_settings.json", settings)


def _check_stays_inside(data_dir: Path, app: Path, info: dict) -> None:
    """已建过的预览数据再用之前复查：项目库位置和登记的项目都还在 data_dir 里，不在就抛 ValueError。

    应用的 config.json 里没有 downloads_root 时会退回写死的默认项目库（用户真实的那一份）；登记里若混进了
    数据目录之外的项目，预览窗口会用没合入的代码直接读写它。两种情况都不带着继续开。
    """
    config = _read_json(app / "config.json")
    root = config.get("downloads_root") if isinstance(config, dict) else None
    outside = []
    if not root or not _inside(root, data_dir):
        outside.append(f"config.json 的 downloads_root（{root or '缺失'}）")
    entries = info.get("projects")
    paths = [info.get("active")]
    if isinstance(entries, list):
        paths += [item.get("path") for item in entries if isinstance(item, dict)]
    for path in dict.fromkeys(str(item) for item in paths if item):
        if not _inside(path, data_dir):
            outside.append(f"登记的项目 {path}")
    if outside:
        raise ValueError("预览数据指到了数据目录之外：" + "；".join(outside) + "。请先用 --reset 删掉这份预览数据再开")


def build_sample(data_dir) -> dict:
    """在 data_dir 下建最小可用数据（结构同 tests/test_desktop_startup_perf._startup_app）。

    返回 {"app": <应用数据目录>, "project": <项目目录>}；已建过时先复查数据没有指到目录之外，再把当日项目选择
    刷成今天，不覆盖 config.json 与 projects.json。不建 private，不复制任何密钥、登录状态或设置文件。
    """
    data_dir = check_data_dir(data_dir)
    app = data_dir / "app"
    projects_file = app / "projects.json"
    today = date.today()
    if projects_file.is_file():
        info = _read_json(projects_file)
        active = info.get("active") if isinstance(info, dict) else None
        if not active:
            raise ValueError(f"projects.json 已存在但读不出有效 active：{projects_file}")
        _check_stays_inside(data_dir, app, info)
        _remember_choice(app, active)
        return {"app": app, "project": Path(active)}
    downloads = data_dir / "downloads"
    project = downloads / "项目" / f"预览示例项目_{today:%Y%m%d}"
    (project / "01剧本准备" / "输入").mkdir(parents=True, exist_ok=True)
    (project / "config.json").write_text("{}", encoding="utf-8")
    _write_json(app / "config.json", {"downloads_root": str(downloads)})
    _write_json(projects_file, {
        "active": str(project),
        "projects": [{"name": "预览示例项目", "path": str(project)}],
    })
    _write_json(app / "desktop_settings.json", {
        "project_choice_day": today.isoformat(),
        "project_choice_path": str(project),
    })
    (data_dir / MARKER).write_text(
        f"created {datetime.now().isoformat(timespec='seconds')} branch {_branch_name()}\n",
        encoding="utf-8")
    return {"app": app, "project": project}


def isolate_user_env(data_dir) -> dict:
    """把本进程的用户级目录环境变量改指到 data_dir/user 下，返回 {变量名: 新取值}。

    应用把配音、生图、云端等设置和密钥存在 LOCALAPPDATA 下的「漫剧制作助手」目录，命令行助手的登录、
    技能目录在用户主目录下；不改指，预览窗口就会和正式应用共用这些文件。同时去掉名字像密钥、令牌的
    环境变量和「配置目录另有所指」的覆盖项（只看名字，不读取值）。只改本进程的环境（子进程继承），不动
    系统设置；必须在导入应用代码之前调用，否则模块级常量已经按原目录算好。
    """
    base = Path(data_dir) / "user"
    targets = {
        "USERPROFILE": base,
        "HOME": base,
        "LOCALAPPDATA": base / "AppData" / "Local",
        "APPDATA": base / "AppData" / "Roaming",
    }
    for path in targets.values():
        path.mkdir(parents=True, exist_ok=True)
    values = {name: str(path) for name, path in targets.items()}
    drive, tail = os.path.splitdrive(str(base))
    if drive:
        values["HOMEDRIVE"], values["HOMEPATH"] = drive, tail or os.sep
    for name in list(os.environ):
        if name.upper() in CONFIG_OVERRIDES or CREDENTIAL_NAME.search(name):
            del os.environ[name]
    os.environ.update(values)
    return values


def _program_on_path() -> None:
    program = str(PROGRAM)
    if not sys.path or sys.path[0] != program:
        sys.path.insert(0, program)


def _swap_everywhere(name, original, replacement):
    """把已导入模块里名为 name、仍指向 original 的引用都换成 replacement；返回把它们换回去的函数。"""
    patched = []
    for module in list(sys.modules.values()):
        namespace = getattr(module, "__dict__", None)
        if isinstance(namespace, dict) and namespace.get(name) is original:
            namespace[name] = replacement
            patched.append(namespace)

    def restore():
        for namespace in patched:
            if namespace.get(name) is replacement:
                namespace[name] = original

    return restore


def block_registry():
    """把应用唯一的注册表入口换成「不可用」，只对本进程生效；返回把它换回去的函数（测试收尾用）。

    应用读写注册表都经 contract.platform_tools.windows_registry()：开机自启写当前用户的 Run 项，
    登录时钟基线写一项数值，「下载」文件夹的位置也从这里读。环境变量管不到注册表，所以预览里让这个入口
    返回 None——各调用方本来就把 None 当「本机不支持」处理。已经导入、手里留着原函数引用的模块一并换掉。
    """
    _program_on_path()
    import contract.platform_tools as platform_tools
    original = platform_tools.windows_registry

    def registry_unavailable():
        return None

    return _swap_everywhere("windows_registry", original, registry_unavailable)


def block_exit_cleanup():
    """关窗后不起后台清理，只对本进程生效；返回把它换回去的函数（测试收尾用）。

    应用关窗时经 orchestrator.exit_maintenance.launch_cleanup 另起三个后台进程：项目库清理、日志清理、
    仓库卫生。项目库清理按代码目录里的 config.json 找项目库，车道里没有这份文件就退回写死的默认位置——用户
    真实的项目库，会把各项目的历史版本挪进回收站。预览窗口关掉时不该碰这些，所以把派发入口换成只打印一行
    的空操作；已经导入、手里留着原函数引用的模块一并换掉。
    """
    _program_on_path()
    import orchestrator.exit_maintenance as exit_maintenance
    original = exit_maintenance.launch_cleanup

    def cleanup_disabled(program=None, **_options):
        try:
            print("[预览] 关窗清理已关闭：预览窗口不清理项目库、日志和工作树")
        except (OSError, ValueError):
            pass
        return dict.fromkeys(("storage", "logs", "workspace"), "preview-disabled")

    return _swap_everywhere("launch_cleanup", original, cleanup_disabled)


def open_window(app_dir, label):
    """用本工作树代码起 Desktop 窗口，数据目录为 app_dir；标题始终保持「预览 · <label> · 」前缀。

    Desktop 自己还会改标题，所以立即补一次前缀，再挂每 500 毫秒一次的检查回调；
    窗口已销毁时回调安静结束。只建窗口、不进 mainloop，返回 (window, desktop) 由调用方收尾。
    本函数不做隔离：用户级目录、注册表和关窗清理由调用方先调 isolate_user_env、block_registry、
    block_exit_cleanup（main 就是这么做的）。
    """
    os.chdir(PROGRAM)
    _program_on_path()
    import tkinter as tk
    from desktop import Desktop
    window = tk.Tk()
    desktop = Desktop(window, root=Path(app_dir))
    wanted = TITLE_PREFIX + label + " · "

    def keep_prefix():
        try:
            if window.winfo_exists():
                title = window.title()
                if not title.startswith(TITLE_PREFIX):
                    window.title(wanted + title)
                window.after(500, keep_prefix)
        except tk.TclError:
            return

    keep_prefix()
    return window, desktop


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="合入前预览：本工作树代码配隔离示例数据，打开带「预览」字样的窗口")
    parser.add_argument("--data", metavar="目录",
                        help="预览数据目录（缺省 <系统临时目录>/manju-preview/<分支名>）")
    parser.add_argument("--reset", action="store_true", help="删除本工具建的预览数据目录后退出")
    parser.add_argument("--print-only", action="store_true", help="只建数据打印路径，不打开窗口")
    args = parser.parse_args(argv)
    data_dir = Path(args.data) if args.data else default_data_dir()
    try:
        if args.reset:
            resolved = check_data_dir(data_dir)
            if resolved.exists():
                if not (resolved / MARKER).is_file():
                    raise ValueError(f"{resolved} 不是预览工具建的目录，拒绝删除")
                shutil.rmtree(resolved)
                print(f"[预览] 已删除 {resolved}")
            return 0
        if not args.print_only and not in_linked_worktree():
            raise ValueError("预览只能在车道工作树里开：主工作区放着正式应用的数据，"
                             "看主干效果请开正式应用")
        built = build_sample(data_dir)
        print(f"[预览] 数据目录 {data_dir}；项目 {built['project']}")
        if args.print_only:
            return 0
        label = _branch_name()
        isolate_user_env(built["app"].parent)
        block_registry()
        block_exit_cleanup()
        window, _ = open_window(built["app"], label)
        window.mainloop()
        return 0
    except ValueError as exc:
        print(f"[预览] 未启动：{exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
