"""Shared, lazy project workspace. Standard-library-only desktop UI."""
import app_logging
from desktop_idea_menus import IdeaMenusMixin
from desktop_asset_pages import AssetPagesMixin
from desktop_script_pages import ScriptPagesMixin
from desktop_media_pages import MediaPagesMixin
from desktop_project_pages import ProjectPagesMixin
from desktop_storyboard_page import StoryboardPageMixin
from desktop_writing_page import WritingPageMixin, TALK_MIN_LINES, TALK_MAX_LINES
from desktop_page_support import ASSET_FIRST_ROWS, ASSET_ROWS_PER_FRAME, ASSET_ROW_LABEL, STAGE_ACTION_WIDTH, _prefs, bind_host, THUMB_SIZE, ASSET_ROW_HEIGHT
from desktop_idea_chat import IdeaChatMixin, IDEA_FIELDS, BUBBLE_FLOOR, BUBBLE_LINE, BUBBLE_MAX_RATIO, script_raw_saved_notice, model_error_display
from desktop_auto_flows import AutoFlowsMixin, UNATTENDED_NEXT, UNATTENDED_BACKOFF_FLOOR, ASSET_RETRY_LIMIT
import os, shutil, queue, threading, subprocess, sys, time, uuid, hashlib, re, json, logging
from datetime import date
from pathlib import Path
from file_cache import remove_temporary_file
from storyboard_paths import media_root
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from agent.core import read,save,save_text,save_bytes
import project_settings
from projects import Projects, needs_cleanup_after_open_error, is_missing_storyboard_open_error
from responsive_ui import FlowBar,growable_extra,configure_check_column,refresh_check_heading,CheckboxColumn,fit_columns_by_content,auto_columns,bind_row_toggle,fit_row_height,row_height_for,bind_show_all
from engine import approved_versions, review_label, adoption_summary
from local_video import open_studio,skip_summary
from app import App
from integrations import comfy_executable
from ui_theme import apply as apply_theme, install_window_placement
from project_naming import dated_path
import asset_thumbs
import asset_resume
import frame_checks
import pet_ui
import project_stages
import ui_plugin_registry
import stage_handler_registry
from platform_tools import find_editor_shortcut, launch_windows_app, open_directory, open_path, open_target, tcp_listener
from desktop_startup_service import DesktopStartupController
from desktop_automation_service import BackgroundTaskLifecycle, DesktopAutomationScheduler, BackgroundTaskQueue, PersistentBackgroundTaskQueue, inspect_project_storage, RetryRegistry
from idea_chat_controller import IdeaChatController, speaker_name
from ui_tokens import COLORS, FONTS, SPACING, DESKTOP_LAYOUT, SCRIPT_ACTION_WIDTH, SCRIPT_ACTION_PADDING, SCRIPT_FILE_FONT, ICON_FOLDER, ICON_DELETE
from ui_dialogs import FileDialog
from ui_shortcuts import ShortcutRegistry
from ui_widgets import (SelectBox, BaseDialog, BusyState, ContextMenu, Card, DataTable, NotificationDispatcher,
                        PrimaryButton, SecondaryButton, TextArea, HintLabel, Tooltip, TreeRowTooltip, EllipsisLabel, ask_confirmation, setup_styles)

ROOT=Path(__file__).resolve().parent
LOGGER=logging.getLogger(__name__)


def confirm(parent, title, message, *, dangerous=False, **_legacy_options):
    """桌面历史确认框的统一同步适配器，忽略系统 messagebox 专属视觉参数。"""
    return ask_confirmation(parent, title, message, dangerous=dangerous)





def confirm_project_removal_from_last_script(parent, files):
    """红色破坏性确认：删掉最后剧本时，用户必须明确同意删除整个项目。"""
    names='\n'.join(str(name) for name in files)
    win=BaseDialog(parent, '危险操作：删除当前项目', modal=False, chrome=False)
    win.resizable(False,False)
    border=tk.Frame(win,bg=COLORS['danger'],padx=2,pady=2);border.pack(fill='both',expand=True)
    body=tk.Frame(border,bg=COLORS['danger_subtle'],padx=22,pady=18);body.pack(fill='both',expand=True)
    tk.Label(body,text='⚠ 将删除当前项目',bg=COLORS['danger_subtle'],fg=COLORS['danger_hover'],
             font=('Microsoft YaHei UI',15,'bold')).pack(anchor='w')
    tk.Label(body,text='这是最后一份剧本。继续后会将当前项目及其全部素材移入项目库回收站。',
             bg=COLORS['danger_subtle'],fg=COLORS['danger_text'],justify='left',wraplength=500,
             font=('Microsoft YaHei UI',10)).pack(anchor='w',pady=(10,5))
    tk.Label(body,text=names,bg=COLORS['danger_subtle'],fg=COLORS['danger_text'],justify='left',wraplength=500).pack(anchor='w')
    result={'accepted':False}
    buttons=tk.Frame(body,bg=COLORS['danger_subtle']);buttons.pack(anchor='e',fill='x',pady=(18,0))
    def close(accepted=False):
        result['accepted']=accepted
        try:win.grab_release()
        except tk.TclError:pass
        win.destroy()
    SecondaryButton(buttons,text='取消',command=close,width=10).pack(side='right')
    PrimaryButton(buttons,text='移入回收站',command=lambda:close(True),width=11,
                  style='Tokens.Danger.TButton').pack(side='right',padx=(SPACING['none'],SPACING['sm']))
    win.protocol('WM_DELETE_WINDOW',close)
    win.update_idletasks()
    x=max(0,parent.winfo_rootx()+(parent.winfo_width()-win.winfo_width())//2)
    y=max(0,parent.winfo_rooty()+(parent.winfo_height()-win.winfo_height())//2)
    win.geometry('+%d+%d'%(x,y))
    win.grab_set()
    parent.wait_window(win)
    return result['accepted']


def protect_readonly_combobox(win):
    """只读下拉框不再被滚轮改选。

    Tk 8.6 的 TCombobox <MouseWheel> 绑定会调用 ttk::combobox::Scroll 直接换选项；
    落在只读下拉框上时表现为「滚轮滑过选择分镜，文件被切换，整页重建抖动」。
    这里给 ttk::combobox::Scroll 加一层只读／禁用判断，全局生效，可编辑下拉框不受影响。
    """
    try:
        # 注意：Tcl 的 0/1 是字符串，'0' 在 Python 里为真，必须显式比较。
        if win.tk.eval('info exists ::dramaComboWheelGuard')=='1':return
        if not win.tk.eval('info commands ::ttk::combobox::Scroll'):return
        # 改名必须留在同一命名空间：原过程内部调用 SelectEntry 等非限定名命令。
        win.tk.eval('rename ::ttk::combobox::Scroll ::ttk::combobox::ScrollOriginal')
        win.tk.eval('proc ::ttk::combobox::Scroll {cb dir} {'
                    ' if {[$cb instate readonly] || [$cb instate disabled]} { return };'
                    ' ::ttk::combobox::ScrollOriginal $cb $dir }')
        win.tk.eval('set ::dramaComboWheelGuard 1')
    except Exception:app_logging.swallowed()
_PENDING_TK_GC = []        # worker 线程里被回收的 Tk 对象，等主线程释放
_KEEP_APPS = []            # 解释器句柄：Tcl 的 async handler 只能在主线程析构（否则进程直接中止）

def _pin_tk_app():
    """把每个 Tk 解释器都留在进程里。

    Tcl 的 async handler 只能在创建它的线程里析构，否则 Tcl 直接 Tcl_Panic 中止整个进程
    （Tcl_AsyncDelete: async handler deleted by the wrong thread）。解释器句柄是 C 层对象，
    按引用计数析构，加不了 __del__ 守卫；worker 线程里的一次 GC 就可能把「主线程建的窗口对象环」
    连同解释器一起回收掉，唯一的办法是自己拿住引用。
    """
    try:
        import _tkinter
        if getattr(_tkinter,'_dramaPinned',False):return
        original=_tkinter.create
        def create(*args,**kwargs):
            app=original(*args,**kwargs)
            _KEEP_APPS.append(app)
            return app
        _tkinter.create=create
        _tkinter._dramaPinned=True
    except Exception:app_logging.swallowed()


def protect_tk_gc(win=None):
    """Tk 对象只在界面线程里释放。

    tkinter 里只有三个类型会在 __del__ 里调 Tcl 释放自己的资源：Variable、Image（PhotoImage）、
    font.Font。对象若在 worker 线程被 GC 回收，这次 Tcl 调用就跨线程跑，轻则刷
    RuntimeError: main thread is not in main loop，重则与正在 update() 的界面线程互相等待而卡死
    （实测：无人值守收尾阶段在 worker 里分配对象时，复选框图标与字体对象都会被回收）。

    所以这里做四件事：
    1) 给这三个 __del__ 加线程守卫：非主线程不调 Tcl；
    2) 被拦下的对象交给 _PENDING_TK_GC 暂存、由主线程的 drain_tk_gc() 真正释放——顺带让它所在的
       对象环整体活到主线程。若就地释放，环里的 Tkapp 会在 worker 里析构，Tcl 直接
       Tcl_AsyncDelete 中止整个进程；
    3) 记下解释器句柄：Tkapp 的析构只能在主线程发生；
    4) 把所有 Tk 解释器都留在进程里（见 _pin_tk_app）——否则 worker 里的一次 GC 就足以中止进程。
    幂等（各类上的 _dramaGuarded、模块上的 _dramaPinned）。
    """
    _pin_tk_app()
    try:
        import threading
        import tkinter as tk
        from tkinter import font as tkfont
        if win is not None and getattr(win,'tk',None) is not None:
            _KEEP_APPS.append(win.tk)
        for cls in (tk.Variable,tk.Image,tkfont.Font):
            if getattr(cls,'_dramaGuarded',False):continue
            original=getattr(cls,'__del__',None)
            if original is None:continue
            def guarded(self,_original=original):
                if threading.current_thread() is not threading.main_thread():
                    app=getattr(self,'tk',None) or getattr(self,'_tk',None)
                    if app is not None and not any(item is app for item in _KEEP_APPS):
                        _KEEP_APPS.append(app)
                    _PENDING_TK_GC.append(self)
                    return
                _original(self)
            cls.__del__=guarded
            cls._dramaGuarded=True
    except Exception:app_logging.swallowed()

def drain_tk_gc(limit=64):
    """主线程心跳里调用：释放 worker 线程回收到的 Tk 对象（每轮最多 64 个，不拖慢界面）。"""
    try:
        for _ in range(limit):
            if not _PENDING_TK_GC:break
            _PENDING_TK_GC.pop()
    except Exception:app_logging.swallowed()



import pet_bus
# 制作页名称只从 pet_bus.STAGES／STAGE_NAMES 生成；「参考网站」是唯一非阶段工具页。
PAGES = [f'{index:02d}  {pet_bus.stage_name(stage)}'
         for index, stage in enumerate(pet_bus.STAGES, start=1)] + ['14  参考网站']
# 页面序号一律由阶段表推出来（PAGES 与 pet_bus.STAGES 一一对应），
# 再加一个阶段时只改 pet_bus.STAGES／STAGE_NAMES。
import pet_state
PAGE=pet_state.PAGE_OF
PAGE_SITES=len(PAGES)-1          # 「参考网站」是工具页，不进状态机
# 侧栏切回时复用：02 以内容签名校验，03 沿用后台目录监听。
CACHED_PAGES=frozenset({PAGE['script_structure'],PAGE['storyboard']})

# 宠物「自动推进」用的对照表（第 23 期）：制作阶段 → 那一步的无人值守轮询名。
# 只登记真的带无人值守轮询的阶段；剧本与配音没有轮询，不在表里（宠物问到时老实说没有）。
PET_STAGE_POLL={'storyboard':'auto_adopt','assets':'auto_asset','final':'auto_final','keyframe':'auto_keyframe',
                'previs':'auto_previs','video':'auto_video','edit':'auto_edit','delivery':'auto_handoff'}
# 第 67 期任务 5：无人值守轮询名 → 打开它的那一把开关（project_settings 里的 set_auto_*）。
# 用户切到自动档之后，三虎要「自动开始每个阶段的任务」：先把这一步的开关替他打开，再起跑。
UNATTENDED_SWITCH={'auto_adopt':'set_auto_adopt','auto_asset':'set_auto_asset','auto_final':'set_auto_final',
                   'auto_keyframe':'set_auto_keyframe','auto_previs':'set_auto_previs','auto_video':'set_auto_video',
                   'auto_edit':'set_auto_edit','auto_handoff':'set_auto_handoff'}

# 第 44 期：版本号只写这一份——系统标题栏与左上角那一行（齿轮就挨着它）都用它。
from app_metadata import APP_NAME, VERSION

bind_host(sys.modules[__name__])  # 剧本准备页的 confirm／ContextMenu 等转发到本模块，保持按 desktop.<名字> 打补丁有效

class Desktop(IdeaMenusMixin, AssetPagesMixin, ScriptPagesMixin, MediaPagesMixin, ProjectPagesMixin, StoryboardPageMixin, WritingPageMixin, IdeaChatMixin, AutoFlowsMixin):
    def __init__(self,win,root=ROOT):
        self._diagnostic_start=time.perf_counter()
        from stage_execution_service import project_registry_gateway
        self.win=win;self.app=Path(root);self.projects=Projects(root,gateway=project_registry_gateway(),migrate_legacy=False);self.worker=False;self.q=queue.Queue();self._brief_load_results=queue.Queue();self._async_ticket=0;self.background_tasks=BackgroundTaskLifecycle();self.task_queue=PersistentBackgroundTaskQueue(self.app/'outputs'/'desktop-task-queue.json',handlers={'storage_inspect':inspect_project_storage});self.retry_registry=RetryRegistry();self._async_result_poll_id=None;self._auto_edit_result_poll_id=None;self._auto_handoff_result_poll_id=None;self._idea_brief_generation=0;self.idea_chat_controller=IdeaChatController();self.video=None
        self._stage_model_sync_results=queue.Queue();self._stage_model_sync_generation=0
        self._legacy_project_migration_results=queue.Queue();self._legacy_project_migration_poll_id=None
        self._legacy_project_migration_started=False
        win._desktop_first_paint_complete=False
        win._desktop_loading_project=False
        self.video_sessions={};self.cloud_monitor_busy=False;self.cloud_monitor_due=0;self.cloud_monitor_cursor=0;self._cloud_monitor_ticket=0;self.cloud_monitor_tasks=BackgroundTaskLifecycle();self.cloud_monitor_result=queue.Queue()
        self.settings_file=self.app/'desktop_settings.json';self.settings=read(self.settings_file) if self.settings_file.exists() else {'comfy_url':'http://127.0.0.1:8189','jianying':''}
        win.title(APP_NAME+' · '+VERSION);win.state('normal')
        win.geometry('%dx%d'%(min(1360,win.winfo_screenwidth()-80),min(900,win.winfo_screenheight()-100)))
        # 第 19 期：安装后的图标（三虎）——主窗口标题栏／任务栏都用它，拿不到就照旧用 Tk 默认图标。
        try:
            import app_icon;app_icon.apply(win)
        except Exception:app_logging.swallowed()
        win.minsize(DESKTOP_LAYOUT['min_width'],DESKTOP_LAYOUT['min_height']);apply_theme(win);setup_styles(win);install_window_placement(win)
        # 左侧阶段导航从 230px 缩至约三分之二，正文阅读区在小窗口也能保留空间。
        sidebar_area=ttk.Frame(win,width=DESKTOP_LAYOUT['sidebar_width']);sidebar_area.pack(side='left',fill='y');sidebar_area.pack_propagate(False)
        side=ttk.Frame(sidebar_area,padding=DESKTOP_LAYOUT['sidebar_padding']);self.sidebar=side
        side.pack(fill='both',expand=True);side.grid_propagate(False)
        # 左上角只保留应用名；设置齿轮由 pet_ui 放在相邻的根层安全位。
        self.sidebar_head=ttk.Frame(side)
        self.app_title=ttk.Label(self.sidebar_head,text=APP_NAME,font=('Microsoft YaHei UI',16,'bold'))
        self.app_title.pack(side='left',pady=(2,4))
        self.sidebar_head.pack(fill='x',anchor='w')
        # 设置齿轮直接落在主窗口根层，避免侧栏或页面画布在窄窗口时裁掉入口；
        # 实际文字尺寸决定齿轮位置；字号或显示名改变时不留旧名称的空洞。
        self.settings_gear_layer=win
        self.settings_gear_position=(0,0)
        self.project_label=ttk.Label(side,text='我的项目')
        self.project_label.pack(anchor='w',pady=(DESKTOP_LAYOUT['project_label_gap'],SPACING['none']))
        self.list=ttk.Treeview(side,show='tree',height=3,selectmode='browse',style='Project.Treeview');self.list.column('#0',width=136,minwidth=96,stretch=True);self.list.pack(fill='x',pady=SPACING['xs'])
        self.list.bind('<<TreeviewSelect>>',self.switch);self.list.bind('<Button-3>',self.project_menu)
        self.project_tip=TreeRowTooltip(self.list,lambda item:self.list.item(item,'text'))
        self.project_buttons=(self.button(side,'+ 新建项目',self.new),self.button(side,'打开项目目录',self.open_current_project))
        for button in self.project_buttons:button.configure(style='ProjectAction.TButton')
        ttk.Separator(side).pack(fill='x',pady=SPACING['sm'])
        self.nav=[]
        self.asset_list_button=None
        for i,title in enumerate(PAGES):
            # 第 48 期第 3 条：点「10 视频生成」的入口逻辑——本次启动第一次点先摆「选择生成方式」
            # 那一屏；之后（用户已经选过线上或线下）再点就直接回他选的那一侧，不再反复拦在选择页上。
            # 页内切分镜、刷新列表仍直接调 show()。
            b=SecondaryButton(side,text=title,command=lambda n=i:self.go_page(n),style='Nav.TButton');b.pack(anchor='w',fill='x',pady=2);self.nav.append(b)
            if i==PAGE['assets']:
                # 第 71 期任务 2：「05 资产管理」下面挂一级缩进的二级入口「资产清单」——
                # 一页看完每个角色的正典板与换状态面板（见 asset_detail.show_roster）。
                sub=SecondaryButton(side,text='资产清单',command=lambda:self.safe(self.open_asset_roster),style='Sub.Nav.TButton')
                sub.pack(anchor='w',fill='x',pady=(0,2))
                self.asset_list_button=sub
        # 项目列表只占可见行数，剩余空间留在导航下方。
        side.columnconfigure(0,weight=1)
        for row,child in enumerate(side.winfo_children()):
            child.pack_forget()
            separator=isinstance(child,ttk.Separator)
            side.rowconfigure(row,weight=0,minsize=SPACING['xs'] if separator else 0)
            child.grid(row=row,column=0,sticky='ew' if isinstance(child,ttk.Label) or separator else 'nsew',pady=DESKTOP_LAYOUT['row_gap'])
        side.rowconfigure(len(side.winfo_children()),weight=1)
        self.sidebar_size=None
        self.list.bind('<<TreeviewOpen>>',self.schedule_sidebar_fit,add='+')
        self.list.bind('<<TreeviewClose>>',self.schedule_sidebar_fit,add='+')
        side.bind('<Configure>',self.fit_sidebar)
        self.body=ttk.Frame(win,padding=DESKTOP_LAYOUT['body_padding']);self.body.pack(side='left',fill='both',expand=True)
        self.title_row=ttk.Frame(self.body);self.title_row.pack(fill='x');self.title_row.pack_propagate(False)
        self.pet_layer=self.title_row
        self.title=ttk.Label(self.title_row,font=('Microsoft YaHei UI',18,'bold'));self.title.pack(side='left',anchor='n',padx=(DESKTOP_LAYOUT['title_inset'],0))
        self.header_slogan=ttk.Label(self.title_row,text='✦  把灵感变成故事',
                                   style='Muted.TLabel',font=DESKTOP_LAYOUT['slogan_font'])
        self.title.bind('<Configure>',self.align_header,add='+')
        self.app_title.bind('<Configure>',self.align_header,add='+')
        self.list.bind('<Configure>',self.fit_sidebar,add='+')
        self.title_row.bind('<Configure>',self.align_header,add='+')
        self.header_info=ttk.Frame(self.title_row);self.header_info.pack(side='right',fill='x',expand=True,padx=(12,0))
        self.header_model=ttk.Label(self.header_info,style='Muted.TLabel',font=('Microsoft YaHei UI',8),anchor='e');self.header_model.pack(side='bottom',fill='x')
        self.header_status=ttk.Label(self.header_info,style='Muted.TLabel',font=('Microsoft YaHei UI',8),anchor='e',justify='right');self.header_status.pack(side='top',fill='x')
        # 第 30 期第 6／8 条：阶段配置那颗按钮从标题栏挪到「剧本准备」页的「创作入口」那一行，
        # 紧挨着「手动制作剧本」（按钮那时才建得出来，见 brief_editor）；这里先留个占位，别的页没有它。
        self.stage_button=None
        # 第 33 期第 4 条：07 分镜定稿那一页没有「手动XX」，它的「阶段配置」挂在页标题右边。
        self.header_stage_button=None
        self.header_status.bind('<Configure>',lambda e:self.header_status.configure(wraplength=max(120,e.width)))
        self.header_model.bind('<Configure>',lambda e:self.header_model.configure(wraplength=max(120,e.width)))
        # 宠物贴片（方案 A）：挂在标题栏右上角，随主窗口移动，不参与布局计算。
        # 第 30 期第 3 条：把「前台窗口是不是本进程」交上去——用户切到别的应用时，三虎的自动
        # 播报（心跳、进度气泡、主动询问、失败提醒）一律不冒；自己点开的对话框照旧一条都不拦。
        self.pet=pet_ui.attach(self,front=pet_ui.our_process_in_front)
        # 页面仍由画布和鼠标滚轮滚动，但不显示贴在窗口最右侧的整页长滑块。
        # 各页面共用这一层，因而无需在 11 个页面里分别隐藏；表格、对话框等局部滚动条照常保留。
        area=ttk.Frame(self.body);area.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(area,bg=COLORS['background_primary'],highlightthickness=0)
        self.canvas.pack(fill='both',expand=True)
        self.page_scrollbar=None
        self.content=ttk.Frame(self.canvas);self.content_id=self.canvas.create_window(0,0,window=self.content,anchor='nw')
        self.content.bind('<Configure>',self.fit_content)
        self.content.bind('<Configure>',self.align_header,add='+')
        self.canvas.bind('<Configure>',self.fit_content)
        protect_readonly_combobox(win);protect_tk_gc(win)
        win.bind_class('DramaPageWheel','<MouseWheel>',self.scroll_page)
        win.bind_all('<MouseWheel>',self.scroll_page,add='+')
        # 最小化恢复时 Windows 可能先交付一枚滚轮事件，随后才派发画布的新尺寸。
        # 重新映射后沿用既有的合并空闲布局，确保滚动区域已按恢复后的可视高度计算。
        win.bind('<Map>',self.on_window_map,add='+')
        self.progress=ttk.Progressbar(self.body,mode='determinate');self.progress.pack(fill='x',pady=(8,0))
        # 全部阶段只保留一条绿色信息栏：操作说明与动态状态汇总在这里。
        self.status=tk.StringVar(value='就绪 · 所有项目共用一份程序')
        self.notifier=NotificationDispatcher(self.status, parent=win)
        self.file_dialog=FileDialog(win, notifier=self.notifier)
        self.shortcuts=ShortcutRegistry()
        self.busy_state=BusyState(self.status, self.progress, idle_determinate=True)
        # ui_theme 的窗口定位失败只做恢复，不另建反馈链；状态栏建好后把
        # 既有可见提示入口交给根窗口。
        win._drama_place_notice=self.status.set
        self.banner_status=tk.StringVar(value='')
        def refresh_banner(*_unused):
            self.banner_status.set(self.status.get().strip())
        self.status.trace_add('write',refresh_banner);refresh_banner()
        pet_ui.watch_status(self,self.pet)
        self.status_label=ttk.Label(self.body,textvariable=self.banner_status,
                                    style='PaleGreenHint.TLabel',wraplength=700)
        self.status_label.pack(fill='x',pady=(4,6))
        self.sizegrip=ttk.Sizegrip(win);self.sizegrip.place(relx=1.0,rely=1.0,anchor='se')
        # Timed callbacks cannot run inside the placement code's update_idletasks.
        # An idle modal here would block the root while it is still transparent.
        self._initialize_automation_state()
        self.root=None
        self.studio=None
        self.asset_kind='all'
        self.asset_detail_id=None
        self.asset_roster=False
        self.gate_auto_due=0
        self.gate_auto_error=''
        self._destroy_cleanup_done=False
        self.reload()
        self.show(0)
        # 只记录启动壳完成耗时；采集不遍历项目目录，也不参与启动决策。
        import diagnostic_capture
        diagnostic_capture.record_startup_timing('desktop_shell_ready', (time.perf_counter()-self._diagnostic_start)*1000)
        self.shutting_down=False
        self._tick_id=None
        self._startup_tick_paused=True
        self._startup_tick_resume_id=None
        self._startup_project_page_job=None
        self._startup_script_build_job=None
        self._startup_project_recovery_job=None
        self._startup_project_choice=True
        # 窗口只提供 Tk 调度与事件绑定；无 Tk 控制器保持首帧后才选择项目的时序。
        self._startup_timer=None
        self.startup_controller=DesktopStartupController(
            schedule_after=win.after, schedule_idle=win.after_idle,
            cancel_scheduled=win.after_cancel,
            is_stopping=lambda:getattr(self,'shutting_down',False),
            before_project_choice=self._after_first_paint,
            choose_project=self.choose_project,
            remember_timer=lambda timer:setattr(self,'_startup_timer',timer),
        )
        # 启动画面整块盖住、主窗口仍透明时，没有白屏可防，让步只需一次消息循环。
        self.startup_controller.start(*((10,) if self._startup_window_held() else ()))
        self.automation_scheduler=DesktopAutomationScheduler(
            schedule_after=win.after, cancel_scheduled=win.after_cancel,
            is_stopping=lambda:getattr(self,'shutting_down',False))
        self.automation_scheduler.start(
            'idea_attachments',100,self.poll_idea_attachment_preparation,
            on_error=lambda exc:self._set_automation_error('附档后台任务异常，已忽略：',exc),
            remember_timer=lambda timer:setattr(self,'_idea_attachment_poll_id',timer))
        win.bind('<Destroy>',self.on_window_destroy,add='+')
        win.protocol('WM_DELETE_WINDOW',self.close)
        # 第 18 期：清掉上次的对话，再让三虎用爱心框打个招呼（推迟到主循环里再冒）。
        # 项目续开可能仍在构造剧本准备页；把首次招呼留到首帧稳定之后，
        # 不让气泡的浮窗映射与页面回填争用同一轮 Tk 事件循环。
        pet_ui.start(self,delay_ms=5000)











    def _initialize_automation_state(self):
        """建立各阶段自动队列的完整初始契约，避免 UI 构造中遗漏状态。"""
        self.auto_adopt_due=0
        self.auto_adopt_errors={}
        self.auto_adopt_signature=None
        self.auto_adopt_pending=False
        self.auto_adopt_startup=True
        self.auto_final_due=0
        self.auto_final_busy=False
        self.auto_final_queue=pet_ui.StageQueue('final',self.pet.drain)
        self.auto_final_signature=None
        self.auto_final_notice=None
        self.auto_final_blocked=False
        self.auto_final_error=''
        self.auto_edit_due=0;self._auto_edit_ticket=0;self.auto_edit_tasks=BackgroundTaskLifecycle()
        self.auto_edit_busy=False
        self.auto_edit_queue=pet_ui.StageQueue('edit',self.pet.drain)
        self.auto_edit_signature=None
        self.auto_edit_error=''
        self.auto_keyframe_due=0;self._auto_keyframe_ticket=0;self.auto_keyframe_tasks=BackgroundTaskLifecycle()
        self.auto_keyframe_busy=False
        self.auto_keyframe_queue=pet_ui.StageQueue('keyframe')
        self.auto_keyframe_messages=queue.Queue()
        self.auto_keyframe_signature=None
        self.auto_keyframe_blocked=None
        self.auto_keyframe_error=''
        self.auto_asset_due=0;self._auto_asset_ticket=0;self.auto_asset_tasks=BackgroundTaskLifecycle()
        self.auto_asset_busy=False
        self.auto_asset_queue=pet_ui.StageQueue('assets')
        self.auto_asset_messages=queue.Queue()
        self.auto_asset_signature=None
        self.auto_asset_attempt=0
        self.auto_asset_blocked=None
        self.auto_asset_error=''
        self.auto_asset_tried=None
        self.auto_video_due=0;self._auto_video_ticket=0;self.auto_video_tasks=BackgroundTaskLifecycle()
        self.auto_video_busy=False
        self.auto_video_queue=pet_ui.StageQueue('video',self.pet.drain)
        self.auto_video_messages=queue.Queue()
        self.auto_video_signature=None
        self.auto_video_notice=None
        self.auto_video_error=''
        self.auto_video_last=''
        self.auto_previs_due=0
        self._auto_previs_ticket=0;self.auto_previs_tasks=BackgroundTaskLifecycle()
        self.auto_previs_signature=None
        self.auto_previs_notice=None
        self.auto_previs_error=''
        self.auto_handoff_due=0;self._auto_handoff_ticket=0;self.auto_handoff_tasks=BackgroundTaskLifecycle()
        self.auto_handoff_busy=False
        self.auto_handoff_queue=pet_ui.StageQueue('delivery',self.pet.drain)
        self.auto_handoff_signature=None
        self.auto_handoff_error=''
    def schedule_sidebar_fit(self,event=None):
        if getattr(self,'_sidebar_fit_job',None) is not None:return
        def run():
            self._sidebar_fit_job=None
            self.fit_sidebar()
        self._sidebar_fit_job=self.win.after_idle(run)
    def fit_sidebar(self,event=None):
        compact=self.sidebar.winfo_height()<DESKTOP_LAYOUT['compact_below']
        style=ttk.Style(self.win)
        font=('Microsoft YaHei UI',9 if compact else 10)
        row_height=20 if compact else 24
        if self.sidebar_size!=compact:
            self.sidebar_size=compact
            for name in ('Compact.TButton','Nav.TButton','Selected.Nav.TButton'):
                style.configure(name,font=font,padding=(10,1 if compact else 4))
            for name in ('Sub.Nav.TButton','Selected.Sub.Nav.TButton'):
                style.configure(name,font=font,padding=(26,1 if compact else 4))
            style.configure('ProjectAction.TButton',font=font,padding=DESKTOP_LAYOUT['project_button_padding'])
            style.configure('Project.Treeview',font=font,rowheight=row_height)
        # 由可用像素反算最大整行数；不以 Treeview 上一次请求高度作为下一次预算。
        gap=DESKTOP_LAYOUT['row_gap']*2
        fixed=DESKTOP_LAYOUT['sidebar_padding']*2+getattr(self,'_header_list_gap',SPACING['none'])
        for child in self.sidebar.winfo_children():
            fixed+=gap
            if child is not self.list:
                fixed+=max(child.winfo_reqheight(),SPACING['xs'] if isinstance(child,ttk.Separator) else 0)
        chrome=max(0,self.list.winfo_reqheight()-int(self.list.cget('height'))*row_height)
        def visible(parent=''):
            return sum(1+(visible(item) if self.list.item(item,'open') else 0)
                       for item in self.list.get_children(parent))
        maximum=max(DESKTOP_LAYOUT['project_min_rows'],(self.sidebar.winfo_height()-fixed-chrome)//row_height)
        rows=min(maximum,max(DESKTOP_LAYOUT['project_min_rows'],visible()))
        if int(self.list.cget('height'))!=rows:self.list.configure(height=rows)
        self.align_header()
    def align_header(self,event=None):
        """用真实控件边界对齐齿轮与聊天顶边，不参与页面业务或读盘。"""
        if not hasattr(self,'title_row'):return
        title=self.app_title
        gear=getattr(getattr(self,'pet',None),'gear',None)
        if gear is not None:
            canvas=gear.canvas
            x=title.winfo_rootx()-self.win.winfo_rootx()+title.winfo_reqwidth()+DESKTOP_LAYOUT['gear_gap']
            y=title.winfo_rooty()-self.win.winfo_rooty()+round((title.winfo_reqheight()-canvas.winfo_reqheight())/2)
            self.settings_gear_position=(x,y)
            canvas.place_configure(x=x,y=y)
        minimum=max(self.title.winfo_reqheight(),pet_ui.PATCH_ROOM)
        list_top=self.list.winfo_rooty()-self.title_row.winfo_rooty()
        measurement=(list_top,minimum)
        if self.list.winfo_ismapped() and measurement!=getattr(self,'_header_list_measurement',None):
            self._header_list_measurement=measurement
            previous=getattr(self,'_header_list_gap',SPACING['none'])
            gap=max(SPACING['none'],minimum-(list_top-previous))
            if gap!=previous:
                self._header_list_gap=gap
                self.list.grid_configure(pady=(DESKTOP_LAYOUT['row_gap']+gap,DESKTOP_LAYOUT['row_gap']))
        height=max(minimum,list_top)
        if int(self.title_row.cget('height'))!=height:self.title_row.configure(height=height)
        content=getattr(self,'content',None)
        if content is None:return
        box=getattr(self,'idea_log',None)
        script=self.page_index==PAGE['script'] and box is not None and box.winfo_exists()
        anchor=box if script else content
        inset=max(SPACING['none'],anchor.winfo_rootx()-self.title_row.winfo_rootx())
        def horizontal_pad(widget):
            value=widget.pack_info()['padx']
            values=tuple(map(int,value if isinstance(value,tuple) else widget.tk.splitlist(str(value))))
            return values if len(values)>1 else values*2
        title_pad=(inset,SPACING['none'])
        if horizontal_pad(self.title)!=title_pad:
            self.title.pack_configure(padx=title_pad)
        pet=getattr(self,'pet',None)
        obstacles=[w for w in (getattr(pet,'canvas',None),getattr(pet,'paws',None),
                               getattr(pet,'caption',None)) if w is not None and w.winfo_exists()]
        if script and box.winfo_ismapped():
            dialog=box.master
            overlapping=[w for w in obstacles if w.winfo_rooty()<box.winfo_rooty()+box.winfo_height()
                         and w.winfo_rooty()+w.winfo_height()>box.winfo_rooty()]
            right=dialog.master.winfo_rootx()+dialog.master.winfo_width()-SPACING['xs']
            reserve=max([SPACING['none']]+[right-w.winfo_rootx()+DESKTOP_LAYOUT['pet_clearance'] for w in overlapping])
            dialog_pad=(SPACING['none'],reserve)
            if horizontal_pad(dialog)!=dialog_pad:
                dialog.pack_configure(padx=dialog_pad)
        slogan=self.header_slogan
        x=inset+self.title.winfo_reqwidth()+DESKTOP_LAYOUT['slogan_gap']
        edge=min([self.title_row.winfo_width()]+[w.winfo_rootx()-self.title_row.winfo_rootx() for w in obstacles])
        stage=getattr(self,'header_stage_button',None)
        if stage is not None and stage.winfo_exists() and stage.winfo_ismapped():
            edge=min(edge,stage.winfo_rootx()-self.title_row.winfo_rootx())
        if x+slogan.winfo_reqwidth()+DESKTOP_LAYOUT['slogan_gap']<=edge:
            y=round(self.title.winfo_y()+self.title.winfo_height()/2)
            placed=slogan.place_info()
            if not placed or (int(placed['x']),int(placed['y']))!=(x,y):
                slogan.place(x=x,y=y,anchor='w')
                slogan.tk.call('raise',str(slogan))
        else:slogan.place_forget()
    def fit_content(self,event=None):
        # 迟到的请求不能丢：内容框行数变化常发生在一次重算过程中，若不补算一次，
        # 页面滚动区域会停留在旧高度，底部按钮就可能被滚出可视区。
        if getattr(self,'_fit_pending',False):
            self._fit_again=True
            return
        self._fit_pending=True
        def run():
            self._fit_job=None
            self._fit_pending=False
            layout_key=None
            try:layout_key=self._fit_content_now()
            except Exception:app_logging.swallowed()
            if getattr(self,'_fit_again',False):
                self._fit_again=False
                self.fit_content()
                return
            # Canvas 固定内容高度后，子控件请求高度变化不再触发内容框 Configure。
            # 沿现有空闲队列等请求尺寸逐层传播；最多补八轮，避免异常布局反复排队。
            signature=getattr(self,'_fit_request_signature',layout_key)
            changed=signature!=getattr(self,'_last_fit_request_signature',None)
            self._last_fit_request_signature=signature
            passes=getattr(self,'_fit_stability_passes',0)
            if changed and passes<8:
                self._fit_stability_passes=passes+1
                self.fit_content()
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
        try:self._fit_job=self.win.after_idle(run)
        except tk.TclError:
            self._fit_job=None
            self._fit_pending=False
    def _fit_content_now(self):
        width=max(1,self.canvas.winfo_width());height=max(1,self.canvas.winfo_height())
        req=self.content.winfo_reqheight()
        req_min=max(1,req-growable_extra())
        target=max(height,req_min)
        self.canvas.itemconfigure(self.content_id,width=width,height=target)
        # 滚动区域就是内容实际高度：内容框（Treeview）会长到填满窗口，若按请求高度
        # 记录滚动区域，窗口缩小时会残留旧高度，底部按钮可能被滚出可视区。
        self.canvas.configure(scrollregion=(0,0,width,target))
        if hasattr(self,'status_label'):self.status_label.configure(wraplength=max(200,width-12))
        resized=getattr(self,'_last_fit_width',None)!=width
        if resized:self._last_fit_width=width
        # 页面重建（切换分镜、刷新列表）会产生新控件，必须每次重新补挂滚轮标签：
        # 漏挂标签时滚轮会落到控件自身的绑定上，只读下拉框会直接换选项并重建整页，
        # 表现出来就是「滚轮滑过下拉框，文件被切换，内容抖动」。
        measured_requests=[]
        def resize(widget):
            for child in widget.winfo_children():
                tags=child.bindtags()
                if 'DramaPageWheel' not in tags:child.bindtags(('DramaPageWheel',)+tags)
                if resized and isinstance(child,ttk.Label) and not getattr(child,'local_wrap',False) and int(child.cget('wraplength') or 0)>0:
                    child.configure(wraplength=max(200,width-28))
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
    def scroll_page(self,event):
        widget=event.widget
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
        if str(widget).startswith(str(self.sidebar)):return
        if not steps:return 'break'
        # This bindtag runs before native widget bindings, so one wheel event
        # moves either the hovered editor/table or the surrounding page once.
        while widget is not self.content and widget is not self.win:
            if isinstance(widget,(tk.Text,tk.Listbox,ttk.Treeview)):
                top,bottom=widget.yview()
                if (steps<0 and top>0.000001) or (steps>0 and bottom<0.999999):
                    widget.yview_scroll(steps,'units');self.clear_hover(widget);return 'break'
            widget=getattr(widget,'master',self.win)
            if widget is None:break
        self.canvas.yview_scroll(steps,'units')
        return 'break'
    def on_window_map(self,event=None):
        """主窗口从最小化恢复后，重新排定整页滚动范围。"""
        if event is not None and event.widget is not self.win:return
        if getattr(self,'shutting_down',False):return
        self.fit_content()
    def save_brief(self,path,value):
        path=Path(path)
        # 第 37 期第 2 条：预置示例随程序打包（默认创意示例.md），比的是程序里那一份——
        # 不改动就一个字都不落进项目文件。
        example=self.idea_example().strip()
        value=str(value or '').strip()
        if value.startswith(example):
            # 兼容旧界面把示例和用户补充放在同一编辑框的情形：示例仅供参考，
            # 绝不能作为项目创意的一部分写入，也不能让其字段表格触发自然剧本校验。
            value=value[len(example):].lstrip()
        if not value:
            raise ValueError('请先填写自己的创意；灰色文字只是软件示例，不会保存到项目。')
        if path.is_file():
            from file_cache import read_text
            if read_text(path,encoding='utf-8')==value:
                self.status.set('文字未改动，未创建新版本')
                return path
        import idea_chat
        from stage_execution_service import publish_idea_creative
        dest=idea_chat.save_manual_creative(self.idea_chat_context(),value,publish=publish_idea_creative)
        editor=getattr(self,'brief_editor',None)
        if editor and editor[0]==path:
            self.brief_editor=(dest,editor[1]);self.brief_saved_text=value
        self.status.set('已另存新版本 · '+dest.name)
        return dest
    def brief_text(self):
        """上一次存下的那份创意（还没有对话时拿它垫在展示框里）；没有就是空串。"""
        editor=getattr(self,'brief_editor',None)
        path=editor[0] if editor else None
        try:
            if not path or not Path(path).is_file():return ''
            from file_cache import read_text
            return read_text(path,encoding='utf-8').strip()
        except OSError:
            return ''
    def draft_text(self):
        """只读取下方发送框；聊天气泡不参与发送。"""
        box=getattr(self,'idea_input',None)
        if box is None or not box.winfo_exists():return ''
        start,end=self.idea_draft_range()
        try:
            from idea_brief_form import strip_inline_required_markers
            return strip_inline_required_markers(box.get(start,end))
        except tk.TclError:return ''
    def text_width(self,text):
        """这一段字自然有多宽（像素）。"""
        cache=self.__dict__.setdefault('_text_widths',{})
        key=str(text)
        if key in cache:return cache[key]
        lines=key.splitlines() or ['']
        face=self.bubble_font()
        if face is None:return BUBBLE_LINE*max(len(line) for line in lines)
        try:width=max(int(face.measure(line)) for line in set(lines))
        except Exception:return BUBBLE_LINE*max(len(line) for line in lines)
        if len(cache)>512:cache.clear()
        cache[key]=width
        return width
    def model_name(self,row):
        """对话气泡的署名（实现搬到 L3 idea_chat_controller，入口不变）。"""
        return speaker_name(row)
    def displayed_chat_model(self):
        """所有气泡操作绑定已显示会话，不随未刷新的配置漂移。"""
        cached=getattr(self,'_idea_view_model_cache',None)
        return (cached[1] if isinstance(cached,tuple) and cached[0]==self.root and cached[1]
                else self.idea_chat_model())





    def model_chat_colors(self, model):
        """为同一模型稳定分配一组浅色主题，切换回来仍保持原色。"""
        key = str(model or self.idea_chat_model() or 'AI 助手').encode('utf-8')
        hue = (int(hashlib.sha256(key).hexdigest()[:8], 16) % 360) / 360
        def hsv(saturation, value):
            section = int(hue * 6) % 6
            fraction = hue * 6 - int(hue * 6)
            low = value * (1 - saturation)
            falling = value * (1 - fraction * saturation)
            rising = value * (1 - (1 - fraction) * saturation)
            return ((value, rising, low), (falling, value, low), (low, value, rising),
                    (low, falling, value), (rising, low, value), (value, low, falling))[section]
        light = hsv(0.20, 1.0)
        dark = hsv(0.54, 0.60)
        to_hex = lambda rgb: '#%02x%02x%02x' % tuple(round(value * 255) for value in rgb)
        return to_hex(light), to_hex(dark)

    def open_dialog(self):
        """发送框始终显示；此处只把焦点放回输入处。"""
        box=getattr(self,'idea_input',None)
        if box is not None and box.winfo_exists():
            box.configure(state='normal');box.focus_set()
    def close_dialog(self):
        """保存剧本也不隐藏发送框，用户仍可继续补充。"""
        self.open_dialog()














    def poll_flow_processes(self):
        """回收已退出的桌面 Agent；自动链只把异常退出标为失败。

        交互式 Agent 正常退出并不等于已经产出可采用的文件，因此不能据此推进阶段；
        但非零退出时，当前自动阶段必须收到终止信号，避免一直卡在“制作中”。
        """
        sessions=getattr(self,'flow_processes',{})
        if not sessions:return
        from workflow_engines import forget_process
        from workflow_settings import STAGE_CONFIG_STAGES
        remaining={}
        for key,process in list(sessions.items()):
            try:code=process.poll()
            except (OSError,ValueError):
                # 进程句柄暂不可读时先保留，下一个 tick 再判断，不能把它误清掉。
                remaining[key]=process;continue
            if code is None:
                remaining[key]=process;continue
            project=Path(key[0]) if key else self.root
            try:forget_process(project,process)
            except (OSError,ValueError):pass
            flow=str(key[1]) if len(key)>1 else ''
            pet_stage=STAGE_CONFIG_STAGES.get(flow,flow)
            auto=getattr(getattr(self,'pet',None),'auto',None)
            is_active=getattr(auto,'active',None)==pet_stage
            if code and is_active:
                message=(f'{flow} Agent 已异常退出（退出码 {code}），未确认产出；'
                         '请检查 Agent 窗口或重试。')
                self.status.set(message)
                self.pet._emit('stage.failed',stage=pet_stage,error=message)
            elif not code and is_active and pet_stage=='script':
                # 桌面 Agent 的正常退出不是成功证据；只有它写出规范自然剧本时，
                # 才通知三虎继续。先发 script.completed 以武装自动链，再收场 script。
                try:
                    import script_contract
                    source=script_contract.resolve_script_source(project)
                except (OSError, TypeError, ValueError):
                    source=None
                if source is not None:
                    if (getattr(self, '_script_quality_pending_project', None) == str(project)
                            and not (getattr(self, '_script_quality_result', None) or {}).get('quality_passed')):
                        self.status.set('自然剧本已返回，四项质检尚未完成；请查看质检报告。')
                        continue
                    message='剧本 Agent 已保存自然剧本：'+source.name
                    if source.name == script_contract.RAW_SCRIPT_NAME:
                        message += '；Agent 未产出规范正式稿(任务书要求写入 项目剧本/)'
                    self.status.set(message)
                    # 完成事件只经三虎的产物校验出口；Agent 正常退出本身不是成功证据。
                    self.pet.report_done('script', message)
        self.flow_processes=remaining




    def button(self,parent,text,fn):
        # 宠物接缝③：按钮薄封装——原逻辑照旧先跑，成功后再上报「用户点了什么」。
        def action():return pet_ui.tap(self,text,fn)
        stage_action=str(text).startswith('手动制作')
        if isinstance(parent,FlowBar):
            button_type=PrimaryButton if stage_action else SecondaryButton
            b=button_type(parent,text=text,command=lambda:self.safe(action),
                         style='Primary.TButton' if stage_action else 'TButton',
                         width=STAGE_ACTION_WIDTH if stage_action else 0)
            b.pack(side='left',padx=(0,6),pady=2)
        else:
            b=SecondaryButton(parent,text=text,command=lambda:self.safe(action),style='Compact.TButton' if parent is self.sidebar else 'TButton')
            b.pack(anchor='w',fill='x',pady=2 if parent is self.sidebar else 4)
        if 'Agent' in text:
            b.bind('<Button-1>',lambda e,b=b,text=text:self._agent_disabled_hint(b,text,e),add='+')
        return b
    def _agent_disabled_hint(self,button,text,event):
        if button.instate(['disabled']):
            self.notifier.warning(text+' 当前不可用，请先完成对应前置步骤（选择文件、补齐内容或等待任务结束）。', title='无法执行', modal=True)
            return 'break'
    def safe(self,fn):
        try:
            if self.worker:raise ValueError('当前操作尚未结束，请稍后')
            return fn()
        except Exception as e:
            import diagnostic_capture
            diagnostic_capture.record_degradation(
                e, page=PAGES[getattr(self,'page_index',0)],
                project=str(getattr(self,'root', '') or ''),
                automatic_daily_open=bool(getattr(self,'_startup_project_choice',False)))
            self.notifier.error(str(e))

    def export_diagnostics_package(self):
        """唯一的用户诊断包动作：先透明说明白名单，再让用户选择保存位置。"""
        import diagnostic_capture
        entries=diagnostic_capture.preview()
        detail='\n'.join(entries) if entries else '当前没有可导出的诊断记录（仍会导出清单）。'
        if not confirm(self.win, '导出诊断包', '将仅包含以下脱敏程序日志（不会包含项目文件、private、.env 或凭据）：\n\n'+detail):
            return None
        target=FileDialog(self.win).save_file(title='保存诊断包', defaultextension='.zip', filetypes=[('诊断包','*.zip')])
        if not target:return None
        result=diagnostic_capture.export(target)
        self.status.set('诊断包已导出：'+str(result))
        return result
    def async_(self,fn,done=None,show_progress=True,label=None):
        self._async_ticket+=1;ticket=self.background_tasks.submit(self._async_ticket,label=label)
        self.worker=True
        self.busy_state.set_busy(True, message=label or '正在处理… 界面保持响应',
                                 progress=show_progress)
        def run():
            try:self.q.put((ticket,True,fn(),done))
            except Exception as e:
                import diagnostic_capture
                diagnostic_capture.record_degradation(
                    e, page=PAGES[getattr(self,'page_index',0)],
                    project=str(getattr(self,'root', '') or ''),
                    automatic_daily_open=bool(getattr(self,'_startup_project_choice',False)))
                self.q.put((ticket,False,str(e),None))
        threading.Thread(target=run,daemon=True).start()
        self._schedule_async_result_poll(ticket)
        return ticket
    def async_queued(self,fn,done=None,label=None,show_progress=True,retryable=False):
        """后台空闲就立即执行，忙就排队（最多 10 个）；只给互相独立、可延后的任务用。

        ``retryable=True`` 表示任务只读／幂等：失败后可在「运行状况」里手动重试；不会自动重试。
        """
        if not self.worker:
            ticket=self.async_(fn,done,show_progress,label=label)
            if retryable:self.retry_registry.remember(ticket,(fn,done,label,show_progress))
            return ticket
        position=self.task_queue.enqueue(fn,done,label or '',show_progress,retryable)
        self.status.set('已排队（第%d个）：%s'%(position,label or '后台任务'))
        return None
    def async_descriptor(self,kind,payload,*,label='',priority=0,expires_at=None):
        task_id=self.task_queue.enqueue_descriptor(kind,payload,label=label,priority=priority,expires_at=expires_at)
        self.status.set('已排队：'+label)
        self._start_next_queued()
        return task_id
    def _start_next_queued(self):
        """当前主动任务收尾后继续待办；关闭期间不领取，持久待办留待重启。"""
        if self.worker or getattr(self,'shutting_down',False):return
        item=self.task_queue.pop()
        if item:
            ticket=self.async_(item['fn'],item['done'],item['show_progress'],label=item['label'] or None)
            if item['retryable']:self.retry_registry.remember(ticket,(item['fn'],item['done'],item['label'] or None,item['show_progress']))
    def retry_failed_task(self):
        """手动重试最近一次失败的可重试任务；没有则返回 False。"""
        spec=self.retry_registry.take_latest_failed(self.background_tasks.history())
        if spec is None:return False
        self.async_queued(*spec,retryable=True)
        return True
    def _schedule_async_result_poll(self,ticket):
        """启动早期的全局 tick 暂停时，也要能交付用户主动任务的后台结果。"""
        if getattr(self,'shutting_down',False):return None
        if getattr(self,'_async_result_poll_id',None) is None:
            self._async_result_poll_id=self.win.after(50,lambda:self._poll_async_result(ticket))
        return self._async_result_poll_id
    def _poll_async_result(self,ticket):
        self._async_result_poll_id=None
        if (getattr(self,'shutting_down',False) or ticket!=self._async_ticket
                or not self.background_tasks.accepts(ticket)):return
        self._tick_async_result()
        if self.worker and ticket==self._async_ticket:
            self._schedule_async_result_poll(ticket)
    def _schedule_auto_edit_result_poll(self):
        """启动期暂停全局 tick 时，仍交付已经派发的自动粗剪结果。"""
        if (getattr(self,'shutting_down',False) or not getattr(self,'_startup_tick_paused',False)
                or getattr(self,'_auto_edit_result_poll_id',None) is not None):
            return None
        self._auto_edit_result_poll_id=self.win.after(50,self._poll_auto_edit_result)
        return self._auto_edit_result_poll_id
    def _schedule_auto_handoff_result_poll(self):
        """启动期暂停全局 tick 时，仍交付已经派发的自动交接结果。"""
        if (getattr(self,'shutting_down',False) or not getattr(self,'_startup_tick_paused',False)
                or getattr(self,'_auto_handoff_result_poll_id',None) is not None):
            return None
        self._auto_handoff_result_poll_id=self.win.after(50,self._poll_auto_handoff_result)
        return self._auto_handoff_result_poll_id
    def queue_initial_brief_document(self,input_box,provisional):
        """后台发现创意历史；翻页或重建后绝不把旧结果写回新页面。"""
        self._idea_brief_generation=getattr(self,'_idea_brief_generation',0)+1
        generation=self._idea_brief_generation
        root=self.root
        def apply(path):
            editor=getattr(self,'brief_editor',None)
            if (generation!=getattr(self,'_idea_brief_generation',0)
                    or getattr(self,'page_index',None)!=PAGE['script']
                    or not editor or editor[0]!=provisional or editor[1] is not input_box):
                return
            try:
                if not input_box.winfo_exists():return
            except tk.TclError:return
            self.brief_editor=(path,input_box)
        # 这只是首帧后的只读发现，不能占用 ``worker``：后者是用户提交操作的
        # 全局门禁，若复用它，输入框刚出现就会被误报为“当前操作尚未结束”。
        def discover():
            import idea_chat
            from stage_execution_service import project_context
            try:
                path=idea_chat.initial_brief_document(project_context(root));error=None
            except (OSError,ValueError,TypeError,KeyError) as exc:
                # 线程只传递结果；Tk 状态须由 _tick_async_result 在主线程更新。
                path=None;error=str(exc)
            self._brief_load_results.put((generation,root,apply,path,error))
        threading.Thread(target=discover,daemon=True).start()
        return generation
    def cancel_timers(self,event=None):
        # 先停掉定时器再销毁窗口：残留的 after 回调会在 Tk 里报 invalid command name。
        if event is not None and event.widget is not self.win:return
        self.shutting_down=True
        for name in ('_navigation_job','_sidebar_fit_job'):
            job=getattr(self,name,None)
            if job is not None:
                try:self.win.after_cancel(job)
                except tk.TclError:pass
            setattr(self,name,None)
        # 计时器回归会构造最小 Desktop 替身；真实窗口在 __init__ 中必定拥有这些
        # 生命周期登记器，但关闭路径也必须兼容尚未完成初始化的窗口。
        for lifecycle_name in ('background_tasks','cloud_monitor_tasks','auto_asset_tasks','auto_keyframe_tasks','auto_video_tasks','auto_edit_tasks','auto_handoff_tasks','auto_previs_tasks'):
            lifecycle=getattr(self,lifecycle_name,None)
            if lifecycle is not None:lifecycle.cancel()
        # ``fit_content`` 的空闲布局任务属于桌面窗口；若关闭发生在首帧／重建之间，
        # 必须在销毁 Tcl 回调前取消，否则会留下 ``...run`` 的 after 噪声。
        fit_job=getattr(self,'_fit_job',None)
        self._fit_job=None
        self._fit_pending=False
        self._fit_again=False
        if fit_job is not None:
            try:self.win.after_cancel(fit_job)
            except tk.TclError:pass
        startup_tick_resume=getattr(self,'_startup_tick_resume_id',None)
        self._startup_tick_resume_id=None
        if startup_tick_resume is not None:
            try:self.win.after_cancel(startup_tick_resume)
            except tk.TclError:pass
        startup_page=getattr(self,'_startup_project_page_job',None)
        self._startup_project_page_job=None
        if startup_page is not None:
            try:self.win.after_cancel(startup_page)
            except tk.TclError:pass
        startup_script_build=getattr(self,'_startup_script_build_job',None)
        self._startup_script_build_job=None
        if startup_script_build is not None:
            try:self.win.after_cancel(startup_script_build)
            except tk.TclError:pass
        startup_recovery=getattr(self,'_startup_project_recovery_job',None)
        self._startup_project_recovery_job=None
        if startup_recovery is not None:
            try:self.win.after_cancel(startup_recovery)
            except tk.TclError:pass
        legacy_migration_poll=getattr(self,'_legacy_project_migration_poll_id',None)
        self._legacy_project_migration_poll_id=None
        if legacy_migration_poll is not None:
            try:self.win.after_cancel(legacy_migration_poll)
            except tk.TclError:pass
        async_result_poll=getattr(self,'_async_result_poll_id',None)
        self._async_result_poll_id=None
        if async_result_poll is not None:
            try:self.win.after_cancel(async_result_poll)
            except tk.TclError:pass
        for name in ('_auto_edit_result_poll_id','_auto_handoff_result_poll_id'):
            result_poll=getattr(self,name,None)
            setattr(self,name,None)
            if result_poll is not None:
                try:self.win.after_cancel(result_poll)
                except tk.TclError:pass
        self.idea_chat_controller.cancel_request()
        # 宠物的动画循环也挂在这个窗口上（同一个 after 表）：不一起停掉，关窗后它还会到期一次，
        # 控制台就会报 invalid command name "…step" ("after" script)。
        pet=getattr(self,'pet',None)
        if pet is not None:
            cloud=getattr(pet,'_cloud',None)
            if cloud is not None:
                try:cloud.cancel_deferred_render()
                except Exception:app_logging.swallowed()
            try:pet.stop()
            except Exception:app_logging.swallowed()
            # 第 18 期的开机招呼也挂在这个窗口上：还没到点就关窗，一样要收回来。
            try:pet.cancel_greet()
            except Exception:app_logging.swallowed()
        controller=getattr(self,'startup_controller',None)
        if controller is not None:
            try:controller.cancel()
            except Exception:app_logging.swallowed()
        scheduler=getattr(self,'automation_scheduler',None)
        if scheduler is not None:
            scheduler.cancel_all()
    def on_window_destroy(self,event=None):
        """系统直接销毁主窗口时也收回桌面拥有的后台资源。"""
        if event is not None and event.widget is not self.win:return
        if getattr(self,'_destroy_cleanup_done',False):return
        self._destroy_cleanup_done=True
        self.cancel_timers()
        self.stop_automation_processes()
        try:
            asset_thumbs.forget()
            asset_thumbs.reset_worker()
        except tk.TclError:
            # 销毁阶段 worker 可能已释放；其他失败不可吞没。
            pass
    def _set_automation_error(self,prefix,exc):
        try:
            self.status.set(prefix+str(exc))
        except Exception:app_logging.swallowed()
    def _startup_window_held(self):
        """启动器让主窗口保持透明、由启动画面盖住时为真。"""
        return getattr(self.win,'_drama_hold_alpha',False) is True
    def _after_first_paint(self):
        """首帧已交给 Tk 后，才恢复会触发轮询／回填的周期 tick。"""
        self.win._desktop_first_paint_complete=True
        if not getattr(self,'_codex_skill_sync_started',False):
            from codex_skill_sync import start_codex_skill_sync
            self._codex_skill_sync_started=True
            start_codex_skill_sync()
        self._start_legacy_project_migration()
        # 首帧通知不能覆盖用户已发起的后台操作（例如“强制关闭 ComfyUI”）；
        # 否则任务实际结束后状态栏仍停在“正在打开今日项目”。
        # 自动续开尚未选择项目时才显示这条启动提示。已有项目（含测试或
        # 外部入口已经装配好的项目）不能让延后的首帧回调覆盖刚完成的操作结果。
        if self.root is None and not self.worker and not self.projects.legacy_migration_pending:
            self.status.set('正在打开今日项目…')
        if isinstance(getattr(self,'task_queue',None),PersistentBackgroundTaskQueue):
            self._start_next_queued()


    def _request_tick_resume_after_first_paint(self):
        """项目页已完成一次构建后再恢复既有 tick，避免回填重入首帧／建页。"""
        if not bool(getattr(self.win,'_desktop_first_paint_complete',False)):
            return None
        if self._startup_tick_resume_id is None:
            self._startup_tick_resume_id=self.win.after_idle(self._resume_tick_after_first_paint)
        return self._startup_tick_resume_id
    def _resume_tick_after_first_paint(self):
        self._startup_tick_resume_id=None
        if getattr(self,'shutting_down',False):
            return
        self._startup_tick_paused=False
        self.automation_scheduler.start(
            'tick',150,self._tick_once,
            on_error=lambda exc:self._set_automation_error('后台任务回调异常，已忽略：',exc),
            remember_timer=lambda timer:setattr(self,'_tick_id',timer))
    def _tick_once(self):
        # 启动期是否排期由 ``_resume_tick_after_first_paint`` 控制；这里保留为
        # 可显式调用的一轮处理，供用户主动操作的收尾与无 Tk 调度器的接缝使用。
        # 若在此再按暂停位直接返回，手工交付的后台结果和自动链都会被永久饿死。
        startup_paused=bool(getattr(self,'_startup_tick_paused',False))
        self._tick_stage_model_sync_result()
        if not startup_paused:
            self._tick_pre_automation()
            # 待办裁决属于本轮自动链的前置准备；先处理才能让后续实际
            # 阶段结果落在状态栏，而不是被一条“已按推荐处理”覆盖。
            self._tick_auto_gates()
        self._tick_async_result()
        self._tick_cloud_monitor()
        self._tick_auto_adopt()
        self._tick_auto_final()
        self._tick_auto_edit()
        self._tick_auto_keyframe()
        self._tick_auto_asset()
        self._tick_auto_video()
        # 白模派发是本轮最后一个可见的前置制作结果，避免同轮视频的“缺首帧”
        # 提示覆盖它；后者已在白模之前完成检查。
        self._tick_auto_previs()
        self._tick_auto_handoff()
        self._tick_pet_events()
        self._tick_download_inbox()



    def shot_numbering_hint(self):
        """编号与剧本顺序不一致时返回一句提示。只提示不自动改名：重排会改写项目里的文件名与
        文本引用，属于用户可见的改动，必须由人在 03 初步分镜 点「重排镜头编号」确认后执行。"""
        import shot_numbering
        try:
            # 看的是目录里全部分镜 JSON，而不是只看已采用的：编号错了要在 03 初步分镜 就发现，
            # 不必等采用之后才在下游暴露。
            from stage_execution_service import storyboard_catalog as catalog
            problems=shot_numbering.verify(self.root,[entry['path'] for entry in catalog(self.root,'storyboard')])
        except (OSError,ValueError):return ''
        return '；镜头编号与剧本顺序不一致（'+problems[0]+'），可在 '+pet_bus.stage_label('storyboard')+' 点“重排镜头编号”修正' if problems else ''
    def _tick_async_result(self):
        """消费主后台任务结果，并恢复相关 UI 与自动链。"""
        # 首帧的创意历史发现不属于用户操作，单独回收，绝不改变 worker 状态。
        try:
            while True:
                generation,root,apply,path,error=self._brief_load_results.get_nowait()
                if (generation==getattr(self,'_idea_brief_generation',0)
                        and root==self.root and not self.shutting_down):
                    if error:self.status.set('创意历史未加载：%s；请稍后重试。' % error)
                    else:apply(path)
        except queue.Empty:pass
        try:
            ticket,ok,value,done=self.q.get_nowait()
            if not self.background_tasks.finish(ticket, succeeded=ok, error='' if ok else str(value)) or ticket!=self._async_ticket:return
            self.worker=False;self.busy_state.set_busy(False)
            if ok and done:done(value)
            elif ok:self.status.set(str(value))
            elif not ok:
                # 创意对话失败也要恢复发送框；否则一次网络错误会把唯一发送入口永久锁住。
                if getattr(self,'_idea_requesting',False):
                    self.idea_chat_controller.cancel_request()
                    send=getattr(self,'idea_send',None)
                    if send is not None and send.winfo_exists():send.state(['!disabled'])
                self._script_agent_launching=False
                self.update_script_interrupt_button()
                self.clear_thinking()
                self.notifier.error(str(value), title='操作未完成')
            # 自动链派到结构剧本时，若恰有另一项后台工作在收尾，不能把这次
            # 暂时占用误判成永久失败。只保留一个待派发标记；当前队列清空后
            # 仍走 L3 注册器重新启动，避免在 UI 层复制派发逻辑或无限重试。
            if getattr(self, '_auto_structure_retry', False) and not self.worker:
                self._auto_structure_retry=False
                try:self.pet_start('script_structure')
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    self.status.set('自动恢复结构剧本暂缓：'+str(exc))
            self._start_next_queued()
        except queue.Empty:pass
    def _tick_pre_automation(self):
        """在自动阶段调度前回收 Tk 任务并轮询流程进程。"""
        drain_tk_gc()
        try:self.poll_flow_processes()
        except (OSError,ValueError,KeyError):pass
    def _tick_pet_events(self):
        """在本轮自动调度完成后聚合三虎事件，不创建额外线程。"""
        pet_ui.pump(self)
    def auto_final_scan(self):
        """自动定稿的只读扫描（第 72 期 Round 5）：采用清单里还有哪几份没同步、该做哪一份、缺什么。

        返回 dict 四项：sources（采用清单原文）、pending（还没同步成定稿的分镜路径，按采用
        顺序）、target（这一轮该同步的那一份，资产已齐）、source／missing（第一份资产没齐的
        分镜与它缺的编号）。判据与 storyboard_final 的定稿口径同一条：分镜 JSON ＋ 它引用的
        资产都在清单里且有图。04 页那条提示条每 1.5 秒问一次，所以这一份必须只读——不动文件、
        不起批次（「把工作稿移进回收站」那件事只有 poll_auto_final 与手动按钮能做）。
        """
        from storyboard_selection import adopted
        from storyboard_paths import is_final_dir
        from asset_context import references
        from asset_batch_state_service import ready_asset_ids
        try:sources=list(adopted(self.root))
        except (OSError,ValueError,KeyError):sources=[]
        available=ready_asset_ids(self.asset_base())
        pending=[];target=None;blocked=None
        for source in sources:
            path=Path(source)
            if is_final_dir(path.parent.name):continue
            if not path.is_file():continue
            pending.append(path)
            if target is not None:continue
            episode=read(source)
            shots=episode.get('shots',[]) if isinstance(episode,dict) else []
            missing={aid for shot in shots for _,aid in references(shot)}-available
            if missing:
                if blocked is None:blocked=(path,missing)
            else:target=path
        return {'sources':sources,'pending':pending,'target':target,
                'source':blocked[0] if blocked else None,'missing':blocked[1] if blocked else set()}
    def auto_final_target(self):
        """无人值守自动定稿这一轮该做哪一份分镜（第 64 期任务 9）。

        原来只看「当前选择的那一份」：它已经是定稿目录就直接收工，采用清单里其余还没同步的
        分镜永远轮不到——用户报的「自动状态下三虎没有自动同步分镜」。现在按采用顺序挑第一份
        「还是工作稿、引用资产已齐」的；资产没齐的那一份在状态栏说明缺什么，04 页那条提示条
        也同步显示（第 72 期），不挡住别的份。
        """
        scan=self.auto_final_scan()
        if not scan['sources']:
            self.auto_final_signature=None;self.auto_final_notice=None;return None
        if scan['target'] is not None:
            self.auto_final_notice=None;return scan['target']
        missing=scan['missing']
        if missing:
            notice=(str(scan['source']),tuple(sorted(missing)))
            if notice!=self.auto_final_notice:
                self.auto_final_notice=notice
                shown='、'.join(sorted(missing)[:6])+('…' if len(missing)>6 else '')
                self.status.set('无人值守自动定稿暂缓：还缺 '+str(len(missing))+' 项资产图片（'+shown+'）；补齐后会自动定稿')
        else:
            # 剩下的都已经定稿（或被移走）了：别再让提示条挂着上一次那句「还缺…」。
            self.auto_final_notice=None
        return None
    def auto_final_state(self):
        """04 页那条「未同步分镜的可见重试」提示条要显示的东西（第 72 期 Round 5）。

        返回 kind／text／retry／pending／missing 五项：页面拿 text 显示、按 retry 决定
        「立即重试」那颗按钮能不能点。kind 七档：
          off      「自动生成定稿」没勾上
          busy     本轮正在同步资产、生成定稿
          blocked  该动手，但要让正在读这份工作稿的制作批次先跑完
          error    上一轮失败（退避 5 分钟中，点「立即重试」可以马上再来）
          ready    资产齐、等下一轮轮询动手
          missing  还缺资产图片（missing 里是编号，text 报份数并列出最多 6 个）
          done     采用清单里没有要同步的分镜了
        text 尾巴永远带一句「还有 N 份没同步成定稿」——这正是原来只写在状态栏、用户切个页面
        就丢了的那条信息（「无人值守走完采用分镜就静默停住」那条现象）。
        """
        if self.root is None or self.studio is None:
            return {'kind':'off','text':'请先选择项目','retry':False,'pending':0,'missing':()}
        scan=self.auto_final_scan()
        pending=scan['pending']
        shown='、'.join(path.name for path in pending[:3])+('…' if len(pending)>3 else '')
        tail=('还有 %d 份已采用的分镜没同步成定稿（%s）'%(len(pending),shown)) if pending else '已采用的分镜都同步成定稿了'
        def state(kind,text,retry=False,missing=()):
            return {'kind':kind,'text':text+'；'+tail,'retry':retry,'pending':len(pending),'missing':tuple(missing)}
        if not self.pet.should_auto_run('final'):
            return state('off','「自动生成定稿」没勾上：勾上之后资产一补齐就自动同步（定稿会把工作稿移入回收站，可恢复）')
        if self.auto_final_busy:return state('busy','正在同步资产、生成定稿…')
        if self.auto_final_blocked:return state('blocked','自动定稿在等：有制作批次正在读这份工作稿，它跑完就自动接手',retry=True)
        if self.auto_final_error:return state('error','上一轮自动定稿失败：'+self.auto_final_error,retry=True)
        if scan['target'] is not None:
            return state('ready','资产已齐，下一轮轮询就动手（点「立即重试」可以马上做）',retry=True)
        if scan['missing']:
            listed='、'.join(sorted(scan['missing'])[:6])+('…' if len(scan['missing'])>6 else '')
            return state('missing','%s 还缺 %d 项资产图片（%s），补齐后自动定稿；也可以点「立即重试」重扫一遍'
                         %(scan['source'].name,len(scan['missing']),listed),retry=True,missing=sorted(scan['missing']))
        return state('done','当前没有要同步的分镜')
    def retry_auto_final(self):
        """04 页那颗「立即重试」（第 72 期 Round 5）：清掉签名与失败退避，马上再跑一轮自动定稿。

        给「资产刚补齐」「上一轮失败」「刚让完路」这三种情况一个能点的入口——不必等下一个
        30 秒轮询周期，也不用重启。让路规则照旧：真有制作批次在读这份工作稿时，它照样只标一句
        「在等」，不会把人家的批次拆掉。返回这一轮之后该显示的那句话（给状态栏用；页面那条
        提示条自己会重新读一次 auto_final_state）。
        """
        try:
            if self.root is None or self.studio is None:return '请先选择项目'
            if not self.pet.should_auto_run('final'):
                return '未开启「自动生成定稿」：勾上之后资产补齐才会自动同步。'
            self.auto_final_signature=None;self.auto_final_notice=None;self.auto_final_error=''
            self.auto_final_blocked=False;self.auto_final_due=0
            self.poll_auto_final()
            return self.auto_final_state()['text']
        except Exception as exc:
            self.auto_final_error=str(exc)
            return '自动定稿重试失败：'+str(exc)

    def final_storyboard_hint(self,source=None):
        """当前分镜还是工作稿、且引用的资产都已导入时，提示可以去分镜定稿页生成定稿。

        只提示不自动做：生成定稿会把工作稿移入回收站（用户可见的改动），按约定必须由人确认。
        """
        try:source=self.current_frame_json() if source is None else source
        except (OSError,ValueError):return ''
        if not source:return ''
        from storyboard_paths import is_final_dir
        if is_final_dir(Path(source).parent.name):return ''
        episode=read(source)
        shots=episode.get('shots',[]) if isinstance(episode,dict) else []
        if not shots:return ''
        if self.final_missing_assets(source):return ''
        return '；当前分镜引用的资产都已导入，可在'+pet_bus.stage_step('final')+'「分镜定稿」生成定稿（定稿接管后续流程，工作稿移入回收站）'
    def reconcile_storyboards(self):
        """启动对账（第 62 期任务 7）：强制关闭后重开，把已完成的分镜同步进工作集。

        强制关闭可能正好落在 adopt() 与 sync_working_episode() 之间：分镜已经记进采用清单，
        config.json 的 episode_file 还停在旧分镜上。重启后 adopt_pending 看到「没有新东西」
        就早退了，这一步没人补，04 之后各步就还按旧分镜走——用户报的「三虎没有自动同步已经
        完成的分镜」就是这个。这里只补指针，不擅自采用用户没勾「自动采用」的东西。
        """
        from storyboard_selection import repair_working_episode
        try:switched=repair_working_episode(self.root)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            self.status.set('工作集同步暂缓：'+str(exc));return None
        if not switched:return None
        try:
            self.align_studio()
            if getattr(self,'page_index',None) in (PAGE['storyboard'],PAGE['final'],PAGE['keyframe']):
                self.show(self.page_index)
        except (OSError,ValueError,KeyError,TypeError):pass
        self.status.set('已把已完成的分镜同步到工作集：'+Path(switched).name)
        return switched
    def pet_show_text(self,title,text,receipt=''):
        """宠物「查看详情」的只读文本：复用全程序唯一的只读文本窗口（prompt_window），不另造一个。"""
        from prompt_window import show
        return show(self.win,title,text,status=self.status,receipt=receipt,button='复制详情')
    def pet_goto(self,stage):
        """宠物说「切到某一页」时真的把那页翻开（第 23 期）。

        页序号只认 pet_state.PAGE_OF 那一份（阶段枚举与页面一一对应）；没有项目、认不出这一步、
        页面翻不动都返回空串——聊天里先听到一句「切到「剪辑」这一步」然后什么也没发生，比不说还糟。
        返回真正翻过去的那一页标题。
        """
        import pet_state
        index=pet_state.PAGE_OF.get(stage)
        if index is None or self.root is None:return ''
        try:
            self.show(index)
        except Exception as exc:
            self.status.set('切页失败，已忽略：'+str(exc));return ''
        return PAGES[index]
    def pet_advance(self,stage):
        """宠物「自动推进」的接缝（第 23 期）：把这一步对应的无人值守轮询提前叫醒一轮。

        只把 due 拉到当前（下一次心跳就会轮到它），不碰任何开关、不代按任何按钮：
        那一步该不该跑、要怎么跑，仍然由它自己的轮询与用户在页面上勾的开关说了算。
        没项目、这一步没有轮询、正在退避（due 比正常节流周期还远）都原样不动，返回空串。
        """
        name=PET_STAGE_POLL.get(stage)
        if name is None or self.root is None:return ''
        if getattr(self,name+'_busy',False):return ''
        now=time.monotonic()
        if getattr(self,name+'_due',0)>now+UNATTENDED_BACKOFF_FLOOR:return ''
        setattr(self,name+'_due',0)
        import pet_bus
        return '已把「'+pet_bus.STAGE_NAMES.get(stage,stage)+'」这一步提前叫醒一轮'
    def pet_start(self,stage):
        """第 67 期任务 5：三虎在自动档要「自动开始每个阶段的任务」。

        先把这一步的无人值守开关替他打开（用户不必自己回页面上勾），再把它提前叫醒一轮——
        开关一开，这一步的轮询从此每一轮都会接着做，直到做完（中途断了也照旧自己接着做）。
        剧本结构虽没有常驻轮询，但有一条与手动按钮相同的确定性模板执行链，单独派发；
        其余没有无人值守的步骤（剧本、连贯性、配音）老实给空串，让宠物自己说「没有能自动跑的路子」。
        """
        return stage_handler_registry.start(self,stage,trigger='auto',fallback=self._start_unattended_stage)
    def _start_unattended_stage(self,stage,trigger):
        """尚未拆出的无人值守阶段由 L3 启动适配器回调到此处。"""
        if self.root is None:return ''
        if stage=='script_structure':return self.pet_script_structure_batch(trigger=trigger)
        # 首帧不是普通的轮询开关：自动链需要立即把当前缺口派发，并由批次的
        # completed/failed 事件收场。经 L3 转到这里，避免 Pet UI 再另走一条直连路径。
        if stage=='keyframe':return self.pet_frame_batch(trigger=trigger)
        name=PET_STAGE_POLL.get(stage)
        if name is None:return ''
        import project_settings,pet_bus
        turn_on=getattr(project_settings,UNATTENDED_SWITCH.get(name,''),None)
        if callable(turn_on):
            try:turn_on(self.root,True)
            except (OSError,ValueError,KeyError,TypeError):pass
        title=pet_bus.STAGE_NAMES.get(stage,stage)
        if self.pet_advance(stage):
            return '已自动开始「'+title+'」：无人值守已打开，跑完自己往下走'
        return '「'+title+'」这一步已经在跑，等它收尾'
    def pet_storyboard_batch(self, trigger='manual'):
        """第 62 期任务 2：三虎要「自动制作分镜」时走这一条——与「手动制作分镜」同一份实现。

        没有可做的输入（没勾剧本、或勾中的都做好了）返回空串，让宠物自己说「没有要做的事」；
        真的派了就返回一句人话。派发本身是异步的（work 在后台线程里算），失败那句会走
        「操作未完成」的既有出口，不在这里另造一套。
        """
        return stage_handler_registry.start(self,'storyboard',trigger=trigger)
    def batch_blockers(self,source,pending):
        """用引擎自己的逐镜检查（batch_frames.shot_inputs）列出无法生成的镜头与原因。

        与批次内部判定的口径完全一致：只有真正能出图的镜头才值得启动一次批次。
        """
        from batch_frames_tool.batch_frames import load_assets,shot_inputs
        assets=load_assets(source);result=[]
        for shot in pending:
            try:shot_inputs(shot,media_root(source),assets)
            except ValueError as exc:result.append((shot['id'],str(exc)))
        return result
    def busy_reason(self):
        """当前拦着退出的那件事（没有就返回空串）。

        第 47 期第 7 条从 close 里拆出来：关窗要先知道「在等什么」，才问得出那句「要强制关闭吗」。
        """
        if getattr(self,'previs_jobs',{}).get('busy'):return '白模预演正在制作'
        if self.worker:return '有一步 Agent 任务或批量任务正在执行'
        if self.cloud_monitor_busy:return '正在查询线上任务'
        if any(v.busy or getattr(v,'optimizer_busy',False) for v in self.video_sessions.values()):
            return '视频提交、下载或提示词优化正在跑'
        return ''
    def close(self):
        if getattr(self,'_closing',False):return
        reason=self.busy_reason()
        if reason:
            # 若根窗口仍在任务栏最小化，确认框会跟着藏起来，用户既看不到主界面
            # 也无法选择“强制关闭”。先经宠物的唯一恢复入口把根窗口带回前台。
            pet=getattr(self,'pet',None)
            if pet is not None:
                try:pet.show_main()
                except Exception:app_logging.swallowed()
            # 第 47 期第 7 条：原来这里只弹一句「请等待…结束后退出」就什么都不做——白模那一批
            # 卡住时用户就再也关不掉程序了（用户报的「无法关闭程序」）。现在问一句：答「是」就把
            # 还在跑的进程收掉再退；答「否」照旧守着，等这一步自己结束。
            if not confirm(self.win, '仍在处理', reason+'。\n\n现在强制关闭程序吗？\n中断这一步不会删掉已经做好的成果，下次打开可以接着做。\n若正在调用付费模型或线上任务，中断不会撤销远端调用，仍可能继续执行并按实际用量计费。', dangerous=True):return
            return self.force_quit()
        if self.pet_hides_instead_of_quitting():return
        self._closing=True
        self.flush_brief()
        # 第 36 期第 5 条：原来这里会借三虎递一张日报／周报标签框、并把真关推迟几秒（标签框才有
        # 时间渐入）。用户要「删除日报和周报的关闭前弹框逻辑」——关就是关；报表改由三虎在下午／
        # 夜里活儿慢下来时自己递上来（见 pet_ui.Pet.report_hint）。
        self.finish_close()
    def force_quit(self):
        """强制关闭（第 47 期第 7 条）：先把还在跑的引擎进程与白模批次收掉，再照常收摊。

        收不干净也照样退：这几件事都是尽力而为，用户要的是「关得掉」，不是「等它跑完」。
        """
        self._forcing_quit=True
        state=getattr(self,'previs_jobs',None)
        if isinstance(state,dict) and state.get('busy'):
            try:
                from previs_automation import force_stop
                force_stop(self.root,state)
            except Exception as exc:
                print('强制关闭：白模批次未收干净（'+str(exc)+'）')
        self.stop_automation_processes()
        self._closing=True
        try:self.flush_brief()
        except Exception:app_logging.swallowed()
        self.finish_close()
        return True
    def stop_automation_processes(self):
        """关闭本窗口派发的自动／交互式制作进程，不触碰用户自行启动的终端。"""
        if getattr(self,'_automation_processes_stopped',False):return []
        self._automation_processes_stopped=True
        if self.root is None:return []
        try:
            from workflow_engines import terminate
            killed=terminate(self.root)
        except Exception as exc:
            print('关闭：引擎进程未收干净（'+str(exc)+'）')
            return []
        self.flow_processes={}
        return killed
    def finish_close(self):
        """真的收摊：停表、停监视页、销毁窗口、清一次缓存（第 18 期从 close 里拆出来）。"""
        self.cancel_timers()
        # 未标记 busy 的已派发任务也随程序退出，避免后台模型留存并拖慢下一次启动。
        self.stop_automation_processes()
        # 第 47 期第 2 条：白模那个浏览器监视页跟着程序一起收，端口不留着。
        state=getattr(self,'previs_jobs',None)
        if isinstance(state,dict) and state.get('monitor'):
            try:
                from previs_monitor import stop as stop_monitor
                stop_monitor(state)
            except Exception:app_logging.swallowed()
        try:
            import asset_thumbs
            asset_thumbs.forget()
            asset_thumbs.reset_worker()
        except tk.TclError:
            # 关窗清理仅忽略 Tk 生命周期竞态。
            pass
        self.win.destroy()
        from exit_maintenance import launch_cleanup
        launch_cleanup(self.app, forced=getattr(self, '_forcing_quit', False))
    def pet_report(self,stage,text,ok=True):
        """第 47 期第 5 条：某一步的制作收了尾，说给三虎听——各页共用这一条出口。

        成了当场播报（pet.report_done）；没成仍走原来那条「待确认清单」（pet.drain），
        由三虎按自动化等级决定重试还是问用户。宠物不在（自检里的宿主）就什么都不做。
        """
        pet=getattr(self,'pet',None)
        if pet is None:return None
        # 宠物报告是阶段状态链的一部分；真实报告器故障必须让调用者看见，
        # 不能把完成／失败事件吞成“页面看似正常”。没有宠物的假宿主仍是无操作。
        if ok:return pet.report_done(str(stage),str(text))
        return pet.drain(str(stage),(False,str(text),None))
    def pet_at_stage(self,index,*,automatic=False):
        """进入制作页交给三虎统一协调：提示进度、半自动征询或全自动按 SKILL 执行。

        宠物不在、问不出来都不影响翻页——它只是搭一句话，不参与页面本身。
        """
        pet=getattr(self,'pet',None)
        if pet is None:return ''
        try:
            # 启动自动进页不得抢先打开聊天框；用户主动切页不受静默限制。
            if automatic and pet.quiet():return ''
            return pet.enter_stage(index)
        except Exception:return ''
    def pet_hides_instead_of_quitting(self):
        """常驻模式（配置里明确开）：关主窗口＝收进宠物窗，不退出。

        只有独立窗真的起来了才拦这一步：收不起来还硬拦，用户就再也关不掉程序了。
        """
        if getattr(self,'_forcing_quit',False):return False
        pet=getattr(self,'pet',None)
        if pet is None:return False
        try:return bool(pet.hide_to_pet())
        except Exception:return False
    def reload(self):
        self.fill_projects(self.list)
        self.schedule_sidebar_fit()
        tree=getattr(self,'_project_home_tree',None)
        if tree is not None and tree.winfo_exists():self.fill_projects(tree)

    def flush_brief(self):
        """第 65 期任务 9：翻页只丢引用，不再自动另存——对话结束前一个字都不落盘。

        原来翻页会把创意栏里改过的字偷偷存成一份 创意_ 文件；现在这一页是跟模型对话，
        落盘只有一条路：模型给出剧本、用户点了「是」，见 confirm_script。
        """
        self.preserve_idea_draft()
        self.brief_editor=None
    def load(self,path,*,defer_page=False):
        from stage_execution_service import recover_stage_publications
        recover_stage_publications()
        # 第 45 期：项目文件夹被移走／删掉时，先给一句能照做的话——原来会一路抛到
        # 「[Errno 2] No such file or directory: …」这种原始报错，用户看不懂也不知道删哪一项。
        if path and not Path(path).is_dir():
            service=getattr(self,'projects',None)
            if service is not None:
                recovered=self._project_result_data(service.reconcile_missing(path))
                if recovered.get('state')=='claimed':
                    original_path=path
                    path=recovered['path']
                    self._sync_desktop_project_paths(original_path,path)
                    # 认领已替换登记路径，先同步以路径为 iid 的侧栏再选择新项目。
                    self.reload()
                    self.status.set('已按新位置同步项目登记')
                elif recovered.get('state')=='confirm':
                    raise ValueError('项目目录已被改名，找到多个候选目录；请在项目选择窗口点击“重新查找项目”后选择。')
            if not Path(path).is_dir():
                raise ValueError('项目目录不存在或已被移动：'+str(path)
                                 +'。未找到可自动认领的目录；可“重新查找项目”或只清除登记，不动磁盘。')
        # ``Studio`` 服务于初步分镜之后的工作集，初始化时会要求
        # episode.json。剧本准备/剧本结构尚未产出分镜时不能因此拒绝打开
        # 项目，更不能误报“剧本已删除”；后续页面会经 align_studio() 延迟建立。
        studio=None
        if path:
            try:
                studio=open_studio(Path(path))
            except ValueError as exc:
                if not is_missing_storyboard_open_error(exc):
                    raise
        self.flush_brief()
        if self.root != (Path(path) if path else None) and self.idea_chat_controller.requesting:
            self.interrupt_script_agent()
        self.root=Path(path) if path else None;self.studio=studio
        if path:
            # 第 68 期任务 9：把「当前项目」记进 projects.json 只是记账——记账这一步失败
            # （程序目录只读、杀毒软件锁住 projects.json、磁盘满…）绝不该把「打开项目」拦下来，
            # 更不该弹一句「无法打开项目：[Errno 2] No such file or directory：…」让用户无从下手。
            try:
                self._project_result_data(self.projects.activate(str(self.root)))
            except (OSError, ValueError) as exc:
                # 打开仍可继续，但必须明确告知“本次项目未记为当前项目”，
                # 否则下次启动回到旧项目会被误认为无响应或打开错误。
                self.status.set('项目已打开，但当前项目登记未同步：%s；请稍后重新打开项目。' % exc)
            self.list.selection_set(str(self.root));self.list.see(str(self.root))
            self.mark_current_project()
        else:
            selected=self.list.selection()
            if selected:self.list.selection_remove(*selected)
        if defer_page:
            # 先把已映射的壳交还给 Windows；剧本准备页本身控件很多，不能与
            # 自动续开项目挤在同一首帧回调里。
            self.status.set('正在载入今日项目…')
            target=self.root
            def show_loaded_project():
                self._startup_project_page_job=None
                if not self.shutting_down and self.root==target:
                    # 只在真实的自动续开建页期间延后云朵量测；测试和普通手动
                    # 页面不应继承这段启动期限制。
                    self.win._desktop_loading_project=True
                    try:self.show(0)
                    finally:
                        self.win._desktop_loading_project=False
                        # ``show(0)`` 会先交出一个可见的剧本准备壳；完整页面
                        # 尚未建完时，恢复维护也必须跟着后移，不能抢在壳之前阻塞。
                        if self._startup_script_build_job is None:
                            self._request_tick_resume_after_first_paint()
                            self._schedule_project_recovery(target)
            # 只让出一个可见绘制周期，不能用 ``after_idle``，否则紧随其后的
            # update() 仍会在首帧调用栈内建整页控件。此前这里固定等 1 秒，
            # 实际上会把项目选择页连同“正在载入”留在屏幕上，误导为启动卡死。
            # 80ms 足以交还 Windows 绘制，又不会成为一次可感知的假等待。
            self._startup_project_page_job=self.win.after(10 if self._startup_window_held() else 80,show_loaded_project)
        else:
            self.show(0)
        self.asset_detail_id=None            # 第 64 期任务 13：换项目／换目录回到主页面
        # 第 62 期任务 7：换项目要重扫——原来跨项目沿用上一份指纹，新项目正好撞上同样的
        # （份数，最新写入时间）就会被跳过；顺手把「启动对账」重新排上。
        self.auto_adopt_signature=None;self.auto_adopt_pending=False;self.auto_adopt_startup=True
        if path:
            self._schedule_stage_model_sync(self.root)
            if not defer_page:
                self._complete_project_recovery(self.root)
        if not defer_page and getattr(self,'_startup_tick_paused',False):
            self._request_tick_resume_after_first_paint()



    def ensure_stage_layout(self):
        """按需补齐「阶段目录 ＋ 固定子目录」。

        只建缺的、绝不覆盖已有文件；目录树是给人和 Agent 看的骨架，缺了照旧能干活，
        所以失败不拦住「打开项目」，但必须明确提示用户阶段目录尚未补齐。
        """
        if not self.root:return []
        try:
            from stage_layout import ensure
            return ensure(self.root)
        except Exception as exc:
            self.status.set('阶段目录未补齐：%s；请稍后重试。' % exc)
            return []
    def sync_stage_models(self, project=None):
        """第 59 期第 12 条：这个项目里各页面挑过的模型补进模型池（设置 → 模型配置 里也跟着有）。"""
        from skill_panel import program_of, sync_models
        return sync_models(project if project is not None else self.root, program_of(self))
    def _schedule_stage_model_sync(self, project):
        """模型对账不占用启动 UI 线程；结果按项目代次回填。"""
        self._stage_model_sync_generation+=1
        generation=self._stage_model_sync_generation
        target=Path(project) if project else None
        def work():
            try:result=self.sync_stage_models(target)
            except (OSError,ValueError,TypeError,KeyError) as exc:
                # 工作线程只带错误结果回主线程；不能在这里直接操作 Tk 状态栏。
                result={'error':str(exc), 'kind': 'bug'}
            self._stage_model_sync_results.put((generation,target,result))
            # 总控（00全流程SKILL）有更新就自动同步各阶段；只把提示文字带回主线程。
            if target is None:return
            try:
                from master_skill import sync as sync_master_skill
                message=sync_master_skill(target).get('message','')
            except (OSError,ValueError,TypeError,KeyError) as exc:
                message='总控同步未完成：%s；请打开阶段配置重试。' % exc
            if message:self._stage_model_sync_results.put((generation,target,{'master':message}))
        threading.Thread(target=work,daemon=True).start()
    def _tick_stage_model_sync_result(self):
        try:generation,target,result=self._stage_model_sync_results.get_nowait()
        except queue.Empty:return
        if generation!=self._stage_model_sync_generation or target!=self.root:return
        if isinstance(result,dict) and result.get('master'):
            self.status.set(result['master'])
            return
        if isinstance(result,dict) and result.get('error'):
            LOGGER.warning('项目模型同步失败：%s', result['error'])
            self.status.set('项目模型同步未完成：%s；请稍后重试。' % result['error'])
            return
        if result:self.status.set('已同步项目模型：'+'、'.join(result))
    def switch(self,event=None):
        selected=self.list.selection()
        if not selected or selected[0].startswith('group:'):return
        path=selected[0]
        if Path(path)!=self.root:self.safe(lambda:self.request_project_switch(path))

    def new(self):
        name=simpledialog.askstring('新建项目','项目名称：',parent=self.win)
        if name:
            p=self._project_result_data(self.projects.create(name));self.reload();self.load(p)
            self.remember_daily_project_choice(p)
            self._startup_project_choice=False
        elif getattr(self,'_startup_project_choice',False) and self.root is None:
            self._startup_project_choice=False
            if not getattr(self,'shutting_down',False):
                if self.status.get()=='正在打开今日项目…':
                    self.status.set('未选择项目，可创建新项目。')
                self._request_tick_resume_after_first_paint()
    def import_json(self):
        if self.root:
            from stage_workspace_service import ensure_storyboard_workspace
            result=ensure_storyboard_workspace(self.root)
            if not result.ok:raise ValueError(result.reason)
            base=result.data
        else:
            base=self.projects.base
            base.mkdir(parents=True,exist_ok=True)
        p=FileDialog(self.win).open_file(initialdir=base,filetypes=[('镜头 JSON','*.json')])
        if p:
            source=Path(p)
            # 文件选择框有时会交回外部工具解包出来的临时文件。原来随后把 create()
            # 丢进后台队列，临时目录已被清理时才读取 episode.json，便会冒出 WinError 3。
            # 导入本身必须在来源仍存在的这一刻完成；文件不存在则给出可操作的提示。
            if not source.is_file():
                raise ValueError('所选分镜文件已不存在（临时文件可能已被清理）。请重新选择并导入 JSON。')
            data=read(source)
            if not isinstance(data,dict):raise ValueError('请选择有效的镜头 JSON（顶层必须为对象）')
            name=data.get('title') or source.stem
            previous=self.win.cget('cursor')
            try:
                self.win.configure(cursor='watch');self.win.update_idletasks()
                result=self._project_result_data(self.projects.create(name,source))
            finally:
                self.win.configure(cursor=previous)
            self.reload();self.load(result)
            self.remember_daily_project_choice(result)
    def page_of(self,stage):
        """阶段 → 页序号（第 62 期任务 11：别的模块要认页时也不用写死数字）。"""
        return PAGE.get(stage)
    def show_stage(self,stage,video_mode=None):
        """按阶段名换页：序号从阶段表推，与侧栏上那一格是同一页。"""
        index=PAGE.get(stage)
        return self.show(index,video_mode=video_mode) if index is not None else None
    def go_page(self,index):
        """侧栏导航的入口（第 48 期第 3 条）。

        「10 视频生成」这一格要记住用户第一次选的那一侧：本次启动第一次点它先摆「选择生成方式」，
        选定之后再点就直接进那一侧；想换一侧用页里的「返回生成方式」。
        """
        if index==PAGE['assets']:self.asset_detail_id=None;self.asset_roster=False
        mode='choose' if (index==PAGE['video'] and not getattr(self,'video_mode_picked',False)) else None
        # 即刻反馈最后一次点击，包括连续点击后又回到当前页的情况。
        try:
            for i,b in enumerate(self.nav):b.configure(style='Selected.Nav.TButton' if i==index else 'Nav.TButton')
            self.title.configure(text=PAGES[index])
        except (tk.TclError,IndexError,AttributeError):pass
        pending=getattr(self,'_navigation_job',None)
        if pending is not None:self.win.after_cancel(pending)
        project=self.root
        def navigate():
            self._navigation_job=None
            if getattr(self,'shutting_down',False) or self.root!=project:return
            self._reuse_cached_page=True
            try:self.go(index,video_mode=mode)
            finally:self._reuse_cached_page=False
        self._navigation_job=self.win.after_idle(navigate)
    def go(self,index,video_mode=None):
        """侧栏导航专用：页面构建失败时给出提示，而不是留下一个空白页。

        用 .pyw 启动时没有控制台，未捕获的异常只有一条看不见的 stderr traceback，用户面对的
        就是一个空白内容区。这里换成一条读得懂的提示。与 self.safe 不同：不因后台任务在跑
        而拦下翻页（批次期间必须能切换页面）；程序内的其他位置仍直接调 show()，
        这样页面真出问题时会照旧抛出异常，不会被测试漏掉。

        第 35 期第 4 条：video_mode 原样透给 show()——侧栏点「10 视频生成」时传 'choose'。
        """
        try:self.show(index,video_mode=video_mode)
        except Exception as exc:self.notifier.error(str(exc), title='页面无法显示')
    def _page_cache_for(self,index,*,same_page):
        """整页缓存（CACHED_PAGES）：只在侧栏点回来时复用；同页重建、换项目一律作废重建。

        缓存页各有一块自己的内容框（画布的子框），不挂在公共内容框下：收起来时既不显示，
        也不会被按 self.content 遍历控件的代码数到。换页先把画布换回公共内容框。
        """
        base=getattr(self,'_base_content',None)
        if base is None:base=self._base_content=self.content
        if self.content is not base:
            self.content=base
        cache=getattr(self,'_page_cache',None)
        if cache is None:cache=self._page_cache={}
        for key,entry in list(cache.items()):
            stale=entry['root']!=self.root or not entry['holder'].winfo_exists()
            if not stale and key==index==PAGE['script_structure']:
                from script_workspace_service import script_structure_signature
                stale=entry.get('signature')!=script_structure_signature(self.root)
            if stale or (key==index and (same_page or not getattr(self,'_reuse_cached_page',False))):
                cache.pop(key)
                if entry['holder'].winfo_exists():entry['holder'].destroy()
        # 命中时直接从旧页换到目标页，避免先映射公共空框再映射缓存页的两次布局。
        if index not in cache:self.canvas.itemconfigure(self.content_id,window=base)
        return cache
    def _show_cached_page(self,index,builder,cache):
        """建过且仍有效就直接换上（控件、文件监听都还在），否则新建一块内容框建页并留存。"""
        entry=cache.get(index)
        if entry is not None:
            self.content=entry['holder']
            self.canvas.itemconfigure(self.content_id,window=self.content)
            self.stage_button=entry['stage_button']
            if entry['note']:self.status.set(entry['note'])
            return
        holder=ttk.Frame(self.canvas)
        holder.bind('<Configure>',self.fit_content)
        self.content=holder
        self.canvas.itemconfigure(self.content_id,window=holder)
        builder()
        note=self.status.get()
        cache[index]={'holder':holder,'root':self.root,'stage_button':self.stage_button,
                      'note':'' if note==str(self.root) else note}
        if index==PAGE['script_structure']:
            from script_workspace_service import script_structure_signature
            cache[index]['signature']=script_structure_signature(self.root)
    @app_logging.timed('page.show',800)
    def show(self,index,video_mode=None):
        pending=getattr(self,'_navigation_job',None)
        if pending is not None:
            self.win.after_cancel(pending)
            self._navigation_job=None
        from video_navigation import hide_back
        hide_back(self)
        # 同一页重建（切换分镜、刷新列表、自动流程刷新）保留原来的滚动位置：
        # 旧行为每次都把整页拉回顶部，换文件时看起来就是「内容抖动」。换页仍回到顶部。
        previous_index=getattr(self,'page_index',None)
        if previous_index==PAGE['script']:
            self._idea_brief_generation=getattr(self,'_idea_brief_generation',0)+1
            self.preserve_idea_draft()
        scroll_offset=self.canvas.canvasy(0) if previous_index==index else 0
        self.page_index=index
        # 第 71 期任务 2：资产详情页与资产清单页都是「05 资产管理」的子路由；翻到别的页就回主页面。
        if index!=PAGE['assets']:self.asset_detail_id=None;self.asset_roster=False

        if index==PAGE['video']:
            self.progress.pack_forget();self.status_label.pack_forget()
        else:
            self.progress.pack(fill='x',pady=(8,0));self.status_label.pack(fill='x',pady=6)
        if index==PAGE['video']:
            prefs_path=self.root/'ui_settings.json' if self.root else None
            prefs=_prefs(prefs_path)
            # 第 32 期第 3 条：本次启动第一次进这一页，先摆「选择生成方式」；用户在这里选过一次
            # 之后，来回切页仍按他刚选的那个模式进，不会被反复拦在选择页上。
            if video_mode=='choose':
                self.video_mode=None;self.video_mode_picked=False
            elif video_mode:
                self.video_mode=video_mode
            else:
                self.video_mode=prefs.get('last_video_mode') if getattr(self,'video_mode_picked',False) else None
            if self.video_mode in ('cloud','local'):
                self.video_mode_picked=True
                if prefs_path and prefs.get('last_video_mode')!=self.video_mode:
                    from stage_execution_service import publish_cloud_video_workspace_preference
                    prefs['last_video_mode']=self.video_mode
                    publish_cloud_video_workspace_preference(prefs_path,prefs)
        else:self.video_mode=None
        if self.video:
            self.video.window.pack_forget()
            self.video.footer.pack_forget()
            self.video=None
        self.flush_brief()
        retained={v.window for v in self.video_sessions.values()}
        page_cache=self._page_cache_for(index,same_page=previous_index==index)
        for c in self.content.winfo_children():
            if c in retained:c.pack_forget()
            else:c.destroy()
        for i,b in enumerate(self.nav):b.configure(style='Selected.Nav.TButton' if i==index else 'Nav.TButton')
        # 第 71 期任务 2：二级入口只在它自己那一屏高亮
        if self.asset_list_button is not None:self.asset_list_button.configure(style='Selected.Sub.Nav.TButton' if (index==PAGE['assets'] and self.asset_roster) else 'Sub.Nav.TButton')
        self.header_status.configure(text='',textvariable='');self.header_model.configure(text='');self.title.configure(text=PAGES[index]);self.status.set(str(self.root))
        self.stage_button=None                 # 那一行随页面重建：旧按钮这会儿已跟着 content 一起销毁
        if self.header_stage_button is not None:
            self.header_stage_button.destroy();self.header_stage_button=None    # 页标题旁那颗同理
        # 只有真正换页才回到顶部：同一页重建（切换分镜、刷新列表）保留当前位置，否则看起来就是内容抖动。
        if not scroll_offset:
            self._pending_scroll_restore=None
            self._pending_scroll_layout=None
            self.canvas.yview_moveto(0)
        if index==PAGE_SITES:
            self.reference_sites()
            # 参考网站页和普通制作页一样会在这里新增内容；不能因为提前返回而把
            # Canvas window 留在建壳时量到的 1px 高度。
            self.fit_content()
            return
        if self.root is None:
            self.title.configure(text='我的项目');self.status.set('选择项目开始创作');self.project_home()
            # 首屏此前在这里提前返回，项目树虽已创建却没有重新量画布；窗口刚映射时
            # content window 常仍是 1px 高，于是用户只看到白屏和底部状态栏。
            self.fit_content()
            return
        # 第 26 期第 3 条：07 步还没选生成方式时不需要分镜——「选择分镜」下拉框与那道
        # 「先采用分镜」的闸门都留到选定方式之后，选定方式那一页本来也不挑镜头。
        choosing_video=index==PAGE['video'] and getattr(self,'video_mode',None) not in ('local','cloud')
        if index in (PAGE['keyframe'],PAGE['previs']) or (index==PAGE['video'] and not choosing_video):
            from storyboard_selection import prefs
            if prefs(self.root).get('adopted_storyboards')==[]:
                message='请先在'+pet_bus.stage_step('storyboard')+'采用一份或多份分镜 JSON。'
                # 不能只写到底部状态栏：视频工作台被阻止时，用户的视线仍在当前内容区。
                ttk.Label(self.content,text=message,style='Muted.TLabel').pack(anchor='w',padx=SPACING['lg'],pady=18)
                self.note(message)
                self.fit_content()
                return
        if PAGE['assets']<=index<=PAGE['audio'] and not choosing_video and not (index==PAGE['assets'] and (getattr(self,'asset_detail_id',None) or getattr(self,'asset_roster',False))):
            from storyboard_selection import source_selector
            source_selector(self,index,select_box=SelectBox)
        # 08／09 步直接读工作集：切换分镜或自动采用后必须先让工作集跟上，否则会按旧分镜拼接和交付。
        if index in (PAGE['edit'],PAGE['delivery']):self.align_studio()
        if index==PAGE['script'] and getattr(self.win,'_desktop_loading_project',False):
            # 自动续开原先在一个 Tk 回调中拆掉“我的项目”再同步建完整剧本页，
            # Windows 因而一直只能显示旧页。先摆出当前阶段的轻量壳，等一个
            # 确定的绘制时隙后才创建聊天、文件表和它们的绑定。
            target=self.root
            ttk.Label(self.content,text='剧本准备',font=('Microsoft YaHei UI',16,'bold')).pack(anchor='w',padx=SPACING['lg'],pady=(18,6))
            ttk.Label(self.content,text='正在打开剧本准备…',style='Muted.TLabel').pack(anchor='w',padx=SPACING['lg'])
            self.status.set('正在打开剧本准备…')
            self.fit_content()
            def build_startup_script_page():
                # 启动画面还盖着时直接在幕后建完整页：揭开后用户看到的就是完整页面。
                # 过去先揭开轻量壳再同步建页，建页期间 Windows 无法重绘，主窗口会整片发白。
                self._startup_script_build_job=None
                if getattr(self,'shutting_down',False) or self.root!=target or self.page_index!=PAGE['script']:
                    # 延后建页可能因用户切页而取消；tick 的解冻不应依赖建页成功，
                    # 否则异步创意结果会永远留在队列中。
                    self._request_tick_resume_after_first_paint()
                    return
                for child in self.content.winfo_children():child.destroy()
                self.writing()
                self.status.set(str(self.root))
                self.fit_content()
                self.pet_at_stage(PAGE['script'],automatic=True)
                self._request_tick_resume_after_first_paint()
                self._schedule_project_recovery(target)
            # 不能用 after_idle：空闲队列会在 Windows 处理首帧绘制之前继续执行，
            # 仍会把完整建页压回同一帧。40ms 给出一次实际消息循环机会。
            self._startup_script_build_job=self.win.after(40,build_startup_script_page)
            return
        if index==PAGE['assets'] and getattr(self,'asset_roster',False):
            # 第 71 期任务 2：侧栏「资产清单」那一格摆的是清单页（每个角色的正典板与状态变体）。
            from asset_detail import show_roster
            show_roster(self)
        elif index==PAGE['assets'] and getattr(self,'asset_detail_id',None):
            # 第 64 期任务 13：资产详情页是资产管理页的子路由（附件 v3.0 任务 2.1／2.3）。
            from asset_detail import show as asset_detail_page
            asset_detail_page(self,self.asset_detail_id)
        else:
            builder=[self.writing,self.script_structure,self.storyboard_creation,self.animatic_page,self.asset_page,self.continuity_page,self.final_storyboard,self.storyboard,self.previs,self.videos,self.audio,self.editing,self.delivery][index]
            if index in CACHED_PAGES:self._show_cached_page(index,builder,page_cache)
            else:builder()
        # 页面树可能很大；强制 Tk 立刻完成两次尺寸计算会阻塞点击与绘制，启动时尤其容易
        # 被 Windows 判为无响应。交给已有的合并空闲布局：同一轮连续换页只做最后一次，
        # 内容尺寸晚到时由 _fit_again 补算，首帧也能先交还事件循环。
        if scroll_offset>0:
            self._pending_scroll_restore=scroll_offset
            self._pending_scroll_layout=None
        self.fit_content()
        # 第 36 期第 6 条：换阶段了，三虎主动问一句能做什么。气泡重排会强制整窗同步布局，
        # 当场播报会把新页的首帧压到它后面；等新页先画出来再说，连续换页只说最后一页。
        job=getattr(self,'_pet_stage_job',None)
        if job is not None:
            try:self.win.after_cancel(job)
            except tk.TclError:pass
        def speak():
            self._pet_stage_job=None
            if self.page_index==index and not getattr(self,'shutting_down',False):self.pet_at_stage(index)
        # 1ms 会在布局尚未结束时到期，气泡的同步重排仍抢在首帧之前。
        # 留出短暂导航稳定期；期间再次切页会取消旧播报。
        try:self._pet_stage_job=self.win.after(150,speak)
        except tk.TclError:self._pet_stage_job=None

    def text(self,value,height=10):
        t=TextArea(self.content,bg=COLORS['background_card'],fg=COLORS['text_primary'],insertbackground=COLORS['primary'],height=height,wrap='word',font=('Microsoft YaHei UI',11),relief='flat',padx=SPACING['md'],pady=SPACING['md']);t.insert('1.0',value);t.pack(fill='both',expand=True,pady=SPACING['sm']);bind_show_all(t,after=self.fit_content);return t
    def note(self,value):
        """把页面操作说明写入共享绿色信息栏，不再额外占一行。"""
        text=' '.join(str(value or '').split())
        if not text:return None
        self.status.set(text)
        return self.status_label
    def header_stage_config(self,index):
        """页标题右边那颗「阶段配置」（第 41 期第 2 条）。

        没有「手动XX」那一行的页面（分镜定稿／配音与字幕／后期剪辑／质检与交付）就摆在这里：
        原先只有分镜定稿手写了两行，下游三页因此一个入口都没有，11 个阶段的模型＋SKILL
        面板里那三块从界面上点不进去。按钮随页面重建一起销毁（见 show()）。
        """
        self.header_stage_button=ui_plugin_registry.module('skill_panel').stage_button(self.title_row,self,index)
        self.header_stage_button.pack(side='left',padx=(12,0))
        return self.header_stage_button
    def storyboard_creation(self):
        from storyboard_files import show
        show(self)
    # 第 29 期第 1 条：页面上那几处重复的「Model ＋ SKILL」控制行整个拿掉——入口只留那颗
    # 「阶段配置」。第 32 期第 6 条起它不再集中在剧本准备页，而是各阶段页「手动XX」右边各一颗
    # （见 skill_panel.stage_button），模型／SKILL／接口／说明都在面板里。
    # flow_settings 留着：首帧页的「Skill 调用设置」在模型接口窗口里还要用它（第 26 期那处）。
    def flow_settings(self,stage,function=None):
        from workflow_settings import show_settings
        if self.root is None:raise ValueError('请先选择项目')
        from workflow_agents import refresh
        show_settings(self,self.root,stage=stage,on_saved=lambda:refresh(self),function=function)
    def open_storyboard_skill(self,key=None):
        batch={}
        def work():
            from stage_execution_service import storyboard_produced_scripts as produced_scripts
            from storyboard_selection import selected_many
            from workflow_tasks import storyboard_batch_prompt
            scripts=selected_many(self.root,'script');existing=selected_many(self.root,'storyboard')
            made=produced_scripts(self.root);already=[p for p in scripts if p in made]
            prompt,followup=storyboard_batch_prompt(self.root,scripts,existing)
            batch.update(prompt=prompt,followup=followup)
            # 跳过已有定稿的剧本是无损操作：直接继续，避免模态确认挂住无人值守流程。
            if not already:return '正在启动分镜制作 agent…'
            return '已跳过 '+str(len(already))+' 个已制作分镜的剧本：'+'、'.join(Path(p).name for p in already)+'；继续处理其余剧本／分镜。'
        def finish(message):
            # 异步准备阶段的结果原来只作为回调参数传入，界面一直停留在
            # 「正在处理」；批量跳过已有分镜时，必须把实际处理结果反馈出来。
            self.open_flow_agent('storyboard','初步分镜',batch['prompt'],batch['followup'])
            self.status.set(message)
        # 结果经异步队列回到主线程：工作线程直接调用 winfo_exists／after 在 Tk 里会抛
        # RuntimeError: main thread is not in main loop，表现为「点了按钮没有反应」。
        self.async_(work,finish)
    def open_codex_skill(self,folder,brief,value):
        """兼容旧入口：仍只启动工作流，绝不回退为直连模型对话。"""
        creative=str(value or '').strip()
        if not creative:
            raise ValueError('请先输入创意，再启动剧本 Agent。')
        return self.start_script_workflow(creative)

    # ── 第 61 期 v0.8：正典板／状态变体（任务 3／5）的折叠区・连贯性清单（任务 7）独立成页 ──
    def copy_text(self,text):
        """把一段文字复制到剪贴板（锚点字符串逐字复用）。

        第 61 期 v0.8：全程序只有 prompt_window.copy_text 写剪贴板（既有规矩），这里只转调一次。
        """
        from prompt_window import copy_preview,copy_text as write_clipboard
        reason=write_clipboard(self.win,str(text))
        self.status.set('复制失败：'+reason if reason else '已复制：'+copy_preview(text))
        return reason
    def pick_gate(self,key,choice,again=None,digest=''):
        """记一次人工确认，顺手把选择写进资产、再刷面板（第 64 期任务 6）。

        原来只调用 record()：选择进的是 gate_confirmations.json，资产清单里该写的
        canonical_board／character_anchor 一个字没写——「采用推荐」点了资产还是空的。
        现在与资产详情页走同一条写入路径（confirm_gates.apply_choice）。
        """
        from stage_execution_service import record_stage_confirmation
        from stage_execution_service import apply_asset_plan_gate_choice
        apply_asset_plan_gate_choice(self.root,key,choice)
        path=record_stage_confirmation(self.root,key,choice,digest=digest)
        if again:again()                      # 先重建页面（重建会重置状态栏），再写状态栏
        self.status.set('已确认：'+str(choice))
        return path
    def gate_level(self):
        """三虎当前那一档（hint／semi／auto）。读不出来按 hint 算——绝不替用户做主。"""
        import pet_agent
        pet=getattr(self,'pet',None)
        if pet is None:return pet_agent.DEFAULT_LEVEL
        try:value=str(pet.level({}) or '')
        except Exception:return pet_agent.DEFAULT_LEVEL
        return value if value in pet_agent.LEVELS else pet_agent.DEFAULT_LEVEL
    def pending_gate_asks(self):
        """这一刻还没点的门禁候选：锚点定稿、正典板、连贯性裁决三处合起来。"""
        from stage_execution_service import run_stage_confirmation_gate
        try:assets=self.asset_requirements()
        except (ValueError,OSError,TypeError,AttributeError,KeyError):assets={}
        try:ledger=self.continuity_ledger_data()
        except (ValueError,OSError,TypeError,AttributeError,KeyError):ledger={}
        asks=[]
        for gate in ('G-05','G-06','G-08'):
            asks.extend(run_stage_confirmation_gate(
                self.root, gate, assets=assets, ledger=ledger).get('ask') or ())
        return asks
    def auto_decide_gates(self):
        """半自动／全自动：三虎自己把「待办与裁决」里没点的候选按推荐选掉。

        第 64 期任务 6：hint（只提示）档一个字都不做；半自动／全自动不该卡在等人点。
        每一条只处理一次（记进 gate_confirmations.json），选择同时写进资产清单。
        """
        import stage_flow
        from confirm_gates import AUTO
        from stage_execution_service import record_stage_confirmation
        from stage_execution_service import apply_asset_plan_gate_choice
        if self.gate_level() not in stage_flow.AUTO_LEVELS:return 0
        done=0
        for item in self.pending_gate_asks():
            key=str(item.get('key') or '');candidates=list(item.get('candidates') or ())
            if not key or not candidates:continue
            try:index=int(item.get('recommended') or 0)
            except (TypeError,ValueError):index=0
            choice=candidates[min(max(index,0),len(candidates)-1)]
            # 写资产清单或确认账本失败不能伪装成“这条已经处理过”。交给外层
            # _poll_auto_due 的节流与可见错误反馈，下一拍才会重试。
            apply_asset_plan_gate_choice(self.root,key,choice)
            record_stage_confirmation(self.root,key,choice,by=AUTO,digest=str(item.get('digest') or ''))
            done+=1
        if done:
            text='已按推荐处理 %d 条待办：锚点、正典板与连贯性裁决。'%done
            self.pet_report('continuity',text)
            if getattr(self,'page_index',None)==PAGE['continuity']:self.show(PAGE['continuity'])
            self.status.set(text)
        return done














    def final_storyboard(self):
        from storyboard_files import show_final
        # 第 68 期任务 6：这一页补上了主动作「手动同步资产」，阶段配置就跟着挪到那一行
        # （原来挂在页标题右边，两处会重复），见 storyboard_files.show_final。
        show_final(self)
    def make_final_storyboard(self,source=None):
        if source is None:source=self.current_frame_json()
        if not source or not Path(source).is_file():raise ValueError('请先到'+pet_bus.stage_step('assets')+'选择'+pet_bus.stage_step('storyboard')+'生成的JSON并同步资产清单')
        from storyboard_final_controller import finalize_stage_storyboard
        if self.worker or any(getattr(v,'busy',False) for v in self.video_sessions.values()):raise ValueError('请等待当前制作任务结束后再生成定稿')
        project=self.root;episode=self.asset_base()
        def done(folder):
            # 第 47 期第 5 条：手动定稿收了尾，三虎说一句。
            self.pet_report('final',self.apply_final(project,folder))
        self.async_(lambda:finalize_stage_storyboard(project,episode,source),done)
    def apply_final(self,project,folder):
        """定稿生成后的公共收尾：刷新已打开的工作集、记住当前分镜、写偏好并重建分镜定稿页面。

        手动「同步资产 · 生成定稿」和无人值守自动定稿共用这一份收尾，行为不会走偏。
        """
        result=read(folder/'episode.json')
        missing=len((result.get('missing_assets') or [])) if isinstance(result,dict) else 0
        if self.root is not None and Path(project)==Path(self.root):
            from stage_execution_service import refresh_storyboard_studios
            refresh_storyboard_studios(self, project)
            final_source = folder / 'episode.json'
            self.remember_frame_json(final_source)
            from storyboard_selection import remember_final_view
            remember_final_view(project, final_source)
            # 只在用户本来就在分镜定稿页时重建页面：无人值守不该把人从别的页面拽走（手动按钮本来就在这一页）。
            if getattr(self,'page_index',None)==PAGE['final']:self.show(PAGE['final'])
        return 'JSON已刷新：'+str(folder)+f'；另有 {missing} 项资产待补齐。'
    def sync_working_episode(self):
        """采用分镜后，若项目还没有视频任务，把工作集指针切到最新采用的分镜。"""
        from storyboard_selection import sync_working_episode
        target=sync_working_episode(self.root)
        if target is None:return None
        if Path(self.studio.episode_path).resolve()!=target:self.studio=open_studio(self.root)
        return target

    def current_episode(self):
        """当前分镜 JSON：配音、字幕、对白脚本共用同一个入口，不再各写一遍读文件。"""
        return read(self.current_frame_json())
    def dialogue_entries(self,episode=None):
        """对白行与「时间轴是草稿」标记；已经读过盘就把 episode 传进来，不重复读。"""
        from subtitle_timing import timed_entries
        return timed_entries(self.current_episode() if episode is None else episode)


    def open_folder(self,p):open_directory(p)
    def open_version_picker(self):
        from version_picker import open_picker
        return open_picker(self)
    def final_import(self):
        from stage_workspace_service import ensure_delivery_workspace
        result=ensure_delivery_workspace(self.root)
        if not result.ok:raise ValueError(result.reason)
        delivery_dir,_=result.data
        p=FileDialog(self.win).open_file(initialdir=delivery_dir,filetypes=[('成片','*.mp4 *.mov')])
        if not p:return
        def work():
            from service_contract import UserError
            from stage_execution_service import import_delivery_master
            result=import_delivery_master(self.root,p)
            if result.ok:return '最终成片已导入：'+str(result.data)
            if isinstance(result,UserError):raise ValueError(result.reason)
            raise RuntimeError('最终成片导入失败，请稍后重试')
        self.async_(work)

    def commercial_delivery_review(self,create=False):
        from stage_completion_service import create_commercial_template, confirm_commercial_evidence
        root=Path(self.root).resolve()
        if create:
            target=create_commercial_template(root)
            self.open_folder(target.parent)
            self.log('商用待填资料已生成：'+str(target)+'；请按说明填写授权和内容审核证据')
            return
        selected=FileDialog(self.win).open_file(title='选择已填写的商用交付资料',filetypes=[('审核资料','*.json')])
        if not selected:return
        def work():
            target=confirm_commercial_evidence(root,read(Path(selected)))
            return '商用资料核验通过（依据人工记录）：'+str(target)
        self.async_(work)

    def confirm_stage_media(self,stage):
        from stage_completion_service import (media_output_folders, media_scope,
                                              prepare_media_completion, confirm_media_completion)
        root=Path(self.root).resolve()
        scope=media_scope(root)
        folders,suffixes=media_output_folders(root,stage)
        paths=FileDialog(self.win).open_files(title='选择当前集的本阶段成果',initialdir=folders[0],
            filetypes=[('媒体',' '.join('*'+suffix for suffix in sorted(suffixes)))])
        if not paths:return
        def work():
            return prepare_media_completion(root,stage,paths,scope=scope)
        def done(prepared):
            if Path(self.root).resolve()!=root:
                raise ValueError('项目已切换，请在当前项目重新校验成果')
            names='\n'.join(item['path'] for item in prepared['outputs'])
            if not confirm(self.win,'确认本集成果',
                '媒体技术校验通过。请确认以下文件属于当前集，内容完整且已人工审核：\n'
                +prepared['scope']['episode']+'\n'+names
                +('\n此操作不代表商用授权或内容合规通过。' if stage=='delivery' else '')):return
            confirm_media_completion(root,stage,prepared)
            self.pet.report_done(stage,'本集成果已校验并确认')
        self.async_(work,done)

if __name__=='__main__':
    window=tk.Tk();Desktop(window);window.mainloop()
