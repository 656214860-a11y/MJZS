# -*- coding: utf-8 -*-
"""REQ-UI-SIDEBAR-1：侧栏项目区——单个「项目」图标＋项目名称列表＋右侧二级图标列。

原四个项目控件（在制作／已完成／新建／打开目录）收进按需展开的二级列
（``ui.desktop_expand_column.ExpandIconColumn``），原位置改为项目名称列表：
搜索过滤、状态点、当前高亮、点击走 ``request_project_switch`` 既有确认流。
项目数据只读已加载的 ``projects.info``，不在启动路径扫目录。
"""

import tkinter as tk
from pathlib import Path
from tkinter import ttk

import infra.app_logging as app_logging
from ui.desktop_expand_column import ExpandIconColumn
from ui.desktop_page_registry import PROJECT_ACTION_ICONS, PROJECT_GROUP_ICONS
from ui.ui_icons import IconLoader
from ui_tokens import COLORS, DESKTOP_LAYOUT, SPACING
from ui_widgets import DataTable, SecondaryButton, Tooltip

MIN_ROWS = 3                 # 列表最少显示行数（卡面：矮窗也至少 3 行）
LIST_SHARE = 0.4             # 列表高度上限占窗口高度的比例
DEFAULT_HEIGHT_ROWS = 6      # 窗口尺寸未就绪时的初始行数


class ProjectNameList(ttk.Frame):
    """项目名称列表：可键盘操作的名称表（无搜索框与项目管理按钮，腾出空间放项目二级图标）。

    行文本＝「状态点 名称」（● 在制作／○ 已完成），当前项目打 ``current``
    标签高亮；单击／双击／Enter 都走 ``request_project_switch``，
    右键出既有项目菜单（标记完成／删除等）。
    """

    def __init__(self, host, parent):
        super().__init__(parent)
        self.host = host
        self._fit_job = None
        self.table = DataTable(self, columns=[('name', '项目', SPACING['sm'] * 15)],
                               show='tree', height=DEFAULT_HEIGHT_ROWS,
                               selectmode='browse', empty_text='暂无项目',
                               auto_hide_scrollbars=True, horizontal=False)
        self.table.pack(fill='x')
        tree = self.table.tree
        tree.column('#0', width=SPACING['sm'] * 15, stretch=True)
        tree.heading('#0', text='')
        tree.tag_configure('current', background=COLORS['primary_subtle'])
        tree.configure(takefocus=1)
        tree.bind('<Button-1>', self._click_row, add='+')
        tree.bind('<Double-1>', self._activate_selected)
        tree.bind('<Return>', self._activate_selected)
        tree.bind('<Button-3>', self._row_menu, add='+')
        win = getattr(host, 'win', None)
        self._resize_bind = None
        if win is not None:
            self._resize_bind = win.bind('<Configure>', self._on_resize, add='+')
        self.bind('<Destroy>', self._on_destroy, add='+')

    def _on_destroy(self, event=None):
        """控件销毁时摘掉尺寸监听并撤掉未执行的 fit 回调，避免拆除后 Tcl 报 invalid command。"""
        if event is not None and getattr(event, 'widget', None) is not self:
            return
        win = getattr(self.host, 'win', None)
        if win is not None and self._resize_bind:
            try:
                win.unbind('<Configure>', self._resize_bind)
            except tk.TclError:
                pass
            self._resize_bind = None
        if self._fit_job is not None:
            if win is not None:
                try:
                    win.after_cancel(self._fit_job)
                except tk.TclError:
                    pass
            self._fit_job = None

    # ── 数据与渲染 ────────────────────────────────────────────────────
    def refresh(self):
        """按 ``_picker_items``（已分组、已排序）重建行；当前项目打高亮。"""
        tree = self.table.tree
        tree.tag_configure('current', background=COLORS['primary_subtle'])
        tree.delete(*tree.get_children())
        items = list(getattr(self.host, '_picker_items', None) or [])
        root = getattr(self.host, 'root', None)
        for project in items:
            status = project.get('status', 'making')
            glyph = '●' if status == 'making' else '○'
            name = project.get('name') or Path(str(project.get('path'))).name
            tags = ()
            if root is not None:
                try:
                    if Path(str(project.get('path'))) == Path(root):
                        tags = ('current',)
                except (OSError, ValueError):
                    pass
            tree.insert('', 'end', iid=str(project.get('path')),
                        text='%s %s' % (glyph, name), tags=tags)
        registry = ((getattr(getattr(self.host, 'projects', None), 'info', None)
                     or {}).get('projects') or [])
        self.table.empty_label.configure(
            text='暂无项目' if not registry else '该分组暂无项目')
        self.table.refresh_empty_state()
        self._fit_height(len(items))

    # ── 高度钳制：随窗口收缩，最少 MIN_ROWS 行 ─────────────────────────
    def _row_pixels(self, tree):
        try:
            value = ttk.Style(tree).lookup('Tokens.DataTable.Treeview',
                                           'rowheight')
            if value:
                return max(1, int(value))
        except (tk.TclError, ValueError, TypeError):
            pass
        try:
            return max(1, tree.winfo_reqheight()
                       // max(1, int(tree.cget('height'))))
        except (tk.TclError, ValueError, TypeError, ZeroDivisionError):
            return 24

    def _fit_height(self, count):
        tree = self.table.tree
        row_px = self._row_pixels(tree)
        win = getattr(self.host, 'win', None)
        win_h = win.winfo_height() if win is not None else 0
        if win_h > 1:
            cap_px = max(MIN_ROWS * row_px, int(win_h * LIST_SHARE))
        else:
            cap_px = MIN_ROWS * row_px * 4
        fit_rows = max(MIN_ROWS, cap_px // row_px)
        height = max(MIN_ROWS, min(count, fit_rows)) if count else MIN_ROWS
        try:
            tree.configure(height=height)
        except tk.TclError:
            pass

    def _on_resize(self, _event=None):
        win = getattr(self.host, 'win', None)
        if win is None:
            return
        if self._fit_job is not None:
            try:
                win.after_cancel(self._fit_job)
            except tk.TclError:
                pass
        self._fit_job = win.after_idle(self._fit_now)

    def _fit_now(self):
        self._fit_job = None
        try:
            if self.winfo_exists():
                self._fit_height(len(self.table.tree.get_children()))
        except tk.TclError:
            pass

    # ── 选择与动作 ────────────────────────────────────────────────────
    def _pick(self, iid):
        """切换项目：复用 ``request_project_switch``（任务拦截＋确认＋失效找回）。"""
        host = self.host
        path = str(iid)
        root = getattr(host, 'root', None)
        if root is not None:
            try:
                if Path(path) == Path(root):
                    return
            except (OSError, ValueError):
                pass
        host.safe(lambda: host.request_project_switch(path))

    def _click_row(self, event):
        iid = self.table.tree.identify_row(event.y)
        if not iid:
            return
        try:
            self.table.tree.selection_set(iid)
        except tk.TclError:
            return
        self._pick(iid)

    def _activate_selected(self, _event=None):
        selection = self.table.tree.selection()
        if selection:
            self._pick(selection[0])

    def _row_menu(self, event):
        iid = self.table.tree.identify_row(event.y)
        if not iid:
            return
        project = next((p for p in (getattr(self.host, '_picker_items', None)
                                    or [])
                        if str(p.get('path')) == str(iid)), None)
        if project is not None:
            self.host._project_item_menu(dict(project), event)


def build_project_rail(host, side):
    """侧栏项目区：单个「项目」图标＋名称列表；四个二级图标在项目区内部 2×2 展开。

    二级图标留在侧栏宽度内（与上方项目列表框同宽），绝不向外挤占右侧聊天框空间；
    点主图标展开、再点／点空白／Esc 收起；分组钮兼作列表过滤（再点回「全部」）。
    """
    host.project_block = ttk.Frame(side)
    host.project_block.pack(fill='x', pady=(SPACING['xs'], SPACING['none']))
    host._project_group = 'making'
    host._picker_items = []
    image = IconLoader.nav_icon(side, 'project_files')
    host.project_button = SecondaryButton(
        host.project_block, text='', image=image,
        compound='image' if image is not None else 'text', width=0,
        style='RailIcon.TButton', command=lambda: toggle_project_expand(host))
    host.project_button.pack(anchor='w',
                             pady=(SPACING['none'], DESKTOP_LAYOUT['nav_gap']))
    Tooltip(host.project_button, '项目')
    host.project_name_list = ProjectNameList(host, host.project_block)
    host.project_name_list.pack(fill='x')
    host._sidebar_expand_kind = None
    host.project_group_buttons = {}
    host.project_buttons = ()
    column = ExpandIconColumn(host.project_block, getattr(host, 'win', side),
                              scrollbar=False, keys=True, columns=2)
    host._project_expand_column = column
    host.sidebar_expand = column.frame
    for state in ('making', 'completed'):
        button = column.add(
            state, PROJECT_GROUP_ICONS[state], '',
            '在制作项目' if state == 'making' else '已完成项目',
            lambda s=state: host.set_project_group(
                'all' if getattr(host, '_project_group', 'making') == s else s))
        host.project_group_buttons[state] = button
    host.project_new_button = column.add(
        'new', PROJECT_ACTION_ICONS['new'], '', '+ 新建项目',
        lambda: (close_sidebar_expand(host), host.new()))
    host.project_open_button = column.add(
        'open', PROJECT_ACTION_ICONS['open'], '', '打开项目目录',
        lambda: (close_sidebar_expand(host), host.open_current_project()))
    host.project_buttons = (host.project_new_button, host.project_open_button)
    column.finalize()
    host._sync_project_group_styles()
    host._sync_project_picker()


# ── 侧栏内嵌二级列的开合（点空白／Esc 收起）────────────────────────────
def toggle_project_expand(host):
    if getattr(host, '_sidebar_expand_kind', None) == 'project':
        close_sidebar_expand(host)
        return
    open_sidebar_expand(host, 'project')


def open_sidebar_expand(host, kind='project'):
    """在项目区内部展开四个二级图标；与侧栏浮层互斥（开一个收另一个）。"""
    close_popup = getattr(host, '_close_sidebar_popup', None)
    if callable(close_popup):
        close_popup()
    column = getattr(host, '_project_expand_column', None)
    if column is None:
        return
    host._sidebar_expand_kind = kind
    if not column.frame.winfo_manager():
        target = getattr(host, 'project_name_list', None)
        pack_kw = dict(side='top', anchor='w', pady=(SPACING['none'], SPACING['xs']))
        if target is not None and target.winfo_manager():
            pack_kw['before'] = target
        column.frame.pack(**pack_kw)
    win = getattr(host, 'win', None)
    if win is None:
        return
    if getattr(host, '_sidebar_expand_button_bind', None) is None:
        host._sidebar_expand_button_bind = win.bind(
            '<Button-1>',
            lambda event: sidebar_expand_outside(host, event), add='+')
    if getattr(host, '_sidebar_expand_escape_bind', None) is None:
        host._sidebar_expand_escape_bind = win.bind(
            '<Escape>', lambda _event: close_sidebar_expand(host), add='+')


def close_sidebar_expand(host):
    """收起侧栏二级列并摘掉点空白／Esc 监听（unbind 带 funcid，只摘自己那条）。"""
    try:
        host._sidebar_expand_kind = None
    except Exception:
        app_logging.swallowed()
    column = getattr(host, '_project_expand_column', None)
    if column is not None and column.frame.winfo_manager():
        column.frame.pack_forget()
    win = getattr(host, 'win', None)
    for attr, seq in (('_sidebar_expand_button_bind', '<Button-1>'),
                      ('_sidebar_expand_escape_bind', '<Escape>')):
        bind = getattr(host, attr, None)
        if bind and win is not None:
            try:
                win.unbind(seq, bind)
            except tk.TclError:
                pass
        try:
            setattr(host, attr, None)
        except Exception:
            app_logging.swallowed()


def sidebar_expand_outside(host, event):
    """二级列外按下左键即收；点主图标与列内部的点击放行。"""
    if getattr(host, '_sidebar_expand_kind', None) is None:
        return
    node = getattr(event, 'widget', None)
    expand = getattr(host, 'sidebar_expand', None)
    anchor = getattr(host, 'project_button', None)
    try:
        for _ in range(32):
            if node is None or node is host.win:
                break
            if node is expand or node is anchor:
                return
            node = getattr(node, 'master', None)
    except Exception:
        app_logging.swallowed()
    close_sidebar_expand(host)
