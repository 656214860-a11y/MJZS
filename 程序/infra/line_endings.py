# -*- coding: utf-8 -*-
"""写入即校验行尾（第 7 轮）：程序文件按各自的换行符回写，CR CR LF 落不下去。

第 62 期那次「启动失败，详情已保存到 启动错误.log」：`pet_ui.py` 被写文件脚本写成了
「CR CR LF」，CPython 读到只剩一个空行的那一行，抛 `SyntaxError: expected ':'`；自检的
Tk 保护又会把 `\r\n` 归一，所以只有双击 `.pyw` 才炸。根子只有一条——

    读的时候把 `\r` 留下来了，写的时候文本模式又翻译一次：`\r\n` → `\r\r\n`。

所以写入只留这一条路 `write_text`：正文里一切行尾先归成 LF，再按**目标文件自己的**换行符
铺回去，用 `newline=''` 原样写（不做任何翻译）；写完当场按字节复核「和算好的一模一样」，
核对通过才原子换到正式路径（`agent.core.replace` 会在 Windows 上被读着时退避重试）。
核对不过就抛 `ValueError`，正式文件一个字节都不动。

自检（`test_line_endings.py`）拿 `inspect` / `problems` / `audit` 把程序目录整棵扫一遍：
**不许有落单的 CR，更不许有 CR CR LF**。
"""
import io
import os
from pathlib import Path
from infra.file_cache import remove_temporary_file

from agent.core import replace, temporary_path

LF = '\n'
CRLF = '\r\n'
EOLS = (LF, CRLF)
# 只有这些后缀当文本看：图片、视频、DPAPI 密文这些按字节原样，不惹它们。
TEXT_SUFFIXES = ('.py', '.pyw', '.md', '.json', '.jsonl', '.txt', '.toml', '.cmd', '.ps1',
                 '.yml', '.yaml', '.js', '.html', '.svg', '.lock', '.env', '.gitignore', 'license')


def inspect(raw):
    """一段字节的行尾情报：crlf／纯 LF／落单的 CR／重复的 CR，以及「干净吗、是混着的吗」。

    判据就两条：**落单的 CR**（没有跟着 LF 的那个）与**重复的 CR**（`\r\r`）。CR CR LF
    会同时踩中这两条——它既是重复的 CR，去掉一处 CRLF 之后又剩一个落单的 CR。
    """
    data = raw if isinstance(raw, (bytes, bytearray)) else str(raw).encode('utf-8')
    crlf = data.count(b'\r\n')
    double_cr = data.count(b'\r\r')
    rest = data.replace(b'\r\n', b'')
    lone_cr = rest.count(b'\r')
    plain_lf = rest.count(b'\n')
    return {'eol': CRLF if crlf else LF, 'crlf': crlf, 'lf': plain_lf,
            'lone_cr': lone_cr, 'double_cr': double_cr,
            'clean': not (lone_cr or double_cr),
            'mixed': bool(crlf and plain_lf)}


def detect_eol(raw):
    """这个文件自己用的是哪种换行符：有 CRLF 就算 CRLF（坏成 CR CR LF 的文件也认回 CRLF）。"""
    return inspect(raw)['eol']


def read_text(path):
    """读正文（行尾一律归成 LF）＋ 这个文件自己的换行符；读不动照常往上抛。"""
    path = Path(path)
    raw = path.read_bytes()
    return normalize(raw.decode('utf-8')), detect_eol(raw)


def normalize(text):
    """正文里一切行尾归成 LF。

    `\r\r\n` 先按**一个**换行收掉：它是第 62 期那种事故的签名（本来一个换行被写了两遍），
    不收掉的话，拿一份坏文件修一次反而凭空多出一倍空行。落单的 `\r` 也算行尾。
    """
    return str(text).replace('\r\r\n', '\n').replace('\r\n', '\n').replace('\r', '\n')


def compose(text, eol):
    """按指定的换行符把正文铺出来；eol 只认 LF／CRLF，其余一律拦下。"""
    if eol not in EOLS:
        raise ValueError('换行符只认 LF 或 CRLF，收到的是 %r' % (eol,))
    return normalize(text).replace('\n', eol)


def write_text(path, text, eol=None):
    """写入并当场校验行尾，返回实际用的换行符。

    eol 不给就用目标文件自己的（新文件按 Windows 文本惯例给 CRLF）。两道闸：铺好的正文里
    不许有落单／重复的 CR；写进临时文件后按字节复核，和算好的一模一样才原子换到正式路径，
    对不上就抛 `ValueError` 并删掉临时文件——正式文件一个字节都不动。
    """
    path = Path(path)
    if eol is None:
        eol = detect_eol(path.read_bytes()) if path.is_file() else CRLF
    body = compose(text, eol)
    if not inspect(body)['clean']:
        raise ValueError('正文里有落单或重复的 CR，已拦下不写：%s' % path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # 不能复用固定 ``.tmp``：并行保存两个字幕或配置时会互相覆盖、
    # 甚至把对方的临时文件当作自己的清理掉。
    temp = temporary_path(path)
    try:
        with io.open(temp, 'w', encoding='utf-8', newline='') as sink:   # newline=''：一个字节都不翻译
            sink.write(body)
            sink.flush()
            os.fsync(sink.fileno())   # 先落盘再换名，断电后不会换出一个空文件
        want = body.encode('utf-8')
        if temp.read_bytes() != want:
            raise ValueError('写入校验没过（字节对不上），已拦下不落盘：%s' % path)
        replace(temp, path)
    finally:
        # 任何一步失败（写入、校验、换名）都清掉本轮临时文件；成功后它已不存在。
        if temp.exists():
            try:
                remove_temporary_file(temp)
            except OSError:
                pass
    return eol


def problems(path):
    """这个文件的行尾毛病（空列表＝干净）：落单／重复的 CR、不是 UTF-8、读不动。"""
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return ['读不动：%s' % exc]
    info = inspect(raw)
    found = []
    if info['double_cr']:
        found.append('重复的 CR（CR CR LF）%d 处' % info['double_cr'])
    if info['lone_cr']:
        found.append('落单的 CR %d 处' % info['lone_cr'])
    try:
        raw.decode('utf-8')
    except UnicodeDecodeError:
        found.append('不是 UTF-8')
    return found


def audit(folder, suffixes=TEXT_SUFFIXES, skip=('__pycache__',)):
    """扫一棵树：{相对路径: inspect 的情报}；只收文本后缀、只跳过 skip 里的目录。"""
    folder = Path(folder)
    found = {}
    for root, dirs, files in os.walk(folder):
        dirs[:] = [name for name in dirs if name not in skip]
        for name in files:
            if not str(name).lower().endswith(tuple(suffixes)):
                continue
            path = Path(root) / name
            try:
                raw = path.read_bytes()
            except OSError:
                continue
            found[os.path.relpath(path, folder).replace(os.sep, '/')] = inspect(raw)
    return found
