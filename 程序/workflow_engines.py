"""Engine adapters; isolated per-run options, no shell command interpolation."""
import json
import subprocess
import threading
import time
import uuid
from pathlib import Path
from file_cache import remove_temporary_file
from datetime import datetime
from agent.core import save,save_text,read,temporary_path,replace
from workflow_settings import find_program,gui_claude_program,GUI_CLAUDE_CLI_HINT,ENGINES,skill_prompt,stage_output_contract,writer_style_prompt,master_gate
from workflow_process_registry import (register_process, forget_process, processes,
                                       reserve_process_slot, release_process_slot,
                                       request_process_slot, claim_process_slot,
                                       cancel_project_slot_requests, cancel_slot_request)
from platform_tools import hidden_console_flags, launch_windows_app, terminate_process_tree
from workflow_context_budget import ensure_request_context
import client_profiles


def _stage_slot_arguments(stage):
    """阶段名（英文键或中文名）→ 槽位注册表要的 (键, 阶段并发上限, 全局上限, 显示名)。"""
    from pet_bus import STAGE_NAMES
    from stage_parallel import GLOBAL_LIMIT, concurrency_limit, label
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
    blocked=master_gate(config,stage)
    if blocked:raise ValueError(blocked)
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
    return skill_prompt(config, stage=stage)+stage_output_contract(stage)+writer_style_prompt(config,stage)+prompt+('\n用户补充制作要求：\n'+extra if extra else '')+language+media_apps

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
        args=[exe,'exec','--skip-git-repo-check','--sandbox','workspace-write','--cd',str(project),'--add-dir',str(output),'--color','never','-o',str(report)]
    else:
        args=[exe,'-p','--output-format','json','--permission-mode','auto','--add-dir',str(output)]
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


def _run(args,project,prompt,stdout,stderr):
    """启动引擎进程并登记：只有登记过的进程才会被「强制停止制作」结束。"""
    key=str(project)
    process=subprocess.Popen(args,stdin=subprocess.PIPE,text=True,encoding='utf-8',errors='replace',
                             stdout=stdout,stderr=stderr,cwd=project,creationflags=hidden_console_flags())
    register_process(key,process)
    try:process.communicate(prompt)
    except BaseException:
        # 异常打断（含 Ctrl+C）时进程可能还在跑；先结束再注销，否则它脱离登记表后「强制停止」找不到。
        terminate_process_tree(process)
        raise
    finally:forget_process(key,process)
    return process.returncode


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
            returncode=_run(background_command(config,project,output,report,prompt_file),project,'',out,log)
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


def _run_claude_json(args,project,prompt,log,report):
    """Claude 以 JSON 输出运行：响应落临时文件，成功后转正并写制作报告。"""
    response=Path(report).with_suffix('.response.json')
    response_temp=temporary_path(response)
    try:
        with response_temp.open('w',encoding='utf-8') as out:
            returncode=_run(args,project,prompt,out,log)
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

def run_background(config,project,output,report,logfile,prompt):
    prompt=ensure_request_context(prompt, config.get('stage', '当前阶段'))
    slot=reserve_stage_process_slot(project, config.get('stage', '当前阶段'))
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
                    returncode=_run(args,project,client_profiles.stdin_text(item,prompt),out,log)
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
            from qwen_adapter import run_background as run_qwen
            return run_qwen(config,project,output,report,logfile,prompt)
        if config['engine']=='opencode':
            return _run_opencode(config,project,output,report,logfile,prompt)
        args=background_command(config,project,output,report)
        with Path(logfile).open('w',encoding='utf-8') as log:
            if config['engine']=='codex':
                returncode=_run(args,project,prompt,log,log)
            else:
                returncode=_run_claude_json(args,project,prompt,log,report)
        if returncode:raise ValueError(ENGINES[config['engine']]+' 执行失败，请查看运行日志（安装版本、登录、额度或权限）')
    finally:
        release_process_slot(slot)

# 隔夜续接的旧 Claude 会话会把已删除的旧稿带回上下文；超过该时长不再续接，改开新会话。
CLAUDE_SESSION_STALE_SECONDS = 12 * 3600

def claude_session_stale(project, stage, now=None):
    """绑定的 Claude 会话记录最后写入超过阈值即视为过期；无绑定或无记录不算过期。"""
    bindings = Path(project) / '工作流任务' / 'Claude对话.json'
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
        folder=project/'工作流任务'/'交互任务'/stage/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
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
        except ValueError as exc:
            release_process_slot(slot)
            raise ValueError('本机命令行客户端无法启动；任务已保存到 %s，请手动打开并粘贴。' % task) from exc
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
            from qwen_adapter import launch_interactive as launch_qwen
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
    folder=project/'工作流任务'/'交互任务'/stage/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
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
        bindings=project/'工作流任务'/'Claude对话.json'
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
        from qwen_adapter import launch_interactive as launch_qwen
        release_process_slot(slot)
        return launch_interactive(project,stage,title,prompt,fallback_config,followup)
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
    from workflow_settings import current
    return current(project, stage)
