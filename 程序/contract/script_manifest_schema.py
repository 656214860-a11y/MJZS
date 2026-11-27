"""剧本阶段 manifest／编号与校验的契约实现（L0）。

从 `script_contract` 拆出（R1618／Q9）："五类 manifest 的编号规则、JSON Schema 与
完整性检查"是同一件事，和自然剧本读写／阶段锁／交付规格互不相干；
混在一个文件里超过 1500 行上限，改动时定位成本高。物理特征字段化的实体在
`contract.asset_contract`（轮 6A：asset_contract 须能被 script_manifest_contract
反向引用 KINDS 而不成环），本模块按原名再导出，调用点不必改。

`script_contract` 仍按原名转发本模块的公开名（兼容既有 `script_contract.X` 调用），
所以新代码可以直接 import 本模块，老调用点不必改。
"""
from __future__ import annotations

import re
from pathlib import Path

from agent.core import read
from contract.asset_contract import HINTS, PHYSICAL_KEYS, SPLIT, field_features, split_features
from contract.script_manifest_contract import (HEADER, KIND_OF_MANIFEST, MANIFEST_KINDS,
                                               MANIFESTS, MANIFEST_OF_KIND)

# 剧本准备阶段目录（原定义在 script_contract，随本模块一起搬来）；旧名 00_script 只在
# stage_layout.LEGACY_STAGE_ALIASES 里作为只读别名，不再作为落盘目录。
STAGE = '01剧本准备'
STRUCTURE_STAGE = '02剧本结构'
STORYBOARD_STAGE = '03初步分镜'


# manifest 文件名 → (产出者, 这份产物落在哪个阶段目录 output/)
PRODUCERS = {
    'character_manifest.json': ('stage:script_structure', STRUCTURE_STAGE),
    'scene_manifest.json': ('stage:script_structure', STRUCTURE_STAGE),
    'prop_manifest.json': ('stage:script_structure', STRUCTURE_STAGE),
    'scene_breakdown.json': ('stage:storyboard', STORYBOARD_STAGE),
    'emotion_curve.json': ('stage:script', STAGE)}
# 'stage:<阶段键>' 显式阶段产出者的常量、辅助函数与 PRODUCER_SKILLS 定义在文件底部。

# ── 编号口径（任务 7）────────────────────────────────────────────────────────
# 角色／场景／道具沿用资产清单那一套（CHAR_／LOC_／PROP_），场次拆分与情绪节拍各给一套。
PREFIX = {'character': 'CHAR', 'scene': 'LOC', 'prop': 'PROP',
          'scene_breakdown': 'SC', 'emotion_curve': 'EC'}
PREFIX_OF = dict((value, key) for key, value in PREFIX.items())
ID_FIELD = {'character': 'character_id', 'scene': 'scene_id', 'prop': 'prop_id',
            'scene_breakdown': 'breakdown_id', 'emotion_curve': 'beat_id'}
PATTERN = dict((kind, '^%s_[0-9]{3,}$' % prefix) for kind, prefix in PREFIX.items())

# ── 物理特征五件（任务 6）────────────────────────────────────────────────────
# PHYSICAL_KEYS／HINTS／SPLIT 与字段化函数已迁往 contract.asset_contract（轮 6A：
# asset_contract 要能被 script_manifest_contract 反向引用 KINDS 而不成环），
# 这里按原名再导出，script_contract 与既有调用点不受影响。
PHYSICAL_LABELS = {'skin_tone': '肤色', 'hair': '发型发色', 'eyes': '眼睛',
                   'distinctive_marks': '标志性特征', 'body_type': '体型'}

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
    for kind in MANIFEST_KINDS:
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


# ── 阶段产出者（RET-PIPELINE-COMPAT-L0）───────────────────────────────────
# PRODUCERS 的产出者是在册 SKILL 名，或 'stage:<阶段键>' 显式阶段产出者——后者不挂在
# 某个 SKILL 上，表示该阶段整体产出（emotion_curve.json 由剧本准备阶段产出）。
# 旧产出者 ID pipeline-script-preparation 经 LEGACY_STAGE_PRODUCERS 只读映射，
# 不改写用户已有 manifest 文件。
STAGE_PRODUCER_PREFIX = 'stage:'
LEGACY_STAGE_PRODUCERS = {
    'pipeline-script-preparation': 'stage:script',
    'script-character-extraction': 'stage:script_structure',
    'storyboard-scene-breakdown': 'stage:storyboard',
}


def is_stage_producer(producer):
    """产出者是否为 'stage:<阶段键>' 显式阶段产出者（去空白后前缀命中且阶段键非空）。"""
    text = str(producer or '').strip()
    return (text.startswith(STAGE_PRODUCER_PREFIX)
            and bool(text[len(STAGE_PRODUCER_PREFIX):].strip()))


def normalize_producer(producer):
    """产出者规范化（只读）：命中旧 ID 映射表返回规范阶段产出者，否则返回去空白原串。"""
    text = str(producer or '').strip()
    return LEGACY_STAGE_PRODUCERS.get(text, text)


def producer_stage_key(producer):
    """规范化后是阶段产出者则返回其阶段键（如 'script'），否则返回 ''。"""
    text = normalize_producer(producer)
    return (text[len(STAGE_PRODUCER_PREFIX):].strip()
            if is_stage_producer(text) else '')


# 只含实际在册的产出技能：阶段产出者不算 SKILL，从 PRODUCER_SKILLS 中排除。
PRODUCER_SKILLS = tuple(sorted({skill for skill, _folder in PRODUCERS.values()
                                if not is_stage_producer(skill)}))
