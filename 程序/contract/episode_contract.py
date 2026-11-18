"""镜头 JSON 的纯契约校验。

此模块刻意不依赖项目服务或阶段编排；项目创建、剧本和分镜都可以安全复用。
``writing`` 仍重导出这些函数，兼容既有插件和脚本。

镜头字段的单一事实源也在本模块（轮 6C·D7）：``SHOT_FIELD_SPECS`` 与取值常量
被 ``shot_batches.schema()``／``shot_batches.validate()``、本模块
``validate_episode()``／``duration_gap()``、``storyboard_contract.rules()``
三处呈现共用，改字段先改这里再同步呈现。
"""
from __future__ import annotations

import math
import re
from pathlib import Path, PureWindowsPath

from contract.media_signature import is_png


# ===== 镜头字段契约事实（轮 6C·D7：schema()／validate()／rules() 的单一事实源）=====
# 分镜镜头字段「有哪些、取值约束、提示词写法」只在这里定义一份；三个呈现方：
#   · schema()   → contract/shot_batches.schema() 的镜头 properties；
#   · validate() → 本模块 validate_episode()／duration_gap() 与
#                  contract/shot_batches.validate() 的判定；
#   · rules()    → contract/storyboard_contract.rules() 的提示词枚举。
# 改字段或约束先改这里再同步各呈现；rules() 输出须与改动前逐字一致
# （tests/fixtures/golden/storyboard_contract_rules.txt 黄金对照）。

#: 镜头编号：提示词样例（rules()）与合法格式（validate_episode 判定）。
SHOT_ID_SAMPLE = 'SH001'
SHOT_ID_PATTERN = r'(?:EP\d{3,}_)?SH\d{3,}'

#: 镜头 duration（秒）与 video_prompt（字符数）的合法区间。
SHOT_DURATION_RANGE = (2, 15)
VIDEO_PROMPT_RANGE = (1, 1500)

#: action_complexity 的合法取值（rules() 提示词与 shot_batches.schema() 枚举同源）。
ACTION_COMPLEXITY = ('simple', 'medium', 'complex')

#: 镜头字段清单：(字段名, rules() 括注, schema() properties 片段)。
#: - 括注 None → rules() 枚举里裸写字段名；否则渲染为 ``name（note）``。
#: - 片段 None → schema() 不单列 properties（字段仍可出现在镜头 JSON，
#:   靠 additionalProperties: True 放行）。
#: 次序即 rules() 字段枚举的次序；批次层九字段在 contract/shot_batches.SHOT_FIELDS。
SHOT_FIELD_SPECS = (
    ('id', '%s 格式且不重复' % SHOT_ID_SAMPLE,
     {'type': 'string', 'description': '兼容老字段：没有 shot_id 时由它推'}),
    ('title', None, {'type': 'string'}),
    ('duration', '%d–%d 的整数秒' % SHOT_DURATION_RANGE,
     {'type': 'integer', 'minimum': SHOT_DURATION_RANGE[0], 'maximum': SHOT_DURATION_RANGE[1]}),
    ('characters', '角色编号字符串数组',
     {'type': 'array', 'items': {'type': 'string'}}),
    ('location', '场景编号', {'type': 'string'}),
    ('props', '关键道具编号数组',
     {'type': 'array', 'items': {'type': 'string'}}),
    ('frame', '相对素材目录的 frames/镜头编号.png', {'type': 'string'}),
    ('frame_prompt', None, {'type': 'string'}),
    ('video_prompt', None, {'type': 'string'}),
    ('dialogue', None, {'type': 'array'}),
    ('action_complexity', '/'.join(ACTION_COMPLEXITY), {'enum': list(ACTION_COMPLEXITY)}),
    ('complexity_reason', None, None),
    ('ordinary_props', None, None),
    ('edit_duration', None, None),
    ('trim_in', None, None),
    ('trim_out', None, None),
)


def relative(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('首帧路径为空')
    path = PureWindowsPath(value)
    if path.is_absolute() or path.drive or '..' in path.parts or ':' in value:
        raise ValueError('首帧路径必须是项目内相对路径')
    return Path(*path.parts)


def number(value):
    """是不是一个能参与运算的有限数值（bool 不算数字）。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def edited_total(shots):
    """按 edit_duration（配 trim_in／trim_out）计算成片时长；不合法时返回 None。"""
    edits = []
    for shot in shots:
        if not isinstance(shot, dict):
            return None
        length = shot.get('edit_duration', shot.get('duration'))
        duration = shot.get('duration')
        if not (number(length) and number(duration) and 0 < length <= duration):
            return None
        if 'trim_in' in shot or 'trim_out' in shot:
            start = shot.get('trim_in', 0)
            end = shot.get('trim_out', duration)
            if not (number(start) and number(end) and 0 <= start < end <= duration and abs(end - start - length) < 0.001):
                return None
        edits.append(length)
    return sum(edits)


def duration_gap(episode):
    """整集时长与镜头合计不一致时返回 ``(声明时长, 镜头时长)``。"""
    if not isinstance(episode, dict) or 'duration' not in episode:
        return None
    shots = episode.get('shots')
    if not isinstance(shots, list):
        return None
    total = sum(shot.get('duration') for shot in shots
                if isinstance(shot, dict) and number(shot.get('duration'))
                and isinstance(shot.get('duration'), int)
                and SHOT_DURATION_RANGE[0] <= shot['duration'] <= SHOT_DURATION_RANGE[1])
    declared = episode['duration']
    if declared == total:
        return None
    edited = edited_total(shots)
    return None if number(declared) and edited is not None and abs(edited - declared) < 0.001 else (declared, total)


def validate_episode(episode, source, assets=None):
    source = Path(source).resolve()
    errors, warnings = [], []
    shots = episode.get('shots') if isinstance(episode, dict) else None
    if not isinstance(shots, list) or not shots:
        raise ValueError('JSON必须包含非空shots数组')
    if assets is not None and not isinstance(assets, dict):
        raise ValueError('assets.json必须是资产ID到资产信息的对象')
    if not isinstance(episode.get('episode_id'), str) or not episode['episode_id'].strip(): errors.append('缺少episode_id')
    if not isinstance(episode.get('title'), str) or not episode['title'].strip(): errors.append('缺少title')
    ids, total = set(), 0
    for index, shot in enumerate(shots, 1):
        tag = f'第{index}镜'
        if not isinstance(shot, dict): errors.append(tag + '不是对象'); continue
        shot_id = shot.get('id')
        if not isinstance(shot_id, str) or not re.fullmatch(SHOT_ID_PATTERN, shot_id): errors.append(tag + '编号须为%s或EP001_%s格式' % (SHOT_ID_SAMPLE, SHOT_ID_SAMPLE))
        if isinstance(shot_id, str) and shot_id in ids: errors.append(tag + '编号重复')
        if isinstance(shot_id, str): ids.add(shot_id)
        duration = shot.get('duration')
        valid_duration = number(duration) and isinstance(duration, int) and SHOT_DURATION_RANGE[0] <= duration <= SHOT_DURATION_RANGE[1]
        if not valid_duration: errors.append(tag + '时长必须为%d–%d的整数秒' % SHOT_DURATION_RANGE)
        else: total += duration
        if not isinstance(shot.get('title'), str) or not shot['title'].strip(): errors.append(tag + '缺少title')
        prompt = shot.get('video_prompt')
        if not isinstance(prompt, str) or not VIDEO_PROMPT_RANGE[0] <= len(prompt.strip()) <= VIDEO_PROMPT_RANGE[1]: errors.append(tag + 'video_prompt须为%d–%d字符' % VIDEO_PROMPT_RANGE)
        characters = shot.get('characters')
        if not isinstance(characters, list) or not all(isinstance(item, str) and item.strip() for item in characters): errors.append(tag + 'characters须为角色ID数组（空镜头可为空）'); characters = []
        location = shot.get('location')
        if not isinstance(location, str) or not location: errors.append(tag + '缺少location')
        if assets is not None:
            for asset_id in characters + ([location] if isinstance(location, str) else []):
                if asset_id not in assets: errors.append(tag + '未登记资产：' + asset_id)
        try:
            frame = (source / relative(shot.get('frame'))).resolve()
            if not frame.is_relative_to(source): raise ValueError('路径超出项目')
            if frame.suffix.lower() != '.png': raise ValueError('首帧须为PNG')
            if not frame.exists(): warnings.append(tag + '首帧尚未制作：' + shot['frame'])
            elif not frame.is_file() or not is_png(frame): raise ValueError('首帧不是有效PNG')
        except (ValueError, OSError) as exc: errors.append(tag + '：' + str(exc))
        lines, end = shot.get('dialogue', []), 0
        if not isinstance(lines, list): errors.append(tag + 'dialogue必须是数组'); continue
        for line in lines:
            if isinstance(line, str):
                if not line.strip(): errors.append(tag + '对白为空')
                else: warnings.append(tag + '对白尚未标注角色编号和字幕时间')
                continue
            if not isinstance(line, dict): errors.append(tag + '对白须为文字或对象'); continue
            if 'start' not in line and 'end' not in line:
                if not isinstance(line.get('text'), str) or not line['text'].strip(): errors.append(tag + '对白为空')
                else: warnings.append(tag + '对白尚未标注字幕时间')
                continue
            start, finish = line.get('start'), line.get('end')
            if not (number(start) and number(finish) and valid_duration and end <= start < finish <= duration): errors.append(tag + '对白时间越界或重叠')
            else: end = finish
            if line.get('speaker') not in characters: errors.append(tag + '对白角色不在本镜角色表')
            if not isinstance(line.get('text'), str) or not line['text'].strip(): errors.append(tag + '对白为空')
    if 'duration' in episode and episode['duration'] != total:
        edited = edited_total(shots)
        if number(episode['duration']) and edited is not None and abs(edited - episode['duration']) < 0.001: warnings.append(f'素材合计{total}秒，按edit_duration剪辑为{episode["duration"]}秒')
        else: errors.append(f'整集时长{episode["duration"]}秒，各镜时长合计{total}秒，两者必须一致')
    if errors:
        raise ValueError('\n'.join(errors))
    return {'shot_count': len(shots), 'total_seconds': total, 'warnings': warnings}
