# -*- coding: utf-8 -*-
"""REQ-UI-SIDEBAR-1：侧栏项目区——「项目」主图标＋右对齐二级图标＋悬停宽项目卡片。

窄侧栏（96px）里直接放树表只能露出两三个字，因此：
- 侧栏顶部的「项目」主图标放大并与主导航轨对齐居中；点击后在右侧展开 4 枚
  缩小后的二级图标（在制作／已完成／新建／打开目录），不占聊天区。
- 主图标下方改为紧凑的「当前项目胶囊」：展示当前项目短名与当前分组数量；
  鼠标悬停或点击即可在侧栏右侧浮出一张宽项目卡片（320px），完整展示全部项目名、
  分组切换、当前高亮、单击切换、右键菜单与新建／打开／管理快捷入口，不挤动聊天框。
项目数据只读已加载的 ``projects.info``，不在启动路径扫目录。
"""

import tkinter as tk
from pathlib import Path
from tkinter import ttk

import infra.app_logging as app_logging
from ui.desktop_expand_column import ExpandIconColumn
from ui.desktop_file_card import TreeRowCard
from ui.desktop_page_registry import PROJECT_ACTION_ICONS, PROJECT_GROUP_ICONS
from ui.ui_icons import IconLoader
from ui.ui_popup import Flyout, monitor_bounds
from ui.ui_theme import box_frame
from ui_tokens import (COLORS, DESKTOP_LAYOUT, NAV_PRIMARY_ICON_SIZE,
                       NAV_SECONDARY_ICON_SIZE, PROJECT_CARD_CLOSE_MS,
                       PROJECT_CARD_HOVER_MS, PROJECT_CARD_WIDTH, SPACING)
from ui_widgets import DataTable, SecondaryButton, Tooltip

MIN_ROWS = 3
MAX_CARD_ROWS = 9
GROUP_LABELS = (('all', '全部'), ('making', '在制作'), ('completed', '已完成'))
_GROUP_TEXT = dict(GROUP_LABELS)
_CAPSULE_NAME_LIMIT = 12


def _compact_name(name, limit=_CAPSULE_NAME_LIMIT):
    text = str(name or '').strip()
    if len(text) <= limit:
        return text
    return text[:limit - 1] + '…'


def _project_display_name(project):
    return str(project.get('name') or Path(str(project.get('path'))).name)


def _is_same_path(first, second):
    if first is None or second is None:
        return False
    try:
        return Path(str(first)) == Path(str(second))
    except (OSError, ValueError):
        return str(first) == str(second)


def _pointer_in_widget(widget, px, py):
    if widget is None:
        return False
    try:
        if not widget.winfo_exists() or not widget.winfo_ismapped():
            return False
        left = widget.winfo_rootx()
        top = widget.winfo_rooty()
        return (left <= px <= left + widget.winfo_width()
                and top <= py <= top + widget.winfo_height())
    except tk.TclError:
        return False


class ProjectNameList(ttk.Frame):
    """侧栏项目切换器：窄侧栏放可读的当前项目胶囊，悬停／点击弹出宽项目选择卡片。

    卡片浮在侧栏右侧（被动 Flyout，不抢输入焦点、不挤压聊天区），提供完整项目名、
    分组切换、当前高亮、单击／Enter 切换、右键项目菜单与底部快捷动作。
    """

    def __init__(self, host, parent):
        super().__init__(parent)
        self.host = host
        self._card_win = None
        self._card_group_buttons = {}
        self._card_details = {}
        self._row_tips = None
        self._open_job = None
        self._close_job = None
        self._card_button_bind = None
        self._card_escape_bind = None
        self._menu_open = False
        self.table = None

        self.trigger = box_frame(self, padding=(SPACING['xs'], SPACING['xs']),
                                 cursor='hand2')
        self.trigger.pack(fill='x')
        self.trigger.configure(takefocus=1)
        wrap_px = max(SPACING['2xl'],
                      DESKTOP_LAYOUT['sidebar_width'] - SPACING['xl'])
        self.current_label = ttk.Label(
            self.trigger, text='未打开项目', style='SidebarProject.TLabel',
            anchor='center', justify='center', wraplength=wrap_px,
            cursor='hand2')
        self.current_label.pack(fill='x')
        self.count_label = ttk.Label(
            self.trigger, text='在制作 0 ▸', style='SidebarProjectMuted.TLabel',
            anchor='center', cursor='hand2')
        self.count_label.pack(fill='x', pady=(SPACING['xs'] // 2, SPACING['none']))

        for widget in (self, self.trigger, self.current_label, self.count_label):
            widget.bind('<Enter>', self._on_trigger_enter, add='+')
            widget.bind('<Leave>', self._on_trigger_leave, add='+')
            widget.bind('<Button-1>', self._on_trigger_click, add='+')
        self.trigger.bind('<Return>', lambda _e: self.open_card(focus_list=True), add='+')
        self.trigger.bind('<space>', lambda _e: self.open_card(focus_list=True), add='+')
        self.bind('<Destroy>', self._on_destroy, add='+')

    def _on_destroy(self, event=None):
        if event is not None and getattr(event, 'widget', None) is not self:
            return
        self._cancel_timers()
        self.close_card()

    # ── 胶囊刷新与悬停卡片同步 ────────────────────────────────────────
    def _current_project_title(self):
        root = getattr(self.host, 'root', None)
        if root is None:
            return '未打开项目'
        registry = ((getattr(getattr(self.host, 'projects', None), 'info', None)
                     or {}).get('projects') or [])
        for project in registry:
            if _is_same_path(project.get('path'), root):
                glyph = '●' if project.get('status', 'making') == 'making' else '○'
                return '%s %s' % (glyph, _compact_name(_project_display_name(project)))
        return '● ' + _compact_name(Path(str(root)).name)

    def refresh(self):
        """刷新胶囊文字；悬停卡片展开时同步刷新其中的项目列表与分组高亮。"""
        items = list(getattr(self.host, '_picker_items', None) or [])
        group = getattr(self.host, '_project_group', 'making')
        group_name = _GROUP_TEXT.get(group, '全部')
        try:
            self.current_label.configure(text=self._current_project_title())
            self.count_label.configure(text='%s %d ▸' % (group_name, len(items)))
        except tk.TclError:
            return
        if self._card_open():
            self._populate_card_rows()
            self._sync_card_group_styles()

    # ── 悬停状态机（移入延迟＋移出宽限，跨入卡片不断开）────────────────
    def _cancel_timers(self):
        win = getattr(self.host, 'win', None)
        for attr in ('_open_job', '_close_job'):
            job = getattr(self, attr, None)
            if job is not None and win is not None:
                try:
                    win.after_cancel(job)
                except tk.TclError:
                    pass
            setattr(self, attr, None)

    def _on_trigger_enter(self, _event=None):
        self._cancel_close()
        if self._card_open() or self._open_job is not None:
            return
        win = getattr(self.host, 'win', None)
        if win is None:
            self.open_card()
            return
        try:
            self._open_job = win.after(PROJECT_CARD_HOVER_MS, self._open_from_hover)
        except tk.TclError:
            self._open_job = None

    def _open_from_hover(self):
        self._open_job = None
        if not self._card_open():
            self.open_card()

    def _on_trigger_leave(self, _event=None):
        self._cancel_open()
        self._schedule_close()

    def _on_trigger_click(self, _event=None):
        self._cancel_timers()
        self.toggle_card()

    def _cancel_open(self):
        win = getattr(self.host, 'win', None)
        if self._open_job is not None and win is not None:
            try:
                win.after_cancel(self._open_job)
            except tk.TclError:
                pass
        self._open_job = None

    def _cancel_close(self):
        win = getattr(self.host, 'win', None)
        if self._close_job is not None and win is not None:
            try:
                win.after_cancel(self._close_job)
            except tk.TclError:
                pass
        self._close_job = None

    def _schedule_close(self):
        if self._menu_open or not self._card_open():
            return
        self._cancel_close()
        win = getattr(self.host, 'win', None)
        if win is None:
            self.close_card()
            return
        try:
            self._close_job = win.after(PROJECT_CARD_CLOSE_MS, self._close_if_pointer_away)
        except tk.TclError:
            self._close_job = None

    def _close_if_pointer_away(self):
        self._close_job = None
        if self._menu_open or not self._card_open():
            return
        win = getattr(self.host, 'win', None)
        if win is not None:
            try:
                px, py = win.winfo_pointerxy()
            except tk.TclError:
                px = py = -1
            if (_pointer_in_widget(self.trigger, px, py)
                    or _pointer_in_widget(self._card_win, px, py)):
                return
        self.close_card()

    # ── 宽项目卡片构建与定位 ──────────────────────────────────────────
    def _card_open(self):
        top = self._card_win
        if top is None:
            return False
        try:
            return bool(top.winfo_exists())
        except tk.TclError:
            return False

    def toggle_card(self):
        if self._card_open():
            self.close_card()
        else:
            self.open_card()

    def open_card(self, *, focus_list=False):
        """在侧栏右侧弹出宽项目卡片（320px）；与侧栏其他弹层互斥。"""
        self._cancel_timers()
        close_popup = getattr(self.host, '_close_sidebar_popup', None)
        if callable(close_popup):
            close_popup()
        close_sidebar_expand(self.host)
        if self._card_open():
            self._populate_card_rows()
            self._sync_card_group_styles()
            if focus_list and self.table is not None:
                self.table.tree.focus_set()
            return self._card_win
        win = getattr(self.host, 'win', None)
        if win is None:
            return None
        top = Flyout(win, noactivate=not focus_list)
        self._card_win = top
        self._build_card_contents(top.body)
        self._populate_card_rows()
        self._sync_card_group_styles()
        self._position_card(top)
        top.bind('<Enter>', lambda _e: self._cancel_close(), add='+')
        top.bind('<Leave>', lambda _e: self._schedule_close(), add='+')
        top.bind('<Destroy>', self._on_card_destroyed, add='+')
        self._card_button_bind = win.bind('<Button-1>', self._on_outside_click, add='+')
        self._card_escape_bind = win.bind('<Escape>', lambda _e: self.close_card(), add='+')
        if focus_list and self.table is not None:
            self.table.tree.focus_set()
        return top

    def _build_card_contents(self, body):
        header = ttk.Frame(body)
        header.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
        ttk.Label(header, text='项目目录', style='CardHeading.TLabel').pack(side='left')
        pills = ttk.Frame(header)
        pills.pack(side='right')
        self._card_group_buttons = {}
        for state, label in GROUP_LABELS:
            button = SecondaryButton(
                pills, text=label, width=0, style='Compact.TButton',
                command=lambda s=state: self._switch_group(s))
            button.pack(side='left', padx=(SPACING['xs'], SPACING['none']))
            self._card_group_buttons[state] = button

        ttk.Separator(body).pack(fill='x', pady=(SPACING['none'], SPACING['xs']))

        state_w = SPACING['sm'] * 8
        name_w = PROJECT_CARD_WIDTH - state_w - SPACING['lg']
        self.table = DataTable(
            body,
            columns=[('name', '项目名称', name_w), ('state', '状态', state_w)],
            show='', height=MIN_ROWS, selectmode='browse',
            empty_text='该分组暂无项目', auto_hide_scrollbars=True,
            horizontal=False)
        self.table.pack(fill='both', expand=True)
        tree = self.table.tree
        tree.column('name', width=name_w, minwidth=SPACING['2xl'] * 4,
                    anchor='w', stretch=True)
        tree.column('state', width=state_w, minwidth=state_w,
                    anchor='e', stretch=False)
        tree.tag_configure('current', background=COLORS['primary_subtle'])
        tree.configure(takefocus=1)
        self._card_details = {}
        self._row_tips = TreeRowCard(tree, lambda item: self._card_details.get(item, ''))
        tree.bind('<Button-1>', self._click_row, add='+')
        tree.bind('<Double-1>', self._activate_selected)
        tree.bind('<Return>', self._activate_selected)
        tree.bind('<Button-3>', self._row_menu, add='+')

        ttk.Separator(body).pack(fill='x', pady=(SPACING['xs'], SPACING['xs']))
        footer = ttk.Frame(body)
        footer.pack(fill='x')
        SecondaryButton(
            footer, text='+ 新建项目', width=0, style='Compact.TButton',
            command=lambda: (self.close_card(), self.host.safe(self.host.new))
        ).pack(side='left')
        SecondaryButton(
            footer, text='打开目录', width=0, style='Compact.TButton',
            command=lambda: (self.close_card(),
                             self.host.safe(self.host.open_current_project))
        ).pack(side='left', padx=(SPACING['xs'], SPACING['none']))
        SecondaryButton(
            footer, text='项目管理…', width=0, style='Compact.TButton',
            command=lambda: (self.close_card(), self.host.safe(self.host.choose_project))
        ).pack(side='right')

    def _populate_card_rows(self):
        if self.table is None:
            return
        tree = self.table.tree
        tree.tag_configure('current', background=COLORS['primary_subtle'])
        tree.delete(*tree.get_children())
        self._card_details.clear()
        items = list(getattr(self.host, '_picker_items', None) or [])
        root = getattr(self.host, 'root', None)
        for project in items:
            status = project.get('status', 'making')
            glyph = '●' if status == 'making' else '○'
            name = _project_display_name(project)
            path = str(project.get('path'))
            current = _is_same_path(path, root)
            badge = '当前' if current else ('在制作' if status == 'making' else '已完成')
            tags = ('current',) if current else ()
            tree.insert('', 'end', iid=path,
                        values=('%s %s' % (glyph, name), badge), tags=tags)
            self._card_details[path] = '%s\n状态：%s\n路径：%s' % (name, badge, path)
        registry = ((getattr(getattr(self.host, 'projects', None), 'info', None)
                     or {}).get('projects') or [])
        self.table.empty_label.configure(
            text='暂无项目' if not registry else '该分组暂无项目')
        rows = max(MIN_ROWS, min(len(items), MAX_CARD_ROWS)) if items else MIN_ROWS
        tree.configure(height=rows)
        self.table.refresh_empty_state()

    def _sync_card_group_styles(self):
        current = getattr(self.host, '_project_group', 'making')
        for state, button in self._card_group_buttons.items():
            try:
                button.configure(
                    style='Selected.Compact.TButton' if state == current else 'Compact.TButton')
            except tk.TclError:
                pass

    def _position_card(self, top):
        top.update_idletasks()
        width = max(PROJECT_CARD_WIDTH, top.winfo_reqwidth())
        height = top.winfo_reqheight()
        sidebar = getattr(self.host, 'sidebar_area', None) or self.trigger
        x = sidebar.winfo_rootx() + sidebar.winfo_width() + SPACING['xs'] // 2
        y = self.trigger.winfo_rooty()
        left, stop, right, sbottom = monitor_bounds(self.host.win, x, y)
        if x + width > right - SPACING['xs']:
            x = max(left + SPACING['xs'], right - SPACING['xs'] - width)
        if y + height > sbottom - SPACING['xs']:
            y = max(stop + SPACING['xs'], sbottom - SPACING['xs'] - height)
        top.geometry('%dx%d+%d+%d' % (width, height, x, y))

    def _switch_group(self, state):
        self.host.set_project_group(state)
        if self._card_open():
            self._position_card(self._card_win)

    def _on_outside_click(self, event):
        if self._menu_open or not self._card_open():
            return
        widget = getattr(event, 'widget', None)
        try:
            if widget is not None and widget.winfo_toplevel() is self._card_win:
                return
            node = widget
            for _ in range(16):
                if node is None:
                    break
                if node is self or node is self.trigger:
                    return
                node = getattr(node, 'master', None)
        except tk.TclError:
            pass
        self.close_card()

    def _on_card_destroyed(self, event=None):
        top = self._card_win
        if top is None or (event is not None and event.widget is not top):
            return
        self._unbind_card_events()
        self._card_win = None
        self.table = None
        self._card_group_buttons = {}

    def _unbind_card_events(self):
        win = getattr(self.host, 'win', None)
        for attr, seq in (('_card_button_bind', '<Button-1>'),
                          ('_card_escape_bind', '<Escape>')):
            bind = getattr(self, attr, None)
            if bind and win is not None:
                try:
                    win.unbind(seq, bind)
                except tk.TclError:
                    pass
            setattr(self, attr, None)

    def close_card(self):
        """关闭宽项目卡片并摘掉事件监听。"""
        self._cancel_timers()
        self._unbind_card_events()
        top = self._card_win
        self._card_win = None
        self.table = None
        self._card_group_buttons = {}
        self._menu_open = False
        if top is not None:
            try:
                if top.winfo_exists():
                    top.destroy()
            except tk.TclError:
                pass

    # ── 选择与动作 ────────────────────────────────────────────────────
    def _pick(self, iid):
        """切换项目：收起卡片并复用 ``request_project_switch``（任务拦截＋确认＋失效找回）。"""
        path = str(iid)
        self.close_card()
        if _is_same_path(path, getattr(self.host, 'root', None)):
            return
        self.host.safe(lambda: self.host.request_project_switch(path))

    def _click_row(self, event):
        if self.table is None:
            return
        iid = self.table.tree.identify_row(event.y)
        if not iid:
            return
        try:
            self.table.tree.selection_set(iid)
        except tk.TclError:
            return
        self._pick(iid)

    def _activate_selected(self, _event=None):
        if self.table is None:
            return
        selection = self.table.tree.selection()
        if selection:
            self._pick(selection[0])

    def _row_menu(self, event):
        if self.table is None:
            return
        iid = self.table.tree.identify_row(event.y)
        if not iid:
            return
        project = next((p for p in (getattr(self.host, '_picker_items', None)
                                    or [])
                        if str(p.get('path')) == str(iid)), None)
        if project is None:
            return
        self._menu_open = True
        self._cancel_close()
        try:
            self.host._project_item_menu(dict(project), event)
        finally:
            self._menu_open = False


def build_project_rail(host, side):
    """侧栏项目区：居中放大的「项目」主图标＋贴右展开的 4 枚小二级图标＋悬停项目切换胶囊。"""
    host.project_block = ttk.Frame(side)
    host.project_block.pack(fill='x', pady=(SPACING['xs'], SPACING['none']))
    host._project_group = 'making'
    host._picker_items = []
    image = IconLoader.nav_icon(side, 'project_files', size=NAV_PRIMARY_ICON_SIZE)
    host.project_button = SecondaryButton(
        host.project_block, text='', image=image,
        compound='image' if image is not None else 'text', width=0,
        style='RailIcon.TButton', command=lambda: toggle_project_expand(host))
    host.project_button.pack(
        anchor='w',
        padx=(DESKTOP_LAYOUT['nav_primary_inset'], SPACING['none']),
        pady=(SPACING['none'], DESKTOP_LAYOUT['nav_gap']))
    Tooltip(host.project_button, '项目')
    host.project_name_list = ProjectNameList(host, host.project_block)
    host.project_name_list.pack(fill='x')
    host._sidebar_expand_kind = None
    host.project_group_buttons = {}
    host.project_buttons = ()
    column = ExpandIconColumn(host.project_block, getattr(host, 'win', side),
                              scrollbar=False, keys=True, columns=2,
                              icon_size=NAV_SECONDARY_ICON_SIZE)
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
    """在项目区右侧展开四个缩小后的二级图标；与侧栏浮层、项目卡片互斥。"""
    close_popup = getattr(host, '_close_sidebar_popup', None)
    if callable(close_popup):
        close_popup()
    project_list = getattr(host, 'project_name_list', None)
    if project_list is not None and callable(getattr(project_list, 'close_card', None)):
        project_list.close_card()
    column = getattr(host, '_project_expand_column', None)
    if column is None:
        return
    host._sidebar_expand_kind = kind
    if not column.frame.winfo_manager():
        target = getattr(host, 'project_name_list', None)
        pack_kw = dict(side='top', anchor='e', pady=(SPACING['none'], SPACING['xs']))
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
