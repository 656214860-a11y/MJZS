"""剧本内容阅读区的行级样式：只给原文加 Text 标签，不增删任何字符。"""
import re

from ui_tokens import (
    COLORS,
    FONTS,
    SCRIPT_VIEW_FONT,
    SCRIPT_VIEW_LINE_SPACING,
    SCRIPT_VIEW_LIST_INDENT,
    SCRIPT_VIEW_MAX_CHARS,
    SCRIPT_VIEW_PARAGRAPH_SPACING,
    SCRIPT_VIEW_QUOTE_INDENT,
    SPACING,
)


BODY = "script_body"
EPISODE = "script_episode"
SCENE = "script_scene"
SPEAKER = "script_speaker"
ANNOTATION = "script_annotation"
LIST = "script_list"
FIELD = "script_field"
QUOTE = "script_quote"
TABLE = "script_table"
TABLE_SEPARATOR = "script_table_separator"
CODE = "script_code"
FENCE = "script_fence"
SEPARATOR = "script_separator"
MARKER = "script_marker"
HEADING_TAGS = {level: "script_heading%d" % level for level in range(1, 5)}

_ALL_TAGS = (
    BODY, LIST, HEADING_TAGS[1], HEADING_TAGS[2], HEADING_TAGS[3], HEADING_TAGS[4],
    EPISODE, SCENE, SPEAKER, ANNOTATION, FIELD, QUOTE, TABLE, TABLE_SEPARATOR,
    CODE, FENCE, SEPARATOR, MARKER,
)

_EPISODE = re.compile(r"^\s*第\s*(?:\d+|[一二三四五六七八九十百零〇]+)\s*集(?:\s*[：:].*)?\s*$")
_SCENE = re.compile(r"^\s*场景\s*(?:\d+|[一二三四五六七八九十百零〇]+)\s*[：:]")
_SPEAKER = re.compile(r"^\s*([^\s：:，。！？、；·“”'‘’（）()【】\[\]<>《》]{1,12})\s*[：:]\s*(.+)$")
_ANNOTATION = re.compile(r"^\s*(?:道具|物品|时间|地点|人物|角色|备注|旁白|画外音|字幕|音乐|音效|画面)\s*[：:]")
_HEADING = re.compile(r"^(#{1,4})(?:\s+.*)?$")
_FIELD = re.compile(r"^(\s*[-*+]\s+)([^：:\n]{1,20})([：:])")
_LIST = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+")
_QUOTE = re.compile(r"^\s*>")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_CELL_SEPARATOR = re.compile(r"^:?-{3,}:?$")
_FENCE = re.compile(r"^\s*(?:`{3,}|~{3,})")
_HR = re.compile(r"^\s{0,3}(?:-{3,}|\*{3,}|_{3,})\s*$")


def should_style(text):
    """超过高亮阈值的大文件只保留纯文本，避免逐行扫描与大量 tag_add 卡住界面。"""
    return len(str(text or "")) <= SCRIPT_VIEW_MAX_CHARS


def wrap_mode(text):
    """小文件按词换行；大文件保持原文横向滚动，避免 Tcl 反复量宽。"""
    return "word" if should_style(text) else "none"


def compact_display(text):
    """折叠代码块外的空白行；只用于展示，不改变源文件。"""
    value = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not value:
        return value
    lines = []
    in_code = False
    for line in value.split("\n"):
        if _FENCE.match(line):
            in_code = not in_code
            lines.append(line)
        elif in_code or line.strip():
            lines.append(line)
    return "\n".join(lines)


def _span(line_no, start, end, tag):
    if end <= start:
        return None
    return (line_no, start, line_no, end, tag)


def _append(spans, line_no, start, end, tag):
    span = _span(line_no, start, end, tag)
    if span is not None:
        spans.append(span)


def _natural_line(line_no, line):
    spans = []
    _append(spans, line_no, 0, len(line), BODY)
    if not line.strip():
        return spans
    if _EPISODE.match(line):
        _append(spans, line_no, 0, len(line), EPISODE)
        return spans
    if _SCENE.match(line):
        _append(spans, line_no, 0, len(line), SCENE)
        return spans
    if _ANNOTATION.match(line):
        _append(spans, line_no, 0, len(line), ANNOTATION)
        return spans
    speaker = _SPEAKER.match(line)
    if speaker:
        _append(spans, line_no, speaker.start(1), speaker.end(1), SPEAKER)
    return spans


def _heading_spacing(level):
    if level == 1:
        return SPACING["lg"], SPACING["sm"]
    if level == 2:
        return SPACING["md"], SPACING["xs"]
    return SPACING["sm"], SPACING["xs"]


def _is_table_separator(line):
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return bool(cells) and all(not cell or _TABLE_CELL_SEPARATOR.match(cell) for cell in cells)


def _structured_spans(text):
    spans = []
    in_code = False
    for line_no, raw in enumerate(text.split("\n"), 1):
        line = raw[:-1] if raw.endswith("\r") else raw
        stripped = line.strip()
        _append(spans, line_no, 0, len(line), BODY)
        if in_code:
            if _FENCE.match(line):
                in_code = False
                _append(spans, line_no, 0, len(line), FENCE)
            else:
                _append(spans, line_no, 0, len(line), CODE)
            continue
        if _FENCE.match(line):
            in_code = True
            _append(spans, line_no, 0, len(line), FENCE)
            continue
        heading = _HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            _append(spans, line_no, 0, len(line), HEADING_TAGS[level])
            _append(spans, line_no, 0, level, MARKER)
            continue
        if _HR.match(stripped):
            _append(spans, line_no, 0, len(line), SEPARATOR)
            continue
        if _TABLE_ROW.match(line):
            tag = TABLE_SEPARATOR if _is_table_separator(line) else TABLE
            _append(spans, line_no, 0, len(line), tag)
            continue
        if _QUOTE.match(line):
            _append(spans, line_no, 0, len(line), QUOTE)
            continue
        field = _FIELD.match(line)
        if field:
            _append(spans, line_no, 0, len(line), LIST)
            _append(spans, line_no, field.start(2), field.end(2), FIELD)
            continue
        if _LIST.match(line):
            _append(spans, line_no, 0, len(line), LIST)
    return spans


def spans(text, kind="natural"):
    """返回 ``(start_line, start_col, end_line, end_col, tag)``；行列均从 1.0 起算。"""
    value = str(text or "")
    if not value or not should_style(value):
        return []
    if kind == "structured":
        return _structured_spans(value)
    if kind == "natural":
        spans_out = []
        for line_no, raw in enumerate(value.split("\n"), 1):
            line = raw[:-1] if raw.endswith("\r") else raw
            spans_out.extend(_natural_line(line_no, line))
        return spans_out
    return [span for line_no, raw in enumerate(value.split("\n"), 1)
            for span in _natural_line(line_no, raw[:-1] if raw.endswith("\r") else raw)[:1]]


def _configure_tags(widget):
    widget.tag_configure(
        BODY,
        font=SCRIPT_VIEW_FONT,
        spacing1=SPACING["none"],
        spacing2=SCRIPT_VIEW_LINE_SPACING,
        spacing3=SCRIPT_VIEW_PARAGRAPH_SPACING,
        lmargin1=SPACING["none"],
        lmargin2=SPACING["none"],
    )
    widget.tag_configure(
        LIST,
        lmargin1=SCRIPT_VIEW_LIST_INDENT,
        lmargin2=SCRIPT_VIEW_LIST_INDENT + SPACING["xs"],
    )
    for level, tag in HEADING_TAGS.items():
        before, after = _heading_spacing(level)
        widget.tag_configure(
            tag,
            font=FONTS["heading_%d" % level],
            spacing1=before,
            spacing2=SPACING["none"],
            spacing3=after,
        )
    widget.tag_configure(
        EPISODE,
        font=FONTS["heading_2"],
        spacing1=SPACING["md"],
        spacing3=SPACING["sm"],
    )
    widget.tag_configure(
        SCENE,
        font=FONTS["body_bold"],
        spacing1=SPACING["sm"],
        spacing3=SPACING["xs"],
    )
    widget.tag_configure(SPEAKER, font=FONTS["body_bold"])
    widget.tag_configure(
        FIELD,
        font=FONTS["body_bold"],
    )
    widget.tag_configure(
        QUOTE,
        lmargin1=SCRIPT_VIEW_QUOTE_INDENT,
        lmargin2=SCRIPT_VIEW_QUOTE_INDENT,
    )
    widget.tag_configure(TABLE, font=FONTS["code"])
    widget.tag_configure(TABLE_SEPARATOR, font=FONTS["code"])
    widget.tag_configure(
        CODE,
        font=FONTS["code"],
        lmargin1=SPACING["xs"],
        lmargin2=SPACING["xs"],
        spacing2=SPACING["none"],
        spacing3=SPACING["none"],
    )
    widget.tag_configure(FENCE, font=FONTS["code"])
    widget.tag_configure(
        SEPARATOR,
        spacing1=SPACING["sm"],
        spacing3=SPACING["sm"],
    )
    widget._refresh_tag_colors = refresh_tags
    refresh_tags(widget)


def refresh_tags(widget):
    """重配文字与代码块颜色，保留当前字号、折叠状态和选区。"""
    for token, tags in (
        ('text_primary', (BODY, TABLE, CODE)),
        ('text_heading', (*HEADING_TAGS.values(), EPISODE, SCENE, FIELD)),
        ('primary_text', (SPEAKER,)),
        ('text_secondary', (ANNOTATION, QUOTE)),
        ('text_muted', (TABLE_SEPARATOR, FENCE, MARKER)),
        ('border_strong', (SEPARATOR,)),
    ):
        for tag in tags:
            widget.tag_configure(tag, foreground=COLORS[token])
    widget.tag_configure(CODE, background=COLORS['code_background'])


def apply_tags(widget, text, kind="natural"):
    """只做 tag_configure／tag_remove／tag_add；调用后控件文字必须逐字不变。"""
    value = str(text or "")
    parts = spans(value, kind)
    if not value or not should_style(value):
        return parts
    _configure_tags(widget)
    for tag in _ALL_TAGS:
        widget.tag_remove(tag, "1.0", "end")
    for start_line, start_col, end_line, end_col, tag in parts:
        widget.tag_add(tag, "%d.%d" % (start_line, start_col), "%d.%d" % (end_line, end_col))
    return parts
