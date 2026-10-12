"""字幕与对白脚本的无界面发布服务。"""
from pathlib import Path
import json
import logging
import uuid

from project_stages import subtitles
from subtitle_timing import calibrate_entries, rows_from_entries, validate_entries
from service_contract import SystemError, UserError, success

LOGGER = logging.getLogger(__name__)


def _publish_result(publish, data, *args, **kwargs):
    if not callable(publish):
        raise TypeError('字幕文本发布需要 L3 注入发布器')
    try:
        publish(*args, **kwargs)
    except OSError:
        LOGGER.exception('字幕或对白脚本发布失败')
        return SystemError('字幕或对白脚本保存失败，请检查文件权限和磁盘空间后重试。')
    return success(data)


def publish_srt_text(target, text, *, publish=None):
    """校验行尾并原子发布由调用方指定位置的字幕成果。"""
    target_path = Path(target)
    return _publish_result(publish, target_path, target_path, str(text))


def pending_calibration(episode, audio=None):
    """导出前先列出仍未按实际音频校准的句子（只读，不改文件）。"""
    _entries, report = calibrate_entries(episode, audio=audio)
    return report.get('uncalibrated', [])


def _calibrated(episode, audio=None):
    """算校准轴并先做时间校验；非法时间（负数／重叠／越界等）直接抛错。"""
    entries, report = calibrate_entries(episode, audio=audio)
    validate_entries(entries, report.get('total'))
    return entries, report


def export_srt(project_root, episode, *, publish, audio=None):
    """准备 SRT：按校准轴（有音频则按真实音频，否则按句长）渲染，再交注入发布器原子发布。"""
    entries, report = _calibrated(episode, audio)
    if not entries:
        return UserError('当前分镜没有对白，无法导出字幕')
    target = subtitles(Path(project_root)) / ('对白_' + uuid.uuid4().hex[:6] + '.srt')
    result = _publish_result(publish, (target, report), target, '\n'.join(rows_from_entries(entries)),
                             lambda value: bool(value.strip()), lambda _target: None,
                             encoding='utf-8-sig')
    if result.ok:
        calibration = export_calibration(project_root, episode, publish=publish, audio=audio)
        if not calibration.ok:
            LOGGER.warning('字幕校准状态写入失败：%s', calibration.reason)
    return result


def export_dialogue_script(project_root, episode, assets, *, publish, audio=None):
    """准备供配音核对的对白脚本，并交由注入发布器原子发布。"""
    entries, report = _calibrated(episode, audio)
    if not entries:
        return UserError('当前分镜没有对白，无法导出对白脚本')
    assets = assets if isinstance(assets, dict) else {}
    shots = episode.get('shots', []) if isinstance(episode, dict) else []
    lines, current = [], None
    for sid, speaker, text, start, end in entries:
        if sid != current:
            shot = next((item for item in shots if isinstance(item, dict) and item.get('id') == sid), None)
            lines.append(f"{sid}  {shot.get('title', '') if shot else ''}")
            current = sid
        item = assets.get(speaker) if isinstance(assets.get(speaker), dict) else {}
        name = item.get('name') or speaker or '未注明角色'
        lines.append(f"  {name}（{start:.1f}-{end:.1f}秒）：{text}")
    target = subtitles(Path(project_root)) / ('对白脚本_' + uuid.uuid4().hex[:6] + '.txt')
    return _publish_result(publish, (target, report), target, '\n'.join(lines),
                           lambda value: bool(value.strip()), lambda _target: None,
                           encoding='utf-8-sig')


def export_calibration(project_root, episode, *, publish, audio=None):
    """把字幕来源音频摘要与校准状态写成字幕目录下的 字幕校准.json。"""
    _entries, report = _calibrated(episode, audio)
    target = subtitles(Path(project_root)) / '字幕校准.json'
    return _publish_result(publish, (target, report), target,
                           json.dumps(report, ensure_ascii=False, indent=2),
                           lambda value: bool(value.strip()), lambda _target: None,
                           encoding='utf-8')
