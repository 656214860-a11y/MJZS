# -*- coding: utf-8 -*-
"""批次划分与分镜 JSON 契约（v0.8 任务 4／10）。

任务 4 给的是跑量剧的批次规则，任务 10 给的是切分算法与镜头对象的九个必填字段。

规则表（任务 4）：

- 单镜时长 2–5 秒（默认 3 秒，复杂动作 5 秒）
- 单批镜头数 3–5 个
- 单批总时长 默认 ≤18 秒，特殊段落 ≤25 秒
- 单集镜头数 18–25 个
- 单集批次 5–7 组
- 100 集总批次约 500–700 组

切分算法（任务 10，归属分镜定稿）：遍历分镜 JSON，scene_id／character_ids／costume_id 任一变化
就切新批次；同一批次内镜头数不超过 4（BATCH_MAX_SHOTS，比任务 4 的 3–5 这个**设计区间**更紧一档，
取整落在区间下沿，先保证不超长），累计时长不超过 18 秒。

新增的九个字段一律「有默认值 ＋ 有校验规则」（硬约束 7）：老分镜 JSON 只有 id／characters／
location／duration 也能跑——normalize() 从老字段推出新字段的默认值，一个键都不用先改。

镜头字段的单一事实源在 ``contract.episode_contract``（轮 6C·D7）：本表的九个批次字段
与 ``SHOT_FIELD_SPECS`` 的镜头字段一起构成 ``schema()`` 的镜头 properties；
``validate()`` 的时长区间与 ``estimated_duration`` 的 schema 上下限同样取自那里。
"""
import copy
import re

from contract.episode_contract import SHOT_DURATION_RANGE, SHOT_FIELD_SPECS

SHOT_SECONDS = (2, 5)
DEFAULT_SECONDS = 3
COMPLEX_SECONDS = 5
BATCH_SHOTS = (3, 5)
BATCH_MAX_SHOTS = 4
BATCH_SECONDS = 18
BATCH_SECONDS_LONG = 25
EPISODE_SHOTS = (18, 25)
EPISODE_BATCHES = (5, 7)
EPISODE_TOTAL_BATCHES = (500, 700)

# 镜头对象的九个必填字段（任务 10）：(新字段名, 默认值来源, 说明, schema() properties 片段)。
# schema() 的 required 与 properties 键集由本表派生，改字段只改这里。
REF_ROLE_SCHEMA = {'type': 'object', 'required': ['responsibility', 'exclude'],
                   'properties': {'responsibility': {'type': 'string', 'minLength': 1},
                                  'exclude': {'type': 'string', 'minLength': 1}}}
SHOT_FIELDS = (
    ('shot_id', 'id', '镜头编号（S01／SH001）',
     {'type': 'string', 'pattern': '^(EP[0-9]{3,}_)?(S|SH)[0-9]{2,}$'}),
    ('scene_id', 'location', '场景编号（同 location）',
     {'type': 'string', 'minLength': 1}),
    ('character_ids', 'characters', '出场角色编号数组（同 characters）',
     {'type': 'array', 'items': {'type': 'string'}}),
    ('costume_id', '', '状态变体编号（CST-##），指向资产 JSON 的 state_variants',
     {'type': 'string', 'pattern': '^CST-[0-9]{2,}$|^$'}),
    ('batch_id', '', '批次编号（B01…），由 group() 切分后回填',
     {'type': 'string', 'pattern': '^B[0-9]{2,}$'}),
    ('character_refs', '', '参考图标签数组（@图片1…），与 character_ids 一一对应',
     {'type': 'array', 'items': {'type': 'string', 'pattern': '^@'}}),
    ('reference_roles', '', '每个参考图标签的职责声明：responsibility ＋ exclude',
     {'type': 'object', 'additionalProperties': REF_ROLE_SCHEMA}),
    ('continuity_flags', '', '跨镜必须保持的锚点（角色耳环、场景光源方向…）',
     {'type': 'array', 'items': {'type': 'string'}}),
    ('estimated_duration', 'duration', '生成用的估计时长（秒），批次划分只看它',
     {'type': 'integer', 'minimum': SHOT_DURATION_RANGE[0], 'maximum': SHOT_DURATION_RANGE[1],
      'description': '批次划分只看它；设计区间 %d–%d 秒' % SHOT_SECONDS}),
)
TRIPLET = ('scene_id', 'character_ids', 'costume_id')
BATCH_ID = 'B%02d'
REF_LABEL = '@图片%d'
DEFAULT_RESPONSIBILITY = '面部、发型、服装'
DEFAULT_EXCLUDE = '场景、动作、镜头'


def number(value, default=0):
    """读一个整数秒（读不出来给默认值）。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return int(value)


def duration(shot):
    """这一镜的估计时长：先看 estimated_duration，再退回 duration。"""
    if not isinstance(shot, dict):
        return DEFAULT_SECONDS
    value = shot.get('estimated_duration')
    if value in (None, ''):
        value = shot.get('duration')
    return number(value, DEFAULT_SECONDS)


def normalize(shot, index=0):
    """按任务 10 补九个字段（只补缺的）：默认值从老字段推，老键一个都不动。"""
    out = dict(shot) if isinstance(shot, dict) else {}
    shots = out.get('character_ids')
    if not isinstance(shots, list):
        shots = out.get('characters')
    shots = [str(item).strip() for item in shots
             if isinstance(item, str) and str(item).strip()] if isinstance(shots, list) else []
    out.setdefault('shot_id', str(out.get('id') or '').strip() or 'S%02d' % (index + 1))
    out.setdefault('scene_id', str(out.get('location') or '').strip())
    out.setdefault('character_ids', shots)
    out.setdefault('costume_id', '')
    out.setdefault('batch_id', '')
    refs = out.get('character_refs')
    if not isinstance(refs, list) or not refs:
        refs = [REF_LABEL % (position + 1) for position in range(len(out['character_ids']))]
    out['character_refs'] = [str(item) for item in refs]
    roles = out.get('reference_roles')
    if not isinstance(roles, dict):
        roles = {}
    for ref in out['character_refs']:
        item = roles.get(ref)
        if not isinstance(item, dict):
            item = {}
        item.setdefault('responsibility', DEFAULT_RESPONSIBILITY)
        item.setdefault('exclude', DEFAULT_EXCLUDE)
        roles[ref] = item
    out['reference_roles'] = roles
    flags = out.get('continuity_flags')
    out['continuity_flags'] = [str(item) for item in flags if str(item).strip()] \
        if isinstance(flags, list) else []
    if out.get('estimated_duration') in (None, ''):
        out['estimated_duration'] = number(out.get('duration'), DEFAULT_SECONDS)
    return out


def triplet(shot):
    """三元组：scene_id ＋ character_ids ＋ costume_id（同一批次内必须一致）。"""
    item = shot if isinstance(shot, dict) else {}
    chars = item.get('character_ids')
    chars = tuple(str(value) for value in chars) if isinstance(chars, list) else ()
    return (str(item.get('scene_id') or ''), chars, str(item.get('costume_id') or ''))


def group(shots, long=False, max_shots=None, max_seconds=None):
    """切批次（任务 10 的算法）：三元组一变、或本批满了就切下一个。

    返回批次列表，每批是一组已经 normalize 过的镜头（batch_id 还没回填）。
    """
    cap_shots = BATCH_MAX_SHOTS if max_shots is None else max(1, int(max_shots))
    cap = (BATCH_SECONDS_LONG if long else BATCH_SECONDS) if max_seconds is None else max_seconds
    out, current, seconds = [], [], 0
    for index, raw in enumerate(shots or []):
        item = normalize(raw, index)
        if current and (triplet(item) != triplet(current[-1]) or len(current) >= cap_shots
                        or seconds + duration(item) > cap):
            out.append(tuple(current))
            current, seconds = [], 0
        current.append(item)
        seconds += duration(item)
    if current:
        out.append(tuple(current))
    return tuple(out)


def assign(shots, long=False, start=1):
    """切批次并回填 batch_id（B01…），返回「镜头对象 + batch_id」的平铺列表。"""
    out = []
    for offset, batch in enumerate(group(shots, long=long)):
        name = BATCH_ID % (start + offset)
        for item in batch:
            copy = dict(item)
            copy['batch_id'] = name
            out.append(copy)
    return tuple(out)


def batches(shots, long=False):
    """按 batch_id 归组：{'B01': (镜头…)}（没有 batch_id 的现切一次）。"""
    if shots and all(str(item.get('batch_id') or '').strip() for item in shots
                     if isinstance(item, dict)):
        out = {}
        for raw in shots:
            name = str(raw.get('batch_id')).strip()
            out.setdefault(name, [])
            out[name].append(raw)
        return {name: tuple(items) for name, items in sorted(out.items())}
    out = {}
    for offset, batch in enumerate(group(shots, long=long)):
        out[BATCH_ID % (offset + 1)] = batch
    return out


def validate(shot, index=0):
    """这一镜的九个新增字段有没有毛病（空列表＝通过）。老字段不查。"""
    if not isinstance(shot, dict):
        return ['第 %d 镜不是对象' % (index + 1)]
    data = normalize(shot, index)
    tag = '第 %d 镜' % (index + 1)
    problems = []
    if not re.fullmatch(r'(?:EP\d{3,}_)?(?:S|SH)\d{2,}', str(data['shot_id'])):
        problems.append(tag + 'shot_id 须为 S01 或 SH001 格式：' + str(data['shot_id']))
    if not str(data['scene_id']).strip():
        problems.append(tag + '缺少 scene_id')
    if not isinstance(data['character_ids'], list):
        problems.append(tag + 'character_ids 必须是数组')
    costume = str(data['costume_id']).strip()
    if costume and not re.fullmatch(r'CST-\d{2,}', costume):
        problems.append(tag + 'costume_id 须为 CST-## 格式：' + costume)
    if data['character_ids'] and not costume:
        problems.append(tag + '有角色却没有 costume_id（指向状态变体）')
    name = str(data['batch_id']).strip()
    if name and not re.fullmatch(r'B\d{2,}', name):
        problems.append(tag + 'batch_id 须为 B01 格式：' + name)
    if len(data['character_refs']) != len(data['character_ids']):
        problems.append(tag + 'character_refs 要与 character_ids 一一对应（%d ≠ %d）'
                        % (len(data['character_refs']), len(data['character_ids'])))
    for ref in data['character_refs']:
        item = data['reference_roles'].get(ref)
        if not isinstance(item, dict) or not str(item.get('responsibility') or '').strip() \
                or not str(item.get('exclude') or '').strip():
            problems.append(tag + '参考图缺少职责声明：' + str(ref))
    seconds = duration(data)
    if not SHOT_DURATION_RANGE[0] <= seconds <= SHOT_DURATION_RANGE[1]:
        problems.append(tag + 'estimated_duration 必须是 %d–%d 的整数秒：%s'
                        % (SHOT_DURATION_RANGE[0], SHOT_DURATION_RANGE[1], seconds))
    return problems


def advise(shots):
    """任务 4 那几条设计区间的提醒（不是错误：特殊段落本来就允许放宽）。"""
    shots = [normalize(item, index) for index, item in enumerate(shots or [])]
    if not shots:
        return ['还没有镜头']
    notes = []
    total = len(shots)
    if not EPISODE_SHOTS[0] <= total <= EPISODE_SHOTS[1]:
        notes.append('单集 %d 个镜头，不在 %d–%d 的设计区间' % (total, *EPISODE_SHOTS))
    grouped = batches(shots)
    if not EPISODE_BATCHES[0] <= len(grouped) <= EPISODE_BATCHES[1]:
        notes.append('单集 %d 个批次，不在 %d–%d 的设计区间' % (len(grouped), *EPISODE_BATCHES))
    for name, items in grouped.items():
        seconds = sum(duration(item) for item in items)
        if not BATCH_SHOTS[0] <= len(items) <= BATCH_SHOTS[1]:
            notes.append('%s 有 %d 个镜头，不在 %d–%d 的设计区间'
                         % (name, len(items), *BATCH_SHOTS))
        if seconds > BATCH_SECONDS:
            notes.append('%s 累计 %d 秒，超过 %d 秒（特殊段落才放宽到 %d 秒）'
                         % (name, seconds, BATCH_SECONDS, BATCH_SECONDS_LONG))
    for index, item in enumerate(shots, 1):
        seconds = duration(item)
        if not SHOT_SECONDS[0] <= seconds <= SHOT_SECONDS[1]:
            notes.append('第 %d 镜 %d 秒，不在 %d–%d 秒的设计区间'
                         % (index, seconds, *SHOT_SECONDS))
    return notes


def check_batches(shots):
    """批次本身是否合规（门禁 G-07）：每批 ≤4 镜、累计 ≤18 秒、三元组一致。"""
    problems = []
    for name, items in batches(shots).items():
        if len(items) > BATCH_MAX_SHOTS:
            problems.append('%s 有 %d 个镜头，超过每批 %d 个的上限'
                            % (name, len(items), BATCH_MAX_SHOTS))
        seconds = sum(duration(item) for item in items)
        if seconds > BATCH_SECONDS:
            problems.append('%s 累计 %d 秒，超过每批 %d 秒的上限' % (name, seconds, BATCH_SECONDS))
        kinds = {triplet(item) for item in items}
        if len(kinds) > 1:
            problems.append('%s 里的三元组不一致（scene_id／character_ids／costume_id 必须相同）' % name)
    return problems


def rules_rows():
    """批次时长规则表（交付物 3 的前半）。"""
    return (
        ('单镜时长', '%d–%d 秒（默认 %d 秒，复杂动作 %d 秒）'
         % (SHOT_SECONDS[0], SHOT_SECONDS[1], DEFAULT_SECONDS, COMPLEX_SECONDS), 'estimated_duration'),
        ('单批镜头数', '%d–%d 个' % BATCH_SHOTS, '设计区间；切分上限 %d' % BATCH_MAX_SHOTS),
        ('单批总时长', '默认 ≤%d 秒，特殊段落 ≤%d 秒' % (BATCH_SECONDS, BATCH_SECONDS_LONG),
         '累计 estimated_duration'),
        ('单集镜头数', '%d–%d 个' % EPISODE_SHOTS, '一集 1–2 分钟'),
        ('单集批次', '%d–%d 组' % EPISODE_BATCHES, '按三元组切分后落在这个区间'),
        ('100 集总批次', '约 %d–%d 组' % EPISODE_TOTAL_BATCHES, '跑量剧的排期口径'),
    )


def pseudocode():
    """分组算法伪代码（交付物 3 的后半）。"""
    return (
        'batch = []            # 当前批次\n'
        'batches = []\n'
        'seconds = 0\n'
        'for shot in 分镜JSON.shots:            # 按 JSON 里的先后顺序\n'
        '    triplet = (shot.scene_id, shot.character_ids, shot.costume_id)\n'
        '    if batch and (triplet != 上一个镜头的 triplet\n'
        '                  or len(batch) >= 4          # 同一批次不超过 4 镜\n'
        '                  or seconds + shot.estimated_duration > 18):  # 累计不超过 18 秒\n'
        '        batches.append(batch); batch = []; seconds = 0\n'
        '    batch.append(shot); seconds += shot.estimated_duration\n'
        'if batch: batches.append(batch)\n'
        'for index, batch in enumerate(batches, 1):\n'
        '    for shot in batch: shot.batch_id = "B%02d" % index\n'
        'return batches\n'
    )


def _shot_properties():
    """镜头 properties：九个批次字段（本表 SHOT_FIELDS）＋ 契约字段表（episode_contract）同源生成。"""
    props = {row[0]: copy.deepcopy(row[3]) for row in SHOT_FIELDS}
    props.update({name: copy.deepcopy(fragment) for name, _note, fragment in SHOT_FIELD_SPECS
                  if fragment is not None})
    return props


def schema():
    """分镜 JSON 的 Schema 片段（交付物 6）：字段集与契约事实表同源生成。"""
    shot = {
        'type': 'object',
        'required': [row[0] for row in SHOT_FIELDS],
        'properties': _shot_properties(),
        'additionalProperties': True,
    }
    return {'$schema': 'https://json-schema.org/draft/2020-12/schema',
            'title': '漫剧助手分镜 JSON（v0.8 含三元组／batch_id／reference_roles／continuity_flags）',
            'type': 'object',
            'required': ['episode_id', 'title', 'duration', 'shots'],
            'properties': {'episode_id': {'type': 'string'}, 'title': {'type': 'string'},
                           'duration': {'type': 'integer'},
                           'prompt_language': {'const': 'zh'},
                           'shots': {'type': 'array', 'minItems': 1, 'items': shot}},
            'additionalProperties': True}
