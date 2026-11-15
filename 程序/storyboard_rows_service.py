"""Pure row discovery for the first-frame page.

The Tk page supplies the current scope and renders these rows; this module owns
the cross-storyboard validation and the stable row identifiers.  Keeping it
outside ``desktop.py`` makes “all adopted storyboards” usable and testable
without constructing a window.
"""
from pathlib import Path

from agent.core import read
from contract.storyboard_paths import media_root
from pet_bus import read_json


def shot_stats(paths):
    """返回有效分镜镜头数及其已落盘首帧数。"""
    shots = frames = 0
    for path in paths or ():
        try:
            base = media_root(path).resolve()
        except (OSError, ValueError):
            continue
        data = read_json(path)
        listed = data.get('shots') if isinstance(data, dict) else None
        for shot in (listed if isinstance(listed, list) else []):
            if not isinstance(shot, dict) or not shot.get('id'):
                continue
            shots += 1
            name = shot.get('frame')
            if not name or shot.get('frame_deleted'):
                continue
            try:
                frame = (base / name).resolve()
            except (OSError, ValueError):
                continue
            if frame.is_relative_to(base) and frame.is_file():
                frames += 1
    return shots, frames


def frame_rows(project, source, episode, base, scope='current', on_skip=None):
    """Return ``(row_id, shot, source, media_base, episode)`` rows.

    ``scope='adopted'`` joins every valid adopted storyboard.  Duplicate shot
    IDs receive a source-stem suffix only when necessary, keeping normal row
    IDs backwards compatible with the single-storyboard page.
    """
    source = Path(source).resolve()
    pairs = [(source, Path(base).resolve(), episode)]
    if scope == 'adopted':
        from asset_context import scope_sources
        from writing import validate_episode
        try:
            found = list(scope_sources(project, 'adopted'))
        except (ValueError, OSError, KeyError):
            found = []
        if len(found) > 1:
            pairs = []
            for item in found:
                item = Path(item).resolve()
                try:
                    one = read(item)
                    one_base = media_root(item)
                    validate_episode(one, one_base)
                except (ValueError, OSError, KeyError) as exc:
                    if on_skip is not None:
                        on_skip(item.name + ' 这一份分镜暂时读不了，已跳过：' + str(exc))
                    continue
                pairs.append((item, one_base, one))
    return rows_from_sources(pairs)


def rows_from_sources(pairs):
    """Build stable rows from already validated ``(source, base, episode)`` triples."""
    counts = {}
    for _item, _base, one in pairs:
        for shot in one.get('shots', []):
            shot_id = str(shot.get('id') or '')
            counts[shot_id] = counts.get(shot_id, 0) + 1
    result = []
    for item, item_base, one in pairs:
        for shot in one.get('shots', []):
            shot_id = str(shot.get('id') or '')
            row_id = shot_id if counts[shot_id] == 1 else shot_id + '@' + item.stem
            result.append((row_id, shot, item, item_base, one))
    return result
