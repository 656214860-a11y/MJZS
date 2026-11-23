"""Engine adapters; isolated per-run options, no shell command interpolation."""
import functools
import json
import subprocess
import threading
import time
import uuid
from pathlib import Path
from infra.file_cache import remove_temporary_file
from datetime import datetime
from agent.core import save,save_text,read,temporary_path,replace
import orchestrator.edit_habits as edit_habits, stage_layout
from orchestrator.workflow_settings import find_program,gui_claude_program,GUI_CLAUDE_CLI_HINT,ENGINES,skill_prompt,stage_output_contract,writer_style_prompt
from infra.workflow_process_registry import (register_process, forget_process, processes, run_registered,
                                       reserve_process_slot, release_process_slot,
                                       request_process_slot, claim_process_slot,
                                       cancel_project_slot_requests, cancel_project_requests, cancel_slot_request)
from contract.platform_tools import launch_windows_app, terminate_process_tree
from contract.workflow_context_budget import ensure_request_context
import infra.client_profiles as client_profiles
from infra import engine_probe as _engine_probe
def _stage_slot_arguments(stage):
    """阶段名（英文键或中文名）→ 槽位注册表要的 (键, 阶段并发上限, 全局上限, 显示名)。"""
    from contract.pet_bus import STAGE_NAMES
    from orchestrator.stage_parallel import GLOBAL_LIMIT, concurrency_limit, label
    value = str(stage or '')
    key = next((name for name, text in STAGE_NAMES.items() if value in (name, text)), value)
    key = {'writing': 'script', 'frames': 'keyframe', 'video_prompt': 'video'}.get(key, key)
    return key, concurrency_limit(key), GLOBAL_LIMIT, label(key)


def reserve_stage_process_slot(project, stage):
    """L3 在唯一并行配置上计算模型进程容量，L1 注册表只保存槽位。"""
    return reserve_process_slot(project, *_stage_slot_arguments(stage))

def request_stage_process_slot(project, stage):
    """申请交互模型槽位：满额时返回排队票据，调用方可在 UI 空闲时轮询。"""
    return request_process_slot(project, *_stage_slot_arguments(stage))

def claim_stage_process_slot(ticket):
    return claim_process_slot(ticket)

def release_stage_process_slot(slot):
    """释放阶段模型槽位，供短生命周期 API 调用在完成后归还容量。"""
    release_process_slot(slot)

def cancel_stage_slot_requests(project):
    """撤销项目尚未获得槽位的阶段模型请求。"""
    return cancel_project_slot_requests(project)


def cancel_stage_slot_request(ticket):
    """取消调用方持有的单个排队票据。"""
    return cancel_slot_request(ticket)

def prompt_with_settings(prompt,config,stage=None):
    extra=config.get('instructions','')
    language=('\n统一语言要求：所有面向用户的回复、剧本、分镜描述、资产外观、正负向提示词、首帧图片提示词、视频提示词及制作说明，统一使用简体中文。'
              '技术字段名、资产和镜头编号、模型 ID、文件路径、程序代码及必须保持原样的专有标识保留原文。'
              '引用已有英文内容时，本次新交付的自然语言内容须忠实转为中文，保留动作、构图和连续性要求；不要因为翻译重做已完成素材。'
              '此语言要求同样适用于所选 Skill，不沿用其默认英文输出示例。\n')
    # 第 47 期第 2 条：Blender 一律后台跑（blender --background），不要再弹桌面窗口——
    # 白模那一批的进度由助手打开的本地监视页（浏览器）显示；ComfyUI 照旧保留桌面工作流。
    media_apps=('\n本地制作软件：需要 ComfyUI 时，打开本机已安装的桌面程序供用户操作，'
                'ComfyUI 可经本机 API 执行任务，同时保留桌面工作流；不要只打开浏览器地址。'
                '需要 Blender 时一律用后台方式（blender --background）制作与渲染，不要打开 Blender 桌面窗口；'
                '本次的进度由助手打开的本地制作监视页（浏览器）显示，用户要改工程时会自己把 .blend 调出来。\n')
    stage = stage if stage is not None else config.get('stage')
    if stage not in ('assets', 'frames', 'keyframe', 'previs', 'video_prompt', 'video'):
        media_apps = ''
    return skill_prompt(config, stage=stage)+stage_output_contract(stage)+writer_style_prompt(config,stage)+edit_habits.prompt(config,stage)+prompt+REPLY_FORMAT_RULE+('\n用户补充制作要求：\n'+extra if extra else '')+language+media_apps

def _client_profile(config):
    found = client_profiles.profile_for_config(config)
    if not found:
        raise ValueError('未识别本地客户端；请在模型管理重新点「检测」或手动指定 .exe')
    return found


def _client_command(config, project, output, report, prompt_file='', prompt=''):
    item = _client_profile(config)
    if not item.get('invoke'):
        raise ValueError('该命令行程序未识别投递参数；请改用手动制作入口打开交互式窗口，或在模型管理重新检测')
    exe = find_program(config)
    args = client_profiles.executable_command(item, exe)
    args += client_profiles.build_invocation(item, prompt, prompt_file,
                                             title=str(config.get('title') or ''),
                                             model=str(config.get('model') or ''))
    if not args:
        raise ValueError('该命令行程序未识别可用参数；请改用手动制作入口打开交互式窗口')
    return args


def background_command(config,project,output,report,prompt_file=None,*,prompt=''):
    if config['engine'] == 'client-cli':
        return _client_command(config, project, output, report, prompt_file or '', prompt)
    if config['engine'] in ('claude-desktop-app', 'desktop-app'):
        raise ValueError(ENGINES[config['engine']]+' 需要在桌面窗口中手动发送，请使用手动制作入口')
    exe=find_program(config)
    if config['engine']=='claude' and gui_claude_program(exe):raise ValueError(GUI_CLAUDE_CLI_HINT)
    if config['engine']=='opencode':
        if not prompt_file:raise ValueError('OpenCode 后台调用缺少提示词文件')
        args=[exe,'run','--auto','--format','json']
        if config.get('model'):args+=['-m',config['model']]
        args+=['--file',str(Path(prompt_file)),'执行附件中的制作任务']
        return args
    if config['engine']=='codex':
        resume = config.get('resume_session')
        if resume:
            # codex 的续跑是 exec 的子命令：codex exec resume <session_id> <prompt>（prompt 用 - 走 stdin）。
            args=[exe,'exec','resume',str(resume),'--skip-git-repo-check','--sandbox','workspace-write','--cd',str(project),'--add-dir',str(output),'--color','never','--json','-o',str(report)]
        else:
            args=[exe,'exec','--skip-git-repo-check','--sandbox','workspace-write','--cd',str(project),'--add-dir',str(output),'--color','never','--json','-o',str(report)]
    else:
        args=[exe,'-p','--output-format','json','--permission-mode','auto','--add-dir',str(output)]
        # claude 的续跑是 -p 的 flag：claude -p --resume <session_id>。
        resume = config.get('resume_session')
        if resume:
            args += ['--resume', str(resume)]
        else:
            # 后台调用主动指定 session id（--session-id），跑完持久化，失败重试用 --resume 续上下文；
            # 与 launch_interactive 的 claude 分支同一机制。uuid 回写 config['session_id'] 供 run_background 持久化。
            session_id = config.get('session_id') or str(uuid.uuid4())
            args += ['--session-id', session_id]
            config['session_id'] = session_id
    # 勾选的 SKILL 目录一并授权给 CLI 模型，让模型能读全文、看图、跑脚本（等效 desktop 原生）。
    from orchestrator.workflow_settings import skill_roots_for_config
    for directory in skill_roots_for_config(config):
        args += ['--add-dir', str(directory)]
    if config.get('model'):args+=['--model',config['model']]
    if config['engine']=='codex':args+=['-']
    return args

def running(project):
    """本项目当前还在跑的引擎进程：已经退出的当场清掉，避免越积越多。"""
    items=processes(project)
    alive=[process for process in items if process.poll() is None]
    for process in items:
        if process not in alive:forget_process(project,process)
    return alive


def terminate(project):
    """强制结束本项目正在跑的引擎进程（连同子进程），供「强制停止制作」使用。

    只结束本项目登记过的进程，不按进程名乱杀：同名 CLI 可能是用户自己的对话窗口；
    返回被结束的进程号列表，空列表代表当前没有可结束的制作进程。
    """
    cancel_project_slot_requests(project)
    cancel_project_requests(project)
    killed=[]
    for process in running(project):
        terminate_process_tree(process)
        # taskkill 的命令本身返回时，目标进程在某些 Windows 会话里仍处于退出中。
        # 「强制停止」只有等到登记的父进程真正收束，才可以让调用方开始下一批任务。
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        forget_process(project,process)
        killed.append(process.pid)
    return killed


# 一次后台制作的最长等待：CLI 卡死时到点结束进程树、让出阶段槽位；阶段配置可用 timeout_seconds 改。
ENGINE_TIMEOUT_SECONDS = 2 * 3600


def engine_timeout(config):
    return config.get('timeout_seconds') or ENGINE_TIMEOUT_SECONDS


def _run(args,project,prompt,stdout,stderr,timeout=ENGINE_TIMEOUT_SECONDS,on_output=None):
    """启动引擎进程并登记：只有登记过的进程才会被「强制停止制作」结束。

    ``on_output`` 可选：逐行流式回调 ``on_output(line, stream)``（stream 为 'stdout'/'stderr'），
    见 ``run_registered``；同时仍会把读到的行写回 ``stdout``/``stderr`` 文件对象（若有）。
    """
    return run_registered(args,project,prompt,(stdout,stderr),timeout,timeout_label='引擎运行超时',
                          options={'on_output': on_output})


def _opencode_prompt_file(report):
    return Path(report).with_suffix('.opencode-prompt.md').resolve()


def _opencode_report_text(raw):
    parts=[]
    for number,line in enumerate(raw.splitlines(),1):
        line=line.strip()
        if not line:continue
        try:event=json.loads(line)
        except ValueError as exc:
            raise ValueError('OpenCode 事件流第 %d 行不是有效 JSON，请查看运行日志' % number) from exc
        if not isinstance(event,dict):
            raise ValueError('OpenCode 事件流第 %d 行不是 JSON 对象，请查看运行日志' % number)
        if event.get('type')!='text':continue
        part=event.get('part') or {}
        text=part.get('text') if isinstance(part,dict) else None
        if isinstance(text,str):parts.append(text)
    return ''.join(parts).strip()


def _run_opencode(config,project,output,report,logfile,prompt):
    prompt_file=_opencode_prompt_file(report)
    save_text(prompt_file,prompt)
    response=Path(report).with_suffix('.response.jsonl')
    response_temp=temporary_path(response)
    try:
        with response_temp.open('w',encoding='utf-8') as out, Path(logfile).open('w',encoding='utf-8') as log:
            returncode=_run(background_command(config,project,output,report,prompt_file),project,'',out,log,engine_timeout(config))
        if returncode:
            replace(response_temp,response)
            raise ValueError('OpenCode CLI 执行失败（退出码 %s），请查看运行日志（安装版本、登录、额度或权限）' % returncode)
        report_text=_opencode_report_text(response_temp.read_text(encoding='utf-8-sig'))
        if not report_text:
            replace(response_temp,response)
            raise ValueError('OpenCode 未返回制作报告正文，请查看响应记录')
        replace(response_temp,response)
        save_text(Path(report),report_text)
    finally:
        if response_temp.exists():remove_temporary_file(response_temp)


def _run_claude_json(args,project,prompt,log,report,timeout=ENGINE_TIMEOUT_SECONDS,on_output=None):
    """Claude 以 JSON 输出运行：响应落临时文件，成功后转正并写制作报告。

    ``on_output`` 可选：透传给 ``_run``；注意 Claude 的 stdout 是 JSON 响应、stderr 才是
    运行日志，调用方应按 ``stream`` 过滤，只把 stderr 当实时日志显示。
    """
    response=Path(report).with_suffix('.response.json')
    response_temp=temporary_path(response)
    try:
        with response_temp.open('w',encoding='utf-8') as out:
            returncode=_run(args,project,prompt,out,log,timeout,on_output=on_output)
        if returncode==0:
            result=json.loads(response_temp.read_text(encoding='utf-8-sig'))
            replace(response_temp,response)
            report_text = str(result.get('result', '')).strip()
            if not report_text:
                raise ValueError('Claude 未返回制作报告正文，请查看响应记录')
            save_text(Path(report), report_text)
            if result.get('is_error') or result.get('permission_denials'):
                raise ValueError('Claude 未完成任务或所需操作未获授权，请查看制作报告及响应记录')
    finally:
        if response_temp.exists():remove_temporary_file(response_temp)
    return returncode

def run_background(config,project,output,report,logfile,prompt,on_output=None):
    """后台无人值守跑 CLI 引擎；``on_output`` 可选，逐行流式回调 ``on_output(line, stream)``。

    codex 的 stdout/stderr 都是运行日志；claude 的 stdout 是 JSON 响应、stderr 是运行日志，
    调用方应按 ``stream`` 过滤。透传给 ``_run``／``_run_claude_json``。
    """
    prompt=ensure_request_context(prompt, config.get('stage', '当前阶段'))
    stage = config.get('stage', '当前阶段')
    # 失败重试续跑：调用方没显式给 resume_session 时，回读上次后台会话绑定。
    if config.get('engine') in ('codex', 'claude') and not config.get('resume_session'):
        config = dict(config)
        config['resume_session'] = load_background_session(project, stage, config['engine'])
    slot=reserve_stage_process_slot(project, stage)
    try:
        if config['engine']=='client-cli':
            prompt_file=Path(report).with_suffix('.client-prompt.md')
            save_text(prompt_file,prompt)
            args=background_command(config,project,output,report,prompt_file,prompt=prompt)
            response=Path(report).with_suffix('.client-response.txt')
            response_temp=temporary_path(response)
            item=_client_profile(config)
            try:
                with response_temp.open('w',encoding='utf-8') as out, Path(logfile).open('w',encoding='utf-8') as log:
                    returncode=_run(args,project,client_profiles.stdin_text(item,prompt),out,log,engine_timeout(config))
                text=response_temp.read_text(encoding='utf-8-sig').strip()
                replace(response_temp,response)
                if returncode:
                    raise ValueError('%s 执行失败（退出码 %s）；任务文件已保留，请查看运行日志或改用交互式窗口'
                                     % (item['display'],returncode))
                if not text:
                    raise ValueError('%s 未返回制作报告正文；请查看运行日志或改用交互式窗口' % item['display'])
                save_text(Path(report),text)
            finally:
                if response_temp.exists():remove_temporary_file(response_temp)
            return None
        if config['engine']=='qwen':
            from orchestrator.qwen_adapter import run_background as run_qwen
            return run_qwen(config,project,output,report,logfile,prompt)
        if config['engine']=='opencode':
            return _run_opencode(config,project,output,report,logfile,prompt)
        args=background_command(config,project,output,report)
        with Path(logfile).open('w',encoding='utf-8') as log:
            if config['engine']=='codex':
                # 边流式显示边从 --json 输出解析 thread_id（thread.started 事件），跑完后持久化供 resume。
                # stdout 是 JSONL：只把 agent_message 正文交给 on_output，机器事件（thread/turn/usage）滤掉，
                # 这样监视页看到的是人读回复，而不是 JSON 行。
                captured = {'thread_id': None}
                returncode = _run(args, project, prompt, log, log, engine_timeout(config),
                                  on_output=functools.partial(_codex_stream_output, captured, on_output))
                if returncode == 0 and captured['thread_id']:
                    save_background_session(project, stage, 'codex', captured['thread_id'])
            else:
                returncode=_run_claude_json(args,project,prompt,log,report,engine_timeout(config),on_output=on_output)
                if returncode == 0 and config.get('session_id'):
                    save_background_session(project, stage, 'claude', config['session_id'])
        if returncode:raise ValueError(ENGINES[config['engine']]+' 执行失败，请查看运行日志（安装版本、登录、额度或权限）')
    finally:
        release_process_slot(slot)


def _codex_stream_output(captured, on_output, line, stream):
    """codex --json 输出逐行回调：stdout 提取 thread_id + 人读正文，stderr 原样透传。

    从 ``run_background`` 提为模块级函数，压平 ``run_background`` 的嵌套深度（闭包会抬高复杂度棘轮计数）。
    ``captured`` 是可变字典，回调期间把 thread.started 事件的 thread_id 写进去供跑完后持久化。
    """
    if stream == 'stdout':
        tid = extract_codex_thread_id(line)
        if tid:
            captured['thread_id'] = tid
        if on_output is not None:
            message = extract_codex_message_text(line)
            if message:
                on_output(message + '\n', 'stdout')
        return
    if on_output is not None:
        on_output(line, stream)


def extract_codex_thread_id(line):
    """从 codex exec --json 的一行 JSONL 里取出 thread_id（thread.started 事件），否则 None。

    实证（codex v0.169.0）：``{"type":"thread.started","thread_id":"<uuid>"}``，thread_id 即
    session id，供 ``codex exec resume <id>`` 续跑。
    """
    text = str(line or '').strip()
    if not text:
        return None
    try:
        event = json.loads(text)
    except ValueError:
        return None
    if not isinstance(event, dict) or event.get('type') != 'thread.started':
        return None
    thread_id = event.get('thread_id')
    return str(thread_id) if thread_id else None


def extract_codex_message_text(line):
    """从 codex exec --json 的一行 JSONL 里取出 agent 回复正文，否则 None。

    实证：``{"type":"item.completed","item":{"type":"agent_message","text":"..."}}``；
    非 agent_message 事件（thread.started／turn.*／usage 等）返回 None，便于流式显示只留正文。
    """
    text = str(line or '').strip()
    if not text:
        return None
    try:
        event = json.loads(text)
    except ValueError:
        return None
    if not isinstance(event, dict) or event.get('type') != 'item.completed':
        return None
    item = event.get('item')
    if not isinstance(item, dict) or item.get('type') != 'agent_message':
        return None
    body = item.get('text')
    return str(body) if body else None


def _background_session_path(project):
    """后台引擎会话绑定文件：``<项目>/工作流任务/后台引擎会话.json``（按 engine + stage 存 session id）。"""
    return stage_layout.workflow_dir(project, '后台引擎会话.json')


def save_background_session(project, stage, engine, session_id):
    """记录后台引擎某阶段跑完后的 session id，供失败重试 resume；不同 engine 互不覆盖。

    会话绑定只是失败重试的辅助记录：绑定文件损坏按空记录重建，写不动也不把
    已经成功的一轮变成失败。
    """
    path = _background_session_path(project)
    try:
        try:
            data = read(path) if path.is_file() else {}
        except (OSError, ValueError, TypeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        entry = data.get(stage)
        if not isinstance(entry, dict):
            entry = {}
        entry[engine] = session_id
        data[stage] = entry
        save(path, data)
    except (OSError, ValueError, TypeError):
        import infra.app_logging as app_logging
        app_logging.swallowed('后台引擎会话绑定落盘')


def load_background_session(project, stage, engine):
    """读取后台引擎某阶段上次的 session id；无记录返回 None。"""
    path = _background_session_path(project)
    if not path.is_file():
        return None
    try:
        data = read(path)
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    entry = data.get(stage)
    if not isinstance(entry, dict):
        return None
    value = entry.get(engine)
    return str(value) if value else None


# 隔夜续接的旧 Claude 会话会把已删除的旧稿带回上下文；超过该时长不再续接，改开新会话。
CLAUDE_SESSION_STALE_SECONDS = 12 * 3600

def claude_session_stale(project, stage, now=None):
    """绑定的 Claude 会话记录最后写入超过阈值即视为过期；无绑定或无记录不算过期。"""
    bindings = stage_layout.workflow_dir(project, 'Claude对话.json')
    try:
        data = read(bindings) if bindings.is_file() else {}
        session = str(uuid.UUID(str(data.get(stage)))) if isinstance(data, dict) and data.get(stage) else None
    except (OSError, ValueError, TypeError):
        return False
    if not session:
        return False
    latest = 0.0
    for path in (Path.home() / '.claude/projects').glob('*/' + session + '.jsonl'):
        try:
            latest = max(latest, path.stat().st_mtime)
        except OSError:
            continue
    now = time.time() if now is None else now
    return bool(latest) and now - latest > CLAUDE_SESSION_STALE_SECONDS

def launch_interactive(project,stage,title,prompt,config,followup=None,slot=None,*,new_session=False):
    """Custom engines use a real interactive CLI, preserving creative Q&A."""
    prompt=ensure_request_context(prompt, stage)
    if config['engine'] == 'desktop-app':
        raise ValueError('Desktop 模型请通过桌面发送入口打开，不支持命令行参数')
    if config['engine'] == 'client-cli':
        item=_client_profile(config);project=Path(project)
        folder=stage_layout.workflow_dir(project,'交互任务')/stage/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        folder.mkdir(parents=True)
        task=folder/'任务.md';save_text(task,prompt);save(folder/'调用配置.json',config)
        exe=find_program(config)
        args=client_profiles.executable_command(item,exe)
        args+=client_profiles.build_invocation(item,prompt,str(task),title=title,
                                               model=str(config.get('model') or ''))
        slot=slot or reserve_stage_process_slot(project, stage)
        try:
            process=launch_windows_app(args[0],item['display'],args=args,cwd=project,
                                       creationflags=getattr(subprocess,'CREATE_NEW_CONSOLE',0))
        except (ValueError, OSError) as exc:
            release_process_slot(slot)
            raise ValueError('本机命令行客户端无法启动；任务已保存到 %s，请手动打开并粘贴。' % task) from exc
        except BaseException:
            release_process_slot(slot)
            raise
        process.workflow_process_slot=slot
        register_process(project,process)
        process.agent_folder=folder;process.agent_engine='client-cli'
        reason=('已按档案参数启动 '+item['display']+'，任务已提交。'
                if item.get('invoke') else
                '未识别该客户端的参数，已打开交互式窗口；任务已保存到 %s，请在该窗口手动粘贴或打开任务文件。' % task)
        return {'engine':item['display'],'task_file':str(task),'process':process,'reason':reason}
    if config['engine'] == 'opencode':
        raise ValueError('OpenCode CLI 仅支持后台制作入口；请使用手动／后台运行，不支持交互启动')
    if config['engine']=='qwen':
        slot=slot or reserve_stage_process_slot(project, stage)
        try:
            from orchestrator.qwen_adapter import launch_interactive as launch_qwen
            result=launch_qwen(project,stage,title,prompt,config,followup)
            result['process'].workflow_process_slot=slot
            return result
        except Exception:
            release_process_slot(slot)
            raise
    if config['engine'] == 'claude-desktop-app':
        raise ValueError('Claude Desktop 请通过桌面发送入口打开，不支持 Claude Code 命令行参数')
    exe=find_program(config);project=Path(project)
    if config['engine']=='claude' and gui_claude_program(exe):raise ValueError(GUI_CLAUDE_CLI_HINT)
    folder=stage_layout.workflow_dir(project,'交互任务')/stage/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    folder.mkdir(parents=True)
    task=folder/'任务.md';save_text(task,prompt);save(folder/'调用配置.json',config)
    initial=f'请将任务命名为“{title}”，完整读取并执行任务文件：{task}。需要讨论时在本对话继续。'
    if config['engine']=='codex':
        from codex_tasks import prepare_task
        prepared=prepare_task(project,title,stage,prompt,followup=followup)
        args=[exe]
        if prepared['mode']=='existing':
            args+=['resume',prepared['url'].rsplit('/',1)[-1]]
        initial=prepared['prompt']
        args+=['--cd',str(project),'--sandbox','workspace-write']
    else:
        bindings=stage_layout.workflow_dir(project,'Claude对话.json')
        data=read(bindings) if bindings.is_file() else {}
        if not isinstance(data,dict):data={}
        session=data.get(stage)
        try:session=str(uuid.UUID(str(session))) if session else None
        except ValueError:session=None
        persisted=bool(not new_session and session and any((Path.home()/'.claude/projects').glob('*/'+session+'.jsonl')))
        if persisted:
            args=[exe,'--resume',session]
            if followup is not None:save_text(task,followup)
            initial=f'请读取本次新任务：{task}，在当前对话继续。'
        else:
            session=str(uuid.uuid4());args=[exe,'--session-id',session,'--name',title]
        data[stage]=session;save(bindings,data)
    if config.get('model'):args+=['--model',config['model']]
    args+=[initial]
    slot=slot or reserve_stage_process_slot(project, stage)
    try:
        process=launch_windows_app(args[0], ENGINES[config['engine']], args=args, cwd=project,
                                   creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))
    except ValueError as exc:
        if not isinstance(exc.__cause__, OSError):
            release_process_slot(slot)
            raise
        fallback=config.get('api_fallback') if isinstance(config,dict) else None
        api=(fallback or {}).get('api') if isinstance(fallback,dict) else None
        # Qwen Code 的自定义接口是 OpenAI 兼容协议；不能把 Anthropic 原生请求伪装成它。
        if not fallback or not isinstance(api,dict) or api.get('wire_api','chat') not in ('chat','responses'):
            release_process_slot(slot)
            raise ValueError('本机 Agent 无法启动；未配置可兼容的 API 回退，请检查本机客户端或模型管理。') from exc
        fallback_config={'engine':'qwen', **dict(fallback.get('profile') or {}),
                         'model':fallback.get('model',''), 'api':api}
        from orchestrator.qwen_adapter import launch_interactive as launch_qwen
        release_process_slot(slot)
        return launch_interactive(project,stage,title,prompt,fallback_config,followup)
    except BaseException:
        release_process_slot(slot)
        raise
    # 交互窗口也是本应用派发的制作任务；登记后关闭应用能收掉它及其子进程。
    process.workflow_process_slot=slot
    register_process(project,process)
    process.agent_folder=folder;process.agent_engine=config['engine']
    return {'engine':ENGINES[config['engine']],'task_file':str(task),'process':process}

def close_for_restart(project, process):
    """Only exit an idle owned CLI; never interrupt generation or discard a draft."""
    if process.poll() is None:
        from console_submit import send
        result = send(process.pid, '/exit')
        if not result['ok']:
            raise ValueError(result['reason'])
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired as exc:
            raise ValueError('旧 Claude 窗口尚未退出；请检查窗口后重试，本次未启动重复请求。') from exc
    forget_process(project, process)


def _engine_probe_command_builder(config, project, output, report):
    """I3b：把 background_command 登记给 L1 engine_probe（迟绑定，mock 补丁面不变）。"""
    return background_command(config, project, output, report)


def submit_existing(process,prompt,title=None):
    """Continue the exact CLI process using a short immutable task-file message."""
    if process.poll() is not None:raise ValueError('Agent 窗口已关闭，请重新打开')
    folder=Path(process.agent_folder)
    task=folder/('任务_'+uuid.uuid4().hex[:12]+'.md');save_text(task,prompt)
    message=f'请完整读取并执行本次任务文件：{task}。仅执行本次指定任务，沿用已有成果。'
    from console_submit import send
    return send(process.pid,message)


def current_config(project, stage):
    """供 L3 编排读取实际引擎配置；复用引擎模块既有的设置依赖边界。"""
    from orchestrator.workflow_settings import current
    return current(project, stage)


# I3b（L1 任务书）：engine_probe 不再反向 import 本模块；导入本模块即完成注入，
# 未导入时 engine_probe 返回明确的「未配置」结果。
_engine_probe.register_command_builder(_engine_probe_command_builder)

# 对话回复／进度汇报／失败说明的组织约束；产物（剧本、分镜、JSON）明确排除（REQ／DES-S01-108）。
# 放在文件末尾，避免上移 launch_windows_app 行号触及进程启动点登记。
REPLY_FORMAT_RULE = (
    '\n回话组织要求：对话回复、进度汇报、失败说明请先给结论；再分点说明；最后给出下一步。'
    '本要求不适用于剧本、分镜、JSON 等产物，产物仍按各自输出契约。\n'
)


def terminate_all(timeout=3.0):
    """结束所有项目登记的、退出时应收掉的制作进程（不含 detached）。

    先对每个候选 ``terminate_process_tree``，再在总 ``timeout`` 秒内统一等待；
    到点仍活着的 ``kill``；逐个 ``forget_process``。涉及项目各取消一次排队与直连请求。
    放在文件末尾，避免上移 ``launch_windows_app`` 行号触及进程启动点登记。
    """
    import infra.app_logging as app_logging
    from infra.workflow_process_registry import exit_candidates as _exit_candidates
    candidates = _exit_candidates()
    if not candidates:
        return []
    seen = set()
    for project, _process in candidates:
        if project in seen:
            continue
        seen.add(project)
        cancel_project_slot_requests(project)
        cancel_project_requests(project)
    for _project, process in candidates:
        terminate_process_tree(process)
    deadline = time.monotonic() + max(0.0, float(timeout))
    killed = []
    for project, process in candidates:
        if process.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining > 0:
                try:
                    process.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    pass
            if process.poll() is None:
                try:
                    process.kill()
                    process.wait(timeout=3)
                except Exception:
                    app_logging.swallowed()
        forget_process(project, process)
        killed.append(process.pid)
    return killed
