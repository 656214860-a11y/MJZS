"""桌面布局与滚动（从 desktop.Desktop 原样迁出，SPLITD 结构治理轮）。

方法体未改、self 语义不变；Desktop 通过继承 LayoutMixin 获得。仍与 Tk 控件紧耦合，
故与 desktop 同属 L4。
"""
import infra.app_logging as app_logging
import logging
import tkinter as tk
from tkinter import ttk

import ui.pet_ui as pet_ui
from ui.desktop_layout_resize import PaintFreeze, ResizeCoalescer, repaint_area
from ui.desktop_page_registry import PAGE
from responsive_ui import growable_extra
from ui.ui_scroll import eased_scroll
from ui_tokens import (CONTROL_PADDING_Y, DESKTOP_LAYOUT, FONTS, NAV_PADDING_X, NAV_PADDING_Y,
                       NAV_PADDING_Y_COMPACT, NAV_ROW_HEIGHT, NAV_ROW_HEIGHT_COMPACT, NAV_SUB_PADDING_X, SPACING)
from ui.ui_rounded import set_button_padding

LOGGER=logging.getLogger('desktop_layout')

# 聊天记录框（idea_log）滚轮加速：一条消息通常跨多行，滚一格只走 1 行太慢，按行数放大步长。
IDEA_LOG_WHEEL_LINES = 5


class LayoutMixin:
    # R3025：首帧布局收敛前为 False；thaw_page_paint 首次调用时置 True（实例属性），
    # pet 动画/侧栏补排等周期工作据此避开首帧争用窗。类属性只作缺省，唯一写者是 thaw。
    _first_paint_settled=False
    def _join_resize(self,apply,event=None):
        """拖动改窗口期间把这次重排并进松手后的补做；返回 True 表示这次不必立即做。"""
        coalescer=getattr(self,'resize_scheduler',None)
        if coalescer is None or event is None:return False
        return coalescer.schedule(apply,event=event)
    def cancel_resize(self):
        coalescer=getattr(self,'resize_scheduler',None)
        if coalescer is not None:coalescer.cancel()
        self.thaw_page_paint()
    def freeze_page_paint(self):
        """换页开始：冻结内容区绘制，旧页留在屏幕上，等新页布局稳定后一次画出（见 PaintFreeze）。"""
        freezer=getattr(self,'_page_paint_freeze',None)
        if freezer is None:
            canvas=getattr(self,'canvas',None)
            if canvas is None:return False
            freezer=self._page_paint_freeze=PaintFreeze(canvas)
        if getattr(self,'_sidebar_before_page',None) is None:
            self._sidebar_before_page=self._sidebar_geometry()
        return freezer.freeze()
    def thaw_page_paint(self):
        freezer=getattr(self,'_page_paint_freeze',None)
        thawed=freezer.thaw() if freezer is not None else False
        # R3025：首次布局收敛=首帧落定；pet 动画、侧栏补排等周期工作据此放行，
        # 不再与首帧窗内的布局轮次争事件循环。只置一次，后续换页不重置。
        if not getattr(self,'_first_paint_settled',False):
            self._first_paint_settled=True
        self._settle_sidebar_paint()
        return thawed
    def _sidebar_geometry(self):
        """侧栏会挪动导航行的几个量：滚动位置、滚动区、末行纵坐标、项目列表行数与表头间距。"""
        canvas=getattr(self,'sidebar_canvas',None)
        nav=getattr(self,'nav',None)
        if canvas is None or not nav:return ()
        try:
            return (tuple(round(v,4) for v in canvas.yview()),str(canvas.cget('scrollregion')),
                    nav[-1].winfo_y(),len(getattr(self,'_picker_items',())))
        except tk.TclError:
            return ()
    def _settle_sidebar_paint(self):
        """换页落定：侧栏整块擦底重画一次，清掉导航行挪位后空隙里的旧文字；几何真变了记一条日志。"""
        before=getattr(self,'_sidebar_before_page',None)
        if before is None:return
        self._sidebar_before_page=None
        after=self._sidebar_geometry()
        if before!=after:
            LOGGER.info('换页时侧栏几何变化 前=%s 后=%s',before,after)
        canvas=getattr(self,'sidebar_canvas',None)
        if canvas is not None:repaint_area(canvas)
    def watch_window_resize(self,win):
        """主窗口／页面画布／内容框的尺寸变化统一经合并器；子控件变化照旧立即处理。"""
        self.resize_scheduler=ResizeCoalescer(win,freeze=self._freeze_content,thaw=self._thaw_content)
        for widget in (win,self.canvas,self.content):
            widget.bind('<Configure>',self._on_resize_configure,add='+')
    def _freeze_content(self):
        """拖外框期间收起页面内容与侧栏内容，只画外层框架（标题栏、进度条、状态栏）；松手后放回。"""
        self.canvas.itemconfigure(self.content_id,state='hidden')
        side=getattr(self,'sidebar_scroll',None)
        if side is not None:side.canvas.itemconfigure(side.window_id,state='hidden')
    def _thaw_content(self):
        self.canvas.itemconfigure(self.content_id,state='normal')
        side=getattr(self,'sidebar_scroll',None)
        if side is not None:side.canvas.itemconfigure(side.window_id,state='normal')
    def _own_content_configure(self,event):
        """布局刚把内容框设成这个尺寸：同尺寸 <Configure> 是自己写出的几何，不是外部变化。"""
        if event is None or getattr(event,'widget',None) is not getattr(self,'_content_applied_widget',None):return False
        return (event.width,event.height)==getattr(self,'_content_applied_size',None)
    def _on_resize_configure(self,event=None):
        """尺寸变了：拖动期间只登记一次整页补做，其余场景照旧立即重排。

        绑在顶层窗口上的 <Configure> 也会经 bindtags 收到所有后代控件的尺寸事件；
        只有本页画布／内容框自身的尺寸变化才重排，子控件变化交给原绑定处理。
        """
        if event is not None and getattr(event,'widget',None) not in (None,self.win,self.canvas,self.content):return
        if self._own_content_configure(event):return
        if event is not None and getattr(event,'widget',None) is self.win:
            # 移动窗口也发 Configure；只有宽高真的变了才重排。
            size=(event.width,event.height)
            if getattr(self,'_last_window_size',None)==size:return
            self._last_window_size=size
        if self._join_resize(self._layout_all,event):return
        self.fit_content()
    def schedule_sidebar_fit(self,event=None):
        # 拖动改窗口期间保持稳定：侧栏行数、表头对齐都并进松手后的那一次整页重排。
        if self._join_resize(self._layout_all,event):return
        if getattr(self,'_sidebar_fit_job',None) is not None:return
        def run():
            self._sidebar_fit_job=None
            # R3025：首帧收敛前空转重排——此时每轮 _fit_content_now 已在做
            # align_header，侧栏补排纯属重复劳动；收敛后下一次 Configure 自然接管。
            if not getattr(self,'_first_paint_settled',True):
                try:self._sidebar_fit_job=self.win.after_idle(run)
                except tk.TclError:self._sidebar_fit_job=None
                return
            self.fit_sidebar()
        self._sidebar_fit_job=self.win.after_idle(run)
    def fit_sidebar(self,event=None):
        viewport=getattr(self,'sidebar_canvas',self.sidebar)
        compact=viewport.winfo_height()<DESKTOP_LAYOUT['compact_below']
        style=ttk.Style(self.win)
        font=FONTS['pet_body'] if compact else FONTS['body']
        row_height=NAV_ROW_HEIGHT_COMPACT if compact else NAV_ROW_HEIGHT
        if self.sidebar_size!=compact:
            self.sidebar_size=compact
            pad_y=NAV_PADDING_Y_COMPACT if compact else NAV_PADDING_Y
            for name in ('Compact.TButton','Selected.Compact.TButton'):
                set_button_padding(style,name,(NAV_PADDING_X,pad_y),font=font)
            # 图标轨（R2897）：编号+图标左对齐，锁标也放得下；纯图标小按钮用更小内边距。
            for name in ('Nav.TButton','Selected.Nav.TButton','RailIcon.TButton','Selected.RailIcon.TButton'):
                set_button_padding(style,name,(SPACING['xs'],pad_y),font=font)
            for name in ('Sub.Nav.TButton','Selected.Sub.Nav.TButton'):
                set_button_padding(style,name,(NAV_SUB_PADDING_X,pad_y),font=font)
            # 项目动作与全局控件同高（36px）：横向沿用侧栏紧凑内边距，纵向取控件标准内边距；
            # 只有矮窗口（compact）才收到 4px 刻度，把空间让给导航行。
            set_button_padding(style,'ProjectAction.TButton',
                               (DESKTOP_LAYOUT['project_button_padding'][0],SPACING['xs'] if compact else CONTROL_PADDING_Y),font=font)
            style.configure('Project.Treeview',font=font,rowheight=row_height)
        self.align_header()
    def align_header(self,event=None):
        """页头对齐（第 R2950 期建，R3016 P2 收编）：顶部标题行已删，标题行高度与
        用量块左沿对齐逻辑随之移除；pet_dock 高度仍跟三虎簇正方形边长（patch_room）走。"""
        pet=getattr(self,'pet',None)
        pet_room=getattr(pet,'patch_room',None)
        dock=getattr(self,'pet_dock',None)
        if dock is not None:
            room=max(pet_ui.DOCK_ROOM,int(pet_room or pet_ui.DOCK_ROOM))
            if int(dock.cget('height'))!=room:dock.configure(height=room)
    def fit_content(self,event=None):
        # 尺寸事件落在拖动期间：并进松手后的补做。主动调用（页面切换、最小化恢复）
        # 不带事件，保持原来的同步 after_idle 语义，不受静默影响。
        if self._own_content_configure(event):return
        if event is not None and self._join_resize(self._layout_all,event):return
        self._apply_layout()
    def _layout_all(self):
        """松手补做：内容高度、侧栏行数、表头一次排好，结果与改前同尺寸一致。"""
        if getattr(self,'shutting_down',False):return
        self._apply_layout()
        self.fit_sidebar()
        self.align_header()
    def _apply_layout(self):
        """等同改前 fit_content 的重算主体。"""
        if getattr(self,'_fit_pending',False):
            self._fit_again=True
            return
        self._fit_pending=True
        def run():
            self._fit_job=None
            self._fit_pending=False
            # R2990：每跑完一轮整页布局记一次；page.paint 用它拆「等布局 vs 建页/其它」。
            self._layout_pass_count=getattr(self,'_layout_pass_count',0)+1
            layout_key=None
            try:layout_key=self._fit_content_now()
            except Exception:app_logging.swallowed()
            # R3018：pending 期间到达的重复 fit_content 不再无条件补排——本轮
            # _fit_content_now 已按最新几何计算，签名没变时重排结果必然相同；
            # 真实变化由下方请求尺寸签名稳定性检查兜底（上限仍是 8 轮）。
            if getattr(self,'_fit_again',False):
                self._fit_again=False
                app_logging.count('layout.fit_again.suppressed',1)
            # Canvas 固定内容高度后，子控件请求高度变化不再触发内容框 Configure。
            # 沿现有空闲队列等请求尺寸逐层传播；最多补八轮，避免异常布局反复排队。
            # 子控件请求尺寸会逐层传播；总高相同也不代表后代请求已稳定。
            # 用完整请求签名判断收敛，避免自身 Configure 被抑制后留下旧滚动边界。
            signature=getattr(self,'_fit_request_signature',layout_key)
            changed=signature!=getattr(self,'_last_fit_request_signature',None)
            self._last_fit_request_signature=signature
            passes=getattr(self,'_fit_stability_passes',0)
            if changed and passes<8:
                self._fit_stability_passes=passes+1
                app_logging.count('layout.repass.stability',1)
                self._relayout()
                return
            self._fit_stability_passes=0
            pending_scroll=getattr(self,'_pending_scroll_restore',None)
            if pending_scroll is not None:
                if getattr(self,'_pending_scroll_layout',None)!=layout_key:
                    self._pending_scroll_layout=layout_key
                    self.fit_content()
                    return
                self._pending_scroll_restore=None
                self._pending_scroll_layout=None
                self.restore_scroll(pending_scroll)
            # 尺寸与滚动位置都定了：换页时冻住的内容区这会儿一次画出。
            self.thaw_page_paint()
        try:self._fit_job=self.win.after_idle(run)
        except tk.TclError:
            self._fit_job=None
            self._fit_pending=False
    def _relayout(self):
        """补算一次整页：拖动期间并入静默补做，其余情况照旧立即排队。"""
        coalescer=getattr(self,'resize_scheduler',None)
        if coalescer is not None and coalescer.schedule(self._layout_all):return
        self._apply_layout()
    def _fit_content_now(self):
        width=max(1,self.canvas.winfo_width());height=max(1,self.canvas.winfo_height())
        req=self.content.winfo_reqheight()
        req_min=max(1,req-growable_extra())
        target=max(height,req_min)
        self.canvas.itemconfigure(self.content_id,width=width,height=target)
        self._content_applied_widget=self.content;self._content_applied_size=(width,target)
        # 滚动区域就是内容实际高度：内容框（Treeview）会长到填满窗口，若按请求高度
        # 记录滚动区域，窗口缩小时会残留旧高度，底部按钮可能被滚出可视区。
        self.canvas.configure(scrollregion=(0,0,width,target))
        if hasattr(self,'status_label'):self.status_label.configure(wraplength=max(200,width-12))
        # 页面重建（切换分镜、刷新列表）会产生新控件，必须每次重新补挂滚轮标签：
        # 漏挂标签时滚轮会落到控件自身的绑定上，只读下拉框会直接换选项并重建整页，
        # 表现出来就是「滚轮滑过下拉框，文件被切换，内容抖动」。
        measured_requests=[]
        def resize(widget):
            for child in widget.winfo_children():
                tags=child.bindtags()
                if 'DramaPageWheel' not in tags:child.bindtags(('DramaPageWheel',)+tags)
                if isinstance(child,ttk.Label) and not getattr(child,'local_wrap',False):
                    wrap=int(child.cget('wraplength') or 0)
                    if wrap>0 and wrap!=max(200,width-28):child.configure(wraplength=max(200,width-28))
                measured_requests.append((str(child),child.winfo_reqwidth(),child.winfo_reqheight()))
                resize(child)
        resize(self.content)
        if self.page_index==PAGE['script'] and hasattr(self,'_fit_talk'):
            self._fit_talk()
        self._fit_request_signature=(width,req,target,tuple(measured_requests))
        # 缓存页会替换 content，且等宽标题切换不会触发 Configure。
        # 在当前页几何收敛时统一刷新，不沿用上一页的聊天内边距。
        self.align_header()
        return (width,req,target)
    def wheel_steps(self,event):
        delta=getattr(event,'delta',0)
        if not delta:return 0
        return -max(1,abs(int(delta/120))) if delta>0 else max(1,abs(int(delta/120)))
    def popdown_listbox(self,widget):
        """下拉框展开时返回弹出的列表控件路径；未展开时返回 None。

        Tk 直接创建的下拉列表只会在事件里给出路径字符串，所以这里同时接受控件和路径。
        """
        path=str(widget)
        if '.popdown' in path:
            target=path.split('.popdown')[0]+'.popdown.f.l'
        elif isinstance(widget,ttk.Combobox):
            try:target=str(self.win.tk.call('ttk::combobox::PopdownWindow',path))+'.f.l'
            except tk.TclError:return None
        else:return None
        try:
            if not self.win.tk.call('winfo','exists',target):return None
            if not self.win.tk.call('winfo','ismapped',target):return None
        except tk.TclError:return None
        return target
    def native_wheel(self,widget):
        """Tk 自建控件（下拉列表、滚动条）是否已有类级滚轮绑定：有就不要再滚一次。"""
        try:
            name=self.win.tk.call('winfo','class',widget)
            return bool(self.win.tk.call('bind',name,'<MouseWheel>'))
        except tk.TclError:return False
    def clear_hover(self,widget):
        """滚轮滚动内容框后清掉悬停高亮：高亮是按旧坐标浮在表格上的，不跟着滚动就会停在错行上。"""
        hover=getattr(widget,'cell_hover',None)
        if hover is None:return
        try:hover.clear()
        except tk.TclError:pass
    def _inside_path(self,widget,ancestor):
        """控件是否就是 ancestor 或在其下；不能只比字符串前缀（.!frame 会误吞 .!frame2）。"""
        try:path=str(widget);base=str(ancestor)
        except tk.TclError:return False
        return bool(path) and (path==base or path.startswith(base+'.'))
    def scroll_page(self,event):
        widget=event.widget
        if not isinstance(widget,str):
            # 控件自带 Ctrl+滚轮缩放（如剧本正文）：交给控件处理，不走页面滚动。
            zoom=getattr(widget,'_ctrl_wheel_zoom',None)
            if zoom is not None and event.state & 0x4 and getattr(event,'delta',0):
                zoom(1 if event.delta>0 else -1)
                return 'break'
        steps=self.wheel_steps(event)
        if isinstance(widget,str):
            # 下拉框弹出的列表／滚动条由 Tk 自己创建，事件里拿到的是路径字符串。
            target=self.popdown_listbox(widget)
            if not target:return
            try:
                # Listbox／TScrollbar 的类绑定已经滚过它；再滚一次一次跳两倍，看起来就是内容抖动。
                if not self.native_wheel(widget):self.win.tk.call(target,'yview','scroll',steps,'units')
            except tk.TclError:pass
            return 'break'

        # 下拉框展开时滚轮只滚弹出的列表：既不换选项，也不重建页面；任何窗口都适用。
        target=self.popdown_listbox(widget)
        if target and steps:
            self.win.tk.call(target,'yview','scroll',steps,'units')
            return 'break'
        if widget.winfo_toplevel()!=self.win:return
        if self._inside_path(widget,getattr(self,'sidebar_viewport',self.sidebar)):
            if steps and not self.native_wheel(widget):eased_scroll(self.sidebar_canvas,steps)
            return 'break'
        if not steps:return 'break'
        # This bindtag runs before native widget bindings, so one wheel event
        # moves either the hovered editor/table or the surrounding page once.
        while widget is not self.content and widget is not self.win:
            if isinstance(widget,(tk.Text,tk.Listbox,ttk.Treeview)):
                top,bottom=widget.yview()
                if (steps<0 and top>0.000001) or (steps>0 and bottom<0.999999):
                    # 聊天记录框滚轮加速：气泡消息跨多行，一格 1 行太慢，按 IDEA_LOG_WHEEL_LINES 放大。
                    if widget is getattr(self,'idea_log',None):
                        widget.yview_scroll(steps*IDEA_LOG_WHEEL_LINES,'units')
                    else:
                        widget.yview_scroll(steps,'units')
                    self.clear_hover(widget);return 'break'
            widget=getattr(widget,'master',self.win)
            if widget is None:break
        eased_scroll(self.canvas,steps)
        return 'break'
    def _page_scroll_target(self,widget=None):
        focus=self.win.focus_get() if widget is None else widget
        if focus is not None:
            try:path=str(focus)
            except tk.TclError:path=''
            if path and self._inside_path(focus,self.sidebar_viewport):
                return self.sidebar_canvas
        return self.canvas
    def page_shortcut(self,event):
        """Ctrl+1…9／Ctrl+0 跳到第 1…10 页，Ctrl+PageUp／PageDown 前后翻页。

        与侧栏点击走同一个入口 go_page；文本框里的 Ctrl+数字照样交给文本框。
        """
        focus=self.win.focus_get()
        try:klass=focus.winfo_class() if focus is not None else ''
        except tk.TclError:klass=''
        if klass in ('Text','Entry','TEntry','Spinbox','TSpinbox'):return None
        count=len(getattr(self,'nav',()) or ())
        key=event.keysym
        current=getattr(self,'page_index',None)
        if key in ('Prior','Next'):
            if current is None or not count:return None
            index=(current+(-1 if key=='Prior' else 1))%count
        elif key.isdigit():
            index=(int(key)-1)%10
        else:return None
        if not 0<=index<count:return None
        self.go_page(index)
        return 'break'
    def scroll_page_key(self,event):
        """PageUp／PageDown／Home／End 翻主内容或侧栏，文本框与表格保留自己的按键。"""
        owned=('Text','Entry','Spinbox','TEntry','TCombobox','TSpinbox','Listbox','Treeview')
        focus=self.win.focus_get();receiver=getattr(event,'widget',None)
        # 按键事件先认实际接收控件；真实键盘输入时它就是焦点控件。
        widgets=(receiver,focus) if receiver is not None else (focus,)
        for widget in widgets:
            if widget is None:continue
            try:klass=widget.winfo_class()
            except tk.TclError:klass=''
            if klass in owned:return None
        target=self._page_scroll_target(receiver if receiver is not None else focus);key=event.keysym
        if key=='Prior':target.yview_scroll(-1,'pages')
        elif key=='Next':target.yview_scroll(1,'pages')
        elif key=='Home':target.yview_moveto(0)
        elif key=='End':target.yview_moveto(1)
        else:return None
        return 'break'
    def on_window_map(self,event=None):
        """主窗口从最小化恢复后，重新排定整页滚动范围。"""
        # 最小化恢复属于非拖动场景：撤销挂起的拖动合并，立即重排。
        # 只认顶层窗口自己的 <Map>：后代控件映射也会经 bindtags 冒到这里，
        # 内容区冻结/解冻引发的整批 <Map> 若在此撤销合并，拖动补做必然丢失。
        if event is not None and event.widget is not self.win:return
        coalescer=getattr(self,'resize_scheduler',None)
        if coalescer is not None:coalescer.flush()
        if getattr(self,'shutting_down',False):return
        self.fit_content()
