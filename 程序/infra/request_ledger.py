"""请求级可对账台账（自 pet_llm 拆出，L1）。

与 Token 台账（pet_llm.Ledger）分工：Token 台账算「当天花了多少」，这里回答「这一笔请求
怎么回事」——请求号、调用种类、估计还是实报、预留还是结算、关联哪个远端任务。
token／秒／次数各列各的，不把它们相加成金额；价格表可选，带上版本与日期；缺 usage 记
「未知」而不是 0。

RequestLedger 一条请求一行：预留 → 结算／未知／取消，同一请求号只认一笔（重试不重复结算）。
"""
import json
import hashlib
import time
import threading
from contextlib import contextmanager
from pathlib import Path

import infra.app_logging as app_logging
import contract.stage_layout as stage_layout
from agent.core import save, read

_REQUEST_LOCK = threading.RLock()
REQUEST_LOCK_WAIT_SECONDS = 10.0
REQUEST_LOCK_POLL_SECONDS = 0.02
REQUEST_RESERVED_STALE_SECONDS = 1800.0


class LedgerLockTimeout(ValueError):
    """台账文件锁在期限内未拿到；授权路径按 ValueError 语义抛出，结算路径降级记 unknown。"""

# ── O29 请求级可对账台账 ─────────────────────────────────────────────────────
# 与 Token 台账分工：Token 台账算「当天花了多少」，这里回答「这一笔请求怎么回事」——
# 请求号、调用种类、估计还是实报、预留还是结算、关联哪个远端任务。token／秒／次数
# 各列各的，不把它们相加成金额；价格表可选，带上版本与日期；缺 usage 记「未知」而不是 0。
REQUEST_LEDGER_PATH = (stage_layout.WORKFLOW_DIR, '宠物', '请求台账.json')
REQUEST_KINDS = ('tokens', 'seconds', 'images', 'videos', 'requests')
REQUEST_STATES = ('reserved', 'settled', 'unknown', 'cancelled', 'duplicate')
REQUEST_MODES = ('estimated', 'reported', 'unknown')


def request_ledger_path(project):
    return Path(project).joinpath(*REQUEST_LEDGER_PATH)


class BudgetRejected(ValueError):
    """请求未发送：金额预留未通过。"""


def _sweep_stale_reserved(entries, clock):
    """本地预留超时未结算改记 unknown：进程中途退出会遗留 reserved 长期占用预算。

    只扫没有 remote_task_id 的本地预留——远端任务有自己的轮询生命周期，不在此处裁决。
    """
    now = float(clock())
    for entry in entries:
        if (entry.get('state') == 'reserved' and not entry.get('remote_task_id')
                and now - float(entry.get('at') or 0) > REQUEST_RESERVED_STALE_SECONDS):
            entry['state'] = 'unknown'
            entry['mode'] = 'unknown'
            entry['amount'] = None
            if 'money_state' in entry:
                entry['money_state'] = 'unknown'
            entry['settled_at'] = now


@contextmanager
def _ledger_file_transaction(ledger):
    """文件锁等待在 ``_REQUEST_LOCK`` 之外轮询（有界、间隔见常量、片间 checkpoint），
    拿到文件锁后再进进程内锁做读—改—写，避免等锁期间阻塞本进程其它台账操作。"""
    if ledger.project is None:
        yield
        return
    path = request_ledger_path(ledger.project).with_suffix('.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    import msvcrt
    with path.open('a+b') as stream:
        # Windows 可锁定 EOF 之外的范围；锁前写入会与另一持锁者冲突。
        stream.seek(0)
        from contract.platform_tools import current_execution
        control = current_execution()
        deadline = time.monotonic() + REQUEST_LOCK_WAIT_SECONDS
        while True:
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise LedgerLockTimeout('请求台账正在更新，请稍后重试') from None
                if control is not None and hasattr(control, 'checkpoint'):
                    control.checkpoint()
                time.sleep(REQUEST_LOCK_POLL_SECONDS)
        try:
            with _REQUEST_LOCK:
                ledger.load()
                yield
                ledger.save()
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def _settle_lock_timeout(ledger, request_id, exc):
    """结算等锁超时不向上抛：付费结果已经产生。条目尽力记 unknown，落盘交给后续清扫对账。"""
    try:
        entry = ledger._find(request_id)
        if entry is not None and entry.get('state') == 'reserved':
            entry['state'] = 'unknown'
            entry['mode'] = 'unknown'
            entry['amount'] = None
            if 'money_state' in entry:
                entry['money_state'] = 'unknown'
            entry['settled_at'] = ledger._stamp(None)
    except Exception:
        app_logging.swallowed()
    try:
        from infra import diagnostic_capture
        diagnostic_capture.record_degradation(exc, stage='request-ledger')
    except Exception:
        app_logging.swallowed()


class RequestLedger:
    """一条请求一行：预留 → 结算／未知／取消，同一请求号只认一笔（重试不重复结算）。"""

    def __init__(self, project=None, clock=time.time):
        self.project = Path(project) if project else None
        self.clock = clock
        self.entries = []

    def _find(self, request_id, kind=None):
        rid = str(request_id)
        for entry in self.entries:
            if entry.get('id') == rid and (kind is None or entry.get('kind') == kind):
                return entry
        return None

    def _stamp(self, at):
        return float(self.clock() if at is None else at)

    def _remote_owner(self, remote_task_id):
        if not remote_task_id:
            return None
        for entry in self.entries:
            if entry.get('remote_task_id') == remote_task_id and entry.get('state') != 'duplicate':
                return entry
        return None

    def reserve(self, request_id, kind, amount, *, remote_task_id=None, note='', at=None):
        """先占一笔：同一请求号＋种类只占一次；已有就原样返回（重试不重复预留）。"""
        existing = self._find(request_id, kind)
        if existing is not None:
            return existing
        amount = self._quantity(amount)
        entry = {'id': str(request_id), 'kind': str(kind), 'amount': amount,
                 'mode': 'estimated', 'state': 'reserved', 'remote_task_id': None,
                 'note': str(note or ''), 'at': self._stamp(at), 'settled_at': None}
        self.entries.append(entry)
        if remote_task_id:
            self.link(request_id, remote_task_id)
        return entry

    def link(self, request_id, remote_task_id):
        """把请求号绑到远端任务号；同一远端任务只认第一笔账单，后来者标 duplicate。"""
        entry = self._find(request_id)
        if entry is None or not remote_task_id:
            return entry
        task = str(remote_task_id)
        owner = self._remote_owner(task)
        if owner is not None and owner.get('id') != entry.get('id'):
            entry['state'] = 'duplicate'
            entry['note'] = '同一远端任务已由请求 ' + str(owner.get('id')) + ' 记账，本笔不重复结算'
            return entry
        entry['remote_task_id'] = task
        return entry

    def settle(self, request_id, *, kind=None, amount=None, usage=None, mode='reported',
               remote_task_id=None, note='', at=None):
        """结算实报量：同一请求号只写一次，重复调用只是覆盖，不会翻倍。"""
        entry = self._find(request_id, kind)
        if entry is None:
            entry = self.reserve(request_id, kind or ('tokens' if usage is not None else 'requests'), 0)
        if entry.get('state') == 'duplicate':
            return entry
        if amount is None and isinstance(usage, dict):
            total = usage.get('total_tokens')
            if total is None:
                total = (usage.get('prompt_tokens') or 0) + (usage.get('completion_tokens') or 0)
            amount = total
        if amount is None:
            return self.mark_unknown(request_id, reason=note or '结算时没有可用量', at=at)
        entry['amount'] = self._quantity(amount)
        entry['mode'] = str(mode)
        entry['state'] = 'settled'
        entry['settled_at'] = self._stamp(at)
        if remote_task_id:
            entry['remote_task_id'] = str(remote_task_id)
        if note:
            entry['note'] = str(note)
        return entry

    def mark_unknown(self, request_id, *, reason='', at=None):
        """用量的确不知道时记「未知」：既不记 0（会显示成免费），也不丢这笔账。"""
        entry = self._find(request_id)
        if entry is None:
            entry = self.reserve(request_id, 'requests', 0)
        if entry.get('state') == 'duplicate':
            return entry
        entry['state'] = 'unknown'
        entry['mode'] = 'unknown'
        entry['amount'] = None
        entry['settled_at'] = self._stamp(at)
        if reason:
            entry['note'] = str(reason)
        return entry

    def cancel(self, request_id, *, reason='', at=None):
        """取消只改本机记录：不伪造远端退款，也不抹掉已经实报的用量。"""
        entry = self._find(request_id)
        if entry is None:
            return None
        entry['state'] = 'cancelled'
        entry['cancelled_at'] = self._stamp(at)
        if entry.get('mode') != 'reported':
            entry['mode'] = 'unknown'
            entry['amount'] = None
        if reason:
            entry['note'] = str(reason)
        return entry

    def report(self, price_table=None, currency='CNY'):
        """汇总：token／秒／次数各列各的，另给未知、重复、取消的编号；配了价格表才折算金额。"""
        kinds = {kind: {'settled': 0.0, 'reserved': 0.0, 'unknown': 0, 'count': 0}
                 for kind in REQUEST_KINDS}
        unknown, duplicates, cancelled = [], [], []
        for entry in self.entries:
            if entry.get('cost_only'):
                continue
            kind = entry.get('kind')
            bucket = kinds.setdefault(kind, {'settled': 0.0, 'reserved': 0.0, 'unknown': 0, 'count': 0})
            state = entry.get('state')
            if state == 'duplicate':
                duplicates.append(entry.get('id'))
                continue
            bucket['count'] += 1
            if state == 'cancelled':
                # 取消不退款：已经实报的量继续计，没上报的算未知，都不记 0。
                cancelled.append(entry.get('id'))
                if entry.get('mode') == 'reported' and entry.get('amount') is not None:
                    bucket['settled'] += float(entry['amount'])
                else:
                    bucket['unknown'] += 1
                    unknown.append(entry.get('id'))
                continue
            if state == 'unknown' or entry.get('mode') == 'unknown':
                bucket['unknown'] += 1
                unknown.append(entry.get('id'))
                continue
            if state == 'settled':
                bucket['settled'] += float(entry.get('amount') or 0)
            elif state == 'reserved':
                bucket['reserved'] += float(entry.get('amount') or 0)
        out = {'kinds': kinds, 'unknown_ids': unknown, 'duplicate_ids': duplicates,
               'cancelled_ids': cancelled,
               'requests': sum(bucket['count'] for bucket in kinds.values())}
        if price_table:
            out['money'] = self.price(kinds, price_table, currency)
            out['money']['estimated_requests'] = sum(
                1 for entry in self.entries if entry.get('state') == 'settled' and entry.get('mode') == 'estimated')
            if out['money']['estimated_requests']:out['money']['complete'] = False
        if price_table and any('money_state' in row for row in self.entries):
            out['money'] = self.priced_models(price_table, currency)
        out['model_costs'] = self.model_costs()
        return out

    @staticmethod
    def effective_money_state(row):
        """失效账单只降级读视图，不抹去原金额或核对历史。"""
        state = row.get('money_state')
        if state != 'reconciled':
            return state
        history = row.get('cost_reconciliations')
        if not isinstance(history, list) or not history or not isinstance(history[-1], dict):
            return 'unknown'
        audit = history[-1]
        if audit.get('amount') != row.get('budget_cost') or audit.get('currency') != row.get('currency'):
            return 'unknown'
        try:
            digest = hashlib.sha256()
            with Path(audit['evidence_path']).open('rb') as stream:
                for chunk in iter(lambda: stream.read(65536), b''):
                    digest.update(chunk)
            return 'reconciled' if digest.hexdigest() == audit.get('evidence_sha256') else 'unknown'
        except (OSError, ValueError, TypeError, KeyError):
            return 'unknown'

    def priced_models(self, price_table, currency):
        legacy = RequestLedger()
        legacy.entries = [row for row in self.entries if 'money_state' not in row and not row.get('cost_group')]
        money = legacy.report(price_table, currency)['money']
        spent, held = self.decimal(money['settled_amount']), self.decimal(money['reserved_amount'])
        versions = set()
        for row in self.entries:
            if 'money_state' not in row or row.get('state') == 'duplicate':
                continue
            versions.add(str(row.get('price_version') or 'unknown'))
            cost = row.get('budget_cost')
            if cost is None or row.get('currency') != money['currency']:
                money['missing_rates'].append(str(row.get('model') or 'unknown'))
                money['complete'] = False
                continue
            state = self.effective_money_state(row)
            if state in ('estimated', 'reconciled'):
                spent += self.decimal(cost)
            else:
                held += self.decimal(cost)
                money['complete'] = False
                if state == 'unknown':
                    money['unknown_requests'] += 1
        money.update(settled_amount=float(round(spent, 4)), reserved_amount=float(round(held, 4)),
                     amount=float(round(spent + held, 4)), frozen_model_price_versions=sorted(versions))
        return money

    def model_costs(self):
        groups = {}
        for row in self.entries:
            if 'money_state' not in row or row.get('state') == 'duplicate':
                continue
            currency = str(row.get('currency') or '币种未配置')
            group = groups.setdefault(currency, {'estimated_spent': '0', 'reconciled_spent': '0', 'held': '0', 'unknown': 0, 'stale_receipts': 0})
            state = self.effective_money_state(row)
            if row['money_state'] == 'reconciled' and state != 'reconciled':
                group['stale_receipts'] += 1
            if row.get('budget_cost') is None or state == 'unknown':
                group['unknown'] += 1
            if row.get('budget_cost') is not None:
                key = {'estimated': 'estimated_spent', 'reconciled': 'reconciled_spent'}.get(state, 'held')
                group[key] = str(self.decimal(group[key]) + self.decimal(row['budget_cost']))
        return groups

    @staticmethod
    def _quantity(value):
        import math
        if isinstance(value, bool):raise ValueError('用量或费率必须是有限非负数')
        try: number = float(value)
        except (ValueError, TypeError):raise ValueError('用量或费率必须是有限非负数') from None
        if not math.isfinite(number) or number < 0:raise ValueError('用量或费率必须是有限非负数')
        return number

    @staticmethod
    def price(kinds, price_table, currency='CNY'):
        """只有配了价格表才折算金额；带上价格表的版本／日期，缺费率不猜。"""
        table = price_table if isinstance(price_table, dict) else {}
        rates = table.get('rates') if isinstance(table.get('rates'), dict) else {}
        from decimal import Decimal
        settled, reserved, missing, unknown = Decimal(0), Decimal(0), [], 0
        for kind, bucket in kinds.items():
            unknown += bucket.get('unknown', 0)
            rate = rates.get(kind)
            if rate is None:
                if bucket.get('settled') or bucket.get('reserved'):
                    missing.append(kind)
                continue
            rate = Decimal(str(RequestLedger._quantity(rate)))
            settled += Decimal(str(RequestLedger._quantity(bucket.get('settled', 0)))) * rate
            reserved += Decimal(str(RequestLedger._quantity(bucket.get('reserved', 0)))) * rate
        settled_amount = round(settled, 4)
        reserved_amount = round(reserved, 4)
        return {'amount': float(settled_amount + reserved_amount),
                'settled_amount': float(settled_amount), 'reserved_amount': float(reserved_amount),
                'unknown_requests': unknown, 'complete': not missing and not unknown and not any(
                    bucket.get('reserved') for bucket in kinds.values()),
                'currency': str(table.get('currency') or currency),
                'table_version': table.get('version'), 'table_at': table.get('at'),
                'missing_rates': sorted(missing)}

    def save(self):
        if self.project is None:
            return None
        path = request_ledger_path(self.project)
        save(path, {'updated_at': self.clock(), 'entries': self.entries})
        return path

    def load(self):
        if self.project is None:
            return self
        from agent.core import read
        path = request_ledger_path(self.project)
        data = read(path) if path.exists() else {'entries': []}
        if (not isinstance(data, dict) or not isinstance(data.get('entries'), list)
                or any(not isinstance(row, dict) for row in data['entries'])):
            raise ValueError('请求台账损坏，请恢复后继续')
        self.entries = data['entries']
        _sweep_stale_reserved(self.entries, self.clock)
        return self

    def transaction(self):
        """重新读盘、检查、保存共用同一把跨进程锁，防止并发覆盖与超支。"""
        return _ledger_file_transaction(self)

    @staticmethod
    def decimal(value):
        from decimal import Decimal, InvalidOperation
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValueError('金额和费率必须是有限非负数') from None
        if isinstance(value, bool) or not result.is_finite() or result < 0:
            raise ValueError('金额和费率必须是有限非负数')
        return result

    def authorize_model(self, request_id, model, stage, input_estimate, output_limit):
        """冻结配置费率及估计用量；启用金额上限后，未知费用不能按零继续。"""
        if type(input_estimate) is not int or input_estimate < 0 or type(output_limit) is not int or output_limit < 0:
            raise ValueError('请求用量预估必须是非负整数')
        return self.authorize_units(request_id, model, stage, 'tokens',
                                    {'prompt_tokens': input_estimate, 'completion_tokens': output_limit})

    @classmethod
    def _model_price(cls, table, model, quantities):
        rate_map = table.get('model_rates') or {}
        if not isinstance(rate_map, dict):
            raise ValueError('模型费率格式不正确')
        rates = rate_map.get(model)
        known = isinstance(rates, dict) and all(key in rates for key in quantities)
        known = known and bool(table.get('version')) and bool(table.get('currency'))
        rates = {key: str(cls.decimal(rates[key])) for key in quantities} if known else None
        cost = sum((value * cls.decimal(rates[key]) for key, value in quantities.items()), cls.decimal(0)) if rates else None
        return rates, cost

    def preview_units(self, model, kind, quantities):
        """只读批次报价快照；不建账、不预留，执行时仍逐请求原子检查。"""
        from agent.core import read
        if not quantities or kind not in REQUEST_KINDS:
            raise ValueError('请求用量单位不能为空或未知')
        quantities = {key: self.decimal(value) for key, value in quantities.items()}
        self.load()
        path = self.project / 'cost_profile.json' if self.project else None
        profile = read(path) if path is not None and path.exists() else {}
        if not isinstance(profile, dict) or not isinstance(profile.get('price_table', {}), dict):
            raise ValueError('成本配置格式不正确')
        table = profile.get('price_table', {})
        _rates, cost = self._model_price(table, model, quantities)
        cap = self.decimal(profile['budget_amount']) if profile.get('budget_amount') is not None else None
        reasons = []
        if cost is None:
            reasons.append('金额预算需要模型费率、币种和价格表版本，请先配置')
        if kind == 'tokens' and quantities.get('completion_tokens', 0) <= 0:
            reasons.append('金额预算需要明确的输出Token上限')
        used = self.decimal(0)
        try:
            self.check_legacy_video_costs('')
        except ValueError as exc:
            reasons.append(str(exc)); used = None
        for row in self.entries:
            if row.get('state') == 'duplicate' or row.get('cost_group'):
                continue
            if row.get('money_state') == 'reconciled' and self.effective_money_state(row) != 'reconciled':
                reasons.append('账单凭据缺失或已变化，请重新核对费用'); used = None
            if row.get('budget_cost') is None or row.get('currency') != table.get('currency'):
                reasons.append('存在未计价费用或币种不一致，请核对后继续'); used = None
            elif used is not None:
                used += self.decimal(row['budget_cost'])
        if cap is not None and used is not None and cost is not None and used + cost > cap:
            reasons.append('超过项目金额预算，请核对费用或明确提高预算后重试')
        return {'model': model, 'currency': table.get('currency'), 'price_version': table.get('version'),
                'cost': str(cost) if cost is not None else None,
                'used': str(used) if used is not None else None,
                'cap': str(cap) if cap is not None else None,
                'remaining': str(cap - used) if cap is not None and used is not None else None,
                'notes': list(dict.fromkeys(reasons)), 'allowed': cap is None or not reasons}

    def preview_text(self, model, kind, quantities):
        quote = self.preview_units(model, kind, quantities)
        if not quote['allowed']:
            raise ValueError('本批次金额预检未通过：' + '；'.join(quote['notes']))
        currency = quote['currency'] or '币种未配置'
        return ('模型：%s；价格版本：%s。\n本批预计：%s %s；项目已占用（含预留）：%s %s。\n'
                '项目金额上限：%s；剩余金额：%s。\n%s\n预估不锁定额度；每次发送前重新核验，实际账单需核对。') % (
                    model, quote['price_version'] or '未配置', quote['cost'] or '未知', currency,
                    quote['used'] if quote['used'] is not None else '未知', currency,
                    quote['cap'] if quote['cap'] is not None else '未启用',
                    quote['remaining'] if quote['remaining'] is not None else '未知', '；'.join(quote['notes']))

    def legacy_video_costs(self, request_id='', *, include_unpriced=False):
        """只读归组旧视频来源；只保存摘要，不保存提示词原文、配置或私有任务内容。"""
        groups = {}
        if self.project is None:
            return groups
        from agent.core import read
        def fingerprint(value):
            return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
        def add(workspace, key, source, value, *, pending=False, root_row=None):
            relative = workspace.relative_to(self.project).as_posix()
            gid = 'legacy-cost:' + fingerprint([relative, key])
            group = groups.setdefault(gid, {'label': relative + ' / ' + key, 'sources': [], 'pending': False, 'root_rows': []})
            group['sources'].append({'source': source, 'sha256': fingerprint(value)})
            group['pending'] |= pending
            if root_row is not None:
                group['root_rows'].append(root_row)
        workspaces = [self.project]
        cloud = self.project / 'cloud_video'
        if cloud.exists():
            workspaces.extend(sorted(path for path in cloud.iterdir() if path.is_dir()))
        for workspace in workspaces:
            legacy = self if workspace == self.project else RequestLedger(workspace).load()
            for row in legacy.entries:
                rid = str(row.get('id') or '')
                if row.get('state') == 'duplicate' or row.get('cost_only'):
                    continue
                if workspace == self.project and ('money_state' in row or not rid.startswith('video:')):
                    continue
                accounted = self._find(rid, row.get('kind'))
                if workspace != self.project and accounted and 'money_state' in accounted and not accounted.get('cost_only'):
                    continue
                key = rid.rsplit(':', 1)[0] if rid.startswith('video:') and rid.endswith((':count', ':seconds')) else rid
                add(workspace, key, 'ledger:' + rid + ':' + str(row.get('kind')),
                    {k: v for k, v in row.items() if k != 'cost_group'},
                    pending=row.get('state') == 'reserved', root_row=row if workspace == self.project else None)
            path = workspace / 'data' / 'state.json'
            if not path.exists():
                continue
            state = read(path)
            shots = state.get('shots') if isinstance(state, dict) else None
            if not isinstance(shots, dict) or any(not isinstance(vs, list) for vs in shots.values()):
                raise ValueError('旧视频任务状态损坏，无法核对历史费用：' + workspace.name)
            for sid, versions in shots.items():
                for index, version in enumerate(versions, 1):
                    if not isinstance(version, dict):
                        raise ValueError('旧视频任务记录损坏，无法核对历史费用')
                    if version.get('not_submitted') is True:
                        continue
                    rid = version.get('money_request_id') or 'video:' + str(version.get('local_request', ''))
                    accounted = self._find(rid)
                    if rid == request_id or (accounted and 'money_state' in accounted and not accounted.get('cost_only')):
                        continue
                    key = f"video:{sid}:v{version.get('version', index)}"
                    add(workspace, key, 'task:' + key, version,
                        pending=version.get('state') in ('submitting', 'queued', 'running'))
        for path in sorted((self.project / 'workflows').glob('comfy_*.json')):
            job = read(path)
            if not isinstance(job, dict):
                raise ValueError('旧Comfy任务记录损坏，无法核对历史费用：' + path.name)
            graph = job.get('workflow', {})
            if not isinstance(graph, dict):
                raise ValueError('旧Comfy工作流损坏，无法核对历史费用：' + path.name)
            cloud_image = any(isinstance(node, dict) and node.get('class_type') == 'DramaCloudImage'
                              for node in graph.values())
            if not cloud_image and not include_unpriced:
                continue
            rid = job.get('cost_request_id')
            accounted = self._find(rid) if rid else None
            if (rid and rid == request_id) or (accounted and 'money_state' in accounted and not accounted.get('cost_only')):
                continue
            if job.get('not_submitted') is True:continue
            key = 'comfy:' + path.name
            add(self.project, key, 'comfy-task:' + path.name, job,
                pending=job.get('state') in ('submitting', 'queued', 'running'))
            if not cloud_image:
                groups['legacy-cost:' + fingerprint(['.', key])]['unit'] = 'requests'
        for group in groups.values():
            group['sources'].sort(key=lambda source: (source['source'], source['sha256']))
            group['digest'] = fingerprint(group['sources'])
        return groups

    def check_legacy_video_costs(self, request_id):
        for gid, group in self.legacy_video_costs(request_id, include_unpriced=True).items():
            entry = self._find(gid)
            if entry is None or entry.get('legacy_digest') != group['digest']:
                label = ('旧Comfy工作流费用' if group.get('unit') == 'requests'
                         else '旧Comfy云图片费用' if any(s['source'].startswith('comfy-task:') for s in group['sources'])
                         else '旧视频任务费用' if any(s['source'].startswith('task:') for s in group['sources']) else '旧视频会话费用')
                raise ValueError(label + '尚未纳入项目总账或来源已变化，请导入后核对：' + group['label'])

    def import_legacy_video_costs(self, *, include_unpriced=False):
        """显式导入未知费用；源会话不修改，来源变化使原金额失效并保留审计。"""
        changed = 0
        with self.transaction():
            groups = self.legacy_video_costs(include_unpriced=include_unpriced)
            for gid, group in groups.items():
                entry = self._find(gid)
                if entry is not None and entry.get('legacy_digest') == group['digest']:
                    continue
                if entry is None:
                    comfy = any(s['source'].startswith('comfy-task:') for s in group['sources'])
                    entry = self.reserve(gid, group.get('unit', 'images' if comfy else 'videos'), 0)
                    entry.update(cost_only=True, stage='legacy-comfy' if comfy else 'legacy-video')
                else:
                    entry.setdefault('legacy_changes', []).append({
                        'at': self.clock(), 'digest': entry.get('legacy_digest'),
                        'budget_cost': entry.get('budget_cost'), 'money_state': entry.get('money_state')})
                entry.update(legacy_digest=group['digest'], legacy_sources=group['sources'],
                             legacy_label=group['label'], money_state='unknown', budget_cost=None,
                             state='reserved' if group['pending'] else 'unknown', mode='unknown')
                for row in group['root_rows']:
                    row['cost_group'] = gid
                changed += 1
        return changed

    def authorize_units(self, request_id, model, stage, kind, quantities, *, amount=None):
        """所有模型共用金额上限；按明确计费单位冻结预留。"""
        from agent.core import read
        if not quantities or kind not in REQUEST_KINDS:
            raise ValueError('请求用量单位不能为空或未知')
        quantities = {key: self.decimal(value) for key, value in quantities.items()}
        with self.transaction():
            if self._find(request_id) is not None:
                raise ValueError('该请求已有记录，请核对原任务，不能重复发送')
            path = self.project / 'cost_profile.json' if self.project else None
            profile = read(path) if path is not None and path.exists() else {}
            if not isinstance(profile, dict):
                raise ValueError('成本配置格式不正确')
            table = profile.get('price_table') or {}
            if not isinstance(table, dict):
                raise ValueError('价格表格式不正确')
            cap = profile.get('budget_amount')
            if cap is not None:
                cap = self.decimal(cap)
                self.check_legacy_video_costs(request_id)
                if kind == 'tokens' and quantities.get('completion_tokens', 0) <= 0:
                    raise ValueError('金额预算需要明确的输出Token上限')
            rates, cost = self._model_price(table, model, quantities)
            if cap is not None:
                if not rates or not table.get('version') or not table.get('currency'):
                    raise ValueError('金额预算需要模型费率、币种和价格表版本，请先配置')
                used = self.decimal(0)
                for row in self.entries:
                    if row.get('state') == 'duplicate' or row.get('cost_group'):
                        continue
                    if row.get('money_state') == 'reconciled' and self.effective_money_state(row) != 'reconciled':
                        raise ValueError('账单凭据缺失或已变化，请重新核对费用')
                    money = row.get('budget_cost')
                    if money is None or row.get('currency') != table['currency']:
                        raise ValueError('存在未计价费用或币种不一致，请核对后继续')
                    used += self.decimal(money)
                if used + cost > cap:
                    raise ValueError('超过项目金额预算，请核对费用或明确提高预算后重试')
            entry = self.reserve(request_id, kind, sum(quantities.values()) if amount is None else amount)
            entry.update(model=model, stage=stage, input_estimate=float(quantities.get('prompt_tokens', 0)),
                         output_limit=float(quantities.get('completion_tokens', 0)),
                         quantities={key: str(value) for key, value in quantities.items()},
                         rates=rates, price_version=table.get('version'), currency=table.get('currency'),
                         budget_cost=str(cost) if cost is not None else None, money_state='reserved')
            return dict(entry)

    @contextmanager
    def metered_units(self, request_id, model, stage, kind, amount, *, quantities=None):
        """成功产物按单价估算；任何发送后异常都不自动释放额度。"""
        try:
            self.authorize_units(request_id, model, stage, kind, quantities if quantities is not None else {kind: amount}, amount=amount)
        except (ValueError, OSError) as exc:
            raise BudgetRejected(str(exc)) from exc
        try:
            yield
        except Exception:
            self.settle_units(request_id)
            raise
        else:
            self.settle_units(request_id, amount=amount)

    def settle_units(self, request_id, *, amount=None, remote_task_id=None):
        """异步生成与同步请求共享结算；未知不释放费用，重复回执不重复计费。"""
        try:
            with self.transaction():
                entry = self._find(request_id)
                if entry is None:
                    raise ValueError('请求预留记录缺失')
                if entry.get('money_state') == 'reconciled':
                    return
                if remote_task_id:
                    self.link(request_id, remote_task_id)
                if entry.get('state') == 'duplicate' or entry.get('money_state') in ('estimated', 'reconciled'):
                    return
                if amount is None:
                    self.mark_unknown(request_id)
                    entry['money_state'] = 'unknown'
                else:
                    self.settle(request_id, amount=amount, mode='estimated')
                    entry['money_state'] = 'estimated'
        except LedgerLockTimeout as exc:
            _settle_lock_timeout(self, request_id, exc)

    def settle_model(self, request_id, usage):
        """费用按冻结费率估算；未报齐输入/输出用量时保留全部预留，不假装退款。"""
        try:
            with self.transaction():
                entry = self._find(request_id)
                if entry is None:
                    raise ValueError('请求预留记录缺失')
                if entry.get('money_state') == 'reconciled' or (entry.get('state') == 'settled' and entry.get('money_state') == 'estimated'):
                    return
                keys = ('prompt_tokens', 'completion_tokens');known = all(type(usage.get(key)) is int and usage[key] >= 0 for key in keys)
                if not known:
                    self.mark_unknown(request_id)
                    entry['money_state'] = 'unknown'
                    return
                self.settle(request_id, usage=usage)
                rates = entry.get('rates')
                cost = sum((self.decimal(usage[key]) * self.decimal(rates[key]) for key in keys), self.decimal(0)) if rates else None
                entry.update(budget_cost=str(cost) if cost is not None else None, money_state='estimated')
        except LedgerLockTimeout as exc:
            _settle_lock_timeout(self, request_id, exc)
            return
        _record_model_usage(self.project, request_id, entry)  # 费用统计模块挂接：失败只记日志

    def reconcile_cost(self, request_id, kind, amount, currency, evidence, reviewer):
        """人工核对请求的最终账单金额，保留每次修订，不改变远端任务状态。"""
        amount = self.decimal(amount)
        currency, reviewer = str(currency).strip().upper(), str(reviewer).strip()
        if len(currency) != 3 or not currency.isascii() or not currency.isalpha() or not reviewer:
            raise ValueError('请填写三字母币种和核对人')
        path = Path(evidence)
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError('请选择非空的本地账单凭据文件')
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(65536), b''):
                digest.update(chunk)
        with self.transaction():
            entry = self._find(request_id, kind)
            if entry is None or entry.get('state') not in ('unknown', 'settled', 'cancelled'):
                raise ValueError('只能核对已结算、未知或已取消请求，进行中请求请先查询最终结果')
            if entry.get('cost_group'):
                raise ValueError('该用量已合并，请核对对应的旧视频费用组')
            if entry.get('cost_only'):
                current = self.legacy_video_costs(include_unpriced=True).get(request_id)
                if current is None or current['digest'] != entry.get('legacy_digest'):
                    raise ValueError('旧生成记录来源已变化，请重新导入后核对')
            if entry.get('currency') and str(entry['currency']).upper() != currency:
                raise ValueError('币种与原请求不一致，不能直接覆盖或自动换汇')
            currency = entry.get('currency') or currency
            audit = {'amount': str(amount), 'currency': currency, 'reviewer': reviewer,
                     'evidence_path': str(path.resolve()), 'evidence_sha256': digest.hexdigest(),
                     'previous_amount': entry.get('budget_cost'), 'previous_money_state': entry.get('money_state')}
            if entry.get('legacy_digest'):
                audit['legacy_digest'] = entry['legacy_digest']
            history = entry.setdefault('cost_reconciliations', [])
            if not isinstance(history, list) or any(not isinstance(item, dict) for item in history):
                raise ValueError('费用核对记录损坏，请先恢复台账')
            if entry.get('money_state') == 'reconciled' and history and all(history[-1].get(key) == audit[key] for key in
                               ('amount', 'currency', 'reviewer', 'evidence_path', 'evidence_sha256')):
                return dict(entry)
            audit['at'] = self.clock()
            history.append(audit)
            entry.update(budget_cost=str(amount), currency=currency, money_state='reconciled')
            return dict(entry)


def record_request_attempt(ledger, request_id, *, status=None, error_class='', retry_after=None,
                           wire_api='', retry_count=0):
    """追加一次传输/协议尝试元数据，供故障分桶与重试审计；不改金额或状态。"""
    entry = ledger._find(request_id)
    if entry is None:
        return None
    attempts = entry.setdefault('attempts', [])
    if not isinstance(attempts, list):
        attempts = []
        entry['attempts'] = attempts
    attempts.append({
        'at': ledger._stamp(None),
        'status': status,
        'error_class': str(error_class or ''),
        'retry_after': retry_after,
        'wire_api': str(wire_api or ''),
        'retry_count': int(retry_count or 0),
    })
    return entry


def record_request(project, request_id, kind, amount, *, note='', mode='reported'):
    """把一笔已完成的付费请求写进项目请求台账；同一 request_id＋kind 只算一笔，重复调用只覆盖。

    生产路径上的记账不能影响制作：任何落盘或数据问题都只返回 None，不抛异常。
    不传远端任务号，避免按任务号去重把同一请求的两类用量（次数与秒数）误判为重复。"""
    try:
        ledger = RequestLedger(project)
        with ledger.transaction():
            ledger.reserve(request_id, kind, amount, note=note)
            ledger.settle(request_id, kind=kind, amount=amount, mode=mode, note=note)
        return ledger
    except (OSError, ValueError, TypeError):
        return None


def _record_model_usage(project, request_id, entry):
    """``settle_model`` 结算成功后的用量快照挂接（费用统计模块）。

    任何失败都只记一笔日志：记账绝不能弄断请求结算与生产调用。
    """
    if project is None or not isinstance(entry, dict) or entry.get('state') == 'duplicate':
        return
    try:
        from infra.usage_snapshot import get_snapshot
        get_snapshot(project).record_call(
            entry.get('stage'), entry.get('model'), int(entry.get('amount') or 0),
            cost=entry.get('budget_cost') or '', currency=entry.get('currency') or '',
            request_id=str(request_id))
    except Exception:
        app_logging.swallowed()
