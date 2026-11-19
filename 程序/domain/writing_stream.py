"""剧本对话的流式取回：线程内订阅文字片段，chat 协议走流式，其余协议和失败场景退回普通请求。"""
from contextlib import contextmanager
from contextvars import ContextVar

_STREAM_SINK = ContextVar('writing_stream_sink', default=None)


@contextmanager
def stream_to(sink):
    """本线程内的剧本对话改走流式：每个新增文字片段交给 ``sink``（在调用线程里被调用）。"""
    token = _STREAM_SINK.set(sink)
    try:
        yield
    finally:
        _STREAM_SINK.reset(token)


def chat_streaming(adapter, messages, options, model, system, cancelled=None):
    """有人订阅且是 chat 协议就流式取回；还没收到任何文字就失败时退回普通请求，已出字的失败不再重发。"""
    sink = _STREAM_SINK.get()
    if sink is None or getattr(adapter, 'wire_api', '') != 'chat':
        return adapter.chat(messages, options=options, model=model, system=system)
    seen = []

    def forward(chunk):
        seen.append(chunk)
        sink(chunk)
    result = adapter.stream(messages, options=options, model=model, system=system,
                            on_chunk=forward, cancelled=cancelled)
    if (not result.get('ok') and not seen and result.get('error_class') != 'cancelled'
            and not (cancelled is not None and cancelled())):
        return adapter.chat(messages, options=options, model=model, system=system)
    return result
