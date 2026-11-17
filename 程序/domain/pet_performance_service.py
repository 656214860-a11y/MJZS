"""三虎优化模式的离线基准比较服务。

只比较已生成的 JSON 报告，不启动 Tk、不执行基准脚本，也不改写维护目录中的基准快照。
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

import contract.stage_layout as stage_layout
from agent.core import read_json
from contract.project_context import ProjectContext

LEDGER_PATH = (stage_layout.WORKFLOW_DIR, '宠物', '优化.json')
SLOWDOWN_THRESHOLD = 1.4
KEEP = 30
BASELINE_NAME = '基准结果_启动与页面_start.json'
SCRIPT_NAME = '基准_启动与页面.py'
LONG_LIST_BASELINE_NAME = '基准结果_长列表.json'
LONG_LIST_SCRIPT_NAME = '基准_长列表.py'
HOTSPOT_BASELINE_NAME = '基准结果_热点路径.json'
HOTSPOT_SCRIPT_NAME = '基准_热点路径.py'


def _report(value):
    """接受字典或 JSON 路径；坏报告按空报告处理。"""
    return value if isinstance(value, dict) else read_json(Path(value), {})


def _durations(value, prefix=()):
    """扁平化所有 ``*_ms`` 数字叶子，排除行数和内存等非耗时指标。"""
    if not isinstance(value, dict):
        return {}
    rows = {}
    for key, item in value.items():
        path = prefix + (str(key),)
        if isinstance(item, dict):
            rows.update(_durations(item, path))
        elif str(key).endswith('_ms') and isinstance(item, (int, float)) and item >= 0:
            rows['.'.join(path)] = float(item)
    return rows


def slowdowns(baseline, current, threshold=SLOWDOWN_THRESHOLD):
    """返回比基准慢超过阈值的耗时项，结果稳定按指标名排序。"""
    base, now = _durations(_report(baseline)), _durations(_report(current))
    rows = []
    for name in sorted(set(base) & set(now)):
        if base[name] > 0 and now[name] > base[name] * float(threshold):
            rows.append({'metric': name, 'ratio': round(now[name] / base[name], 3)})
    return rows


def record(context, rows, at=None, keep=KEEP, publish=None):
    """保存仅含退化指标与倍率的摘要；正式发布必须由 L3 注入。"""
    if not callable(publish):
        raise TypeError('宠物优化账本发布必须由 L3 注入。')
    now = time.time() if at is None else float(at)
    if not isinstance(context, ProjectContext):
        raise TypeError('宠物优化账本需要由 L3 注入 ProjectContext。')
    path = context.root.joinpath(*LEDGER_PATH)
    old = read_json(path, {})
    items = list(old.get('runs') or []) if isinstance(old, dict) else []
    item = {'at': now, 'slowdowns': list(rows), 'count': len(rows)}
    items.append(item)
    publish(path, {'updated_at': now, 'runs': items[-int(keep):]})
    return item


def compare_and_record(context, baseline, current, at=None, threshold=SLOWDOWN_THRESHOLD, publish=None):
    """比较两份离线报告并生成适合三虎单次播报的简短结果。"""
    rows = slowdowns(baseline, current, threshold=threshold)
    item = record(context, rows, at=at, publish=publish)
    if not rows:
        text = '优化检查完成：未发现超过 %.0f%% 的耗时退化' % ((float(threshold) - 1) * 100)
    else:
        first = rows[0]
        text = '优化检查：%s 比基准慢 %.0f%%' % (
            first['metric'], (first['ratio'] - 1) * 100)
    return {'item': item, 'text': text, 'slowdowns': rows}


def _start_check(program, project, script_name, baseline_name, arguments=(), executable=None, popen=None):
    """启动一种离线基准；报告写项目而非维护基线，由既有 UI 心跳轮询。"""
    program, project = Path(program), Path(project)
    script = program / '维护记录' / '基准脚本' / script_name
    baseline = script.parent / baseline_name
    current = stage_layout.workflow_dir(project, '宠物', '性能', baseline_name)
    if not script.is_file() or not baseline.is_file():
        raise RuntimeError('缺少启动基准脚本或维护基线')
    current.parent.mkdir(parents=True, exist_ok=True)
    output = tempfile.TemporaryFile(mode='w+b')
    command = [str(executable or sys.executable), str(script), *arguments, '--output', str(current)]
    try:
        process = (popen or subprocess.Popen)(
            command, cwd=str(program), stdout=output, stderr=subprocess.STDOUT)
    except Exception:
        output.close()
        raise
    return {'process': process, 'output': output, 'project': project,
            'baseline': baseline, 'current': current, 'command': command}


def start_startup_check(program, project, executable=None, popen=None):
    """启动短启动基准。"""
    return _start_check(program, project, SCRIPT_NAME, BASELINE_NAME, ('start',), executable, popen)


def start_long_list_check(program, project, executable=None, popen=None):
    """启动 300/1000 行资产列表基准；仍只写项目运行报告。"""
    return _start_check(program, project, LONG_LIST_SCRIPT_NAME, LONG_LIST_BASELINE_NAME,
                        (), executable, popen)


def start_hotspot_check(program, project, executable=None, popen=None):
    """启动热点路径离线基准（换项目／目录刷新／长对话／媒体导入）；只写项目运行报告。"""
    return _start_check(program, project, HOTSPOT_SCRIPT_NAME, HOTSPOT_BASELINE_NAME,
                        (), executable, popen)


def poll_startup_check(session, context, at=None, publish=None):
    """已完成时比较报告；子进程文本仅在失败提示中截短，不写入台账。"""
    process = session['process']
    if process.poll() is None:
        return None
    output = session['output']
    try:
        output.seek(0)
        text = output.read().decode('utf-8', 'replace').strip()
    finally:
        output.close()
    if process.returncode:
        tail = text.splitlines()[-1:] or ['未知错误']
        return {'failed': True, 'text': '优化检查运行失败：' + tail[0][:160]}
    if not session['current'].is_file():
        return {'failed': True, 'text': '优化检查未生成运行报告'}
    return compare_and_record(context, session['baseline'], session['current'], at=at,
                              publish=publish)
