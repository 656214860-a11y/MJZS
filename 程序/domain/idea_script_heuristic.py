# -*- coding: utf-8 -*-
"""剧本启发式判断：一段回复够不够长、有没有至少两个剧本要素。

第 65 期任务 9：这段回复像不像「一份能开拍的剧本」——够长 ＋ 至少两个剧本要素，
给界面决定要不要弹「保存剧本」。只做纯文本判断：不读文件、不发网络、不碰 Tk。
"""
import re

SCRIPT_MARKS = ('场景', '镜头', '分镜', '台词', '角色', '第一集', '第 1 集', '第1集')
SCRIPT_MIN = 300

# 「重新生成/重新创作/重新输出<阶段>」的口令识别，供剧本准备 API 与桌面 Agent
# 两条发送路径共用同一口径；纯文本判断，不读阶段配置、不依赖编排层。
_RESTART_REQUESTED = re.compile(
    r'(?:请)?重新(?:创作|生成|输出)(?:\s*(?:项目设定|剧本大纲|项目大纲|大纲|角色卡|自然剧本|剧本))?')


def looks_like_script(text):
    """第 65 期任务 9：这段回复像不像一份能开拍的剧本（给界面决定要不要弹「保存剧本」）。"""
    value = str(text or '').strip()
    if len(value) < SCRIPT_MIN:
        return False
    return sum(1 for mark in SCRIPT_MARKS if mark in value) >= 2


def writing_restart_requested(text):
    """仅认开头口令的显式重启指令；附件或正文里的字样不算。"""
    first = str(text or '').strip().split('\n', 1)[0].strip().rstrip('。！!')
    return bool(_RESTART_REQUESTED.fullmatch(first))


_ARCHIVE_SKIP = frozenset({
    '待确认', '无', '暂无', '名称', '角色', '角色名', '人物', '场景', '场景名',
    '道具', '道具名', '编号', '序号', 'ID',
})
_CHAR_TITLES = ('角色档案', '角色清单', '角色设定', '角色表', '人物档案', '人物清单', '主要角色')
_SCENE_TITLES = ('场景档案', '场景清单', '场景设定', '场景表', '主要场景')
_PROP_TITLES = ('道具档案', '道具清单', '道具设定', '道具表', '关键道具', '重要道具')


def _strip_md(value):
    return re.sub(r'^\*{1,2}|\*{1,2}$', '', str(value or '').strip()).strip()


def _archive_block(text, headings):
    pattern = re.compile(
        r'(?m)^(#{2,3})\s*(?:[一二三四五六七八九十\d]+[、.．\s]+)?\*{0,2}('
        + '|'.join(re.escape(h) for h in headings) + r')\*{0,2}(?:[\s（(：:].*)?$'
    )
    match = pattern.search(text)
    if not match:
        return ''
    level = len(match.group(1))
    end = re.search(r'(?m)^#{1,%d}\s+' % level, text[match.end():])
    return text[match.start():] if not end else text[match.start():match.end() + end.start()]


def _parse_sub_cards(blocks):
    rows = []
    for block in blocks:
        title, _, body = block.partition('\n')
        name = _strip_md(title)
        if not name or name.startswith('待确认') or name in _ARCHIVE_SKIP:
            continue
        fields = {_strip_md(k): v.strip()
                  for k, v in re.findall(r'(?m)^[-*+]\s+\*{0,2}([^：:\n*]+?)\*{0,2}[：:]\s*(.*)$', body)}
        rows.append((name, fields))
    return rows


def _parse_list_or_table(body):
    rows, seen = [], set()
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        bullet = re.match(r'^(?:[-*+]|\d+[、.．])\s+\*{0,2}([^：:\n*]+?)\*{0,2}(?:[：:]\s*(.*))?$', line)
        if bullet:
            name = _strip_md(bullet.group(1))
            if name and not name.startswith('待确认') and name not in _ARCHIVE_SKIP and name not in seen:
                seen.add(name)
                rows.append((name, {'_desc': (bullet.group(2) or '').strip()}))
        elif line.startswith('|') and '|' in line[1:]:
            cells = [_strip_md(c) for c in line.strip('|').split('|')]
            if not cells or all(set(c) <= {'-', ':', ' '} for c in cells):
                continue
            name = cells[1] if len(cells) > 1 and re.match(r'^(?:\d+|CHAR_\d+|LOC_\d+|PROP_\d+)$', cells[0], re.I) else cells[0]
            if name and not name.startswith('待确认') and name not in _ARCHIVE_SKIP and name not in seen:
                seen.add(name)
                rows.append((name, {'_desc': ' '.join(c for c in cells[1:] if c and c != name)}))
    return rows


def _parse_archive_entries(text, headings):
    section = _archive_block(text, headings)
    if not section:
        return []
    body = section.split('\n', 1)[1] if '\n' in section else ''
    sub_blocks = re.split(r'(?m)^#{3,4}\s+', body)[1:]
    return _parse_sub_cards(sub_blocks) if sub_blocks else _parse_list_or_table(body)


def flexible_structure_manifests(script_contract, text):
    """纯解析：兼容模型生成的变体标题／加粗键／列表／表格结构稿，派生三份合规 manifest。"""
    def known(val):
        cleaned = re.sub(r'（来源：原稿声明）', '', str(val or '')).strip()
        return '' if not cleaned or cleaned.startswith('待确认') else cleaned

    chars = [{
        'name': name,
        'aliases': [known(card.get('别名'))] if known(card.get('别名')) else [],
        'cross_episode_id': card.get('跨集 ID', '').split('（')[0],
        'description': ('默认服装：' + known(card.get('默认服装') or card.get('服装')))
                       if known(card.get('默认服装') or card.get('服装')) else known(card.get('_desc')),
        'physical_features': script_contract.field_features(known(card.get('物理特征') or card.get('外貌特征'))),
    } for name, card in _parse_archive_entries(text, _CHAR_TITLES)]
    scenes = [{
        'name': re.sub(r'^场景\s*\d+[：:]', '', name).strip() or name,
        'description': known(card.get('空间锚点') or card.get('场景描述') or card.get('_desc')),
        'time_of_day': known(card.get('光照方向') or card.get('时间')),
        'timeline': known(card.get('时间线')),
    } for name, card in _parse_archive_entries(text, _SCENE_TITLES)]
    props = [{
        'name': name,
        'description': known(card.get('说明') or card.get('用途') or card.get('_desc')),
        'holder': known(card.get('持有者') or card.get('归属')),
    } for name, card in _parse_archive_entries(text, _PROP_TITLES)]
    return {
        'character_manifest.json': script_contract.manifest('character', chars),
        'scene_manifest.json': script_contract.manifest('scene', scenes),
        'prop_manifest.json': script_contract.manifest('prop', props),
    }

