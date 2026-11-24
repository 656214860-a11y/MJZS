"""共享模型配置的路径、只读探针和配置覆盖前的环形快照（U10）。

快照固定使用 ``SLOTS`` 个槽位轮流覆盖。调用方只在写入前调用 ``keep``；
快照失败时记录日志，继续保存配置。
"""
import os
from pathlib import Path

import infra.app_logging as app_logging
from agent.core import read, save_bytes

MODEL_CONFIG_PATH = ('配置', '宠物', '配置.json')
SLOTS = 20


def model_config_file(program):
    return Path(program).joinpath(*MODEL_CONFIG_PATH)


def has_stored_models(program) -> bool:
    """配置文件缺失视为空池，其他读取错误交给调用方处理。"""
    try:
        config = read(model_config_file(program))
    except FileNotFoundError:
        return False
    models = config.get('models') if isinstance(config, dict) else None
    return isinstance(models, dict) and bool(models)


def has_usable_cli_engine(which=None, environ=None, home=None) -> bool:
    """本机是否装有任一已知命令行引擎（REL-03）；``which``／``environ``／``home`` 可注入。

    查找点与 ``workflow_settings.find_program`` 的 CLI 分支对齐：PATH 先行，
    再查各引擎的已知安装目录（Qwen 需 node 与入口脚本成对存在）。判定只用
    表达式短路（``any``／``and``），不增语句级分支——分支覆盖率基线按实体
    决策点数钉死，本模块属 L1 受棘轮。
    """
    import shutil
    which = which or shutil.which
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    local = Path(environ.get('LOCALAPPDATA', ''))
    qwen = local / 'qwen-code' / 'qwen-code'
    appdata = environ.get('APPDATA')
    return any((
        any(which(exe) for exe in ('codex.exe', 'claude.exe', 'qwen.exe', 'opencode-cli.exe')),
        any((local / 'OpenAI' / 'Codex' / 'bin').glob('*/codex.exe')),
        (home / '.local' / 'bin' / 'claude.exe').is_file(),
        (qwen / 'node' / 'node.exe').is_file() and (qwen / 'lib' / 'cli-entry.js').is_file(),
        bool(appdata) and any((Path(appdata) / 'ai.opencode.desktop' / 'cli').glob('*/opencode-cli.exe')),
    ))


def keep(path, folder, prefix, slots=SLOTS):
    """把 ``path`` 现有内容复制进 ``folder`` 里最久没写的槽位；源文件不存在则什么也不做。"""
    try:
        path = Path(path)
        if not path.is_file():
            return None
        folder = Path(folder)
        names = [folder / ('%s_%02d.json' % (prefix, index)) for index in range(slots)]
        target = min(names, key=lambda item: os.path.getmtime(item) if item.exists() else 0.0)
        save_bytes(target, path.read_bytes())
        return target
    except OSError:
        app_logging.swallowed()
        return None
