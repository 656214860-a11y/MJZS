"""Qwen Code adapter: official CLI, explicit session IDs and JSONL input."""
import hashlib,json,os,subprocess,time,uuid,re,threading
from pathlib import Path
import stage_layout
import client_profiles
from file_cache import remove_temporary_file
from agent.core import read,save,save_text,temporary_path,replace
from platform_tools import launch_windows_app
from workflow_context_budget import ensure_request_context

# 比 --max-wall-time 2h 多留 10 分钟：CLI 自己的时限先生效，它卡死时由这里兜底。
TIMEOUT_SECONDS = 2 * 3600 + 600

def command(config):
    return client_profiles.qwen_command(config)

def setup_key(config):return hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()

def window_title(project_name,stage,page_index=None):
    """Qwen 窗口标题：页号 ＋ 阶段名 ＋ 项目名。

    第 62 期任务 11：页号与阶段名都从阶段表推（pet_state），一个数字都不写死。
    page_index 是用户点下去的那一页——同一个阶段在别页上跑时（首帧管理页里跑资产复核、
    视频生成页里跑分镜提示词），标题跟着那一页走。
    """
    import pet_state
    sid={'writing':'script','frames':'keyframe','video_prompt':'video'}.get(stage,stage)
    index=pet_state.PAGE_OF.get(sid)
    if page_index is not None:
        try:index=int(page_index)
        except (TypeError,ValueError):pass
    stages=pet_state.STAGES
    label=(str(stage) if index is None or not 0<=index<len(stages)
           else '%02d %s'%(index+1,pet_state.STAGE_NAMES.get(stages[index],stage)))
    name=' '.join(re.sub(r'[\x00-\x1f\x7f-\x9f]',' ',str(project_name)).split())[:48]
    return f'{label}｜{name}｜Qwen'


def wait_ready(process):
    if process.poll() is not None:raise ValueError('Qwen 窗口已关闭，请重新点击制作按钮')
    deadline=time.monotonic()+20
    while not process.qwen_events.is_file() or not process.qwen_events.stat().st_size or time.monotonic()-process.qwen_started<3:
        if process.poll() is not None:raise ValueError('Qwen 启动未完成，请检查 Qwen 窗口中的 API 配置提示')
        if time.monotonic()>deadline:raise ValueError('Qwen 尚未就绪，任务未重复发送；请等待窗口初始化后重试')
        time.sleep(.25)


def append_input(process,prompt=None,title=None):
    # Keep a stage rename and its task in the same ordered append. This is Qwen's
    # local /rename command, without --auto, so naming never invokes a model.
    with process.qwen_input_lock:
        if title is not None:process.qwen_title=title
        desired=process.qwen_title
        rename=bool(desired and desired!=process.qwen_renamed_title)
        texts=([f'/rename -- {desired}'] if rename else [])+([prompt] if prompt is not None else [])
        if not texts:return
        with process.qwen_input.open('a',encoding='utf-8',newline='\n') as file:
            for text in texts:file.write(json.dumps({'type':'submit','text':text},ensure_ascii=False)+'\n')
            file.flush();os.fsync(file.fileno())
        if rename:process.qwen_renamed_title=desired


def name_when_ready(process):
    try:
        wait_ready(process);append_input(process)
    except (ValueError,OSError) as exc:
        # Naming is retried by the next normal submission; it must not resubmit
        # the initial production task or interrupt an already running task.
        process.qwen_title_error=str(exc)


def launch_interactive(project,stage,title,prompt,config,followup=None):
    ensure_request_context(prompt, stage)
    from qwen_setup import environment
    env=environment(config.get('model',''),config.get('api'));project=Path(project)
    title=' '.join(re.sub(r'[\x00-\x1f\x7f-\x9f]',' ',str(title)).split())[:80]
    env['CLI_TITLE']=title
    bindings=stage_layout.workflow_dir(project,'Qwen对话.json');info=read(bindings) if bindings.is_file() else {}
    if not isinstance(info,dict):info={}
    entry=info.get(stage,{})
    session=None
    try:
        if entry.get('events') and Path(entry['events']).is_file() and Path(entry['events']).stat().st_size:
            session=str(uuid.UUID(entry['session_id']))
    except (KeyError,ValueError,OSError):pass
    key=setup_key(config)
    if session and entry.get('setup_key')==key and followup is not None:prompt=followup
    folder=stage_layout.workflow_dir(project,'交互任务')/stage/('Qwen_'+uuid.uuid4().hex[:12]);folder.mkdir(parents=True)
    task=folder/'任务.md';save_text(task,prompt)
    incoming=folder/'输入.jsonl';incoming.touch();events=folder/'事件.jsonl'
    args=command(config)+['--auth-type','openai','--model',config.get('model') or env['OPENAI_MODEL'],'--approval-mode','auto',
        '--input-file',str(incoming),'--json-file',str(events),'--chat-recording']
    from workflow_settings import skill_roots_for_config
    for directory in skill_roots_for_config(config):
        args+=['--include-directories',str(directory)]
    if session:args+=['--resume',session]
    else:session=str(uuid.uuid4());args+=['--session-id',session]
    args+=['--prompt-interactive',f'本次流程：{title}。完整读取并执行任务文件：{task}。后续任务在当前对话继续。']
    process=launch_windows_app(args[0], 'Qwen Code', args=args, cwd=project, env=env,
                               creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))
    from workflow_process_registry import register_process
    register_process(project, process)
    process.qwen_input=incoming;process.qwen_events=events;process.qwen_folder=folder;process.qwen_started=time.monotonic()
    process.qwen_input_lock=threading.Lock();process.qwen_title=title;process.qwen_renamed_title=''
    threading.Thread(target=name_when_ready,args=(process,),daemon=True).start()
    info[stage]={'session_id':session,'events':str(events),'title':title,'setup_key':key};save(bindings,info)
    return {'engine':'Qwen Code（阿里云）','task_file':str(task),'process':process}

def submit_existing(process,prompt,title=None):
    wait_ready(process)
    task=process.qwen_folder/('任务_'+uuid.uuid4().hex[:12]+'.md');save_text(task,prompt)
    # The official input-file protocol queues a submission in the existing TUI.
    message=f'请完整读取并执行本次任务文件：{task}。沿用已有成果，仅执行本次指定任务。'
    append_input(process,message,title)
    return '已自动提交到当前 Qwen Code 对话；忙碌时会按顺序处理。'

def run_background(config,project,output,report,logfile,prompt):
    ensure_request_context(prompt, config.get('stage', '当前阶段'))
    from qwen_setup import environment
    env=environment(config.get('model',''),config.get('api'))
    args=command(config)+['--auth-type','openai','--model',config.get('model') or env['OPENAI_MODEL'],
        '--prompt','执行标准输入中的制作任务。','--output-format','json','--approval-mode','auto',
        '--include-directories',str(output),'--max-session-turns','120','--max-wall-time','2h']
    from workflow_settings import skill_roots_for_config
    for directory in skill_roots_for_config(config):
        args+=['--include-directories',str(directory)]
    response=Path(report).with_suffix('.response.json')
    response_temp=temporary_path(response)
    # 第 47 期第 6 条：这一趟原来走 subprocess.run，不进引擎台账，于是「强制停止制作」找不到它，
    # 用户点了停止还在制作（报的就是这条链路）。改成 Popen ＋ 登记，与其它引擎同一套。
    # 适配器只能依赖无业务规则的进程注册表，不能反向导入工作流引擎；
    # 引擎的停止控制也使用同一注册表，因此任务生命周期仍可被统一观察。
    from workflow_process_registry import run_registered
    try:
        with Path(logfile).open('w',encoding='utf-8') as log,response_temp.open('w',encoding='utf-8') as out:
            returncode=run_registered(args,project,prompt,(out,log),config.get('timeout_seconds') or TIMEOUT_SECONDS,
                                      timeout_label='Qwen 运行超时',options={'env': env})
        if returncode:raise ValueError('Qwen 执行失败，请查看运行日志并检查 API、模型权限及额度')
        data=json.loads(response_temp.read_text(encoding='utf-8-sig'))
        replace(response_temp,response)
        events=data if isinstance(data,list) else [data]
        final=next((item for item in reversed(events) if item.get('type')=='result'),None)
        if final is None:raise ValueError('Qwen 未返回结束结果，请检查响应记录')
        report_text = str(final.get('result', '')).strip()
        if not report_text:raise ValueError('Qwen 未返回制作报告正文，请查看响应记录')
        save_text(Path(report),report_text)
        if final.get('is_error') or final.get('subtype','success')!='success':raise ValueError('Qwen 未完成任务，请查看制作报告')
    finally:
        if response_temp.exists():remove_temporary_file(response_temp)
