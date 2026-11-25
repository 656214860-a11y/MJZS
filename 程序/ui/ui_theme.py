"""Shared lightweight pastel theme; no image downloads or animation loop."""

import infra.app_logging as app_logging
import tkinter as tk
from ui.ui_popup import refresh_menus
from tkinter import ttk
from ui_tokens import COLORS, DESKTOP_LAYOUT, DIALOG_MIN_HEIGHT, DIALOG_MIN_WIDTH, FONTS, SPACING
from responsive_ui import row_height_for,font_linespace

FONT=FONTS['body']     # 全局字体（行高就按它量出来的一行算）

BG=COLORS['background_primary']

INK=COLORS['text_primary']

ACCENT=COLORS['primary']

def apply(win):

    win.configure(bg=BG)

    for pattern,value in {'*Text.background':COLORS['background_card'],'*Text.foreground':INK,

                          '*Text.insertBackground':INK,'*Text.selectBackground':COLORS['selection_bg'],

                          '*Text.selectForeground':COLORS['selection_text'],'*Text.inactiveSelectBackground':COLORS['selection_bg'],

                          '*Toplevel.background':BG,'*Menu.background':COLORS['background_card'],

                          '*Menu.foreground':INK,'*Menu.activeBackground':COLORS['selection_bg'],

                          '*Menu.activeForeground':COLORS['selection_text'],'*Menu.disabledForeground':COLORS['disabled_text'],

                          '*Menu.selectColor':INK,'*Listbox.background':COLORS['background_card'],

                          '*Listbox.foreground':INK,'*Listbox.selectBackground':COLORS['selection_bg'],

                          '*Listbox.selectForeground':COLORS['selection_text']}.items():win.option_add(pattern,value)

    s=ttk.Style(win);s.theme_use('clam')

    install_tick_indicators(win,s)

    s.configure('.',font=FONT,background=BG,foreground=INK)

    s.configure('TFrame',background=BG)

    s.configure('Card.TFrame',background=COLORS['background_card'])
    s.configure('SelectedShot.TFrame',background=COLORS['focus'],padding=1)

    s.configure('TLabel',background=BG,foreground=INK)

    s.configure('Muted.TLabel',foreground=COLORS['text_secondary'])
    s.configure('SidebarProject.TLabel',background=COLORS['background_primary'],foreground=COLORS['text_primary'],font=FONTS['pet_body'])
    s.configure('SidebarProjectMuted.TLabel',background=COLORS['background_primary'],foreground=COLORS['text_secondary'],font=FONTS['pet_body'])
    s.configure('CardHeading.TLabel',background=COLORS['background_primary'],foreground=COLORS['text_primary'],font=FONTS['body_bold'])
    s.configure('SkillDesc.TLabel',background=COLORS['background_card'],foreground=COLORS['text_muted'],font=FONTS['pet_body'])
    s.configure('SkillDescHover.TLabel',background=COLORS['surface_hover'],foreground=COLORS['text_secondary'],font=FONTS['pet_body'])
    s.configure('Warn.TLabel',foreground=COLORS['warning_text'])
    s.configure('Expired.TLabel',foreground=COLORS['danger_text'])
    # 各设置页会随操作变化的说明统一用这一档：柔和高级灰雾底区别于静态说明，
    # 保持石板灰深色文字可读性，并保留既有样式名 PaleGreenHint.TLabel 兼容消费方。
    s.configure('PaleGreenHint.TLabel', background=COLORS['surface_hover'], foreground=COLORS['text_secondary'], padding=(SPACING['sm'], SPACING['xs']))

    s.configure('Project.Treeview',rowheight=24)

    # 第 58 期第 2 条：内容框的行高按格子里最高的那点内容算。纯文字的表（剧本、
    # 分镜…）只需要一行字加一小截余地，不再写死 34；摆缩略图的那几张各自
    # 按自己的图高设（见 responsive_ui.fit_row_height）。
    s.configure('Treeview',rowheight=row_height_for(0,font_linespace(win,FONT)),background=COLORS['background_card'],fieldbackground=COLORS['background_card'],foreground=INK,borderwidth=0)

    s.configure('Treeview.Heading',background=COLORS['header_bg'],foreground=COLORS['text_heading'],padding=SPACING['sm'])

    s.map('Treeview',background=[('selected',COLORS['selection_bg'])],foreground=[('selected',COLORS['selection_text'])])

    s.configure('TNotebook.Tab',padding=(SPACING['md'] + SPACING['xs'] // 2, SPACING['sm'] + SPACING['xs'] // 4))


    s.configure('TLabelframe',background=BG,bordercolor=COLORS['border_strong'],relief='solid',borderwidth=1)

    s.configure('TLabelframe.Label',background=BG,foreground=COLORS['text_heading'])

    # 第 31 期第 4/5 条：空的 TLabelframe 仍会为标签留出约 19 像素——按钮行到内容框之间

    # 就多出一条空白。这条样式把「卡片」画在普通 Frame 上：边框与 TLabelframe 一致，

    # 但没有标签行，内容框能紧贴上面的按钮行。

    s.configure('Box.TFrame',background=BG,bordercolor=COLORS['border_strong'],relief='solid',borderwidth=1)

    s.map('TCheckbutton',background=[('active',BG)],foreground=[('disabled',COLORS['disabled_text'])])

    # 按钮／输入／焦点／滚动条样式只有一个定义处：ui_widgets.setup_styles()。主题先装，
    # 再调用它；Desktop 里随后的 setup_styles() 命中同一主题缓存，不会二次覆盖。
    from ui_widgets import setup_styles
    setup_styles(win)







def install_tick_indicators(win,style):

    """Use a tick for every themed checkbutton, retaining native input behavior."""

    from tkinter import font as tkfont
    from ui.ui_icons import IconLoader

    text_font=tkfont.Font(root=win,font=('Microsoft YaHei UI',10))

    size=max(12,int(text_font.metrics('ascent')))

    off,on,disabled_off,disabled_on=[
        IconLoader.check_indicator(win, size=size, selected=selected,
                                   disabled=disabled, accent=ACCENT)
        for selected, disabled in [(False,False),(True,False),(False,True),(True,True)]]

    win._tick_images=(off,on,disabled_off,disabled_on)
    # 第 30 期：apply() 在同一个解释器里会被调用多次（入口一次、Desktop 一次），而勾选图元只在
    # 第一次登记。每次都造一套新图、旧图随手丢，旧图一被回收，图元就再也画不出勾选框——
    # 真窗核对时整栏勾选框全空。每一代都留着，图元手上那套永远有效；图存在解释器上，
    # 多个 Tk 根、多次 apply 互不干扰。
    keep=getattr(win,'_tick_images_keep',None)
    if keep is None:keep=[];win._tick_images_keep=keep
    keep.extend([off,on,disabled_off,disabled_on])
    # 旧代表面仍被已建表格行、CheckboxColumn 与 ttk 图元持有；整批就地重画，
    # 静态缓存与直接 image= 引用在日→夜→日切换时不留在上一套颜色。
    for index,image in enumerate(keep):
        role=index%4
        IconLoader.paint_check_indicator(image,selected=role in (1,3),
                                         disabled=role>=2,accent=ACCENT)

    from ui_tokens import current_theme
    name='DramaTick.indicator.' + current_theme()

    if name not in style.element_names():

        style.element_create(name,'image',off,('disabled','selected',disabled_on),('disabled',disabled_off),('selected',on),border=0,sticky='')

    style.layout('TCheckbutton',[('Checkbutton.padding',{'sticky':'nswe','children':[

        (name,{'side':'left','sticky':''}),

        ('Checkbutton.focus',{'side':'left','sticky':'w','children':[('Checkbutton.label',{'sticky':'nswe'})]})]})])

    style.configure('TCheckbutton',padding=(SPACING['xs'] // 2, SPACING['xs'] - SPACING['xs'] // 4),background=BG,foreground=INK)





def box_frame(master,padding=(SPACING['xs'],SPACING['none']),**kwargs):

    """Box 框体唯一创建入口（U5）：聊天框／内容框／列表框的直角 1px 描边外框。

    样式 ``Box.TFrame`` 由 ``apply()`` 定义（直角、1px ``color.border.strong``）；
    页面不得再直接写 ``style='Box.TFrame'``，由 ``test_box_boundary`` 门禁守住。
    """

    return ttk.Frame(master,style='Box.TFrame',padding=padding,**kwargs)


# ── 第 8 轮（收口）：弹窗右上角那两颗「最小化／最大化」撤掉 ─────────────────────
# 第 65 期任务 5 在 install_window_placement 的 hidden_init 里给每个弹窗长出那两颗键，
# 第 67 期任务 1 又把三虎的云朵框单独摘掉。用户这次定的口径就是删：全程序不再画那两颗键，
# 画键的代码与那一处接线一并删掉，弹窗右上角只剩系统那颗 ×（弹窗照旧居中、抓取与置顶）。


def main_window_size(work_width, work_height):
    """主窗口首次尺寸：默认 1280×800，屏幕放不下时按可用区收缩。

    保留原有 24px／48px 边缘留白的意图；返回值永不超过传入的可用区。
    """
    width = min(DESKTOP_LAYOUT['default_width'],
                max(0, int(work_width) - DESKTOP_LAYOUT['window_margin_x']))
    height = min(DESKTOP_LAYOUT['default_height'],
                 max(0, int(work_height) - DESKTOP_LAYOUT['window_margin_y']))
    return max(1, min(width, int(work_width))), max(1, min(height, int(work_height)))


def _grab_popup(event,window):
    import tkinter as tk
    # <Map> 会沿 bindtags 冒泡：子 Label／Frame 映射时也会送到
    # Toplevel 的绑定。只能由窗口自身取得 grab，绝不能让子控件
    # 把整个应用的输入锁走。
    if getattr(event,'widget',None) is not window:
        return
    try:window.grab_set()
    except tk.TclError:pass


def _release_popup_on_unmap(event,window):
    import tkinter as tk
    # 隐藏以复用的窗口不应继续持有输入；同样只响应自身事件，避免
    # 子控件卸载时误释放仍可见窗口的 grab。
    if getattr(event,'widget',None) is not window:
        return
    try:window.grab_release()
    except tk.TclError:pass


def _focus_popup(window):

    """弹窗摆好之后把它点活（第 59 期第 13 条）。

    这些弹窗都是「置顶 ＋ 抓到手里」的（见上面的 grab_popup）：置顶窗在 Windows 上

    不会自动成为活动窗，用户的第一下点击只会被系统当成「点活这扇窗」——按钮于是要

    点两次才生效（用户报的「关闭按钮要点两次」就是这个）。三虎的云朵框早就单独补过

    这一下（pet_cloud 的 show → focus_force），这里把同一件事做给所有居中弹出的窗口。

    """

    try:window.focus_force()

    except Exception:app_logging.swallowed()


def _work_area(window,root):

    try:

        import ctypes

        from ctypes import wintypes

        class MONITORINFO(ctypes.Structure):

            _fields_=[('cbSize',wintypes.DWORD),('rcMonitor',wintypes.RECT),('rcWork',wintypes.RECT),('dwFlags',wintypes.DWORD)]

        api=ctypes.windll.user32

        api.MonitorFromWindow.argtypes=[wintypes.HWND,wintypes.DWORD]

        api.MonitorFromWindow.restype=wintypes.HANDLE

        api.GetMonitorInfoW.argtypes=[wintypes.HANDLE,ctypes.POINTER(MONITORINFO)]

        info=MONITORINFO();info.cbSize=ctypes.sizeof(info)

        monitor=api.MonitorFromWindow(window.winfo_id(),2)

        if api.GetMonitorInfoW(monitor,ctypes.byref(info)):

            r=info.rcWork;return r.left,r.top,r.right,r.bottom

    except (AttributeError,OSError):pass

    return 0,0,root.winfo_screenwidth(),root.winfo_screenheight()


def _cancel_position_job(window,event=None):
    """取消该窗口尚未执行的定位回调。

    ``after`` 挂在 Tcl 解释器上而不是控件上；窗口先销毁时，若 Python 闭包没有持有
    回调 id，Tcl 到时仍会尝试执行已被删除的命令并污染 stderr。回调 id 因此归窗口
    所有，且只绑定一次自身的 ``<Destroy>``，避免子控件销毁误取消定位。
    """
    if event is not None and getattr(event,'widget',None) is not window:
        return
    job=getattr(window,'_drama_place_job',None)
    if job is not None:
        try:window.after_cancel(job)
        except Exception:app_logging.swallowed()
    window._drama_place_job=None


def _fit_dialog(window,parent,width,height,limit):
    """弹窗首次尺寸：返回 ``(宽, 高, 是否自然尺寸)``，并设好缩放范围。

    主窗口仅约束首次尺寸；之后由用户自由缩放，不沿用业务页的固定尺寸。但不能小于内容的
    请求尺寸：业务页写死的「600x400」在高 DPI 下装不下表单，主窗口偏小时也会把弹窗裁短；
    只有工作区（``limit``）放不下时才让步。尺寸恰好等于自然尺寸（内容或声明的下限）时由
    调用方只摆位置不定尺寸，之后才加载的内容（如联网读回的设备列表）还能把窗口撑大。
    """
    minw,minh=window.minsize()
    reqw,reqh=window.winfo_reqwidth(),window.winfo_reqheight()
    width=max(min(width,parent.winfo_width()),min(reqw,limit[0]))
    height=max(min(height,parent.winfo_height()),min(reqh,limit[1]))
    natural=(width,height)==(max(reqw,minw),max(reqh,minh))
    window.resizable(True,True)
    # 弹窗不再被压到 1×1：未声明也至少保留 240×160 的内容下限。写死尺寸的弹窗之后可由用户
    # 随意缩小；自然尺寸的弹窗要靠声明过的下限撑住宽度，否则放开尺寸后会缩回内容宽。
    window.minsize(*((max(DIALOG_MIN_WIDTH,minw),max(DIALOG_MIN_HEIGHT,minh)) if natural
                     else (DIALOG_MIN_WIDTH,DIALOG_MIN_HEIGHT)))
    window.maxsize(window.winfo_vrootwidth(),window.winfo_vrootheight())
    return width,height,natural


def install_window_placement(root):

    """Center each window once; leave subsequent user moves alone."""

    import tkinter as tk

    if getattr(root,'_drama_place_enabled',False):return

    root._drama_place_enabled=True
    # Hide new application windows before their first native Map event.

    if not getattr(tk.Toplevel,'_drama_hidden_init',False):

        original_init=tk.Toplevel.__init__



        def hidden_init(window,*args,**kwargs):

            original_init(window,*args,**kwargs)

            try:rt=window._root()

            except Exception:rt=window.master

            if getattr(rt,'_drama_place_enabled',False):

                window.attributes('-alpha',0)

                # patched ``hidden_init`` retains callbacks for the app lifetime;
                # a one-off lambda can be deleted before a queued Map event runs.
                def grab_on_own_map(event,w=window):
                    _grab_popup(event,w)
                def release_on_own_unmap(event,w=window):
                    _release_popup_on_unmap(event,w)
                window._drama_grab_popup_callback=grab_on_own_map
                window._drama_release_popup_callback=release_on_own_unmap
                window.bind('<Map>',grab_on_own_map,add='+')
                window.bind('<Unmap>',release_on_own_unmap,add='+')

                # 第 8 轮（收口）：弹窗右上角那两颗「最小化 / 最大化」删掉了（用户点名要删）。
                # 第 65 期任务 5 曾在这一处给每个弹窗长出它们（全程序只此一处接线），第 67 期
                # 任务 1 又把三虎的云朵框单独摘过；现在这里什么都不长，弹窗只剩系统那颗 ×。

        tk.Toplevel.__init__=hidden_init

        tk.Toplevel._drama_hidden_init=True

    root.attributes('-alpha',0)



    def place(window,parent=None):

        if not window.winfo_exists():return

        # 主窗口的宽高由下面的工作区规则直接给出，不必先量自然尺寸；整壳布局只算一遍。
        if parent is not None:window.update_idletasks()

        left,top,right,bottom=_work_area(parent or window,root)

        width=min(window.winfo_width(),right-left-24)

        height=min(window.winfo_height(),bottom-top-48)

        natural=False
        if parent and not window.overrideredirect():
            window.transient(parent)
            width,height,natural=_fit_dialog(window,parent,width,height,(right-left-24,bottom-top-48))

        if parent is None:

            window.state('normal')

            width,height=main_window_size(right-left,bottom-top)

            minw,minh=window.minsize();window.minsize(min(minw,width),min(minh,height))

        if parent:

            x=parent.winfo_x()+(parent.winfo_width()-width)//2

            y=parent.winfo_y()+(parent.winfo_height()-height)//2

            if window.overrideredirect():window.transient(parent)

        else:x=left+(right-left-width)//2;y=top+(bottom-top-height)//2

        x=max(left,min(x,right-width));y=max(top,min(y,bottom-height))

        if natural:window.geometry('');window.geometry(f'+{x}+{y}')
        else:window.geometry(f'{width}x{height}+{x}+{y}')
        window.update_idletasks()
        # update_idletasks 只排完几何，不等于已经画过；alpha 直接回 1 时 Windows 可能先把
        # 未上色的窗口帧合成成一块黑。显形前强制同步重画一次，非 Windows 由 repaint_area 自己降级。
        from ui.desktop_layout_resize import repaint_area
        repaint_area(window)

        # 启动画面盖着主窗口时由启动器决定何时显形，这里只摆位置。
        if not getattr(window,'_drama_hold_alpha',False):window.attributes('-alpha',1);window.lift()

        if parent:_focus_popup(window)      # 第 59 期第 13 条：弹窗摆好就点活，不留一下“白点”给用户


    def schedule_place(window,parent=None):
        _cancel_position_job(window)
        if not getattr(window,'_drama_place_cancel_bound',False):
            # Keep the callback on the widget.  Tcl may dispatch a queued Destroy
            # event after this helper has returned; an unreferenced lambda would
            # then have been deleted from Tcl before the event is handled.
            def cancel_position_on_destroy(event, w=window):
                _cancel_position_job(w,event)
            window._drama_place_destroy_callback=cancel_position_on_destroy
            window.bind('<Destroy>',cancel_position_on_destroy,add='+')
            window._drama_place_cancel_bound=True

        def ready():
            window._drama_place_job=None
            try:
                if window.winfo_exists():
                    place(window,parent)
            except Exception as exc:
                # 已在 Map 时隐藏并取得输入的窗口，定位失败也必须恢复为
                # 可见且无 grab；否则会留下“看不见但点不动”的全局输入锁。
                try:window.attributes('-alpha',1)
                except tk.TclError:pass
                try:window.grab_release()
                except tk.TclError:pass
                notice=getattr(root,'_drama_place_notice',None)
                if callable(notice):
                    try:notice('窗口定位失败，已恢复交互：%s'% (str(exc) or '未知错误'))
                    except Exception:app_logging.swallowed()

        window._drama_place_job=window.after_idle(ready)

    def mapped(event):

        window=event.widget

        if not isinstance(window,tk.Toplevel) or getattr(window,'_positioned_once',False):return

        window._positioned_once=True

        schedule_place(window,root)

    root.bind_all('<Map>',mapped,add='+')

    schedule_place(root)



# ---- 日间／夜间切换后的存量控件换色 ----
# ttk 控件由样式表负责；这里只处理样式表够不着的原生 tk 控件（Canvas、Label、Text、
# Menu、Frame）和画布图元（三虎头像、爪印、齿轮等）。只替换与旧调色板某个值严格相等
# 的颜色，其余（插画、自定义色）原样保留。
_WIDGET_OPTIONS = ('bg', 'fg', 'highlightbackground', 'highlightcolor', 'activebackground',
                   'activeforeground', 'insertbackground', 'selectbackground',
                   'selectforeground', 'disabledforeground', 'troughcolor', 'selectcolor')
_ITEM_OPTIONS = ('fill', 'outline', 'activefill', 'activeoutline')
# 同一旧色对应多个键时按这个顺序取第一个：底色优先于装饰色。
_PRIORITY = ('background_card', 'background_primary', 'text_primary', 'text_secondary')


def color_map(old, new):
    """旧调色板 → 新调色板的 {旧色: 新色}（小写十六进制），旧色重复时按优先键取。"""
    mapping = {}
    keys = [k for k in _PRIORITY if k in old] + [k for k in old if k not in _PRIORITY]
    for key in keys:
        before, after = old.get(key), new.get(key)
        if not isinstance(before, str) or not isinstance(after, str):
            continue
        if not before.startswith('#') or not after.startswith('#'):
            continue
        mapping.setdefault(before.lower(), after)
    return {k: v for k, v in mapping.items() if k != v.lower()}


def _recolor_options(widget, options, mapping):
    for option in options:
        try:
            target = mapping.get(str(widget.cget(option)).lower())
            if target is not None:
                widget.configure(**{option: target})
        except tk.TclError:
            continue


def _recolor_canvas(canvas, mapping):
    try:
        items = canvas.find_all()
    except tk.TclError:
        return
    for item in items:
        for option in _ITEM_OPTIONS:
            try:
                target = mapping.get(str(canvas.itemcget(item, option)).lower())
                if target is not None:
                    canvas.itemconfigure(item, **{option: target})
            except tk.TclError:
                continue


def _recolor_text_tags(text, mapping):
    try:
        tags = text.tag_names()
    except tk.TclError:
        return
    for tag in tags:
        if tag == 'sel':  # Tk mirrors this tag to the selection widget options.
            continue
        for option in ('foreground', 'background', 'lmargincolor', 'rmargincolor'):
            try:
                target = mapping.get(str(text.tag_cget(tag, option)).lower())
                if target is not None:
                    text.tag_configure(tag, **{option: target})
            except tk.TclError:
                continue


def _treeview_tag_names(tree):
    """ttk.Treeview 已配置的 tag 名；旧 Tk 无 ``tag names`` 时从现有行反推。"""
    try:
        names = tree.tk.splitlist(tree.tk.call(tree._w, 'tag', 'names'))
        if names:
            return [str(name) for name in names]
    except (tk.TclError, AttributeError, TypeError):
        pass
    found = []
    seen = set()
    stack = list(tree.get_children(''))
    while stack:
        item = stack.pop()
        try:
            stack.extend(tree.get_children(item))
            for tag in tree.item(item, 'tags') or ():
                if tag not in seen:
                    seen.add(tag)
                    found.append(tag)
        except tk.TclError:
            continue
    return found


def _recolor_treeview_tags(tree, mapping):
    """Treeview 的行 tag 不走样式表；completed/hover 等显式颜色也要随主题换。"""
    for tag in _treeview_tag_names(tree):
        for option in ('background', 'foreground'):
            try:
                current = tree.tag_configure(tag, option)
                target = mapping.get(str(current).lower())
                if target is not None:
                    tree.tag_configure(tag, **{option: target})
            except tk.TclError:
                continue


def recolor_tree(root, old, new):
    """递归换色；返回处理过的控件数以便测试。"""
    mapping = color_map(old, new)
    if not mapping:
        return 0
    touched = 0
    stack = [root]
    while stack:
        widget = stack.pop()
        try:
            stack.extend(widget.winfo_children())
        except tk.TclError:
            continue
        if isinstance(widget, ttk.Treeview):
            _recolor_treeview_tags(widget, mapping)
        if isinstance(widget, ttk.Widget):
            # 显式赋给控件的颜色会覆盖主题样式，例如状态栏文本与进度说明。
            options = set(widget.keys()).intersection(('foreground', 'background'))
            _recolor_options(widget, options, mapping)
            continue
        if isinstance(widget, tk.Text):
            # 夜间正文与选区文字可以同色；按选项的语义映射才能正确切回日间。
            for option, token in (('selectforeground', 'selection_text'),
                                  ('selectbackground', 'selection_bg'),
                                  ('inactiveselectbackground', 'selection_bg'),
                                  ('insertbackground', 'text_primary')):
                _recolor_options(widget, (option,), {old[token].lower(): new[token]})
        _recolor_options(widget, _WIDGET_OPTIONS, mapping)
        if isinstance(widget, tk.Canvas):
            _recolor_canvas(widget, mapping)
        if isinstance(widget, tk.Text):
            _recolor_text_tags(widget, mapping)
            refresh = getattr(widget, "_refresh_tag_colors", None)
            if refresh is not None:
                refresh(widget)
        refresh_theme = getattr(widget, "_refresh_theme_colors", None)
        if refresh_theme is not None:
            refresh_theme(widget)
        touched += 1
    return touched


def refresh_native_widgets(win):
    """主题切换后：原生 tk 控件换色，侧栏／项目文件图标按新文字色重染。"""
    import ui_tokens
    from ui.ui_icons import retint_check_indicators, retint_nav_icons
    from ui.ui_rounded import retint_empty_icons
    previous = ui_tokens.previous_palette()
    recolor_tree(win, previous, COLORS)
    retint_empty_icons(win, color_map(previous, COLORS))
    refresh_menus()
    retint_nav_icons()
    retint_check_indicators()
