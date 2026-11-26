# -*- coding: utf-8 -*-
"""资产缩略图。界面只加载有界小图，原图交给后台进程按整数步长抽点。"""
import infra.app_logging as app_logging
import atexit
import hashlib
import io
from itertools import islice
import re
import json
import logging
import os
import struct
import subprocess
import sys
import time
from contract.platform_tools import run_process, tool_path
from infra.workflow_process_registry import spawn, forget_process
import tkinter as tk
from pathlib import Path
from infra.file_cache import read_json, remove_temporary_file
from infra import executors, prefetch as _prefetch
from agent.core import save, save_bytes
DEFAULT_SIZE = 36
LIMIT = 1200
_CACHE = {}
PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
GIF_MAGIC = (b'GIF87a', b'GIF89a')
PROGRAM = Path(__file__).resolve().parents[1]
CACHE_ROOT = Path(os.environ.get('TEMP') or os.environ.get('LOCALAPPDATA') or PROGRAM) / 'AI漫剧制作助手' / '缩略图'
CACHE_LIMIT = 4000
POLL_MS = 120
WORKER_IDLE = 90
FALLBACK_SECONDS = 2.0
JOB_DEADLINE = 20.0
QUEUE_LIMIT = 400
RESULTS_PER_TICK = 12

SOURCE_EDGE = 16384
SOURCE_PIXELS = 16 * 1024 * 1024
SOURCE_BYTES = 64 * 1024 * 1024
THUMB_EDGE = 256
THUMB_BYTES = 512 * 1024
MEMORY_BYTES = 24 * 1024 * 1024
DISK_BYTES = 128 * 1024 * 1024
TRIM_INTERVAL = 16
_CACHE_COST = {}
_CACHE_BYTES = 0
_GENERATION = 0
_PENDING = {}
_PUMP = None
_PUMP_ID = None
_PENDING_CURSOR = 0   # 分批轮询 pending 的起点，避免永远只检查队首
_WORKER_START = None  # 仅 Tk 线程调度和清理启动任务
_WORKER = None        # 后台进程句柄
_WORKER_AT = 0.0
_WORKER_BAD = False   # 失败启动进入有限冷却；回收失败保留句柄
_BLIT_BAD = False     # 这一趟会话里「就地贴图」用不了（老 Tk）：照旧先给 None，不摆空盒子
def png_size(data):
    """PNG 的 IHDR：宽、高（都是大端 4 字节）；认不出返回 None。"""
    if len(data) < 24 or not data.startswith(PNG_MAGIC) or data[12:16] != b'IHDR':
        return None
    return struct.unpack('>II', data[16:24])
def gif_size(data):
    """GIF 的逻辑屏幕宽高（小端 2 字节）；认不出返回 None。"""
    if len(data) < 10 or data[:6] not in GIF_MAGIC:
        return None
    return struct.unpack('<HH', data[6:10])

def image_size(path):
    """这张图的（宽，高）；认不出（不是 PNG／GIF、读不到）返回 None。"""
    try:
        with open(str(path), 'rb') as handle:
            return _safe_size(handle.read(32))
    except OSError:
        return None

def _safe_size(head):
    dimensions = png_size(head) or gif_size(head)
    if dimensions:
        width, height = dimensions
        if 0 < min(dimensions) and max(dimensions) <= SOURCE_EDGE and width * height <= SOURCE_PIXELS:
            return dimensions
    return None

def factor(width, height, size=DEFAULT_SIZE):
    """subsample 的整数倍：长边不超过 size，且不放大（至少 1）。"""
    longest = max(int(width or 0), int(height or 0), 1)
    return max(1, -(-longest // max(1, min(THUMB_EDGE, int(size)))))

def build(master, path, size=DEFAULT_SIZE):
    """后台读取首帧，校验头、释放源文件后解码有界快照，再按旧步长取样。"""
    try:
        from PIL import Image
        with Path(path).open('rb') as stream:
            encoded_size = os.fstat(stream.fileno()).st_size
            if encoded_size > SOURCE_BYTES:
                return None
            known = _safe_size(stream.read(32))
            if known is None:
                return None
            stream.seek(0)
            data = stream.read(encoded_size + 1)
        if len(data) != encoded_size:
            return None
        with Image.open(io.BytesIO(data), formats=('PNG', 'GIF')) as source:
            w, h = known
            if source.size != known:
                return None
            step = factor(w, h, size)
            target = (-(-w // step), -(-h // step))
            # NEAREST 以输出像素中心采样；偏移后对应原图 (0, step, 2*step...)。
            offset = (1 - step) / 2
            image = source.convert('RGBA').transform(target, Image.Transform.AFFINE,
                (step, 0, offset, 0, step, offset), Image.Resampling.NEAREST)
            output = io.BytesIO()
            image.save(output, format='PNG')
            return tk.PhotoImage(master=master, data=output.getvalue(), format='png')
    except Exception:
        return None

def _root_key(master):
    """缓存按 Tk 解释器分开：解释器换了一个，手上那张图元就不能再用了。"""
    try:
        return master.tk.interpaddr()
    except Exception:
        return str(master)

def _alive(master):
    """这个 master（Tk 根或控件）还在不在：窗口拆了之后它就一直报 False。"""
    try:
        return bool(master.winfo_exists())
    except Exception:
        return False

def placeholder_size(path, size=DEFAULT_SIZE):
    """这张图缩完之后是多大（宽，高）；文件头读不出来（jpg／webp）返回 None。

    Tk 的 subsample 是「每 N 个点取一个」，所以尺寸是**向上取整**（实测 400 → 67，不是 66）。
    空图元按这个尺寸摆，图到了就地贴进去才严丝合缝——差一个像素就会露出一条边。
    """
    known = image_size(path)
    if not known:
        return None
    step = factor(known[0], known[1], size)
    return max(1, -(-int(known[0]) // step)), max(1, -(-int(known[1]) // step))

# ── 磁盘缓存（Round 1）──────────────────────────────────────────────────
def cache_key(path, stamp, size):
    """这一张图在缓存里的键：路径 ＋ 改动时间 ＋ size 一起算。

    图换了（改动时间变）、或换个尺寸要，键就换一个——旧的那份自然用不上，不必去比时间戳。
    """
    raw = '%s|%s|%s' % (os.path.normcase(str(path)), stamp, int(size))
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()[:20]

def cache_file(token):
    """造好的那张小图落在哪（.png）。"""
    return Path(CACHE_ROOT) / (token + '.png')


def blank_mark(token):
    """「Tk 解不开这一张」的记号落在哪（.none）。"""
    return Path(CACHE_ROOT) / (token + '.none')


def _jobs_dir():
    """等后台进程来接的任务落在哪。"""
    return Path(CACHE_ROOT) / 'jobs'


def info_file(token):
    """媒体封面的旁路记录（时长／分辨率）落在哪——与封面同键不同后缀（任务书 M4）。"""
    return Path(CACHE_ROOT) / (token + '.info.json')


# ── 视频／音频封面（任务书 M4）───────────────────────────────────────────
def media_kind(path):
    """按后缀判媒体类型：视频 'video'、音频 'audio'，其他 None。

    任务书 M4：按后缀不按 ``file_index.kind_of``——后者把图片归入「资产」，
    没有独立图片类型；后缀表只引 ``infra.file_index`` 已有的一份，不重复定义。
    """
    from infra import file_index
    suffix = Path(path).suffix.lower()
    if suffix in file_index.VIDEO_SUFFIXES:
        return 'video'
    if suffix in file_index.AUDIO_SUFFIXES:
        return 'audio'
    return None


def file_stamp(path):
    """媒体缓存键的文件签名：mtime ＋ 大小；文件换过（任一变化）键就换一个。"""
    try:
        stat = Path(path).stat()
    except OSError:
        return None
    return '%d:%d' % (stat.st_mtime_ns, stat.st_size)


def media_geometry(kind, size=DEFAULT_SIZE):
    """媒体封面的固定画幅（宽，高）：视频 16:9、音频波形约 3:1。

    ffmpeg 按同一画幅出图（scale＋pad 补黑边／showwavespic 固定 s=宽x高），
    空盒尺寸与成品严丝合缝，落地时才能就地贴上不露边。
    """
    width = max(1, min(THUMB_EDGE, int(size)))
    if kind == 'audio':
        return width, max(1, width // 3)
    return width, max(1, round(width * 9 / 16))


def media_info(path, size=DEFAULT_SIZE):
    """与封面同键的旁路记录：{'duration', 'width', 'height'}（有什么给什么）；没有返回 None。"""
    stamp = file_stamp(path)
    if stamp is None:
        return None
    try:
        data = read_json(info_file(cache_key(path, stamp, size)))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


_MEDIA_PH = {}            # 占位图：占位本身不随文件走，按（解释器, 类型, 画幅）留一份


def _media_empty(master, key, kind, size):
    """媒体任务排进队列：先摆同画幅的空盒，封面到了就地贴上（同 _placeholder 语义）。"""
    if _BLIT_BAD:
        return None
    width, height = media_geometry(kind, size)
    try:
        image = tk.PhotoImage(master=master, width=width, height=height)
    except Exception:
        return None
    _remember(key, image)
    return image


def _media_placeholder(master, kind, size):
    """ffmpeg 不可用或文件损坏时的占位图：灰底卡片＋播放（视频）／波形（音频）记号。

    占位图按（解释器, 类型, 画幅）缓存，不把每张坏文件各画一遍。
    """
    from ui.asset_thumb_placeholder import draw_media_placeholder
    width, height = media_geometry(kind, size)
    key = ('media-placeholder', _root_key(master), kind, width, height)
    image = _MEDIA_PH.get(key)
    if image is not None:
        try:
            image.width()
            return image
        except Exception:
            _MEDIA_PH.pop(key, None)
    try:
        image = draw_media_placeholder(master, kind, width, height)
    except Exception:
        return None
    if len(_MEDIA_PH) >= 8:
        _MEDIA_PH.pop(next(iter(_MEDIA_PH)))
    _MEDIA_PH[key] = image
    return image


def media_thumbnail(master, path, size=DEFAULT_SIZE, configured=None):
    """视频封面帧／音频波形的缩略图；非媒体文件返回 None。

    与 thumbnail() 同一条机制：内存 → 磁盘缓存 → 后台任务（界面线程绝不做 ffmpeg）。
    ffmpeg 缺失、文件损坏或后台不可用时给固定占位图，不阻断列表（任务书 M4）。
    ``configured`` 是项目级 {'ffmpeg','ffprobe'} 显式配置，透传给后台解析。
    """
    kind = media_kind(path)
    if kind is None:
        return None
    path = Path(path)
    stamp = file_stamp(path)
    if stamp is None:
        return None
    key = (_root_key(master), str(path), stamp, int(size), kind)
    if key in _CACHE:
        image = _CACHE[key]
        try:
            if image is not None:
                image.width()
            _CACHE[key] = _CACHE.pop(key)
            return image
        except Exception:
            _discard(key)
    token = cache_key(path, stamp, size)
    state, image = _load_cached(master, token)
    if state == 'hit':
        _remember(key, image)
        return image
    if state == 'blank':
        image = _media_placeholder(master, kind, size)
        _remember(key, image)
        return image
    queued = request_media(master, key, path, size, stamp, token, configured)
    if queued:
        return _media_empty(master, key, kind, size)     # 交给后台：先摆同画幅空盒
    return _media_placeholder(master, kind, size)         # 队列／后台不可用：直接占位图


def request_media(master, key, path, size, stamp, token, configured=None):
    """登记一条媒体封面任务给后台进程；返回 False 后台不可用、None 队列饱和。"""
    if token in _PENDING:
        return True                    # 已经在队列里，不重复登记
    if len(_PENDING) >= QUEUE_LIMIT:
        return None
    if not _queue_worker_start():
        return False
    kind = media_kind(path)
    cfg = configured or {}
    spec = {'src': str(path), 'size': int(size), 'stamp': stamp, 'kind': kind,
            'ffmpeg': str(cfg.get('ffmpeg') or ''), 'ffprobe': str(cfg.get('ffprobe') or '')}
    try:
        jobs = _jobs_dir()
        jobs.mkdir(parents=True, exist_ok=True)
        save(jobs / (token + '.json'), spec, durable=False)  # 原子落盘：后台进程读不到半截
    except OSError:
        return False
    _PENDING[token] = {'key': key, 'path': Path(path), 'size': int(size), 'stamp': stamp,
                       'kind': kind, 'spec': spec, 'master': master, 'at': time.monotonic()}
    _arm(master)
    return True


def prefetch_media(master, paths, size=DEFAULT_SIZE, configured=None):
    """一批文件里的视频／音频后台预生成封面（面板打开、发布或导入完成时补齐）。

    I22 试点：登记完成后把这批源文件投进 io 池低优先级暖系统页缓存——
    后台 worker／ffmpeg 下次读时命中页缓存。受内存／活跃／关闭开关三闸约束，
    调度不上静默放弃；``master``／Tk 一概不进后台。
    """
    count = 0
    media_paths = []
    for path in paths:
        if len(_PENDING) >= max(0, QUEUE_LIMIT - RESULTS_PER_TICK):
            break
        if media_kind(path) is None:
            continue
        media_thumbnail(master, path, size=size, configured=configured)
        media_paths.append(path)
        count += 1
    if media_paths:
        _prefetch.schedule(lambda: _prefetch.warm_files(media_paths),
                           label='asset_thumbs.prefetch')
    return count


def _blank_fallback(job):
    """「解不开」落地时给什么：媒体给占位图（ffmpeg 不进界面线程），图片照旧 None。"""
    if job.get('kind'):
        return _media_placeholder(job['master'], job['kind'], job['size'])
    return None


def _load_cached(master, token):
    """磁盘缓存里这一张的说法：(状态, 图)。

    状态三选一：'hit' 有图（是张小图，解得极快）、'blank' 是「Tk 解不开」、'miss' 是还没有。
    """
    if blank_mark(token).is_file():
        return 'blank', None
    path = cache_file(token)
    if not path.is_file():
        return 'miss', None
    try:
        with path.open('rb') as stream:
            data = stream.read(THUMB_BYTES + 1)
        shape = png_size(data)
        if len(data) > THUMB_BYTES or not shape or min(shape) < 1 or max(shape) > THUMB_EDGE:
            raise ValueError('invalid thumbnail')
        return 'hit', tk.PhotoImage(master=master, data=data, format='png')
    except Exception:
        if _alive(master):           # 窗口还在才当它是坏缓存；窗口没了只是这张读不了
            try:
                remove_temporary_file(path)
            except OSError:
                pass
        return 'miss', None


def write_cache(image, token):
    """把这张小图（或「解不开」这句记号）写进磁盘缓存；写不成也不当回事。

    先写 .part 再 os.replace——读缓存的那一侧只会读到完整的一份（半截的 PNG 解不开，
    会让那一格白白退回文字）。
    """
    root = Path(CACHE_ROOT)
    try:
        root.mkdir(parents=True, exist_ok=True)
        if image is None:
            save_bytes(blank_mark(token), b'')
            return False
        save_bytes(cache_file(token), image.tk.call(str(image), 'data', '-format', 'png'))
        return True
    except Exception:
        return False


# ── 内存缓存与入口 ──────────────────────────────────────────────────────
def _remember(key, image):
    """收进内存缓存：刚用过的排到最后，最久没看的先挤掉（第 64 期任务 8 的 LRU）。"""
    global _CACHE_BYTES
    cost = image.width() * image.height() * 4 if image is not None else 0
    _discard(key)
    if cost > MEMORY_BYTES:
        return
    while _CACHE and (len(_CACHE) >= LIMIT or _CACHE_BYTES + cost > MEMORY_BYTES):
        _discard(next(iter(_CACHE)))
    _CACHE_COST[key] = cost
    _CACHE_BYTES += cost
    _CACHE[key] = image


def _discard(key):
    global _CACHE_BYTES
    _CACHE.pop(key, None)
    _CACHE_BYTES -= _CACHE_COST.pop(key, 0)


def _blit(target, source):
    """把真图就地贴进已经摆在画面上的那个图元；贴不了返回 False。"""
    for options in (('-compositingrule', 'set'), ()):
        try:
            target.tk.call(str(target), 'copy', str(source), *options)
            return True
        except Exception:
            continue
    return False


def _placeholder(master, key, path, size):
    """先摆一个同尺寸的空图元（图到了就地贴进去）；摆不出来就照旧给 None。"""
    if _BLIT_BAD:
        return None
    known = placeholder_size(path, size)
    if known is None:
        return None
    try:
        image = tk.PhotoImage(master=master, width=known[0], height=known[1])
    except Exception:
        return None
    _remember(key, image)
    return image


def _landed(job, image):
    """图到手了：摆在画面上的那个空盒子就地贴上；没摆过就照旧收进内存缓存。"""
    global _BLIT_BAD
    target = _CACHE.get(job['key'])
    if image is not None and target is not None and target is not image:
        if (target.width(), target.height()) != (image.width(), image.height()):
            _remember(job['key'], image)
            return 'set'
        if _blit(target, image):
            return 'blit'
        _BLIT_BAD = True               # 贴不进去：这一趟会话不再摆空盒子，免得永远空着
    _remember(job['key'], image)
    return 'set'


def thumbnail(master, path, size=DEFAULT_SIZE):
    """给这张图造（或取）一份缩略图；还在后台造，就返回 None（那一格先让原来的字顶着）。

    界面线程上只剩两件轻活：内存里有的直接给；磁盘缓存里有的读一张小图。两处都没有才登记
    一条后台任务——整张解 PNG 那一趟不在这一拍里，页面因此不会被一百来张图堵住。
    """
    path = Path(path)
    try:
        stamp = path.stat().st_mtime_ns
    except OSError:
        return None
    key = (_root_key(master), str(path), stamp, int(size))
    if key in _CACHE:
        image = _CACHE[key]
        try:
            if image is not None:
                image.width()          # 解释器要是已经拆了，这张图就作废
            _CACHE[key] = _CACHE.pop(key)
            return image
        except Exception:
            _discard(key)
    token = cache_key(path, stamp, size)
    state, image = _load_cached(master, token)
    if state == 'hit':
        _remember(key, image)
        return image
    if state == 'blank':
        _remember(key, None)           # 解不开的也记一笔，别每拍都去问一遍磁盘
        return None
    queued = request(master, key, path, size, stamp, token)
    if queued:
        return _placeholder(master, key, path, size)   # 交给后台了：先摆一个同尺寸的空盒子
    if queued is None:
        # 队列饱和时不在界面线程解大图；本轮先显示文字，滚动回来再自然补图。
        return None
    # 后台进程不可用时宁可本拍留文字，也不能在 Tk 回调里解整张图：大图解码会把滚动和
    # 页面切换一起卡住。下一次项目打开或 worker 恢复后会自然补图。
    return None


def request(master, key, path, size, stamp, token):
    """登记一条「造这张小图」的任务交给后台进程；排不出去返回 False。

    返回 False 表示后台进程或任务写入不可用，调用方本轮保留文字；返回 None 表示队列已满，
    同样不在界面线程解图，避免长列表把大图解码挤回界面线程。
    """
    if token in _PENDING:
        return True                    # 已经在队列里，不重复登记
    if len(_PENDING) >= QUEUE_LIMIT:
        return None
    if not _queue_worker_start():
        return False
    spec = {'src': str(path), 'size': int(size), 'stamp': stamp}
    try:
        jobs = _jobs_dir()
        jobs.mkdir(parents=True, exist_ok=True)
        save(jobs / (token + '.json'), spec, durable=False)  # 原子落盘：后台进程读不到半截
    except OSError:
        return False
    _PENDING[token] = {'key': key, 'path': Path(path), 'size': int(size), 'stamp': stamp,
                       'spec': spec, 'master': master, 'at': time.monotonic()}
    _arm(master)
    return True


def _arm(master):
    """挂上（或已经挂着）界面线程那一拍：每 POLL_MS 收一次结果。"""
    global _PUMP, _PUMP_ID
    if _PUMP is not None:
        if _PUMP is master:
            return                     # 这一位已经挂着定时器了，不重复挂
        if _alive(_PUMP):
            return                     # 那一位还活着，它那一拍会把结果一起收走
        _PUMP = None                   # 那一位拆了（自检反复新建 Tk 根）：把位置让出来
        _PUMP_ID = None
    try:
        if not getattr(master, '_asset_thumbs_pump_cleanup_bound', False):
            master.bind('<Destroy>', lambda event, owner=master: _disarm(owner, event), add='+')
            master._asset_thumbs_pump_cleanup_bound = True
        _PUMP = master
        generation = _GENERATION
        _PUMP_ID = master.after(POLL_MS, lambda: update(master) if generation == _GENERATION and _PUMP is master else None)
    except Exception:
        _PUMP = None
        _PUMP_ID = None


def _disarm(master, event=None):
    """窗口销毁时撤掉缩略图轮询，避免 Tcl 调用已删除的 lambda。"""
    global _PUMP, _PUMP_ID
    if event is not None and event.widget is not master:
        return
    if _PUMP is not master:
        return
    global _GENERATION
    _GENERATION += 1
    pump_id = _PUMP_ID
    _PUMP = None
    _PUMP_ID = None
    if pump_id is not None:
        try:
            master.after_cancel(pump_id)
        except Exception:
            # <Destroy> 期间 winfo_exists() 已可能是 false，但 Tcl 解释器通常
            # 仍在，所以上面必须实际尝试取消；走到这里才说明解释器也已拆掉。
            app_logging.swallowed()
    for token, job in list(_PENDING.items()):
        if job['master'] is master:
            _cancel_job(token, job)
    if _PENDING:
        _arm(next(iter(_PENDING.values()))['master'])


def update(master=None):
    """界面线程上的一拍：把后台造好的图收进内存缓存，落地了就贴进画面上那个空盒子。

    界面线程调它只有两个时机：上面那个 after 定时器到点，或自检里 settle() 自己轮着跑。
    返回这一拍收了几张。
    """
    global _PUMP, _PUMP_ID, _PENDING_CURSOR
    master = master or _PUMP
    pump_id = _PUMP_ID
    _PUMP = None
    _PUMP_ID = None
    # settle() 会主动调用 update()；必须顺手取消那一拍尚未触发的 after，
    # 否则根窗口销毁后 Tcl 仍会尝试调用已回收的 lambda。
    if master is not None and pump_id is not None:
        try:
            master.after_cancel(pump_id)
        except Exception:
            app_logging.swallowed()
    if not _PENDING:
        return 0
    gone = (_WORKER_START is None or _WORKER_START.done()) and _worker_gone()
    landed = []
    jobs = list(_PENDING.items())
    start = _PENDING_CURSOR % len(jobs) if jobs else 0
    checked = min(RESULTS_PER_TICK, len(jobs))
    for offset in range(checked):
        token, job = jobs[(start + offset) % len(jobs)]
        if token not in _PENDING:
            continue
        if not _alive(job['master']):
            _cancel_job(token, job)
            continue
        state, image = _load_cached(job['master'], token)
        age = time.monotonic() - job['at']
        if state == 'miss' and (age > JOB_DEADLINE or gone and age > FALLBACK_SECONDS):
            if not job.get('retried'):
                job['retried'] = True
                job['at'] = time.monotonic()
                if job.get('kind'):
                    _landed(job, _media_placeholder(job['master'], job['kind'], job['size']))
                spec_path = _jobs_dir() / (token + '.json')
                try:
                    if not spec_path.exists():
                        save(spec_path, job['spec'], durable=False)
                    if _queue_worker_start():
                        continue
                except OSError:
                    pass
            _cancel_job(token, job)
            continue
        if state == 'miss':
            continue
        _PENDING.pop(token, None)
        _landed(job, image if state == 'hit' else _blank_fallback(job))
        landed.append(token)
    _PENDING_CURSOR = (start + checked) % max(1, len(_PENDING))
    if _PENDING:
        _arm(master)
    return len(landed)


def _worker_gone():
    """后台进程还在不在。刚起来就没了（FALLBACK_SECONDS 之内）就判它这一趟会话不可用。"""
    global _WORKER_BAD
    if _WORKER is None:
        return True
    if _WORKER.poll() is None:
        return False
    if time.monotonic() - _WORKER_AT < FALLBACK_SECONDS:
        _WORKER_BAD = True
    return True


def pending():
    """还在等后台进程的那几条（界面线程与自检都看它）。"""
    return len(_PENDING)


def settle(master, seconds=30.0):
    """等这一批任务落地（自检与冒烟测试用；界面线程不调它）。

    界面线程靠 after 定时器收图，自检里没有 mainloop，所以要自己把 update() 与 master.update()
    轮着跑：一边收结果、一边让到点的那一拍跑起来。返回「全都落地了没有」。
    """
    deadline = time.monotonic() + float(seconds)
    while _PENDING and time.monotonic() < deadline:
        update(master)
        try:
            master.update()
        except Exception:
            break
        time.sleep(0.02)
    return not _PENDING


def _cancel_job(token, job):
    _PENDING.pop(token, None)
    _discard(job['key'])
    remove_temporary_file(_jobs_dir() / (token + '.json'))


def forget():
    """把内存缓存清空（自检换项目、换窗口时用）。"""
    global _PUMP, _PUMP_ID, _PENDING_CURSOR
    global _GENERATION, _CACHE_BYTES
    _GENERATION += 1
    master, pump_id = _PUMP, _PUMP_ID
    _PUMP = None
    _PUMP_ID = None
    if master is not None and pump_id is not None:
        try:
            master.after_cancel(pump_id)
        except Exception:
            app_logging.swallowed()
    for token in _PENDING:
        remove_temporary_file(_jobs_dir() / (token + '.json'))
    _PENDING.clear()
    _CACHE.clear()
    _CACHE_COST.clear()
    _CACHE_BYTES = 0
    _MEDIA_PH.clear()
    _PENDING_CURSOR = 0


def reset_worker(timeout=2.0):
    """收掉后台进程（自检换缓存目录时用）：下一次登记任务会按新目录重起一个。

    terminate 等不到退出就升级到 kill；两者都收不掉时返回 False 并写一条 warning 日志，
    不再像从前那样把 TimeoutExpired 吞掉、让调用方以为进程已经走了。返回 True 表示
    句柄已回收（没有进程，或进程确认退出）。
    """
    global _WORKER, _WORKER_AT, _WORKER_BAD
    global _WORKER_START
    if _WORKER_START is not None:
        if not _WORKER_START.cancel():
            try:
                _WORKER_START.result(timeout=timeout)
            except TimeoutError:
                return False
        _WORKER_START = None
    worker = _WORKER
    # I9a：_WORKER 现在是 SupervisedProcess 包装；等待/终止须落在底层 Popen 上，
    # 否则 wait 超时返回 None 而非抛 TimeoutExpired，kill 升级路径会失效。
    proc = getattr(worker, 'process', worker) if worker is not None else None
    reaped = True
    if proc is not None and callable(getattr(proc, 'wait', None)):
        try:
            proc.terminate()
        except Exception:
            app_logging.swallowed()
        try:
            proc.wait(timeout=timeout)   # 回收掉，别留一个「还在跑」的句柄（自检会报 ResourceWarning）
        except subprocess.TimeoutExpired:
            reaped = False
            try:
                proc.kill()
                proc.wait(timeout=timeout)
                reaped = True
            except subprocess.TimeoutExpired:
                pass
            except Exception:
                app_logging.swallowed()
        except Exception:
            reaped = False
            app_logging.swallowed()
        if not reaped:
            logging.getLogger('asset_thumbs').warning(
                '后台缩略图进程未能在 %.1f 秒内退出：已尝试 terminate/kill，它可能仍占用缓存文件',
                timeout)
    if not reaped:
        _WORKER_BAD = True
        return False
    _WORKER = None
    _WORKER_AT = 0.0
    _WORKER_BAD = False
    if proc is not None:
        try:
            forget_process(PROGRAM, proc)
        except Exception:
            app_logging.swallowed()
    return reaped


def _worker_environment():
    """缩略图 worker 只继承启动 Python 所必需的环境，不带模型/API 凭据。"""
    allowed = ('APPDATA', 'COMSPEC', 'HOMEDRIVE', 'HOMEPATH', 'LOCALAPPDATA',
               'NUMBER_OF_PROCESSORS', 'OS', 'PATH', 'PATHEXT', 'PROCESSOR_ARCHITECTURE',
               'PROCESSOR_IDENTIFIER', 'SYSTEMROOT', 'TEMP', 'TMP', 'USERNAME', 'WINDIR')
    return {name: os.environ[name] for name in allowed if os.environ.get(name)}


# 直接运行单个测试模块时不会经过 Desktop.close() 或 run_selftests 的清理器。
# 进程退出前仍须回收本进程启动的缩略图 worker，避免它成为孤儿进程。
atexit.register(reset_worker)


# ── 后台进程（Round 1）──────────────────────────────────────────────────
def _worker_blocked():
    return _WORKER_BAD and (not _WORKER_AT or time.monotonic() - _WORKER_AT < FALLBACK_SECONDS
                            or (_WORKER is not None and _WORKER.poll() is None))


def _queue_worker_start():
    """将首次启动及进程登记移出 Tk 回调，多张图共享一个启动任务。"""
    global _WORKER_START
    if _WORKER_START is not None and not _WORKER_START.done():
        return True
    if _worker_blocked():
        return False
    if _WORKER is not None and _WORKER.poll() is None:
        return True
    try:
        _WORKER_START = executors.submit('io', _ensure_worker, label='启动缩略图进程')
    except RuntimeError:
        return False
    return True


def _ensure_worker():
    """后台进程在不在：不在（或已经退了）就起一个；失败后冷却再试。"""
    global _WORKER, _WORKER_AT, _WORKER_BAD
    if _worker_blocked():
        return False
    _WORKER_BAD = False
    if _WORKER is not None and _WORKER.poll() is None:
        return True
    try:
        Path(CACHE_ROOT).mkdir(parents=True, exist_ok=True)
        # I9a：经进程监督器拉起——进 Job Object（应用退出即收）、登记进程表；
        # 凭据白名单环境不变，空转 90 秒自退的契约不变（timeout 只约束 wait 缺省）。
        _WORKER = spawn(
            'ffmpeg', [sys.executable, '-m', 'ui.asset_thumbs', '--worker', str(CACHE_ROOT)],
            project=PROGRAM, stage='asset-thumbs', timeout=3600,
            cwd=str(PROGRAM),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=_worker_environment())
        _WORKER_AT = time.monotonic()
        return True
    except Exception:
        _WORKER = None
        _WORKER_BAD = True
        _WORKER_AT = time.monotonic()
        return False


def _trim_cache():
    """只回收本模块生成的缓存文件，按时间淘汰至两个预算以内。"""
    files = []
    for path in Path(CACHE_ROOT).glob('*'):
        if not re.fullmatch(r'[0-9a-f]{20}\.(png|none|info\.json)', path.name):
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        files.append((stat.st_mtime_ns, path, stat.st_size))
    total = sum(item[2] for item in files)
    count = len(files)
    if count <= CACHE_LIMIT and total <= DISK_BYTES:
        return
    for _, path, size in sorted(files):
        if count <= CACHE_LIMIT and total <= DISK_BYTES:
            break
        if remove_temporary_file(path):
            total -= size
            count -= 1


def worker_main(cache_root, idle=WORKER_IDLE):
    """后台进程：自己一个 Tk 解释器，把 jobs/ 里的任务解成缓存里的小图。

    抽点倍数与界面线程那一套是同一个 factor()，所以缓存里的像素和从前同步解出来的完全一样。
    空转 idle 秒自己退——软件关掉之后不留常驻进程。
    """
    global CACHE_ROOT
    CACHE_ROOT = Path(cache_root)
    jobs = _jobs_dir()
    try:
        jobs.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    _trim_cache()
    try:
        root = tk.Tk()            # 解图只要一个解释器，不要窗口
        root.withdraw()
    except Exception:
        return                    # 没有桌面会话：不接活，界面保留占位
    processed = 0
    quiet = time.monotonic()
    while True:
        todo = list(islice(jobs.glob('*.json'), QUEUE_LIMIT))
        if not todo:
            if processed:
                _trim_cache()
                processed = 0
            if time.monotonic() - quiet > idle:
                return
            time.sleep(0.05)
            continue
        quiet = time.monotonic()
        for spec_file in todo:
            try:
                spec = read_json(spec_file)
                src = Path(spec['src'])
                token = cache_key(src, spec['stamp'], spec['size'])
                if spec.get('kind') in ('video', 'audio'):
                    _media_job(src, int(spec['size']), token, spec['kind'], spec)
                else:
                    write_cache(build(root, src, int(spec['size'])), token)
            except Exception:
                app_logging.swallowed()                    # 单张图出事不许把这一批带停
            processed += 1
            if processed == TRIM_INTERVAL:
                _trim_cache()
                processed = 0
            try:
                remove_temporary_file(spec_file)
            except OSError:
                pass


def _media_job(src, size, token, kind, spec):
    """后台媒体封面：ffprobe 记旁路（时长／分辨率），ffmpeg 出固定画幅 PNG。

    ffmpeg／ffprobe 一律经 M1 统一后的 ``tool_path`` 解析（任务书 M4）；两者都拿不到、
    或文件损坏出不了图时落 ``.none`` 记号，界面那一侧给占位图，不反复重试。
    单进程顺序执行＝同一时刻只跑一个 ffmpeg，天然满足并发生成上限。
    """
    ffmpeg = tool_path('ffmpeg', configured=spec.get('ffmpeg') or '')
    ffprobe = tool_path('ffprobe', configured=spec.get('ffprobe') or '')
    info = _probe_media(ffprobe, src) if ffprobe else {}
    if info:
        try:
            save(info_file(token), info)
        except Exception:
            app_logging.swallowed()
    image = _render_media(ffmpeg, src, kind, *media_geometry(kind, size), info) if ffmpeg else None
    try:
        if image is None or len(image) > THUMB_BYTES:
            save_bytes(blank_mark(token), b'')
        else:
            save_bytes(cache_file(token), image)
    except Exception:
        app_logging.swallowed()


def _probe_media(ffprobe, src):
    """ffprobe 取时长与分辨率；探不出来返回 {}（不挡封面生成）。"""
    try:
        result = run_process(
            [ffprobe, '-v', 'error', '-show_entries',
             'stream=width,height:format=duration', '-of', 'json', str(src)],
            capture_output=True, timeout=15)
    except Exception:
        return {}
    if result.returncode != 0:
        return {}
    try:
        data = json.loads(result.stdout.decode('utf-8', 'replace'))
    except (AttributeError, ValueError):
        return {}
    info = {}
    for stream in data.get('streams') or ():
        if stream.get('width'):
            info['width'] = int(stream['width'])
            info['height'] = int(stream['height'])
            break
    try:
        duration = float((data.get('format') or {}).get('duration'))
        if duration > 0:
            info['duration'] = round(duration, 3)
    except (TypeError, ValueError):
        pass
    return info


def _cover_seek(info):
    """抽帧时间点：时长的 5%（上限 3 秒）；探测不到时长从 0 抽。"""
    try:
        duration = float((info or {}).get('duration') or 0)
    except (TypeError, ValueError):
        duration = 0
    return '%.3f' % max(0.0, min(duration * 0.05, 3.0))


def _render_media(ffmpeg, src, kind, width, height, info):
    """ffmpeg 出一张固定画幅 PNG（stdout 管道）：视频抽帧补黑边、音频画波形；失败 None。"""
    if kind == 'audio':
        args = [ffmpeg, '-nostdin', '-v', 'error', '-i', str(src),
                '-filter_complex', 'showwavespic=s=%dx%d:split_channels=0' % (width, height),
                '-frames:v', '1', '-f', 'image2pipe', '-c:v', 'png', '-']
    else:
        args = [ffmpeg, '-nostdin', '-v', 'error', '-ss', _cover_seek(info), '-i', str(src),
                '-frames:v', '1',
                '-vf', 'scale=%d:%d:force_original_aspect_ratio=decrease,'
                       'pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=black' % (width, height, width, height),
                '-f', 'image2pipe', '-c:v', 'png', '-']
    try:
        result = run_process(args, capture_output=True, timeout=30)
    except Exception:
        return None
    if result.returncode != 0 or not result.stdout.startswith(PNG_MAGIC):
        return None
    return result.stdout


def main(argv=None):
    """`python asset_thumbs.py --worker <缓存目录>`：只做后台解码那一件事。"""
    args = list(sys.argv[1:] if argv is None else argv)
    if '--worker' in args:
        rest = args[args.index('--worker') + 1:]
        worker_main(rest[0] if rest else CACHE_ROOT)
        return 0
    print('asset_thumbs：模块本体给界面线程用；后台解码进程由 --worker <缓存目录> 启动。')
    return 1


if __name__ == '__main__':
    sys.exit(main())
