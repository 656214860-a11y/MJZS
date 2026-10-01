# -*- coding: utf-8 -*-
"""本机加密的模型密钥：「直接输入」那种密钥的落脚处。

规格（《三虎模型设置》）要求两种放进密钥的方式：
- 从 .env 读：记录里只存变量名（`key_env`），运行时再取；
- 直接输入：用系统密钥链加密存本机，**明文不落盘**，配置 JSON 里也一个字都不写。

这个模块只管第二种：DPAPI 加密写到「程序目录/private/密钥/<名字>.dpapi」。它在本层
实现 Windows 用户范围的加解密，不再反向依赖任何供应商 API；密钥只在这条链上出现，
日志与界面里一律走 `redacted()`（前 4 位 ＋ ****）。
"""
import ctypes
import os
import re
from pathlib import Path
from storage_maintenance import remove_private_file
from model_protocol import BytesProtector
from agent.core import replace, temporary_path

PROGRAM = Path(__file__).resolve().parent
SECRET_DIR = ('private', '密钥')
SUFFIX = '.dpapi'
LABEL = '模型 API Key'                      # 只用于 DPAPI 报错时的中文提示
KEEP = 4                                    # 日志／界面里露出的位数（规格：前 4 位 ＋ ****）


def protect(data, decrypt=False, label='模型 API Key'):
    """Windows DPAPI 加解密；仅由密钥存储层实现，供应商模块不参与。"""
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    function = (ctypes.windll.crypt32.CryptUnprotectData if decrypt
                else ctypes.windll.crypt32.CryptProtectData)
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise ValueError('Windows 无法读取或保存' + label + '，请在当前用户下重新保存。')
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        ctypes.windll.kernel32.LocalFree.restype = ctypes.c_void_p
        ctypes.windll.kernel32.LocalFree(output.pbData)


# 显式校验本层实现遵循协议；不注册全局实现，也不产生跨模块依赖。
PROTECTOR: BytesProtector = protect


def name_for(model_id, key_env=''):
    """这份密钥叫什么名字：填了密钥名就用它，没填就按模型 ID 起一个（同一个模型名字稳定）。"""
    text = str(key_env or '').strip()
    if text:
        return text
    cleaned = re.sub(r'[^0-9A-Za-z]+', '_', str(model_id or '').strip()).strip('_').upper()
    return ('MODEL_%s_KEY' % cleaned) if cleaned else ''


def safe_name(name):
    """名字 → 文件名：只留字母数字与 ._-，别的字符一律换成下划线（不留路径分隔符）。"""
    return re.sub(r'[^0-9A-Za-z_.-]+', '_', str(name or '').strip()) or ''


def path(name, program=None, root=None):
    folder = Path(root) if root else Path(program or PROGRAM)
    return folder.joinpath(*SECRET_DIR, safe_name(name) + SUFFIX)


def redacted(value):
    """能给人看的那一眼：前 4 位 ＋ ****（短到不足 4 位就只剩 ****）。"""
    text = str(value or '')
    return (text[:KEEP] + '****') if len(text) > KEEP else '****'


def load(name, program=None, root=None):
    """读回那把密钥（只有当前 Windows 用户解得开）；没有、坏了、名字为空都当空串。"""
    target = path(name, program, root)
    if not safe_name(name) or not target.is_file():
        return ''
    try:
        return PROTECTOR(target.read_bytes(), decrypt=True, label=LABEL).decode('utf-8')
    except Exception:
        return ''                            # 别的用户存的、文件坏了：当没配，不打断调用


def save(name, value, program=None, root=None):
    """把这把密钥加密存到本机（原子替换）；返回存到哪儿了。空值、带空格一律拒绝。"""
    text = str(value or '').strip()
    if not text:
        raise ValueError('API Key 不能为空')
    if any(char.isspace() for char in text):
        raise ValueError('API Key 不能带空格')
    if not safe_name(name):
        raise ValueError('请先填模型 ID（或密钥名），才知道这份密钥该记在谁名下')
    target = path(name, program, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = temporary_path(target)
    temporary.write_bytes(PROTECTOR(text.encode('utf-8'), label=LABEL))
    replace(temporary, target)
    return target


def migrate_legacy_env(legacy_path, program=None, root=None):
    """把受本程序管理的旧 ``.env`` 密钥迁入 DPAPI 后再清除旧文件。

    只有所有条目均已成功加密且旧文件已删除，迁移才算完成。任一加密、解析或删除失败
    都保留旧 ``.env``，让用户可以恢复重试；错误信息绝不包含变量值或密钥内容。
    """
    legacy = Path(legacy_path)
    if not legacy.is_file():
        return 0
    entries = {}
    try:
        lines = legacy.read_text(encoding='utf-8-sig').splitlines()
    except OSError as exc:
        raise OSError('无法读取旧密钥文件，未执行迁移') from exc
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if '=' not in line:
            raise ValueError('旧密钥文件格式无效，未执行迁移')
        name, value = line.split('=', 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if not safe_name(name) or not value or any(char.isspace() for char in value):
            raise ValueError('旧密钥文件含无效条目，未执行迁移')
        entries[name] = value
    if not entries:
        raise ValueError('旧密钥文件没有可迁移条目，未执行迁移')

    destination_root = Path(root) if root else Path(program or PROGRAM)
    backups = {}
    try:
        for name, value in entries.items():
            target = path(name, destination_root)
            backups[target] = target.read_bytes() if target.is_file() else None
            save(name, value, destination_root)
    except Exception:
        for target, previous in backups.items():
            try:
                if previous is None:
                    remove_private_file(target)
                else:
                    temporary = temporary_path(target)
                    temporary.write_bytes(previous)
                    replace(temporary, target)
            except OSError:
                pass
        raise
    if not remove_private_file(legacy):
        raise OSError('旧密钥文件未能清除，已保留原文件以便恢复')
    return len(entries)


def clear(name, program=None, root=None):
    """删掉这份本机密钥；本来就没有返回 False（界面据此说「本来就没存」）。"""
    target = path(name, program, root)
    if target.is_file():
        return remove_private_file(target)
    return False
