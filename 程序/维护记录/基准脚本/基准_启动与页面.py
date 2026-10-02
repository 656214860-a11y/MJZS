# -*- coding: utf-8 -*-
"""性能基准（第 58 期附件：先测量，后优化）。离线跑，不碰真安装目录的项目数据。

用法：python bench58.py [start|full]
  start —— 只量「解释器＋导入＋主界面首帧」，给外部计时用（冷启动）
  full  —— 页面／缩略图／长列表／内存
"""
import atexit
import ctypes
import ctypes.wintypes
import io, json, os, shutil, struct, sys, tempfile, time, zlib
from pathlib import Path
from benchmark_history import append_history, measurement_conditions

ARGS = sys.argv[1:]
MODE = ARGS[0] if ARGS and not ARGS[0].startswith('--') else 'full'


def output_path(default):
    """允许自动检查写项目运行报告，默认仍更新人工维护的基准快照。"""
    if '--output' not in ARGS:
        return default
    index = ARGS.index('--output')
    if index + 1 >= len(ARGS):
        raise SystemExit('--output 需要一个 JSON 路径')
    return Path(ARGS[index + 1])
PROG = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROG))
sys.path.insert(0, str(PROG / 'tests'))
os.chdir(str(PROG))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

T0 = time.perf_counter()


def since(t):
    return round((time.perf_counter() - t) * 1000.0, 1)


def rss_mb():
    """当前进程的工作集（MB）——启动器第 34 期注释里量的就是这个口径。"""
    class PMC(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong),
                    ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]
    kernel32 = ctypes.windll.kernel32
    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    kernel32.GetCurrentProcess.restype = ctypes.wintypes.HANDLE
    fn = kernel32.K32GetProcessMemoryInfo
    fn.argtypes = [ctypes.wintypes.HANDLE, ctypes.POINTER(PMC), ctypes.wintypes.DWORD]
    fn.restype = ctypes.wintypes.BOOL
    try:
        if fn(kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
            return round(pmc.WorkingSetSize / 1048576.0, 1)
    except Exception:
        pass
    return -1.0


report = {'mode': MODE, 'start': {}, 'pages': {}, 'thumbs': {}, 'memory': {}, 'list': {}}

t = time.perf_counter()
import tkinter as tk
report['start']['import_tkinter_ms'] = since(t)

t = time.perf_counter()
from desktop import Desktop
report['start']['import_desktop_ms'] = since(t)

t = time.perf_counter()
import asset_thumbs
report['start']['import_asset_thumbs_ms'] = since(t)
report['start']['imports_total_ms'] = since(T0)
report['memory']['after_import_mb'] = rss_mb()

Desktop.choose_project = lambda self: None            # 基准里不弹「选项目」框
win = tk.Tk()
t = time.perf_counter()
d = Desktop(win, root=PROG)
report['start']['desktop_ctor_ms'] = since(t)
t = time.perf_counter()
win.update()
report['start']['first_frame_ms'] = since(t)
report['start']['ready_total_ms'] = since(T0)
report['memory']['after_start_mb'] = rss_mb()

if MODE == 'start':
    out = output_path(Path(__file__).resolve().parent / '基准结果_启动与页面_start.json')
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    append_history(family='startup_page', condition=measurement_conditions(cache_state='cold', first_frame=True),
                   metrics={'first_frame_ms': report['start']['first_frame_ms'],
                            'ready_total_ms': report['start']['ready_total_ms']}, source_result=out.name)
    print(json.dumps(report, ensure_ascii=False))
    win.destroy()
    sys.exit(0)


def png(width, height, phase=0):
    raw = b''.join(b'\x00' + b''.join(bytes(((x * 7 + phase) % 256, (y * 5) % 256, 160))
                                       for x in range(width)) for y in range(height))

    def chunk(tag, data):
        return (struct.pack('>I', len(data)) + tag + data
                + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff))
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
td = Path(tmp.name)
# 这台机器上 TEMP 取不到时，临时目录会落在「程序\」里——中途抛错也要删干净（第 58 期）。
atexit.register(shutil.rmtree, str(td), True)
import test_ui_edges as T
proj = T.make_populated_project(str(td))

d.root = proj
try:
    import local_video
    d.studio = local_video.open_studio(proj)
except Exception as exc:
    report['start']['studio_error'] = str(exc)

rows_cold, rows_warm = [], []
for index in range(11):
    t = time.perf_counter()
    d.show(index)
    win.update()
    rows_cold.append([index, since(t)])
for index in range(11):
    t = time.perf_counter()
    d.show(index)
    win.update()
    rows_warm.append([index, since(t)])
report['pages']['cold_ms'] = rows_cold
report['pages']['warm_ms'] = rows_warm
report['memory']['after_all_pages_mb'] = rss_mb()

big = td / 'big'
big.mkdir(exist_ok=True)
for i in range(12):
    (big / ('img%02d.png' % i)).write_bytes(png(1024, 1024, i))
asset_thumbs.forget()
cold = []
for i in range(12):
    t = time.perf_counter()
    asset_thumbs.thumbnail(win, big / ('img%02d.png' % i))
    cold.append(since(t))
warm = []
for i in range(12):
    t = time.perf_counter()
    asset_thumbs.thumbnail(win, big / ('img%02d.png' % i))
    warm.append(since(t))
report['thumbs']['cold_ms'] = cold
report['thumbs']['cold_avg_ms'] = round(sum(cold) / len(cold), 1)
report['thumbs']['warm_avg_ms'] = round(sum(warm) / len(warm), 1)

bulk = td / 'bulk'
T.make_minimal_project(str(bulk))
base = bulk / 'episode'
(base / 'assets' / 'bulk').mkdir(parents=True, exist_ok=True)
table = {}
for i in range(300):
    name = 'BULK_%03d' % i
    (base / 'assets' / 'bulk' / (name + '.png')).write_bytes(png(96, 96, i))
    table[name] = {'name': '素材 %d' % i, 'image': 'assets/bulk/%s.png' % name}
(base / 'assets.json').write_text(json.dumps(table, ensure_ascii=False), encoding='utf-8')
d.root = bulk
asset_thumbs.forget()
t = time.perf_counter()
d.show(2)
win.update()
report['list']['asset_page_300_ms'] = since(t)
report['list']['scroll_fraction'] = list(d.canvas.yview())
t = time.perf_counter()
for step in range(20):
    d.canvas.yview_moveto(min(0.99, step / 20.0))
    win.update()
report['list']['scroll_20_steps_ms'] = since(t)
report['list']['scroll_fraction_after'] = list(d.canvas.yview())
t = time.perf_counter()
d.show(2)
win.update()
report['list']['asset_page_300_warm_ms'] = since(t)
report['memory']['after_300_assets_mb'] = rss_mb()

out = output_path(Path(__file__).resolve().parent / ('基准结果_启动与页面_%s.json' % MODE))
out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
append_history(family='startup_page', condition=measurement_conditions(cache_state='cold', first_frame=True),
               metrics={'first_frame_ms': report['start']['first_frame_ms'],
                        'ready_total_ms': report['start']['ready_total_ms'],
                        'asset_page_300_ms': report['list']['asset_page_300_ms']}, source_result=out.name)
append_history(family='startup_page', condition=measurement_conditions(cache_state='warm', first_frame=False),
               metrics={'asset_page_300_warm_ms': report['list']['asset_page_300_warm_ms'],
                        'thumbnail_warm_ms': report['thumbs']['warm_avg_ms']}, source_result=out.name)
print(json.dumps(report, ensure_ascii=False, indent=1))
win.destroy()
tmp.cleanup()
