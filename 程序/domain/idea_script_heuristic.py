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
    '道具', '道具名', '编号', '序号', 'ID', '时间', '地点', '对白', '台词', '旁白',
    '镜头', '画面', '音效', '时长', '情绪', '备注', '说明', '来源', '集数', '总时长',
    '景别', '运镜', '出场角色', '出场人物', '主要角色', '关键道具', '补充要求',
})
_CHAR_TITLES = ('角色档案', '角色清单', '角色设定', '角色表', '人物档案', '人物清单',
                '人物设定', '人物表', '人物列表', '主要角色', '出场人物', '出场角色', '角色介绍')
_SCENE_TITLES = ('场景档案', '场景清单', '场景设定', '场景表', '场景列表', '场景汇总',
                 '主要场景', '地点设定', '地点表')
_PROP_TITLES = ('道具档案', '道具清单', '道具设定', '道具表', '道具列表', '道具汇总',
                '关键道具', '重要道具', '核心道具')


def _strip_md(value):
    return re.sub(r'^\*{1,2}|\*{1,2}$', '', str(value or '').strip()).strip()


def _archive_block(text, headings):
    titles = '|'.join(re.escape(h) for h in headings)
    pattern = re.compile(
        r'(?m)^(#{1,4})\s*(?:[一二三四五六七八九十\d]+[、.．\s]+)?\*{0,2}('
        + titles + r')\*{0,2}(?:[\s（(：:].*)?$'
    )
    match = pattern.search(text)
    if match:
        level = len(match.group(1))
        end = re.search(r'(?m)^#{1,%d}\s+' % level, text[match.end():])
        return text[match.start():] if not end else text[match.start():match.end() + end.start()]
    bold = re.search(r'(?m)^\*{2}(?:[一二三四五六七八九十\d]+[、.．\s]+)?(' + titles + r')\*{2}[：:]?\s*$', text)
    if not bold:
        return ''
    end = re.search(r'(?m)^(?:#{1,4}\s+|\*{2}[^*\n]{2,16}\*{2}[：:]?\s*$)', text[bold.end():])
    return text[bold.start():] if not end else text[bold.start():bold.end() + end.start()]


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


def _split_inline_names(raw):
    items = []
    for part in re.split(r'[、,，/；;]+', str(raw or '')):
        name = re.sub(r'[（(][^）)]*[）)]', '', _strip_md(part)).strip()
        if name and not name.startswith('待确认') and name not in _ARCHIVE_SKIP and len(name) <= 20:
            items.append(name)
    return items


def _inline_fallback_entries(text):
    """分集／分场式结构稿无独立档案节时，从场景标题、出场角色、道具行与对白说话人兜底提取。"""
    chars, scenes, props = [], [], []
    seen_c, seen_s, seen_p = set(), set(), set()
    for raw in str(text or '').splitlines():
        line = raw.strip()
        if not line:
            continue
        sc_head = re.match(r'^#{2,4}\s*(?:场景|场次|场|第\s*\d+\s*场)\s*[\d\-]*\s*[：:.\s]*(.+)$', line)
        if sc_head:
            name = _strip_md(sc_head.group(1))
            if name and name not in _ARCHIVE_SKIP and name not in seen_s:
                seen_s.add(name); scenes.append((name, {}))
            continue
        m_char = re.match(r'^(?:[-*+]\s+)?\*{0,2}(?:出场角色|出场人物|角色|人物)\*{0,2}[：:]\s*(.+)$', line)
        if m_char:
            for name in _split_inline_names(m_char.group(1)):
                if name not in seen_c:
                    seen_c.add(name); chars.append((name, {}))
            continue
        m_scene = re.match(r'^(?:[-*+]\s+)?\*{0,2}(?:场景|地点)\*{0,2}[：:]\s*(.+)$', line)
        if m_scene:
            for name in _split_inline_names(m_scene.group(1)):
                if name not in seen_s:
                    seen_s.add(name); scenes.append((name, {}))
            continue
        m_prop = re.match(r'^(?:[-*+]\s+)?\*{0,2}(?:关键道具|重要道具|道具)\*{0,2}[：:]\s*(.+)$', line)
        if m_prop:
            for name in _split_inline_names(m_prop.group(1)):
                if name not in seen_p:
                    seen_p.add(name); props.append((name, {}))
            continue
        m_spk = re.match(r'^\*{0,2}([\u4e00-\u9fff]{2,4})\*{0,2}(?:[（(][^）)]*[）)])?[：:]\s*\S', line)
        if m_spk:
            name = m_spk.group(1)
            if name not in _ARCHIVE_SKIP and name not in seen_c:
                seen_c.add(name); chars.append((name, {}))
    return chars, scenes, props


def flexible_structure_manifests(script_contract, text):
    """纯解析：兼容模型生成的变体标题／加粗键／列表／表格与分场式结构稿，派生三份合规 manifest。"""
    def known(val):
        cleaned = re.sub(r'（来源：原稿声明）', '', str(val or '')).strip()
        return '' if not cleaned or cleaned.startswith('待确认') else cleaned

    char_rows = _parse_archive_entries(text, _CHAR_TITLES)
    scene_rows = _parse_archive_entries(text, _SCENE_TITLES)
    prop_rows = _parse_archive_entries(text, _PROP_TITLES)
    if not (char_rows or scene_rows or prop_rows):
        char_rows, scene_rows, prop_rows = _inline_fallback_entries(text)
    else:
        fb_chars, fb_scenes, fb_props = _inline_fallback_entries(text)
        char_rows = char_rows or fb_chars
        scene_rows = scene_rows or fb_scenes
        prop_rows = prop_rows or fb_props

    chars = [{
        'name': name,
        'aliases': [known(card.get('别名'))] if known(card.get('别名')) else [],
        'cross_episode_id': card.get('跨集 ID', '').split('（')[0],
        'description': ('默认服装：' + known(card.get('默认服装') or card.get('服装')))
                       if known(card.get('默认服装') or card.get('服装')) else known(card.get('_desc')),
        'physical_features': script_contract.field_features(known(card.get('物理特征') or card.get('外貌特征'))),
    } for name, card in char_rows]
    scenes = [{
        'name': re.sub(r'^场景\s*\d+[：:]', '', name).strip() or name,
        'description': known(card.get('空间锚点') or card.get('场景描述') or card.get('_desc')),
        'time_of_day': known(card.get('光照方向') or card.get('时间')),
        'timeline': known(card.get('时间线')),
    } for name, card in scene_rows]
    props = [{
        'name': name,
        'description': known(card.get('说明') or card.get('用途') or card.get('_desc')),
        'holder': known(card.get('持有者') or card.get('归属')),
    } for name, card in prop_rows]
    return {
        'character_manifest.json': script_contract.manifest('character', chars),
        'scene_manifest.json': script_contract.manifest('scene', scenes),
        'prop_manifest.json': script_contract.manifest('prop', props),
    }

