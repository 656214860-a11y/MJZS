"""Ordinary props belong to the shot description, not the image asset queue."""
import copy
import re

RULES = (
    '道具制作规则：默认不为普通道具建立独立资产，也不给普通道具分配 PROP 编号。'
    '普通家具、餐具、纸笔、工具、背景摆设及一次性日用品，由 AI 按当前剧本和画风随镜头设计；'
    '在镜头 ordinary_props 数组中写 name、description（数量、颜色、位置和本镜初始状态），'
    '并合入 frame_prompt/video_prompt，保留必要的剧情动作和前后镜头连续性。'
    '只有承担核心剧情或悬念线索、需要反复特写识别的独特物件，或用户明确指定的重要道具，才建立 PROP 资产；'
    '仅仅被拿起、在多个镜头出现或发生动作，不足以要求单独生图。'
    '关键道具写 requires_asset=true、prop_importance="key"、asset_reason（本剧情为什么必须单独制作）；'
    '只有这些关键道具进入统一资产清单以及镜头 props/first_frame_assets 的 PROP 引用。'
    '普通道具不能因为缺少独立参考图而阻止首帧或视频制作，不生成单独参考图、不重复建档。'
    '旧清单中 requires_asset=false 或 prop_importance="ordinary" 的道具仅保留历史记录，'
    '读取其描述并按普通道具处理，不重新创建编号；已有图片和文件保留。'
)

CHARACTER_RULES = (
    '角色制作规则：默认只为需要保持身份、露脸且跨镜反复出现的角色建立 CHAR 资产并分配编号。'
    '背景人物、群演、路人、只露背影或局部、不露脸或一次性角色，不建立 CHAR 资产、不分配 CHAR 编号、'
    '也不写入统一资产清单；直接在镜头 action、frame_prompt、video_prompt 中描述人数、服装、姿态和本镜状态，'
    '随画面按项目画风生成，不单独制作参考图。'
    '只有需要反复特写识别、有台词或身份延续的角色才建立 CHAR 资产。'
    '历史清单中 requires_asset=false 或 character_importance 为 background/extra/non_face 的角色仅保留记录，'
    '不重新建档、不生成图片、不在资产页显示。'
)


def requires_asset(aid, asset):
    aid = str(aid)
    if aid.startswith('PROP_'):
        if isinstance(asset.get('requires_asset'), bool):
            return asset['requires_asset']
        if asset.get('prop_importance') in ('key', 'ordinary'):
            return asset['prop_importance'] == 'key'
        # Old explicit IDs stay compatible until classified; names alone never
        # allocate a new prop ID. Existing key objects must not silently disappear.
        return True
    if aid.startswith('CHAR_'):
        if isinstance(asset.get('requires_asset'), bool):
            return asset['requires_asset']
        if asset.get('character_importance') in ('key', 'background', 'extra', 'non_face'):
            return asset['character_importance'] == 'key'
        return True
    return True


def removed_ids(entries):
    """清单里那些「不建独立资产」的编号（普通道具／背景人物）。

    这一份只跟清单有关、跟镜头一点关系都没有，可原来是 normalize_shot 每个镜头现算一遍：
    300 个镜头 × 一份 47 条的清单 = 每建一次页面 2.8 万次 requires_asset，几千个镜头的项目
    实测 28 万次，占了资产页打开时间的一半（第 72 期，Round 3 性能门禁）。sync_plan 因此把
    算好的那一份按阶段递进来（见 normalize_shot 的 removed 参数）。
    """
    return frozenset(aid for aid, row in entries.items() if not requires_asset(aid, row))


def _resolve(value, entries):
    raw = value if isinstance(value, dict) else {}
    name = raw.get('id') or raw.get('name') if raw else value
    if not isinstance(name, str):
        return None, {}, raw
    name = name.strip()
    if name in entries and name.startswith('PROP_'):
        return name, entries[name], raw
    matches = [(aid, row) for aid, row in entries.items()
               if aid.startswith('PROP_') and name in [row.get('name'), *row.get('aliases', [])]]
    return (*matches[0], raw) if len(matches) == 1 else (name, {}, raw)


def normalize_shot(shot, entries=None, removed=None):
    """按清单现在的政策收拾一个镜头：普通道具降级成镜头内描述、撤掉它们的编号引用。

    removed 是 removed_ids(entries) 算好的那一份。同一份清单会被成百上千个镜头反复用，
    所以调用方算一次递进来就行；不给就照老样子现算（口径与 removed_ids 完全一样）。
    """
    entries = entries or {}
    if not isinstance(shot, dict):
        return {}
    result = copy.deepcopy(shot)
    ordinary = result.get('ordinary_props', [])
    ordinary = ordinary if isinstance(ordinary, list) else [ordinary] if ordinary else []
    ordinary = [item if isinstance(item, dict) else {'name': str(item), 'description': str(item)} for item in ordinary]
    seen = {str(item.get('name', '')) for item in ordinary}
    removed = set(removed_ids(entries) if removed is None else removed)
    for key in ('props', 'first_frame_assets'):
        if key not in result:
            continue
        values = result[key]
        values = values if isinstance(values, list) else [values] if values else []
        kept = []
        for value in values:
            aid, row, raw = _resolve(value, entries)
            if key == 'first_frame_assets' and not (aid and aid.startswith('PROP_')):
                kept.append(value)
                continue
            # The current library policy takes priority over stale shot snapshots.
            merged = {**raw, **row}
            explicit = isinstance(merged.get('requires_asset'), bool) or merged.get('prop_importance') in ('key', 'ordinary')
            required = requires_asset('PROP_', merged) if explicit else bool(aid and re.fullmatch(r'PROP_\d{3,}', aid))
            if required:
                kept.append(aid if aid in entries else value)
                continue
            if aid and aid.startswith('PROP_'):
                removed.add(aid)
            name = str(merged.get('name') or aid or '').strip()
            if name and name not in seen:
                description = str(merged.get('description') or merged.get('appearance') or name)
                ordinary.append({'name': name, 'description': description})
                seen.add(name)
        result[key] = kept
    if ordinary:
        result['ordinary_props'] = ordinary
    if 'upload_asset_ids' in result:
        result['upload_asset_ids'] = [aid for aid in result['upload_asset_ids'] if aid not in removed]
    if isinstance(result.get('asset_bindings'), dict):
        result['asset_bindings'] = {aid: row for aid, row in result['asset_bindings'].items() if aid not in removed}
    return result


def inline_text(shot, entries=None):
    props = normalize_shot(shot, entries).get('ordinary_props', [])
    if not props:
        return ''
    details = []
    for item in props:
        name = str(item.get('name', ''))
        description = str(item.get('description') or name)
        details.append(name + '：' + description)
    return ('普通道具随画面设计（不需要单独参考图；沿用项目画风，数量和状态以本镜提示词为准，'
            '保持镜头衔接，不提前表现后续动作）：' + '；'.join(details))
