"""Shared preflight limit for non-interactive workflow-engine requests."""

REQUEST_CONTEXT_MAX_CHARS = 96_000


def compact_repeated_context(prompt):
    """Keep one authoritative copy of repeated large context sections.

    This is deliberately lossless for unique text: only an exact duplicate
    paragraph of at least 1,024 characters may be replaced, and its first
    occurrence remains in the request.
    """
    parts = prompt.split('\n\n')
    kept = []
    seen = set()
    removed = 0
    for part in parts:
        key = part.strip()
        if len(key) >= 1_024 and key in seen:
            removed += 1
            continue
        kept.append(part)
        if len(key) >= 1_024:
            seen.add(key)
    if not removed:
        return prompt
    kept.append(f'【上下文去重摘要：已合并 {removed} 段与前文完全相同的大段内容，首份完整内容保留。】')
    return '\n\n'.join(kept)


def ensure_request_context(prompt, stage='当前阶段'):
    """Compact repeated context, then reject an oversized engine request."""
    prompt, _budget = prepare_request_context(prompt, stage)
    return prompt


def prepare_request_context(prompt, stage='当前阶段', strategy=''):
    """Compact, limit and expose request-size metadata without retaining text."""
    if not isinstance(prompt, str):
        raise ValueError(str(stage) + '请求内容格式无效，请重新生成任务。')
    prompt = compact_repeated_context(prompt)
    size = len(prompt)
    if size > REQUEST_CONTEXT_MAX_CHARS:
        raise ValueError(
            f'{stage}请求上下文超过 {REQUEST_CONTEXT_MAX_CHARS:,} 字符（当前 {size:,}），'
            '请缩短输入、拆分任务或先生成摘要后重试。')
    return prompt, {
        'stage': str(stage),
        'strategy': str(strategy or 'unspecified'),
        'characters': size,
        'limit': REQUEST_CONTEXT_MAX_CHARS,
        'remaining': REQUEST_CONTEXT_MAX_CHARS - size,
    }
