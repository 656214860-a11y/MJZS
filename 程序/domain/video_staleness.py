"""视频持久过期标记：用版本记录提交时签名与「同一口径」现算指纹比对（只读）。

过期判定只发生在这里：已提交视频版本记录里的 ``signature`` 是提交时那一版内容的指纹；
过期（stale）当且仅当它与「现在由同一口径重算」的当前指纹不一致。持久性来自版本记录里
提交时固化的签名本身，不落任何第二份真源，重启后照常用现算结果比对。

只读：不改版本记录、不落盘、不自动重做；由用户经既有 ``review('revise')`` 路径决定重做。
"""
from pathlib import Path
from agent.core import read
from domain.storyboard_lifecycle import signature as content_signature


def version_signature(version):
    """版本记录里提交时固化的签名（提交时对同一内容口径算出）。"""
    return str((version or {}).get('signature') or '')


def version_is_stale(version, current_signature_value):
    """已提交版本与当前内容指纹不一致即过期；没有提交签名的记录不强判。"""
    recorded = version_signature(version)
    if not recorded:
        return False
    return recorded != str(current_signature_value or '')


def _load_assets(source):
    """只读读取当前分镜对应的资产清单（不经 agent.shot_assets，避免静态循环导入）。"""
    source = Path(source).resolve()
    base = None
    for folder in source.parents:
        if (folder / 'assets.json').is_file() or (folder / 'assets/资产清单/assets.json').is_file():
            base = folder
            break
    entries = {}
    if base is not None:
        reg_path = base / 'assets.json'
        registered = read(reg_path) if reg_path.is_file() else {}
        if not isinstance(registered, dict):
            registered = {}
        plan_path = base / 'assets/资产清单/assets.json'
        planned = read(plan_path) if plan_path.is_file() else {}
        if not isinstance(planned, dict):
            planned = {}
        entries = {
            aid: {**registered.get(aid, {}), **planned.get(aid, {}),
                  'image': registered.get(aid, {}).get('image'),
                  '_registry_base': str(base)}
            for aid in dict.fromkeys([*planned, *registered])
        }
    snapshot = source.parent / 'assets.json'
    if snapshot.is_file() and snapshot.parent != base:
        snap = read(snapshot)
        if isinstance(snap, dict):
            for aid, asset in snap.items():
                if aid not in entries or not entries[aid].get('image'):
                    entries[aid] = {**(asset if isinstance(asset, dict) else {}),
                                    **entries.get(aid, {}),
                                    'image': (asset or {}).get('image') if isinstance(asset, dict) else None,
                                    '_registry_base': str(snapshot.parent)}
    return entries


def current_signature(source, shot):
    """同一口径现算：当前镜头内容（引用资产图片字节＋提示词）的指纹。

    与视频提交时对同一内容口径算出的版本签名同源（经 ``domain.storyboard_lifecycle.signature``，
    忽略使用计数、含图片字节哈希），因此重启后重算出的指纹与提交时的一致。
    """
    source = Path(source).resolve()
    episode = read(source)
    try:
        assets = _load_assets(source)
    except (OSError, ValueError):
        assets = {}
    value = content_signature(episode, assets, source.parent)
    return value if isinstance(value, str) and value else ''


def stale_shots(source, generated, versions_by_shot):
    """已生成视频集合中，与当前内容不符（即过期）的镜头编号，只读。

    ``generated``：已生成过视频的镜头 id 集合（可来自 storyboard_catalog_service）。
    ``versions_by_shot``：镜头 -> 版本记录列表。任一已提交版本签名与现算指纹不一致即过期。
    """
    source = Path(source).resolve()
    episode = read(source)
    shots = {str(shot.get('id') or ''): shot for shot in episode.get('shots') or [] if isinstance(shot, dict)}
    stale = []
    for sid in sorted(generated):
        versions = versions_by_shot.get(sid) or []
        shot = shots.get(sid)
        if shot is None or not versions:
            continue
        current = current_signature(source, shot)
        if not current:
            # 现算不到内容指纹（资产缺图等）时不强判过期，避免误标。
            continue
        if any(version_is_stale(version, current) for version in versions):
            stale.append(sid)
    return stale
