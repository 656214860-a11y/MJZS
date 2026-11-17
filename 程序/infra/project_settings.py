"""项目级开关（ui_settings.json）的统一读写入口，供无人值守/自动流程复用。

只保存「助手行为」类开关，不保存分镜采用列表等业务数据；沿用同一份 ui_settings.json，
写入前先读回已有内容，避免覆盖其他模块的键。
"""
from pathlib import Path
from agent.core import read,save,read_json
from agent.publication import access

DEFAULTS={'auto_review':False,'auto_adopt':False,'auto_edit':False,'auto_submit':False,'auto_keyframe':False,'auto_asset':False,'auto_video':False,'auto_previs':False,'auto_final':False,'auto_handoff':False}

def file(project):return Path(project)/'ui_settings.json'

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
    """put 的严格读取：文件不存在→空；读失败→原文件改名 ``.corrupt`` 保留，再按空处理。

    与 ``load()`` 的分工同 ``account_store._load_write``：读路径读不出就当开关全关；
    写路径读不出却整份覆盖，会把用户刚改的其它开关全部抹掉。坏文件先留证再写。
    """
    target=Path(path)
    if not target.is_file():return {}
    try:data=read(target)
    except FileNotFoundError:return {}
    except (OSError,ValueError,UnicodeError):
        try:target.replace(target.with_name(target.name+'.corrupt'))
        except OSError:pass
        return {}
    return data if isinstance(data,dict) else {}

def put(project,key,value):
    path=file(project)
    with access():
        data=_read_for_write(path)
        if data.get(key)!=value:
            data[key]=value;save(path,data)
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
