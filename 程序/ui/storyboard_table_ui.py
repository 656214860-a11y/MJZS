"""Tk table adapters and S03 storyboard editor view shared by storyboard pages."""
import json
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk
import infra.app_logging as app_logging
from ui_tokens import (
    COLORS, SCRIPT_VIEW_FONT, SCRIPT_VIEW_FONT_MAX, SCRIPT_VIEW_FONT_MIN,
    SCRIPT_VIEW_PADDING, SPACING,
)
from ui_widgets import ContextMenu, DataTable, LineInput, SecondaryButton, TextArea
from ui.ui_shortcuts import ShortcutRegistry

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


S03_HINT_READ = '快捷键：右键采用/编辑/导入/重排 · Ctrl+F 查找 · Ctrl+滚轮/Ctrl+± 缩放 · Ctrl+O 打开文件（右侧文件栏切换结构剧本与初步分镜）'
S03_HINT_EDIT = '编辑中：Ctrl+S 保存 · Ctrl+Z 撤销 · Ctrl+Y 重做 · Ctrl+F 查找 · 右键退出编辑'
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


class S03EditorView:
    """03 初步分镜单编辑器视图组件：正文区、底部快捷键提示条、Ctrl+F 查找条与缩放。"""

    def __init__(self, page, wheel_lines=9):
        self.page = page
        self.wheel_lines = wheel_lines
        self.zoom_delta = 0
        self._find_pos = '1.0'
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
        area = ttk.Frame(frame)
        area.pack(fill='both', expand=True)
        self.viewer = TextArea(
            area, bg=COLORS['background_card'], fg=COLORS['text_primary'], height=1,
            wrap='word', undo=True, maxundo=-1, font=SCRIPT_VIEW_FONT, relief='flat',
            padx=SCRIPT_VIEW_PADDING[0], pady=SCRIPT_VIEW_PADDING[1])
        self.viewer._wheel_lines = self.wheel_lines
        self.viewer._ctrl_wheel_zoom = self.zoom_by
        scroll = ttk.Scrollbar(area, orient='vertical', command=self.viewer.yview)
        self.viewer.configure(yscrollcommand=scroll.set)
        self.viewer.grid(row=0, column=0, sticky='nsew')
        scroll.grid(row=0, column=1, sticky='ns')
        area.columnconfigure(0, weight=1)
        area.rowconfigure(0, weight=1)
        self.viewer.bind('<Button-3>', self.page.on_context_menu, add='+')
        self.viewer.bind('<Escape>', self._on_escape, add='+')
        self._bind_shortcuts()

    def _build_find_bar(self, parent):
        bar = ttk.Frame(parent)
        self.find_bar = bar
        self.find_var = tk.StringVar(value='')
        self.find_entry = LineInput(bar, textvariable=self.find_var, width=SPACING['xl'])
        self.find_entry.pack(side='left', fill='x', expand=True, padx=(SPACING['none'], SPACING['xs']))
        self.find_entry.bind('<Return>', lambda _e: self.find_next())
        self.find_entry.bind('<Escape>', lambda _e: self.hide_find_bar())
        SecondaryButton(bar, text='下一个', width=0, style='Compact.TButton',
                        command=self.find_next).pack(side='left', padx=(SPACING['none'], SPACING['xs']))
        SecondaryButton(bar, text='关闭', width=0, style='Compact.TButton',
                        command=self.hide_find_bar).pack(side='left')

    def show_find_bar(self):
        if not self.find_bar.winfo_manager():
            self.find_bar.pack(side='top', fill='x', pady=(SPACING['none'], SPACING['xs']),
                               before=self.viewer.master)
        self.find_entry.focus_set()

    def hide_find_bar(self):
        if self.find_bar.winfo_manager():
            self.find_bar.pack_forget()
        self.viewer.tag_remove('s03_find', '1.0', 'end')
        self.viewer.focus_set()

    def find_next(self):
        needle = self.find_var.get().strip()
        if not needle:
            return
        self.viewer.tag_remove('s03_find', '1.0', 'end')
        start = self.viewer.search(needle, self._find_pos, stopindex='end', nocase=True)
        if not start:
            start = self.viewer.search(needle, '1.0', stopindex='end', nocase=True)
        if not start:
            self.page.desktop.status.set('未找到「%s」' % needle)
            return
        end = '%s + %d chars' % (start, len(needle))
        self.viewer.tag_configure('s03_find', background=COLORS['primary_subtle'],
                                  foreground=COLORS['selection_text'])
        self.viewer.tag_add('s03_find', start, end)
        self.viewer.see(start)
        self._find_pos = end

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
        self.viewer.configure(font=font_at_size(SCRIPT_VIEW_FONT, clamped))
        self.page.desktop.status.set('字号 %d' % clamped)

    def _bind_shortcuts(self):
        shortcuts = getattr(self.page.desktop, 'shortcuts', None)
        if shortcuts is None:
            return
        scope = '初步分镜·编辑器'
        shortcuts.bind(self.viewer, ('<Control-f>', '<Control-F>'),
                       lambda _e: (self.show_find_bar(), 'break')[1],
                       scope=scope, name='查找')
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
        self.viewer.configure(state='normal')
        self.viewer.delete('1.0', 'end')
        self.viewer.insert('1.0', str(text or ''))
        self.viewer.edit_reset()
        self.viewer.configure(state='normal' if editable else 'disabled')
        self.shortcut_hint.configure(text=S03_HINT_EDIT if editable else S03_HINT_READ)

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
