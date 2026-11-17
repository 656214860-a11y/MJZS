# -*- coding: utf-8 -*-
"""Fixed, prominent navigation for both video workspaces."""
from pathlib import Path
from tkinter import ttk
from file_cache import read_json as read_cached_json
from ui_tokens import COLORS, SPACING
from ui_widgets import SecondaryButton
import contract.pet_bus as pet_bus


def read_json(path):
    """读一份 JSON；读不到或不是对象都当空表——这一页只做展示，绝不因为坏文件炸掉。"""
    try:
        data=read_cached_json(path)
    except (OSError,ValueError):
        return {}
    return data if isinstance(data,dict) else {}


def storyboard_facts(project):
    """(份数, 镜头数)：已采用的分镜。一份都没有、文件缺失或读坏都当 0。"""
    try:
        from storyboard_selection import adopted
        files=adopted(project)
    except Exception:
        return 0,0
    shots=0
    for path in files:
        shots+=len(read_json(path).get('shots') or [])
    return len(files),shots


def frame_facts(source):
    """(就绪镜头数, 总镜头数)：这份分镜里已经有好首帧的镜头。"""
    if not source:
        return 0,0
    from contract.storyboard_paths import media_root
    source=Path(source)
    media=media_root(source)
    shots=[shot for shot in (read_json(source).get('shots') or []) if isinstance(shot,dict)]
    ready=0
    for shot in shots:
        name=str(shot.get('frame') or '')
        if not name or shot.get('frame_deleted'):
            continue
        try:
            path=(media/name).resolve()
        except OSError:
            continue
        if path.is_file():
            ready+=1
    return ready,len(shots)


def cloud_workspace(project):
    """线上视频任务目录：偏好里记住的那个；否则最近改过的那一个；都没有返回 None。"""
    project=Path(project)
    saved=read_json(project/'ui_settings.json').get('cloud_video_workspace')
    if saved and (project/saved/'config.json').is_file():
        return project/saved
    found=[path for path in (project/'cloud_video').glob('*/config.json') if path.is_file()]
    if not found:
        return None
    try:
        return max(found,key=lambda path:path.stat().st_mtime).parent
    except OSError:
        return found[0].parent


def cloud_facts(project):
    """(服务商, 模型)：线上这一路现在会用哪一套；没配好返回 ('','')。"""
    folder=cloud_workspace(project)
    if folder is None:
        return '',''
    config=read_json(folder/'config.json')
    model=str(config.get('model') or '')
    if not model:
        return '',''
    from cloud_video_service import PROVIDERS, provider_label
    return provider_label(config, PROVIDERS),model


def local_model(project):
    """本地这一路现在会用哪个模型（config.json 里 local_video 那个工作流）。"""
    from local_video import model_name
    return model_name(read_json(Path(project)/'config.json'))


def confirm_rows(desktop,project=None):
    """「开工前先确认」的几行：(标签, 说明)。

    第 26 期第 3 条：还没选生成方式时不需要分镜，但「分镜有几份、首帧够不够、两种方式各用哪个
    模型」这些本来要进了工作台才知道——先摆在这里，选定方式进去之后就不用再翻回来问。
    读文件一律按「读不到就照实说」处理，不抛。
    """
    project=Path(project or desktop.root)
    files,shots=storyboard_facts(project)
    try:
        source=desktop.current_frame_json()
    except Exception:
        source=None
    ready,total=frame_facts(source)
    provider,model=cloud_facts(project)
    return [
        ('分镜','已采用 %d 份，共 %d 镜'%(files,shots) if files else
         '尚未采用分镜；本页先挑生成方式，采用分镜在'+pet_bus.stage_step('storyboard')),
        ('首帧','当前分镜已就绪 %d / %d 镜'%(ready,total) if total else '当前分镜没有镜头'),
        ('本地模型',local_model(project)+'（本机 ComfyUI，免费）'),
        ('线上模型',(provider+' · '+model) if model else '尚未配置；在「阶段配置」→「接口」里配'),
    ]


def show_back(desktop):
    from ui_icons import IconLoader
    box=getattr(desktop,'video_back',None)
    if box is None:
        box=ttk.Frame(desktop.title_row,width=SPACING['sm'] * 10,height=SPACING['sm'] * 7)
        box.pack_propagate(False)
        # R3060：返回箭头换 Fluent PNG（assets/nav/back.png），缺失时退回手绘 return_arrow。
        icon=IconLoader.nav_icon(desktop.win,'back') or IconLoader.return_arrow(box,color=COLORS['primary'])
        # 返回属于次要动作；主题色箭头在正常和浅色悬停背景上均可读。
        button=SecondaryButton(box,text='返回生成方式',image=icon,
            padding=(SPACING['sm'],SPACING['xs']),cursor='hand2',takefocus=True,
            command=lambda:desktop.safe(lambda:desktop.show_stage('video',video_mode='choose')))
        button.image=icon
        button.pack(fill='both',expand=True)
        desktop.video_back=box
    # R2946/R2950 期页标题搬进侧栏顶行，title_row 里只剩用量块（左）与状态/模型（右）；
    # 返回钮仍占标题行最左，before 锚到同 master 的 usage_indicator（原 before=desktop.title 跨父级报 TclError）。
    box.pack(side='left',before=desktop.usage_indicator,padx=(SPACING['none'],SPACING['md']),anchor='center')


def hide_back(desktop):
    box=getattr(desktop,'video_back',None)
    if box is not None:box.pack_forget()
