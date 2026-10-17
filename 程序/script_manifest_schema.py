"""剧本阶段 manifest／物理特征／编号与校验的契约实现（L0）。

从 `script_contract` 拆出（R1618／Q9）："五类 manifest 的编号规则、物理特征字段化、
JSON Schema 与完整性检查"是同一件事，和自然剧本读写／阶段锁／交付规格互不相干；
混在一个文件里超过 1500 行上限，改动时定位成本高。

`script_contract` 仍按原名转发本模块的公开名（兼容既有 `script_contract.X` 调用），
所以新代码可以直接 import 本模块，老调用点不必改。
"""
from __future__ import annotations

import re
from pathlib import Path

from agent.core import read
from script_manifest_contract import HEADER, KIND_OF_MANIFEST, KINDS, MANIFESTS, MANIFEST_OF_KIND

# 剧本准备阶段目录（原定义在 script_contract，随本模块一起搬来）；旧名 00_script 只在
# stage_layout.LEGACY_STAGE_ALIASES 里作为只读别名，不再作为落盘目录。
STAGE = '01剧本准备'
STRUCTURE_STAGE = '02剧本结构'
STORYBOARD_STAGE = '03初步分镜'


# manifest 文件名 → (产出它的 SKILL, 这份产物落在哪个阶段目录 output/)
PRODUCERS = {
    'character_manifest.json': ('script-character-extraction', STRUCTURE_STAGE),
    'scene_manifest.json': ('script-character-extraction', STRUCTURE_STAGE),
    'prop_manifest.json': ('script-character-extraction', STRUCTURE_STAGE),
    'scene_breakdown.json': ('storyboard-scene-breakdown', STORYBOARD_STAGE),
    'emotion_curve.json': ('pipeline-script-preparation', STAGE)}
PRODUCER_SKILLS = tuple(sorted({skill for skill, _folder in PRODUCERS.values()}))

# ── 编号口径（任务 7）────────────────────────────────────────────────────────
# 角色／场景／道具沿用资产清单那一套（CHAR_／LOC_／PROP_），场次拆分与情绪节拍各给一套。
PREFIX = {'character': 'CHAR', 'scene': 'LOC', 'prop': 'PROP',
          'scene_breakdown': 'SC', 'emotion_curve': 'EC'}
PREFIX_OF = dict((value, key) for key, value in PREFIX.items())
ID_FIELD = {'character': 'character_id', 'scene': 'scene_id', 'prop': 'prop_id',
            'scene_breakdown': 'breakdown_id', 'emotion_curve': 'beat_id'}
PATTERN = dict((kind, '^%s_[0-9]{3,}$' % prefix) for kind, prefix in PREFIX.items())

# ── 物理特征五件（任务 6）────────────────────────────────────────────────────
PHYSICAL_KEYS = ('skin_tone', 'hair', 'eyes', 'distinctive_marks', 'body_type')
PHYSICAL_LABELS = {'skin_tone': '肤色', 'hair': '发型发色', 'eyes': '眼睛',
                   'distinctive_marks': '标志性特征', 'body_type': '体型'}
# 拆字段用的关键词：一个片段命中哪个键就进哪个键；命中多个时取「命中的词最长」的那个
# （先认长的，别让「短发」被「发」抢走），一样长就按这张表的先后。
HINTS = (
    ('skin_tone', ('肤色', '冷白', '白皙', '苍白', '小麦色', '小麦', '蜜色', '古铜', '黝黑', '偏黑')),
    ('hair', ('发型', '发色', '刘海', '马尾', '丸子头', '长辫', '麻花辫', '短发', '长发', '卷发',
              '直发', '银发', '黑发', '白发', '金发', '光头', '发')),
    ('eyes', ('眼型', '杏眼', '丹凤眼', '桃花眼', '双眼皮', '单眼皮', '瞳色', '蓝瞳', '金瞳',
              '琥珀瞳', '眼', '瞳', '眸')),
    ('distinctive_marks', ('胎记', '疤痕', '伤疤', '伤痕', '记号', '纹身', '刺青', '义肢', '机械臂',
                           '眼罩', '绷带', '耳钉', '耳饰', '断眉', '疤', '痣')),
    ('body_type', ('身形', '体型', '身材', '高挑', '高大', '矮小', '娇小', '魁梧', '修长', '匀称',
                   '结实', '瘦', '胖', '壮')))
# 拆句子的标点：中文逗号顿号分号句号全角冒号，加半角斜杠竖线与空白。
SPLIT = '\u3001\uff0c,\uff1b;\u3002\uff1a:/\uff5c \n\t'

# ── 任务 2／3／4 的审计表 ────────────────────────────────────────────────────
# 任务 3 的四种分类与对应的处理动作（唯一口径，报告照它写）。
CATEGORIES = {'核心': '保留并强化结构化', '支撑': '保留并降级为辅助',
              '重叠': '合并到唯一归属', '冗余': '删除或归档到 _archive/'}
# (SKILL 名, 分类, 改造后归属, 理由)——分类与理由来自任务 2 的四问法与任务 3 的归类。
AUDIT = (
    ('script-structured-generation', '核心', '剧本结构 · 结构化剧本生成',
     '剧本正稿的唯一产出者，拆镜、配音、字幕都读它；三类 manifest 的字段由它定型'),
    ('script-character-extraction', '核心', '剧本结构 · 角色与设定提取',
     '角色／场景／道具三条资产链路的唯一入口，直接支撑「资产」可控性'),
    ('script-dialogue-polish', '重叠', 'script-structured-generation（台词那一段）',
     '台词本来就是正稿的一部分，润色结果没有独立的消费方，不单独出文件'),
    ('script-worldbuilding', '支撑', '剧本结构 · script-structured-generation（设定那一段）',
     '世界观是分镜与资产的背景，但不产出可校验的编号，产物落 docs（人读）'),
    ('screenplay-production-line', '支撑', '剧本准备 · 外部包总入口',
     '受控默认值只提供 creative-writing；不自动展开内部子 SKILL，且无 output/manifest 声明'),
    ('screenplay-writer', '支撑', '剧本准备 · 外部包总入口',
     '受控默认值只提供 creative-writing；不自动展开内部子 SKILL，且无 output/manifest 声明'),
    ('script-forging', '支撑', '剧本准备 · 外部包总入口',
     '受控默认值只提供 creative-writing；不自动展开内部子 SKILL，且无 output/manifest 声明'),
    ('短剧编剧搭子', '支撑', '剧本准备 · 外部包总入口',
     '受控默认值只提供 creative-writing；不自动展开内部子 SKILL，且无 output/manifest 声明'),
    ('编剧技能集', '支撑', '剧本准备 · 外部包总入口',
     '受控默认值只提供 creative-writing；不自动展开内部子 SKILL，且无 output/manifest 声明'))

# ── 任务 3 的收口（第 8 轮）：重叠／支撑的那两个并到哪一段去 ──────────────────
# 「合并／降级」在这一步都不是删文件：SKILL 文件留着（注册表与阶段并行表按这一层挂步，
# 按各阶段的实际分布挂步，变的是产物归属——不再单独出文件，并回唯一归属者的相应那一段。
MERGE_OWNER = 'script-structured-generation'
# (SKILL 名, 并回归属者的哪一段, 产物落在哪)
MERGED = (
    ('script-dialogue-polish', '台词那一段', '（并回正稿，不单独出文件）'),
    ('script-worldbuilding', '设定那一段', 'docs/world_bible.md'))
MERGED_SKILLS = tuple(skill for skill, _part, _landing in MERGED)
MERGE_PART = dict((skill, part) for skill, part, _landing in MERGED)
MERGE_LANDING = dict((skill, landing) for skill, _part, landing in MERGED)


# ── 编号 ────────────────────────────────────────────────────────────────────
def new_id(kind, index):
    """按类别发号：character → CHAR_001。"""
    return '%s_%03d' % (PREFIX.get(kind, 'X'), int(index))


def kind_of_id(aid):
    """编号 → 类别（认不出来返回空串）。"""
    match = re.match(r'^([A-Z]+)_[0-9]{3,}$', str(aid or '').strip())
    return PREFIX_OF.get(match[1], '') if match else ''


def id_field(kind):
    """这一类条目的编号写在哪个键上。"""
    return ID_FIELD.get(kind, '')


def id_of(kind, item):
    """这一条现在的编号（没有就是空串）。"""
    field = id_field(kind)
    return str((item or {}).get(field) or '').strip() if field else ''


# ── 字段与默认值 ────────────────────────────────────────────────────────────
def defaults(kind):
    """这一类条目的键与空壳（normalize 拿它补缺，只补不改）。"""
    if kind == 'character':
        return {'character_id': '', 'name': '', 'aliases': [], 'description': '',
                'physical_features': dict((key, '') for key in PHYSICAL_KEYS),
                'image_prompt': ''}
    if kind == 'scene':
        return {'scene_id': '', 'name': '', 'description': '', 'time_of_day': '',
                'weather': '', 'image_prompt': ''}
    if kind == 'prop':
        return {'prop_id': '', 'name': '', 'description': '', 'holder': '', 'image_prompt': ''}
    if kind == 'scene_breakdown':
        return {'breakdown_id': '', 'episode_id': '', 'scene_id': '', 'order': 0,
                'time_place': '', 'characters': [], 'task': '', 'boundary': ''}
    if kind == 'emotion_curve':
        return {'beat_id': '', 'episode_id': '', 'scene_id': '', 'order': 0, 'intensity': 0,
                'reason': '', 'hook': '', 'turn': ''}
    return {}


def _copy(value):
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    return value


def normalize(kind, item, index=1):
    """补缺的键与缺的编号（返回一份新 dict）：已有的值一个都不动。"""
    if not isinstance(item, dict):
        return None
    out = dict(item)
    for key, value in defaults(kind).items():
        if key not in out:
            out[key] = _copy(value)
    field = id_field(kind)
    if field and not str(out.get(field) or '').strip():
        out[field] = new_id(kind, index)
    if kind == 'character':
        out['physical_features'] = field_features(out.get('physical_features'))
    if kind in ('scene_breakdown', 'emotion_curve') and not out.get('order'):
        out['order'] = int(index)
    return out


# ── 任务 6：物理特征字段化 ──────────────────────────────────────────────────
def _pieces(body):
    """按中文标点把一句话切成片段（不用正则，省得当心转义）。"""
    out, buf = [], []
    for char in str(body or ''):
        if char in SPLIT:
            out.append(''.join(buf))
            buf = []
        else:
            buf.append(char)
    out.append(''.join(buf))
    return [piece.strip() for piece in out if piece.strip()]


def _hit(piece):
    """这个片段该进哪个键：命中的词最长的那个；没命中返回空串。"""
    best, size = '', 0
    for key, words in HINTS:
        for word in words:
            if word in piece and len(word) > size:
                best, size = key, len(word)
    return best


def split_features(text):
    """一整句自然语言 → 五个字段（认不出来的片段留在 raw 里，原文不丢）。"""
    out = dict((key, '') for key in PHYSICAL_KEYS)
    body = str(text or '').strip()
    if not body:
        return out
    rest = []
    for piece in _pieces(body):
        key = _hit(piece)
        if not key:
            rest.append(piece)
            continue
        out[key] = (out[key] + '\u3001' + piece) if out[key] else piece
    if rest:
        out['raw'] = '\u3001'.join(rest)
    return out


def field_features(value):
    """把 physical_features 收成五个字段：字符串＝整句自然语言，按关键词拆；对象＝补齐缺的键。

    老写法（一整句塞在其中一个字段里）也认：只有一个字段有值、而它拆得出两个以上字段时，
    就地拆开——任务 6 要的就是「不许拿自然语言顶上」。
    """
    if not isinstance(value, dict):
        return split_features(value)
    out = dict(value)
    for key in PHYSICAL_KEYS:
        item = out.get(key)
        out[key] = item if isinstance(item, str) else ('' if item is None else str(item))
    filled = [key for key in PHYSICAL_KEYS if out[key].strip()]
    if len(filled) == 1:
        split = split_features(out[filled[0]])
        if len([key for key in PHYSICAL_KEYS if split[key].strip()]) >= 2:
            out.update(split)
    return out


# ── 一份 manifest ───────────────────────────────────────────────────────────
def manifest(kind, items):
    """把条目收成一份 manifest：抬头三件（manifest／kind／items）＋ 补好缺的键与编号。"""
    return {'manifest': MANIFEST_OF_KIND.get(kind, ''), 'kind': kind,
            'items': [normalize(kind, item, index)
                      for index, item in enumerate(items or [], 1) if isinstance(item, dict)]}


def items_of(data):
    """从一份 manifest 里取条目（两种写法都认：带抬头的对象，或直接一个数组）。"""
    values = data.get('items') if isinstance(data, dict) else data
    return [item for item in values if isinstance(item, dict)] if isinstance(values, list) else []


def manifest_name(data, fallback=''):
    """这一份的抬头名（没写抬头时用调用方给的名字兜底）。"""
    return str(data.get('manifest') or fallback) if isinstance(data, dict) else str(fallback)


# ── 任务 7：ID 唯一性 ───────────────────────────────────────────────────────
def duplicate_ids(manifests):
    """所有 manifest 里重复或缺失的编号（跨份撞号也算）。空列表＝全部唯一。

    manifests 是 {manifest 文件名: 那一份数据}；少写的那几类自动跳过。
    """
    seen, problems = {}, []
    for name in MANIFESTS:                       # 顺序固定，报告每次一样
        data = (manifests or {}).get(name)
        if data is None:
            continue
        kind = KIND_OF_MANIFEST[name]
        for position, item in enumerate(items_of(data), 1):
            aid = id_of(kind, item)
            if not aid:
                problems.append('%s：第 %d 条还没有编号' % (name, position))
                continue
            if aid in seen:
                problems.append('%s：%s 与 %s 撞号' % (name, aid, seen[aid]))
                continue
            seen[aid] = name
    return problems


def unique_ids(manifests):
    """所有 manifest 的编号都不重（任务 7 的验收口径）。"""
    return not duplicate_ids(manifests)


def _spare(kind, taken):
    """发一个还没被占的号（从 001 往上找）。"""
    index = 1
    while new_id(kind, index) in taken:
        index += 1
    return new_id(kind, index)


def reassign_ids(manifests):
    """撞号的条目重发号（先出现的那个号留着）：返回 (改好的 manifests, 改动说明)。

    重发号只往空号上排，所以原本占着那个号的条目会跟着让位（每一条改动都记在说明里，
    一条不多一条不少）。形状照旧：原来是一份带抬头的对象，改完还是对象；原来是一个数组，
    改完还是数组。
    """
    taken, changes, fixed = set(), [], {}
    for name in MANIFESTS:
        data = (manifests or {}).get(name)
        if data is None:
            continue
        kind = KIND_OF_MANIFEST[name]
        items = []
        for item in items_of(data):
            item = dict(item)
            aid = id_of(kind, item)
            if aid and aid not in taken:
                taken.add(aid)
            else:
                fresh = _spare(kind, taken)
                taken.add(fresh)
                changes.append('%s：%s → %s' % (name, aid or '（空编号）', fresh))
                item[ID_FIELD[kind]] = fresh
            items.append(item)
        fixed[name] = dict(data, items=items) if isinstance(data, dict) else items
    return fixed, changes


# ── 校验 ────────────────────────────────────────────────────────────────────
def validate(kind, item):
    """这一条的问题（空列表＝通过）。规则就是这一类 manifest 的必填与值域。"""
    problems = []
    if not isinstance(item, dict):
        return ['条目必须是对象']
    field = id_field(kind)
    aid = id_of(kind, item)
    if not aid:
        problems.append('缺少 %s' % field)
    elif not re.match(PATTERN.get(kind, ''), aid):
        problems.append('%s 编号不合规（应为 %s_###）：%s' % (field, PREFIX.get(kind, ''), aid))
    if kind != 'emotion_curve' and not str(item.get('name') or '').strip():
        problems.append('缺少 name')
    if kind == 'character':
        features = item.get('physical_features')
        if isinstance(features, str) and features.strip():
            problems.append('物理特征要字段化（%s），别写成整句自然语言'
                            % '\u3001'.join(PHYSICAL_KEYS))
        elif features is not None and not isinstance(features, (dict, str)):
            problems.append('physical_features 必须是对象或字符串')
        elif not any(str((features or {}).get(key) or '').strip() for key in PHYSICAL_KEYS):
            problems.append('物理特征五件还是空的（%s）' % '\u3001'.join(PHYSICAL_KEYS))
    if kind in ('scene_breakdown', 'emotion_curve'):
        if not re.match(PATTERN['scene'], str(item.get('scene_id') or '').strip()):
            problems.append('scene_id 要写场景编号（LOC_###）：%r' % (item.get('scene_id'),))
    if kind == 'scene_breakdown':
        for member in item.get('characters') or []:
            if not re.match(PATTERN['character'], str(member or '').strip()):
                problems.append('characters 里要写角色编号（CHAR_###）：%r' % (member,))
    if kind == 'emotion_curve':
        value = item.get('intensity')
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 10:
            problems.append('intensity 须为 1～10 的整数：%r' % (value,))
    return problems


# ── 任务 8：五份交付物里「Schema／示例／完整性」这三份的落点 ────────────────
def _box(props, required):
    return {'type': 'object', 'required': list(required), 'properties': props,
            'additionalProperties': True}


def _features_box():
    return {'type': 'object', 'description': '物理特征（五件字段化，任务 6）',
            'properties': dict((key, {'type': 'string', 'description': PHYSICAL_LABELS[key]})
                               for key in PHYSICAL_KEYS),
            'additionalProperties': True}


def _item_box(kind):
    """一类 manifest 的一条目（JSON Schema 里的 items）。"""
    text = {'type': 'string'}
    boxes = {
        'character': (_box({'character_id': {'type': 'string', 'pattern': PATTERN['character']},
                            'name': {'type': 'string', 'minLength': 1},
                            'aliases': {'type': 'array', 'items': text},
                            'description': text, 'physical_features': _features_box(),
                            'image_prompt': text},
                           ('character_id', 'name', 'physical_features')),),
        'scene': (_box({'scene_id': {'type': 'string', 'pattern': PATTERN['scene']},
                        'name': {'type': 'string', 'minLength': 1}, 'description': text,
                        'time_of_day': text, 'weather': text, 'image_prompt': text},
                       ('scene_id', 'name')),),
        'prop': (_box({'prop_id': {'type': 'string', 'pattern': PATTERN['prop']},
                       'name': {'type': 'string', 'minLength': 1}, 'description': text,
                       'holder': {'type': 'string', 'description': '持有者角色编号，没有就留空'},
                       'image_prompt': text},
                      ('prop_id', 'name')),),
        'scene_breakdown': (_box({'breakdown_id': {'type': 'string',
                                                   'pattern': PATTERN['scene_breakdown']},
                                  'episode_id': text,
                                  'scene_id': {'type': 'string', 'pattern': PATTERN['scene']},
                                  'order': {'type': 'integer', 'minimum': 1},
                                  'time_place': text,
                                  'characters': {'type': 'array',
                                                 'items': {'type': 'string',
                                                           'pattern': PATTERN['character']}},
                                  'task': text, 'boundary': text},
                                 ('breakdown_id', 'scene_id', 'order')),),
        'emotion_curve': (_box({'beat_id': {'type': 'string', 'pattern': PATTERN['emotion_curve']},
                                'episode_id': text,
                                'scene_id': {'type': 'string', 'pattern': PATTERN['scene']},
                                'order': {'type': 'integer', 'minimum': 1},
                                'intensity': {'type': 'integer', 'minimum': 1, 'maximum': 10},
                                'reason': text, 'hook': text, 'turn': text},
                               ('beat_id', 'scene_id', 'intensity')),)}
    return boxes[kind][0]


def schema():
    """五类 manifest 的 JSON Schema（交付物 2）：manifest 文件名 → 一份 draft 2020-12 Schema。"""
    out = {}
    for kind in KINDS:
        name = MANIFEST_OF_KIND[kind]
        out[name] = {'$schema': 'https://json-schema.org/draft/2020-12/schema',
                     'title': '漫剧助手 %s（第 70 期任务 5～7）' % name,
                     'type': 'object', 'required': list(HEADER),
                     'properties': {'manifest': {'const': name}, 'kind': {'const': kind},
                                    'items': {'type': 'array', 'items': _item_box(kind)}},
                     'additionalProperties': True}
    return out


# 交付物 3 的那句示例：一句话里五个字段都能认出来。
SAMPLE = '肤色冷白，黑色短发，杏眼，左眉一道浅疤，身形修长'


def sample_character_manifest():
    """交付物 3：改造后的 character_manifest.json 示例（两个角色，物理特征全部字段化）。"""
    return manifest('character', (
        {'character_id': 'CHAR_001', 'name': '林小满', 'aliases': ['小满'],
         'description': '十七岁高中生，米色针织衫配深色长裤',
         'physical_features': SAMPLE,
         'image_prompt': '林小满，十七岁少女，冷白肤色，黑色齐耳短发，杏眼，左眉一道浅疤，'
                         '身形修长，米色针织衫'},
        {'character_id': 'CHAR_002', 'name': '陆时', 'aliases': [],
         'description': '二十出头，深灰风衣，常带着一块旧怀表',
         'physical_features': {'skin_tone': '小麦色', 'hair': '深棕微卷短发', 'eyes': '狭长眼',
                               'distinctive_marks': '左手腕一道旧疤', 'body_type': '高挑结实'},
         'image_prompt': '陆时，小麦肤色，深棕微卷短发，狭长眼，左手腕一道旧疤，高挑结实，深灰风衣'}))


def completeness(folder):
    """剧本阶段产出的完整性检查（交付物 5）：每一类一行（名字／状态／说明）。

    状态是三选一：已产出／缺失／有问题。folder 传产出方阶段目录的 output/（如 02剧本结构/output）。
    """
    root = Path(folder)
    rows = []
    for name in MANIFESTS:
        path = root / name
        kind = KIND_OF_MANIFEST[name]
        if not path.is_file():
            rows.append((name, '缺失', '这一份还没产出'))
            continue
        try:
            data = read(path)
        except (OSError, ValueError) as exc:
            rows.append((name, '有问题', '读不出来：%s' % exc))
            continue
        items = items_of(data)
        bad = list(duplicate_ids({name: data}))
        for index, item in enumerate(items, 1):
            bad += ['第 %d 条：%s' % (index, text) for text in validate(kind, item)]
        if bad:
            rows.append((name, '有问题', '；'.join(bad[:3])))
        else:
            rows.append((name, '已产出', '%d 条，编号唯一' % len(items)))
    return tuple(rows)
