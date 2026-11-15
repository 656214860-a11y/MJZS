# -*- coding: utf-8 -*-
"""SKILL 引用的递归内联与体积预算。

从 ``workflow_settings`` 拆出：R2450 的 depth=-1 递归完整内联让本模块体积超过上限；
R2540 给递归补上按模型窗口推导的估算 token 预算（``_charge_inline``），装不下的引用记
``skipped`` 并留本地路径提示——CLI／桌面引擎有目录白名单可按需读取，API 直发则保持不超窗。
"""
from pathlib import Path

import skill_registry
from skill_registry import reference_row as _reference_row
from workflow_context_budget import estimate_tokens, skill_inline_token_budget

_TEXT_SCRIPT_SUFFIXES = ('.py', '.sh', '.ps1', '.bat', '.cmd', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg')


def _is_text_script(suffix):
    return suffix.lower() in _TEXT_SCRIPT_SUFFIXES


def _skill_inline_budget(config):
    """depth=-1 递归内联的估算 token 预算：按发送模型的上下文窗口留足任务、历史、
    输出预留与固定规则份额；查不到窗口返回 None（不设限，如本地引擎路径）。"""
    model = str((config or {}).get('model') or '').strip()
    if not model:
        return None
    try:
        import model_pool
        record = model_pool.pool(program=Path(__file__).resolve().parent).get(model) or {}
    except Exception:
        import app_logging
        app_logging.swallowed()
        return None
    budget = skill_inline_token_budget(model_pool.context_length_of(record.get('context_length')))
    return {'remaining': budget} if budget is not None else None


def _charge_inline(budget, block_text):
    """估算 block 占用的 token 并从预算扣减；装不下返回 False 且不扣、不内联。"""
    if budget is None:
        return True
    cost = estimate_tokens(block_text)
    if cost > budget['remaining']:
        return False
    budget['remaining'] -= cost
    return True


def _skipped_inline_hint(reference):
    """超预算未内联的引用仍留本地路径：CLI／桌面引擎有目录白名单可按需读取。"""
    return f'\n\n<!-- 体积超本次发送窗口预算，未内联；本地路径：{reference} -->'


def _recurse_references(reference, body, context):
    """展开一个已内联引用文件里再出现的链接（递归一层），返回 closure 行。

    ``seen`` 跨层去重（回环记 cycle 由调用方 _nested_references 或本函数处理）；
    这里只负责把下一层引用真正内联进 ``blocks``。depth 递减直到 0 停止递归。
    """
    strict, locks, depth, blocks, seen, sections, budget = context
    next_depth = depth - 1 if depth > 0 else depth
    roots = skill_registry.skill_roots()
    out = []
    for entry in skill_registry.reference_targets(body):
        relative = entry['path']
        if relative is None:
            out.append(_reference_row(entry, None, entry['kind'], 2))
            continue
        if relative.is_absolute():
            out.append(_reference_row(entry, relative, 'absolute', 2))
            continue
        target = skill_registry.resolve_reference(reference, relative)
        markdown = entry['kind'] == 'markdown'
        text_script = not markdown and _is_text_script(target.suffix)
        if not markdown and not text_script:
            out.append(_reference_row(entry, target, 'resource', 2))
            if depth == -1:
                blocks.append((target, f'\n\n<!-- 本请求不发送该资源，本地路径：{target} -->'))
            continue
        if target in seen:
            out.append(_reference_row(entry, target, 'cycle', 2))
            continue
        if not any(target.is_relative_to(root) for root in roots):
            out.append(_reference_row(entry, target, 'outside', 2))
            continue
        fragment = entry.get('fragment') or ''
        if (target, fragment) in sections:
            out.append(_reference_row(entry, target, 'duplicate', 2))
            continue
        try:
            nested_body = target.read_text(encoding='utf-8-sig')
        except OSError as exc:
            out.append(_reference_row(entry, target, 'missing', 2))
            if strict:
                raise ValueError(f'SKILL 引用缺失，已阻止发送：{target}（{exc}）') from exc
            continue
        if text_script:
            block = f'\n\n## 脚本: {target.name}\n```{target.suffix.lstrip(".")}\n{nested_body}\n```'
            if _charge_inline(budget, block):
                seen.add(target)
                blocks.append((target, block))
                out.append(_reference_row(entry, target, 'inlined', 2))
            else:
                blocks.append((target, _skipped_inline_hint(target)))
                out.append(_reference_row(entry, target, 'skipped', 2))
            continue
        part = skill_registry.section(nested_body, fragment)
        if part is not None:
            block = f'\n\n## 引用: {target.name}#{fragment}（节选）\n{part}'
            if not _charge_inline(budget, block):
                blocks.append((target, _skipped_inline_hint(target)))
                out.append(_reference_row(entry, target, 'skipped', 2))
                continue
            sections.add((target, fragment))
            seen.add(target)
            blocks.append((target, block))
            out.append(_reference_row(entry, target, 'section', 2))
            if next_depth != 0:
                out.extend(_recurse_references(target, part, (strict, locks, next_depth, blocks, seen, sections, budget)))
            continue
        block = f'\n\n## 引用: {target.name}\n{nested_body}'
        if not _charge_inline(budget, block):
            blocks.append((target, _skipped_inline_hint(target)))
            out.append(_reference_row(entry, target, 'skipped', 2))
            continue
        seen.add(target)
        blocks.append((target, block))
        out.append(_reference_row(entry, target, 'inlined', 2))
        if next_depth != 0:
            out.extend(_recurse_references(target, nested_body, (strict, locks, next_depth, blocks, seen, sections, budget)))
    return out
