"""Shared endpoint validation; editing or saving never contacts a service."""
# 第 34 期第 9 条：`urllib.request` 连 ssl 一起加载（约 4.4 MB 常驻），探测函数里再 import。
from urllib.parse import urlparse

def normalize_url(value):
    value=str(value).strip().rstrip('/')
    parsed=urlparse(value)
    try:parsed.port
    except ValueError:raise ValueError('API 地址端口无效') from None
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or any(c.isspace() for c in value):
        raise ValueError('请填写完整 API 根地址，不要包含密钥、空格或查询参数')
    if parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in ('127.0.0.1','localhost','::1')):
        raise ValueError('请使用 HTTPS 地址；本机服务可使用 HTTP')
    return value

def configured_key(config):
    """Read credentials for this configuration without changing process globals."""
    import os
    from pathlib import Path
    if not isinstance(config, dict):
        raise ValueError('接口配置无效，请在 API 设置中重新保存')
    name=config.get('key_env','VIDEO_API_KEY')
    key=''
    if config.get('key_provider') == 'model_pool':
        # 新会话只保存变量名，不再把程序目录的明文 .env 路径写进项目配置。
        # 这里直接读 DPAPI 存储，避免 model_pool（它兼容读取旧配置时会调用本函数）形成导入环。
        import model_secrets
        key=model_secrets.load(name)
    elif config.get('project_dir'):
        path=Path(config['project_dir'])/'.env'
        if path.is_file():
            for line in path.read_text(encoding='utf-8-sig').splitlines():
                if line.lstrip().startswith('#') or '=' not in line:continue
                entry,value=line.split('=',1)
                if entry.strip()==name:key=value.strip().strip('"').strip("'")
    else:
        key=os.environ.get(name,'').strip()
    if not key or key in ('replace_me','<YOUR_API_KEY>') or not key.isascii() or any(c.isspace() for c in key):
        raise ValueError('当前接口缺少有效 API Key，请在 API 设置中填写并保存')
    return key


def probe_endpoint(base_url, timeout=8):
    """无害的连通性探测：只访问根地址，不发送密钥，不提交任务。"""
    import urllib.request, urllib.error        # 第 34 期第 9 条：HTTP 栈按需加载
    try:
        with urllib.request.urlopen(str(base_url).rstrip('/'), timeout=timeout) as response:
            return {'reachable': True, 'code': response.status}
    except urllib.error.HTTPError as exc:
        return {'reachable': True, 'code': exc.code}
    except Exception as exc:
        reason = getattr(exc, 'reason', None)
        detail = str(reason) if reason is not None else str(exc)
        low = detail.lower()
        if 'getaddrinfo' in low or 'name or service not known' in low or 'gaierror' in low:
            hint = '域名解析失败，请检查网络/DNS 或确认地址拼写正确'
        elif 'certificate' in low or 'ssl' in low:
            hint = 'HTTPS 证书校验失败，请检查系统时间、代理或防火墙'
        elif 'timed out' in low or 'timeout' in low:
            hint = '连接超时，请检查网络、防火墙或代理'
        elif 'refused' in low or '10061' in low:
            hint = '连接被拒绝，请确认地址与端口正确'
        else:
            hint = type(exc).__name__
        return {'reachable': False, 'code': None, 'error': f'{hint}（{detail[:160]}）'}
