"""三虎测试模式的无界面结果服务。

测试模式只运行既有 ``run_selftests.py --incremental``，不会调用模型、不会修改项目产物；
每次运行的摘要写入项目自己的宠物台账，供 UI 在既有心跳中轮询并播报。
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from agent.core import read_json, save

LEDGER_PATH = ('工作流任务', '宠物', '测试.json')
KEEP = 30
MAX_REPEATS = 20


def repeat_count(text, default=1, maximum=MAX_REPEATS):
    """从“跑 3 次增量自检”取次数；无次数时只跑一次。"""
    found = re.search(r'(\d+)\s*次', str(text or ''))
    if not found:
        return int(default)
    return max(1, min(int(found.group(1)), int(maximum)))


def failure_names(output):
    """从 unittest 文本提取失败用例名，避免把完整日志写进项目台账。"""
    names = []
    for line in str(output or '').splitlines():
        match = re.search(r'^(?:FAIL|ERROR):\s*([^\s(]+)', line.strip())
        if match:
            names.append(match.group(1))
    return list(dict.fromkeys(names))


def result_of(completed, index):
    output = str(getattr(completed, 'stdout', '') or '')
    match = re.search(r'Ran\s+(\d+)\s+tests?', output)
    return {'index': int(index), 'ok': int(getattr(completed, 'returncode', 1)) == 0,
            'tests': int(match.group(1)) if match else 0,
            'failures': failure_names(output)}


def ledger_path(project):
    return Path(project).joinpath(*LEDGER_PATH)


def record(project, runs, at=None, keep=KEEP):
    """追加一条不含原始日志的测试模式摘要，并返回新记录。"""
    now = time.time() if at is None else float(at)
    path = ledger_path(project)
    old = read_json(path, {})
    rows = list(old.get('runs') or []) if isinstance(old, dict) else []
    passed = sum(1 for row in runs if row.get('ok'))
    item = {'at': now, 'mode': 'incremental', 'runs': list(runs),
            'total': len(runs), 'passed': passed,
            'success_rate': (passed / len(runs)) if runs else 0.0}
    rows.append(item)
    save(path, {'updated_at': now, 'runs': rows[-int(keep):]})
    return item


def run_incremental(program, project, text='', executable=None, invoke=None, at=None):
    """顺序运行增量自检，写台账并返回用于播报的精简摘要。"""
    program = Path(program)
    repeats = repeat_count(text)
    command = [str(executable or sys.executable), 'run_selftests.py', '--incremental']
    invoke = invoke or (lambda args, cwd: subprocess.run(
        args, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding='utf-8', errors='replace', check=False))
    runs = [result_of(invoke(command, program), index + 1) for index in range(repeats)]
    item = record(project, runs, at=at)
    failed = [name for row in runs for name in row['failures']]
    text = '增量自检 %d/%d 通过（成功率 %.0f%%）' % (
        item['passed'], item['total'], item['success_rate'] * 100)
    if failed:
        text += '；失败：' + '、'.join(list(dict.fromkeys(failed))[:3])
    return {'item': item, 'text': text, 'failures': list(dict.fromkeys(failed))}


def start_incremental(program, text='', executable=None, popen=None):
    """启动一次增量自检；调用方在既有心跳里用 ``poll_incremental`` 取结果。"""
    program = Path(program)
    output = tempfile.TemporaryFile(mode='w+b')
    command = [str(executable or sys.executable), 'run_selftests.py', '--incremental']
    popen = popen or subprocess.Popen
    try:
        process = popen(command, cwd=str(program), stdout=output, stderr=subprocess.STDOUT)
    except Exception:
        output.close()
        raise
    return {'program': program, 'command': command, 'process': process, 'output': output,
            'repeats': repeat_count(text), 'runs': []}


def poll_incremental(session, project, at=None):
    """轮询一次；未完成返回 ``None``，多次请求会顺序启动下一次。"""
    process = session['process']
    if process.poll() is None:
        return None
    output = session['output']
    try:
        output.seek(0)
        text = output.read().decode('utf-8', 'replace')
    finally:
        output.close()
    completed = type('Completed', (), {'returncode': process.returncode, 'stdout': text})()
    session['runs'].append(result_of(completed, len(session['runs']) + 1))
    if len(session['runs']) < session['repeats']:
        runs, repeats = session['runs'], session['repeats']
        next_session = start_incremental(
            session['program'], '%d次' % repeats, executable=session['command'][0])
        session.update(next_session)
        session['runs'], session['repeats'] = runs, repeats
        return {'running': True, 'completed': len(session['runs']), 'total': session['repeats']}
    item = record(project, session['runs'], at=at)
    failed = list(dict.fromkeys(name for row in session['runs'] for name in row['failures']))
    message = '增量自检 %d/%d 通过（成功率 %.0f%%）' % (
        item['passed'], item['total'], item['success_rate'] * 100)
    if failed:
        message += '；失败：' + '、'.join(failed[:3])
    return {'running': False, 'item': item, 'text': message, 'failures': failed}
