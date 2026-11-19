# -*- coding: utf-8 -*-
"""桌面与云服务验收任务书 D 维取证·恢复与连续使用（R3759）父进程驱动。

三个相互独立的隐藏桌面进程跑同一可丢弃项目：
  adopt   创意稿 →「项目设定」阶段稿 →「继续」→ 模型推进 → 项目设定被确认 → 正常退出。
  hang    打开同项目 →「继续」→ 台账 reserved 且供应商请求在途 → 父进程强杀 worker。
  verify  打开同项目 → 空等观察窗（核对无自动重发）→ 再发「继续」→ 陈旧 reserved
          按既有清扫规则转 unknown、新请求正常结算、下一阶段稿推进确认。

时间压缩：夭折请求的 reserved 按生产规则要等 REQUEST_RESERVED_STALE_SECONDS=1800 秒
才清扫；verify 进程经 --stale-seconds 把该常量压到「杀进程至本次加载已超过」的值
（生产默认不变），走的仍是 _sweep_stale_reserved 同一代码路径。

证据输出到 --evidence-dir：adopt/ hang/ verify/ 各阶段 worker 结果与 gui 日志、
ledger_at_kill.json、ledger_at_verify_open.json、ledger_final.json、
manifest_{adopt,kill,verify}.json、supplier_log.jsonl、preparation_state.json、
transcript.json、desktop-task-history.json、network_probe.json、summary.json。

用法（在 程序/ 下）：
  ../运行环境/Python/python.exe -B scripts/acceptance_recovery_probe.py \
      --evidence-dir <目录> [--port 0] [--observe-seconds 8]
"""
import argparse
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
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

MODEL_ID = 'fake-acceptance-recovery-1'
KEY_ENV = 'FAKE_ACCEPTANCE_RECOVERY_KEY'
WORKER = HERE / 'scripts' / 'acceptance_recovery_worker.py'
GUI_HIDDEN = HERE / 'scripts' / 'gui_hidden.py'
SERVICE_HOST = '8.138.223.126'

DOC_PROJECT = ('# 项目设定\n\n'
               '- 名称：验收样例·深夜修理铺\n'
               '- 题材：都市奇幻\n'
               '- 时代背景：近未来港口城市\n'
               '- 视觉基调：暖黄灯光与霓虹冷色对比\n\n'
               '待确认\n')
DOC_OUTLINE = ('# 剧本大纲\n\n'
               '- 主线：修理铺老板接下「修复记忆」的委托\n'
               '- 结构：12 集单元剧，每集一个委托\n'
               '- 高潮：第 10 集委托人身份揭晓\n\n'
               '待确认\n')
DOC_CHARACTER = ('# 人物设定（角色卡）\n\n'
                 '- 陈麦：男，26 岁，修理铺老板，记忆残缺\n'
                 '- 阿棠：女，外卖骑手，委托人之一\n\n'
                 '待确认\n')
DOCS = {1: DOC_PROJECT, 2: DOC_OUTLINE}
DOC_DEFAULT = DOC_CHARACTER
USAGE = {'prompt_tokens': 120, 'completion_tokens': 30, 'total_tokens': 150,
         'prompt_tokens_details': {'cached_tokens': 0}}


class SupplierState:
    def __init__(self):
        self.lock = threading.Lock()
        self.mode = 'ok'          # ok | hang
        self.seq = 0
        self.log = []
        self.responses = {}
        self.chunks_sent = {}
        self.server_port = None


STATE = SupplierState()


def _now():
    return datetime.now().isoformat(timespec='milliseconds')


def _write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                    encoding='utf-8')


def _read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


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
            entry = {'seq': seq, 'at': _now(), 'at_epoch': time.time(),
                     'path': self.path, 'stream': bool(stream),
                     'model': (payload or {}).get('model'),
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

    def _reply_text(self, seq):
        return DOCS.get(seq, DOC_DEFAULT)

    def _stream_ok(self, seq):
        self._sse_headers()
        text = self._reply_text(seq)
        for index in range(0, len(text), 8):
            chunk = text[index:index + 8]
            self._sse_chunk({'id': 'chatcmpl-fake-%d' % seq,
                             'choices': [{'delta': {'content': chunk}, 'finish_reason': None}]})
            with STATE.lock:
                STATE.chunks_sent[seq] = STATE.chunks_sent.get(seq, 0) + 1
        self._finish_sse(seq)

    def _stream_hang(self, seq):
        """首块后静默挂起：客户端进程被强杀时连接随之死亡。"""
        self._sse_headers()
        self._sse_chunk({'id': 'chatcmpl-fake-%d' % seq,
                         'choices': [{'delta': {'content': '…'}, 'finish_reason': None}]})
        with STATE.lock:
            STATE.chunks_sent[seq] = 1
        try:
            time.sleep(240)
        except Exception:
            pass
        try:
            self._finish_sse(seq)
        except Exception:
            pass

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
                if mode == 'hang':
                    self._stream_hang(seq)
                else:
                    self._stream_ok(seq)
            else:
                body = json.dumps({'id': 'chatcmpl-fake-%d' % seq, 'object': 'chat.completion',
                                   'created': int(time.time()), 'model': payload.get('model') or MODEL_ID,
                                   'choices': [{'index': 0, 'message': {'role': 'assistant',
                                                                        'content': self._reply_text(seq)},
                                                'finish_reason': 'stop'}],
                                   'usage': USAGE}, ensure_ascii=False).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
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
    from tests.ui_edges_support import make_minimal_project
    import orchestrator.stage_config as stage_config
    proj = make_minimal_project(str(root))
    stage_config.put(proj, 'script', model=MODEL_ID, skills=['pipeline-script-preparation'])
    (Path(proj) / 'cost_profile.json').write_text(json.dumps({
        'budget_amount': '10.00',
        'price_table': {'currency': 'CNY', 'version': 'acceptance-recovery-v1',
                        'model_rates': {MODEL_ID: {'prompt_tokens': '0.000001',
                                                   'completion_tokens': '0.000002'}}},
    }, ensure_ascii=False), encoding='utf-8')
    return Path(proj)


def write_pool_config():
    path = HERE / '配置' / '宠物' / '配置.json'
    backup = path.with_suffix('.json.acceptance-bak')
    existed = path.exists()
    if existed:
        shutil.copyfile(path, backup)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {'label': '验收恢复假供应商', 'model': MODEL_ID,
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
            shutil.move(str(backup), str(path))
        elif path.exists():
            path.unlink()
    except OSError:
        pass


def manifest(proj):
    """项目全文件清单：相对路径 → {bytes, sha256}；供三点比对成果完整性。"""
    items = {}
    for path in sorted(Path(proj).rglob('*')):
        try:
            if not path.is_file():
                continue
            if any(part in ('.git', '__pycache__') for part in path.parts):
                continue
            rel = path.relative_to(proj).as_posix()
            items[rel] = {'bytes': path.stat().st_size,
                          'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        except OSError:
            continue
    return items


def ledger_snapshot(proj):
    path = Path(proj) / '工作流任务' / '宠物' / '请求台账.json'
    data = _read_json(path)
    return data if isinstance(data, dict) else {'entries': []}


def ledger_path(proj):
    return Path(proj) / '工作流任务' / '宠物' / '请求台账.json'


def copy_file(src, dst):
    try:
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        return True
    except OSError:
        return False


def spawn_worker(mode, proj, evdir, extra):
    """经 gui_hidden.py 在隐藏桌面拉起 worker；返回 Popen。"""
    log = Path(evdir) / ('gui_%s.log' % mode)
    log.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, '-B', str(GUI_HIDDEN), str(log), str(HERE), '--',
           sys.executable, '-B', str(WORKER),
           '--mode', mode, '--project', str(proj), '--evidence', str(evdir)] + list(extra)
    env = dict(os.environ, DRAMA_HIDDEN_DESKTOP='1')
    return subprocess.Popen(cmd, cwd=str(HERE), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)




def wait_file(path, timeout, proc=None):
    """等文件出现；进程先退出则提前返回 False。返回 (出现?, 进程退出码或None)。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if Path(path).is_file():
            return True, (proc.poll() if proc is not None else None)
        if proc is not None and proc.poll() is not None:
            end = time.monotonic() + 2.0
            while time.monotonic() < end:
                if Path(path).is_file():
                    return True, proc.poll()
                time.sleep(0.1)
            return False, proc.poll()
        time.sleep(0.2)
    return False, (proc.poll() if proc is not None else None)


def kill_pid(pid):
    """Windows 强杀：os.kill(SIGTERM)→TerminateProcess；失败回退 taskkill /F。"""
    try:
        os.kill(int(pid), signal.SIGTERM)
        return 'os.kill(SIGTERM)'
    except (OSError, ValueError):
        pass
    try:
        subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                       capture_output=True, timeout=15)
        return 'taskkill /F'
    except (OSError, subprocess.SubprocessError):
        return 'failed'


def supplier_log_rows():
    with STATE.lock:
        return [dict(row, **({'response': STATE.responses[row['seq']]}
                             if row['seq'] in STATE.responses else {}))
                for row in STATE.log]


def copy_transcript(proj, dst):
    try:
        from contract.stage_path_service import write_dir
        src = write_dir(Path(proj), 'script') / '创意对话' / '对话.json'
    except Exception:
        src = Path(proj) / '01剧本准备' / '创意对话' / '对话.json'
    copy_file(src, dst)


def copy_preparation_state(proj, dst):
    try:
        from contract.stage_path_service import write_dir
        src = write_dir(Path(proj), 'script') / 'preparation_state.json'
    except Exception:
        src = Path(proj) / '01剧本准备' / 'preparation_state.json'
    copy_file(src, dst)


def network_probe(out_path):
    """服务端管理面/SSH 只读可达性探测：TCP connect + 协议层应答（3 秒超时）。

    本机出口对部分端口呈「TCP connect 成功但协议数据被重置/超时」的透明代理特征，
    只测 connect 会高估可达性；这里对每个端口再做一次被动/主动协议探测：
    22 读 SSH banner；443/8443 做 TLS+HTTP GET /v1/meta（证书不校验，仅测可达）；
    8000/8001 发 HTTP GET 观察是否有应用层应答。全部只读、不携带凭据。
    """
    import ssl
    results = {}
    for port in (22, 443, 8000, 8001, 8443):
        started = time.time()
        entry = {'connect_seconds': None, 'protocol': 'none', 'detail': ''}
        try:
            raw = socket.create_connection((SERVICE_HOST, port), timeout=3)
            entry['connect_seconds'] = round(time.time() - started, 3)
            entry['tcp_connect'] = True
            raw.settimeout(3)
            try:
                if port == 22:
                    banner = raw.recv(64)
                    entry['protocol'] = 'ssh-banner' if banner else 'closed'
                    entry['detail'] = banner[:40].decode('ascii', 'replace') if banner else ''
                elif port in (443, 8443):
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    tls = ctx.wrap_socket(raw, server_hostname=SERVICE_HOST)
                    tls.settimeout(3)
                    tls.sendall(b'GET /v1/meta HTTP/1.1\r\nHost: ' + SERVICE_HOST.encode() +
                                b'\r\nConnection: close\r\n\r\n')
                    data = tls.recv(256)
                    entry['protocol'] = 'https-get'
                    entry['detail'] = ('HTTP %s' % data.split(b' ', 2)[1].decode('ascii', 'replace')
                                       if data[:5] == b'HTTP/' else 'non-http reply %dB' % len(data))
                    tls.close()
                else:
                    raw.sendall(b'GET / HTTP/1.1\r\nHost: ' + SERVICE_HOST.encode() +
                                b'\r\nConnection: close\r\n\r\n')
                    data = raw.recv(256)
                    entry['protocol'] = 'http-get'
                    entry['detail'] = ('HTTP %s' % data.split(b' ', 2)[1].decode('ascii', 'replace')
                                       if data[:5] == b'HTTP/' else 'non-http reply %dB' % len(data))
            except (socket.timeout, TimeoutError):
                entry['protocol'] = 'timeout'
                entry['detail'] = 'connected but no protocol data within 3s'
            except (ConnectionResetError, BrokenPipeError, ssl.SSLError, OSError) as exc:
                entry['protocol'] = 'reset'
                entry['detail'] = type(exc).__name__ + ': ' + str(exc)[:100]
            finally:
                try:
                    raw.close()
                except OSError:
                    pass
        except OSError as exc:
            entry['tcp_connect'] = False
            entry['protocol'] = 'unreachable'
            entry['detail'] = type(exc).__name__ + ': ' + str(exc)[:120]
            entry['connect_seconds'] = round(time.time() - started, 3)
        results[str(port)] = entry
    _write_json(out_path, {'host': SERVICE_HOST, 'probed_at': _now(), 'ports': results,
                           'note': 'TCP connect + 协议层只读探测；B 轮协议级证据见 R3739'})
    return results


def run_adopt_phase(proj, evdir):
    sub = Path(evdir) / 'adopt'
    sub.mkdir(parents=True, exist_ok=True)
    proc = spawn_worker('adopt', proj, sub, [])
    ok, code = wait_file(sub / 'worker_result_adopt.json', 420, proc)
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
    result = _read_json(sub / 'worker_result_adopt.json')
    return {'proc_returncode': proc.returncode, 'result': result,
            'result_file_seen': ok, 'wait_exit': code}


def run_hang_phase(proj, evdir):
    sub = Path(evdir) / 'hang'
    sub.mkdir(parents=True, exist_ok=True)
    STATE.mode = 'hang'
    seq_before = STATE.seq
    proc = spawn_worker('hang', proj, sub, ['--hang-wait', '120', '--hang-hold', '600'])
    armed_path = sub / 'hang_armed.json'
    deadline = time.monotonic() + 150
    armed = None
    while time.monotonic() < deadline:
        if armed_path.is_file():
            armed = _read_json(armed_path)
            if armed and STATE.seq > seq_before:
                break
        if proc.poll() is not None:
            break
        time.sleep(0.3)
    return {'proc': proc, 'armed': armed, 'seq_before': seq_before,
            'armed_seen': bool(armed), 'supplier_seq': STATE.seq}


def run_verify_phase(proj, evdir, stale_seconds, observe_seconds):
    sub = Path(evdir) / 'verify'
    sub.mkdir(parents=True, exist_ok=True)
    STATE.mode = 'ok'
    open_path = sub / 'verify_open.json'
    send_path = sub / 'verify_send.json'
    proc = spawn_worker('verify', proj, sub,
                        ['--observe-seconds', str(observe_seconds),
                         '--stale-seconds', str(stale_seconds)])
    deadline = time.monotonic() + 180
    opened_epoch = None
    while time.monotonic() < deadline:
        if open_path.is_file():
            opened = _read_json(open_path) or {}
            opened_epoch = opened.get('opened_epoch')
            copy_file(ledger_path(proj), evdir / 'ledger_at_verify_open.json')
            break
        if proc.poll() is not None:
            break
        time.sleep(0.2)
    ok, code = wait_file(sub / 'worker_result_verify.json', 300, proc)
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
    result = _read_json(sub / 'worker_result_verify.json')
    return {'proc_returncode': proc.returncode, 'result': result,
            'result_file_seen': ok, 'opened_epoch': opened_epoch,
            'send_epoch': (_read_json(send_path) or {}).get('sent_epoch')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir', required=True)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--observe-seconds', type=float, default=8.0)
    parser.add_argument('--work-dir', default='')
    args = parser.parse_args()

    evdir = Path(args.evidence_dir)
    evdir.mkdir(parents=True, exist_ok=True)
    sandbox = Path(args.work_dir) if args.work_dir else Path(tempfile.mkdtemp(prefix='acceptance-recovery-'))
    sandbox.mkdir(parents=True, exist_ok=True)
    proj = make_project(sandbox)
    summary = {'project': str(proj), 'sandbox': str(sandbox), 'checks': [],
               'started_at': _now(), 'started_epoch': time.time()}

    def check(name, ok, detail=''):
        summary['checks'].append({'name': name, 'ok': bool(ok), 'detail': str(detail)[:500]})
        return ok

    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    STATE.server_port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    pool_path = pool_backup = pool_existed = None
    try:
        STATE.mode = 'ok'
        pool_path, pool_backup, pool_existed = write_pool_config()
        os.environ[KEY_ENV] = 'acceptance-dummy-key'

        # ── Phase 1: adopt ────────────────────────────────────────────
        t0 = time.time()
        adopt = run_adopt_phase(proj, evdir)
        summary['adopt_seconds'] = round(time.time() - t0, 3)
        adopt_result = adopt['result'] or {}
        check('adopt_worker_exited', adopt['proc_returncode'] == 0,
              'returncode=%s' % adopt['proc_returncode'])
        check('adopt_project_setting_confirmed',
              adopt_result.get('adopted_confirmed') is True
              and adopt_result.get('ok') is True,
              json.dumps(adopt_result.get('final_stage_status'), ensure_ascii=False)[:300])
        _write_json(evdir / 'manifest_adopt.json', manifest(proj))

        # ── Phase 2: hang + 强杀 ──────────────────────────────────────
        t0 = time.time()
        hang = run_hang_phase(proj, evdir)
        armed = hang['armed'] or {}
        check('hang_armed_reserved_seen', hang['armed_seen'] and hang['supplier_seq'] > hang['seq_before'],
              'armed=%s supplier_seq=%s' % (hang['armed_seen'], hang['supplier_seq']))
        kill_epoch = None
        kill_method = ''
        if hang['armed_seen']:
            kill_epoch = time.time()
            kill_method = kill_pid(armed.get('pid'))
            try:
                hang['proc'].wait(timeout=30)
            except subprocess.TimeoutExpired:
                hang['proc'].kill()
            summary['hang_proc_returncode'] = hang['proc'].returncode
            summary['kill'] = {'pid': armed.get('pid'), 'method': kill_method,
                               'kill_epoch': kill_epoch, 'request_id': armed.get('request_id'),
                               'request_at': armed.get('at'),
                               'proc_returncode': hang['proc'].returncode,
                               'armed_payload': armed}
            _write_json(evdir / 'ledger_at_kill.json', ledger_snapshot(proj))
            _write_json(evdir / 'manifest_kill.json', manifest(proj))
        summary['hang_seconds'] = round(time.time() - t0, 3)

        # ── Phase 3: verify（重启同项目）──────────────────────────────
        t0 = time.time()
        stale_seconds = 0.0
        if kill_epoch:
            age = max(1.0, time.time() - float(armed.get('sent_at') or kill_epoch))
            stale_seconds = round(max(2.0, age * 0.5), 3)
        verify = run_verify_phase(proj, evdir, stale_seconds, args.observe_seconds)
        summary['verify_seconds'] = round(time.time() - t0, 3)
        summary['stale_seconds_applied'] = stale_seconds
        vresult = verify['result'] or {}
        check('verify_worker_exited', verify['proc_returncode'] == 0,
              'returncode=%s' % verify['proc_returncode'])
        check('verify_resend_replied', vresult.get('resend', {}).get('ok') is True,
              json.dumps(vresult.get('resend'), ensure_ascii=False)[:200])
        _write_json(evdir / 'manifest_verify.json', manifest(proj))
        _write_json(evdir / 'ledger_final.json', ledger_snapshot(proj))
        copy_preparation_state(proj, evdir / 'preparation_state.json')
        copy_transcript(proj, evdir / 'transcript.json')
        copy_file(HERE / 'outputs' / 'desktop-task-history.json',
                  evdir / 'desktop-task-history.json')

        # ── 分析 ──────────────────────────────────────────────────────
        final_entries = (ledger_snapshot(proj).get('entries') or [])
        killed_id = armed.get('request_id')
        killed_entry = next((row for row in final_entries if row.get('id') == killed_id), None)
        check('killed_request_marked_unknown_stale',
              killed_entry is not None and killed_entry.get('state') == 'unknown'
              and killed_entry.get('unknown_via') == 'stale-reserved',
              json.dumps(killed_entry, ensure_ascii=False)[:300] if killed_entry else 'entry missing')
        kill_ledger = _read_json(evdir / 'ledger_at_kill.json') or {}
        kill_entry = next((row for row in (kill_ledger.get('entries') or [])
                           if row.get('id') == killed_id), None)
        check('killed_request_reserved_at_kill',
              kill_entry is not None and kill_entry.get('state') == 'reserved',
              json.dumps(kill_entry, ensure_ascii=False)[:300] if kill_entry else 'entry missing')

        opened_epoch = verify.get('opened_epoch')
        send_epoch = verify.get('send_epoch')
        # 无自动重发：verify 阶段供应商请求数必须恰为 1（人工重发那笔）。
        # 自动重发会在 Desktop 打开后数秒内到达观察窗，导致计数 >=2。
        verify_requests = []
        if opened_epoch:
            verify_requests = [row for row in supplier_log_rows()
                               if float(row.get('at_epoch') or 0) >= opened_epoch - 1
                               and row.get('seq', 0) > hang.get('supplier_seq', 0)]
        auto_resends = [row for row in verify_requests
                        if send_epoch and float(row.get('at_epoch') or 0) < send_epoch - 0.5]
        summary['verify_phase_requests'] = verify_requests
        check('no_auto_resend_during_observe_window',
              len(verify_requests) == 1 and not auto_resends,
              'verify_requests=%s send_epoch=%s opened_epoch=%s'
              % ([row.get('seq') for row in verify_requests], send_epoch, opened_epoch))

        # 成果完整性：采用稿文件在 adopt→kill→verify 三点哈希一致
        adopt_manifest = _read_json(evdir / 'manifest_adopt.json') or {}
        kill_manifest = _read_json(evdir / 'manifest_kill.json') or {}
        verify_manifest = _read_json(evdir / 'manifest_verify.json') or {}
        prep_state = _read_json(evdir / 'preparation_state.json') or {}
        docs = [doc for doc in (prep_state.get('documents') or []) if isinstance(doc, dict)]
        adopted_docs = [doc for doc in docs if doc.get('confirmed') is True]
        intact = []
        missing = []
        for doc in adopted_docs:
            rel = doc.get('path')
            base = None
            try:
                from contract.stage_path_service import write_dir
                base = write_dir(proj, 'script')
            except Exception:
                base = proj / '01剧本准备'
            key = None
            if rel:
                try:
                    key = (Path(base) / rel).resolve().relative_to(proj.resolve()).as_posix()
                except (OSError, ValueError):
                    key = None
            hashes = [m.get(key, {}).get('sha256') for m in
                      (adopt_manifest, kill_manifest, verify_manifest)] if key else [None] * 3
            if key and all(h and h == hashes[0] for h in hashes):
                intact.append({'path': rel, 'sha256': hashes[0]})
            else:
                missing.append({'path': rel, 'hashes': hashes})
        check('adopted_artifacts_intact_across_crash', bool(adopted_docs) and not missing,
              'intact=%s missing=%s' % (len(intact), missing))
        summary['adopted_artifacts'] = intact
        summary['adopted_docs'] = docs

        if kill_epoch and opened_epoch:
            summary['recovery_seconds'] = round(opened_epoch - kill_epoch, 3)
        summary['manual_steps'] = [
            '重新启动漫剧制作助手（探针以新进程等价）',
            '打开同一项目目录（探针 open_studio(proj) 等价）',
            '在剧本页重新发送「继续」推进（探针 send_message 等价）',
            '陈旧 reserved 由台账既有清扫规则自动转 unknown，无需人工核对即可继续制作',
        ]
        summary['ledger_final_entries'] = [
            {'id': row.get('id'), 'kind': row.get('kind'), 'state': row.get('state'),
             'money_state': row.get('money_state'), 'unknown_via': row.get('unknown_via'),
             'at': row.get('at'), 'settled_at': row.get('settled_at')}
            for row in final_entries]
        summary['supplier_requests'] = supplier_log_rows()
        summary['supplier_seq_total'] = STATE.seq

        network_probe(evdir / 'network_probe.json')
        summary['network_probe'] = _read_json(evdir / 'network_probe.json')
    except Exception:
        summary['fatal'] = traceback.format_exc()
        check('probe_completed', False, summary['fatal'][-300:])
    finally:
        if pool_path is not None:
            restore_pool_config(pool_path, pool_backup, pool_existed)
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass
        _write_json(evdir / 'supplier_log.jsonl',
                    {'requests': supplier_log_rows()})
        summary['finished_at'] = _now()
        summary['finished_epoch'] = time.time()
        summary['all_checks_passed'] = all(row['ok'] for row in summary['checks']) \
            and 'fatal' not in summary
        _write_json(evdir / 'summary.json', summary)
    print(json.dumps({'all_checks_passed': summary.get('all_checks_passed'),
                      'checks': [(c['name'], c['ok']) for c in summary['checks']],
                      'recovery_seconds': summary.get('recovery_seconds'),
                      'evidence': str(evdir)}, ensure_ascii=False, indent=2))
    return 0 if summary.get('all_checks_passed') else 1


if __name__ == '__main__':
    sys.exit(main())
