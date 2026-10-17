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


def _shot_duration(shot):
    """镜头时长：缺省或非法一律回退 5 秒（与旧版等分估算同一口径）。"""
    try:
        dur = float(shot.get("duration") or 5)
    except (TypeError, ValueError):
        dur = 5
    if not math.isfinite(dur) or dur <= 0:
        dur = 5
    return dur


def _dialogue_rows(shot):
    """解出镜内对白行 [speaker, text, start 或 None, end 或 None]，口径与旧版一致。"""
    rows = []
    dialogue = shot.get("dialogue", [])
    if not isinstance(dialogue, list):
        dialogue = []
    for d in dialogue:
        if isinstance(d, str):
            for speaker, tx in _split_string(d):
                rows.append([speaker, tx, None, None])
        elif isinstance(d, dict):
            tx = str(d.get("text") or "").strip()
            if not tx:
                continue
            speaker = str(d.get("speaker") or "")
            a = d.get("start"); b = d.get("end")
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                rows.append([speaker, tx, float(a), float(b)])
            else:
                rows.append([speaker, tx, None, None])
    return rows


def _clamp(a, b, dur):
    """把一句的起止夹进 [0, dur] 且保证 end > start（旧 clamp 口径，保持向后兼容）。"""
    a = float(a); b = float(b)
    if b <= a:
        b = a + 0.2
    a = max(0.0, min(a, dur))
    b = max(a + 0.2, min(b, dur))
    if b > dur:
        b = dur
        a = min(a, max(0.0, b - 0.2))
    return a, b


def timed_entries(episode):
    """返回 (entries, estimated)。entry = (shot_id, speaker, text, start秒, end秒)。

    这是**低成本估算**：未标注时间的句子在镜头内**等分**，够快但未必贴合实际语音。
    真实配音生成后请改用 calibrate_entries 按实际句长或音频对齐结果校准。
    """
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
        dur = _shot_duration(shot)
        shot_entries = _dialogue_rows(shot)
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
            a, b = _clamp(a, b, dur)
            entries_out.append((sid, speaker, tx, offset + a, offset + b))
        offset += dur
    return entries_out, estimated


DEFAULT_LINE_SECONDS = 0.2


def line_weight(text):
    """一句台词的时长权重：按可见字符数（空白不计）计，至少 1，避免整句被压成 0。"""
    return float(max(1, len(re.sub(r"\s+", "", str(text if text is not None else "")))))


def _audio_seconds(item):
    """把「真实音频时长」或「(起, 止) 对齐区间」归一成秒；未知或非法一律返回 None。"""
    if item is None or isinstance(item, bool):
        return None
    if isinstance(item, (list, tuple)) and len(item) == 2:
        try:
            start, end = float(item[0]), float(item[1])
        except (TypeError, ValueError):
            return None
        if math.isfinite(start) and math.isfinite(end) and end > start:
            return end - start
        return None
    try:
        value = float(item)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value <= 0:
        return None
    return value


def _distribute(rows, dur, known):
    """在镜头内分摊每句时长：已知真实时长优先，其余按句长权重分剩余预算。

    已知时长合计占满或超出镜头时整镜按比例压缩，保证每句都还有位置，并标记 overflow
    （真实音频比镜头长，需要人工确认）。返回 (每句秒数, 是否溢出)。
    """
    n = len(rows)
    secs = [None] * n
    for i in range(min(n, len(known))):
        secs[i] = _audio_seconds(known[i])
    fixed = sum(s for s in secs if s is not None)
    unknown = [i for i in range(n) if secs[i] is None]
    overflow = False
    if unknown:
        remaining = dur - fixed
        if remaining <= 0:
            overflow = True
            target_known = dur * 0.5
            scale = (target_known / fixed) if fixed > 0 else 0.0
            for i in range(n):
                if secs[i] is not None:
                    secs[i] = secs[i] * scale
            remaining = dur - target_known
        weights = [line_weight(rows[i][1]) for i in unknown]
        total_weight = sum(weights) or 1.0
        for i, weight in zip(unknown, weights):
            secs[i] = remaining * weight / total_weight
    elif fixed > dur:
        overflow = True
        scale = dur / fixed
        for i in range(n):
            secs[i] = secs[i] * scale
    return [float(s or 0.0) for s in secs], overflow


def calibrate_entries(episode, audio=None):
    """在低成本估算之上，用实际句长或真实音频时长／对齐结果校准每镜内的字幕轴。

    返回 (entries, report)。entries 与 timed_entries 同构；report 记录校准方式与仍
    未按音频校准的句子，供导出前提示。audio 是与 entries 对齐的序列，元素可为真实秒
    数、(start, end) 对齐区间或 None（未知）。已标注时间的句子按作者给定、不参与重排；
    只有全未标注的镜头才重排。本函数只算时间，不读盘、不改台词。
    """
    report = {"mode": "estimate", "estimated": False, "calibrated": 0, "audio": 0,
              "total": 0.0, "shots": 0, "uncalibrated": [], "overflow": [], "source": {}}
    if not isinstance(episode, dict):
        return [], report
    shots = episode.get("shots", [])
    if not isinstance(shots, list):
        shots = []
    items = list(audio) if isinstance(audio, (list, tuple)) else []
    out = []
    offset = 0.0
    cursor = 0
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        sid = shot.get("id", "")
        dur = _shot_duration(shot)
        rows = _dialogue_rows(shot)
        if not rows:
            offset += dur
            report["total"] += dur
            continue
        report["shots"] += 1
        has_timed = any(r[2] is not None for r in rows)
        has_untimed = any(r[2] is None for r in rows)
        if has_timed and has_untimed:
            raise ValueError(f"{sid or '镜头'} 部分对白已标注时间、部分未标注，请统一后再导出字幕")
        if has_timed:
            placed = [(r[0], r[1], r[2], r[3]) for r in rows]
            report["calibrated"] += len(rows)
        else:
            known = items[cursor:cursor + len(rows)]
            secs, overflow = _distribute(rows, dur, known)
            if overflow:
                report["overflow"].append(str(sid) or "镜头")
            placed = []
            at = 0.0
            for i, row in enumerate(rows):
                placed.append((row[0], row[1], at, at + secs[i]))
                at += secs[i]
                source = _audio_seconds(known[i]) if i < len(known) else None
                if source is None:
                    report["uncalibrated"].append({"shot": str(sid) or "镜头",
                                                   "speaker": row[0], "text": row[1]})
                else:
                    report["calibrated"] += 1
                    report["audio"] += 1
        for speaker, tx, a, b in placed:
            a, b = _clamp(a, b, dur)
            out.append((sid, speaker, tx, offset + a, offset + b))
        cursor += len(rows)
        offset += dur
        report["total"] += dur
    report["estimated"] = bool(report["uncalibrated"])
    if not out:
        report["mode"] = "estimate"
    elif not report["uncalibrated"]:
        report["mode"] = "audio" if report["audio"] else "explicit"
    elif report["calibrated"]:
        report["mode"] = "mixed"
    else:
        report["mode"] = "length"
    report["source"] = {"entries": len(out), "calibrated": report["calibrated"],
                        "audio": report["audio"], "uncalibrated": len(report["uncalibrated"]),
                        "overflow": list(report["overflow"]),
                        "total_seconds": round(report["total"], 3)}
    return out, report


def validate_entries(entries, total=None):
    """校验字幕时间轴：非有限、负数、反向、重叠、越界一律直接报错，不静默修正。"""
    prev_end = None
    for sid, _speaker, _text, start, end in entries:
        try:
            a, b = float(start), float(end)
        except (TypeError, ValueError):
            raise ValueError(f"{sid or '镜头'} 字幕时间不是数字：{start!r} → {end!r}")
        if not math.isfinite(a) or not math.isfinite(b):
            raise ValueError(f"{sid or '镜头'} 字幕时间不是有限值：{a} → {b}")
        if a < 0 or b < 0:
            raise ValueError(f"{sid or '镜头'} 字幕时间出现负数：{a} → {b}")
        if b <= a:
            raise ValueError(f"{sid or '镜头'} 字幕结束时间不大于开始时间：{a} → {b}")
        if prev_end is not None and a < prev_end - 1e-6:
            raise ValueError(f"{sid or '镜头'} 字幕时间与上一句重叠：{a} < {prev_end}")
        if total is not None and b > float(total) + 1e-6:
            raise ValueError(f"{sid or '镜头'} 字幕时间越界：{b} > {float(total)}")
        prev_end = b
    return None


def rows_from_entries(entries):
    """把 (shot_id, speaker, text, start, end) 渲染成 SRT 条目列表。"""
    return [f"{i+1}\n{stamp(a)} --> {stamp(b)}\n{_srt_text(tx)}\n"
            for i, (_sid, _speaker, tx, a, b) in enumerate(entries)]


ASS_HEADER = (
    "[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 0\n"
    "ScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
    "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
    "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
    "Style: Default,Microsoft YaHei,60,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,"
    "0,0,0,0,100,100,0,0,1,3,1,2,60,60,50,1\n\n[Events]\n"
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")


def ass_stamp(seconds):
    """ASS 时间码 ``H:MM:SS.cc``（百分之一秒）。"""
    total = int(round(float(seconds) * 100))
    hours, rest = divmod(total, 360000)
    minutes, rest = divmod(rest, 6000)
    return f"{hours}:{minutes:02}:{rest // 100:02}.{rest % 100:02}"


def ass_text(entries):
    """把 (shot_id, speaker, text, start, end) 渲染成含默认样式的 ASS 全文；时间与文本口径同 SRT。"""
    body = [f"Dialogue: 0,{ass_stamp(a)},{ass_stamp(b)},Default,,0,0,0,,"
            + _srt_text(tx).replace("{", "｛").replace("}", "｝")
            for _sid, _speaker, tx, a, b in entries]
    return ASS_HEADER + "\n".join(body) + "\n"


def srt_rows(episode, audio=None):
    """预导出 SRT 行：用校准轴（有 audio 则按真实音频，否则按句长），并先做时间校验。"""
    entries, report = calibrate_entries(episode, audio=audio)
    validate_entries(entries, report.get("total"))
    return rows_from_entries(entries), bool(report.get("estimated"))


def _srt_text(tx):
    """对白文本压成单行，避免换行/空行破坏 SRT 条目结构。"""
    return re.sub(r"\s+", " ", str(tx)).strip()
