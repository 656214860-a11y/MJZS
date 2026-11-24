"""剧本阅读辅助编排（REQ-S02-36/39/40/43）：行号槽／查找条／大纲面板／折叠／右键菜单的页面接线。

``desktop_script_pages._ContentBox`` 只负责构造与装载边界；本模块的
``ReadingAids`` 持有内容变化后三件套同步、``zoom_by`` 统一缩放入口、
``ShortcutRegistry`` 快捷键登记与 ``scroll_page`` 的 ``_ctrl_wheel_zoom``
滚轮交接，避免页面文件超出模块行数棘轮。缩放状态 ``zoom_delta`` 仍挂在
内容框上，测试可直接断言。REQ-S02-39 起编辑器的完整右键菜单也在这里
构建（会话模块只暴露契约面），REQ-S02-40 的按标题折叠与 REQ-S02-43 的
跳转／状态栏段同样由本模块编排。
"""
import time
import tkinter as tk
from pathlib import Path

import ui.script_view_style as script_view_style
from ui.script_outline import highlight_line, outline_entries, outline_sections
from ui_tokens import (
    FONTS,
    SCRIPT_VIEW_FONT,
    SCRIPT_VIEW_FONT_MAX,
    SCRIPT_VIEW_FONT_MIN,
)

_FOLD_TAG = "script_fold"
_CURSOR_SEGMENT = "script_cursor"

# REQ-S02-36（R4）：缩放时逐 tag 重放字号；tag→基础字体与
# script_view_style._configure_tags 的字体指派一一对应，样式算法本身不改。
_SCRIPT_FONT_TAGS = (
    (script_view_style.BODY, SCRIPT_VIEW_FONT),
    (script_view_style.HEADING_TAGS[1], FONTS['heading_1']),
    (script_view_style.HEADING_TAGS[2], FONTS['heading_2']),
    (script_view_style.HEADING_TAGS[3], FONTS['heading_3']),
    (script_view_style.HEADING_TAGS[4], FONTS['heading_4']),
    (script_view_style.EPISODE, FONTS['heading_2']),
    (script_view_style.SCENE, FONTS['body_bold']),
    (script_view_style.SPEAKER, FONTS['body_bold']),
    (script_view_style.FIELD, FONTS['body_bold']),
    (script_view_style.TABLE, FONTS['code']),
    (script_view_style.TABLE_SEPARATOR, FONTS['code']),
    (script_view_style.CODE, FONTS['code']),
    (script_view_style.FENCE, FONTS['code']),
)


def _font_at_size(spec, size):
    """字体描述 ``(族, 字号[, 字重...])`` 换字号；结果夹在 ui_tokens 缩放区间。"""
    size = max(SCRIPT_VIEW_FONT_MIN, min(SCRIPT_VIEW_FONT_MAX, int(size)))
    return (spec[0], size) + tuple(spec[2:])


def _safe_after_idle(widget, callback):
    """安排空闲回调；窗口销毁时吞掉 TclError，与页面既有守卫同构。"""
    try:
        return widget.after_idle(callback)
    except tk.TclError:
        return None


class ReadingAids:
    """一个内容框的阅读辅助；gutter／find_bar／outline／zoom_delta 都在 box 上。"""

    def __init__(self, box):
        self.box = box
        self._views_idle_pending = False
        self._sections = []
        self._collapsed = set()

    # ---- 内容同步 -----------------------------------------------------

    def preview_text(self):
        try:
            return self.box.preview.get('1.0', 'end-1c')
        except tk.TclError:
            return ''

    def refresh_outline(self):
        """按当前正文重算大纲条目；只在装载／替换等边界调用，不随击键刷新。"""
        self.box.outline.set_entries(outline_entries(self.preview_text(), self.box.kind))

    def refresh_reading_views(self):
        """内容变化后同步折叠段、行号槽与大纲；不动查找命中状态（替换后由 FindBar 自己续位）。"""
        self.refresh_fold_support()
        self.box.gutter.refresh()
        self.refresh_outline()

    def after_text_load(self):
        """_reset_preview_text 与异步分块装完的统一收尾：重放缩放字号并刷新三件套。"""
        self.apply_zoom()
        self.refresh_reading_views()
        self.box.find_bar.reset()
        self.update_cursor_status()

    def schedule_reading_views(self, _event=None):
        """``<<Modified>>`` 驱动的合并刷新：折叠段重算＋行号槽重绘＋查找命中复位。"""
        if self._views_idle_pending:
            return
        self._views_idle_pending = True

        def run():
            self._views_idle_pending = False
            try:
                self.refresh_fold_support()
                self.box.gutter.refresh()
                self.box.find_bar.reset()
                self.update_cursor_status()
            except tk.TclError:
                pass
        if _safe_after_idle(self.box.owner.page.win, run) is None:
            self._views_idle_pending = False

    # ---- 缩放 ---------------------------------------------------------

    def apply_zoom(self):
        """把 zoom_delta 重放到正文控件字体、全部样式 tag 与行号槽。"""
        box = self.box
        size = SCRIPT_VIEW_FONT[1] + box.zoom_delta
        box.preview.configure(font=_font_at_size(SCRIPT_VIEW_FONT, size))
        for tag, spec in _SCRIPT_FONT_TAGS:
            box.preview.tag_configure(tag, font=_font_at_size(spec, spec[1] + box.zoom_delta))
        box.gutter.set_font(_font_at_size(SCRIPT_VIEW_FONT, size))

    def zoom_by(self, delta):
        """Ctrl+=／Ctrl+-／Ctrl+滚轮 的统一入口：±1 步进并夹在 token 区间。"""
        box = self.box
        base = SCRIPT_VIEW_FONT[1]
        clamped = max(SCRIPT_VIEW_FONT_MIN,
                      min(SCRIPT_VIEW_FONT_MAX, base + box.zoom_delta + int(delta)))
        if clamped == base + box.zoom_delta:
            return
        box.zoom_delta = clamped - base
        self.apply_zoom()
        box.owner.page.status.set('字号 %d' % clamped)

    # ---- 大纲／查找开合 -----------------------------------------------

    def on_preview_escape(self, _event=None):
        if self.box.find_bar.visible:
            self.box.find_bar.hide()
            return 'break'
        return None

    def show_find_bar(self):
        self.box.find_bar.show()

    def toggle_outline(self):
        box = self.box
        if box.outline.winfo_manager() == 'grid':
            box.outline.grid_remove()
            box.outline_toggle.configure(text='大纲')
        else:
            self.refresh_outline()
            box.outline.grid()
            box.outline_toggle.configure(text='收起大纲')

    # ---- 段落折叠（REQ-S02-40）----------------------------------------

    def refresh_fold_support(self):
        """重算标题段表、丢弃失效折叠并重放 elide；行号槽随刷新。"""
        self._sections = outline_sections(self.preview_text(), self.box.kind)
        headings = {line for line, _t, _lv, _e in self._sections}
        self._collapsed &= headings
        self._apply_elide()

    def heading_lines(self):
        """FindBar「只在标题里找」的命中行号集合。"""
        return {line for line, _t, _lv, _e in self._sections}

    def fold_marks(self):
        """行号槽折叠标记数据源：``{行号: 是否已折叠}``。"""
        return {line: line in self._collapsed
                for line, _t, _lv, _e in self._sections}

    def _apply_elide(self):
        """按 ``_collapsed`` 重放 elide：每个收起标题隐藏到下一个标题行前的间隙。"""
        preview = self.box.preview
        preview.tag_configure(_FOLD_TAG, elide=True)
        preview.tag_remove(_FOLD_TAG, '1.0', 'end')
        sections = self._sections
        for index, (line, _t, _lv, _e) in enumerate(sections):
            if line not in self._collapsed:
                continue
            if index + 1 < len(sections):
                stop = '%d.0' % sections[index + 1][0]
            else:
                stop = 'end'
            preview.tag_add(_FOLD_TAG, '%d.0' % (line + 1), stop)
        gutter = getattr(self.box, 'gutter', None)
        if gutter is not None:
            gutter.refresh()

    def toggle_fold(self, line):
        """标记点击：该标题连同其子标题一并收起；再点一并展开。"""
        for start, _t, _lv, end in self._sections:
            if start != line:
                continue
            descendants = {later for later, _t2, _lv2, _e2 in self._sections
                           if start < later < end}
            if line in self._collapsed:
                self._collapsed -= descendants | {line}
            else:
                self._collapsed |= descendants | {line}
            self._apply_elide()
            return

    def fold_all(self):
        """「全部折叠」：所有标题收起间隙，只留标题行。"""
        self._collapsed = {line for line, _t, _lv, _e in self._sections}
        self._apply_elide()

    def expand_all(self):
        """「全部展开」：清空全部折叠。"""
        if self._collapsed:
            self._collapsed.clear()
            self._apply_elide()

    def ensure_line_visible(self, line):
        """查找命中或跳转落在收起的段里：展开所有包含该行的已折叠段。"""
        keep = set(self._collapsed)
        for start, _t, _lv, end in self._sections:
            if start < line < end:
                keep.discard(start)
        if keep != self._collapsed:
            self._collapsed = keep
            self._apply_elide()

    # ---- 右键菜单（REQ-S02-39）----------------------------------------

    def context_menu(self, event):
        """编辑器右键菜单：编辑功能与阅读辅助全收进来；空文档退化为置灰五项。"""
        box = self.box
        page = box.owner.page
        session = box.edit_session
        preview = box.preview
        menu = page.script_page_services.context_menu(preview)
        editing = session.editing and str(preview.cget('state')) == 'normal'
        labels = session._MENU_LABELS
        if editing:
            menu.command('退出编辑', lambda: page.safe(session.exit_edit))
            menu.command(labels[0], lambda: page.safe(session.undo_step))
            menu.command(labels[1], lambda: page.safe(session.redo_step))
            initial = session.controller.initial
            if initial is not None and preview.get('1.0', 'end-1c') != initial:
                menu.command(labels[2], lambda: page.safe(session.restore_full))
            else:
                menu.disabled(labels[2])
            menu.command(labels[3], lambda: page.safe(session.save_now))
            menu.command('剪切', lambda: page.safe(
                lambda: preview.event_generate('<<Cut>>')))
            menu.command('复制', lambda: page.safe(
                lambda: preview.event_generate('<<Copy>>')))
            menu.command('粘贴', lambda: page.safe(
                lambda: preview.event_generate('<<Paste>>')))
            menu.command('全选', lambda: page.safe(self.select_all))
            menu.command('查找…', lambda: page.safe(self.show_find_bar))
            menu.command('大纲', lambda: page.safe(self.toggle_outline))
            menu.command('全部折叠', lambda: page.safe(self.fold_all))
            menu.command('全部展开', lambda: page.safe(self.expand_all))
        else:
            if session.editable and session.active['path'] is not None:
                menu.command('编辑', lambda: page.safe(session.begin_edit))
            else:
                menu.disabled('编辑')
            for label in labels:
                menu.disabled(label)
            if session.active['path'] is not None:
                menu.disabled('剪切')
                menu.command('复制', lambda: page.safe(
                    lambda: preview.event_generate('<<Copy>>')))
                menu.disabled('粘贴')
                menu.command('全选', lambda: page.safe(self.select_all))
                menu.command('查找…', lambda: page.safe(self.show_find_bar))
                menu.command('大纲', lambda: page.safe(self.toggle_outline))
                menu.command('全部折叠', lambda: page.safe(self.fold_all))
                menu.command('全部展开', lambda: page.safe(self.expand_all))
        if session.active['path'] is not None:
            opener = getattr(box, 'open_any_document', None)
            if callable(opener):
                menu.separator()
                menu.command('打开其他文件… (Ctrl+O)', lambda: page.safe(opener))
        session.last_menu = menu
        return menu.popup(event)

    def select_all(self):
        """「全选」：优先走 Tk 虚拟事件，再把选区归一到正文 ``end-1c``。"""
        preview = self.box.preview
        preview.event_generate('<<SelectAll>>')
        try:
            preview.tag_remove('sel', '1.0', 'end')
            preview.tag_add('sel', '1.0', 'end-1c')
            preview.mark_set('insert', 'end-1c')
            preview.focus_set()
        except tk.TclError:
            pass

    # ---- 跳转与状态栏（REQ-S02-43）------------------------------------

    def goto_line(self, query=None):
        """Ctrl+G：按行号或集／场／标题名跳转；落在收起段里先自动展开。"""
        if query is None:
            # 输入弹窗由宿主注入（_ContentBox 喂 ui_widgets.ask_string）：
            # script_reading 不直依赖 ui_widgets，避免新增同层边。
            asker = getattr(self, 'goto_ask', None)
            if not callable(asker):
                return False
            query = asker(self.box.owner.page.win, '跳转',
                          '行号或集／场／标题：')
        line = self._goto_target(query)
        if line is None:
            return False
        preview = self.box.preview
        self.ensure_line_visible(line)
        highlight_line(preview, line)
        try:
            preview.mark_set('insert', '%d.0' % line)
            preview.focus_set()
        except tk.TclError:
            pass
        self.update_cursor_status()
        return True

    def _goto_target(self, query):
        """输入解析：纯数字按行号（钳到全文），否则按标题子串找第一段。"""
        text = str(query or '').strip()
        if not text:
            return None
        if text.isdigit():
            try:
                total = int(str(self.box.preview.index('end-1c')).split('.')[0])
            except (tk.TclError, ValueError):
                total = 1
            return max(1, min(total, int(text)))
        needle = text.casefold()
        for start, title, _level, _end in self._sections:
            if needle in str(title).casefold():
                return start
        return None

    def update_cursor_status(self, _event=None):
        """REQ-S02-43：底栏段写光标行号、所在集·场／最近标题、全文字数与最近保存时间。"""
        page = self.box.owner.page
        set_segment = getattr(page, 'set_status_segment', None)
        if not callable(set_segment):
            return
        preview = self.box.preview
        try:
            line = int(str(preview.index('insert')).split('.')[0])
            text = preview.get('1.0', 'end-1c')
        except tk.TclError:
            return
        parts = ['第 %d 行' % line]
        where = self._cursor_heading(line)
        if where:
            parts.append(where)
        parts.append('全文 %d 字' % len(text))
        parts.append('保存 ' + self._saved_stamp())
        try:
            set_segment(_CURSOR_SEGMENT, '｜'.join(parts))
        except tk.TclError:
            pass

    def _cursor_heading(self, line):
        """光标所在位置最近的集·场（natural）或最近标题（其余文档）。"""
        episode = scene = ''
        for start, title, level, _end in self._sections:
            if start > line:
                break
            if self.box.kind == 'natural':
                if level == 1:
                    episode, scene = title, ''
                else:
                    scene = title
            else:
                scene = title
        if self.box.kind == 'natural':
            return '·'.join(part for part in (episode, scene) if part)
        return scene

    def _saved_stamp(self):
        """当前文档的最近写盘时刻（mtime 的 HH:MM），无文档或读不到时 '—'。"""
        path = None
        if isinstance(getattr(self.box, 'active', None), dict):
            path = self.box.active.get('path')
        if not path:
            return '—'
        try:
            return time.strftime('%H:%M', time.localtime(Path(path).stat().st_mtime))
        except (OSError, ValueError):
            return '—'

    def release(self):
        """页面销毁时清掉本编辑器占用的底栏段。"""
        bar = getattr(self.box.owner.page, 'status_bar', None)
        clear = getattr(bar, 'clear_segment', None)
        if callable(clear):
            try:
                clear(_CURSOR_SEGMENT)
            except tk.TclError:
                pass

    # ---- 快捷键 -------------------------------------------------------

    def install_reading_shortcuts(self):
        """Ctrl+F／Ctrl+=／Ctrl+- 经 ShortcutRegistry 登记；Ctrl+滚轮由 scroll_page 转交。"""
        box = self.box
        page = box.owner.page
        shortcuts = getattr(page, 'shortcuts', None)
        if shortcuts is None:
            return
        scope = '剧本结构·' + box.attribute
        shortcuts.bind(box.preview, ('<Control-f>', '<Control-F>'),
                       lambda _event: self.show_find_bar(),
                       scope=scope, name='查找')
        # keysym 区分大小写：'=' 的 shifted 形态是 'plus'，数字小键盘另有 KP_* 键名。
        shortcuts.bind(box.preview, ('<Control-equal>', '<Control-plus>',
                                     '<Control-KP_Equal>', '<Control-KP_Add>'),
                       lambda _event: self.zoom_by(1),
                       scope=scope, name='字号放大')
        shortcuts.bind(box.preview, ('<Control-minus>', '<Control-KP_Subtract>'),
                       lambda _event: self.zoom_by(-1),
                       scope=scope, name='字号缩小')
        shortcuts.bind(box.preview, ('<Control-g>', '<Control-G>'),
                       lambda _event: self.goto_line(),
                       scope=scope, name='跳转')
        box.preview.bind('<KeyRelease>', self.update_cursor_status, add='+')
        box.preview.bind('<ButtonRelease-1>', self.update_cursor_status, add='+')
        box.preview.bind('<Escape>', self.on_preview_escape, add='+')
        # Ctrl+滚轮缩放：DramaPageWheel 类绑定对滚轮恒 'break'，控件级 bind 不可达；
        # scroll_page 识别 ``_ctrl_wheel_zoom`` 属性后把 Ctrl+滚轮交回本框。
        box.preview._ctrl_wheel_zoom = self.zoom_by
