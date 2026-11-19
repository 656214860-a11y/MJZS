"""模型调用计量的唯一序列：授权 → 发送 → 结算（R2178 J10）；重试口径也在这里显式命名（J12）。

``pet_llm`` 与 ``writing_api`` 原先各抄一份「估算 → authorize_model → 发送 → settle_model」，
现在都走这里；两处各自的诊断目录与 reason 文案不在此处，仍由调用方决定。
"""
import logging

import infra.app_logging as app_logging

LOGGER = logging.getLogger(__name__)


def _settle(ledger, request_id, usage, *, stage=''):
    """结算是兜底动作：等锁超时／保存失败时不丢已付费结果，降级记入诊断。"""
    try:
        ledger.settle_model(request_id, usage)
    except Exception as exc:
        LOGGER.warning('请求结算失败（%s），调用结果照常返回', type(exc).__name__)
        try:
            from infra import diagnostic_capture
            diagnostic_capture.record_degradation(exc, stage=stage, error_code='E-IO-WRITE')
        except Exception:
            app_logging.swallowed()


def _record_attempt(ledger, request_id, **fields):
    """尝试诊断是旁路记录：写盘失败只记日志，不影响已付费结果的返回。"""
    if not hasattr(ledger, '_find'):
        return
    try:
        from infra.request_ledger import record_request_attempt
        if getattr(ledger, 'project', None) is None:
            record_request_attempt(ledger, request_id, **fields)
        else:
            with ledger.transaction():
                record_request_attempt(ledger, request_id, **fields)
    except Exception:
        LOGGER.exception('请求尝试记录失败')


def metered(ledger, request, send, usage_of, on_result=None):
    """返回 ``(result, usage, rejected)``。

    ``request`` 是 ``(request_id, model, stage, estimate, reserved)``。授权被拒（ValueError／OSError）时
    ``rejected`` 为该错误、不发送、``result`` 为 None；发送抛错时按未知用量结算后原样抛出，
    所以发送里的 ValueError 不会被误当预算错误；``on_result(result, usage)`` 在结算前调用，供调用方记诊断，
    其异常只记录不外抛。发送成功后结算必达（try/finally），结算自身失败不丢结果。
    """
    request_id, model, stage, estimate, reserved = request
    try:
        ledger.authorize_model(request_id, model, stage, estimate, reserved)
    except (ValueError, OSError) as error:
        return None, {}, error
    try:
        result = send()
    except Exception:
        _settle(ledger, request_id, {}, stage=stage)
        _record_attempt(ledger, request_id, error_class='exception')
        raise
    usage = {}
    try:
        usage = usage_of(result)
        if on_result is not None:
            try:
                on_result(result, usage)
            except Exception:
                LOGGER.exception('计量结果回调失败')
        if isinstance(result, dict):
            meta = result.get('response_meta')
            _record_attempt(
                ledger,
                request_id,
                status=result.get('status'),
                error_class=result.get('error_class'),
                retry_after=result.get('retry_after'),
                wire_api=(meta or {}).get('wire_api', '') if isinstance(meta, dict) else '',
                retry_count=result.get('retry_count') or 0)
        else:
            _record_attempt(ledger, request_id, error_class='exception')
    finally:
        _settle(ledger, request_id, usage, stage=stage)
    return result, usage, None


def chat_metered(adapter, ledger, stage, messages, options, model, system):
    """直连 API 文本模型的一次对话也过计量：有台账就授权／结算，没有台账（无项目）就是普通调用。

    授权被拒时抛 ValueError（文案是预算原因），发送失败按未知用量结算后原样抛出；其余原样返回适配器结果。
    """
    import json
    from uuid import uuid4

    import infra.token_saver as token_saver
    keys = ('prompt_tokens', 'completion_tokens', 'cached_tokens')

    def send():
        return adapter.chat(messages, options=options, model=model, system=system)
    if ledger is None:
        return send()

    def usage_of(result):
        data = result.get('data')
        reported = token_saver.reported_usage(data.get('usage') if isinstance(data, dict) else {})
        return {key: reported[key] for key in keys if key in reported}
    estimate = len(json.dumps({'system': system, 'messages': messages, 'options': options},
                              ensure_ascii=False).encode('utf-8')) + 256
    result, _usage, refused = metered(ledger, (uuid4().hex, model, stage, estimate, int(options['max_tokens'])),
                                     send, usage_of)
    if refused is not None:
        raise ValueError(str(refused))
    return result


# ── 重试口径：两种请求性质，两种口径，各自显式命名（R2178 J12，不单方裁决）──────────────
# 对话可重放：同一段对话再发一次不会多收费或多做事，所以 5xx／429／超时／本地网络异常都可以重发。
# 状态 0（无 HTTP 响应）不在重放名单：它可能是本地构造的失败，重放口径交给调用方的降级链决定。
REPLAYABLE_RETRY_STATUS = (408, 409, 425, 429, 500, 502, 503, 504)


def replayable_retry(status):
    """对话（pet_llm 的降级／兜底重发）用：HTTP 状态是否值得原样再发一次。"""
    return status in REPLAYABLE_RETRY_STATUS


def submission_retryable(acceptance, reason_code):
    """媒体／任务提交用（model_router.failure_policy）：HTTP 5xx 可能已受理并计费，只有确认「未受理」的限流与服务端错误才重发。"""
    return acceptance == 'not_accepted' and reason_code in ('rate_limit', 'server_error')
