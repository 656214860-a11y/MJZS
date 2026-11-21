"""把 SKILL 说明的 Markdown 排版到 Tk Text；解析层不依赖 Tk，也不读写文件。"""
import re

from ui_tokens import COLORS, FONTS, NOTE_PARAGRAPH_SPACING, SPACING


BODY = "body"
BOLD = "bold"
INLINE_CODE = "inline_code"
CODE_BLOCK = "code_block"
LIST = "list"
LIST_L2 = "list_l2"
LIST_L3 = "list_l3"
QUOTE = "quote"
TABLE = "table"
SEPARATOR = "separator"
HINT = "hint"

NOTE = "note"
CHAT = "chat"

HEADING_TAGS = {level: "heading%d" % level for level in range(1, 5)}
_HEADING = re.compile(r"^(#{1,4})\s+(.*?)(?:\s+#+)?\s*$")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
_LIST = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
_HR = re.compile(r"^\s{0,3}(?:-{3,}|\*{3,}|_{3,})\s*$")
_TABLE_ROW = re.compile(r"^\|.*\|$")
_TABLE_SPLIT = re.compile(r"^\s*:?-{3,}:?\s*$")
_INLINE = re.compile(
    r"!?\[[^\]\n]*\]\([^\)\n]*\)"
    r"|\*\*.+?\*\*"
    r"|__.+?__"
    r"|`[^`\n]+`"
)
_INLINE_COMMENT = re.compile(r"<!--.*?-->")
_BULLET = "\u2022 "
_TABLE_JOIN = " \uff5c "
_SEPARATOR_TEXT = "\u2500" * 40
_CODE_INDENT = " " * SPACING["xs"]
_HINT_PREFIXES = ("正在生成中文说明", "中文翻译未完成", "中文翻译需要")


def _drop_front_matter(lines):
    if not lines or lines[0].lstrip("\ufeff").strip() != "---":
        return lines
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return lines[index + 1:]
    return lines


def _plain_inline(text):
    value = _INLINE_COMMENT.sub("", str(text))
    previous = None
    while previous != value:
        previous = value
        value = re.sub(r"\*\*(.+?)\*\*", r"\1", value)
        value = re.sub(r"__(.+?)__", r"\1", value)
        value = re.sub(r"`([^`\n]+)`", r"\1", value)
        value = re.sub(r"!?\[([^\]\n]*)\]\([^)\n]*\)", r"\1", value)
    return value


def _inline_fragments(text, tags):
    value = str(text or "")
    if not value:
        return []
    fragments = []
    cursor = 0
    for match in _INLINE.finditer(value):
        if match.start() > cursor:
            fragments.append((value[cursor:match.start()], tags))
        token = match.group(0)
        if token.startswith("**") and token.endswith("**") and len(token) > 4:
            fragments.append((_plain_inline(token[2:-2]), tags + (BOLD,)))
        elif token.startswith("__") and token.endswith("__") and len(token) > 4:
            fragments.append((_plain_inline(token[2:-2]), tags + (BOLD,)))
        elif token.startswith("`") and token.endswith("`") and len(token) > 2:
            fragments.append((token[1:-1], tags + (INLINE_CODE,)))
        else:
            label = token[token.find("[") + 1:token.rfind("](")]
            fragments.append((_plain_inline(label), tags))
        cursor = match.end()
    if cursor < len(value):
        fragments.append((value[cursor:], tags))
    return fragments


def _table_cells(line):
    return [cell.strip() for cell in line[1:-1].split("|")]


def _is_table_separator(cells):
    return bool(cells) and all(not cell or _TABLE_SPLIT.match(cell) for cell in cells)


def _chat_blank(prev_block, kind):
    if prev_block is None:
        return False
    if prev_block in ("heading", "separator") or kind in ("heading", "separator"):
        return False
    return not (prev_block == "list" and kind == "list")


def _list_level(match, stack):
    indent = len(match.group(1).replace("\t", "    "))
    while stack and stack[-1] > indent:
        stack.pop()
    if not stack or stack[-1] < indent:
        stack.append(indent)
    return len(stack)


def _list_marker(match, chat):
    marker = match.group(2)
    if chat and marker[:1].isdigit():
        return marker[:-1] + ". "
    return _BULLET


def parse(markdown, *, profile=NOTE):
    """Markdown -> [(text, tags)]。未知语法原样保留，任何输入都不抛异常。

    profile 是 CHAT 时用对话口径：不删文件头、不识别提示前缀、
    编号列表保留数字、列表按缩进分层、块间空行并成一个空行片段；
    其他值一律按 NOTE 处理，输出与改动前相同。
    """
    if not isinstance(markdown, str) or not markdown:
        return []
    chat = profile == CHAT
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not chat:
        lines = _drop_front_matter(lines)
    fragments = []
    in_code = False
    in_comment = False
    prev_block = None
    blank_pending = False
    indent_stack = []

    def _block(kind):
        nonlocal prev_block, blank_pending
        if chat and blank_pending and _chat_blank(prev_block, kind):
            fragments.append(("\n", (BODY,)))
        blank_pending = False
        prev_block = kind
        if chat and kind != "list":
            indent_stack.clear()

    for line in lines:
        stripped = line.strip()
        if in_code:
            if _FENCE.match(line):
                in_code = False
            else:
                fragments.append((_CODE_INDENT + line.rstrip() + "\n", (CODE_BLOCK,)))
            continue
        if in_comment:
            if "-->" in line:
                in_comment = False
            continue
        if stripped.startswith("<!--"):
            if "-->" not in stripped:
                in_comment = True
            continue
        line = _INLINE_COMMENT.sub("", line)
        stripped = line.strip()
        if not stripped:
            if prev_block is not None:
                blank_pending = True
            continue
        if _FENCE.match(line):
            _block("code")
            in_code = True
            continue
        if not chat and any(stripped.startswith(prefix) for prefix in _HINT_PREFIXES):
            fragments.append((stripped, (HINT,)))
            fragments.append(("\n", (BODY,)))
            continue
        heading = _HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            _block("heading")
            fragments.append((_plain_inline(heading.group(2)), (HEADING_TAGS[level],)))
            fragments.append(("\n", (BODY,)))
            continue
        if _HR.match(stripped):
            _block("separator")
            fragments.append((_SEPARATOR_TEXT + "\n", (SEPARATOR,)))
            continue
        if _TABLE_ROW.match(stripped):
            cells = _table_cells(stripped)
            _block("table")
            if _is_table_separator(cells):
                continue
            row = _TABLE_JOIN.join(_plain_inline(cell) for cell in cells)
            fragments.append((row + "\n", (TABLE,)))
            continue
        if stripped.startswith(">"):
            _block("quote")
            fragments.extend(_inline_fragments(stripped[1:].lstrip(), (QUOTE,)))
            fragments.append(("\n", (BODY,)))
            continue
        item = _LIST.match(line)
        if item:
            _block("list")
            tags = (LIST,)
            if chat:
                level = _list_level(item, indent_stack)
                if level == 2:
                    tags = (LIST, LIST_L2)
                elif level >= 3:
                    tags = (LIST, LIST_L3)
            marker = _list_marker(item, chat)
            parts = _inline_fragments(item.group(3), tags)
            if parts:
                parts[0] = (marker + parts[0][0], parts[0][1])
                fragments.extend(parts)
            else:
                fragments.append((marker, tags))
            fragments.append(("\n", (BODY,)))
            continue
        _block("body")
        fragments.extend(_inline_fragments(stripped, (BODY,)))
        fragments.append(("\n", (BODY,)))
    return fragments


def _heading_spacing(level):
    before = SPACING["lg"] if level == 1 else SPACING["md"]
    after = SPACING["sm"] if level <= 2 else SPACING["xs"]
    return before, after


def _configure_tags(widget):
    body = {
        "font": FONTS["body"],
        "foreground": COLORS["text_primary"],
        "spacing1": SPACING["none"],
        "spacing2": SPACING["xs"],
        "spacing3": NOTE_PARAGRAPH_SPACING,
    }
    widget.tag_configure(BODY, **body)
    for level, tag in HEADING_TAGS.items():
        before, after = _heading_spacing(level)
        widget.tag_configure(
            tag,
            font=FONTS["heading_%d" % level],
            foreground=COLORS["text_heading"],
            spacing1=before,
            spacing2=SPACING["none"],
            spacing3=after,
        )
    widget.tag_configure(BOLD, font=FONTS["body_bold"], foreground=COLORS["text_primary"])
    widget.tag_configure(
        INLINE_CODE,
        font=FONTS["code"],
        foreground=COLORS["text_primary"],
        background=COLORS["code_background"],
    )
    widget.tag_configure(
        CODE_BLOCK,
        font=FONTS["code"],
        foreground=COLORS["text_primary"],
        background=COLORS["code_background"],
        spacing1=SPACING["none"],
        spacing2=SPACING["none"],
        spacing3=SPACING["none"],
    )
    widget.tag_configure(
        LIST,
        lmargin1=SPACING["lg"],
        lmargin2=SPACING["lg"] + SPACING["xs"],
        spacing1=SPACING["none"],
        spacing2=SPACING["xs"],
        spacing3=SPACING["none"],
    )
    widget.tag_configure(
        QUOTE,
        lmargin1=SPACING["md"],
        lmargin2=SPACING["md"],
        foreground=COLORS["text_secondary"],
        spacing2=SPACING["xs"],
    )
    widget.tag_configure(
        TABLE,
        font=FONTS["code"],
        foreground=COLORS["text_primary"],
        spacing2=SPACING["none"],
    )
    widget.tag_configure(
        SEPARATOR,
        foreground=COLORS["border_strong"],
        spacing1=SPACING["sm"],
        spacing3=SPACING["sm"],
    )
    widget.tag_configure(
        HINT,
        font=FONTS["hint"],
        foreground=COLORS["text_secondary"],
        spacing2=SPACING["xs"],
    )


def apply(text_widget, markdown):
    """清空并重画 Text；保留调用前的可编辑状态，说明栏通常传入 disabled。"""
    fragments = parse(markdown)
    _configure_tags(text_widget)
    state = str(text_widget.cget("state")) or "normal"
    text_widget.configure(state="normal")
    text_widget.delete("1.0", "end")
    for text, tags in fragments:
        text_widget.insert("end", text, tags)
    text_widget.configure(state=state)
    return fragments
