"""Shared lightweight pastel theme; no image downloads or animation loop."""

import app_logging
from tkinter import ttk
from ui_tokens import COLORS
from responsive_ui import row_height_for,font_linespace

FONT=('Microsoft YaHei UI',10)     # 全局字体（行高就按它量出来的一行算）

BG=COLORS['background_primary']

INK=COLORS['text_primary']

ACCENT=COLORS['primary']



def apply(win):

    win.configure(bg=BG)

    for pattern,value in {'*Text.background':COLORS['background_card'],'*Text.foreground':INK,

                          '*Text.insertBackground':ACCENT,'*Text.selectBackground':ACCENT,

                          '*Text.selectForeground':COLORS['background_card'],'*Text.inactiveSelectBackground':ACCENT,

                          '*Toplevel.background':BG,'*Menu.background':COLORS['background_card'],

                          '*Menu.foreground':INK}.items():win.option_add(pattern,value)

    s=ttk.Style(win);s.theme_use('clam')

    install_tick_indicators(win,s)

    s.configure('.',font=FONT,background=BG,foreground=INK)

    s.configure('TFrame',background=BG)

    s.configure('Card.TFrame',background=COLORS['background_card'])

    s.configure('TLabel',background=BG,foreground=INK)

    s.configure('Muted.TLabel',foreground=COLORS['text_secondary'])
    # 各设置页会随操作变化的说明统一用这一档：淡绿底区别于静态说明，
    # 但仍保持深色文字，长提示与错误提示都能清楚阅读。
    s.configure('PaleGreenHint.TLabel', background=COLORS['success_subtle'], foreground=COLORS['success_text'], padding=(8, 4))

    s.configure('TButton',font=('Microsoft YaHei UI',9),padding=(9,5),background=COLORS['secondary_bg'],foreground=COLORS['secondary_text'],borderwidth=0,focuscolor=ACCENT)

    s.map('TButton',background=[('disabled',COLORS['disabled_bg']),('pressed',COLORS['secondary_pressed']),('active',COLORS['secondary_hover'])],foreground=[('disabled',COLORS['disabled_text'])])

    s.configure('Compact.TButton',font=('Microsoft YaHei UI',9),padding=(6,4))
    s.configure('Send.TButton',font=('Microsoft YaHei UI',11,'bold'),padding=(10,4),background=ACCENT,foreground='white',borderwidth=0,focuscolor=ACCENT)
    s.map('Send.TButton',background=[('disabled',COLORS['secondary_bg']),('pressed',COLORS['primary_hover']),('active',COLORS['primary_hover'])],foreground=[('disabled',COLORS['disabled_text'])])

    s.configure('Selected.Compact.TButton',font=('Microsoft YaHei UI',9),padding=(7,4),background=ACCENT,foreground='white')

    s.map('Selected.Compact.TButton',background=[('active',COLORS['primary_hover'])],foreground=[('active','white')])

    s.configure('Asset.TButton',font=('Microsoft YaHei UI',10),padding=(14,8))

    s.map('Asset.TButton',background=[('disabled',COLORS['disabled_bg']),('pressed',COLORS['secondary_pressed']),('active',COLORS['secondary_hover'])],foreground=[('disabled',COLORS['disabled_text'])])

    s.configure('Primary.TButton',font=('Microsoft YaHei UI',11,'bold'),background=ACCENT,foreground='white',padding=(18,8),borderwidth=0,focuscolor=ACCENT)

    s.map('Primary.TButton',background=[('disabled',COLORS['disabled_bg']),('pressed',COLORS['primary_hover']),('active',COLORS['primary_hover'])],foreground=[('disabled',COLORS['disabled_text'])])

    # 「MCP 优化」是要花钱的那一步：用比主按钮更深一档的主色表示，不再使用橙色／琥珀色。
    s.configure('Highlight.TButton',font=('Microsoft YaHei UI',10,'bold'),background=COLORS['primary_pressed'],foreground='white',padding=(14,7),borderwidth=0,focuscolor=COLORS['focus'])
    s.map('Highlight.TButton',background=[('disabled',COLORS['disabled_bg']),('pressed',COLORS['primary_pressed']),('active',COLORS['primary_hover'])],foreground=[('disabled',COLORS['disabled_text'])])

    s.configure('Project.Treeview',rowheight=24)

    s.configure('Nav.TButton',anchor='w',background=BG,padding=(12,5))
    # 第 71 期任务 2：侧栏的二级入口（「05 资产管理」下面的「资产清单」）——左边留一截缩进，
    # 一眼看出它挂在上一格下面。
    s.configure('Sub.Nav.TButton',anchor='w',background=BG,padding=(26,4))
    s.configure('Selected.Sub.Nav.TButton',anchor='w',background=ACCENT,foreground='white',padding=(26,4))
    s.map('Selected.Sub.Nav.TButton',background=[('active',COLORS['primary_hover'])],foreground=[('active','white')])

    s.configure('Selected.Nav.TButton',background=ACCENT,foreground='white')

    s.map('Selected.Nav.TButton',background=[('active',COLORS['primary_hover'])],foreground=[('active','white')])

    s.configure('TEntry',fieldbackground='white',foreground=INK,padding=7)

    s.configure('TCombobox',fieldbackground='white',foreground=INK,padding=6)

    s.map('TCombobox',fieldbackground=[('readonly','white')],foreground=[('readonly',INK)])

    # 第 58 期第 2 条：内容框的行高按格子里最高的那点内容算。纯文字的表（剧本、
    # 分镜…）只需要一行字加一小截余地，不再写死 34；摆缩略图的那几张各自
    # 按自己的图高设（见 responsive_ui.fit_row_height）。
    s.configure('Treeview',rowheight=row_height_for(0,font_linespace(win,FONT)),background='white',fieldbackground='white',foreground=INK,borderwidth=0)

    s.configure('Treeview.Heading',background=COLORS['header_bg'],foreground=COLORS['text_heading'],padding=8)

    s.map('Treeview',background=[('selected',COLORS['selection_bg'])],foreground=[('selected',COLORS['selection_text'])])

    s.configure('TNotebook.Tab',padding=(14,9))

    s.configure('Horizontal.TProgressbar',background=COLORS['progress'],troughcolor=COLORS['trough'],borderwidth=0)

    s.configure('TLabelframe',background=BG,bordercolor=COLORS['border_strong'],relief='solid',borderwidth=1)

    s.configure('TLabelframe.Label',background=BG,foreground=COLORS['text_heading'])

    # 第 31 期第 4/5 条：空的 TLabelframe 仍会为标签留出约 19 像素——按钮行到内容框之间

    # 就多出一条空白。这条样式把「卡片」画在普通 Frame 上：边框与 TLabelframe 一致，

    # 但没有标签行，内容框能紧贴上面的按钮行。

    s.configure('Box.TFrame',background=BG,bordercolor=COLORS['border_strong'],relief='solid',borderwidth=1)

    from ui_tokens import (SCROLLBAR_ARROW, SCROLLBAR_BORDER_WIDTH, SCROLLBAR_THUMB,
                           SCROLLBAR_THUMB_ACTIVE, SCROLLBAR_TROUGH)
    for name in ('Vertical.TScrollbar', 'Horizontal.TScrollbar'):
        s.configure(name, background=SCROLLBAR_THUMB, troughcolor=SCROLLBAR_TROUGH,
                    arrowcolor=SCROLLBAR_ARROW, borderwidth=SCROLLBAR_BORDER_WIDTH)
        s.map(name, background=[('active', SCROLLBAR_THUMB_ACTIVE)])

    s.map('TEntry',bordercolor=[('focus',ACCENT)])

    s.map('TCheckbutton',background=[('active',BG)],foreground=[('disabled',COLORS['disabled_text'])])







def install_tick_indicators(win,style):

    """Use a tick for every themed checkbutton, retaining native input behavior."""

    from tkinter import font as tkfont
    from ui_icons import IconLoader

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

    name='DramaTick.indicator'

    if name not in style.element_names():

        style.element_create(name,'image',off,('disabled','selected',disabled_on),('disabled',disabled_off),('selected',on),border=0,sticky='')

    style.layout('TCheckbutton',[('Checkbutton.padding',{'sticky':'nswe','children':[

        (name,{'side':'left','sticky':''}),

        ('Checkbutton.focus',{'side':'left','sticky':'w','children':[('Checkbutton.label',{'sticky':'nswe'})]})]})])

    style.configure('TCheckbutton',padding=(2,3),background=BG,foreground=INK)





# ── 第 8 轮（收口）：弹窗右上角那两颗「最小化／最大化」撤掉 ─────────────────────
# 第 65 期任务 5 在 install_window_placement 的 hidden_init 里给每个弹窗长出那两颗键，
# 第 67 期任务 1 又把三虎的云朵框单独摘掉。用户这次定的口径就是删：全程序不再画那两颗键，
# 画键的代码与那一处接线一并删掉，弹窗右上角只剩系统那颗 ×（弹窗照旧居中、抓取与置顶）。


def install_window_placement(root):

    """Center each window once; leave subsequent user moves alone."""

    import tkinter as tk

    if getattr(root,'_drama_place_enabled',False):return

    root._drama_place_enabled=True

    # Hide new application windows before their first native Map event.

    if not getattr(tk.Toplevel,'_drama_hidden_init',False):

        original_init=tk.Toplevel.__init__

        def grab_popup(event,window):
            # <Map> 会沿 bindtags 冒泡：子 Label／Frame 映射时也会送到
            # Toplevel 的绑定。只能由窗口自身取得 grab，绝不能让子控件
            # 把整个应用的输入锁走。
            if getattr(event,'widget',None) is not window:
                return
            try:window.grab_set()
            except tk.TclError:pass

        def release_popup_on_unmap(event,window):
            # 隐藏以复用的窗口不应继续持有输入；同样只响应自身事件，避免
            # 子控件卸载时误释放仍可见窗口的 grab。
            if getattr(event,'widget',None) is not window:
                return
            try:window.grab_release()
            except tk.TclError:pass

        def hidden_init(window,*args,**kwargs):

            original_init(window,*args,**kwargs)

            try:rt=window._root()

            except Exception:rt=window.master

            if getattr(rt,'_drama_place_enabled',False):

                window.attributes('-alpha',0)

                # patched ``hidden_init`` retains callbacks for the app lifetime;
                # a one-off lambda can be deleted before a queued Map event runs.
                def grab_on_own_map(event,w=window):
                    grab_popup(event,w)
                def release_on_own_unmap(event,w=window):
                    release_popup_on_unmap(event,w)
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

    def focus_popup(window):

        """弹窗摆好之后把它点活（第 59 期第 13 条）。

        这些弹窗都是「置顶 ＋ 抓到手里」的（见上面的 grab_popup）：置顶窗在 Windows 上

        不会自动成为活动窗，用户的第一下点击只会被系统当成「点活这扇窗」——按钮于是要

        点两次才生效（用户报的「关闭按钮要点两次」就是这个）。三虎的云朵框早就单独补过

        这一下（pet_cloud 的 show → focus_force），这里把同一件事做给所有居中弹出的窗口。

        """

        try:window.focus_force()

        except Exception:app_logging.swallowed()

    def work_area(window):

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

    def place(window,parent=None):

        if not window.winfo_exists():return

        # 主窗口的宽高由下面的工作区规则直接给出，不必先量自然尺寸；整壳布局只算一遍。
        if parent is not None:window.update_idletasks()

        left,top,right,bottom=work_area(parent or window)

        width=min(window.winfo_width(),right-left-24)

        height=min(window.winfo_height(),bottom-top-48)

        if parent and not window.overrideredirect():
            window.transient(parent)
            # 主窗口仅约束首次尺寸；之后由用户自由缩放，不沿用业务页的固定尺寸。
            width=min(width,parent.winfo_width())
            height=min(height,parent.winfo_height())
            window.resizable(True,True)
            window.minsize(1,1)
            window.maxsize(window.winfo_vrootwidth(),window.winfo_vrootheight())

        if parent is None:

            window.state('normal')

            width=min(1080,int((right-left)*0.80));height=min(740,int((bottom-top)*0.80))

        minw,minh=window.minsize();window.minsize(min(minw,width),min(minh,height))

        if parent:

            x=parent.winfo_rootx()+(parent.winfo_width()-width)//2

            y=parent.winfo_rooty()+(parent.winfo_height()-height)//2

            if window.overrideredirect():window.transient(parent)

        else:x=left+(right-left-width)//2;y=top+(bottom-top-height)//2

        x=max(left,min(x,right-width));y=max(top,min(y,bottom-height))

        window.geometry(f'{width}x{height}+{x}+{y}');window.update_idletasks()

        # 启动画面盖着主窗口时由启动器决定何时显形，这里只摆位置。
        if not getattr(window,'_drama_hold_alpha',False):window.attributes('-alpha',1);window.lift()

        if parent:focus_popup(window)      # 第 59 期第 13 条：弹窗摆好就点活，不留一下“白点”给用户

    def cancel_position_job(window,event=None):
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

    def schedule_place(window,parent=None):
        cancel_position_job(window)
        if not getattr(window,'_drama_place_cancel_bound',False):
            # Keep the callback on the widget.  Tcl may dispatch a queued Destroy
            # event after this helper has returned; an unreferenced lambda would
            # then have been deleted from Tcl before the event is handled.
            def cancel_position_on_destroy(event, w=window):
                cancel_position_job(w,event)
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
