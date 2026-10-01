"""Project-scoped engine profiles for the white-model production entry."""
import copy
import os
import re
import shutil
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
import tkinter as tk
from agent.core import save
from file_cache import read_json

ENGINES={'codex':'ChatGPT / Codex','qwen':'Qwen Code（阿里云）','claude':'Claude Code'}
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
# 统筹预设是受控登记，不从外部包 frontmatter 推导执行字段。
WORKFLOW_PRESETS={'AIGC全流程': {
    'package': 'skills/00全流程SKILL/AIGC创作全流程/short-drama-director/SKILL.md',
    'stage_skills': {'script':['pipeline-script-preparation'], 'script_structure':['pipeline-script-structure'],
        'storyboard':['pipeline-storyboard-draft'], 'assets':['pipeline-assets'], 'continuity':['pipeline-continuity'],
        'final':['pipeline-storyboard-final'], 'keyframe':['pipeline-keyframe'], 'previs':['pipeline-previs'],
        'video':['pipeline-video-generation'], 'audio':['pipeline-audio-subtitle'], 'edit':['pipeline-editing'],
        'delivery':['pipeline-delivery']},
    'locks': [
        {'key':'aspect_ratio','label':'画幅','options':['16:9','9:16','21:9','1:1']},
        {'key':'delivery_format','label':'交付形态','options':['只要离线看板','只要 markdown 文档','两者都交付']},
        {'key':'video_model_version','label':'视频模型版本','options':['Seedance 2.5','Seedance 2.0','MiniMax H3']},
    ],
}}
_DESKTOP_INSTALLATION_CACHE={}

# 预设 SKILL 可以覆盖创作风格，不能跨越当前工作阶段。该契约在运行时总是附在
# SKILL 之后，因而比通用工作流里的“可做分镜／资产”等能力说明优先。
_STAGE_OUTPUT_CONTRACTS={
    'writing': ('\n\n【剧本准备阶段输出契约（最高优先级）】\n'
                '本阶段唯一可交付内容是完整的自然语言剧本原稿：分集标题、场景／时间地点、可见动作、人物目标、冲突、对白和结尾悬念。\n'
                '剧本正文中禁止出现结构化剧本、角色／场景／道具档案、字段表、JSON／YAML、镜头或分镜表、首帧／视频提示词、资产清单；结构化剧本工作仍属下一阶段“02剧本结构”，即使所选 SKILL 含有这些能力，也不得以剧本正文形式在本阶段产出。\n'
                '所选 SKILL 要求的过程文档（分集大纲、情节节点表、节奏／逻辑／合规审查报告、确认清单等供人阅读的 Markdown）允许写入本阶段目录的 docs/ 子目录；它们不是阶段交付物，不得并入剧本原稿，不得替代“02剧本结构”的结构化剧本。\n'
                '五类 manifest JSON 仍按 script_contract.PRODUCERS 的归属产出，本阶段对话不生成。只返回剧本正文与 SKILL 要求的确认清单，不解释创作过程。'),
    'script_structure': ('\n\n【剧本整理阶段输出契约（最高优先级）】\n'
                         '本阶段核心任务是整理剧本要素：从自然语言原稿提取并校验人物、场景、道具、事件、冲突、台词与分场关系，生成可追溯的结构剧本。\n'
                         '不得重写或替换自然语言原稿，不得做核心人物切镜头、镜头三元组、镜头拆分、分镜 JSON、首帧或媒体提示词；这些只属于“03初步分镜”。'),
    'storyboard': ('\n\n【初步分镜阶段输出契约（最高优先级）】\n'
                   '本阶段只以已确认的结构剧本为来源制作分镜初稿：围绕核心人物的目标、动作与情绪变化切镜头；每镜明确镜头三元组“核心人物／主体—可见动作—景别机位与运镜”，并按动作闭合点拆分镜头。\n'
                   '不得重新整理角色、场景、道具档案或重写结构剧本。输出的分镜定稿负责锁定来源剧本、人物／场景／道具编号、镜头编号、时长、动作起止、对白和连续性约束；锁定后只允许在明确修订流程中改动。'),
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
    try:
        import stage_config
        import model_pool
        selected = str(stage_config.get(project, STAGE_CONFIG_STAGES.get(stage, stage)).get('model') or '').strip()
        if model_pool.desktop_engine(selected):
            return model_pool.label_of(selected, model_pool.pool(program=Path(__file__).resolve().parent))
    except Exception:
        pass
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


def current(project,stage='previs'):
    value=load(project,stage);engine=value['engine']
    selected='';item={};local_program=''
    import stage_config
    import model_pool
    selected = str(stage_config.get(project, STAGE_CONFIG_STAGES.get(stage, stage)).get('model') or '').strip()
    item = model_pool.pool(program=Path(__file__).resolve().parent).get(selected, {})
    explicit_engine = model_pool.desktop_engine(selected)
    if explicit_engine:
        engine = explicit_engine
    else:
        local_engine, local_program = _local_engine_for_selected_model(value, selected, item, stage)
        if local_engine:
            engine = local_engine
        elif item:
            # 模型池中的任意 API 模型都必须交给兼容调用器。此前仅 GPT／Anthropic
            # 会走这里，选 DeepSeek V4 Flash 时便错误沿用默认 Codex，导致三虎
            # 自动打开的是 Codex 而阶段按钮却显示 DeepSeek。
            engine = 'qwen'
    profile=validate_stage_profile(value['profiles'][engine],stage)
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
    model,api=stage_model(project,stage) if engine=='qwen' else ('','')
    if model:profile['model']=model
    if api:profile['api']=api
    # 统筹投影不改变旧引擎档；仅在生成提示词时作为受控前缀读取。
    workflow = stage_config.current_workflow(project)
    locks = stage_config.workflow_lock(project)
    if locks:
        profile['workflow_lock'] = locks
    name = str(workflow.get('name') or '').strip()
    preset = WORKFLOW_PRESETS.get(name, {})
    if preset:
        profile['workflow_skill_prompt'] = '请先完整读取并遵循统筹 SKILL：' + str(preset['package'])
    try:
        import skill_registry
        reg = skill_registry.default_registry()
        profile['stage_skills'] = [str(reg.getById(item).path) for item in
                                  stage_config.get(project, STAGE_CONFIG_STAGES.get(stage, stage)).get('skills', ())
                                  if reg.getById(item) is not None]
    except Exception:
        profile['stage_skills'] = []
    return {'engine':engine,**profile}

def find_program(config):
    if config['program']:return config['program']
    if config['engine']=='qwen':
        from qwen_adapter import command
        return command(config)[0]
    engine=config['engine'];found=shutil.which(engine+'.exe')
    if found:return found
    if engine=='codex':
        choices=list((Path(os.environ.get('LOCALAPPDATA',''))/'OpenAI/Codex/bin').glob('*/codex.exe'))
        if choices:return str(max(choices,key=lambda p:p.stat().st_mtime))
    else:
        native=Path.home()/'.local/bin/claude.exe'
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
    if engine not in _DESKTOP_INSTALLATION_CACHE:
        try:find_program({'engine':engine,'program':''})
        except Exception:_DESKTOP_INSTALLATION_CACHE[engine]=False
        else:_DESKTOP_INSTALLATION_CACHE[engine]=True
    return str(label or '')+('（未安装）' if not _DESKTOP_INSTALLATION_CACHE[engine] else '')

def skill_prompt(config):
    """这一档勾中的 SKILL 拼成一段「先读这份技能文件」的说明（第 59 期第 5 条：可以勾几份）。"""
    locks=config.get('workflow_lock') if isinstance(config,dict) else None
    header=''.join('制作锁：%s=%s\n' % (key,value) for key,value in (locks or {}).items() if str(value).strip())
    coordinator=str(config.get('workflow_skill_prompt') or '') if isinstance(config,dict) else ''
    if coordinator and not coordinator.endswith('\n'):
        coordinator += '\n'
    # 顺序是契约：锁 → 统筹 → 阶段清单 → 引擎档附加清单。
    stage_items=config.get('stage_skills') if isinstance(config,dict) else None
    attached=skills_of(config)
    return header + coordinator + ''.join(_one_skill_prompt(config,item) for item in (stage_items or ())) + ''.join(_one_skill_prompt(config,item) for item in attached)


def _one_skill_prompt(config,skill):
    if not skill:return ''
    path=Path(skill)
    # Both engines read the same skill and its relative support files.
    adapter=''
    if preset_folder(skill) in ('cinematic-director','video-storyboard-gen'):
        adapter=('\n本次只执行后文指定的分镜／提示词任务，按需读取 Skill 的相关参考资料。'
                 '沿用项目已确认的剧本、角色固定外观、场景、画风和资产编号，补齐缺项，不重新开始设定。'
                 '不调用媒体生成服务。本次明确要求图片及视频提示词，需同时交付。'
                 'Skill 自带的通用表格或脚手架不能直接当成本助手最终 JSON；须逐镜依据剧本细化，并按后文输出契约和校验器转换。\n')
    if config['engine'] in ('claude','qwen'):
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
    win=tk.Toplevel(desktop.win);win.attributes('-alpha',0)
    # The shared placement handler reveals the dialog after centering it.
    win.title(FLOWS[stage]+' · 调用设置');win.geometry('800x610');win.minsize(640,520);win.transient(desktop.win)
    dialogs[dialog_key]=win;desktop._flow_settings_dialogs=dialogs
    footer=ttk.Frame(win,padding=(16,8));footer.pack(side='bottom',fill='x')
    body=ttk.Frame(win,padding=16);body.pack(fill='both',expand=True);body.columnconfigure(1,weight=1)
    ttk.Label(body,text='当前项目的本流程生效；保存后用于新任务，进行中的整批任务不变。',wraplength=680).grid(row=0,column=0,columnspan=3,sticky='w',pady=(0,6))
    # 第 63 期任务 3.1／3.2：每一次打开阶段配置都能看见「本步怎么并行」和「门禁过没过」——
    # 口径只有 stage_parallel 一处（附件那张并行配置速查表）。
    from stage_parallel import page_lines
    ttk.Label(body,text='\n'.join(page_lines(project,stage)),justify='left',
              wraplength=680,style='Muted.TLabel').grid(row=0,column=0,columnspan=3,sticky='w',pady=(0,12))
    chosen=tk.StringVar(value=ENGINES[saved['engine']]);active=[saved['engine']]
    ttk.Label(body,text='制作引擎').grid(row=1,column=0,sticky='w',padx=(0,12))
    selector=ttk.Label(body,textvariable=chosen);selector.grid(row=1,column=1,sticky='ew',pady=4)
    values={key:tk.StringVar() for key in ('program','model','skill')}
    custom=ttk.LabelFrame(body,text='自定义模型 / Skill / API',padding=10)
    custom.grid(row=3,column=0,columnspan=3,sticky='ew',pady=(8,4));custom.columnconfigure(1,weight=1)
    def browse(key):
        name=filedialog.askopenfilename(parent=win,title='选择 '+('SKILL.md' if key=='skill' else ENGINES[active[0]]+' 命令行程序'),
            filetypes=[('Skill','SKILL.md')] if key=='skill' else [('命令行程序','*.exe')])
        if name:values[key].set(name)
    for row,key,label in [(1,'program','程序位置'),(0,'model','自定义模型 ID'),(3,'skill','Skill 文件')]:
        ttk.Label(custom,text=label).grid(row=row,column=0,sticky='w',padx=(0,12))
        entry=ttk.Entry(custom,textvariable=values[key],state='normal');entry.grid(row=row,column=1,sticky='ew',pady=5)
        if key=='model':win.model_entry=entry
        if key=='skill':skill_entry=entry
        if key!='model':ttk.Button(custom,text='选择文件',command=lambda k=key:browse(k)).grid(row=row,column=2,padx=(8,0))
    ttk.Label(custom,text='模型 ID 可直接填写；留空使用默认模型。保存后更新外面的 Agent 名称。',wraplength=650,style='Muted.TLabel').grid(row=4,column=0,columnspan=3,sticky='w',pady=4)
    skill_details=tk.StringVar()
    def update_skill(*_):
        value=values['skill'].get()
        skill_details.set(SKILL_DETAILS.get(preset_folder(value),'自定义文件将随任务交给所选引擎读取。' if value else '仅使用本流程的内置要求。'))
    values['skill'].trace_add('write',update_skill)
    ttk.Label(custom,textvariable=skill_details,wraplength=650).grid(row=5,column=0,columnspan=3,sticky='w',pady=4)
    ttk.Label(body,text='补充制作要求（可选）').grid(row=4,column=0,columnspan=2,sticky='w')
    notes=tk.Text(body,height=4,wrap='word',undo=True);notes.grid(row=5,column=0,columnspan=3,sticky='nsew',pady=5);body.rowconfigure(5,weight=1)
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
        except Exception as exc:messagebox.showerror('调用设置',str(exc),parent=win)
    def api_saved():
        model=__import__('qwen_setup').load()['model']
        sync_qwen_model(project,model)
        draft['profiles']['qwen']['model']=model
        if active[0]=='qwen':values['model'].set(model)
        feedback.set('API 设置已保存，Qwen 模型已同步。')
    api_button=ttk.Button(custom,text='自定义 API（Qwen）',command=lambda:__import__('qwen_setup').show(win,on_saved=api_saved))
    api_button.grid(row=0,column=2,padx=(8,0))
    row=ttk.Frame(footer);row.pack(side='right')
    ttk.Button(row,text='检查配置',command=check).pack(side='left',padx=5)
    ttk.Button(row,text='保存',command=commit).pack(side='left',padx=5)
    ttk.Button(row,text='取消',command=win.destroy).pack(side='left')
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
