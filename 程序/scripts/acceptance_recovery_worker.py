# -*- coding: utf-8 -*-
"""桌面与云服务验收任务书 D 维取证·隐藏桌面工作进程（R3759）。

由 ``scripts/acceptance_recovery_probe.py`` 经 ``scripts/gui_hidden.py`` 拉起；
每个模式是一个独立进程，模拟「同一项目被反复打开」的真实桌面会话。

模式（--mode）：
  adopt   打开项目 → 发送创意 → 等「项目设定」阶段稿 → 再发「继续」→ 等「项目设定」被确认
          （剧本大纲落稿）→ 写 worker_result_adopt.json 后正常退出。
  hang    打开项目 → 发送「继续」→ 台账出现 reserved 条目后写 hang_armed.json，
          然后挂起等待被父进程强杀（模拟生成中途进程夭折）。
  verify  打开项目 → 先空等 --observe-seconds（父进程据此核对无自动重发）→
          再发「继续」→ 等下一阶段稿回复 → 写 worker_result_verify.json。
          --stale-seconds>0 时在建 Desktop 前把 request_ledger 的
          REQUEST_RESERVED_STALE_SECONDS 压成该值（生产默认 1800 不变），
          让夭折遗留的 reserved 预留在下一次台账事务里按既有清扫规则转 unknown。

证据文件（均写入 --evidence 目录）：
  worker_pid.json        启动即写：pid/模式/时间，供父进程定位强杀目标
  hang_armed.json        hang 模式：reserved 条目出现时写入 request_id 与台账快照
  verify_open.json       verify 模式：Desktop 就绪、进入空等窗口时写入
  verify_send.json       verify 模式：显式重发前写入，供父进程对照供应商到达时刻
  worker_result_<mode>.json  该模式结论（阶段确认状态、台账状态、耗时）

用法（在 程序/ 下，由 gui_hidden.py 包装）：
  python scripts/gui_hidden.py <out> <程序目录> -- <python> scripts/acceptance_recovery_worker.py \
      --mode adopt --project <项目目录> --evidence <证据目录>
"""
import argparse
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import app_logging  # noqa: E402  验收探针尽力而为路径留痕
import file_cache  # noqa: E402  正式 JSON 读唯一入口


def _now():
    return datetime.now().isoformat(timespec='milliseconds')


def _write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                    encoding='utf-8')


def ledger_path(project):
    return Path(project) / '工作流任务' / '宠物' / '请求台账.json'


def ledger_entries(project):
    path = ledger_path(project)
    if not path.is_file():
        return []
    try:
        data = file_cache.read_json(path)
    except ValueError:
        return []
    return data.get('entries') or []


def preparation_state(project):
    """读剧本准备台账；返回 (state_dict, error)。沿用写口径的阶段目录解析。"""
    try:
        from contract.stage_path_service import write_dir
        folder = write_dir(Path(project), 'script')
    except Exception:
        folder = Path(project) / '01剧本准备'
    target = folder / 'preparation_state.json'
    if not target.is_file():
        return None, 'missing'
    try:
        return file_cache.read_json(target), None
    except ValueError as exc:
        return None, str(exc)


def stage_status(project):
    """三阶段各自的确认状态：[{stage, confirmed, path}]。"""
    state, error = preparation_state(project)
    if state is None:
        return {'error': error, 'documents': []}
    docs = state.get('documents') or []
    return {'documents': [
        {'stage': doc.get('stage'), 'confirmed': doc.get('confirmed') is True,
         'path': doc.get('path'), 'sha256': doc.get('sha256')}
        for doc in docs if isinstance(doc, dict)]}


def transcript_rows(project):
    try:
        from contract.stage_path_service import write_dir
        path = write_dir(Path(project), 'script') / '创意对话' / '对话.json'
    except Exception:
        path = Path(project) / '01剧本准备' / '创意对话' / '对话.json'
    if not path.is_file():
        return []
    try:
        data = file_cache.read_json(path)
    except ValueError:
        return []
    return data.get('messages') or []


def pump(win, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            win.update()
        except Exception:
            break
        time.sleep(0.01)
    try:
        win.update()
    except Exception:
        app_logging.swallowed()


def pump_until(win, predicate, timeout, interval=0.05):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            win.update()
        except Exception:
            return False
        if predicate():
            return True
        time.sleep(interval)
    try:
        win.update()
    except Exception:
        app_logging.swallowed()
    return predicate()


def open_project_desktop(proj):
    """真实 Desktop 实例打开既有项目（与 A 轮同一实例化路径）。"""
    import tkinter as tk
    import desktop as desktop_module
    from desktop import Desktop, PAGE
    from local_video import open_studio

    original_choose = desktop_module.Desktop.choose_project
    desktop_module.Desktop.choose_project = lambda self: None
    win = tk.Tk()
    win.withdraw()
    try:
        d = Desktop(win, root=HERE)
        d.root = Path(proj)
        d.studio = open_studio(Path(proj))
        d.show(PAGE['script'])
        pump(win, 0.3)
        ready = pump_until(win, lambda: bool(getattr(d, '_idea_view_model_cache', None)), 15.0)
        pump(win, 0.3)
        return win, d, ready, original_choose, desktop_module
    except Exception:
        try:
            win.destroy()
        except Exception:
            app_logging.swallowed()
        desktop_module.Desktop.choose_project = original_choose
        raise


def send_idea(d, win, text, timeout=90.0):
    """写输入框并走真实 send_message；等 assistant 回复落盘后返回回复条数。"""
    before = len([row for row in transcript_rows(d.root) if row.get('role') == 'assistant'])
    box = d.idea_input
    box.delete('1.0', 'end')
    box.insert('1.0', text)
    pump(win, 0.1)
    d.send_message()

    def replied():
        rows = transcript_rows(d.root)
        return len([row for row in rows if row.get('role') == 'assistant']) > before
    ok = pump_until(win, replied, timeout, interval=0.1)
    pump(win, 0.6)
    after = len([row for row in transcript_rows(d.root) if row.get('role') == 'assistant'])
    return ok, after - before


def run_adopt(args, ev):
    started = time.time()
    proj = Path(args.project)
    win, d, ready, original_choose, desktop_module = open_project_desktop(proj)
    result = {'mode': 'adopt', 'project': str(proj), 'desktop_ready': ready,
              'started_at': _now(), 'sends': []}
    try:
        if not ready:
            result['error'] = 'Desktop 剧本页未就绪'
            return result
        draft = ('故事梗概：海港城市的灯塔信标连夜熄灭，前自动化工程师循线索追查。\n'
                 '故事角色：林澈\n'
                 '故事题材：科幻悬疑\n'
                 '故事集数：12集\n'
                 '单集时间：120秒\n'
                 '故事画幅：9:16\n'
                 '视频模型：MiniMax H3\n'
                 '交付形态：只要 markdown 文档')
        ok1, n1 = send_idea(d, win, draft, timeout=120.0)
        result['sends'].append({'text': 'draft', 'ok': ok1, 'assistant_new': n1,
                                'stage_status': stage_status(proj)})
        if not ok1:
            result['error'] = '第一轮（项目设定）未收到回复'
            return result
        pump_until(win, lambda: any(
            doc.get('stage') == '项目设定' and doc.get('confirmed') is not True
            for doc in (preparation_state(proj)[0] or {}).get('documents') or ()), 15.0)
        ok2, n2 = send_idea(d, win, '继续', timeout=120.0)
        result['sends'].append({'text': '继续', 'ok': ok2, 'assistant_new': n2,
                                'stage_status': stage_status(proj)})
        if not ok2:
            result['error'] = '第二轮（推进确认）未收到回复'
            return result
        # 等采用确认落盘（confirmed=True 与确认快照由统一写口异步完成）
        def adopted():
            state, _e = preparation_state(proj)
            docs = (state or {}).get('documents') or []
            return any(isinstance(doc, dict) and doc.get('stage') == '项目设定'
                       and doc.get('confirmed') is True for doc in docs)
        result['adopted_confirmed'] = pump_until(win, adopted, 20.0, interval=0.1)
        pump(win, 0.5)
        result['final_stage_status'] = stage_status(proj)
        result['elapsed_seconds'] = round(time.time() - started, 3)
        result['ok'] = bool(result['adopted_confirmed'])
        if not result['ok']:
            result['error'] = '项目设定未确认（采用未完成）'
        return result
    except Exception:
        result['error'] = traceback.format_exc()
        return result
    finally:
        try:
            desktop_module.Desktop.choose_project = original_choose
            win.destroy()
        except Exception:
            app_logging.swallowed()


def run_hang(args, ev):
    started = time.time()
    proj = Path(args.project)
    result = {'mode': 'hang', 'project': str(proj), 'started_at': _now()}
    win = d = original_choose = desktop_module = None
    try:
        win, d, ready, original_choose, desktop_module = open_project_desktop(proj)
        result['desktop_ready'] = ready
        if not ready:
            result['error'] = 'Desktop 剧本页未就绪'
            return result
        before = len(ledger_entries(proj))
        box = d.idea_input
        box.delete('1.0', 'end')
        box.insert('1.0', '继续')
        pump(win, 0.1)
        d.send_message()
        sent_at = time.time()

        def reserved_seen():
            for row in ledger_entries(proj)[before:]:
                if row.get('state') == 'reserved':
                    return row
            return None
        deadline = time.monotonic() + float(args.hang_wait)
        armed = None
        while time.monotonic() < deadline:
            try:
                win.update()
            except Exception:
                break
            armed = reserved_seen()
            if armed is not None:
                break
            time.sleep(0.05)
        if armed is None:
            result['error'] = '%.0f 秒内台账未出现 reserved 条目' % float(args.hang_wait)
            result['elapsed_seconds'] = round(time.time() - started, 3)
            return result
        armed_payload = {'pid': __import__('os').getpid(), 'mode': 'hang',
                         'request_id': armed.get('id'), 'kind': armed.get('kind'),
                         'state': armed.get('state'), 'money_state': armed.get('money_state'),
                         'at': armed.get('at'), 'sent_at': sent_at, 'armed_at': _now(),
                         'ledger_path': str(ledger_path(proj))}
        _write_json(Path(args.evidence) / 'hang_armed.json', armed_payload)
        result['armed'] = armed_payload
        # 挂起：等父进程强杀；超时兜底退出，避免悬挂 worker。
        hang_deadline = time.monotonic() + float(args.hang_hold)
        while time.monotonic() < hang_deadline:
            try:
                win.update()
            except Exception:
                break
            time.sleep(0.05)
        result['elapsed_seconds'] = round(time.time() - started, 3)
        result['note'] = 'hang_hold 超时未被强杀，worker 自行退出'
        result['ok'] = False
        return result
    except Exception:
        result['error'] = traceback.format_exc()
        return result
    finally:
        try:
            if desktop_module is not None:
                desktop_module.Desktop.choose_project = original_choose
            if win is not None:
                win.destroy()
        except Exception:
            app_logging.swallowed()


def run_verify(args, ev):
    started = time.time()
    proj = Path(args.project)
    result = {'mode': 'verify', 'project': str(proj), 'started_at': _now()}
    # 在任何台账加载之前压缩陈旧预留窗口：只影响本进程内存常量，生产默认不变。
    patched = None
    if float(args.stale_seconds) > 0:
        import infra.request_ledger as request_ledger
        patched = float(args.stale_seconds)
        request_ledger.REQUEST_RESERVED_STALE_SECONDS = patched
        result['stale_seconds_applied'] = patched
        result['stale_seconds_production'] = 1800.0
    win = d = original_choose = desktop_module = None
    try:
        win, d, ready, original_choose, desktop_module = open_project_desktop(proj)
        result['desktop_ready'] = ready
        if not ready:
            result['error'] = 'Desktop 剧本页未就绪'
            return result
        opened_at = time.time()
        _write_json(Path(args.evidence) / 'verify_open.json',
                    {'opened_at': _now(), 'opened_epoch': opened_at,
                     'observe_seconds': float(args.observe_seconds)})
        # 空等窗口：期间不得有任何供应商请求（父进程据此核对无自动重发）。
        pump(win, float(args.observe_seconds))
        _write_json(Path(args.evidence) / 'verify_send.json',
                    {'sent_at': _now(), 'sent_epoch': time.time(), 'text': '继续'})
        ok, n = send_idea(d, win, '继续', timeout=150.0)
        result['resend'] = {'ok': ok, 'assistant_new': n}
        pump(win, 0.8)
        # 台账终态快照（重发授权事务已把陈旧 reserved 清扫为 unknown 并落盘）。
        entries = ledger_entries(proj)
        result['ledger_entries'] = [
            {'id': row.get('id'), 'kind': row.get('kind'), 'state': row.get('state'),
             'mode': row.get('mode'), 'money_state': row.get('money_state'),
             'unknown_via': row.get('unknown_via'), 'at': row.get('at'),
             'settled_at': row.get('settled_at')} for row in entries]
        result['final_stage_status'] = stage_status(proj)
        result['elapsed_seconds'] = round(time.time() - started, 3)
        result['ok'] = bool(ok)
        if not ok:
            result['error'] = '重发未收到回复'
        return result
    except Exception:
        result['error'] = traceback.format_exc()
        return result
    finally:
        try:
            if desktop_module is not None:
                desktop_module.Desktop.choose_project = original_choose
            if win is not None:
                win.destroy()
        except Exception:
            app_logging.swallowed()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', required=True, choices=('adopt', 'hang', 'verify'))
    parser.add_argument('--project', required=True)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--observe-seconds', type=float, default=8.0)
    parser.add_argument('--stale-seconds', type=float, default=0.0)
    parser.add_argument('--hang-wait', type=float, default=90.0,
                        help='hang 模式等 reserved 条目出现的上限（秒）')
    parser.add_argument('--hang-hold', type=float, default=300.0,
                        help='hang 模式挂起上限（秒），兜底防悬挂')
    args = parser.parse_args()

    ev = Path(args.evidence)
    ev.mkdir(parents=True, exist_ok=True)
    _write_json(ev / 'worker_pid.json',
                {'pid': __import__('os').getpid(), 'mode': args.mode, 'at': _now()})

    runner = {'adopt': run_adopt, 'hang': run_hang, 'verify': run_verify}[args.mode]
    try:
        result = runner(args, ev)
    except Exception:
        result = {'mode': args.mode, 'ok': False, 'error': traceback.format_exc()}
    result['finished_at'] = _now()
    _write_json(ev / ('worker_result_%s.json' % args.mode), result)
    print(json.dumps({'mode': args.mode, 'ok': result.get('ok'),
                      'error': (result.get('error') or '')[:200]}, ensure_ascii=False))
    return 0 if result.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
