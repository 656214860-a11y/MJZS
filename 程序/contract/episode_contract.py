"""镜头 JSON 的纯契约校验。

此模块刻意不依赖项目服务或阶段编排；项目创建、剧本和分镜都可以安全复用。
``writing`` 仍重导出这些函数，兼容既有插件和脚本。
"""
from __future__ import annotations

import math
import re
from pathlib import Path, PureWindowsPath

from contract.media_signature import is_png


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
                and isinstance(shot.get('duration'), int) and 2 <= shot['duration'] <= 15)
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
        if not isinstance(shot_id, str) or not re.fullmatch(r'(?:EP\d{3,}_)?SH\d{3,}', shot_id): errors.append(tag + '编号须为SH001或EP001_SH001格式')
        if isinstance(shot_id, str) and shot_id in ids: errors.append(tag + '编号重复')
        if isinstance(shot_id, str): ids.add(shot_id)
        duration = shot.get('duration')
        valid_duration = number(duration) and isinstance(duration, int) and 2 <= duration <= 15
        if not valid_duration: errors.append(tag + '时长必须为2–15的整数秒')
        else: total += duration
        if not isinstance(shot.get('title'), str) or not shot['title'].strip(): errors.append(tag + '缺少title')
        prompt = shot.get('video_prompt')
        if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 1500: errors.append(tag + 'video_prompt须为1–1500字符')
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
