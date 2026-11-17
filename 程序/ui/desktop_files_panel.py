# -*- coding: utf-8 -*-
"""主界面「项目文件」全局入口与右侧停靠面板（R2962，自 ``_WritingPage`` 迁入，REQ-S01-90）。

原「剧本准备」页内 ``script_box`` 文件栏改为全局固定目录：R2998 起入口从
标题行迁到内容区右缘独立图标列（``rail``，聊天区滑块右侧、与画布同高，
图标在列顶、下方留白给后续图标功能），点击后右侧停靠面板向左展开、主内容
区收窄；默认隐藏，切页／切项目自动收起，面板外按下或 Esc 关闭。文件名列宽
按最长文件名动态调整（``script_width_sizer`` 驱动面板宽）。默认通过后台项目
索引按阶段分组；索引加载与批次渲染在 ``desktop_files_panel_index``，剧本四类
沿用采用、确认和历史操作。``self.page`` 即 ``Desktop`` 实例。
"""
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ui.desktop_files_panel_filters import (
    FilesPanelFilterMixin, STAGE_FILTER_ROW_CATEGORY,
    PANEL_META_WIDTH, PANEL_PREVIEW_COL_WIDTH,
)

from ui.desktop_file_card import TreeRowCard, script_row_card
from ui.desktop_page_registry import PAGE_ACCOUNT, PAGE_SITES
from ui.desktop_writing_snapshots import WritingSnapshotsMixin
from responsive_ui import fit_row_height, measure, row_toggle_target
from ui.ui_icons import IconLoader
from ui_tokens import ICON_CHEVRON_RIGHT, SCRIPT_FILE_FONT, SCRIPT_FILE_MAX_ROWS, SPACING
from ui_widgets import DataTable, SecondaryButton, Tooltip, ask_string
from ui.writing_page_controller import ScriptListLoadController

# R3150：入口钮左右 padding 收 0——右 padding 再收半档图标再右移半步贴边，
# 左 padding 同步收 0 使图标与左侧聊天框间距减半（实测 8px→4px，余量即按钮内边距）。

# R2998：文件名列宽不再写死——面板宽度由 0 高 sizer 驱动，按最长文件名量宽。
SCRIPT_LIST_MIN_WIDTH = SPACING['sm'] * 23      # 沿用原固定列宽下限（184）
SCRIPT_PANEL_MAX_SHARE = 0.5                     # 面板最多占内容区一半宽
SCRIPT_PANEL_MAX_WIDTH = SPACING['sm'] * 60      # 480：更长的文件名靠悬停看全
SCRIPT_CELL_OVERHEAD = SPACING['md'] * 4         # 48：格内边距＋滚动条＋面板留白
# R3196 后续（任务书 M5，REQ-S01-95/96）：预览列图元长边与列宽、时长／分辨率列宽都从 token 派生；
# 定义在 desktop_files_panel_filters（本模块自它导入），视频封面 16:9（40×22）与音频波形
# （40×13）落在字高行内，行高仍由字体 token 量。


class ProjectFilesPanel(FilesPanelFilterMixin, WritingSnapshotsMixin):
    """内容区右缘图标列「项目文件」入口＋右侧停靠文件列表；``page`` 是 ``Desktop`` 实例。"""

    def __init__(self, page):
        self.page = page
        self._open = False
        self._panel_root = None
        self._button_bind = None
        self._escape_bind = None
        self._fit_width_job = None

    def build(self):
        """建入口图标列与停靠面板；初始收起，文件列表默认隐藏（REQ-S01-90）。"""
        page = self.page
        image = IconLoader.nav_icon(page.win, 'project_files')
        # R3060：图标列挂 panel_area（panel_dock 的父级）而非画布列——面板打开时
        # 停靠列从图标列左侧让位，图标恒为内容区最右竖条。
        area = getattr(page, 'panel_area', None) or page.canvas.master
        # R2998：入口从标题行迁到内容区右缘独立图标列——先于任何停靠面板 pack，
        # 恒为该容器最右竖条（与画布同高，图标在列顶、下方留白给后续图标）。
        self.rail = ttk.Frame(area)
        self.rail.pack(side='right', fill='y')
        # Tk 空 frame 的请求宽度只增不收：常驻一个 0 尺寸占位子件，让列在
        # 按钮隐藏时塌回约 1px，而不是卡住上次的宽度。
        self.rail_sizer = tk.Frame(self.rail, width=0, height=0)
        self.rail_sizer.pack(side='bottom')
        self.button = SecondaryButton(self.rail, text='', image=image,
                                      compound='image' if image is not None else 'text',
                                      command=self.toggle, style='RailIcon.TButton')
        self._pack_button()
        Tooltip(self.button, '项目文件')
        page.files_button = self.button

        # R3060：面板停靠列独立于画布列（canvas.master 已是 stage_area），输入框与聊天框同宽收窄；
        # 停靠框/分隔线都进 panel_dock，面板宽度不再与 stage_area 竞争需求宽度。
        dock = getattr(page, 'panel_dock', None)
        area = dock or getattr(page, 'panel_area', None) or page.canvas.master
        self._dock = dock if dock is area else None
        self.script_box = ttk.Frame(area, padding=(SPACING['xs'], SPACING['xs']))
        self.sep = ttk.Separator(area, orient='vertical')
        # R3137（任务书 P1）：阶段快捷图标列在停靠面板**右缘**、按 pet_bus.STAGES 垂直排列；
        # 先于列表 pack，右缘竖条优先占整列高，列表随后吃剩余区域。
        self.stage_rail = ttk.Frame(self.script_box)
        self.stage_rail.pack(side='right', fill='y', padx=(SPACING['xs'], SPACING['none']))
        self._build_stage_rail()
        self.script_header = ttk.Frame(self.script_box)
        self.script_header.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
        self.script_title = ttk.Label(self.script_header, text='项目文件', style='Muted.TLabel')
        self.script_title.pack(side='left')
        self.script_toggle = SecondaryButton(self.script_header, text=ICON_CHEVRON_RIGHT, width=0,
                                             style='Tokens.Composer.Icon.TButton', command=self.collapse)
        self.script_toggle.pack(side='right')
        Tooltip(self.script_toggle, '收起项目文件面板')
        # R3137（任务书 P1，Q25）：筛选条（阶段／类型／状态／关键字）与阶段快捷图标列
        # 由 FilesPanelFilterMixin 提供；空条件即全项目索引分组视图。
        self._build_filter_bar()
        self.script_row_details = {}
        self.script_row_category = {}
        tips = lambda item: self.script_row_details.get(item, '')
        table = DataTable(
            self.script_box,
            columns=[('name', '文件名', SCRIPT_LIST_MIN_WIDTH),
                     ('kind', '类型', SPACING['sm'] * 9),
                     ('size', '大小', SPACING['sm'] * 10),
                     ('mtime', '修改时间', SPACING['sm'] * 21)],
            show='headings', height=1, selectmode='extended', style='Script.Treeview',
            auto_hide_scrollbars=True, empty_text='', horizontal=True)
        self.script_list = table
        self.script_tree = table.tree
        self.script_tree.heading('name', text='文件名', anchor='center')
        self.script_tree.column('name', width=SCRIPT_LIST_MIN_WIDTH,
                                minwidth=SPACING['sm'] * 12, stretch=True)
        for column in ('kind', 'size', 'mtime'):
            self.script_tree.column(column, stretch=False)
        self._apply_columns(True)
        self.script_tree.heading('#0', text='分组／预览')
        self.script_tree.column('#0', width=PANEL_PREVIEW_COL_WIDTH,
                                minwidth=PANEL_PREVIEW_COL_WIDTH, stretch=False)
        self.page.script_file_tips = TreeRowCard(self.script_tree, tips)
        self.script_list.pack(fill='both', expand=True, pady=(SPACING['none'], SPACING['xs']))
        # R2998：文件名列宽不再写死——0 高 sizer 驱动 script_box 请求宽，
        # _fit_script_width 按最长文件名量宽后 configure；列 stretch 铺满。
        # 必须关 grid 传播：Treeview 删行重填后会把 stretch 列的 reqwidth 锁成
        # 当时分配宽（delete+insert 实测 reqw=alloc 且不再回落），不关掉面板
        # 就永远缩不回来；关掉后面板宽只由 sizer 决定，列 stretch 仍管视觉铺满。
        self.script_list.grid_propagate(False)
        self.script_width_sizer = tk.Frame(self.script_box, width=SCRIPT_LIST_MIN_WIDTH, height=0)
        self.script_width_sizer.pack()
        # 状态标记放在文件名前面：列窄时被截掉的是文件名尾巴，不是[已确认]/[待确认]。
        ttk.Style(self.script_tree).configure('Script.Treeview', font=SCRIPT_FILE_FONT)
        fit_row_height(self.script_tree, style='Script.Treeview')
        # 窗口缩放改变内容区宽度上限时重算面板宽（去抖到 idle，且只在面板开着时跑）。
        area.bind('<Configure>', self._on_files_area_resize, add='+')
        self.script_loader = ScriptListLoadController(('setting', 'outline', 'character', 'script'))
        self.script_load_job = None
        self.script_box.bind('<Destroy>', self.cancel_script_load, add='+')
        self.script_tree.bind('<Double-1>', self.open_script_file)
        self.script_tree.bind('<Return>', self.open_script_file)
        self.script_tree.bind('<<TreeviewSelect>>', self.keep_one_selection, add='+')
        self.script_tree.bind('<Button-3>', lambda event, tree=self.script_tree: self.script_menu(tree, event))
        # 与原 script_box 同名挂到 Desktop：外部 getattr 消费方与既有测试定位不变。
        page.script_box = self.script_box
        page.script_tree = self.script_tree
        page.script_title = self.script_title
        page.script_toggle = self.script_toggle
        page.script_row_category = self.script_row_category
        page.refresh_script_list = self.fill_script_list
        page.open_script_file = self.open_script_file
        self.sync_entry()

    # ── 入口显隐与开合（REQ-S01-90）────────────────────────────────────────
    def _apply_columns(self, media):
        """统一保留文件属性与主线媒体元数据列，分组/预览共用#0列。"""
        tree = self.script_tree
        tree.configure(columns=('name', 'kind', 'size', 'mtime', 'meta'))
        columns = (('name', '文件名', SCRIPT_LIST_MIN_WIDTH),
                   ('kind', '类型', SPACING['sm'] * 9),
                   ('size', '大小', SPACING['sm'] * 10),
                   ('mtime', '修改时间', SPACING['sm'] * 21),
                   ('meta', '时长／分辨率', PANEL_META_WIDTH))
        for key, title, width in columns:
            tree.heading(key, text=title, anchor='center')
            tree.column(key, width=width, minwidth=width, stretch=(key == 'name'))

    def _entry_allowed(self):
        """有项目且当前页不是会员账户／参考网站时才显示入口。"""
        # build() 早于 Desktop.__init__ 给 self.root 赋值，缺属性时按无项目处理。
        if getattr(self.page, 'root', None) is None:
            return False
        return getattr(self.page, 'page_index', None) not in (PAGE_SITES, PAGE_ACCOUNT)

    def _pack_button(self):
        """图标钮挂进右侧图标列顶；已在管时不重复 pack。"""
        if self.button.winfo_manager():
            return
        self.button.pack(side='top', fill='x', padx=SPACING['none'],
                         pady=(SPACING['sm'], SPACING['xs']))

    def sync_entry(self):
        """按当前项目与页码显隐图标列里的入口钮；不满足时收起面板（列随钮塌缩）。"""
        if not self._entry_allowed():
            self.collapse()
            if self.button.winfo_manager():
                self.button.pack_forget()
            return
        if not self.button.winfo_manager():
            self._pack_button()

    def project_changed(self):
        """``_show_reset_page`` 每次换页调用：项目根变化时收起并允许下次打开重扫。"""
        root = getattr(self.page, 'root', None)
        if root == self._panel_root:
            self.sync_entry()
            if self._open:
                self.fill_script_list()
            return
        self._panel_root = root
        # R3137（任务书 P1，Q25）：换项目时阶段／类型／状态／关键字筛选全部复位。
        self._reset_filters()
        self.collapse()
        self.sync_entry()

    def _reload_current_view(self):
        """默认全部、筛选与全局库统一采用后台索引视图。"""
        self._sync_view_filters()
        if getattr(self, 'library_view', False):
            from infra import file_index
            self._fill_global_list(file_index.read_global_dir())
        else:
            self._fill_index_list()

    def toggle(self):
        if self._open:
            self.collapse()
        else:
            self.open_panel()

    def open_panel(self):
        """向左侧打开右侧停靠面板：主内容区收窄，列表立即重扫。"""
        if self._open or not self._entry_allowed():
            return
        self._open = True
        # R3060：分隔线贴停靠列左缘、文件框吃满列宽；停靠列此刻才打包进 panel_area
        # （常驻空包会让 Tk 卡住需求宽度，画布被永久挤窄）。
        if self._dock is not None:
            # 先把子件装进未映射的停靠列（需求宽度先算好），再把整列打包进 panel_area，
            # 避免空列先占位、内容装入后需求宽度在小窗下传不进来。
            self.sep.pack(side='left', fill='y')
            self.script_box.pack(side='left', fill='both', expand=True)
            if not self._dock.winfo_manager():
                self._dock.pack(side='right', fill='y')
        else:
            self.script_box.pack(side='right', fill='both', expand=True)
            self.sep.pack(side='right', fill='y')
        self._bind_outside()
        self._reload_current_view()
        fit = getattr(self.page, 'fit_content', None)
        if callable(fit):
            fit()

    def collapse(self):
        """收起停靠面板：停批次、摘监听、让出宽度并重排。"""
        if not self._open:
            return
        self._open = False
        self.cancel_script_load()
        self._unbind_outside()
        self.script_box.pack_forget()
        self.sep.pack_forget()
        # 连停靠列一起撤：只 forget 子件会让空列需求宽度卡住、画布无法收回。
        if self._dock is not None and self._dock.winfo_manager():
            self._dock.pack_forget()
        fit = getattr(self.page, 'fit_content', None)
        if callable(fit):
            fit()

    def _bind_outside(self):
        """打开期间挂面板外按下／Esc 监听（仿 ``_open_sidebar_popup`` 的 funcid 模式）。"""
        win = self.page.win
        self._button_bind = win.bind('<Button-1>', self._outside_press, add='+')
        self._escape_bind = win.bind('<Escape>', lambda event: self.collapse(), add='+')

    def _unbind_outside(self):
        win = self.page.win
        for tag, bind in (('<Button-1>', self._button_bind), ('<Escape>', self._escape_bind)):
            if bind:
                try:
                    win.unbind(tag, bind)
                except tk.TclError:
                    pass
        self._button_bind = self._escape_bind = None

    def _outside_press(self, event):
        """面板外按下左键即收起；面板内部与入口钮的点击放行。"""
        if not self._open:
            return
        node = getattr(event, 'widget', None)
        try:
            for _ in range(32):
                if node is None or node is self.page.win:
                    break
                if node is self.script_box or node is self.sep or node is self.button or node is self.rail:
                    return
                node = getattr(node, 'master', None)
        except tk.TclError:
            pass
        self.collapse()

    # ── 文件列表（自 _WritingPage 原样迁入，方法体未改）────────────────────
    def cancel_script_load(self, event=None):
        """面板销毁时撤销尚未提交的目录批次。"""
        if event is not None and getattr(event, 'widget', None) is not self.script_box:
            return None
        self.script_loader.invalidate()
        self._invalidate_index_load()
        if self.script_load_job is not None:
            try:
                self.page.win.after_cancel(self.script_load_job)
            except tk.TclError:
                pass
            self.script_load_job = None
        return None

    def fill_script_list(self):
        """刷新当前项目/素材库索引；全部视图同样后台加载。"""
        if self._open:
            self._reload_current_view()

    # ── 文件名列宽自适应（R2998）───────────────────────────────────────────
    def _script_list_font(self):
        """列表实际渲染字体：与 ``Script.Treeview`` 样式同一份 ``SCRIPT_FILE_FONT``。"""
        font = getattr(self, '_script_list_font_obj', None)
        if font is None:
            from tkinter import font as tkfont
            font = self._script_list_font_obj = tkfont.Font(root=self.script_tree, font=SCRIPT_FILE_FONT)
        return font

    def _fit_script_width(self):
        """按最长文件名量出停靠面板宽度：sizer 驱动 script_box 请求宽，列 stretch 铺满。

        上限取「内容区宽一半」与 ``SCRIPT_PANEL_MAX_WIDTH`` 的较小者，保证主内容区
        不被超长文件名挤没；更长的名字仍可经行悬停卡片看全文。
        """
        tree = getattr(self, 'script_tree', None)
        sizer = getattr(self, 'script_width_sizer', None)
        if tree is None or sizer is None or not tree.winfo_exists():
            return
        groups = tree.get_children()
        rows = tuple(groups) + tuple(item for group in groups for item in tree.get_children(group))
        widest = 0
        if rows:
            font = self._script_list_font()
            for item in rows:
                values = tree.item(item, 'values')
                if values:
                    widest = max(widest, measure(font, str(values[0])))
            needed = widest + SCRIPT_CELL_OVERHEAD
        else:
            needed = SCRIPT_LIST_MIN_WIDTH
        # 名字保留实测宽度，metadata 列超出面板时由横向滚动访问；面板本身仍按名字收窄。
        name_width = max(SCRIPT_LIST_MIN_WIDTH, widest + SPACING['lg'])
        if int(tree.column('name', 'width')) != name_width:
            tree.column('name', width=name_width)
        try:
            # R3060：script_box.master 已是自适应宽度的 panel_dock，拿它当分母会形成
            # 「面板宽→停靠列宽→上限」的循环；内容区宽度应量 panel_area（画布列同级外框）。
            host = getattr(self.page, 'panel_area', None) or self.script_box.master
            share = int(host.winfo_width() * SCRIPT_PANEL_MAX_SHARE)
        except tk.TclError:
            share = SCRIPT_PANEL_MAX_WIDTH
        cap = max(SCRIPT_LIST_MIN_WIDTH, min(share, SCRIPT_PANEL_MAX_WIDTH))
        panel_width = max(SCRIPT_LIST_MIN_WIDTH, min(needed, cap))
        if int(sizer.cget('width')) != panel_width:
            sizer.configure(width=panel_width)

    def _on_files_area_resize(self, event=None):
        """内容区宽度变化（窗口缩放）时去抖重算面板宽；只在面板开着时跑。"""
        if not self._open or self._fit_width_job is not None:
            return
        if event is not None and getattr(event, 'widget', None) is not self.script_box.master:
            return
        try:
            self._fit_width_job = self.page.win.after_idle(self._fit_script_width_debounced)
        except tk.TclError:
            self._fit_width_job = None

    def _fit_script_width_debounced(self):
        self._fit_width_job = None
        self._fit_script_width()

    def all_script_items(self):
        """返回文件叶子，不把阶段/类型/日期组当成可操作文件。"""
        if hasattr(self, '_index_rows'):
            return [item for item in self._index_rows if self.script_tree.exists(item)]
        return list(self.script_tree.get_children())

    def current_script_tree(self):
        return self.script_tree if self.script_tree.selection() else None

    def keep_one_selection(self, _tree=None):
        """单条「项目文件」列表共用一个「当前行」；多选由 Treeview 自身维持。"""
        return None

    def open_script_file(self, event=None):
        # 表头（分类名）与列宽分隔线也在 Treeview 的 <Double-1> 范围内；
        # 此时 selection() 仍保留着上次高亮的行，不能直接拿它打开文件。
        # 鼠标双击只认落点所在的行；键盘 Enter 仍打开当前高亮行。
        event_type = getattr(getattr(event, 'type', None), 'name', getattr(event, 'type', None))
        if event_type == 'ButtonPress':
            tree = event.widget
            if not isinstance(tree, ttk.Treeview):
                return
            row = row_toggle_target(tree, event.x, event.y)
        else:
            tree = self.current_script_tree()
            selected = tree.selection() if tree else ()
            row = selected[0] if selected else ''
        if not row or self.is_file_group(row):
            return
        if row.startswith('library:'):
            from infra import file_index
            library = file_index.read_global_dir()
            if library is None:
                raise ValueError('尚未设置全局素材库目录')
            path = (Path(library) / row.split(':', 1)[1]).resolve()
            if not path.is_relative_to(Path(library).resolve()):
                raise ValueError('素材路径超出全局素材库')
        else:
            path = Path(row)
            if not path.is_absolute():
                # R3137：阶段筛选视图的行是项目相对 posix 路径；无项目（测试替身）时按原样处理。
                root = getattr(self.page, 'root', None)
                if root is not None:
                    path = Path(root) / path
        if path is not None and path.is_file():
            self.page.writing_page_services.open_path(path)

    def selected_script(self):
        tree = self.current_script_tree()
        selected = tree.selection() if tree else ()
        if not selected:
            raise ValueError('请先选择剧本文件')
        from domain.script_workspace_service import selected_script_paths
        item = selected[0]
        path = self.index_file_path(item) if item in getattr(self, '_index_rows', {}) else item
        return selected_script_paths(self.page.root, [path])[0]

    def selected_scripts(self):
        """当前表里选中的各行（Ctrl／Shift 多选），并标出是否选中了列表里的全部文件。"""
        tree = self.current_script_tree()
        from domain.script_workspace_service import script_deletion_selection
        return script_deletion_selection(self.page.root, self.all_script_items(), tree.selection() if tree else ())

    def rename_script(self):
        path = self.selected_script()
        new = ask_string(self.page.win, '重命名文件', '新文件名：', initialvalue=path.name)
        if not new:
            return
        from domain.script_workspace_service import rename_script_document
        result = rename_script_document(self.page.root, path, new)
        if not result.ok:
            raise ValueError(result.reason)
        dest = result.data
        if dest == path:
            return
        self.fill_script_list()
        self.page.status.set('已重命名：' + dest.name)

    def confirmed_note(self, paths):
        # 删掉已确认阶段文件会让剧本准备的确认失效，删前点明。
        import writing_api
        confirmed = writing_api.confirmed_preparation_files(self.page.root)
        hits = [confirmed[p.resolve()] + '：' + p.name for p in paths if p.resolve() in confirmed]
        if not hits:
            return ''
        return '\n\n注意：以下是剧本准备已确认的阶段文件，删除后该阶段确认失效，需要恢复或重新确认才能继续：\n' + '\n'.join(hits)

    def delete_script(self):
        """删除仅作用于选中文件，列表全选绝不升级为删除整个项目。"""
        if getattr(self, '_index_rows', None) is not None:
            return self.delete_index_files()
        selection = self.selected_scripts()
        paths = list(selection.paths)
        one = len(paths) == 1
        if one:
            prompt = f'确定将 {paths[0].name} 移入项目回收站吗？\n\n可在对应页面恢复最近删除。' + self.confirmed_note(paths)
        else:
            names = '\n'.join(path.name for path in paths)
            prompt = '确定将选中的 ' + str(len(paths)) + ' 份剧本文件移入项目回收站吗？\n\n' + names + '\n\n可在对应页面恢复最近删除。' + self.confirmed_note(paths)
        if not self.page.writing_page_services.confirm(self.page.win, '移入回收站', prompt, dangerous=True):
            return
        from infra.storage_maintenance import recycle_paths
        recycled = recycle_paths(self.page.root, paths, '删除项目剧本' if one else '批量删除项目剧本')
        self.fill_script_list()                  # 部分成功时已进回收站的那些也要从列表消失：先刷新再报错
        if len(recycled) != len(paths):
            raise OSError('文件未能移入回收站，请刷新后重试' if one else '部分文件未能移入回收站，请刷新后重试')
        self.page.status.set('已移入回收站：' + paths[0].name if one else '已移入回收站 ' + str(len(paths)) + ' 份剧本文件')

    def adopt_script(self):
        from stage_execution_service import adopt_natural_script
        adopted = adopt_natural_script(self.page.root, self.selected_script())
        self.fill_script_list()
        self.page.status.set('已采用自然剧本：' + adopted.name + '；后续结构化使用此版本')

    def unconfirm_preparation(self, stage):
        """右键「取消已确认」：取消该阶段确认并把准备流程回退到该阶段；只改台账、不删文件。"""
        from writing_api import PREPARATION_STAGES
        from orchestrator.writing_unconfirm import preparation_confirmed_stages
        confirmed = preparation_confirmed_stages(self.page.root)
        if stage not in confirmed:
            return
        index = PREPARATION_STAGES.index(stage)
        downstream = tuple(s for s in confirmed if PREPARATION_STAGES.index(s) > index)
        prompt = ('确定取消「' + stage + '」的确认吗？\n\n'
                  '取消后剧本准备流程回到「' + stage + '」，您需要重新确认该阶段。')
        if downstream:
            prompt += '\n\n已确认的「' + '」「'.join(downstream) + '」会一并取消。'
        prompt += '\n\n不会删除或覆盖任何文件，原稿保留。'
        if not self.page.writing_page_services.confirm(self.page.win, '取消已确认', prompt):
            return
        from stage_execution_service import unconfirm_writing_preparation
        invalidated = unconfirm_writing_preparation(self.page.root, stage)
        self.fill_script_list()
        note = ('，「' + '」「'.join(invalidated) + '」的确认一并取消' if invalidated else '')
        self.page.status.set('已取消「' + stage + '」的确认' + note + '，当前回到「' + stage + '」')

    def confirm_document(self, stage):
        """把用户改过的当前文件设为该阶段定稿；之后各阶段的定稿会失效。"""
        path = self.selected_script()
        from stage_execution_service import confirm_writing_preparation
        if not self.page.writing_page_services.confirm(self.page.win, '设为' + stage + '定稿',
                                                      '把这份文件设为「' + stage + '」的定稿？\n\n' + path.name +
                                                      '\n\n以文件当前内容为准；「' + stage + '」之后已定稿的阶段需要重新确认。'):
            return
        invalidated = confirm_writing_preparation(self.page.root, stage, path)
        self.fill_script_list()
        self.page.status.set('已把' + path.name + '设为「' + stage + '」定稿' +
                             ('；「' + '」「'.join(invalidated) + '」需要重新确认' if invalidated else ''))

    def script_menu(self, tree, event):
        row = tree.identify_row(event.y)
        if not row or self.is_file_group(row):
            return
        # 右键落在已选中的行上时保留 Ctrl／Shift 多选；落在别的行上改选这一行。
        if row not in tree.selection():
            tree.selection_set(row)
        self.keep_one_selection(tree)
        menu = self.page.writing_page_services.context_menu(self.page.win)
        # 普通索引行与剧本四类动作分开；项目文件删除统一走回收服务。
        if self.script_row_category.get(row) == STAGE_FILTER_ROW_CATEGORY:
            menu.command('打开', lambda: self.page.safe(self.open_script_file))
            # R3165（任务书 P3）：全局素材库视图的行可「引用到当前项目」。
            if str(row).startswith('library:'):
                menu.command('引用到当前项目',
                             lambda: self.page.safe(lambda: self.reference_from_library(row)))
            else:
                if len(tree.selection()) == 1:
                    menu.command('重命名', lambda: self.page.safe(lambda: self.rename_index_file(row)))
                menu.command('添加到全局素材库', lambda: self.page.safe(lambda: self.add_to_library(row)))
                menu.command('删除', lambda: self.page.safe(self.delete_index_files))
            menu.command('在文件夹中显示', lambda: self.page.safe(self.show_in_folder))
            menu.command('另存为…', lambda: self.page.safe(self.save_as_file))
            return menu.popup(event)
        if len(tree.selection()) > 1:
            # 多选时只给「删除」：查看、改名、定稿都只针对一份文件。
            menu.command('删除', lambda: self.page.safe(self.delete_script))
            return menu.popup(event)
        # 第 46 期第 1 条：内容框的右键一律是「查看／…／删除」这一套，剧本表原来只有改名与删除。
        menu.command('查看', lambda: self.page.safe(self.open_script_file))
        menu.command('添加到全局素材库', lambda: self.page.safe(lambda: self.add_to_library(row)))
        menu.command('重命名', lambda: self.page.safe(self.rename_script))
        category = self.script_row_category.get(row, 'script')
        if category == 'script':
            menu.command('采用此剧本', lambda: self.page.safe(self.adopt_script))
        else:
            stages = {'setting': '项目设定', 'outline': '剧本大纲', 'character': '角色卡'}
            stage = stages[category]
            from orchestrator.writing_unconfirm import preparation_confirmed_stages
            if stage in preparation_confirmed_stages(self.page.root):
                menu.command('取消已确认', lambda: self.page.safe(lambda: self.unconfirm_preparation(stage)))
            menu.command('设为' + stage + '定稿', lambda: self.page.safe(lambda: self.confirm_document(stage)))
            menu.command('按段落采用…', lambda: self.page.safe(lambda: self.show_partial_adoption(stage)))
            menu.command('历史快照／对比', lambda: self.page.safe(lambda: self.show_preparation_snapshots(stage)))
        # 任务书 M5（REQ-S01-96）：剧本四类行也提供文件级「在文件夹中显示／另存为…」。
        menu.command('在文件夹中显示', lambda: self.page.safe(self.show_in_folder))
        menu.command('另存为…', lambda: self.page.safe(self.save_as_file))
        menu.command('删除', lambda: self.page.safe(self.delete_script))
        return menu.popup(event)
