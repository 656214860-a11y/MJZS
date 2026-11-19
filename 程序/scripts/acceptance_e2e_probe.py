# -*- coding: utf-8 -*-
"""桌面与云服务验收任务书 E 维取证父进程（R3800）：本地制作链＋受控云端链。

跑一个隐藏桌面 worker（scripts/acceptance_e2e_worker.py），本进程提供：
  - 假模型供应商（127.0.0.1，SSE/JSON，模式经 evidence/supplier_mode.json 热切换：
    ok／slow／error）；
  - 假会员服务（127.0.0.1，/v1/* 真实路径；RSA-2048 租约用内置测试密钥对 k-e2e
    纯 Python 签发，客户端验签链路真实）；
  - 项目制备（make_minimal_project＋script/script_structure 阶段配置＋成本档案＋
    模型池临时配置，跑完还原）；
  - 证据汇总 summary.json＋出站规则静态抽检 outbound_scan.txt。

用法（程序/ 下）：
  python scripts/acceptance_e2e_probe.py --evidence-dir tasks_round/evidence/R3800
"""
import argparse
import base64
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'tests'))
sys.path.insert(0, str(HERE / 'scripts'))
import app_logging  # noqa: E402  验收探针尽力而为路径留痕
import file_cache  # noqa: E402  正式 JSON 读唯一入口

MODEL_ID = 'fake-acceptance-e2e-1'
KEY_ENV = 'FAKE_ACCEPTANCE_E2E_KEY'
WORKER = HERE / 'scripts' / 'acceptance_e2e_worker.py'
GUI_HIDDEN = HERE / 'scripts' / 'gui_hidden.py'
LEASE_KID = 'k-e2e'

# 本轮测试专用 RSA-2048 密钥对（与服务端 app/lease.py 同构；私钥仅存在于本探针内存，
# 只签 k-e2e 租约，不接触 k2026a 真实签名私钥）。
LEASE_N = int(
    'df59c67583b224d9f67265198adadb8cbb93d8e12b727b26755e4e50da28290ab69ce6f0d1fa9a3b'
    '14496023f5267b5b691ea0b36222c8e1ebb00346d2f287c36fb8dc45a83148c0494dddda3aa5941'
    'b8dba3fcd50f9edf8d247e5e057d8cc6b3f4b4b8d21055eccc1a88c443036d79efff48ca9af7d'
    'c80fdf81a99fffd4a4678db1ac173f0a95f7eecb5f111a68af64bfabc9c49aa1ffa959f762225a'
    'e3bbb7d9084972f4051abc7914ce8945cadf4a300fc92199af0c3db73fd7f0ae59594e2d4631b16'
    '858dacbce4ed734038494bf0de85af53082e02ee82d1707c7d8a69045a236591633a3750028fc52'
    '8e16edada5b9bc205fb24d27f07833542c34caff', 16)
LEASE_E = 65537
LEASE_D = int(
    '1a177abfafaad7f33e7f0ea075402bf5bcd400ba0d414a71abb460a1c15a7fb0e8b45ba6366178'
    '32fea3b3bf7f9c073d1e829d73573b890c1b646c7d919713951930174b6be29605208b2027a6424'
    '19316737390a0ad11c7c788eea9ce995d080a54d9769b2ced6e2e116a916cb07b6fefa6b9e7f8c'
    '050e6c9cd73eb650f8a44f6c1b09b3069d5603945e914a3889e4d59f4073e2a88cd865c390e8f'
    '05289223ca5c12ae7eab6b2c7c080870a877136f8edb43589575b6578be7d84bcb61884bf09bfb'
    '0424279825bac396db50bb4f8d43594ca5f24c63315f3187fa17f503cd5afe990068dd5cd430423'
    '6c42d363919b3e48c4e61b862c372b4b05a8937a79', 16)
_SHA256_PREFIX = bytes.fromhex('3031300d060960864801650304020105000420')

DOC_PROJECT = ('# 项目设定\n\n'
               '- 名称：验收样例·深夜修理铺E2E\n'
               '- 题材：都市奇幻\n'
               '- 时代背景：当代中国二线城市\n'
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

import acceptance_e2e_worker as e2e_worker  # noqa: E402  复用 DOC_SCRIPT 等常量
DOC_SCRIPT = e2e_worker.DOC_SCRIPT
DOCS = {1: DOC_PROJECT, 2: DOC_OUTLINE, 3: DOC_CHARACTER}
USAGE = {'prompt_tokens': 120, 'completion_tokens': 30, 'total_tokens': 150,
         'prompt_tokens_details': {'cached_tokens': 0}}


def _now():
    return datetime.now().isoformat(timespec='milliseconds')


def _write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                    encoding='utf-8')


def _read_json(path, default=None):
    try:
        return file_cache.read_json(Path(path))
    except (OSError, ValueError):
        return default


class SupplierState:
    def __init__(self, mode_path):
        self.lock = threading.Lock()
        self.seq = 0
        self.log = []
        self.responses = {}
        self.chunks_sent = {}
        self.mode_path = Path(mode_path) if mode_path else None

    def mode(self):
        if self.mode_path is None:
            return 'ok'
        data = _read_json(self.mode_path, {})
        return str((data or {}).get('mode') or 'ok')


class AccountState:
    def __init__(self):
        self.lock = threading.Lock()
        self.log = []
        self.codes = {}
        self.refresh = 'rt-e2e-1'
        self.grace_seconds = 8
        self.up = True


STATE = SupplierState(None)
ACCT = AccountState()
ACCT_PORT = [0]
EVIDENCE = [None]


def _b64e(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()


def sign_lease(payload, server_time):
    """与 app/lease.py Signer.sign 同构：b64e(json{v,kid,...}) + '.' + b64e(RSA签名)。"""
    payload = {**payload, 'iat_server': int(server_time)}
    body = _b64e(json.dumps({'v': 1, 'kid': LEASE_KID, **payload},
                            separators=(',', ':'), ensure_ascii=False).encode())
    digest_info = _SHA256_PREFIX + hashlib.sha256(body.encode('ascii')).digest()
    k = 256
    em = b'\x00\x01' + b'\xff' * (k - len(digest_info) - 3) + b'\x00' + digest_info
    sig = pow(int.from_bytes(em, 'big'), LEASE_D, LEASE_N)
    return body + '.' + _b64e(sig.to_bytes(k, 'big'))


def make_lease(device_id, now, state='trial', grace_seconds=None):
    now = int(now)
    grace = int(now + (ACCT.grace_seconds if grace_seconds is None else grace_seconds))
    trial_end = now + 3 * 86400
    period_end = now + 30 * 86400
    return sign_lease({'uid': 'u-e2e', 'sid': 's-e2e-1', 'did': str(device_id),
                       'state': state, 'plan': state, 'trial_ends_at': trial_end,
                       'period_end': period_end, 'issued_at': now,
                       'expires_at': min(now + 86400, trial_end),
                       'grace_until': min(grace, trial_end),
                       'nonce': 'e2enonce01'}, now)


class SupplierHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *a):
        pass

    def _read_body(self):
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            length = 0
        return self.rfile.read(length) if length else b''

    def _record(self, payload, stream):
        with STATE.lock:
            STATE.seq += 1
            seq = STATE.seq
            STATE.log.append({'seq': seq, 'at': _now(), 'path': self.path,
                              'stream': stream, 'model': (payload or {}).get('model'),
                              'mode': STATE.mode(), 'auth_present': bool(
                                  self.headers.get('Authorization')),
                              'body_bytes': len(getattr(self, '_raw_body', b''))})
        return seq

    def _sse_headers(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True

    def _sse_chunk(self, obj):
        self.wfile.write(('data: ' + json.dumps(obj, ensure_ascii=False) + '\n\n').encode('utf-8'))
        self.wfile.flush()

    def _finish_sse(self, seq):
        self._sse_chunk({'id': 'chatcmpl-fake-%d' % seq, 'choices': [
            {'delta': {}, 'finish_reason': 'stop'}], 'usage': USAGE})
        self.wfile.write(b'data: [DONE]\n\n')
        self.wfile.flush()

    def _reply_text(self, seq):
        # 角色卡→自然剧本的过渡调用：任务书要求模型只回 {"next_stage":"自然剧本"}。
        # 按请求内容识别（不依赖序号），避免辅助调用漂移导致错位。
        blob = getattr(self, '_raw_body', b'')
        try:
            blob = blob.decode('utf-8', 'replace')
        except Exception:
            blob = ''
        if '紧邻的“自然剧本”' in blob:
            return '{"next_stage":"自然剧本"}'
        return DOCS.get(seq, DOC_SCRIPT)

    def _stream(self, seq, chunks, delay=0.0):
        self._sse_headers()
        for chunk in chunks:
            if delay:
                time.sleep(delay)
            self._sse_chunk({'id': 'chatcmpl-fake-%d' % seq,
                             'choices': [{'delta': {'content': chunk}, 'finish_reason': None}]})
            with STATE.lock:
                STATE.chunks_sent[seq] = STATE.chunks_sent.get(seq, 0) + 1
        self._finish_sse(seq)

    def do_POST(self):
        raw = self._read_body()
        self._raw_body = raw
        try:
            payload = json.loads(raw.decode('utf-8', 'replace') or '{}')
        except ValueError:
            payload = {}
        stream = bool(payload.get('stream'))
        seq = self._record(payload, stream)
        mode = STATE.mode()
        finished = False
        note = ''
        try:
            if mode == 'error':
                body = json.dumps({'error': {'message': 'fake supplier failure',
                                             'type': 'server_error'}}).encode()
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif stream:
                text = self._reply_text(seq)
                chunks = [text[i:i + 8] for i in range(0, len(text), 8)] or [text]
                self._stream(seq, chunks, delay=0.35 if mode == 'slow' else 0.0)
            else:
                body = json.dumps({'id': 'chatcmpl-fake-%d' % seq, 'object': 'chat.completion',
                                   'created': int(time.time()),
                                   'model': payload.get('model') or MODEL_ID,
                                   'choices': [{'index': 0, 'message': {
                                       'role': 'assistant', 'content': self._reply_text(seq)},
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
                                    'chunks': STATE.chunks_sent.get(seq, 0), 'mode': mode}


class AccountHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *a):
        pass

    def _read_body(self):
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            length = 0
        return self.rfile.read(length) if length else b''

    def _send(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _record(self, kind, payload):
        with ACCT.lock:
            ACCT.log.append({'at': _now(), 'kind': kind, 'payload': payload})

    def _down(self):
        """worker 写入 evidence/account_down.json 后，本服务按「不可达」处理：直接断连。"""
        return EVIDENCE[0] is not None and (Path(EVIDENCE[0]) / 'account_down.json').is_file()

    def do_GET(self):
        if self._down():
            try:
                self.connection.shutdown(2)
            except OSError:
                pass
            self.connection.close()
            return
        path = urllib.parse.urlsplit(self.path).path
        if path == '/v1/meta':
            self._send(200, {'service': 'e2e-fake-account', 'version': 'e2e-1'})
        elif path == '/v1/me':
            self._record('me', {})
            self._send(200, {'user': {'id': 'u-e2e', 'email': 'e2e-acceptance@example.test'},
                             'lease': {'state': 'trial'}, 'server_time': int(time.time())})
        else:
            self._send(404, {'code': 'not_found', 'message': 'no such route'})

    def do_POST(self):
        if self._down():
            try:
                self.connection.shutdown(2)
            except OSError:
                pass
            self.connection.close()
            return
        raw = self._read_body()
        try:
            payload = json.loads(raw.decode('utf-8', 'replace') or '{}')
        except ValueError:
            payload = {}
        path = urllib.parse.urlsplit(self.path).path
        now = int(time.time())
        if path == '/v1/auth/email/code':
            email = str(payload.get('email') or '')
            with ACCT.lock:
                ACCT.codes[email] = '123456'
            self._record('send_code', {'email': email, 'purpose': payload.get('purpose')})
            self._send(200, {'sent': True})
        elif path == '/v1/auth/email/verify':
            device = payload.get('device') or {}
            device_id = str(device.get('id') or '')
            self._record('verify', {'email': payload.get('email'),
                                    'age_confirmed': payload.get('age_confirmed'),
                                    'device_id': device_id})
            lease = make_lease(device_id, now)
            with ACCT.lock:
                ACCT.refresh = 'rt-e2e-%d' % now
            self._send(200, {'lease': lease, 'refresh_token': ACCT.refresh,
                             'user': {'id': 'u-e2e', 'is_new': True, 'has_password': False},
                             'state': 'trial', 'server_time': now})
        elif path == '/v1/lease/renew':
            device_id = str(payload.get('device_id') or '')
            self._record('renew', {'device_id': device_id})
            lease = make_lease(device_id, now)
            with ACCT.lock:
                ACCT.refresh = 'rt-e2e-%d' % now
            self._send(200, {'lease': lease, 'refresh_token': ACCT.refresh,
                             'state': 'trial', 'server_time': now})
        elif path == '/v1/redeem':
            device_id = 'unknown'
            auth = self.headers.get('Authorization') or ''
            self._record('redeem', {'auth_present': bool(auth)})
            lease = make_lease(device_id, now, state='active', grace_seconds=30 * 86400)
            self._send(200, {'lease': lease, 'state': 'active', 'server_time': now})
        else:
            self._send(404, {'code': 'not_found', 'message': 'no such route'})


def make_project(root):
    from tests.ui_edges_support import make_minimal_project
    import orchestrator.stage_config as stage_config
    proj = make_minimal_project(str(root))
    stage_config.put(proj, 'script', model=MODEL_ID, skills=['pipeline-script-preparation'])
    stage_config.put(proj, 'script_structure', model=MODEL_ID,
                     skills=['pipeline-script-structure'])
    (Path(proj) / 'cost_profile.json').write_text(json.dumps({
        'budget_amount': '10.00',
        'price_table': {'currency': 'CNY', 'version': 'acceptance-e2e-v1',
                        'model_rates': {MODEL_ID: {'prompt_tokens': '0.000001',
                                                   'completion_tokens': '0.000002'}}},
    }, ensure_ascii=False), encoding='utf-8')
    return Path(proj)


def write_pool_config(port):
    path = HERE / '配置' / '宠物' / '配置.json'
    backup = path.with_suffix('.json.acceptance-bak')
    existed = path.exists()
    if existed:
        shutil.copyfile(path, backup)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {'label': '验收E2E假供应商', 'model': MODEL_ID,
              'base_url': 'http://127.0.0.1:%d' % port,
              'path': '/chat/completions', 'wire_api': 'chat',
              'key_env': KEY_ENV, 'provider': 'custom',
              'context_length': 200000,
              'model_rates': {'prompt_tokens': '0.000001',
                              'completion_tokens': '0.000002'}}
    path.write_text(json.dumps({'models': {MODEL_ID: record}},
                               ensure_ascii=False, indent=2), encoding='utf-8')
    return path, backup, existed


def spawn_worker(proj, evdir, account_port):
    """经 gui_hidden.py 在隐藏桌面拉起 worker；返回 Popen（子输出由 gui_hidden 写 log）。"""
    log = Path(evdir) / 'gui_e2e.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, '-B', str(GUI_HIDDEN), str(log), str(HERE), '--',
           sys.executable, '-B', str(WORKER),
           '--project', str(proj), '--evidence', str(evdir),
           '--account-port', str(account_port),
           '--key-n', format(LEASE_N, 'x'), '--key-e', str(LEASE_E),
           '--key-kid', LEASE_KID]
    env = dict(os.environ, DRAMA_HIDDEN_DESKTOP='1')
    env[KEY_ENV] = 'e2e-fake-key-not-real'
    return subprocess.Popen(cmd, cwd=str(HERE), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL), log


def collect_evidence(evdir, proj):
    evdir = Path(evdir)
    collected = {}
    for name in ('transcript.json',):
        try:
            from contract.stage_path_service import write_dir
            src = write_dir(proj, 'script') / '创意对话' / '对话.json'
        except Exception:
            src = proj / '01剧本准备' / '创意对话' / '对话.json'
        if src.is_file():
            shutil.copyfile(src, evdir / name)
            collected[name] = True
    ledger = proj / '工作流任务' / '宠物' / '请求台账.json'
    if ledger.is_file():
        shutil.copyfile(ledger, evdir / 'request_ledger_final.json')
        collected['request_ledger_final.json'] = True
    state, _err = __import__('acceptance_recovery_worker').preparation_state(proj)
    _write_json(evdir / 'preparation_state_final.json', state or {})
    collected['preparation_state_final.json'] = True
    return collected


def outbound_scan(evdir):
    """出站规则抽检：枚举直连出站调用点，与 http_client/白名单口径对照。"""
    lines = []
    patterns = ('urlopen', 'build_opener', 'requests.', 'http.client', 'socket.create_connection')
    roots = [HERE]
    hits = []
    for root in roots:
        for path in sorted(root.rglob('*.py')):
            if any(part in ('.git', '__pycache__', 'tests', 'tasks_round', 'scripts')
                   for part in path.parts):
                continue
            try:
                text = path.read_text(encoding='utf-8', errors='replace')
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if any(p in line for p in patterns) and 'urlopen' in line or \
                   'build_opener' in line or 'requests.' in line:
                    hits.append('%s:%d: %s' % (path.relative_to(HERE.parent), i,
                                              line.strip()[:160]))
    lines.append('# 出站调用点静态抽检（R3800）')
    lines.append('# 口径：新 JSON API 唯一入口 infra/http_client.request_json；'
                 'urlopen/build_opener 只许 http_client 与登记白名单（test_http_boundary 守卫）。')
    lines.append('# 命中 %d 处（含注释/字符串，需人工对照白名单）：' % len(hits))
    lines.extend(hits)
    (Path(evdir) / 'outbound_scan.txt').write_text('\n'.join(lines), encoding='utf-8')
    return {'hits': len(hits)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--evidence-dir', required=True)
    ap.add_argument('--account-grace-seconds', type=int, default=8)
    ap.add_argument('--offline-wait-seconds', type=float, default=15.0)
    args = ap.parse_args()

    evdir = Path(args.evidence_dir)
    evdir.mkdir(parents=True, exist_ok=True)
    import tempfile
    sandbox = Path(tempfile.mkdtemp(prefix='acceptance-e2e-'))
    proj = make_project(sandbox / 'p')
    EVIDENCE[0] = evdir
    STATE.mode_path = evdir / 'supplier_mode.json'
    _write_json(STATE.mode_path, {'mode': 'ok'})
    ACCT.grace_seconds = args.account_grace_seconds

    # 假供应商
    supplier = ThreadingHTTPServer(('127.0.0.1', 0), SupplierHandler)
    supplier_port = supplier.server_address[1]
    threading.Thread(target=supplier.serve_forever, daemon=True).start()

    # 假会员服务
    account_server = ThreadingHTTPServer(('127.0.0.1', 0), AccountHandler)
    ACCT_PORT[0] = account_server.server_address[1]
    threading.Thread(target=account_server.serve_forever, daemon=True).start()

    pool_path, pool_backup, pool_existed = write_pool_config(supplier_port)
    summary = {'started': _now(), 'project': str(proj), 'sandbox': str(sandbox),
               'supplier_port': supplier_port, 'account_port': ACCT_PORT[0],
               'model': MODEL_ID, 'lease_kid': LEASE_KID,
               'account_grace_seconds': args.account_grace_seconds}
    t0 = time.time()
    try:
        proc, log = spawn_worker(proj, evdir, ACCT_PORT[0])
        summary['worker_pid'] = proc.pid
        deadline = time.time() + 900
        while proc.poll() is None and time.time() < deadline:
            time.sleep(1.0)
        if proc.poll() is None:
            proc.kill()
            summary['worker_killed'] = True
        summary['worker_returncode'] = proc.poll()
        summary['worker_seconds'] = round(time.time() - t0, 3)

        # worker 结束后收尾：供应商日志、账号日志、项目证据
        with STATE.lock:
            summary['supplier_requests'] = list(STATE.log)
            summary['supplier_responses'] = dict(STATE.responses)
        with ACCT.lock:
            summary['account_requests'] = list(ACCT.log)

        result = _read_json(evdir / 'e2e_result.json', {})
        summary['e2e'] = result
        collected = collect_evidence(evdir, proj)
        summary['collected'] = collected
        summary['outbound_scan'] = outbound_scan(evdir)

        # 汇总判定（如实：缺证据即 False/未测）
        checks = {}
        checks['desktop_ready'] = bool(result.get('desktop_ready'))
        checks['script_raw_landed'] = bool((result.get('checks') or {}).get('script_raw_landed'))
        se = result.get('script_evidence') or {}
        checks['script_stage_evidence'] = bool(se.get('ok'))
        sr = result.get('stage_structure_run') or {}
        checks['stage_structure_run_ok'] = bool(sr.get('ok'))
        art = result.get('structure_artifact') or {}
        checks['structure_artifact_verified'] = bool(
            art.get('is_structured') and (art.get('evidence') or {}).get('ok'))
        pr = result.get('pause_resume') or {}
        checks['pause_blocks_next_stage'] = pr.get('paused_next_stage') is None and \
            bool((pr.get('paused_state') or {}).get('paused'))
        checks['resume_releases_stage'] = pr.get('resumed_first_stage') not in (None, '')
        cx = result.get('cancel') or {}
        checks['cancel_produces_ledger_entry'] = int(cx.get('ledger_after') or 0) > \
            int(cx.get('ledger_before') or 0)
        cl = result.get('cloud') or {}
        steps = {s.get('step'): s for s in (cl.get('steps') or [])}
        checks['cloud_meta_ok'] = bool((steps.get('meta') or {}).get('ok'))
        checks['cloud_request_code_ok'] = bool((steps.get('request_code') or {}).get('ok'))
        checks['cloud_login_ok'] = bool((steps.get('login') or {}).get('ok'))
        ent = cl.get('entitlement') or {}
        checks['cloud_entitlement_usable'] = bool(ent.get('usable'))
        gate = cl.get('stage_gate') or {}
        checks['paid_stage_open_when_usable'] = gate.get('storyboard_paid') == ''
        ent_off = cl.get('entitlement_after_offline') or {}
        gate_off = cl.get('stage_gate_after_offline') or {}
        checks['offline_entitlement_locked'] = ent_off.get('usable') is False
        checks['offline_paid_stage_blocked'] = bool(gate_off.get('storyboard_paid'))
        checks['offline_free_stage_open'] = gate_off.get('script_structure_free') == ''
        checks['local_artifact_survives_cloud_down'] = bool(
            (cl.get('local_op_after_cloud_down') or {}).get('structured_script_present'))
        summary['checks'] = checks
        summary['all_checks_passed'] = all(checks.values())
        summary['elapsed_seconds'] = round(time.time() - t0, 3)
    except Exception:
        summary['fatal'] = traceback.format_exc()[-2000:]
    finally:
        try:
            supplier.shutdown()
        except Exception:
            app_logging.swallowed()
        try:
            account_server.shutdown()
        except Exception:
            app_logging.swallowed()
        if pool_existed:
            shutil.copyfile(pool_backup, pool_path)
        else:
            try:
                pool_path.unlink()
            except OSError:
                pass
        summary['finished'] = _now()
        _write_json(evdir / 'summary.json', summary)
    print(json.dumps({'all_checks_passed': summary.get('all_checks_passed'),
                      'checks': summary.get('checks'),
                      'elapsed': summary.get('elapsed_seconds'),
                      'fatal': summary.get('fatal', '')[:300]},
                     ensure_ascii=False, indent=1))


def tempfile_mkdtemp():
    import tempfile
    return Path(tempfile.mkdtemp(prefix='acceptance-e2e-'))


if __name__ == '__main__':
    main()
