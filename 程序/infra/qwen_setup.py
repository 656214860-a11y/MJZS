"""Local Alibaba connection settings, kept out of project task files and logs."""
import json,os,re
from pathlib import Path
from urllib.parse import urlparse
# R2178 J2：设置窗口在 qwen_setup_dialog，这里只留连接设置的读取、校验与密钥读写，导入时不加载 tkinter。

def settings_path():return Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'漫剧制作助手'/'qwen-api.json'

# 第 65 期任务 1：密钥统一存进「程序目录/private/.env」，qwen-api.json 里不再留明文。
KEY_ENV='DASHSCOPE_API_KEY'


def child_environment():
    """给 Qwen CLI 的最小 Windows 运行环境，不转交父进程中的其它密钥。"""
    allowed = ('APPDATA', 'COMSPEC', 'HOMEDRIVE', 'HOMEPATH', 'LOCALAPPDATA',
               'NUMBER_OF_PROCESSORS', 'OS', 'PATH', 'PATHEXT', 'PROCESSOR_ARCHITECTURE',
               'PROCESSOR_IDENTIFIER', 'SYSTEMROOT', 'TEMP', 'TMP', 'USERNAME', 'WINDIR')
    return {name: os.environ[name] for name in allowed if os.environ.get(name)}


def unified_key():
    """统一那份 .env 里的密钥；没有就是空串。"""
    try:
        import model_pool
        return model_pool.named_key(KEY_ENV)
    except Exception:
        return ''


def save_key(value):
    """把密钥写进统一那份 .env（界面点「保存设置」时走这里）。"""
    import model_pool
    return model_pool.save_named_key(KEY_ENV,value)


def load():
    path=settings_path()
    value={}
    if path.is_file():
        try:
            data=json.loads(path.read_text(encoding='utf-8-sig'))
            if isinstance(data,dict):
                value=data
        except (OSError,ValueError):
            pass
    merged={'base_url':'https://dashscope.aliyuncs.com/compatible-mode/v1','model':'qwen3.7-plus','api_key':'',**value}
    if not merged['api_key']:
        merged['api_key']=unified_key()          # 密钥不再存在这份 json 里，从统一那份补回来
    return merged

def validate(value):
    value={k:str(value.get(k,'')).strip() for k in ('base_url','model','api_key')}
    from infra.api_endpoints import normalize_url
    value['base_url']=normalize_url(value['base_url'])
    url=urlparse(value['base_url'])
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}',value['model']):raise ValueError('请填写有效的模型 ID')
    if not value['api_key'] and url.hostname in ('localhost','127.0.0.1','::1'):value['api_key']='local'
    if not value['api_key'] or any(c.isspace() for c in value['api_key']):raise ValueError('请填写当前接口对应的 API Key')
    value['base_url']=value['base_url'].rstrip('/')
    return value

def api_credential(api):
    """这一条模型的密钥：只有 model_pool 一处判据（.env／private/.env／环境变量／本机加密）。

    第 62 期任务 3：阶段配置挑的模型自带接口，密钥也照它自己的密钥名去取；不另写一遍读取
    逻辑——界面上说这条能用，这里就得找得到同一把钥匙。
    """
    name=str((api or {}).get('key_env') or '').strip()
    if not name:return ''
    try:
        import model_pool
        return model_pool.key_of({'key_env':name})
    except Exception:
        return ''


def environment(model='',api=None):
    """这一趟要交给 Qwen Code 的运行环境。

    第 62 期任务 3：`api` 是阶段配置里选中那一条模型的接口（根地址／密钥名），给了就用它，
    不再无条件打到 Qwen 的默认地址上——用户在那里选了 deepseek，就不该再调用 qwen3.7-plus。
    """
    cfg=load()
    if not cfg['api_key'] and cfg['base_url'].rstrip('/')=='https://dashscope.aliyuncs.com/compatible-mode/v1':
        cfg['api_key']=os.environ.get('DASHSCOPE_API_KEY','')
    if api:
        cfg['base_url']=str(api.get('base_url') or cfg['base_url'])
        cfg['api_key']=api_credential(api) or cfg['api_key']
    cfg=validate(cfg);env=child_environment()
    env.update(OPENAI_API_KEY=cfg['api_key'],OPENAI_BASE_URL=cfg['base_url'],OPENAI_MODEL=model or cfg['model'])
    return env

def probe(cfg):
    """「测试连接」：带密钥查 ``/models``，返回给用户看的一句话（在后台线程里调用）。

    走 model_pool 的统一传输：不跟随重定向（密钥不会被转给跳转目标），并补默认 User-Agent。"""
    import model_pool                                    # 第 34 期第 9 条：HTTP 栈按需加载
    try:
        result=model_pool.http_transport(cfg['base_url']+'/models',None,{'Authorization':'Bearer '+cfg['api_key']},15)
        if result.get('ok'):
            models=[str(m.get('id')) for m in result['data'].get('data',[])]
            return 'API 已连接；模型在返回列表中。' if cfg['model'] in models else 'API 已连接；请确认填写的模型已开通权限。'
        code=result.get('status')
    except Exception:                    # 返回体形状不对、地址拼不成请求：只报连接失败，后台线程不能死在半路
        code=0
    return '连接失败'+('（HTTP '+str(code)+'）' if code else '')+'，请检查网络、根地址和 API Key。'

