# -*- coding: utf-8 -*-
"""资产图片的缩略图（第 52 期第 3 条）：一个第三方库都不引，Tk 自己就认 PNG／GIF。

Tk 8.6 的 PhotoImage 能从文件读 PNG／GIF，缩放只有整数倍的 subsample（抽点）。所以先读文件头
拿原图尺寸，再挑一个「长边不超过 size」的最大整数倍：原图越大抽得越狠，缩略图不会放大、也不会
超过 size，最小是 size 的一半。读不出尺寸（jpg／webp 这些 Tk 不认的）、文件不在、Tk 解不开，
一律返回 None——界面上退回原来的文字，不抛。

同一张图（哪个 Tk 解释器 ＋ 路径 ＋ 改动时间 ＋ size）只造一次：PhotoImage 一被回收，画面上就
只剩空框（第 30 期踩过这个坑），所以图元一直留在缓存里；缓存按解释器分开，自检里反复新建 Tk 根
也不会串。

第 64 期任务 8：淘汰规则从「先进先出」改成「最久没看的先走」（LRU），容量 240 → 1200。
先进先出挤掉的是**最早**造的那几张——恰恰是天天在看的资产图；图一多（长项目、一页几十行）
每次翻回来都得整张重新解码，用户看到的就是「资产管理打开缓慢」。

Round 1（2026-09-23）：缩略图不再在界面线程里整张解 PNG（95 张实测 26.3 秒），改成两层：

· 磁盘缓存（本机临时目录下的 `AI漫剧制作助手/缩略图/<键>.png`）：抽好点的小图按「路径 ＋ 改动时间 ＋ size」存一份，
  像素与从前同步解出来的一字不差（同一个整数倍抽点）。第二次打开读的就是这份小图——Tk 解一张
  长边几十像素的图是零点几毫秒的事，用户看到的就是「二次打开秒显」。Tk 不认的（jpg／webp）
  落一份 `<键>.none` 记号，省得每翻一次重试一次。
· 后台进程：没缓存过的图，界面线程只登记一条任务（`private/缩略图/jobs/<键>.json`），返回的是
  **一个同尺寸的空图元**（尺寸从文件头算得，与缩出来的图严丝合缝），页面上照旧当「有图」对待、
  照旧写它该写的字。由 `python asset_thumbs.py --worker <缓存目录>` 那个进程去解、去写缓存；
  这一批落地之后由 update()（挂在界面线程的定时器上）把真图**就地贴进**那个空图元
  （`image copy`）——Tk 自己会把用到这个图元的地方重画一遍，缩略图就这么长出来，不必用户先滚
  一下，页面一行也不用改（正典板那种「有图才写文件名」的地方也不会先显示一句「缺图」）。

后台进程起不来、或者起了一半就没了（换台机器、没有桌面会话），同一批任务就地退回老路：
界面线程同步解一次并把结果写进缓存——最坏也不过是和从前一样慢，图不会不见。JOB_DEADLINE
兜住「进程还活着、这一张却一直不回来」那种情况。
"""
import app_logging
import atexit
import hashlib
import os
import struct
import subprocess
import sys
import time
from platform_tools import launch_background
import tkinter as tk
from pathlib import Path
from file_cache import read_json, remove_temporary_file
from agent.core import save, save_bytes

DEFAULT_SIZE = 36
LIMIT = 1200          # 第 64 期任务 8：一项约 20 KB，满打满算约 24 MB
_CACHE = {}
PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
GIF_MAGIC = (b'GIF87a', b'GIF89a')

PROGRAM = Path(__file__).resolve().parent
# 安装目录在交付版中可能是只读的；缓存与任务队列必须落在当前用户可写的位置，
# 否则 request() 会失败并把每张大图退回界面线程同步解码。
CACHE_ROOT = Path(os.environ.get('TEMP') or os.environ.get('LOCALAPPDATA') or PROGRAM) / 'AI漫剧制作助手' / '缩略图'
CACHE_LIMIT = 4000    # 缓存上限（张）：超过就先丢最久没动过的那一半
POLL_MS = 120         # 界面线程每 120 毫秒收一次结果
WORKER_IDLE = 90      # 后台进程空转 90 秒自己退（关掉软件之后不留常驻进程）
FALLBACK_SECONDS = 2.0   # 「刚起来就死」的判据：这么短就没了的，当它这一趟不可用
JOB_DEADLINE = 20.0      # 一条任务等这么久还不回来，就地同步解（进程卡住也不至于不出图）
QUEUE_LIMIT = 400         # 大项目滚动列表时，后台任务不能无限堆积占满磁盘与内存
RESULTS_PER_TICK = 12     # 分批收结果，不能一拍扫／贴完整个长列表队列，留出 Tk 绘制时间

_PENDING = {}         # 键 → 一条等 update() 来收的任务
_PUMP = None          # 界面线程上那个定时器挂在哪个 master 上
_PUMP_ID = None       # 上面那一拍的 after 标识；销毁窗口前必须取消
_PENDING_CURSOR = 0   # 分批轮询 pending 的起点，避免永远只检查队首
_WORKER = None        # 后台进程句柄
_WORKER_AT = 0.0
_WORKER_BAD = False   # 这一趟会话里它已经不可用了，不必再起
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
            head = handle.read(32)
    except OSError:
        return None
    return png_size(head) or gif_size(head)


def factor(width, height, size=DEFAULT_SIZE):
    """subsample 的整数倍：长边不超过 size，且不放大（至少 1）。"""
    longest = max(int(width or 0), int(height or 0), 1)
    return max(1, -(-longest // max(1, int(size))))


def build(master, path, size=DEFAULT_SIZE):
    """在调用方这一侧把这张图解成缩略图；解不出来返回 None。

    界面线程只在「没有后台进程可用」时才走这一条（上面那三种兜底），平时都是那个进程在解。
    """
    known = image_size(path)
    try:
        source = tk.PhotoImage(master=master, data=Path(path).read_bytes())
        step = factor(known[0], known[1], size) if known else 1
        return source.subsample(step, step) if step > 1 else source
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
        return 'hit', tk.PhotoImage(master=master, data=path.read_bytes())
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
    while len(_CACHE) >= LIMIT and _CACHE:
        _CACHE.pop(next(iter(_CACHE)), None)
    _CACHE[key] = image


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
            _CACHE.pop(key, None)
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
    if not _ensure_worker():
        return False
    spec = {'src': str(path), 'size': int(size), 'stamp': stamp}
    try:
        jobs = _jobs_dir()
        jobs.mkdir(parents=True, exist_ok=True)
        save(jobs / (token + '.json'), spec)  # 原子落盘：后台进程读不到半截
    except OSError:
        return False
    _PENDING[token] = {'key': key, 'path': Path(path), 'size': int(size), 'stamp': stamp,
                       'master': master, 'at': time.monotonic()}
    _arm(master)
    return True


def _build_here(master, path, size, stamp, token):
    """没有后台进程可用的那条老路：界面线程解一次，顺手把结果写进磁盘缓存。"""
    image = build(master, Path(path), size)
    write_cache(image, token)
    return image


# ── 界面线程那一拍：收结果、通知页面 ─────────────────────────────────────
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
        _PUMP_ID = master.after(POLL_MS, lambda: update(master))
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
    landed = []
    jobs = list(_PENDING.items())
    start = _PENDING_CURSOR % len(jobs) if jobs else 0
    checked = min(RESULTS_PER_TICK, len(jobs))
    for offset in range(checked):
        token, job = jobs[(start + offset) % len(jobs)]
        if token not in _PENDING:
            continue
        if not _alive(job['master']):
            _PENDING.pop(token, None)  # 那一页拆了：这条不必再收，也不去动磁盘缓存
            continue
        state, image = _load_cached(job['master'], token)
        if state == 'miss' and time.monotonic() - job['at'] > JOB_DEADLINE:
            image = _build_here(job['master'], job['path'], job['size'], job['stamp'], token)
            state = 'hit' if image is not None else 'blank'
        if state == 'miss':
            continue
        _PENDING.pop(token, None)
        _landed(job, image if state == 'hit' else None)
        landed.append(token)
    _PENDING_CURSOR = (start + checked) % max(1, len(_PENDING))
    if _PENDING and _worker_gone():
        # worker 不可用时也分批回退，不能把数百张图的同步解码塞进一次 UI tick。
        for token, job in list(_PENDING.items())[:RESULTS_PER_TICK]:
            image = _build_here(job['master'], job['path'], job['size'], job['stamp'], token)
            _PENDING.pop(token, None)
            _landed(job, image)
            landed.append(token)
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


def worker_bad():
    """这一趟会话里后台进程是不是已经判了不可用（判了就一直走同步那条老路）。"""
    return _WORKER_BAD


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


def forget():
    """把内存缓存清空（自检换项目、换窗口时用）。"""
    global _PUMP, _PUMP_ID, _PENDING_CURSOR
    master, pump_id = _PUMP, _PUMP_ID
    _PUMP = None
    _PUMP_ID = None
    if master is not None and pump_id is not None:
        try:
            master.after_cancel(pump_id)
        except Exception:
            app_logging.swallowed()
    _CACHE.clear()
    _PENDING.clear()
    _PENDING_CURSOR = 0


def reset_worker():
    """收掉后台进程（自检换缓存目录时用）：下一次登记任务会按新目录重起一个。"""
    global _WORKER, _WORKER_AT, _WORKER_BAD
    if _WORKER is not None:
        try:
            _WORKER.terminate()
            _WORKER.wait(timeout=2)      # 回收掉，别留一个「还在跑」的句柄（自检会报 ResourceWarning）
        except Exception:
            app_logging.swallowed()
    _WORKER = None
    _WORKER_AT = 0.0
    _WORKER_BAD = False


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
def _ensure_worker():
    """后台进程在不在：不在（或已经退了）就起一个；这一趟会话里它坏过一次就不再起。"""
    global _WORKER, _WORKER_AT, _WORKER_BAD
    if _WORKER_BAD:
        return False
    if _WORKER is not None and _WORKER.poll() is None:
        return True
    try:
        Path(CACHE_ROOT).mkdir(parents=True, exist_ok=True)
        _WORKER = launch_background(
            [sys.executable, str(Path(__file__).resolve()), '--worker', str(CACHE_ROOT)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=_worker_environment(), popen=subprocess.Popen)
        _WORKER_AT = time.monotonic()
        return True
    except Exception:
        _WORKER = None
        _WORKER_BAD = True
        return False


def _trim_cache():
    """缓存太多了就先丢最久没动过的那一半（只在后台进程刚起来时做一次）。"""
    root = Path(CACHE_ROOT)
    try:
        files = sorted((item for item in root.glob('*') if item.is_file()),
                       key=lambda item: item.stat().st_mtime)
    except OSError:
        return
    for old in files[:max(0, len(files) - CACHE_LIMIT // 2)]:
        try:
            remove_temporary_file(old)
        except OSError:
            pass


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
        return                    # 没有桌面会话：不接活，界面线程那一侧会就地退回同步解
    quiet = time.monotonic()
    while True:
        todo = sorted(jobs.glob('*.json'))
        if not todo:
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
                write_cache(build(root, src, int(spec['size'])), token)
            except Exception:
                app_logging.swallowed()                    # 单张图出事不许把这一批带停
            try:
                remove_temporary_file(spec_file)
            except OSError:
                pass


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
