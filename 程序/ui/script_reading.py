"""剧本阅读辅助编排（REQ-S02-36）：行号槽／查找条／大纲面板／字号缩放的页面接线。

``desktop_script_pages._ContentBox`` 只负责构造与装载边界；本模块的
``ReadingAids`` 持有内容变化后三件套同步、``zoom_by`` 统一缩放入口、
``ShortcutRegistry`` 快捷键登记与 ``scroll_page`` 的 ``_ctrl_wheel_zoom``
滚轮交接，避免页面文件超出模块行数棘轮。缩放状态 ``zoom_delta`` 仍挂在
内容框上，测试可直接断言。
"""
import tkinter as tk

import ui.script_view_style as script_view_style
from ui.script_outline import outline_entries
from ui_tokens import (
    FONTS,
    SCRIPT_VIEW_FONT,
    SCRIPT_VIEW_FONT_MAX,
    SCRIPT_VIEW_FONT_MIN,
)

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
        """内容变化后同步行号槽与大纲；不动查找命中状态（替换后由 FindBar 自己续位）。"""
        self.box.gutter.refresh()
        self.refresh_outline()

    def after_text_load(self):
        """_reset_preview_text 与异步分块装完的统一收尾：重放缩放字号并刷新三件套。"""
        self.apply_zoom()
        self.refresh_reading_views()
        self.box.find_bar.reset()

    def schedule_reading_views(self, _event=None):
        """``<<Modified>>`` 驱动的合并刷新：行号槽重绘＋查找命中复位；大纲不随击键刷。"""
        if self._views_idle_pending:
            return
        self._views_idle_pending = True

        def run():
            self._views_idle_pending = False
            try:
                self.box.gutter.refresh()
                self.box.find_bar.reset()
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
        box.preview.bind('<Escape>', self.on_preview_escape, add='+')
        # Ctrl+滚轮缩放：DramaPageWheel 类绑定对滚轮恒 'break'，控件级 bind 不可达；
        # scroll_page 识别 ``_ctrl_wheel_zoom`` 属性后把 Ctrl+滚轮交回本框。
        box.preview._ctrl_wheel_zoom = self.zoom_by
