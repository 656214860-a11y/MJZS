"""Local production state machine. No API calls during construction/import."""
import json
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from storyboard_paths import media_root, is_cloud_workspace
from agent.core import read, save, save_text, fingerprint, file_hash, download, command, replace, temporary_path
from agent.wan import WanAdapter, ArkRejected
from agent.media import check, probe
import project_settings
from project_naming import dated_path
from legacy_compat import resolved_storyboard_alias
import pet_bus

def approved_versions(versions):
    """已下载＋技术质检通过＋已验收的版本；自动粗剪、手动拼装与交接包共用同一口径。

    `review` 为 `pass` 含无人值守的自动技术放行，不等于真人看过内容（见 `content_reviewed`）。
    """
    return [v for v in versions or [] if v.get('review')=='pass' and v.get('state')=='downloaded' and v.get('qc_pass')]

REVIEW_PENDING='pending'
REVIEW_PASS='pass'
REVIEW_REVISE='revise'
AUTO_REVIEW_MARK='无人值守自动验收'
AUTO_REVIEW_NOTE=AUTO_REVIEW_MARK+'：技术质检通过，未做内容审核，等您确认内容'
QC_NAME='qc.json'
EDIT_MANIFEST_NAME='edit_manifest.json'
EDIT_BUNDLE_NAME='edit_bundle.json'

def review_source(version):
    """这条验收是谁给的：'user' 真人点过，'auto' 无人值守按设置自动放行，'' 还没验收。

    老记录没有 `review_by`，按 `review_note` 是否以自动标记开头回推：认不出来就当真人验收（保守取“已审”）。
    """
    value=(version or {}).get('review')
    if value not in (REVIEW_PASS,REVIEW_REVISE):return ''
    by=(version or {}).get('review_by')
    if by in ('user','auto'):return by
    note=str((version or {}).get('review_note') or '')
    return 'auto' if note.startswith(AUTO_REVIEW_MARK) else 'user'

def content_reviewed(version):
    """内容审核是否真做过：只有真人点过「通过」才算；自动技术放行不算。"""
    return (version or {}).get('review')==REVIEW_PASS and review_source(version)=='user'

def review_label(version):
    """质量面板那一格：把「技术合格」与「内容审核」分开说清。"""
    value=(version or {}).get('review')
    if value==REVIEW_PASS:
        return '通过（您已确认内容）' if review_source(version)=='user' else '技术自动放行（未做内容审核）'
    if value==REVIEW_REVISE:return '需修改'
    return '待验收'

ADOPT_UNAPPROVED='unapproved'
ADOPT_MISSING='missing'
ADOPT_REPLACED='replaced'
ADOPT_UNREADABLE='unreadable'
ADOPT_REASON_TEXT={ADOPT_UNAPPROVED:'尚未验收',ADOPT_MISSING:'视频文件缺失',
                   ADOPT_REPLACED:'视频已被替换，需重新验收',ADOPT_UNREADABLE:'视频无法读取'}

def adopted_edit_version(versions, root=None):
    """本镜真正会进成片的那一版：已下载＋技术合格＋已验收的最后一条，且文件在、内容与验收摘要一致。

    返回 ``(version, reason)``：取到就是 ``(v, '')``；取不到时 ``version`` 为 None，``reason``
    说明原因（``unapproved``／``missing``／``replaced``／``unreadable``）。自动粗剪、进度与交付界面
    共用这一个口径，界面显示的「采用」才和真实成片来源一致，不会按「最新版」或「只要审核过」各说各的。
    """
    approved=approved_versions(versions)
    if not approved:return None,ADOPT_UNAPPROVED
    version=approved[-1]
    if root is None:return version,''
    path=Path(root)/str(version.get('file') or '')
    try:
        if not path.is_file():return None,ADOPT_MISSING
        if file_hash(path)!=version.get('sha256'):return None,ADOPT_REPLACED
    except OSError:
        return None,ADOPT_UNREADABLE
    return version,''

def adoption_summary(root, versions):
    """进度／交付界面每一镜那一行的事实：实际采用哪一版、最新版为什么没被采用。

    ``source`` 是要显示状态的那一版：有采用就用采用版，没有才退回最新版（与旧界面一致）。
    ``latest_is_adopted`` 为假说明最新版没进成片，界面必须写出来，否则用户会以为最新版已经进了成片。
    这里只给原始事实，文案由界面拼。
    """
    versions=list(versions or [])
    adopted,reason=adopted_edit_version(versions,root)
    latest=versions[-1] if versions else None
    return {'source':adopted if adopted is not None else (latest or {}),
            'adopted':adopted,'latest':latest,
            'latest_is_adopted':adopted is not None and latest is adopted,
            'reason':reason,'reason_text':ADOPT_REASON_TEXT.get(reason,'')}

def read_edit_bundle(out):
    """读成片目录里那份可恢复的发布清单；还没写过 bundle 的老成片退回两份索引。

    返回 ``{'master','master_sha256','manifest','qc','coverage'}``；什么都读不出时返回 None。
    只读、不猜：成片名与摘要都来自磁盘上的记录，界面和交付据此核对真实成片来源。
    """
    out=Path(out)
    try:
        data=read(out/EDIT_BUNDLE_NAME)
    except (OSError,ValueError):
        data=None
    if isinstance(data,dict) and data.get('master'):return data
    try:
        manifest=read(out/EDIT_MANIFEST_NAME)
    except (OSError,ValueError):
        manifest=None
    if not isinstance(manifest,list):return None
    return {'master':'MASTER.mp4','master_sha256':'','manifest':manifest,'qc':None,'coverage':{},'legacy':True}


def episode_file_of(project,cfg,episode_file=None):
    """第 45 期：工作集里那份镜头 JSON 到底在哪一份——配置、改名映射、定稿目录挨个找。

    用户报的「ERRNO 2: 无法打开项目」就出在这里：老项目 config 里的 episode_dir 写的是
    storyboard/分镜拆分，而那份 episode.json 早被规范化挪进了 定稿_…／EP00X_分镜定稿_… 子目录
    （新位置就记在 分镜拆分/文件路径映射.json 里，见 storyboard_storage.resolved_alias）。
    这里原来自顾自读 episode_dir/episode.json，一读不到就抛 [Errno 2]，整个项目都打不开——
    先按映射表认名字，再按定稿目录兜底，最后才把「找不到的那条路」交给上层报清楚。
    """
    project=Path(project).resolve()
    from project_stages import storyboard
    # 配置文件里的相对路径必须相对于项目解析。此前 ``storyboard/…`` 会被
    # 错当成进程工作目录下的路径，迁移前项目即使文件仍在也会被判为丢失。
    def _project_path(value):
        path=Path(value)
        return path if path.is_absolute() else project/path

    declared=_project_path(cfg.get('episode_dir')) if cfg.get('episode_dir') else storyboard(project)/'分镜拆分'
    explicit=_project_path(episode_file) if episode_file else (_project_path(cfg['episode_file']) if cfg.get('episode_file') else None)
    wanted=explicit if explicit is not None else declared/'episode.json'
    # 1) 配置／调用方明写的那一份（改名挪走了也认映射表）
    if explicit is not None:
        path=resolved_storyboard_alias(project,explicit)
        if path.is_file():return path
    # 2) 老布局：episode_dir 里就摆着 episode.json
    elif (declared/'episode.json').is_file():
        return (declared/'episode.json').resolve()
    # 3) 认「当前分镜」那一份（ui_settings.json 的 frame_json）：第 03／04／07 页看的正是它，
    #    工作集跟着它走，几页之间才不会各说各的。
    if episode_file is None:
        current=current_episode(project)
        if current is not None:return current
    # 4) 配置那条路被规范化挪进定稿目录了：按映射表认领新位置（用户报的 ERRNO 2 就出在这一步之前）
    path=resolved_storyboard_alias(project,wanted)
    if path.is_file():return path
    # 5) 最后的兜底：定稿目录里最新那份 episode.json。编号阶段是新布局；
    #    ``storyboard`` 是迁移前项目的只读兼容入口，不能让它阻断老项目打开。
    try:
        roots=[storyboard(project)/'分镜拆分', project/'storyboard'/'分镜拆分']
        found=[p for root in roots for p in root.glob('*/episode.json') if p.is_file()]
    except OSError:
        found=[]
    if found:return max(found,key=lambda p:p.stat().st_mtime)
    return path


def current_episode(project):
    """ui_settings.json 里那份「当前分镜」（frame_json）：读得出来、文件还在才认。"""
    try:
        prefs=read(Path(project)/'ui_settings.json')
    except (OSError,ValueError):
        return None
    value=prefs.get('frame_json') if isinstance(prefs,dict) else None
    if not value:return None
    path=resolved_storyboard_alias(project,Path(value))
    return path if path.is_file() else None


class Studio:
    def __init__(self, root, factory=WanAdapter,episode_file=None):
        self.root=Path(root).resolve()
        self.factory=factory
        try:
            cfg=read(self.root/'config.json')
        except (OSError,ValueError) as exc:
            raise ValueError('项目配置文件 config.json 无法读取：'+str(exc)) from None
        if not isinstance(cfg,dict):
            raise ValueError('项目配置文件 config.json 顶层必须为对象')
        self.cfg=cfg
        # 第 45 期：镜头 JSON 与它所在的目录一起定下来（改名映射、定稿目录都算数）。目录原来是从
        # config 里单读的，与真正那份 JSON 一脱节就报「[Errno 2] 无法打开项目」；现在以找到的文件
        # 为准。显式传了 episode_file（切工作集那条路，见 desktop.align_studio）就只换内存指针。
        self.episode_path=episode_file_of(self.root,cfg,episode_file)
        self.episode_dir=self.episode_path.parent
        if not self.episode_path.is_file():
            raise ValueError('项目里找不到镜头 JSON（episode.json）：'+str(self.episode_path)
                             +'；请在'+pet_bus.stage_step('storyboard')+'重新采用一份分镜 JSON 后再进入后续步骤。')
        if episode_file is None:self.remember_episode()
        self.media_dir=media_root(self.episode_path)
        self.episode=read(self.episode_path)
        self.db=self.root/'data/state.json'
        self.db.parent.mkdir(exist_ok=True)
        if not self.db.exists():
            save(self.db, {'schema':1,'shots':{s['id']:[] for s in self.episode['shots']}})
        self.validate()

    def remember_episode(self):
        """第 45 期：把找到的那份镜头 JSON 写回项目配置，下一趟不必再满世界找。

        只在「配置里的指针确实不对」时写（对的就一个字节都不动），写不动也不影响这次打开——
        它省的是下一次启动的时间与一次误报的机会（见 episode_file_of）。
        """
        wanted={'episode_file':str(self.episode_path),'episode_dir':str(self.episode_path.parent)}
        def same(key,value):
            raw=self.cfg.get(key)
            if not raw:return False
            path=Path(raw)
            if not path.is_absolute():path=self.root/path      # 配置里写相对项目根的路径也算数
            try:return path.resolve()==Path(value).resolve()
            except (OSError,ValueError):return False
        if all(same(key,value) for key,value in wanted.items()):return False
        try:
            save(self.root/'config.json',{**self.cfg,**wanted})
        except OSError:
            return False
        self.cfg={**self.cfg,**wanted}
        return True

    def validate(self):
        ids=[s['id'] for s in self.episode['shots']]
        if len(ids)!=len(set(ids)) or not ids:
            raise ValueError('镜头编号重复或为空')
        reserve=self.cfg.get('reserve_seconds',0);budget=self.cfg.get('budget_seconds',0)
        if not 0<=reserve<=budget:
            raise ValueError('备用秒数必须在预算范围内')
        for shot in self.episode['shots']:
            if not 2<=shot['duration']<=15: raise ValueError('万相镜头时长须为2–15秒')
            if not shot['video_prompt'].strip(): raise ValueError('视频提示词为空')
            self.frame(shot,required=False)

    def frame(self, shot, required=True):
        path=(self.media_dir/shot['frame']).resolve()
        if not path.is_relative_to(self.media_dir):
            raise ValueError('首帧路径超出素材目录，已阻止访问：'+shot['id'])
        if required and (shot.get('frame_deleted') or not path.is_file()):
            raise ValueError(shot['id']+' 尚未生成／导入首帧，请到'+pet_bus.stage_step('keyframe')+'选择此镜头，生成或导入图片后再制作视频。')
        return path

    @contextmanager
    def lock(self):
        # Windows releases this byte lock even when the process crashes.
        path=self.root/'data/operation.lock'
        with path.open('a+b') as f:
            if path.stat().st_size==0: f.write(b'0'); f.flush()
            f.seek(0)
            import msvcrt
            try: msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
            except OSError: raise ValueError('另一操作正在运行，请稍后再试') from None
            try: yield
            finally:
                f.seek(0); msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)

    def state(self):
        try:
            state=read(self.db)
        except (OSError,ValueError):
            state={}
        if not isinstance(state,dict) or not isinstance(state.get('shots'),dict):
            state={'schema':1,'shots':{}}
        for shot in self.episode['shots']:state['shots'].setdefault(shot['id'],[])
        return state
    def shot(self,sid):
        for s in self.episode['shots']:
            if s['id']==sid:return s
        raise ValueError('镜头不存在：'+str(sid))
    def shot_folder(self,sid):
        import re
        if not re.fullmatch(r'[A-Za-z0-9_-]+',sid):raise ValueError('镜头编号不能包含路径字符')
        if is_cloud_workspace(self.root):return self.root.parent/'镜头'/sid
        return self.root/'data'/sid
    def task_folder(self,sid,version):
        if version.get('output_dir'):return (self.root/version['output_dir']).resolve()
        return self.root/'data'/sid/f"v{version['version']:03}"
    def publish_downloaded_video(self,state,sid,version,dest,report=None,qc_error=None):
        """视频完整落盘后，再发布 QC 与可见成果索引。"""
        dest=Path(dest).resolve()
        if not dest.is_file() or not dest.is_relative_to(self.root):raise ValueError('视频成果尚未安全落盘')
        folder=self.task_folder(sid,version)
        if report is not None:save(folder/'qc.json',report)
        version.update(state='downloaded',file=os.path.relpath(dest,self.root),sha256=file_hash(dest),
                       qc_pass=bool(report is not None and not report.get('errors')),downloaded_at=time.time())
        if qc_error is not None:version['qc_error']=str(qc_error)
        version['finished_at']=time.time()
        save(self.db,state)
        return version
    def cloud_index(self):
        if not is_cloud_workspace(self.root):return
        grouped={}
        for db in self.root.parent.glob('*/data/state.json'):
            cfgfile=db.parent.parent/'config.json'
            if not cfgfile.is_file():continue
            cfg=read(cfgfile);session=db.parent.parent
            for sid,versions in read(db).get('shots',{}).items():
                for version in versions:
                    folder=(session/version['output_dir']).resolve() if version.get('output_dir') else session/'data'/sid/f"v{version['version']:03}"
                    grouped.setdefault(sid,[]).append(f"- {cfg.get('model','模型')} · v{version['version']:03} · {version.get('state','')}\n  目录：{folder}\n")
        for sid,lines in grouped.items():
            folder=self.shot_folder(sid);folder.mkdir(parents=True,exist_ok=True)
            save_text(folder/'历史任务索引.txt', '\n'.join(lines))
    def used(self,state=None):
        return sum(v.get('seconds',0) for vv in (state or self.state())['shots'].values() for v in vv if v.get('charged',True))
    def remaining(self):
        return max(0,self.cfg.get('budget_seconds',0)-self.cfg.get('reserve_seconds',0)-self.used())

    def client(self):
        from api_endpoints import configured_key
        configured_key(self.cfg)
        return self.factory(self.cfg)

    def submit(self,sid):
        from api_models import ensure_cloud_model
        ensure_cloud_model(self.root,self.cfg)
        from importlib import import_module
        # 第 8 轮：勾了「白模 · 上传」时它返回那份参考视频的描述（接不上就当场抛）；不勾返回 None。
        white=import_module('white_model').validate_video_submission(self,sid)
        with self.lock():
            if not self.cfg['live_enabled']: raise ValueError('当前为离线模式；请在设置中开启联网操作')
            st=self.state(); versions=st['shots'][sid]; shot=self.shot(sid)
            from video_task_state import submission_block_reason
            blocked=submission_block_reason(versions)
            if blocked:raise ValueError(blocked)
            if shot['duration']>self.remaining(): raise ValueError('超过可用制作秒数；备用额度不会自动动用')
            command([self.cfg['ffmpeg'],'-version']); command([self.cfg['ffprobe'],'-version'])
            from agent.shot_assets import prepare
            shot=prepare(self.episode_path,shot,self.cfg,white=white)
            client=self.client(); payload=client.payload(shot,self.frame(shot))
            v={'version':len(versions)+1,'state':'submitting','seconds':shot['duration'],'charged':True,
               'signature':fingerprint(payload),'review':'pending','created':time.time(),'local_request':uuid.uuid4().hex}
            v['generate_audio']=bool(shot.get('generate_audio',True))
            if is_cloud_workspace(self.root):
                import re
                model=re.sub(r'[^A-Za-z0-9_-]','_',self.cfg['model'])
                target=self.shot_folder(sid)/(model+'_'+self.root.name)/f"v{v['version']:03}"
                v['output_dir']=os.path.relpath(target,self.root)
            versions.append(v); save(self.db,st) # Reserve before network; ambiguous requests stay reserved.
            folder=self.task_folder(sid,v)
            folder.mkdir(parents=True,exist_ok=True)
            def redact(value):
                if isinstance(value,dict):return {k:redact(v) for k,v in value.items()}
                if isinstance(value,list):return [redact(v) for v in value]
                if isinstance(value,str) and value.startswith(('data:image/','data:video/')):
                    import hashlib,base64
                    return 'sha256:'+hashlib.sha256(base64.b64decode(value.split(',',1)[1])).hexdigest()
                return value
            preview=redact(payload)
            save(folder/'request.json',preview)
            save(folder/'assets_manifest.json',{'mode':shot['_reference_mode'],'assets':shot['_asset_references'],
                                               'white_model_reference':shot.get('_white_model_reference')})
            save_text(folder/'实际提交提示词.txt', shot['video_prompt'])
            try:
                v['task_id']=client.submit(shot,self.frame(shot),v['local_request'])
                save(folder/'task_receipt.json',{'shot':sid,'version':v['version'],'local_request':v['local_request'],'task_id':v['task_id']})
                v['state']='queued';v['submitted_at']=time.time()
            except ArkRejected as e:
                # A server error can occur after task creation; keep its reservation.
                uncertain='HTTP 5' in str(e)
                v.update(state='unknown' if uncertain else 'rejected',charged=uncertain,error=str(e)); save(self.db,st); raise
            except Exception:
                v.update(state='unknown',error='提交连接中断；任务可能已创建，不自动重发')
                save(self.db,st); raise RuntimeError(v['error']) from None
            save(self.db,st)
            return '已提交 '+sid+'；已保存任务编号，自动跟踪并下载。'

    def poll(self,sid):
        with self.lock():
            if not self.cfg['live_enabled']: raise ValueError('离线模式下不查询云端')
            st=self.state(); vs=st['shots'][sid]
            if not vs: raise ValueError('镜头尚未提交')
            v=vs[-1]
            if v['state']=='downloaded' and v.get('file') and (self.root/v['file']).is_file():return '已下载：'+str(self.root/v['file'])
            if not v.get('task_id'):
                receipt=self.task_folder(sid,v)/'task_receipt.json'
                if receipt.is_file():
                    info=read(receipt)
                    if info.get('shot')==sid and info.get('local_request')==v.get('local_request') and info.get('task_id'):
                        v.update(task_id=info['task_id'],state='queued');save(self.db,st)
            if not v.get('task_id'):raise ValueError('提交中断，没拿到任务编号。请去服务商控制台核对，用「恢复任务编号」找回。')
            client=self.client()
            try: result=client.poll(v['task_id'])
            except Exception: raise RuntimeError('查询连接中断；编号已保留，下次继续查询即可') from None
            observed=time.time();v['last_checked_at']=observed
            if result['status']=='running':v.setdefault('running_observed_at',observed)
            if result['status']=='succeeded':v.setdefault('succeeded_observed_at',observed)
            for field in ('provider_created_at','provider_updated_at'):
                if isinstance(result.get(field),(int,float)):v[field]=result[field]
            v.update(state=result['status'],usage=result.get('usage'),error_code=result.get('error_code'))
            save(self.db,st)
            if v['state']=='failed': return '云端失败，保守保留预算占用；请核对账单。'
            if v['state']!='succeeded': return sid+' · 云端状态：'+{'queued':'排队中','running':'生成中'}.get(v['state'],v['state'])
            folder=self.task_folder(sid,v); folder.mkdir(parents=True,exist_ok=True)
            dest=folder/f'{sid}.mp4';v['download_started_at']=time.time();save(self.db,st)
            url=result.get('url')
            try:
                if hasattr(client,'download_video'):client.download_video(v['task_id'],dest)
                elif not url:raise ValueError('服务商没有返回视频地址')
                else:download(url,dest)
            except ValueError:raise RuntimeError('云端任务已成功但没有返回视频地址；请在服务商控制台核对并手动下载，不要重复提交') from None
            except Exception:
                # O28：记下取回失败但保留 succeeded 状态；再查询即续取，不重生成、不重投。
                v['download_error']='下载中断；任务已成功，再次查询可续取，不会重新生成';save(self.db,st)
                raise RuntimeError(v['download_error']) from None
            try:
                report=check(dest,v['seconds'],{**self.cfg,'require_audio':v.get('generate_audio',True)})
                command([self.cfg['ffmpeg'],'-v','error','-xerror','-i',dest,'-f','null','-'])
                if not report['errors'] and project_settings.auto_review(self.root):
                    # 无人值守：技术质检通过即自动放行，让下载→质检→验收→剪辑可以连续跑完。
                    # 这是技术放行、不是内容审核——沿用旧记录前缀，面板会另说是谁点的。
                    v.update(review=REVIEW_PASS,review_by='auto',review_note=AUTO_REVIEW_NOTE)
            except Exception as e:
                self.publish_downloaded_video(st,sid,v,dest,qc_error=e)
                return '视频已下载：'+str(dest)+'；质检未完成，请检查FFmpeg设置后再验收。'
            self.publish_downloaded_video(st,sid,v,dest,report)
            total=int(v['finished_at']-v.get('created',v['finished_at']))
            if not v['qc_pass']:note='；'.join(report['errors'])
            elif v.get('review')==REVIEW_PASS:note='技术检查通过，已按自动验收设置放行（未做内容审核）'
            else:note='技术检查通过，等您验收'
            return f'已下载（总耗时 {total//60}分{total%60:02}秒）：'+str(dest)+'；'+note

    def review(self,sid,value,note):
        with self.lock():
            st=self.state(); vs=st['shots'][sid]
            if not vs: raise ValueError('没有可验收的版本')
            v=vs[-1]
            if value=='pass' and (v['state']!='downloaded' or not v.get('qc_pass')): raise ValueError('仅下载且技术合格的版本可通过')
            if value not in ('pass','revise'): raise ValueError('无效验收值')
            v.update(review=value,review_by='user',review_note=note); save(self.db,st)

    def review_many(self,shot_ids,value,note=''):
        """按镜头批量验收：逐镜汇总结果，单镜不合格只跳过，不中断整批。"""
        ids=list(shot_ids)
        if not ids: raise ValueError('请先勾选要验收的镜头')
        passed=[];skipped=[]
        for sid in ids:
            try:
                self.review(sid,value,note);passed.append(sid)
            except (ValueError,RuntimeError,KeyError) as exc:
                skipped.append(str(sid)+'：'+str(exc))
        text=('已通过 ' if value=='pass' else '已标记需修改 ')+str(len(passed))+'/'+str(len(ids))+' 镜'
        if skipped:text+='；跳过 '+'；'.join(skipped)
        return text

    def attach(self,sid,task_id):
        import re
        if not re.fullmatch(r'[A-Za-z0-9_-]{10,200}',task_id): raise ValueError('任务编号格式不正确')
        with self.lock():
            st=self.state(); vs=st['shots'][sid]
            if not vs or vs[-1].get('task_id') or vs[-1]['state'] not in ('unknown','submitting'):
                raise ValueError('只恢复无编号、结果不确定的提交')
            if any(v.get('task_id')==task_id for vv in st['shots'].values() for v in vv): raise ValueError('编号已属于其他版本')
            vs[-1].update(task_id=task_id,state='queued',review_note='您在控制台手动恢复；请核实镜头内容')
            save(self.db,st)

    def auto_edit_ready(self):
        """无人值守粗剪的前置检查：返回 (成片指纹, 已就绪版本清单)。

        只有本集每个未删除镜头都有「已下载＋技术质检通过＋已验收」且文件与验收指纹一致的版本，
        才给出指纹；否则返回 (None, 未就绪原因列表)，由调用方决定何时再试。
        """
        st=self.state();rows=[];waiting=[]
        waiting_text={ADOPT_UNAPPROVED:' 尚未验收',ADOPT_MISSING:' 视频文件缺失',
                      ADOPT_REPLACED:' 视频已被替换，需重新验收',ADOPT_UNREADABLE:' 视频无法读取'}
        for shot in self.episode['shots']:
            if shot.get('video_deleted'):continue
            v,reason=adopted_edit_version(st['shots'].get(shot['id']),self.root)
            if v is None:
                waiting.append(shot['id']+waiting_text.get(reason,' 视频不可用'));continue
            rows.append({'shot':shot['id'],'version':v['version'],'sha256':v['sha256']})
        if waiting:return None,waiting
        if not rows:return None,['本集没有可剪辑的镜头']
        return fingerprint(rows),rows

    def assemble(self,shot_ids=None,skip_unready=False,report=None):
        """拼装成片。skip_unready=True：跳过未验收／文件缺失的镜头，只在没有任何可用镜头时报错；
        report 传入 dict 时会写入 skipped（未就绪镜头与原因），供界面提示。"""
        with self.lock():
            st=self.state(); chosen=[];skipped=[]
            selected=set(shot_ids) if shot_ids is not None else None
            available={s['id'] for s in self.episode['shots'] if not s.get('video_deleted')}
            if selected is not None and (not selected or selected-available):raise ValueError('勾选镜头为空或已失效，请重新选择')
            for shot in self.episode['shots']:
                if shot.get('video_deleted') or (selected is not None and shot['id'] not in selected):continue
                v,reason=adopted_edit_version(st['shots'].get(shot['id']),self.root)
                if v is None:
                    if reason==ADOPT_UNAPPROVED:
                        if not skip_unready: raise ValueError(shot['id']+'缺少已下载、质检及验收通过的视频，请先验收或取消勾选')
                        skipped.append(shot['id']+' 缺少已下载、质检及验收通过的视频');continue
                    if reason==ADOPT_MISSING:
                        if not skip_unready: raise ValueError(shot['id']+'的视频文件缺失，请重新生成或取消勾选')
                        skipped.append(shot['id']+' 的视频文件缺失');continue
                    if reason==ADOPT_UNREADABLE:
                        if not skip_unready: raise ValueError(shot['id']+'的视频无法读取，请重新生成或取消勾选')
                        skipped.append(shot['id']+' 的视频无法读取');continue
                    if not skip_unready: raise ValueError('视频已被替换，请重新验收')
                    skipped.append(shot['id']+' 的视频已被替换，需重新验收');continue
                chosen.append((shot,v,self.root/v['file']))
            coverage={'included':[shot['id'] for shot,_,_ in chosen],
                      'expected':len(available if selected is None else selected),
                      'duration':round(sum(float(shot.get('duration') or 0) for shot,_,_ in chosen),3),
                      'skipped':list(skipped)}
            if report is not None:report.update(coverage)
            if not chosen:
                if skipped:raise ValueError('没有可剪辑的镜头；'+'；'.join(skipped))
                raise ValueError('没有可剪辑的镜头')
            shot_names=[shot['id'] for shot,_,_ in chosen]
            full_name='_'.join(shot_names)
            # Keep paths short on Windows; the manifest below records every shot.
            label=full_name if len(full_name)<=100 else '_'.join(shot_names[:5])+f'_等{len(shot_names)}镜'
            from project_stages import exports
            parent=exports(self.root);parent.mkdir(parents=True,exist_ok=True)
            out=dated_path(parent,label)
            out.mkdir()
        return self._encode(chosen,out,coverage)

    def publish_edit_bundle(self, out, master, report, chosen):
        """成片完整发布后，再登记与其绑定的质检报告和剪辑清单。

        先把「成片＋质检＋来源清单」合成一份 ``edit_bundle.json`` 一次性原子落盘，再写两份可读索引。
        索引任一份写失败都能靠这份 bundle 恢复，不会再出现「有清单没质检」或反过来的半份成果；
        界面和交付据此核对真实成片来源。
        """
        out = Path(out).resolve()
        master = Path(master).resolve()
        if not master.is_file() or not master.is_relative_to(out):
            raise ValueError('成片尚未安全发布，不能登记剪辑成果')
        manifest = [
            {'shot': shot['id'], 'version': version['version'], 'sha256': version['sha256']}
            for shot, version, _ in chosen
        ]
        save(out/EDIT_BUNDLE_NAME, {
            'master': master.name, 'master_sha256': file_hash(master),
            'output_spec': report.get('output_spec'), 'qc': report,
            'manifest': manifest, 'coverage': report.get('coverage') or {},
            'published_at': time.time(),
        })
        save(out/QC_NAME, report)
        save(out/EDIT_MANIFEST_NAME, manifest)

    def publish_edit_lists(self, out, chosen, spec):
        """成片之外再给剪辑软件一份 EDL／FCPXML／分轨素材清单；失败只记日志，不影响已发布的成片。"""
        import logging
        from edit_export import export_texts, TRACKS_NAME
        try:
            clips = [{'shot': shot['id'], 'file': shot['id'] + '.mp4', 'duration': shot['duration']}
                     for shot, _version, _path in chosen]
            sources = {shot['id']: {'version': version.get('version'), 'sha256': version.get('sha256')}
                       for shot, version, _path in chosen}
            for name, content in export_texts(Path(out).name, clips, spec, sources).items():
                if name == TRACKS_NAME:
                    save(Path(out) / name, content)
                else:
                    save_text(Path(out) / name, content)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            logging.getLogger(__name__).warning('剪辑软件导出清单未生成：%s', exc)

    def _encode(self,chosen,out,coverage=None):
        # 编码放在项目锁之外：ffmpeg 可能持续几分钟，占着锁会让同时进行的下载／验收全部报「另一操作正在运行」。
        from script_contract import output_filter,loudness_filter,overlay_metrics
        spec=self.output_spec()
        listing=[]
        for shot,v,path in chosen:
            dest=out/(shot['id']+'.mp4')
            vf=output_filter(spec)
            if shot.get('post_overlay'):
                import shutil
                font_source='C:/Windows/Fonts/msyh.ttc'
                if Path(font_source).is_file():
                    shutil.copyfile(font_source,out/'font.ttc')
                    save_text(out/'label.txt', shot['post_overlay'])
                    metrics=overlay_metrics(spec)
                    vf+=',drawtext=fontfile=font.ttc:textfile=label.txt:fontsize=%d:fontcolor=white:box=1:boxcolor=black@0.6:x=%d:y=%d'%(metrics['fontsize'],metrics['x'],metrics['y'])
            from agent.media import probe
            streams=probe(path,self.cfg).get('streams',[])
            has_audio=any(stream.get('codec_type')=='audio' for stream in streams)
            args=[self.cfg['ffmpeg'],'-y','-v','error','-i',path]
            if not has_audio:args+=['-f','lavfi','-i','anullsrc=channel_layout=stereo:sample_rate=48000']
            args+=['-map','0:v:0','-map','0:a:0' if has_audio else '1:a:0','-vf',vf]
            if has_audio:args+=['-af',loudness_filter(spec)]
            else:args+=['-shortest']
            args+=['-ar','48000','-ac','2','-c:v','libx264','-preset','fast','-crf','20','-c:a','aac',dest]
            command(args,cwd=out)
            if not has_audio:
                save(out/(shot['id']+'_音轨说明.json'),{'shot':shot['id'],'source_has_audio':False,'action':'补齐静音音轨，仅用于拼接，不生成对白或音效'})
            listing.append("file '"+dest.name+"'")
        save_text(out/'concat.txt', '\n'.join(listing))
        master=out/('MASTER.mp4')
        pending_master=temporary_path(master, '.partial.mp4')
        try:
            command([self.cfg['ffmpeg'],'-v','error','-f','concat','-safe','1','-i','concat.txt','-c','copy','-movflags','+faststart',pending_master],cwd=out)
            command([self.cfg['ffmpeg'],'-v','error','-xerror','-i',pending_master,'-f','null','-'])
            report=check(pending_master,sum(s['duration'] for s,_,_ in chosen),self.cfg);report['output_spec']=spec
            if coverage is not None:report['coverage']=coverage
            replace(pending_master, master)
        finally:
            if pending_master.exists():
                from file_cache import remove_temporary_file
                remove_temporary_file(pending_master)
        self.publish_edit_bundle(out, master, report, chosen)
        self.publish_edit_lists(out, chosen, spec)
        if report['errors']: raise ValueError('成片技术检查未通过，报告已保存')
        return str(master)
    def output_spec(self):
        """本项目的正式交付规格：画幅／分辨率／帧率来自制作锁，缺省才用出厂默认。"""
        from stage_config import workflow_lock
        from script_contract import resolve_output_spec
        return resolve_output_spec(workflow_lock(self.root))

    def output_spec_text(self):
        """给界面的一行实际规格（导出前显示「实际怎么出」）。"""
        from script_contract import describe_output_spec
        return describe_output_spec(self.output_spec())
