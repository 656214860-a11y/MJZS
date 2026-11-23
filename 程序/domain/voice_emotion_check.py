"""配音情感检查：把配音与剧本的情绪标注逐句比对，偏差大的列出来。

纯函数，不调用 TTS、不改音、不重合成。规则表（情绪 → 允许的语速/音量/情感参数区间）
放在本模块的 DEFAULT_RULES，缺省保守：没有规则或缺数据时单列「无法核验」，
不算通过也不算失败。
"""
import math
import re

# 情绪 → 允许区间。speed/volume 为 (min, max)；emotion 为允许的情感参数集合（None 表示不校验）。
DEFAULT_RULES = {
    "平静": {"speed": (0.8, 1.1), "volume": (0.6, 1.0), "emotion": None},
    "平和": {"speed": (0.8, 1.1), "volume": (0.6, 1.0), "emotion": None},
    "愤怒": {"speed": (1.1, 1.6), "volume": (1.0, 1.4), "emotion": {"angry", "anger", "愤怒"}},
    "怒": {"speed": (1.1, 1.6), "volume": (1.0, 1.4), "emotion": {"angry", "anger", "愤怒"}},
    "悲伤": {"speed": (0.7, 1.0), "volume": (0.5, 0.9), "emotion": {"sad", "sorrow", "悲伤"}},
    "伤心": {"speed": (0.7, 1.0), "volume": (0.5, 0.9), "emotion": {"sad", "sorrow", "悲伤"}},
    "喜悦": {"speed": (1.0, 1.4), "volume": (0.9, 1.3), "emotion": {"happy", "joy", "喜悦"}},
    "高兴": {"speed": (1.0, 1.4), "volume": (0.9, 1.3), "emotion": {"happy", "joy", "喜悦"}},
    "紧张": {"speed": (1.0, 1.5), "volume": (0.8, 1.2), "emotion": {"tense", "nervous", "紧张"}},
    "激动": {"speed": (1.1, 1.6), "volume": (1.0, 1.4), "emotion": {"excited", "激动"}},
    "低沉": {"speed": (0.7, 0.95), "volume": (0.5, 0.85), "emotion": None},
    "急促": {"speed": (1.2, 1.7), "volume": (1.0, 1.4), "emotion": None},
}


def _norm_text(value):
    return re.sub(r"\s+", "", str(value or "")).strip()


def _get(dct, *keys):
    if not isinstance(dct, dict):
        return None
    for key in keys:
        if key in dct and dct.get(key) is not None:
            return dct.get(key)
    # case-insensitive fallback
    lower = {str(k).lower(): v for k, v in dct.items()}
    for key in keys:
        lk = str(key).lower()
        if lk in lower and lower[lk] is not None:
            return lower[lk]
    return None


def _num(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            v = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(v):
            return None
        return v
    try:
        v = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v):
        return None
    return v


def _normalize_script_item(item, idx):
    if not isinstance(item, dict):
        item = {"text": item}
    shot_id = _get(item, "shot_id", "shot", "shotId", "id", "镜头号", "镜头")
    index = _get(item, "index", "line_no", "lineNo", "seq", "no", "序号", "句号")
    if index is None:
        index = idx + 1
    text = _get(item, "text", "line", "dialogue", "台词", "对白")
    emotion = _get(item, "emotion", "mood", "tone", "annotated_emotion", "expected_emotion",
                   "情绪", "情绪标注", "标注情绪")
    try:
        index = int(index)
    except (TypeError, ValueError):
        pass
    return {"shot_id": str(shot_id) if shot_id is not None else "", "index": index,
            "text": text, "emotion": (str(emotion).strip() if emotion is not None else None)}


def _normalize_tts_item(item, idx):
    if not isinstance(item, dict):
        item = {"text": item}
    shot_id = _get(item, "shot_id", "shot", "shotId", "id", "镜头号", "镜头")
    index = _get(item, "index", "line_no", "lineNo", "seq", "no", "序号", "句号")
    if index is None:
        index = idx + 1
    text = _get(item, "text", "line", "dialogue", "台词", "对白")
    speed = _num(_get(item, "speed", "rate", "speed_rate", "语速"))
    volume = _num(_get(item, "volume", "vol", "loudness", "音量"))
    emotion_param = _get(item, "emotion", "emotion_param", "mood", "param", "voice_emotion",
                         "情感参数", "情感")
    try:
        index = int(index)
    except (TypeError, ValueError):
        pass
    return {"shot_id": str(shot_id) if shot_id is not None else "", "index": index,
            "text": text, "speed": speed, "volume": volume, "emotion_param": emotion_param}


def _match_tts(script_item, tts_items, used):
    nt = _norm_text(script_item.get("text"))
    sid = script_item.get("shot_id", "")
    # 1. shot_id + text
    for j, t in enumerate(tts_items):
        if j in used:
            continue
        if t.get("shot_id") == sid and nt and _norm_text(t.get("text")) == nt:
            return j
    # 2. shot_id + index
    for j, t in enumerate(tts_items):
        if j in used:
            continue
        if t.get("shot_id") == sid and t.get("index") == script_item.get("index"):
            return j
    # 3. text only
    if nt:
        for j, t in enumerate(tts_items):
            if j in used:
                continue
            if _norm_text(t.get("text")) == nt:
                return j
    # 4. same position by index order
    return None


def check(script_annotations=None, tts_lines=None, *, rules=None, **kwargs):
    # accept alternative kw names
    if script_annotations is None:
        script_annotations = kwargs.get("script") or kwargs.get("script_sentences") or kwargs.get("annotations") or []
    if tts_lines is None:
        tts_lines = kwargs.get("tts") or kwargs.get("tts_list") or kwargs.get("lines") or kwargs.get("checklist") or []
    if rules is None:
        rules = kwargs.get("rule_table") or kwargs.get("rules_table") or DEFAULT_RULES
    if rules is None:
        rules = DEFAULT_RULES

    scripts = [_normalize_script_item(x, i) for i, x in enumerate(script_annotations or [])]
    tts = [_normalize_tts_item(x, i) for i, x in enumerate(tts_lines or [])]

    deviations = []
    unverifiable = []
    used = set()

    # pair script -> tts
    for i, s in enumerate(scripts):
        j = _match_tts(s, tts, used)
        if j is None:
            # try positional fallback if counts align
            if i < len(tts) and i not in used:
                j = i
        if j is not None:
            used.add(j)
            t = tts[j]
        else:
            t = None

        shot_id = s.get("shot_id", "")
        line_no = s.get("index", i + 1)
        emotion = s.get("emotion")
        text = s.get("text")

        if not emotion:
            unverifiable.append({"shot_id": shot_id, "line_no": line_no, "text": text,
                                 "reason": "缺标注", "annotated_emotion": None})
            continue
        if t is None:
            unverifiable.append({"shot_id": shot_id, "line_no": line_no, "text": text,
                                 "reason": "缺参数", "annotated_emotion": emotion})
            continue
        # check params presence
        if t.get("speed") is None or t.get("volume") is None:
            unverifiable.append({"shot_id": shot_id, "line_no": line_no, "text": text,
                                 "reason": "缺参数", "annotated_emotion": emotion,
                                 "actual": {"speed": t.get("speed"), "volume": t.get("volume"),
                                            "emotion": t.get("emotion_param")}})
            continue
        rule = None
        if isinstance(rules, dict):
            rule = rules.get(emotion)
        if not isinstance(rule, dict):
            unverifiable.append({"shot_id": shot_id, "line_no": line_no, "text": text,
                                 "reason": "缺规则", "annotated_emotion": emotion,
                                 "actual": {"speed": t.get("speed"), "volume": t.get("volume"),
                                            "emotion": t.get("emotion_param")}})
            continue

        reasons = []
        # speed
        sr = rule.get("speed")
        if isinstance(sr, (tuple, list)) and len(sr) == 2:
            lo, hi = sr
            if t["speed"] < lo or t["speed"] > hi:
                reasons.append(f"语速 {t['speed']} 超出 [{lo}, {hi}]")
        # volume
        vr = rule.get("volume")
        if isinstance(vr, (tuple, list)) and len(vr) == 2:
            lo, hi = vr
            if t["volume"] < lo or t["volume"] > hi:
                reasons.append(f"音量 {t['volume']} 超出 [{lo}, {hi}]")
        # emotion param
        allowed = rule.get("emotion")
        if allowed is not None and t.get("emotion_param") is not None:
            allowed_set = set(allowed) if not isinstance(allowed, set) else allowed
            if str(t.get("emotion_param")) not in {str(x) for x in allowed_set} and t.get("emotion_param") not in allowed_set:
                reasons.append(f"情感参数 {t.get('emotion_param')} 不在 {sorted(allowed_set, key=str)}")

        if reasons:
            severity = "高" if len(reasons) >= 2 else "中"
            deviations.append({
                "shot_id": shot_id,
                "line_no": line_no,
                "text": text,
                "annotated_emotion": emotion,
                "actual": {"speed": t.get("speed"), "volume": t.get("volume"),
                           "emotion": t.get("emotion_param")},
                "reason": "；".join(reasons),
                "severity": severity,
            })

    # tts lines without any script annotation -> 缺标注
    for j, t in enumerate(tts):
        if j in used:
            continue
        unverifiable.append({"shot_id": t.get("shot_id", ""), "line_no": t.get("index", j + 1),
                             "text": t.get("text"), "reason": "缺标注",
                             "actual": {"speed": t.get("speed"), "volume": t.get("volume"),
                                        "emotion": t.get("emotion_param")}})

    return {"deviations": deviations, "unverifiable": unverifiable,
            "passed": len(scripts) - len(deviations) - len([u for u in unverifiable if u.get("reason") != "缺标注" or True])}


# aliases
check_emotion = check
check_emotions = check
check_voice_emotion = check
run = check
run_check = check
compare = check
audit = check
evaluate = check


def format_report(result):
    result = result or {}
    deviations = result.get("deviations", []) or []
    unverifiable = result.get("unverifiable", []) or []
    lines = ["配音情感检查报告", f"偏差 {len(deviations)} 条，无法核验 {len(unverifiable)} 条"]
    for d in deviations:
        lines.append(f"[{d.get('severity')}] {d.get('shot_id')} 句{d.get('line_no')} "
                     f"标注={d.get('annotated_emotion')} 实际={d.get('actual')} 原因={d.get('reason')}")
    for u in unverifiable:
        lines.append(f"[无法核验] {u.get('shot_id')} 句{u.get('line_no')} 原因={u.get('reason')}")
    return "\n".join(lines)
