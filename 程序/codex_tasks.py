"""One persisted Codex task per project/stage. Never starts a model turn."""
import json,os,queue,shutil,subprocess,threading,time
import contract.stage_layout as stage_layout
import infra.token_saver as token_saver
from pathlib import Path
from contextlib import contextmanager
from importlib import import_module
from agent.core import read,save,save_text
from contract.pet_bus import read_json
from pet_llm import config_path
from contract.platform_tools import terminate_process_tree
from contract.workflow_context_budget import ensure_request_context

class RPC:
    def __init__(self, program=None):
        self.program = program

    def subagent_env(self):
        """第 66 期：子 Agent 一律用 fast 便宜模型、思考量封顶（附件通用原则 4）。

        「设置 → Token 节省」里改过就按改过的来；读不出来就用附件那组出厂值，
        绝不因为读盘失败把任务拦住。
        """
        # RPC 只需要 token 节省这一小块持久化配置；不能为了它导入父 Agent，
        # 否则任务适配器会把整个三虎编排链重新拉进来形成循环依赖。
        try:
            data = read_json(config_path(self.program))
            values = data.get('token') if isinstance(data, dict) else None
        except Exception:
            values = None
        return token_saver.subagent_env(values)

    def environment(self):
        """起子 Agent 用的那一份环境变量：本机的照旧，另加上面那两个。"""
        env = dict(os.environ)
        env.update(self.subagent_env())
        return env

    def __enter__(self):
        exe=shutil.which('codex')
        if not exe:
            paths=list((Path(os.environ.get('LOCALAPPDATA',''))/'OpenAI/Codex/bin').glob('*/codex.exe'))
            exe=str(max(paths,key=lambda p:p.stat().st_mtime)) if paths else None
        if not exe:raise ValueError('未找到Codex程序，请先安装并打开Codex')
        self.process=subprocess.Popen([exe,'app-server','--stdio'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8',errors='replace',env=self.environment(),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.messages=queue.Queue();self.counter=0
        def pump():
            try:
                for line in self.process.stdout:
                    try:self.messages.put(json.loads(line))
                    except ValueError:continue
            finally:self.messages.put(None)
        threading.Thread(target=pump,daemon=True).start()
        try:
            self.call('initialize',{'clientInfo':{'name':'drama_studio','version':'0.7'}})
            self.send({'method':'initialized','params':{}})
        except Exception:self.__exit__(None,None,None);raise
        return self
    def send(self,obj):
        self.process.stdin.write(json.dumps(obj,ensure_ascii=False)+'\n');self.process.stdin.flush()
    def call(self,method,params):
        self.counter+=1;identifier=self.counter
        self.send({'id':identifier,'method':method,'params':params});deadline=time.monotonic()+25
        while True:
            try:reply=self.messages.get(timeout=max(.01,deadline-time.monotonic()))
            except queue.Empty:raise ValueError('Codex接口响应超时，请稍后重试') from None
            if reply is None:raise ValueError('Codex接口已关闭，请确认Codex已登录')
            if reply.get('id')!=identifier:continue
            if 'error' in reply:raise ValueError('Codex：'+reply['error'].get('message','请求失败'))
            return reply['result']
    def __exit__(self,*args):
        if self.process.poll() is None:
            terminate_process_tree(self.process)
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
        for pipe in (self.process.stdin,self.process.stdout):
            if pipe:pipe.close()

@contextmanager
def task_lock(project):
    """跨平台排他锁；Windows 与 POSIX 都拒绝第二个并发任务。"""
    with (project/'codex_tasks.lock').open('a+b') as f:
        if not f.tell():f.write(b'0');f.flush()
        f.seek(0)
        if os.name == 'nt':
            import msvcrt
            try:msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:raise ValueError('正在打开此项目的Codex任务，请稍后') from None
            unlock=lambda:msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
        else:
            # Windows 裁剪运行环境不含 Unix 专用模块；仅在 POSIX 锁分支加载。
            fcntl = import_module('fcntl')
            try:fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError:raise ValueError('正在打开此项目的Codex任务，请稍后') from None
            unlock=lambda:fcntl.flock(f.fileno(),fcntl.LOCK_UN)
        try:yield
        finally:
            f.seek(0);unlock()

def task_file_reference(project, stage, prompt):
    """保存桌面任务快照；输入框只传引用，不启动模型或 Codex RPC。"""
    taskdir = stage_layout.workflow_dir(Path(project).resolve(), stage)
    signature = __import__('hashlib').sha256(prompt.encode('utf-8')).hexdigest()[:20]
    taskfile = taskdir / (signature + '.md')
    if not taskfile.is_file() or taskfile.read_text(encoding='utf-8') != prompt:
        save_text(taskfile, prompt)
    return taskfile


def prepare_task(project,title,stage,prompt,rpc_factory=RPC,followup=None,setup_key=None,*,delivery_summary=''):
    from urllib.parse import urlencode,quote
    prompt=ensure_request_context(prompt, stage)
    project=Path(project).resolve();file=project/'codex_tasks.json'
    with task_lock(project):
        info=read(file) if file.exists() else {}
        if not isinstance(info,dict):info={}
        entry=info.get(stage,{})
        if not isinstance(entry,dict):entry={}
        prompt='请将当前任务命名为“'+title+'”。\n'+prompt
        def usable(thread):
            return (Path(thread.get('cwd','')).resolve()==project
                    and bool(thread.get('path')) and Path(thread['path']).is_file())
        thread_id=None;draft=''
        with rpc_factory() as rpc:
            if entry.get('thread_id'):
                try:
                    thread=rpc.call('thread/read',{'threadId':entry['thread_id'],'includeTurns':False})['thread']
                except ValueError as exc:
                    if not any(x in str(exc).lower() for x in ('not found','does not exist','no rollout','unable to resolve')):raise
                else:
                    if usable(thread):thread_id=thread['id']
            if not thread_id:
                cursor=None
                while True:
                    result=rpc.call('thread/list',{'cwd':str(project),'searchTerm':title,'limit':100,'cursor':cursor})
                    matches=[t for t in result['data'] if t.get('name')==title and usable(t)]
                    if matches:thread_id=matches[0]['id'];break
                    cursor=result.get('nextCursor')
                    if not cursor:break
        if thread_id:
            if followup is not None and (setup_key is None or entry.get('setup_key',setup_key)==setup_key):prompt=followup
            info[stage]={'thread_id':thread_id,'title':title,'state':'ready'}
            url='codex://threads/'+thread_id;mode='existing'
        else:
            info[stage]={'title':title,'state':'draft','invalid_thread_id':entry.get('thread_id') or entry.get('invalid_thread_id')}
            mode='new'
        taskfile=task_file_reference(project,stage,prompt)
        delivery=f'请将当前任务命名为“{title}”。请完整读取并执行本次任务文件：{taskfile}。仅执行该文件指定的任务，沿用已有成果，不重复制作。'
        if delivery_summary:
            delivery = delivery_summary + '\n' + delivery
        if mode=='new':
            draft=delivery
            url='codex://new?'+urlencode({'path':str(project),'prompt':draft},quote_via=quote)
        if setup_key is not None:info[stage]['setup_key']=setup_key
        save(file,info)
        return {'url':url,'title':title,'prompt':delivery,'task_file':str(taskfile),'mode':mode,'draft_prompt':draft,'project':str(project)}
