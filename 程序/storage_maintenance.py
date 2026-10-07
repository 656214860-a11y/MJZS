"""Conservative project cleanup; run only after the UI has closed."""
import os, shutil, subprocess, sys, time
from pathlib import Path
from agent.core import save
from file_cache import recycled, read_json
from platform_tools import launch_background

PROGRAM=Path(__file__).resolve().parent
def downloads_root():
    cfg_file = PROGRAM / "config.json"
    if cfg_file.is_file():
        try:
            cfg = read_json(cfg_file)
            return Path(cfg.get("downloads_root", "D:/漫剧下载")) / "项目"
        except (OSError, ValueError):
            pass
    return Path("D:/漫剧下载") / "项目"
AGE_SECONDS=7*24*3600
PENDING={'queued','running','succeeded','unknown','submitting'}

def launch_cleanup(app_root=None):
    program=Path(app_root or PROGRAM)
    launch_background([sys.executable,str(program/'storage_maintenance.py'),'--cleanup'],
                      stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def _within(child,parent):
    return child.resolve().is_relative_to(parent.resolve())

def _recycle_base(root):
    """自动维护的唯一回收站；从不扫描或再次清理其中的历史成果。"""
    return Path(root) / '工作流任务' / '回收站'


def recycle_base(root):
    """返回 ``root`` 唯一回收站的位置；不创建目录也不扫描其历史内容。"""
    return _recycle_base(Path(root))


def read_recycle_batch(root, batch):
    """只读一个已登记回收批次，兼容 ``items`` 与早期 ``files`` 清单。

    列表 UI 也必须走与恢复相同的根目录边界，不能把手工传入的目录当作
    可恢复批次。条目保留原始相对路径供展示；真正移动仍只由
    :func:`restore_recycle_batch` 完成并再次完整校验。
    """
    root = Path(root).resolve()
    batch = Path(batch).resolve()
    base = _recycle_base(root).resolve()
    if not batch.is_relative_to(base):
        raise ValueError('恢复批次不在当前项目回收站中')
    manifest = batch / '恢复位置.json'
    try:
        data = read_json(manifest)
    except (OSError, ValueError) as exc:
        raise ValueError('恢复清单无法读取：' + str(exc)) from exc
    rows = data.get('items') if isinstance(data, dict) else None
    if not isinstance(rows, list):
        rows = data.get('files') if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError('恢复清单格式无效')
    items = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('恢复清单格式无效')
        source = str(row.get('source', row.get('original', ''))).replace('\\', '/')
        recycled_path = str(row.get('recycle_path', row.get('recycled', ''))).replace('\\', '/')
        if not source or not recycled_path:
            raise ValueError('恢复清单格式无效')
        items.append({'source': source, 'recycle_path': recycled_path})
    return {
        'batch': batch,
        'created_at': str(data.get('created_at', '')) if isinstance(data, dict) else '',
        'reason': str(data.get('reason', '')) if isinstance(data, dict) else '',
        'items': items,
    }


def _recycle(path, root, batch):
    """把受控项目内文件移动到回收站，返回恢复记录而非永久删除。"""
    path=Path(path)
    root=Path(root)
    if path.is_symlink() or path.is_junction() or not _within(path,root):return None
    if not path.exists():return None
    relative=path.resolve().relative_to(root.resolve())
    target=Path(batch) / relative
    if target.exists():return None
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.move(str(path),str(target))
    return {'source':relative.as_posix(),'recycle_path':target.relative_to(root).as_posix()}


def recycle_paths(root, paths, reason, now=None):
    """供用户可见的删除入口复用的受控回收接口。"""
    root=Path(root).resolve(); now=now or time.time()
    batch=_recycle_base(root)/('自动维护_'+time.strftime('%Y%m%d_%H%M%S',time.localtime(now)))
    records=[]
    for path in paths:
        record=_recycle(path,root,batch)
        if record is not None:records.append(record)
    if records:
        manifest=batch/'恢复位置.json'
        try:previous=read_json(manifest) if manifest.is_file() else {}
        except (OSError,ValueError):previous={}
        previous['created_at']=time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(now))
        previous['reason']=str(reason)
        previous['items']=[*previous.get('items',[]),*records]
        save(manifest,previous)
        recycled((root / record['source'], root / record['recycle_path']) for record in records)
    return records


def restore_recycle_batch(root, batch, sources=None):
    """恢复一个回收批次的文件或目录，目标冲突或清单异常时零移动。

    兼容自动维护的 ``items`` 清单和分镜页早期的 ``files`` 清单。批次必须位于当前
    项目回收站内，不能借由手工编辑清单越界移动任意文件。
    """
    root = Path(root).resolve()
    batch = _restore_location(root, batch, '恢复批次不在当前项目回收站中')
    recycle_base = _recycle_base(root).resolve()
    if not batch.is_relative_to(recycle_base):
        raise ValueError('恢复批次不在当前项目回收站中')
    manifest = batch / '恢复位置.json'
    try:
        data = read_json(manifest)
    except (OSError, ValueError) as exc:
        raise ValueError('恢复清单无法读取：' + str(exc)) from exc
    rows = data.get('items') if isinstance(data, dict) else None
    if not isinstance(rows, list):
        rows = data.get('files') if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError('恢复清单为空')
    wanted = None if sources is None else {str(item).replace('\\', '/') for item in sources}
    moves = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('恢复清单格式无效')
        source_text = row.get('recycle_path', row.get('recycled'))
        target_text = row.get('source', row.get('original'))
        if wanted is not None and str(target_text or '').replace('\\', '/') not in wanted:
            continue
        source = _restore_location(root, source_text)
        target = _restore_location(root, target_text)
        if (not source.is_relative_to(batch) or not target.is_relative_to(root)
                or target.is_relative_to(recycle_base) or source.is_symlink() or source.is_junction()
                or not (source.is_file() or source.is_dir()) or target.exists()):
            raise ValueError('恢复目标不存在、已被占用或超出项目范围')
        if source == batch or any(
                source.is_relative_to(old_source) or old_source.is_relative_to(source)
                or target.is_relative_to(old_target) or old_target.is_relative_to(target)
                for old_source, old_target in moves):
            raise ValueError('恢复清单含重复或相互嵌套的路径')
        moves.append((source, target))
    if not moves:
        raise ValueError('回收站中没有可恢复的指定文件')
    moved = []
    try:
        for source, target in moves:
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)
            moved.append((source, target))
    except OSError as exc:
        for source, target in reversed(moved):
            try:
                source.parent.mkdir(parents=True, exist_ok=True)
                target.rename(source)
            except OSError:
                pass
        raise ValueError('恢复未完成，已回滚：' + str(exc)) from exc
    recycled(moves)
    return [target for _source, target in moves]


def restore_latest_recycled_path(root, path):
    """仅恢复 ``path`` 最近一次回收记录，不连带恢复同批其他用户文件。"""
    root = Path(root).resolve()
    target = Path(path).resolve()
    if not _within(target, root):
        raise ValueError('恢复目标超出当前项目范围')
    relative = target.relative_to(root).as_posix()
    base = _recycle_base(root)
    if not base.is_dir():
        raise ValueError('没有可恢复的删除记录')
    for batch in sorted((item for item in base.iterdir() if item.is_dir()), key=lambda item: item.name, reverse=True):
        manifest = batch / '恢复位置.json'
        try:
            data = read_json(manifest)
        except (OSError, ValueError):
            continue
        rows = data.get('items', data.get('files', [])) if isinstance(data, dict) else []
        if any(isinstance(row, dict) and str(row.get('source', row.get('original', ''))).replace('\\', '/') == relative for row in rows):
            return restore_recycle_batch(root, batch, sources=(relative,))
    raise ValueError('没有可恢复的删除记录')


def restore_latest_recycled_child(root, parent, stem, suffixes):
    """按目录、文件名和后缀恢复最近回收的一项，且不连带同批其他文件。"""
    root = Path(root).resolve()
    parent = Path(parent).resolve()
    if not _within(parent, root):
        raise ValueError('恢复目录超出当前项目范围')
    allowed = {str(suffix).lower() for suffix in suffixes}
    base = _recycle_base(root)
    if base.is_dir():
        for batch in sorted((item for item in base.iterdir() if item.is_dir()), key=lambda item: item.name, reverse=True):
            manifest = batch / '恢复位置.json'
            try:
                data = read_json(manifest)
            except (OSError, ValueError):
                continue
            rows = data.get('items', data.get('files', [])) if isinstance(data, dict) else []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                relative = str(row.get('source', row.get('original', ''))).replace('\\', '/')
                target = (root / relative).resolve()
                if target.parent == parent and target.stem == str(stem) and target.suffix.lower() in allowed:
                    return restore_recycle_batch(root, batch, sources=(target.relative_to(root).as_posix(),))
    # 旧版资产图片在同目录“历史版本”中留存，尚未具备回收站清单。只读兼容该历史：
    # 新删除始终走 recycle_paths()，这里绝不向旧目录写入或批量搬运。
    history = parent / '历史版本'
    candidates = sorted((item for item in history.glob(str(stem) + '_*')
                         if item.is_file() and not item.is_symlink()
                         and item.suffix.lower() in allowed),
                        key=lambda item: (item.name, item.stat().st_mtime_ns), reverse=True) if history.is_dir() else []
    if candidates:
        source = candidates[0]
        target = parent / (str(stem) + source.suffix.lower())
        if target.exists():
            raise ValueError('恢复目标已存在同名图片')
        source.rename(target)
        return [target]
    raise ValueError('没有可恢复的删除记录')


def remove_project_link_node(path):
    """只移除已经确认的项目入口链接，绝不递归进入其目标目录。"""
    path = Path(path)
    if not (path.is_symlink() or path.is_junction()):
        return False
    try:
        if path.is_symlink():
            path.unlink()
        else:
            os.rmdir(path)
        return True
    except OSError:
        return False


def remove_private_file(path):
    """清除本机私密配置文件；不用于项目内用户成果。"""
    try:
        Path(path).unlink(missing_ok=True)
        return True
    except OSError:
        return False


def remove_regenerable_tree(path, result, *, dry_run=False, stats=None):
    """受控清除可再生缓存树，供退出后的仓库卫生任务复用。

    该入口只接受调用方已完成边界校验的临时或缓存目录；锁定文件保持原状并计入
    ``errors``，避免一个占用项扩大成失败或递归到不受控路径。
    """
    path = Path(path)
    try:
        if dry_run:
            files, size = ((0, path.lstat().st_size) if path.is_file()
                           else (stats(path) if stats else (0, 0)))
            result['removed_entries'] += 1
            result['removed_files'] += files
            result['removed_bytes'] += size
            return True
        if path.is_file() or path.is_symlink():
            size = path.lstat().st_size
            path.unlink()
            result['removed_entries'] += 1
            result['removed_files'] += 1
            result['removed_bytes'] += size
            return True
        files, size = stats(path) if stats else (0, 0)
        for dirpath, dirnames, filenames in os.walk(path, topdown=False, followlinks=False):
            directory = Path(dirpath)
            for name in filenames:
                try:
                    Path(dirpath, name).unlink()
                except OSError:
                    result['errors'] += 1
            for name in dirnames:
                try:
                    Path(dirpath, name).rmdir()
                except OSError:
                    pass
            try:
                if directory != path:
                    directory.rmdir()
            except OSError:
                result['errors'] += 1
        try:
            path.rmdir()
        except OSError:
            result['errors'] += 1
            return False
        result['removed_entries'] += 1
        result['removed_files'] += files
        result['removed_bytes'] += size
        return True
    except OSError:
        result['errors'] += 1
        return False


def clear_generated_workflow_state(project_root, state_path, filename):
    """受控清除 ``workflows`` 下可重建的内部状态文件。"""
    root = Path(project_root).resolve()
    workflows = (root / "workflows").resolve()
    expected = (workflows / filename).resolve()
    candidate = Path(state_path)
    try:
        resolved_candidate = candidate.resolve()
    except OSError:
        return False
    if (
        expected.parent != workflows
        or not _within(expected, root)
        or candidate.is_symlink()
        or resolved_candidate != expected
    ):
        return False
    try:
        candidate.unlink()
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False

def clean_project(root,now=None):
    root=Path(root).resolve();now=now or time.time();removed=[];records=[]
    if root.parent!=downloads_root().resolve() or not (root/'config.json').is_file():return removed
    stamp=time.strftime('%Y%m%d_%H%M%S',time.localtime(now))
    recycle_base=_recycle_base(root)
    batch=recycle_base/('自动维护_'+stamp)

    def recycle(path):
        record=_recycle(path,root,batch)
        if record is None:return False
        records.append(record);removed.append(Path(record['source']));return True

    # Closing the assistant clears every explicitly named history directory.
    # Active creative folders, current storyboards and final outputs are untouched.
    # 清理改为可恢复移动，历史回收站自身永不参与下一轮扫描。
    histories=[p for p in root.rglob('*') if p.name in ('历史版本','分镜历史') and not _within(p,recycle_base)]
    for history in sorted(histories,key=lambda p:len(p.parts),reverse=True):
        try:
            recycle(history)
        except OSError:
            # An occupied history must not prevent cleanup of the other folders.
            continue
    # Completed generation versions: retain newest per shot and all unfinished jobs.
    for ledger in list(root.glob('**/data/state.json'))+list(root.glob('**/06_本地生成/state.json')):
        if not _within(ledger,root):continue
        try:state=read_json(ledger)
        except (OSError,ValueError):continue
        dirty=False
        for shot_id,versions in state.get('shots',{}).items():
            if not isinstance(versions,list) or len(versions)<2:continue
            newest=max(v.get('version',0) for v in versions)
            for version in versions:
                if version.get('version')==newest or version.get('state') in PENDING or version.get('cleaned_at'):continue
                if now-float(version.get('created',now))<AGE_SECONDS:continue
                if version.get('output_dir'):
                    folder=(ledger.parent.parent/version['output_dir']).resolve()
                else:
                    folder=ledger.parent/shot_id/f"v{version['version']:03}"
                if folder.is_dir() and recycle(folder):
                    version.update(cleaned_at=now,file=None,qc_pass=False);dirty=True
        if dirty:
            save(ledger,state)                  # 原子写只有 agent.core.save 一份
    # Empty accidental folders only. Keep the named workflow stages visible.
    for folder in sorted(root.rglob('*'),key=lambda x:len(x.parts),reverse=True):
        if folder.is_dir() and not folder.is_symlink() and not folder.is_junction() and _within(folder,root) and not _within(folder,recycle_base):
            if folder.name in ('历史版本','分镜输入','video_prompts'):
                try:
                    if not any(folder.iterdir()):folder.rmdir();removed.append(folder)
                except OSError:pass
    if records:
        save(batch/'恢复位置.json',{'created_at':time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(now)),
                                  'reason':'自动维护','items':records})
    return removed

def main():
    time.sleep(3)
    root=downloads_root()
    if not root.is_dir():return
    summary=[]
    for project in root.iterdir():
        if project.is_dir() and not project.is_symlink() and not project.is_junction():
            try:summary.extend(clean_project(project))
            except (OSError,ValueError):continue
    log=PROGRAM/'维护记录';log.mkdir(exist_ok=True)
    save(log/'上次关闭清理.json',{'at':time.strftime('%Y-%m-%d %H:%M:%S'),'recycled':[str(p) for p in summary]})

def _restore_location(root, value, message='恢复路径超出项目范围'):
    """解析前检查路径节点与祖先链接；目录移动不遍历内部内容。"""
    path = root / str(value or '')
    if '..' in path.parts or not path.is_relative_to(root) or path == root:
        raise ValueError(message)
    cursor = root
    for part in path.relative_to(root).parts:
        cursor = cursor / part
        if cursor.is_symlink() or cursor.is_junction():
            raise ValueError('恢复路径不能包含链接或连接点')
    return path.resolve()


if __name__=='__main__' and '--cleanup' in sys.argv:main()
