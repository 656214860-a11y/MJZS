"""Offline screenplay preparation and validated, isolated episode imports."""
import json
import re
import uuid
from pathlib import Path
from storyboard_paths import media_root
from agent.core import read,save
from episode_contract import duration_gap, edited_total, number, relative, validate_episode

STAGES=['Step 0 需求整理','Step 1 全局大纲','Step 2 分集规划','Step 3 分镜初稿','Step 4 剧本精修']

def episode_dir(root):
    cfg=read(Path(root)/'config.json')
    if not isinstance(cfg,dict):cfg={}
    return Path(cfg.get('episode_dir',Path(root)/'episode')).resolve()

def _project_title(root):
    """Return the project name for the screenplay task brief, avoiding hardcoded titles."""
    try:
        cfg = read(Path(root) / "config.json")
        ep_file = cfg.get("episode_file") or (episode_dir(root) / "episode.json")
        ep = read(ep_file)
        title = ep.get("title") or ep.get("episode_id")
        if title:
            return str(title).strip()
    except (OSError, ValueError):
        pass
    name = Path(root).name
    return re.sub(r"_\d{8}_\d{6}(_\d+)?$", "", name)

def prepare(root,brief,stage,target,*,publish=None):
    """准备剧本工作区描述；用户可见成果只能由 L3 注入发布器发布。"""
    root=Path(root)
    if stage not in STAGES:raise ValueError('请选择有效编剧阶段')
    if not brief.strip():raise ValueError('请填写创意或剧本需求')
    target=int(target)
    if not 2<=target<=600:raise ValueError('单集目标时长须为2–600秒')
    if not callable(publish):
        raise TypeError('剧本准备工作区需要由 L3 注入发布器。')
    title=_project_title(root)
    folder_name='brief_'+uuid.uuid4().hex[:10]
    skill=Path(__file__).resolve().parent/'skills/01 剧本准备SKILL/影视剧本写作技能/SKILL.md'
    if not skill.is_file():raise ValueError('缺少随包编剧技能')
    asset_file=episode_dir(root)/'assets.json'
    assets=read(asset_file) if asset_file.exists() else {}
    artifacts=[{'name': '共用技能位置.txt', 'data': str(skill).encode('utf-8')}]
    for index,asset in enumerate(assets.values()):
        if not isinstance(asset,dict) or not asset.get('image'):continue
        rel=relative(asset['image']);p=(episode_dir(root)/rel).resolve()
        if p.is_relative_to(episode_dir(root)) and p.is_file() and p.suffix.lower() in ('.png','.jpg','.jpeg','.webp'):
            newrel=Path('assets')/f'reference_{index:03}{p.suffix.lower()}'
            artifacts.append({'name': newrel.as_posix(), 'source': p})
            asset['image']=newrel.as_posix()
    task=f'''# 《{title}》编剧任务书

当前阶段：{stage}
单集目标：{target}秒。这是时长目标，不是生成授权。

## 用户需求
{brief.strip()}

## 执行说明
先读取同目录SKILL.md，按所选阶段工作。已有确认的前置文档可复用；若缺少，先列出缺项，不虚构已确认内容。
风格与角色以项目 01剧本准备 目录下已有的《项目设定》《角色设定》等文档为准；若项目尚无设定，默认日常搞笑 3D 动画、低成本、固定机位和简单动作。
无Blender，低成本，固定机位和简单动作。不得因技能措辞而强行加入复杂运镜、大场面或长篇对白。
未经要求不覆盖已有试播片，不查询第3镜，不调用图片、视频或付费模型API。

## 交付
先输出可审阅的剧本文档。进入分镜阶段且剧本方向确认后，再输出严格JSON，结构参照episode_template.json。
角色和场景尽量复用assets.json中的ID；新增资产须另行登记。
每镜2–15整数秒，dialogue使用本镜内相对秒数；台词不重叠，speaker必须在本镜characters中。
首帧路径是frames/SH001.png等相对PNG路径；尚未生成时保留路径，不伪造文件。
只写本镜实际出场的人物。禁止把手机屏幕小字作为关键证据。结尾优先喜剧笑点，不强制悬念黑屏。
JSON仅为制作计划，不自动提交视频。
'''
    template={'episode_id':'EP002','title':'待填写','duration':10,'shots':[{'id':'SH001','title':'开场','duration':10,
        'characters':['CHAR_001'],'location':'LOC_001','frame':'frames/SH001.png','video_prompt':'填写本镜画面与对白要求',
        'dialogue':[{'start':1,'end':3,'speaker':'CHAR_001','text':'填写实际台词'}],'post_overlay':None}]}
    artifacts.extend((
        {'name': 'assets.json', 'data': json.dumps(assets, ensure_ascii=False, indent=2).encode('utf-8')},
        {'name': '编剧任务书.md', 'data': task.encode('utf-8')},
        {'name': 'episode_template.json', 'data': json.dumps(template, ensure_ascii=False, indent=2).encode('utf-8')},
    ))
    return publish(root, folder_name, artifacts)

def import_project(root,json_file):
    """Create a data-only project; reuse the one installed application and skills."""
    from projects import Projects
    app=Path(__file__).resolve().parent
    source=Path(json_file).resolve()
    ep=read(source)
    own_assets=source.parent/'assets.json'
    assets=read(own_assets) if own_assets.exists() else None
    report=validate_episode(ep,media_root(source),assets)
    target=Projects(app).create(ep.get('title') or source.stem,source=source)
    save(target/'import_report.json',report)
    return target,report
