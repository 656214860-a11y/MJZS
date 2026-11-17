"""Tk table adapters shared by storyboard picker pages."""
import infra.app_logging as app_logging
from datetime import datetime
from ui_tokens import COLORS
from ui_widgets import DataTable
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
        header_w=measure(heading,tree.heading(column,'text'))+14
        cells=[measure(body,row[index]) for row in rows if index < len(row)]
        content_w=(max(cells) if cells else 0)+14
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
