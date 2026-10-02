"""资产批处理的可恢复台账与落盘状态操作；不依赖 Tk。"""
from pathlib import Path

from agent.core import read
from asset_batch_service import KINDS


def ledger_path(project):
    return Path(project) / 'workflows' / '资产批量记录.json'


def read_ledger(project):
    """读取资产批次台账；坏的历史台账不作为可继续状态使用。"""
    file = ledger_path(project)
    data = read(file) if file.is_file() else {}
    return data if isinstance(data, dict) else {}


def save_ledger(project, data, *, publish=None):
    """通过 L3 注入的发布器原子发布资产批次台账。"""
    if not isinstance(data, dict):
        raise ValueError('资产批次台账必须为对象')
    if not callable(publish):
        raise RuntimeError('资产批次台账发布必须由 L3 注入')
    publish(ledger_path(project), data)


def _resumable_record(record):
    try:
        info = read(Path(record))
    except (OSError, ValueError):
        return False
    return isinstance(info, dict) and bool(info.get('prompt_id') or info.get('state') == 'downloaded')


def uncertain_assets(project):
    """返回提交状态未知且没有可接续记录的资产编号。"""
    data = read_ledger(project)
    return sorted(aid for aid, job in data.items()
                  if isinstance(job, dict) and job.get('state') == 'submitting'
                  and not (job.get('record') and _resumable_record(job['record'])))


def release_uncertain(project, ids, *, publish=None):
    """在用户确认后允许未知提交重新生成，保留可审计的原因。"""
    data = read_ledger(project)
    released = []
    for aid in ids:
        job = data.get(aid)
        if isinstance(job, dict) and job.get('state') == 'submitting':
            job.update(state='failed', note='您已在 ComfyUI／云端核实，本次重新生成')
            released.append(aid)
    if released:
        save_ledger(project, data, publish=publish)
    return released


def prune_raw_outputs(base):
    """将未登记的旧 Comfy 原图移入回收站，绝不直接删除用户成果。"""
    base = Path(base).resolve()
    registry = read(base / 'assets.json')
    registry = registry if isinstance(registry, dict) else {}
    keep = {(base / entry['image']).resolve() for entry in registry.values()
            if isinstance(entry, dict) and entry.get('image')}
    candidates = []
    for folder_name, _label in KINDS.values():
        folder = base / 'assets' / folder_name
        if folder.is_dir():
            candidates.extend(path for path in sorted(folder.glob('comfy_*.png'))
                              if path.resolve() not in keep)
    if not candidates:
        return []
    from storage_maintenance import recycle_paths
    recycled = recycle_paths(base, candidates, '清理未登记的原始资产图')
    moved = {record['source'] for record in recycled}
    return [path for path in candidates if path.resolve().relative_to(base).as_posix() in moved]


def ready_asset_ids(base):
    """一次读盘计算已登记且真实落盘的资产编号。"""
    base = Path(base).resolve()
    file = base / 'assets.json'
    registry = read(file) if file.is_file() else {}
    if not isinstance(registry, dict):
        return set()
    result = set()
    for aid, asset in registry.items():
        image = asset.get('image') if isinstance(asset, dict) else None
        if not image:
            continue
        path = (base / image).resolve()
        if path.is_relative_to(base) and path.is_file():
            result.add(aid)
    return result
