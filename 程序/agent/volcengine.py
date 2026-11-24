"""Volcano Ark adapter. No automatic retries of billable POST requests."""
import base64
import re
import json
# 第 34 期第 9 条：urllib.request 连 ssl 一起加载（约 4.4 MB 常驻），真发请求的地方在 call() 里。
from .video import VideoAdapter



class ArkRejected(RuntimeError):
    pass


class VolcengineAdapter(VideoAdapter):
    def __init__(self, cfg):
        self.cfg = cfg
        from infra.api_endpoints import normalize_url
        self.endpoint=normalize_url(cfg.get('base_url','https://ark.cn-beijing.volces.com/api/v3'))+'/contents/generations/tasks'

    def payload(self, shot, frame):
        if shot.get('_reference_mode')=='seedance':
            from .shot_assets import image_url
            from ui.white_model_ref import entries as white_entries   # 第 8 轮：白模参考视频那一槽
            images=[frame]+[a['path'] for a in shot['_asset_references']]
            content=[{'type':'text','text':shot['video_prompt']}]+[
                {'type':'image_url','image_url':{'url':image_url(p)},'role':'reference_image'} for p in images]
            content+=white_entries(shot.get('_white_model_reference'))
            content+=_motion_reference_entries(shot, self.cfg)
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
        import urllib.error, urllib.parse   # 第 34 期第 9 条：HTTP 栈按需加载
        import infra.http_client as http_client
        from infra.api_endpoints import configured_key
        from contract.platform_tools import current_execution
        control = current_execution()
        timeout = 90 if payload is not None else 15
        if control is not None:
            timeout = control.remaining(timeout)
        key = configured_key(self.cfg)
        url = self.endpoint if task_id is None else self.endpoint + '/' + urllib.parse.quote(task_id, safe='')
        result = http_client.request_json('POST' if payload is not None else 'GET', url,
                                          headers={'Authorization': 'Bearer ' + key},
                                          payload=payload, timeout=timeout)
        data = result.data or {}
        if result.ok:
            parsed = data.get('json')
            if parsed is None:
                raise ValueError('火山接口返回非 JSON 响应')
            return parsed
        status = data.get('status')
        if status is None:
            raise urllib.error.URLError(str(data.get('error_body') or result.reason))
        code = 'Unknown'
        message = ''
        try:
            error = (data.get('error_json') or {}).get('error', {})
            vendor_code = error.get('code', '')
            message = str(error.get('message', '')).replace(key, '[REDACTED]')
            message = re.sub(r'data:image/[^\s\"]+', '[IMAGE]', message)[:700]
            if re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', vendor_code):
                code = vendor_code
        except Exception:
            pass
        # Print only whitelisted error code, never echoed request or credentials.
        raise ArkRejected(f'火山接口 HTTP {status} / {code}。{message} 未自动重试。') from None

    def submit(self, shot, frame, request_id, *, payload=None):
        result = self.call(payload=self.payload(shot, frame) if payload is None else payload)
        task_id = result.get('id')
        if not isinstance(task_id, str) or not task_id:
            raise RuntimeError('未收到任务ID；提交结果不确定，先核对控制台')
        from contract.platform_tools import current_execution
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


_MOTION_SUFFIXES = ('.mp4', '.mov', '.webm')


def _motion_base_of(image_path):
    """从资产图路径向上找含 ``assets/资产清单/assets.json`` 的资产库根；找不到回 ``None``。"""
    from pathlib import Path
    for parent in Path(str(image_path or '')).resolve().parents:
        if (parent / 'assets' / '资产清单' / 'assets.json').is_file():
            return parent
    return None


def _motion_rows_of(image_path, aid):
    """读该角色登记的 ``motion_references``；坏行／越界／缺文件／非视频后缀跳过。"""
    from infra.file_cache import read_json
    base = _motion_base_of(image_path)
    if base is None:
        return []
    try:
        plan = read_json(base / 'assets' / '资产清单' / 'assets.json')
    except (OSError, ValueError):
        return []
    row = plan.get(aid) if isinstance(plan, dict) else None
    items = row.get('motion_references') if isinstance(row, dict) else None
    out = []
    for item in items if isinstance(items, list) else ():
        if not isinstance(item, dict):
            continue
        rel = str(item.get('path') or '')
        candidate = (base / rel).resolve() if rel else None
        if (candidate and candidate.is_file() and candidate.is_relative_to(base)
                and candidate.suffix.lower() in _MOTION_SUFFIXES):
            out.append(candidate)
    return out


def _motion_reference_entries(shot, cfg):
    """角色自己登记的动态参考视频（AST-MOTION-REF）：模型认参考视频才进 content 槽位。

    能力判定复用 ``ui.white_model_ref.SUPPORT`` 同一张表：不在表里或槽位不是
    ``content`` 就跳过不带（详情页已写明「仅存档」）；只认本镜引用到的 CHAR_ 资产；
    单条超模型上限当场抛错，不发请求。函数放在文件尾部：``__init__`` 里写死的
    方舟地址已按行号登记进 ``docs/process/外部依赖清单.md``，行号不能漂。
    """
    from ui.white_model_ref import data_url, support, target
    rule = support(*target(cfg))
    if rule is None or rule.get('slot') != 'content':
        return []
    out = []
    limit = int(rule['max_mb']) * 1024 * 1024
    for ref in shot.get('_asset_references') or ():
        ref = ref if isinstance(ref, dict) else {}
        aid = str(ref.get('id') or '')
        if not aid.startswith('CHAR_'):
            continue
        for path in _motion_rows_of(ref.get('path'), aid):
            if path.stat().st_size > limit:
                raise ValueError('动态参考视频 ' + path.name + ' 超过 '
                                 + str(rule['max_mb']) + 'MB 上限：请压小后再提交')
            out.append({'type': 'video_url',
                        'video_url': {'url': data_url(path, path.suffix)},
                        'role': 'reference_video'})
    return out
