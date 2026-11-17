# -*- coding: utf-8 -*-
"""SKILL 引用的递归内联与体积预算。

从 ``workflow_settings`` 拆出：R2450 的 depth=-1 递归完整内联让本模块体积超过上限；
R2540 给递归补上按模型窗口推导的估算 token 预算（``_charge_inline``），装不下的引用记
``skipped`` 并留本地路径提示——CLI／桌面引擎有目录白名单可按需读取，API 直发则保持不超窗。
"""
from dataclasses import dataclass
from pathlib import Path

import orchestrator.skill_registry as skill_registry
from orchestrator.skill_registry import reference_row as _reference_row
from contract.workflow_context_budget import estimate_tokens, skill_inline_token_budget, preset_context_length

_TEXT_SCRIPT_SUFFIXES = ('.py', '.sh', '.ps1', '.bat', '.cmd', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg')


@dataclass(frozen=True)
class _ReferenceContext:
    roots: object
    locks: object
    seen: set
    sections: set
    reader: object


def _skill_envelope(name, blocks):
    from html import escape
    return (f'<skill name="{escape(name, quote=True)}">\n'
            + ''.join(body for _, body in blocks) + '\n</skill>')


def _reserve_frozen_text(budget, fixed_text, body_cost, names, hint_reserves):
    """正文、实际包装与全部未发送提示先占位，再分配可选引用。"""
    if budget is None:
        return
    fixed_cost = estimate_tokens(fixed_text)
    hint_cost = sum(hint_reserves.values())
    limit = budget['remaining']
    if fixed_cost + hint_cost > limit:
        error = ValueError(f'正文合计 {body_cost:,} token（{"、".join(names)}）；包装 {fixed_cost - body_cost:,} token\n'
                           f'引用提示 {hint_cost:,} token；预算 {limit:,} token\n已阻止发送。')
        error.detail = {'body_tokens': body_cost, 'fixed_tokens': fixed_cost,
                        'wrapper_tokens': fixed_cost - body_cost, 'hint_tokens': hint_cost,
                        'budget_tokens': limit}
        raise error
    budget['remaining'] = limit - fixed_cost - hint_cost
    budget['pending'] = hint_reserves


def _skill_snapshot_reader():
    """单次冻结专用 memo；正文、预留和实际发送复用同一次磁盘读取。"""
    snapshots = {}
    def read(path):
        if path not in snapshots:
            try:
                snapshots[path] = path.read_text(encoding='utf-8-sig')
            except (OSError, UnicodeError) as exc:
                snapshots[path] = exc
        result = snapshots[path]
        if isinstance(result, (OSError, UnicodeError)):
            raise result
        return result
    return read


def _skill_roots_for_path(path):
    roots = list(skill_registry.skill_roots())
    project_root = skill_registry.project_skill_root_for(path)
    if project_root is not None and project_root not in roots:
        roots.append(project_root)
    return roots


def _is_text_script(suffix):
    return suffix.lower() in _TEXT_SCRIPT_SUFFIXES


def _skill_inline_budget(config, record=None, program=None):
    """从同次请求的记录推导预算；None 才查池，空记录仍是有效快照。

    仅直连 API 强制要求已知窗口，CLI／桌面保留无窗口模式。
    返回值只含安全预算元数据，不保留模型记录或凭据。
    """
    config = config or {}
    model = str(config.get('model') or '').strip()
    api = config.get('invocation_mode') == 'api' or config.get('engine') == 'api'
    if not model and not api:
        return None
    if record is None and config.get('skill_budget', {}).get('model') == model:
        saved = config['skill_budget']
        limit = saved['context_length']
        source = saved['source']
    else:
        import infra.model_pool as model_pool
        if record is None:
            # model_pool 拥有默认程序根；不能使用 script_contract 的 contract 根。
            records = model_pool.pool() if program is None else model_pool.pool(program=program)
            record = records.get(model) or {}
        limit = model_pool.context_length_of(record.get('context_length'))
        source = 'explicit' if limit else 'preset'
        limit = limit or preset_context_length(model)
    if not limit:
        if api:
            raise ValueError(f'未填写上下文窗口，已阻止发送：{model or "未选择模型"}；请在模型管理中补填。')
        return None
    return {'remaining': skill_inline_token_budget(limit), 'context_length': limit, 'source': source, 'model': model}


def _reference_frontier(source, text, context, *, allow_folder=False):
    """只读当前层候选，预留发送块/未发送提示中的较小值；不展开后代。"""
    roots, locks = context.roots, context.locks
    seen, sections, reader = context.seen, context.sections, context.reader
    frontier = {}
    for entry in skill_registry.reference_targets(text):
        relative = entry['path']
        if relative is None or relative.is_absolute():
            continue
        target = skill_registry.resolve_reference(source, relative)
        fragment = entry.get('fragment') or ''
        markdown = entry['kind'] == 'markdown'
        script = not markdown and _is_text_script(target.suffix)
        key = (str(target), fragment) if markdown or script else ('resource', str(target))
        if not markdown and not script:
            frontier[key] = estimate_tokens(f'\n\n<!-- 本请求不发送该资源，本地路径：{target} -->')
            continue
        if (target in seen or (target, fragment) in sections or
                not (any(target.is_relative_to(root) for root in roots) or
                     (allow_folder and target.is_relative_to(Path(source).parent))) or
                skill_registry.condition_unmet(text, entry.get('start', 0), locks)):
            continue
        hint_cost = estimate_tokens(_skipped_inline_hint(target))
        try:
            body = reader(target)
            part = skill_registry.section(body, fragment) if markdown else None
            block = (f'\n\n## 脚本: {target.name}\n```{target.suffix.lstrip(".")}\n{body}\n```' if script else
                     f'\n\n## 引用: {target.name}#{fragment}（节选）\n{part}' if part is not None else
                     f'\n\n## 引用: {target.name}\n{body}')
            hint_cost = min(hint_cost, estimate_tokens(block))
        except (OSError, UnicodeError):
            pass  # 只有实际到达该候选时才沿原闭包报错。
        frontier[key] = hint_cost
    return frontier


def _charge_reference(budget, reference, fragment, block, body, context):
    """父块和新增子 frontier 原子分配；失败只发送父提示，绝不读取孙辈。"""
    if budget is None or 'pending' not in budget:
        return _charge_inline(budget, block)
    key = (str(reference), fragment)
    budget['remaining'] += budget['pending'].pop(key, 0)
    quality_cost = _quality_inline_cost(budget, block)
    cost = estimate_tokens(block) + quality_cost
    if cost > budget['remaining']:
        return False
    child_context = _ReferenceContext(context.roots, context.locks, context.seen | {reference},
                                      context.sections, context.reader)
    children = _reference_frontier(reference, body, child_context)
    sent_resources = budget.get('sent_resources', set())
    children = {key: value for key, value in children.items()
                if key not in budget['pending'] and key not in sent_resources}
    total = cost + sum(children.values())
    if total > budget['remaining']:
        return False
    budget['remaining'] -= total
    budget['pending'].update(children)
    _commit_inline_quality(budget, block, quality_cost)
    return True


def _quality_inline_cost(budget, block):
    if 'quality_probe' not in budget or budget.get('quality_reserved'):
        return 0
    from domain.writing_quality import enabled
    return estimate_tokens(budget['quality_prompt']) if enabled(budget['quality_probe'] + block) else 0


def _commit_inline_quality(budget, block, cost):
    if 'quality_probe' in budget:
        budget['quality_probe'] += block
        budget['quality_reserved'] = budget.get('quality_reserved', False) or bool(cost)


def _charge_inline(budget, block_text):
    """估算 block 占用的 token 并从预算扣减；装不下返回 False 且不扣、不内联。"""
    if budget is None:
        return True
    quality_cost = _quality_inline_cost(budget, block_text)
    cost = estimate_tokens(block_text) + quality_cost
    if cost > budget['remaining']:
        return False
    budget['remaining'] -= cost
    _commit_inline_quality(budget, block_text, quality_cost)
    return True


def _append_hint(blocks, reference, text, budget):
    """提示也是实际发送文本；不能以 skipped/resource 绕过预算。"""
    resource_key = None
    if budget is not None and 'pending' in budget and text.startswith('\n\n<!-- 本请求不发送该资源'):
        resource_key = ('resource', str(reference))
        if resource_key in budget.get('sent_resources', set()):
            return
        budget['remaining'] += budget['pending'].pop(resource_key, 0)
    if not _charge_inline(budget, text):
        raise ValueError(f'SKILL/阶段指令预算不足：包装/未发送引用提示超限（{reference}），已阻止发送。')
    blocks.append((reference, text))
    if resource_key is not None:
        budget.setdefault('sent_resources', set()).add(resource_key)


def _skipped_inline_hint(reference):
    """标明未发送，不承诺直连 API 能读取本地文件。"""
    return f'\n\n<!-- 体积超本次发送窗口预算，未内联；本地路径：{reference}；API 无法读取此本地文件。 -->'


def _recurse_references(reference, body, context, *, reader=None, roots=None):
    """展开一个已内联引用文件里再出现的链接（递归一层），返回 closure 行。

    ``seen`` 跨层去重（回环记 cycle 由调用方 _nested_references 或本函数处理）；
    这里只负责把下一层引用真正内联进 ``blocks``。depth 递减直到 0 停止递归。
    """
    strict, locks, depth, blocks, seen, sections, budget = context
    next_depth = depth - 1 if depth > 0 else depth
    roots = skill_registry.skill_roots() if roots is None else roots
    reader = reader or (lambda path: path.read_text(encoding='utf-8-sig'))
    reference_context = _ReferenceContext(roots, locks, seen, sections, reader)
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
                _append_hint(blocks, target, f'\n\n<!-- 本请求不发送该资源，本地路径：{target} -->', budget)
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
            nested_body = reader(target)
        except OSError as exc:
            out.append(_reference_row(entry, target, 'missing', 2))
            if strict:
                raise ValueError(f'SKILL 引用缺失，已阻止发送：{target}（{exc}）') from exc
            continue
        if text_script:
            block = f'\n\n## 脚本: {target.name}\n```{target.suffix.lstrip(".")}\n{nested_body}\n```'
            if _charge_reference(budget, target, fragment, block, '', context=reference_context):
                seen.add(target)
                blocks.append((target, block))
                out.append(_reference_row(entry, target, 'inlined', 2))
            else:
                _append_hint(blocks, target, _skipped_inline_hint(target), budget)
                out.append(_reference_row(entry, target, 'skipped', 2))
            continue
        part = skill_registry.section(nested_body, fragment)
        if part is not None:
            block = f'\n\n## 引用: {target.name}#{fragment}（节选）\n{part}'
            if not _charge_reference(budget, target, fragment, block, part, reference_context):
                sections.add((target, fragment))
                _append_hint(blocks, target, _skipped_inline_hint(target), budget)
                out.append(_reference_row(entry, target, 'skipped', 2))
                continue
            sections.add((target, fragment))
            blocks.append((target, block))
            out.append(_reference_row(entry, target, 'section', 2))
            if next_depth != 0:
                out.extend(_recurse_references(target, part, (strict, locks, next_depth, blocks, seen, sections, budget), reader=reader, roots=roots))
            continue
        block = f'\n\n## 引用: {target.name}\n{nested_body}'
        if not _charge_reference(budget, target, fragment, block, nested_body, context=reference_context):
            seen.add(target)
            _append_hint(blocks, target, _skipped_inline_hint(target), budget)
            out.append(_reference_row(entry, target, 'skipped', 2))
            continue
        seen.add(target)
        blocks.append((target, block))
        out.append(_reference_row(entry, target, 'inlined', 2))
        if next_depth != 0:
            out.extend(_recurse_references(target, nested_body, (strict, locks, next_depth, blocks, seen, sections, budget), reader=reader, roots=roots))
    return out
