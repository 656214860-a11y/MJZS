"""Highlight one clickable Treeview cell without opening anything on hover.

带链接的格子：未勾选时单击先勾选本行再打开；已勾选时只打开，不取消勾选。
勾选列本身只切换勾选，不触发自动勾选。

第 46 期第 1／9 条：内容框的格子上再挂一层右键菜单——「查看」＝打开这一格
（与单击同一条路），「删除」＝只删右键点中的那一行。删除从此不再看「高亮」：
逐个删除认右键那一行，批量删除只认勾选行（各页的批量按钮），高亮不再兼作删除目标。

第 52 期第 2 条：这个菜单只在「鼠标底下这一格真能打开一个文件」时才弹——纯文字格与勾选列
都不再弹（原来右键纯文字格还能走 menu_column 兜底、或只摆一个「删除」，用户判那是误触）。
第 52 期第 3 条：外加一层 CellImages——Tk 的 value 格只能写文字，缩略图得另盖一层 Label。

第 55 期第 1 条：两层的位置都是现问 tree.bbox 要的，视图一变就得重排——watch_view 把
「滚动条动了／列宽变了／内容框改了尺寸」收成一处通知，谁也不必再自己往 xscrollcommand
末尾补一次重排（漏一处，那一层就钉在原处）。
第 55 期第 2／3 条：盖着缩略图的格子不再走高亮（原来图与高亮叠在同一格上互相顶掉，
用户判它显示不对）；盖图的格子也不再写字——文字由盖图这一层在盖上的时候收走、
撤掉的时候写回，页面不必为了「这一格要不要写字」去解每一张图。
第 60 期第 3 条：单击（点亮这一行）不打开；第 64 期任务 12 起改成**双击打开**——
要看这一格的文件双击缩略图，或者走右键菜单里的「查看」。
"""
import inspect
import tkinter as tk
from tkinter import ttk

ROW_MENU_VIEW = '查看'          # 右键菜单第一项：等同单击这一格
ROW_MENU_DELETE = '删除'        # 右键菜单第二项：逐个删除（目标就是右键那一行）
ZOOM_SIZE = 480                 # 缩略图悬停放大后的长边（第 57 期第 5 条）：看清人物与背景
# 第 59 期第 1 条：用户嫌放大图还是小，长边从 240 提到 480（再放大一倍）。
# 第 64 期任务 12：用户还是要更大，480 → 960（再放大一倍）；各页的 zoom= 都取这一个常量。
# 第 67 期任务 3：用户嫌太大了，960 → 480——回到第 64 期之前那一挡（缩小一倍）。
ZOOM_GAP = 12                   # 放大图离那一格、离窗口边留多少像素
ZOOM_HIDE_MS = 90               # 鼠标离开后隔这么久再看一眼指针在不在放大图上
ZOOM_WATCH_MS = 250             # 第 60 期第 5 条：放大图在的时候，隔这么久自己再看一眼指针
# 第 58 期第 3 条：放大图紧贴鼠标右上角——离指针只留这么一点，离窗口边还是 ZOOM_GAP。
ZOOM_NEAR = 6


def _chain_scroll(command, notify):
    """把「滚动条动了」接在原来那份 xscrollcommand／yscrollcommand 后面。"""
    if command in (None, '') or getattr(command, '_view_chained', False):
        return command

    def chained(first, last):
        result = command(first, last) if callable(command) else None
        notify()
        return result

    chained._view_chained = True
    return chained


def _tcl_command(tree, name, notify):
    """设钩子以前就装在树上的那份滚动回调：Tcl 命令名读得回来，照样接上通知。"""

    def chained(first, last):
        try:
            tree.tk.call(name, first, last)
        finally:
            notify()
        return None

    chained._view_chained = True
    return chained


def _notify_view(tree):
    """同一帧里来多少次都只跑一遍（after_idle 收口）。"""
    if getattr(tree, '_view_pending', False):
        return
    tree._view_pending = True

    def run():
        tree._view_pending = False
        try:
            alive = bool(tree.winfo_exists())
        except Exception:
            alive = False
        if not alive:
            return
        for callback in list(getattr(tree, '_view_watchers', ())):
            try:
                callback()
            except Exception:
                pass

    try:
        tree._view_pending_id = tree.after_idle(run)
    except Exception:
        tree._view_pending = False


def _install_view_hooks(tree):
    """把三条「视图变了」的来源都接到 _notify_view 上（只装一次）。"""
    notify = lambda: _notify_view(tree)
    original_configure = tree.configure

    def configure(cnf=None, **kw):
        for key in ('xscrollcommand', 'yscrollcommand'):
            if key in kw:
                kw[key] = _chain_scroll(kw[key], notify)
        if isinstance(cnf, dict):
            cnf = dict(cnf)
            for key in ('xscrollcommand', 'yscrollcommand'):
                if key in cnf:
                    cnf[key] = _chain_scroll(cnf[key], notify)
        return original_configure(cnf, **kw)

    original_column = tree.column

    def column(column=None, option=None, **kw):
        resized = 'width' in kw
        before = original_column(column, 'width') if resized else None
        result = original_column(column, option, **kw)
        if resized:
            try:
                after = original_column(column, 'width')
            except Exception:
                after = None
            if str(before) != str(after):
                notify()
        return result

    # 第 57 期第 4 条：用鼠标拖表头那条分隔线改列宽，走的是 ttk 内部的 Tcl，既不经过
    # tree.column()、也不改内容框尺寸，前三条来源一个都不响——用户看到的就是「列宽变了、
    # 缩略图还按老宽度摆着，滑一下才跟上」。这里按「分隔线上的按下—拖动—松开」自己通知。
    def separator_press(event):
        try:
            if tree.identify_region(event.x, event.y) == 'separator':
                tree._view_resizing = True
        except Exception:
            tree._view_resizing = False

    def separator_drag(event=None):
        if getattr(tree, '_view_resizing', False):
            notify()

    def separator_release(event=None):
        if getattr(tree, '_view_resizing', False):
            tree._view_resizing = False
            notify()

    tree.configure = configure
    tree.column = column
    tree.bind('<Button-1>', separator_press, add='+')
    tree.bind('<B1-Motion>', separator_drag, add='+')
    tree.bind('<ButtonRelease-1>', separator_release, add='+')
    tree.bind('<Configure>', lambda event: notify(), add='+')
    tree.bind('<Destroy>', _drop_view_hooks, add='+')
    # 装钩子以前就已经在树上的那两份滚动回调，一并接上（命令名读得回来）。
    for key in ('xscrollcommand', 'yscrollcommand'):
        try:
            name = str(tree.cget(key) or '')
        except Exception:
            name = ''
        if name:
            tree.configure(**{key: _tcl_command(tree, name, notify)})
    return tree


def _drop_view_hooks(event=None):
    tree = getattr(event, 'widget', None)
    if tree is None:
        return
    pending = getattr(tree, '_view_pending_id', None)
    if pending is not None:
        try:
            tree.after_cancel(pending)
        except Exception:
            pass
        tree._view_pending_id = None
    tree._view_pending = False
    tree._view_resizing = False
    tree._view_watchers = []


def watch_view(tree, callback):
    """登记一个「这张内容框的视图变了」的回调（第 55 期第 1 条）。

    视图变了＝滚动条一动、列宽一变、内容框改尺寸（缩放窗口／换页）。缩略图与悬停高亮
    那两层都盖在格子上、位置全靠 tree.bbox 现问，漏一次重排就「格子走了、那一层还在原处」。
    这里统一通知，去抖到 after_idle：同一帧里来多少次都只跑一遍。
    """
    if not hasattr(tree, '_view_watchers'):
        tree._view_watchers = []
        tree._view_pending = False
        tree._view_pending_id = None
        _install_view_hooks(tree)
    tree._view_watchers.append(callback)
    return callback


def wants_column(callback):
    """这个回调要不要第二个人参（「哪一列」）：delete(row) 与 delete(row, column) 都收。

    第 57 期第 3 条：资产页「参考图」那一格删的是这一格的参考图，别处删的还是这一行的那张图——
    同一份右键菜单得把「右键落在哪一列」交给回调，而老写法（一个人参）照旧不动。
    """
    try:
        parameters = list(inspect.signature(callback).parameters.values())
    except (TypeError, ValueError):
        return False
    if any(item.kind == item.VAR_POSITIONAL for item in parameters):
        return True
    return len([item for item in parameters
                if item.kind in (item.POSITIONAL_ONLY, item.POSITIONAL_OR_KEYWORD)]) >= 2


def call_delete(delete, row, column):
    """按回调自己的签名把「那一列」传下去。"""
    return delete(row, column) if wants_column(delete) else delete(row)


def popup_row_menu(tree, row, column, view=None, delete=None, x=None, y=None):
    """弹一次「查看／删除」：view(row, column) 与 delete 拿到的都是右键那一格那一行。

    column 给 None＝这一格没有「查看」（比如勾选列）。两项都摆不出来就不弹，返回 None。
    delete 收一个人参＝delete(row)，收两个人参＝delete(row, column)。
    """
    menu = tk.Menu(tree, tearoff=False)
    if view is not None and column is not None:
        menu.add_command(label=ROW_MENU_VIEW, command=lambda: view(row, column))
    if delete is not None:
        menu.add_command(label=ROW_MENU_DELETE, command=lambda: call_delete(delete, row, column))
    if menu.index('end') is None:
        return None
    try:
        menu.tk_popup(int(x if x is not None else tree.winfo_pointerx()),
                      int(y if y is not None else tree.winfo_pointery()))
    finally:
        menu.grab_release()
    return menu


def bind_row_menu(tree, view=None, delete=None, columns=None, checkbox_column='#0'):
    """给内容框装右键菜单（第 46 期第 1 条）：columns 给 None 就认所有格。

    只认格子上（表头、列宽拖动条上不弹），并把右键那一行交给调用方——调用方因此不必
    去猜「用户到底想删高亮那行还是勾选那行」。

    第 52 期第 2 条：勾选列不弹（那一格没有可打开的文件）；columns 给了就只认这几列。
    """
    allowed = None if columns is None else {str(item) for item in columns}

    def handler(event):
        if tree.identify_region(event.x, event.y) not in ('cell', 'tree'):
            return None
        row = tree.identify_row(event.y)
        if not row:
            return None
        column = tree.identify_column(event.x)
        if column == checkbox_column:
            return None
        if allowed is not None and column not in allowed:
            return None
        popup_row_menu(tree, row, column, view, delete, event.x_root, event.y_root)
        return 'break'

    tree.bind('<Button-3>', handler, add='+')
    tree.row_menu = handler
    return handler

class CellHover:
    def __init__(self, tree, columns, command, cell_image=None, hover_only=False, checked=None, toggle=None, checkbox_column='#0', delete=None, forward=None, plain_columns=()):
        self.tree=tree;self.columns=set(columns);self.command=command;self.cell_image=cell_image;self.hover_only=hover_only
        self.checked=checked;self.toggle=toggle;self.checkbox_column=checkbox_column
        # 第 55 期第 2 条：这几列盖着缩略图，不再走高亮（原来是两层叠在同一格上互相顶掉，
        # 用户看到的就是「高亮和缩略图打架、显示不对」）。CellImages 建层时会自己来登记。
        self.plain=set(plain_columns)
        # 第 46 期第 1 条：delete 给了就在这些格子上挂右键菜单（查看／删除）。
        # 第 52 期第 2 条：菜单只在这些带链接的格子上弹——原来那个 menu_column 兜底删掉了
        # （用户要的是「鼠标底下有可查看的文件才弹」）。
        self.delete=delete
        self.active=None;self.pending=None;self.editor=None
        font=ttk.Style(tree).lookup(tree.cget('style') or 'Treeview','font') or 'TkDefaultFont'
        self.overlay=tk.Label(tree,bg='#deebfa',fg='#173d72',font=font,anchor='w',padx=3,
                              borderwidth=0,highlightbackground='#80a5d4',highlightthickness=1,cursor='hand2')
        for widget in (tree,self.overlay):
            widget.bind('<Motion>',self.motion,add='+')
            widget.bind('<Leave>',self.leave,add='+')
            if not hover_only:
                widget.bind('<Button-1>',self.click,add='+')
            widget.bind('<MouseWheel>',self.clear,add='+')
        tree.bind('<Configure>',self.clear,add='+')
        tree.bind('<Destroy>',self.destroy,add='+')
        # 第 55 期第 1 条：滚动条一动、列宽一变，格子就挪了位——高亮那一层别停在原处。
        watch_view(tree,self.clear)
        # 第 46 期第 1 条：挂上右键菜单；funcid 留着，树拆掉时按 id 精确解绑。
        self.bind_id=None;self.overlay_bind_id=None
        if delete is not None:
            self.bind_id=tree.bind('<Button-3>',self.menu,add='+')
            # 鼠标停在哪一格，那一格上就盖着这层 Label——右键先落到它身上，
            # 只绑树的话「先看一眼再右键」正好点不出菜单。
            self.overlay_bind_id=self.overlay.bind('<Button-3>',self.menu,add='+')
        # 第 53 期第 1／2 条：只高亮（hover_only）时这一层把格子整个盖住了，单击与右键
        # 就落不到树上——forward(event) 由调用方给（把这一下重发给树），树上的原行为
        # 一条不动。只绑这一层：绑到树上会把事件再发一次、绕回自己。
        self.forward_bind_ids=()
        if forward is not None:
            self.forward_bind_ids=(self.overlay.bind('<Button-1>',forward,add='+'),
                                   self.overlay.bind('<Button-3>',forward,add='+'))
    def clear(self,event=None):
        self.active=None;self.overlay.place_forget();self.tree.configure(cursor='')
    def at(self,x,y):
        tree=self.tree
        if self.editor is not None:return
        if x<0 or y<0 or x>=tree.winfo_width() or y>=tree.winfo_height():self.clear();return
        row=tree.identify_row(y);col=tree.identify_column(x)
        if not row or col not in self.columns or col in self.plain or tree.identify_region(x,y) not in ('cell','tree'):
            self.clear();return
        bounds=tree.bbox(row,col)
        if not bounds:self.clear();return
        if self.active==(row,col):return
        # Hide the old cell before changing text or geometry.
        self.overlay.place_forget()
        self.active=(row,col)
        value=tree.item(row,'text') if col=='#0' else tree.item(row,'values')[int(col[1:])-1]
        image=self.cell_image(row,col) if self.cell_image else None
        if image is not None and not str(value):
            self.overlay.configure(text='',image=image,compound='none',anchor='center',padx=0)
        else:
            self.overlay.configure(text=str(value),image=image if image is not None else '',compound='left' if image is not None else 'none',anchor='w',padx=3)
        self.tree.configure(cursor='hand2')
        self.overlay.place(x=bounds[0],y=bounds[1],width=bounds[2],height=bounds[3])
        self.overlay.lift()
    def motion(self,event):
        self.at(event.x_root-self.tree.winfo_rootx(),event.y_root-self.tree.winfo_rooty())
    def leave(self,event=None):
        # Entering the cell overlay emits Leave on Treeview. Re-check the
        # pointer after Tk finishes that transition instead of hiding it.
        if self.pending is None:self.pending=self.tree.after_idle(self.recheck)
    def recheck(self):
        self.pending=None
        if self.tree.winfo_exists():
            self.at(self.tree.winfo_pointerx()-self.tree.winfo_rootx(),self.tree.winfo_pointery()-self.tree.winfo_rooty())
    def click(self,event):
        self.motion(event)
        target=self.active
        if target:return self.open(*target)
    def open(self,row,column):
        """打开这一格：先补勾选再走 command（第 55 期第 2 条，单击缩略图那一层走同一条路）。

        与 click() 的区别只有一个——它不经过「先悬停高亮」：盖着缩略图的格子本来就不亮，
        鼠标也不在树身上，高亮那一层收不到 Motion。
        """
        self.clear()
        if not row or not self.tree.exists(row):return None
        self.tree.selection_set(row);self.tree.focus(row)
        if self.should_check(row,column):self.toggle(row)
        self.command(row,column)
        return 'break'
    def cover(self,*columns):
        """这几列归盖图那一层了：不再走高亮（第 55 期第 2 条）。"""
        self.plain.update(str(item) for item in columns)
        if self.active is not None and self.active[1] in self.plain:self.clear()
        return self.plain
    def menu(self,event):
        """第 46 期第 1 条：右键＝查看（这一格）／删除（这一行）。

        第 52 期第 2 条：整张菜单只在这些带链接的格子上弹——勾选列与纯文字格一个都不弹，
        「删除」的目标永远是右键那一行。
        """
        # 事件可能来自树上，也可能来自盖在高亮格上的那层 Label；一律换算成树的坐标。
        x=event.x_root-self.tree.winfo_rootx();y=event.y_root-self.tree.winfo_rooty()
        if self.tree.identify_region(x,y) not in ('cell','tree'):return None
        row=self.tree.identify_row(y)
        if not row:return None
        column=self.tree.identify_column(x)
        # 第 52 期第 2 条：只有鼠标底下这一格真能打开文件才弹；勾选列与纯文字格都不弹。
        if column==self.checkbox_column or column not in self.columns:return None
        popup_row_menu(self.tree,row,column,self.command,self.delete,event.x_root,event.y_root)
        return 'break'

    def should_check(self,row,column):
        """带链接的格子是否需要先补勾选：勾选列与已勾选的行都不补。"""
        if self.toggle is None or self.checked is None or column==self.checkbox_column:return False
        return not self.checked(row)
    def destroy(self,event):
        if event.widget is self.tree and self.pending is not None:
            self.tree.after_cancel(self.pending);self.pending=None

    def edit_name(self,row,value,save,on_error,column='#1'):
        self.clear()
        if self.editor is not None:return
        bounds=self.tree.bbox(row,column)
        if not bounds:return
        entry=ttk.Entry(self.tree);self.editor=entry
        entry.insert(0,value);entry.place(x=bounds[0],y=bounds[1],width=bounds[2],height=bounds[3])
        # 第 52 期第 3 条：改名这一格上可能盖着一张缩略图，输入框得提到最上面才看得见。
        entry.lift()
        entry.focus_set();entry.selection_range(0,'end')
        done=[False]
        def close():
            done[0]=True;self.editor=None;entry.destroy()
        def commit(event=None):
            if done[0]:return 'break'
            name=entry.get().strip()
            if not name:
                on_error('名称不能为空，已保留原名称')
                if event is not None and event.type==tk.EventType.FocusOut:close()
                return 'break'
            if name!=value:
                try:save(name)
                except Exception as exc:
                    on_error(str(exc))
                    if event is not None and event.type==tk.EventType.FocusOut:close()
                    return 'break'
            close();return 'break'
        def cancel(event=None):
            if not done[0]:close()
            return 'break'
        entry.bind('<Return>',commit);entry.bind('<FocusOut>',commit);entry.bind('<Escape>',cancel)
        entry.commit_edit=commit;entry.cancel_edit=cancel


class CellImages:
    """在内容框的某几列上盖一层图片（第 52 期第 3 条）。

    ttk.Treeview 只有 #0 那一格能摆图，其余格子只能写文字——所以缩略图得另盖一层 Label。
    位置全是现问 tree.bbox 要的，视图一变（滚动条一动、列宽一变、内容框改尺寸）就得重排：
    这一层挂进 watch_view，调用方不必再往 xscrollcommand 末尾补一次 refresh——漏一处，
    格子向左走了、缩略图还钉在原处。

    盖住的那一格鼠标就落不到树上了，第 55 期第 2 条起改成：
    · 不再走高亮：那一格上只挂一样东西（图）。原来两层叠在同一格上互相顶掉，用户看到的
      就是「高亮和缩略图打架、显示不对」；
    · 单击不打开（第 60 期第 3 条），双击打开（第 64 期任务 12）：单击那一下常被当成
      「先点亮这一行」，看着像点了没反应，所以只认双击；右键菜单里的「查看」照旧是同一条路；
    · 右键照旧转给 CellHover——「查看／删除」那一份菜单没变（放大图上右键也认这一格）。

    第 55 期第 3 条：盖上的那一格也不再写字——文字由这一层收着（盖上时读走并清空，撤掉时
    写回）。页面因此不必为了「这一格要不要写字」去解每一张图：那是整页卡顿的来源（100 项
    资产＝100 张图全解一遍，其中绝大多数根本不在可视区）。

    第 57 期第 5 条：缩略图多了「鼠标停上去就放大」——zoom(row, column) 给一张放大图就生效。
    放大图另起一个 Label，挂在**顶层窗口**下（挂在内容框里会被它裁掉）；鼠标离开那一格先等
    一小会儿再看一眼指针在不在放大图上，压在图上就算还在看。

    第 58 期第 3 条：这张放大图**紧贴鼠标的右上角**——底边压着指针、往右上铺开（见 zoom_spot）。
    原来它按「格子的右边、竖直居中」摆，而 place 用的是顶层窗口的坐标、格子象限却是内容框自己的，
    内容框一旦不在窗口角上（几页的内容框都不是），那一份坐标就整块偏出去。
    """

    def __init__(self, tree, columns, provider, hover=None, background='#ffffff', forward=None, plain=None,
                 zoom=None):
        self.tree = tree
        self.columns = tuple(columns)
        self.provider = provider                 # (row, column) → (image, text) 或 None
        self.hover = hover                       # 盖住那格的悬停／右键转给它
        self.forward = forward                   # 第 53 期第 1／5 条：盖住那格的单击／右键重发给树
        # 第 55 期第 2 条：这几列归图这一层，不再走高亮。默认就是转交那份 CellHover；只借高亮
        # 那一条关系、不借它的交互时（07 线上生成那一页就是）用 plain 单独指一份。
        self.plain = hover if plain is None else plain
        self.background = background             # 底色：一个颜色，或者 background(row)
        self.labels = {}
        self.texts = {}                          # 盖上图的那几格原来写了什么（撤掉时写回去）
        self.zoom = zoom                         # 第 57 期第 5 条：(row, column) → 放大后的图，None＝不放大
        self.zoom_label = None
        self.zoom_key = None
        self.zoom_pending = None
        self.zoom_watch = None                   # 第 60 期第 5 条：盯着指针的那个定时器
        self.zoom_at = None                      # 上一次看到的指针（没动过就不必再判一遍）
        # `after` 归整套 Tcl 解释器管理。根窗口直接销毁时，子 Treeview 的 <Destroy>
        # 绑定可能已来不及撤掉 Python 命令；同时监听顶层窗口，先于子控件销毁取消它。
        self._zoom_owner = tree.winfo_toplevel()
        if self.plain is not None:
            self.plain.cover(*self.columns)
        watch_view(tree, self.refresh)           # 第 55 期第 1 条：视图一变就跟着重排
        tree.bind('<Destroy>', self.destroy, add='+')
        # 顶层销毁时 Tk 会先依次销毁它的子控件；不把 event 原样转发，确保
        # 放大图 Label 先收到销毁事件时也能立即撤掉悬挂的 watcher。
        self._zoom_owner.bind('<Destroy>', lambda event: self.destroy(), add='+')

    # ── 格子里的文字（第 55 期第 3 条）：盖上收走、撤掉写回 ─────────────────
    def text_at(self, row, column):
        """这一格现在写的是什么（行已经没了就返回空串）。"""
        try:
            return str(self.tree.item(row, 'text') if column == '#0' else self.tree.set(row, column))
        except Exception:
            return ''

    def write(self, row, column, text):
        try:
            if column == '#0':
                self.tree.item(row, text=text)
            else:
                self.tree.set(row, column, text)
            return True
        except Exception:
            return False                         # 行已被删除（换页、刷新列表）

    def blank(self, row, column):
        """这一格盖上了图：把原来的文字收好、格子清空。"""
        key = (row, column)
        current = self.text_at(row, column)
        if key not in self.texts or current:
            self.texts[key] = current            # 行重建会写上新文字，以新的为准
        if current:
            self.write(row, column, '')

    def restore(self, key):
        """这一格不再盖图：把收着的文字写回去。

        只在格子还空着的时候写——页面重建行、改了状态之后，格子里已经写上了新文字，
        这时候把旧的写回去就成了「状态回退」，那比空着还糟。
        """
        text = self.texts.pop(key, None)
        if not text:
            return
        if self.text_at(key[0], key[1]):
            return
        self.write(key[0], key[1], text)

    # ── 悬停放大（第 57 期第 5 条）────────────────────────────────────────
    def zoom_hide(self):
        """收起放大图：鼠标一走、一滚、这一层一重排就收。"""
        if self.zoom_pending is not None:
            try:
                self._zoom_owner.after_cancel(self.zoom_pending)
            except Exception:
                pass
            self.zoom_pending = None
        self.zoom_cancel_watch()
        self.zoom_key = None
        self.zoom_at = None
        if self.zoom_label is not None:
            try:
                self.zoom_label.place_forget()
            except Exception:
                pass
        return None

    def zoom_in(self, key):
        """鼠标停在盖着缩略图的那一格上：旁边弹一张放大的图（够看清人物与背景）。"""
        if self.zoom is None:
            return None
        row, column = key
        bounds = self.tree.bbox(row, column)
        if not bounds:
            self.zoom_hide()
            return None
        image = None
        try:
            image = self.zoom(row, column)
        except Exception:
            image = None
        if image is None:
            self.zoom_hide()                      # 放大图造不出来（jpg 之类 Tk 不认）就不放大
            return None
        host = self.tree.winfo_toplevel()
        if self.zoom_label is None or not self.zoom_label.winfo_exists():
            self.zoom_label = tk.Label(host, borderwidth=1, relief='solid', background='#ffffff',
                                       highlightthickness=0)
            self.bind_zoom_label(self.zoom_label)
        try:
            self.zoom_label.configure(image=image)
        except Exception:
            return None
        self.zoom_label.image = image             # 图元得挂住：Tk 一回收，画面上只剩空框
        try:
            width, height = int(image.width()), int(image.height())
        except Exception:
            return None
        try:
            room_x, room_y = int(host.winfo_width()), int(host.winfo_height())
        except Exception:
            room_x, room_y = width + 2 * ZOOM_GAP, height + 2 * ZOOM_GAP
        left, top = self.zoom_spot(bounds, width, height, room_x, room_y)
        try:
            self.zoom_label.place(x=int(left), y=int(top))
            self.zoom_label.lift()
        except Exception:
            return None
        self.zoom_key = key
        self.zoom_at = self.screen_pointer()      # 第 60 期第 5 条：以这会儿的指针为基准
        self.zoom_watch_arm()
        return key

    def bind_zoom_label(self, label):
        """放大图自己也认「鼠标走了」（第 60 期第 5 条）。

        这张图原来一条绑定都没有：鼠标从那一格挪到放大图上（两张图只差 ZOOM_NEAR 像素，很容易），
        再挪走时谁都不响——那一格早收到 <Leave> 了（它看一眼「指针压在图上，算还在看」就不收），
        放大图这边却没人接，图于是钉在桌面上不走（用户报的「移动鼠标离开缩略图，放大图不会消失」；
        三虎的聊天框一冒出来，置顶窗压在指针上，鼠标更容易先落到放大图上）。

        右键同理（第 60 期第 3 条）：放大图盖住的往往是**别的**格子，那一格点不到，
        「查看」得由这张图转给同一份菜单，目标认它的来路（zoom_key）。
        """
        label.bind('<Leave>', lambda event: self.zoom_leave())
        label.bind('<Enter>', lambda event: self.zoom_watch_arm())
        label.bind('<MouseWheel>', lambda event: self.zoom_hide())
        if self.hover is not None:
            label.bind('<Button-3>', self.zoom_menu)
        return label

    def zoom_menu(self, event):
        """放大图上右键＝来路那一格的「查看／删除」（第 60 期第 3 条）。"""
        key = self.zoom_key
        hover = self.hover
        if key is None or hover is None:
            return None
        popup_row_menu(self.tree, key[0], key[1], hover.command, hover.delete,
                       event.x_root, event.y_root)
        return 'break'

    def screen_pointer(self):
        """指针在屏幕上的哪儿（判「动没动」用；读不出来给 None）。"""
        try:
            x, y = self.tree.winfo_pointerxy()
            return int(x), int(y)
        except Exception:
            return None

    def zoom_cancel_watch(self):
        if self.zoom_watch is not None:
            try:
                self._zoom_owner.after_cancel(self.zoom_watch)
            except Exception:
                pass
            self.zoom_watch = None
        return None

    def zoom_watch_arm(self):
        """保险丝：放大图在的时候，隔一小会儿自己看一眼指针（第 60 期第 5 条）。

        <Leave> 是主路，但它有收不到的时候（三虎的聊天框是置顶窗，冒出来正好压在指针上；
        窗口从指针底下长出来那一拍鼠标根本没动，谁来都不响）。这一条只判「指针动过了、眼下
        又不在放大图上、也不在那一格上」——自检里指针是造出来的、动不了，所以它不会替用例
        下结论（不会把用例里刚弹出的放大图悄悄收掉）。
        """
        if self.zoom is None or self.zoom_key is None:
            return None
        try:
            if not self.tree.winfo_exists():
                return None
        except Exception:
            return None
        self.zoom_cancel_watch()
        try:
            # 挂在顶层窗口而不是会被换页销毁的 Treeview 上。Tk 直接销毁父窗时
            # 不会逐一调用子控件的 Python `destroy()`，原来因此残留 zoom_watchdog。
            self.zoom_watch = self._zoom_owner.after(ZOOM_WATCH_MS, self.zoom_watchdog)
        except Exception:
            self.zoom_watch = None
        return None

    def zoom_under(self):
        """指针这会儿压没压在「放大图／那一格」上：True／False，读不出指针给 None（当作还在看）。"""
        try:
            x, y = self.tree.winfo_pointerxy()
            under = self.tree.winfo_containing(int(x), int(y))
        except Exception:
            return None
        label = self.zoom_label
        if label is not None and under is label:
            return True
        source = self.labels.get(self.zoom_key) if self.zoom_key is not None else None
        return bool(source is not None and under is source)

    def zoom_watchdog(self):
        # 测试和关闭路径会直接调用本方法。先撤掉已排队的同一轮 watcher，
        # 否则仅清空 Python 侧编号会让 Tcl 的旧 after 在窗口销毁后继续触发。
        self.zoom_cancel_watch()
        if self.zoom_key is None:
            return None
        try:
            if not self.tree.winfo_exists():
                self.zoom_hide()
                return None
        except Exception:
            return None
        label = self.zoom_label
        if label is None or not label.winfo_exists() or not label.winfo_ismapped():
            return None
        point = self.screen_pointer()
        if point is not None and point != self.zoom_at:
            self.zoom_at = point
            if self.zoom_under() is False:
                self.zoom_hide()
                return None
        self.zoom_watch_arm()
        return None

    def pointer_xy(self):
        """指针落在顶层窗口里的哪儿（第 58 期第 3 条）；没有真指针（自检）就给 None。"""
        try:
            host = self.tree.winfo_toplevel()
            x, y = self.tree.winfo_pointerxy()
            return int(x) - int(host.winfo_rootx()), int(y) - int(host.winfo_rooty())
        except Exception:
            return None

    def zoom_spot(self, bounds, width, height, room_x, room_y):
        """这张放大图摆哪儿（第 58 期第 3 条）：紧贴鼠标右上角。

        底边压着指针、往右上铺开——右边放不下就翻到指针左边，上头顶到窗口边就顺势压到指针下头，
        怎么摆都不许出窗口。指针读不出来（自检／无真指针）时退回「贴这一格右边、竖直居中」，
        并把格子坐标从内容框换算到顶层窗口（place 用的是窗口坐标，两套坐标不能混）。
        """
        point = self.pointer_xy()
        if point is None:
            try:
                host = self.tree.winfo_toplevel()
                offset_x = int(self.tree.winfo_rootx()) - int(host.winfo_rootx())
                offset_y = int(self.tree.winfo_rooty()) - int(host.winfo_rooty())
            except Exception:
                offset_x = offset_y = 0
            px = bounds[0] + bounds[2] + offset_x
            py = bounds[1] + bounds[3] // 2 + offset_y
        else:
            px, py = point
        left = px + ZOOM_NEAR
        top = py - ZOOM_NEAR - height
        if left + width > room_x - ZOOM_GAP:
            left = px - ZOOM_NEAR - width          # 右边放不下就翻到指针左边
        if top < ZOOM_GAP:
            top = py + ZOOM_NEAR                   # 上头装不下就压到指针下头
        left = max(ZOOM_GAP, min(left, max(ZOOM_GAP, room_x - width - ZOOM_GAP)))
        top = max(ZOOM_GAP, min(top, max(ZOOM_GAP, room_y - height - ZOOM_GAP)))
        return int(left), int(top)

    def zoom_leave(self, key=None):
        """鼠标离开那一格：等一小会儿再看一眼指针在不在放大图上（压在图上就算还在看）。

        放大图压在那一格旁边的机会不小，直接收会把「正凑近看」的人手里的图收走；等这一小会儿
        再看指针落点，图上／那一格上都算还在看，别处才收。
        """
        if self.zoom is None or self.zoom_key is None or self.zoom_pending is not None:
            return None

        def check():
            self.zoom_pending = None
            label = self.zoom_label
            if label is None or not label.winfo_exists() or not label.winfo_ismapped():
                return None
            try:
                x, y = self.tree.winfo_pointerxy()
                under = self.tree.winfo_containing(x, y)
                source = self.labels.get(self.zoom_key)
                keep = under is label or (source is not None and under is source)
            except Exception:
                keep = False
            if not keep:
                self.zoom_hide()
            return None

        try:
            self.zoom_pending = self._zoom_owner.after(ZOOM_HIDE_MS, check)
        except Exception:
            self.zoom_pending = None
        return None

    # ── 那一层 Label ───────────────────────────────────────────────────────
    def hide(self, key):
        """撤掉这一格的图（行被删、滚出可视区、这一行本来就没图），文字写回。"""
        if self.zoom_key == key:
            self.zoom_hide()
        label = self.labels.pop(key, None)
        if label is not None:
            try:
                label.place_forget()
                label.destroy()
            except Exception:
                pass
        self.restore(key)

    def label_for(self, key):
        label = self.labels.get(key)
        if label is not None and label.winfo_exists():
            return label
        label = tk.Label(self.tree, borderwidth=0, padx=3, anchor='w', compound='left',
                         background='#ffffff', cursor='hand2')
        if self.plain is not None:
            # 第 55 期第 2 条：这一格上是图，不再走高亮——鼠标移上来只把可能还亮着的旧格灭掉。
            for sequence, callback in (('<Motion>', self.plain.clear), ('<Leave>', self.plain.leave),
                                       ('<MouseWheel>', self.plain.clear)):
                label.bind(sequence, callback, add='+')
        if self.hover is not None:
            label.bind('<Button-3>', self.hover.menu, add='+')
        if self.zoom is not None:
            # 第 57 期第 5 条：停上来就放大；走开／滚轮都收（滚轮之后这一格会挪位，留着就错位了）。
            label.bind('<Enter>', lambda event, key=key: self.zoom_in(key), add='+')
            label.bind('<Leave>', lambda event, key=key: self.zoom_leave(key), add='+')
            label.bind('<MouseWheel>', lambda event: self.zoom_hide(), add='+')
        # 第 55 期第 2 条：这一格盖着图，鼠标落不到树上——forward 给了就把这一下重发给树
        # （树上的原行为一条不动），右键照旧转给 CellHover 那份「查看／删除」菜单。
        # 第 60 期第 3 条撤掉的那条左键路，第 64 期任务 12 按用户要求补回来一半：**只认双击**
        # （单击照旧只点亮这一行，不打开）。想看这一格的文件双击缩略图，或走右键菜单的「查看」。
        if self.forward is not None:
            for sequence in ('<Button-1>', '<Button-3>'):
                label.bind(sequence, self.forward, add='+')
        if self.hover is not None:
            label.bind('<Double-1>', lambda event, key=key: self.view(key), add='+')
        self.labels[key] = label
        return label

    def view(self, key):
        """打开这一格（与 CellHover.open 同一条路）。

        第 60 期第 3 条起不再绑在单击上；第 64 期任务 12 起绑在**双击**上（见 label_for），
        右键菜单里的「查看」也走这里。别的层要「按这一格打开」时照样能走同一条路。
        """
        if self.hover is None:
            return None
        return self.hover.open(*key)

    def visible_rows(self):
        """内容框里现在真的露着的那几行。

        第 72 期（Round 3）：重排一次原来要把整张表扫一遍——1000 行的表就是每帧 1000 次
        `bbox`，实测 33 ms/帧，而且这份开销跟表有多长成正比。滚动条自己知道这一屏落在哪
        一段（`yview` 给的就是行数的比例），按它粗算出一小段候选行、再逐行 `bbox` 验一遍，
        每次重排就只碰十几行（实测 999 行的表从 1001 次 bbox 降到 8 次）。
        候选段一个都没验出来时退回老做法（整表扫一遍）：宁可慢一拍，也不许「一格都不盖」。
        """
        tree = self.tree
        children = tree.get_children()
        if not children:
            return ()
        try:
            first, last = tree.yview()
        except Exception:
            return tuple(children)
        total = len(children)
        start = int(first * total)
        span = int((last - first) * total) + 3
        rows = children[max(0, start - 1):start + span]
        visible = ()
        for column in (*self.columns, '#0'):
            visible = tuple(row for row in rows if tree.bbox(row, column))
            if visible:
                break
        return visible or tuple(children)

    def refresh(self, event=None):
        """把可见行重排一遍：该盖的盖上、不该盖的撤掉；返回这次盖住的那几格。"""
        if not self.tree.winfo_exists():
            return set()
        if self.zoom_key is not None:
            self.zoom_hide()                     # 第 57 期第 5 条：格子挪了，放大图那一份跟着作废
        covered = set()
        for row in self.visible_rows():
            background = self.background(row) if callable(self.background) else self.background
            for column in self.columns:
                bounds = self.tree.bbox(row, column)
                value = self.provider(row, column) if bounds else None
                if value is None:
                    self.hide((row, column))
                    continue
                image, text = value
                label = self.label_for((row, column))
                label.configure(image=image, text=text or '',
                                compound='left' if text else 'none',
                                anchor='w' if text else 'center',
                                background=background)
                label.place(x=bounds[0], y=bounds[1], width=bounds[2], height=bounds[3])
                label.lift()
                covered.add((row, column))
                self.blank(row, column)
        for key in list(self.labels):
            if key not in covered:
                self.hide(key)
        # 高亮那一层是 CellHover 的，盖图这层刚被提到它上面：把它抬回去。
        if self.hover is not None:
            try:
                self.hover.overlay.lift()
            except Exception:
                pass
        return covered

    def destroy(self, event=None):
        if event is not None and getattr(event, 'widget', None) not in (self.tree, self._zoom_owner):
            return
        self.zoom_hide()
        if self.zoom_label is not None:
            try:
                self.zoom_label.destroy()
            except Exception:
                pass
            self.zoom_label = None
        for key in list(self.labels):
            self.hide(key)
