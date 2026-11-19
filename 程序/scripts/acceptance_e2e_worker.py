# -*- coding: utf-8 -*-
"""桌面与云服务验收任务书 E 维取证 worker（R3800）：隐藏桌面里的端到端链路。

一个真实 Desktop 会话内顺序跑两条链：

本地制作链（L）：
  1. 剧本准备创意对话 send_message → 假供应商按序回「项目设定／剧本大纲／角色卡／自然剧本」；
     循环发「继续」直到 script_raw.md 落盘或轮数用尽（真实采用/落盘路径，不代写文件）。
  2. 自然剧本候选存在时走 stage_execution_service.adopt_natural_script（与文件面板
     「采用自然剧本」同一入口）。
  3. stage_exec.run(d, 'script_structure', trigger='manual') —— 与「手动制作结构剧本→
     直接执行」同一 runner（本地规则链，不调模型）：结构化正稿 script.md 经
     publish_stage_text 发布。
  4. stage_completion_service.completion_evidence 核验 script／script_structure。
  5. stage_flow.AUTO 暂停／恢复状态机实测（armed→pause→next_stage=None→resume→放行）。
  6. 取消：供应商慢速流 → interrupt_script_agent() → 台账/转录取证。
  7. 失败反馈：供应商 error 模式 → 观察用户可见失败信号。

受控云端链（C）：
  8. 进程内把 domain.account_client.request 的 opener 重定向到本机假会员服务
     （真实请求构造/JSON/错误映射/会话落盘全保留），并把 infra.lease_verifier.PUBLIC_KEYS
     加入本轮测试密钥对 kid=k-e2e（探针侧用纯 Python RSA-2048 签发真实格式租约）。
  9. account.request_code → account.login → entitlement/stage_gate 取证；
     假服务端把 grace_until 设为短窗，服务不可达后观察 paid 阶段拦截与免费阶段放行。

证据：--evidence 目录写 e2e_result.json（步骤、检查、台账、核验结果）。
用法（程序/ 下，隐藏桌面）：
  python scripts/gui_hidden.py <out> <程序目录> -- python scripts/acceptance_e2e_worker.py \
      --project <项目目录> --evidence <证据目录> --account-port <端口> --account-up 0|1
"""
import argparse
import importlib
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'scripts'))

import acceptance_recovery_worker as rw  # noqa: E402  复用 A/D 轮同一批取证助手

# 自然剧本正文：>800 字符、含「人物名：对白」标签，供本地规则结构化与 auto-save 阈值。
DOC_SCRIPT = (
    '# 自然剧本\n\n'
    '## 第一集 深夜修理铺\n\n'
    '【场景一：修理铺内·夜】\n\n'
    '陈麦：（俯身焊接）今晚最后一台，祖母留下的留声机。\n\n'
    '阿棠：（推门进来，雨水顺着发梢滴落）老板，我妈的旧怀表又不走了。\n\n'
    '陈麦：拿来吧。你的委托单上写着「修复记忆」，我这儿修的是时间。\n\n'
    '阿棠：时间也能修？\n\n'
    '陈麦：能。只要你还记得它原来走得有多准。\n\n'
    '【场景二：修理铺后间·夜】\n\n'
    '陈麦：（打开工作台暗格）这台机器三年前停的，停在我妈走的那晚。\n\n'
    '阿棠：（轻声）那今晚能修好吗？\n\n'
    '陈麦：不知道。但委托人付了双倍的定金——定金是用来买「试试看的勇气」的。\n\n'
    '阿棠：（把怀表放上台面）那我也押一把。修不好，我用一个月的外卖钱赔你。\n\n'
    '陈麦：（调试旋钮）走了。\n\n'
    '阿棠：（凑近听）真的走了……老板，你刚才的手在抖。\n\n'
    '陈麦：修表师傅的手，抖是常事。怕的是不敢接单。\n\n'
    '【场景三：街口·黎明前】\n\n'
    '阿棠：（跨上电动车）明晚我还来，带我表姐的旧钢琴。\n\n'
    '陈麦：（站在门口挥手）记得带够定金。\n\n'
    '阿棠：（回头喊）修不好就分期！\n\n'
    '【场景四：修理铺内·白天】\n\n'
    '陈麦：（擦拭工作台）留声机修好了，怀表也修好了，下一台是什么？\n\n'
    '（墙上的挂钟指向正午，秒针稳稳地走着。）\n\n'
    '陈麦：（轻声自语）今晚关门早一点，给自己也留一单。\n\n'
    '【场景五：修理铺门口·黄昏】\n\n'
    '阿棠：（抱着一台旧钢琴踏板）表姐说这玩意儿比她命还难伺候。\n\n'
    '陈麦：钢琴踏板不修声音，只修手感。你表姐弹琴用脚还是用手？\n\n'
    '阿棠：都用。她说踏板一沉，整个人就像踩进了小时候的雨里。\n\n'
    '陈麦：（接过踏板翻看）弹簧锈了，轴承缺油。不过这东西比留声机老得多，零件都是手工挫出来的。\n\n'
    '阿棠：修得好吗？\n\n'
    '陈麦：修不好也没关系——修的过程本身就是委托。\n\n'
    '阿棠：（笑）老板你这话比心理医生还贵。\n\n'
    '陈麦：定金已经收了，概不退换。\n\n'
    '【场景六：修理铺内·深夜】\n\n'
    '陈麦：（独自调试钢琴踏板）三年了，我修过的东西都还在走。\n\n'
    '（窗外港口的灯一盏盏熄灭，工作台的台灯是最后一盏。）\n\n'
    '陈麦：（合上工具箱）明天开门，继续修。\n\n'
    '待确认\n')

# 与 R3759 adopt 轮同一已验证简报格式：结构化字段触发四阶段确认流程与直连模型回复。
IDEA = ('故事梗概：海港城市的深夜修理铺「回声维修」里，老板陈麦接下「修复记忆」的委托，'
        '每集修好一件承载往事的物件；外卖骑手阿棠成为常客与见证者。\n'
        '故事角色：陈麦、阿棠\n'
        '故事题材：都市奇幻\n'
        '故事集数：12集\n'
        '单集时间：120秒\n'
        '故事画幅：9:16\n'
        '视频模型：MiniMax H3\n'
        '交付形态：只要 markdown 文档')


def _jlog(ev, name, payload):
    rw._write_json(Path(ev) / name, payload)


def _state_summary(proj):
    state, err = rw.preparation_state(proj)
    docs = []
    if isinstance(state, dict):
        docs = [{'stage': d.get('stage'), 'confirmed': d.get('confirmed') is True,
                 'path': d.get('path'), 'sha256': d.get('sha256')}
                for d in (state.get('documents') or []) if isinstance(d, dict)]
    brief = None
    try:
        from contract.stage_path_service import write_dir
        brief = (write_dir(Path(proj), 'script') / 'brief_complete.json').is_file()
    except Exception:
        brief = None
    return {'error': err, 'brief_complete': brief, 'documents': docs}


def _script_raw(proj):
    try:
        from contract.stage_path_service import write_dir
        p = write_dir(Path(proj), 'script') / 'script_raw.md'
        return p if p.is_file() else None
    except Exception:
        return None


def _natural_candidates(proj):
    try:
        from contract.script_contract import natural_script_paths
        return [str(p) for p in natural_script_paths(Path(proj))]
    except Exception:
        return []


def phase_local(d, win, proj, ev, rec):
    """本地制作链：创意对话→采用→剧本结构阶段→核验→暂停/取消/失败反馈。"""
    from contract.script_contract import resolve_script_source
    from orchestrator import stage_completion_service, stage_exec
    import orchestrator.stage_flow as stage_flow
    import stage_execution_service as ses

    # L1 启动：真实创意对话首条消息（简报格式）
    ok, _ = rw.send_idea(d, win, IDEA, timeout=150.0)
    rec['steps'].append({'step': 'idea_send', 'ok': bool(ok)})

    # L2 推进：循环「继续」，观察采用稿与 script_raw.md 落盘
    rounds = []
    source = None
    for i in range(10):
        rw.pump(win, 0.5)
        summary = _state_summary(proj)
        raw = _script_raw(proj)
        try:
            source = resolve_script_source(proj)
        except Exception:
            source = None
        row = {'round': i, 'prep': summary, 'script_raw': bool(raw),
               'source': str(source) if source else None,
               'candidates': _natural_candidates(proj)}
        rounds.append(row)
        _jlog(ev, 'prep_round_%d.json' % i, row)
        if raw is not None and source is not None:
            break
        try:
            ok, _ = rw.send_idea(d, win, '继续', timeout=150.0)
            row['send_ok'] = bool(ok)
        except ValueError as exc:
            # 上一请求仍在途（「模型正在回复中」）：不重复发送，等待其落盘后下轮再推进
            row['send_ok'] = False
            row['send_error'] = str(exc)[:120]
            rw.pump(win, 20.0)
    rec['prep_rounds'] = rounds
    rec['checks']['script_raw_landed'] = _script_raw(proj) is not None

    # L3 自然剧本采用（若聊天产出候选）：与文件面板「采用自然剧本」同一 L3 入口
    adopted = None
    candidates = _natural_candidates(proj)
    if candidates:
        try:
            adopted = ses.adopt_natural_script(proj, candidates[0])
            rec['steps'].append({'step': 'adopt_natural_script', 'ok': True,
                                 'path': str(adopted)})
        except Exception as exc:
            rec['steps'].append({'step': 'adopt_natural_script', 'ok': False,
                                 'error': str(exc)})
    rec['natural_candidates'] = candidates
    rec['adopted_natural_script'] = str(adopted) if adopted else None

    # L4 阶段完成核验（script）
    try:
        ok_ev, reason = stage_completion_service.completion_evidence(proj, 'script')
    except Exception as exc:
        ok_ev, reason = False, 'evidence_error: %s' % exc
    rec['script_evidence'] = {'ok': bool(ok_ev), 'reason': reason}

    # L5 本地制作链：手动制作结构剧本（与执行页「直接执行」同一 runner）
    stage_run = None
    try:
        stage_run = stage_exec.run(d, 'script_structure', trigger='manual')
    except Exception as exc:
        stage_run = {'ok': False, 'error': repr(exc), 'trace': traceback.format_exc()[-800:]}
    summary_run = {}
    if isinstance(stage_run, dict):
        summary_run = {'ok': stage_run.get('ok'), 'skipped': stage_run.get('skipped'),
                       'text': stage_run.get('text'),
                       'results': [{'tool': r.get('tool'), 'status': r.get('status'),
                                    'detail': str(r.get('detail'))[:160]}
                                   for r in (stage_run.get('results') or [])],
                       'errors': [str(e)[:200] for e in (stage_run.get('errors') or [])]}
    rec['stage_structure_run'] = summary_run

    # L6 产物核验：script.md + structure manifest + completion_evidence
    try:
        from contract.script_contract import structured_script_path, is_structured_script
        target = structured_script_path(proj)
        artifact = {'path': str(target) if target else None,
                    'is_structured': bool(target and is_structured_script(target))}
        if target and target.is_file():
            artifact['sha256'] = __import__('hashlib').sha256(target.read_bytes()).hexdigest()
            artifact['bytes'] = target.stat().st_size
    except Exception as exc:
        artifact = {'error': str(exc)}
    try:
        ok_ev2, reason2 = stage_completion_service.completion_evidence(proj, 'script_structure')
    except Exception as exc:
        ok_ev2, reason2 = False, 'evidence_error: %s' % exc
    artifact['evidence'] = {'ok': bool(ok_ev2), 'reason': reason2}
    rec['structure_artifact'] = artifact

    # L7 暂停/恢复：自动链状态机（armed→pause→next_stage=None→resume→放行→done 推进）
    pause_rec = {}
    try:
        stage_flow.AUTO.script_done('semi')
        pause_rec['armed'] = stage_flow.AUTO.state()
        stage_flow.AUTO.pause()
        pause_rec['paused_next_stage'] = stage_flow.AUTO.next_stage()
        pause_rec['paused_state'] = stage_flow.AUTO.state()
        stage_flow.AUTO.resume()
        first = stage_flow.AUTO.next_stage()
        pause_rec['resumed_first_stage'] = first
        if first:
            stage_flow.AUTO.done(first, ok=False, reason='e2e-probe')
        pause_rec['final_state'] = stage_flow.AUTO.state()
        stage_flow.AUTO.script_done('')   # 解除武装，避免心跳在会话余下时间里真派阶段
    except Exception as exc:
        pause_rec['error'] = repr(exc)
    rec['pause_resume'] = pause_rec

    # L8 取消：慢速供应商 + interrupt_script_agent（与 A 轮同一取消入口）
    cancel_rec = {}
    try:
        _jlog(ev, 'supplier_mode.json', {'mode': 'slow'})
        before_cancel = len(rw.ledger_entries(proj))
        ok_c, _ = rw.send_idea(d, win, '请再写一段场景二的 alternate take。', timeout=8)
        rw.pump(win, 1.5)
        try:
            d.interrupt_script_agent()
        except Exception as exc:
            cancel_rec['interrupt_error'] = repr(exc)
        rw.pump(win, 2.5)
        entries = rw.ledger_entries(proj)
        cancel_rec.update({'send_returned': bool(ok_c),
                           'ledger_before': before_cancel, 'ledger_after': len(entries),
                           'new_entries': entries[before_cancel:]})
        _jlog(ev, 'cancel_ledger.json', {'entries': entries[before_cancel:]})
    except Exception as exc:
        cancel_rec['error'] = repr(exc)
    rec['cancel'] = cancel_rec

    # L9 失败反馈：供应商 error 模式 → 用户可见失败信号
    fail_rec = {}
    try:
        _jlog(ev, 'supplier_mode.json', {'mode': 'error'})
        status_before = ''
        try:
            status_before = str(getattr(d, 'status', None).get() or '')
        except Exception:
            pass
        ok_f, _ = rw.send_idea(d, win, '失败反馈探针：请回复一个字。', timeout=30)
        rw.pump(win, 1.0)
        status_after = ''
        try:
            status_after = str(getattr(d, 'status', None).get() or '')
        except Exception:
            pass
        rows = rw.transcript_rows(proj)
        fail_rec.update({'send_returned': bool(ok_f), 'status_before': status_before[:200],
                         'status_after': status_after[:300],
                         'last_rows': rows[-3:]})
        _jlog(ev, 'failure_transcript_tail.json', {'rows': rows[-4:]})
    except Exception as exc:
        fail_rec['error'] = repr(exc)
    rec['failure_feedback'] = fail_rec
    _jlog(ev, 'supplier_mode.json', {'mode': 'ok'})
    return rec


def _patch_account_client(account_port):
    """把账号客户端的传输层重定向到本机假会员服务；请求构造/错误映射保持真实。"""
    import urllib.parse
    import urllib.request
    import domain.account_client as ac

    def local_opener(url, *, timeout=60, data=None, headers=None, method=None, context=None):
        parts = urllib.parse.urlsplit(str(url))
        target = 'http://127.0.0.1:%d%s%s' % (account_port, parts.path,
                                            ('?' + parts.query) if parts.query else '')
        req = urllib.request.Request(target, data=data, headers=dict(headers or {}), method=method)
        return urllib.request.urlopen(req, timeout=timeout)

    original = ac.request

    def rerouted(method, path, body=None, *, token='', opener=None, **kw):
        return original(method, path, body, token=token,
                        opener=opener or local_opener, **kw)

    ac.request = rerouted
    return {'patched': True, 'module': ac.__name__}


def _install_test_lease_key(n_hex, e_int, kid='k-e2e'):
    import infra.lease_verifier as lv
    lv.PUBLIC_KEYS[kid] = (int(n_hex, 16), int(e_int))
    return kid


def phase_cloud(d, win, proj, ev, rec, args):
    """受控云端链：假会员服务 + 真实 AccountController/租约验签/闸门。"""
    cloud = {'steps': []}
    kid = _install_test_lease_key(args.key_n, args.key_e, getattr(args, 'key_kid', 'k-e2e'))
    cloud['lease_key_installed'] = kid
    patch = _patch_account_client(args.account_port)
    cloud['client_patch'] = patch

    account = getattr(d, 'account', None)
    if account is None:
        try:
            account = d.account  # property 懒装配真实 AccountController
        except Exception as exc:
            cloud['steps'].append({'step': 'account_mount', 'ok': False, 'error': repr(exc)})
            rec['cloud'] = cloud
            return rec
    cloud['device_id'] = account.device_id

    results = {}

    def wait_result(key, timeout=30.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            rw.pump(win, 0.1)
            if key in results:
                return results.pop(key)
        return None

    email = 'e2e-acceptance@example.test'

    # C1 元数据 + 发送验证码（真实 client→HTTP→假服务链路）
    try:
        meta = account._client.meta()
        cloud['steps'].append({'step': 'meta', 'ok': bool(getattr(meta, 'ok', False)),
                               'code': (getattr(meta, 'data', None) or {}).get('code')})
    except Exception as exc:
        cloud['steps'].append({'step': 'meta', 'ok': False, 'error': repr(exc)})

    try:
        account.request_code(email, lambda r: results.__setitem__('code', r), purpose='login')
        r = wait_result('code')
        cloud['steps'].append({'step': 'request_code',
                               'ok': bool(r and getattr(r, 'ok', False)),
                               'detail': _result_brief(r)})
    except Exception as exc:
        cloud['steps'].append({'step': 'request_code', 'ok': False, 'error': repr(exc)})

    # C2 验证码登录（假服务端认固定码 123456；签发 k-e2e 租约）
    try:
        account.login(email, '123456', age_confirmed=True,
                      done=lambda r: results.__setitem__('login', r))
        r = wait_result('login', timeout=40.0)
        cloud['steps'].append({'step': 'login',
                               'ok': bool(r and getattr(r, 'ok', False)),
                               'detail': _result_brief(r)})
    except Exception as exc:
        cloud['steps'].append({'step': 'login', 'ok': False, 'error': repr(exc)})

    # C3 授权判定：登录后 entitlement / stage_gate（付费 vs 免费阶段）
    try:
        ent = account.entitlement()
        cloud['entitlement'] = {'state': getattr(ent, 'state', None),
                                'usable': bool(getattr(ent, 'usable', False)),
                                'payload_state': (getattr(ent, 'payload', None) or {}).get('state')}
        cloud['stage_gate'] = {
            'storyboard_paid': account.stage_gate('storyboard'),
            'script_structure_free': account.stage_gate('script_structure'),
            'script_free': account.stage_gate('script')}
        sess = account.session()
        cloud['session_keys'] = sorted(sess.keys())
    except Exception as exc:
        cloud['entitlement_error'] = repr(exc)

    # C4 云端不可达：写 account_down.json 让假服务断连 → 续签失败 → 宽限耗尽后闸门
    try:
        _jlog(ev, 'account_down.json', {'down_at': rw._now()})
    except Exception:
        pass
    try:
        account.renew(done=lambda r: results.__setitem__('renew_offline', r), quiet=False)
        r = wait_result('renew_offline', timeout=40.0)
        cloud['steps'].append({'step': 'renew_offline',
                               'ok': bool(r and getattr(r, 'ok', False)),
                               'detail': _result_brief(r)})
    except Exception as exc:
        cloud['steps'].append({'step': 'renew_offline', 'ok': False, 'error': repr(exc)})

    # 宽限窗由探针侧 lease 参数控制（grace_until≈签发+8s）：轮询到授权失效或超时
    offline_wait = []
    ent2 = None
    try:
        deadline = time.monotonic() + 25.0
        while time.monotonic() < deadline:
            rw.pump(win, 0.4)
            ent2 = account.entitlement()
            offline_wait.append({'t': round(time.monotonic() - (deadline - 25.0), 1),
                                 'state': getattr(ent2, 'state', None),
                                 'usable': bool(getattr(ent2, 'usable', False))})
            if not getattr(ent2, 'usable', False):
                break
            time.sleep(0.5)
    except Exception as exc:
        cloud['post_offline_error'] = repr(exc)
    cloud['entitlement_offline_trace'] = offline_wait[-6:]
    try:
        ent2 = account.entitlement()
        cloud['entitlement_after_offline'] = {
            'state': getattr(ent2, 'state', None), 'usable': bool(getattr(ent2, 'usable', False))}
        cloud['stage_gate_after_offline'] = {
            'storyboard_paid': account.stage_gate('storyboard'),
            'script_structure_free': account.stage_gate('script_structure')}
        cloud['session_after_offline'] = bool(account.session().get('lease'))
    except Exception as exc:
        cloud['post_offline_error'] = repr(exc)

    # C5 本地操作可继续性：账号锁定状态下免费阶段本地链仍可跑（结构剧本已在 L 段跑过；
    # 这里补一次轻量本地核验函数调用证明本地路径不依赖账号服务）
    try:
        from contract.script_contract import structured_script_path
        p = structured_script_path(proj)
        cloud['local_op_after_cloud_down'] = {
            'structured_script_present': bool(p and Path(p).is_file()),
            'note': 'script_structure 为免费阶段且本地规则执行，不经账号闸门与模型出站'}
    except Exception as exc:
        cloud['local_op_error'] = repr(exc)

    rec['cloud'] = cloud
    return rec


def _result_brief(r):
    if r is None:
        return 'no_result'
    data = getattr(r, 'data', None)
    brief = {'ok': bool(getattr(r, 'ok', False))}
    if isinstance(data, dict):
        brief['code'] = data.get('code')
        brief['status'] = data.get('status')
        if 'state' in data:
            brief['state'] = data.get('state')
    return brief


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True)
    ap.add_argument('--evidence', required=True)
    ap.add_argument('--account-port', type=int, default=0)
    ap.add_argument('--key-n', default='')
    ap.add_argument('--key-e', default='65537')
    ap.add_argument('--key-kid', default='k-e2e')
    ap.add_argument('--skip-cloud', action='store_true')
    args = ap.parse_args()

    ev = Path(args.evidence)
    ev.mkdir(parents=True, exist_ok=True)
    rec = {'started': datetime.now().isoformat(timespec='seconds'),
           'project': args.project, 'steps': [], 'checks': {}}
    t0 = time.time()
    win = d = None
    try:
        win, d, ready, _orig, _mod = rw.open_project_desktop(args.project)
        rec['desktop_ready'] = bool(ready)
        rec['steps'].append({'step': 'desktop_open', 'ok': bool(ready)})
        phase_local(d, win, Path(args.project), ev, rec)
        if not args.skip_cloud and args.account_port:
            phase_cloud(d, win, Path(args.project), ev, rec, args)
        else:
            rec['cloud'] = {'skipped': 'no account port'}
    except Exception:
        rec['fatal'] = traceback.format_exc()[-2000:]
    finally:
        rec['elapsed_seconds'] = round(time.time() - t0, 3)
        rec['finished'] = datetime.now().isoformat(timespec='seconds')
        _jlog(ev, 'e2e_result.json', rec)
        if win is not None:
            try:
                win.destroy()
            except Exception:
                pass
    print(json.dumps({'elapsed': rec.get('elapsed_seconds'),
                      'checks': rec.get('checks'),
                      'fatal': bool(rec.get('fatal'))}, ensure_ascii=False))


if __name__ == '__main__':
    main()
