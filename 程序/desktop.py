"""Shared, lazy project workspace. Standard-library-only desktop UI."""
import app_logging
import page_navigation_controller as page_nav
from desktop_idea_menus import IdeaMenusMixin
from desktop_asset_pages import AssetPagesMixin, AssetPageServices
from desktop_script_pages import ScriptPagesMixin, ScriptPageServices
from desktop_media_pages import MediaPagesMixin, MediaPageServices
from desktop_project_pages import ProjectPagesMixin, ProjectPageServices
from desktop_storyboard_page import StoryboardPageMixin, StoryboardPageServices
from desktop_writing_page import WritingPageMixin, WritingPageServices, TALK_MIN_LINES, TALK_MAX_LINES
from desktop_page_support import ASSET_FIRST_ROWS, ASSET_ROWS_PER_FRAME, ASSET_ROW_LABEL, STAGE_ACTION_WIDTH, _prefs, THUMB_SIZE, ASSET_ROW_HEIGHT
from desktop_idea_chat import IdeaChatMixin, IDEA_FIELDS, BUBBLE_FLOOR, BUBBLE_LINE, BUBBLE_MAX_RATIO, script_raw_saved_notice, model_error_display
import desktop_shared_send
from desktop_auto_state import AutoStateHolderMixin, create_auto_state
from desktop_auto_flows import AutoFlowsMixin, UNATTENDED_NEXT, UNATTENDED_BACKOFF_FLOOR, ASSET_RETRY_LIMIT
import os, shutil, queue, threading, subprocess, sys, time, uuid, hashlib, re, json, logging
from datetime import date
from pathlib import Path
from file_cache import remove_temporary_file
from contract.storyboard_paths import media_root
import tkinter as tk
from tkinter import ttk, messagebox
from agent.core import read,save,save_text,save_bytes
import project_settings
from projects import Projects, needs_cleanup_after_open_error, is_missing_storyboard_open_error
from responsive_ui import FlowBar,ScrollForm,growable_extra,configure_check_column,refresh_check_heading,CheckboxColumn,fit_columns_by_content,auto_columns,bind_row_toggle,fit_row_height,row_height_for,bind_show_all
from engine import approved_versions, review_label, adoption_summary
from local_video import open_studio,skip_summary
from app import App
from integrations import comfy_executable
from ui_theme import apply as apply_theme, install_window_placement
from project_naming import dated_path
import asset_thumbs
import asset_resume
import contract.frame_checks as frame_checks
import pet_ui
import ui_usage_indicator
import contract.project_stages as project_stages
import ui_plugin_registry
import stage_handler_registry
from contract.platform_tools import find_editor_shortcut, launch_windows_app, open_directory, open_path, open_target, tcp_listener
from desktop_startup_service import DesktopStartupController
from desktop_account_page import AccountPageMixin
from desktop_login_gate import LoginGateMixin
from desktop_page_nav import PageNavMixin
from desktop_lifecycle import LifecycleMixin
from desktop_automation_service import BackgroundTaskLifecycle, DesktopAutomationScheduler, BackgroundTaskQueue, PersistentBackgroundTaskQueue, inspect_project_storage, RetryRegistry
from idea_chat_controller import IdeaChatController, speaker_name
from ui_tokens import BUTTON_GAP, BUTTON_WIDTH_DIALOG, CHAR_WIDTH, WRAPLENGTH, COLORS, FONTS, SPACING, DESKTOP_LAYOUT, SCRIPT_ACTION_WIDTH, SCRIPT_ACTION_PADDING, SCRIPT_FILE_FONT, ICON_FOLDER, ICON_DELETE
from ui_dialogs import FileDialog
from ui_motion import Spinner
from ui_shortcuts import ShortcutRegistry
import ui_stage_popups  # noqa: F401  导入即向 stage_exec 登记阶段弹窗呈现器
from ui_widgets import (BaseDialog, BusyState, ContextMenu, Card, DataTable, NotificationDispatcher,
                        PrimaryButton, SecondaryButton, TextArea, HintLabel, Tooltip, EllipsisLabel, ask_confirmation, ask_string, setup_styles)
from ui_icons import IconLoader

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
    border=tk.Frame(win,bg=COLORS['danger'],padx=SPACING['xs'],pady=SPACING['xs']);border.pack(fill='both',expand=True)
    body=tk.Frame(border,bg=COLORS['danger_subtle'],padx=SPACING['xl'],pady=SPACING['lg']);body.pack(fill='both',expand=True)
    tk.Label(body,text='⚠ 将删除当前项目',bg=COLORS['danger_subtle'],fg=COLORS['danger_hover'],
             font=('Microsoft YaHei UI',15,'bold')).pack(anchor='w')
    tk.Label(body,text='这是最后一份剧本。继续后会将当前项目及其全部素材移入项目库回收站。',
             bg=COLORS['danger_subtle'],fg=COLORS['danger_text'],justify='left',wraplength=WRAPLENGTH['sm'],
             font=FONTS['body']).pack(anchor='w',pady=(SPACING['sm'],SPACING['xs']))
    tk.Label(body,text=names,bg=COLORS['danger_subtle'],fg=COLORS['danger_text'],justify='left',wraplength=WRAPLENGTH['sm']).pack(anchor='w')
    result={'accepted':False}
    buttons=tk.Frame(body,bg=COLORS['danger_subtle']);buttons.pack(anchor='e',fill='x',pady=(SPACING['lg'],SPACING['none']))
    def close(accepted=False):
        result['accepted']=accepted
        try:win.grab_release()
        except tk.TclError:pass
        win.destroy()
    SecondaryButton(buttons,text='取消',command=close,width=BUTTON_WIDTH_DIALOG).pack(side='right')
    PrimaryButton(buttons,text='移入回收站',command=lambda:close(True),width=BUTTON_WIDTH_DIALOG,
                  style='Tokens.Danger.TButton').pack(side='right',padx=(SPACING['none'],BUTTON_GAP))
    win.protocol('WM_DELETE_WINDOW',close)
    win.update_idletasks()
    x=max(0,parent.winfo_rootx()+(parent.winfo_width()-win.winfo_width())//2)
    y=max(0,parent.winfo_rooty()+(parent.winfo_height()-win.winfo_height())//2)
    win.geometry('+%d+%d'%(x,y))
    win.grab_set()
    parent.wait_window(win)
    return result['accepted']


import contract.pet_bus as pet_bus
# 页面序号一律由阶段表推出来（PAGES 与 pet_bus.STAGES 一一对应），
# 再加一个阶段时只改 pet_bus.STAGES／STAGE_NAMES。
import pet_state


# 第 44 期：版本号只写这一份——系统标题栏与左上角那一行（齿轮就挨着它）都用它。
from contract.app_metadata import APP_NAME, VERSION
from desktop_page_registry import (CACHED_PAGES, PAGE, PAGE_ACCOUNT, PAGE_NAV_ICONS,
                                   PAGE_SITES, PAGES, nav_label, page_title)

# 「页面第一次画完」按页指标名：用 PAGE 稳定键区分 14 页，不用会变的中文标题。

def _late(name):
    """页面服务的默认实现：调用时才按名字取本模块当前值，测试按 ``desktop.<名字>`` 打补丁照常生效。"""
    return lambda *args, **kwargs: globals()[name](*args, **kwargs)


def _page_services(given):
    """六页服务：调用方（测试）可按 ``<页>_page_services`` 关键字替换，其余用 ``_late`` 默认实现。"""
    page = dict(open_path=_late('open_path'), confirm=_late('confirm'))
    ctx, dialog = dict(context_menu=_late('ContextMenu')), dict(file_dialog=_late('FileDialog'))
    made = dict(
        script_page_services=ScriptPageServices(**page, **ctx),
        writing_page_services=WritingPageServices(**page, **ctx, confirm_project_removal=_late('confirm_project_removal_from_last_script')),
        storyboard_page_services=StoryboardPageServices(**page, **dialog),
        project_page_services=ProjectPageServices(**page, **ctx),
        asset_page_services=AssetPageServices(**page, **dialog),
        media_page_services=MediaPageServices(
            **page, **dialog, open_studio=_late('open_studio'), comfy_executable=_late('comfy_executable'),
            find_editor_shortcut=_late('find_editor_shortcut')))
    unknown = set(given) - set(made)
    if unknown:
        raise TypeError(f'Desktop() 不认识的参数：{sorted(unknown)}')
    return {**made, **{k: v for k, v in given.items() if v is not None}}




from desktop_tk_gc import (protect_readonly_combobox, protect_tk_gc, drain_tk_gc, _pin_tk_app,
                        _PENDING_TK_GC, _KEEP_APPS)
from desktop_automation_tick import AutomationTickMixin
from desktop_layout import LayoutMixin
from desktop_pet_bridge import PetBridgeMixin, PET_STAGE_POLL, UNATTENDED_SWITCH
from desktop_async_tasks import AsyncTasksMixin
from desktop_tray import TrayMixin



STATUS_ERROR_MARKERS=('失败','错误','异常','无法','未能','未完成','未启动','出错','中断','超时','暂缓')
STATUS_RUNNING_MARKERS=('正在','处理中','执行中','生成中','加载中','检测中','排队','请稍候','等待')
# 数量为零的写法（「失败 0 个」「0 个失败」「失败：0」）只报计数，不算错误；分色前先把这些片段抹掉。
_STATUS_ZERO_COUNT=re.compile(r'(?:'+('|'.join(STATUS_ERROR_MARKERS))+r')\s*[:：]?\s*0(?![\d.])|(?<![\d.])0\s*个?\s*(?:'+('|'.join(STATUS_ERROR_MARKERS))+r')')


def status_kind(message):
    """把状态栏文本归为就绪／执行中／失败三类；失败优先于执行中，零计数的失败不算错误。"""
    text='' if message is None else str(message)
    if any(marker in _STATUS_ZERO_COUNT.sub('', text) for marker in STATUS_ERROR_MARKERS):return 'error'
    if any(marker in text for marker in STATUS_RUNNING_MARKERS):return 'running'
    return 'ready'

class Desktop(PageNavMixin, LifecycleMixin, AutoStateHolderMixin, AccountPageMixin, LoginGateMixin, IdeaMenusMixin, AssetPagesMixin, ScriptPagesMixin, MediaPagesMixin, ProjectPagesMixin, StoryboardPageMixin, WritingPageMixin, IdeaChatMixin, AutoFlowsMixin, AutomationTickMixin, LayoutMixin, PetBridgeMixin, AsyncTasksMixin, TrayMixin):
    def __init__(self,win,root=ROOT,*,require_login=False,**page_services):
        self._init_window_and_sidebar(win, root, page_services)
        self._init_body_and_status(win)
        # Timed callbacks cannot run inside the placement code's update_idletasks.
        # An idle modal here would block the root while it is still transparent.
        self._initialize_automation_state()
        self.root=None
        self.studio=None
        self.asset_kind='all'
        self.asset_detail_id=None
        self.asset_roster=False
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
        self.begin_startup_or_login(require_login,lambda:self.startup_controller.start(*((10,) if self._startup_window_held() else ())))
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
        self.setup_tray()

    def _init_window_and_sidebar(self, win, root, page_services):
        """服务、窗口外观与侧栏（项目列表、导航按钮、标题行），从 __init__ 原样切出，R1808。"""
        self._diagnostic_start=time.perf_counter()
        for name, services in _page_services(page_services).items():
            setattr(self, name, services)
        from stage_execution_service import project_registry_gateway
        self.win=win;self.app=Path(root);self.projects=Projects(root,gateway=project_registry_gateway(),migrate_legacy=False);self.worker=False;self.q=queue.Queue();self._brief_load_results=queue.Queue();self._async_ticket=0;self.background_tasks=BackgroundTaskLifecycle(self.app/'outputs'/'desktop-task-history.json');self.task_queue=PersistentBackgroundTaskQueue(self.app/'outputs'/'desktop-task-queue.json',handlers={'storage_inspect':inspect_project_storage});self.retry_registry=RetryRegistry();self._async_result_poll_id=None;self._auto_edit_result_poll_id=None;self._auto_handoff_result_poll_id=None;self._idea_brief_generation=0;self.idea_chat_controller=IdeaChatController();self.video=None
        self._stage_model_sync_results=queue.Queue();self._stage_model_sync_generation=0
        self._legacy_project_migration_results=queue.Queue();self._legacy_project_migration_poll_id=None
        self._legacy_project_migration_started=False
        win._desktop_first_paint_complete=False
        win._desktop_loading_project=False
        win._desktop_startup_settled=False   # 启动页建完、tick 恢复后置真；三虎开机招呼等它
        self.video_sessions={};self.cloud_monitor_busy=False;self.cloud_monitor_due=0;self.cloud_monitor_cursor=0;self._cloud_monitor_ticket=0;self.cloud_monitor_tasks=BackgroundTaskLifecycle(self.app/'outputs'/'desktop-task-history.json');self.cloud_monitor_result=queue.Queue()
        self.settings_file=self.app/'desktop_settings.json';from desktop_settings_service import load_desktop_settings;self.settings=load_desktop_settings(self.settings_file,{'comfy_url':'http://127.0.0.1:8189','jianying':''},read=read,preserve=lambda path:shutil.copy2(path,path.with_name(path.name+'.corrupt')))
        win.title(APP_NAME+' · '+VERSION);win.state('normal')
        win.geometry('%dx%d'%(min(DESKTOP_LAYOUT['default_width'],win.winfo_screenwidth()-DESKTOP_LAYOUT['window_margin_x']),min(DESKTOP_LAYOUT['default_height'],win.winfo_screenheight()-DESKTOP_LAYOUT['window_margin_y'])))
        # 第 19 期：安装后的图标（三虎）——主窗口标题栏／任务栏都用它，拿不到就照旧用 Tk 默认图标。
        try:
            import app_icon;app_icon.apply(win)
        except Exception:app_logging.swallowed()
        win.minsize(DESKTOP_LAYOUT['min_width'],DESKTOP_LAYOUT['min_height']);apply_theme(win);setup_styles(win);install_window_placement(win)
        self._build_sidebar(win)
        side=self.sidebar
        # 设置齿轮直接落在主窗口根层，避免侧栏或页面画布在窄窗口时裁掉入口；
        # 实际文字尺寸决定齿轮位置；字号或显示名改变时不留旧名称的空洞。
        self.settings_gear_layer=win
        self.settings_gear_position=(0,0)
        # 项目区收成三行图标控件：分组筛选、项目选择器、新建/打开目录（R2897 图标轨改版，构建在 ProjectPagesMixin）。
        self._build_project_rail(side)
        ttk.Separator(side).pack(fill='x',pady=DESKTOP_LAYOUT['section_gap'])
        self.nav=[]
        self.build_account_nav(side)
        for i,title in enumerate(PAGES):
            # 第 48 期第 3 条：点「10 视频生成」的入口逻辑——本次启动第一次点先摆「选择生成方式」
            # 那一屏；之后（用户已经选过线上或线下）再点就直接回他选的那一侧，不再反复拦在选择页上。
            # 页内切分镜、刷新列表仍直接调 show()。
            image=IconLoader.nav_icon(win,PAGE_NAV_ICONS.get(i))
            b=SecondaryButton(side,text=nav_label(i),image=image,
                              compound='left' if image is not None else 'text',
                              command=lambda n=i:self.go_page(n),style='Nav.TButton')
            Tooltip(b,page_title(i))
            b.pack(anchor='w',fill='x',pady=(SPACING['none'],DESKTOP_LAYOUT['nav_gap']));self.nav.append(b)
            if i==PAGE['assets']:
                # 第 71 期任务 2：「05 资产管理」下面挂一级缩进的二级入口「资产清单」（构建在 ProjectPagesMixin）。
                self._build_asset_roster_nav(side)
        # 侧栏内容按自然高度依次 pack；超出视口的部分由外层 ScrollForm 滚动。
        self.sidebar_size=None
        self.project_block.bind('<Configure>',self.schedule_sidebar_fit,add='+')
        side.bind('<Configure>',self.schedule_sidebar_fit)
        self.sidebar_canvas.bind('<Configure>',self.schedule_sidebar_fit,add='+')

    def _init_body_and_status(self, win):
        """主体区：标题行右侧信息、页面画布、进度条、状态栏与尺寸把手，从 __init__ 原样切出，R1808。"""
        self.body=ttk.Frame(win,padding=DESKTOP_LAYOUT['body_padding']);self.body.pack(side='left',fill='both',expand=True)
        self.title_row=ttk.Frame(self.body);self.title_row.pack(fill='x');self.title_row.pack_propagate(False)
        self.pet_layer=self.title_row
        self.title=ttk.Label(self.title_row,font=FONTS['heading_1']);self.title.pack(side='left',anchor='n',padx=(DESKTOP_LAYOUT['title_inset'],SPACING['none']))
        self.header_slogan=ttk.Label(self.title_row,text='✦  把灵感变成故事',
                                   style='Muted.TLabel',font=DESKTOP_LAYOUT['slogan_font'])
        self.title.bind('<Configure>',self.align_header,add='+')
        self.app_title.bind('<Configure>',self.align_header,add='+')
        self.project_block.bind('<Configure>',self.schedule_sidebar_fit,add='+')
        self.title_row.bind('<Configure>',self.align_header,add='+')
        self.header_info=ttk.Frame(self.title_row);self.header_info.pack(side='right',fill='x',expand=True,padx=(SPACING['md'],SPACING['none']))
        self.header_model=ttk.Label(self.header_info,style='Muted.TLabel',font=FONTS['pet_hint'],anchor='e');self.header_model.pack(side='bottom',fill='x')
        self.header_status=ttk.Label(self.header_info,style='Muted.TLabel',font=FONTS['pet_hint'],anchor='e',justify='right');self.header_status.pack(side='top',fill='x')
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
        # 用量指示器（费用统计模块）：标题行右上角、三虎头像左侧常驻；总线绑定由每拍 sync_bus 负责。
        self.usage_indicator=ui_usage_indicator.UsageIndicator(self.pet_layer,self)
        ui_usage_indicator.place_in_title_row(self.usage_indicator,self.pet_layer)
        # 页面仍由画布和鼠标滚轮滚动，但不显示贴在窗口最右侧的整页长滑块。
        # 各页面共用这一层，因而无需在 11 个页面里分别隐藏；表格、对话框等局部滚动条照常保留。
        area=ttk.Frame(self.body);area.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(area,bg=COLORS['background_primary'],highlightthickness=0)
        self.canvas.pack(fill='both',expand=True)
        self.page_scrollbar=None
        self.content=ttk.Frame(self.canvas);self.content_id=self.canvas.create_window(0,0,window=self.content,anchor='nw')
        self.content.bind('<Configure>',self.align_header,add='+')
        self.watch_window_resize(win)
        protect_readonly_combobox(win);protect_tk_gc(win)
        win.bind_class('DramaPageWheel','<MouseWheel>',self.scroll_page)
        win.bind_all('<MouseWheel>',self.scroll_page,add='+')
        for key,cb in [(k,self.scroll_page_key) for k in ('<Prior>','<Next>','<Home>','<End>')]+[(k,self.page_shortcut) for k in ['<Control-Key-%d>'%n for n in range(10)]+['<Control-Prior>','<Control-Next>']]:win.bind(key,cb,add='+')
        # 最小化恢复时 Windows 可能先交付一枚滚轮事件，随后才派发画布的新尺寸。
        # 重新映射后沿用既有的合并空闲布局，确保滚动区域已按恢复后的可视高度计算。
        win.bind('<Map>',self.on_window_map,add='+')
        win.bind('<FocusIn>',self.refresh_membership_view,add='+')    # R2064：回到前台时静默续签
        # 全部阶段只保留一条绿色信息栏：操作说明与动态状态汇总在这里。
        self.status=tk.StringVar(value='就绪 · 所有项目共用一份程序')
        self.notifier=NotificationDispatcher(self.status, parent=win)
        self.file_dialog=FileDialog(win, notifier=self.notifier)
        self.shortcuts=ShortcutRegistry()
        # 不再用进度条：忙碌只由状态栏右端的转圈表示（spinner 在状态栏建好后挂上）。
        self.busy_state=BusyState(self.status)
        # ui_theme 的窗口定位失败只做恢复，不另建反馈链；状态栏建好后把
        # 既有可见提示入口交给根窗口。
        win._drama_place_notice=self.status.set
        self.banner_status=tk.StringVar(value='')
        def refresh_banner(*_unused):
            self.banner_status.set(self.status.get().strip())
        self.status.trace_add('write',refresh_banner);refresh_banner()
        pet_ui.watch_status(self,self.pet)
        self.status_label=ttk.Label(self.body,textvariable=self.banner_status,
                                    style='PaleGreenHint.TLabel',wraplength=WRAPLENGTH['lg'])
        self.status_label.pack(fill='x',pady=DESKTOP_LAYOUT['status_gap'])
        # 共享底部输入框（任务书轮 4）：13 个阶段页共用同一实例，位于画布与状态栏之间；
        # 页面切换只调 set_stage 换上下文（desktop_page_nav._sync_shared_input），
        # 非阶段页与锁定／首页路由由 pack_forget 隐藏。``before`` 把它的包裹位次插到
        # 状态栏之上，重 pack 也不会掉到状态栏下面。
        self.shared_input=desktop_shared_send.make_shared_input(self)
        self.shared_input.pack(side='top',fill='x',before=self.status_label)
        # 忙碌时在状态栏右端转一个小圆圈（BusyState 起停）；平时不占位。
        self.busy_state.spinner=Spinner(self.body,host=self.status_label)
        self._install_status_styles();self.status.trace_add('write',self.sync_status_style);self.sync_status_style()
        # 不放 ttk.Sizegrip：它由 Tk 逐像素实时改窗口大小、内容跟着重排，和另三个角（系统边框缩放）表现不一致；右下角也走系统边框。

    def _build_sidebar(self,win):
        """应用名做成固定浮层盖在滚动区顶；滚轮只滚下面的目录与导航，标题和齿轮不动。"""
        sidebar_area=ttk.Frame(win,width=DESKTOP_LAYOUT['sidebar_width']);sidebar_area.pack(side='left',fill='y');sidebar_area.pack_propagate(False)
        scroll=ScrollForm(sidebar_area,bg=COLORS['background_primary'],scrollbar=False)
        self.sidebar_viewport=sidebar_area;self.sidebar_scroll=scroll;self.sidebar_canvas=scroll.canvas
        scroll.canvas.configure(takefocus=True)
        # 固定头是 place 浮层，不参与 pack，不改变滚动画布视口高度（避免整页布局被侧栏结构扰动）。
        self.sidebar_head=ttk.Frame(sidebar_area,padding=(DESKTOP_LAYOUT['sidebar_padding'],DESKTOP_LAYOUT['sidebar_padding'],DESKTOP_LAYOUT['sidebar_padding'],SPACING['xs']))
        self.app_title=ttk.Label(self.sidebar_head,text=APP_NAME,font=FONTS['heading_1'])
        self.app_title.pack(side='left')
        self.sidebar_head.place(x=0,y=0,relwidth=1.0)
        header_height=self.sidebar_head.winfo_reqheight()
        # 滚动内容从浮层下沿开始，顶部留出与浮层等高的空当，标题不会盖住「我的项目」。
        side=ttk.Frame(scroll.form,padding=(DESKTOP_LAYOUT['sidebar_padding'],header_height,DESKTOP_LAYOUT['sidebar_padding'],DESKTOP_LAYOUT['sidebar_padding']));self.sidebar=side
        side.pack(fill='both',expand=True)
        self.project_label=ttk.Label(side,text='我的项目')
        self.project_label.pack(anchor='w',pady=(DESKTOP_LAYOUT['row_gap'],SPACING['none']))


    def _install_status_styles(self):
        """状态栏三类语义色；就绪沿用既有 PaleGreenHint，执行中／失败只在本页登记。"""
        style=ttk.Style(self.win)
        style.configure('Tokens.Status.Running.TLabel',background=COLORS['primary_subtle'],foreground=COLORS['primary_pressed'],padding=(SPACING['sm'],SPACING['xs']))
        style.configure('Tokens.Status.Error.TLabel',background=COLORS['danger_subtle'],foreground=COLORS['danger_text'],padding=(SPACING['sm'],SPACING['xs']))


    def sync_status_style(self,*_unused):
        kind=status_kind(self.status.get())
        name={'ready':'PaleGreenHint.TLabel','running':'Tokens.Status.Running.TLabel','error':'Tokens.Status.Error.TLabel'}[kind]
        self.status_label.configure(style=name)


    def _initialize_automation_state(self):
        """建立各阶段自动队列的完整初始契约，避免 UI 构造中遗漏状态（状态本体见 desktop_auto_state）。"""
        self.auto=create_auto_state(self.app/'outputs'/'desktop-task-history.json',stage_queue=pet_ui.StageQueue,drain=self.pet.drain)

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
        selected=str(getattr(self,'_idea_model_filter',None) or '').strip()
        if selected and getattr(self,'_idea_model_filter_root',None)==self.root:
            return selected
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
                    import contract.script_contract as script_contract
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
            b.pack(side='left',padx=(SPACING['none'],SPACING['sm']),pady=SPACING['xs'])
        else:
            b=SecondaryButton(parent,text=text,command=lambda:self.safe(action),style='Compact.TButton' if parent is self.sidebar else 'TButton')
            b.pack(anchor='w',fill='x',pady=DESKTOP_LAYOUT['row_gap']*2 if parent is self.sidebar else SPACING['xs'])
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
            except Exception as exc:
                # 线程只传递结果；Tk 状态须由 _tick_async_result 在主线程更新。
                # 任何异常都要投递结果：线程静默退出会让输入框一直处于加载态。
                app_logging.swallowed()
                path=None;error=str(exc)
            self._brief_load_results.put((generation,root,apply,path,error))
        threading.Thread(target=discover,daemon=True).start()
        return generation



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
                    # 认领已替换登记路径，先同步项目选择器再选中新项目。
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
            self.mark_current_project()
        else:
            self._sync_project_picker()
            self.refresh_sidebar_title()
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
        self.auto.adopt_signature=None;self.auto.adopt_pending=False;self.auto.adopt_startup=True
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
            from contract.stage_layout import ensure
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
            except Exception as exc:
                # 工作线程只带错误结果回主线程；不能在这里直接操作 Tk 状态栏。
                app_logging.swallowed()
                result={'error':str(exc), 'kind': 'bug'}
            self._stage_model_sync_results.put((generation,target,result))
        threading.Thread(target=work,daemon=True).start()
    def _tick_stage_model_sync_result(self):
        indicator=getattr(self,'usage_indicator',None)  # 总线随项目重建，每拍对齐 usage_updated 订阅
        if indicator is not None:
            try:indicator.sync_bus()
            except Exception:app_logging.swallowed()
        try:generation,target,result=self._stage_model_sync_results.get_nowait()
        except queue.Empty:return
        if generation!=self._stage_model_sync_generation or target!=self.root:return
        if isinstance(result,dict) and result.get('error'):
            LOGGER.warning('项目模型同步失败：%s', result['error'])
            self.status.set('项目模型同步未完成：%s；请稍后重试。' % result['error'])
            return
        if result:self.status.set('已同步项目模型：'+'、'.join(result))
    def switch(self,event=None):
        """项目选择器换选：确认后才真正切换；取消由 restore_project_selection 把框复位。"""
        picker=getattr(self,'project_picker',None)
        items=getattr(self,'_picker_items',())
        if picker is None or not items:return
        index=picker.current()
        if index<0 or index>=len(items):return
        path=items[index]['path']
        if Path(path)!=self.root:self.safe(lambda:self.request_project_switch(path))

    def new(self):
        name=ask_string(self.win,'新建项目','项目名称：')
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
        self.header_stage_button.pack(side='left',padx=(SPACING['md'],SPACING['none']))
        return self.header_stage_button
    def storyboard_creation(self):
        from storyboard_files import show
        show(self)
    # 第 29 期第 1 条：页面上那几处重复的「Model ＋ SKILL」控制行整个拿掉——入口只留那颗
    # 「阶段配置」。第 32 期第 6 条起它不再集中在剧本准备页，而是各阶段页「手动XX」右边各一颗
    # （见 skill_panel.stage_button），模型／SKILL／接口／说明都在面板里。
    # flow_settings 留着：首帧页的「Skill 调用设置」在模型接口窗口里还要用它（第 26 期那处）。
    def flow_settings(self,stage,function=None):
        from workflow_settings_dialog import show_settings
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
        p=FileDialog(self.win).open_file(initialdir=delivery_dir,filetypes=[('成片','*.mp4 *.mov *.mkv')])
        if not p:return
        def work():
            from contract.service_contract import UserError
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
                +('\n质检：'+('通过' if (prepared.get('qc') or {}).get('passed') else '未通过')
                  +''.join('\n警告：'+item for item in (prepared.get('qc') or {}).get('warnings', []))
                  +'\n此操作不代表商用授权或内容合规通过。' if stage=='delivery' else '')):return
            confirm_media_completion(root,stage,prepared)
            self.pet.report_done(stage,'本集成果已校验并确认')
        self.async_(work,done)

if __name__=='__main__':
    window=tk.Tk();Desktop(window);window.mainloop()
