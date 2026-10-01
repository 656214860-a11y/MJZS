"""SRT 时间轴生成：优先使用已标注时间，未标注则按镜头时长均分为草稿。"""
import math
import re


def stamp(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        v = 0.0
    if not math.isfinite(v) or v < 0:
        v = 0.0
    ms = round(v * 1000)
    return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"


def _split_string(text):
    """拆分旧版纯文本对白为 (speaker, text) 片段。"""
    parts = []
    for part in str(text).strip().replace("／", "/").split("/"):
        part = part.strip()
        if not part:
            continue
        if "：" in part or ":" in part:
            sep = "：" if "：" in part else ":"
            speaker, tx = part.split(sep, 1)
            speaker = speaker.strip(); tx = tx.strip()
        else:
            speaker, tx = "", part
        if tx:
            parts.append((speaker, tx))
    return parts


def timed_entries(episode):
    """返回 (entries, estimated)。entry = (shot_id, speaker, text, start秒, end秒)。"""
    if not isinstance(episode, dict):
        return [], False
    entries_out = []
    offset = 0.0
    estimated = False
    shots = episode.get("shots", [])
    if not isinstance(shots, list):
        shots = []
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        sid = shot.get("id", "")
        try:
            dur = float(shot.get("duration") or 5)
        except (TypeError, ValueError):
            dur = 5
        if not math.isfinite(dur) or dur <= 0:
            dur = 5
        shot_entries = []
        dialogue = shot.get("dialogue", [])
        if not isinstance(dialogue, list):
            dialogue = []
        for d in dialogue:
            if isinstance(d, str):
                for speaker, tx in _split_string(d):
                    shot_entries.append([speaker, tx, None, None])
            elif isinstance(d, dict):
                tx = str(d.get("text") or "").strip()
                if not tx:
                    continue
                speaker = str(d.get("speaker") or "")
                a = d.get("start"); b = d.get("end")
                if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                    shot_entries.append([speaker, tx, float(a), float(b)])
                else:
                    shot_entries.append([speaker, tx, None, None])
        if not shot_entries:
            offset += dur
            continue
        has_timed = any(e[2] is not None for e in shot_entries)
        has_untimed = any(e[2] is None for e in shot_entries)
        if has_timed and has_untimed:
            raise ValueError(f"{sid or '镜头'} 部分对白已标注时间、部分未标注，请统一后再导出字幕")
        if has_untimed:
            estimated = True
            per = dur / len(shot_entries)
            for i, e in enumerate(shot_entries):
                e[2] = i * per; e[3] = (i + 1) * per
        for speaker, tx, a, b in shot_entries:
            a = float(a); b = float(b)
            if b <= a:
                b = a + 0.2
            a = max(0.0, min(a, dur))
            b = max(a + 0.2, min(b, dur))
            if b > dur:
                b = dur
                a = min(a, max(0.0, b - 0.2))
            entries_out.append((sid, speaker, tx, offset + a, offset + b))
        offset += dur
    return entries_out, estimated


def srt_rows(episode):
    entries, estimated = timed_entries(episode)
    rows = [f"{i+1}\n{stamp(a)} --> {stamp(b)}\n{_srt_text(tx)}\n" for i, (_, _, tx, a, b) in enumerate(entries)]
    return rows, estimated


def _srt_text(tx):
    """对白文本压成单行，避免换行/空行破坏 SRT 条目结构。"""
    return re.sub(r"\s+", " ", str(tx)).strip()
