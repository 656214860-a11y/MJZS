"""One application, isolated data-only projects."""
import uuid, re, time, copy, os, logging
from functools import wraps
from datetime import datetime
from pathlib import Path
from storyboard_paths import media_root
from agent.core import file_hash
from episode_contract import validate_episode, relative
import project_stages
from storage_maintenance import remove_project_link_node
from file_cache import read_json as cached_read_json
from service_contract import SystemError, success

_LOG = logging.getLogger(__name__)


def _project_write_result(operation):
    """将项目服务的环境写入失败收口为统一结果，保留输入校验异常。"""
    @wraps(operation)
    def wrapped(*args, **kwargs):
        try:
            return success(operation(*args, **kwargs))
        except OSError as exc:
            _LOG.exception('项目登记写入失败：%s', operation.__name__)
            return SystemError('项目登记未能保存，请检查磁盘或文件占用后重试。',
                               data={'cause': str(exc), 'operation': operation.__name__})
    return wrapped

def _slug(path):
    return re.sub(r'_\d{8}(?:_\d+)?$','',Path(path).name)


def _episode_project_root(value):
    """从旧 ``episode_*`` 指针取项目根；不碰磁盘，也不递归。"""
    if not isinstance(value,str) or not value:return None
    path=Path(value)
    stage_names=set(project_stages.STAGES.values())
    for ancestor in (path,*path.parents):
        if ancestor.name in stage_names:
            return ancestor.parent
    return None


def _same_renamed_prefix(left,right):
    """只作为没有配置指纹时的保守二级匹配。"""
    left_date=re.search(r'(\d{8})(?:_\d+)?$',left.name)
    right_date=re.search(r'(\d{8})(?:_\d+)?$',right.name)
    return bool(left_date and right_date and left_date.group(1)==right_date.group(1)
                and _slug(left)==_slug(right))

def reconcile_missing(projects_info, base):
    """只扫项目库一级，找回资源管理器改名后失效的登记。无 Tk、无写入。"""
    base=Path(base); info=copy.deepcopy(projects_info); missing=[x for x in info.get('projects',[]) if not Path(x.get('path','')).is_dir()]
    if not missing:return {'state':'none','info':info,'matches':{}}
    candidates=[]
    for p in base.iterdir():
        # ``工作流任务`` 是项目库内回收站；历史回收站绝不回流到下一轮扫描。
        if not p.is_dir() or p.name=='工作流任务' or '工作流任务' in p.parts:continue
        cfg=p/'config.json'
        if not cfg.is_file() and not any((p/name).is_dir() for name in project_stages.STAGES.values()):continue
        try:data=cached_read_json(cfg) if cfg.is_file() else {}
        except (OSError,ValueError):continue
        candidates.append((p,data if isinstance(data,dict) else {}))
    matches={}
    for item in missing:
        old=Path(item['path']); found=[]
        for p,cfg in candidates:
            refs=(cfg.get('episode_dir',''),cfg.get('episode_file',''))
            high=any(_episode_project_root(r)==old for r in refs)
            mid=(all((p/name).is_dir() for name in project_stages.STAGES.values())
                 and _same_renamed_prefix(p,old))
            if high or mid:found.append(str(p))
        matches[item['path']]=found
    return {'state':'found' if any(matches.values()) else 'new','info':info,'matches':matches,
            'candidates':[str(p) for p,_ in candidates]}

def needs_cleanup_after_open_error(error):
    """仅在项目根目录已不存在时才提示清理残留登记。

    ``episode.json`` 是初步分镜及之后阶段的工作集，不是项目存在性的
    判据。剧本准备/剧本结构阶段尚未生成分镜时仍必须可以打开项目。
    """
    text=str(error)
    return '项目目录不存在或已被移动' in text


def is_missing_storyboard_open_error(error):
    """判断是否仅因尚未采用分镜而无法建立后续阶段工作集。"""
    return '项目里找不到镜头 JSON' in str(error)

class Projects:
    def __init__(self, app, *, gateway=None, migrate_legacy=True):
        self.app=Path(app); self.registry=self.app/'projects.json'; self.gateway=gateway
        self._require_gateway()
        cfg=self._read_json(self.app/'config.json') if (self.app/'config.json').is_file() else {}
        if not isinstance(cfg,dict):cfg={}
        self.downloads=Path(cfg.get('downloads_root','D:/漫剧下载'))
        self.base=self.downloads/'项目'; self.base.mkdir(parents=True,exist_ok=True)
        # 桌面首帧不能为了旧版数据迁移而递归遍历整个程序目录。命令行导入等
        # 非 UI 调用仍维持原有的同步兼容行为；Desktop 会在首帧后把迁移交给 worker。
        self.legacy_migration_pending=not self.registry.exists()
        if self.legacy_migration_pending and migrate_legacy:
            self._migrate()
        info=self._read_json(self.registry) if self.registry.exists() else {}
        info=dict(info) if isinstance(info,dict) else {}
        if 'active' not in info:info['active']=None
        if not isinstance(info.get('projects'),list):info['projects']=[]
        self.info=info

    def refresh_registry(self):
        """在后台迁移完成后由 UI 线程刷新内存登记。"""
        info=self._read_json(self.registry)
        info=dict(info) if isinstance(info,dict) else {}
        if 'active' not in info:info['active']=None
        if not isinstance(info.get('projects'),list):info['projects']=[]
        self.info=info
        self.legacy_migration_pending=False
        return self.info

    def _require_gateway(self):
        """L2 项目服务没有注入读写边界时，拒绝一切项目操作。"""
        required=('read_json','read_bytes','publish_json','publish_bytes','restore_bytes','copy_file','copy_tree')
        if not isinstance(self.gateway,dict) or any(not callable(self.gateway.get(name)) for name in required):
            raise TypeError('项目操作需要由 L3 注入项目登记读写网关。')
        self._read_json=self.gateway['read_json'];self._read_bytes=self.gateway['read_bytes']
        self._publish_json=self.gateway['publish_json'];self._publish_bytes=self.gateway['publish_bytes']
        self._restore_bytes=self.gateway['restore_bytes'];self._copy_file=self.gateway['copy_file'];self._copy_tree=self.gateway['copy_tree']

    def _migrate(self):
        if self.registry.exists():
            return self.refresh_registry()
        config_path=self.app/'config.json'
        cfg=self._read_json(config_path) if config_path.is_file() else {}
        if not isinstance(cfg,dict):cfg={}
        src=Path(cfg.get('episode_dir',self.app/'episode'))
        # 新安装或测试沙箱没有旧版 episode 时，不应因为一次迁移探测阻断程序启动。
        # 保留空注册表；用户随后可通过“新建项目/打开项目”进入正常流程。
        if not (src/'episode.json').is_file():
            self._publish_json(self.registry,{'active':None,'projects':[]})
            return self.refresh_registry()
        ep=self._read_json(src/'episode.json'); title=str(ep.get('title') or '项目')
        slug=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',title)[:50].rstrip('. ')
        dst=self.base/(slug+'_EP001_'+uuid.uuid4().hex[:6])
        dst.mkdir(); self._copy_tree(src,project_stages.storyboard(dst)/'分镜拆分')
        for name,target in (('data',dst/'data'),('exports',project_stages.exports(dst))):
            if (self.app/name).exists():
                target.parent.mkdir(parents=True,exist_ok=True)
                self._copy_tree(self.app/name,target,ignore=lambda _folder, names: {'operation.lock'} & set(names))
                for p in (self.app/name).rglob('*'):
                    if p.is_file() and p.name!='operation.lock' and file_hash(p)!=file_hash(target/p.relative_to(self.app/name)):
                        raise ValueError('迁移校验失败，原文件仍保留')
        cfg['episode_dir']=str(project_stages.storyboard(dst)/'分镜拆分');cfg['assets_root']=str(self.base)
        credentials=self.app/'private'
        if not Path(cfg.get('project_dir','.')).exists() and (credentials/'.env').exists():cfg['project_dir']=str(credentials)
        self._publish_json(dst/'config.json',cfg); self.organize(dst)
        self._publish_json(self.registry,{'active':str(dst),'projects':[{'name':title,'path':str(dst)}]})
        return self.refresh_registry()

    @_project_write_result
    def migrate(self):
        return self._migrate()
    def organize(self,root):
        root=Path(root); base=project_stages.assets(root); assets=self._read_json(base/'assets.json') if (base/'assets.json').exists() else {}
        if not isinstance(assets,dict):assets={}
        for kind in ('characters','scenes','props'): (base/'assets'/kind).mkdir(parents=True,exist_ok=True)
        for aid,a in assets.items():
            if not a.get('image'):continue
            p=(base/relative(a['image'])).resolve()
            if not p.is_relative_to(base.resolve()) or not p.is_file():continue
            # An entire shot used as a region reference must not be relabeled a portrait.
            if a.get('reference_region'):continue
            dest=base/'assets'/('scenes' if aid.startswith('LOC') else ('props' if aid.startswith('PROP') else 'characters'))/(aid+p.suffix)
            if p!=dest.resolve():self._copy_file(p,dest)
            a['image']=dest.relative_to(base).as_posix()
        self._publish_json(base/'assets.json',assets)
        for name in project_stages.STAGES.values(): (root/name).mkdir(exist_ok=True)
        project_stages.audio(root).mkdir(parents=True,exist_ok=True)
        project_stages.subtitles(root).mkdir(parents=True,exist_ok=True)

    def ensure_stage_dirs(self,root):
        """认领后只补目录骨架；不得重写或搬动既有项目文件。"""
        root=Path(root)
        for name in project_stages.STAGES.values():
            (root/name).mkdir(exist_ok=True)
        project_stages.audio(root).mkdir(parents=True,exist_ok=True)
        project_stages.subtitles(root).mkdir(parents=True,exist_ok=True)

    @staticmethod
    def _replace_root(value,old,new):
        if not isinstance(value,str):return value
        try:
            return str(new / Path(value).relative_to(old))
        except ValueError:
            return value

    def _live_path_writes(self,old,new,info):
        """准备所有活路径改写，先读完再写，供事务及测试共同使用。"""
        writes=[]
        def changed_json(path, transform):
            if not path.is_file():return
            data=cached_read_json(path)
            if not isinstance(data,dict):return
            updated=transform(copy.deepcopy(data))
            if updated!=data:
                import json
                writes.append((path,json.dumps(updated,ensure_ascii=False,indent=2).encode('utf-8')))
        import json
        writes.append((self.registry,json.dumps(info,ensure_ascii=False,indent=2).encode('utf-8')))
        def rewrite_config(data):
            for key in ('episode_dir','episode_file'):
                data[key]=self._replace_root(data.get(key),old,new)
            return data
        changed_json(new/'config.json',rewrite_config)
        def rewrite_local_registry(data):
            data['active']=self._replace_root(data.get('active'),old,new)
            for item in data.get('projects',[]):
                if isinstance(item,dict):item['path']=self._replace_root(item.get('path'),old,new)
            return data
        changed_json(new/'projects.json',rewrite_local_registry)
        cloud=new/'cloud_video'
        if cloud.is_dir():
            for child in cloud.iterdir():
                if child.is_dir():changed_json(child/'config.json',rewrite_config)
        return writes

    def _write_transaction(self,writes):
        """逐文件原子发布；任一失败以原字节回滚，留下的内容与开始前一致。"""
        previous=[(path,self._read_bytes(path) if path.exists() else None) for path,_ in writes]
        committed=[]
        try:
            for path,content in writes:
                self._publish_bytes(path,content);committed.append(path)
        except Exception:
            rollback_error=None
            for path,before in reversed(previous):
                try:self._restore_bytes(path,before)
                except Exception as exc:rollback_error=exc
            if rollback_error:raise RuntimeError('项目登记同步失败，且回滚失败') from rollback_error
            raise

    def _claim_reconciled(self,old_path,new_path):
        """把一条已确认的失效登记认领到新目录，并同步唯一允许变动的活路径。"""
        old=Path(old_path);new=Path(new_path)
        if not new.is_dir() or new.parent.resolve()!=self.base.resolve():
            raise ValueError('认领目录必须是项目库一级的项目目录')
        info=copy.deepcopy(self.info)
        item=next((x for x in info.get('projects',[]) if x.get('path')==str(old)),None)
        if item is None:raise ValueError('失效项目未登记')
        item['path']=str(new);item['name']=_slug(new)
        if info.get('active')==str(old):info['active']=str(new)
        self._write_transaction(self._live_path_writes(old,new,info))
        self.info=info
        self.ensure_stage_dirs(new)
        return str(new)

    @_project_write_result
    def claim_reconciled(self,old_path,new_path):
        return self._claim_reconciled(old_path,new_path)

    @_project_write_result
    def reconcile_missing(self,path,selected=None):
        """包装纯扫描服务：自动仅接受一对一，多个候选交给 UI 选择。"""
        result=reconcile_missing(self.info,self.base)
        choices=result['matches'].get(str(path),[])
        if selected is not None:
            if str(selected) not in choices:raise ValueError('所选目录不是该失效项目的候选目录')
            return {'state':'claimed','path':self._claim_reconciled(path,selected),'result':result}
        if len(choices)==1:
            return {'state':'claimed','path':self._claim_reconciled(path,choices[0]),'result':result}
        return {'state':'confirm' if len(choices)>1 else 'missing','choices':choices,'result':result}

    @_project_write_result
    def register_discovered_project(self,path):
        """将扫描到但不属于失效登记的一级目录作为新项目登记。"""
        candidate=Path(path)
        if candidate.parent.resolve()!=self.base.resolve() or candidate.name=='工作流任务':
            raise ValueError('只能登记项目库一级的非回收站目录')
        result=reconcile_missing(self.info,self.base)
        if str(candidate) not in result['candidates']:
            raise ValueError('该目录不是可登记的项目候选目录')
        if str(candidate) in [x.get('path') for x in self.info.get('projects',[])]:
            raise ValueError('项目已登记')
        info=copy.deepcopy(self.info)
        stamp=datetime.fromtimestamp(candidate.stat().st_mtime)
        info['projects'].append({'name':_slug(candidate),'path':str(candidate),
                                 'created_at':datetime.combine(stamp.date(),datetime.min.time()).timestamp()})
        self._publish_json(self.registry,info);self.info=info
        return str(candidate)

    @_project_write_result
    def clear_missing_registration(self,path):
        """普通目录已不存在时只清登记，绝不尝试移动或删除磁盘文件。"""
        if Path(path).exists():raise ValueError('项目目录仍存在，请使用“删除选中项目”移入回收站')
        if path not in [x.get('path') for x in self.info.get('projects',[])]:raise ValueError('项目未登记')
        info=copy.deepcopy(self.info)
        info['projects']=[x for x in info['projects'] if x.get('path')!=path]
        if info.get('active')==path:info['active']=info['projects'][0]['path'] if info['projects'] else None
        self._publish_json(self.registry,info);self.info=info
    @_project_write_result
    def set_status(self,path,status):
        if status not in ('making','completed'):raise ValueError('无效的项目状态')
        item=next((p for p in self.info['projects'] if p['path']==path),None)
        if item is None:raise ValueError('项目未登记')
        item['status']=status;self._publish_json(self.registry,self.info)
    @_project_write_result
    def activate(self,path):
        if path not in [x['path'] for x in self.info['projects']]:raise ValueError('项目未登记')
        self.info['active']=path;self._publish_json(self.registry,self.info)
    def deletion_target(self,path):
        if path not in [x['path'] for x in self.info['projects']]:raise ValueError('项目未登记，不能删除')
        raw=Path(path);target=raw.resolve();base=self.base.resolve()
        if target.parent!=base or target==self.app.resolve() or raw.is_symlink() or raw.is_junction():
            raise ValueError('只允许删除项目根目录下的独立项目，拒绝链接或越界路径')
        return target

    @_project_write_result
    def delete(self,path):
        target=self.deletion_target(path)
        if not target.exists():
            raise ValueError('项目目录已不存在；可选择“只清除登记，不动磁盘”。')
        # target 是已登记的完整用户项目；移动至项目库回收站而非递归永久删除。
        from storage_maintenance import recycle_paths
        try:records=recycle_paths(self.base,[target],'删除项目')
        except FileNotFoundError as exc:
            raise ValueError('项目目录已不存在；可选择“只清除登记，不动磁盘”。') from exc
        except OSError as exc:
            raise ValueError('项目目录仍被占用，项目入口未删除。请关掉占用它的窗口后重试。') from exc
        if not records or target.exists():
            raise ValueError('项目未能安全移入回收站，项目入口已保留。')
        self.info['projects']=[x for x in self.info['projects'] if x['path']!=path]
        if self.info['active']==path:self.info['active']=self.info['projects'][0]['path'] if self.info['projects'] else None
        self._publish_json(self.registry,self.info)
    @_project_write_result
    def unlink_registered_project(self,path):
        """只移除登记项目自身的目录链接，绝不递归进入它指向的真实目录。"""
        if path not in [x['path'] for x in self.info['projects']]:raise ValueError('项目未登记，不能删除')
        raw=Path(path);base=self.base.resolve()
        if raw.parent.resolve()!=base or not (raw.is_symlink() or raw.is_junction()):
            raise ValueError('只允许移除项目根目录下的项目链接')
        try:
            if not remove_project_link_node(raw):
                raise OSError('project link removal rejected')
        except OSError as exc:
            raise ValueError('项目链接仍被占用，项目入口未删除。请关闭占用它的窗口后重试。') from exc
        if raw.exists() or raw.is_symlink():raise ValueError('项目链接未能删除，项目入口已保留。')
        self.info['projects']=[x for x in self.info['projects'] if x['path']!=path]
        if self.info['active']==path:self.info['active']=self.info['projects'][0]['path'] if self.info['projects'] else None
        self._publish_json(self.registry,self.info)
    @_project_write_result
    def create(self,name,source=None):
        name=name.strip()
        if not name:raise ValueError('请填写项目名称')
        active=self.info.get('active')
        config_path=(Path(active) if active else self.app)/'config.json'
        if not config_path.is_file():config_path=self.app/'config.json'
        cfg=self._read_json(config_path)
        if not isinstance(cfg,dict):cfg={}
        slug=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',name)[:50].rstrip('. ')
        # 项目目录只展示创建日期；当天重名项目使用序号，既不覆盖也不把具体时间露给用户。
        day=datetime.now().strftime('%Y%m%d')
        dst=self.base/(slug+'_'+day)
        serial=2
        while dst.exists():
            dst=self.base/(slug+'_'+day+'_'+str(serial));serial+=1
        dst.mkdir()
        story=project_stages.storyboard(dst)/'分镜拆分';story.mkdir(parents=True)
        base=project_stages.assets(dst);(project_stages.stage(dst,'frames')/'frames').mkdir(parents=True)
        assets={}
        if source:
            source=Path(source);ep=self._read_json(source)
            af=source.parent/'assets.json';assets=self._read_json(af) if af.exists() else None
            validate_episode(ep,media_root(source),assets)
            for s in ep['shots']:
                p=(media_root(source)/relative(s['frame'])).resolve()
                if p.is_file():d=project_stages.stage(dst,'frames')/relative(s['frame']);d.parent.mkdir(parents=True,exist_ok=True);self._copy_file(p,d)
            for a in (assets or {}).values():
                if not a.get('image'):continue
                rel=relative(a['image']);p=(source.parent/rel).resolve()
                if not p.is_relative_to(source.parent.resolve()):raise ValueError('资产路径越界')
                if p.is_file():d=base/rel;d.parent.mkdir(parents=True,exist_ok=True);self._copy_file(p,d)
        else:
            ep={'episode_id':'EP001','title':name,'shots':[{'id':'SH001','title':'待编写','duration':5,'characters':['CHAR_001'],'location':'LOC_001','frame':'frames/SH001.png','video_prompt':'待填写镜头画面、动作和对白','dialogue':[]}]}
        self._publish_json(story/'episode.json',ep);self._publish_json(base/'assets.json',assets or {})
        cfg.update(episode_dir=str(story),episode_file=str(story/'episode.json'),asset_library_dir='05资产管理',live_enabled=False,budget_seconds=0,reserve_seconds=0,video_backend='comfy')
        self._publish_json(dst/'config.json',cfg);self.organize(dst)
        self.info['projects'].append({'name':name,'path':str(dst),'created_at':datetime.now().timestamp()});self.info['active']=str(dst);self._publish_json(self.registry,self.info)
        return dst

    @_project_write_result
    def register_restored_projects(self, paths):
        """只登记恢复服务明确返回的一级目录，不扫描或臆造旧登记元数据。"""
        base = self.base.resolve()
        info = copy.deepcopy(self.info)
        known = {item.get('path') for item in info.get('projects', [])}
        added = []
        for value in paths:
            path = Path(value)
            if (path.is_symlink() or path.is_junction() or not path.is_dir()
                    or path.resolve().parent != base or path.name == '工作流任务'):
                raise ValueError('只能重新登记恢复的项目库一级独立目录')
            path = path.resolve()
            if str(path) in known:
                continue
            info['projects'].append({'name': _slug(path), 'path': str(path),
                                     'created_at': path.stat().st_mtime})
            known.add(str(path)); added.append(path)
        if added:
            if not info.get('active'):
                info['active'] = str(added[0])
            self._publish_json(self.registry, info)
            self.info = info
        return added
