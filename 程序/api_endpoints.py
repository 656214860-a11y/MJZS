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
        # 项目目录的 .env 只在第一次迁进本机加密存储（文件不删），之后一律读加密存储。
        import model_secrets
        root=config.get('secret_root')
        model_secrets.import_env_keys(Path(config['project_dir'])/'.env',root=root)
        key=model_secrets.load(name,root=root)
    else:
        key=os.environ.get(name,'').strip()
    if not key or key in ('replace_me','<YOUR_API_KEY>') or not key.isascii() or any(c.isspace() for c in key):
        raise ValueError('当前接口缺少有效 API Key，请在 API 设置中填写并保存')
    return key


def probe_endpoint(base_url, timeout=8):
    """无害的连通性探测：只访问根地址，不发送密钥，不提交任务。"""
    from platform_tools import probe_http_endpoint
    return probe_http_endpoint(base_url, timeout=timeout)


def no_redirect():
    """不跟随重定向的处理器实例（唯一实现，R2178 J13）：密钥与请求体不会被带到别处。

    第 34 期第 9 条：惰性建类——只有真要发 HTTP 时才 import urllib.request。
    """
    from urllib.request import HTTPRedirectHandler

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    return NoRedirect()


def probe_message(base_url):
    """测试连接按钮的状态栏文案：401／403／404 说明接口在、只是要密钥；探测本身抛异常交给调用方。"""
    result = probe_endpoint(base_url)
    if result.get('reachable') and result.get('code') in (401, 403, 404):
        return '接口可达（HTTP %s，需密钥）' % result['code']
    if result.get('reachable'):
        return '接口可达（HTTP %s）' % result['code']
    return '连接失败：' + str(result.get('error', '未知错误'))
