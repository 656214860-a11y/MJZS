"""Conservative project cleanup; run only after the UI has closed."""
import math, os, shutil, subprocess, sys, time, uuid
from pathlib import Path, PurePosixPath
import contract.stage_layout as stage_layout
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
MANIFEST_NAME='恢复位置.json'
BATCH_PREFIX='自动维护_'
# O38：回收批次要「写前计划 → 逐项状态 → 最终提交」，中断后还能恢复或撤回。
# 批次状态：planned（写前清单已落盘，尚未搬完）／committed（全部搬完，可恢复）／
# rolled_back（整批撤回，原文件已回原位）。逐项状态：planned／moved／failed／undone。
BATCH_PLANNED='planned'
BATCH_COMMITTED='committed'
BATCH_ROLLED_BACK='rolled_back'
ITEM_PLANNED='planned'
ITEM_MOVED='moved'
ITEM_FAILED='failed'
ITEM_UNDONE='undone'
# O39：清理老视频前先查成果引用图，只清真正无引用的旧版。
# 成片来源清单的文件名权威在 engine（L3）；L1 不能向上导入，故在此复名并由架构测试锁死一致。
EXPORT_MANIFEST_NAMES=('edit_bundle.json','edit_manifest.json')
# 已定局状态：只有这三种旧版本才可以进入回收候选；其余（含空）一律按「未结算」留住。
SETTLED_STATES=frozenset(('downloaded','failed','rejected'))
RETAIN_UNSETTLED='unsettled'
RETAIN_LOCKED='locked'
RETAIN_EDIT_SOURCE='edit_source'
RETAIN_APPROVED='approved'
RETAIN_LATEST='latest'
RETAIN_FRESH='fresh'
RETAIN_REASONS={RETAIN_UNSETTLED:'任务未结算，等结果取回或查询',
                RETAIN_LOCKED:'用户锁定该版本',
                RETAIN_EDIT_SOURCE:'已进入已发布成片的来源清单',
                RETAIN_APPROVED:'已验收通过的采用版本',
                RETAIN_LATEST:'该镜头最新版本',
                RETAIN_FRESH:'未到项目保留期或创建时间无效'}
VERSION_CLEAN_REASON='超过保留期，且未被采用、未进成片来源、未锁定、任务已定局'

def launch_cleanup(app_root=None):
    program=Path(app_root or PROGRAM)
    launch_background([sys.executable,str(program/'storage_maintenance.py'),'--cleanup'],
                      stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def _within(child,parent):
    return child.resolve().is_relative_to(parent.resolve())

def _recycle_base(root):
    """自动维护的唯一回收站；从不扫描或再次清理其中的历史成果。"""
    return stage_layout.workflow_dir(root, '回收站')


def recycle_base(root):
    """返回 ``root`` 唯一回收站的位置；不创建目录也不扫描其历史内容。"""
    return _recycle_base(Path(root))


OVERWRITE_BACKUP_DIR='覆盖前备份'   # 与回收站同在项目「工作流任务」下


def backup_before_overwrite(root, path, now=None):
    """外部来源覆盖用户可见文件前，把原文件复制到 ``root`` 的「覆盖前备份」并返回副本路径。

    只复制、不移动：原文件仍在原位，调用方随后照常覆盖。文件不存在返回 None；
    越界、链接或复制不完整一律抛错，调用方据此放弃覆盖。
    """
    root=Path(root).resolve(); path=Path(path)
    if not path.is_file():return None
    if path.is_symlink() or not _within(path,root):
        raise ValueError('覆盖前备份只接受项目内的普通文件：'+str(path))
    from agent.core import save_file
    stamp=time.strftime('%Y%m%d_%H%M%S',time.localtime(now if now is not None else time.time()))
    target=(_recycle_base(root).parent/OVERWRITE_BACKUP_DIR/(stamp+'_'+uuid.uuid4().hex[:8])
            /path.resolve().relative_to(root))
    save_file(target,path)   # 原子复制并核对长度；来源变化即放弃
    return target


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
        'state': str(data.get('state', '')) if isinstance(data, dict) else '',
        'items': items,
    }


def batch_name(now=None):
    """批次目录名：秒级时间给人看，UUID 后缀保证同一秒并发也各成一个独立批次。"""
    stamp=time.strftime('%Y%m%d_%H%M%S',time.localtime(now if now is not None else time.time()))
    return BATCH_PREFIX+stamp+'_'+uuid.uuid4().hex[:8]


def _write_batch_manifest(batch, state, records, reason, created_at):
    """把批次清单原子落盘（agent.core.save）：写前计划与逐项状态都靠它保命。"""
    save(Path(batch)/MANIFEST_NAME,
         {'created_at':str(created_at or ''),'reason':str(reason),'state':state,
          'items':[dict(record) for record in records]})


def plan_recycle(path, root, batch):
    """写前计划：只算这一项该去哪，不移动文件；越界／链接／不存在／目标已占一律返回 None。"""
    path=Path(path)
    root=Path(root)
    if path.is_symlink() or path.is_junction() or not _within(path,root):return None
    if not path.exists():return None
    relative=path.resolve().relative_to(root.resolve())
    target=Path(batch) / relative
    if target.exists():return None
    return {'source':relative.as_posix(),'recycle_path':target.relative_to(root).as_posix(),
            'status':ITEM_PLANNED,'error':''}


def move_planned(record, root, batch):
    """按计划把这一项移进回收站；成功把状态改成 moved，失败原样抛出给调用方。"""
    root=Path(root)
    source=root/str(record['source'])
    target=root/str(record['recycle_path'])
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.move(str(source),str(target))
    record['status']=ITEM_MOVED
    record['error']=''
    return record


def _undo_moves(records, root):
    """把本批已进回收站（status=moved，或中断时仍记 planned）的项移回原位置。

    以“文件是否真的在回收站里”为准：被占用、已不在的跳过，绝不覆盖用户新文件；
    planned 也纳入，是因为进程可能在“移完再更新清单”之间中断，此时文件已在回收站。
    """
    root=Path(root)
    restored=[]
    for record in reversed(list(records)):
        if not isinstance(record,dict) or record.get('status') not in (ITEM_MOVED,ITEM_PLANNED):continue
        source=root/str(record.get('recycle_path') or '')
        target=root/str(record.get('source') or '')
        if not (source.is_file() or source.is_dir()) or target.exists():continue
        try:
            target.parent.mkdir(parents=True,exist_ok=True)
            source.rename(target)
        except OSError:
            continue
        record['status']=ITEM_UNDONE
        restored.append(target)
    return restored


def _distinct_outermost(records):
    """同批去重：同一路径只留第一次；祖先目录已在批内的子项不再单列（随目录一起搬）。

    否则「先文件后目录」会把目录套进自己的回收位置（a → a/a），「先目录后文件」第二项找不到源而整批撤回。"""
    parts=[PurePosixPath(str(record['source'])).parts for record in records]
    every=set(parts); seen=set(); kept=[]
    for record,mine in zip(records,parts):
        if mine in seen or any(mine[:size] in every for size in range(1,len(mine))):continue
        seen.add(mine); kept.append(record)
    return kept


def recycle_paths(root, paths, reason, now=None):
    """供用户可见的删除入口复用的受控回收接口。

    O38：先把写前计划（UUID 批次、逐项状态 state=planned）原子落盘，再逐项移动并随时更新
    清单，全部搬完才写 state=committed。任一项移动失败就撤回本批已移动项、写明失败原因后
    再抛出原异常；进程中断时清单已带逐项状态（恢复按文件是否真的在回收站里判断），可经
    restore_recycle_batch 恢复已搬走的项，或经 rollback_recycle_batch 撤回整批。
    同批重复路径只算一次，目录已在批内时不再单列其中的文件。始终只移动、不永久删除。
    """
    root=Path(root).resolve(); now=now or time.time()
    batch=_recycle_base(root)/batch_name(now)
    created_at=time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(now))
    records=_distinct_outermost([record for record in (plan_recycle(path,root,batch) for path in paths) if record is not None])
    if not records:return []
    batch.mkdir(parents=True,exist_ok=True)
    _write_batch_manifest(batch,BATCH_PLANNED,records,reason,created_at)     # 写前计划先落盘
    moved=[]
    try:
        for record in records:
            move_planned(record,root,batch)
            _write_batch_manifest(batch,BATCH_PLANNED,records,reason,created_at)  # 逐项状态
            moved.append(record)
    except OSError as exc:
        record['status']=ITEM_FAILED
        record['error']=type(exc).__name__+'：'+str(exc)
        _undo_moves(records,root)
        _write_batch_manifest(batch,BATCH_ROLLED_BACK,records,reason,created_at)
        recycled((root/str(item['source']),root/str(item['recycle_path'])) for item in records)
        raise
    _write_batch_manifest(batch,BATCH_COMMITTED,records,reason,created_at)
    recycled((root/record['source'],root/record['recycle_path']) for record in moved)
    return moved


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
        if str(row.get('status') or ITEM_MOVED) in (ITEM_PLANNED, ITEM_FAILED):
            # 写前计划里没搬成功的项（中断后状态未更新或明确 failed）：只要回收站里确实没有
            # 这个文件，就不算可恢复内容，不能让一条没搬成的记录挡住同批其余项。
            planned = root / str(source_text or '')
            if '..' not in planned.parts and not (planned.is_file() or planned.is_dir()):
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


def rollback_recycle_batch(root, batch):
    """撤回一个中断／未提交的回收批次：把已移动项移回原位置。

    只认写前记录过的批次（清单带 state）：state=committed 已提交，不能撤回请改用恢复；
    原位置被占用或文件已不在的项如实跳过，不覆盖用户新文件；始终不永久删除任何内容。
    """
    root=Path(root).resolve()
    batch=_restore_location(root,batch,'恢复批次不在当前项目回收站中')
    base=_recycle_base(root).resolve()
    if not batch.is_relative_to(base):
        raise ValueError('恢复批次不在当前项目回收站中')
    try:
        data=read_json(batch/MANIFEST_NAME)
    except (OSError,ValueError) as exc:
        raise ValueError('恢复清单无法读取：'+str(exc)) from exc
    if not isinstance(data,dict):
        raise ValueError('恢复清单格式无效')
    state=str(data.get('state') or '')
    if not state:
        raise ValueError('这批没有写前记录，不能撤回；请用恢复')
    if state==BATCH_COMMITTED:
        raise ValueError('已提交的回收批次不能撤回，请用恢复')
    rows=data.get('items')
    if not isinstance(rows,list) or not rows:
        raise ValueError('恢复清单为空')
    restored=_undo_moves(rows,root)
    _write_batch_manifest(batch,BATCH_ROLLED_BACK,rows,data.get('reason'),data.get('created_at'))
    recycled((root/str(row.get('source') or ''),root/str(row.get('recycle_path') or ''))
             for row in rows if isinstance(row,dict))
    return restored


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
        if isinstance(data, dict) and str(data.get('state') or '') == BATCH_ROLLED_BACK:
            continue                                   # 已撤回的批次不是可恢复内容
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
            if isinstance(data, dict) and str(data.get('state') or '') == BATCH_ROLLED_BACK:
                continue                               # 已撤回的批次不是可恢复内容
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

def edit_source_versions(root):
    """已发布成片（剪辑／交付）清单里被引用的视频版本。

    只读 ``13质检交付/导出成片`` 下的成片清单（``edit_bundle.json``，老成片退回
    ``edit_manifest.json``）：成片来源的权威仍归 engine 的剪辑清单，这里只为「删前先查引用」
    读出被引用的 ``(镜头, 版本)`` 与 ``(镜头, sha256)``，不重写、不删除任何成片记录。
    """
    root=Path(root)
    pairs=set();digests=set()
    try:
        from contract.project_stages import exports
        parent=exports(root)
    except (OSError,ValueError):
        return pairs,digests
    if not parent.is_dir():return pairs,digests
    for name in EXPORT_MANIFEST_NAMES:
        for manifest in parent.rglob(name):
            try:data=read_json(manifest)
            except (OSError,ValueError):continue
            rows=data.get('manifest') if isinstance(data,dict) else data
            if not isinstance(rows,list):continue
            for row in rows:
                if not isinstance(row,dict):continue
                shot=str(row.get('shot') or '')
                if not shot:continue
                try:pairs.add((shot,int(row.get('version'))))
                except (TypeError,ValueError):pass
                digest=str(row.get('sha256') or '')
                if digest:digests.add((shot,digest))
    return pairs,digests


def retention_seconds(root):
    """项目策略只接受1至3650天；坏配置阻断自动回收，不偷偷用更短期限。"""
    path = Path(root) / 'storage_policy.json'
    data = read_json(path) if path.exists() else {}
    days = data.get('retention_days', 7) if isinstance(data, dict) else None
    if type(days) is not int or not 1 <= days <= 3650:
        raise ValueError('项目旧版本保留天数必须为1至3650的整数')
    return days * 86400


def version_retention(version, shot, newest, referenced, digests, now, retention=AGE_SECONDS):
    """这一版该留还是可回收：返回保留原因，可以回收时返回空串。

    保留口径（任一成立即留，给出原因）：任务未结算（含未知状态）／用户锁定／已进已发布成片
    来源（按 ``(镜头, 版本)`` 或 ``(镜头, sha256)`` 命中）／已验收通过（含无人值守自动放行，
    旧版被采用也必须留住）／该镜头最新版本／不足保留期。全部不成立才可回收。
    """
    state=str((version or {}).get('state') or '')
    if state in PENDING or state not in SETTLED_STATES:return RETAIN_UNSETTLED
    if (version or {}).get('locked') or (version or {}).get('pinned'):return RETAIN_LOCKED
    digest=str((version or {}).get('sha256') or '')
    if (str(shot),(version or {}).get('version')) in referenced:return RETAIN_EDIT_SOURCE
    if digest and (str(shot),digest) in digests:return RETAIN_EDIT_SOURCE
    if (version or {}).get('review')=='pass':return RETAIN_APPROVED
    if (version or {}).get('version')==newest:return RETAIN_LATEST
    try:
        if isinstance((version or {}).get('created'), bool):return RETAIN_FRESH
        created=float((version or {}).get('created'))
    except (TypeError,ValueError):
        return RETAIN_FRESH
    return RETAIN_FRESH if not math.isfinite(created) or now-created<retention else ''


def _collect_sources(value, parent, root, protected):
    """递归收集字符串引用：路径同时兼容项目根及清单目录；只保护确实存在的项目内文件。"""
    if isinstance(value, dict):
        for child in value.values():
            _collect_sources(child, parent, root, protected)
        return
    if isinstance(value, list):
        for child in value:
            _collect_sources(child, parent, root, protected)
        return
    if not (isinstance(value, str) and value and len(value) < 1024):
        return
    for base in (root, parent):
        try:
            path = (base / value).resolve()
            if path.is_relative_to(root) and path.is_file():
                protected.add(path)
        except (OSError, ValueError):
            continue


def _protect_ledger(root, path, data, rules, protected):
    """生成台账：每个镜头的保留版本引用的文件与该版本目录里的 assets_manifest.json 都要保护。

    rules 是 (被成片引用的版本, 被引用的摘要, 现在, 保留期秒数)，原样传给 version_retention。
    """
    referenced, digests, now, retention = rules
    shots = data.get('shots') if isinstance(data, dict) else None
    if not isinstance(shots, dict):
        raise ValueError('生成台账缺少镜头表')
    for shot, versions in shots.items():
        if not isinstance(versions, list) or any(not isinstance(v, dict) for v in versions):
            raise ValueError('生成版本列表无效')
        numbers = [v.get('version', 0) for v in versions]
        if any(type(number) is not int for number in numbers):
            raise ValueError('生成版本编号无效')
        newest = max(numbers, default=0)
        for version in versions:
            if not version_retention(version, shot, newest, referenced, digests, now, retention):
                continue
            _collect_sources(version, path.parent.parent, root, protected)
            folder = _version_folder(root, path, shot, version)
            if folder is not None and (folder / 'assets_manifest.json').is_file():
                protected.add((folder / 'assets_manifest.json').resolve())


def _check_export_manifest(data):
    rows = data.get('manifest') if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError('成片来源清单缺失')
    if any(not isinstance(row, dict) or not row.get('shot') or
           (not row.get('sha256') and type(row.get('version')) is not int) for row in rows):
        raise ValueError('成片来源条目无法确认')


def _chase_receipts(root, recycle, protected, errors):
    """只沿保留文件追踪旁证，不能把每个过期版本自己的清单变成永久保留理由。"""
    checked = set()
    while True:
        receipts = set()
        for path in protected:
            candidates = (path.with_name(path.name + '.source.json'),
                          path.parent / 'assets_manifest.json')
            if path.name == 'assets_manifest.json' or path.name.endswith('.source.json'):
                candidates += (path,)
            receipts.update(p.resolve() for p in candidates
                            if _within(p, root) and not _within(p, recycle) and p.is_file())
        pending = receipts - checked
        if not pending:
            break
        checked.update(pending)
        protected.update(pending)
        for path in sorted(pending):
            try:
                data = read_json(path)
                if not isinstance(data, dict):
                    raise ValueError('来源旁证不是对象')
                _collect_sources(data, path.parent, root, protected)
            except (OSError, ValueError) as exc:
                errors.append(str(path.relative_to(root)) + '：' + str(exc))


def source_protection(root, now=None):
    """收集明确来源声明与其项目内文件；读坏的声明不能被解释为没有引用。"""
    root = Path(root).resolve()
    protected, errors = set(), []
    now = time.time() if now is None else now
    try:
        retention = retention_seconds(root)
    except (OSError, ValueError) as exc:
        return protected, [str(exc)]
    recycle = _recycle_base(root)
    names = {'episode.json', 'assets.json', *EXPORT_MANIFEST_NAMES}
    referenced, digests = edit_source_versions(root)
    for path in root.rglob('*.json'):
        if not _within(path, root) or _within(path, recycle):
            continue
        ledger = path.name == 'state.json' and path.parent.name in ('data', '06_本地生成')
        if path.name not in names and '.commercial.' not in path.name and not ledger:
            continue
        protected.add(path.resolve())
        try:
            data = read_json(path)
            if not isinstance(data, (dict, list)):
                raise ValueError('来源声明不是对象或清单')
            if ledger:
                _protect_ledger(root, path, data, (referenced, digests, now, retention), protected)
                continue
            if path.name in EXPORT_MANIFEST_NAMES:
                _check_export_manifest(data)
            _collect_sources(data, path.parent, root, protected)
        except (OSError, ValueError) as exc:
            errors.append(str(path.relative_to(root)) + '：' + str(exc))
    _chase_receipts(root, recycle, protected, errors)
    return protected, errors


def _shot_versions(root, ledger, shot, rows, select_adopted, scan):
    """storage_summary 的一个镜头：逐版本判定保留理由，把行写进 scan['versions']、文件归进候选／采用／其它三个集合。"""
    file_sizes, protected = scan['file_sizes'], scan['protected']
    newest = max((v.get('version', 0) for v in rows), default=0)
    adopted = select_adopted(rows, ledger.parent.parent)[0] if select_adopted else None
    for version in rows:
        if version.get('cleaned_at'):
            continue
        folder = _version_folder(root, ledger, shot, version)
        reason = version_retention(version, shot, newest, scan['referenced'], scan['digests'], scan['now'], scan['retention'])
        if folder is None:
            scan['versions'].append({'shot': shot, 'version': version.get('version'), 'bytes': 0, 'reason': '生成目录无法安全定位', 'candidate': False})
            continue
        files = {p for p in file_sizes if p.is_relative_to(folder)}
        if not reason and any(p == folder or p.is_relative_to(folder) for p in protected):
            reason = '来源或授权资料仍被引用'
        if not reason:
            scan['candidate_files'].update(files)
        (scan['adopted_files'] if version is adopted else scan['other_files']).update(files)
        scan['versions'].append({'shot': shot, 'version': version.get('version'), 'bytes': sum(file_sizes[p] for p in files),
                                 'reason': RETAIN_REASONS.get(reason, reason) or VERSION_CLEAN_REASON,
                                 'candidate': not bool(reason), 'adopted': version is adopted if select_adopted else None})


def storage_summary(root, now=None, select_adopted=None):
    """只读盘点；未发现引用不等于可删除，同盘回收不等于释放容量。"""
    root = Path(root).resolve()
    now = time.time() if now is None else now
    protected, errors = source_protection(root, now)
    sizes = {'protected': 0, 'unclassified': 0, 'recycled': 0}
    file_sizes = {}
    for path in root.rglob('*'):
        if path.is_symlink() or path.is_junction() or not _within(path, root):
            continue
        try:
            if not path.is_file():
                continue
            key = 'recycled' if _within(path, _recycle_base(root)) else 'protected' if path.resolve() in protected else 'unclassified'
            file_sizes[path.resolve()] = path.stat().st_size
            sizes[key] += file_sizes[path.resolve()]
        except OSError as exc:
            errors.append(str(path.relative_to(root)) + '：' + str(exc))
    try:
        retention = retention_seconds(root)
    except (OSError, ValueError):
        retention = None
    versions, candidate_files, adopted_files, other_files = [], set(), set(), set()
    referenced, digests = edit_source_versions(root)
    if not errors and retention is not None:
        for ledger in list(root.glob('**/data/state.json')) + list(root.glob('**/06_本地生成/state.json')):
            if not _within(ledger, root) or _within(ledger, _recycle_base(root)):
                continue
            scan = {'file_sizes': file_sizes, 'protected': protected, 'referenced': referenced, 'digests': digests,
                    'now': now, 'retention': retention, 'versions': versions, 'candidate_files': candidate_files,
                    'adopted_files': adopted_files, 'other_files': other_files}
            try:
                state = read_json(ledger)
                for shot, rows in state['shots'].items():
                    _shot_versions(root, ledger, shot, rows, select_adopted, scan)
            except (OSError, ValueError, TypeError, KeyError) as exc:
                errors.append(str(ledger.relative_to(root)) + '：' + str(exc))
    return {'bytes': sizes, 'errors': errors, 'retention_days': retention // 86400 if retention else None,
            'versions': versions, 'recyclable_bytes': sum(file_sizes[p] for p in candidate_files) if not errors else None,
            'adopted_bytes': sum(file_sizes[p] for p in adopted_files) if select_adopted and not errors else None,
            'other_version_bytes': sum(file_sizes[p] for p in other_files - adopted_files) if select_adopted and not errors else None,
            'immediately_released_bytes': 0}


def _version_folder(root, ledger, shot, version):
    number = version.get('version')
    if type(number) is not int or (version.get('output_dir') and not isinstance(version['output_dir'], str)):
        return None
    folder = ((ledger.parent.parent / version['output_dir']).resolve() if version.get('output_dir')
              else (ledger.parent / str(shot) / f'v{number:03}').resolve())
    if folder == root or not folder.is_relative_to(root) or ledger.resolve().is_relative_to(folder):
        return None
    return folder


def clean_project(root,now=None):
    root=Path(root).resolve();now=now or time.time();removed=[];records=[]
    if root.parent!=downloads_root().resolve() or not (root/'config.json').is_file():return removed
    protected, protection_errors = source_protection(root, now)
    if protection_errors:
        return removed
    retention = retention_seconds(root)
    recycle_base=_recycle_base(root)
    batch=recycle_base/batch_name(now)
    created_at=time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(now))

    def recycle(path):
        resolved = Path(path).resolve()
        if any(source == resolved or source.is_relative_to(resolved) for source in protected):
            return False
        record=plan_recycle(path,root,batch)
        if record is None:return False
        records.append(record)
        batch.mkdir(parents=True,exist_ok=True)
        _write_batch_manifest(batch,BATCH_PLANNED,records,'自动维护',created_at)   # 写前计划先落盘
        try:
            move_planned(record,root,batch)
        except OSError as exc:
            # 单项移动失败如实记 failed 与原因后再抛出，其余项交给调用方继续清理。
            record['status']=ITEM_FAILED
            record['error']=type(exc).__name__+'：'+str(exc)
            _write_batch_manifest(batch,BATCH_PLANNED,records,'自动维护',created_at)
            raise
        _write_batch_manifest(batch,BATCH_PLANNED,records,'自动维护',created_at)   # 逐项状态
        removed.append(Path(record['source']));return True

    # Closing the assistant recycles unreferenced explicitly named history directories.
    # Active creative folders, current storyboards and final outputs are untouched.
    # 清理改为可恢复移动，历史回收站自身永不参与下一轮扫描。
    histories=[p for p in root.rglob('*') if p.name in ('历史版本','分镜历史') and not _within(p,recycle_base)]
    for history in sorted(histories,key=lambda p:len(p.parts),reverse=True):
        try:
            recycle(history)
        except OSError:
            # An occupied history must not prevent cleanup of the other folders.
            continue
    # Completed generation versions: retain newest per shot, all unfinished jobs, every adopted
    # version and everything a published cut still references (O39：删前先查成果引用图)。
    referenced,digests=edit_source_versions(root)
    ledgers=list(root.glob('**/data/state.json'))+list(root.glob('**/06_本地生成/state.json'))
    for ledger in ledgers:
        # 回收区里的旧台账不是生产目录：既不能再按它清理，也不能碰回收站里的东西。
        if not _within(ledger,root) or _within(ledger,recycle_base):continue
        try:state=read_json(ledger)
        except (OSError,ValueError):continue
        dirty=False
        for shot_id,versions in state.get('shots',{}).items():
            if not isinstance(versions,list) or len(versions)<2:continue
            newest=max((v.get('version',0) for v in versions if isinstance(v,dict)),default=0)
            for version in versions:
                if not isinstance(version,dict) or version.get('cleaned_at'):continue
                if version_retention(version,shot_id,newest,referenced,digests,now,retention):continue
                number=version.get('version')
                if not isinstance(number,int):continue
                folder=_version_folder(root,ledger,shot_id,version)
                if folder is not None and folder.is_dir() and recycle(folder):
                    version.update(cleaned_at=now,file=None,qc_pass=False,cleaned_reason=VERSION_CLEAN_REASON);dirty=True
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
        _write_batch_manifest(batch,BATCH_COMMITTED,records,'自动维护',created_at)
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
