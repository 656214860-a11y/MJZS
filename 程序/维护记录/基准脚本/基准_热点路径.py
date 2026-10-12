# -*- coding: utf-8 -*-
"""热点路径基准（任务 O46）：先测量，再决定动不动实现。

只量能离线、无 Tk 的那一段；主界面首帧、页面切换、滚动、缩略图像素这些依赖
Tk 渲染的路径由 基准_启动与页面.py 负责。两者合起来覆盖验收点列的七条路径：
启动／换项目／刷新目录／滚动／缩略图／长对话／媒体导入。

用法：python 基准_热点路径.py [--output PATH]
产出：基准结果_热点路径.json，并往 维护记录/基准历史.json 追加一条可比较记录。
"""
import atexit
import ctypes
import ctypes.wintypes
import io
import json
import os
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

from benchmark_history import append_history, measurement_conditions

ARGS = sys.argv[1:]

# 媒体导入在落盘／解码之前先按扩展名把目录扫一遍；这里量的是这一段发现成本。
MEDIA_SUFFIXES = {'.mp4', '.mov', '.mkv', '.avi', '.webm', '.mp3', '.wav',
                  '.m4a', '.flac', '.png', '.jpg', '.jpeg', '.webp'}
CHAT_MESSAGES = 800
STAGE_FILES = 1500
LIBRARY_PROJECTS = 24
MEDIA_FILES = 400
REPEAT = 3


def output_path(default):
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
    """当前进程工作集（MB）；取不到时返回 -1，口径与 基准_启动与页面.py 一致。"""
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


def measured(fn, repeat=REPEAT):
    """跑 repeat 次，给出首跑（冷）与最小/中位；首跑常命中不到缓存，最能代表真实首屏。"""
    before = rss_mb()
    samples = []
    for _ in range(repeat):
        t = time.perf_counter()
        fn()
        samples.append(since(t))
    return {'first_ms': samples[0], 'min_ms': min(samples),
            'median_ms': round(statistics.median(samples), 1), 'samples_ms': samples,
            'rss_delta_mb': round(rss_mb() - before, 1)}


report = {'mode': 'hotspot', 'workload': {
    'library_projects': LIBRARY_PROJECTS, 'stage_files': STAGE_FILES,
    'chat_messages': CHAT_MESSAGES, 'media_files': MEDIA_FILES, 'repeat': REPEAT},
    'paths': {}, 'memory': {}}

tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
td = Path(tmp.name)
atexit.register(shutil.rmtree, str(td), True)

import projects
import idea_chat
from agent.core import read_json as core_read_json

# --- 换项目：项目库一级扫描 + 逐项目读 config.json（探针里 config 会进缓存，故看首跑） ---
library = td / 'library'
library.mkdir()
for index in range(LIBRARY_PROJECTS):
    folder = library / ('项目%02d' % index)
    (folder / 'episode').mkdir(parents=True)
    (folder / 'config.json').write_text(json.dumps({'name': '项目%02d' % index}), encoding='utf-8')
report['paths']['project_switch'] = measured(lambda: projects._discover_candidates(library))

# --- 刷新目录：阶段目录里逐文件列举并按后缀筛（刷新列表走的就是这一步） ---
stage = td / 'stage'
stage.mkdir()
for index in range(STAGE_FILES):
    (stage / ('shot_%04d.json' % index)).write_text('{}', encoding='utf-8')


def refresh_dir():
    return [item for item in stage.iterdir() if item.suffix == '.json']


report['paths']['dir_refresh'] = measured(refresh_dir)

# --- 长对话：历史 JSON 解析 + 行规整；每个样本换一个文件，避免命中读取缓存 ---
def _noop(*_args, **_kwargs):
    return None


gateway = {'read_json': core_read_json, 'publish_json': _noop, 'publish_text': _noop}
chat_files = []
for index in range(REPEAT):
    rows = [{'role': 'user' if step % 2 == 0 else 'assistant',
             'text': '第%d条消息内容，用于压一压解析与规整成本。' % step,
             'at': '20261012_08%02d%02d' % (step % 60, step % 60),
             'model': 'DeepSeek V4 Pro'} for step in range(CHAT_MESSAGES)]
    path = td / ('chat_%d.json' % index)
    path.write_text(json.dumps({'messages': rows}, ensure_ascii=False), encoding='utf-8')
    chat_files.append(path)

_cursor = {'n': 0}


def load_chat():
    path = chat_files[_cursor['n'] % len(chat_files)]
    _cursor['n'] += 1
    idea_chat._read_rows(path, gateway)


report['paths']['long_chat'] = measured(load_chat)

# --- 媒体导入：导入前的目录发现（解码/落盘在服务层，需真实项目上下文，不在探针内） ---
media = td / 'media'
media.mkdir()
suffixes = sorted(MEDIA_SUFFIXES)
for index in range(MEDIA_FILES):
    (media / ('clip_%03d%s' % (index, suffixes[index % len(suffixes)]))).write_bytes(b'x' * 64)


def discover_media():
    return [item for item in media.iterdir() if item.suffix.lower() in MEDIA_SUFFIXES]


report['paths']['media_import'] = measured(discover_media)

report['memory']['end_mb'] = rss_mb()
report['elapsed_total_ms'] = since(T0)

out = output_path(Path(__file__).resolve().parent / '基准结果_热点路径.json')
out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
append_history(family='hotspot_paths',
               condition=measurement_conditions(cache_state='cold', first_frame=False),
               metrics={key: value['first_ms'] for key, value in report['paths'].items()},
               source_result=out.name)
print(json.dumps(report, ensure_ascii=False, indent=1))
