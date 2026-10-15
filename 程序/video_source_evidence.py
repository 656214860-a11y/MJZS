"""从已脱敏的实际视频请求保留首帧及白模摘要，不重读文件推测提交版本。"""
from pathlib import Path


def submitted_sources(preview, frame, white=None):
    first = None
    white_digest = None
    inputs = preview.get('input', {})
    if isinstance(inputs, dict):
        first = inputs.get('img_url')
        for row in inputs.get('media', []):
            if row.get('type') == 'first_frame':
                first = row.get('url')
            elif row.get('type') == 'reference_video':
                white_digest = row.get('url')
    for row in preview.get('content', []):
        if row.get('type') == 'image_url' and first is None:
            first = row.get('image_url', {}).get('url')
        elif row.get('type') == 'video_url' and row.get('role') == 'reference_video':
            white_digest = row.get('video_url', {}).get('url')

    def record(path, digest, category):
        if (not isinstance(digest, str) or not digest.startswith('sha256:')
                or len(digest[7:]) != 64 or any(c not in '0123456789abcdef' for c in digest[7:])):
            raise ValueError('实际提交素材缺少可追溯摘要')
        return {'path': str(Path(path).resolve()), 'sha256': digest[7:], 'category': category}

    result = {}
    if first is not None:
        result['first_frame'] = record(frame, first, 'image')
    if white_digest is not None:
        if not isinstance(white, dict) or not white.get('path'):
            raise ValueError('实际提交白模缺少来源路径')
        result['white_model_reference'] = record(white['path'], white_digest, 'reference')
    return result
