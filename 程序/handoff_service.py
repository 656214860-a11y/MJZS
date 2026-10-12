"""无人值守交接包的无界面派发与成果描述。"""
import hashlib
import json
import time
import uuid
from pathlib import Path
from functools import wraps
import logging
from service_contract import SystemError, UserError, success
from project_context import ProjectContext


def _project_root(project=None, *, context=None):
    if context is None:
        return Path(project).resolve()
    if not isinstance(context, ProjectContext):
        raise TypeError('交接包需要由 L3 注入 ProjectContext。')
    root = context.root.resolve()
    if project is not None and Path(project).resolve() != root:
        raise ValueError('项目路径与注入的 ProjectContext 不一致。')
    return root


def _write_result(function):
    @wraps(function)
    def run(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except OSError:
            logging.getLogger(__name__).exception('交接成果保存失败')
            return SystemError('交接成果保存失败，请检查文件权限和磁盘空间。')
    return run


AUTOMATIC_HANDOFF_MARKER_NAME = '自动交接.json'
BUNDLE_MANIFEST_NAME = '交接包清单.json'
MEDIA_PACKAGE_KIND = 'media'
MEDIA_PACKAGE_LABEL = '素材交接包'
MEDIA_PACKAGE_NOTE = '这是素材交接包，不是剪映草稿；未下载镜头没有补齐。'


def automatic_decision(signature, digest, previous_signature, completed_marker):
    """决定交接包应等待、跳过已完成成果，还是启动一次整理。"""
    if signature == previous_signature:
        return {'action': 'skip', 'signature': signature}
    if digest is None:
        return {'action': 'wait', 'signature': signature}
    if isinstance(completed_marker, dict) and completed_marker.get('digest') == digest:
        return {'action': 'complete', 'signature': signature}
    return {'action': 'dispatch', 'signature': signature}


@_write_result
def save_automatic_handoff_marker(target, digest, folder, shot_count, *, publish):
    """登记一次无人值守交接；正式发布器必须由 L3 注入。"""
    if not callable(publish):
        raise TypeError('自动交接标记需要由 L3 注入发布器。')
    target = Path(target)
    publish(target, {'digest': digest, 'folder': str(folder), 'shots': shot_count})
    return success(target)


@_write_result
def publish_bundle(root, shots, rows, subtitle=None, auto=False, *, publish=None, context=None):
    """准备剪映交接包描述；正式文件只能由 L3 注入的发布器写入。"""
    if not callable(publish):
        raise TypeError('剪映交接包需要由 L3 注入发布器。')
    root = _project_root(root, context=context)
    if not rows:
        return UserError('当前项目没有已下载视频')
    manifest = []
    artifacts = []
    sources = []
    for index, (shot, version) in enumerate(rows, 1):
        source = (root / version['file']).resolve()
        if not source.is_relative_to(root):
            return UserError('视频路径越界')
        name = f'{index:03}_{shot["id"]}{source.suffix}'
        artifacts.append({'name': name, 'source': source})
        manifest.append({'shot': shot['id'], 'file': name, 'review': version.get('review'), 'seconds': shot['duration']})
        sources.append({'shot': shot['id'], 'file': name, 'version': version.get('version'),
                        'review': version.get('review'), 'qc_pass': version.get('qc_pass'),
                        'seconds': shot['duration']})
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
    included = [item['shot'] for item in manifest]
    included_set = set(included)
    summary = {
        'kind': MEDIA_PACKAGE_KIND,
        'label': MEDIA_PACKAGE_LABEL,
        'note': MEDIA_PACKAGE_NOTE,
        'shots': {'included': included, 'expected': len(shots),
                  'missing': [str(shot['id']) for shot in shots if shot['id'] not in included_set]},
        'subtitle': subtitle is not None,
        'sources': sources,
    }
    name = '自动交接包' if auto else '剪映交接_' + uuid.uuid4().hex[:8]
    return success(publish(root, name, artifacts, auto=auto, summary=summary))


def build_bundle_manifest(summary, files, *, built_at=None):
    """把交接包的事实与每个文件的摘要汇成一份离线可校验清单。

    ``summary`` 是 ``publish_bundle`` 给出的事实（类型、镜头覆盖、字幕与来源版本）；
    ``files`` 是 ``[{'name', 'data'}]``，大小与 sha256 在这里算好，换台机器解包后照单核对即可。
    """
    entries = [{'name': str(item['name']), 'size': len(item['data']),
                'sha256': hashlib.sha256(bytes(item['data'])).hexdigest()}
               for item in files]
    manifest = dict(summary or {})
    manifest['files'] = entries
    manifest['count'] = len(entries)
    manifest['built_at'] = built_at or time.strftime('%Y-%m-%d %H:%M:%S')
    return manifest


def verify_manifest(manifest, probe):
    """按清单离线核对一个已解包的交接包：文件在不在、有没有被改、声明齐全时有没有漏镜。

    ``probe(name)`` 返回 ``(size, sha256)``，文件缺失或读不动时抛 ``OSError``。返回
    ``{'ok', 'problems', 'missing', 'count', 'label'}``：``problems`` 都是真缺陷，
    ``missing`` 是清单自己声明的缺项（素材包允许缺镜，如实列出，不算失败）。
    """
    if not isinstance(manifest, dict):
        return {'ok': False, 'problems': ['交接包清单格式不正确'], 'missing': [], 'count': 0, 'label': ''}
    problems = []
    files = manifest.get('files')
    if not isinstance(files, list) or not files:
        problems.append('清单没有记录任何文件')
        files = []
    names = set()
    for item in files:
        if not isinstance(item, dict):
            problems.append('清单里有一条记录格式不对')
            continue
        name = str(item.get('name') or '')
        if not name:
            problems.append('清单里有一条没有文件名')
            continue
        names.add(name)
        try:
            size, sha256 = probe(name)
        except OSError:
            problems.append('文件缺失或读不动：' + name)
            continue
        try:
            recorded = int(item.get('size'))
        except (TypeError, ValueError):
            recorded = -1
        if recorded != int(size):
            problems.append('文件大小不符：' + name)
        elif str(item.get('sha256') or '') != str(sha256):
            problems.append('文件内容与清单不符：' + name)
    shots = manifest.get('shots') if isinstance(manifest.get('shots'), dict) else {}
    included = list(shots.get('included') or [])
    expected = shots.get('expected')
    missing = [str(item) for item in (shots.get('missing') or [])]
    if isinstance(expected, int) and expected > 0 and not missing and len(included) < expected:
        problems.append('清单声明镜头齐全，却只记录了 %d/%d 镜' % (len(included), expected))
    if manifest.get('subtitle') and '对白.srt' not in names:
        problems.append('清单声明含字幕，包里却没有对白.srt')
    return {'ok': not problems, 'problems': problems, 'missing': missing,
            'count': len(files), 'label': str(manifest.get('label') or '')}
