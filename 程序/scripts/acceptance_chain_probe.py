# -*- coding: utf-8 -*-
"""桌面与云服务验收任务书 A 维取证驱动（R3709）：假供应商＋真实 Desktop 创意对话。

场景（--scenario）：
  ok       供应商正常 SSE 流式回复 → 预期 settled
  timeout  供应商流式首块后挂起 → 预期 unknown（真实 socket 超时；探针内 WRITING_REQUEST_TIMEOUT 覆盖为 15s，生产默认 180s 不变）
  cancel   供应商慢速流式 → 中途调 interrupt_script_agent() → 预期 unknown/cancelled

链路：Desktop(真 Tk，隐藏桌面运行) → send_message → submit_idea_api_request
→ stage_execution_service.reply_to_writing → writing_api.reply
→ WritingRequestAdapter(PoolAdapter) → model_metering.metered(RequestLedger)
→ model_pool.http_stream → api_endpoints.http_stream → urllib → 本机假供应商。

证据输出到 --evidence-dir/<scenario>/：
  supplier_log.jsonl      供应商侧收到的每个请求（回执）
  request_ledger.json     项目请求台账快照
  token_ledger.json       Token 台账快照
  model_events/*.json     model_diagnostics 逐请求事件（已脱敏）
  transcript.json         创意对话落盘记录
  summary.json            本跑关键结论（台账状态、费用、诊断回执、耗时）

用法（在 程序/ 下，隐藏桌面）：
  python scripts/gui_hidden.py <out> <程序目录> -- python scripts/acceptance_chain_probe.py \
      --scenario ok --evidence-dir <目录>
"""
import argparse
import json
import os
import sys
import tempfile
import threading
import time
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'tests'))
import app_logging  # noqa: E402  验收探针尽力而为路径留痕
import file_cache  # noqa: E402  正式 JSON 读唯一入口

MODEL_ID = 'fake-acceptance-1'
KEY_ENV = 'FAKE_ACCEPTANCE_KEY'
SCENARIOS = ('ok', 'timeout', 'cancel')

# 剧本准备「项目设定」阶段的合规交付物：恰好一个一级标题＝阶段名、末尾「待确认」，
# 采用后落入项目设定目录并记入准备台账；原文同时归档 responses/。
REPLY_TEXT = ('# 项目设定\n\n'
              '- 名称：验收样例·夜班照相馆\n'
              '- 题材：都市悬疑\n'
              '- 时代背景：当代中国二线城市\n'
              '- 视觉基调：冷色调、胶片质感\n\n'
              '待确认\n')
CHUNKS = [REPLY_TEXT[i:i + 8] for i in range(0, len(REPLY_TEXT), 8)] or [REPLY_TEXT]
USAGE = {'prompt_tokens': 120, 'completion_tokens': 30, 'total_tokens': 150,
         'prompt_tokens_details': {'cached_tokens': 0}}


class SupplierState:
    def __init__(self):
        self.lock = threading.Lock()
        self.mode = 'ok'
        self.seq = 0
        self.log = []            # 每个 HTTP 请求一行
        self.responses = {}      # seq → {'finished': bool, 'note': str, 'chunks': int}
        self.chunks_sent = {}    # request 序号 → 已发分片数（cancel 场景判定首块已达）
        self.first_chunk_at = None
        self.probe_timeout = None  # timeout 场景下写作请求超时的探针覆盖值（秒）


STATE = SupplierState()


# 探针把写作请求超时压到 15 秒：与生产 WRITING_REQUEST_TIMEOUT=180 走同一条
# socket read-timeout 代码路径，只缩短等待；供应商挂起 240 秒仍是真实超时。
# 生产默认不变（tests/test_writing_api.py 钉住 180），这里只在探针进程内临时覆盖。
PROBE_REQUEST_TIMEOUT = 15


def _now():
    return datetime.now().isoformat(timespec='milliseconds')


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass

    def _read_body(self):
        length = int(self.headers.get('Content-Length') or 0)
        return self.rfile.read(length) if length else b''

    def _record(self, payload, stream):
        with STATE.lock:
            STATE.seq += 1
            seq = STATE.seq
            entry = {'seq': seq, 'at': _now(), 'path': self.path,
                     'stream': bool(stream), 'model': (payload or {}).get('model'),
                     'mode': STATE.mode,
                     'auth_present': bool(self.headers.get('Authorization')),
                     'body_bytes': len(getattr(self, '_raw_body', b''))}
            STATE.log.append(entry)
            return seq

    def _sse_headers(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'close')
        self.end_headers()

    def _sse_chunk(self, obj):
        self.wfile.write(('data: ' + json.dumps(obj, ensure_ascii=False) + '\n\n').encode('utf-8'))
        self.wfile.flush()

    def _finish_sse(self, seq):
        self._sse_chunk({'id': 'chatcmpl-fake-%d' % seq,
                         'choices': [{'delta': {}, 'finish_reason': 'stop'}], 'usage': USAGE})
        self.wfile.write(b'data: [DONE]\n\n')
        self.wfile.flush()

    def _stream_ok(self, seq):
        self._sse_headers()
        for index, chunk in enumerate(CHUNKS):
            self._sse_chunk({'id': 'chatcmpl-fake-%d' % seq, 'choices': [{'delta': {'content': chunk}, 'finish_reason': None}]})
            with STATE.lock:
                STATE.chunks_sent[seq] = STATE.chunks_sent.get(seq, 0) + 1
        self._finish_sse(seq)

    def _stream_hang(self, seq):
        """首块后静默：客户端在 read 上等 socket 超时（真实超时路径）。"""
        self._sse_headers()
        self._sse_chunk({'id': 'chatcmpl-fake-%d' % seq, 'choices': [{'delta': {'content': CHUNKS[0]}, 'finish_reason': None}]})
        with STATE.lock:
            STATE.chunks_sent[seq] = 1
            STATE.first_chunk_at = STATE.first_chunk_at or _now()
        try:
            time.sleep(240)   # 长于生产 180s 与探针 15s 两种超时；客户端断开后写失败无妨
        except Exception:
            app_logging.swallowed()
        try:
            self._finish_sse(seq)
        except Exception:
            app_logging.swallowed()

    def _stream_slow(self, seq):
        """每 0.4 秒一块、共约 16 秒：留出中途取消窗口。"""
        self._sse_headers()
        for chunk in CHUNKS:
            self._sse_chunk({'id': 'chatcmpl-fake-%d' % seq, 'choices': [{'delta': {'content': chunk}, 'finish_reason': None}]})
            with STATE.lock:
                STATE.chunks_sent[seq] = STATE.chunks_sent.get(seq, 0) + 1
            time.sleep(0.4)
        self._finish_sse(seq)

    def _chat_ok(self, payload):
        body = {'id': 'chatcmpl-fake-%d' % STATE.seq, 'object': 'chat.completion',
                'created': int(time.time()), 'model': payload.get('model') or MODEL_ID,
                'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': REPLY_TEXT},
                             'finish_reason': 'stop'}],
                'usage': USAGE}
        raw = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        raw = self._read_body()
        self._raw_body = raw
        try:
            payload = json.loads(raw.decode('utf-8', 'replace') or '{}')
        except ValueError:
            payload = {}
        stream = bool(payload.get('stream'))
        seq = self._record(payload, stream)
        mode = STATE.mode
        finished = False
        note = ''
        try:
            if stream:
                if mode == 'timeout':
                    self._stream_hang(seq)
                elif mode == 'cancel':
                    self._stream_slow(seq)
                else:
                    self._stream_ok(seq)
            else:
                if mode == 'timeout':
                    time.sleep(240)
                self._chat_ok(payload)
            finished = True
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError) as exc:
            note = type(exc).__name__
        except Exception as exc:
            note = type(exc).__name__
            traceback.print_exc()
        with STATE.lock:
            STATE.responses[seq] = {'finished': finished, 'note': note,
                                    'chunks': STATE.chunks_sent.get(seq, 0)}


def make_project(root):
    """最小项目＋剧本阶段模型/技能＋金额预算价格表（隔离临时目录）。"""
    from tests.ui_edges_support import make_minimal_project
    import orchestrator.stage_config as stage_config
    proj = make_minimal_project(str(root))
    stage_config.put(proj, 'script', model=MODEL_ID, skills=['pipeline-script-preparation'])
    (Path(proj) / 'cost_profile.json').write_text(json.dumps({
        'budget_amount': '10.00',
        'price_table': {'currency': 'CNY', 'version': 'acceptance-fake-v1',
                        'model_rates': {MODEL_ID: {'prompt_tokens': '0.000001',
                                                   'completion_tokens': '0.000002'}}},
    }, ensure_ascii=False), encoding='utf-8')
    return Path(proj)


def write_pool_config():
    """把假供应商写进 程序/配置/宠物/配置.json 的 models 表（git 忽略的运行时配置）。

    已存在的文件先备份到 evidence 目录，跑完原样放回；不存在则跑完删除。
    """
    path = HERE / '配置' / '宠物' / '配置.json'
    backup = path.with_suffix('.json.acceptance-bak')
    existed = path.exists()
    if existed:
        import shutil
        shutil.copyfile(path, backup)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {'label': '验收假供应商', 'model': MODEL_ID,
              'base_url': 'http://127.0.0.1:%d' % STATE.server_port,
              'path': '/chat/completions', 'wire_api': 'chat',
              'key_env': KEY_ENV, 'provider': 'custom',
              'context_length': 200000,
              'capabilities': ['long-context', 'structured-output', 'creative-writing']}
    path.write_text(json.dumps({'models': {MODEL_ID: record}}, ensure_ascii=False, indent=2),
                    encoding='utf-8')
    return path, backup, existed


def restore_pool_config(path, backup, existed):
    try:
        if existed:
            import shutil
            shutil.move(str(backup), str(path))
        elif path.exists():
            path.unlink()
    except OSError:
        pass


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


def ledger_rows(proj):
    path = Path(proj) / '工作流任务' / '宠物' / '请求台账.json'
    if not path.exists():
        return []
    try:
        data = file_cache.read_json(path)
    except ValueError:
        return []
    return data.get('entries') or []


def transcript_rows(proj):
    """直接读剧本写作区的 创意对话/对话.json（idea_transcript 落盘格式）。"""
    try:
        from contract.stage_path_service import write_dir
        path = write_dir(Path(proj), 'script') / '创意对话' / '对话.json'
    except Exception:
        path = Path(proj) / '01剧本准备' / '创意对话' / '对话.json'
    if not path.is_file():
        return []
    try:
        data = file_cache.read_json(path)
    except ValueError:
        return []
    return data.get('messages') or []


def _log_line_in_window(line, started_at):
    """app.log 行首 ISO 时间戳粗判是否落在本跑窗口（started_at 为 epoch 秒）。"""
    stamp = line[:19]
    try:
        return datetime.fromisoformat(stamp).timestamp() >= started_at - 30
    except ValueError:
        return False


def collect_evidence(proj, outdir, started_at, send_error=None):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    events_dir = out / 'model_events'
    events_dir.mkdir(exist_ok=True)
    logs = Path(proj) / 'logs'
    copied_events = []
    if logs.is_dir():
        for path in sorted(logs.rglob('*.json')):
            try:
                if path.is_file() and path.stat().st_mtime >= started_at - 5:
                    target = events_dir / path.relative_to(logs).as_posix()
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(path.read_bytes())
                    copied_events.append(path.relative_to(logs).as_posix())
            except OSError:
                pass
    ledger_path = Path(proj) / '工作流任务' / '宠物' / '请求台账.json'
    ledger_snapshot = None
    if ledger_path.exists():
        ledger_snapshot = file_cache.read_json(ledger_path)
        (out / 'request_ledger.json').write_text(
            json.dumps(ledger_snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
    token_path = Path(proj) / '工作流任务' / '宠物' / 'Token台账.json'
    if token_path.exists():
        (out / 'token_ledger.json').write_bytes(token_path.read_bytes())
    rows = transcript_rows(proj)
    (out / 'transcript.json').write_text(
        json.dumps(rows, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    with STATE.lock:
        supplier = [dict(row, first_chunk_at=STATE.first_chunk_at,
                         **({'response': STATE.responses[row['seq']]}
                            if row['seq'] in STATE.responses else {}))
                    for row in STATE.log]
    (out / 'supplier_log.jsonl').write_text(
        ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in supplier), encoding='utf-8')
    entries = [row for row in (ledger_snapshot or {}).get('entries', [])
               if float(row.get('at') or 0) >= started_at - 30]
    assistant = [row for row in rows if row.get('role') == 'assistant']

    # 产物清单：本跑窗口内项目内新建/修改的文件（相对路径＋大小＋sha256），
    # 小文本产物（md/txt/json，≤64KB）复制进 evidence/artifacts/ 供核对正文。
    import hashlib
    artifacts_dir = out / 'artifacts'
    artifacts_dir.mkdir(exist_ok=True)
    artifact_manifest = []
    try:
        for path in sorted(Path(proj).rglob('*')):
            try:
                if not path.is_file() or path.stat().st_mtime < started_at - 5:
                    continue
                if any(part in ('.git', '__pycache__') for part in path.parts):
                    continue
                rel = path.relative_to(proj).as_posix()
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                item = {'path': rel, 'bytes': path.stat().st_size, 'sha256': digest}
                if path.suffix.lower() in ('.md', '.txt', '.json') and path.stat().st_size <= 65536:
                    target = artifacts_dir / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(path.read_bytes())
                    item['copied'] = True
                artifact_manifest.append(item)
            except OSError:
                continue
    except OSError:
        pass
    (out / 'artifacts_manifest.json').write_text(
        json.dumps(artifact_manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    # 程序级运行证据：桌面后台任务历史（app 根 outputs/）与 app.log 本跑窗口行。
    task_history = HERE / 'outputs' / 'desktop-task-history.json'
    if task_history.is_file():
        try:
            (out / 'desktop-task-history.json').write_bytes(task_history.read_bytes())
        except OSError:
            pass
    app_log = HERE / 'logs' / 'app.log'
    if app_log.is_file():
        try:
            lines = app_log.read_text(encoding='utf-8', errors='replace').splitlines()
            window = [line for line in lines[-4000:]
                      if _log_line_in_window(line, started_at)]
            (out / 'app_log_window.jsonl').write_text(
                chr(10).join(window) + (chr(10) if window else ''), encoding='utf-8')
        except OSError:
            pass
    summary = {
        'scenario': STATE.mode,
        'project': str(proj),
        'send_error': send_error,
        'supplier_requests': supplier,
        'ledger_entries': entries,
        'assistant_replies': [{'at': row.get('at'), 'model': str(row.get('model') or ''),
                               'text_len': len(str(row.get('text') or '')),
                               'text_head': str(row.get('text') or '')[:60]} for row in assistant],
        'diagnostic_events': copied_events,
        'artifact_count': len(artifact_manifest),
        'artifacts': [item['path'] for item in artifact_manifest],
        'probe_request_timeout_seconds': STATE.probe_timeout,
        'collected_at': _now(),
    }
    (out / 'summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    return summary


def _install_meter_trace(outdir):
    """调试追踪：每次 metered 调用与 chat_streaming 结果写进 evidence/debug_trace.log。

    只读包装，不改行为；用于定位取消/超时下重复计量调用的来源。
    """
    trace = Path(outdir) / 'debug_trace.log'
    trace.parent.mkdir(parents=True, exist_ok=True)

    def log(line):
        try:
            with trace.open('a', encoding='utf-8') as handle:
                handle.write(line + chr(10))
        except OSError:
            pass

    import infra.model_metering as model_metering
    import writing_api
    original_metered = model_metering.metered
    original_streaming = writing_api.chat_streaming

    def metered_spy(ledger, request, send, usage_of, on_result=None):
        import traceback
        log('=== %.3f metered request_id=%s model=%s stage=%s' % (time.time(), request[0], request[1], request[2]))
        log(''.join(traceback.format_stack(limit=12)[:-1]))
        try:
            return original_metered(ledger, request, send, usage_of, on_result=on_result)
        finally:
            log('=== %.3f metered done request_id=%s' % (time.time(), request[0]))

    def streaming_spy(adapter, messages, options, model, system, cancelled=None):
        state = cancelled() if callable(cancelled) else cancelled
        log('=== %.3f chat_streaming enter cancelled=%s' % (time.time(), state))
        try:
            result = original_streaming(adapter, messages, options, model, system, cancelled)
        except Exception as exc:
            log('=== %.3f chat_streaming RAISED %s' % (time.time(), type(exc).__name__))
            raise
        log('=== %.3f chat_streaming -> ok=%s error_class=%s error=%s'
            % (time.time(), result.get('ok'), result.get('error_class'), str(result.get('error'))[:80]))
        return result

    model_metering.metered = metered_spy
    writing_api.chat_streaming = streaming_spy

    # 适配器层追踪：数 on_chunk 实际回调次数与 stream/chat 结果的 error_class，
    # 用于判定 chat_streaming 退回普通请求的判定依据（seen 是否为空）。
    original_wra_stream = writing_api.WritingRequestAdapter.stream
    original_wra_chat = writing_api.WritingRequestAdapter.chat

    def stream_spy(self, messages, options=None, model='', system='', **kwargs):
        calls = {'n': 0}
        inner = kwargs.get('on_chunk')
        def counting(chunk):
            calls['n'] += 1
            if callable(inner):
                inner(chunk)
        kwargs['on_chunk'] = counting
        result = original_wra_stream(self, messages, options=options, model=model,
                                     system=system, **kwargs)
        log('=== %.3f adapter.stream on_chunk_calls=%d -> ok=%s error_class=%s error=%s'
            % (time.time(), calls['n'], result.get('ok'), result.get('error_class'),
               str(result.get('error'))[:80]))
        return result

    def chat_spy(self, messages, options=None, model='', system=''):
        try:
            result = original_wra_chat(self, messages, options=options, model=model, system=system)
        except Exception as exc:
            log('=== %.3f adapter.chat RAISED %s' % (time.time(), type(exc).__name__))
            raise
        log('=== %.3f adapter.chat -> ok=%s error_class=%s error=%s'
            % (time.time(), result.get('ok'), result.get('error_class'), str(result.get('error'))[:80]))
        return result

    writing_api.WritingRequestAdapter.stream = stream_spy
    writing_api.WritingRequestAdapter.chat = chat_spy


def run_scenario(scenario, evidence_root):
    import tkinter as tk
    import desktop as desktop_module
    from desktop import Desktop, PAGE
    from local_video import open_studio

    sandbox = Path(tempfile.mkdtemp(prefix='acceptance-%s-' % scenario))
    proj = make_project(sandbox)
    outdir = Path(evidence_root) / scenario
    started_at = time.time()

    STATE.mode = scenario
    STATE.seq = 0
    STATE.log = []
    STATE.responses = {}
    STATE.chunks_sent = {}
    STATE.first_chunk_at = None
    STATE.probe_timeout = None

    import writing_api
    original_request_timeout = writing_api.WRITING_REQUEST_TIMEOUT
    if scenario == 'timeout':
        STATE.probe_timeout = PROBE_REQUEST_TIMEOUT
        writing_api.WRITING_REQUEST_TIMEOUT = PROBE_REQUEST_TIMEOUT

    pool_path, pool_backup, pool_existed = write_pool_config()
    os.environ[KEY_ENV] = 'acceptance-dummy-key'
    _install_meter_trace(outdir)
    original_choose = desktop_module.Desktop.choose_project
    desktop_module.Desktop.choose_project = lambda self: None
    win = None
    send_error = None
    try:
        win = tk.Tk()
        win.withdraw()
        d = Desktop(win, root=HERE)
        d.root = proj
        d.studio = open_studio(proj)
        d.show(PAGE['script'])
        pump(win, 0.3)
        # 等模型键解析与首绘空闲分片落定（同 tests/test_idea_chat settle_script_page 口径）
        pump_until(win, lambda: bool(getattr(d, '_idea_view_model_cache', None)), 10.0)
        pump(win, 0.3)

        draft = ('故事梗概：夜班照相馆收到一张会显影未来的旧底片。\n'
                 '故事角色：摄影师林默\n故事题材：都市悬疑\n故事集数：12集\n'
                 '单集时间：120秒\n故事画幅：9:16\n视频模型：MiniMax H3\n'
                 '交付形态：只要 markdown 文档')
        box = d.idea_input
        box.delete('1.0', 'end')
        box.insert('1.0', draft)
        pump(win, 0.1)

        if scenario == 'cancel':
            # 慢速流：send_message 本身只投递异步请求、立即返回；等供应商首块
            # 确实发出后再走真实中断入口 interrupt_script_agent。
            try:
                d.send_message()
            except Exception as exc:
                send_error = repr(exc)
            pump_until(win, lambda: any(STATE.chunks_sent.values()), 60.0)
            pump(win, 0.3)
            try:
                d.interrupt_script_agent()
            except Exception as exc:
                send_error = (send_error or '') + ' interrupt: ' + repr(exc)
            pump_until(win, lambda: not getattr(d.idea_chat_controller, 'requesting', False), 60.0)
            # UI 先解除忙碌，worker 的 settle 在后台收尾；等台账到终态再取证，
            # 否则进程退出会把 daemon 线程的结算一并带走（reserved 悬挂）。
            def terminal():
                return any(row.get('state') in ('settled', 'unknown', 'cancelled')
                           for row in ledger_rows(proj))
            pump_until(win, terminal, 30.0, interval=0.1)
            pump(win, 0.5)
        else:
            try:
                d.send_message()
            except Exception as exc:
                send_error = repr(exc)
            if scenario == 'timeout':
                # 真实超时：流式超时后设计上会退回普通请求，普通请求也要等它自己的
                # socket 超时收尾；等到台账没有任何在途（reserved/estimated）条目。
                def all_terminal():
                    rows = ledger_rows(proj)
                    return bool(rows) and all(
                        row.get('state') in ('settled', 'unknown', 'cancelled')
                        for row in rows)
                pump_until(win, all_terminal, 420.0, interval=0.5)
            else:
                def replied():
                    return any(row.get('role') == 'assistant' for row in transcript_rows(proj))
                pump_until(win, replied, 60.0, interval=0.1)
            pump(win, 0.8)
    except Exception:
        send_error = (send_error or '') + traceback.format_exc()
    finally:
        try:
            if win is not None:
                win.update()
        except Exception:
            app_logging.swallowed()
        desktop_module.Desktop.choose_project = original_choose
        writing_api.WRITING_REQUEST_TIMEOUT = original_request_timeout
        restore_pool_config(pool_path, pool_backup, pool_existed)
        try:
            if win is not None:
                win.destroy()
        except Exception:
            app_logging.swallowed()
    summary = collect_evidence(proj, outdir, started_at, send_error=send_error)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', required=True, choices=SCENARIOS)
    parser.add_argument('--evidence-dir', required=True)
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()

    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    STATE.server_port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        summary = run_scenario(args.scenario, args.evidence_dir)
    finally:
        server.shutdown()
        server.server_close()
    print(json.dumps({'scenario': args.scenario,
                      'supplier_requests': len(summary['supplier_requests']),
                      'ledger_states': [(row.get('id'), row.get('state'), row.get('money_state'),
                                         row.get('budget_cost')) for row in summary['ledger_entries']],
                      'assistant_replies': len(summary['assistant_replies']),
                      'evidence': str(Path(args.evidence_dir) / args.scenario)},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
