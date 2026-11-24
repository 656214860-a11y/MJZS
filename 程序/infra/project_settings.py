"""项目级开关（ui_settings.json）的统一读写入口，供无人值守/自动流程复用。

只保存「助手行为」类开关，不保存分镜采用列表等业务数据；沿用同一份 ui_settings.json，
写入前先读回已有内容，避免覆盖其他模块的键。
另收项目配置 JSON 的「最近一次可读快照」助手（同目录 ``<原名>.bak``），
config.json 等配置读坏时回退用，命名口径与 ``artifact_schema.migrate_file`` 一致。
"""
import shutil
from contextlib import suppress
from pathlib import Path
from agent.core import read,save,read_json
from agent.publication import access
from contract.infra_errors import ConfigError

DEFAULTS={'auto_review':False,'auto_adopt':False,'auto_edit':False,'auto_submit':False,'auto_keyframe':False,'auto_asset':False,'auto_video':False,'auto_previs':False,'auto_final':False,'auto_handoff':False}

def file(project):return Path(project)/'ui_settings.json'

def config_backup_path(path):
    """项目配置「最近一次可读快照」的位置：同目录 ``<原名>.bak``（如 config.json.bak）。"""
    path=Path(path)
    return path.with_name(path.name+'.bak')

def refresh_json_backup(path):
    """主文件读通后刷新 .bak 快照：内容一致不重复写；快照写不动不挡读取主流程。"""
    path=Path(path);backup=config_backup_path(path)
    with suppress(OSError):
        if not backup.is_file() or backup.read_bytes()!=path.read_bytes():shutil.copyfile(path,backup)
    return backup if backup.is_file() else None

def read_json_or_backup(path,reader=read,error=None):
    """主文件读坏后回退最近 .bak 快照：快照是 JSON 对象就返回它；救不回时抛 ``error()``，未传则返回 None。"""
    backup=config_backup_path(path)
    data=None
    with suppress(OSError,ValueError,UnicodeError):data=reader(backup)
    if isinstance(data,dict):return data
    if error is not None:raise error()
    return None

def config_open_error(path, exc):
    """项目配置读坏且 .bak 也不可用时的可操作报错：点名备份文件，给检查与找回两条路。"""
    backup=config_backup_path(path)
    detail='；同目录备份 '+backup.name+' 也读不出来' if backup.is_file() else '；同目录没有可用的备份 '+backup.name
    return ValueError('项目配置文件 '+Path(path).name+' 无法读取：'+str(exc)+detail
                      +'。请保留原文件，检查 UTF-8 编码与 JSON 对象格式后重试，'
                      '或在项目选择窗口选中这个项目后点「重新查找项目」。')

def note_json_backup_recovered(path, exc, *, logger):
    """.bak 回退成功的提示：应用日志警告＋诊断台账一笔；两处写不动都不挡读取主流程。"""
    import logging
    logging.getLogger(logger).warning('项目配置文件 %s 读坏，已回退到同目录备份 %s（%s）',
                                      Path(path).name,config_backup_path(path).name,exc)
    with suppress(Exception):
        from infra.diagnostic_state import record_degradation
        record_degradation(exc,stage='project-config',project=str(Path(path).parent),error_code='E-IO-CORRUPT')

def read_prefs(path,reader=read):
    """读取 ui_settings.json：损坏时抛出可操作的中文提示，而不是把 JSONDecodeError 抛到界面。

    与 load() 的区别：load() 服务于「开关」，读不到就按默认关闭处理（无人值守宁可不做）；
    而采用状态、当前分镜这些数据缺了就静默丢，用户会以为助手忘了自己的操作。
    reader 决定缓存策略：页面只读路径传 file_cache.read_json（同一轮只解析一次），
    读—改—写路径用默认的 agent.core.read（每次返回新对象，就地改不会污染缓存）。
    """
    if not Path(path).is_file():return {}
    try:data=reader(path)
    except (OSError,ValueError,UnicodeError) as exc:
        raise ValueError('项目设置文件 ui_settings.json 无法读取（可能被截断或被手工改坏）：'+str(exc)
                         +'。请保留原文件并检查，或把它移走后重新采用分镜。') from exc
    return data if isinstance(data,dict) else {}

def load(project):
    # 读不出来（没有／坏 JSON）一律当「开关都没开」：无人值守宁可不做，也不能被一个坏文件卡住。
    data=read_json(file(project))
    return data if isinstance(data,dict) else {}

def get(project,key,default=None):
    data=load(project)
    if key in data:return data[key]
    return DEFAULTS.get(key,default)

def _read_for_write(path):
    """put 锁内严格重读：仅文件不存在可建空表，其余读取错误均拒写。

    ``load()`` 的安全关闭视图只供读取；损坏文件须由用户显式恢复后才能写入。
    """
    try:data=read(Path(path))
    except FileNotFoundError:return {}
    except (OSError,ValueError,UnicodeError):
        raise ConfigError('项目设置文件 ui_settings.json 无法读取，已取消保存。'
                          '请保留原文件，检查访问权限、UTF-8 编码和 JSON 对象格式后重试。') from None
    if not isinstance(data,dict):
        raise ConfigError('项目设置文件 ui_settings.json 顶层必须是 JSON 对象，已取消保存。'
                          '请保留原文件，修复格式后重试。')
    return data

def save_prefs(project,data):
    """写 ui_settings.json：项目目录被移走、改名或删除后，不得因为写设置把它重新建出来。"""
    if not Path(project).is_dir():raise ConfigError('项目目录不存在或已被移动：'+str(project)+'。本次设置没有保存。')
    save(file(project),data)

def put(project,key,value):
    path=file(project)
    with access():
        data=_read_for_write(path)
        if data.get(key)!=value:
            data[key]=value;save_prefs(project,data)
    return data.get(key)

def unattended_label(text,model):
    """无人值守勾选框的统一写法：括号里写明当前实际使用的模型／引擎。

    以前各页把「本地 ComfyUI」写死在文案里，用户换过生图模型后勾选框仍在说本地，
    看不出点下去会跑哪个模型。四个页面统一用这一个函数拼装，口径一致。

    第 35 期第 3 条：按钮上那四个字「无人值守」撤掉，各页传进来的都是「自动补XX」。
    """
    model=str(model or '').strip()
    return text+'（'+model+'）' if model else text


def auto_review(project):
    """无人值守自动验收：视频下载且技术质检通过后，直接标记为已验收。"""
    return get(project,'auto_review',False) is True

def set_auto_review(project,value):
    return put(project,'auto_review',True if value else False) is True

def auto_adopt(project):
    """无人值守自动采用：agent 产出的新分镜 JSON 一出现就采用并推进后续流程。"""
    return get(project,'auto_adopt',False) is True

def set_auto_adopt(project,value):
    return put(project,'auto_adopt',True if value else False) is True

def auto_edit(project):
    """无人值守自动粗剪：本集全部镜头验收通过后自动拼接整集，不需要人工点按钮。"""
    return get(project,'auto_edit',False) is True

def set_auto_edit(project,value):
    return put(project,'auto_edit',True if value else False) is True

def auto_submit(project):
    """无人值守自动提交：云端批量提交不再逐次弹确认框，仅在不超剩余预算时直接提交。"""
    return get(project,'auto_submit',False) is True

def set_auto_submit(project,value):
    return put(project,'auto_submit',True if value else False) is True

def auto_keyframe(project):
    """无人值守自动补首帧：缺首帧的镜头按「首帧制作」窗口当前保存的模型自动排队生成（不弹窗）。"""
    return get(project,'auto_keyframe',False) is True

def set_auto_keyframe(project,value):
    return put(project,'auto_keyframe',True if value else False) is True

def auto_asset(project):
    """无人值守自动补资产：缺图的资产按「资产图片制作」窗口当前保存的生图模型自动排队生成（不弹窗）。"""
    return get(project,'auto_asset',False) is True

def set_auto_asset(project,value):
    return put(project,'auto_asset',True if value else False) is True

def auto_video(project):
    """无人值守自动补视频：当前分镜缺视频的镜头由本地 ComfyUI 依次提交并自动取回（免费后端，不弹窗）。"""
    return get(project,'auto_video',False) is True

def set_auto_video(project,value):
    return put(project,'auto_video',True if value else False) is True

def auto_previs(project):
    """无人值守自动补白模：复杂动作镜头交给当前调用的制作引擎自动出白模；简单镜头跳过、中等镜头仍需线上入口人工制作。"""
    return get(project,'auto_previs',False) is True

def set_auto_previs(project,value):
    return put(project,'auto_previs',True if value else False) is True

def auto_final(project):
    """无人值守自动生成定稿：当前分镜引用的资产都导入后自动定稿，工作稿移入回收站（可恢复）。"""
    return get(project,'auto_final',False) is True

def set_auto_final(project,value):
    return put(project,'auto_final',True if value else False) is True

def auto_handoff(project):
    """无人值守自动整理交接包：整集验收通过后自动生成剪映素材交接包（只复制本地成片，不调用云端）。"""
    return get(project,'auto_handoff',False) is True

def set_auto_handoff(project,value):
    return put(project,'auto_handoff',True if value else False) is True
