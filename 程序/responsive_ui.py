"""Wrapping action rows and proportionate table columns for Tkinter."""
import app_logging
import tkinter as tk
from tkinter import ttk, TclError
from ui.ui_scroll import eased_scroll
from ui_tokens import SPACING

# 第 47 期第 1 条：内容框的「选中」统一口径（勾选／高亮）见下面 work_rows 那一组。
_growables=[]

# 内容框的前 GROWABLE_FLOOR 行算在「页面本来就要占的高度」里，多出来的行由 growable_extra
# 从请求高度里扣掉（页面于是不会被表格顶飞）。反过来说，谁要预留「表格至少占多高」，
# 预留这一档就够了——第 71 期任务 5 的创意框就是这么算的。
GROWABLE_FLOOR=2

def register_growable(tree,row_height=34,padding=30):
    _growables.append([tree,row_height,padding])

def growable_extra():
    extra=0;dead=[]
    for index,(tree,row_height,padding) in enumerate(_growables):
        try:
            if not tree.winfo_exists():dead.append(index);continue
            cur=int(tree.cget('height'))
            extra+=max(0,cur-GROWABLE_FLOOR)*row_height
        except Exception:
            dead.append(index)
    for index in reversed(dead):_growables.pop(index)
    return extra

class QuietVar(tk.StringVar):
    """内容没变就不写 Tcl 的显示用 StringVar。

    带 wraplength 的标签每被写一次就要重新折行排版：进度栏那种多行长文字实测约 4 毫秒/次，
    而页面刷新常把同一句话反复写回去（同一镜头没变、汇总没变）。与 configure_column 同一套
    思路——参数真的变了才落到 Tk。变量的最终值不变，这些变量上也没有任何 trace 依赖重复写入。
    """
    def set(self,value):
        if super().get()!=value:super().set(value)


CHECK_COLUMN_WIDTH = 28

def configure_check_column(tree, command=None):
    """把 #0 配置为独立勾选列，供各内容框复用。"""
    if command is None:
        tree.heading('#0', text='')
    else:
        tree.heading('#0', text='', command=command)
    tree.column('#0', width=CHECK_COLUMN_WIDTH, minwidth=CHECK_COLUMN_WIDTH, stretch=False, anchor='center')

def refresh_check_heading(tree, tick_images, is_checked):
    """按当前勾选状态刷新 #0 表头的全选图标。"""
    items = list(tree.get_children())
    all_checked = bool(items) and all(is_checked(item) for item in items)
    tree.heading('#0', image=tick_images[1 if all_checked else 0])

class CheckboxColumn:
    """统一内容框首列勾选：单行切换 / 全选切换 / 行图标与表头刷新。"""
    def __init__(self, tree, tick_images, get_checked, set_checked, on_change=None):
        self.tree=tree;self.tick_images=tick_images;self.get_checked=get_checked;self.set_checked=set_checked;self.on_change=on_change
    def refresh_row(self,item):
        if self.tree.exists(item):
            self.tree.item(item,image=self.tick_images[1 if self.get_checked(item) else 0])
    def refresh_header(self):
        refresh_check_heading(self.tree,self.tick_images,self.get_checked)
    def toggle(self,item):
        self.set_checked(item,not self.get_checked(item));self.refresh_row(item);self.refresh_header()
        if self.on_change:self.on_change()
    def set_all(self,value):
        for item in list(self.tree.get_children()):
            self.set_checked(item,value);self.refresh_row(item)
        self.refresh_header()
        if self.on_change:self.on_change()
    def toggle_all(self):
        items=list(self.tree.get_children())
        self.set_all(not (bool(items) and all(self.get_checked(i) for i in items)))

def row_toggle_target(tree, x, y, link_columns=()):
    """内容框点击归属：表头、列宽拖动和带链接的格子返回 None，其余返回要切换勾选的行。"""
    if tree.identify_region(x,y) not in ('tree','cell'):return None
    row=tree.identify_row(y)
    if not row or tree.identify_column(x) in {str(column) for column in link_columns}:return None
    return row

def bind_row_toggle(tree, toggle, link_columns=()):
    """统一内容框点击：格子里只是文本时单击勾选本行、再次单击取消；带链接的格子由 CellHover 打开。"""
    def click(event):
        row=row_toggle_target(tree,event.x,event.y,link_columns)
        if not row:return
        tree.focus_set();tree.focus(row)
        if tree.selection()!=(row,):tree.selection_set(row)
        toggle(row)
        return 'break'
    tree.bind('<Button-1>',click,add='+')

def bind_space_toggle(tree, toggle):
    """空格键勾选／取消当前行：优先光标行，光标行失效时退到高亮行，并把高亮对齐到该行。"""
    def press(event):
        row=tree.focus()
        if not row or not tree.exists(row):
            rows=tree.selection();row=rows[0] if rows else None
        if row:
            if tree.selection()!=(row,):tree.selection_set(row)
            toggle(row)
        return 'break'
    tree.bind('<space>',press,add='+')

def checked_rows(tree, is_checked):
    """内容框里勾着的那几行（按表格里的先后次序）。

    第 47 期第 1 条：内容框里「勾选」是正式的选中口径，「高亮」（Treeview 的当前行）
    只是光标。下面几个函数把这两件事统一起来，各页不再各说各话。
    """
    try:
        rows = list(tree.get_children())
    except Exception:
        return []
    out = []
    for row in rows:
        try:
            if is_checked(row):
                out.append(row)
        except Exception:
            continue
    return out

def shown_row(tree):
    """内容框里高亮（当前行）的那一行：先认 selection，没高亮再看光标。"""
    row = ''
    try:
        rows = tree.selection()
    except Exception:
        rows = ()
    if rows:
        row = str(rows[0])
    if not row:
        try:
            row = str(tree.focus() or '')
        except Exception:
            row = ''
    if not row:
        return ''
    try:
        if not tree.exists(row):
            return ''
    except Exception:
        app_logging.swallowed()
    return row

def work_rows(tree, is_checked):
    """「制作／删除」这一类动作的目标：勾选优先；一个都没勾就按高亮那一行算（第 47 期第 1 条）。

    返回 (ids, 来源)：来源是 'checked'（勾选的那几行）、'shown'（只有一行高亮）或 ''（都没有）。
    以前高亮一行却没勾上时，批量删除会说「请先勾选」——用户看着那一行明明是选中的；
    统一口径以后，这一行也算数（文案用 work_hint 补一句说清）。
    """
    rows = checked_rows(tree, is_checked)
    if rows:
        return rows, 'checked'
    row = shown_row(tree)
    if row:
        return [row], 'shown'
    return [], ''

def work_hint(ids, source):
    """按 work_rows 的结果补一句说明：这一行是按高亮算的。"""
    if source == 'shown' and ids:
        return '（没有勾选行，这次按高亮的那一行 ' + str(ids[0]) + ' 算）'
    return ''

def view_row(tree, is_checked):
    """「查看／定位」（播放、打开、跳到某一行）的目标：高亮优先；没高亮就用第一个勾选行。

    与 work_rows 正相反：这一类动作看的是「用户正在看的那一行」，勾选只是兜底。
    """
    row = shown_row(tree)
    if row:
        return row
    rows = checked_rows(tree, is_checked)
    return rows[0] if rows else ''

def cached_fonts(tree):
    """按样式字体规格缓存 Font 对象：每次自动列宽都新建 Font 会重复注册 Tcl 字体。"""
    from tkinter import font as tkfont
    style=ttk.Style(tree)
    body_spec=style.lookup('Treeview','font') or 'TkDefaultFont'
    heading_spec=style.lookup('Treeview.Heading','font') or 'TkHeadingFont'
    signature=(str(body_spec),str(heading_spec))
    cached=getattr(tree,'_fit_fonts',None)
    if cached is None or cached[0]!=signature:
        cached=(signature,tkfont.Font(root=tree,font=body_spec),tkfont.Font(root=tree,font=heading_spec))
        tree._fit_fonts=cached
    return cached[1],cached[2]


_measure_cache={}


def measure(font,text):
    """按 (字体, 文字) 记忆宽度：窗口缩放和每次刷新都会反复量同一批单元格文字。"""
    text=str(text)
    key=(font.name,text)
    width=_measure_cache.get(key)
    if width is None:
        width=font.measure(text)
        if len(_measure_cache)>=20000:_measure_cache.clear()
        _measure_cache[key]=width
    return width


def _column_option(tree,column,key):
    try:value=tree.column(column,key)
    except TclError:return None
    if key=='anchor':return str(value)
    try:return int(value)
    except (TypeError,ValueError):return str(value)


def configure_column(tree,column,width,minwidth=None,stretch=None,anchor=None):
    """只在列参数真的变化时才配置列：重复写同一列会让整张表重新排版。"""
    options={'width':int(width)}
    if minwidth is not None:options['minwidth']=int(minwidth)
    if stretch is not None:options['stretch']=1 if stretch else 0
    if anchor is not None:options['anchor']=str(anchor)
    if all(_column_option(tree,column,key)==value for key,value in options.items()):return
    tree.column(column,**options)


MIN_COL = 56            # 数据列缩到这么窄就钉住：还能看清表头那两个字
VIEW_PAD = 6            # 内容框右沿给纵向滚动条留的一点余量


def view_width(tree):
    """内容框现在实际有多宽：还没被映射出来（1 像素）时返回 0，调用方照内容宽度排。"""
    try:
        width=int(tree.winfo_width())
    except Exception:
        return 0
    return width if width>1 else 0


def squeeze(widths,available,floors=None):
    """把 widths 塞进 available：先按比例缩，缩到 floor 就钉住，缺的由还能缩的列分摊。

    用户第 26 期第 2 条要的是「界面缩小时每列尽量都还能显示」，所以宁可均摊到挤一点，
    也不让某一列被顶出可视区。四轮足够收敛；轮数用完还差几个像素就算了——那点时侯
    留一点横向滚动，比把一列压成一条缝强。
    """
    out=[int(w) for w in widths]
    floors=[int(f) for f in floors] if floors else [0]*len(out)
    # 第 26 期第 2 条：列宽本来就是手写死的表（资产管理那一张的「导入状态(点击查看)」写的是 90，
    # 而表头要 120 才放得下）——只缩不抬的话，这一列永远卡在 90，表头就被裁成「导入状态(点…」。
    # 所以先把手写宽度不足下限的列抬到下限；抬完超宽再由下面的循环从其他列身上找回来。
    for index,floor in enumerate(floors):
        if index<len(out) and out[index]<floor:out[index]=floor
    if available<=0 or sum(out)<=available:
        return out
    for _ in range(4):
        extra=sum(out)-available
        if extra<=0:
            break
        loose=[index for index,width in enumerate(out) if width>floors[index]]
        if not loose:
            break
        room=sum(out[index]-floors[index] for index in loose)
        if room<=0:
            break
        scale=min(1.0,extra/float(room))
        for index in loose:
            out[index]=max(floors[index],int(out[index]-(out[index]-floors[index])*scale))
        if sum(out)<=available:
            break
    return out


def fill_columns(widths,needs,floors,available):
    """把 widths 撑满 available（第 53 期第 4 条）：先补回被裁掉的内容，富余再按比例分给每一列。

    用户要的是「每一列都跟着内容框的大小走，还能完整显示格子的内容」：
    - 内容框放得下全部内容时，先把宽得不够的列补到内容宽度（长分镜名不再被裁）；
    - 补完还有富余，就按各列现有宽度成比例地分掉——不留一条空白带，也不让最后一列独吞；
    - 内容框装不下就交给 squeeze，按比例缩、缩到下限钉住。
    """
    out=[int(w) for w in widths]
    room=int(available or 0)
    if room<=0:
        return out
    if sum(out)>=room:
        return squeeze(out,room,floors)
    extra=room-sum(out)
    deficit=[max(0,int(needs[i])-out[i]) for i in range(len(out))]
    want=sum(deficit)
    if want>0:
        take=min(extra,want)
        for index,room_left in enumerate(deficit):
            if room_left:
                out[index]+=int(take*room_left/float(want))
        extra=room-sum(out)
    if extra>0:
        base=sum(out)
        if base>0:
            for index,width in enumerate(out):
                out[index]+=int(extra*width/float(base))
        out[-1]+=room-sum(out)          # 几像素的零头给最后一列，别为它多出一条横向滚动条
    for index,floor in enumerate(floors):
        if out[index]<floor:
            out[index]=int(floor)
    return out


def fit_columns_by_content(tree,specials=None,pad=32,minwidth=MIN_COL,fill=False):
    """按表头与单元格文字排数据列宽，再按内容框当前的宽度收一收。

    #0 是固定勾选列；其余列先按内容量出「想要多宽」，再按窗口宽度等比缩——缩到
    minwidth 就钉住，于是界面变窄时每列都还在，而不是最后一列之外的列被顶出可视区。
    最后一列随窗口伸展。内容框宽度一变会自动重排（见 bind_view_fit），调用方只要在
    填完行之后调一次就够了。specials={column: fn(width)->width}。

    第 53 期第 4 条：fill=True 时改用 fill_columns——「想要多宽」不再是各列各管各的，而是
    把整个内容框铺满：先补回被裁掉的内容，富余按比例分给每一列。分镜定稿那一页要的就是它。
    """
    body,heading=cached_fonts(tree)
    configure_column(tree,'#0',CHECK_COLUMN_WIDTH,minwidth=CHECK_COLUMN_WIDTH,stretch=False)
    rows=[tree.item(item) for item in tree.get_children()]
    specials=specials or {}
    columns=list(tree['columns'])
    widths=[];floors=[];needs=[]
    for index,column in enumerate(columns):
        texts=[str(row['values'][index]) for row in rows]
        head=measure(heading,tree.heading(column,'text'))
        width=max([head]+[measure(body,text) for text in texts])+pad
        needs.append(int(width))          # 内容本来要多大（不含 specials 的上限）
        if column in specials:width=specials[column](width)
        widths.append(int(width))
        floors.append(max(int(minwidth),int(head)+pad))
    desired=list(widths)                  # 「想要多宽」：缩之前先记下来，窗口变宽要还原
    available=view_width(tree)
    if available:
        room=max(1,available-CHECK_COLUMN_WIDTH-VIEW_PAD)
        widths=(fill_columns(widths,needs,floors,room) if fill else squeeze(widths,room,floors))
    _apply_columns(tree,columns,widths,floors)
    remember_columns(tree,zip(columns,desired))
    tree._view_fit_args=(specials,pad,fill)
    tree._view_fit_width=available
    bind_view_fit(tree)
    return widths


def remember_columns(tree,pairs):
    """记下每列「想要多宽」：缩放只是在这基础上收放，不会越收越小。"""
    tree._column_desired=dict(pairs)
    return tree._column_desired


def desired_widths(tree,minwidth=MIN_COL):
    """这一张表各列想要多宽：记过就用记下的，没记过就拿当前列宽当基底并记下来。

    没记过时必须**当场记住**：否则第一次按窗口缩完之后，「当前列宽」已经是被缩过的值，
    再按它当基底就永远长不回去了（实测窗口回宽时最后一列独吞全部余量、其余列卡在窄值）。
    """
    columns=list(tree['columns'])
    remembered=getattr(tree,'_column_desired',None)
    if not remembered or any(column not in remembered for column in columns):
        remembered=remember_columns(tree,[(column,int(tree.column(column,'width'))) for column in columns])
    widths,floors=[],[]
    for column in columns:
        widths.append(int(remembered[column]))
        head=measure(cached_fonts(tree)[1],tree.heading(column,'text'))
        floors.append(max(int(minwidth),int(head)+16))
    return columns,widths,floors


def fit_current_columns(tree,minwidth=MIN_COL):
    """按内容框现在的宽度收放**现有**列宽：不重算内容，只保证每一列都还看得见。

    给那些自己定死了列宽的表格用（见 auto_columns）——它们不跑 fit_columns_by_content，
    窗口一窄就会把右边的列顶出可视区，用户第 26 期第 2 条要的正是这一条。
    """
    columns,widths,floors=desired_widths(tree,minwidth)
    if not columns:
        return []
    configure_column(tree,'#0',CHECK_COLUMN_WIDTH,minwidth=CHECK_COLUMN_WIDTH,stretch=False)
    available=view_width(tree)
    if available:
        widths=squeeze(widths,max(1,available-CHECK_COLUMN_WIDTH-VIEW_PAD),floors)
    _apply_columns(tree,columns,widths,floors)
    tree._view_fit_width=available
    return widths


def refresh_request_width(tree):
    """窄窗时让 Treeview 按当前列宽重算请求宽度，避免旧宽度把内容区顶出窗口。

    列宽被 ``fit_current_columns`` 收小后 Tk 仍把旧的请求宽度钉住，内容区会被顶出窗口；
    这里在 ``<Configure>`` 时重设一次 ``displaycolumns``，让 Tk 重算请求宽度。重设去抖到
    ``after_idle``，同一时刻只挂一个；控件销毁时取消还挂着的回调。
    """
    def refresh():
        width = tree.winfo_width()
        if width <= 1 or tree.winfo_reqwidth() <= width:
            return
        if getattr(tree, '_request_refresh_width', None) == width:
            return
        tree._request_refresh_width = width
        tree.configure(displaycolumns=tree['columns'])
    def run():
        tree._request_refresh_pending = False
        tree._request_refresh_after_id = None
        try:
            if tree.winfo_exists():
                refresh()
        except tk.TclError:
            pass
    def on_configure(event=None):
        if event is not None and getattr(event, 'widget', None) is not tree:
            return
        if getattr(tree, '_request_refresh_pending', False):
            return
        tree._request_refresh_pending = True
        try:
            tree._request_refresh_after_id = tree.after_idle(run)
        except tk.TclError:
            tree._request_refresh_pending = False
    def on_destroy(event=None):
        if event is not None and getattr(event, 'widget', None) is not tree:
            return
        job = getattr(tree, '_request_refresh_after_id', None)
        if job:
            try:
                tree.after_cancel(job)
            except tk.TclError:
                pass
        tree._request_refresh_after_id = None
        tree._request_refresh_pending = False
    tree.bind('<Configure>', on_configure, add='+')
    tree.bind('<Destroy>', on_destroy, add='+')
    return tree


def _bind_debounced_configure(tree, bound_attr, pending_attr, run):
    """仅在内容框实际变宽时，于 idle 阶段执行一次列重排。"""
    if getattr(tree, bound_attr, False):
        return tree
    setattr(tree, bound_attr, True)
    def on_configure(event=None):
        if event is not None and getattr(event, 'widget', None) is not tree:
            return
        width = view_width(tree)
        if not width or width == getattr(tree, '_view_fit_width', 0):
            return
        if getattr(tree, pending_attr, False):
            return
        setattr(tree, pending_attr, True)
        def after_idle():
            setattr(tree, pending_attr, False)
            try:
                if tree.winfo_exists():
                    run()
            except Exception:
                app_logging.swallowed()
        try:
            tree.after_idle(after_idle)
        except Exception:
            setattr(tree, pending_attr, False)
    try:
        tree.bind('<Configure>', on_configure, add='+')
    except Exception:
        setattr(tree, bound_attr, False)
    return tree


def auto_columns(tree,minwidth=MIN_COL):
    """绑定「内容框宽度一变就收放列宽」：只绑一次，去抖到 after_idle。

    与 bind_view_fit 同一套规矩（宽度没变就什么都不做），区别是这里不重算内容宽度，
    所以给那些列宽本来就是写死的表格用。
    """
    return _bind_debounced_configure(
        tree, '_auto_columns_bound', '_auto_columns_pending',
        lambda: fit_current_columns(tree, minwidth))


def _apply_columns(tree,columns,widths,floors):
    """把量好的宽度落到列上：最后一列随窗口伸展，其余按量出来的宽度。"""
    last=columns[-1] if columns else None
    for index,column in enumerate(columns):
        configure_column(tree,column,widths[index],minwidth=floors[index],stretch=(column==last))


def bind_view_fit(tree,pad=32):
    """内容框宽度一变就重排一次列宽：只绑一次，去抖到 after_idle。

    `<Configure>` 期间直接改列宽会让 Tk 自己再排一轮，所以推后一拍；宽度没变就直接返回，
    否则「列宽→内容框宽度→列宽」会来回抖。
    """
    def fit():
        args=getattr(tree,'_view_fit_args',(None,pad))
        spec,size=args[0],args[1]
        fit_columns_by_content(tree,spec,size,fill=args[2] if len(args)>2 else False)
    return _bind_debounced_configure(
        tree, '_view_fit_bound', '_view_fit_pending', fit)

class FlowBar(ttk.Frame):
    """可缩放的操作栏：不足一行时换行，而不裁掉按钮标签。

    页面上的按钮可继续用 ``pack`` 声明顺序；本类会在布局时统一转换为 ``place``。
    因此按钮宽度始终至少是其文字所需的请求宽度（单个按钮比栏宽时才收至栏宽），
    窗口缩小只会增加行数，不会发生左右两组控件互相覆盖或标签被截断。
    ``set_visible`` 隐藏的子控件不占位，重新显示时回到原来的创建顺序位置。
    """
    def __init__(self,parent,**kwargs):
        super().__init__(parent,**kwargs)
        self.pack_propagate(False);self.configure(height=SPACING['sm'] * 5)
        self.pending=None;self.hidden_children=set()
        self.bind('<Configure>',self.schedule)
        self.pending=self.after_idle(self.layout)
        self.bind('<Destroy>',self.disposed,add='+')
    def disposed(self,event):
        if event.widget is self and self.pending is not None:
            self.after_cancel(self.pending);self.pending=None
    def schedule(self,event=None):
        if self.pending is None:self.pending=self.after_idle(self.layout)
    def set_visible(self,child,visible):
        if visible:self.hidden_children.discard(child)
        else:self.hidden_children.add(child)
        self.schedule()
    def layout(self):
        self.pending=None
        if not self.winfo_exists():return
        available=self.winfo_width()
        if available<=1:
            # 控件刚建好、还没被几何管理器映射时 winfo_width() 是 1：按 1 像素排版会把每个
            # 按钮各占一行，底部行瞬间高几百像素（实测 38→258），整页跟着跳一下——切换分镜、
            # 重建页面时看起来就是「内容抖动」。先借容器宽度（容器通常已经定好尺寸），
            # 容器也没有尺寸就什么都不做，等 <Configure> 带来真实宽度再排。
            available=self.master.winfo_width() if self.master is not None else 1
            if available<=1:return
        available=max(1,available);x=0;y=0;rowheight=0
        for child in self.winfo_children():
            if child.winfo_manager()=='pack':child.pack_forget()
            if child in self.hidden_children:
                child.place_forget();continue
            if isinstance(child,ttk.Label):child.configure(wraplength=max(80,available-8))
            width=min(available,child.winfo_reqwidth());height=child.winfo_reqheight()
            if x and x+width>available:y+=rowheight+4;x=0;rowheight=0
            child.place(x=x,y=y,width=width,height=height)
            x+=width+5;rowheight=max(rowheight,height)
        height=y+rowheight
        if int(self.cget('height'))!=height:self.configure(height=height)


# ── 第 58 期第 2 条：内容框的行高按格子里最高的那点内容算 ───────────
# 用户原话：「全部内容框自动根据格子内容调整行间距」。以前是每张表各写一个数字（镜头表 60、
# 资产表 80、主题里的 34），图尺寸或字体一变就对不上了。现在统一算：格子里摆
# 缩略图的按图高算，纯文字的按字体量出来的一行高算，两样都有时取高的那个，再加一小截余地。
ROW_PAD = 8          # 图／字与上下边框之间留的余地
ROW_FLOOR = 22       # 纯文字那一行最矮也得有这么高


def font_linespace(widget, spec=None, fallback=18):
    """字体（描述或名字）一行多高；量不出来就用固定的那一档。"""
    from tkinter import font as tkfont
    for candidate in (spec, 'TkDefaultFont'):
        if candidate is None:
            continue
        try:
            return max(8, int(tkfont.Font(root=widget, font=candidate).metrics('linespace')))
        except Exception:
            continue
    return fallback


def row_text_height(widget, fallback=18):
    """这一张内容框里一行字有多高：先按它样式里的字体量
    （tk 的表格字体就设在样式里，控件本身没有 font 这一项），量不出来退回默认字体。"""
    spec = None
    try:
        spec = ttk.Style(widget).lookup(widget.cget('style') or 'Treeview', 'font')
    except Exception:
        spec = None
    if not spec:
        try:
            spec = widget.cget('font')
        except Exception:
            spec = None
    return font_linespace(widget, spec, fallback)


def row_height_for(thumb=0, line_height=18, pad=ROW_PAD, floor=ROW_FLOOR):
    """按格子里最高的那点内容算行高（第 58 期第 2 条）：
    摆缩略图（thumb 像素高）的那一列按图算，纯文字按一行字算，取高的那个再加余地。"""
    def size(value):
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0
    return max(size(floor), size(thumb), size(line_height)) + size(pad)


def row_height_of(tree, fallback=34):
    """这张内容框现在一行多高：先问它自己的样式，问不到就用主题那一档。"""
    try:
        value = ttk.Style(tree).lookup(tree.cget('style') or 'Treeview', 'rowheight')
        return max(1, int(value))
    except Exception:
        return fallback


def fit_row_height(tree, thumb=0, style=None, pad=ROW_PAD, floor=ROW_FLOOR):
    """把一张内容框的行高按它的格子内容设好（第 58 期第 2 条），返回设成的行高。

    摆缩略图的那几张把图高传进来；纯文字的不传，按字体量出来的一行字算。
    """
    name = style or (tree.cget('style') or 'Treeview')
    height = row_height_for(thumb, row_text_height(tree), pad, floor)
    ttk.Style(tree).configure(name, rowheight=height)
    tree._row_height = height
    return height


def auto_height(tree, container, row_height=None, padding=48, minimum=2):
    """让 Treeview 内容框高度随所在容器自动调整，供各页面复用。

    row_height 不给就按这张表现在的行高算（第 58 期第 2 条：行高本身也是按格子内容定的，
    这里再写一个 34 就会与它脱节）。minimum 是「再挤也得留几行」（第 71 期任务 5：剧本那一页
    的下方文件框原来只保证 2 行，矮窗口里几乎看不见内容）。
    """
    if row_height is None:
        row_height = row_height_of(tree)
    minimum = max(1, int(minimum))
    register_growable(tree, row_height, padding)
    def fit(event=None):
        if getattr(tree, '_auto_height_pending', False):
            return
        tree._auto_height_pending = True
        def run():
            tree._auto_height_pending = False
            try:
                if not container.winfo_exists():
                    return
                avail = max(1, int(container.winfo_height()) - padding)
                rows = max(minimum, avail // max(1, row_height))
                count = len(tree.get_children())
                if count:
                    rows = min(rows, count)
                if int(tree.cget('height')) != rows:
                    tree.configure(height=rows)
            except Exception:
                app_logging.swallowed()
        container.after_idle(run)
    container.bind('<Configure>', fit, add='+')
    fit()
    return fit

def display_lines(box, limit=None):
    """这个文本框在屏幕上占几行（自动换行折出来的也算）。量不出来按一行算。

    displaylines 会把折行算上，所以是「屏幕上真实几行」。第 71 期任务 5／6：创意框自动
    定高、以及「点一下看全部」，量的都是这一个数。
    limit：调用方只关心「到没到这么多行」时传入；长记录只排版到第 limit 行就停，
    返回值封顶为 limit，不再为整段历史逐行折行。
    """
    try:
        end='end-1c'
        if limit is not None:
            stop=box.index('1.0 + %d displaylines' % max(1, int(limit)))
            if box.compare(stop,'<',end):
                return max(1, int(limit))
        counted=box.count('1.0',end,'displaylines')
    except (TclError,AttributeError):
        return 1
    lines=counted[0] if isinstance(counted,(tuple,list)) else counted
    if lines is None:lines=1                    # 只有一行时 Tk 会回 None，按一行算
    try:
        return max(1,int(lines))
    except (TypeError,ValueError):
        return 1


def show_all_content(box, maximum=40):
    """把内容框撑到能看见全部文字（封顶 maximum 行），字少的框保持原样不动。

    第 65 期任务 7：创意栏／与模型的对话／剧本这些内容框原来是固定高度，长一点就只能滚着看。
    只长不缩：点一下字少的框子不会突然缩水，也不会把滚动位置弹回开头。
    """
    lines=display_lines(box)
    try:
        current=int(box.cget('height'))
        target=max(current,min(maximum,max(1,int(lines))))
        if target!=current:box.configure(height=target)
    except (TclError,ValueError):
        return None
    return target

def bind_show_all(box, maximum=40, after=None):
    """内容框挂上「点一下就显示全部内容」：鼠标点入和键盘聚焦都算。

    after 给页面用：框子长高了，页面得跟着重算高度，不然底部会被切掉。
    """
    def handler(event=None):
        show_all_content(box,maximum)
        if after is not None:
            try:after()
            except Exception:app_logging.swallowed()
    box.bind('<Button-1>',handler,add='+')
    box.bind('<FocusIn>',handler,add='+')
    return handler


class ScrollForm:
    """可滚动的表单区：滚动条 + 画布 + 内容框，批量资产与首帧制作共用同一份实现。

    内容框长高了不用管滚动范围（内容框自己的 <Configure> 已经接上）；滚轮要等控件都建完再
    `bind_wheel()`——Tkinter 的 <MouseWheel> 是逐控件绑定，递归挂一次之后新加的子控件才会跟着滚。

    ``scrollbar=False`` 时不建可见滚动条（``self.scroll`` 为 None），仍可用滚轮／翻页键滚动画布；
    桌面左侧阶段导航用这种方式，省出一条竖栏的宽度。
    """

    def __init__(self, parent, bg=None, *, scrollbar=True):
        options = {'highlightthickness': 0}
        if bg is not None:
            options['bg'] = bg
        self.canvas = tk.Canvas(parent, **options)
        self.scroll = None
        if scrollbar:
            self.scroll = ttk.Scrollbar(parent, orient='vertical', command=self.canvas.yview)
            self.canvas.configure(yscrollcommand=self.scroll.set)
            self.scroll.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.form = ttk.Frame(self.canvas)
        self.window_id = self.canvas.create_window((0, 0), window=self.form, anchor='nw')
        self.form.bind('<Configure>', self.fit)
        self.canvas.bind('<Configure>', self.resize)

    def fit(self, event=None):
        """按内容实际大小刷新可滚动范围。"""
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def resize(self, event):
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def wheel(self, event):
        steps = max(1, abs(event.delta) // 120)
        eased_scroll(self.canvas, -steps if event.delta > 0 else steps)
        return 'break'

    def bind_wheel(self, widget=None):
        target = self.form if widget is None else widget
        target.bind('<MouseWheel>', self.wheel, add='+')
        for child in target.winfo_children():
            self.bind_wheel(child)
        return self


def scroll_form(parent, bg=None):
    """建一块可滚动的表单区（用法见 ScrollForm）。"""
    return ScrollForm(parent, bg=bg)
