"""账号会话的本机落盘：刷新令牌、授权租约、最近一次已知服务器时间与设备指纹种子。

文件在「程序目录/private/账户/session.json」，与模型 API Key（private/密钥）分开存放。
按设计决策 D10 不走 DPAPI 机器绑定：刷新令牌可被服务端吊销，换机重新登录即可。
内容不进日志、不进任务 JSON；本模块不联网、不导入 Tk。
"""
import hashlib
import secrets
from pathlib import Path

from agent.core import read_json, save
from contract.platform_tools import windows_registry
from storage_maintenance import remove_private_file

PROGRAM = Path(__file__).resolve().parent
SESSION_FILE = ('private', '账户', 'session.json')
# 会话字段；device_seed 只在取不到机器标识时兜底，退出登录也保留，保证同机指纹稳定。
SESSION_KEYS = ('email', 'refresh_token', 'lease', 'server_time', 'has_password')
_FINGERPRINT_SALT = 'manju-device-v1:'


def session_path(base=None):
    return Path(base or PROGRAM).joinpath(*SESSION_FILE)


def load(path=None):
    """读取会话；文件缺失、损坏或不是对象都按空会话处理。"""
    data = read_json(path or session_path(), {})
    return data if isinstance(data, dict) else {}


def _write(data, path=None):
    target = Path(path or session_path())
    target.parent.mkdir(parents=True, exist_ok=True)
    save(target, data)


def save_session(fields, path=None):
    """合并写入会话字段；``server_time`` 只增不减（防止旧响应把时钟基线拉回去）。"""
    data = load(path)
    known = int(data.get('server_time') or 0)
    for key in SESSION_KEYS:
        if key in fields:
            data[key] = fields[key]
    data['server_time'] = max(known, int(fields.get('server_time') or 0))
    if fields.get('email'):
        data['last_email'] = str(fields['email'])      # R2052：退出登录后登录框仍默认填上次的邮箱
    _write(data, path)
    return data


def last_email(path=None):
    data = load(path)
    return str(data.get('last_email') or data.get('email') or '')


def note_server_time(server_time, path=None):
    data = load(path)
    if int(server_time or 0) > int(data.get('server_time') or 0):
        data['server_time'] = int(server_time)
        _write(data, path)


def update_seen(path=None):
    return str(load(path).get('update_seen') or '')


def mark_update_seen(version, path=None):
    """记下已主动提示过的新版本号，同一版本不再重复弹提示。"""
    data = load(path)
    data['update_seen'] = str(version or '')
    _write(data, path)


def clear_session(path=None):
    """退出登录：删掉令牌与租约；保留设备种子和最近服务器时间（防回拨钟重放旧租约）。"""
    data = load(path)
    kept = {key: data[key] for key in ('device_seed', 'server_time', 'update_seen', 'last_email') if key in data}
    if data.get('email') and 'last_email' not in kept:
        kept['last_email'] = str(data['email'])
    if kept:
        _write(kept, path)
        return True
    return remove_private_file(path or session_path())


def _machine_guid():
    winreg = windows_registry()
    if winreg is None:
        return ''
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Cryptography',
                            0, winreg.KEY_READ | getattr(winreg, 'KEY_WOW64_64KEY', 0)) as key:
            return str(winreg.QueryValueEx(key, 'MachineGuid')[0] or '')
    except OSError:
        return ''


def device_fingerprint(path=None, machine_id=None):
    """本机设备指纹：机器标识加盐 SHA-256 的 64 位十六进制，只上传哈希。"""
    ident = _machine_guid() if machine_id is None else machine_id
    if not ident:
        data = load(path)
        ident = data.get('device_seed') or ''
        if not ident:
            ident = data['device_seed'] = secrets.token_hex(32)
            _write(data, path)
    return hashlib.sha256((_FINGERPRINT_SALT + ident).encode('utf-8')).hexdigest()
