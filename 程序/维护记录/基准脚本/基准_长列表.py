# -*- coding: utf-8 -*-
"""长列表基准：300／1000 个需求资产的资产管理页（真实控件路径）。"""
import atexit, io, json, os, shutil, struct, sys, tempfile, time, zlib
from pathlib import Path
from benchmark_history import append_history, measurement_conditions
PROG = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROG)); sys.path.insert(0, str(PROG / 'tests')); os.chdir(str(PROG))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import tkinter as tk
from tkinter import ttk
from desktop import Desktop
import local_video
import test_ui_edges as T
from project_stages import storyboard as storyboard_stage
from test_perf_baseline import big_project as performance_big_project
from pet_state import PAGE_OF


def output_path(args, default):
    """允许自动检查写项目运行报告，默认仍更新人工维护的基准快照。"""
    if '--output' not in args:
        return default
    index = args.index('--output')
    if index + 1 >= len(args):
        raise SystemExit('--output 需要一个 JSON 路径')
    return Path(args[index + 1])


def png(w, h, phase=0):
    raw = b''.join(b'\x00' + b''.join(bytes(((x * 7 + phase) % 256, (y * 5) % 256, 160))
                                       for x in range(w)) for y in range(h))

    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def big_project(td, count):
    """count 个需求资产（CHAR_/LOC_/PROP_ 各 1/3），每张资产图都是真的 96×96 PNG。"""
    proj = T.make_adopted_project(td)
    base = proj / 'episode'
    shots = []
    per = max(1, count // 3)
    chars = ['CHAR_%03d' % i for i in range(1, per + 1)]
    locs = ['LOC_%03d' % i for i in range(1, per + 1)]
    props = ['PROP_%03d' % i for i in range(1, per + 1)]
    for i in range(1, (per if per else 1) + 1):
        shots.append({'id': 'SH%03d' % i, 'title': '镜头 %d' % i, 'duration': 5,
                      'characters': [chars[i - 1]], 'location': locs[i - 1],
                      'props': [props[i - 1]], 'frame': 'frames/SH%03d.png' % i,
                      'video_prompt': '画面', 'frame_prompt': '窗边的猫', 'dialogue': []})
    episode = {'episode_id': 'EP001', 'title': 'T', 'shots': shots}
    for folder in ('characters', 'scenes', 'props'):
        (base / 'assets' / folder).mkdir(parents=True, exist_ok=True)
    for aid in chars:
        path = base / 'assets' / 'characters' / (aid + '.png')
        path.write_bytes(png(96, 96, len(aid)))
    for aid in locs:
        (base / 'assets' / 'scenes' / (aid + '.png')).write_bytes(png(96, 96, len(aid)))
    for aid in props:
        (base / 'assets' / 'props' / (aid + '.png')).write_bytes(png(96, 96, len(aid)))
    target = storyboard_stage(proj) / '分镜文档' / 'episode.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(episode, ensure_ascii=False), encoding='utf-8')
    T.keep_storyboard_fresh(proj)
    return proj


Desktop.choose_project = lambda self: None
win = tk.Tk()
d = Desktop(win, root=PROG)
out = {}
for count in (300, 1000):
    with tempfile.TemporaryDirectory() as td:
        atexit.register(shutil.rmtree, td, True)     # 第 58 期：中途抛错也要删掉临时项目
        # 与性能门禁共用同一正式资产页 fixture，避免“只量到一行”的假基准。
        proj = performance_big_project(td, count)
        d.root = proj
        d.studio = local_video.open_studio(proj)
        d.asset_kind = 'all'
        import asset_thumbs
        asset_thumbs.forget()
        t = time.perf_counter(); d.show(PAGE_OF['assets']); win.update(); cold = round((time.perf_counter() - t) * 1000, 1)
        rows = []
        def walk(w):
            for child in w.winfo_children():
                if isinstance(child, ttk.Treeview):
                    rows.append(len(child.get_children()) or 0)
                walk(child)
        walk(d.content)
        t = time.perf_counter(); d.show(PAGE_OF['assets']); win.update(); warm = round((time.perf_counter() - t) * 1000, 1)
        table = None
        def find(w):
            global table
            for child in w.winfo_children():
                # 资产页按视口虚拟化，Treeview 只保留可见行；不能再用“>100 子项”否定真列表。
                if isinstance(child, ttk.Treeview) and len(child.get_children()) > 0:
                    table = child
                find(child)
        find(d.content)
        frames = []
        if table is not None:
            for i in range(60):
                a = time.perf_counter()
                table.yview_scroll(3, 'units')
                win.update()
                frames.append(round((time.perf_counter() - a) * 1000, 2))
        out[count] = {'cold_ms': cold, 'warm_ms': warm, 'treeview_rows': max(rows or [0]),
                      'scroll_avg_ms': round(sum(frames) / len(frames), 2) if frames else None,
                      'scroll_max_ms': max(frames) if frames else None}
        print(count, out[count])
win.destroy()
result_path = output_path(sys.argv[1:], Path(__file__).resolve().parent / '基准结果_长列表.json')
result_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
for count, values in out.items():
    append_history(family='long_list', condition=measurement_conditions(cache_state='cold', first_frame=False),
                   metrics={'row_count': int(count), 'cold_ms': values['cold_ms']}, source_result=result_path.name)
    append_history(family='long_list', condition=measurement_conditions(cache_state='warm', first_frame=False),
                   metrics={'row_count': int(count), 'warm_ms': values['warm_ms'],
                            'scroll_avg_ms': values['scroll_avg_ms'],
                            'scroll_max_ms': values['scroll_max_ms']}, source_result=result_path.name)
