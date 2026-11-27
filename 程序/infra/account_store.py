"""账号会话的本机落盘：刷新令牌、授权租约和最近一次已知服务器时间。

文件在「程序目录/private/账户/session.json」，与模型 API Key（private/密钥）分开存放。
文件级 MAC 校验内容完整性。DPAPI 保护本机 MAC 密钥，D10 仍允许换机后重新登录并取得授权。
内容不进日志、不进任务 JSON；本模块不联网、不导入 Tk。
"""
import hashlib
import json
import secrets
from pathlib import Path

from agent.core import read, save_bytes, save_text
from agent.publication import access
from contract.platform_tools import windows_registry
from infra import session_integrity
from infra.storage_maintenance import remove_private_file

PROGRAM = Path(__file__).resolve().parents[1]
SESSION_FILE = ('private', '账户', 'session.json')
DEVICE_SEED_FILE = ("设备", "seed.txt")
SESSION_KEYS = ('email', 'refresh_token', 'lease', 'server_time', 'has_password', 'login_generation')
_FINGERPRINT_SALT = 'manju-device-v1:'
_CLOCK_KEY = r'Software\漫剧制作助手'
_CLOCK_VALUE = 'clock_floor'


def session_path(base=None):
    return Path(base or PROGRAM).joinpath(*SESSION_FILE)


def renew_lock_path(path=None):
    return Path(path or session_path()).with_name('renew.lock')


def load(path=None):
    """完整性验证失败按未登录处理，由既有登录入口提示重新登录。"""
    target = Path(path or session_path())
    try:
        with access():
            data = read_session_file(target)
    except (OSError, ValueError):
        data = {}
    if session_integrity.verify(data, target):
        return session_integrity.fields(data)
    if target.is_file():
        with access():
            try:
                return _load_write(target)
            except (OSError, ValueError):
                return {}
    return {}


def _load_write(path=None):
    """锁内读取和校验，避免重新签署失效会话或清除其他进程刚保存的会话。"""
    target = Path(path or session_path())
    try:
        data = read_session_file(target)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise ValueError(f'账户会话文件 {target} 无法读取。请关闭占用它的程序后重试；'
                         '如果文件已损坏，请移走文件再重新登录。') from exc
    if session_integrity.verify(data, target):
        return session_integrity.fields(data)
    if isinstance(data, dict) and '_mac' not in data and '_mac_key_id' not in data:
        _device_seed(data, target)
    remove_private_file(target)
    return {}


def read_session_file(path=None):
    """读会话文件：DPAPI 密文先解密；旧明文照读（下次写入时转存为密文）。

    密文解不开（被篡改或换过用户）返回空字典，交给完整性校验按未登录恢复。
    """
    target = Path(path or session_path())
    raw = target.read_bytes()
    if not session_integrity.is_sealed_blob(raw):
        return read(target)
    try:
        text = session_integrity.protect_session(raw, decrypt=True)
    except ValueError:
        return {}
    return json.loads(text.decode('utf-8'))


def write_session_file(data, path=None):
    """整份会话（含 MAC）序列化后经 DPAPI 加密落盘：先解密再验 MAC。"""
    target = Path(path or session_path())
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False).encode('utf-8')
    save_bytes(target, session_integrity.protect_session(payload))


def _write(data, path=None):
    target = Path(path or session_path())
    write_session_file(session_integrity.seal(data, target), target)


def _read_clock_value(registry, key):
    try:
        value, kind = registry.QueryValueEx(key, _CLOCK_VALUE)
    except FileNotFoundError:
        return 0
    return max(0, value) if kind == registry.REG_QWORD and isinstance(value, int) else 0


def _registry_clock_floor(path=None, *, value=None):
    """返回独立基线，访问失败为 None。替代会话路径与主机注册表隔离。"""
    if path is not None and Path(path) != session_path():
        return None
    registry = windows_registry()
    if registry is None:
        return None
    permissions = registry.KEY_QUERY_VALUE | registry.KEY_SET_VALUE
    try:
        open_key = registry.OpenKey if value is None else registry.CreateKeyEx
        with open_key(registry.HKEY_CURRENT_USER, _CLOCK_KEY, 0, permissions) as key:
            known = _read_clock_value(registry, key)
            if value is not None and value > known:
                registry.SetValueEx(key, _CLOCK_VALUE, 0, registry.REG_QWORD, value)
                return value
            return known
    except FileNotFoundError:
        return 0 if value is None else None
    except OSError:
        return None


def clock_baseline(session_floor=0, path=None):
    """JSON 与注册表分别单调保存，读取时合取较高的可信基线。"""
    return max(int(session_floor or 0), _registry_clock_floor(path) or 0)


def clock_backup_available(path=None):
    return _registry_clock_floor(path) is not None


def save_session(fields, path=None):
    """合并写入会话字段；``server_time`` 只增不减（防止旧响应把时钟基线拉回去）。"""
    with access():
        data = _load_write(path)
        known = int(data.get('server_time') or 0)
        for key in SESSION_KEYS:
            if key in fields:
                data[key] = fields[key]
        data['server_time'] = max(known, int(fields.get('server_time') or 0))
        if fields.get('email'):
            data['last_email'] = str(fields['email'])      # R2052：退出登录后登录框仍默认填上次的邮箱
        _write(data, path)
        if data['server_time']:
            _registry_clock_floor(path, value=data['server_time'])
    return data


def last_email(path=None):
    data = load(path)
    return str(data.get('last_email') or data.get('email') or '')


def note_server_time(server_time, path=None):
    with access():
        data = _load_write(path)
        if int(server_time or 0) > int(data.get('server_time') or 0):
            data['server_time'] = int(server_time)
            _write(data, path)
            _registry_clock_floor(path, value=data['server_time'])


def update_seen(path=None):
    return str(load(path).get('update_seen') or '')


def mark_update_seen(version, path=None):
    """记下已主动提示过的新版本号，同一版本不再重复弹提示。"""
    with access():
        data = _load_write(path)
        data['update_seen'] = str(version or '')
        _write(data, path)


def clear_session(path=None):
    """退出登录：删掉令牌与租约；保留独立存放的设备种子和最近服务器时间（防回拨钟重放旧租约）。"""
    with access():
        data = _load_write(path)
        if 'device_seed' in data:
            _device_seed(data, path)
        kept = {key: data[key] for key in ('server_time', 'update_seen', 'last_email') if key in data}
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


def _device_seed_path(path=None):
    account_dir = Path(path or session_path()).parent
    private_dir = account_dir.parent if account_dir.name == SESSION_FILE[1] else account_dir
    return private_dir.joinpath(*DEVICE_SEED_FILE)


def _device_seed(data, path=None, *, generate=False):
    """在发布锁内读取或迁移种子。先持久化种子，再由调用方保存会话。"""
    seed_path = _device_seed_path(path)
    try:
        seed = seed_path.read_text(encoding='utf-8').strip()
    except FileNotFoundError:
        seed = ''
    legacy = data.pop('device_seed', '')
    if not seed and (legacy or generate):
        seed = legacy or secrets.token_hex(32)
        seed_path.parent.mkdir(parents=True, exist_ok=True)
        save_text(seed_path, seed)
    return seed


def device_fingerprint(path=None, machine_id=None):
    """本机设备指纹：机器标识加盐 SHA-256 的 64 位十六进制，只上传哈希。"""
    ident = _machine_guid() if machine_id is None else machine_id
    if not ident or 'device_seed' in load(path):
        with access():
            data = _load_write(path)
            migrate = 'device_seed' in data
            seed = _device_seed(data, path, generate=not ident)
            if migrate:
                _write(data, path)
            ident = ident or seed
    return hashlib.sha256((_FINGERPRINT_SALT + ident).encode('utf-8')).hexdigest()
