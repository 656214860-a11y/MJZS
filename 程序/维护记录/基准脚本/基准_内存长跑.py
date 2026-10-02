# -*- coding: utf-8 -*-
"""内存长跑（第 72 期，Round 3）：不停地把 11 页来回开，看工作集会不会一直涨。

维护记录里那条内存口径原来只量了约 20 秒的短程（裸解释器 26.7 → 首帧 51.0 → 11 页全开
59.0 → 300 项资产页 61.4 MB），「长跑会不会漏」一直空着。这个脚本把它补上：同一个进程里
反复开页（每轮 11 页 ＋ 300 项资产页），每分钟记一笔工作集／页面文件／控件数／缩略图缓存，
跑完给出「前段均值 vs 后段均值 ＋ 斜率」的结论。

用法：
    python 基准_内存长跑.py                    # 30 分钟，每分钟一笔
    python 基准_内存长跑.py 5 --sample 30       # 先快速试一把
每采一笔就往 基准结果_内存长跑_<分钟>min.json 落一次盘：跑到一半被打断也不丢数据。
关窗那两条路（close／finish_close）在长跑里被挡住、只记一笔调用栈——三十分钟的数据不该
因为有人顺手点了那扇窗的 X 就白跑。采样除工作集外还记 Tk 图元数与句柄数：这两个只涨不落才是真泄漏。
"""
import atexit
import ctypes
import ctypes.wintypes
import io
import json
import os
import shutil
import struct
import sys
import tempfile
import time
import traceback
import zlib
from pathlib import Path
from benchmark_history import append_history, measurement_conditions

PROG = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROG))
sys.path.insert(0, str(PROG / 'tests'))
os.chdir(str(PROG))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

MINUTES = float(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith('-') else 30.0
SAMPLE = 60.0
ASSETS = 300
for flag, setter in (('--sample', 'sample'), ('--assets', 'assets')):
    if flag in sys.argv:
        value = float(sys.argv[sys.argv.index(flag) + 1])
        if setter == 'sample':
            SAMPLE = value
        else:
            ASSETS = int(value)


def usage_mb():
    """工作集与页面文件用量（MB）：与维护记录里那条内存口径同一套接口。"""

    class PMC(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong),
                    ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]

    import ctypes.wintypes as wt
    kernel32 = ctypes.windll.kernel32
    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    kernel32.GetCurrentProcess.restype = wt.HANDLE
    fn = kernel32.K32GetProcessMemoryInfo
    fn.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]
    fn.restype = wt.BOOL
    if fn(kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
        return round(pmc.WorkingSetSize / 1048576.0, 1), round(pmc.PagefileUsage / 1048576.0, 1)
    return -1.0, -1.0


def png(width, height, phase=0):
    raw = b''.join(b'\x00' + b''.join(bytes(((x * 7 + phase) % 256, (y * 5) % 256, 160))
                                       for x in range(width)) for y in range(height))

    def chunk(tag, data):
        return (struct.pack('>I', len(data)) + tag + data
                + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff))

    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def count_widgets(widget):
    """把一棵控件树数一遍：数字一直涨就说明页面没拆干净。"""
    total = 1
    try:
        for child in widget.winfo_children():
            total += count_widgets(child)
    except Exception:
        pass
    return total


def big_project(td, count):
    """有数据、且资产页真有很多行的项目：11 页都走「有内容」那条路。"""
    import test_ui_edges as T
    proj = T.make_populated_project(str(td))
    base = proj / 'episode'
    episode_file = base / 'episode.json'
    from project_stages import storyboard as storyboard_stage
    source_file = storyboard_stage(proj) / '分镜文档' / 'episode.json'
    source_file.parent.mkdir(parents=True, exist_ok=True)
    episode = json.loads(episode_file.read_text(encoding='utf-8'))
    shots = episode.setdefault('shots', [])
    per = max(1, count // 3)
    folders = (('characters', 'CHAR_'), ('scenes', 'LOC_'), ('props', 'PROP_'))
    registry = json.loads((base / 'assets.json').read_text(encoding='utf-8'))
    for index in range(1, per + 1):
        ids = {}
        for folder, prefix in folders:
            aid = '%s%03d' % (prefix, index)
            ids[folder] = aid
            target = base / 'assets' / folder
            target.mkdir(parents=True, exist_ok=True)
            (target / (aid + '.png')).write_bytes(png(256, 256, index))
            registry[aid] = {'name': aid, 'image': 'assets/%s/%s.png' % (folder, aid)}
        shots.append({'id': 'SH%03d' % (1000 + index), 'title': '镜头 %d' % index, 'duration': 5,
                      'characters': [ids['characters']], 'location': ids['scenes'],
                      'props': [ids['props']], 'frame': 'frames/SH%03d.png' % (1000 + index),
                      'video_prompt': '画面', 'frame_prompt': '窗边的猫', 'dialogue': []})
    (base / 'assets.json').write_text(json.dumps(registry, ensure_ascii=False), encoding='utf-8')
    for target in (episode_file, source_file):
        target.write_text(json.dumps(episode, ensure_ascii=False), encoding='utf-8')
    T.keep_storyboard_fresh(proj)
    return proj


import tkinter as tk
import asset_thumbs
from desktop import Desktop
import local_video

desktop_choose = Desktop.choose_project
Desktop.choose_project = lambda self: None      # 长跑里不弹「选项目」框

tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
atexit.register(shutil.rmtree, tmp.name, True)
proj = big_project(tmp.name, ASSETS)
print('项目就绪：%s（资产 %d 项）' % (proj, ASSETS), flush=True)

win = tk.Tk()
win.geometry('1180x760+40+40')
d = Desktop(win, root=PROG)
d.root = proj
try:
    d.studio = local_video.open_studio(proj)
except Exception as exc:
    print('studio 打不开（不影响内存观察）：%s' % exc, flush=True)
d.asset_kind = 'all'


import tkinter as tk
import asset_thumbs
from desktop import Desktop
import local_video

desktop_choose = Desktop.choose_project
Desktop.choose_project = lambda self: None      # 长跑里不弹「选项目」框

# 长跑里绝不允许窗口被关掉：三十分钟的数据不该因为有人顺手点了那扇窗的 X 就白跑。
# 关窗的动作记一笔（连着调用栈），然后当没发生。必须在 Desktop(win) 之前换掉：
# WM_DELETE_WINDOW 绑的是构造那一刻的那个函数对象，晚一步就换不动了。
close_attempts = []
_desktop_close = Desktop.close
_desktop_finish_close = Desktop.finish_close


def _note_close(what):
    close_attempts.append({'what': what, 'at': time.time(),
                           'from': [line.strip() for line in traceback.format_stack()[-6:-1]]})


def guarded_close(self, *args, **kwargs):
    _note_close('close')
    print('  有人想 close() 收摊，长跑里挡住了（已记进结果）。', flush=True)
    return None


def guarded_finish_close(self):
    _note_close('finish_close')
    print('  有人想 finish_close() 收摊，长跑里挡住了（已记进结果）。', flush=True)
    return None


Desktop.close = guarded_close
Desktop.finish_close = guarded_finish_close

tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
atexit.register(shutil.rmtree, tmp.name, True)
proj = big_project(tmp.name, ASSETS)
print('项目就绪：%s（资产 %d 项）' % (proj, ASSETS), flush=True)

win = tk.Tk()
win.geometry('1180x760+40+40')
d = Desktop(win, root=PROG)
d.root = proj
try:
    d.studio = local_video.open_studio(proj)
except Exception as exc:
    print('studio 打不开（不影响内存观察）：%s' % exc, flush=True)
d.asset_kind = 'all'


def tk_image_count():
    """Tk 图元数（PhotoImage 等）：只涨不落才是真泄漏，与工作集对得上才算数。"""
    try:
        return len(win.tk.call('image', 'names'))
    except Exception:
        return -1


def handle_count():
    """本进程句柄数：句柄只涨不落，多半是哪里没关（图元／文件／事件）。"""
    try:
        kernel32 = ctypes.windll.kernel32
        count = ctypes.c_ulong(0)
        if kernel32.GetProcessHandleCount(kernel32.GetCurrentProcess(), ctypes.byref(count)):
            return int(count.value)
    except Exception:
        pass
    return -1


def window_alive():
    try:
        return bool(win.winfo_exists())
    except Exception:
        return False


samples = []
started = time.time()
last_sample = 0.0
rounds = 0
fatal = None
print('开跑：%.0f 分钟 / 每 %.0f 秒记一笔' % (MINUTES, SAMPLE), flush=True)
print('  分钟   工作集MB  页面文件MB  控件数  Tk图元  句柄  缩略图内存  待办', flush=True)


def average(rows, field):
    return round(sum(row[field] for row in rows) / len(rows), 1) if rows else None


def slope_mb_per_min(rows):
    """最小二乘斜率：这一段里每分钟涨多少 MB。"""
    if len(rows) < 2:
        return 0.0
    mean_x = sum(row['minute'] for row in rows) / len(rows)
    mean_y = sum(row['rss_mb'] for row in rows) / len(rows)
    denom = sum((row['minute'] - mean_x) ** 2 for row in rows)
    if denom <= 0:
        return 0.0
    return sum((row['minute'] - mean_x) * (row['rss_mb'] - mean_y) for row in rows) / denom


def build_report():
    """按「热身 → 中段 → 收尾」出结论；跑到一半被打断也照出。"""
    minutes_now = max(1e-6, (time.time() - started) / 60.0)
    span = max(1.0, min(5.0, minutes_now / 6.0))
    head = [row for row in samples if row['minute'] <= span]                          # 开局（还在热身）
    mid = [row for row in samples if minutes_now * 0.4 <= row['minute'] <= minutes_now * 0.6]
    tail = [row for row in samples if row['minute'] >= max(0.0, minutes_now - span)]  # 收尾
    head_avg = average(head, 'rss_mb')
    mid_avg = average(mid, 'rss_mb')
    tail_avg = average(tail, 'rss_mb')
    latter = [row for row in samples if row['minute'] >= minutes_now / 2] or samples
    slope = round(slope_mb_per_min(latter), 3)
    peak = max(samples, key=lambda row: row['rss_mb']) if samples else {'rss_mb': None, 'minute': None, 'rounds': 0}
    widget_growth = (samples[-1]['widgets'] - samples[0]['widgets']) if len(samples) >= 2 else 0
    image_growth = (samples[-1]['tk_images'] - samples[0]['tk_images']) if len(samples) >= 2 else 0
    handle_growth = (samples[-1]['handles'] - samples[0]['handles']) if len(samples) >= 2 else 0
    delta = None if mid_avg is None or tail_avg is None else round(tail_avg - mid_avg, 1)
    shape = ('控件数 %d→%d、Tk 图元 %d→%d、句柄 %d→%d'
             % (samples[0]['widgets'], samples[-1]['widgets'], samples[0]['tk_images'],
                samples[-1]['tk_images'], samples[0]['handles'], samples[-1]['handles']))
    if delta is None:
        verdict = '采样太少，看不出趋势'
    elif delta <= 2.0 and slope <= 0.05 and widget_growth <= 5:
        verdict = ('收敛：热身 %.1f → 中段 %.1f → 收尾 %.1f MB（中段到收尾 Δ%.1f），后半程斜率 %.3f MB/分钟，'
                   '%s；峰值 %.1f MB（第 %.1f 分钟，第 %s 轮）——没有长跑泄漏'
                   % (head_avg, mid_avg, tail_avg, delta, slope, shape, peak['rss_mb'], peak['minute'], peak['rounds']))
    else:
        verdict = ('仍在涨：热身 %.1f → 中段 %.1f → 收尾 %.1f MB（Δ%.1f），后半程斜率 %.3f MB/分钟，%s'
                   % (head_avg, mid_avg, tail_avg, delta, slope, shape))
    if fatal:
        verdict += '；第 %.2f 分钟被打断：%s' % (fatal['minute'], fatal['error'])
    return {'minutes': round(minutes_now, 2), 'sample_seconds': SAMPLE, 'assets': ASSETS, 'rounds': rounds,
            'samples': samples, 'head_avg_mb': head_avg, 'mid_avg_mb': mid_avg, 'tail_avg_mb': tail_avg,
            'peak_mb': peak['rss_mb'], 'peak_minute': peak['minute'], 'peak_round': peak['rounds'],
            'delta_mb': delta, 'slope_mb_per_min': slope, 'widget_growth': widget_growth,
            'tk_image_growth': image_growth, 'handle_growth': handle_growth,
            'window_alive': window_alive(), 'interrupted': fatal,
            'close_attempts': [{'what': row['what'], 'minute': round((row['at'] - started) / 60.0, 2),
                                'from': row['from']} for row in close_attempts],
            'verdict': verdict}


def write_report(archive=False):
    """每采一笔就落一次盘：跑到一半被打断也不至于丢掉整段数据。"""
    report = build_report()
    out = Path(__file__).resolve().parent / ('基准结果_内存长跑_%dmin.json' % int(round(MINUTES)))
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    if archive:
        append_history(family='memory_endurance', condition=measurement_conditions(cache_state='warm', first_frame=False),
                       metrics={'tail_avg_mb': report['tail_avg_mb'], 'delta_mb': report['delta_mb'],
                                'slope_mb_per_min': report['slope_mb_per_min'],
                                'widget_growth': report['widget_growth']}, source_result=out.name)
    return report, out


try:
    while time.time() - started < MINUTES * 60:
        try:
            for index in range(11):
                d.show(index)
                win.update()
            d.asset_kind = 'all'
            d.show(2)
            win.update()
        except tk.TclError as exc:
            fatal = {'error': str(exc), 'minute': round((time.time() - started) / 60.0, 2),
                     'note': '窗口没了或被 Tk 自己收掉，按已有采样出结论'}
            print('\n中断：%s' % exc, flush=True)
            break
        rounds += 1
        if rounds % 5 == 0:
            asset_thumbs.forget()          # 逼它下一轮走磁盘缓存（二次打开那条路）
        elapsed = (time.time() - started) / 60.0
        if elapsed * 60 - last_sample >= SAMPLE or not samples:
            last_sample = elapsed * 60
            rss, pagefile = usage_mb()
            row = {'minute': round(elapsed, 2), 'rss_mb': rss, 'pagefile_mb': pagefile,
                   'widgets': count_widgets(win), 'tk_images': tk_image_count(), 'handles': handle_count(),
                   'thumbs_cached': len(getattr(asset_thumbs, '_CACHE', {}) or {}),
                   'thumbs_pending': len(getattr(asset_thumbs, '_PENDING', {}) or {}), 'rounds': rounds}
            samples.append(row)
            print('  %6.2f  %8.1f  %10.1f  %6d  %7d  %5d  %10d  %4d'
                  % (row['minute'], row['rss_mb'], row['pagefile_mb'], row['widgets'], row['tk_images'],
                     row['handles'], row['thumbs_cached'], row['thumbs_pending']), flush=True)
            write_report()
        time.sleep(0.2)
except KeyboardInterrupt:
    print('手动中断，按已有采样出结论。', flush=True)

report, out = write_report(archive=True)
print('\n跑了 %.1f 分钟 / %d 轮；%s' % (report['minutes'], rounds, report['verdict']), flush=True)
print('结果写到 %s' % out, flush=True)
Desktop.choose_project = desktop_choose
Desktop.close = _desktop_close
Desktop.finish_close = _desktop_finish_close
try:
    win.destroy()
except Exception:
    pass
