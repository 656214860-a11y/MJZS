"""Project-scoped engine profiles for the white-model production entry."""
import app_logging
import copy
import os
import re
import shutil
from pathlib import Path
from tkinter import ttk
import tkinter as tk
from agent.core import save
from file_cache import read_json
import skill_registry
from script_contract import PRODUCTION_LOCK_DEFINITIONS, STAGE_LOCK_REQUIREMENTS, lock_stage
from workflow_context_budget import REQUEST_CONTEXT_MAX_CHARS
from ui_dialogs import FileDialog
from ui_widgets import BaseDialog, Card, PrimaryButton, SecondaryButton, notify
from ui_widgets import LineInput, TextArea
from ui_tokens import SPACING

ENGINES={'codex':'ChatGPT / Codex','qwen':'Qwen Code（阿里云）','claude':'Claude Code','claude-desktop-app':'Claude Desktop','desktop-app':'自定义桌面应用','opencode':'opencode CLI（自动放行权限）'}
FLOWS={'writing':'剧本创作','storyboard':'初步分镜','assets':'资产图片制作','frames':'批量首帧','previs':'白模预演','video_prompt':'视频提示词','audio':'配音与字幕'}
DEFAULT_SKILLS={'writing':'coconah-ai-short-drama-agent-skill','storyboard':'short-drama-storyboard','assets':'.system/imagegen','frames':'.system/imagegen','previs':'create-blender-story-video','video_prompt':'short-drama-storyboard','audio':''}
SKILL_PRESETS=[('万能剧本工作流','coconah-ai-short-drama-agent-skill'),('鲸剧工作流','jingju-skills'),
               ('Drama 分镜','short-drama-storyboard'),('Blender 白模','create-blender-story-video'),
               ('图像生成','.system/imagegen'),('分镜制图提示词','storyboard-image-prompts'),
               ('导演分镜','cinematic-director'),('中文逐镜分镜','video-storyboard-gen')]
SKILL_DETAILS={
    'short-drama-storyboard':'适合短剧：戏剧职责、轴线、站位、视线和持物连续性。',
    'jingju-skills':'适合漫剧完整流程：剧本、角色一致性、分镜和图片／视频提示词。',
    'cinematic-director':'适合叙事与人物调度：剧情节拍、动作起止、镜头动机和连续性。',
    'video-storyboard-gen':'适合中文逐镜拆分：时间分配、镜头表、声音和中文视频提示词。',
}
FLOW_SKILLS={
    'writing':('coconah-ai-short-drama-agent-skill','jingju-skills'),
    'storyboard':('short-drama-storyboard','jingju-skills','cinematic-director','video-storyboard-gen'),
    'assets':('.system/imagegen',),
    'frames':('.system/imagegen',),
    'previs':('create-blender-story-video',),
    'video_prompt':('short-drama-storyboard','jingju-skills','cinematic-director','video-storyboard-gen'),
    'audio':(),
}
STAGE_CONFIG_STAGES={'writing':'script','storyboard':'storyboard','assets':'assets','frames':'keyframe',
                     'previs':'previs','video_prompt':'video','audio':'audio'}
# 总控预设是受控登记，不从外部包 frontmatter 推导执行字段。R1433 起唯一来源是
# skills/00全流程SKILL/总控.json（MASTER_MANIFEST）；下面这份只作清单缺失／损坏时的出厂兜底。
BUILTIN_WORKFLOW_PRESETS={'AIGC全流程': {
    'package': 'skills/00全流程SKILL/AIGC创作全流程/short-drama-director/SKILL.md',
    'stage_skills': {'script':['pipeline-script-preparation'], 'script_structure':['pipeline-script-structure'],
        'storyboard':['pipeline-storyboard-draft'], 'assets':['pipeline-assets'], 'continuity':['pipeline-continuity'],
        'final':['pipeline-storyboard-final'], 'keyframe':['pipeline-keyframe'], 'previs':['pipeline-previs'],
        'video':['pipeline-video-generation'], 'audio':['pipeline-audio-subtitle'], 'edit':['pipeline-editing'],
        'delivery':['pipeline-delivery']},
    'locks': list(PRODUCTION_LOCK_DEFINITIONS),
}}
MASTER_MANIFEST=Path(__file__).resolve().parent/'skills'/'00全流程SKILL'/'总控.json'
# 兼容既有调用方与测试的 patch.dict：对象身份不变，只在清单文件变化时原地刷新。
WORKFLOW_PRESETS={}
MASTER_MANIFEST_PROBLEMS=[]
_MASTER_MANIFEST_STAMP={'value': object()}


def _manifest_presets(data):
    """把总控清单转成预设表；锁键换成契约定义，未知键与非法项记为问题而不是静默丢弃。"""
    problems=[]
    rows=data.get('presets') if isinstance(data,dict) else None
    if not isinstance(rows,dict) or not rows:
        return {},['总控清单缺少 presets']
    definitions={item['key']:item for item in PRODUCTION_LOCK_DEFINITIONS}
    out={}
    for name,row in rows.items():
        if not isinstance(row,dict) or not str(row.get('package') or '').strip():
            problems.append('总控「%s」缺少 package' % name);continue
        stages=row.get('stage_skills')
        if not isinstance(stages,dict):
            problems.append('总控「%s」的 stage_skills 不是表' % name);continue
        keys=row.get('locks')
        keys=list(definitions) if keys is None else [str(key) for key in keys]
        unknown=[key for key in keys if key not in definitions]
        if unknown:problems.append('总控「%s」有未登记的制作锁：%s' % (name,'、'.join(unknown)))
        out[str(name)]={'package':str(row['package']),
                        'stage_skills':{str(stage):[str(item) for item in (items or ())]
                                        for stage,items in stages.items()},
                        'locks':[definitions[key] for key in keys if key in definitions]}
    return out,problems


def refresh_workflow_presets(force=False):
    """按总控清单刷新 WORKFLOW_PRESETS；文件没变就什么都不做。返回当前预设表。"""
    try:
        stat=MASTER_MANIFEST.stat();stamp=(stat.st_mtime_ns,stat.st_size)
    except OSError:
        stamp=None
    if not force and stamp==_MASTER_MANIFEST_STAMP['value']:
        return WORKFLOW_PRESETS
    _MASTER_MANIFEST_STAMP['value']=stamp
    presets,problems=({},['总控清单不存在：%s' % MASTER_MANIFEST]) if stamp is None else ({},[])
    if stamp is not None:
        try:
            data=read_json(MASTER_MANIFEST)
        except (OSError,UnicodeError,ValueError) as exc:
            problems=['总控清单读不出：%s' % exc]
        else:
            presets,problems=_manifest_presets(data)
    if not presets:
        presets=copy.deepcopy(BUILTIN_WORKFLOW_PRESETS)
        problems.append('已改用出厂内置总控')
    WORKFLOW_PRESETS.clear();WORKFLOW_PRESETS.update(presets)
    MASTER_MANIFEST_PROBLEMS[:]=problems
    return WORKFLOW_PRESETS


refresh_workflow_presets(force=True)
_DESKTOP_INSTALLATION_CACHE={}

# 预设 SKILL 可以覆盖创作风格，不能跨越当前工作阶段。该契约在运行时总是附在
# SKILL 之后，因而比通用工作流里的“可做分镜／资产”等能力说明优先。
_STAGE_OUTPUT_CONTRACTS={
    'writing': ('\n\n【剧本准备阶段输出契约（最高优先级）】\n'
                '先问清楚，再创作：用户未提供故事大体环境和小说/漫剧类型时，必须先问，不能直接写。'
                '按四阶段输出：①项目设定 → ②剧本大纲 → ③角色卡 → ④自然剧本。'
                '每个关键阶段都必须用户确认，不能自动跳到下一阶段；每次只输出当前阶段一个文件，末尾“待确认”。'
                '项目设定和角色卡存入规范的项目设定目录，剧本大纲存入项目大纲目录；前三项仅供用户审阅参考，不进入 02 结构剧本的输入。'
                '角色卡标明“人物设定”，同一路径更新时保留已确认设定。'
                '本阶段唯一正式交付物是完整自然语言剧本正文（场景/动作/人物目标/冲突/对白/悬念），存入规范的项目剧本目录；'
                '02 结构剧本的唯一来源仍是最终自然剧本，character_manifest 仍由 02 从自然剧本提取。'
                'script_raw.md 仅为内部工作稿；正式交付以既有规范路径为准，不越级输出分镜及以后阶段。'),
    'script_structure': ('\n\n【剧本整理阶段输出契约（最高优先级）】\n'
                         '本阶段核心任务是整理剧本要素：从自然语言原稿提取并校验人物、场景、道具、事件、冲突、台词与分场关系，生成可追溯的结构剧本。\n'
                         '不得重写或替换自然语言原稿，不得做核心人物切镜头、镜头三元组、镜头拆分、分镜 JSON、首帧或媒体提示词；这些只属于“03初步分镜”。'),
    'storyboard': ('\n\n【初步分镜阶段输出契约（最高优先级）】\n'
                   '本阶段只以已确认的结构剧本为来源制作分镜初稿：围绕核心人物的目标、动作与情绪变化切镜头；每镜明确镜头三元组“核心人物／主体—可见动作—景别机位与运镜”，并按动作闭合点拆分镜头。\n'
                   '不得重新整理角色、场景、道具档案或重写结构剧本。输出的分镜初稿记录来源剧本、人物／场景／道具编号、镜头编号、时长、动作起止、对白和连续性约束；批次划分与最终锁定属于第 07 阶段“分镜定稿”，本阶段不做。'),
}


def stage_output_contract(stage):
    """返回不可被通用 SKILL 越过的当前阶段交付边界。"""
    return _STAGE_OUTPUT_CONTRACTS.get(str(stage or ''), '')

SKILL_ALIASES={'coconah-ai-short-drama-agent-skill':'screenplay','.system/imagegen':'imagegen'}
BUNDLED_SKILLS=Path(__file__).resolve().parent/'skills'


def _bundled_skill(folder):
    return BUNDLED_SKILLS/SKILL_ALIASES.get(folder,folder)/'SKILL.md'


def preset_skill(folder):
    return _bundled_skill(folder)


_PRESET_PATHS={}


def _preset_paths():
    """预解析程序内置预设 SKILL.md，供路径反查复用。"""
    cached=_PRESET_PATHS.get('bundled')
    if cached is None:
        cached=[(folder,_bundled_skill(folder).resolve()) for _,folder in SKILL_PRESETS]
        _PRESET_PATHS.clear();_PRESET_PATHS['bundled']=cached
    return cached


def preset_folder(skill):
    if not skill:return None
    path=Path(skill).resolve()
    for folder,bundled in _preset_paths():
        if path==bundled:return folder
    return None

def preset_label(skill):
    if not skill:return '不使用 Skill'
    known=preset_folder(skill)
    for label,folder in SKILL_PRESETS:
        if folder==known:return label
    return '自定义 Skill'


def agent_label(profile, stage, engine, function=None):
    """Stable display label shared by the settings dialog and Agent selector."""
    model=profile.get('model','').strip() or ENGINES[engine]
    names=[]
    for path in skills_of(profile):
        name=preset_label(path)
        if name=='自定义 Skill':name=Path(path).parent.name
        if name not in names:names.append(name)
    skill='、'.join(names) or '内置要求'
    return '.'.join((model,function or FLOWS[stage],skill.replace(' ','')))


def skills_of(profile):
    """这一档勾了哪几份 SKILL（第 59 期第 5 条：一处可以勾不止一份）。

    `skills` 是权威（列表）；老配置只有单个 `skill`，就当成「只勾了这一份」。
    """
    if not isinstance(profile,dict):return []
    items=profile.get('skills')
    out=[]
    if isinstance(items,(list,tuple)):
        for value in items:
            text=str(value or '').strip()
            if text and text not in out:out.append(text)
        return out
    single=str(profile.get('skill') or '').strip()
    return [single] if single else []


def set_skills(profile,paths):
    """把勾选写回这一档：`skills` 是完整清单，`skill` 跟着记第一份（老读者照旧看得出主 SKILL）。"""
    kept=[]
    for value in paths or ():
        text=str(value or '').strip()
        if text and text not in kept:kept.append(text)
    profile['skills']=kept
    profile['skill']=kept[0] if kept else ''
    return kept


def skills_for_stage(profile,stage,name='codex'):
    """这一档存下来的 SKILL 归一到「这一步能用的那几份」（第 59 期第 5 条）。

    - 列表键 skills 是权威；老配置只有单个 skill，就当成一张只有一项的清单；
    - 不适用于这一流程的预设剔掉；老配置里那份不适用时退回这一步的默认那一份
      （与第 36 期「换到别的流程要退回默认」的老规矩一致）。
    """
    listed=isinstance(profile.get('skills'),(list,tuple))
    picked=[]
    for item in skills_of(profile):
        folder=preset_folder(item)
        if folder and folder not in FLOW_SKILLS[stage]:
            if not listed:
                return skills_of(defaults(stage)['profiles'][name])
            continue
        if item not in picked:picked.append(item)
    return picked

def settings_path(project):
    return Path(project)/'工作流任务'/'工作流调用设置.json'


def shared_qwen_model(data):
    if 'qwen' in data.get('shared_models',{}):return data['shared_models']['qwen']
    flows=data.get('flows',{})
    for stage in ('storyboard',*FLOWS):
        candidate=flows.get(stage,{}).get('profiles',{}).get('qwen',{}).get('model','')
        if candidate:return candidate
    from qwen_setup import load as qwen_api
    return qwen_api().get('model','')


def sync_qwen_model(project,model):
    model=str(model).strip()
    if model and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}',model):
        raise ValueError('Qwen 模型 ID 格式不正确')
    target=settings_path(project)
    data={}
    if target.is_file():
        try:
            loaded=read_json(target)
            if isinstance(loaded,dict):data=loaded
        except (OSError,ValueError):pass
    data.setdefault('shared_models',{})['qwen']=model
    for stage in data.get('flows',{}).values():
        if 'qwen' in stage.get('profiles',{}):stage['profiles']['qwen']['model']=model
    save(target,data)

def defaults(stage='previs'):
    if stage not in FLOWS:raise ValueError('未知的工作流入口')
    skill_file=preset_skill(DEFAULT_SKILLS[stage])
    skill=str(skill_file) if skill_file.is_file() else ''
    return {'engine':'codex','profiles':{name:{'program':'','model':'','skill':skill,
                                               'skills':[skill] if skill else [],
                                               'instructions':''} for name in ENGINES}}

def load(project,stage='previs'):
    result=defaults(stage);path=settings_path(project)
    if path.is_file():
        try:
            data=read_json(path)
        except (OSError,ValueError):
            data={}
        if not isinstance(data,dict):raise ValueError('工作流调用设置格式错误')
        value=data.get('flows',{}).get(stage,{})
        engine=value.get('engine','codex')
        if engine not in ENGINES:raise ValueError('未知的制作引擎')
        result['engine']=engine
        for name in ENGINES:
            profile=value.get('profiles',{}).get(name,{})
            stored=result['profiles'][name]
            for key in ('program','model','instructions'):
                if key in profile:stored[key]=str(profile[key])
            # 第 59 期第 5 条：勾选是一张清单；这一档根本没存过 SKILL 就留着 defaults 那一份，
            # 存过就按存的来（空表＝这一流程不挂 SKILL）。
            if isinstance(profile.get('skills'),(list,tuple)) or 'skill' in profile:
                set_skills(stored,skills_for_stage(profile,stage,name))
    else:data={}
    result['profiles']['qwen']['model']=shared_qwen_model(data)
    return result

def validate_profile(profile):
    result={k:str(profile.get(k,'')).strip() for k in ('program','model','skill','instructions')}
    if result['program']:
        path=Path(result['program']).expanduser()
        if not path.is_absolute() or path.suffix.lower()!='.exe' or not path.is_file():
            raise ValueError('请选择已安装的命令行 .exe 程序，或留空自动查找')
        result['program']=str(path.resolve())
    if result['model'] and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}',result['model']):
        raise ValueError('模型 ID 格式不正确；留空可使用引擎默认模型')
    # 第 59 期第 5 条：一处可以勾几份 SKILL，逐份按同一把尺子验。
    paths=[]
    for value in skills_of(profile):
        path=Path(value).expanduser()
        if not path.is_absolute() or not path.is_file() or path.name.lower()!='skill.md':
            raise ValueError('请选择有效的 SKILL.md 文件；留空时仅按此流程的内置要求执行')
        resolved=str(path.resolve())
        if resolved not in paths:paths.append(resolved)
    set_skills(result,paths)
    return result

def validate_stage_profile(profile,stage):
    result=validate_profile(profile)
    for item in skills_of(result):
        known=preset_folder(item)
        if known and known not in FLOW_SKILLS[stage]:
            raise ValueError('所选常用 Skill 不适用于“'+FLOWS[stage]+'”，请选择本流程的 Skill 或自定义文件')
    return result

def stage_model(project,stage):
    """阶段配置 → 模型：这一步的 Agent 实际要用哪个大模型（第 62 期任务 3）。

    用户报的毛病：在「阶段配置 → 模型」里手选了 deepseek，跑起来调用的还是 Qwen 的
    qwen3.7-plus。根因是两个下拉框各存一份、谁也不管谁——`current()` 只读引擎自己那一栏
    （`工作流调用设置.json` 的 profiles[engine]['model']），阶段配置写进 `skill_config.json`
    的那一格没人读。于是那一格看起来像"选了模型"，其实一点作用都没有。

    现在这一格说了算：池里的一条换成引擎认的模型名，连它的接口（根地址／协议／密钥名）
    一起交出去，Qwen Code 的 OpenAI 兼容模式照它发请求——选了 deepseek 就真的打到 deepseek。

    - 「自动」＝照旧按引擎自己那一栏走（默认行为一个字都不变）；
    - 生产模型（本地 ComfyUI／Seedream 这类）不是发给文本模型的 id，跳过；
    - 别的阶段的生产模型被预设套过来时同样跳过（stage_models.belongs_to_other_stage）；
    - 只有 Qwen Code 这一个引擎认自定义 OpenAI 兼容接口：它是项目中负责转发模型池 API
      的调用器（名称沿用历史设置，不代表请求一定发给 Qwen）。Codex 与 Claude 的模型由它们
      各自那一栏决定，硬塞一个别的服务商的模型名只会让窗口起不来。
    """
    try:
        import stage_config
        import stage_models
        import model_pool
        chosen=str(stage_config.get(project,STAGE_CONFIG_STAGES.get(stage,stage)).get('model') or '').strip()
    except Exception:
        return '',''
    if not chosen or chosen==model_pool.AUTO or model_pool.desktop_engine(chosen):
        return '',''
    # 生产模型（本地 ComfyUI／Seedream 这类）与「别的阶段的生产模型」都不是发给文本模型的 id：
    # 首帧那一格的下拉框里还并着几个 Agent 引擎的显示名，同样跳过。
    # 判据按「带项目的那一份 choices」算——不带项目时首帧只列得出两条静态的。
    try:
        choices=stage_models.production_choices(stage,project)
    except Exception:
        choices=()
    if any(chosen==value for value,_label in choices):
        return '',''
    if chosen in ENGINES.values():
        return '',''
    if stage_models.belongs_to_other_stage(stage,chosen):
        return '',''
    program=Path(__file__).resolve().parent
    item=model_pool.pool(program=program).get(chosen)
    if not item:
        return chosen,''                  # 用户自己填的 id：照原样交给引擎，接口用引擎那一栏
    if model_pool.call_mode(item, chosen) == 'Desktop':
        return '', ''
    api={'base_url':item['base_url'],'path':item['path'],'wire_api':item['wire_api'],
         'key_env':item['key_env']}
    return str(item['model'] or chosen),api


def effective_model(project,stage='previs'):
    """这一步真正会发出去的模型名（第 62 期任务 3）：阶段配置挑了就用它，否则按引擎那一栏。

    界面文案（比如分镜页那个「自动采用新文件（当前使用的模型）」）与自检都读这一处，
    不另算一遍——显示的和真发出去的必须是同一个名字。
    """
    # 不能只读保存的默认引擎：阶段配置可能把默认 Codex 改成了模型池 API，
    # `current()` 才是三虎实际会启动的那一条路由。
    cfg=current(project,stage);engine=cfg['engine']
    if engine == 'desktop-app':
        return cfg['display_model']
    try:
        import stage_config
        import model_pool
        selected = str(stage_config.get(project, STAGE_CONFIG_STAGES.get(stage, stage)).get('model') or '').strip()
        if model_pool.desktop_engine(selected):
            return model_pool.label_of(selected, model_pool.pool(program=Path(__file__).resolve().parent))
    except Exception:
        app_logging.swallowed()
    model,api=stage_model(project,stage) if engine=='qwen' else ('','')
    if model:
        return model
    return str(cfg.get('model') or '').strip() or ENGINES[engine]


def _local_engine_for_selected_model(value, selected, item, stage):
    """已选 OpenAI/Anthropic 模型有本机 Agent 时，优先回到对应本机客户端。"""
    import model_pool
    engine = model_pool.desktop_engine(selected)
    if not engine:
        engine = {'GPT': 'codex', 'Anthropic': 'claude'}.get(
            model_pool.provider_name(selected, item), '')
    if not engine:
        return '', ''
    try:
        profile = validate_stage_profile(value['profiles'][engine], stage)
        return engine, find_program({'engine': engine, 'program': profile['program']})
    except (KeyError, ValueError):
        return '', ''


def desktop_route_notice(project, stage, selected, item=None):
    """用户刚选模型时按需说明是否会优先交给可用本机程序；只读且不写盘。"""
    import model_pool
    selected = str(selected or '').strip()
    if not selected or model_pool.desktop_engine(selected):
        return ''
    record = item if isinstance(item, dict) else \
        model_pool.pool(program=Path(__file__).resolve().parent).get(selected, {})
    engine = {'GPT': 'codex', 'Anthropic': 'claude'}.get(
        model_pool.provider_name(selected, record), '')
    if not engine:
        return ''
    try:
        value = load(project, stage)
        profile = validate_stage_profile(value['profiles'][engine], stage)
        find_program({'engine': engine, 'program': profile['program']})
    except Exception:
        return ''
    name = '本机 GPT 程序' if engine == 'codex' else '本机 Claude 程序'
    return '已检测到%s：运行时会优先由本机程序执行；若启动失败，将回落到所选 API。' % name


def current(project,stage='previs', *, direct_api=False, model_snapshot=None):
    value=load(project,stage);engine=value['engine']
    selected='';item={};local_program=''
    import stage_config
    import model_pool
    if model_snapshot is None:
        selected = str(stage_config.get(project, STAGE_CONFIG_STAGES.get(stage, stage)).get('model') or '').strip()
        item = model_pool.pool(program=Path(__file__).resolve().parent).get(selected, {})
    else:
        selected, item = model_snapshot
    explicit_engine = model_pool.desktop_engine(selected)
    if not explicit_engine and item and model_pool.call_mode(item, selected) == 'Desktop':
        explicit_engine = 'desktop-app'
    if explicit_engine:
        engine = explicit_engine
    else:
        local_engine, local_program = ('', '') if direct_api else _local_engine_for_selected_model(value, selected, item, stage)
        if local_engine:
            engine = local_engine
        elif item:
            # 模型池中的任意 API 模型都必须交给兼容调用器。此前仅 GPT／Anthropic
            # 会走这里，选 DeepSeek V4 Flash 时便错误沿用默认 Codex，导致三虎
            # 自动打开的是 Codex 而阶段按钮却显示 DeepSeek。
            engine = 'qwen'
    if direct_api:
        engine = 'qwen'
    profile=validate_stage_profile(value['profiles'][engine],stage)
    if engine == 'desktop-app':
        profile['program'] = str(item.get('program') or '').strip()
        profile['model'] = ''
    if explicit_engine and item.get('program'):
        if explicit_engine == 'codex':
            profile['desktop_program'] = item['program']
            profile['program'] = ''
            profile['model'] = ''
        else:
            profile['program'] = item['program']
    if local_program:
        # 本机 Codex/Claude 的可选模型集合由客户端登录态决定，不能把 API 模型 id 当 CLI 参数塞入。
        profile['program']=local_program
        profile['model']=''
        selected_model, selected_api = stage_model(project,stage)
        if selected_api:
            # 仅本机程序无法启动时交给启动器兜底；不把任务内容在后台悄悄重发。
            profile['api_fallback']={'model':selected_model,'api':selected_api,
                                     'profile':validate_stage_profile(value['profiles']['qwen'],stage)}
    # 阶段配置里挑了 API 模型就以它为准；qwen 是兼容 API 调用器，见 stage_model。
    model,api=(selected, {}) if direct_api else (stage_model(project,stage) if engine=='qwen' else ('',''))
    if model:profile['model']=model
    if api:profile['api']=api
    # 统筹投影不改变旧引擎档；仅在生成提示词时作为受控前缀读取。
    workflow = stage_config.current_workflow(project)
    locks = stage_config.workflow_lock(project)
    profile['project_created_at'] = stage_config.project_created_at(project)
    if locks:
        profile['workflow_lock'] = locks
    if stage == 'writing':
        profile['writer_style'] = stage_config.writer_style(project, 'script')
    name = str(workflow.get('name') or '').strip()
    preset = refresh_workflow_presets().get(name, {})
    if preset:
        # 总控门禁（master_skill.gate）凭这个名字判断项目是否处于总控模式。
        profile['workflow_name'] = name
        profile['workflow_skill_prompt'] = '按当前阶段需要，只读取总控 SKILL 中与本阶段交付相关的章节，不全文加载总控 SKILL 及无关 reference：' + str(preset['package'])
    try:
        import skill_registry
        reg = skill_registry.default_registry()
        profile['stage_skills'] = [str(reg.getById(item).path) for item in
                                  stage_config.get(project, STAGE_CONFIG_STAGES.get(stage, stage)).get('skills', ())
                                  if reg.getById(item) is not None]
    except Exception as exc:
        raise ValueError('阶段 SKILL 无法加载，请修复技能配置后重试：' + str(exc)) from exc
    display_model = (model_pool.label_of(selected, {selected: item}) if explicit_engine
                     else str(profile.get('model') or '').strip() or ENGINES[engine])
    return {'engine':engine, 'stage':stage, 'display_model':display_model, **profile}


def writer_style_summary(config, stage=None):
    """任务书可见摘要：只说明是否带了项目级编剧风格，不暴露风格正文。"""
    stage = stage if stage is not None else config.get('stage')
    if stage != 'writing' or not str(config.get('writer_style') or '').strip():
        return ''
    return '编剧风格：已启用本项目编剧风格（编剧角色创作并审核五阶门控）'


def writer_style_prompt(config, stage=None):
    """项目级编剧风格；首次与续发同源，只在剧本准备阶段注入，空风格不占请求。"""
    stage = stage if stage is not None else config.get('stage')
    style = str(config.get('writer_style') or '').strip() if stage == 'writing' else ''
    if not style:
        return ''
    return ('本项目编剧风格（编剧角色创作与审核五阶门控时优先遵守，不改变阶段交付物与单集时长）：' + chr(10)
            + style + chr(10))


_STORE_PACKAGE=re.compile(r'^(?P<head>.*\\WindowsApps\\)(?P<name>[^\\_]+)_[^\\_]+_(?P<arch>[^\\_]+)__(?P<publisher>[^\\]+)\\(?P<rest>.+)$',re.I)
_STORE_PACKAGES_KEY=r'Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages'


def current_store_program(program):
    """商店应用目录名带版本号，应用自动更新后已保存的路径即失效。
    WindowsApps 不可列目录，改从注册表的已装包清单找同名同发布者的现行版本。"""
    program=str(program or '')
    match=_STORE_PACKAGE.match(program)
    if not match or Path(program).is_file():return program
    prefix=(match['name']+'_').casefold();suffix=('_'+match['arch']+'__'+match['publisher']).casefold()
    from platform_tools import windows_registry
    winreg=windows_registry()
    if winreg is None:return program
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,_STORE_PACKAGES_KEY) as key:
            names=[];index=0
            while True:
                try:names.append(winreg.EnumKey(key,index))
                except OSError:break
                index+=1
    except OSError:return program
    def version(name):
        return tuple(int(part) for part in name[len(prefix):-len(suffix)].split('.') if part.isdigit())
    for name in sorted((n for n in names if n.casefold().startswith(prefix) and n.casefold().endswith(suffix)),key=version,reverse=True):
        candidate=Path(match['head']+name)/match['rest']
        if candidate.is_file():return str(candidate)
    return program


def store_package_program(package, relative):
    """按已安装的商店包定位程序：WindowsApps 不可列目录，只读注册表包清单，新版本优先。"""
    from platform_tools import windows_registry
    winreg=windows_registry()
    if winreg is None:return ''
    prefix=(str(package)+'_').casefold()
    def version(name):
        parts=name.split('_')
        return tuple(int(part) for part in (parts[1] if len(parts)>1 else '').split('.') if part.isdigit())
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,_STORE_PACKAGES_KEY) as key:
            names=[];index=0
            while True:
                try:names.append(winreg.EnumKey(key,index))
                except OSError:break
                index+=1
            for name in sorted((n for n in names if n.casefold().startswith(prefix)),key=version,reverse=True):
                root=''
                try:
                    with winreg.OpenKey(key,name) as package_key:
                        root=str(winreg.QueryValueEx(package_key,'PackageRootFolder')[0] or '')
                except OSError:
                    root=''
                if not root:
                    root=str(Path(os.environ.get('ProgramFiles') or r'C:\Program Files')/'WindowsApps'/name)
                candidate=Path(root)/relative
                if candidate.is_file():return str(candidate)
    except OSError:
        return ''
    return ''


def gui_claude_program(path):
    """路径是否 Claude Desktop 图形程序（商店版／Squirrel／Programs 安装），而非命令行 claude.exe。
    图形程序不接受 -p／--output-format，当作 CLI 调用只会得到「未返回有效 JSON」。"""
    text=str(path or '').replace('/','\\').lower()
    if not text.endswith('\\claude.exe'):return False
    return any(mark in text for mark in ('\\windowsapps\\','\\anthropicclaude\\','\\programs\\claude\\'))


GUI_CLAUDE_CLI_HINT=('所选程序是 Claude Desktop 图形界面，不是命令行（claude.exe）。'
                     '请在模型管理改用「Claude Desktop」条目（模型 ID claude-desktop-app），'
                     '或把本条的程序改为命令行版 claude.exe。')



def find_model_program(model, mode):
    """模型管理按当前名称和调用方式查询安装位置，不执行候选程序。"""
    import re
    name = re.sub(r'[\s_-]+', '-', str(model).strip().casefold())
    if not name or mode not in ('Desktop', 'CLI'):
        raise ValueError('请先填写本地应用的模型 ID 并选择 Desktop 或 CLI')
    if mode == 'CLI':
        aliases = {'claude-code': 'claude', 'claude-code-cli': 'claude',
                   'claude-desktop': 'claude', 'qwen-code': 'qwen', 'codex-cli': 'codex',
                   'opencode-cli': 'opencode'}
        engine = aliases.get(name, name)
        if engine in ('claude', 'codex', 'qwen', 'opencode'):
            return find_program({'engine': engine, 'program': ''})
        raise ValueError('未找到对应的受支持 CLI：' + str(model))
    if name in ('claude', 'claude-desktop', 'claude-desktop-app'):
        return find_program({'engine': 'claude-desktop-app', 'program': ''})
    aliases = {'chatgpt-desktop': 'codex', 'codex-desktop': 'codex',
               'google-gemini': 'gemini'}
    app = aliases.get(name, name)
    if re.fullmatch(r'(google-)?gemini(?:-[0-9.]+(?:-[a-z0-9]+)*)?', name):
        app = 'gemini'
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]*', app):
        raise ValueError('未找到对应桌面应用，请填写应用名或手动浏览安装路径')
    executable = app + '.exe'
    from platform_tools import windows_registry
    registry = windows_registry()
    if registry is not None:
        for hive in (registry.HKEY_CURRENT_USER, registry.HKEY_LOCAL_MACHINE):
            for branch in (r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths',
                           r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths'):
                try:
                    with registry.OpenKey(hive, branch + '\\' + executable) as key:
                        candidate = str(registry.QueryValueEx(key, '')[0]).strip('"')
                    if Path(candidate).is_file():
                        return candidate
                except OSError:
                    continue
    package = {'codex': 'OpenAI.Codex', 'chatgpt': 'OpenAI.ChatGPT'}.get(app)
    if package:
        for relative in (Path('app') / executable, Path(executable)):
            found = store_package_program(package, relative)
            if found:
                return found
    local = Path(os.environ.get('LOCALAPPDATA', ''))
    roots = [local / 'Programs', local, Path(os.environ.get('ProgramFiles', r'C:\Program Files')),
             Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'))]
    folders = [app, 'OpenAI/' + app] if app in ('codex', 'chatgpt') else [app]
    if app == 'gemini':
        folders.append('Google/Gemini')
    for root in roots:
        for folder in folders:
            candidate = root / folder / executable
            if candidate.is_file():
                return str(candidate)
    raise ValueError('未找到“%s”的 Desktop 安装程序；请确认已安装对应桌面应用，或点“浏览…”指定 .exe' % model)


def find_program(config):
    if config['program']:return current_store_program(config['program'])
    if config['engine'] not in ENGINES:
        raise ValueError('未知的本地调用引擎：' + str(config['engine']))
    if config['engine'] == 'desktop-app':
        raise ValueError('请在模型管理为此 Desktop 模型指定桌面程序路径')
    if config['engine'] == 'claude-desktop-app':
        local = Path(os.environ.get('LOCALAPPDATA', ''))
        candidates = [local/'AnthropicClaude/claude.exe', local/'Programs/Claude/Claude.exe']
        candidates.extend(sorted((local/'AnthropicClaude').glob('app-*/claude.exe'),
                                 key=lambda path: path.stat().st_mtime, reverse=True))
        for candidate in candidates:
            if candidate.is_file():return str(candidate)
        # 商店版（MSIX）装在 WindowsApps，目录名带版本号，只能经注册表包清单定位。
        store = store_package_program('Claude', Path('app')/'Claude.exe')
        if store:return store
        raise ValueError('未找到 Claude Desktop，请在模型管理选择其 .exe')
    if config['engine']=='qwen':
        from qwen_adapter import command
        return command(config)[0]
    if config['engine']=='opencode':
        found=shutil.which('opencode-cli.exe')
        if found:return found
        appdata=os.environ.get('APPDATA')
        if appdata:
            choices=list((Path(appdata)/'ai.opencode.desktop'/'cli').glob('*/opencode-cli.exe'))
            if choices:return str(max(choices,key=lambda p:p.stat().st_mtime))
        raise ValueError('未找到 OpenCode CLI（opencode-cli.exe），请安装后在“调用设置”选择其 .exe')
    engine=config['engine'];found=shutil.which(engine+'.exe')
    if found:return found
    if engine=='codex':
        choices=list((Path(os.environ.get('LOCALAPPDATA',''))/'OpenAI/Codex/bin').glob('*/codex.exe'))
        if choices:return str(max(choices,key=lambda p:p.stat().st_mtime))
    else:
        native=Path.home()/'.local/bin/claude.exe'
        if native.is_file():return str(native)
        # npm 的 PATH 入口是脚本；直接定位包内原生程序，不解释或执行包装脚本。
        shim=shutil.which('claude.cmd')
        prefixes=[Path(shim).parent] if shim else []
        appdata=os.environ.get('APPDATA')
        if appdata:prefixes.append(Path(appdata)/'npm')
        for prefix in prefixes:
            native=prefix/'node_modules/@anthropic-ai/claude-code/bin/claude.exe'
            if native.is_file():return str(native)
    raise ValueError('未找到 '+ENGINES[engine]+' 命令行程序，请安装并登录后在“调用设置”选择其 .exe')


def clear_desktop_installation_cache():
    """仅供本进程展示层刷新状态；不持久化探测结果。"""
    _DESKTOP_INSTALLATION_CACHE.clear()


def desktop_model_label(model_id, label):
    """桌面模型的展示标注：复用 find_program，失败和异常一律按未安装显示。"""
    import model_pool
    engine=model_pool.desktop_engine(model_id)
    if not engine:return str(label or '')
    configured=model_pool.pool(program=Path(__file__).resolve().parent).get(model_id, {}).get('program', '')
    if configured:
        return str(label or '')+('（未安装）' if not Path(current_store_program(configured)).is_file() else '')
    if engine not in _DESKTOP_INSTALLATION_CACHE:
        try:find_program({'engine':engine,'program':''})
        except Exception:_DESKTOP_INSTALLATION_CACHE[engine]=False
        else:_DESKTOP_INSTALLATION_CACHE[engine]=True
    return str(label or '')+('（未安装）' if not _DESKTOP_INSTALLATION_CACHE[engine] else '')

def validate_selected_skills(project, stage):
    """在解析前检查保留的选择，禁止把失效选择静默变成未勾选。"""
    import stage_config
    import skill_registry
    from file_cache import read_json
    target = stage_config.path(project)
    data = read_json(target)
    if target.exists() and not isinstance(data, dict):
        raise ValueError('SKILL 配置无法读取，已阻止发送，请重新确认阶段配置。')
    entry = (data or {}).get(STAGE_CONFIG_STAGES.get(stage, stage), {})
    if not isinstance(entry, dict) or not isinstance(entry.get('skills', []), (list, tuple)):
        raise ValueError('阶段 SKILL 配置格式无效，已阻止发送，请重新确认阶段配置。')
    registry = skill_registry.default_registry()
    for name in entry.get('skills') or ():
        if registry.getById(name) is None:
            raise ValueError(f'已勾选的 SKILL 未加载：{name}；已阻止发送，请重新确认阶段配置。')


def _reference_row(entry, reference, status, depth=1):
    """引用闭包里的一行：目标、类型、结果与深度（1＝直接引用，2＝引用文件里再出现）。"""
    row = {'kind': entry['kind'], 'status': status, 'target': entry['raw'], 'depth': depth}
    if reference is not None:
        row['path'] = str(reference)
    return row


def _nested_references(reference, body, seen, root):
    """引用文件里再出现的链接：只登记、不展开（明确不递归加载）。"""
    out = []
    for entry in skill_registry.reference_targets(body):
        relative = entry['path']
        if relative is None:
            out.append(_reference_row(entry, None, entry['kind'], 2))
            continue
        if relative.is_absolute():
            out.append(_reference_row(entry, relative, 'absolute', 2))
            continue
        target = (reference.parent / relative).resolve()
        if target in seen:
            status = 'cycle'
        elif not target.is_relative_to(root):
            status = 'outside'
        elif not target.is_file():
            status = 'missing'
        else:
            status = 'nested'
        out.append(_reference_row(entry, target, status, 2))
    return out


def _skill_blocks(path, *, strict):
    """走一遍技能正文与它的直接引用；返回 (正文, 元数据, 分块, 引用闭包)。

    闭包是「实际发生了什么」的唯一记录：inlined（已内联）、duplicate（重复）、
    outside（越界）、missing（缺失）、resource（图片／脚本等资源）、remote（外部地址）、
    anchor（纯锚点）、absolute（绝对路径），以及 depth=2 的嵌套项：nested（未展开）、
    cycle（回指已加载文件）、outside、missing。只加载直接引用，不递归。
    """
    path = Path(path).resolve()
    text = path.read_text(encoding='utf-8-sig')
    meta, content = skill_registry.parse(text, source=str(path))
    if strict and not content.strip():
        raise ValueError(f'已勾选的 SKILL 内容为空，已阻止发送：{path}')
    blocks = [(path, f'<!-- 来源: {path} -->\n{text}')]
    closure, seen = [], {path}
    root = skill_registry.default_root().resolve()
    for entry in skill_registry.reference_targets(text):
        relative = entry['path']
        if relative is None:
            closure.append(_reference_row(entry, None, entry['kind']))
            continue
        if relative.is_absolute():
            closure.append(_reference_row(entry, relative, 'absolute'))
            continue
        reference = (path.parent / relative).resolve()
        markdown = entry['kind'] == 'markdown'
        within_root = reference.is_relative_to(root)
        within_folder = reference.is_relative_to(path.parent)
        if markdown and strict and not (within_root or within_folder):
            closure.append(_reference_row(entry, reference, 'outside'))
            raise ValueError(f'SKILL 引用超出允许目录，已阻止发送：{reference}')
        if not markdown:
            closure.append(_reference_row(entry, reference, 'resource'))
            continue
        if not (within_root or (strict and within_folder)):
            closure.append(_reference_row(entry, reference, 'outside'))
            continue
        if reference in seen:
            closure.append(_reference_row(entry, reference, 'duplicate'))
            continue
        seen.add(reference)
        try:
            body = reference.read_text(encoding='utf-8-sig')
        except OSError as exc:
            closure.append(_reference_row(entry, reference, 'missing'))
            raise ValueError(f'SKILL 引用缺失，已阻止发送：{reference}（{exc}）') from exc
        blocks.append((reference, f'\n\n## 引用: {reference.name}\n{body}'))
        closure.append(_reference_row(entry, reference, 'inlined'))
        closure.extend(_nested_references(reference, body, seen, root))
    return text, meta, blocks, closure


def master_gate(config, stage=None, check_references=True):
    """总控门禁（见 master_skill 模块说明）：返回阻断原因，空串＝放行；手动与自动路径共用。"""
    name = str(config.get('workflow_name') or '').strip()
    if not name:
        return ''
    stage = lock_stage(stage if stage is not None else config.get('stage'))
    reasons = []
    from script_contract import stage_lock_requirements
    required_keys = stage_lock_requirements(stage, config.get('project_created_at'))
    if stage == 'script':
        required_keys = tuple(key for key in required_keys if key != 'delivery_format')
    if required_keys:
        # 剧本准备的制作锁由简报采集门禁负责，不能挡住收集制作锁的那段对话。
        preset = WORKFLOW_PRESETS.get(name, {})
        declared = {item['key']: item.get('label') or item['key'] for item in preset.get('locks') or ()}
        locks = config.get('workflow_lock') or {}
        missing = [declared[key] for key in required_keys
                   if key in declared and not str(locks.get(key) or '').strip()]
        if missing:
            reasons.append('本阶段必填制作锁未填：' + '、'.join(missing)
                           + '（在阶段配置的总控栏或 01 剧本准备发送框补齐）')
    config['workflow_lock_warnings'] = [item['label'] + '未选（旧项目兼容，不阻断）'
        for item in PRODUCTION_LOCK_DEFINITIONS if stage == 'script' and item.get('required_from')
        and item['key'] not in required_keys and not (config.get('workflow_lock') or {}).get(item['key'])]
    if check_references:
        for item in [*(config.get('stage_skills') or ()), *skills_of(config)]:
            if not item:
                continue
            try:
                _skill_blocks(item, strict=True)
            except (OSError, UnicodeError, ValueError) as exc:
                reasons.append(str(exc))
    if not reasons:
        return ''
    return '总控门禁已阻断：' + '；'.join(reasons)


def _inline_skill_report(path, *, cap=REQUEST_CONTEXT_MAX_CHARS, strict=False):
    """内联技能正文，并给出「实际加载了什么」的引用闭包，供请求快照留凭据。"""
    from html import escape
    _text, meta, blocks, closure = _skill_blocks(path, strict=strict)
    name = str(meta.get('name') or Path(path).resolve().parent.name)
    complete = (f'<skill name="{escape(name, quote=True)}">\n'
                + ''.join(body for _, body in blocks) + '\n</skill>')
    if len(complete) > cap:
        raise ValueError(f'SKILL 内容超过 {cap:,} 字符，已阻止发送：{Path(path).resolve()}；'
                         '请减少所选技能或缩短内容。')
    return complete, closure


def _inline_skill(path, *, cap=REQUEST_CONTEXT_MAX_CHARS, strict=False):
    """API 发送快照：技能及目录边界内的直接引用，不递归加载引用。"""
    return _inline_skill_report(path, cap=cap, strict=strict)[0]


def freeze_skills(config):
    """冻结发送内容；桌面与 API、四角色复用同一份正文，不在工作线程重读。"""
    from copy import deepcopy
    import hashlib
    from html import unescape
    frozen = deepcopy(config)
    if 'frozen_skill_prompt' in frozen:
        return frozen
    # 引用由下方逐项冻结严格核验；这里只补总控的制作锁门禁，手动与自动同样阻断。
    blocked = master_gate(frozen, check_references=False)
    if blocked:
        raise ValueError(blocked)
    selected, loaded, bodies, references, seen = [], [], [], [], set()
    for item in [*(frozen.get('stage_skills') or ()), *skills_of(frozen)]:
        path = Path(item).resolve()
        identity = os.path.normcase(str(path))
        if identity in seen:
            continue
        seen.add(identity)
        selected.append(str(path))
        try:
            body, closure = _inline_skill_report(path, strict=True)
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValueError(f'已勾选的 SKILL 或其引用未加载：{path}；已阻止发送。{exc}') from exc
        bodies.append(body)
        loaded.append({'path': str(path), 'name': unescape(body.split('"', 2)[1]),
                       'chars': len(body), 'sha256': hashlib.sha256(body.encode('utf-8')).hexdigest()})
        # 引用闭包按技能归属，随请求一起冻结，历史记录可核对「实际加载了什么」。
        references.extend(dict(row, skill=str(path)) for row in closure)
    header_config = dict(frozen, skills=[], skill='', stage_skills=[])
    frozen['frozen_skill_prompt'] = skill_prompt(header_config, inline=True) + ''.join(bodies)
    from writing_quality import enabled, prompt as quality_prompt
    if enabled(frozen['frozen_skill_prompt']):
        frozen['frozen_skill_prompt'] += quality_prompt()
    from workflow_context_budget import prepare_request_context
    prepare_request_context(frozen['frozen_skill_prompt'], 'SKILL')
    frozen['skill_injection'] = {'mode': frozen.get('invocation_mode') or frozen.get('engine', ''),
                                'engine': frozen.get('engine', ''),
                                'model': frozen.get('model', ''),
                                'selected': selected, 'loaded': loaded,
                                'references': references}
    return frozen


def _lock_fallback(key, value):
    """下拉以外的手填值若契约登记了兜底说明，附在该制作锁行尾。"""
    for item in PRODUCTION_LOCK_DEFINITIONS:
        if item['key'] == key and item.get('fallback'):
            known = {str(option).replace(' ', '').casefold() for option in item.get('options') or ()}
            if str(value).replace(' ', '').casefold() not in known:
                return '（' + item['fallback'] + '）'
    return ''


def skill_prompt(config, stage=None, inline=False):
    """桌面使用路径引用；直连 API 按需内联技能及直接引用的发送快照。"""
    if 'frozen_skill_prompt' in config:
        return config['frozen_skill_prompt']
    stage = lock_stage(stage if stage is not None else config.get('stage'))
    locks = config.get('workflow_lock') or {}
    required = STAGE_LOCK_REQUIREMENTS.get(stage)
    from script_contract import production_lock_active
    definitions = {item['key']: item for item in PRODUCTION_LOCK_DEFINITIONS}
    extra = {item['key'] for item in PRODUCTION_LOCK_DEFINITIONS[5:]}
    header = ''.join('制作锁：%s=%s%s\n' % (key, value, _lock_fallback(key, value)) for key, value in locks.items()
                     if str(value).strip() and (required is None or key in required or key in extra)
                     and production_lock_active(definitions.get(key, {}), locks))
    if header:
        header += '以项目锁定值为准，不要再向用户弹问这些锁。\n'
    coordinator = str(config.get('workflow_skill_prompt') or '')
    if coordinator and not coordinator.endswith('\n'):
        coordinator += '\n'
    items = [*(config.get('stage_skills') or ()), *skills_of(config)]
    prompts, seen = [], set()
    for item in items:
        if not item:
            continue
        identity = os.path.normcase(str(Path(item).resolve()))
        if identity in seen:
            continue
        seen.add(identity)
        prompts.append(_one_skill_prompt(config, item, inline=inline))
    return header + coordinator + ''.join(prompts)


def _one_skill_prompt(config,skill,inline=False):
    if not skill:return ''
    if inline:return _inline_skill(skill)
    path=Path(skill)
    # Both engines read the same skill and its relative support files.
    adapter=''
    if preset_folder(skill) in ('cinematic-director','video-storyboard-gen'):
        adapter=('\n本次只执行后文指定的分镜／提示词任务，按需读取 Skill 的相关参考资料。'
                 '沿用项目已确认的剧本、角色固定外观、场景、画风和资产编号，补齐缺项，不重新开始设定。'
                 '不调用媒体生成服务。本次明确要求图片及视频提示词，需同时交付。'
                 'Skill 自带的通用表格或脚手架不能直接当成本助手最终 JSON；须逐镜依据剧本细化，并按后文输出契约和校验器转换。\n')
    if config['engine'] in ('claude','qwen','opencode','claude-desktop-app','desktop-app'):
        return f'请先完整读取并遵循本地技能文件 {path}，相对引用以该技能文件所在目录为基准。'+adapter
    text=path.read_text(encoding='utf-8-sig')
    match=re.search(r'^name:\s*[\"\']?([A-Za-z0-9_-]+)',text,re.M)
    name=match.group(1) if match else re.sub(r'[^A-Za-z0-9_-]','_',path.parent.name)
    return f'请使用 [${name}]({path.as_posix()})。'+adapter

def model_name(project,stage='previs'):
    """当前流程实际使用的模型名：填了模型 ID 用 ID，留空用引擎显示名。

    第 62 期任务 3：改读 effective_model——阶段配置那一格挑了模型时，这里显示的必须是
    真发出去的那个名字，不能还念引擎的默认值。
    """
    return effective_model(project,stage)

def summary(project,stage='previs'):
    """Describe the same engine/model route that the dispatcher will execute."""
    cfg=current(project,stage);profile=cfg
    skill=Path(profile['skill']).parent.name if profile['skill'] else '内置制作要求'
    return f"调用：{ENGINES[cfg['engine']]} · {effective_model(project,stage)} · {skill}"

def show_settings(desktop,project,on_saved=None,stage='previs',function=None):
    dialog_key=(str(Path(project).resolve()),stage)
    dialogs=getattr(desktop,'_flow_settings_dialogs',{})
    previous=dialogs.get(dialog_key)
    if previous is not None and previous.winfo_exists():
        previous.lift();previous.model_entry.focus_set();return previous
    saved=load(project,stage);draft=copy.deepcopy(saved)
    stage_presets=[(label,folder) for label,folder in SKILL_PRESETS if folder in FLOW_SKILLS[stage] and preset_skill(folder).is_file()]
    win=BaseDialog(desktop.win,FLOWS[stage]+' · 调用设置',geometry='800x610',minsize=(640,520),modal=False,chrome=False);win.attributes('-alpha',0)
    # The shared placement handler reveals the dialog after centering it.
    dialogs[dialog_key]=win;desktop._flow_settings_dialogs=dialogs
    footer=ttk.Frame(win,padding=(16,8));footer.pack(side='bottom',fill='x')
    body=Card(win);body.pack(fill='both',expand=True,padx=SPACING['lg'],pady=SPACING['lg']);body.columnconfigure(1,weight=1)
    ttk.Label(body,text='当前项目的本流程生效；保存后用于新任务，进行中的整批任务不变。',wraplength=680).grid(row=0,column=0,columnspan=3,sticky='w',pady=(0,6))
    # 第 63 期任务 3.1／3.2：每一次打开阶段配置都能看见「本步怎么并行」和「门禁过没过」——
    # 口径只有 stage_parallel 一处（附件那张并行配置速查表）。
    from stage_parallel import page_lines
    ttk.Label(body,text='\n'.join(page_lines(project,stage)),justify='left',
              wraplength=680,style='Muted.TLabel').grid(row=0,column=0,columnspan=3,sticky='w',pady=(0,12))
    chosen=tk.StringVar(value=ENGINES[saved['engine']]);active=[saved['engine']]
    ttk.Label(body,text='制作引擎').grid(row=1,column=0,sticky='w',padx=(0,12))
    selector=ttk.Label(body,textvariable=chosen);selector.grid(row=1,column=1,sticky='ew',pady=SPACING['xs'])
    values={key:tk.StringVar() for key in ('program','model','skill')}
    custom=ttk.LabelFrame(body,text='自定义模型 / Skill / API',padding=10)
    custom.grid(row=3,column=0,columnspan=3,sticky='ew',pady=(8,4));custom.columnconfigure(1,weight=1)
    def browse(key):
        name=FileDialog(win).open_file(title='选择 '+('SKILL.md' if key=='skill' else ENGINES[active[0]]+' 命令行程序'),
            filetypes=[('Skill','SKILL.md')] if key=='skill' else [('命令行程序','*.exe')])
        if name:values[key].set(name)
    for row,key,label in [(1,'program','程序位置'),(0,'model','自定义模型 ID'),(3,'skill','Skill 文件')]:
        ttk.Label(custom,text=label).grid(row=row,column=0,sticky='w',padx=(0,12))
        entry=LineInput(custom,textvariable=values[key],state='normal');entry.grid(row=row,column=1,sticky='ew',pady=5)
        if key=='model':win.model_entry=entry
        if key=='skill':skill_entry=entry
        if key!='model':SecondaryButton(custom,text='选择文件',command=lambda k=key:browse(k)).grid(row=row,column=2,padx=(8,0))
    ttk.Label(custom,text='模型 ID 可直接填写；留空使用默认模型。保存后更新外面的 Agent 名称。',wraplength=650,style='Muted.TLabel').grid(row=4,column=0,columnspan=3,sticky='w',pady=SPACING['xs'])
    skill_details=tk.StringVar()
    def update_skill(*_):
        value=values['skill'].get()
        skill_details.set(SKILL_DETAILS.get(preset_folder(value),'自定义文件将随任务交给所选引擎读取。' if value else '仅使用本流程的内置要求。'))
    values['skill'].trace_add('write',update_skill)
    ttk.Label(custom,textvariable=skill_details,wraplength=650).grid(row=5,column=0,columnspan=3,sticky='w',pady=SPACING['xs'])
    ttk.Label(body,text='补充制作要求（可选）').grid(row=4,column=0,columnspan=2,sticky='w')
    notes=TextArea(body,height=4,wrap='word',undo=True);notes.grid(row=5,column=0,columnspan=3,sticky='nsew',pady=5);body.rowconfigure(5,weight=1)
    feedback=tk.StringVar(value='模型与 Skill 在主页面切换；此处编辑当前配置，保存后自动关闭。')
    ttk.Label(body,textvariable=feedback,wraplength=680).grid(row=6,column=0,columnspan=3,sticky='w',pady=6)
    ttk.Label(body,text='当前 Agent').grid(row=2,column=0,sticky='w')
    agent_name=tk.StringVar()
    ttk.Label(body,textvariable=agent_name,wraplength=540).grid(row=2,column=1,columnspan=2,sticky='w',pady=5)
    def update_agent_label(*_):
        agent_name.set(agent_label({k:v.get() for k,v in values.items()},stage,active[0],function))
    values['skill'].trace_add('write',update_agent_label)
    values['model'].trace_add('write',update_agent_label)
    def stash():
        profile={**{k:v.get().strip() for k,v in values.items()},'instructions':notes.get('1.0','end-1c').strip()}
        # 第 59 期第 5 条：这一格改的是这一档的第一份 SKILL，面板上勾的其余几份照旧留着。
        rest=skills_of(draft['profiles'][active[0]])[1:]
        set_skills(profile,([profile['skill']] if profile['skill'] else [])+rest)
        draft['profiles'][active[0]]=profile
    def populate():
        profile=draft['profiles'][active[0]]
        if active[0]=='qwen' and not profile['program']:
            try:profile['program']=find_program({'engine':'qwen','program':''})
            except ValueError:pass
        for key,var in values.items():var.set(profile[key])
        notes.delete('1.0','end');notes.insert('1.0',profile['instructions'])
        api_button.state(['!disabled'] if active[0]=='qwen' else ['disabled'])
        update_agent_label()
    def check():
        try:
            stash();cfg={'engine':active[0],**validate_stage_profile(draft['profiles'][active[0]],stage)}
            feedback.set('已找到程序：'+find_program(cfg)+'；登录和模型权限将在制作时验证。')
        except Exception as exc:feedback.set(str(exc))
    def commit():
        try:
            stash();draft['profiles'][active[0]]=validate_stage_profile(draft['profiles'][active[0]],stage)
            draft['engine']=active[0]
            path=settings_path(project)
            all_settings=read_json(path) if path.is_file() else {}
            all_settings.setdefault('flows',{})[stage]=draft;save(path,all_settings)
            if active[0]=='qwen':sync_qwen_model(project,draft['profiles']['qwen']['model'])
            if on_saved:on_saved()
            win.destroy()
        except Exception as exc:notify(win, str(exc), level='error', title='调用设置', status=feedback)
    def api_saved():
        model=__import__('qwen_setup').load()['model']
        sync_qwen_model(project,model)
        draft['profiles']['qwen']['model']=model
        if active[0]=='qwen':values['model'].set(model)
        feedback.set('API 设置已保存，Qwen 模型已同步。')
    api_button=SecondaryButton(custom,text='自定义 API（Qwen）',command=lambda:__import__('qwen_setup').show(win,on_saved=api_saved))
    api_button.grid(row=0,column=2,padx=(8,0))
    row=ttk.Frame(footer);row.pack(side='right')
    SecondaryButton(row,text='检查配置',command=check).pack(side='left',padx=5)
    PrimaryButton(row,text='保存',command=commit).pack(side='left',padx=5)
    SecondaryButton(row,text='取消',command=win.destroy).pack(side='left')
    populate()
    def focus_model():
        if win.winfo_exists():win.lift();win.model_entry.focus_set()
    focus_timer=win.after_idle(focus_model)
    def disposed(event):
        if event.widget is win:
            try:win.after_cancel(focus_timer)
            except tk.TclError:pass
            if dialogs.get(dialog_key) is win:dialogs.pop(dialog_key,None)
    win.bind('<Destroy>',disposed,add='+')
    return win
