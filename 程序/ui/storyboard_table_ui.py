"""Tk table adapters and S03 storyboard editor view shared by storyboard pages."""
import json
import re
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk
import infra.app_logging as app_logging
from ui_tokens import (
    COLORS, FONTS, SCRIPT_VIEW_FONT, SCRIPT_VIEW_FONT_MAX, SCRIPT_VIEW_FONT_MIN,
    SCRIPT_VIEW_PADDING, SCROLLBAR_WIDTH, SPACING, TEXT_ROWS,
)
from ui_widgets import ContextMenu, DataTable, LineInput, SecondaryButton, TextArea, Tooltip
from ui.ui_shortcuts import ShortcutRegistry
from ui.script_line_numbers import LineNumberGutter

from responsive_ui import (
    CHECK_COLUMN_WIDTH, VIEW_PAD, auto_columns, auto_height, cached_fonts,
    configure_check_column, configure_column, fit_columns_by_content, measure,
    remember_columns, squeeze, view_width,
)
from domain.storyboard_catalog_service import content_preview, has_synced_assets


def file_table(parent, height=4, selectmode='browse', first_label='文件 / 内容', status_label=None):
    columns=[('file',first_label,240)]
    if status_label:columns.append(('status',status_label,90))
    columns+= [('content','文件内容(点击查看)',240),('time','创建时间',90),('location','项目内位置',160)]
    area=DataTable(parent,columns=columns,show='tree headings',height=height,selectmode=selectmode)
    area.pack(fill='both',expand=True)
    tree=area.tree
    configure_check_column(tree)
    for col,label,width in columns:
        tree.heading(col,text=label);tree.column(col,width=width,minwidth=60,stretch=True)
    if selectmode=='extended':
        def select_all(event=None):
            tree.selection_set(tree.get_children());return 'break'
        ShortcutRegistry().bind(tree, ('<Control-a>', '<Control-A>'), select_all,
                               scope='分镜文件表', name='全选文件')
    tree.tag_configure('completed',background=COLORS['row_done_bg'],foreground=COLORS['success_text'])
    auto_height(tree, area)
    def schedule_fit(event=None):
        if getattr(tree,'_fit_columns_pending',False):return
        tree._fit_columns_pending=True
        def run():
            tree._fit_columns_pending=False
            if getattr(tree,'_entries_filling',False):return
            try:fit_file_columns(tree)
            except Exception:app_logging.swallowed()
        tree.after_idle(run)
    tree.bind('<Configure>',schedule_fit,add='+')
    return tree


def fit_file_columns(tree, cap=220):
    """Fit file-picker columns to content while respecting the visible viewport."""
    body,heading=cached_fonts(tree)
    rows=[list(tree.item(item,'values')) for item in tree.get_children()]
    configure_column(tree,'#0',CHECK_COLUMN_WIDTH,minwidth=CHECK_COLUMN_WIDTH,stretch=False,anchor='center')
    meta={'status','sync','time'};columns=list(tree['columns']);widths=[];floors=[]
    for index,column in enumerate(columns):
        header_w=measure(heading,tree.heading(column,'text'))+SPACING['lg']
        cells=[measure(body,row[index]) for row in rows if index < len(row)]
        content_w=(max(cells) if cells else 0)+SPACING['lg']
        widths.append(int(max(header_w,content_w) if column in meta else min(cap,max(header_w,content_w))))
        floors.append(int(header_w))
    remember_columns(tree,zip(columns,widths))
    available=view_width(tree)
    if available:widths=squeeze(widths,max(1,available-CHECK_COLUMN_WIDTH-VIEW_PAD),floors)
    for index,column in enumerate(columns):
        centered=column in meta
        configure_column(tree,column,widths[index],minwidth=floors[index],stretch=not centered,
                         anchor='center' if centered else 'w')
    tree._view_fit_width=available
    auto_columns(tree)


def fit_final_columns(tree):
    """Fit synchronized-storyboard columns to content and the current viewport."""
    fit_columns_by_content(tree,{'file':lambda width:min(360,width)},fill=True)


def tree_columns(tree):
    columns=tree['columns']
    return [str(column) for column in (columns if isinstance(columns,(list,tuple)) else str(columns).split())]


def insert_entries(tree, project, entries, status_of=None, with_sync=False, *, batch_size=None, on_complete=None):
    """Render catalog entries into a picker table without owning catalog discovery."""
    cancel=getattr(tree,'_entry_fill_cancel',None)
    if cancel is not None:cancel()
    columns=tree_columns(tree)
    previous=set(tree.get_children());wanted=[];position=0
    state={'job':None,'cancelled':False}
    def cancel_fill():
        state['cancelled']=True
        if state['job'] is not None:
            tree.after_cancel(state['job']);state['job']=None
    tree._entry_fill_cancel=cancel_fill
    if not getattr(tree,'_entry_fill_bound',False):
        def destroyed(event):
            if event.widget is tree:tree._entry_fill_cancel()
        tree.bind('<Destroy>',destroyed,add='+');tree._entry_fill_bound=True
    tree._entries_filling=True
    def insert(entry):
        path=entry['path'];location=path.relative_to(project).as_posix() if path.is_relative_to(project) else str(path)
        title=str(entry.get('title','')).replace(' · 已制作分镜','').replace(' · 已采用','')
        synced=has_synced_assets(path) if with_sync or 'sync' in columns else False
        row={'file':(title+'·'+('同步' if synced else '未同步')) if with_sync else title,
             'status':status_of(entry) if status_of is not None else '',
             'sync':'已同步' if synced else '未同步',
             'content':(entry['preview'] if 'preview' in entry else content_preview(path)) if 'content' in columns else '',
             'time':datetime.fromtimestamp(entry['created']).strftime('%m-%d %H:%M'), 'location':location}
        item=str(path);wanted.append(item)
        options=dict(text='',values=[row.get(column,'') for column in columns],
                     tags=('completed',) if with_sync and synced else ())
        if item in previous:tree.item(item,**options)
        else:tree.insert('','end',iid=item,**options)
    def fill():
        nonlocal position
        state['job']=None
        if state['cancelled']:return
        end=min(len(entries),position+(batch_size or max(1,len(entries))))
        for entry in entries[position:end]:insert(entry)
        position=end
        if position<len(entries):
            state['job']=tree.after(1,fill);return
        stale=previous-set(wanted)
        if stale:tree.delete(*stale)
        tree.set_children('',*wanted)
        tree._entries_filling=False
        (fit_final_columns if with_sync else fit_file_columns)(tree)
        table=getattr(tree,'_data_table',None)
        if table is not None:table.refresh_empty_state()
        if on_complete is not None:on_complete()
    fill()


S03_HINT_READ = '快捷键：Ctrl+G 镜头定位 · Ctrl+F 查找 · Ctrl+滚轮/Ctrl+± 缩放 · Ctrl+O 打开 · 右键采用/编辑/重排（右侧文件栏切换剧本与分镜）'
S03_HINT_EDIT = '编辑中：Ctrl+S 保存 · Ctrl+Z 撤销 · Ctrl+Y 重做 · Ctrl+F 查找 · Ctrl+G 镜头定位 · 右键退出编辑'
_SHOT_NAV_WIDTH = 24
_SHOT_NAV_WHEEL_LINES = 4
_SHOT_LABEL_MAX = 26
_SHOT_HIT_TAG = 's03_shot_hit'
_FIELD_PREFIX = re.compile(r'^-\s*(?:角色|场景|道具|对白|首帧提示词|视频提示词|景别|运镜|情绪|时长|音效)[：:]')
_SHOT_ID_RE = re.compile(r'\bSH\d+[A-Za-z0-9_-]*\b')
_MD_SHOT_HEAD = re.compile(r'^#{2,3}\s+(.+)$')
_JSON_SHOT_ID = re.compile(r'"id"\s*:\s*"(SH[^"]+)"')
_JSON_SHOT_TITLE = re.compile(r'"title"\s*:\s*"([^"]*)"')
S03_EMPTY_TEXT = (
    '尚未生成初步分镜。\n\n'
    '· 在右侧文件停靠面板查看「来源文档（结构剧本）」与「本阶段产物（初步分镜）」，点击即可在此阅读；\n'
    '· 直接在下方输入框发送（可填补充要求或输入 / 调用技能）即可开始制作初步分镜；\n'
    '· 在本区域点击鼠标右键可执行：采用／取消采用分镜、导入 JSON 分镜、重排镜头编号、打开分镜目录等操作。'
)


def font_at_size(spec, size):
    """在 token 缩放范围内生成字号调整后的字体元组，避免在 font= 处内联元组字面量。"""
    clamped = max(SCRIPT_VIEW_FONT_MIN, min(SCRIPT_VIEW_FONT_MAX, int(size)))
    return (spec[0], clamped) + tuple(spec[2:])


def format_storyboard_for_editor(path, data, adopted=False):
    """把分镜 JSON 渲染为易读的分镜文本视图，突出集头、采用状态与逐镜提示词。"""
    shots = data.get('shots') if isinstance(data, dict) else None
    if not isinstance(shots, list):
        return json.dumps(data, ensure_ascii=False, indent=2)
    ep = str(data.get('episode_id') or Path(path).stem)
    title = str(data.get('title') or '')
    badge = '已采用' if adopted else '未采用'
    header = '# %s%s  [%s]' % (ep, (' · ' + title) if title else '', badge)
    meta = ['镜头数：%d' % len(shots)]
    if data.get('duration') is not None:
        meta.append('总时长：%s 秒' % data.get('duration'))
    if data.get('source_script'):
        meta.append('来源剧本：%s' % data.get('source_script'))
    lines = [header, '｜'.join(meta)]
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        lines.append('')
        lines.append('## %s｜%s（%ss）' % (
            shot.get('id') or 'SH?', shot.get('title') or '未命名镜头',
            shot.get('duration') if shot.get('duration') is not None else '?'))
        chars = '、'.join(str(c) for c in (shot.get('characters') or ()) if c)
        loc = str(shot.get('location') or '')
        props = '、'.join(str(p) for p in (shot.get('props') or ()) if p)
        parts = []
        if chars:
            parts.append('角色：' + chars)
        if loc:
            parts.append('场景：' + loc)
        if props:
            parts.append('道具：' + props)
        if parts:
            lines.append('- ' + '｜'.join(parts))
        if shot.get('dialogue'):
            lines.append('- 对白：%s' % shot.get('dialogue'))
        if shot.get('frame_prompt'):
            lines.append('- 首帧提示词：%s' % shot.get('frame_prompt'))
        if shot.get('video_prompt'):
            lines.append('- 视频提示词：%s' % shot.get('video_prompt'))
    return '\n'.join(lines)


def _clip_label(text):
    clean = ' '.join(str(text or '').split())
    return clean if len(clean) <= _SHOT_LABEL_MAX else clean[:_SHOT_LABEL_MAX - 1] + '…'


def extract_storyboard_shots(text):
    """解析分镜／剧本文本中的所有镜头或场次锚点，返回 ``[(行号, 标题, 全块检索串)]``。

    同时支持格式化分镜视图（``## SH001｜...``）、Markdown 分镜／分场标题与原始 JSON（``"id": "SH..."``）。
    """
    lines = str(text or '').split('\n')
    anchors = []
    for index, raw in enumerate(lines, 1):
        stripped = raw.strip()
        match = _MD_SHOT_HEAD.match(stripped)
        if match:
            anchors.append((index, _clip_label(match.group(1))))
    if not anchors:
        for index, raw in enumerate(lines, 1):
            match = _JSON_SHOT_ID.search(raw)
            if not match:
                continue
            sid = match.group(1)
            window = '\n'.join(lines[index - 1:min(len(lines), index + 6)])
            t_match = _JSON_SHOT_TITLE.search(window)
            label = ('%s｜%s' % (sid, t_match.group(1))) if (t_match and t_match.group(1)) else sid
            anchors.append((index, _clip_label(label)))
    entries = []
    for pos, (line_no, label) in enumerate(anchors):
        next_line = anchors[pos + 1][0] - 1 if pos + 1 < len(anchors) else len(lines)
        blob = '\n'.join(lines[line_no - 1:next_line]).casefold()
        entries.append((line_no, label, blob))
    return entries


def apply_storyboard_highlights(viewer, text):
    """给分镜正文施加结构化语法高亮：集头、镜头标题、字段前缀与镜头编号。"""
    viewer.tag_configure('s03_ep', font=FONTS['heading_3'], foreground=COLORS['text_heading'])
    viewer.tag_configure('s03_shot', font=FONTS['body_bold'], foreground=COLORS['primary'])
    viewer.tag_configure('s03_field', font=FONTS['body_bold'], foreground=COLORS['text_secondary'])
    viewer.tag_configure('s03_id', foreground=COLORS['primary'])
    for tag in ('s03_ep', 's03_shot', 's03_field', 's03_id'):
        viewer.tag_remove(tag, '1.0', 'end')
    for index, raw in enumerate(str(text or '').split('\n'), 1):
        stripped = raw.lstrip()
        if stripped.startswith('# ') and not stripped.startswith('##'):
            viewer.tag_add('s03_ep', '%d.0' % index, '%d.end' % index)
        elif stripped.startswith('##'):
            viewer.tag_add('s03_shot', '%d.0' % index, '%d.end' % index)
        else:
            field = _FIELD_PREFIX.match(stripped)
            if field:
                lead = len(raw) - len(stripped)
                viewer.tag_add('s03_field', '%d.%d' % (index, lead), '%d.%d' % (index, lead + field.end()))
            for match in _SHOT_ID_RE.finditer(raw):
                viewer.tag_add('s03_id', '%d.%d' % (index, match.start()), '%d.%d' % (index, match.end()))


class S03ShotNavigator(ttk.Frame):
    """03 初步分镜左侧镜头定位与搜索栏：按镜头号／角色／场景／对白／提示词实时过滤并一键跳转。"""

    def __init__(self, master, viewer, on_escape=None):
        super().__init__(master)
        self._viewer = viewer
        self._on_escape = on_escape
        self._all_entries = []
        self._filtered = []
        self._selected = -1
        self._user_hidden = False
        viewer.tag_configure(_SHOT_HIT_TAG, background=COLORS['selection_bg'])
        head = ttk.Frame(self)
        head.pack(fill='x', pady=(SPACING['none'], SPACING['xs'] // 2))
        ttk.Label(head, text='镜头定位', style='SidebarProjectMuted.TLabel').pack(side='left')
        self.count_label = ttk.Label(head, text='', style='SidebarProjectMuted.TLabel')
        self.count_label.pack(side='right')
        self.query_var = tk.StringVar(value='')
        self.search_entry = LineInput(
            self, textvariable=self.query_var,
            placeholder='搜镜头号/角色/场景…', width=SPACING['lg'])
        self.search_entry.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
        self.query_var.trace_add('write', lambda *_a: self._apply_filter())
        self.search_entry.bind('<Return>', self._jump_current)
        self.search_entry.bind('<Down>', lambda _e: self._step(1))
        self.search_entry.bind('<Up>', lambda _e: self._step(-1))
        self.search_entry.bind('<Escape>', self._handle_escape)
        body = ttk.Frame(self)
        body.pack(fill='both', expand=True)
        self.list_view = TextArea(
            body, bg=COLORS['background_card'], fg=COLORS['text_primary'],
            width=_SHOT_NAV_WIDTH, height=TEXT_ROWS['lg'], wrap='none',
            font=SCRIPT_VIEW_FONT, relief='flat', cursor='hand2',
            padx=SPACING['xs'], pady=SPACING['xs'], state='disabled')
        self.list_view._wheel_lines = _SHOT_NAV_WHEEL_LINES
        self.list_view.tag_configure(
            's03_nav_sel', background=COLORS['primary'], foreground=COLORS['background_card'])
        scroll = ttk.Scrollbar(body, orient='vertical', command=self.list_view.yview)
        self.list_view.configure(yscrollcommand=scroll.set)
        self.list_view.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.list_view.bind('<Button-1>', self._on_click)
        self.list_view.bind('<Return>', self._jump_current)
        self.list_view.bind('<Escape>', self._handle_escape)

    @property
    def visible(self):
        return bool(self.winfo_manager())

    def items(self):
        return [label for _line, label, _blob in self._filtered]

    def set_text(self, text):
        self._all_entries = extract_storyboard_shots(text)
        self._viewer.tag_remove(_SHOT_HIT_TAG, '1.0', 'end')
        self._apply_filter()
        if len(self._all_entries) >= 2 and not self._user_hidden:
            self.show(focus_search=False)
        elif not self._all_entries:
            self.hide(by_user=False)

    def show(self, *, focus_search=False):
        self._user_hidden = False
        if not self.visible:
            self.pack(side='left', fill='y', padx=(SPACING['none'], SPACING['xs']),
                      before=self._viewer.master)
        if focus_search:
            self.search_entry.focus_set()
            try:
                self.search_entry.selection_range(0, 'end')
            except tk.TclError:
                pass

    def hide(self, *, by_user=True):
        if by_user:
            self._user_hidden = True
        if self.visible:
            self.pack_forget()

    def _query_text(self):
        try:
            return str(self.search_entry.get() or '').strip().casefold()
        except tk.TclError:
            return ''

    def _apply_filter(self):
        needle = self._query_text()
        self._filtered = ([item for item in self._all_entries if needle in item[2]]
                          if needle else list(self._all_entries))
        self._selected = -1
        self.list_view.configure(state='normal')
        self.list_view.delete('1.0', 'end')
        if self._filtered:
            self.list_view.insert('1.0', '\n'.join(label for _line, label, _blob in self._filtered))
        self.list_view.tag_remove('s03_nav_sel', '1.0', 'end')
        self.list_view.configure(state='disabled')
        total, shown = len(self._all_entries), len(self._filtered)
        text = ('%d/%d 镜' % (shown, total)) if needle else ('%d 镜' % total if total else '无镜头')
        self.count_label.configure(text=text)

    def _select_index(self, index):
        if not (0 <= index < len(self._filtered)):
            return
        self._selected = index
        row_start = '%d.0' % (index + 1)
        row_end = '%d.end' % (index + 1)
        self.list_view.tag_remove('s03_nav_sel', '1.0', 'end')
        self.list_view.tag_add('s03_nav_sel', row_start, row_end)
        self.list_view.see(row_start)
        line, _label, _blob = self._filtered[index]
        start = '%d.0' % line
        try:
            end = self._viewer.index('%s lineend' % start)
        except tk.TclError:
            end = start
        self._viewer.tag_remove(_SHOT_HIT_TAG, '1.0', 'end')
        self._viewer.tag_add(_SHOT_HIT_TAG, start, end)
        self._viewer.see(start)
        self._viewer.mark_set('insert', start)

    def _on_click(self, event):
        try:
            line = int(str(self.list_view.index('@%d,%d' % (event.x, event.y))).split('.')[0])
        except (tk.TclError, ValueError):
            return 'break'
        if 1 <= line <= len(self._filtered):
            self._select_index(line - 1)
        return 'break'

    def _jump_current(self, _event=None):
        if not self._filtered:
            return 'break'
        idx = self._selected if 0 <= self._selected < len(self._filtered) else 0
        self._select_index(idx)
        return 'break'

    def _step(self, delta):
        if not self._filtered:
            return 'break'
        base = self._selected if 0 <= self._selected < len(self._filtered) else (-1 if delta > 0 else 0)
        self._select_index((base + delta) % len(self._filtered))
        return 'break'

    def _handle_escape(self, _event=None):
        if self._query_text():
            self.query_var.set('')
            self.search_entry.delete(0, 'end')
        if callable(self._on_escape):
            self._on_escape()
        self._viewer.focus_set()
        return 'break'


class S03EditorView:
    """03 初步分镜单编辑器视图组件：左侧镜头定位与搜索、语法高亮、查找计数条与缩放。"""

    def __init__(self, page, wheel_lines=9):
        self.page = page
        self.wheel_lines = wheel_lines
        self.zoom_delta = 0
        self._find_matches = []
        self._find_index = -1
        self._build()

    def _build(self):
        parent = self.page.page_content
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, pady=(SPACING['xs'], SPACING['none']))
        self.frame = frame
        self.shortcut_hint = ttk.Label(
            frame, text=S03_HINT_READ, style='SidebarProjectMuted.TLabel', anchor='w')
        self.shortcut_hint.pack(side='bottom', fill='x', pady=(SPACING['xs'] // 2, SPACING['none']))
        self._build_find_bar(frame)
        body = ttk.Frame(frame)
        body.pack(fill='both', expand=True)
        self.body = body
        area = ttk.Frame(body)
        area.pack(side='left', fill='both', expand=True)
        self.editor_area = area
        self.viewer = TextArea(
            area, bg=COLORS['background_card'], fg=COLORS['text_primary'], height=1,
            wrap='word', undo=True, maxundo=-1, font=SCRIPT_VIEW_FONT, relief='flat',
            padx=SCRIPT_VIEW_PADDING[0], pady=SCRIPT_VIEW_PADDING[1])
        self.viewer._wheel_lines = self.wheel_lines
        self.viewer._ctrl_wheel_zoom = self.zoom_by
        self.gutter = LineNumberGutter(area, self.viewer)
        scroll = ttk.Scrollbar(area, orient='vertical', command=self.viewer.yview)

        def sync_scroll(first, last):
            scroll.set(first, last)
            self.gutter.refresh()

        self.viewer.configure(yscrollcommand=sync_scroll)
        self.viewer.bind('<<Modified>>', lambda _e: self.gutter.refresh(), add='+')
        self.gutter.grid(row=0, column=0, sticky='ns')
        self.viewer.grid(row=0, column=1, sticky='nsew')
        scroll.grid(row=0, column=2, sticky='ns')
        area.columnconfigure(1, weight=1)
        area.rowconfigure(0, weight=1)
        self.close_button = SecondaryButton(
            area, text='×', width=0, style='Tokens.Secondary.TButton', takefocus=True,
            command=lambda: self.page.desktop.safe(self.page.close_document))
        Tooltip(self.close_button, '关闭当前文件（项目文件保留）')
        for sequence in ('<Return>', '<space>'):
            self.close_button.bind(sequence, lambda _e: (self.close_button.invoke(), 'break')[1], add='+')
        self.shot_nav = S03ShotNavigator(body, self.viewer)
        self.viewer.bind('<Button-3>', self.page.on_context_menu, add='+')
        self.viewer.bind('<Escape>', self._on_escape, add='+')
        self._bind_shortcuts()

    def set_document_header(self, path):
        """按当前文件显隐右上角关闭×；S03 不再显示顶部文件名内容框。"""
        if path is not None:
            self.close_button.place(relx=1.0, x=-(SCROLLBAR_WIDTH + SPACING['xs']),
                                    y=SPACING['xs'], anchor='ne')
            self.close_button.lift()
        else:
            self.close_button.place_forget()

    def follow_renamed(self, changed):
        page = self.page
        moved = {Path(old).resolve(): Path(new).resolve() for old, new in (changed or ())}
        if page.active_path in moved:
            page.active_path = moved[page.active_path]
            page.active_board_json = page._matching_board_json(page.active_path)
            self.set_document_header(page.active_path)

    def close_current(self, *, confirm_fn):
        """关闭当前文件视图；编辑态先走真实保存，保存失败则原样留在现场。"""
        page = self.page
        if page.active_path is None:
            return False
        if page.editing:
            try:
                page.exit_edit()
            except (OSError, ValueError) as exc:
                page.desktop.status.set('保存失败，未关闭当前文档：' + str(exc))
                return False
        page.active_path = None
        page.active_board_json = None
        page.raw_json_mode = False
        page.editing = False
        page._user_closed_document = True
        self.set_document_header(None)
        if self.find_bar.winfo_manager():
            self.hide_find_bar()
        self.shot_nav.hide(by_user=False)
        page._set_viewer_text(S03_EMPTY_TEXT, editable=False)
        page._update_status_segment()
        page.desktop.status.set('已关闭当前文档；项目文件保留')
        return True

    def _build_find_bar(self, parent):
        bar = ttk.Frame(parent)
        self.find_bar = bar
        self.find_var = tk.StringVar(value='')
        self.find_entry = LineInput(bar, textvariable=self.find_var,
                                    placeholder='查找镜头、角色、对白或提示词…', width=SPACING['xl'])
        self.find_entry.pack(side='left', fill='x', expand=True, padx=(SPACING['none'], SPACING['xs']))
        self.find_var.trace_add('write', lambda *_a: self._refresh_find_matches())
        self.find_entry.bind('<Return>', lambda _e: self.find_step(1))
        self.find_entry.bind('<Shift-Return>', lambda _e: self.find_step(-1))
        self.find_entry.bind('<Escape>', lambda _e: self.hide_find_bar())
        self.find_count = ttk.Label(bar, text='', style='SidebarProjectMuted.TLabel')
        self.find_count.pack(side='left', padx=(SPACING['none'], SPACING['xs']))
        SecondaryButton(bar, text='上一个', width=0, style='Compact.TButton',
                        command=lambda: self.find_step(-1)).pack(side='left', padx=(SPACING['none'], SPACING['xs']))
        SecondaryButton(bar, text='下一个', width=0, style='Compact.TButton',
                        command=lambda: self.find_step(1)).pack(side='left', padx=(SPACING['none'], SPACING['xs']))
        SecondaryButton(bar, text='关闭', width=0, style='Compact.TButton',
                        command=self.hide_find_bar).pack(side='left')

    def show_find_bar(self):
        if not self.find_bar.winfo_manager():
            self.find_bar.pack(side='top', fill='x', pady=(SPACING['none'], SPACING['xs']),
                               before=self.body)
        self.find_entry.focus_set()
        self._refresh_find_matches()

    def hide_find_bar(self):
        if self.find_bar.winfo_manager():
            self.find_bar.pack_forget()
        self.viewer.tag_remove('s03_find', '1.0', 'end')
        self.viewer.tag_remove('s03_find_all', '1.0', 'end')
        self.find_count.configure(text='')
        self.viewer.focus_set()

    def _find_query(self):
        try:
            return str(self.find_entry.get() or '').strip()
        except tk.TclError:
            return ''

    def _refresh_find_matches(self):
        self.viewer.tag_remove('s03_find', '1.0', 'end')
        self.viewer.tag_remove('s03_find_all', '1.0', 'end')
        self._find_matches = []
        self._find_index = -1
        needle = self._find_query()
        if not needle:
            self.find_count.configure(text='')
            return
        self.viewer.tag_configure('s03_find_all', background=COLORS['selection_bg'])
        self.viewer.tag_configure('s03_find', background=COLORS['primary_subtle'],
                                  foreground=COLORS['selection_text'])
        pos = '1.0'
        while True:
            start = self.viewer.search(needle, pos, stopindex='end', nocase=True)
            if not start:
                break
            end = '%s + %d chars' % (start, len(needle))
            self._find_matches.append((start, end))
            self.viewer.tag_add('s03_find_all', start, end)
            pos = end
        if not self._find_matches:
            self.find_count.configure(text='无匹配')
            return
        self._select_find(0)

    def _select_find(self, index):
        if not self._find_matches:
            return
        self._find_index = index % len(self._find_matches)
        start, end = self._find_matches[self._find_index]
        self.viewer.tag_remove('s03_find', '1.0', 'end')
        self.viewer.tag_add('s03_find', start, end)
        self.viewer.see(start)
        self.find_count.configure(text='%d/%d' % (self._find_index + 1, len(self._find_matches)))

    def find_step(self, delta=1):
        if not self._find_matches:
            self._refresh_find_matches()
            if not self._find_matches:
                needle = self._find_query()
                if needle:
                    self.page.desktop.status.set('未找到「%s」' % needle)
                return
        self._select_find(self._find_index + int(delta))

    def find_next(self):
        self.find_step(1)

    def toggle_shot_nav(self, *, focus_search=False):
        if self.shot_nav.visible and not focus_search:
            self.shot_nav.hide(by_user=True)
        elif self.shot_nav.visible and focus_search:
            self.shot_nav.search_entry.focus_set()
        else:
            self.shot_nav.show(focus_search=focus_search)

    def _on_escape(self, _event=None):
        if self.find_bar.winfo_manager():
            self.hide_find_bar()
            return 'break'
        return None

    def zoom_by(self, delta):
        base = SCRIPT_VIEW_FONT[1]
        clamped = max(SCRIPT_VIEW_FONT_MIN,
                      min(SCRIPT_VIEW_FONT_MAX, base + self.zoom_delta + int(delta)))
        if clamped == base + self.zoom_delta:
            return
        self.zoom_delta = clamped - base
        scaled = font_at_size(SCRIPT_VIEW_FONT, clamped)
        self.viewer.configure(font=scaled)
        self.gutter.set_font(scaled)
        self.page.desktop.status.set('字号 %d' % clamped)

    def _bind_shortcuts(self):
        shortcuts = getattr(self.page.desktop, 'shortcuts', None)
        if shortcuts is None:
            return
        scope = '初步分镜·编辑器'
        shortcuts.bind(self.viewer, ('<Control-f>', '<Control-F>'),
                       lambda _e: (self.show_find_bar(), 'break')[1],
                       scope=scope, name='查找')
        shortcuts.bind(self.viewer, ('<Control-g>', '<Control-G>'),
                       lambda _e: (self.toggle_shot_nav(focus_search=True), 'break')[1],
                       scope=scope, name='镜头定位')
        shortcuts.bind(self.viewer, ('<Control-o>', '<Control-O>'),
                       lambda _e: (self.page.desktop.safe(self.page.open_any_document), 'break')[1],
                       scope=scope, name='打开文件')
        shortcuts.bind(self.viewer, ('<Control-s>', '<Control-S>'),
                       lambda _e: (self.page.desktop.safe(self.page.save_edited)
                                   if self.page.editing else None, 'break')[1],
                       scope=scope, name='保存')
        shortcuts.bind(self.viewer, ('<Control-equal>', '<Control-plus>',
                                     '<Control-KP_Equal>', '<Control-KP_Add>'),
                       lambda _e: (self.zoom_by(1), 'break')[1], scope=scope, name='放大')
        shortcuts.bind(self.viewer, ('<Control-minus>', '<Control-KP_Subtract>'),
                       lambda _e: (self.zoom_by(-1), 'break')[1], scope=scope, name='缩小')

    def set_text(self, text, *, editable=False):
        content = str(text or '')
        self.viewer.configure(state='normal')
        self.viewer.delete('1.0', 'end')
        self.viewer.insert('1.0', content)
        apply_storyboard_highlights(self.viewer, content)
        self.viewer.edit_reset()
        self.viewer.edit_modified(False)
        self.viewer.configure(state='normal' if editable else 'disabled')
        self.shortcut_hint.configure(text=S03_HINT_EDIT if editable else S03_HINT_READ)
        self.gutter.refresh()
        self.shot_nav.set_text(content)
        if self.find_bar.winfo_manager():
            self._refresh_find_matches()

    def popup_context_menu(self, event, *, document_dir_fn):
        page = self.page
        menu = ContextMenu(self.viewer)
        if page.editing:
            menu.command('退出编辑并保存', lambda: page.desktop.safe(page.exit_edit))
            menu.command('立即保存 (Ctrl+S)', lambda: page.desktop.safe(page.save_edited))
        elif page.active_path is not None and page.active_path.is_file():
            menu.command('编辑当前文档', lambda: page.desktop.safe(page.begin_edit))
        if page.active_path is not None and page.active_path.suffix.lower() == '.json':
            label = '切换为分镜阅读视图' if page.raw_json_mode else '切换为原始 JSON'
            menu.command(label, lambda: page.desktop.safe(page.toggle_json_view))
        if page.active_path is not None:
            menu.command('关闭当前文档', lambda: page.desktop.safe(page.close_document))
        menu.separator()
        if page.active_board_json is not None or page.catalogs.get('storyboard'):
            adopted = set(page.controller.adopted())
            if page.active_board_json is not None and page.active_board_json in adopted:
                menu.command('取消采用当前分镜', lambda: page.desktop.safe(page.remove_selected))
            else:
                menu.command('采用分镜', lambda: page.desktop.safe(page.adopt_selected))
        menu.command('导入 JSON 分镜…', lambda: page.desktop.safe(page.desktop.import_json))
        menu.command('选择其他剧本…', lambda: page.desktop.safe(page.browse))
        menu.command('重排镜头编号', lambda: page.desktop.safe(page.renumber_shots))
        menu.separator()
        nav_label = '隐藏镜头定位 (Ctrl+G)' if self.shot_nav.visible else '显示镜头定位 (Ctrl+G)'
        menu.command(nav_label, lambda: self.toggle_shot_nav(focus_search=not self.shot_nav.visible))
        menu.command('查找 (Ctrl+F)', self.show_find_bar)
        menu.command('打开其他文件… (Ctrl+O)', lambda: page.desktop.safe(page.open_any_document))
        menu.command('打开分镜目录', lambda: page.desktop.safe(
            lambda: page.desktop.open_folder(document_dir_fn(page.project))))
        menu.command('刷新分镜列表', lambda: page.desktop.safe(page.refresh))
        menu.command('恢复最近删除', lambda: page.desktop.safe(page.restore_latest))
        page.last_menu = menu
        return menu.popup(event)

    def open_any_document(self):
        page = self.page
        dialog = getattr(page.desktop, 'file_dialog', None)
        if dialog is None or not hasattr(dialog, 'open_file'):
            return
        chosen = dialog.open_file(
            parent=page.desktop.win, title='打开分镜或剧本文档',
            initialdir=str(page.project),
            filetypes=[('分镜与剧本', '*.json *.md *.txt'), ('全部文件', '*.*')])
        if chosen:
            page.show_document(chosen)


def pick_default_document(adopted, catalogs):
    """按「已采用分镜 → 最新分镜 → 首份结构剧本」顺序选出 S03 默认打开文档。"""
    boards = catalogs.get('storyboard') or ()
    for entry in boards:
        candidate = Path(entry['path']).resolve()
        if candidate in adopted and candidate.is_file():
            return candidate
    for path in sorted(adopted, key=lambda p: str(p)):
        if Path(path).is_file():
            return Path(path).resolve()
    if boards and Path(boards[0]['path']).is_file():
        return Path(boards[0]['path']).resolve()
    scripts = catalogs.get('script') or ()
    if scripts and Path(scripts[0]['path']).is_file():
        return Path(scripts[0]['path']).resolve()
    return None


def render_document_text(target, *, raw_json=False, adopted=False, read_json_fn=None, read_text_fn=None):
    """读取并格式化 S03 当前文档；JSON 默认输出分镜阅读视图，可切原始 JSON。"""
    if target is None or not Path(target).is_file():
        return S03_EMPTY_TEXT
    target = Path(target)
    try:
        if target.suffix.lower() == '.json':
            data = read_json_fn(target)
            return (json.dumps(data, ensure_ascii=False, indent=2)
                    if raw_json else format_storyboard_for_editor(target, data, adopted=adopted))
        return read_text_fn(target, encoding='utf-8-sig')
    except (OSError, UnicodeError, ValueError) as exc:
        return '文档读取失败：%s' % exc
