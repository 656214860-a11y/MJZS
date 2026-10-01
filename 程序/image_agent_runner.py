"""Qwen executes the app's configured local image backend for a fixed batch."""
import argparse,copy,json,shutil,sys,threading,time
from pathlib import Path
from agent.core import read,save,fingerprint
from agent.media import is_png


def task_instruction(project,manifest):
    def quote(value):return "'"+str(value).replace("'","''")+"'"
    python=Path(sys.executable)
    if python.name.lower()=='pythonw.exe':python=python.with_name('python.exe')
    command='& '+quote(python)+' '+quote(Path(__file__).resolve())+' --project '+quote(project)+' --manifest '+quote(manifest)
    return ('实际出图后端为本机 ComfyUI。所选 Skill 用于核对原分镜、角色锚点、构图、画风和参考图一致性；'
            '本次用户已指定由当前 Agent 执行下面的本机生图命令；Skill 中其他平台的工具名称不适用于本次任务。'
            '沿用清单已经确认的提示词，不重写角色设定，不只交付提示词。'
            '如发现会改变剧情或固定外观的矛盾，报告具体编号；其余项继续。'
            '核对后运行以下 PowerShell 命令执行已勾选批次，不改动批次文件，不另外发送生图任务：\n'+command+
            '\n命令复用助手保存的图像工作流与生成记录，逐张输出 PNG，助手按清单自动导入。'
            '仅在命令成功且目标PNG存在时报告完成；失败时读出真实错误，不伪造图片或改用绘图代码。')


class Events:
    def __init__(self,manifest):self.folder=Path(manifest).parent
    def put(self,message):
        print(message,flush=True)
        with (self.folder/'执行日志.txt').open('a',encoding='utf-8') as stream:stream.write(str(message)+'\n')
        save(self.folder/'执行状态.json',{'state':'running','message':str(message),'updated':time.time()})


def contained(root,value):
    path=Path(value).resolve()
    if not path.is_relative_to(root):raise ValueError('批次路径不在当前项目内')
    return path


def publish(image,target):
    # 只读文件头判断类型，用复制落盘：生成图动辄几 MB，没必要整份读进内存再写出去。
    if not is_png(image):raise ValueError('生成结果不是 PNG')
    if target.exists():return
    temp=target.with_suffix('.pending.png');shutil.copyfile(image,temp);temp.replace(target)


def execute(project,manifest):
    import msvcrt
    project=Path(project).resolve();manifest=contained(project,manifest)
    workflows=project/'workflows'
    if not manifest.is_relative_to(workflows) or manifest.name!='批次.json':raise ValueError('请选择助手创建的图片批次.json')
    with (workflows/'image_agent.lock').open('a+b') as lock:
        if not lock.tell():lock.write(b'0');lock.flush()
        lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:raise ValueError('已有图片 Agent 批次运行，请等待完成后继续') from None
        try:
            save(manifest.parent/'执行状态.json',{'state':'running','message':'已执行生图命令，正在连接 ComfyUI','updated':time.time()})
            _execute(project,manifest)
            save(manifest.parent/'执行状态.json',{'state':'complete','message':'生成完成，等待助手自动导入','updated':time.time()})
        except Exception as exc:
            save(manifest.parent/'执行状态.json',{'state':'failed','message':str(exc),'updated':time.time()})
            raise
        finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)


def _execute(project,manifest):
    data=read(manifest);stop=threading.Event()
    if 'assets' in data:
        from asset_batch_execution import run_batch
        base=contained(project,data['base'])
        pending=[item for item in data['assets'] if item.get('state')=='pending']
        planned=read(base/'assets/资产清单/assets.json')
        from prop_assets import requires_asset
        for item in pending:
            aid=item['id'];current=planned.get(aid)
            if not current or not requires_asset(aid,current):raise ValueError(aid+' 已移除或改为普通道具，请重新建立批次')
            if any(current.get(k)!=item['asset'].get(k) for k in ('name','description','image_prompt','negative_prompt','reference_images','reference_roles')):raise ValueError(aid+' 定义已变化，请重新建立批次')
        registry=read(base/'assets.json') if (base/'assets.json').is_file() else {}
        def ready(item):
            image=registry.get(item['id'],{}).get('image')
            return bool(image and contained(base,base/image).is_file())
        todo=[item for item in pending if not ready(item)]
        if todo:
            options=data.get('comfy_config') or read(project/'ui_settings.json').get('asset_batch',{})
            if not options.get('url'):raise ValueError('请先在资产图片制作窗口保存 ComfyUI 设置')
            from comfy_runtime import open_comfy
            open_comfy()
            result=run_batch(project,base,[(i['id'],i['asset']) for i in todo],options,Events(manifest),stop)
            print(result,flush=True)
        registry=read(base/'assets.json');missing=[]
        for item in pending:
            row=registry.get(item['id'],{});image=contained(base,base/row['image']) if row.get('image') else None
            output=contained(manifest.parent,manifest.parent/item['output'])
            if image and image.is_file():publish(image,output)
            else:missing.append(item['id'])
        if missing:raise ValueError('尚未出图：'+'、'.join(missing))
    elif 'items' in data:
        from batch_frames_tool.batch_frames import run
        from storyboard_paths import media_root
        source=contained(project,data['source']);ep=read(source);selected=[]
        items=[item for item in data['items'] if item.get('state')=='pending']
        for item in items:
            shot=next((s for s in ep['shots'] if s['id']==item['shot_id']),None)
            if shot is None or fingerprint(shot)!=item['shot_signature']:raise ValueError('镜头已修改，请重新创建首帧批次：'+item['shot_id'])
            selected.append(copy.deepcopy(shot))
        if not selected:return
        snapshot=manifest.parent/'agent_source.json'
        if not snapshot.exists():
            for s in selected:s['frame']='frames/'+s['id']+'.png'
            save(snapshot,{**ep,'duration':sum(s['duration'] for s in selected),'shots':selected})
        config=data.get('comfy_config') or read(Path(__file__).parent/'batch_frames_tool/config.json')
        config={**config,'shot_id':''}
        from comfy_runtime import open_comfy,wait_comfy
        open_comfy();wait_comfy(config['url'],Events(manifest).put)
        run(snapshot,config,lambda text:print(text,flush=True),stop)
        updated={s['id']:s for s in read(snapshot)['shots']};missing=[]
        for item in items:
            output=contained(manifest.parent,manifest.parent/item['output'])
            image=contained(manifest.parent,media_root(snapshot)/updated[item['shot_id']]['frame'])
            if image.is_file():publish(image,output)
            else:missing.append(item['shot_id'])
        if missing:raise ValueError('尚未生成首帧：'+'、'.join(missing))
    else:raise ValueError('不是资产或首帧批次')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--project',required=True);parser.add_argument('--manifest',required=True)
    args=parser.parse_args()
    try:execute(args.project,args.manifest)
    except Exception as exc:print('图片制作未完成：'+str(exc),file=sys.stderr);sys.exit(1)
