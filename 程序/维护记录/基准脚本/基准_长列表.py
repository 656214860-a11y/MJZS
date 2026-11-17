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
import ui_edges_support as T
from contract.project_stages import storyboard as storyboard_stage
from test_perf_baseline import big_project as performance_big_project
from infra.pet_state import PAGE_OF


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


def find_tree(root):
    """内容框里最后一个有行的 Treeview（资产表）。"""
    found = [None]
    def walk(w):
        for child in w.winfo_children():
            if isinstance(child, ttk.Treeview) and len(child.get_children()) > 0:
                found[0] = child
            walk(child)
    walk(root)
    return found[0]


def settle_rows(win, table, expected, timeout=30.0):
    """像 mainloop 一样分段 ``update``，等分批插行与缩略图落地走完再量。

    单次 ``win.update()`` 会把整条 ``after`` 链排空：行数读数与滚动帧测到的都是
    「全量建完」的瞬间，看不到「首帧之后渐进长齐」的真实过程（R2979 定性：
    此前 treeview_rows 在 24／300 间摆动、scroll 225ms→1.4ms 的落差都是这个口径
    造成的，不是产品退化）。返回 (耗时 ms, 最终行数)。
    """
    import asset_thumbs
    start = time.perf_counter()
    rows = last = -1
    quiet = still = 0
    while time.perf_counter() - start < timeout:
        win.update()
        try:
            rows = len(table.get_children())
        except Exception:
            rows = -1
        still = still + 1 if rows == last else 0
        last = rows
        done = asset_thumbs.pending() == 0 and (rows >= expected or still >= 40)
        quiet = quiet + 1 if done else 0
        if quiet >= 3:
            break
        time.sleep(0.05)
    return round((time.perf_counter() - start) * 1000, 1), rows


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
        expected = 3 * max(1, count // 3)             # CHAR_/LOC_/PROP_ 各 per 项
        t = time.perf_counter(); d.show(PAGE_OF['assets']); win.update(); cold = round((time.perf_counter() - t) * 1000, 1)
        table = find_tree(d.content)
        # fill_ms＝从 show() 到行长齐的总时长＝首帧 update 已耗时长＋补齐余量；
        # 首帧 update 把整条 after 链排空时它≈cold_ms，如实反映「全量可用」的代价。
        rest_ms, rows = settle_rows(win, table, expected) if table is not None else (0.0, 0)
        fill_ms = round(cold + rest_ms, 1) if rest_ms is not None else None
        t = time.perf_counter(); d.show(PAGE_OF['assets']); win.update(); warm = round((time.perf_counter() - t) * 1000, 1)
        table = find_tree(d.content)
        if table is not None:
            settle_rows(win, table, expected)
        frames = []
        if table is not None:
            for i in range(60):
                a = time.perf_counter()
                table.yview_scroll(3, 'units')
                win.update()
                frames.append(round((time.perf_counter() - a) * 1000, 2))
        # 中位数与性能门禁同口径（test_perf_baseline 的 median 判据）；avg/max 只作参考。
        ordered = sorted(frames)
        median_ms = ordered[len(ordered) // 2] if ordered else None
        out[count] = {'cold_ms': cold, 'warm_ms': warm, 'treeview_rows': rows, 'fill_ms': fill_ms,
                      'scroll_avg_ms': round(sum(frames) / len(frames), 2) if frames else None,
                      'scroll_median_ms': median_ms,
                      'scroll_max_ms': max(frames) if frames else None}
        print(count, out[count])
win.destroy()
result_path = output_path(sys.argv[1:], Path(__file__).resolve().parent / '基准结果_长列表.json')
result_path.parent.mkdir(parents=True, exist_ok=True)
result_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
for count, values in out.items():
    append_history(family='long_list', condition=measurement_conditions(cache_state='cold', first_frame=False),
                   metrics={'row_count': int(count), 'cold_ms': values['cold_ms'],
                            'fill_ms': values['fill_ms']}, source_result=result_path.name)
    append_history(family='long_list', condition=measurement_conditions(cache_state='warm', first_frame=False),
                   metrics={'row_count': int(count), 'warm_ms': values['warm_ms'],
                            'scroll_avg_ms': values['scroll_avg_ms'],
                            'scroll_median_ms': values['scroll_median_ms'],
                            'scroll_max_ms': values['scroll_max_ms']}, source_result=result_path.name)
