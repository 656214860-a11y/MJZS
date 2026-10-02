"""字幕与对白脚本的无界面发布服务。"""
from pathlib import Path
import uuid

from project_stages import subtitles
from subtitle_timing import srt_rows, timed_entries


def publish_srt_text(target, text, *, publish=None):
    """校验行尾并原子发布由调用方指定位置的字幕成果。"""
    target_path = Path(target)
    if not callable(publish):
        raise TypeError('字幕文本发布需要 L3 注入发布器')
    publish(target_path, str(text))
    return target_path


def export_srt(project_root, episode, *, publish):
    """准备 SRT，并交由调用方注入的阶段发布器原子发布。"""
    rows, estimated = srt_rows(episode)
    if not rows:
        raise ValueError('当前分镜没有对白，无法导出字幕')
    target = subtitles(Path(project_root)) / ('对白_' + uuid.uuid4().hex[:6] + '.srt')
    publish(target, '\n'.join(rows), lambda value: bool(value.strip()), lambda _target: None,
            encoding='utf-8-sig')
    return target, estimated


def export_dialogue_script(project_root, episode, assets, *, publish):
    """准备供配音核对的对白脚本，并交由注入发布器原子发布。"""
    entries, estimated = timed_entries(episode)
    if not entries:
        raise ValueError('当前分镜没有对白，无法导出对白脚本')
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
    publish(target, '\n'.join(lines), lambda value: bool(value.strip()), lambda _target: None,
            encoding='utf-8-sig')
    return target, estimated
