"""从已脱敏的实际视频请求保留首帧及白模摘要，不重读文件推测提交版本。"""
from pathlib import Path


def submitted_sources(preview, frame, white=None, assets=None):
    first = None
    white_digest = None
    references = []
    inputs = preview.get('input', {})
    if isinstance(inputs, dict):
        first = inputs.get('img_url')
        for row in inputs.get('media', []):
            if row.get('type') == 'first_frame':
                first = row.get('url')
            elif row.get('type') == 'reference_video':
                white_digest = row.get('url')
            elif row.get('type') == 'reference_image':
                references.append(row.get('url'))
    for row in preview.get('content', []):
        if row.get('type') == 'image_url' and first is None:
            first = row.get('image_url', {}).get('url')
        elif row.get('type') == 'image_url':
            references.append(row.get('image_url', {}).get('url'))
        elif row.get('type') == 'video_url' and row.get('role') == 'reference_video':
            white_digest = row.get('video_url', {}).get('url')

    def record(path, digest, category):
        if (not isinstance(digest, str) or not digest.startswith('sha256:')
                or len(digest[7:]) != 64 or any(c not in '0123456789abcdef' for c in digest[7:])):
            raise ValueError('实际提交素材缺少可追溯摘要')
        return {'path': str(Path(path).resolve()), 'sha256': digest[7:], 'category': category}

    result = {}
    if assets is not None:
        if len(assets) != len(references):
            raise ValueError('实际提交参考图与来源清单数量不一致')
        result['assets'] = [{**asset, **record(asset['path'], digest, 'reference')}
                            for asset, digest in zip(assets, references)]
    if first is not None:
        result['first_frame'] = record(frame, first, 'image')
    if white_digest is not None:
        if not isinstance(white, dict) or not white.get('path'):
            raise ValueError('实际提交白模缺少来源路径')
        result['white_model_reference'] = record(white['path'], white_digest, 'reference')
    return result


def input_signature_record(episode_path, shot, backend, reference_rows=None, frame_sha256=None):
    """视频版本要持久化的输入指纹字段；不改变旧 payload/graph ``signature`` 的语义。"""
    from domain import video_staleness
    return {video_staleness.INPUT_SIGNATURE_FIELD: video_staleness.input_signature(
        episode_path, shot, backend, reference_rows, frame_sha256)}


def media_input_signature_record(episode_path, shot, backend, media_sources):
    """按已上传素材回执生成版本输入指纹字段；缺首帧回执时退回当前首帧事实。"""
    assets = (media_sources or {}).get('assets', [])
    frame = ((media_sources or {}).get('first_frame') or {}).get('sha256')
    return input_signature_record(episode_path, shot, backend, assets, frame)
