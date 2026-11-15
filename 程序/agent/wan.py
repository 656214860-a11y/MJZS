"""Wan first-frame adapter; one submission, persistent task ID in runner."""
import base64
import json
import re
import urllib.parse
from .video import VideoAdapter
from .volcengine import ArkRejected
# 第 34 期第 9 条：urllib.request／urllib.error 连 ssl 一起加载，改到 call() 里按需 import。

class WanAdapter(VideoAdapter):
    def __init__(self, cfg):
        self.cfg = cfg
        from api_endpoints import normalize_url
        self.base = normalize_url(cfg['base_url'])

    def payload(self, shot, frame):
        if shot.get('_reference_mode')=='wan':
            from .shot_assets import image_url
            from white_model_ref import entries as white_entries   # 第 8 轮：白模参考视频那一槽
            media=[{'type':'first_frame','url':image_url(frame)}]+[
                {'type':'reference_image','url':image_url(a['path'])} for a in shot['_asset_references']]
            media+=white_entries(shot.get('_white_model_reference'))
            return {'model':self.cfg['model'],'input':{'prompt':shot['video_prompt'],'media':media},
                'parameters':{'resolution':'720P','duration':shot['duration'],'prompt_extend':False,'watermark':False}}
        data = frame.read_bytes()
        if not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data) > 20*1024*1024:
            raise ValueError('Invalid PNG')
        return {'model': self.cfg['model'], 'input': {
            'prompt': shot['video_prompt'],
            'img_url': 'data:image/png;base64,' + base64.b64encode(data).decode()},
            'parameters': {'audio': bool(shot.get('generate_audio',True)), 'resolution': '720P', 'duration': shot['duration'],
                           'prompt_extend': False, 'watermark': False}}

    def call(self, task_id=None, payload=None):
        import urllib.error, urllib.parse          # 第 34 期第 9 条：HTTP 栈按需加载
        import infra.http_client as http_client
        from api_endpoints import configured_key
        from contract.platform_tools import current_execution
        control = current_execution()
        timeout = 90
        if control is not None:
            timeout = control.remaining(timeout)
        key = configured_key(self.cfg)
        url = self.base + ('/tasks/' + urllib.parse.quote(task_id, safe='') if task_id else '/services/aigc/video-generation/video-synthesis')
        headers = {'Authorization': 'Bearer '+key}
        if payload is not None:
            headers['X-DashScope-Async'] = 'enable'
        result = http_client.request_json('POST' if payload is not None else 'GET', url,
                                          headers=headers, payload=payload, timeout=timeout)
        data = result.data or {}
        if result.ok:
            parsed = data.get('json')
            if parsed is None:
                raise ValueError('接口返回非 JSON 响应')
            return parsed
        status = data.get('status')
        if status is None:
            raise urllib.error.URLError(str(data.get('error_body') or result.reason))
        body = data.get('error_json') or {}
        message = str(body.get('message', '')).replace(key, '[REDACTED]')
        message = re.sub(r'data:image/[^\s\"]+', '[IMAGE]', message)[:600]
        raise ArkRejected(f"HTTP {status} / {body.get('code', 'Unknown')} / {message} / request_id={body.get('request_id', '')}") from None

    def submit(self, shot, frame, request_id, *, payload=None):
        result = self.call(payload=self.payload(shot, frame) if payload is None else payload)
        task_id = result.get('output', {}).get('task_id')
        if not isinstance(task_id, str) or not task_id:
            raise RuntimeError('No task ID returned; check console before retrying')
        from contract.platform_tools import current_execution
        control = current_execution()
        if control is not None:
            control.report(event='remote', remote_task_id=task_id, provider='wan', costly=True)
        return task_id

    def poll(self, task_id):
        result = self.call(task_id=task_id)
        out = result.get('output', {})
        status = {'PENDING':'queued', 'RUNNING':'running', 'SUCCEEDED':'succeeded',
                  'FAILED':'failed', 'CANCELED':'failed'}.get(out.get('task_status'))
        if status is None:
            raise RuntimeError('Unknown task status; task ID preserved')
        return {'status':status, 'provider_status':out.get('task_status'),
                'url':out.get('video_url'), 'usage':result.get('usage'),
                'error_code':out.get('code'), 'request_id':result.get('request_id')}
