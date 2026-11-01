"""模型调用计量的唯一序列：授权 → 发送 → 结算（R2178 J10）。

``pet_llm`` 与 ``writing_api`` 原先各抄一份「估算 → authorize_model → 发送 → settle_model」，
现在都走这里；两处各自的诊断目录与 reason 文案不在此处，仍由调用方决定。
"""


def metered(ledger, request, send, usage_of, on_result=None):
    """返回 ``(result, usage, rejected)``。

    ``request`` 是 ``(request_id, model, stage, estimate, reserved)``。授权被拒（ValueError／OSError）时
    ``rejected`` 为该错误、不发送、``result`` 为 None；发送抛错时按未知用量结算后原样抛出，
    所以发送里的 ValueError 不会被误当预算错误；``on_result(result, usage)`` 在结算前调用，供调用方记诊断。
    """
    request_id, model, stage, estimate, reserved = request
    try:
        ledger.authorize_model(request_id, model, stage, estimate, reserved)
    except (ValueError, OSError) as error:
        return None, {}, error
    try:
        result = send()
    except Exception:
        ledger.settle_model(request_id, {})
        raise
    usage = usage_of(result)
    if on_result is not None:
        on_result(result, usage)
    ledger.settle_model(request_id, usage)
    return result, usage, None


def chat_metered(adapter, ledger, stage, messages, options, model, system):
    """直连 API 文本模型的一次对话也过计量：有台账就授权／结算，没有台账（无项目）就是普通调用。

    授权被拒时抛 ValueError（文案是预算原因），发送失败按未知用量结算后原样抛出；其余原样返回适配器结果。
    """
    import json
    from uuid import uuid4

    import token_saver
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
