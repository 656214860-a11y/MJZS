# -*- coding: utf-8 -*-
"""桌面图标与快捷方式（第 21 期）：把三虎那张 .ico 挂到桌面快捷方式上，并建出快捷方式。

- 快捷方式指向自带解释器（pythonw.exe）＋程序根目录里的「启动漫剧制作助手.pyw」，
  工作目录＝程序根目录，图标＝根目录里那张设计好的 漫剧制作助手.ico（没有才退回 app_icon）。
- 建 .lnk 借 Windows 自带的 PowerShell ＋ WScript.Shell：不引 pywin32。
  脚本按 ASCII 写盘、里面的中文用 [char] 码拼——PowerShell 读 UTF-8 的 here-string 会把
  中文读坏（第 20 期就是这么踩到的）。
- 桌面与程序目录各放一份：前者给用户点，后者是重建/备份用（重装后照样能把桌面那份补回来）。
运行：python app_shortcut.py  会（重新）建好这两份快捷方式并打印路径。
"""
import infra.app_logging as app_logging
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from infra.file_cache import remove_temporary_file

import infra.app_icon as app_icon
from contract.app_metadata import APP_NAME
from agent.core import save_bytes

PROGRAM = Path(__file__).resolve().parent
NAME = APP_NAME                           # 快捷方式的显示名字
ICON_NAME = '漫剧制作助手.ico'              # 程序根目录里那张设计好的图
# 第 26 期第 9 条：用户报「桌面图片已做好但是导入失败」——其实图换了，是资源管理器拿**图标缓存**
# 画桌面（同名文件换了内容它认不出来）。所以除了原来那张，再按内容指纹写一份新名字的
# （漫剧制作助手_图标_<8位哈希>.ico），快捷方式指向带指纹的那一份：路径变了，缓存一定失效。
ICON_TAG = '_图标_'
LAUNCHER = '启动漫剧制作助手.pyw'            # 程序根目录里那个双击入口
# 图标路径含中文时，资源管理器读不出快捷方式里的 IconLocation，画成空白文件图标（R2339 实测）；
# 所以快捷方式改指向复制到纯英文目录里的那一份。
ICON_HOME = app_icon.ICON_HOME             # 与窗口图标共用同一个英文目录（测试可替换）


def ps_text(value):
    """一段文字写成 PowerShell 的 [char] 拼法：脚本按 ASCII 存，中文才不会被读坏。"""
    codes = ', '.join('0x%X' % ord(char) for char in str(value))
    return '(-join ([char[]]@(%s)))' % codes


def powershell():
    """系统自带的 PowerShell；找不到就返回 None（那就不建快捷方式，绝不抛）。"""
    if os.name != 'nt':
        return None
    for candidate in ('powershell.exe', 'pwsh.exe'):
        try:
            found = subprocess.run([candidate, '-NoProfile', '-Command', 'exit 0'],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            if found.returncode == 0:
                return candidate
        except Exception:
            continue
    return None


# 给 .lnk 写 System.AppUserModel.ID，与窗口里 app_icon.set_app_id 设的一致：
# 任务栏才认得运行窗口就是这份快捷方式，固定后沿用它的图标与启动方式（不再变成 Python 图标）。
APP_ID_CODE = '''Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
[ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IPropStore { int GetCount(out uint c); int GetAt(uint i, out PropKey k);
 int GetValue(ref PropKey k, out PropVar v); int SetValue(ref PropKey k, ref PropVar v); int Commit(); }
[StructLayout(LayoutKind.Sequential, Pack = 4)] public struct PropKey { public Guid fmtid; public uint pid; }
[StructLayout(LayoutKind.Explicit)] public struct PropVar { [FieldOffset(0)] public ushort vt; [FieldOffset(8)] public IntPtr p; }
public static class LinkAppId {
 [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
 static extern void SHGetPropertyStoreFromParsingName(string path, IntPtr bc, int flags, ref Guid riid,
  [MarshalAs(UnmanagedType.Interface)] out IPropStore store);
 public static void Set(string path, string id) {
  Guid iid = new Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"); IPropStore store;
  SHGetPropertyStoreFromParsingName(path, IntPtr.Zero, 2, ref iid, out store);
  PropKey key = new PropKey(); key.fmtid = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"); key.pid = 5;
  PropVar value = new PropVar(); value.vt = 31; value.p = Marshal.StringToCoTaskMemUni(id);
  try { Marshal.ThrowExceptionForHR(store.SetValue(ref key, ref value)); Marshal.ThrowExceptionForHR(store.Commit()); }
  finally { Marshal.FreeCoTaskMem(value.p); Marshal.ReleaseComObject(store); } } }
'@'''


def script(link, target, arguments, workdir, icon, description='', app_id=app_icon.APP_ID):
    """生成那段建快捷方式的 PowerShell 脚本（纯 ASCII）。"""
    return '\n'.join([
        "$ErrorActionPreference = 'Stop'",
        '$ws = New-Object -ComObject WScript.Shell',
        '$lnk = $ws.CreateShortcut(%s)' % ps_text(link),
        '$lnk.TargetPath = %s' % ps_text(target),
        '$lnk.Arguments = %s' % ps_text(arguments),
        '$lnk.WorkingDirectory = %s' % ps_text(workdir),
        '$lnk.IconLocation = %s' % ps_text(icon),
        '$lnk.Description = %s' % ps_text(description or NAME),
        '$lnk.Save()',
        APP_ID_CODE,
        '[LinkAppId]::Set(%s, %s)' % (ps_text(link), ps_text(app_id)),
        ''])


def make_shortcut(link, target, arguments='', workdir=None, icon=None, description=''):
    """建一份快捷方式；返回建好的 .lnk 路径，建不出来返回 None。"""
    shell = powershell()
    if shell is None:
        return None
    link = Path(link)
    payload = script(link, target, arguments, workdir or str(PROGRAM),
                     icon or str(app_icon.icon_path()), description)
    script_path = None
    try:
        link.parent.mkdir(parents=True, exist_ok=True)
        handle, script_path = tempfile.mkstemp(suffix='.ps1', prefix='drama_lnk_')
        os.close(handle)
        with open(script_path, 'w', encoding='ascii', errors='replace') as fh:
            fh.write(payload)
        done = subprocess.run([shell, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', script_path],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        if done.returncode != 0:
            return None
        return link if link.is_file() else None
    except Exception:
        return None
    finally:
        if script_path:
            from infra.file_cache import remove_temporary_file
            remove_temporary_file(script_path)


def root_dir(program=None):
    """程序根目录：双击入口（启动漫剧制作助手.pyw）所在的那一层。"""
    return Path(program or PROGRAM).parent


def launcher_path(program=None):
    """双击入口：程序根目录里的 启动漫剧制作助手.pyw。"""
    return root_dir(program) / LAUNCHER


def icon_digest(data):
    """图标内容的前 8 位 sha1：用它当文件名，换了图就一定换名字。"""
    return hashlib.sha1(data).hexdigest()[:8]


def tagged_icon_name(data):
    """带指纹的图标名：漫剧制作助手_图标_<哈希>.ico。"""
    return '%s%s%s.ico' % (Path(ICON_NAME).stem, ICON_TAG, icon_digest(data))


def versioned_icons(program=None):
    """根目录里那些带指纹的图标（新的在前）。"""
    pattern = '%s%s*.ico' % (Path(ICON_NAME).stem, ICON_TAG)
    try:
        found = [path for path in root_dir(program).glob(pattern) if path.is_file()]
    except Exception:
        return []
    return sorted(found, key=lambda path: path.stat().st_mtime, reverse=True)


def icon_file(program=None):
    """快捷方式图标：优先带指纹的那张（绕开图标缓存），再退回设计图与算出来的那张。"""
    tagged = versioned_icons(program)
    if tagged:
        return tagged[0]
    designed = root_dir(program) / ICON_NAME
    if designed.is_file() and designed.stat().st_size > 0:
        return designed
    return app_icon.icon_path()


def shell_icon(icon, home=None):
    """快捷方式实际引用的图标：同 app_icon.ascii_icon，目录取本模块 ICON_HOME（测试可替换）。"""
    return app_icon.ascii_icon(icon, home or ICON_HOME)


def runner(program=None):
    """(解释器, 参数, 工作目录)：自带解释器的 pythonw ＋ 根目录的双击入口。"""
    root = root_dir(program)
    pythonw = root / '运行环境' / 'Python' / 'pythonw.exe'
    launcher = launcher_path(program)
    exe = pythonw if pythonw.is_file() else Path(sys.executable)
    return exe, ('-I "%s"' % launcher) if launcher.is_file() else '', root


def desktop_dir():
    """桌面目录：优先问 Windows（中文系统上文件夹名不一定是 Desktop）。"""
    try:
        import ctypes
        from ctypes import wintypes
        shell32 = ctypes.windll.shell32
        buf = ctypes.create_unicode_buffer(260)
        # CSIDL_DESKTOPDIRECTORY = 0x10
        if shell32.SHGetFolderPathW(None, 0x10, None, 0, buf) == 0 and buf.value:
            return Path(buf.value)
    except Exception:
        app_logging.swallowed()
    return Path(os.path.expanduser('~')) / 'Desktop'


def install_icon(program=None, force=True):
    """把 app_icon 画的那张 .ico 复制成根目录里「设计好的」那一张（桌面快捷方式用的就是它）。

    第 25 期：图标重新设计之后，光换 assets 里那份不够——快捷方式认的是根目录这一张。
    写不出来返回 None，绝不抛。
    """
    program = Path(program or PROGRAM)
    source = app_icon.ensure(force=force)
    if source is None or not Path(source).is_file():
        return None
    root = root_dir(program)
    target = root / ICON_NAME
    try:
        data = Path(source).read_bytes()
        save_bytes(target, data)
        # 带指纹的那一份才是快捷方式真正指向的（第 26 期第 9 条：同名换内容看不出来）
        tagged = root / tagged_icon_name(data)
        save_bytes(tagged, data)
        for old in versioned_icons(program):
            if old.name != tagged.name:
                try:
                    remove_temporary_file(old)
                except OSError:
                    pass
    except Exception:
        return None
    return target


def refresh_shell():
    """让资源管理器重画图标（换了图之后桌面上那张才立刻变样）；拿不到能力就算了。

    第 26 期第 9 条：只广播 SHChangeNotify 有时候还不够——资源管理器的图标缓存里还是旧画。
    再叫一次系统自带的 ie4uinit（把图标缓存重建一遍），两条都试，能成一条就算成。
    """
    moved = False
    try:
        import ctypes
        # SHCNE_ASSOCCHANGED = 0x08000000, SHCNF_IDLIST = 0
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
        moved = True
    except Exception:
        app_logging.swallowed()
    for exe in (os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'ie4uinit.exe'),
                'ie4uinit.exe'):
        try:
            done = subprocess.run([exe, '-show'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  timeout=30)
            if done.returncode == 0:
                moved = True
            break
        except Exception:
            continue
    return moved


def ensure(program=None, name=NAME, folder=None):
    """只在根目录建一份快捷方式（用户固定到任务栏的唯一来源）；返回建出来的路径表。"""
    program = Path(program or PROGRAM)
    if not (root_dir(program) / ICON_NAME).is_file():
        install_icon(program, force=False)      # 设计图丢了就用算出来的那张补上
    exe, arguments, workdir = runner(program)
    icon = str(shell_icon(icon_file(program)))
    made = []
    link = make_shortcut(Path(folder or root_dir(program)) / (name + '.lnk'), str(exe), arguments,
                         str(workdir), icon, description=f'{APP_NAME} · 三虎陪着您做漫剧')
    if link is not None:
        made.append(link)
    return made


def main():
    icon = install_icon(force=False)            # 图标已是三虎头像生成的成品，不再用算出来的那张覆盖
    if icon is not None:
        print('图标：%s' % icon)
    made = ensure()
    refresh_shell()
    if not made:
        print('快捷方式没建出来：本机 PowerShell 不可用或写不进去')
        return []
    for path in made:
        print('快捷方式：%s' % path)
    return made


if __name__ == '__main__':
    main()
