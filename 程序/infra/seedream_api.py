"""Volcengine Seedream profiles and direct Images API, shared with the assistant."""
import app_logging
import base64
import json
import os
import re
import uuid
from pathlib import Path
from urllib.parse import urlparse
from agent.core import read, read_json, save
import infra.model_pool as model_pool
from infra.api_endpoints import no_redirect
# 第 34 期第 9 条：`urllib.request`／`urllib.error` 连 ssl 一起加载（约 4.4 MB 常驻），
# 本模块只在真要请求生图接口时用得到——都改成函数内 import。


DEFAULT_URL='https://ark.cn-beijing.volces.com/api/v3'
# 第 65 期任务 1：这条 profile 的密钥在统一那份 .env 里叫什么。
DEFAULT_KEY_ENV='ARK_API_KEY'


def key_name_for(base_url):
    """火山方舟用 ARK_API_KEY（与云端视频同一把）；别的自建端点按主机名各起一个，
    免得几条 profile 互相盖掉。"""
    text=str(base_url or '').rstrip('/')
    if text==DEFAULT_URL:
        return DEFAULT_KEY_ENV
    host=urlparse(text).hostname or 'custom'
    return 'SEEDREAM_%s_KEY' % re.sub(r'[^0-9A-Za-z]+','_',host).strip('_').upper()


def unified_key(name):
    """统一那份 .env（程序目录/private/.env）里的密钥；没有就是空串。"""
    try:
        return model_pool.named_key(name)
    except Exception:
        return ''


def settings_path():
    return Path(os.environ['LOCALAPPDATA'])/'漫剧制作助手/seedream_profiles.json'


def read_settings():
    data=read_json(settings_path())
    if isinstance(data,dict) and isinstance(data.get('profiles'),dict):
        return data
    return {'active':'','profiles':{}}


def write_settings(data):
    # 原子写只有 agent.core.save 一份（先写临时文件再替换，带 Windows 句柄重试）。
    save(settings_path(),data)


def protect(data,decrypt=False,label='火山 API Key'):
    """Windows DPAPI 加解密：实现只在 model_secrets.protect，这里留默认标签的入口给火山、TTS、Comfy 云模型。

    label 只用于出错时的中文提示（各家的 Key 名字不同），加解密行为完全一样。
    """
    from infra import model_secrets
    return model_secrets.protect(data,decrypt,label)


def validate(base_url,model,key):
    base_url=base_url.strip().rstrip('/')
    if base_url.endswith('/images/generations'):base_url=base_url[:-len('/images/generations')]
    parsed=urlparse(base_url)
    try:parsed.port
    except ValueError:raise ValueError('接口端口无效') from None
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or any(c.isspace() for c in base_url):
        raise ValueError('请填写不含密钥或查询参数的 HTTPS API 根地址')
    model=model.strip();key=key.strip()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}',model):raise ValueError('请填写火山控制台已开通的模型 ID 或推理接入点 ID')
    if not key or not key.isascii() or any(c.isspace() for c in key):raise ValueError('请填写有效的火山方舟 API Key')
    return {'base_url':base_url,'model':model,'api_key':key}


def public_profile(profile_id=''):
    data=read_settings();profile_id=profile_id or data.get('active','')
    value=data.get('profiles',{}).get(profile_id)
    if not isinstance(value,dict):raise ValueError('请先在“火山 API 设置”保存模型 ID 和 API Key。')
    return {'profile_id':profile_id,'base_url':value['base_url'],'model':value['model']}


def profile_key(value,base_url=''):
    """这条 profile 的密钥：统一那份 .env 优先，老安装留下的本机加密那份仍认（只读兼容）。"""
    key=unified_key(str(value.get('key_env') or key_name_for(base_url)))
    if key:
        return key
    enc=value.get('encrypted_key')
    if not enc:
        raise ValueError('请在“火山 API 设置”里重新填写 API Key 并保存。')
    return protect(base64.b64decode(enc),True).decode('utf-8')


def load_profile(profile_id=''):
    public=public_profile(profile_id)
    value=read_settings()['profiles'][public['profile_id']]
    key=profile_key(value,public['base_url'])
    return {**validate(public['base_url'],public['model'],key),'profile_id':public['profile_id']}


def save_profile(base_url,model,key,profile_id=None):
    """第 65 期任务 1：密钥写进统一那份 .env，profile 里只留根地址与模型 ID。"""
    value=validate(base_url,model,key);data=read_settings()
    profile_id=profile_id or uuid.uuid4().hex
    record=data.get('profiles',{}).get(profile_id) or {}
    key_env=str(record.get('key_env') or key_name_for(value['base_url']))
    model_pool.save_named_key(key_env, value.pop('api_key'))
    data.setdefault('profiles',{})[profile_id]={**value,'key_env':key_env}
    data['active']=profile_id;write_settings(data)
    return profile_id


class Rejected(ValueError):pass
class Uncertain(RuntimeError):pass


def request_image(profile,payload):
    from urllib.request import Request, build_opener        # 第 34 期第 9 条：HTTP 栈按需加载
    from urllib.error import HTTPError
    # Redirects must never forward the user's Authorization header to another host.
    request=Request(profile['base_url']+'/images/generations',data=json.dumps(payload,ensure_ascii=False).encode('utf-8'),
                    headers={'Authorization':'Bearer '+profile['api_key'],'Content-Type':'application/json'})
    try:
        with build_opener(no_redirect()).open(request,timeout=300) as response:
            raw=response.read(64*1024*1024+1)
    except HTTPError as exc:
        try:detail=exc.read().decode('utf-8','replace').strip()
        except Exception:detail=''
        messages={400:'参数或模型 ID 不匹配',401:'API Key 无效',403:'模型权限或账户余额不足',404:'接口或模型不存在',429:'请求限流或额度不足'}
        if detail:
            try:
                parsed=json.loads(detail)
                error=parsed.get('error') if isinstance(parsed,dict) else parsed
                if isinstance(error,dict):detail=error.get('message') or error.get('code') or detail
                elif isinstance(error,str):detail=error
            except Exception:app_logging.swallowed()
        if 400<=exc.code<500:
            raise Rejected('火山接口拒绝请求：'+messages.get(exc.code,'HTTP '+str(exc.code))+'。'+(detail or '请检查火山 API 设置。')) from None
        raise Uncertain('火山接口响应异常，未自动重试；请先在火山控制台核实本次用量。') from None
    except (OSError,TimeoutError):
        raise Uncertain('火山请求连接中断或超时，结果未确定；未自动重复扣费请求。') from None
    try:
        if len(raw)>64*1024*1024:raise ValueError('响应过大')
        result=json.loads(raw)
        data=result.get('data',[])
        if len(data)!=1 or not data[0].get('b64_json'):raise ValueError('没有返回单张图片')
        image=base64.b64decode(data[0]['b64_json'],validate=True)
        if not image:raise ValueError('图片为空')
        return image
    except (ValueError,KeyError,TypeError):
        raise Uncertain('火山已返回响应，但图片数据不完整；保留记录，未自动重试。') from None


# 上一次请求没有拿到结果的状态：可能已经扣费，未核实前不得重复提交。
UNSETTLED = ('sending', 'uncertain')


def unsettled(folder, values, prefix='seedream_'):
    """返回上次请求未拿到结果的编号，供界面先提示用户核实。"""
    blocked = []
    for value in values:
        path = Path(folder) / (prefix + str(value) + '.json')
        try:
            state = read(path).get('state') if path.is_file() else ''
        except (OSError, ValueError):
            state = ''
        if state in UNSETTLED:
            blocked.append(str(value))
    return blocked


def release(folder, values, prefix='seedream_'):
    """用户已在火山控制台核实后，把未确定记录降级为 failed，允许本次重新提交。

    只改状态，不删除记录，便于之后继续核对用量。
    """
    changed = []
    for value in values:
        path = Path(folder) / (prefix + str(value) + '.json')
        if not path.is_file():
            continue
        try:
            data = read(path)
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get('state') in UNSETTLED:
            data.update(state='failed', note='您已在火山控制台核实，本次重新生成')
            save(path, data)
            changed.append(str(value))
    return changed
