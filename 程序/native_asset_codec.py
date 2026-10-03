"""Pure Seedream request/image conversion helpers with no UI dependency."""
import base64
import subprocess
from pathlib import Path

from platform_tools import run_process, tool_path


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


def to_png(raw):
    if raw.startswith(b'\x89PNG\r\n\x1a\n'):
        return raw
    ffmpeg = tool_path('ffmpeg', 'D:/Tools/ffmpeg/bin/ffmpeg.exe')
    proc = run_process([ffmpeg, '-y', '-v', 'error', '-i', 'pipe:0', '-f', 'image2pipe', '-c:v', 'png', 'pipe:1'],
                       input=raw, capture_output=True, timeout=120, run=subprocess.run)
    if proc.returncode != 0 or not proc.stdout.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Seedream 图片转换 PNG 失败：' + proc.stderr.decode('utf-8', 'replace')[:160])
    return proc.stdout
