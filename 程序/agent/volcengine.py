"""Volcano Ark adapter. No automatic retries of billable POST requests."""
import base64
import re
import json
# 第 34 期第 9 条：urllib.request 连 ssl 一起加载（约 4.4 MB 常驻），真发请求的地方在 call() 里。
from .video import VideoAdapter



class ArkRejected(RuntimeError):
    pass


def no_redirect():
    """第 34 期第 9 条：惰性建类——只有真要发 HTTP 时才 import urllib.request。"""
    import urllib.request

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    return NoRedirect


class VolcengineAdapter(VideoAdapter):
    def __init__(self, cfg):
        self.cfg = cfg
        from api_endpoints import normalize_url
        self.endpoint=normalize_url(cfg.get('base_url','https://ark.cn-beijing.volces.com/api/v3'))+'/contents/generations/tasks'

    def payload(self, shot, frame):
        if shot.get('_reference_mode')=='seedance':
            from .shot_assets import image_url
            from white_model_ref import entries as white_entries   # 第 8 轮：白模参考视频那一槽
            images=[frame]+[a['path'] for a in shot['_asset_references']]
            content=[{'type':'text','text':shot['video_prompt']}]+[
                {'type':'image_url','image_url':{'url':image_url(p)},'role':'reference_image'} for p in images]
            content+=white_entries(shot.get('_white_model_reference'))
            payload={'model':self.cfg['model'],'content':content,
                'generate_audio':bool(shot.get('generate_audio',True)),'ratio':'adaptive','duration':shot['duration'],
                'resolution':self.cfg.get('resolution','720p'),'watermark':False}
            if len(json.dumps(payload).encode())>64*1024*1024:raise ValueError('参考图总大小超过接口64MB请求限制，请压缩图片')
            return payload
        image = frame.read_bytes()
        if not image.startswith(b'\x89PNG\r\n\x1a\n') or len(image) > 20 * 1024 * 1024:
            raise ValueError('首帧必须是20MB以内的PNG')
        payload={
            'model': self.cfg['model'],
            'content': [
                {'type': 'text', 'text': shot['video_prompt']},
                {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(image).decode()}, 'role': 'first_frame'}
            ],
            'generate_audio': bool(shot.get('generate_audio',True)), 'ratio': '16:9',
            'duration': shot['duration'], 'resolution': self.cfg.get('resolution', '720p'),
            'watermark': False
        }
        if 'seedance-1-0' in self.cfg['model']:payload.pop('generate_audio',None)
        return payload

    def call(self, task_id=None, payload=None):
        import urllib.request, urllib.error, urllib.parse   # 第 34 期第 9 条：HTTP 栈按需加载
        from api_endpoints import configured_key
        from platform_tools import current_execution
        control = current_execution()
        timeout = 90 if payload is not None else 15
        if control is not None:
            timeout = control.remaining(timeout)
        key = configured_key(self.cfg)
        url = self.endpoint if task_id is None else self.endpoint + '/' + urllib.parse.quote(task_id, safe='')
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
        try:
            with urllib.request.build_opener(no_redirect()).open(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            code = 'Unknown'
            message = ''
            try:
                error = json.loads(e.read(8192)).get('error', {})
                vendor_code = error.get('code', '')
                message = str(error.get('message', '')).replace(key, '[REDACTED]')
                message = re.sub(r'data:image/[^\s\"]+', '[IMAGE]', message)[:700]
                if re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', vendor_code):
                    code = vendor_code
            except Exception:
                pass
            # Print only whitelisted error code, never echoed request or credentials.
            raise ArkRejected(f'火山接口 HTTP {e.code} / {code}。{message} 未自动重试。') from None

    def submit(self, shot, frame, request_id, *, payload=None):
        result = self.call(payload=self.payload(shot, frame) if payload is None else payload)
        task_id = result.get('id')
        if not isinstance(task_id, str) or not task_id:
            raise RuntimeError('未收到任务ID；提交结果不确定，先核对控制台')
        from platform_tools import current_execution
        control = current_execution()
        if control is not None:
            control.report(event='remote', remote_task_id=task_id, provider='volcengine', costly=True)
        return task_id

    def poll(self, task_id):
        result = self.call(task_id=task_id)
        original = result.get('status')
        status = 'failed' if original in {'cancelled', 'expired'} else original
        if status not in {'queued', 'running', 'succeeded', 'failed'}:
            raise RuntimeError('返回未知任务状态；保留任务ID，不重复提交')
        return {'status': status, 'provider_status': original,
                'url': (result.get('content') or {}).get('video_url'),
                'provider_created_at':result.get('created_at'),'provider_updated_at':result.get('updated_at'),
                'usage': result.get('usage'), 'error_code': (result.get('error') or {}).get('code')}
