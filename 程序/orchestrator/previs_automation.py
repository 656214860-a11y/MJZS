"""Non-interactive, bounded-to-project Codex jobs. No Tk calls in workers."""
import json, queue, shutil, subprocess, threading
from datetime import datetime
from pathlib import Path
from agent.core import save
from file_cache import read_json
from contract.storyboard_paths import media_root
import contract.stage_layout as stage_layout
import white_model_service as wm
from contract.platform_tools import hidden_console_flags

def verify(project,sid,seconds,source=None):
    """媒体可播放且来源未变才算通过；通过后登记来源摘要与媒体事实，供复用与失效判定。"""
    from stage_execution_service import white_model_shot_directory
    root=white_model_shot_directory(project,sid,source=source)
    data=wm.read_record(root)
    paths=[Path(data.get(k,'')) for k in ('preview','project_file')]
    if not all(p.is_file() and p.stat().st_size for p in paths):return False
    if wm.evidence_state(data,paths[0],source,sid)=='changed':return False
    from integrations import tool_path
    probe=tool_path('ffprobe','D:/Tools/ffmpeg/bin/ffprobe.exe')
    result=subprocess.run([probe,'-v','error','-show_streams','-show_format','-of','json',str(paths[0])],capture_output=True,text=True,encoding='utf-8',timeout=30,creationflags=hidden_console_flags())
    if result.returncode:return False
    media=json.loads(result.stdout)
    duration=float(media.get('format',{}).get('duration',0))
    if not (any(s.get('codec_type')=='video' for s in media.get('streams',[]))
            and abs(duration-float(seconds))<=.5):return False
    if wm.evidence_state(data,paths[0],source,sid)!='ok':
        wm.record_evidence(root,sid,source,publish=save,preview=paths[0],
                           media={'duration':duration,'has_video':True})
    from stage_execution_service import sync_previs_copy
    sync_previs_copy(project,sid,source)
    return True


def select_agent_shots(project,source,ids,state):
    """只把复杂动作交给 Agent：简单镜头无需白模、中等镜头走线上入口，都只跳过、不中断整批。"""
    from domain.previs_routing import partition
    from stage_execution_service import project_context
    groups,_=partition(project_context(project),source,ids)
    for level,note in (('simple','无需白模，已跳过'),('medium','待线上制作／导入')):
        for sid in groups[level]:
            key=str(project)+'|'+sid
            state.setdefault('status',{})[key]=note
            state.setdefault('progress',{}).pop(key,None)
    return list(groups['complex'])

def announce(state,ok,text,ticket=None):
    """把这一批的结局放进 state['news']：界面线程的心跳取出来交给三虎播报（第 47 期第 5 条）。

    工作线程不碰 Tk、也不 import pet_ui：这里只写队列，谁取谁播报。state 上没有这条队列就现建。
    """
    try:
        state.setdefault('news',queue.Queue()).put((ticket,bool(ok),str(text)))
    except (AttributeError,TypeError):
        return None
    return text


LOCAL_AGENT_REQUIRED='白模预演需要本地 Agent（Claude 或 Codex 桌面通道），请在该阶段设置里切换引擎'


def require_local_agent(config):
    """REQ-S09-50：白模预演不走 API 直连；选了模型池 API 模型（engine=qwen）时拒绝，不启动 Qwen Code。"""
    if (config or {}).get('engine')=='qwen':raise ValueError(LOCAL_AGENT_REQUIRED)


def force_stop(project,state):
    """强制停止白模制作：先结束本项目正在跑的引擎进程（连同子进程），再让工作线程停掉后续镜头。

    与只置 stop 标记的「停止后续镜头」不同：这里立刻结束当前镜头，不必等它跑完。
    只结束本项目登记过的引擎进程，用户自己的对话窗口不受影响；taskkill 由调用方放在后台线程，
    界面线程不等待。
    """
    state['stop']=True
    from workflow_engines import terminate
    killed=terminate(project)
    for key,value in state.get('progress',{}).items():
        if value in ('queued','running','validating'):state['status'][key]='已强制停止'
    if killed:
        state['summary']='已强制停止：结束 '+str(len(killed))+' 个制作进程，后续镜头不再继续'
    else:
        state['summary']='已请求停止：当前没有可结束的制作进程，本镜结束后不再继续'
    return killed


def start(project,source,ids,state,monitor=False,ticket=None,is_current=None,execute=None):
    if state.get('busy'):raise ValueError('已有白模任务进行中')
    from workflow_settings import current,find_program,ENGINES
    call_config=current(project,'previs')
    require_local_agent(call_config)
    from domain.previs_routing import ready
    from stage_execution_service import project_context
    context=project_context(project)
    ids=[sid for sid in select_agent_shots(project,source,ids,state) if not ready(context,sid,source)]
    if not ids:
        state['summary']='没有需要 Agent 制作的镜头：简单镜头无需白模、中等镜头走线上入口，或所选镜头已就绪';return
    if call_config['engine']=='claude-desktop-app':
        # 白模是逐镜无人值守后台制作；Claude Desktop 只能由用户在窗口里手动发送，
        # 不先拦下会在建好批次、打开监视页后才逐镜失败。
        raise ValueError('白模自动制作需后台模型：请改用 Claude Code、Codex 或 API')
    call_config['program']=find_program(call_config)
    if call_config['engine']=='qwen':
        from qwen_setup import environment
        environment(call_config.get('model',''),call_config.get('api'))
    engine_name=ENGINES[call_config['engine']]
    if not wm.find_blender(refresh=True):raise ValueError('未找到本地 Blender')
    from orchestrator.previs_batch_service import prepare_batch
    # Capture source before dispatch: later selection/source edits cannot change this batch.
    episode=read_json(source)
    shots=[s for s in episode.get('shots',[]) if s.get('id') in ids]
    if not shots or {s['id'] for s in shots}!=set(ids):raise ValueError('镜头清单发生变化，请刷新页面')
    batch=stage_layout.workflow_dir(project,'白模自动制作')/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    batch.mkdir(parents=True)
    snapshot=batch/'分镜快照.json'
    # 派发前冻结的输入必须完整可读；后台 Agent 不能看到被中断的半份快照或配置。
    save(snapshot,episode)
    save(batch/'调用配置.json',call_config)
    state.update(busy=True,stop=False,summary='正在准备自动制作',log_dir=str(batch))
    # 第 47 期第 2 条：手动派发时把浏览器监视页打开（用户要的是「HTTP 浏览器里看制作」，
    # 不是再弹一个桌面 Blender 窗口）。无人值守那条路不弹浏览器——用户不在跟前，弹了也没人看。
    if monitor:
        from orchestrator.previs_monitor import start as start_monitor,url_of
        start_monitor(state,project)
        if url_of(state):state['summary']='制作监视页已开在浏览器里：'+url_of(state)
    state.setdefault('progress',{})
    for shot in shots:
        key=str(project)+'|'+shot['id'];state['progress'][key]='queued';state['status'][key]='排队中'
    def worker():
        result={};completed=0
        def persist():
            save(batch/'状态.json',result)      # 原子写只有 agent.core.save 一份
        try:
            # 第 47 期第 2 条：这一条线不再打开桌面 Blender 窗口——制作在后台跑，用户在浏览器
            # 监视页里看进度；要改工程时用户自己用页面上的「打开工程调整」把 .blend 调出来。
            for i,shot in enumerate(shots):
                sid=shot['id'];key=str(project)+'|'+sid
                if state.get('stop'):
                    for pending in shots[i:]:
                        pending_key=str(project)+'|'+pending['id'];state['progress'][pending_key]='cancelled';state['status'][pending_key]='已停止'
                        result[pending['id']]={'state':'cancelled'}
                    persist()
                    state['summary']='已强制停止：后续镜头不再继续';break
                state['summary']=f'{i+1}/{len(shots)} · {sid} 自动制作中'
                state['status'][key]=engine_name+' 制作中';state['progress'][key]='running';result[sid]={'state':'running'};persist()
                try:
                    from contract.platform_tools import execution_checkpoint, ExecutionStopped
                    execution_checkpoint()
                    if verify(project,sid,shot.get('duration',5),source=source):
                        result[sid]={'state':'ready','reused':True};state['status'][key]='已就绪';state['progress'][key]='ready';completed+=1;continue
                    prompt=prepare_batch(project,snapshot,[sid],call_config=call_config)
                    prompt+=f' 原始分镜路径为 {source}，首帧等frame相对路径以 {media_root(source)} 为素材基准；资产路径以各自assets.json所在目录为基准，不能相对于任务快照目录解析。'
                    prompt+=' 这是无人值守制作任务，直接完成制作和导出，不等待用户发送或回复；无法执行时清楚记录错误并结束，不声称完成。'
                    progress_file=batch/(sid+'_进度.json')
                    helper=batch/'previs_progress.py'
                    if not helper.exists():shutil.copy2(Path(__file__).resolve().parents[1] / 'previs_progress.py',helper)
                    prompt+=(f' 实时进度：在本次 Blender Python 脚本内，先把 {batch} 加入 sys.path，'
                             f'再 from previs_progress import install_blender_progress; install_blender_progress({str(progress_file)!r}, {sid!r})。'
                             '在正式动画渲染前调用；此模块会按实际写出帧数原子更新进度。'
                             '不要模拟百分比。分段渲染时应汇总已完成帧数和总帧数，写入相同JSON的shot_id、stage=render、completed、total字段。')
                    from stage_execution_service import white_model_shot_directory
                    output=white_model_shot_directory(project,sid,source=source);output.mkdir(parents=True,exist_ok=True)
                    from workflow_engines import run_background
                    # 引擎实时输出尾随最后 N 行写进 state，监视页边跑边显示；不落额外文件。
                    ENGINE_LOG_TAIL = 200
                    def engine_output(line, stream):
                        tail = state.setdefault('engine_log', [])
                        tail.append('%s%s' % (('' if stream == 'stdout' else '[err] '), line.rstrip('\n')))
                        if len(tail) > ENGINE_LOG_TAIL:
                            del tail[:-ENGINE_LOG_TAIL]
                    run_background(call_config,project,output,batch/(sid+'_制作报告.txt'),batch/(sid+'_运行日志.txt'),prompt,on_output=engine_output)
                    execution_checkpoint()
                    state['progress'][key]='validating';state['status'][key]='校验视频中'
                    if not verify(project,sid,shot.get('duration',5),source=source):raise ValueError('输出未通过校验，请查看制作报告')
                    result[sid]={'state':'ready'};state['status'][key]='已就绪';state['progress'][key]='ready';completed+=1
                except ExecutionStopped as exc:
                    result[sid]={'state':'unknown','error':str(exc)}
                    state['status'][key]='本机已停止等待；结果待核对';state['progress'][key]='unknown'
                    state['stop']=True
                    break
                except Exception as exc:
                    if state.get('stop'):
                        # 强制停止会先结束引擎进程，被结束的这一镜按「已停止」记账，不算失败。
                        result[sid]={'state':'cancelled'};state['status'][key]='已强制停止';state['progress'][key]='cancelled'
                    else:
                        result[sid]={'state':'failed','error':str(exc)};state['status'][key]='失败：'+str(exc);state['progress'][key]='failed'
                finally:persist()
            else:
                # 强制停止后不再报「失败项请查看运行日志」：这一批是按用户要求停的。
                if state.get('stop'):state['summary']=f'已强制停止：就绪 {completed}/{len(shots)} 镜，后续镜头不再继续'
                else:
                    state['summary']=f'自动制作结束：{completed}/{len(shots)} 就绪；失败项请查看运行日志'
                    # 第 47 期第 5 条：这一批收了尾就说一句（强制停止是用户自己按的，不用再报）。
                    announce(state,True,state['summary'],ticket)
        except Exception as exc:
            state['summary']='自动制作中断：'+str(exc)
            announce(state,False,state['summary'],ticket)
            for shot in shots:
                key=str(project)+'|'+shot['id']
                if state['progress'].get(key) in ('queued','running','validating'):
                    state['progress'][key]='failed';state['status'][key]='失败：'+str(exc)
        finally:
            # 被替换或关闭的批次仍可能在线程退出时返回；不得由旧代次
            # 解除新批次的忙碌态。无生命周期调用方维持原有兼容行为。
            if is_current is None or is_current(ticket):state['busy']=False
    def controlled_worker():
        from contract.platform_tools import ExecutionStopped
        try:
            execute(worker)
        except ExecutionStopped:
            if is_current is None or is_current(ticket):
                state['stop']=True;state['busy']=False
                state['summary']='本机已停止等待；在途白模结果待核对'
                announce(state,False,state['summary'],ticket)
    threading.Thread(target=controlled_worker if execute is not None else worker,daemon=True).start()
