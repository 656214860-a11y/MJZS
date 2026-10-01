"""无人值守交接包的无界面派发与成果描述。"""
import json
import time
import uuid
from pathlib import Path


AUTOMATIC_HANDOFF_MARKER_NAME = '自动交接.json'


def automatic_decision(signature, digest, previous_signature, completed_marker):
    """决定交接包应等待、跳过已完成成果，还是启动一次整理。"""
    if signature == previous_signature:
        return {'action': 'skip', 'signature': signature}
    if digest is None:
        return {'action': 'wait', 'signature': signature}
    if isinstance(completed_marker, dict) and completed_marker.get('digest') == digest:
        return {'action': 'complete', 'signature': signature}
    return {'action': 'dispatch', 'signature': signature}


def save_automatic_handoff_marker(target, digest, folder, shot_count, *, publish):
    """登记一次无人值守交接；正式发布器必须由 L3 注入。"""
    if not callable(publish):
        raise TypeError('自动交接标记需要由 L3 注入发布器。')
    target = Path(target)
    publish(target, {'digest': digest, 'folder': str(folder), 'shots': shot_count})
    return target


def publish_bundle(root, shots, rows, subtitle=None, auto=False, *, publish=None):
    """准备剪映交接包描述；正式文件只能由 L3 注入的发布器写入。"""
    if not callable(publish):
        raise TypeError('剪映交接包需要由 L3 注入发布器。')
    root = Path(root).resolve()
    if not rows:
        raise ValueError('当前项目没有已下载视频')
    manifest = []
    artifacts = []
    for index, (shot, version) in enumerate(rows, 1):
        source = (root / version['file']).resolve()
        if not source.is_relative_to(root):
            raise ValueError('视频路径越界')
        name = f'{index:03}_{shot["id"]}{source.suffix}'
        artifacts.append({'name': name, 'source': source})
        manifest.append({'shot': shot['id'], 'file': name, 'review': version.get('review'), 'seconds': shot['duration']})
    if subtitle is not None:
        if isinstance(subtitle, (bytes, bytearray)):
            artifacts.append({'name': '对白.srt', 'data': bytes(subtitle)})
        else:
            artifacts.append({'name': '对白.srt', 'source': Path(subtitle)})
    artifacts.extend((
        {'name': '镜头顺序.json', 'data': json.dumps(manifest, ensure_ascii=False).encode('utf-8')},
        {'name': '导入剪映说明.txt', 'data': ('新建剪映项目，将编号视频按文件名顺序拖入时间线。字幕是剧本时间，需要听校。\n这是素材交接包，不是剪映草稿。未下载镜头没有补齐；缺镜时不附全片字幕，以免错位。\n' + f'已下载 {len(rows)}/{len(shots)} 镜。').encode('utf-8')},
    ))
    if auto:
        artifacts.append({'name': '交接包标记.json', 'data': json.dumps(
            {'kind': 'auto', 'built_at': time.strftime('%Y-%m-%d %H:%M:%S')}, ensure_ascii=False).encode('utf-8')})
    name = '自动交接包' if auto else '剪映交接_' + uuid.uuid4().hex[:8]
    return publish(root, name, artifacts, auto=auto)
