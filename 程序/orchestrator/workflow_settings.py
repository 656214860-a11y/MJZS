"""Project-scoped engine profiles for the white-model production entry."""
import app_logging
import os
import re
import shutil
from pathlib import Path
from agent.core import save
from file_cache import read_json
import orchestrator.skill_registry as skill_registry
from orchestrator.skill_registry import nested_references as _nested_references, reference_row as _reference_row
from orchestrator.skill_inline import (_charge_inline, _is_text_script, _recurse_references,
                          _skill_inline_budget, _skipped_inline_hint)
import client_profiles, orchestrator.edit_habits as edit_habits, stage_layout
from contract.script_contract import PRODUCTION_LOCK_DEFINITIONS, STAGE_LOCK_REQUIREMENTS, lock_stage
from contract.workflow_context_budget import REQUEST_CONTEXT_MAX_CHARS, estimate_tokens, skill_inline_token_budget
from infra.store_program_locator import current_store_program, store_package_program, gui_claude_program, GUI_CLAUDE_CLI_HINT
ENGINES={'codex':'ChatGPT / Codex','qwen':'Qwen Code（阿里云）','claude':'Claude Code','claude-desktop-app':'Claude Desktop','desktop-app':'自定义桌面应用','client-cli':'自定义命令行客户端','opencode':'opencode CLI（自动放行权限）'}
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
_DESKTOP_INSTALLATION_CACHE={}
_STAGE_OUTPUT_CONTRACTS={
    'writing': ('\n\n【剧本准备阶段输出契约（最高优先级）】\n'
                '先问清楚，再创作：用户未提供故事大体环境和小说/漫剧类型时，必须先问，不能直接写。'
                '按四阶段输出：①项目设定 → ②剧本大纲 → ③角色卡 → ④自然剧本。'
                '每个关键阶段都必须用户确认，不能自动跳到下一阶段；每次只输出当前阶段一个文件，末尾“待确认”。'
                '项目设定和角色卡存入规范的项目设定目录，剧本大纲存入项目大纲目录；前三项仅供用户审阅参考，不进入 02 结构剧本的输入。'
                '角色卡标明“人物设定”，同一路径更新时保留已确认设定。'
                '本阶段唯一正式交付物是完整自然语言剧本正文（场景/动作/人物目标/冲突/对白/悬念），存入规范的项目剧本目录；'
                '每集在正文前附本集节拍表（每场 3–5 个情绪节拍，含情绪关键词、剧本动作、权重、强度），与正文同属自然剧本文件、不另存；节拍表不含机位、情境 ID 等镜头层内容。'
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
BUNDLED_SKILLS=Path(__file__).resolve().parents[1]/'skills'
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
def skill_roots_for_config(config):
    """勾选 SKILL 的目录白名单（供 CLI 引擎 `--add-dir`／`--include-directories`）。

    返回去重后的目录列表：每份勾选 SKILL 的所在目录（导入包＝包目录、单文件＝阶段目录）。
    勾选了 SKILL 时再附上 skill 根目录（内置/用户层，供 ``../00全流程SKILL`` 跨层引用可读）；
    未勾选任何 SKILL 时返回空表，不把整个 skills 树无谓授权给 CLI。CLI 模型据此能按需读全文、
    看图、跑脚本，等效 desktop 原生行为；纯 API 模型走内联，不经过这里。
    """
    dirs, seen = [], set()
    for item in [*(config.get('stage_skills') or ()), *skills_of(config)]:
        if not item:
            continue
        parent = Path(item).resolve().parent
        identity = os.path.normcase(str(parent))
        if identity not in seen:
            seen.add(identity)
            dirs.append(parent)
    if dirs:
        roots = list(skill_registry.skill_roots())
        # 项目层 SKILL 的 ``../`` 跨层引用需要项目 skills 根一并授权；config 不带
        # 项目字段，从已勾选路径反推（祖先 skills/ 且父级有 skill_config.json）。
        for directory in dirs:
            project_root = skill_registry.project_skill_root_for(directory)
            if project_root is not None and project_root not in roots:
                roots.append(project_root)
        for root in roots:
            identity = os.path.normcase(str(root))
            if identity not in seen:
                seen.add(identity)
                dirs.append(root)
    return dirs
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
    return stage_layout.workflow_dir(project,'工作流调用设置.json')
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
def save_flow(project,stage,draft,engine):
    """调用设置窗口「保存」：校验所选引擎这一档 → 写回本流程 → Qwen 再同步共享模型。

    就地更新 draft（校验后的这一档与 engine），顺序与原窗口内保存一致；任何一步出错都原样抛给调用方。
    """
    draft['profiles'][engine]=validate_stage_profile(draft['profiles'][engine],stage)
    draft['engine']=engine
    path=settings_path(project)
    all_settings=read_json(path) if path.is_file() else {}
    all_settings.setdefault('flows',{})[stage]=draft;save(path,all_settings)
    if engine=='qwen':sync_qwen_model(project,draft['profiles']['qwen']['model'])
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
        import orchestrator.stage_config as stage_config
        import orchestrator.stage_models as stage_models
        import model_pool
        chosen=str(stage_config.get(project,STAGE_CONFIG_STAGES.get(stage,stage)).get('model') or '').strip()
    except Exception:
        return '',''
    if not chosen or chosen==model_pool.AUTO or model_pool.desktop_engine(chosen):
        return '',''
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
    program=Path(__file__).resolve().parents[1]
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
    cfg=current(project,stage);engine=cfg['engine']
    if engine == 'desktop-app':
        return cfg['display_model']
    try:
        import orchestrator.stage_config as stage_config
        import model_pool
        selected = str(stage_config.get(project, STAGE_CONFIG_STAGES.get(stage, stage)).get('model') or '').strip()
        if model_pool.desktop_engine(selected):
            return model_pool.label_of(selected, model_pool.pool(program=Path(__file__).resolve().parents[1]))
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
        model_pool.pool(program=Path(__file__).resolve().parents[1]).get(selected, {})
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
    import orchestrator.stage_config as stage_config
    import model_pool
    if model_snapshot is None:
        selected = str(stage_config.get(project, STAGE_CONFIG_STAGES.get(stage, stage)).get('model') or '').strip()
        item = model_pool.pool(program=Path(__file__).resolve().parents[1]).get(selected, {})
    else:
        selected, item = model_snapshot
    explicit_engine = model_pool.desktop_engine(selected)
    if not explicit_engine and item:
        selected_mode = model_pool.call_mode(item, selected)
        if selected_mode == 'Desktop':
            explicit_engine = 'desktop-app'
        elif selected_mode == 'CLI' and str(item.get('program') or '').strip():
            explicit_engine = 'client-cli'
    if explicit_engine:
        engine = explicit_engine
    else:
        local_engine, local_program = ('', '') if direct_api else _local_engine_for_selected_model(value, selected, item, stage)
        if local_engine:
            engine = local_engine
        elif item:
            engine = 'qwen'
    if direct_api:
        engine = 'qwen'
    profile=validate_stage_profile(value['profiles'][engine],stage)
    if engine == 'desktop-app':
        profile['program'] = str(item.get('program') or '').strip()
        profile['model'] = ''
    if explicit_engine in ('desktop-app', 'client-cli'):
        wanted = 'desktop' if explicit_engine == 'desktop-app' else 'cli'
        found = client_profiles.profile_for_model(selected, item, kind=wanted) or \
            client_profiles.profile_for_mode(selected, wanted)
        profile['client_profile'] = found.get('id', '')
        profile['delivery'] = found.get('delivery', 'paste' if explicit_engine == 'desktop-app' else 'cli_stdin')
        profile['app_name'] = found.get('display', '') or str(item.get('label') or selected or '').strip()
        profile['client_process_names'] = list(found.get('process_names') or ())
        profile['client_window'] = dict(found.get('window') or {})
        if not profile.get('program') and found:
            try:
                profile['program'] = client_profiles.detect_executable(
                    found, store_finder=store_package_program)
            except Exception:
                app_logging.swallowed()
    if explicit_engine and item.get('program'):
        if explicit_engine == 'codex':
            profile['desktop_program'] = item['program']
            profile['program'] = ''
            profile['model'] = ''
        else:
            profile['program'] = item['program']
    if local_program:
        profile['program']=local_program
        profile['model']=''
        selected_model, selected_api = stage_model(project,stage)
        if selected_api:
            profile['api_fallback']={'model':selected_model,'api':selected_api,
                                     'profile':validate_stage_profile(value['profiles']['qwen'],stage)}
    model,api=(selected, {}) if direct_api else (stage_model(project,stage) if engine=='qwen' else ('',''))
    if model:profile['model']=model
    if api:profile['api']=api
    locks = stage_config.workflow_lock(project)
    profile['project_created_at'] = stage_config.project_created_at(project)
    if locks:
        profile['workflow_lock'] = locks
    profile.update(edit_habits.config_fields(stage))  # REQ-S01-61：建配置时读一次已采用的修改习惯
    if stage == 'writing': profile['writer_style'] = stage_config.writer_style(project, 'script')
    try:
        import orchestrator.skill_registry as skill_registry
        reg = skill_registry.default_registry(project=project)
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
        found = client_profiles.profile_for_mode(name, 'CLI')
        if found:
            path = client_profiles.detect_executable(found, store_finder=store_package_program)
            if path:
                return path
            raise ValueError('未找到“%s”的命令行程序；请手动浏览 .exe，或改用交互式窗口' % model)
        raise ValueError('未找到对应的受支持 CLI：' + str(model))
    if name in ('claude', 'claude-desktop', 'claude-desktop-app'):
        return find_program({'engine': 'claude-desktop-app', 'program': ''})
    aliases = {'chatgpt-desktop': 'codex', 'codex-desktop': 'codex',
               'google-gemini': 'gemini'}
    app = aliases.get(name, name)
    legacy = {'claude', 'claude-desktop', 'claude-desktop-app', 'chatgpt-desktop',
              'codex-desktop', 'google-gemini', 'gemini'}
    if name not in legacy:
        found = client_profiles.profile_for_mode(name, 'Desktop')
        if found:
            path = client_profiles.detect_executable(found, store_finder=store_package_program)
            if path:
                return path
            raise ValueError('未找到“%s”的 Desktop 安装程序；请确认已安装，或点“浏览…”指定 .exe' % model)
    if re.fullmatch(r'(google-)?gemini(?:-[0-9.]+(?:-[a-z0-9]+)*)?', name):
        app = 'gemini'
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]*', app):
        raise ValueError('未找到对应桌面应用，请填写应用名或手动浏览安装路径')
    executable = app + '.exe'
    from contract.platform_tools import windows_registry
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
    for app_name in (app, name):
        found = client_profiles.profile_for_mode(app_name, 'Desktop')
        if found:
            path = client_profiles.detect_executable(found, store_finder=store_package_program)
            if path:
                return path
    raise ValueError('未找到“%s”的 Desktop 安装程序；请确认已安装对应桌面应用，或点“浏览…”指定 .exe' % model)
def find_program(config):
    if config['program']:return current_store_program(config['program'])
    engine = config['engine']
    if engine not in ENGINES:
        found = client_profiles.profile_for_config(config) or client_profiles.profile(engine)
        if found:
            path = client_profiles.detect_executable(found, store_finder=store_package_program)
            if path:return path
            raise ValueError('未找到“%s”的程序；请在模型管理指定 .exe，或改用交互式窗口' % found['display'])
        raise ValueError('未知的本地调用引擎：' + str(engine))
    if config['engine'] == 'desktop-app':
        found = client_profiles.profile_for_config(config)
        if found:
            path = client_profiles.detect_executable(found, store_finder=store_package_program)
            if path:return path
            raise ValueError('未找到桌面程序路径；请在模型管理为此 Desktop 模型指定 .exe')
        raise ValueError('请在模型管理为此 Desktop 模型指定桌面程序路径')
    if config['engine'] == 'client-cli':
        found = client_profiles.profile_for_config(config)
        if not found:
            raise ValueError('请在模型管理为此命令行模型指定 .exe，或重新点「检测」生成档案')
        path = client_profiles.detect_executable(found, store_finder=store_package_program)
        if path:return path
        raise ValueError('未找到“%s”的命令行程序；请在模型管理指定 .exe，或改用交互式窗口' % found['display'])
    if config['engine'] == 'claude-desktop-app':
        local = Path(os.environ.get('LOCALAPPDATA', ''))
        candidates = [local/'AnthropicClaude/claude.exe', local/'Programs/Claude/Claude.exe']
        candidates.extend(sorted((local/'AnthropicClaude').glob('app-*/claude.exe'),
                                 key=lambda path: path.stat().st_mtime, reverse=True))
        for candidate in candidates:
            if candidate.is_file():return str(candidate)
        store = store_package_program('Claude', Path('app')/'Claude.exe')
        if store:return store
        raise ValueError('未找到 Claude Desktop，请在模型管理选择其 .exe')
    if config['engine']=='qwen':
        from client_profiles import qwen_command
        return qwen_command(config)[0]
    if config['engine']=='opencode':
        found=shutil.which('opencode-cli.exe')
        if found:return found
        appdata=os.environ.get('APPDATA')
        if appdata:
            choices=list((Path(appdata)/'ai.opencode.desktop'/'cli').glob('*/opencode-cli.exe'))
            if choices:return str(max(choices,key=lambda p:p.stat().st_mtime))
        raise ValueError('未找到 OpenCode CLI，请安装后在“调用设置”选择它的 .exe')
    engine=config['engine'];found=shutil.which(engine+'.exe')
    if found:return found
    if engine=='codex':
        choices=list((Path(os.environ.get('LOCALAPPDATA',''))/'OpenAI/Codex/bin').glob('*/codex.exe'))
        if choices:return str(max(choices,key=lambda p:p.stat().st_mtime))
    else:
        native=Path.home()/'.local/bin/claude.exe'
        if native.is_file():return str(native)
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
    configured=model_pool.pool(program=Path(__file__).resolve().parents[1]).get(model_id, {}).get('program', '')
    if configured:
        return str(label or '')+('（未安装）' if not Path(current_store_program(configured)).is_file() else '')
    if engine not in _DESKTOP_INSTALLATION_CACHE:
        try:find_program({'engine':engine,'program':''})
        except Exception:_DESKTOP_INSTALLATION_CACHE[engine]=False
        else:_DESKTOP_INSTALLATION_CACHE[engine]=True
    return str(label or '')+('（未安装）' if not _DESKTOP_INSTALLATION_CACHE[engine] else '')
def validate_selected_skills(project, stage):
    """在解析前检查保留的选择，禁止把失效选择静默变成未勾选。"""
    import orchestrator.stage_config as stage_config
    import orchestrator.skill_registry as skill_registry
    from file_cache import read_json
    target = stage_config.path(project)
    data = read_json(target)
    if target.exists() and not isinstance(data, dict):
        raise ValueError('SKILL 配置无法读取，已阻止发送，请重新确认阶段配置。')
    entry = (data or {}).get(STAGE_CONFIG_STAGES.get(stage, stage), {})
    if not isinstance(entry, dict) or not isinstance(entry.get('skills', []), (list, tuple)):
        raise ValueError('阶段 SKILL 配置格式无效，已阻止发送，请重新确认阶段配置。')
    registry = skill_registry.default_registry(project=project)
    disabled = registry.disabled_names()
    for name in entry.get('skills') or ():
        if registry.getById(name) is not None:
            continue
        if name in disabled:
            raise ValueError(f'已勾选的 SKILL 已禁用：{name}；已阻止发送，请在「设置 → SKILL 管理」启用后重试。')
        raise ValueError(f'已勾选的 SKILL 未加载：{name}；已阻止发送，请重新确认阶段配置。')
def _closure_blocked(message, closure):
    """发送阻断异常附带已走到的引用闭包，供 SKILL 体检展示「断在哪、之前加载了什么」。"""
    error = ValueError(message)
    error.skill_closure = list(closure)
    return error
def _skill_blocks(path, *, strict, locks=None, depth=0, budget=None):
    """走一遍技能正文与它的引用；返回 (正文, 元数据, 分块, 引用闭包)。

    闭包是「实际发生了什么」的唯一记录：inlined（已内联）、duplicate（重复）、
    outside（越界）、missing（缺失）、resource（图片／视频等二进制资源）、remote（外部地址）、
    anchor（纯锚点）、absolute（绝对路径），以及 depth=2 的嵌套项：nested（未展开）、
    cycle（回指已加载文件）、outside、missing。

    ``depth`` 控制引用递归深度：0＝只内联直接引用（历史行为）；-1＝无限递归展开嵌套引用；
    正整数＝再往下展开该层。脚本类文本（.py/.sh 等）按代码块内联；二进制资源只登记不内联，
    并附一句本地路径提示。回环经 ``seen`` 去重，不重复加载。
    带锚点的链接只内联该节（section），锚点找不到才内联全文；给了 ``locks`` 时，
    「仅 `锁` 为…时追加」条件不满足的链接不加载（conditional）。
    """
    path = Path(path).resolve()
    text = path.read_text(encoding='utf-8-sig')
    meta, content = skill_registry.parse(text, source=str(path))
    if strict and not content.strip():
        raise ValueError(f'已勾选的 SKILL 内容为空，已阻止发送：{path}')
    blocks = [(path, f'<!-- 来源: {path} -->\n{content}')]
    closure, seen, sections = [], {path}, set()
    roots = list(skill_registry.skill_roots())
    project_root = skill_registry.project_skill_root_for(path)
    if project_root is not None and project_root not in roots:
        roots.append(project_root)
    for entry in skill_registry.reference_targets(text):
        relative = entry['path']
        if relative is None:
            closure.append(_reference_row(entry, None, entry['kind']))
            continue
        if relative.is_absolute():
            closure.append(_reference_row(entry, relative, 'absolute'))
            continue
        reference = skill_registry.resolve_reference(path, relative)
        markdown = entry['kind'] == 'markdown'
        text_script = not markdown and _is_text_script(reference.suffix)
        within_root = any(reference.is_relative_to(root) for root in roots)
        within_folder = reference.is_relative_to(path.parent)
        if (markdown or text_script) and strict and not (within_root or within_folder):
            closure.append(_reference_row(entry, reference, 'outside'))
            raise _closure_blocked(f'SKILL 引用超出允许目录，已阻止发送：{reference}', closure)
        if not markdown and not text_script:
            closure.append(_reference_row(entry, reference, 'resource'))
            if depth == -1:
                blocks.append((reference, f'\n\n<!-- 本请求不发送该资源，本地路径：{reference} -->'))
            continue
        if not (within_root or (strict and within_folder)):
            closure.append(_reference_row(entry, reference, 'outside'))
            continue
        fragment = entry.get('fragment') or ''
        if reference in seen or (reference, fragment) in sections:
            closure.append(_reference_row(entry, reference, 'duplicate'))
            continue
        if skill_registry.condition_unmet(text, entry.get('start', 0), locks):
            closure.append(_reference_row(entry, reference, 'conditional'))
            continue
        try:
            body = reference.read_text(encoding='utf-8-sig')
        except OSError as exc:
            closure.append(_reference_row(entry, reference, 'missing'))
            raise _closure_blocked(f'SKILL 引用缺失，已阻止发送：{reference}（{exc}）',
                                   closure) from exc
        if text_script:
            block = f'\n\n## 脚本: {reference.name}\n```{reference.suffix.lstrip(".")}\n{body}\n```'
            if _charge_inline(budget, block):
                seen.add(reference)
                blocks.append((reference, block))
                closure.append(_reference_row(entry, reference, 'inlined'))
            else:
                blocks.append((reference, _skipped_inline_hint(reference)))
                closure.append(_reference_row(entry, reference, 'skipped'))
            continue
        part = skill_registry.section(body, fragment)
        if part is not None:
            block = f'\n\n## 引用: {reference.name}#{fragment}（节选）\n{part}'
            if not _charge_inline(budget, block):
                blocks.append((reference, _skipped_inline_hint(reference)))
                closure.append(_reference_row(entry, reference, 'skipped'))
                continue
            sections.add((reference, fragment))
            blocks.append((reference, block))
            closure.append(_reference_row(entry, reference, 'section'))
            if depth != 0:
                seen.add(reference)
                closure.extend(_nested_references(reference, part, seen, roots))
                closure.extend(_recurse_references(reference, part, (strict, locks, depth, blocks, seen, sections, budget)))
            else:
                closure.extend(_nested_references(reference, part, seen | {reference}, roots))
            continue
        block = f'\n\n## 引用: {reference.name}\n{body}'
        if not _charge_inline(budget, block):
            blocks.append((reference, _skipped_inline_hint(reference)))
            closure.append(_reference_row(entry, reference, 'skipped'))
            continue
        seen.add(reference)
        blocks.append((reference, block))
        closure.append(_reference_row(entry, reference, 'inlined'))
        if depth != 0:
            closure.extend(_recurse_references(reference, body, (strict, locks, depth, blocks, seen, sections, budget)))
        else:
            closure.extend(_nested_references(reference, body, seen, roots))
    return text, meta, blocks, closure
def _inline_skill_report(path, *, cap=REQUEST_CONTEXT_MAX_CHARS, strict=False, locks=None, depth=0, budget=None):
    """内联技能正文，并给出「实际加载了什么」的引用闭包，供请求快照留凭据。"""
    from html import escape
    _text, meta, blocks, closure = _skill_blocks(path, strict=strict, locks=locks, depth=depth, budget=budget)
    name = str(meta.get('name') or Path(path).resolve().parent.name)
    complete = (f'<skill name="{escape(name, quote=True)}">\n'
                + ''.join(body for _, body in blocks) + '\n</skill>')
    if len(complete) > cap:
        raise _closure_blocked(f'SKILL「{name}」内容 {len(complete):,} 字符，超过上限 {cap:,} 字符，'
                               f'已阻止发送：{Path(path).resolve()}；请减少所选技能或缩短内容。',
                               closure)
    return complete, closure
def _inline_skill(path, *, cap=REQUEST_CONTEXT_MAX_CHARS, strict=False, locks=None, depth=0, budget=None):
    """API 发送快照：技能及目录边界内的引用；``depth=-1`` 递归加载引用。"""
    return _inline_skill_report(path, cap=cap, strict=strict, locks=locks, depth=depth, budget=budget)[0]
def freeze_skills(config):
    """冻结发送内容；桌面与 API、四角色复用同一份正文，不在工作线程重读。"""
    from copy import deepcopy
    import hashlib
    from html import unescape
    frozen = deepcopy(config)
    if 'frozen_skill_prompt' in frozen:
        return frozen
    selected, loaded, bodies, references, seen = [], [], [], [], set()
    budget = _skill_inline_budget(frozen)
    for item in [*(frozen.get('stage_skills') or ()), *skills_of(frozen)]:
        path = Path(item).resolve()
        identity = os.path.normcase(str(path))
        if identity in seen:
            continue
        seen.add(identity)
        selected.append(str(path))
        try:
            body, closure = _inline_skill_report(path, strict=True, locks=frozen.get('workflow_lock') or {}, depth=-1, budget=budget)
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValueError(f'已勾选的 SKILL 或其引用未加载：{path}；已阻止发送。{exc}') from exc
        bodies.append(body)
        loaded.append({'path': str(path), 'name': unescape(body.split('"', 2)[1]),
                       'chars': len(body), 'sha256': hashlib.sha256(body.encode('utf-8')).hexdigest()})
        references.extend(dict(row, skill=str(path)) for row in closure)
    header_config = dict(frozen, skills=[], skill='', stage_skills=[])
    frozen['frozen_skill_prompt'] = skill_prompt(header_config, inline=True) + ''.join(bodies)
    from domain.writing_quality import enabled, prompt as quality_prompt
    if enabled(frozen['frozen_skill_prompt']):
        frozen['frozen_skill_prompt'] += quality_prompt()
    from contract.workflow_context_budget import prepare_request_context
    prepare_request_context(frozen['frozen_skill_prompt'], 'SKILL')
    frozen['skill_injection'] = {'mode': frozen.get('invocation_mode') or frozen.get('engine', ''),
                                'engine': frozen.get('engine', ''),
                                'model': frozen.get('model', ''),
                                'selected': selected, 'loaded': loaded,
                                'references': references}
    return frozen
def resolve_for_send(project, stage, *, config=None, intake_only=False, direct_api=False,
                     model_snapshot=None, adjust=None):
    """发送边界唯一入口：校验 → 取当前设置 → adjust 改写 → 冻结 SKILL；config 给定则沿用。"""
    freezing = stage == 'writing' and not intake_only
    if config is None:
        if freezing:
            validate_selected_skills(project, stage)
        config = current(project, stage, direct_api=direct_api, model_snapshot=model_snapshot)
        if adjust is not None:
            adjust(config)
    return freeze_skills(config) if freezing else config
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
    from contract.script_contract import production_lock_active
    definitions = {item['key']: item for item in PRODUCTION_LOCK_DEFINITIONS}
    extra = {item['key'] for item in PRODUCTION_LOCK_DEFINITIONS[5:]}
    header = ''.join('制作锁：%s=%s%s\n' % (key, value, _lock_fallback(key, value)) for key, value in locks.items()
                     if str(value).strip() and (required is None or key in required or key in extra)
                     and production_lock_active(definitions.get(key, {}), locks))
    if header:
        header += '以项目锁定值为准，不要再向用户弹问这些锁。\n'
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
    return header + ''.join(prompts)
def _one_skill_prompt(config,skill,inline=False):
    if not skill:return ''
    if inline:
        depth = -1 if config.get('stage') == 'writing' else 0
        return _inline_skill(skill, locks=config.get('workflow_lock') or {}, depth=depth,
                             budget=_skill_inline_budget(config) if depth == -1 else None)
    path=Path(skill)
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


# ── SKILL 体检（R3006 T1）：注册表问题上屏＋发送前引用闭包干跑 ──────────────
def _health_attribute(lines, by_name):
    """把 ``名字：说明`` 形式的问题／警告行归到对应 SKILL；归不了位的进全局清单。"""
    per, global_lines = {}, []
    for line in lines or ():
        text = str(line)
        head = text.split('：', 1)[0].strip()
        if head and head in by_name:
            per.setdefault(head, []).append(text)
        else:
            global_lines.append(text)
    return per, global_lines


def _health_row(skill, problems, warnings, *, locks=None):
    """单个 SKILL 的体检行：字段问题＋发送前干跑（strict、depth=-1，与 freeze 同口径）。"""
    row = {'name': skill.name, 'display_name': skill.displayName, 'stage': skill.stage,
           'layer': skill.layer, 'path': str(skill.path or ''),
           'problems': list(problems), 'warnings': list(warnings),
           'closure': [], 'chars': 0, 'char_limit': REQUEST_CONTEXT_MAX_CHARS,
           'error': None, 'status': 'ok'}
    path = getattr(skill, 'path', None)
    if path is None or not Path(path).is_file():
        row['error'] = 'SKILL 源文件不存在' if path else 'SKILL 没有源文件'
    else:
        try:
            complete, closure = _inline_skill_report(path, strict=True, locks=locks or {},
                                                     depth=-1)
        except (OSError, UnicodeError, ValueError) as exc:
            row['error'] = str(exc)
            row['closure'] = [dict(item) for item in getattr(exc, 'skill_closure', ()) or ()]
        else:
            row['chars'] = len(complete)
            row['closure'] = [dict(item) for item in closure]
    if row['error']:
        row['status'] = 'error'
    elif row['problems']:
        row['status'] = 'problem'
    elif row['warnings']:
        row['status'] = 'warning'
    return row


def skill_health_report(registry=None, *, program=None, project=None, stage=None, locks=None,
                        local_modified=None):
    """SKILL 体检报告：注册表 problems/warnings 按名归位＋每个 SKILL 的发送前引用闭包干跑。

    只读不发送、不落盘；``stage`` 给阶段 id 或中文名时只出该阶段的行，全局问题照常列出。
    闭包行沿用 ``reference_row`` 字段（kind/status/target/depth/path）；干跑失败的行带
    ``error`` 与异常附带的部分闭包（``skill_closure``）。``local_modified`` 给
    ``skill_import_service.local_modifications`` 的名字集：命中行追加
    ``local-modified`` 警告（T9 安装完整性校验，与更新检测同一判定）。
    """
    registry = registry or skill_registry.default_registry(program, project=project)
    registry.scan(force=True)
    sid = skill_registry.stage_id(stage) if stage else ''
    all_skills = registry.getAll()
    by_name = {skill.name: skill for skill in all_skills}
    problems_per, global_problems = _health_attribute(registry.problems(), by_name)
    warnings_per, global_warnings = _health_attribute(registry.warnings(), by_name)
    rows = [_health_row(skill, problems_per.get(skill.name, ()),
                        warnings_per.get(skill.name, ()), locks=locks)
            for skill in all_skills if not sid or skill.stage == sid]
    modified = set(local_modified or ())
    if modified:
        for row in rows:
            if row['name'] in modified and not any('local-modified' in w for w in row['warnings']):
                row['warnings'].append('本地已修改：已安装内容与导入台账摘要不一致'
                                       '（local-modified），更新检测不会覆盖')
                if row['status'] == 'ok':
                    row['status'] = 'warning'
    return {'skills': rows, 'problems': global_problems, 'warnings': global_warnings}
