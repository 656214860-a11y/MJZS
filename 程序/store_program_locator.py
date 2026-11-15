# -*- coding: utf-8 -*-
"""Windows 商店应用与 Claude Desktop 图形程序的定位（R2313，自 workflow_settings 拆出）。

只依赖注册表适配（platform_tools）与标准库；``workflow_settings`` 重新导出这些名字，
``find_program`` 仍在那边按名字取用，所以按 ``workflow_settings.<名字>`` 打的补丁照常生效。
"""
import os
import re
from pathlib import Path

_STORE_PACKAGE=re.compile(r'^(?P<head>.*\\WindowsApps\\)(?P<name>[^\\_]+)_[^\\_]+_(?P<arch>[^\\_]+)__(?P<publisher>[^\\]+)\\(?P<rest>.+)$',re.I)
_STORE_PACKAGES_KEY=r'Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages'


def current_store_program(program):
    """商店应用目录名带版本号，应用自动更新后已保存的路径即失效。
    WindowsApps 不可列目录，改从注册表的已装包清单找同名同发布者的现行版本。"""
    program=str(program or '')
    match=_STORE_PACKAGE.match(program)
    if not match or Path(program).is_file():return program
    prefix=(match['name']+'_').casefold();suffix=('_'+match['arch']+'__'+match['publisher']).casefold()
    from contract.platform_tools import windows_registry
    winreg=windows_registry()
    if winreg is None:return program
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,_STORE_PACKAGES_KEY) as key:
            names=[];index=0
            while True:
                try:names.append(winreg.EnumKey(key,index))
                except OSError:break
                index+=1
    except OSError:return program
    def version(name):
        return tuple(int(part) for part in name[len(prefix):-len(suffix)].split('.') if part.isdigit())
    for name in sorted((n for n in names if n.casefold().startswith(prefix) and n.casefold().endswith(suffix)),key=version,reverse=True):
        candidate=Path(match['head']+name)/match['rest']
        if candidate.is_file():return str(candidate)
    return program


def store_package_program(package, relative):
    """按已安装的商店包定位程序：WindowsApps 不可列目录，只读注册表包清单，新版本优先。"""
    from contract.platform_tools import windows_registry
    winreg=windows_registry()
    if winreg is None:return ''
    prefix=(str(package)+'_').casefold()
    def version(name):
        parts=name.split('_')
        return tuple(int(part) for part in (parts[1] if len(parts)>1 else '').split('.') if part.isdigit())
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,_STORE_PACKAGES_KEY) as key:
            names=[];index=0
            while True:
                try:names.append(winreg.EnumKey(key,index))
                except OSError:break
                index+=1
            for name in sorted((n for n in names if n.casefold().startswith(prefix)),key=version,reverse=True):
                root=''
                try:
                    with winreg.OpenKey(key,name) as package_key:
                        root=str(winreg.QueryValueEx(package_key,'PackageRootFolder')[0] or '')
                except OSError:
                    root=''
                if not root:
                    root=str(Path(os.environ.get('ProgramFiles') or r'C:\Program Files')/'WindowsApps'/name)
                candidate=Path(root)/relative
                if candidate.is_file():return str(candidate)
    except OSError:
        return ''
    return ''


def gui_claude_program(path):
    """路径是否 Claude Desktop 图形程序（商店版／Squirrel／Programs 安装），而非命令行 claude.exe。
    图形程序不接受 -p／--output-format，当作 CLI 调用只会得到「未返回有效 JSON」。"""
    text=str(path or '').replace('/','\\').lower()
    if not text.endswith('\\claude.exe'):return False
    return any(mark in text for mark in ('\\windowsapps\\','\\anthropicclaude\\','\\programs\\claude\\'))


GUI_CLAUDE_CLI_HINT=('所选程序是 Claude Desktop 图形界面，不是命令行（claude.exe）。'
                     '请在模型管理改用「Claude Desktop」条目（模型 ID claude-desktop-app），'
                     '或把本条的程序改为命令行版 claude.exe。')
