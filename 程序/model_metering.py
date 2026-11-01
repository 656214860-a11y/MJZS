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
