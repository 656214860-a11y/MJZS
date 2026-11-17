"""Pure Seedream request/image conversion helpers with no UI dependency."""
import base64
import hashlib
import subprocess
from pathlib import Path

from contract.platform_tools import run_process, tool_path


def seedream_payload(profile_model, prompt, aspect_ratio, ref_paths):
    sizes = {'1:1':'2048x2048','9:16':'1440x2560','16:9':'2560x1440'}
    if aspect_ratio not in sizes:
        raise ValueError('画幅设置无效：' + str(aspect_ratio))
    payload = {'model':profile_model, 'prompt':prompt, 'size':sizes[aspect_ratio],
               'response_format':'b64_json', 'watermark':True}
    images = []
    for source in ref_paths:
        path = Path(source); raw = path.read_bytes()
        if len(raw) > 10 * 1024 * 1024:
            raise ValueError('参考图超过 10MB：' + path.name)
        mime = {'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp'}.get(path.suffix.lower())
        if not mime:
            raise ValueError('参考图格式不支持：' + path.name)
        images.append('data:' + mime + ';base64,' + base64.b64encode(raw).decode('ascii'))
    if images:
        payload['image'] = images if len(images) > 1 else images[0]
    return payload


def seedream_provenance(payload):
    """Record how a Seedream request was assembled: digests only, never the key or image bytes."""
    images = payload.get('image')
    if isinstance(images, str):
        images = [images]
    references = []
    for item in images or []:
        encoded = item.split(',', 1)[1] if isinstance(item, str) and item.startswith('data:') and ',' in item else None
        references.append(hashlib.sha256(base64.b64decode(encoded)).hexdigest() if encoded is not None else None)
    return {'payload_schema': 'seedream_payload/v1',
            'model': str(payload.get('model', '')),
            'size': str(payload.get('size', '')),
            'watermark': bool(payload.get('watermark')),
            'prompt_sha256': hashlib.sha256(str(payload.get('prompt', '')).encode('utf-8')).hexdigest(),
            'reference_sha256': references}


def to_png(raw):
    if raw.startswith(b'\x89PNG\r\n\x1a\n'):
        return raw
    ffmpeg = tool_path('ffmpeg')
    proc = run_process([ffmpeg, '-y', '-v', 'error', '-i', 'pipe:0', '-f', 'image2pipe', '-c:v', 'png', 'pipe:1'],
                       input=raw, capture_output=True, timeout=120, run=subprocess.run)
    if proc.returncode != 0 or not proc.stdout.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Seedream 图片转换 PNG 失败：' + proc.stderr.decode('utf-8', 'replace')[:160])
    return proc.stdout
