"""Shared, lazy project workspace. Standard-library-only desktop UI."""
import os, shutil, queue, threading, subprocess, time, uuid, hashlib, re, json
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
from engine import approved_versions
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
from platform_tools import launch_windows_app, open_path, open_target, tcp_listener
from desktop_startup_service import DesktopStartupController
from desktop_automation_service import BackgroundTaskLifecycle, DesktopAutomationScheduler
from idea_chat_controller import IdeaChatController
from ui_tokens import COLORS, FONTS, SPACING
from ui_dialogs import FileDialog
from ui_shortcuts import ShortcutRegistry
from ui_widgets import (BaseDialog, BusyState, ContextMenu, DataTable, FormDialog, NotificationDispatcher,
                        PrimaryButton, SecondaryButton, TextArea, ask_confirmation, setup_styles)

ROOT=Path(__file__).resolve().parent


def confirm(parent, title, message, *, dangerous=False, **_legacy_options):
    """桌面历史确认框的统一同步适配器，忽略系统 messagebox 专属视觉参数。"""
    return ask_confirmation(parent, title, message, dangerous=dangerous)


def script_raw_saved_notice(four_roles):
    """剧本原稿发布后的三虎提示，按本次请求实际模式区分。"""
    return '四角色剧本已保存：script_raw.md' if four_roles else '剧本已自动保存：script_raw.md'


# 第 37 期第 2 条：创意栏那七个字段的名字只写一份（预置示例与灰色字段名都取它）。
# 第 71 期任务 4：跟着新的预置示例换成这一组名字，灰色字段名认的还是同一份。
IDEA_FIELDS=('故事集数','单集时间','故事画风','故事主体','故事梗概','故事题材','故事角色','物理特征','故事分集','特殊要求','内容补充')
# 第 69 期任务 1：剧本准备页的创意框改成一段对话；第 72 期任务 9／10：全部消息靠左、
# 紧凑显示，模型名置顶，长消息可折叠，模型回复中显示思考提示。
# 最下面留一段给您写字，DRAFT_MARK 就是「从这儿往下才是您写的」那条线。
DRAFT_MARK='draft'
DRAFT_HINT='─'*18+' 写您的想法，按「发送」 '
BUBBLE_BACK='#ffffff'  # 内容框的底色：气泡两边的留白用它刷，色块才贴着字
BUBBLE_FONT=('Microsoft YaHei UI',10)
BUBBLE_TIME_FONT=('Microsoft YaHei UI',9)
BUBBLE_PAD=10          # 气泡里文字与色块边缘的距离
BUBBLE_GAP=14          # 气泡离画面左右两边各留这么多
BUBBLE_FLOOR=70        # 气泡最窄也有这么宽
BUBBLE_LINE=13         # 量不出字宽时的兜底：一个字大约这么宽
BUBBLE_MAX_RATIO=0.72  # 第 71 期任务 6：字再多，色块也不铺满整行，一行才看得下去
BUBBLE_SLACK=26        # 量字宽只是估算（字号、全角半角都有出入），留一截余地，
                       # 免得一句话末了一个字被挤到下一行
BUBBLE_COLLAPSE_CHARS=360
BUBBLE_COLLAPSE_LINES=8
# 第 71 期任务 5／6：剧本准备页的创意框摆几行——窗口再矮也留 TALK_MIN_LINES 行，
# 字再多、窗口再高也不超过 TALK_MAX_LINES 行（一次铺满半页纸就不好操作了）；
TALK_MIN_LINES=6
TALK_MAX_LINES=15
# 第 31 期第 7 条：资产管理页「参考图」「资产图片」两行的标签宽度（字符数）——一样宽，
# 两行按钮的左边缘才对得齐。
ASSET_ROW_LABEL=6
# 第 52 期第 3 条：资产管理「名称」「导入图片」两列的缩略图——长边 72 像素，行高 80（图上下留白）。
# 第 65 期任务 4：用户要「缩略图缩小一倍」，这一档 72 → 36（行高跟着 fit_row_height 一起收）。
THUMB_SIZE=36
# 第 58 期第 2 条：行高按格子里最高的那点内容算——这两张表是 72 像素的缩略图，
# 行高就是图高加上下余地（实际值由 responsive_ui.fit_row_height 当场算）。
ASSET_ROW_HEIGHT=row_height_for(THUMB_SIZE)
STAGE_ACTION_WIDTH=16  # 所有阶段主操作与“阶段配置”共用宽度，页面操作行左侧对齐。

# 第 72 期（Round 3）性能门禁：资产表分段建行——先同步建够第一屏的，剩下的按帧补上。
# 当前资产行高约 80 像素，760 像素窗口可见不足十行；首帧放 24 行仍有三屏余量，
# 又不会在首次绘制时为 48 张图同时登记缩略图任务。余项随后按帧补齐。
ASSET_FIRST_ROWS=24
ASSET_ROWS_PER_FRAME=12


def confirm_project_removal_from_last_script(parent, files):
    """红色破坏性确认：删掉最后剧本时，用户必须明确同意删除整个项目。"""
    names='\n'.join(str(name) for name in files)
    win=BaseDialog(parent, '危险操作：删除当前项目', modal=False, chrome=False)
    win.resizable(False,False)
    border=tk.Frame(win,bg='#c62828',padx=2,pady=2);border.pack(fill='both',expand=True)
    body=tk.Frame(border,bg='#fff5f5',padx=22,pady=18);body.pack(fill='both',expand=True)
    tk.Label(body,text='⚠ 将删除当前项目',bg='#fff5f5',fg='#b71c1c',
             font=('Microsoft YaHei UI',15,'bold')).pack(anchor='w')
    tk.Label(body,text='这是最后一份剧本。继续后会将当前项目及其全部素材移入项目库回收站。',
             bg='#fff5f5',fg='#7f1d1d',justify='left',wraplength=500,
             font=('Microsoft YaHei UI',10)).pack(anchor='w',pady=(10,5))
    tk.Label(body,text=names,bg='#fff5f5',fg='#5f2120',justify='left',wraplength=500).pack(anchor='w')
    result={'accepted':False}
    buttons=tk.Frame(body,bg='#fff5f5');buttons.pack(anchor='e',fill='x',pady=(18,0))
    def close(accepted=False):
        result['accepted']=accepted
        try:win.grab_release()
        except tk.TclError:pass
        win.destroy()
    tk.Button(buttons,text='取消',command=close,width=10).pack(side='right')
    tk.Button(buttons,text='移入回收站',command=lambda:close(True),width=11,
              bg='#c62828',fg='white',activebackground='#8e0000',activeforeground='white').pack(side='right',padx=(0,8))
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
    except Exception:pass
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
    except Exception:pass


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
    except Exception:pass

def drain_tk_gc(limit=64):
    """主线程心跳里调用：释放 worker 线程回收到的 Tk 对象（每轮最多 64 个，不拖慢界面）。"""
    try:
        for _ in range(limit):
            if not _PENDING_TK_GC:break
            _PENDING_TK_GC.pop()
    except Exception:pass

def _prefs(path):
    if not path:return {}
    # 这里故意用不缓存的 agent.core.read：调用方（当前分镜、资产范围、视频模式）会就地改这份
    # 字典再写回，共享缓存对象一旦被就地改，同一轮里其他读者就会看到没保存的值。
    from project_settings import read_prefs
    return read_prefs(path)


import pet_bus
# 制作页名称只从 pet_bus.STAGES／STAGE_NAMES 生成；「参考网站」是唯一非阶段工具页。
PAGES = [f'{index:02d}  {pet_bus.stage_name(stage)}'
         for index, stage in enumerate(pet_bus.STAGES, start=1)] + ['13  参考网站']
# 页面序号一律由阶段表推出来（PAGES 与 pet_bus.STAGES 一一对应），
# 再加一个阶段时只改 pet_bus.STAGES／STAGE_NAMES。
import pet_state
PAGE=pet_state.PAGE_OF
PAGE_SITES=len(PAGES)-1          # 「参考网站」是工具页，不进状态机

# 无人值守链路的下游关系：某一步刚成功完成时，把它的下游节流清零，链路立刻往前走一步，
# 而不是干等各自的 15/30/60 秒轮询周期。表必须无环：回头踢上游会让视频轮询在长时间生成
# 期间被反复叫醒，变成每 150ms 打一次 ComfyUI 接口。
UNATTENDED_NEXT={'auto_adopt':('auto_asset','auto_final','auto_keyframe','auto_previs','auto_video'),
                 'auto_asset':('auto_final','auto_keyframe','auto_previs','auto_video'),
                 'auto_final':('auto_keyframe','auto_previs','auto_video'),
                 'auto_keyframe':('auto_previs','auto_video'),
                 'auto_previs':('auto_video',),
                 'auto_video':('auto_edit','auto_handoff'),
                 'auto_edit':('auto_handoff',)}
# 正常节流最长 60 秒：due 比这个界还远只可能是失败后的 5 分钟退避，踢的时候要跳过它。
UNATTENDED_BACKOFF_FLOOR=120
# 第 62 期任务 10：无人值守资产「跑完却一张图都没有」时最多自动重试几次（间隔递增），
# 超过就停下等人工处理——无限重试会把失败的原因一直刷在状态栏上。
ASSET_RETRY_LIMIT=3
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
from app_metadata import VERSION

class Desktop:
    def __init__(self,win,root=ROOT):
        self._diagnostic_start=time.perf_counter()
        from stage_execution_service import project_registry_gateway
        self.win=win;self.app=Path(root);self.projects=Projects(root,gateway=project_registry_gateway(),migrate_legacy=False);self.worker=False;self.q=queue.Queue();self._brief_load_results=queue.Queue();self.hollmwood_progress=queue.Queue();self._stream_text='';self._async_ticket=0;self.background_tasks=BackgroundTaskLifecycle();self._async_result_poll_id=None;self._auto_edit_result_poll_id=None;self._auto_handoff_result_poll_id=None;self._idea_brief_generation=0;self.idea_chat_controller=IdeaChatController();self._hollmwood_poll_id=None;self.video=None
        self._stage_model_sync_results=queue.Queue();self._stage_model_sync_generation=0
        self._legacy_project_migration_results=queue.Queue();self._legacy_project_migration_poll_id=None
        self._legacy_project_migration_started=False
        win._desktop_first_paint_complete=False
        win._desktop_loading_project=False
        self.video_sessions={};self.cloud_monitor_busy=False;self.cloud_monitor_due=0;self.cloud_monitor_cursor=0;self._cloud_monitor_ticket=0;self.cloud_monitor_tasks=BackgroundTaskLifecycle();self.cloud_monitor_result=queue.Queue()
        self.settings_file=self.app/'desktop_settings.json';self.settings=read(self.settings_file) if self.settings_file.exists() else {'comfy_url':'http://127.0.0.1:8189','jianying':''}
        win.title('漫剧制作助手 · '+VERSION);win.state('normal')
        win.geometry('%dx%d'%(min(1360,win.winfo_screenwidth()-80),min(900,win.winfo_screenheight()-100)))
        # 第 19 期：安装后的图标（三虎）——主窗口标题栏／任务栏都用它，拿不到就照旧用 Tk 默认图标。
        try:
            import app_icon;app_icon.apply(win)
        except Exception:pass
        win.minsize(940,640);apply_theme(win);setup_styles(win);install_window_placement(win)
        # 左侧阶段导航从 230px 缩至约三分之二，正文阅读区在小窗口也能保留空间。
        sidebar_area=ttk.Frame(win,width=154);sidebar_area.pack(side='left',fill='y');sidebar_area.pack_propagate(False)
        side=ttk.Frame(sidebar_area,padding=(6,6));self.sidebar=side
        side.pack(fill='both',expand=True);side.grid_propagate(False)
        # 左上角只保留应用名；设置齿轮由 pet_ui 放在相邻的根层安全位。
        self.sidebar_head=ttk.Frame(side)
        # 第 50 期第 2 条：那句「✦ 把灵感画成故事」原来单占侧栏一行、被拉伸的行推到离头部很远；
        # 现在并进这一块（先按 bottom 摆下，应用名与版本号再占上面那一行，于是它就落在
        # 「V0.7 与齿轮」那一行下面），并且标签行不再参与纵向拉伸。
        ttk.Label(self.sidebar_head,text='✦  把灵感画成故事',style='Muted.TLabel',
                  font=('Microsoft YaHei UI',9)).pack(side='bottom',anchor='w',pady=(8,2))
        ttk.Label(self.sidebar_head,text='漫剧制作助手',font=('Microsoft YaHei UI',16,'bold')).pack(side='left',pady=(2,4))
        self.sidebar_head.pack(fill='x',anchor='w')
        # 设置齿轮直接落在主窗口根层，避免侧栏或页面画布在窄窗口时裁掉入口；
        # 紧贴标题右缘的安全位：22px 齿轮下移 3px，与 16px 标题的文字中线对齐，
        # 同时仍在下方文案之上。
        self.settings_gear_layer=win
        self.settings_gear_position=(138,11)
        ttk.Label(side,text='我的项目').pack(anchor='w',pady=(8,0))
        self.list=ttk.Treeview(side,show='tree',height=3,selectmode='browse',style='Project.Treeview');self.list.column('#0',width=136,minwidth=96,stretch=True);self.list.pack(fill='x',pady=4)
        self.list.bind('<<TreeviewSelect>>',self.switch);self.list.bind('<Button-3>',self.project_menu)
        self.button(side,'+ 新建项目',self.new);self.button(side,'打开项目目录',self.open_current_project)
        ttk.Separator(side).pack(fill='x',pady=8)
        self.nav=[]
        self.asset_list_button=None
        for i,title in enumerate(PAGES):
            # 第 48 期第 3 条：点「08 视频生成」的入口逻辑——本次启动第一次点先摆「选择生成方式」
            # 那一屏；之后（用户已经选过线上或线下）再点就直接回他选的那一侧，不再反复拦在选择页上。
            # 页内切分镜、刷新列表仍直接调 show()。
            b=SecondaryButton(side,text=title,command=lambda n=i:self.go_page(n),style='Nav.TButton');b.pack(anchor='w',fill='x',pady=2);self.nav.append(b)
            if i==PAGE['assets']:
                # 第 71 期任务 2：「03 资产管理」下面挂一级缩进的二级入口「资产清单」——
                # 一页看完每个角色的正典板与换状态面板（见 asset_detail.show_roster）。
                sub=SecondaryButton(side,text='资产清单',command=lambda:self.safe(self.open_asset_roster),style='Sub.Nav.TButton')
                sub.pack(anchor='w',fill='x',pady=(0,2))
                self.asset_list_button=sub
        # 每一行分一份可用高度：项目列表与导航按钮按权重摊，头部与「我的项目」那两行贴顶不摊
        # （第 50 期第 2 条），最后一步「12 参考网站」始终留在可视区，不靠侧栏滚动条。
        side.columnconfigure(0,weight=1)
        for row,child in enumerate(side.winfo_children()):
            child.pack_forget()
            separator=isinstance(child,ttk.Separator)
            # 第 50 期第 2 条：头部与「我的项目」这两行不拉伸（原来各占一份权重，被撑开后
            # 那几个字浮在空行中间）；空出来的高度都给下面的项目列表与导航按钮。
            hug=child is self.sidebar_head or isinstance(child,ttk.Label) or child is self.asset_list_button
            side.rowconfigure(row,weight=0 if separator or hug else (3 if child is self.list else 1),minsize=4 if separator else 0)
            child.grid(row=row,column=0,sticky='ew' if isinstance(child,ttk.Label) or separator else 'nsew',pady=1)
        self.sidebar_size=None
        side.bind('<Configure>',self.fit_sidebar)
        self.body=ttk.Frame(win,padding=14);self.body.pack(side='left',fill='both',expand=True)
        self.title_row=ttk.Frame(self.body);self.title_row.pack(fill='x',pady=(0,10))
        self.title=ttk.Label(self.title_row,font=('Microsoft YaHei UI',18,'bold'));self.title.pack(side='left')
        self.header_info=ttk.Frame(self.title_row);self.header_info.pack(side='right',fill='x',expand=True,padx=(12,0))
        self.header_model=ttk.Label(self.header_info,style='Muted.TLabel',font=('Microsoft YaHei UI',8),anchor='e');self.header_model.pack(side='bottom',fill='x')
        self.header_status=ttk.Label(self.header_info,style='Muted.TLabel',font=('Microsoft YaHei UI',8),anchor='e',justify='right');self.header_status.pack(side='top',fill='x')
        # 第 30 期第 6／8 条：阶段配置那颗按钮从标题栏挪到「剧本准备」页的「创作入口」那一行，
        # 紧挨着「手动制作剧本」（按钮那时才建得出来，见 brief_editor）；这里先留个占位，别的页没有它。
        self.stage_button=None
        # 第 33 期第 4 条：05 分镜定稿那一页没有「手动XX」，它的「阶段配置」挂在页标题右边。
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
        self.canvas=tk.Canvas(area,bg='#f3f6fa',highlightthickness=0)
        self.canvas.pack(fill='both',expand=True)
        self.page_scrollbar=None
        self.content=ttk.Frame(self.canvas);self.content_id=self.canvas.create_window(0,0,window=self.content,anchor='nw')
        self.content.bind('<Configure>',self.fit_content)
        self.canvas.bind('<Configure>',self.fit_content)
        protect_readonly_combobox(win);protect_tk_gc(win)
        win.bind_class('DramaPageWheel','<MouseWheel>',self.scroll_page)
        win.bind_all('<MouseWheel>',self.scroll_page,add='+')
        # 最小化恢复时 Windows 可能先交付一枚滚轮事件，随后才派发画布的新尺寸。
        # 重新映射后沿用既有的合并空闲布局，确保滚动区域已按恢复后的可视高度计算。
        win.bind('<Map>',self.on_window_map,add='+')
        self.progress=ttk.Progressbar(self.body,mode='indeterminate');self.progress.pack(fill='x',pady=(8,0))
        # 全部阶段只保留一条绿色信息栏：操作说明、动态状态和 HOLLMWOOD 角色进度
        # 汇总在这里，避免空的角色栏与状态栏上下各占一行。
        self.hollmwood_role_status=tk.StringVar(value='')
        self.status=tk.StringVar(value='就绪 · 所有项目共用一份程序')
        self.notifier=NotificationDispatcher(self.status, parent=win)
        self.file_dialog=FileDialog(win, notifier=self.notifier)
        self.shortcuts=ShortcutRegistry()
        self.busy_state=BusyState(self.status, self.progress)
        # ui_theme 的窗口定位失败只做恢复，不另建反馈链；状态栏建好后把
        # 既有可见提示入口交给根窗口。
        win._drama_place_notice=self.status.set
        self.banner_status=tk.StringVar(value='')
        def refresh_banner(*_unused):
            role=self.hollmwood_role_status.get().strip()
            message=self.status.get().strip()
            self.banner_status.set('  ｜  '.join(part for part in (role,message) if part))
        self.hollmwood_role_status.trace_add('write',refresh_banner)
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
        self.startup_controller.start()
        self.automation_scheduler=DesktopAutomationScheduler(
            schedule_after=win.after, cancel_scheduled=win.after_cancel,
            is_stopping=lambda:getattr(self,'shutting_down',False))
        self.automation_scheduler.start(
            'hollmwood_progress',100,self.poll_hollmwood_progress,
            on_error=lambda exc:self._set_automation_error('角色进度刷新异常，已忽略：',exc),
            remember_timer=lambda timer:setattr(self,'_hollmwood_poll_id',timer))
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
    # 这些兼容属性保留既有桌面控件与测试的访问方式；状态归属在无 Tk 控制器。
    @property
    def _idea_requesting(self):
        controller = getattr(self, 'idea_chat_controller', None)
        if controller is None:
            return self.__dict__.get('_idea_requesting_fallback', False)
        return controller.requesting

    @_idea_requesting.setter
    def _idea_requesting(self, value):
        controller = getattr(self, 'idea_chat_controller', None)
        if controller is None:
            self.__dict__['_idea_requesting_fallback'] = bool(value)
            return
        controller.requesting = bool(value)

    @property
    def _script_agent_launching(self):
        return self.idea_chat_controller.script_agent_launching

    @_script_agent_launching.setter
    def _script_agent_launching(self, value):
        self.idea_chat_controller.script_agent_launching = bool(value)

    @property
    def _idea_cancel_event(self):
        return self.idea_chat_controller.cancel_event

    @_idea_cancel_event.setter
    def _idea_cancel_event(self, value):
        self.idea_chat_controller.cancel_event = value

    @property
    def idea_attachment_paths(self):
        return self.idea_chat_controller.attachment_paths

    @idea_attachment_paths.setter
    def idea_attachment_paths(self, paths):
        self.idea_chat_controller.replace_attachments(paths)

    def idea_chat_gateway(self):
        """L4 通过 L3 取得创意聊天的受控读写入口。"""
        from stage_execution_service import idea_chat_gateway
        return idea_chat_gateway()

    def idea_chat_context(self):
        """L4 只从 L3 取得创意聊天所需的项目上下文。"""
        from stage_execution_service import project_context
        return project_context(self.root)

    @staticmethod
    def asset_batch_gateway():
        """L4 只装配资产批处理的 L3 读写入口。"""
        from stage_execution_service import asset_batch_gateway
        return asset_batch_gateway()

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
    def fit_sidebar(self,event=None):
        compact=self.sidebar.winfo_height()<690
        if self.sidebar_size==compact:return
        self.sidebar_size=compact
        style=ttk.Style(self.win)
        font=('Microsoft YaHei UI',9 if compact else 10)
        for name in ('Compact.TButton','Nav.TButton','Selected.Nav.TButton'):
            style.configure(name,font=font,padding=(10,1 if compact else 4))
        for name in ('Sub.Nav.TButton','Selected.Sub.Nav.TButton'):
            style.configure(name,font=font,padding=(26,1 if compact else 4))
        style.configure('Project.Treeview',font=font,rowheight=20 if compact else 24)
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
            except Exception:pass
            if getattr(self,'_fit_again',False):
                self._fit_again=False
                self.fit_content()
                return
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
        def resize(widget):
            for child in widget.winfo_children():
                tags=child.bindtags()
                if 'DramaPageWheel' not in tags:child.bindtags(('DramaPageWheel',)+tags)
                if resized and isinstance(child,ttk.Label) and not getattr(child,'local_wrap',False) and int(child.cget('wraplength') or 0)>0:
                    child.configure(wraplength=max(200,width-28))
                resize(child)
        resize(self.content)
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
    def idea_draft_range(self):
        """固定在聊天区底部的发送框；聊天记录不混入待发送文字。"""
        box=getattr(self,'idea_input',None)
        if box is None or not box.winfo_exists():return '1.0','end-1c'
        return '1.0','end-1c'
    def draft_text(self):
        """只读取下方发送框；聊天气泡不参与发送。"""
        box=getattr(self,'idea_input',None)
        if box is None or not box.winfo_exists():return ''
        start,end=self.idea_draft_range()
        try:return str(box.get(start,end))
        except tk.TclError:return ''
    def preserve_idea_draft(self):
        """翻页重建前把尚未发送的创意留在本次运行内，不写入项目文件。"""
        if not self.root:return
        box=getattr(self,'idea_input',None)
        if box is None or not box.winfo_exists():return
        drafts=getattr(self,'_idea_drafts',None)
        if drafts is None:self._idea_drafts=drafts={}
        key=str(Path(self.root).resolve())
        value=self.draft_text()
        if value:drafts[key]=value
        else:drafts.pop(key,None)
    def restore_idea_draft(self):
        """回到剧本准备页时恢复当前项目尚未发送的输入。"""
        box=getattr(self,'idea_input',None)
        if box is None or not box.winfo_exists() or not self.root:return
        value=getattr(self,'_idea_drafts',{}).get(str(Path(self.root).resolve()),'')
        if value:
            box.delete('1.0','end');box.insert('1.0',value)
    def discard_idea_draft(self):
        """内容真正送出后，清除对应的内存草稿。"""
        if self.root:getattr(self,'_idea_drafts',{}).pop(str(Path(self.root).resolve()),None)
    def idea_still_the_example(self):
        """框里那一段还是不是程序带的那份示例（不改动就不算您写的字）。"""
        return self.draft_text().strip()==str(getattr(self,'idea_template','') or '').strip()
    def tint_brief(self):
        """第 37／45 期：还是示例就置灰，自己写的才是正文黑字；字段名那一层单点亮。"""
        box=getattr(self,'idea_input',None)
        if box is None or not box.winfo_exists():return
        start,end=self.idea_draft_range()
        box.configure(fg='#718196' if self.idea_still_the_example() else '#243247')
        box.tag_remove('field_hint',start,end)
        try:first=int(str(box.index(start)).split('.')[0])
        except (tk.TclError,ValueError):return
        for offset,line in enumerate(str(box.get(start,end)).splitlines()):
            head,sep,_rest=line.partition('：')
            if not sep:head,sep,_rest=line.partition(':')
            name=head.strip()
            for label in IDEA_FIELDS:
                # 按尾巴认：示例里写「故事人物」，点亮的就是这几个字的字段名。
                if sep and name.endswith(label):
                    box.tag_add('field_hint',f'{first+offset}.0',f'{first+offset}.{len(head)+1}')
                    break
        try:box.edit_modified(False)
        except tk.TclError:pass
    def refit_bubbles(self,event=None):
        """第 69 期任务 1：窗口一改宽窄就重算气泡的左右边距——只动边距，
        上面的字和您正在写的那段一个字节都不碰。"""
        box=getattr(self,'idea_log',None)
        if box is None or not box.winfo_exists():return
        if event is not None and getattr(event,'widget',None) is not box:return
        width=int(box.winfo_width() or 0)
        if width<=1 or width==getattr(self,'_bubble_width',None):return
        self._bubble_width=width
        for name,text,mine in getattr(self,'_bubble_rows',[]):
            left,right=self.bubble_margins(box,text,mine)
            for tag in (name,name+'_time',name+'_meta',name+'_toggle',name+'_thinking'):
                try:box.tag_configure(tag,lmargin1=left,lmargin2=left,rmargin=right)
                except tk.TclError:pass
    def bubble_font(self):
        """量字宽用的字体；量不出来给 None（退回「一个字 BUBBLE_LINE 像素」的估算）。"""
        face=getattr(self,'_bubble_font','missing')
        if face=='missing':
            try:
                from tkinter import font as tkfont
                face=tkfont.Font(font=BUBBLE_FONT)
            except Exception:
                face=None
            self._bubble_font=face
        return face
    def text_width(self,text):
        """这一段字自然有多宽（像素）。"""
        lines=str(text).splitlines() or ['']
        face=self.bubble_font()
        if face is None:return BUBBLE_LINE*max(len(line) for line in lines)
        try:return max(int(face.measure(line)) for line in lines)
        except Exception:return BUBBLE_LINE*max(len(line) for line in lines)
    def bubble_margins(self,box,text,mine):
        """第 69 期任务 1：一条气泡的左右边距——量出这段字的宽窄，把色块贴着字放，
        于是每条气泡长短不一、左右错落，看起来才是聊天。

        第 71 期任务 6：字再多，色块也不铺满整行——顶到 BUBBLE_MAX_RATIO 就换行，
        一行到底看不下去、也不好操作。"""
        width=max(240,int(box.winfo_width() or 0))
        span=max(BUBBLE_FLOOR,width-2*BUBBLE_GAP)
        span=min(span,max(BUBBLE_FLOOR,int(width*BUBBLE_MAX_RATIO)))
        body=max(BUBBLE_FLOOR,min(span,self.text_width(text)+BUBBLE_PAD*2+BUBBLE_SLACK))
        # 微信式对话：模型在左、用户在右，气泡仍按文字实际宽度收紧。
        if mine:
            return max(0,width-BUBBLE_GAP-body),BUBBLE_GAP
        return BUBBLE_GAP,max(0,width-BUBBLE_GAP-body)
    def bubble_time(self,at):
        """气泡上面那一行小字：这条是什么时候说的（认不出格式就空着）。"""
        from datetime import datetime
        for shape in ('%Y%m%d_%H%M%S_%f','%Y%m%d_%H%M%S'):
            try:return datetime.strptime(str(at),shape).strftime('%m-%d %H:%M')
            except (ValueError,TypeError):continue
        return ''
    def bubble_preview(self,text):
        """过长的消息先给紧凑预览；完整内容仍在内存和对话 JSON 中。"""
        raw=str(text).strip()
        lines=raw.splitlines()
        if len(raw)<=BUBBLE_COLLAPSE_CHARS and len(lines)<=BUBBLE_COLLAPSE_LINES:
            return raw,False
        preview='\n'.join(lines[:BUBBLE_COLLAPSE_LINES])
        if len(preview)>BUBBLE_COLLAPSE_CHARS:
            preview=preview[:BUBBLE_COLLAPSE_CHARS].rsplit('\n',1)[0]
        return preview.rstrip()+'…',True
    def model_name(self,row):
        if str(row.get('role'))=='user':return '您'
        return '模型 · '+str(row.get('model') or 'AI 助手').strip()
    def toggle_bubble(self,box,name):
        """点击“展开全文／收起”只改当前气泡的正文，不重建输入区。"""
        record=getattr(self,'_bubble_full',{}).get(name)
        if not record:return 'break'
        ranges=box.tag_ranges(name)
        if len(ranges)<2:return 'break'
        was_disabled=str(box.cget('state'))=='disabled'
        if was_disabled:box.configure(state='normal')
        try:
            record['expanded']=not record['expanded']
            shown=record['text'] if record['expanded'] else record['preview']
            box.delete(ranges[0],ranges[-1])
            box.insert(ranges[0],shown+'\n',name)
            toggle=name+'_toggle'
            spans=box.tag_ranges(toggle)
            if len(spans)>=2:
                box.delete(spans[0],spans[-1])
                box.insert(spans[0],('收起' if record['expanded'] else '展开全文')+'\n',toggle)
        finally:
            if was_disabled:box.configure(state='disabled')
        return 'break'
    def bubble_target_at(self,box,event):
        """鼠标位置对应的真实消息；元信息和“展开全文”也归回它所属的气泡。"""
        try:tags=box.tag_names(box.index('@%d,%d'%(event.x,event.y)))
        except tk.TclError:return None
        for tag in tags:
            if str(tag)=='bubble_example':
                return 'example','bubble_example'
            parts=str(tag).split('_')
            if len(parts)>=2 and parts[0]=='bubble' and parts[1].isdigit():
                return int(parts[1]),'bubble_'+parts[1]
        return None
    def copy_selected_bubble_text(self,event=None):
        """保留原生拖选体验；Ctrl+C 只复制用户实际选中的文字。"""
        box=getattr(self,'idea_log',None)
        if box is None:return 'break'
        try:text=box.get('sel.first','sel.last')
        except tk.TclError:return 'break'
        if not text:return 'break'
        from prompt_window import copy_text
        reason=copy_text(box,text)
        self.status.set('复制失败：'+reason if reason else '已复制选中文字')
        return 'break'
    def notice_selected_bubble_text(self,event):
        """长按拖选到消息正文后给出明确复制提示；不改动 Tk 原生蓝色选区。"""
        box=event.widget
        try:
            selected=box.tag_ranges('sel')
            tags=box.tag_names(selected[0]) if len(selected)>=2 else ()
        except tk.TclError:return None
        if any(str(tag).startswith('bubble_') and str(tag).split('_')[1:2] and
               str(tag).split('_')[1].isdigit() for tag in tags):
            self.status.set('已选中气泡正文，按 Ctrl+C 复制。')
        return None
    def begin_bubble_click(self,event,index,name):
        """记录正文按下位置；正在编辑同一气泡时交还给 Tk 原生选字。"""
        edit=getattr(self,'_bubble_edit',None)
        if edit and edit.get('box') is event.widget and edit.get('index')==index:
            self._bubble_click=None
            return None
        self._bubble_click={'box':event.widget,'index':index,'name':name,
                            'x':event.x,'y':event.y,'dragged':False}
        return None
    def track_bubble_click(self,event):
        """鼠标移动说明用户在选字，不能误切进编辑态。"""
        click=getattr(self,'_bubble_click',None)
        if click and click.get('box') is event.widget:
            if abs(event.x-click['x'])>3 or abs(event.y-click['y'])>3:
                click['dragged']=True
        return None
    def finish_bubble_click(self,event):
        """短按正文进入编辑；长按拖选继续使用原生蓝色选区。"""
        click=getattr(self,'_bubble_click',None)
        self._bubble_click=None
        self.notice_selected_bubble_text(event)
        if not click or click.get('box') is not event.widget or click.get('dragged'):
            return None
        try:
            selected=event.widget.tag_ranges('sel')
            if len(selected)>=2 and event.widget.compare(selected[0],'!=',selected[-1]):
                return None
        except tk.TclError:
            return None
        return self.safe(lambda:self.start_bubble_edit(event,click['index'],click['name']))
    def copy_bubble_message(self,index):
        """右键“复制整条信息”：只取持久化的正文，不把界面元信息混进去。"""
        if index == 'example':
            text=self.idea_example()
            if not text:return None
            from prompt_window import copy_text
            reason=copy_text(self.idea_log,text)
            self.status.set('复制失败：'+reason if reason else '已复制软件示例')
            if reason:return None
            return text
        import idea_chat
        rows=idea_chat.load(self.idea_chat_context(),model=self.idea_chat_model(),gateway=self.idea_chat_gateway())
        if not 0<=index<len(rows):return None
        text=str(rows[index].get('text') or '')
        if not text:return None
        from prompt_window import copy_text
        reason=copy_text(self.idea_log,text)
        self.status.set('复制失败：'+reason if reason else '已复制整条信息')
        if reason:return None
        return text
    def delete_bubble_message(self,index):
        """右键“删除整条信息”：移出当前对话，并保留最近删除恢复记录。"""
        import idea_chat
        model=self.idea_chat_model()
        rows=idea_chat.load(self.idea_chat_context(),model=model,gateway=self.idea_chat_gateway())
        if not 0<=index<len(rows):return None
        idea_chat.remove(self.idea_chat_context(),index,model=model,gateway=self.idea_chat_gateway())
        self.show_conversation();self.status.set('已删除整条信息；可在右键菜单恢复最近删除')
        return index
    def restore_latest_bubble_message(self):
        """恢复当前模型聊天页最近删除的一条完整消息。"""
        import idea_chat
        row=idea_chat.restore_latest_removed(self.idea_chat_context(),model=self.idea_chat_model(),gateway=self.idea_chat_gateway())
        self.show_conversation();self.status.set('已恢复最近删除的整条信息')
        return row
    def open_bubble_menu(self,event):
        """消息右键菜单；点击标题、正文或展开控件都能定位同一条消息。"""
        if getattr(self,'_bubble_edit',None):self.finish_bubble_edit()
        target=self.bubble_target_at(event.widget,event)
        if target is None:return None
        index,_name=target
        menu=ContextMenu(event.widget)
        if index == 'example':
            menu.command('复制软件示例',lambda:self.copy_bubble_message('example'))
        else:
            menu.command('复制整条信息',lambda i=index:self.copy_bubble_message(i))
            menu.command('删除整条信息',lambda i=index:self.delete_bubble_message(i))
            menu.command('恢复最近删除的信息',self.restore_latest_bubble_message)
        self._bubble_menu=menu
        return menu.popup(event)
    def open_idea_paste_menu(self,event):
        """输入框右键时，仅在剪贴板有文字时给出粘贴入口。"""
        box=event.widget
        try:text=str(box.clipboard_get() or '')
        except tk.TclError:return 'break'
        if not text:return 'break'
        menu=ContextMenu(box, menu_factory=tk.Menu).command('粘贴',lambda:box.event_generate('<<Paste>>'))
        self._idea_paste_menu=menu
        return menu.popup(event)
    def update_idea_attachment_status(self):
        """仅展示用户已选择的文件名；路径和正文不出现在界面或聊天记录。"""
        label=getattr(self,'idea_attachment_status',None)
        if label is None:return
        prepared=getattr(self.idea_chat_controller,'attachment_details',())
        details=['%s（%d 字）' % (name, count) for name,count in prepared]
        if not details:
            import idea_attachments
            for value in getattr(self,'idea_attachment_paths',()):
                try:details.append('%s（%d 字）' % (Path(value).name, len(idea_attachments.read_source(Path(value)))))
                except (OSError, ValueError):continue
        label.set(('已引用：'+'、'.join(details)) if details else '')
        # 未附档时不保留一整行空白；发送／阶段配置即可紧贴输入框。选择文件后才
        # 显示文件名，且仍不暴露本地路径。
        widget=getattr(self,'idea_attachment_status_label',None)
        row=getattr(self,'idea_input_row',None)
        if widget is None or row is None:return
        if details:
            if not widget.winfo_manager():widget.pack(anchor='w',pady=(1,0),after=row)
        elif widget.winfo_manager():
            widget.pack_forget()
    def choose_idea_attachments(self):
        """选择文本附档；入库、DOCX 解析和校验均在后台进行。"""
        paths=self.file_dialog.open_files(
            title='选择要提交给模型的文本附档', parent=self.win,
            filetypes=[('文本、Markdown 与 Word', '*.txt *.md *.markdown *.docx *.json *.csv *.yaml *.yml *.log'),
                       ('所有文件', '*.*')])
        if not paths:return ()
        self.idea_chat_controller.start_attachment_preparation(self.root, paths)
        if getattr(self,'idea_send',None) is not None:self.idea_send.state(['disabled'])
        self.status.set('正在后台入库和校验 %d 份创意文件…' % len(paths))
        return ()

    def poll_idea_attachment_preparation(self):
        """仅在 Tk 主线程更新附件状态；后台线程绝不触碰控件。"""
        result=self.idea_chat_controller.poll_attachment_preparation()
        if result is None:return
        if (getattr(self,'idea_send',None) is not None and self.idea_send.winfo_exists()
                and not self.idea_chat_controller.requesting):
            self.idea_send.state(['!disabled'])
        if not result['ok']:
            self.status.set('创意文件未入库：'+str(result['value']))
            return
        prepared=result['value']
        self.update_idea_attachment_status()
        self.status.set('已入库 %d 份创意文件；发送时将作为本轮模型素材提交。' % len(prepared['names']))
    def insert_idea_reference(self, path):
        """把已入库创意插入编辑框，并标记为本轮显式引用。"""
        box=getattr(self,'idea_input',None)
        if box is None or not box.winfo_exists():return
        value=str(Path(path))
        self.idea_chat_controller.add_attachment(value)
        box.insert('insert','@'+Path(path).name)
        self.update_idea_attachment_status()
    def show_idea_reference_menu(self, event):
        """用户输入 @ 时仅展示当前项目已入库的创意，不访问任意本地文件。"""
        if str(getattr(event,'char',''))!='@':return None
        from stage_execution_service import stage_idea_attachment_paths
        paths=stage_idea_attachment_paths(self.root)
        if not paths:return None
        menu=ContextMenu(event.widget, menu_factory=tk.Menu)
        for path in paths:
            menu.command(path.name,lambda item=path:self.insert_idea_reference(item))
        self._idea_reference_menu=menu
        return menu.popup(event)
    def bubble_edit_position_allowed(self,box,index,selection=True):
        """编辑态的插入点／选区只能落在正文标记内，气泡外的标题和控件永远只读。"""
        edit=getattr(self,'_bubble_edit',None)
        if not edit or edit.get('box') is not box:return True
        try:
            if selection:
                ranges=box.tag_ranges('sel')
                if len(ranges)>=2 and (box.compare(ranges[0],'<',edit['start']) or
                                       box.compare(ranges[-1],'>',edit['end'])):
                    return False
            return not (box.compare(index,'<',edit['start']) or box.compare(index,'>',edit['end']))
        except tk.TclError:return False
    def guard_bubble_edit_key(self,event):
        """聊天记录常态只读；编辑时也阻止内容越过当前气泡正文边界。"""
        edit=getattr(self,'_bubble_edit',None)
        if not edit or edit.get('box') is not event.widget:
            # 只读记录区仍应保留 Tk 原生的阅读导航；普通字符才需要拦截，
            # 防止焦点停在记录区时意外改写内容。
            if event.keysym in {'Up','Down','Left','Right','Prior','Next',
                                'Home','End','Tab','ISO_Left_Tab'}:
                return None
            return 'break'
        box=event.widget
        try:insert=box.index('insert')
        except tk.TclError:return 'break'
        if not self.bubble_edit_position_allowed(box,insert):return 'break'
        if event.keysym=='BackSpace' and not box.tag_ranges('sel') and box.compare(insert,'<=',edit['start']):
            return 'break'
        if event.keysym=='Delete' and not box.tag_ranges('sel') and box.compare(insert,'>=',edit['end']):
            return 'break'
        return None
    def guard_bubble_edit_pointer(self,event):
        """只在拖选越出正文时限制边界，正文内的选择完全交给 Tk。"""
        edit=getattr(self,'_bubble_edit',None)
        box=event.widget
        if not edit or edit.get('box') is not box:return None
        try:point=box.index('@%d,%d'%(event.x,event.y))
        except tk.TclError:return 'break'
        if not (box.compare(point,'<',edit['start']) or box.compare(point,'>',edit['end'])):
            return None
        if box.compare(point,'<',edit['start']):point=edit['start']
        else:point=edit['end']
        box.mark_set('insert',point)
        return None
    def start_bubble_edit(self,event,index,name):
        """单击消息正文后直接编辑；不再弹出编辑或删除窗口。"""
        if not isinstance(index,int) and index != 'example':return 'break'
        box=event.widget
        if getattr(self,'_bubble_edit',None):self.finish_bubble_edit()
        ranges=box.tag_ranges(name)
        if len(ranges)<2:return 'break'
        import idea_chat
        if index == 'example':
            rows=[]
        else:
            rows=idea_chat.load(self.idea_chat_context(),model=self.idea_chat_model(),gateway=self.idea_chat_gateway())
            if not isinstance(index,int) or not 0<=index<len(rows):
                raise ValueError('这条对话已不存在，请刷新后重试')
        # 折叠的长消息进入编辑时先还原全文，避免只修改预览那几行。
        record=getattr(self,'_bubble_full',{}).get(name,{})
        original=str(record.get('text') or (rows[index].get('text') if rows else self.idea_example()) or '').strip()
        box.configure(state='normal',cursor='xterm')
        box.delete(ranges[0],ranges[-1])
        box.insert(ranges[0],original,name)
        body_end=box.index('%s+%dc'%(ranges[0],len(original)))
        box.insert(body_end,'\n',name)
        start,end='bubble_edit_start','bubble_edit_end'
        box.mark_set(start,ranges[0]);box.mark_gravity(start,'left')
        box.mark_set(end,body_end);box.mark_gravity(end,'right')
        self._bubble_edit={'box':box,'index':index,'start':start,'end':end,'original':original}
        try:box.mark_set('insert',box.index('@%d,%d'%(event.x,event.y)))
        except tk.TclError:box.mark_set('insert',start)
        box.focus_set()
        self.status.set('正在直接编辑软件示例；修改仅保留在本次打开期间。' if index == 'example'
                        else '正在直接编辑消息；只能改气泡正文，删空后点击其他位置即可删除。')
        return 'break'
    def finish_bubble_edit(self,event=None,commit=True):
        """把当前气泡内的直接编辑同步到对话记录；空内容表示删除该条。"""
        edit=getattr(self,'_bubble_edit',None)
        if not edit:return None
        self._bubble_edit=None
        box=edit['box']
        try:value=box.get(edit['start'],edit['end']).strip()
        except tk.TclError:value=edit['original']
        try:box.mark_unset(edit['start'],edit['end'])
        except tk.TclError:pass
        if not commit:
            self.show_conversation()
            self.status.set('已取消修改这条对话')
            return 'break'
        if value==edit['original']:
            self.show_conversation()
            return 'break'
        if edit['index'] == 'example':
            # 软件示例只是可编辑的本次会话提示：绝不伪装成用户消息或写入项目目录。
            self._idea_example=value or edit['original']
            self.show_conversation()
            self.status.set('已修改软件示例（仅本次打开期间有效）')
            return 'break'
        import idea_chat
        model=self.idea_chat_model()
        if value:idea_chat.replace(self.idea_chat_context(),edit['index'],value,model=model,gateway=self.idea_chat_gateway());notice='已修改这条对话'
        else:idea_chat.remove(self.idea_chat_context(),edit['index'],model=model,gateway=self.idea_chat_gateway());notice='已删除这条对话'
        self.show_conversation()
        self.status.set(notice)
        return 'break'
    def add_bubble(self,box,row,index):
        """把一条对话排成微信式左右气泡，并在顶部标出说话者／模型名。"""
        raw_text=str(row.get('text') or '')
        # 软件示例是可复制、可编辑的参考文本；不能为了普通聊天气泡的排版
        # ``strip`` 掉它首尾的换行或空格，否则展示内容已不再等于程序提供的示例。
        # 普通消息仍沿用既有的首尾空白清理，避免空白消息生成气泡。
        text=raw_text if index == 'example' else raw_text.strip()
        if not text.strip():return
        mine=str(row.get('role'))=='user'
        left,right=self.bubble_margins(box,text,mine)
        name='bubble_'+str(index)
        # 页面刚建好时框子还没量过宽度，这一条要留着，等真实宽度下来再摆一次（见 refit_bubbles）。
        getattr(self,'_bubble_rows',[]).append((name,text,mine))
        # 用户气泡仍贴右侧；正文一律由气泡左边开始，长句更容易读。
        align='left'
        example=index == 'example'
        model_back, model_meta = self.model_chat_colors(row.get('model'))
        look=dict(justify=align,
                  background='' if example else ('#dff5e3' if mine else model_back),
                  foreground='#8a96a5' if example else '#243247',
                  lmargin1=left,lmargin2=left,rmargin=right,
                  spacing1=2,spacing2=1,spacing3=4,font=BUBBLE_FONT,wrap='word')
        # Tk 默认连边距一起刷成气泡色，那样每条都是满屏一条；把两边留白按框底的白走，
        # 色块才贴着字（-lmargincolor／-rmargincolor，Tk 8.6 起）。
        bubble_padding=0 if example else BUBBLE_PAD
        margin_back=box.cget('bg') if example else BUBBLE_BACK
        try:box.tag_configure(name,borderwidth=bubble_padding,relief='flat',
                              lmargincolor=margin_back,rmargincolor=margin_back,**look)
        except tk.TclError:box.tag_configure(name,**look)
        box.tag_configure(name+'_meta',justify=align,foreground='#a1aab5' if example else (model_meta if not mine else '#718196'),
                          lmargin1=left,lmargin2=left,rmargin=right,spacing1=4,spacing3=1,
                          font=BUBBLE_TIME_FONT)
        box.insert('end',self.model_name(row)+'\n',name+'_meta')
        stamp=self.bubble_time(row.get('at'))
        if stamp:
            box.tag_configure(name+'_time',justify=align,foreground='#9aa7b7',
                              lmargin1=left,lmargin2=left,rmargin=right,spacing1=0,spacing3=1,font=BUBBLE_TIME_FONT)
            box.insert('end',stamp+'\n',name+'_time')
        # 软件示例是用户填写前唯一的完整参考，不能被折叠；真实长对话仍保持收起功能。
        preview,folded=(text,False) if index=='example' else self.bubble_preview(text)
        self._bubble_full[name]={'text':text,'preview':preview,'expanded':not folded}
        box.insert('end',preview+'\n',name)
        if folded:
            toggle=name+'_toggle'
            # 操作在本条气泡的右下角，而非正文下方左侧；它属于 Text 内容，滚动时和
            # 对应消息一起移动，不会遮住用户正在阅读的其它消息。
            box.tag_configure(toggle,justify='right',foreground='#3564a8',underline=True,
                              lmargin1=left,lmargin2=left,rmargin=right,spacing1=0,spacing3=3,
                              font=BUBBLE_TIME_FONT)
            box.insert('end','展开全文\n',toggle)
            box.tag_bind(toggle,'<Button-1>',lambda event,b=box,n=name:self.toggle_bubble(b,n))
            box.tag_bind(toggle,'<Enter>',lambda event,b=box:b.configure(cursor='hand2'))
            box.tag_bind(toggle,'<Leave>',lambda event,b=box:b.configure(cursor='xterm'))
        if isinstance(index,int) or example:
            # 入口留在消息自身：包括无底色软件示例；拖动时仍由原生 Text 选区负责复制。
            box.tag_bind(name,'<Button-1>',lambda event,i=index,n=name:self.begin_bubble_click(event,i,n))
            box.tag_bind(name,'<Enter>',lambda event,b=box:b.configure(cursor='hand2'))
            box.tag_bind(name,'<Leave>',lambda event,b=box:b.configure(cursor='xterm'))
    def show_thinking(self,model):
        """模型正在请求时，在最近一条消息下方放临时状态；不会写入对话记录。"""
        self._thinking_model=str(model or 'AI 助手').strip()
        self.show_conversation()
    def clear_thinking(self):
        if getattr(self,'_thinking_model',''):
            self._thinking_model=''
            self.show_conversation()
    def idea_chat_model(self):
        """当前剧本阶段的模型标识；它也是独立聊天页的持久化分区键。"""
        if not self.root:
            return ''
        import writing_api
        direct = writing_api.model_label(self.root)
        if direct:
            return direct
        from workflow_settings import model_name
        return model_name(self.root, 'writing')
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
    def show_conversation(self):
        """重绘只读聊天记录；长记录按空闲批次插入，不阻塞剧本页首帧。"""
        import idea_chat
        box=getattr(self,'idea_log',None)
        if box is None or not box.winfo_exists():return
        self._idea_view_generation=getattr(self,'_idea_view_generation',0)+1
        generation=self._idea_view_generation
        previous_jobs=getattr(self,'_idea_view_after_jobs',())
        for job in previous_jobs:
            try:box.after_cancel(job)
            except tk.TclError:pass
        jobs=[]
        self._idea_view_after_jobs=jobs
        def alive():
            try:return (generation==getattr(self,'_idea_view_generation',0)
                       and box.winfo_exists() and box is getattr(self,'idea_log',None))
            except tk.TclError:return False
        def cancel_view_jobs(event=None):
            if event is not None and getattr(event,'widget',None) is not box:
                return None
            for job in tuple(jobs):
                try:box.after_cancel(job)
                except tk.TclError:pass
            jobs.clear()
            return None
        box.bind('<Destroy>',cancel_view_jobs,add='+')
        def later(delay, callback):
            if not alive():return None
            try:job=box.after(delay,callback)
            except tk.TclError:return None
            jobs.append(job)
            return job
        def idle(callback):
            if not alive():return None
            try:job=box.after_idle(callback)
            except tk.TclError:return None
            jobs.append(job)
            return job
        root=self.root
        cached=getattr(self,'_idea_view_model_cache',None)
        resolving_model=False
        if root and (not isinstance(cached,tuple) or cached[0]!=root):
            requested=getattr(self,'_idea_view_model_request',0)+1
            self._idea_view_model_request=requested
            resolved=queue.Queue(maxsize=1)
            def resolve_model():
                try:resolved.put(self.idea_chat_model())
                except Exception:resolved.put('')
            def resume():
                try:model=resolved.get_nowait()
                except queue.Empty:
                    later(50,resume)
                    return
                if (not self.shutting_down and requested==getattr(self,'_idea_view_model_request',0)
                        and self.root==root):
                    self._idea_view_model_cache=(root,model)
                    self.show_conversation()
            threading.Thread(target=resolve_model,daemon=True).start()
            later(50,resume)
            # 模型键只用于读取真实历史；软件示例和空会话壳不依赖它，先交还
            # 可见内容。键回来后 resume 按现有页面代次完整重绘真实历史。
            resolving_model=True
        model=cached[1] if root and isinstance(cached,tuple) else ''
        from stage_execution_service import project_context
        rows=idea_chat.load(project_context(root),model=model,gateway=self.idea_chat_gateway()) if root and not resolving_model else []
        box.configure(state='normal')
        self._bubble_rows=[];self._bubble_full={};self._bubble_width=int(box.winfo_width() or 0)
        for name in [one for one in box.tag_names() if one.startswith('bubble_')]:
            box.tag_delete(name)
        box.delete('1.0','end')
        def finish():
            if not alive():return
            thinking=getattr(self,'_thinking_model','')
            if thinking:
                name='bubble_thinking'
                left,right=self.bubble_margins(box,thinking,False)
                self._bubble_rows.append((name,thinking,False))
                box.tag_configure(name+'_thinking',justify='left',foreground='#718196',
                                  lmargin1=left,lmargin2=left,rmargin=right,spacing1=2,spacing3=3,
                                  font=BUBBLE_TIME_FONT)
                box.insert('end',thinking+' 模型正在思考…\n',name+'_thinking')
                streamed=getattr(self,'_stream_text','')
                if streamed:
                    self.add_bubble(box,{'role':'assistant','model':thinking,'text':streamed+'\n\n（生成中…）'},'streaming')
            if rows:
                try:box.see('end')
                except tk.TclError:pass
            # 一次空闲合并量测；逐条 add_bubble 不再触发布局往返。
            idle(lambda: alive() and self._fit_content_now())
        if rows:
            cursor=[0]
            def append_batch():
                if not alive():return
                end=min(cursor[0]+8,len(rows))
                while cursor[0]<end:
                    self.add_bubble(box,rows[cursor[0]],cursor[0]);cursor[0]+=1
                if cursor[0]<len(rows):
                    # 递归 after_idle 会被一次 update() 连续清空；真实项目的
                    # 历史消息因此仍会堵住首帧。短时延让输入区先处理事件。
                    later(12,append_batch)
                else:finish()
            idle(append_batch)
        else:
            # 空会话的范例也可能很长；首帧只保留已可交互的对话框壳，随后
            # 低优先级补入，不让逐字标签/量测占住 ``show_loaded_project``。
            def append_example():
                if not alive():return
                self.add_bubble(box,{'role':'assistant','model':'软件示例','text':self.idea_example()},'example')
                finish()
            idle(append_example)
        # 保持 normal 才能让 Tk 的原生鼠标拖选建立 ``sel`` 标签；只读由
        # guard_bubble_edit_key 控制，避免 disabled 状态吞掉拖选事件。
        box.configure(state='normal')

    def refresh_script_chat_for_selected_model(self):
        """阶段配置确认后，立刻切换到已选模型的独立聊天页。"""
        box = getattr(self, 'idea_log', None)
        if box is None or not box.winfo_exists():
            return False
        self._idea_view_model_cache=None
        self.show_conversation()
        self.update_script_download_button()
        return True
    def open_dialog(self):
        """发送框始终显示；此处只把焦点放回输入处。"""
        box=getattr(self,'idea_input',None)
        if box is not None and box.winfo_exists():
            box.configure(state='normal');box.focus_set()
    def close_dialog(self):
        """保存剧本也不隐藏发送框，用户仍可继续补充。"""
        self.open_dialog()
    def start_script_workflow(self, creative):
        """启动唯一的剧本 Agent 工作流，模型回复前不生成剧本文档。

        发送框不再直连任意文本 API。模型、SKILL 和追问顺序均由 writing 工作流的
        调用设置负责，避免普通聊天提示词绕开鲸剧等 SKILL 的开工门禁。
        """
        import idea_chat
        from workflow_settings import model_name
        model = model_name(self.root, 'writing')
        from workflow_tasks import script_followup, script_prompt
        prompt = script_prompt(self.root, None, 'writing', creative_text=creative)
        followup = script_followup(None, 'writing', project=self.root, creative_text=creative)
        self.open_flow_agent('writing', '剧本准备', prompt, followup)
        return model, False

    def open_brief_creation_form(self, current_text=''):
        """信息不足时显示可记忆的创作简报表；提交后仍复用普通发送入口。"""
        if not self.root:
            raise ValueError('请先打开项目')
        existing = getattr(self, '_brief_creation_window', None)
        try:
            if existing is not None and existing.winfo_exists():
                existing.deiconify(); existing.lift(); existing.focus_force(); return
        except tk.TclError:
            pass
        import idea_chat
        values = idea_chat.brief_creation_values(self.idea_chat_context(), current_text)
        def cleared():
            self._brief_creation_window = None
        win = FormDialog(self.win, '填写创作信息', geometry='700x680', minsize=(600, 520),
                         on_close=cleared)
        self._brief_creation_window = win
        outer = win.content
        outer.columnconfigure(0, weight=1)
        ttk.Label(outer, text='已自动记住上次填写内容；保存并发送后会写入 brief_creation.md。',
                  style='Muted.TLabel').grid(row=0, column=0, columnspan=2, sticky='w', pady=(SPACING['xs'], SPACING['md']))
        outer.rowconfigure(1, weight=1)
        canvas = tk.Canvas(outer, highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=1, column=0, sticky='nsew')
        scroll.grid(row=1, column=1, sticky='ns')
        form = ttk.Frame(canvas, padding=(0, 0, SPACING['sm'], 0))
        window_id = canvas.create_window((0, 0), window=form, anchor='nw')
        form.columnconfigure(1, weight=1, minsize=180)
        form.columnconfigure(3, weight=1, minsize=180)
        editors = {}
        tall = {'故事梗概', '故事角色', '物理特征', '故事分集', '特殊要求', '内容补充'}
        compact = [label for label in idea_chat.BRIEF_CREATION_FIELDS if label not in tall]
        for index, label in enumerate(compact):
            row, label_column = divmod(index, 2)
            label_column *= 2
            ttk.Label(form, text=label + '：', width=9, anchor='e').grid(
                row=row, column=label_column, sticky='e', padx=(0, SPACING['sm']), pady=SPACING['xs'])
            editor = TextArea(form, height=1, width=20, wrap='word')
            editor.insert('1.0', values.get(label, ''))
            editor.grid(row=row, column=label_column + 1, sticky='ew', padx=(0, SPACING['md']), pady=SPACING['xs'])
            editors[label] = editor
        # 统筹锁只在创作信息窗采集；无统筹或统筹未声明 locks 时完全不显示。
        import stage_config, workflow_settings
        workflow_config = stage_config.current_workflow(self.root)
        preset = workflow_settings.WORKFLOW_PRESETS.get(workflow_config.get('name'), {})
        lock_defs = preset.get('locks', ())
        lock_start = (len(compact) + 1) // 2
        for offset, lock_def in enumerate(lock_defs):
            row = lock_start + offset
            ttk.Label(form, text=lock_def['label'] + '：', width=9, anchor='e').grid(
                row=row, column=0, sticky='e', padx=(0, SPACING['sm']), pady=SPACING['xs'])
            value = ttk.Combobox(form, values=lock_def.get('options', ()), state='readonly')
            value.set(stage_config.workflow_lock(self.root).get(lock_def['key'], ''))
            value.grid(row=row, column=1, columnspan=3, sticky='ew', padx=(0, SPACING['md']), pady=SPACING['xs'])
            editors[lock_def['label']] = value
        detail_start = lock_start + len(lock_defs)
        ttk.Separator(form, orient='horizontal').grid(row=detail_start, column=0, columnspan=4,
                                                       sticky='ew', pady=(SPACING['xs'], SPACING['xs']))
        for offset, label in enumerate(label for label in idea_chat.BRIEF_CREATION_FIELDS if label in tall):
            row = detail_start + offset + 1
            ttk.Label(form, text=label + '：', width=9, anchor='ne').grid(
                row=row, column=0, sticky='ne', padx=(0, SPACING['sm']), pady=SPACING['xs'])
            editor = TextArea(form, height=2, width=56, wrap='word')
            editor.insert('1.0', values.get(label, ''))
            editor.grid(row=row, column=1, columnspan=3, sticky='ew', padx=(0, SPACING['md']), pady=SPACING['xs'])
            editors[label] = editor
        def refit(event=None):
            bounds = canvas.bbox('all')
            canvas.configure(scrollregion=bounds)
            canvas.itemconfigure(window_id, width=max(1, canvas.winfo_width()))
            content_height = (bounds[3] - bounds[1]) if bounds else 0
            if content_height <= canvas.winfo_height():
                scroll.grid_remove()
            else:
                scroll.grid()
        form.bind('<Configure>', refit); canvas.bind('<Configure>', refit)
        def scroll_form(event):
            delta = -int(event.delta / 120) if event.delta else 0
            if delta:
                canvas.yview_scroll(delta, 'units')
            return 'break'
        canvas.bind('<MouseWheel>', scroll_form)
        form.bind('<MouseWheel>', scroll_form)
        def close():
            win.close()
        def save_and_send():
            submitted = {label: (editor.get().strip() if isinstance(editor, ttk.Combobox)
                                else editor.get('1.0', 'end-1c').strip()) for label, editor in editors.items()}
            _path, text = idea_chat.save_brief_creation(self.idea_chat_context(), submitted, gateway=self.idea_chat_gateway())
            box = getattr(self, 'idea_input', None)
            if box is not None and box.winfo_exists():
                box.delete('1.0', 'end'); box.insert('1.0', text)
            close()
            self.safe(self.send_message)
        win.add_form_actions('保存并发送', save_and_send)
        protect_readonly_combobox(win)
        win.after_idle(refit)

    def send_message(self):
        """提交创意；显式 API 模型在聊天框内回复，其余仍启动剧本 Agent。"""
        box=getattr(self,'idea_input',None)
        if box is None or not box.winfo_exists():raise ValueError('这一页还没建好，请重新打开这一页')
        value=self.draft_text()
        prepared=self.idea_chat_controller.prepare_submission(
            self.root, value, is_example=self.idea_still_the_example())
        if prepared is None:
            self.open_brief_creation_form()
            return
        submission=prepared['submission']
        visible_value=prepared['visible_value']
        import idea_chat
        import writing_api
        direct_model = writing_api.model_label(self.root)
        if direct_model and self.idea_chat_controller.requesting:
            raise ValueError('模型正在回复，请不要重复发送。')
        # 先把用户创意交给简报契约：未齐时由本地一次性追问缺项，绝不提前启动模型工作流。
        import stage_config, workflow_settings
        workflow_config = stage_config.current_workflow(self.root)
        preset = workflow_settings.WORKFLOW_PRESETS.get(workflow_config.get('name'), {})
        brief = idea_chat.receive_brief(self.idea_chat_context(), submission, workflow=workflow_config,
                                        lock_definitions=preset.get('locks', ()), gateway=self.idea_chat_gateway())
        if brief.get('workflow_projection') is not None:
            stage_config.put_workflow(self.root, brief['workflow_projection'])
        if direct_model:
            model = direct_model
            cleared = False
        else:
            from workflow_settings import model_name
            model, cleared = model_name(self.root, 'writing'), False
        if not brief['missing']:
            self.idea_chat_controller.mark_sent()
            if not direct_model:
                # 启动失败不能吞掉用户刚输入的内容；成功启动后才落聊天记录并清空编辑框。
                try:model, cleared = self.start_script_workflow(submission)
                except Exception:
                    self.idea_chat_controller.rollback_sent()
                    raise
        idea_chat.append(self.idea_chat_context(),'user',visible_value,model=model,gateway=self.idea_chat_gateway())
        box.delete('1.0','end')
        self.discard_idea_draft()
        self.idea_attachment_paths=()
        self.update_idea_attachment_status()
        self.show_conversation()
        if brief['missing']:
            idea_chat.append(self.idea_chat_context(), 'assistant', brief['followup'], model=model,gateway=self.idea_chat_gateway())
            self.show_conversation()
            self.status.set('已保存创意草稿；请补充缺少的信息后再发送。')
            self.open_brief_creation_form(value)
            return
        prefix = '已打开 '+model+' 的独立对话；' if cleared else ''
        if direct_model:
            token, cancelled = self.idea_chat_controller.begin_request(cancellable=True)
            self.set_hollmwood_role_status()
            async_ticket={'value':None}
            def report_role(role,step):
                current=async_ticket['value']
                if current is not None and self.idea_chat_controller.requesting:
                    self.hollmwood_progress.put((current,role,step))
            if getattr(self,'idea_send',None) is not None:self.idea_send.state(['disabled'])
            self.update_script_interrupt_button()
            self._stream_text=''
            self.show_thinking(model)
            def received(result):
                if not self.idea_chat_controller.finish_request(token):return
                if getattr(self,'idea_send',None) is not None and self.idea_send.winfo_exists():self.idea_send.state(['!disabled'])
                self.update_script_interrupt_button()
                self._stream_text=''
                self.clear_thinking()
                if not result.get('ok'):
                    error=str(result.get('error') or '未收到模型回复')
                    transient=any(mark in error for mark in ('URLError', 'SSLError', 'SSLEOF', 'UNEXPECTED_EOF'))
                    message=('网络连接被模型网关中断，未生成内容；请点击发送重试。'
                             if transient else '模型调用未完成：'+error)
                    self.set_hollmwood_role_status()
                    self.status.set(message)
                    # 直接 API 模型与桌面 Agent 共用“剧本准备”这个自动阶段。
                    # 失败若只写状态栏，三虎会一直把 script 视为 active；仅当
                    # 自动链确实正在等待 script 时，才把可恢复的调用失败交给它。
                    auto=getattr(getattr(self,'pet',None),'auto',None)
                    if getattr(auto,'active',None)=='script':
                        # HOLLMWOOD 自己已经对空正文执行过受控重试；再让通用
                        # Agent 重试只会留下一个没有新请求的 retrying 状态。因此
                        # 直接发出终态失败，明确停在可由用户重试的剧本阶段。
                        self.pet._emit('stage.failed',stage='script',error=message)
                    return
                reply=str(result.get('text') or '').strip()
                if not reply:
                    self.notifier.error(idea_chat.why_empty(result), title='模型调用失败')
                    self.status.set(idea_chat.why_empty(result));return
                idea_chat.append(self.idea_chat_context(),'assistant',reply,model=model,gateway=self.idea_chat_gateway())
                self.show_conversation();self.update_script_download_button()
                if result.get('script_raw_path'):
                    four_roles = result.get('hollmwood_enabled', True)
                    if four_roles:
                        self.set_hollmwood_role_status(complete=True)
                    refresh=getattr(self,'refresh_script_list',None)
                    if callable(refresh):refresh()
                    self.pet_report('script', script_raw_saved_notice(four_roles))
                self.status.set('已收到 '+model+' 的回复；完整剧本可下载保存。')
            from workflow_engines import (request_stage_process_slot, claim_stage_process_slot,
                                          release_stage_process_slot)
            def dispatch(slot):
                def ask():
                    try:
                        from stage_execution_service import reply_to_writing
                        return reply_to_writing(
                            self.root, submission, progress=report_role,
                            cancelled=cancelled.is_set,
                            stream=lambda chunk:self.hollmwood_progress.put(
                                (async_ticket['value'],'actor_stream',chunk)))
                    finally:
                        release_stage_process_slot(slot)
                # async_ 在主线程先递增序号、再启动工作线程；先写入预期值可保证
                # 极快的首个 SSE 分片也拥有正确的 UI 请求令牌。
                async_ticket['value']=self._async_ticket+1
                actual_ticket=self.async_(ask,received,label=model+' 模型正在思考…')
                async_ticket['value']=actual_ticket
            request=request_stage_process_slot(self.root,'writing')
            if request['state']=='granted':
                dispatch(request['slot'])
            else:
                self.status.set('模型请求排队中（第%d位），界面保持响应。' % request['position'])
                def poll_slot():
                    if not self.idea_chat_controller.requesting or cancelled.is_set():
                        return
                    claimed=claim_stage_process_slot(request['ticket'])
                    if claimed['state']=='queued':
                        self.status.set('模型请求排队中（第%d位），界面保持响应。' % claimed['position'])
                        self.win.after(200,poll_slot);return
                    if claimed['state']=='granted':
                        self.status.set('已获得模型请求槽位，正在思考…')
                        dispatch(claimed['slot']);return
                    if self.idea_chat_controller.finish_request(token):
                        if getattr(self,'idea_send',None) is not None and self.idea_send.winfo_exists():
                            self.idea_send.state(['!disabled'])
                        self.update_script_interrupt_button();self.clear_thinking()
                        self.status.set(claimed.get('reason','模型请求已取消'))
                self.win.after(200,poll_slot)
        else:
            self._script_agent_launching=True
            self.update_script_interrupt_button()
            self.status.set(prefix+'已提交创意并启动剧本 Agent；模型回复完整剧本后可下载保存。')
        self.update_script_download_button()

    def script_agent_processes(self):
        """返回当前剧本阶段由本窗口启动、仍在运行的 Agent 进程。"""
        sessions=getattr(self,'flow_processes',{})
        return [(key,process) for key,process in sessions.items()
                if len(key)>1 and key[1]=='writing' and process.poll() is None]

    def poll_flow_processes(self):
        """回收已退出的桌面 Agent；自动链只把异常退出标为失败。

        交互式 Agent 正常退出并不等于已经产出可采用的文件，因此不能据此推进阶段；
        但非零退出时，当前自动阶段必须收到终止信号，避免一直卡在“制作中”。
        """
        sessions=getattr(self,'flow_processes',{})
        if not sessions:return
        from workflow_engines import forget_process, cancel_stage_slot_requests
        cancel_stage_slot_requests(self.root)
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
                    message='剧本 Agent 已保存自然剧本：'+source.name
                    self.status.set(message)
                    # 完成事件只经三虎的产物校验出口；Agent 正常退出本身不是成功证据。
                    self.pet.report_done('script', message)
        self.flow_processes=remaining

    def update_script_interrupt_button(self):
        """按剧本 API 请求或剧本 Agent 的运行状态更新中断按钮。"""
        button=getattr(self,'idea_interrupt',None)
        if button is None or not button.winfo_exists():return
        active=(getattr(self,'_idea_requesting',False) or
                getattr(self,'_script_agent_launching',False) or bool(self.script_agent_processes()))
        button.state(['!disabled'] if active else ['disabled'])

    def refresh_script_workspace(self):
        """刷新剧本聊天和文件表；旧 Claude 思考块会先清洗，必要时仅重发一次正文请求。"""
        import idea_chat
        import writing_api
        repaired = idea_chat.repair_internal_replies(self.idea_chat_context(), model=self.idea_chat_model(), gateway=self.idea_chat_gateway())
        self.show_conversation()
        refresh = getattr(self, 'refresh_script_list', None)
        if callable(refresh):
            refresh()
        creative = repaired.get('retry_creative') or ''
        model = writing_api.model_label(self.root)
        if not creative:
            self.status.set('已刷新对话和剧本文件列表。')
            return True
        if not model:
            self.status.set('已移除无法显示的内部内容；请重新发送上一条创意获取正文。')
            return True
        if getattr(self, '_idea_requesting', False):
            self.status.set('模型正在回复；已刷新显示，稍后会自动显示正文。')
            return True
        token, _unused_cancel = self.idea_chat_controller.begin_request(cancellable=False)
        if getattr(self, 'idea_send', None) is not None:self.idea_send.state(['disabled'])
        self.update_script_interrupt_button();self.show_thinking(model)
        def received(result):
            if not self.idea_chat_controller.finish_request(token):return
            if getattr(self, 'idea_send', None) is not None and self.idea_send.winfo_exists():self.idea_send.state(['!disabled'])
            self.update_script_interrupt_button();self.clear_thinking()
            if not result.get('ok'):
                self.notifier.error(str(result.get('error') or '未收到模型回复'), title='模型调用失败')
                self.status.set('刷新正文失败：' + str(result.get('error') or '未收到模型回复'))
                return
            reply = str(result.get('text') or '').strip()
            if not reply:
                self.notifier.error(idea_chat.why_empty(result), title='模型调用失败')
                self.status.set(idea_chat.why_empty(result));return
            idea_chat.append(self.idea_chat_context(), 'assistant', reply, model=model,gateway=self.idea_chat_gateway())
            self.show_conversation();self.update_script_download_button()
            self.status.set('已恢复并刷新 ' + model + ' 的正文；完整剧本可下载保存。')
        from stage_execution_service import reply_to_writing
        self.async_(lambda: reply_to_writing(self.root, creative), received,
                    label=model + ' 模型正在重新生成正文…')
        return True

    def interrupt_script_agent(self):
        """中断当前剧本 API 请求或本窗口启动的剧本 Agent，不影响其他制作阶段。"""
        api_active=getattr(self,'_idea_requesting',False)
        processes=self.script_agent_processes()
        launching=getattr(self,'_script_agent_launching',False)
        if not api_active and not processes and not launching:
            self.status.set('当前没有可中断的剧本 Agent 调用。')
            return False
        self._async_ticket+=1;self.background_tasks.cancel()
        self.worker=False;self.busy_state.set_busy(False)
        self.idea_chat_controller.cancel_request()
        self._stream_text=''
        if getattr(self,'idea_send',None) is not None and self.idea_send.winfo_exists():self.idea_send.state(['!disabled'])
        self.clear_thinking()
        stopped=[]
        from workflow_engines import forget_process
        sessions=getattr(self,'flow_processes',{})
        for key,process in processes:
            try:
                from platform_tools import terminate_process_tree
                if terminate_process_tree(process):
                    stopped.append(str(process.pid))
                forget_process(self.root,process)
            except (OSError,subprocess.SubprocessError):pass
            sessions.pop(key,None)
        self.flow_processes=sessions
        self.update_script_interrupt_button()
        detail=('，已结束进程 '+', '.join(stopped)) if stopped else ''
        self.status.set('已中断剧本 Agent 调用'+detail+'；API 请求将不再进入后续角色或落盘，可修改创意后重新发送。')
        return True
    def update_script_download_button(self):
        """只有模型给出完整剧本后才允许下载；首次回复绝不弹完成框。"""
        import idea_chat
        button=getattr(self,'idea_download',None)
        if button is None or not button.winfo_exists():return False
        ready=not getattr(self,'_idea_requesting',False) and idea_chat.looks_like_script(idea_chat.latest_text(self.idea_chat_context(),gateway=self.idea_chat_gateway()))
        button.state(['!disabled'] if ready else ['disabled'])
        return ready
    def download_script(self):
        """用户明确下载剧本文档后，才通知三虎询问是否进入分镜阶段。"""
        import idea_chat
        reply=idea_chat.latest_text(self.idea_chat_context(),gateway=self.idea_chat_gateway())
        if not idea_chat.looks_like_script(reply):raise ValueError('请先让模型生成完整剧本，再下载。')
        provider, model = idea_chat.storage_identity(self.idea_chat_model())
        from stage_execution_service import publish_idea_creative
        saved=idea_chat.save_reply(self.idea_chat_context(),reply,provider=provider,model=model,
                                   publish=publish_idea_creative)
        self.brief_editor=(saved,getattr(self,'idea_log',None))
        self.close_dialog()
        refresh=getattr(self,'refresh_script_list',None)
        if callable(refresh):refresh()
        self.status.set('剧本已下载：'+saved.name)
        listener=getattr(self.pet,'script_downloaded',None)
        if callable(listener):listener(saved)
        self.update_script_download_button()
        return saved
    def confirm_script(self):
        """兼容旧入口：保存动作改为用户显式下载。"""
        return self.download_script()
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
        self._async_ticket+=1;ticket=self.background_tasks.submit(self._async_ticket)
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
    def _poll_auto_edit_result(self):
        self._auto_edit_result_poll_id=None
        if getattr(self,'shutting_down',False) or not getattr(self,'_startup_tick_paused',False):return
        self._drain_auto_edit_result()
        if getattr(self,'auto_edit_busy',False):self._schedule_auto_edit_result_poll()
    def _schedule_auto_handoff_result_poll(self):
        """启动期暂停全局 tick 时，仍交付已经派发的自动交接结果。"""
        if (getattr(self,'shutting_down',False) or not getattr(self,'_startup_tick_paused',False)
                or getattr(self,'_auto_handoff_result_poll_id',None) is not None):
            return None
        self._auto_handoff_result_poll_id=self.win.after(50,self._poll_auto_handoff_result)
        return self._auto_handoff_result_poll_id
    def _poll_auto_handoff_result(self):
        self._auto_handoff_result_poll_id=None
        if getattr(self,'shutting_down',False) or not getattr(self,'_startup_tick_paused',False):return
        self._drain_auto_handoff_result()
        if getattr(self,'auto_handoff_busy',False):self._schedule_auto_handoff_result_poll()
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
    def poll_hollmwood_progress(self):
        """每 100ms 在 Tk 主线程消化角色进度；工作线程只允许写 Queue。"""
        labels={'director':'导演','writer':'编剧','editor':'编辑','actor':'演员'}
        try:
            while True:
                ticket,role,step=self.hollmwood_progress.get_nowait()
                if ticket!=self._async_ticket or not getattr(self,'_idea_requesting',False):continue
                name=labels.get(role.split('_',1)[0],role)
                if role == 'actor_stream':
                    self._stream_text += str(step)
                    self.status.set('演员正在流式生成剧本…')
                    self.show_conversation()
                    continue
                self.set_hollmwood_role_status(role)
                text=name+' 正在工作…'
                self.status.set(text)
                if self.root:
                    from broadcaster import Broadcaster
                    Broadcaster(Path(self.root)/'logs'/'sanhu_progress.log').broadcast(
                        Broadcaster.stage(1, 'HOLLMWOOD：'+text))
        except queue.Empty:pass
    def set_hollmwood_role_status(self, active='', complete=False):
        """在总进度条下方显示 HOLLMWOOD 四角色的当前状态。"""
        variable=getattr(self,'hollmwood_role_status',None)
        if variable is None:return ''
        labels={'director':'导演','writer':'编剧','editor':'编辑','actor':'演员'}
        active=str(active or '').split('_',1)[0]
        if complete:text='导演：已完成  ·  编剧：已完成  ·  编辑：已完成  ·  演员：已完成'
        else:text='  ·  '.join(label+'：'+('工作中' if key==active else ('待命' if active else '等待')) for key,label in labels.items())
        try:variable.set(text)
        except (tk.TclError,AttributeError):pass
        return text
    def cancel_timers(self,event=None):
        # 先停掉定时器再销毁窗口：残留的 after 回调会在 Tk 里报 invalid command name。
        if event is not None and event.widget is not self.win:return
        self.shutting_down=True
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
                except Exception:pass
            try:pet.stop()
            except Exception:pass
            # 第 18 期的开机招呼也挂在这个窗口上：还没到点就关窗，一样要收回来。
            try:pet.cancel_greet()
            except Exception:pass
        controller=getattr(self,'startup_controller',None)
        if controller is not None:
            try:controller.cancel()
            except Exception:pass
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
        except Exception:pass
    def _after_first_paint(self):
        """首帧已交给 Tk 后，才恢复会触发轮询／回填的周期 tick。"""
        self.win._desktop_first_paint_complete=True
        self._start_legacy_project_migration()
        # 首帧通知不能覆盖用户已发起的后台操作（例如“强制关闭 ComfyUI”）；
        # 否则任务实际结束后状态栏仍停在“正在打开今日项目”。
        # 自动续开尚未选择项目时才显示这条启动提示。已有项目（含测试或
        # 外部入口已经装配好的项目）不能让延后的首帧回调覆盖刚完成的操作结果。
        if self.root is None and not self.worker and not self.projects.legacy_migration_pending:
            self.status.set('正在打开今日项目…')

    def _start_legacy_project_migration(self):
        """首帧后才在 worker 迁移旧目录；Tk 线程只轮询结果。"""
        if (self._legacy_project_migration_started or not self.projects.legacy_migration_pending
                or getattr(self,'shutting_down',False)):
            return
        self._legacy_project_migration_started=True
        def migrate():
            try:
                self._project_result_data(self.projects.migrate())
            except Exception as exc:
                self._legacy_project_migration_results.put(exc)
            else:
                self._legacy_project_migration_results.put(None)
        threading.Thread(target=migrate,name='legacy-project-migration',daemon=True).start()
        self._poll_legacy_project_migration()

    def _poll_legacy_project_migration(self):
        self._legacy_project_migration_poll_id=None
        if getattr(self,'shutting_down',False):
            return
        try:
            outcome=self._legacy_project_migration_results.get_nowait()
        except queue.Empty:
            self._legacy_project_migration_poll_id=self.win.after(25,self._poll_legacy_project_migration)
            return
        if outcome is None:
            self.projects.refresh_registry();self.reload()
        else:
            self.projects.legacy_migration_pending=False
            self.status.set('旧项目迁移失败：%s；原文件未改动。' % outcome)
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

    def _poll_auto_due(self,due_name,delay,poll,*,busy_name=None,on_error,errors):
        """把自动阶段共同的到期、节流和异常处理交给无 Tk 调度器。"""
        return self.automation_scheduler.run_due(
            now=time.monotonic(), due_at=lambda:getattr(self,due_name),
            delay_seconds=delay,
            allowed=lambda:self.root is not None and not (busy_name and getattr(self,busy_name)),
            set_due=lambda value:setattr(self,due_name,value), poll=poll,
            on_error=on_error, handled_exceptions=errors)

    def shot_numbering_hint(self):
        """编号与剧本顺序不一致时返回一句提示。只提示不自动改名：重排会改写项目里的文件名与
        文本引用，属于用户可见的改动，必须由人在 02 初步分镜 点「重排镜头编号」确认后执行。"""
        import shot_numbering
        try:
            # 看的是目录里全部分镜 JSON，而不是只看已采用的：编号错了要在 02 初步分镜 就发现，
            # 不必等采用之后才在下游暴露。
            from storyboard_catalog_service import catalog
            problems=shot_numbering.verify(self.root,[entry['path'] for entry in catalog(self.root,'storyboard')])
        except (OSError,ValueError):return ''
        return '；镜头编号与剧本顺序不一致（'+problems[0]+'），可在 02 初步分镜 点“重排镜头编号”修正' if problems else ''
    def final_missing_assets(self,source):
        """当前分镜引用的资产里还没有图片的编号集合；空集表示可以定稿。"""
        from asset_context import references
        from asset_batch_state_service import ready_asset_ids
        episode=read(source)
        shots=episode.get('shots',[]) if isinstance(episode,dict) else []
        available=ready_asset_ids(self.asset_base())
        return {aid for shot in shots for _,aid in references(shot)}-available
    def busy_production(self):
        """是否有制作批次正在读当前工作稿：定稿会把工作稿移入回收站，必须等它们跑完。

        05/06/07 的批次都会在收尾时按原路径重读一次分镜 JSON；定稿若在这中间把工作稿
        移走，批次就会以「未完成」收场（虽然下一轮会自愈），所以两边互相让路。
        """
        if self.worker or self.auto_final_busy or self.auto_keyframe_busy or self.auto_asset_busy or self.auto_video_busy:return True
        state=getattr(self,'previs_jobs',None)
        if state and state.get('busy'):return True
        return any(getattr(v,'busy',False) for v in self.video_sessions.values())
    def final_holding(self):
        """自动定稿正在执行，或已经就绪却要给别的制作批次让路：下游步骤这一轮必须等。

        定稿一执行就把工作稿移进回收站，抢在它前面按工作稿跑出来的首帧／白模／视频落在
        归档前的目录上，等定稿接管还得重来一遍。让路是有界的：定稿一跑完或这份分镜已经
        不需要定稿，标记就清掉，下游下一轮照常开工。
        """
        return self.auto_final_busy or self.auto_final_blocked
    def kick_unattended(self,source):
        """某个无人值守步骤刚成功完成：让它的下游立刻各赶一轮。

        正在退避（due 比正常节流周期还远，只可能是失败后的 5 分钟退避）的步骤保持不动，
        避免一次成功把别处的失败重试节奏也打乱。
        """
        now=time.monotonic()
        for name in UNATTENDED_NEXT.get(source,()):
            if getattr(self,name+'_due',0)>now+UNATTENDED_BACKOFF_FLOOR:continue
            setattr(self,name+'_due',0)
    def _tick_auto_final(self):
        """处理自动定稿的后台收尾与下一轮轮询。"""
        try:
            ok,value,signature=self.auto_final_queue.get_nowait();self.auto_final_busy=False
            if ok:
                folder,project=value
                # 后台 ``finalize`` 成功不等于这一步真的完成：还要让采用清单、工作集和
                # 当前页面都切到定稿。这里若失败，不能把成功签名留下，否则下一轮会误以为
                # 已收尾而永久跳过；三虎也只能在这段验证完成后播报“已完成”。
                try:
                    applied=self.apply_final(project,folder)
                except (OSError,ValueError,KeyError,TypeError) as exc:
                    self.auto_final_signature=None;self.auto_final_due=time.monotonic()+300
                    self.auto_final_error='自动定稿收尾失败：'+str(exc)
                    self.status.set(self.auto_final_error+'；已保留定稿产物，稍后会重试同步。')
                    self.pet_report('final',self.auto_final_error,ok=False)
                else:
                    self.auto_final_signature=signature;self.auto_final_notice=None;self.auto_final_error=''
                    self.kick_unattended('auto_final')
                    # 收尾会重建第04步页面，所以先做收尾再写状态栏，顺序反了用户就看不到结果。
                    text='已自动生成定稿。'+applied
                    self.status.set(text)
                    if getattr(getattr(self.pet,'auto',None),'active',None)=='final':
                        self.pet_report('final',text)
            else:
                # 失败时清签名并退避 5 分钟：设置或资产修好后会自动再试。
                self.auto_final_signature=None;self.auto_final_due=time.monotonic()+300
                self.status.set(value)
        except queue.Empty:pass
        def failed(exc):
            if self.auto_final_error!=str(exc):
                self.auto_final_error=str(exc);self.status.set('自动定稿暂缓：'+str(exc))
        if self._poll_auto_due('auto_final_due',30,self.poll_auto_final,busy_name='auto_final_busy',
                               on_error=failed,errors=(OSError,ValueError,KeyError,TypeError)):
            self.auto_final_error=''
    def _drain_auto_edit_result(self):
        """只交付已完成的自动粗剪；不在启动期偷偷触发下一轮轮询。"""
        try:
            ticket,ok,value=self.auto_edit_queue.get_nowait()
            if not self.auto_edit_tasks.finish(ticket,succeeded=ok):return False
            self.auto_edit_busy=False
            # 先重建页面再写状态栏：页面重建会重置状态栏，顺序反了用户就看不到结果。
            if ok and getattr(self,'page_index',None)==PAGE['edit']:self.show(PAGE['edit'])
            elif not ok:self.auto_edit_signature=None;self.auto_edit_due=time.monotonic()+300
            if ok:self.kick_unattended('auto_edit')
            self.status.set(value)
            return True
        except queue.Empty:return False
    def _tick_auto_edit(self):
        """处理自动粗剪的后台收尾与下一轮轮询。"""
        self._drain_auto_edit_result()
        self._poll_auto_due('auto_edit_due',15,self.poll_auto_edit,busy_name='auto_edit_busy',
                            on_error=lambda exc:self.status.set('自动粗剪检查失败，稍后重试：'+str(exc)),
                            errors=(OSError,ValueError,KeyError))
    def _tick_auto_keyframe(self):
        """处理自动补首帧的消息、后台收尾与下一轮轮询。"""
        try:
            while True:
                ticket,text=self.auto_keyframe_messages.get_nowait()
                if self.auto_keyframe_tasks.accepts(ticket):self.status.set('自动补首帧：'+text)
        except queue.Empty:pass
        try:
            ticket,ok,value,signature=self.auto_keyframe_queue.get_nowait()
            if not self.auto_keyframe_tasks.finish(ticket,succeeded=ok):return
            self.auto_keyframe_busy=False
            source,pending,_reason,_warn=self.keyframe_batch_state(check_settings=False)
            if ok and source is not None and not pending:
                self.auto_keyframe_signature=signature
                if getattr(getattr(self.pet,'auto',None),'active',None)=='keyframe':
                    self.pet_report('keyframe',value,ok=True)
                self.kick_unattended('auto_keyframe')
            elif not ok:
                self.auto_keyframe_due=time.monotonic()+300
                if getattr(getattr(self.pet,'auto',None),'active',None)=='keyframe':
                    self.pet_report('keyframe',value,ok=False)
            else:
                # 后端正常返回不代表已落盘。保留自动模式，等待下一轮根据真实缺口继续补。
                self.auto_keyframe_signature=None
                self.auto_keyframe_due=time.monotonic()+30
                value+='；仍缺 '+str(len(pending))+' 镜首帧，继续核对并补齐'
            # 先重建首帧那一页再写状态栏：页面重建会重置状态栏。
            if ok and getattr(self,'page_index',None)==PAGE['keyframe']:self.show(PAGE['keyframe'])
            self.status.set(value)
        except queue.Empty:pass
        def failed(exc):
            if self.auto_keyframe_error!=str(exc):
                self.auto_keyframe_error=str(exc);self.status.set('自动补首帧暂缓：'+str(exc))
        self._poll_auto_due('auto_keyframe_due',30,self.poll_auto_keyframe,busy_name='auto_keyframe_busy',
                            on_error=failed,errors=(OSError,ValueError,KeyError))
    def _tick_auto_previs(self):
        """处理自动补白模轮询及工作线程的三虎播报。"""
        def failed(exc):
            if self.auto_previs_error!=str(exc):
                self.auto_previs_error=str(exc);self.status.set('自动补白模暂缓：'+str(exc))
        self._poll_auto_due('auto_previs_due',30,self.poll_auto_previs,on_error=failed,
                            errors=(OSError,ValueError,KeyError))
        # 工作线程只投递消息；Tk 主线程在心跳中交给三虎播报。
        previs_state=getattr(self,'previs_jobs',None)
        previs_news=previs_state.get('news') if isinstance(previs_state,dict) else None
        while previs_news is not None:
            try:ticket,ok,value=previs_news.get_nowait()
            except queue.Empty:break
            if self.auto_previs_tasks.finish(ticket,succeeded=ok):self.pet_report('previs',value,ok=ok)
    def _tick_auto_asset(self):
        """处理自动补资产的消息、续跑台账、后台收尾与轮询。"""
        try:
            while True:
                ticket,text=self.auto_asset_messages.get_nowait()
                if self.auto_asset_tasks.accepts(ticket):self.status.set('自动补资产：'+text)
        except queue.Empty:pass
        try:
            ticket,ok,value,signature=self.auto_asset_queue.get_nowait()
            if not self.auto_asset_tasks.finish(ticket,succeeded=ok):return
            self.auto_asset_busy=False
            if ok:
                self.auto_asset_signature=signature;self.kick_unattended('auto_asset')
            pending=self.asset_pending_ids()
            if pending:
                left=self.note_asset_resume(pending)
                if self.auto_asset_attempt>=ASSET_RETRY_LIMIT:
                    value=('自动补资产连续 '+str(ASSET_RETRY_LIMIT)+' 次没有成果，已停下等您处理：'
                           '请检查 ComfyUI 与生图模型，再点“手动制作资产”。')
                else:
                    self.auto_asset_signature=None
                    self.auto_asset_due=time.monotonic()+(60*self.auto_asset_attempt if left is None else left)
                    value=('自动补资产没做完（'+value+'）；第 '+str(self.auto_asset_attempt)
                           +' 次尝试，稍后自动重试。')
                self.pet_report('assets',value,ok=False)
            else:
                self.auto_asset_attempt=0
                self.clear_asset_resume()
                if not ok:
                    self.auto_asset_due=time.monotonic()+300
                    self.pet_report('assets',value,ok=False)
                elif getattr(getattr(self.pet,'auto',None),'active',None)=='assets':
                    # 队列返回成功只说明批处理结束；缺图清单已经为空才允许推进自动阶段。
                    self.pet_report('assets',value,ok=True)
            # 先重建资产那一页再写状态栏：页面重建会重置状态栏，也会把新导入的资产图登记进清单。
            if ok and getattr(self,'page_index',None)==PAGE['assets']:self.show(PAGE['assets'])
            self.status.set(value)
        except queue.Empty:pass
        def failed(exc):
            if self.auto_asset_error!=str(exc):
                self.auto_asset_error=str(exc);self.status.set('自动补资产暂缓：'+str(exc))
        self._poll_auto_due('auto_asset_due',60,self.poll_auto_asset,busy_name='auto_asset_busy',
                            on_error=failed,errors=(OSError,ValueError,KeyError))
    def _tick_auto_video(self):
        """处理自动补视频的消息、后台收尾与下一轮轮询。"""
        try:
            while True:
                ticket,text=self.auto_video_messages.get_nowait()
                if self.auto_video_tasks.accepts(ticket):self.status.set('自动补视频：'+text)
        except queue.Empty:pass
        try:
            ticket,ok,value,signature=self.auto_video_queue.get_nowait()
            if not self.auto_video_tasks.finish(ticket,succeeded=ok):return
            self.auto_video_busy=False
            if ok:self.auto_video_signature=signature;self.kick_unattended('auto_video')
            else:self.auto_video_due=time.monotonic()+300
            # 仍在生成的镜头每轮给出同一句话，不重复刷状态栏。
            if self.auto_video_last!=value:
                self.auto_video_last=value
                if ok and getattr(self,'page_index',None)==PAGE['video']:self.show(PAGE['video'])
                self.status.set(value)
        except queue.Empty:pass
        def failed(exc):
            if self.auto_video_error!=str(exc):
                self.auto_video_error=str(exc);self.status.set('自动补视频暂缓：'+str(exc))
        self._poll_auto_due('auto_video_due',60,self.poll_auto_video,busy_name='auto_video_busy',
                            on_error=failed,errors=(OSError,ValueError,KeyError))
    def _drain_auto_handoff_result(self):
        """只交付已完成的自动交接包；不在启动期偷偷触发下一轮轮询。"""
        try:
            ticket,ok,value,signature=self.auto_handoff_queue.get_nowait()
            if not self.auto_handoff_tasks.finish(ticket,succeeded=ok):return False
            self.auto_handoff_busy=False
            # 失败时清掉指纹并推迟重试：否则下一轮会被「签名没变」直接跳过，永远不再重试。
            if ok:self.auto_handoff_signature=signature
            else:self.auto_handoff_signature=None;self.auto_handoff_due=time.monotonic()+300
            # 先重建页面再写状态栏：页面重建会重置状态栏，顺序反了用户就看不到结果。
            if ok and getattr(self,'page_index',None)==PAGE['edit']:self.show(PAGE['edit'])
            self.status.set(value)
            return True
        except queue.Empty:return False
    def _tick_auto_handoff(self):
        """处理自动交接包的后台收尾与下一轮轮询。"""
        self._drain_auto_handoff_result()
        def failed(exc):
            if self.auto_handoff_error!=str(exc):
                self.auto_handoff_error=str(exc);self.status.set('自动整理交接包暂缓：'+str(exc))
        self._poll_auto_due('auto_handoff_due',60,self.poll_auto_handoff,busy_name='auto_handoff_busy',
                            on_error=failed,errors=(OSError,ValueError,KeyError))
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
            if ticket!=self._async_ticket or not self.background_tasks.finish(ticket, succeeded=ok):return
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
        except queue.Empty:pass
    def _project_result_data(self,result):
        """项目登记写服务的 L3 结果只在桌面编排层解包。"""
        from stage_execution_service import unwrap_project_result
        return unwrap_project_result(result)
    def _tick_pre_automation(self):
        """在自动阶段调度前回收 Tk 任务并轮询流程进程。"""
        drain_tk_gc()
        try:self.poll_flow_processes()
        except (OSError,ValueError,KeyError):pass
    def _tick_pet_events(self):
        """在本轮自动调度完成后聚合三虎事件，不创建额外线程。"""
        pet_ui.pump(self)
    def _tick_cloud_monitor(self):
        """处理云端任务监控结果与下一轮轮询。"""
        try:
            ticket,ok,value=self.cloud_monitor_result.get_nowait()
            if not self.cloud_monitor_tasks.finish(ticket,succeeded=ok):return
            self.cloud_monitor_busy=False
            self.cloud_monitor_due=time.monotonic()+(5 if ok else 30)
            if not ok and self.root is not None:self.status.set('线上任务查询稍后重试：'+value)
        except queue.Empty:pass
        if self.root is None:
            if self.cloud_monitor_tasks.cancel():self.cloud_monitor_busy=False
            return
        if not self.cloud_monitor_busy and time.monotonic()>=self.cloud_monitor_due:
            try:self.poll_unwatched_cloud()
            except (OSError,ValueError):self.cloud_monitor_due=time.monotonic()+30
    def _tick_auto_adopt(self):
        """调度自动采用分镜的短周期检查。"""
        self._poll_auto_due('auto_adopt_due',5,self.poll_auto_adopt,
                            on_error=lambda exc:self.status.set('自动采用分镜检查失败，稍后重试：'+str(exc)),
                            errors=(OSError,ValueError,KeyError))
    def _tick_auto_gates(self):
        """调度半自动/全自动模式下的待办与裁决处理。"""
        def failed(exc):
            if self.gate_auto_error!=str(exc):
                self.gate_auto_error=str(exc);self.status.set('自动处理待办暂缓（将在约 20 秒后重试）：'+str(exc))
        self._poll_auto_due('gate_auto_due',20,self.auto_decide_gates,on_error=failed,
                            errors=(OSError,ValueError,KeyError,TypeError))
    def poll_auto_final(self):
        """无人值守：当前分镜还是工作稿、且引用资产都已导入时，自动生成定稿。

        定稿会把工作稿移入回收站（回收站留有恢复位置，可恢复），所以这条路径必须由用户在
        第04步显式勾选才走；同一份工作稿只生成一次，资产没齐时在状态栏和 04 页那条提示条
        上说清缺什么（提示条上还有一颗「立即重试」，见 auto_final_state／retry_auto_final），
        失败退避 5 分钟后重试，定稿接管后当前分镜变成定稿目录，轮询自然停下。
        """
        import project_settings
        if self.root is None or self.studio is None or not self.pet.should_auto_run('final'):
            self.auto_final_signature=None;self.auto_final_notice=None;self.auto_final_blocked=False;return
        source=self.auto_final_target()
        if source is None:
            self.auto_final_blocked=False;return
        self.auto_final_notice=None
        from agent.core import file_hash
        signature=(str(source),file_hash(source))
        from final_service import automatic_finalize_decision
        decision=automatic_finalize_decision(signature,self.auto_final_signature,self.busy_production())
        if decision['action']=='skip':self.auto_final_blocked=False;return
        # 定稿本来这轮就该动手，只是还有别的制作批次在读这份工作稿：把「定稿在等」记下来，
        # 下游（首帧／白模／视频）据此这轮也让路，别抢在定稿前面按工作稿开工。
        if decision['action']=='wait':self.auto_final_blocked=True;return
        self.auto_final_blocked=False
        self.auto_final_busy=True;self.auto_final_signature=decision['signature']
        project=self.root;episode=self.asset_base()
        self.status.set('无人值守自动定稿：正在同步资产并生成定稿…')
        def worker():
            from storyboard_final_controller import finalize_stage_storyboard
            try:self.auto_final_queue.put((True,(finalize_stage_storyboard(project,episode,source),project),signature))
            except Exception as exc:self.auto_final_queue.put((False,'自动定稿未完成：'+str(exc),signature))
        threading.Thread(target=worker,daemon=True).start()
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
        """当前分镜还是工作稿、且引用的资产都已导入时，提示可以去第04步生成定稿。

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
        return '；当前分镜引用的资产都已导入，可在第04步「分镜定稿」生成定稿（定稿接管后续流程，工作稿移入回收站）'
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
    def poll_auto_adopt(self):
        """无人值守：项目开着「自动采用新文件」时，定时把新分镜推进后续流程。

        第 62 期任务 7：打开项目后的第一拍先做一次「启动对账」（reconcile_storyboards），
        把强制关闭时没来得及同步的工作集补上；这一拍不看节流，也不受别的阶段在忙影响。
        """
        import project_settings
        if self.root is None:
            self.auto_adopt_signature=None;self.auto_adopt_pending=False;return
        if getattr(self,'auto_adopt_startup',False):
            self.auto_adopt_startup=False
            self.reconcile_storyboards()
        if not self.pet.should_auto_run('auto_adopt'):
            self.auto_adopt_signature=None;self.auto_adopt_pending=False;return
        from storyboard_selection import tree_signature
        from stage_execution_service import poll_asset_storyboard_adoption
        # 目录里没有新增或改写的分镜时不必反复解析全部 JSON；只有等写入完成的文件才继续轮询。
        signature=tree_signature(self.root)
        from storyboard_adoption_service import automatic_poll_decision
        decision=automatic_poll_decision(signature,self.auto_adopt_signature,self.auto_adopt_pending,self.auto_final_busy)
        if decision['action'] in ('wait','skip'):return
        self.auto_adopt_signature=decision['signature']
        result=poll_asset_storyboard_adoption(self.root)
        self.auto_adopt_pending=bool(result['waiting'])
        for path in list(self.auto_adopt_errors):
            if path not in result['failed']:self.auto_adopt_errors.pop(path,None)
        for path,reason in result['failed'].items():
            if self.auto_adopt_errors.get(path)==reason:continue
            self.auto_adopt_errors[path]=reason
            self.status.set('自动采用分镜暂缓：'+Path(path).name+'：'+reason)
        if result['adopted']:
            self.kick_unattended('auto_adopt')
            # 采用后立刻让工作集跟上：否则 08 剪辑、自动粗剪和交付还会按旧分镜执行。
            switched=self.sync_working_episode() if self.studio is not None else None
            aligned=self.align_studio()
            # 先重建页面再写状态：页面重建会重置状态栏，顺序反了用户就看不到自动采用的结果。
            if getattr(self,'page_index',None) in (PAGE['storyboard'],PAGE['final']):self.show(self.page_index)
            note='；工作集已切到最新采用的分镜' if switched else ('；后续流程按当前选择的分镜执行' if aligned else '；工作集保持不变（项目已有视频任务或在跑任务）')
            text='已自动采用 '+str(len(result['adopted']))+' 份新分镜：'+'、'.join(Path(p).name for p in result['adopted'])+note
            self.status.set(text+self.final_storyboard_hint()+self.shot_numbering_hint())
            # 自动采用是初步分镜真正落盘、同步工作集后的收尾信号。此前只同步了
            # 工作集却没有通知三虎，导致自动链一直停在 storyboard。只在该阶段
            # 仍处于 active 时上报，手动采用及后续轮询不会重复推进下一阶段。
            auto=getattr(getattr(self,'pet',None),'auto',None)
            if getattr(auto,'active',None)=='storyboard':
                self.pet_report('storyboard',text)
    def edit_ready(self):
        """整集「已验收」就绪判定：返回 (验收状态签名, 成片指纹)。

        验收状态没变就不重新校验整集成片（否则每轮把所有成片重读一遍）；签名与指纹放在一处算，
        自动粗剪和自动整理交接包共用同一次校验，避免同一批验收结果被哈希两遍。
        """
        studio=self.studio
        st=studio.state()
        # 签名必须带上分镜文件：两份分镜的镜头编号与版本完全相同（例如按同一模板出的两集）时，
        # 只比镜头状态会让第二集沿用第一集的签名，从而永远跳过拼接与整理。
        signature=(str(studio.episode_path),tuple((shot['id'],tuple((v.get('version'),v.get('review'),v.get('qc_pass'),v.get('state')) for v in st['shots'].get(shot['id']) or [])) for shot in studio.episode['shots']))
        if signature!=getattr(self,'edit_ready_signature',None):
            self.edit_ready_signature=signature
            self.edit_ready_digest,_waiting=studio.auto_edit_ready()
        return signature,getattr(self,'edit_ready_digest',None)
    def poll_auto_edit(self):
        """无人值守：本集全部镜头验收通过后自动粗剪一次。

        成片指纹记在 editing／自动粗剪.json：同一批验收结果只拼接一次，镜头重做并重新验收后才会再拼一版。
        """
        import project_settings
        if self.root is None or self.studio is None or not self.pet.should_auto_run('edit'):
            self.auto_edit_signature=None;return
        # 自动粗剪必须按当前选择的分镜：工作集没跟上时先对齐，正在跑任务、正在定稿或新分镜不合规就等下一轮。
        if self.auto_final_busy or not self.align_studio():return
        studio=self.studio
        signature,digest=self.edit_ready()
        from project_stages import editing
        marker=editing(self.root)/'自动粗剪.json'
        done=read(marker) if marker.is_file() else {}
        from edit_service import automatic_assemble_decision
        decision=automatic_assemble_decision(signature,digest,self.auto_edit_signature,done)
        if decision['action']=='skip':return
        self.auto_edit_signature=decision['signature']
        if decision['action'] in ('wait','complete'):return
        self.auto_edit_busy=True;self._auto_edit_ticket+=1
        ticket=self.auto_edit_tasks.submit(self._auto_edit_ticket)
        self.status.set('全部镜头已验收，正在自动粗剪整集…')
        def worker():
            # 只在工作线程里做文件与队列操作，不碰 Tk。
            try:
                path=studio.assemble()
                from stage_execution_service import save_automatic_assemble_marker
                save_automatic_assemble_marker(self.root,digest,path,time.time())
                self.auto_edit_queue.put((ticket,True,'自动粗剪完成：'+str(path)))
            except Exception as exc:self.auto_edit_queue.put((ticket,False,'自动粗剪未完成，稍后重试：'+str(exc)))
        threading.Thread(target=worker,daemon=True).start()
        self._schedule_auto_edit_result_poll()
    def poll_auto_keyframe(self):
        """无人值守：按「首帧制作」窗口当前的模型补齐当前分镜缺首帧的镜头（不弹窗）。

        同一批「缺首帧镜头」只跑一次，避免批次把缺参考图的镜头跳过后反复空跑；
        新增分镜、补齐资产或换了当前分镜都会让清单变化，从而自动再跑一轮。
        这里只管「什么时候该跑」，派发本身与宠物「一键执行」共用 start_keyframe_batch。
        """
        if self.root is None or self.studio is None or not self.pet.should_auto_run('keyframe'):
            self.auto_keyframe_signature=None
            if self.auto_keyframe_tasks.cancel():self.auto_keyframe_busy=False
            return
        # 先判重再派发：批次跑着的时候这一批的指纹已经记下，不会在生成过程中重复下单。
        sent,message,signature=self.start_keyframe_batch('无人值守自动补首帧',unless_signature=self.auto_keyframe_signature)
        from keyframe_batch import automatic_poll_decision
        decision=automatic_poll_decision(sent,message,signature,self.auto_keyframe_signature)
        if decision['action'] in ('quiet','skip'):return
        # 这一批补不了（缺参考资产／缺提示词／资产清单还没同步）：记住它，别每 30 秒重复同一句话；
        # 资产或提示词补齐后签名变了，会自动继续。
        self.auto_keyframe_signature=decision['signature']
        notice=(str(decision['signature']),decision['message'])
        if notice!=self.auto_keyframe_blocked:
            self.auto_keyframe_blocked=notice
            self.status.set('无人值守自动补首帧暂缓：'+decision['message']+'；补齐后会自动继续')
    def keyframe_signature(self,source,pending):
        """「这一批缺首帧的镜头」的指纹：带上每镜还缺几张参考图。

        资产补齐后清单会变，于是自动补首帧能再跑一轮（否则参考图缺失的镜头跑过一遍就再也不会重试）；
        无人值守与「一键执行」共用同一份指纹，两条路派发出来的批次不会互相再触发一次。
        """
        from asset_batch_state_service import ready_asset_ids
        from asset_context import references
        from keyframe_batch import batch_signature
        return batch_signature(source,pending,ready_asset_ids(self.asset_base()),references)
    def keyframe_settings(self):
        """「首帧制作」窗口保存的本地 ComfyUI 设置里还缺哪几项；空列表表示已就绪。"""
        from keyframe_comfy import missing_settings, saved_settings
        values={key:value for key,value in saved_settings().items() if key not in ('shot_ids','shot_id')}
        return missing_settings(values)
    def keyframe_batch_state(self,check_settings=False):
        """「现在能不能补首帧」的唯一判据：返回 (source, pending, reason, warn)。

        reason 为空串＝可以立刻派发；否则是不能派发的原因。warn=True 表示这个原因值得写进状态栏
        并记住这一批（本地引擎没配好、整批镜头缺参考资产），warn=False 只是这一轮先让路
        （有别的批次在跑、定稿在等），安静等下一轮就行。
        check_settings 只在「用户按了按钮」时打开：无人值守那条路由 auto_batch 自己报设置缺失，
        提前检查会让自检依赖本机有没有配过 ComfyUI。
        """
        if self.root is None or self.studio is None:
            return None,[],'',True
        try:source=self.current_frame_json()
        except ValueError:
            return None,[],'',True
        if source is None or not Path(source).is_file():
            return None,[],'',True
        from keyframe_comfy import pending_shots
        pending=pending_shots(read(source).get('shots'),media_root(source))
        if not pending:
            return source,[],'',True
        if self.auto_keyframe_busy or self.worker or self.final_holding():
            return source,pending,'已有制作任务在跑，等这一轮结束再补',False
        if check_settings:
            missing=self.keyframe_settings()
            if missing:
                return source,pending,'本地 ComfyUI 还没配好（缺 '+'、'.join(missing)+'），可到「首帧制作」窗口保存设置',True
        # 整批镜头都会被引擎逐镜跳过时（缺参考资产、缺提示词），批次只会白跑：它要先连上、
        # 必要时还要启动 ComfyUI，一次白等最长两分钟，最后一张也出不来。这种批次不派发，
        # 用引擎自己的逐镜检查给出原因；资产或提示词补齐后签名变化，会自动继续。
        try:blocked=self.batch_blockers(source,pending)
        except (OSError,ValueError) as exc:
            return source,pending,str(exc),True
        if len(blocked)==len(pending):
            return source,pending,str(len(pending))+' 镜都无法生成：'+skip_summary(blocked),True
        return source,pending,'',True
    def start_keyframe_batch(self,label,check_settings=False,unless_signature=None):
        """补首帧的唯一派发实现：无人值守的定时轮询与宠物「一键执行」都走这里。

        返回 (是否派发, 一句中文结果, 清单指纹)；没有缺口时是 False／''／None——
        「没有缺口」与「有缺口但补不了」必须分开，前者不该打扰任何人。
        unless_signature 是「这一批已经处理过」的指纹：命中就只回指纹、不派发，让无人值守
        能先判重再动手（批次还在跑的时候，同一批镜头不会再被重复下单）。用户按下的按钮不传它。
        """
        source,pending,reason,warn=self.keyframe_batch_state(check_settings=check_settings)
        if source is None or not pending:return False,'',None
        signature=self.keyframe_signature(source,pending)
        if signature==unless_signature:return False,'',signature
        if reason:return False,'首帧未补：'+reason,signature if warn else None
        self.auto_keyframe_blocked=None
        self.auto_keyframe_busy=True
        self._auto_keyframe_ticket+=1
        ticket=self.auto_keyframe_tasks.submit(self._auto_keyframe_ticket)
        self.status.set(label+'：准备用本地 ComfyUI 按分镜顺序补 '+str(len(pending))+' 镜首帧…')
        def worker():
            from keyframe_comfy import auto_batch
            try:self.auto_keyframe_queue.put((ticket,True,auto_batch(source,lambda text:self.auto_keyframe_log(ticket,text)),signature))
            except Exception as exc:self.auto_keyframe_queue.put((ticket,False,label+'未完成：'+str(exc),signature))
        threading.Thread(target=worker,daemon=True).start()
        return True,'已按分镜顺序派发 '+str(len(pending))+' 镜首帧（本地 ComfyUI 免费后端，未运行会自动启动）',signature
    def pet_frame_batch(self, trigger='manual'):
        """宠物「一键执行」的首帧缺口：本地 ComfyUI 就绪时按分镜顺序补一批缺首帧的镜头。

        不读「无人值守自动补首帧」开关——用户按下的按钮就是他的显式意思；也不会去碰付费的
        Seedream 通道，花钱的一律等人自己按。派发与无人值守共用同一份实现（见 start_keyframe_batch）。
        返回一句中文结果；手动入口在没项目、没缺口时仍返回空串。自动入口已经把
        keyframe 标为 active，必须把同样的前置条件转为明确阶段终态，不能静默卡住。
        """
        sent,message,_signature=self.start_keyframe_batch('一键执行',check_settings=True)
        if trigger != 'auto' or sent:
            return message
        return self._finish_unsent_auto_keyframe(message)
    def _finish_unsent_auto_keyframe(self,message):
        """把首帧自动入口未派发的结果转为明确的三虎阶段终态。"""
        pet=getattr(self,'pet',None)
        if message:
            error=message
            if pet is not None:
                pet._emit('stage.failed',stage='keyframe',error=error)
            return error
        source,pending,_reason,_warn=self.keyframe_batch_state(check_settings=True)
        if source is not None and not pending:
            text='首帧已齐全，无需制作'
            if pet is not None:
                pet._complete_if_verified('keyframe', text)
            return text
        error='未找到可用分镜，无法制作首帧'
        if pet is not None:
            pet._emit('stage.failed',stage='keyframe',error=error)
        return error
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
    def pet_script_structure_batch(self, trigger='auto', refresh_page=False):
        """三虎整理剧本：手动与自动入口复用同一条 Writer/Editor + SKILL 异步链。"""
        pet=getattr(self,'pet',None)
        if self.root is None:
            error='当前没有打开项目，无法制作结构剧本'
            if trigger == 'auto' and pet is not None:
                pet._emit('stage.failed',stage='script_structure',error=error)
                return error
            return ''
        if self.worker:
            # 自动链已将本阶段标为 active。后台占用不是业务失败，排队到当前
            # async_ 收尾后通过 pet_start/L3 重新派发；标记是布尔值，连续心跳
            # 不会堆积多次任务。手动入口仍保持原有“暂不能制作”的提示。
            if trigger == 'auto':
                self._auto_structure_retry=True
                return '当前后台任务完成后将自动制作结构剧本'
            return ''
        import script_contract
        source=script_contract.resolve_script_source(self.root)
        if source is None:
            # 自动链已经把 script_structure 标成 active；这里若只静默返回空串，
            # 它就等不到收场事件并永久停在这一步。手动入口在调用前已有提示，
            # 自动入口必须把同一前置条件转成明确的阶段失败，交给三虎阻塞与展示。
            error='未找到剧本准备阶段的剧本，无法制作结构剧本'
            if trigger == 'auto' and pet is not None:
                pet._emit('stage.failed',stage='script_structure',error=error)
            return error
        if pet is None:return ''
        pet._emit('stage.executing',stage='script_structure',trigger=trigger)
        def work():
            try:return ui_plugin_registry.module('stage_exec').run(self,'script_structure',trigger=trigger)
            except Exception as exc:return {'ok':False,'text':str(exc),'errors':[str(exc)]}
        def received(result):
            self._receive_structure_stage_result(pet,result,refresh_page=refresh_page)
        self.async_(work,received,label='三虎正在整理结构化剧本…')
        return ('已自动开始' if trigger == 'auto' else '已开始') + '「剧本结构」：正在整理原稿'
    def _receive_structure_stage_result(self,pet,result,refresh_page=False):
        """处理结构剧本后台任务结果，并保持三虎阶段事件与页面状态一致。"""
        if bool((result or {}).get('ok')):
            # 阶段完成会立刻通知三虎继续下游；必须先把正稿写入初步分镜的选择，
            # 否则全自动的 pet_storyboard_batch 会看到空输入而不派发任务。
            try:
                from storyboard_selection import sync_structured_script
                from script_contract import structured_script_path
                location = structured_script_path(self.root)
                selected = sync_structured_script(self.root)
                if location.resolve() not in {Path(path).resolve() for path in selected}:
                    raise ValueError('结构化剧本未同步到初步分镜输入')
            except (OSError, ValueError, TypeError, AttributeError, KeyError) as exc:
                error = '结构化剧本已生成，但同步初步分镜失败：' + str(exc)
                pet._emit('stage.failed',stage='script_structure',error=error)
                self.status.set('三虎整理剧本失败：'+error)
                return
            text='结构化剧本已保存：'+location.relative_to(self.root).as_posix()
            self.pet_report('script_structure',text)
            self.status.set('三虎已完成'+text)
            # 手动制作和三虎自动制作共用回调。过去仅手动入口传 refresh_page，
            # 因而用户正停留在“剧本结构”页时，后台已经写入的正稿不会重建目录栏，
            # 看起来像“已有文件没有刷新”。当前页就是本阶段时同样立即重建。
            if refresh_page or getattr(self, 'page_index', None) == PAGE['script_structure']:
                self.show(PAGE['script_structure'])
            return
        error=str((result or {}).get('text') or '; '.join((result or {}).get('errors') or []) or '结构化剧本未生成')
        pet._emit('stage.failed',stage='script_structure',error=error)
        self.status.set('三虎整理剧本失败：'+error)
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
    def auto_keyframe_log(self,ticket,text):
        # 工作线程回调：只入队，由主循环写状态栏，线程里不碰 Tk。
        self.auto_keyframe_messages.put((ticket,str(text)))
    def poll_auto_previs(self):
        """无人值守：复杂动作镜头交给当前调用的制作引擎自动出白模；中等动作只在状态栏提示，不代办。

        同一批「复杂且未出白模」的镜头只派一次，避免无人值守时反复空转或反复消耗引擎额度；
        派发失败（没装 Blender、引擎命令行未配置）时清掉签名并退避 5 分钟，设置修好就能自动重试。
        """
        if self.root is None or self.studio is None or not self.pet.should_auto_run('previs'):
            self.auto_previs_signature=None
            if self.auto_previs_tasks.cancel() and getattr(self,'previs_jobs',{}):self.previs_jobs['busy']=False
            return
        state=getattr(self,'previs_jobs',None)
        if state is None:state={'busy':False,'status':{},'selected':set()};self.previs_jobs=state
        if state.get('busy') or self.worker or self.final_holding():return
        try:source=self.current_frame_json()
        except ValueError:return
        if source is None:return
        episode=read(source)
        shots=episode.get('shots',[]) if isinstance(episode,dict) else []
        from previs_routing import automatic_candidates, automatic_notice, automatic_signature, automatic_engine
        try:
            frame_pending = None
            if self.pet.should_auto_run('keyframe'):
                from keyframe_comfy import pending_shots
                frame_pending = lambda rows: [shot['id'] for shot in pending_shots(rows, media_root(source))]
            candidates=automatic_candidates(self.root,source,shots,bool(frame_pending),frame_pending)
        except ValueError:return
        pending=candidates['pending'];waiting=candidates['waiting'];medium=candidates['medium']
        # 顺序是「首帧在前、白模在后」：首帧阶段也在无人值守（05 开关打开）时，等这一镜的首帧落盘再建白模，
        # 否则白模只能按「没有首帧」的保守草排做，等首帧出来还得重做一遍。首帧由用户手动管的项目不受影响。
        notice,notes=automatic_notice(source,pending,medium,waiting)
        if not pending:
            # 这一批已经没有要自动制作的了：清掉派发签名，日后把某个镜头的白模删掉要重做，还能再派一次。
            self.auto_previs_signature=None
            if notes and notice!=self.auto_previs_notice:
                self.auto_previs_notice=notice
                self.status.set('无人值守自动补白模：'+'；'.join(notes)+'；其余镜头无需白模')
            return
        # 派发只看「复杂且未就绪」的清单：中等动作的数量变化不能让同一批复杂镜头被重复派发。
        signature=automatic_signature(source,pending)
        if signature==self.auto_previs_signature:return
        self.auto_previs_signature=signature;self.auto_previs_notice=notice
        try:
            from workflow_settings import current,ENGINES
            engine=automatic_engine(self.root,current,ENGINES)
        except Exception as exc:
            self.auto_previs_signature=None;self.auto_previs_due=time.monotonic()+300
            self.auto_previs_error='白模调用设置无法读取：'+str(exc);self.status.set('无人值守自动补白模暂缓：'+str(exc));return
        self.status.set('无人值守自动补白模：使用 '+engine+' 制作 '+str(len(pending))+' 镜复杂动作…')
        try:
            from previs_automation import start
            self._auto_previs_ticket+=1
            ticket=self.auto_previs_tasks.submit(self._auto_previs_ticket)
            start(self.root,source,pending,state,ticket=ticket,is_current=self.auto_previs_tasks.accepts)
        except Exception as exc:
            self.auto_previs_tasks.cancel()
            self.auto_previs_signature=None;self.auto_previs_due=time.monotonic()+300
            if self.auto_previs_error!=str(exc):
                self.auto_previs_error=str(exc);self.status.set('无人值守自动补白模暂缓：'+str(exc))
            return
        self.auto_previs_error=''
    def poll_auto_asset(self):
        """无人值守：按「资产图片制作」窗口当前的生图模型补齐缺图的资产（不弹窗）。

        同一批「缺图资产＋当前设置」只跑一次；导入图片、补清单或改设置都会让清单变化，从而自动再跑一轮。
        """
        if self.root is None or self.studio is None or not self.pet.should_auto_run('assets'):
            self.auto_asset_signature=None;self.auto_asset_attempt=0
            if self.auto_asset_tasks.cancel():self.auto_asset_busy=False
            return
        if self.auto_asset_busy or self.worker or self.auto_final_busy:return
        from asset_batch_service import current_model, unattended_signature, unattended_retry_decision
        from stage_execution_service import plan_unattended_assets as auto_plan
        from asset_context import scope_sources
        project=self.root;base=self.asset_base();sources=scope_sources(project,'adopted')
        missing,skipped,saved=auto_plan(project,base,sources,'adopted')
        if not missing:
            self.clear_asset_resume()       # 缺图补齐了：台账整份删掉，不留下「历史账」
            return
        signature=unattended_signature(missing,saved)
        # 第 6 轮：次数从项目台账里读回来——重开助手接着上一次的数继续退避，到顶的那一批
        # 直接停下等人（原来内存一清就从第 1 次重来，同一批资产每次开机都白跑一轮）。
        self.auto_asset_attempt=asset_resume.attempts(project,[aid for aid,_ in missing])
        decision=unattended_retry_decision(signature,self.auto_asset_signature,self.auto_asset_attempt,ASSET_RETRY_LIMIT)
        if decision['action']=='skip':return
        if decision['action']=='stop':
            self.auto_asset_signature=decision['signature']
            self.status.set('自动补资产连续 '+str(ASSET_RETRY_LIMIT)+' 次没有成果，已停下等您处理：'
                            '请检查 ComfyUI 与生图模型，再点“手动制作资产”。')
            return
        # 第 64 期任务 2：重试计数只在「清单真的变了」时清零——原来每轮派发前都清零，
        # ASSET_RETRY_LIMIT 永远到不了，同一批没成果的清单会被无限重排。
        if signature!=self.auto_asset_tried:
            self.auto_asset_tried=signature
            self.auto_asset_busy=True
        self._auto_asset_ticket+=1
        ticket=self.auto_asset_tasks.submit(self._auto_asset_ticket)
        self.status.set('无人值守自动补资产（'+current_model(project)+'）：准备处理 '+str(len(missing))+' 项…')
        # 第 64 期任务 2：提交结果不确定的那几项（连接中断、ComfyUI 里也找不到任务编号）按设计
        # 不自动重提，以免重复扣费——但必须说给用户听，否则这一项会永远卡在「待导入」，
        # 看起来就是「三虎没有自动继续完成制图任务」。
        try:
            from asset_batch_state_service import uncertain_assets
            blocked=[aid for aid in uncertain_assets(project) if aid in {a for a,_ in missing}]
        except Exception:
            blocked=[]
        if blocked:
            self.status.set('自动补资产：'+'、'.join(blocked)+' 上次提交结果无法确认，已跳过；'
                            '请在 ComfyUI 或云端核实后点「手动制作资产」重新生成。')
        def worker():
            from asset_auto_batch_service import auto_batch
            try:self.auto_asset_queue.put((ticket,True,auto_batch(project,base,sources,'adopted',lambda text:self.auto_asset_log(ticket,text)),signature))
            except Exception as exc:self.auto_asset_queue.put((ticket,False,'自动补资产未完成：'+str(exc),signature))
        threading.Thread(target=worker,daemon=True).start()
    def asset_pending_ids(self):
        """没人值守这一路还缺图的资产编号（第 6 轮：收尾与台账都按编号记账）。

        原来只问一句「还有没有」（asset_work_left），于是每个编号试了几次、下次该什么时候
        接着试，全在内存里——窗口一关就没了。
        """
        from stage_execution_service import plan_unattended_assets as auto_plan
        from asset_context import scope_sources
        try:
            missing,_skipped,_saved=auto_plan(self.root,self.asset_base(),scope_sources(self.root,'adopted'),'adopted')
        except (OSError,ValueError,KeyError,TypeError):
            return []
        return [aid for aid,_ in missing]
    def asset_work_left(self):
        """无人值守资产清单里还有没有缺图项（第 62 期任务 10：一轮跑完后的收尾判定）。"""
        return bool(self.asset_pending_ids())
    def note_asset_resume(self,ids):
        """这一轮又没做出图：把「第几次、下次从什么时候接着退避」记进项目台账（第 6 轮）。

        次数从台账里读回来（不是内存里自增的那个），`auto_asset_attempt` 因此与落盘的一致：
        重启后 poll_auto_asset 读同一份台账接着往后数、到顶就停下等人。台账写不动时退回内存里
        的计数（宁可多试几次，也不把这条路弄丢）。返回「离该重试还差几秒」，没有等待中的项返回 None。
        """
        from stage_execution_service import note_asset_resume_round
        fallback=self.auto_asset_attempt+1
        try:
            note_asset_resume_round(self.root,ids,limit=ASSET_RETRY_LIMIT)
            counted=asset_resume.attempts(self.root,ids)
            left=asset_resume.delay(self.root)
        except (OSError,ValueError,TypeError,KeyError):
            counted=0;left=None
        self.auto_asset_attempt=max(fallback,counted)
        return left
    def clear_asset_resume(self):
        """缺图补齐了、或用户亲手关掉这一档：把跨重启台账整份删掉（第 6 轮）。"""
        try:
            result=asset_resume.clear(self.root)
            if not result.ok:
                self.status.set('自动补资产续跑记录未清除：'+result.reason)
        except (OSError, ValueError, TypeError) as exc:
            # 续跑台账仍会在下次启动出现；不能把“已经清掉”的假象留给用户。
            self.status.set('自动补资产续跑记录未清除：%s；请稍后重试。' % exc)
    def restore_asset_resume(self):
        """打开项目时把跨重启续跑台账读回来（第 6 轮）。

        与 `prune_asset_leftovers` 同一条规矩：台账读不出来一律当没记过，绝不因此把
        「打开项目」拦下来；读得出来就接着上次的次数与退避时刻继续（台账记的是挂钟时刻，
        换算回 monotonic 后才好排下一次）。
        """
        try:
            self.auto_asset_attempt=asset_resume.attempts(self.root)
            left=asset_resume.delay(self.root)
        except (OSError,ValueError,TypeError,KeyError) as exc:
            self.auto_asset_attempt=0;left=None
            # 续跑失败可以降级为不续跑，但不能让用户误以为没有待续跑的资产任务。
            self.status.set('自动补资产续跑记录未恢复：%s；请稍后重试。' % exc)
        if left is not None:
            self.auto_asset_due=time.monotonic()+left
    def auto_asset_log(self,ticket,text):
        # 工作线程回调：只入队，由主循环写状态栏，线程里不碰 Tk。
        self.auto_asset_messages.put((ticket,str(text)))
    def poll_auto_video(self):
        """无人值守：本地 ComfyUI 自动补齐当前分镜缺视频的镜头（免费后端，不弹窗）。

        已提交的镜头只查询取回，不重复提交；同一批「待提交镜头」只排一次，仍在生成的镜头每轮查询。
        """
        import project_settings
        if self.root is None or self.studio is None or not self.pet.should_auto_run('video'):
            self.auto_video_signature=None
            if self.auto_video_tasks.cancel():self.auto_video_busy=False
            return
        if self.auto_video_busy or self.worker or self.final_holding():return
        if not self.align_studio():return
        from local_video import LocalStudio,auto_plan,auto_poll_decision
        if not isinstance(self.studio,LocalStudio):return
        try:source=self.current_frame_json()
        except ValueError:return
        if source is None:return
        submit,poll,skipped=auto_plan(self.root,source,self.studio)
        decision=auto_poll_decision(source,submit,poll,skipped,self.auto_video_signature)
        if decision['action'] in ('notice','idle'):
            # 全部镜头都被跳过时以前什么都不写：无人值守看起来就是卡死。这里把第一条原因写一次，
            # 清单变化（例如首帧补齐）后签名不同，会再报一次。
            if decision['action']=='notice' and decision['notice']!=self.auto_video_notice:
                self.auto_video_notice=decision['notice']
                self.status.set(decision['message'])
            return
        self.auto_video_notice=None
        if decision['action']=='skip':return
        signature=decision['signature']
        self.auto_video_busy=True;self._auto_video_ticket+=1
        ticket=self.auto_video_tasks.submit(self._auto_video_ticket)
        self.status.set('无人值守自动补视频：准备提交 '+str(len(submit))+' 镜、查询 '+str(len(poll))+' 镜…')
        studio=self.studio
        def worker():
            from local_video import auto_batch
            try:self.auto_video_queue.put((ticket,True,auto_batch(self.root,source,lambda text:self.auto_video_log(ticket,text),studio=studio),signature))
            except Exception as exc:self.auto_video_queue.put((ticket,False,'自动补视频未完成：'+str(exc),signature))
        threading.Thread(target=worker,daemon=True).start()
    def auto_video_log(self,ticket,text):
        # 工作线程回调：只入队，由主循环写状态栏，线程里不碰 Tk。
        self.auto_video_messages.put((ticket,str(text)))
    def poll_auto_handoff(self):
        """无人值守：本集全部镜头验收通过后自动整理剪映素材交接包（只复制本地已下载成片，不调用云端、不产生费用）。

        交接包指纹记在 editing／自动交接.json：同一批验收结果只整理一次，镜头重做并重新验收后才会再出一版；
        自动模式固定复用 editing／自动交接包 这一个目录，不会像手动整理那样每次多出一个目录。
        """
        import project_settings
        if self.root is None or self.studio is None or not self.pet.should_auto_run('delivery'):
            self.auto_handoff_signature=None;return
        # 交接包必须按当前选择的分镜：工作集没跟上时先对齐，正在跑任务、正在定稿或新分镜不合规就等下一轮。
        if self.auto_final_busy or not self.align_studio():return
        studio=self.studio
        signature,digest=self.edit_ready()
        from project_stages import editing
        marker=editing(self.root)/'自动交接.json'
        done=read(marker) if marker.is_file() else {}
        from handoff_service import automatic_decision
        decision=automatic_decision(signature,digest,self.auto_handoff_signature,done)
        if decision['action']=='skip':return
        self.auto_handoff_signature=decision['signature']
        if decision['action'] in ('wait','complete'):return
        self.auto_handoff_busy=True;self._auto_handoff_ticket+=1
        ticket=self.auto_handoff_tasks.submit(self._auto_handoff_ticket)
        self.status.set('全部镜头已验收，正在自动整理剪映素材交接包…')
        def worker():
            try:
                out=self.handoff(auto=True)
                from stage_execution_service import save_automatic_handoff_marker
                save_automatic_handoff_marker(self.root,digest,out,len(studio.episode['shots']))
                self.auto_handoff_queue.put((ticket,True,'自动交接包已整理：'+str(out),signature))
            except Exception as exc:self.auto_handoff_queue.put((ticket,False,'自动整理交接包未完成，稍后重试：'+str(exc),signature))
        threading.Thread(target=worker,daemon=True).start()
        self._schedule_auto_handoff_result_poll()
    def poll_unwatched_cloud(self):
        from video_progress import unwatched_pending
        source=self.current_frame_json()
        watched=[app.root for app in self.video_sessions.values() if app.studio.episode_path.resolve()==source.resolve()]
        pending=unwatched_pending(self.root,source,watched)
        if not pending:
            self.cloud_monitor_due=time.monotonic()+5;return
        root,sid=pending[self.cloud_monitor_cursor%len(pending)];self.cloud_monitor_cursor+=1
        self.cloud_monitor_busy=True;self._cloud_monitor_ticket+=1
        ticket=self.cloud_monitor_tasks.submit(self._cloud_monitor_ticket)
        def work():
            try:
                from local_video import open_studio
                studio=open_studio(root)
                result=studio.poll(sid)
                self.cloud_monitor_result.put((ticket,True,result))
            except Exception as exc:self.cloud_monitor_result.put((ticket,False,str(exc)))
        threading.Thread(target=work,daemon=True).start()
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
                except Exception:pass
            # 第 47 期第 7 条：原来这里只弹一句「请等待…结束后退出」就什么都不做——白模那一批
            # 卡住时用户就再也关不掉程序了（用户报的「无法关闭程序」）。现在问一句：答「是」就把
            # 还在跑的进程收掉再退；答「否」照旧守着，等这一步自己结束。
            if not confirm(self.win, '仍在处理', reason+'。\n\n现在强制关闭程序吗？\n中断这一步不会删掉已经做好的成果，下次打开可以接着做。', dangerous=True):return
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
        except Exception:pass
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
            except Exception:pass
        try:
            import asset_thumbs
            asset_thumbs.forget()
            asset_thumbs.reset_worker()
        except tk.TclError:
            # 关窗清理仅忽略 Tk 生命周期竞态。
            pass
        self.win.destroy()
        from storage_maintenance import launch_cleanup
        launch_cleanup(self.app)
        # 日志维护只在正常退出后另起无窗口进程执行；强制退出不能再多做磁盘操作。
        if not getattr(self, '_forcing_quit', False):
            try:
                from log_maintenance import launch_cleanup as launch_log_cleanup
                launch_log_cleanup(self.app)
            except OSError:
                # 退出后的可选日志卫生不影响已完成退出。
                pass
            # 仓库级清理与日志维护同为正常退出后的可选卫生；强制退出同样不做。
            try:
                from workspace_maintenance import launch_cleanup as launch_workspace_cleanup
                launch_workspace_cleanup(self.app)
            except OSError:
                # 退出后的可选仓库卫生不影响已完成退出。
                pass
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
    def pet_at_stage(self,index):
        """进入制作页交给三虎统一协调：提示进度、半自动征询或全自动按 SKILL 执行。

        宠物不在、问不出来都不影响翻页——它只是搭一句话，不参与页面本身。
        """
        pet=getattr(self,'pet',None)
        if pet is None:return ''
        try:return pet.enter_stage(index)
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
    def fill_projects(self,tree):
        tree.delete(*tree.get_children())
        for state,label in [('making','在制作项目'),('completed','已完成项目')]:
            items=[p for p in self.projects.info['projects'] if p.get('status','making')==state]
            tree.insert('','end',iid='group:'+state,text=f'{label}（{len(items)}）',open=True)
            for p in sorted(items,key=lambda item:item.get('created_at',Path(item['path']).stat().st_ctime if Path(item['path']).exists() else 0)):
                missing=not Path(p['path']).is_dir()
                text=p['name']+('（目录已失效，可右键清除登记）' if missing else '')
                tree.insert('group:'+state,'end',iid=p['path'],text=text)
    def reload(self):self.fill_projects(self.list)
    def idea_example(self):
        """创意栏里那份预置示例（第 37 期第 2 条）：随程序打包，不改动就绝不进项目文件。

        正文只有程序目录这一份（默认创意示例.md）；项目里那份 创意与剧本.md 只有在用户真的
        改过、按过保存之后才会出现（见 save_brief）。程序里那份万一缺了，就退回一张只有字段名
        的空表，界面照常能用。首读一次记在 self._idea_example 上，翻页重建不重复读盘。
        """
        cached=getattr(self,'_idea_example',None)
        if cached is not None:return cached
        path=ROOT/'默认创意示例.md'
        try:
            text=path.read_text(encoding='utf-8-sig') if path.is_file() else ''
        except OSError:
            text=''
        if not text.strip():text='\n'.join(label+'：' for label in IDEA_FIELDS)+'\n'
        self._idea_example=text
        return text

    def flush_brief(self):
        """第 65 期任务 9：翻页只丢引用，不再自动另存——对话结束前一个字都不落盘。

        原来翻页会把创意栏里改过的字偷偷存成一份 创意_ 文件；现在这一页是跟模型对话，
        落盘只有一条路：模型给出剧本、用户点了「是」，见 confirm_script。
        """
        self.preserve_idea_draft()
        self.brief_editor=None
    def load(self,path,*,defer_page=False):
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
            self._startup_project_page_job=self.win.after(80,show_loaded_project)
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

    def _schedule_project_recovery(self,target):
        """首屏剧本准备页绘制后，再执行可延后的项目维护。"""
        if self._startup_project_recovery_job is not None:
            try:self.win.after_cancel(self._startup_project_recovery_job)
            except tk.TclError:pass
        self._startup_project_recovery_job=self.win.after_idle(
            lambda:self._complete_project_recovery(target))

    def _complete_project_recovery(self,target):
        self._startup_project_recovery_job=None
        if getattr(self,'shutting_down',False) or self.root!=target:return
        self.import_generated_assets()
        # 阶段目录改为按实际使用时才创建。过去每次打开项目都会预建 11 套
        # input/output/assets/... 空骨架，并为根目录再建一层链接，资源管理器
        # 看起来像两份文件；真实产物仍只保存在 writing、episode 等工作目录。
        self.prune_asset_leftovers()
        self.restore_asset_resume()

    def prune_asset_leftovers(self):
        """打开项目时清掉资产库里没登记过的原始取回图（第 64 期任务 1／4）。

        这类 comfy_<随机>_1.png 是旧版本留下的中间产物，内容与登记过的那张完全一样，
        用户看到的就是「自动生成的图片中有重复项」。只删没被 assets.json 登记的 comfy_*.png，
        登记过的一个字节都不动；异常一律吞掉，绝不因此把「打开项目」拦下来。
        """
        if not self.root:return []
        try:
            from asset_batch_state_service import prune_raw_outputs
            removed=prune_raw_outputs(self.asset_base())
        except Exception as exc:
            # 清理是可选维护，不能拦住打开项目；但失败也不能伪装成没有重复图。
            self.status.set('重复原始取回图未清理：%s；请稍后重试。' % exc)
            return []
        if removed:
            self.status.set('已清理 '+str(len(removed))+' 张重复的原始取回图（登记过的一张没动）')
        return removed
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
    def adopt_legacy_layout(self):
        """第 64 期任务 3：老目录接进阶段树（只做目录联接，绝不搬动、绝不删除）。

        用户报的「文件还在旧文件夹中，没有导入新的文件夹架构」：老目录照旧是权威位置，
        阶段目录下补一个同名入口，新老两头都看得见。接不上不拦下「打开项目」，但要说明未归位。
        """
        if not self.root:return {}
        try:
            from stage_layout import adopt_legacy
            result=adopt_legacy(self.root)
        except Exception as exc:
            self.status.set('旧目录未归入新架构：%s；请稍后重试。' % exc)
            return {}
        made=list(result.get('made') or [])
        if made:
            self.status.set('旧目录已归入新架构：'+'、'.join(path.name for path in made))
            self.record_legacy_adoption(made)
        return result
    def record_legacy_adoption(self,made):
        """归位留一笔记录（升级说明要照着看）：_archive/logs/旧目录归位.json。"""
        try:
            from stage_execution_service import record_stage_legacy_adoption
            return record_stage_legacy_adoption(self.root,made)
        except (OSError,ValueError,TypeError,KeyError) as exc:
            # 已完成的目录归位不能回滚，但审计记录失败必须让用户知道它不可追溯。
            self.status.set('旧目录归位记录未写入：%s；请稍后重试。' % exc)
            return None
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
                result={'error':str(exc)}
            self._stage_model_sync_results.put((generation,target,result))
        threading.Thread(target=work,daemon=True).start()
    def _tick_stage_model_sync_result(self):
        try:generation,target,result=self._stage_model_sync_results.get_nowait()
        except queue.Empty:return
        if generation!=self._stage_model_sync_generation or target!=self.root:return
        if isinstance(result,dict) and result.get('error'):
            self.status.set('项目模型同步未完成：%s；请稍后重试。' % result['error'])
            return
        if result:self.status.set('已同步项目模型：'+'、'.join(result))
    def import_generated_assets(self):
        """项目加载后自动导入生成目录里尚未登记的资产图：重启软件即可生效，无需先进资产页。"""
        if not self.root:return
        try:
            from stage_execution_service import pending_generated_assets
            if not pending_generated_assets(self.root,self.asset_base()):return
        except Exception as exc:
            self.status.set('生成资产检查未完成：%s；请稍后重试。' % exc)
            return
        def work():
            from stage_execution_service import import_pending_generated_assets
            imported=import_pending_generated_assets(self.root,self.asset_base())
            return ('已自动导入生成资产图：'+'、'.join(imported)) if imported else '生成资产检查完成'
        try:self.async_(work)
        except Exception as exc:
            self.status.set('生成资产导入未启动：%s；请稍后重试。' % exc)
    def switch(self,event=None):
        selected=self.list.selection()
        if not selected or selected[0].startswith('group:'):return
        path=selected[0]
        if Path(path)!=self.root:self.safe(lambda:self.open_project_or_cleanup(path))
    def open_project_or_cleanup(self,path):
        """从侧栏或项目首页打开项目，并记住当天的用户选择。"""
        try:
            self.load(path)
        except Exception as exc:
            if not needs_cleanup_after_open_error(exc):raise
            self.status.set('剧本已删除：请在项目选择窗点击“删除选中项目”清理残留项目。')
            self._cleanup_project_path=str(path)
            self.choose_project()
            return False
        # ``load`` 可能已把资源管理器改名后的旧登记认领到新目录；日常选择必须
        # 记住实际打开的项目，不能把调用入口携带的旧路径再写回设置。
        self.remember_daily_project_choice(getattr(self,'root',None) or path)
        return True
    def daily_project_choice(self):
        """返回今天已确认过的项目；过期、已删或未登记的记录一律不使用。"""
        if self.settings.get('project_choice_day')!=date.today().isoformat():return None
        path=str(self.settings.get('project_choice_path') or '')
        if path in [item.get('path') for item in self.projects.info.get('projects',[])]:return path
        return None
    def remember_daily_project_choice(self,path):
        """仅记录项目入口，不写入用户的剧本、分镜或阶段配置。"""
        from stage_execution_service import publish_desktop_preferences
        result=publish_desktop_preferences(self.settings_file,self.settings,{
            'project_choice_day':date.today().isoformat(),
            'project_choice_path':str(path),
        })
        if not result.ok:raise ValueError(result.reason)
        self.settings=result.data

    def _sync_desktop_project_paths(self,old_path,new_path):
        """认领成功后同步桌面级入口；项目文件改写仍归 Projects 的事务。"""
        from stage_execution_service import publish_desktop_preferences
        old=Path(old_path);new=Path(new_path);updates={}
        if self.settings.get('project_choice_path')==str(old):
            updates['project_choice_path']=str(new)
        legacy=self.settings.get('frame_json_by_project')
        if isinstance(legacy,dict) and str(old) in legacy:
            migrated=dict(legacy);value=migrated.pop(str(old))
            if isinstance(value,str):
                try:value=str(new/Path(value).relative_to(old))
                except ValueError:pass
            migrated[str(new)]=value;updates['frame_json_by_project']=migrated
        if updates:
            result=publish_desktop_preferences(self.settings_file,self.settings,updates)
            if not result.ok:raise ValueError(result.reason)
            self.settings=result.data
    def choose_project(self):
        # 自动续开项目时，三虎的量测只排到这次选择交回事件循环之后；否则
        # 它的 ``update_idletasks`` 会重入本调用栈并放大启动时间。
        if self.projects.legacy_migration_pending:
            self.status.set('正在后台迁移旧项目…')
            self._startup_timer=self.win.after(25,self.choose_project)
            return None
        self.win._desktop_loading_project=True
        try:
            return self._choose_project_impl()
        finally:
            self.win._desktop_loading_project=False
    def _choose_project_impl(self):
        if not self.projects.info['projects']:
            self.safe(self.new)
            return
        cleanup_path=getattr(self,'_cleanup_project_path',None)
        self._cleanup_project_path=None
        startup=bool(getattr(self,'_startup_project_choice',False));self._startup_project_choice=False
        remembered=self.daily_project_choice() if startup and not cleanup_path else None
        if remembered:
            try:self.load(remembered,defer_page=startup);return
            except (ValueError,OSError):
                self.status.set('今天选定的项目已不可用，请选择其他项目或导入新剧本')
        popup=BaseDialog(self.win,'选择项目 · 漫剧制作助手',geometry='640x480',minsize=(500,380),modal=False,chrome=False);popup.attributes('-alpha',0)
        ttk.Label(popup,text='今天继续哪个故事？',font=('Microsoft YaHei UI',17,'bold')).pack(anchor='w',padx=22,pady=(22,8))
        ttk.Label(popup,text='选择项目后点击进入，或双击项目名称。',style='Muted.TLabel').pack(anchor='w',padx=22,pady=(0,12))
        notice=tk.StringVar(value=('剧本已被删除，不能进入项目。请点击“删除选中项目”清理残留文件夹。'
                                   if cleanup_path else ''))
        ttk.Label(popup,textvariable=notice,foreground='#b54708',wraplength=590).pack(anchor='w',padx=22,pady=(0,8))
        tree=ttk.Treeview(popup,show='tree',selectmode='browse');tree.pack(fill='both',expand=True,padx=22);self.fill_projects(tree)
        selected_path=cleanup_path or self.projects.info.get('active')
        if selected_path and tree.exists(selected_path):tree.selection_set(selected_path);tree.see(selected_path)
        def delete_selected_project():
            """项目不完整时也能从选择窗口清理残留目录，无需先成功打开它。"""
            selected=tree.selection()
            if not selected or selected[0].startswith('group:'):
                notice.set('请先选中要删除的项目。');return
            path=selected[0]
            item=next((dict(one) for one in self.projects.info['projects'] if one.get('path')==path),None)
            if item is None:
                notice.set('该项目已不在列表中。');return
            if not Path(path).exists():
                if not confirm(popup, '只清除登记',
                        '项目目录已不存在。只清除这条项目登记，不会改动磁盘上的任何文件。是否继续？',
                        dangerous=True):return
                if not self.clear_missing_project(item,confirmed=True):
                    notice.set('清除失效项目登记失败，请查看状态栏后重试。');return
                self.fill_projects(tree)
                notice.set('已只清除失效项目登记。');return
            linked=False
            try:target=self.projects.deletion_target(path)
            except ValueError as exc:
                if '链接' not in str(exc):raise
                target=Path(path);linked=True
            message=(f"{item.get('name','项目')}\n{target}\n\n"
                     +('这是一条项目目录链接。只会删除链接和项目登记，不会删除链接指向的真实目录。是否删除？'
                       if linked else '将把这个项目文件夹及全部素材移入项目库回收站。是否继续？'))
            if not confirm(popup, '移入项目回收站',
                    message,
                    dangerous=True):return
            notice.set('正在删除项目文件夹…');tree.state(['disabled'])
            def gone(_):
                self.reload();self.fill_projects(tree)
                if str(self.root or '')==path:self.load(None)
                if not self.projects.info['projects']:popup.destroy()
                else:
                    notice.set('项目已删除；请选择其他项目或新建项目。')
                    tree.state(['!disabled']);popup.lift();popup.focus_force()
                self.status.set('项目及残留目录已删除')
            self.async_(lambda:self._project_result_data(self.projects.unlink_registered_project(path) if linked else self.projects.delete(path)),gone)
        def refind_selected_project():
            selected=tree.selection()
            if not selected or selected[0].startswith('group:'):
                notice.set('请先选中失效的项目登记。');return
            old=selected[0]
            try:outcome=self._project_result_data(self.projects.reconcile_missing(old))
            except Exception as exc:
                notice.set(str(exc));return
            if outcome.get('state')=='claimed':
                self.reload();self.fill_projects(tree)
                new=outcome['path'];tree.selection_set(new);tree.see(new)
                notice.set('已按新位置同步项目登记。');return
            choices=outcome.get('choices',[])
            if not choices:
                notice.set('没有找到可认领的目录；可只清除这条失效登记。');return
            picker=BaseDialog(popup,'选择重新找到的项目目录',modal=False,chrome=False)
            ttk.Label(picker,text='找到多个候选目录，请确认实际项目：').pack(anchor='w',padx=16,pady=(16,8))
            candidate=tk.StringVar(value=choices[0])
            for value in choices:
                ttk.Radiobutton(picker,text=value,variable=candidate,value=value).pack(anchor='w',padx=16,pady=3)
            def claim():
                try:claimed=self._project_result_data(self.projects.reconcile_missing(old,selected=candidate.get()))
                except Exception as exc:
                    NotificationDispatcher(self.status, parent=picker).error(str(exc), title='无法同步项目登记');return
                picker.destroy();self.reload();self.fill_projects(tree)
                new=claimed['path'];tree.selection_set(new);tree.see(new)
                notice.set('已按新位置同步项目登记。')
            PrimaryButton(picker,text='认领此目录',command=claim).pack(pady=16)
        def enter(event=None):
            selected=tree.selection()
            if not selected or selected[0].startswith('group:'):return
            try:self.load(selected[0])
            except Exception as e:
                # 用户已删掉整份剧本时，这一项不再是可打开的项目。移除它的登记和目录，
                # 不留下下一次启动还会报错的幽灵入口，也不再叠一层原生错误框。
                if needs_cleanup_after_open_error(e):
                    notice.set('剧本已被删除，不能进入项目。请点击“删除选中项目”清理残留文件夹。')
                    return
                NotificationDispatcher(self.status, parent=popup).error(str(e), title='无法打开项目');return
            # 同侧栏入口：成功认领后以 load() 解析出的实际根目录记忆当天选择。
            self.remember_daily_project_choice(getattr(self,'root',None) or selected[0])
            popup.destroy()
        row=ttk.Frame(popup);row.pack(fill='x',padx=22,pady=18)
        PrimaryButton(row,text='+ 新建项目',command=lambda:(popup.destroy(),self.safe(self.new))).pack(side='left')
        SecondaryButton(row,text='恢复回收站内容…',command=lambda:self.safe(self.open_recycle_recovery)).pack(side='left',padx=(8,0))
        SecondaryButton(row,text='重新查找项目',command=refind_selected_project).pack(side='left',padx=(8,0))
        SecondaryButton(row,text='删除选中项目',command=lambda:self.safe(delete_selected_project)).pack(side='left',padx=(8,0))
        PrimaryButton(row,text='进入项目 →',command=enter).pack(side='right')
        tree.bind('<Double-1>',enter);tree.bind('<Return>',enter)
        popup.bind('<Escape>',lambda e:popup.destroy());popup.grab_set();tree.focus_set()
    def project_home(self):
        self.note('选择一个故事继续制作。右键项目可标记完成、恢复制作或删除项目。')
        tree=ttk.Treeview(self.content,show='tree',height=13,selectmode='browse');tree.pack(fill='both',expand=True,pady=12);self.fill_projects(tree)
        tree.bind('<Button-3>',lambda e:self.project_menu(e,tree))
        def enter(event=None):
            selected=tree.selection()
            if selected and not selected[0].startswith('group:'):self.safe(lambda:self.open_project_or_cleanup(selected[0]))
        tree.bind('<Double-1>',enter);tree.bind('<Return>',enter)
        self.button(self.content,'进入选中的项目 →',enter)
        self.button(self.content,'＋ 创建新项目',self.new)
        self.button(self.content,'恢复回收站内容…',self.open_recycle_recovery)
        self.button(self.content,'导出诊断包…',self.export_diagnostics_package)
    def set_project_status(self,item,status):
        self._project_result_data(self.projects.set_status(item['path'],status));self.reload()
        if self.root:self.list.selection_set(str(self.root))
        else:self.show(0)
        self.status.set('已完成项目' if status=='completed' else '已恢复到在制作项目')
    def new(self):
        name=simpledialog.askstring('新建项目','项目名称：',parent=self.win)
        if name:
            p=self._project_result_data(self.projects.create(name));self.reload();self.load(p)
            self.remember_daily_project_choice(p)
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

        「08 视频生成」这一格要记住用户第一次选的那一侧：本次启动第一次点它先摆「选择生成方式」，
        选定之后再点就直接进那一侧；想换一侧用页里的「返回生成方式」。
        """
        if index==PAGE['assets']:self.asset_detail_id=None;self.asset_roster=False
        mode='choose' if (index==PAGE['video'] and not getattr(self,'video_mode_picked',False)) else None
        return self.go(index,video_mode=mode)
    def go(self,index,video_mode=None):
        """侧栏导航专用：页面构建失败时给出提示，而不是留下一个空白页。

        用 .pyw 启动时没有控制台，未捕获的异常只有一条看不见的 stderr traceback，用户面对的
        就是一个空白内容区。这里换成一条读得懂的提示。与 self.safe 不同：不因后台任务在跑
        而拦下翻页（批次期间必须能切换页面）；程序内的其他位置仍直接调 show()，
        这样页面真出问题时会照旧抛出异常，不会被测试漏掉。

        第 35 期第 4 条：video_mode 原样透给 show()——侧栏点「08 视频生成」时传 'choose'。
        """
        try:self.show(index,video_mode=video_mode)
        except Exception as exc:self.notifier.error(str(exc), title='页面无法显示')
    def show(self,index,video_mode=None):
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
        # 第 71 期任务 2：资产详情页与资产清单页都是「03 资产管理」的子路由；翻到别的页就回主页面。
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
                message='请先在第2步采用一份或多份分镜 JSON。'
                # 不能只写到底部状态栏：视频工作台被阻止时，用户的视线仍在当前内容区。
                ttk.Label(self.content,text=message,style='Muted.TLabel').pack(anchor='w',padx=16,pady=18)
                self.note(message)
                self.fit_content()
                return
        if PAGE['assets']<=index<=PAGE['audio'] and not choosing_video and not (index==PAGE['assets'] and (getattr(self,'asset_detail_id',None) or getattr(self,'asset_roster',False))):
            from storyboard_selection import source_selector
            source_selector(self,index)
        # 08／09 步直接读工作集：切换分镜或自动采用后必须先让工作集跟上，否则会按旧分镜拼接和交付。
        if index in (PAGE['edit'],PAGE['delivery']):self.align_studio()
        if index==PAGE['script'] and getattr(self.win,'_desktop_loading_project',False):
            # 自动续开原先在一个 Tk 回调中拆掉“我的项目”再同步建完整剧本页，
            # Windows 因而一直只能显示旧页。先摆出当前阶段的轻量壳，等一个
            # 确定的绘制时隙后才创建聊天、文件表和它们的绑定。
            target=self.root
            ttk.Label(self.content,text='剧本准备',font=('Microsoft YaHei UI',16,'bold')).pack(anchor='w',padx=16,pady=(18,6))
            ttk.Label(self.content,text='正在打开剧本准备…',style='Muted.TLabel').pack(anchor='w',padx=16)
            self.status.set('正在打开剧本准备…')
            self.fit_content()
            def build_startup_script_page():
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
                self.pet_at_stage(PAGE['script'])
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
            [self.writing,self.script_structure,self.storyboard_creation,self.asset_page,self.continuity_page,self.final_storyboard,self.storyboard,self.previs,self.videos,self.audio,self.editing,self.delivery][index]()
        # 页面树可能很大；强制 Tk 立刻完成两次尺寸计算会阻塞点击与绘制，启动时尤其容易
        # 被 Windows 判为无响应。交给已有的合并空闲布局：同一轮连续换页只做最后一次，
        # 内容尺寸晚到时由 _fit_again 补算，首帧也能先交还事件循环。
        if scroll_offset>0:
            self._pending_scroll_restore=scroll_offset
            self._pending_scroll_layout=None
        self.fit_content()
        self.pet_at_stage(index)   # 第 36 期第 6 条：换阶段了，三虎主动问一句能做什么
    def restore_scroll(self,offset):
        """按像素恢复滚动位置：重建后页面高度可能变了，用比例换算回同样的位置。"""
        try:region=[int(float(part)) for part in self.canvas.cget('scrollregion').split()]
        except (ValueError,tk.TclError):return
        height=region[3] if len(region)==4 else 0
        if height<=0:return
        self.canvas.yview_moveto(max(0.0,min(1.0,offset/height)))

    def text(self,value,height=10):
        t=TextArea(self.content,bg='#ffffff',fg='#243247',insertbackground='#3564a8',height=height,wrap='word',font=('Microsoft YaHei UI',11),relief='flat',padx=12,pady=12);t.insert('1.0',value);t.pack(fill='both',expand=True,pady=8);bind_show_all(t,after=self.fit_content);return t
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
    def reference_sites(self):
        self.note('点击网站名称，在默认浏览器中打开。')
        groups=[
            ('模型与 API 控制台',[
                ('阿里云百炼控制台','https://bailian.console.aliyun.com/','管理通义千问等模型的 API、用量与费用。'),
                ('火山方舟控制台','https://console.volcengine.com/ark','管理火山方舟模型、API 密钥和视频生成任务。')]),
            ('创意与剧本辅助',[
                ('Google Gemini','https://gemini.google.com/app','AI对话，辅助构思故事、整理资料和修改文案。'),
                ('DeepSeek','https://chat.deepseek.com/','AI对话，辅助剧本构思、对白润色和提示词整理。')]),
            ('图片、视频与动画创作',[
                ('即梦 AI','https://jimeng.jianying.com/','AI图片与视频创作，用于角色视觉、场景和动态画面。'),
                ('小云雀网页版','https://xyq.jianying.com/','AI内容创作，辅助制作图片和短视频。'),
                ('Seko','https://seko.sensetime.com/','AI视频与短剧创作，辅助故事画面制作。'),
                ('OiiOii','https://www.oiioii.ai/','AI动画创作，辅助把故事制作成动画。'),
                ('LibLibAI','https://www.liblib.art/','AI绘画与模型社区，查找风格模型及生成图片。')]),
            ('模型与素材资源',[
                ('Hugging Face','https://huggingface.co/','查找开源模型、数据集及在线演示。'),
                ('Civitai','https://civitai.com/','查找绘画模型、LoRA及作品参数参考。')]),
            ('Agent 与技能工作流',[
                ('LobeHub','https://lobehub.com/','AI助手与Agent工作空间，组织对话和工作流。'),
                ('SkillsMP','https://skillsmp.com/zh','搜索Agent技能，查看技能说明与源代码入口。')])]
        for category,sites in groups:
            group=ttk.LabelFrame(self.content,text=category,padding=8)
            group.pack(fill='x',pady=5)
            cards=[]
            for name,url,description in sites:
                card=ttk.Frame(group,padding=(4,3))
                SecondaryButton(card,text=name,command=lambda u=url:self.safe(lambda:open_target(u))).pack(anchor='w')
                link=ttk.Label(card,text=url,style='Muted.TLabel',cursor='hand2',wraplength=240,justify='left')
                link.local_wrap=True;link.pack(anchor='w',fill='x',pady=(4,2))
                link.bind('<Button-1>',lambda event,u=url:self.safe(lambda:open_target(u)))
                detail=ttk.Label(card,text=description,wraplength=240,justify='left')
                detail.local_wrap=True;detail.pack(anchor='w',fill='x')
                cards.append((card,link,detail))
            def arrange(event,box=group,items=cards):
                columns=2 if event.width>=620 else 1
                available=max(120,(event.width-32)//columns-24)
                layout=(columns,available)
                if getattr(box,'site_layout',None)==layout:return
                box.site_layout=layout
                for col in range(2):box.columnconfigure(col,weight=1 if col<columns else 0,uniform='sites' if col<columns else '',minsize=0)
                for index,(card,link,detail) in enumerate(items):
                    card.grid(row=index//columns,column=index%columns,sticky='nsew',padx=(0,8) if columns==2 and index%2==0 else 0,pady=4)
                    link.configure(wraplength=available);detail.configure(wraplength=available)
            group.bind('<Configure>',arrange)
            # Mount cards before the first layout event; width is then set by the page.
            for index,(card,_,_) in enumerate(cards):card.grid(row=index//2,column=index%2,sticky='nsew')
    def writing(self):
        from script_workspace_service import ensure_script_workspace
        result=ensure_script_workspace(self.root)
        if not result.ok:raise ValueError(result.reason)
        # 第 69 期任务 4：原来第一行那句「在下面的对话框写想法…」删掉——页面自己会说清怎么走。
        import idea_chat
        # 先使用不扫描目录的默认路径；历史创意文件由页面建好后在后台发现。
        brief=idea_chat.default_brief_document(self.idea_chat_context())
        self.idea_template=self.idea_example()
        # 聊天记录与发送框分离：记录可滚动，发送框固定停在聊天区域底部。
        talk=ttk.LabelFrame(self.content,text='对话AI',padding=(SPACING['xs'],SPACING['none']))
        # 标题、聊天框与左侧内容起点同高；不在标题下额外留出一档空白。
        talk.pack(fill='both',expand=True,pady=SPACING['none'])
        # 第 69 期任务 2：「发送」挪到创意框左下角；第 69 期任务 3：文件操作挪到右下角。
        # 第 71 期任务 5：这一行先摆下来（pack 先给谁算尺寸，谁就不会被挤掉）——窗口缩小时
        # 收的是上面的创意框，那颗「发送」永远留在看得见的地方。
        # 动作栏与其余制作阶段共用可换行布局。普通 pack 的左右两组按钮会在窗口
        # 变窄时互相挤压，最后把“删除剧本”裁成一个字；FlowBar 会按可用宽度分行，
        # 每颗按钮始终保留自己的完整文字宽度。
        foot=FlowBar(talk);foot.pack(side='bottom',fill='x',pady=SPACING['none'])
        # 输入框与操作栏保留极小缓冲带，视觉仍紧凑，同时避免鼠标落点贴边误触发送。
        composer=ttk.Frame(talk);composer.pack(side='bottom',fill='x',pady=(SPACING['none'],SPACING['xs']))
        ttk.Label(composer,text='输入想法→点击发送',style='Muted.TLabel').pack(anchor='w')
        input_row=ttk.Frame(composer);input_row.pack(fill='x')
        input_box=TextArea(input_row,bg=COLORS['background_card'],fg=COLORS['text_primary'],insertbackground=COLORS['primary'],height=1,wrap='word',
                          font=FONTS['body'],relief='solid',bd=1,padx=SPACING['md'],pady=SPACING['sm'])
        attach_button=SecondaryButton(input_row,text='📁',width=3,
                                 command=lambda:self.safe(self.choose_idea_attachments))
        # 附件入口放在输入框左侧，先占住固定宽度；窄窗口时输入框只使用剩余空间，
        # 既方便点击，也不会把图标挤出可视区。
        attach_button.pack(side='left',padx=(SPACING['none'],SPACING['sm']))
        input_box.pack(side='left',fill='x',expand=True)
        self.idea_attachment_button=attach_button
        self.idea_input_row=input_row
        self.idea_attachment_status=tk.StringVar(value='')
        self.idea_attachment_status_label=ttk.Label(composer,textvariable=self.idea_attachment_status,
                                                     style='Muted.TLabel')
        self.update_idea_attachment_status()
        input_hint=ttk.Label(composer,text='调用模型将创建导演、编剧、编辑、演员四个角色自动进行剧本创作，可在阶段配置中修改规则',style='Muted.TLabel')
        self.idea_input_hint=input_hint
        def stop_input_hint():
            input_hint.place_forget()
        def update_input_hint(event=None):
            try:
                if not self.draft_text().strip() and input_box.focus_get() is not input_box:
                    # 静态提示只在失焦空框显示，水平居中且不向 Tk 主循环投递动画回调。
                    input_hint.place(in_=input_box,relx=0.5,rely=0.5,anchor='center')
                else:stop_input_hint()
            except tk.TclError:pass
        input_box.bind('<Destroy>',lambda event:stop_input_hint() if event.widget is input_box else None,add='+')
        import idea_chat
        dialog=ttk.Frame(talk);dialog.pack(side='top',fill='both',expand=True,pady=SPACING['none'])
        dialog_scroll=ttk.Scrollbar(dialog,orient='vertical')
        dialog_scroll.pack(side='right',fill='y')
        box=TextArea(dialog,bg=COLORS['background_card'],fg=COLORS['text_primary'],insertbackground=COLORS['primary'],
                    selectbackground='#3564a8',inactiveselectbackground='#3564a8',selectforeground='#ffffff',height=TALK_MIN_LINES,wrap='word',
                    font=FONTS['body'],relief='flat',padx=SPACING['md'],pady=SPACING['sm'],yscrollcommand=dialog_scroll.set)
        box.pack(side='left',fill='both',expand=True)
        dialog_scroll.configure(command=box.yview)
        self.brief_editor=(brief,input_box);self.brief_saved_text=''
        self.idea_log=box
        self.idea_scroll=dialog_scroll
        self.idea_input=input_box
        self.queue_initial_brief_document(input_box,brief)
        # 聊天区只读；窗口缩小时只收聊天记录区，底部发送框永远可见。
        def refit_talk(event=None):
            fit=getattr(self,'_fit_talk',None)
            if fit is None:return
            try:fit()
            except Exception:pass
        # 先让 Text 用当前布局命中鼠标位置，再在空闲时重算高度；同步重排会让选区偏到上一行。
        box.bind('<Button-1>',lambda event:box.after_idle(refit_talk),add='+')
        # 常态下可长按拖选并 Ctrl+C；单击进入编辑后，写入边界只限这条气泡的正文。
        self.shortcuts.bind(box, ('<Control-c>', '<Control-C>'), self.copy_selected_bubble_text,
                            scope='剧本准备·聊天记录', name='复制选中气泡文本')
        box.bind('<Button-3>',self.open_bubble_menu,add='+')
        box.bind('<ButtonPress-1>',self.guard_bubble_edit_pointer,add='+')
        box.bind('<B1-Motion>',self.guard_bubble_edit_pointer,add='+')
        box.bind('<B1-Motion>',self.track_bubble_click,add='+')
        box.bind('<ButtonRelease-1>',self.finish_bubble_click,add='+')
        box.bind('<KeyPress>',self.guard_bubble_edit_key,add='+')
        box.bind('<<Paste>>',self.guard_bubble_edit_key,add='+')
        box.bind('<FocusOut>',lambda event:self.finish_bubble_edit(),add='+')
        self.shortcuts.bind(box, ('<Control-Return>',), lambda event:self.finish_bubble_edit(),
                            scope='剧本准备·聊天记录', name='保存气泡编辑')
        self.shortcuts.bind(box, ('<Escape>',), lambda event:self.finish_bubble_edit(commit=False),
                            scope='剧本准备·聊天记录', name='取消气泡编辑')
        self.idea_row=foot
        # 输入框下方的动作统一为紧凑尺寸，避免长旧文案把聊天区挤窄。
        script_action_width=STAGE_ACTION_WIDTH
        send_button=PrimaryButton(foot,text='发送',width=script_action_width,
                               command=lambda:self.safe(self.send_message))
        send_button.pack(side='left',pady=SPACING['none']);self.idea_send=send_button
        # 剧本阶段的唯一配置入口贴着发送键：写完想法后就能直接调整模型／SKILL，
        # 不再在对话框上方额外占一行。
        # 阶段按钮属于首帧可交互核心。使用无配置读取的轻量入口，既保持“设置—
        # 中断”原有相邻顺序，也不再把 stage_config.synchronize 塞进建页回调。
        panel=ui_plugin_registry.module('skill_panel')
        holder={}
        self.stage_button=panel.stage_button_for(
            foot,lambda:panel.open_for_page(self,PAGE['script'],holder['button']))
        holder['button']=self.stage_button
        self.stage_button.pack(side='left',padx=(SPACING['xs'],SPACING['none']),pady=SPACING['none'])
        interrupt_button=SecondaryButton(foot,text='中断',width=script_action_width,command=self.interrupt_script_agent)
        interrupt_button.pack(side='left',padx=(SPACING['xs'],SPACING['none']));interrupt_button.state(['disabled']);self.idea_interrupt=interrupt_button
        refresh_button=SecondaryButton(foot,text='刷新',width=script_action_width,command=lambda:self.safe(self.refresh_script_workspace))
        refresh_button.pack(side='left',padx=(SPACING['xs'],SPACING['none']));self.idea_refresh=refresh_button
        download_button=SecondaryButton(foot,text='下载剧本',width=script_action_width,command=lambda:self.safe(self.download_script))
        download_button.state(['disabled']);self.idea_download=download_button
        SecondaryButton(foot,text='添加剧本',width=script_action_width,
                   command=lambda:self.safe(self.import_json)).pack(side='right')
        SecondaryButton(foot,text='删除剧本',width=script_action_width,
                   command=lambda:self.safe(delete_selected_scripts)).pack(side='right',padx=(SPACING['none'],SPACING['sm']))
        open_folder_button=SecondaryButton(foot,text='剧本目录',width=script_action_width,
                                      command=lambda:self.safe(lambda:self.open_folder(project_stages.writing(self.root))))
        open_folder_button.pack(side='right',padx=(SPACING['none'],SPACING['sm']));self.idea_open_folder=open_folder_button
        download_button.pack(side='right',padx=(SPACING['none'],SPACING['xs']))
        def clear_example(event=None):
            # 第 45 期：还是那份示例就先清掉——第一笔字是您写的，不是压着示例写。
            if self.idea_still_the_example():
                input_box.delete(*self.idea_draft_range());input_box.configure(fg=COLORS['text_primary'])
        def start_writing(event):
            printable=bool(event.char and event.char.isprintable() and not (event.state & 0xC))
            paste=(event.state & 0x4) and event.keysym.lower()=='v'
            if printable or paste or event.keysym in ('Return','KP_Enter'):
                clear_example()
        def on_modified(event=None):
            if event is not None and not input_box.edit_modified():return
            self.tint_brief()
            # 发送框的高度由实际换行数决定；长创意无需在一行小框里横向／纵向挤着看。
            input_box.after_idle(fit_composer)
            update_input_hint()
        def fit_composer(event=None):
            """仅按实际内容撑开输入框，避免点击空框触发布局反馈回路。"""
            if not input_box.winfo_exists():return
            try:
                logical_lines=int(input_box.index('end-1c').split('.')[0])
                # 空框只保留一行。旧逻辑在点击时按聊天框高度把 Text 放大到半屏，
                # 输入框、聊天框、画布各自的 Configure 又会重新测量对方，形成持续抖动。
                # 文字需要多行时才增长，并设上限以维持操作栏和文件表可见。
                lines=min(8,max(1,logical_lines,display_lines(input_box)))
                if int(input_box.cget('height'))!=lines:
                    input_box.configure(height=lines)
                    self.fit_content()
            except (tk.TclError,ValueError):pass
        def expand_composer_for_click(event=None):
            """空框点击只取得编辑焦点；高度只由真实输入内容决定。"""
            input_box.focus_set()
        def restore_composer_after_blur(event=None):
            # 不按焦点收缩：用户输入多行后切换控件，内容高度仍应保持可读。
            return None
        def focus_composer_from_hint(event=None):
            """提示层覆盖输入框时，也必须把点击交还给真正的编辑器。

            否则点击会落到 Label，Text 永远拿不到焦点，用户无法立即开始输入。
            """
            input_box.focus_set()
            expand_composer_for_click()
            # 在失焦/窗口尚未激活的一瞬间，focus_get() 可能仍不是 Text；点击本身
            # 已明确表达要编辑，因此直接撤掉提示，不能等待下一次焦点事件。
            stop_input_hint()
            return 'break'
        input_box.tag_configure('field_hint',foreground=COLORS['text_secondary'])
        input_hint.bind('<Button-1>',focus_composer_from_hint,add='+')
        input_box.bind('<Button-3>',self.open_idea_paste_menu,add='+')
        input_box.bind('<Button-1>',expand_composer_for_click,add='+')
        input_box.bind('<FocusIn>',update_input_hint,add='+')
        input_box.bind('<FocusOut>',restore_composer_after_blur,add='+')
        input_box.bind('<FocusOut>',update_input_hint,add='+')
        input_box.bind('<KeyPress>',start_writing,add='+')
        input_box.bind('<KeyRelease>',self.show_idea_reference_menu,add='+')
        def send_on_enter(event):
            if event.state & 0x1:return None  # Shift+Enter 保留换行
            self.safe(self.send_message)
            return 'break'
        input_box.bind('<Return>',send_on_enter,add='+')
        input_box.bind('<KP_Enter>',send_on_enter,add='+')
        input_box.bind('<<Paste>>',clear_example,add='+')
        input_box.bind('<<Modified>>',on_modified)
        box.bind('<Configure>',self.refit_bubbles,add='+')
        self.restore_idea_draft()
        self.tint_brief()
        update_input_hint()
        self.show_conversation()
        # 下载按钮初始即为禁用；判断历史回复是否可下载会递归扫描旧项目的
        # Markdown，不能占用“打开项目”的首帧。页面仍在当前代次时再补状态。
        page_generation=getattr(self,'_script_page_generation',0)+1
        self._script_page_generation=page_generation
        def refresh_download_state():
            if (page_generation==getattr(self,'_script_page_generation',0)
                    and self.page_index==PAGE['script'] and self.root):
                self.update_script_download_button()
        script_box=ttk.Frame(self.content,padding=(SPACING['xs'],SPACING['xs']));script_box.pack(fill='x',expand=False,pady=SPACING['none'])
        self.script_box=script_box
        try:download_state_job=self.win.after(250,refresh_download_state)
        except tk.TclError:download_state_job=None
        def cancel_download_state(event=None):
            """页面已销毁时不再执行下载状态的后台刷新。"""
            if event is not None and getattr(event,'widget',None) is not script_box:
                return None
            if download_state_job is not None:
                try:self.win.after_cancel(download_state_job)
                except tk.TclError:pass
            return None
        script_box.bind('<Destroy>',cancel_download_state,add='+')
        # 三类文件各用独立列表：同一个 Treeview 的「行」无法让每列各自紧凑排列，
        # 会把其他两列留空。独立列表保持每一类从上到下的文件名排序。
        script_lists=ttk.Frame(script_box);script_lists.grid(row=0,column=0,sticky='nsew')
        script_box.columnconfigure(0,weight=1);script_box.rowconfigure(0,weight=1)
        categories=(('setting','项目设定'),('outline','项目大纲'),('script','项目剧本'))
        script_trees={}
        for column,(category,title) in enumerate(categories):
            script_lists.columnconfigure(column,weight=1,uniform='script-files')
            table=DataTable(script_lists,columns=[('name',title,180)],show='tree headings',height=1,
                            selectmode='browse',style='Script.Treeview',auto_hide_scrollbars=True)
            tree=table.tree
            configure_check_column(tree)
            tree.heading('name',text=title)
            tree.column('name',width=180,minwidth=100,stretch=True)
            table.grid(row=0,column=column,sticky='nsew',padx=(SPACING['none'],SPACING['xs']) if column<2 else SPACING['none'])
            script_trees[category]=tree
        self.script_trees=script_trees
        # 兼容旧的页面外部访问：script_tree 指向项目剧本这一列。
        self.script_tree=script_trees['script']
        script_tree=script_trees['setting']
        from responsive_ui import display_lines,font_linespace,row_height_of,GROWABLE_FLOOR
        fit_row_height(script_tree, style='Script.Treeview')
        # 第 71 期任务 5：这一页「除了创意框」固定要占的高度，建页面时量一次就定下来——
        # 每拍现算的话，创意框自己改行数会牵动下面文件框的行数，两边互相追着改，界面一直抖。
        # 数是这么来的：两排按钮 ＋ 创意框的抬头与按钮行 ＋ 文件框的抬头与边框 ＋ 它必须
        # 自己占下的那两行（GROWABLE_FLOOR，多出来的行由 growable_extra 扣，不占页面）。
        talk_line=max(1,font_linespace(box,BUBBLE_FONT,fallback=19))    # 这个框一行字多高
        box_chrome=2*int(box.cget('pady'))+2                            # 框内上下留白 ＋ 边框
        tree_row=row_height_of(script_tree)
        tree_chrome=max(0,script_tree.winfo_reqheight()-int(script_tree.cget('height'))*tree_row)
        page_fixed=0
        def measure_page_fixed():
            """在空闲布局批次量固定高度，不能为测量阻塞 Tk 消息循环。"""
            nonlocal page_fixed
            page_fixed=max(0,self.content.winfo_reqheight()-box.winfo_reqheight()-script_tree.winfo_reqheight()
                           +tree_chrome+GROWABLE_FLOOR*tree_row)
        def fit_talk(event=None):
            """第 71 期任务 5／6：创意框摆几行＝「窗口还剩多少」「框里有多少字」「上限」三者取小。

            字少就矮下来，字多也不撑过头；下面那一行「发送」与文件框都先算好位置，
            于是窗口怎么缩，它们都还在可视区里。
            """
            if not box.winfo_exists():return
            viewport=int(self.canvas.winfo_height() or 0)
            if viewport<=1:return                      # 还没量出窗口尺寸：等下一拍
            try:
                room=viewport-page_fixed-box_chrome
                lines=max(TALK_MIN_LINES,min(TALK_MAX_LINES,room//talk_line,display_lines(box)))
                if int(box.cget('height'))!=lines:
                    box.configure(height=lines)
                    # 交给已合并的空闲重排；同步递归扫描整页控件会与本次 Configure
                    # 事件嵌套，造成鼠标停留/输入时的布局风暴。
                    self.fit_content()

            except (tk.TclError,ValueError):pass
        self._fit_talk=fit_talk
        talk.bind('<Configure>',fit_talk,add='+')
        # 框自己变宽变窄也要重算：建页面那一小会儿宽度还是 1 像素，折行数虚高，
        # 等真实宽度下来按文字行数收回去（不然会一直停在最大那一档）。
        box.bind('<Configure>',fit_talk,add='+')
        box.bind('<<Modified>>',lambda event=None:fit_talk(),add='+')
        self._fit_composer=fit_composer
        # 页面刚建好时的两次尺寸修正要登记任务 ID。测试或用户快速关闭项目时，
        # 未执行的匿名 after_idle 回调会在 Tcl 删除窗口后报 ``invalid command name``。
        layout_job = None
        def cancel_layout_job(event=None):
            nonlocal layout_job
            if event is not None and getattr(event, 'widget', None) is not self.win:
                return None
            job, layout_job = layout_job, None
            if job is not None:
                try:
                    self.win.after_cancel(job)
                except tk.TclError:
                    pass
            return None
        def schedule_layout(*callbacks):
            nonlocal layout_job
            cancel_layout_job()
            def run():
                nonlocal layout_job
                layout_job = None
                for callback in callbacks:
                    try:
                        callback()
                    except tk.TclError:
                        return None
                return None
            try:
                layout_job = self.win.after_idle(run)
            except tk.TclError:
                layout_job = None
            return layout_job
        self.win.bind('<Destroy>', cancel_layout_job, add='+')
        schedule_layout(fit_composer, measure_page_fixed, fit_talk)
        checked_scripts=set()
        def set_script_box_visible(has_files):
            """没有任何文件时不保留空表格，把整页优先交给上方聊天内容。"""
            if has_files:
                if not script_box.winfo_manager():
                    script_box.pack(fill='x',expand=False,pady=SPACING['none'])
            elif script_box.winfo_manager():
                script_box.pack_forget()
            schedule_layout(fit_talk, self._fit_content_now)
        from writing_page_controller import ScriptListLoadController
        script_loader=ScriptListLoadController(category for category,_title in categories)
        script_load_job=None
        def cancel_script_load(event=None):
            """页面销毁时撤销尚未提交的目录批次。"""
            nonlocal script_load_job
            if event is not None and getattr(event,'widget',None) is not script_box:return None
            script_loader.invalidate()
            if script_load_job is not None:
                try:self.win.after_cancel(script_load_job)
                except tk.TclError:pass
                script_load_job=None
            return None
        script_box.bind('<Destroy>',cancel_script_load,add='+')
        def fill_script_list():
            """渐进加载剧本文件表；新刷新或页面销毁会使旧批次失效。"""
            nonlocal script_load_job
            from script_workspace_service import iter_script_document_rows
            generation=script_loader.start(iter_script_document_rows(self.root))
            if script_load_job is not None:
                try:self.win.after_cancel(script_load_job)
                except tk.TclError:pass
                script_load_job=None
            for tree in script_trees.values():
                tree.delete(*tree.get_children())
            # 首批文件尚未扫描完成时也必须保留三列表的列头。此前这里先隐藏
            # ``script_box``，慢目录扫描期间“项目设定／项目大纲／项目剧本”会完全
            # 消失；只有确认最终为空时才在 finish() 中收起空表。
            set_script_box_visible(True)
            def alive():
                return script_loader.is_current(generation) and all(tree.winfo_exists() for tree in script_trees.values())
            def finish():
                """按修改时间恢复既有排序；每个空闲批次只调整有限条目。"""
                order=[(category,iter(rows)) for category,rows in script_loader.ordered_rows().items()]
                def place():
                    nonlocal script_load_job
                    if not alive():return
                    moved=0
                    while order and moved<24:
                        category,rows=order[0]
                        try:row=next(rows)
                        except StopIteration:
                            order.pop(0);continue
                        script_trees[category].move(row.item_id,'','end')
                        moved+=1
                    if order:
                        script_load_job=self.win.after_idle(place)
                        return
                    live=script_loader.item_ids()
                    checked_scripts.intersection_update(live)
                    for category,tree in script_trees.items():
                        tree.configure(height=max(1,min(6,len(tree.get_children()))))
                        script_checks[category].refresh_header()
                    set_script_box_visible(bool(live));script_load_job=None
                place()
            def load_batch():
                nonlocal script_load_job
                if not alive():return
                rows,finished=script_loader.take_batch(24)
                for row in rows:
                    script_trees[row.category].insert('', 'end', iid=row.item_id, text='',
                        image=self.win._tick_images[int(row.item_id in checked_scripts)], values=(row.name,))
                if finished:
                    finish();return
                set_script_box_visible(True)
                script_load_job=self.win.after_idle(load_batch)
            # 初次目录扫描必须越过首帧的 event loop；after_idle 会在同一次
            # update() 内被追着执行，等同又把 rglob 塞回启动回调。
            script_load_job=self.win.after(250,load_batch)
        self.refresh_script_list=fill_script_list
        def current_script_tree():
            for tree in script_trees.values():
                if tree.selection():return tree
            return None
        def open_script_file(event=None):
            tree=current_script_tree()
            selected=tree.selection() if tree else ()
            if not selected:return
            path=Path(selected[0])
            if path.is_file():open_path(path)
        for tree in script_trees.values():
            tree.bind('<Double-1>',open_script_file)
            tree.bind('<Return>',open_script_file)
        def keep_one_script_selection(tree, event=None):
            if not tree.selection():return
            for other in script_trees.values():
                if other is not tree:other.selection_remove(other.selection())
        for tree in script_trees.values():
            tree.bind('<<TreeviewSelect>>',lambda event,tree=tree:keep_one_script_selection(tree,event),add='+')
        def selected_script():
            tree=current_script_tree()
            selected=tree.selection() if tree else ()
            if not selected:raise ValueError('请先选择剧本文件')
            from script_workspace_service import selected_script_paths
            return selected_script_paths(self.root,[selected[0]])[0]
        def selected_scripts():
            """批量删除只认勾选项；未勾选时将当前高亮行视作单项操作。"""
            all_items=[item for tree in script_trees.values() for item in tree.get_children()]
            tree=current_script_tree()
            active=tree.selection() if tree else ()
            from script_workspace_service import script_deletion_selection
            return script_deletion_selection(self.root,all_items,checked_scripts,active)
        def selection_changed():
            count=len(checked_scripts)
            self.status.set('已勾选 '+str(count)+' 份剧本文件' if count else '已取消剧本文件勾选')
        script_checks={
            category:CheckboxColumn(tree,self.win._tick_images,
                                    lambda item:item in checked_scripts,
                                    lambda item,value:checked_scripts.add(item) if value else checked_scripts.discard(item),
                                    selection_changed)
            for category,tree in script_trees.items()
        }
        for category,tree in script_trees.items():
            tree.heading('#0',command=script_checks[category].toggle_all)
        fill_script_list()
        for category,tree in script_trees.items():
            bind_row_toggle(tree,script_checks[category].toggle)
        def rename_script():
            path=selected_script()
            new=simpledialog.askstring('重命名文件','新文件名：',initialvalue=path.name,parent=self.win)
            if not new:return
            from script_workspace_service import rename_script_document
            result=rename_script_document(self.root,path,new)
            if not result.ok:raise ValueError(result.reason)
            dest=result.data
            if dest==path:return
            fill_script_list();self.status.set('已重命名：'+dest.name)
        def delete_script():
            path=selected_script()
            all_files=[item for tree in script_trees.values() for item in tree.get_children()]
            if len(all_files)==1:
                if not confirm_project_removal_from_last_script(self.win,[path.name]):return
            else:
                prompt=f'确定将 {path.name} 移入项目回收站吗？\n\n可在对应页面恢复最近删除。'
                title='移入回收站'
                if not confirm(self.win,title,prompt,dangerous=True):return
            if len(all_files)==1:
                item=next((dict(p) for p in self.projects.info['projects'] if p['path']==str(self.root)),None)
                if item is None:raise ValueError('当前项目未登记，无法安全删除')
                self.delete_project(item,confirmed=True);return
            from storage_maintenance import recycle_paths
            if not recycle_paths(self.root,[path],'删除项目剧本'):
                raise OSError('文件未能移入回收站，请刷新后重试')
            fill_script_list();self.status.set('已移入回收站：'+path.name)
        def delete_selected_scripts():
            selection=selected_scripts()
            paths=list(selection.paths)
            names='\n'.join(path.name for path in paths)
            if selection.deletes_all:
                if not confirm_project_removal_from_last_script(self.win,[path.name for path in paths]):return
            else:
                title='移入回收站'
                prompt='确定将选中的 '+str(len(paths))+' 份剧本文件移入项目回收站吗？\n\n'+names+'\n\n可在对应页面恢复最近删除。'
                if not confirm(self.win,title,prompt,dangerous=True):return
            if selection.deletes_all:
                item=next((dict(p) for p in self.projects.info['projects'] if p['path']==str(self.root)),None)
                if item is None:raise ValueError('当前项目未登记，无法安全删除')
                self.delete_project(item,confirmed=True);return
            from storage_maintenance import recycle_paths
            recycled=recycle_paths(self.root,paths,'批量删除项目剧本')
            if len(recycled)!=len(paths):
                raise OSError('部分文件未能移入回收站，请刷新后重试')
            fill_script_list()
            self.status.set('已移入回收站 '+str(len(paths))+' 份剧本文件')
        def script_menu(tree,event):
            row=tree.identify_row(event.y)
            if not row:return
            for other in script_trees.values():
                if other is not tree:other.selection_remove(other.selection())
            tree.selection_set(row)
            menu=ContextMenu(self.win)
            # 第 46 期第 1 条：内容框的右键一律是「查看／…／删除」这一套，剧本表原来只有改名与删除。
            menu.command('查看',lambda:self.safe(open_script_file))
            menu.command('重命名',lambda:self.safe(rename_script))
            menu.command('删除',lambda:self.safe(delete_script))
            return menu.popup(event)
        for tree in script_trees.values():
            tree.bind('<Button-3>',lambda event,tree=tree:script_menu(tree,event))
    def storyboard_creation(self):
        from storyboard_files import show
        show(self)
    def script_structure(self):
        """上看剧本准备原稿、下看结构化正稿；两框独立滚动并可分别编辑保存。"""
        import script_contract
        from script_workspace_service import script_structure_documents
        structure = script_structure_documents(self.root)
        source_directory = structure.source_directory
        structure_directory = structure.output_directory
        source = structure.source
        target = structure.target
        # 将两份剧本放入同一个等分网格。动作栏与说明文字不参与分配，窗口缩放时
        # 上、下内容框始终各占剩余阅读区域的一半。
        split_area = ttk.Frame(self.content)
        split_area.pack(fill='both', expand=True)
        split_area.columnconfigure(0, weight=1)
        split_area.rowconfigure(0, weight=1, uniform='script_structure_preview')
        split_area.rowconfigure(2, weight=1, uniform='script_structure_preview')
        structure_note = ('剧本整理：Writer 提取人物、场景、道具、事件、冲突、台词与分场要素，Editor 审校完整性和一致性后输出结构剧本；'
                          '不切镜头、不生成分镜 JSON，也不会改动自然语言原稿。')
        from script_preview_service import LOADING_PREVIEW, preview_chunks, read_preview, should_load_async
        def content_box(parent, title, file_heading, documents, active_path, empty, attribute, editable=True):
            # 文件栏与正文同一行：左列只管选择／确认剧本文件，右列专心阅读和编辑正文。
            # 不再把这份文件清单重复放到页面底部。
            box = ttk.Frame(parent, padding=SPACING["sm"])
            # 可拖动的横向分隔条：自然／结构剧本目录列与正文列都可按阅读需要调宽。
            body = ttk.Panedwindow(box, orient='horizontal'); body.pack(fill='both', expand=True)
            files = ttk.Frame(body)
            # 高度交给外层上下等分网格。这里若声明 12 行，会成为 Tk 的刚性
            # 最小请求高度，窄窗口先撑满上框、把下方结构剧本挤出可视区。
            file_table = DataTable(files, columns=[('script', file_heading, 170)], show='headings',
                                   height=1, selectmode='browse', auto_hide_scrollbars=True)
            file_list = file_table.tree
            # 文件栏仅用于选择；正文是本页的主要阅读区。原来的 260px 在窄窗口
            # 抢走过多空间，缩为约三分之二并允许随窗口继续收缩。
            file_list.column('script', anchor='w', width=170, minwidth=105, stretch=True)
            file_table.pack(fill='both', expand=True)
            available = tuple(path for path in documents if path and path.is_file())
            active = {'path': active_path if active_path in available else (available[0] if available else None)}
            if available:
                for path in available:
                    file_list.insert('', 'end', iid=str(path), values=(path.name,))
                file_list.selection_set(str(active['path']))
            else:
                file_list.insert('', 'end', values=('尚无可用文件',))
            preview_area = ttk.Frame(body)
            preview_header = ttk.Frame(preview_area)
            preview_header.pack(fill='x', pady=(SPACING["none"], SPACING["xs"]))
            ttk.Label(preview_header, text='剧本内容', style='Muted.TLabel').pack(side='left')
            # 编辑操作贴着正文标题的右侧，不再占用内容框上方的一整行。
            controls = ttk.Frame(preview_header)
            controls.pack(side='right')
            text_area = ttk.Frame(preview_area); text_area.pack(fill='both', expand=True)
            preview = TextArea(text_area, bg=COLORS["background_card"], fg=COLORS["text_primary"], height=1,
                              wrap='word', undo=True, maxundo=-1, font=FONTS["caption"], relief='flat',
                              padx=SPACING["md"], pady=SPACING["sm"])
            scroll = ttk.Scrollbar(text_area, orient='vertical', command=preview.yview)
            preview.configure(yscrollcommand=scroll.set)
            preview.grid(row=0, column=0, sticky='nsew'); scroll.grid(row=0, column=1, sticky='ns')
            text_area.columnconfigure(0, weight=1); text_area.rowconfigure(0, weight=1)
            body.add(files, weight=1)
            body.add(preview_area, weight=4)
            preview_ticket = {'value': 0}
            def set_preview(value, ticket=None):
                """小文本立即显示；大文本在 Tk 空闲时分块插入，避免一次性重排。"""
                preview.configure(state='normal')
                preview.delete('1.0', 'end')
                preview.configure(state='disabled')
                chunks = iter(preview_chunks(value))
                def append_chunk():
                    if ticket is not None and ticket != preview_ticket['value']:
                        return
                    try:
                        chunk = next(chunks)
                    except StopIteration:
                        try:
                            preview.configure(state='normal')
                            # 初始预览不能成为“恢复删除”的一条历史记录；只恢复用户本次编辑中的动作。
                            preview.edit_reset()
                            preview.configure(state='disabled')
                        except tk.TclError:
                            pass
                        return
                    try:
                        preview.configure(state='normal')
                        preview.insert('end', chunk)
                        preview.configure(state='disabled')
                        self.win.after_idle(append_chunk)
                    except tk.TclError:
                        pass
                if ticket is None:
                    preview.configure(state='normal')
                    preview.insert('end', value)
                    preview.edit_reset()
                    preview.configure(state='disabled')
                else:
                    self.win.after_idle(append_chunk)
            def load_preview(path):
                """大文本在后台读取；选中项变化或进入编辑态时丢弃旧结果。"""
                preview_ticket['value'] += 1
                ticket = preview_ticket['value']
                if not should_load_async(path):
                    set_preview(read_preview(path, empty))
                    return
                set_preview(LOADING_PREVIEW)
                expected = Path(path) if path else None
                # 不使用 self.async_：后者代表独占的业务工作，会错误地禁用用户操作。
                # 预览读取独立排队，结果只由 Tk 主线程的 after 回写。
                preview_results = queue.Queue(maxsize=1)
                threading.Thread(
                    target=lambda: preview_results.put((ticket, expected, read_preview(expected, empty))),
                    daemon=True,
                ).start()
                def await_preview():
                    try:
                        result_ticket, result_path, value = preview_results.get_nowait()
                    except queue.Empty:
                        try:
                            self.win.after(50, await_preview)
                        except tk.TclError:
                            pass
                        return
                    if (result_ticket != preview_ticket['value'] or active['path'] != result_path or
                            str(preview.cget('state')) != 'disabled'):
                        return
                    try:
                        if preview.winfo_exists():
                            set_preview(value, ticket=ticket)
                    except tk.TclError:
                        pass
                self.win.after(20, await_preview)
            load_preview(active['path'])
            def select_document(_event=None):
                selected = file_list.selection()
                if not selected or not available:
                    return
                if str(preview.cget('state')) == 'normal':
                    file_list.selection_set(str(active['path']))
                    self.status.set('请先保存或完成当前修改，再切换剧本。')
                    return
                chosen = Path(selected[0])
                if chosen == active['path']:
                    return
                active['path'] = chosen
                load_preview(chosen)
            file_list.bind('<<TreeviewSelect>>', select_document)
            def delete_document():
                """目录右键删除只移入项目回收站；来源稿删除后刷新会隐藏关联结构稿。"""
                selected = file_list.selection()
                from script_workspace_service import selected_workspace_document
                destination = selected_workspace_document(available, selected[0] if selected else None)
                from storage_maintenance import recycle_paths
                records = recycle_paths(self.root, [destination], '删除' + title)
                if not records:
                    raise ValueError('未能安全移入项目回收站，原文件未删除。')
                self.show(PAGE['script_structure'])
                self.status.set('已将' + destination.name + '移入回收站；关联的结构剧本已按来源刷新。')
            def open_document_menu(event):
                row = file_list.identify_row(event.y)
                if not row or row not in {str(path) for path in available}:
                    return None
                file_list.selection_set(row)
                menu = ContextMenu(file_list).command('删除（移入回收站）', lambda:self.safe(delete_document))
                self._script_structure_file_menu = menu
                return menu.popup(event)
            file_list.bind('<Button-3>', open_document_menu)
            def begin_edit():
                if not editable or active['path'] is None:
                    raise ValueError('当前没有可修改的剧本文档。')
                preview.configure(state='normal')
                edit.state(['disabled']); restore.state(['!disabled']); save.state(['!disabled'])
                preview.focus_set()
            def save_edit():
                if not editable or active['path'] is None:
                    raise ValueError('当前没有可保存的剧本文档。')
                value = preview.get('1.0', 'end-1c').strip()
                if not value:
                    raise ValueError('剧本内容不能为空。')
                destination = Path(active['path'])
                from script_contract import save_natural_script
                save_natural_script(destination, value)
                preview.configure(state='disabled')
                edit.state(['!disabled']); restore.state(['disabled']); save.state(['disabled'])
                self.status.set('已保存'+title+'：'+destination.name)
                if destination == source:
                    self.status.set('已保存剧本准备阶段剧本；如需更新下方结构化剧本，请重新执行“手动制作结构剧本”。')
            def restore_deleted():
                if str(preview.cget('state')) == 'disabled':
                    raise ValueError('请先点击“修改内容”，再恢复刚删除的文字。')
                try:
                    preview.edit_undo()
                except tk.TclError as exc:
                    raise ValueError('没有可恢复的删除内容。') from exc
            edit = SecondaryButton(controls, text='修改内容', command=lambda:self.safe(begin_edit))
            edit.pack(side='left')
            restore = SecondaryButton(controls, text='恢复删除', command=lambda:self.safe(restore_deleted))
            restore.pack(side='left', padx=(SPACING["sm"], SPACING["none"])); restore.state(['disabled'])
            save = PrimaryButton(controls, text='保存修改', command=lambda:self.safe(save_edit))
            save.pack(side='left', padx=(SPACING["sm"], SPACING["none"])); save.state(['disabled'])
            setattr(self, attribute, preview)
            setattr(self, attribute + '_edit_button', edit)
            setattr(self, attribute + '_restore_button', restore)
            setattr(self, attribute + '_save_button', save)
            setattr(self, attribute + '_files', file_list)
            return box
        self.script_structure_source_box = content_box(
            split_area,
            '自然剧本', '自然剧本目录（01剧本准备）', structure.source_documents, source,
            '尚未找到剧本准备阶段的剧本。请先生成、下载或导入剧本。',
            'script_structure_source_preview', editable=source is not None)
        self.script_structure_source_box.grid(row=0, column=0, sticky='nsew', pady=(SPACING["xs"], SPACING["none"]))
        actions = FlowBar(split_area); actions.grid(row=1, column=0, sticky='ew', pady=(SPACING["sm"], SPACING["xs"]))
        def start_structure():
            if script_contract.resolve_script_source(self.root) is None:
                raise ValueError('请先在“剧本准备”生成、下载或导入剧本。')
            started = self.pet_script_structure_batch(trigger='manual', refresh_page=True)
            if not started:
                raise ValueError('剧本结构正在执行，或三虎自动化暂不可用。')
            self.status.set(started)
        from stage_models import manual_command
        action_group = ttk.Frame(actions)
        action_group.pack(anchor='center', pady=SPACING["xs"])
        manual = PrimaryButton(action_group, text='手动制作结构剧本', width=STAGE_ACTION_WIDTH,
                               command=lambda:self.safe(manual_command(self, 'script_structure', start_structure, self.win)))
        manual.pack(side='left', padx=(SPACING["none"], SPACING["xs"])); self.script_structure_manual_button = manual
        ui_plugin_registry.module('stage_flow').follow(manual, 'script_structure')
        self.stage_button = ui_plugin_registry.module('skill_panel').stage_button(action_group, self, PAGE['script_structure'])
        self.stage_button.pack(side='left', padx=(SPACING["sm"], SPACING["xs"]))
        self.script_structure_output_box = content_box(
            split_area,
            '结构剧本', '结构剧本目录（02剧本结构）', structure.output_documents, target,
            '尚未生成结构化剧本。点击上方“手动制作结构剧本”，或由三虎全自动模式执行。',
            'script_structure_output_preview', editable=True)
        self.script_structure_output_box.grid(row=2, column=0, sticky='nsew', pady=(SPACING["none"], SPACING["none"]))
        # 流程说明留在两块内容之后的右下角，避免占用顶部阅读空间。
        info = ttk.Label(self.content, text=structure_note, style='Muted.TLabel', justify='right', wraplength=760)
        info.pack(anchor='e', pady=(SPACING["xs"], SPACING["none"]))
        self.script_structure_info_label = info
        self.script_structure_source_directory = source_directory
        self.script_structure_output_directory = structure_directory
    # 第 29 期第 1 条：页面上那几处重复的「Model ＋ SKILL」控制行整个拿掉——入口只留那颗
    # 「阶段配置」。第 32 期第 6 条起它不再集中在剧本准备页，而是各阶段页「手动XX」右边各一颗
    # （见 skill_panel.stage_button），模型／SKILL／接口／说明都在面板里。
    # flow_settings 留着：首帧页的「Skill 调用设置」在模型接口窗口里还要用它（第 26 期那处）。
    def flow_settings(self,stage,function=None):
        from workflow_settings import show_settings
        if self.root is None:raise ValueError('请先选择项目')
        from workflow_agents import refresh
        show_settings(self,self.root,stage=stage,on_saved=lambda:refresh(self),function=function)
    def open_flow_agent(self,stage,label,prompt,followup=None,on_receipt=None,_config=None):
        from workflow_settings import current
        from workflow_engines import prompt_with_settings,launch_interactive
        from agent_dispatch import signature,claim,finish,outcome,retryable
        if self.worker:raise ValueError('正在打开或发送 Agent 任务，请稍候；未重复发送。')
        # 「发送待核实」的安全重试必须沿用第一次已经解析的引擎。原来递归重进时会重新
        # 读取阶段配置，恰逢面板刷新／配置回退就可能把 Claude 的续发错误地交给 Codex。
        config=_config if _config is not None else current(self.root,stage);followup=followup if followup is not None else prompt
        setup_key=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
        from codex_tasks import prepare_task
        project=self.root
        name=next((p['name'] for p in self.projects.info['projects'] if Path(p['path'])==project),project.name)
        title=name+' '+label
        if config['engine']=='qwen':
            from qwen_adapter import window_title
            title=window_title(name,stage,getattr(self,'page_index',None))
        use_cli=config['engine']!='codex' or config['program'] or config['model']
        def build():
            from workflow_context import continuation_instruction,snapshot
            from workflow_context_controller import request_stage_instruction
            from workflow_context_budget import prepare_request_context
            data=snapshot(project)
            receipt=claim(project,signature(stage,prompt,followup,config,data),title)
            if on_receipt is not None:on_receipt(receipt)
            if receipt['duplicate']:return {'receipt':receipt}
            try:
                if stage=='previs':
                    from native_apps import open_blender
                    open_blender()
                context,strategy=request_stage_instruction(project,stage,data)
                full,budget=prepare_request_context(
                    prompt_with_settings(context+prompt,config,stage=stage),stage,strategy)
                continuation,continuation_budget=prepare_request_context(
                    prompt_with_settings(continuation_instruction(project,stage,data)+followup,config,stage=stage),
                    stage,'continuation_summary')
                finish(receipt,'preparing','',context_budget={
                    'initial':budget,'continuation':continuation_budget})
                if use_cli:return {'receipt':receipt,'prompt':full,'followup':continuation,
                                   'context_budget':{'initial':budget,'continuation':continuation_budget}}
                result=prepare_task(project,title,stage,full,followup=continuation,setup_key=setup_key)
                result['receipt']=receipt;result['context_budget']={
                    'initial':budget,'continuation':continuation_budget};return result
            except Exception as exc:finish(receipt,'failed',str(exc));raise
        def dispatch(result):
            receipt=result['receipt']
            if receipt['duplicate']:
                sessions=getattr(self,'flow_processes',{})
                key=(str(project),stage,config['engine'],setup_key)
                live=key in sessions and sessions[key].poll() is None
                if retryable(receipt,live):
                    finish(receipt,'failed','上次发送结果未确认，且对应 Agent 窗口已关闭')
                    self.status.set('上次 Agent 发送未确认且窗口已关闭，正在自动重新启动…')
                    self.open_flow_agent(stage,label,prompt,followup,on_receipt,_config=config)
                    return
                if not live:
                    finish(receipt,'failed','上次 Agent 窗口已关闭，请重新点击启动')
                    self.notifier.info('上次 Agent 窗口未在运行，任务状态已重置；请再次点击“手动制作分镜”。', title='请重新点击', modal=True);return
                state={'preparing':'正在打开或发送','sent':'已发送','uncertain':'发送结果待核实'}[receipt['state']]
                self.status.set('相同任务'+state+'，已复用记录，本次不重复发送。请在对应 Agent 窗口继续。');return
            if use_cli:
                launch_cli(result);return
            try:done(result)
            except Exception as exc:finish(receipt,'failed',str(exc));raise
        def launch_cli(result):
            receipt=result['receipt'];full=result['prompt'];continuation=result['followup']
            sessions=getattr(self,'flow_processes',{});key=(str(project),stage,config['engine'],setup_key)
            if key in sessions and sessions[key].poll() is None:
                def submit():
                    try:
                        if config['engine']=='qwen':
                            from qwen_adapter import submit_existing
                            text=submit_existing(sessions[key],continuation,title=title)
                            return {'ok':True,'reason':text,'send_dispatched':True}
                        from workflow_engines import submit_existing
                        return submit_existing(sessions[key],continuation,title=title)
                    except Exception as exc:
                        finish(receipt,'uncertain',str(exc));raise
                def submitted(value):
                    outcome(receipt,value);self.status.set(value['reason'])
                    if not value['ok']:self.notifier.info(value['reason'], title='请检查 Agent 输入框', modal=True)
                self.async_(submit,submitted);return
            def launched(result):
                sessions[key]=result['process'];self.flow_processes=sessions
                if stage=='writing':
                    self._script_agent_launching=False
                    self.update_script_interrupt_button()
                finish(receipt,'sent','启动时已传入初始任务',task_file=result['task_file'])
                self.status.set('已启动 '+result['engine']+'，初始任务已自动提交，可在窗口继续讨论。')
            def launch(slot=None):
                try:return launch_interactive(project,stage,title,full,config,followup=continuation,slot=slot)
                except Exception as exc:finish(receipt,'failed',str(exc));raise
            from workflow_engines import request_stage_process_slot, claim_stage_process_slot
            request=request_stage_process_slot(project,stage)
            if request['state']=='granted':
                self.async_(lambda:launch(request['slot']),launched);return
            self.status.set('模型请求排队中（第%d位），界面保持响应。' % request['position'])
            def poll_slot():
                if getattr(self,'shutting_down',False) or getattr(self,'_closing',False):
                    finish(receipt,'failed','模型请求已在关闭时取消')
                    return
                claimed=claim_stage_process_slot(request['ticket'])
                if claimed['state']=='queued':
                    self.status.set('模型请求排队中（第%d位），界面保持响应。' % claimed['position'])
                    self.win.after(200,poll_slot);return
                if claimed['state']=='granted':
                    self.status.set('已获得模型请求槽位，正在启动…')
                    self.async_(lambda:launch(claimed['slot']),launched);return
                finish(receipt,'failed',claimed['reason'])
                self.status.set(claimed['reason'])
            self.win.after(200,poll_slot)
        def done(result):
            receipt=result['receipt']
            clipboard_text=result['prompt']
            task_file=result.get('task_file')
            if task_file and Path(task_file).is_file():
                try:clipboard_text=Path(task_file).read_text(encoding='utf-8')
                except OSError:clipboard_text=result['prompt']
            from prompt_window import copy_text
            copy_text(self.win,clipboard_text)
            open_target(result['url'])
            from codex_paste import paste_existing,confirm_existing
            def confirmed(outcome):
                ui_plugin_registry.module('agent_dispatch').outcome(receipt,outcome)
                self.status.set(outcome['reason'])
                if not outcome['ok']:self.notifier.info(outcome['reason'], title='发送结果', modal=True)
            def pasted(outcome):
                ui_plugin_registry.module('agent_dispatch').outcome(receipt,outcome)
                self.status.set(outcome['reason'])
                if outcome['ok']:return
                if outcome.get('can_confirm') and not outcome.get('send_dispatched'):
                    accepted=confirm(self.win,'确认发送',
                        '任务：'+result['title']+'\n\n内容已填入 Codex，但自动发送尚未完成。\n'
                        '请确认左侧输入框是本次任务，点击“确认”后助手会直接点击发送，不再粘贴。')
                    if accepted:
                        self.status.set('正在发送已确认的 Codex 输入框内容…')
                        self.async_(lambda:confirm_existing(result['title'],result['prompt'],outcome['confirmation'],
                            result.get('draft_prompt',''),result.get('project','')),confirmed)
                    else:self.status.set('已保留 Codex 输入框内容，尚未发送。')
                else:self.notifier.info(outcome['reason'], title='请检查 Codex 输入框', modal=True)
            self.async_(lambda:paste_existing(result['title'],result['prompt'],result.get('draft_prompt',''),result.get('project',''),auto_send=True),pasted)
            self.status.set('正在将本次任务粘贴到 Codex 并自动发送…')
        self.async_(build,dispatch)
    def open_storyboard_skill(self,key=None):
        batch={}
        def work():
            from storyboard_catalog_service import produced_scripts
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
    def open_current_project(self):
        if self.root is None:raise ValueError('请先创建项目')
        open_path(self.root)
    def open_recycle_recovery(self):
        """打开已承诺的回收站恢复入口；恢复决策与磁盘操作均留在 L2/L3。"""
        from recycle_recovery_controller import RecycleRecoveryController
        dialog=BaseDialog(self.win,'恢复回收站内容',geometry='920x580',minsize=(720,420))
        controller=RecycleRecoveryController(self.root,self.projects.base)
        batches=[]
        ttk.Label(dialog.content,text='选择回收批次后可恢复整批，或选择下方原位置只恢复一项；目标已存在时不会覆盖。').pack(anchor='w',pady=(0,6))
        batch_table=DataTable(dialog.content,columns=[('scope','位置',110),('created','创建时间',155),('reason','原因',390)],show='tree headings',height=8,auto_hide_scrollbars=True)
        batch_tree=batch_table.tree
        batch_tree.heading('#0',text='批次');batch_tree.column('#0',width=180,stretch=False)
        batch_table.pack(fill='x',expand=False)
        ttk.Label(dialog.content,text='批次条目（原位置）').pack(anchor='w',pady=(10,3))
        item_table=DataTable(dialog.content,columns=[('recycled','回收位置',420)],show='tree headings',height=9,auto_hide_scrollbars=True)
        item_tree=item_table.tree
        item_tree.heading('#0',text='原位置');item_tree.column('#0',width=420)
        item_table.pack(fill='both',expand=True)
        def selected_batch():
            selected=batch_tree.selection()
            return batches[int(selected[0])] if selected else None
        def show_items(_event=None):
            item_tree.delete(*item_tree.get_children())
            record=selected_batch()
            if record:
                for item in record['items']:
                    item_tree.insert('', 'end', values=(item['recycle_path'],), text=item['source'])
        def refresh():
            nonlocal batches
            batches=controller.list_batches()
            batch_tree.delete(*batch_tree.get_children());item_tree.delete(*item_tree.get_children())
            for index,record in enumerate(batches):
                batch_tree.insert('', 'end',iid=str(index),text=record['batch'].name,
                                  values=(record['scope'],record['created_at'] or '—',record['reason'] or '—'))
            if batches:batch_tree.selection_set('0');show_items()
        def restore_all():
            record=selected_batch()
            if record is None:raise ValueError('请先选择一个回收批次')
            restored=controller.restore_batch(record)
            refresh();self.status.set('已恢复 '+str(len(restored))+' 项回收内容。')
        def restore_selected():
            record=selected_batch();selected=item_tree.selection()
            if record is None or not selected:raise ValueError('请先选择一个待恢复条目')
            source=item_tree.item(selected[0],'text')
            restored=controller.restore_item(record,source)
            refresh();self.status.set('已恢复：'+str(restored[0].name))
        batch_tree.bind('<<TreeviewSelect>>',show_items)
        dialog.add_action('关闭',dialog.close)
        dialog.add_action('刷新',lambda:self.safe(refresh))
        dialog.add_action('恢复选中条目',lambda:self.safe(restore_selected),primary=True)
        dialog.add_action('恢复整批',lambda:self.safe(restore_all),primary=True)
        refresh()
        return dialog
    def project_menu(self,event,tree=None):
        if self.worker:return
        tree=tree if tree is not None else self.list
        path=tree.identify_row(event.y)
        if not path or path.startswith('group:'):return
        item=next((dict(p) for p in self.projects.info['projects'] if p['path']==path),None)
        if item is None:return
        menu=ContextMenu(self.win)
        completed=item.get('status','making')=='completed'
        menu.command('恢复为在制作项目' if completed else '标记为已完成项目',lambda:self.safe(lambda:self.set_project_status(item,'making' if completed else 'completed')))
        menu.separator()
        if not Path(item['path']).exists():
            # 与项目选择弹窗一致：幽灵登记没有可回收的目录，只能清登记。
            menu.command('只清除失效项目登记',lambda:self.safe(lambda:self.clear_missing_project(item)))
            menu.separator()
        menu.command('恢复回收站内容…',lambda:self.safe(self.open_recycle_recovery))
        menu.separator()
        menu.command('删除项目及全部素材…',lambda:self.safe(lambda:self.delete_project(item)))
        return menu.popup(event)
    def clear_missing_project(self,item,confirmed=False):
        """主界面右键清理幽灵登记；不把不存在的目录送入回收流程。"""
        path=str(item['path'])
        if Path(path).exists():
            raise ValueError('项目目录仍存在，请使用“删除项目及全部素材”移入回收站')
        if not confirmed and not confirm(self.win,
                '只清除登记', '项目目录已不存在。只清除这条项目登记，不会改动磁盘上的任何文件。是否继续？',
                dangerous=True):
            return False
        try:self._project_result_data(self.projects.clear_missing_registration(path))
        except (OSError,ValueError) as exc:
            # 注册表落盘失败不能让主界面或选择弹窗看起来像已清理；目录仍存在
            # 的输入错误在上面的显式判断处上抛，只有写入／登记竞态走可重试降级。
            self.status.set('清除失效项目登记失败，请稍后重试：'+str(exc))
            return False
        if str(self.root or '') == path:
            self.root=None
        self.reload()
        self.status.set('已只清除失效项目登记。')
        return True
    def delete_project(self,item,confirmed=False):
        raw_project=Path(item['path'])
        project=raw_project.resolve()
        sessions=[(key,v) for key,v in self.video_sessions.items() if v.root.resolve().is_relative_to(project)]
        for key,v in sessions:
            pending=any(r.get('state') in ('submitting','unknown','queued','running','succeeded') for versions in v.studio.state()['shots'].values() for r in versions)
            if v.busy or getattr(v,'optimizer_busy',False) or pending:raise ValueError('此项目仍有视频或提示词任务，请待任务结束或处理完成后再删除项目；其他页面可以正常使用。')
        linked=False
        try:target=self.projects.deletion_target(item['path'])
        except ValueError as exc:
            if '链接' not in str(exc):raise
            target=raw_project;linked=True
        note=('这是一条项目目录链接。只会删除链接和项目登记，不会删除链接指向的真实目录。'
              if linked else '将项目的剧本、图片、音频、视频和成片移入项目库回收站；可通过“恢复回收站内容…”入口恢复。')
        if not confirmed and not confirm(self.win,'移入项目回收站',f"{item['name']}\n{target}\n\n{note} 是否继续？",dangerous=True):return
        for key,v in sessions:
            if hasattr(v,'timer'):v.scheduler.after_cancel(v.timer)
            if self.video is v:self.video=None
            v.footer.destroy();v.window.destroy();self.video_sessions.pop(key,None)
        def completed(_):
            if self.root==target:self.brief_editor=None
            self.reload();self.load(None);self.status.set('项目及全部文件已移入项目库回收站')
        self.async_(lambda:self._project_result_data(self.projects.unlink_registered_project(item['path']) if linked
                            else self.projects.delete(item['path'])),completed)

    # ── 第 61 期 v0.8：正典板／状态变体（任务 3／5）的折叠区・连贯性清单（任务 7）独立成页 ──
    def copy_text(self,text):
        """把一段文字复制到剪贴板（锚点字符串逐字复用）。

        第 61 期 v0.8：全程序只有 prompt_window.copy_text 写剪贴板（既有规矩），这里只转调一次。
        """
        from prompt_window import copy_preview,copy_text as write_clipboard
        reason=write_clipboard(self.win,str(text))
        self.status.set('复制失败：'+reason if reason else '已复制：'+copy_preview(text))
        return reason
    def continuity_ledger_data(self):
        """现场算一份连贯性台账：读当前分镜 JSON ＋ 这一集的资产清单（第 61 期 v0.8 任务 7）。"""
        from continuity_ledger import build
        shots=[]
        try:
            episode=read(self.current_frame_json())
            if isinstance(episode,dict) and isinstance(episode.get('shots'),list):shots=episode['shots']
        except (ValueError,OSError):shots=[]
        try:assets=dict(self.asset_requirements())
        except (ValueError,OSError,TypeError,AttributeError,KeyError):assets={}
        return build(shots,assets)
    def continuity_folder(self):
        """这一阶段落盘的地方（03_continuity/output）。"""
        import stage_layout
        return stage_layout.paths(self.root,'03_continuity')['output']
    def write_continuity_ledger(self,ledger=None):
        """把台账落到 03_continuity（第 62 期任务 11：这一步成了独立的一页，清单由「手动生成」写）。"""
        from continuity_ledger import write
        return write(self.root,self.continuity_ledger_data() if ledger is None else ledger)
    def continuity_page(self):
        """04 连贯性清单（第 62 期任务 11）。

        第 61 期 v0.8 它只是资产管理页底部的一个折叠区；用户要它成为独立的一步（左侧列表
        「03 资产管理」之下、「05 分镜定稿」之上），显示方式照首帧管理页那一套：上面一行按钮，
        下面按组各一张表。表里的数字全部来自同一次台账计算，页面上写的批次、镜头与结论不会
        各说各话（第 62 期任务 11 的「信息要准确」）。
        """
        from stage_execution_service import run_stage_confirmation_gate
        ledger=self.continuity_ledger_data()
        summary=ledger.get('summary') or {}
        passed=bool(summary.get('ok'))
        def line():
            return '镜头 %s 个 · 批次 %s 组 · %s'%(summary.get('shots',0),summary.get('batches',0),
                                                 '全部通过' if passed else '有待办')
        def make():
            self.write_continuity_ledger(ledger)
            self.pet_report('continuity','连贯性清单已生成：'+line()+'。')
            self.status.set('连贯性清单已生成并落盘：'+line())
            self.show(PAGE['continuity'])
        bar=FlowBar(self.content);bar.pack(fill='x',pady=(0,3))
        ttk.Label(bar,text='清单',width=ASSET_ROW_LABEL).pack(side='left')
        _make=PrimaryButton(bar,text='手动生成连贯性清单',style='Primary.TButton',width=STAGE_ACTION_WIDTH,command=lambda:self.safe(make))
        _make.pack(side='left',padx=(0,3),pady=2)
        ui_plugin_registry.module('stage_flow').follow(_make,'continuity')     # 三虎在跑这一步就写「自动执行中」并置灰
        self.stage_button=ui_plugin_registry.module('skill_panel').stage_button(bar,self,PAGE['continuity'])
        self.stage_button.pack(side='left',padx=(6,3),pady=2)
        SecondaryButton(bar,text='清单目录',style='Asset.TButton',
                   command=lambda:self.safe(lambda:open_path(self.continuity_folder()))).pack(side='left',padx=3,pady=2)
        head=ttk.Frame(self.content);head.pack(fill='x',pady=(2,0))
        ttk.Label(head,text=line(),foreground='#1a7f37' if passed else '#b54708').pack(side='left')
        file=self.continuity_folder()/'continuity_ledger.json'
        ttk.Label(head,text=('已落盘：'+file.name) if file.is_file() else '还没生成，按左边的按钮生成',
                  foreground='#555555').pack(side='left',padx=(8,0))
        def table_of(title,columns,rows,height,detail=''):
            """一张小表：抬头 ＋ 表头 ＋ 若干行（这一页的清单就是这几张表）。

            第 64 期任务 6：最后一列（「冻结锚点」「说明」）跟着窗口一起收放——原来固定
            620／700 像素，界面一窄就被挤没、界面一宽又留一大片白。detail 写某一列时，
            点这一列的格子弹一扇只读窗把整段字显示全（表格格子放不下长说明）。
            """
            frame=ttk.LabelFrame(self.content,text=title,padding=4)
            frame.pack(fill='both',expand=True,pady=(4,0))
            table=DataTable(frame,columns=columns,show='headings',height=height,
                            selectmode='browse',empty_text='暂无'+title)
            tree=table.tree
            last=columns[-1][0]
            for key,label,width in columns:
                tree.heading(key,text=label)
                tree.column(key,width=width,minwidth=60,stretch=key==last)
            for row in rows:tree.insert('','end',values=row)
            table.pack(fill='both',expand=True)
            if detail:
                def open_detail(event,tree=tree,column_name=detail,heading=title):
                    row=tree.identify_row(event.y);column=tree.identify_column(event.x)
                    if not row or not column:return
                    if tree.column(column,'id')!=column_name:return
                    text=str(tree.set(row,column_name) or '')
                    if not text:return
                    from prompt_window import show as show_text
                    show_text(self.win,heading+' · 说明',text,status=self.status,
                              receipt='说明已复制',button='复制说明',scrollbar=True)
                tree.bind('<Button-1>',open_detail,add='+')
            return tree
        batches=ledger.get('batches') or []
        table_of('批次与冻结锚点',
                 [('batch','批次',120),('shots','镜头',200),('seconds','秒数',70),
                  ('anchors','冻结锚点（逐字复用，机器不许改写）',620)],
                 [(block.get('batch_id') or '','、'.join(block.get('shot_ids') or []) or '—',
                   block.get('seconds') or 0,
                   '；'.join('%s %s：%s'%(entry.get('kind') or '',entry.get('id') or '',entry.get('anchor') or '')
                             for entry in block.get('frozen_anchors') or []) or '—')
                  for block in batches],min(8,max(2,len(batches))))
        checks=[]
        for row in ledger.get('triplets') or []:
            checks.append(('三元组',row.get('batch_id') or '','一致' if row.get('ok') else '不一致',
                           row.get('detail') or ''))
        for row in ledger.get('cross_batch') or []:
            checks.append(('跨批次',row.get('id') or row.get('kind') or '','一致' if row.get('ok') else '不一致',
                           row.get('detail') or ''))
        for row in ledger.get('conflicts') or []:
            checks.append(('参考图裁决',row.get('shot_id') or row.get('batch_id') or '',row.get('kind') or '',
                           (row.get('resolution') or '')+(('；理由：'+str(row.get('reason'))) if row.get('reason') else '')))
        for row in ledger.get('drift') or []:
            checks.append(('锚点漂移',row.get('id') or '','漂移' if not row.get('ok') else '一致',
                           row.get('detail') or ''))
        table_of('跨批次与三元组校验',
                 [('kind','项目',110),('id','编号',150),('result','结论',100),('detail','说明',700)],
                 checks,min(8,max(2,len(checks))),detail='detail')
        problems=list(summary.get('problems') or [])
        foot=ttk.LabelFrame(self.content,text='待办与裁决',padding=4);foot.pack(fill='x',pady=(4,0))
        if problems:
            for text in problems[:8]:ttk.Label(foot,text='· '+text,wraplength=760,justify='left').pack(anchor='w')
        else:
            ttk.Label(foot,text='没有待办：批次、锚点与三元组都对得上。',foreground='#1a7f37').pack(anchor='w')
        asks=run_stage_confirmation_gate(self.root, 'G-08', ledger=ledger).get('ask') or ()
        if asks:
            ttk.Label(foot,text='参考图优先级（每条选一个，问过就不再问）：',
                      foreground='#b54708').pack(anchor='w',pady=(4,0))
        for item in asks:
            box=ttk.Frame(foot);box.pack(fill='x',anchor='w',pady=2)
            text=' ／ '.join('候选%d %s'%(index+1,value)
                            for index,value in enumerate(item['candidates']))
            ttk.Label(box,text=item['title']+'：'+text,wraplength=760,justify='left').pack(anchor='w')
            ttk.Label(box,text='理由：'+str(item.get('reason') or ''),foreground='#555555',
                      wraplength=760,justify='left').pack(anchor='w')
            choice=item['candidates'][item.get('recommended',0)]
            PrimaryButton(box,text='采用推荐',
                       command=lambda key=item['key'],value=choice:self.safe(
                           lambda:self.pick_gate(key,value,
                               lambda:self.show(PAGE['continuity'])))).pack(anchor='w')
    def pick_gate(self,key,choice,again=None):
        """记一次人工确认，顺手把选择写进资产、再刷面板（第 64 期任务 6）。

        原来只调用 record()：选择进的是 gate_confirmations.json，资产清单里该写的
        canonical_board／character_anchor 一个字没写——「采用推荐」点了资产还是空的。
        现在与资产详情页走同一条写入路径（confirm_gates.apply_choice）。
        """
        from stage_execution_service import record_stage_confirmation
        from stage_execution_service import apply_asset_plan_gate_choice
        apply_asset_plan_gate_choice(self.root,key,choice)
        path=record_stage_confirmation(self.root,key,choice)
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
            record_stage_confirmation(self.root,key,choice,by=AUTO)
            done+=1
        if done:
            text='已按推荐处理 %d 条待办：锚点、正典板与连贯性裁决。'%done
            self.pet_report('continuity',text)
            if getattr(self,'page_index',None)==PAGE['continuity']:self.show(PAGE['continuity'])
            self.status.set(text)
        return done
    def open_asset_detail(self,aid=None):
        """进「资产详情页」（第 64 期任务 13；附件 v3.0 任务 2.3 的「点击进入详情」）。

        主页面布局一个像素都不动，只在「资产编号」那一格加这个入口：传 aid 用传进来的那一个，
        没传就看资产表里高亮的那一行。返回按钮走 close_asset_detail。
        """
        value=str(aid or '').strip()
        if not value:
            table=getattr(self,'asset_table',None)
            if table is not None and table.winfo_exists() and table.selection():
                value=str(table.selection()[0]).strip()
        if not value:raise ValueError('先在资产表里点选一项资产，再点「资产编号」进详情')
        self.asset_detail_id=value;self.asset_roster=False
        self.show(PAGE['assets'])
        return value
    def close_asset_detail(self):
        """从资产详情页／资产清单页回资产管理主页面（附件任务 2.3 的返回按钮）。"""
        self.asset_detail_id=None;self.asset_roster=False
        self.show(PAGE['assets'])
    def open_asset_roster(self):
        """进「资产清单」（第 71 期任务 2）：一页看完每个角色的正典板与换状态面板。

        与详情页一样挂在「03 资产管理」下面，只是不含单张表格——清单页只摆展示，
        要改内容点每一项下面的「编辑这一项」进详情页，两页写的是同一份资产 json。
        """
        self.asset_detail_id=None;self.asset_roster=True
        self.show(PAGE['assets'])
        return True
    def asset_page(self):
        from asset_skill_batch import resume
        from asset_reference_images import prepare_folders
        resume(self);prepare_folders(self.asset_base())
        if not hasattr(self,'asset_checks'):self.asset_checks={}
        self.asset_gated_buttons=[]
        toolbar=FlowBar(self.content);toolbar.pack(fill='x',pady=(SPACING['none'],SPACING['xs']))
        # 第 31 期第 7 条：这一行的标签与下面「参考图」「资产图片」两行同宽，三行按钮左边缘对齐。
        ttk.Label(toolbar,text='资产',width=ASSET_ROW_LABEL).pack(side='left')
        def choose_all():self.asset_kind='all';self.show(PAGE['assets'])
        (PrimaryButton if self.asset_kind=='all' else SecondaryButton)(toolbar,text='全部',command=lambda:self.safe(choose_all)).pack(side='left')
        for label,kind in [('角色','characters'),('场景','scenes'),('道具','props')]:
            def choose(k=kind):self.asset_kind=k;self.show(PAGE['assets'])
            (PrimaryButton if self.asset_kind==kind else SecondaryButton)(toolbar,text=label,command=lambda fn=choose:self.safe(fn)).pack(side='left')
        b=SecondaryButton(toolbar,text='检查提示词',command=lambda:self.safe(lambda:ui_plugin_registry.module('asset_prompt_rules').check(self)));b.pack(side='left')
        b=SecondaryButton(toolbar,text='识别背景人物',command=lambda:self.safe(lambda:ui_plugin_registry.module('background_characters').show(self)));b.pack(side='left')
        # 第 31 期第 7 条：参考图／资产图片这两行的按钮挪到「资产」这一行下方，两行标签给同一个
        # 宽度，按钮左边缘对齐——它们本来就是一组资产的动作，摊在表格下面白占两行高度。
        # 第 46 期第 2 条：这两行按钮原来引用的 import_refs／open_ref_folder／delete_image／selected
        # 只长在 self.assets() 的函数体里（按钮一点就是 NameError），「导入资产图片」还把上一个
        # for 循环残留的 kind（永远是道具）当类别用。现在四件事各归各位、都走 Desktop 上的方法：
        #   参考图行＝导入（要选中）／候选图墙（要选中）／参考图目录（选中就开它那一类）
        #   资产图片行＝导入（要选中）／批量删除资产（只删勾选行）／资产目录
        # 第 55 期第 5 条：「资产目录」删掉——它与「生成图目录」打开的是同一个资产库，
        # 用户判它重复（导入图片落到资产库哪一格，右键／「生成图目录」都看得见）。
        # 第 55 期第 6 条：参考图那一行补一颗「查看参考图」——原来「查看」只藏在「参考图」
        # 那一格的单击里，入口看不出来。
        # 第 57 期第 6 条：「查看参考图」又删了——参考图那一格单击打开的就是它（同一件事两个
        # 入口，用户点名去重）；「批量删除图片」改名「批量删除资产」；「生成图目录」改名
        # 「资产目录」，改开 episode 根目录（它下面才是资产库、参考图与生成资产）。
        refs=FlowBar(self.content);refs.pack(fill='x',pady=(SPACING['none'],SPACING['xs']))
        ttk.Label(refs,text='参考图',width=ASSET_ROW_LABEL).pack(side='left')
        b=SecondaryButton(refs,text='导入参考图',command=lambda:self.safe(lambda:self.import_reference_images()));b.pack(side='left',padx=SPACING['xs'],pady=SPACING['xs']);self.asset_gated_buttons.append(b)
        b=SecondaryButton(refs,text='候选图墙',command=lambda:self.safe(lambda:ui_plugin_registry.module('reference_wall').show(self,self.require_asset_selected('先点选一项资产，再打开候选图墙'))));b.pack(side='left',padx=SPACING['xs'],pady=SPACING['xs']);self.asset_gated_buttons.append(b)
        SecondaryButton(refs,text='参考图目录',command=lambda:self.safe(lambda:self.open_reference_folder())).pack(side='left',padx=SPACING['xs'],pady=SPACING['xs'])
        imgs=FlowBar(self.content);imgs.pack(fill='x',pady=(SPACING['none'],SPACING['xs']))
        ttk.Label(imgs,text='资产图片',width=ASSET_ROW_LABEL).pack(side='left')
        b=SecondaryButton(imgs,text='导入资产图片',command=lambda:self.safe(lambda:self.asset_import(self.asset_kind,selected=self.asset_selected())));b.pack(side='left',padx=SPACING['xs'],pady=SPACING['xs']);self.asset_gated_buttons.append(b)
        # 第 57 期第 6 条：「批量删除图片」→「批量删除资产」（它删的本来就不止图片：资产图上
        # 那一行的登记一并撤掉）。
        b=SecondaryButton(imgs,text='批量删除资产',command=lambda:self.safe(lambda:self.delete_asset_images()));b.pack(side='left',padx=SPACING['xs'],pady=SPACING['xs']);self.asset_gated_buttons.append(b)
        SecondaryButton(imgs,text='恢复删除资产',command=lambda:self.safe(lambda:self.restore_asset_image(self.asset_selected()))).pack(side='left',padx=SPACING['xs'],pady=SPACING['xs'])
        def open_library():
            # 第 57 期第 6 条：「生成图目录」→「资产目录」，开的是上一级的 episode 根目录
            # （资产库、参考图、生成资产都在它下面）。
            open_path(self.asset_base())
        SecondaryButton(imgs,text='资产目录',command=lambda:self.safe(open_library)).pack(side='left',padx=SPACING['xs'],pady=SPACING['xs'])
        try:
            from stage_execution_service import import_pending_generated_assets
            imported=import_pending_generated_assets(self.root, self.asset_base(), self.status.set)
            if imported:self.status.set('已自动导入生成资产图：'+'、'.join(imported))
        except Exception as exc:
            self.note('生成图自动导入暂缓：'+str(exc))
        self.assets(self.asset_kind)
        def start_assets():
            """手动制作资产（第 59 期第 3 条）：勾到「已制作」的那几项先问一句重做不重做。

            以前这里只写一句「已跳过 N 个已导入资产」就继续：用户勾了已制作的行去点制作，界面上
            看不出它们会被跳过（只在状态行上闪一句）；现在：确认重做就把旧图移进项目回收站
            （可恢复）、资产回到待导入，批次自然会重做它；不重做就把这几项剔出来，只做剩下的。
            """
            registry=self.asset_requirements()
            controller=self.asset_page_controller(registry)
            selected=controller.checked_ids()
            made=controller.imported_ids(selected)
            if made and confirm(self.win,'重新制作资产',
                    '勾选的 %d 项已经做好了：%s\n\n要删掉旧图重做一遍吗？'
                    '（旧图移入项目回收站，可恢复）'%(len(made),'、'.join(made[:8])),
                    dangerous=True):
                for aid in made:
                    try:
                        self.delete_asset_image(aid,ask=False)
                    except (OSError,ValueError,KeyError) as exc:
                        self.note(aid+'旧图未能删除：'+str(exc))
            else:
                selected=[aid for aid in selected if aid not in made]
                if not selected:
                    self.status.set('没有要制作的资产：勾选的都已经做好了。要重做，先删掉它的资产图片。')
                    return
            ui_plugin_registry.module('asset_batch').show(self,'workflow',selected_ids=selected)
        production=FlowBar(self.content);production.pack(fill='x',pady=(SPACING['sm'],SPACING['xs']))
        # 第 32 期第 1／5 条：按钮改名「手动制作资产」，并把「手动XX」摆到最左边（左对齐）——
        # 「制图」那个行首标签去掉，按钮自己说得清是干什么的。
        # 第 47 期第 3 条：点「手动制作资产」先问一句模型配没配（没配就问要不要现在去「阶段配置」）。
        from stage_models import manual_command as _manual
        b=PrimaryButton(production,text='手动制作资产',width=STAGE_ACTION_WIDTH,command=lambda:self.safe(_manual(self,'assets',start_assets,self.win)));b.pack(side='left',padx=(SPACING['none'],SPACING['xs']),pady=SPACING['xs']);self.asset_gated_buttons.append(b);self.asset_start_button=b
        ui_plugin_registry.module('stage_flow').follow(b,'assets')       # 三虎在跑这一步就写「自动执行中」并置灰
        self.stage_button=ui_plugin_registry.module('skill_panel').stage_button(production,self,PAGE['assets']);self.stage_button.pack(side='left',padx=(SPACING['sm'],SPACING['xs']),pady=SPACING['xs'])
        # 第 65 期任务 1：这两颗从「资产图片制作」弹窗搬到「阶段配置」右边（原话：移到主界面阶段配置旁）。
        def kill_comfy_here():
            # taskkill 逐个镜像、每个最长 10 秒，按下时 ComfyUI 通常正卡着——不能在界面线程上等。
            from native_apps import force_close_comfy
            def work():
                try:return force_close_comfy(self.settings)
                except Exception as exc:return '强制关闭失败：'+str(exc)
            self.async_(work,lambda text:self.status.set(str(text)),show_progress=False,label='正在强制关闭 ComfyUI…')
        SecondaryButton(production,text='强制关闭 ComfyUI',command=lambda:self.safe(kill_comfy_here)).pack(side='left',padx=SPACING['xs'],pady=SPACING['xs'])
        def asset_records():
            folder=self.root/'workflows/Comfy资产批次';folder.mkdir(parents=True,exist_ok=True);open_path(folder)
        SecondaryButton(production,text='制作记录',command=lambda:self.safe(asset_records)).pack(side='left',padx=SPACING['xs'],pady=SPACING['xs'])
        SecondaryButton(production,text='桌面打开 ComfyUI',command=lambda:self.safe(self.launch_comfy)).pack(side='left',padx=SPACING['xs'],pady=SPACING['xs'])
        SecondaryButton(production,text='浏览器打开 ComfyUI',command=lambda:self.safe(self.open_comfy_browser)).pack(side='left',padx=SPACING['xs'],pady=SPACING['xs'])
        # 自动制作开关由三虎模式统一控制；变量保留给活动页面即时同步，初始为关闭。
        self.pet.auto_variable('auto_asset_var')
        self.update_asset_buttons()
    def comfy_listening(self,timeout=0.3):
        """本地 ComfyUI 端口上是否已有实例在听：只做 TCP 连接，不发 HTTP 请求。

        旧实现同步发一次 /system_stats 并等满 3 秒：ComfyUI 刚被拉起（端口已开、还没开始
        应答）或端口被防火墙丢包时，点「开始生成」「启动并检测」整机界面就僵住约 3 秒，
        表现出来正是「点了就卡死」。启动只关心「有没有实例在跑」，连得上就说明有；
        真正就绪与否由工作线程里的 wait_comfy 去等，不该占用界面线程。
        """
        return tcp_listener(self.settings.get('comfy_url','http://127.0.0.1:8188'), timeout=timeout)
    def launch_comfy(self,silent=False):
        # 先看端口再看桌面程序：ComfyUI 已经在跑时根本不需要程序路径，
        # 也就不该因为没配 exe 而弹出选择框拦住正在生成的用户。
        #
        # 第 62 期任务 8：silent=True 是「制作链路自动拉起」这一路——「手动制作资产」「手动
        # 制作首帧」点下去自己开始跑，这时再弹一个「选择 ComfyUI 桌面程序」会把用户从正在
        # 做的事里拽出来（用户报的就是这个）。静默这一路找不到程序就写一句人话收手，
        # 用户回头在「桌面打开 ComfyUI」那颗按钮里选一次，之后就一直静默了。
        if self.comfy_listening():
            self.status.set('ComfyUI 已在运行，无需重复启动。')
            return True
        exe=comfy_executable(self.settings)
        if exe is None:
            if silent:
                self.status.set('没找到 ComfyUI 桌面程序，本次不启动；请点“桌面打开 ComfyUI”选一次程序。')
                return False
            selected=FileDialog(self.win).open_file(title='选择 ComfyUI 桌面版程序',filetypes=[('程序','*.exe')])
            if not selected:return
            exe=Path(selected)
            from stage_execution_service import publish_desktop_preferences
            result=publish_desktop_preferences(self.settings_file,self.settings,{'comfy_exe':str(exe)})
            if not result.ok:raise ValueError(result.reason)
            self.settings=result.data
        from native_apps import open_comfy
        open_comfy({**self.settings,'comfy_exe':str(exe)})
        self.status.set('已打开本地 ComfyUI；可在桌面窗口查看工作流和调整参数。')
        return True
    def open_comfy_browser(self):
        url=self.settings.get('comfy_url','http://127.0.0.1:8188')
        open_target(url)
        self.status.set('已在浏览器打开 ComfyUI：'+url+'（若未就绪请稍后刷新，或先点“桌面打开 ComfyUI”启动服务）')
    def asset_base(self):
        # 资产库属于项目：不跟着当前选择的分镜走，工作集切到别的分镜时资产库位置必须保持稳定。
        from asset_context import library_dir
        return library_dir(self.root)
    def asset_scope(self):
        from storyboard_selection import prefs
        return 'current' if prefs(self.root).get('asset_scope')=='current' else 'adopted'
    def asset_sources(self):
        from asset_context import scope_sources
        return scope_sources(self.root,self.asset_scope())
    def asset_requirements(self):
        from stage_execution_service import sync_asset_plan
        try:return sync_asset_plan(self.root,self.asset_base(),self.asset_sources(),scope=self.asset_scope())
        except (ValueError,OSError,TypeError,AttributeError,KeyError) as e:
            # 门禁会在后台预读资产清单；剧本准备等非资产页不应因此叠出资产错误。
            if getattr(self,'page_index',None)==PAGE['assets']:
                self.note('资产清单暂未同步：'+str(e)+'。请重新采用当前项目的分镜JSON。')
            return {}
    def asset_page_controller(self,registry=None,kind=None):
        """资产页的无 Tk 筛选与勾选编排；控件状态仍由本页面持有。"""
        from asset_page_controller import AssetPageController
        if not hasattr(self,'asset_checks'):self.asset_checks={}
        root=getattr(self,'root',None)
        checks=self.asset_checks.setdefault(str(Path(root).resolve()),{}) if root is not None else {}
        selected_kind=getattr(self,'asset_kind','all') if kind is None else kind
        return AssetPageController(self.asset_requirements() if registry is None else registry,checks,selected_kind)
    def update_asset_buttons(self):
        has=bool(getattr(self,'asset_checked_count',0))
        pending=bool(getattr(self,'asset_has_pending',True))
        start=getattr(self,'asset_start_button',None)
        for button in getattr(self,'asset_gated_buttons',[]):
            if button.winfo_exists():
                enabled=has and pending if button is start else has
                button.configure(state='normal' if enabled else 'disabled')
    def assets(self,kind):
        from asset_context import ensure_browser_directory
        folder=ensure_browser_directory(self.asset_base(),kind)
        registry=self.asset_requirements()
        try:source=self.current_frame_json();episode=read(source)
        except ValueError:source=None;episode={}
        controller=self.asset_page_controller(registry)
        count=len(controller.rows())
        record=self.asset_base()/'assets/资产清单/来源.json'
        current_ids=read(record).get('asset_ids',[]) if record.is_file() else []
        used=sum(controller.matches(aid) for aid in current_ids)
        label={'scenes':'场景','characters':'角色','props':'道具','all':'全部资产'}[kind]
        scope_label={'all':'全部资产','adopted':'已采用分镜','current':'选择分镜'}[self.asset_scope()]
        used_label='本集' if self.asset_scope()=='current' else '已采用分镜'
        from storyboard_selection import summary
        self.note(f'{label} {count} 项 · {scope_label}')
        from asset_reference_prompts import display_prompt,show_prompt
        from asset_reference_images import role_summary
        table_box=ttk.Frame(self.content);table_box.pack(fill='both',expand=True,pady=SPACING['xs']);table_box.columnconfigure(0,weight=1);table_box.rowconfigure(0,weight=1)
        # 第 52 期第 3 条：「导入图片」那一列要放缩略图（value 格只能写文字，图另盖一层），
        # 行高得跟着放大——单给这张表一个样式，别的内容框照旧 34。
        # 第 53 期第 3 条：「名称」那一列不再摆图（用户判它与「导入图片」重复），只留文字；
        # 行高与样式照旧——「导入图片」那一列还要放。
        asset_columns=[('id','资产编号',130),('name','名称',230),('status','资产图片',96),
                       ('references','参考图（类目）',190),('note','外观要求',230),
                       ('prompt','资产提示词',360)]
        table_shell=DataTable(table_box,columns=asset_columns,show='tree headings',height=7,
                              style='Asset.Treeview',empty_text='暂无资产',
                              auto_hide_scrollbars=True)
        table=table_shell.tree
        fit_row_height(table,THUMB_SIZE,style='Asset.Treeview')   # 第 58 期第 2 条：行高跟着 72 像素的缩略图
        configure_check_column(table)
        # 第 52 期第 3 条：两列改名（「名称(点击修改)」→「名称」、「导入状态(点击查看)」→「导入图片」）。
        # 第 55 期第 4 条：「外观要求(点击查看)」「资产提示词(点击查看)」两列去掉「(点击查看)」
        # ——单击就能打开这件事在上一轮已经写进说明，列名越长越挤（其余列的早删干净了）。
        # 第 55 期第 6 条：「参考图」这一栏改成「参考图（类目）」：格子里写的不再只是张数，
        # 而是「几张 · 按类目各几张」——角色／场景／道具各有自己的类目（见 ROLE_GROUPS）。
        # 第 57 期第 6 条：这一栏改名「资产图片」（原来叫「导入图片」，与它上面那一行按钮同名）。
        for col,title,width in asset_columns:
            table.heading(col,text=title);table.column(col,width=width,minwidth=80,stretch=col in ('note','prompt'))
        auto_columns(table)
        table.tag_configure('completed',background=COLORS['border_default'],foreground=COLORS['success'])
        table_shell.grid(row=0,column=0,sticky='nsew')
        from responsive_ui import auto_height
        auto_height(table, table_box, row_height=ASSET_ROW_HEIGHT)      # 行高了，按 80 算，别再按 34
        self.asset_table=table          # 第 46 期第 2 条：两行按钮要问「选中／勾选了哪几行」
        self.asset_registry=registry
        checked=controller.checks
        # 第 54 期第 3 条：「导入图片」那一列盖得上缩略图就只留图，格子里的「已导入」不再显示
        # （图与字叠着用户判是多此一举）；还没导入／图解不开的照旧写原来的状态文字。
        asset_dir=self.asset_base()
        def asset_thumb(aid,size=THUMB_SIZE):
            """这一项资产已经导入的那张图的小图（路径不安全或没导入就是 None）。

            第 57 期第 5 条：多了 size 一档——鼠标停上去要放大时另解一张大图，不是把小图拉大
            （Tk 只认整数倍抽点，小图放大必然糊）。
            """
            asset=registry.get(aid) or {}
            if asset.get('status')!='已导入' or not asset.get('image'):return None
            root=asset_dir.resolve();path=(root/asset['image']).resolve()
            if path!=root and root not in path.parents:return None
            return asset_thumbs.thumbnail(self.win,path,size)
        # 第 72 期（Round 3）：分段建行。原来一口气把整份清单 insert 完，几千项的时候打开
        # 这一拍界面完全不动；现在先建够第一屏＋余量的那些（ASSET_FIRST_ROWS），剩下的按帧
        # 补（ASSET_ROWS_PER_FRAME）。界面立刻可用、列表随后长齐；中途换页或重建时令牌一过期，
        # 上一串没跑完的分片自己作废，不会往新表里插旧行。
        wanted=controller.rows()
        controller.initialize_checks()

        def insert_row(aid,asset):
            prompt=display_prompt(asset)
            # 第 55 期第 3 条：这一格要不要写字交给盖图那一层（盖上收走、撤掉写回）。
            # 原来这里为了判「有没有缩略图」把整个资产库的图都解了一遍——100 项资产就是
            # 100 张图，其中绝大多数根本不在可视区，打开这一页就卡在这儿。
            table.insert('','end',iid=aid,text='',image=self.win._tick_images[int(checked[aid])],values=(aid,asset.get('name',aid),asset['status'],role_summary(asset),asset.get('description',asset.get('reference_region','')),prompt.replace('\n',' ') if prompt else '待第1／2步补齐提示词'),tags=('completed',) if asset.get('status')=='已导入' else ())

        asset_rows_token=self.asset_rows_token=getattr(self,'asset_rows_token',0)+1
        for aid,asset in wanted[:ASSET_FIRST_ROWS]:
            insert_row(aid,asset)
        def checked_ids():
            return controller.checked_ids()
        def update_header_check():
            refresh_check_heading(table, self.win._tick_images, lambda aid: checked.get(aid,False))
        def refresh_buttons():
            self.asset_checked_count=len(checked_ids())
            self.asset_has_pending=controller.has_pending()
            self.update_asset_buttons()
            update_header_check()
        box=CheckboxColumn(table,self.win._tick_images,lambda aid:checked.get(aid,False),lambda aid,v:checked.__setitem__(aid,v),refresh_buttons)
        def toggle_asset(aid):
            box.toggle(aid)
        def toggle_all_assets():
            box.toggle_all()
        table.heading('#0',command=toggle_all_assets)
        def toggle_focus_check(event):
            aid=table.focus()
            if not aid or not table.exists(aid):
                rows=table.selection();aid=rows[0] if rows else None
            if aid:
                if table.selection()!=(aid,):table.selection_set(aid)
                toggle_asset(aid)
            return 'break'
        table.bind('<space>',toggle_focus_check,add='+')
        def preview():
            if not table.selection():raise ValueError('先在资产表中选择一项')
            asset=registry[table.selection()[0]]
            if asset['status']!='已导入':raise ValueError('该资产尚未导入图片，请先导入')
            p=(self.asset_base()/asset['image']).resolve()
            if not p.is_relative_to(self.asset_base()):raise ValueError('资产路径越界')
            open_path(p)
        def selected():return table.selection()[0] if table.selection() else None
        def detail(aid,field):
            asset=registry[aid]
            text={'name':asset.get('name',aid),'note':asset.get('description',asset.get('reference_region',''))}.get(field,'')
            win=BaseDialog(self.win,aid+' · '+('名称' if field=='name' else '外观要求'),geometry='650x340',modal=False,chrome=False)
            box=TextArea(win,wrap='word',height=10,padx=SPACING['md'],pady=SPACING['md']);box.pack(fill='both',expand=True,padx=SPACING['md'],pady=SPACING['md'])
            box.insert('1.0',text or '暂无内容');box.configure(state='disabled');bind_show_all(box)
            if field=='name':SecondaryButton(win,text='修改名称',command=lambda:(win.destroy(),self.safe(lambda:self.rename_asset(aid)))).pack(anchor='e',padx=SPACING['md'],pady=(SPACING['none'],SPACING['md']))
            # 第 64 期任务 13（附件任务 4.1）：正典板不再嵌在主页面这个弹窗里，搬进了资产详情页。
            PrimaryButton(win,text='打开资产详情页',
                          command=lambda:(win.destroy(),self.safe(lambda:self.open_asset_detail(aid)))).pack(anchor='e',padx=SPACING['md'],pady=(SPACING['none'],SPACING['md']))
        def open_cell(aid,col):
            table.selection_set(aid);table.focus(aid)
            if col=='#0':
                toggle_asset(aid);return
            if col=='#1':
                # 第 64 期任务 13：「资产编号」那一格就是进详情的入口（主页面不再嵌正典板）。
                # 走 after_idle：点这一格的是内容框自己的事件处理，等它结束再整页重建。
                self.win.after_idle(lambda:self.safe(lambda:self.open_asset_detail(aid)))
            elif col=='#2':
                def save_name(name):
                    self.rename_asset(aid,name,refresh=False)
                    registry[aid]['name']=name;table.set(aid,'name',name)
                table.cell_hover.edit_name(aid,registry[aid].get('name',aid),save_name,self.status.set,'#2')
            elif col=='#3':
                if registry[aid]['status']=='已导入':preview()
            elif col=='#4':self.view_reference_images(aid)
            elif col=='#5':detail(aid,'note')
            elif col=='#6':show_prompt(self,aid,registry[aid])
        from cell_hover import CellHover,CellImages
        import cell_hover
        link_cols=('#0','#1','#2','#3','#4','#5','#6')
        # 第 46 期第 1／9 条：同一张表上，「查看」认点中的那一格（仍先补勾选再打开，规矩没变），
        # 「删除」只认右键那一行——高亮不再兼作删除目标，逐个删与批量删从此不会互相误伤。
        # 第 57 期第 3 条：「删除」还要认「右键落在哪一列」——「参考图」那一格删的是这一项的
        # 参考图（原来一律删资产图片，用户在参考图上右键就把导入的图删了）。
        table.cell_hover=CellHover(table,link_cols,lambda aid,col:self.safe(lambda:open_cell(aid,col)),cell_image=lambda aid,col:(self.win._tick_images[int(checked.get(aid,False))] if col=='#0' else None),checked=lambda aid:checked.get(aid,False),toggle=toggle_asset,delete=lambda aid,col:self.safe(lambda:self.delete_asset_cell(aid,col)))
        bind_row_toggle(table,toggle_asset,link_cols)
        # 第 52 期第 3 条：给缩略图那一列盖一层图（#3「导入图片」只盖图）。
        # 第 53 期第 3 条：只盖 #3 一列——「名称」那一列退回原来写的文字（两列同时摆同一张
        # 图是重复，用户点名删掉「名称」列的那个图片）。
        # 没缩略图（还没导入、图不在、Tk 不认这个格式）就不盖，那一格退回原来写的文字。
        # 同一资产在本页生命周期内的缩略图（或后台占位图）是稳定的；CellImages 会在滚动时
        # 多次询问同一行，不能每一帧重复 stat／缓存查询。页面重建会自然丢弃这份映射；后台
        # 完成时会原位填充占位图，因此不需要为等待结果再重复读取。
        thumb_values={}
        def thumb_value(aid,column):
            # 第 54 期第 3 条：图与格子里的字只留一样——文字那一边在建行时就清空了，这里只管盖图。
            if aid in thumb_values:
                return thumb_values[aid]
            image=asset_thumb(aid)
            value=None if image is None else (image,'')
            thumb_values[aid]=value
            return value
        def row_background(aid):
            return COLORS['border_default'] if (registry.get(aid) or {}).get('status')=='已导入' else COLORS['background_card']
        # 第 57 期第 5 条：鼠标停在这一格上就在旁边弹一张大图（够看清人物与背景）。
        table.cell_images=CellImages(table,('#3',),thumb_value,hover=table.cell_hover,background=row_background,
                                     zoom=lambda aid,column:asset_thumb(aid,cell_hover.ZOOM_SIZE),
                                     # 750ms 让连续滚动跨过本机 Tk 的绘制抖动窗口；停止后仍会
                                     # 自动对齐新可见区，且防抖不会退化成逐帧刷新。
                                     view_refresh_delay=750)
        # 第 55 期第 1 条：「视图变了就重排」已经收进盖图那一层自己（watch_view：滚动条动了、
        # 列宽变了、内容框改了尺寸都算），这儿不必再往那两条回调末尾补一次重排。
        # 不在建页路径强制 ``update_idletasks``：它会清空同一 Tcl 解释器里不属于资产表的
        # 空闲队列，慢机上还会让后续补行定时器落进首次 ``update``，退化成首帧一次性建表。
        # CellImages 已在映射事件及自己的空闲回调中补齐覆盖层；首帧之后再按真实 bbox 盖图。
        table.cell_images.schedule_initial_refresh()
        refresh_buttons()
        # 第 72 期（Round 3）：剩下的行按帧补上，补完再重排一次缩略图那一层。
        rest=wanted[ASSET_FIRST_ROWS:]
        if rest:
            done=[0]
            row_job={'id':None}
            def cancel_more_rows(event=None):
                """资产页拆掉时撤销尚未执行的分片插行回调。"""
                if event is not None and event.widget is not table:
                    return
                job,row_job['id']=row_job['id'],None
                if job is not None:
                    try:
                        table.after_cancel(job)
                    except tk.TclError:
                        # 表格销毁后 job 已无须取消。
                        pass
            def more_rows():
                row_job['id']=None
                try:
                    alive=bool(table.winfo_exists())
                except Exception:
                    alive=False
                if not alive or getattr(self,'asset_rows_token',None)!=asset_rows_token:return
                for aid,asset in rest[done[0]:done[0]+ASSET_ROWS_PER_FRAME]:
                    insert_row(aid,asset)
                done[0]+=ASSET_ROWS_PER_FRAME
                if done[0]<len(rest):
                    # 小批次之间留出事件循环间隙。短到用户看不到停顿，长到 Tk 不会在一个
                    # 回调里把所有剩余行连续插完。
                    row_job['id']=table.after(50,more_rows)
                else:
                    # 分片完成可能正好撞上用户滚动；已有可视缩略图只需重摆，
                    # 仅为刚插入而尚未有图层的行读取 provider，不能在这一帧全量重读。
                    table.cell_images.refresh(reuse_existing=True);refresh_buttons()
            table.bind('<Destroy>',cancel_more_rows,add='+')
            # 先把计时器的创建交给首帧空闲队列：计时若从 ``show()`` 中开始，慢机的首次
            # ``update()`` 本身就可能耗尽延迟，让第二批仍落在首帧。这里只在首帧绘制已经
            # 让出事件循环后开始计时，保证首批 24 行是唯一同步工作，随后才渐进补齐。
            def arm_more_rows():
                if (getattr(self,'asset_rows_token',None)!=asset_rows_token
                        or not table.winfo_exists()):
                    return
                row_job['id']=table.after(2000,more_rows)
            row_job['id']=table.after_idle(arm_more_rows)
    # ── 第 46 期第 2／9 条：资产管理那两行按钮 + 内容框右键删除的公共实现 ────────
    # 这些活原来散在 assets() 的函数体里，页面上的按钮却摆在 assets() 外面——按下去
    # 找不到名字（NameError）。收到 Desktop 上以后，按钮、右键菜单与内容框走同一份实现。
    def asset_selected(self):
        """资产表当前点中的那一行（没高亮时退回第一个勾选行，都没有就是 None）。

        第 47 期第 1 条：查看／定位这一类是高亮优先、勾选兜底——勾了一行却没高亮时，
        点「查看参考图」不该回一句「先点选一项资产」。
        """
        table=getattr(self,'asset_table',None)
        if table is None or not table.winfo_exists():return None
        from responsive_ui import view_row
        checked=self.asset_checks.get(str(Path(self.root).resolve()),{}) if self.root is not None else {}
        return view_row(table,lambda aid: checked.get(aid,False)) or None

    def require_asset_selected(self,hint='先在资产表里点选一项资产'):
        """按钮要的那一项资产；没点选就报同一句人话（各按钮共用）。"""
        aid=self.asset_selected()
        if not aid:raise ValueError(hint)
        return aid

    def asset_checked_ids(self):
        """资产表里勾选的编号（只认勾选，不看高亮——第 46 期第 9 条的批量删除就按它来）。"""
        table=getattr(self,'asset_table',None)
        if table is None or not table.winfo_exists():return []
        return self.asset_page_controller(getattr(self,'asset_registry',{}),kind='all').checked_ids(table.get_children())

    def asset_work_ids(self):
        """批量删除／批量制作的目标（第 47 期第 1 条）：勾选优先；一个都没勾就按高亮那一行算。

        返回 (ids, 来源)：来源 'checked'／'shown'／''，文案里那句说明由 asset_work_hint 补。
        """
        table=getattr(self,'asset_table',None)
        if table is None or not table.winfo_exists():return [],''
        selected=table.selection()[0] if table.selection() else None
        return self.asset_page_controller(getattr(self,'asset_registry',{}),kind='all').work_ids(list(table.get_children()),selected)

    def asset_work_hint(self,ids,how):
        """统一口径下的一句说明（只有按高亮算的时候才有内容）。"""
        from responsive_ui import work_hint
        return work_hint(ids,how)

    def import_reference_images(self,aid=None):
        """导入参考图：给点中的那一项资产加参考图（没点选就提示先点选）。"""
        aid=aid or self.require_asset_selected('先点选一项资产，再导入参考图')
        return ui_plugin_registry.module('asset_reference_import').show(self,aid,pending=False)

    def view_reference_images(self,aid=None):
        """查看参考图（只读）：与「参考图」那一格单击同一条路。"""
        aid=aid or self.require_asset_selected('先点选一项资产，再查看参考图')
        return ui_plugin_registry.module('asset_reference_images').view_references(self,aid)

    def open_reference_folder(self,aid=None):
        """参考图目录：点选了资产就开它那一类的参考图目录，没点选就开参考图根目录。

        第 46 期第 2 条：原来按「全部／角色／场景／道具」这一档算目录，选「全部」时
        直接拿 None 去 rstrip（崩），而且开着角色页去开道具的文件夹也不合直觉。
        """
        from asset_reference_images import CATEGORIES,prepare_folders
        base=self.asset_base();prepare_folders(base)
        folder=base/'assets/参考图'
        category=CATEGORIES.get(str(aid or self.asset_selected() or '').split('_')[0])
        if category:folder=folder/category
        open_path(folder)
        return folder

    def asset_field_column(self,field):
        """资产表里某一栏的列号（'#4' 这种）：表没建起来或没有这一栏就是 None。

        第 57 期第 3 条：右键删哪一样要看「落在哪一列」，列号按字段名现算——写死 '#4' 的话，
        以后哪一栏一挪位置，删的就不是用户点的那一格了。
        """
        table=getattr(self,'asset_table',None)
        if table is None or not table.winfo_exists():return None
        columns=[str(item) for item in table['columns']]
        return '#'+str(columns.index(field)+1) if field in columns else None

    def delete_asset_cell(self,aid,column):
        """这一格右键的「删除」（第 57 期第 3 条）：落在「参考图」那一格删的是这一项的参考图，
        别的格删的才是这一项已导入的资产图片。"""
        if column==self.asset_field_column('references'):
            return self.delete_asset_references(aid)
        return self.delete_asset_image(aid)

    def delete_asset_references(self,aid,ask=True):
        """删除这一项资产的参考图（第 57 期第 3 条）：解除全部绑定，问一句再动手。

        参考图登记在「资产库/资产清单/assets.json」的 reference_images／reference_roles 里
        （与已导入的资产图片是两回事），删的时候交回 asset_reference_images.unbind——照看
        「同一个文件还绑在别的资产上」这类情况，不误删。
        """
        if not aid:raise ValueError('先在资产表里点选一项资产')
        from asset_reference_images import unbind
        base=self.asset_base()
        entry=read(base/'assets/资产清单/assets.json').get(aid,{}) or {}
        values=[value for value in entry.get('reference_images',[]) if isinstance(value,str) and value]
        values=list(dict.fromkeys(values))
        if not values:raise ValueError(aid+' 还没有参考图')
        if ask and not confirm(self.win,'删除参考图',
                '%s 的 %d 张参考图将移入项目回收站，可在需要时恢复。\n是否继续？'%(aid,len(values)),
                dangerous=True):
            return False
        unbind(base,aid,values)
        self.show(2)
        self.status.set(aid+' 的 '+str(len(values))+' 张参考图已移入回收站。')
        return True

    def delete_asset_image(self,aid,ask=True):
        """逐个删除：把这一项的已导入图片移进项目回收站，资产恢复为待导入。

        ask=False 供批量删除复用（确认框在批量那一步只弹一次）。
        """
        if not aid:raise ValueError('先在资产表里点选一项资产')
        base=self.asset_base()
        assets=read(base/'assets.json')
        entry=assets.get(aid,{})
        image=entry.get('image')
        if not image:raise ValueError('该资产尚未导入图片')
        path=(base/image).resolve()
        if not path.is_relative_to(base):raise ValueError('资产路径越界')
        if not path.is_file():raise ValueError('图片文件已不存在，请刷新列表')
        if ask and not confirm(self.win,'删除已导入图片',
                f'删除 {aid} 的已导入图片？\n{image}\n\n图片将移入项目回收站，该资产恢复为待导入。',
                dangerous=True):
            return False
        from asset_batch_service import remove_asset_image
        remove_asset_image(base,aid,gateway=Desktop.asset_batch_gateway())
        if ask:
            self.show(2)
            self.status.set(aid+' 已导入图片已删除，恢复为待导入。')
        return True

    def delete_asset_images(self):
        """批量删除：勾选的那几行；一个都没勾就按高亮那一行算（第 46 期第 9 条 ＋ 第 47 期第 1 条）。

        第 47 期第 1 条统一了「选中」的口径：高亮一行却没勾上时不再一句「请先勾选」打回去，
        而是按高亮那一行删（提示里写明），与右键的逐个删除、各页的批量删除都是同一副规矩。
        """
        ids,how=self.asset_work_ids()
        if not ids:raise ValueError('先在资产表里勾选要删除图片的资产')
        base=self.asset_base()
        assets=read(base/'assets.json')
        targets=[aid for aid in ids if assets.get(aid,{}).get('image')]
        if not targets:raise ValueError('勾选的资产都没有已导入图片')
        shown='、'.join(targets[:8])+('…' if len(targets)>8 else '')
        if not confirm(self.win,'批量删除已导入图片',
                f'删除勾选的 {len(targets)} 项资产的已导入图片？\n{shown}\n\n图片将移入项目回收站，'
                '这些资产恢复为待导入；未勾选资产不受影响。'+self.asset_work_hint(targets,how),
                dangerous=True):
            return []
        done=[]
        for aid in targets:
            try:
                if self.delete_asset_image(aid,ask=False):done.append(aid)
            except (OSError,ValueError,KeyError) as exc:
                self.note(aid+' 图片未删除：'+str(exc))
        self.show(2)
        self.status.set('已删除 %d 项资产的已导入图片（移入项目回收站，可恢复）：%s'%(len(done),'、'.join(done)))
        return done

    def restore_asset_image(self,aid,ask=True):
        """恢复当前资产最近一次删除的图片；绝不覆盖新导入的同名文件。"""
        if not aid:raise ValueError('先在资产表里点选要恢复的资产')
        base=self.asset_base().resolve()
        assets=read(base/'assets.json')
        entry=assets.get(aid,{})
        if entry.get('image'):raise ValueError(aid+' 已有导入图片，无需恢复')
        prefix=str(aid).split('_',1)[0]
        kind={'CHAR':'characters','LOC':'scenes','PROP':'props'}.get(prefix)
        if not kind:raise ValueError('资产ID格式错误，无法确定恢复目录')
        folder=(base/'assets'/kind).resolve()
        if ask and not confirm(self.win,'恢复资产图片',
                f'恢复 {aid} 的最近删除图片？'):
            return False
        from asset_batch_service import restore_asset_image
        restore_asset_image(base,aid,gateway=Desktop.asset_batch_gateway())
        self.show(PAGE['assets'])
        self.status.set(aid+' 的资产图片已从项目回收站恢复。')
        return True

    def rename_asset(self,aid,name=None,refresh=True):
        if not aid:raise ValueError('请先选择资产')
        rows=self.asset_requirements();old=rows[aid].get('name',aid)
        if name is None:name=simpledialog.askstring('修改资产名称','新的名称：',initialvalue=old,parent=self.win)
        if name is None:return
        name=name.strip()
        if not name:raise ValueError('资产名称不能为空')
        from asset_batch_service import rename_asset as _rename_asset
        _rename_asset(self.asset_base(),aid,old,name,gateway=Desktop.asset_batch_gateway())
        if refresh:self.show(2)
        self.status.set('名称已保存')
    def final_storyboard(self):
        from storyboard_files import show_final
        # 第 68 期任务 6：这一页补上了主动作「手动同步资产」，阶段配置就跟着挪到那一行
        # （原来挂在页标题右边，两处会重复），见 storyboard_files.show_final。
        show_final(self)
    def make_final_storyboard(self,source=None):
        if source is None:source=self.current_frame_json()
        if not source or not Path(source).is_file():raise ValueError('请先到第3步选择第2步生成的JSON并同步资产清单')
        from storyboard_final_controller import finalize_stage_storyboard
        if self.worker or any(getattr(v,'busy',False) for v in self.video_sessions.values()):raise ValueError('请等待当前制作任务结束后再生成定稿')
        project=self.root;episode=self.asset_base()
        def done(folder):
            # 第 47 期第 5 条：手动定稿收了尾，三虎说一句。
            self.pet_report('final',self.apply_final(project,folder))
        self.async_(lambda:finalize_stage_storyboard(project,episode,source),done)
    def apply_final(self,project,folder):
        """定稿生成后的公共收尾：刷新已打开的工作集、记住当前分镜、写偏好并重建第04步页面。

        手动「同步资产 · 生成定稿」和无人值守自动定稿共用这一份收尾，行为不会走偏。
        """
        result=read(folder/'episode.json')
        missing=len((result.get('missing_assets') or [])) if isinstance(result,dict) else 0
        if self.root is not None and Path(project)==Path(self.root):
            from storyboard_lifecycle import refresh_open_studios
            refresh_open_studios(self)
            final_source = folder / 'episode.json'
            self.remember_frame_json(final_source)
            from storyboard_selection import remember_final_view
            remember_final_view(project, final_source)
            # 只在用户本来就在第04步时重建页面：无人值守不该把人从别的页面拽走（手动按钮本来就在这一页）。
            if getattr(self,'page_index',None)==PAGE['final']:self.show(PAGE['final'])
        return 'JSON已刷新：'+str(folder)+f'；另有 {missing} 项资产待补齐。'
    def sync_working_episode(self):
        """采用分镜后，若项目还没有视频任务，把工作集指针切到最新采用的分镜。"""
        from storyboard_selection import sync_working_episode
        target=sync_working_episode(self.root)
        if target is None:return None
        if Path(self.studio.episode_path).resolve()!=target:self.studio=open_studio(self.root)
        return target
    def align_studio(self):
        """工作集跟随当前选择的分镜：切换分镜或自动采用新分镜后，后续流程不能还按旧分镜执行。

        只改内存里的工作集（不重写 config 的工作集指针），正在跑任务时不动，避免切换途中打断批次；
        新分镜暂时不合规（时长、编号、提示词等）时保留原工作集，并在状态栏写明原因。
        """
        if self.root is None:return False
        if self.worker or self.cloud_monitor_busy or any(getattr(v,'busy',False) or getattr(v,'optimizer_busy',False) for v in self.video_sessions.values()):return False
        try:source=self.current_frame_json()
        except ValueError as exc:
            self.status.set('工作集未切换：'+str(exc));return False
        if source is None:return False
        if self.studio is not None and Path(self.studio.episode_path).resolve()==Path(source).resolve():return True
        try:studio=open_studio(self.root,episode_file=source)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            self.status.set('工作集未切换：'+str(exc));return False
        self.studio=studio
        return True
    def asset_import(self,kind,initial=None,selected=None):
        base=self.asset_base()/'assets'
        p=FileDialog(self.win).open_file(initialdir=initial or (base/kind if kind!='all' else base),filetypes=[('图片','*.png *.jpg *.jpeg *.webp')])
        if not p:return
        aid=selected or simpledialog.askstring('资产编号','例如 CHAR_001 / LOC_001 / PROP_001',parent=self.win)
        if not aid:return
        from asset_batch_service import import_asset_image
        kind,result=import_asset_image(self.asset_base(),self.root,aid,p,self.asset_requirements(),gateway=Desktop.asset_batch_gateway())
        self.asset_kind=kind;self.show(PAGE['assets']);self.status.set(result)
    # 第 50 期第 1 条：原来那颗「选择镜头 JSON」删掉——首帧页看的永远是「当前分镜」，
    # 也就是第 02 步采用的那一份（自动认领见 current_frame_json），不用在这儿再挑一遍。
    def focus_missing_frame(self,source,sid):
        from storyboard_selection import focus
        focus(self.root,source)
        self.pending_frame_selection=sid
        self.show(PAGE['keyframe'])
        self.status.set(sid+' 尚无首帧，已定位到首帧管理页；请用「手动制作首帧」生成，或用「导入 / 替换选中首帧」导入图片。')
    def adopt_frame_jsons(self,paths):
        from stage_execution_service import adopt_asset_storyboards
        return adopt_asset_storyboards(self.root,paths)
    def remove_frame_jsons(self,paths):
        from stage_execution_service import remove_asset_storyboards
        return remove_asset_storyboards(self.root,paths)
    def remember_frame_json(self,path):
        return self.adopt_frame_jsons([path])
    def current_frame_json(self):
        from storyboard_selection import current_source
        episode_dir = getattr(getattr(self, 'studio', None), 'episode_dir', None)
        return current_source(
            self.root,
            legacy_sources=self.settings.get('frame_json_by_project', {}).items(),
            fallbacks=(episode_dir / 'episode.json',) if episode_dir else (),
            remember=self.remember_frame_json,
        )
    def storyboard(self):
        from keyframe_import import resume,watch_list
        from keyframe_batch import frame_prompt
        from keyframe_page_controller import KeyframePageController
        resume(self)
        source=self.current_frame_json()
        episode=read(source);base=media_root(source)
        # 第 68 期任务 12：用户报「全部分镜显示不全」。这一页原来只读当前那一份分镜；现在「选择分镜」
        # 选到「全部分镜」时，把已采用的每一份的镜头一起列出来，每一镜各自认自己那一份的目录与文件。
        # 只有一份（用户选了「只这一份」，或本来就只采用了一份）时，下面与从前一字不差。
        def load_rows():
            from storyboard_rows_service import frame_rows
            return frame_rows(self.root, source, episode, base, self.asset_scope(), self.note)
        rows=load_rows()
        page_controller=KeyframePageController(source,episode,base,rows)
        row_ctx=page_controller.row_context
        def use_rows():
            """刷新后将每个表格行重新归属到它的分镜来源。"""
            page_controller.replace_rows(rows)
        def home(shot):return page_controller.home(shot)
        def iid_of(shot):return page_controller.iid_of(shot)
        from writing import validate_episode
        validate_episode(episode,base)
        # 勾选表按行编号记账：只有一份时键就是那一份的路径（与从前同一个键），多份时合成一张。
        self._frame_checks_key=page_controller.checks_key
        self._frame_checks_merged=page_controller.merged
        if not hasattr(self,'frame_checks'):self.frame_checks={}
        checked=self.frame_checks.get(self._frame_checks_key)
        if checked is None:checked=self.frame_checks[self._frame_checks_key]=frame_checks.FrameChecks()
        def frame(shot,required=True):return page_controller.frame_path(shot,required)
        def exists(shot):return page_controller.frame_exists(shot)
        if hasattr(self,'header_status'):
            # 「全部分镜」不是一份文件：这一栏写清这一屏列的是哪几份（第 68 期任务 12）。
            total=len({str(item.resolve()) for _i,_s,item,_b,_e in rows})
            label=('全部 %d 份已采用分镜'%total) if total>1 else source.relative_to(self.root).as_posix()
            self.header_status.configure(text='当前 JSON：'+label)
            self.header_model.configure(text='镜头编号保留；点表头勾选框切换全部，单击镜头行勾选单个。')
        # 底部两行先贴底占位、内容框最后占满剩余高度，主界面缩放时按钮与下拉框始终可见。
        table_box=ttk.Frame(self.content)
        target_row=FlowBar(self.content)
        # 选中镜头一行紧贴镜头内容框下方：左侧是下拉框，右侧依次是刷新、查看与文件维护按钮。
        ttk.Label(target_row,text='选中镜头').pack(
            side='left', padx=(SPACING['none'], SPACING['sm'])
        )
        available_shots={iid:shot for iid,shot,_item,_bse,_one in rows}
        target=ttk.Combobox(target_row,state='readonly',width=19,values=list(available_shots));target.pack(
            side='left', padx=(SPACING['none'], SPACING['sm'])
        )
        if available_shots:target.current(0)
        # 第 53 期第 5 条：「图片文件」那一列要盖一层首帧缩略图（Tk 的 value 格只写得了文字），
        # 行高得跟着放大——这一张表单给一个样式，别的内容框照旧 34。
        table_shell=DataTable(table_box, columns=[
            ('id', '镜头', 155), ('title', '内容', 175), ('duration', '秒数', 60),
            ('status', '首帧状态', 120), ('file', '图片文件(点击查看)', 180),
            ('prompt', '首帧图片提示词(点击查看)', 480),
        ], show='tree headings', height=9, selectmode='browse', style='Frame.Treeview',
            auto_hide_scrollbars=True)
        table=table_shell.tree
        fit_row_height(table,THUMB_SIZE,style='Frame.Treeview')   # 第 58 期第 2 条：同上
        table_shell.grid(row=0,column=0,sticky='nsew')
        table_box.columnconfigure(0,weight=1);table_box.rowconfigure(0,weight=1)
        configure_check_column(table)
        for key,title,width in [('id','镜头',155),('title','内容',175),('duration','秒数',60),('status','首帧状态',120),('file','图片文件(点击查看)',180),('prompt','首帧图片提示词(点击查看)',480)]:
            table.heading(key,text=title);table.column(key,width=width,minwidth=50)
        table.tag_configure(
            'completed', background=COLORS['border_default'], foreground=COLORS['success']
        )
        from responsive_ui import auto_height
        auto_height(table, table_box, row_height=ASSET_ROW_HEIGHT)   # 行高了，按 80 算，别再按 34
        def fit_frame_columns():
            fit_columns_by_content(table, {'prompt': lambda w: min(540,max(360,w))})
        def selected():
            if not table.selection():raise ValueError('请先在镜头内容框中选择一行')
            return shot_row(table.selection()[0])
        box=CheckboxColumn(table,self.win._tick_images,lambda sid:checked.get(sid,False),lambda sid,v:checked.__setitem__(sid,v))
        def update_header_check():
            box.refresh_header()
        def toggle_frame(sid):
            box.toggle(sid);selection_changed()
        def toggle_all_frames():
            box.toggle_all();selection_changed()
        table.heading('#0',command=toggle_all_frames)
        def toggle_focus_check(event):
            sid=table.focus()
            if not sid or not table.exists(sid):
                rows=table.selection()
                sid=rows[0] if rows else None
            if sid:
                if table.selection()!=(sid,):table.selection_set(sid)
                toggle_frame(sid)
            return 'break'
        table.bind('<space>',toggle_focus_check,add='+')
        def selection_changed(event=None):
            valid=bool(table.selection())
            available=valid and exists(selected()) and not selected().get('frame_deleted')
            # 第 46 期第 9 条：删除按钮改成批量——它认的是勾选行，所以按勾选数决定能不能按。
            # 第 47 期第 1 条：「批量删除首帧」按统一口径亮起来——勾选优先，高亮那一行也算
            # （只有一个镜头高亮时按钮不再是灰的，点下去删的就是它，提示里会写明）。
            delete.configure(state='normal' if (page_checked() or table.selection()) else 'disabled')
            replace_button.configure(state='normal' if valid else 'disabled')
            if valid:target.set(table.selection()[0])
            update_header_check()
        def refresh():
            nonlocal rows,episode,base
            rows=load_rows()
            use_rows()
            for _i,_s,item,bse,one in rows:
                if item.resolve()==source.resolve():episode,base=one,bse;break
            previous=table.selection()
            # 重建行以前记住内容框的滚动位置：刷新或无人值守轮询重建后，内容不应跳回顶部。
            offset=0.0;top=''
            try:offset=table.yview()[0];top=table.identify_row(1)
            except tk.TclError:pass
            table.delete(*table.get_children())
            # 建行以前先按最新首帧状态对齐勾选：首帧刚就位的镜头自动取消勾选，缺首帧的新镜头默认勾选，
            # 用户手动改过的待生成镜头保持不动——无人值守轮询刷新因此不会悄悄改掉用户的批次。
            states={iid:(exists(shot) and not shot.get('frame_deleted'),bool(shot.get('frame_deleted'))) for iid,shot,_i,_b,_e in rows}
            available=sum(1 for present,_ in states.values() if present)
            checked.sync([(iid,*states[iid]) for iid in states])
            for iid,shot,_i,_b,_e in rows:
                present=states[iid][0]
                state='已导入' if present else ('待重新生成' if states[iid][1] else '待生成 / 待导入')
                # 第 54 期第 3 条：这一格盖得上缩略图就只留图——那句「图与字叠着多余」的活
                # 第 55 期第 3 条起由盖图那一层自己做（盖上收走、撤掉写回），这里照旧写文件名与「—」：
                # 原来为了判「这一格还写不写字」在这儿逐镜解一遍缩略图（几十上百镜就是几十上百张），白解。
                file_text=Path(shot['frame']).name if present else '—'
                table.insert('','end',iid=iid,text='',image=self.win._tick_images[int(checked[iid])],values=(shot['id'],shot['title'],shot['duration'],state,file_text,frame_prompt(shot).replace('\n',' ') or '待补齐首帧提示词'),tags=('completed',) if present else ())
            available_shots.clear();available_shots.update({row[0]:row[1] for row in rows})
            target.configure(values=list(available_shots))
            fit_frame_columns()
            # 第 53 期第 5 条：行重建之后格子全挪了位，缩略图那一层跟着重排一次。
            images=getattr(table,'cell_images',None)
            if images is not None:images.refresh()
            if previous and table.exists(previous[0]):table.selection_set(previous[0])
            if top and table.exists(top):table.yview_moveto(offset);table.see(top)
            selection_changed()
            # 这句话按「当下有几镜已就位」说，不按「这一次对齐新取消了几镜」——
            # 原来拿的是 sync 的增量，三虎心跳重拍本页时第二次对齐就没增量了，
            # 状态栏会被改回不带这一句的版本（第 71 期发现的偶发）。
            note=f'；其中 {available} 镜首帧已就位，已自动取消勾选' if available else ''
            self.status.set(f'现有首帧 {available} 张；待补图 {len(episode["shots"])-available} 镜'+note)
        table.grid(row=0,column=0,sticky='nsew')
        actions=FlowBar(self.content);actions.pack(
            side='bottom', fill='x', pady=SPACING['sm']
        )
        target_row.pack(
            side='bottom', fill='x', pady=(SPACING['sm'], SPACING['none'])
        )
        table_box.pack(fill='both',expand=True)
        def page_checked():
            ids=checked.checked([iid for iid,_s,_i,_b,_e in rows])
            return ids or None
        def work_targets():
            """第 47 期第 1 条：删除／制作这一类动作的目标——勾选优先，高亮兜底。

            返回 (ids, 来源)；来源为 'shown' 时说明这一行是按高亮算的（文案里由 work_hint 补一句）。
            """
            from responsive_ui import work_rows
            return work_rows(table,lambda sid: checked.get(sid,False))
        def work_hint(ids,how):
            from responsive_ui import work_hint as hint
            return hint(ids,how)
        # 第二行：最高频的生成与查看，选中镜头后即可用；首帧制作用主色按钮突出。
        # 第 47 期第 3 条：点「手动制作首帧」先问一句模型配没配（没配就问要不要现在去「阶段配置」）。
        def pick_batch():
            """「手动制作首帧」要提交的那一批：勾选的镜头，按所属分镜分堆。

            第 68 期任务 12：「全部分镜」把几份分镜合成一屏，而首帧制作是一次一份的事——所以一次
            只提交一堆（当前选中的那一堆），其余几堆说清楚让用户切过去再做，不闷声丢掉。
            """
            item,ids,rest=page_controller.pick_batch(page_checked(),table.selection())
            if not ids:return item,None
            if rest:
                self.note('「手动制作首帧」一次做一份分镜：先做 %s 那一份的 %d 镜，另有 %d 镜请切到它们那一份再生成。'
                          %(item.stem,len(ids),rest))
            return item,ids
        def make_frames():
            item,ids=pick_batch()
            return ui_plugin_registry.module('keyframe_comfy').show(self,item,ids)
        def restore_selected():
            shot=selected();item,bse,one=home(shot)
            return self.restore_keyframe(shot,one,bse,item)
        from stage_models import manual_command
        make_button=self.button(actions,'手动制作首帧',manual_command(self,'keyframe',make_frames,self.win))
        make_button.configure(style='Tokens.Primary.TButton')
        make_button.pack_configure(
            padx=(SPACING['none'], SPACING['sm']), pady=SPACING['xs']
        )
        ui_plugin_registry.module('stage_flow').follow(make_button,'keyframe')
        # 第 32 期第 6 条：这一页的阶段配置就挂在「手动制作首帧」右边。
        self.stage_button=ui_plugin_registry.module('skill_panel').stage_button(actions,self,PAGE['keyframe']);self.stage_button.pack(
            side='left', padx=(SPACING['sm'], SPACING['none'])
        )

        def secondary_action(text, action):
            """Keep the shared safe callback while applying this page's token button contract."""
            button=self.button(target_row,text,action)
            button.configure(style='Tokens.Secondary.TButton')
            button.pack_configure(
                padx=(SPACING['none'], SPACING['sm']), pady=SPACING['xs']
            )
            return button

        self.pet.auto_variable('auto_first_frame_var')
        def prompt_details():
            from prompt_window import show as show_prompt_window
            shot=selected();prompt=frame_prompt(shot)
            if not prompt:self.status.set(shot['id']+' 还没有首帧图片提示词，请先补齐后再复制')
            show_prompt_window(self.win,shot['id']+' · 首帧图片提示词',prompt,status=self.status,
                               receipt=shot['id']+' 首帧图片提示词已复制，可直接粘贴到生图或对话工具',
                               empty_text='此镜头尚未填写首帧图片提示词。',
                               empty_hint='没有可复制的首帧图片提示词，请先补齐后再复制')
        def view_frame_image(sid):
            shot=next(s for s in episode['shots'] if s['id']==sid)
            if exists(shot) and not shot.get('frame_deleted'):
                path=(base/shot['frame']).resolve()
                if path.is_file():
                    open_path(path);return
            self.status.set(sid+' 尚未导入首帧图片，可先导入或生成。')
        def open_cell(sid,col):
            table.selection_set(sid);table.focus(sid);selection_changed()
            if col=='#0':toggle_frame(sid)
            elif col=='#5':view_frame_image(sid)
            elif col=='#6':prompt_details()
        # 第 50 期第 1 条：「选择镜头 JSON」按钮按用户要求删除（上一步已经改掉文案）。
        def choose_target(event=None):
            if table.exists(target.get()):table.selection_set(target.get());table.see(target.get());selection_changed()
        target.bind('<<ComboboxSelected>>',choose_target)
        def replace(shot=None):
            shot=shot or selected();path=FileDialog(self.win).open_file(initialdir=base/'frames',filetypes=[('PNG','*.png')])
            if not path:return
            raw=Path(path).read_bytes()
            from stage_execution_service import replace_stage_keyframe
            result=replace_stage_keyframe(base,source,episode,shot,raw)
            if not result.ok:raise ValueError(result.reason)
            if source.resolve()==(self.studio.episode_dir/'episode.json').resolve():self.studio.episode=episode
            refresh();table.selection_set(iid_of(shot));selection_changed()
            self.status.set('首帧已保存为 '+shot['id']+'.png，镜头JSON已同步')
        # 选中镜头右侧：刷新与查看在前，文件维护三键在后（下行内容框改动本地图片，低频且需谨慎）。
        secondary_action('刷新首帧列表',refresh)
        secondary_action('查看首帧提示词',prompt_details)
        secondary_action('查看镜头资产',lambda:self.notifier.info(ui_plugin_registry.module('agent.shot_assets').summary(home(selected())[0],selected()).replace('；','\n'), title='镜头资产', modal=True))
        replace_button=secondary_action('导入 / 替换选中首帧',replace)
        # 第 46 期第 9 条：这颗按钮改名「批量删除首帧」——它删的是勾选那一批（高亮不算数），
        # 只想删一镜时用内容框上的右键菜单「删除」（目标就是右键那一行）。
        delete=secondary_action('批量删除首帧',lambda:delete_checked_frames())
        secondary_action('恢复删除的首帧',lambda:restore_selected())
        def shot_row(sid):
            row=row_ctx.get(sid)
            if row is None:raise ValueError('镜头已被其他操作移除，请刷新首帧列表')
            return row[0]
        def delete_one(sid):
            """逐个删除：目标就是右键（或下拉框）点中的那一镜。"""
            shot=shot_row(sid);item,bse,one=home(shot)
            self.delete_keyframe(shot,one,bse,item)
        def delete_checked_frames():
            """批量删除：勾选的那些镜头；一个都没勾就按高亮那一行算（第 47 期第 1 条）。

            已删除与没有首帧的镜头自动跳过。
            """
            wanted,how=work_targets()
            shots=[shot for iid,shot,_i,_b,_e in rows
                   if iid in set(wanted) and exists(shot) and not shot.get('frame_deleted')]
            if not shots:raise ValueError('先在镜头内容框里勾选要删除首帧的镜头')
            listed='、'.join(shot['id'] for shot in shots[:12])+('…' if len(shots)>12 else '')
            if not confirm(self.win,'批量删除首帧',
                    f'删除勾选的 {len(shots)} 镜首帧？\n{listed}\n\n图片将移入首帧回收目录，可恢复；'
                    '镜头记录、已生成视频与未勾选的镜头不受影响。'+work_hint(wanted,how),
                    dangerous=True):
                return []
            done=[]
            for shot in shots:
                item,bse,one=home(shot)
                try:
                    if self.delete_keyframe(shot,one,bse,item,ask=False,rebuild=False):done.append(shot['id'])
                except (OSError,ValueError,KeyError) as exc:
                    self.note(shot['id']+' 首帧未删除：'+str(exc))
            refresh()
            self.status.set('已删除 %d 镜首帧（移入回收站，可恢复）：%s'%(len(done),'、'.join(done)))
            return done
        table.bind('<<TreeviewSelect>>',selection_changed)
        from cell_hover import CellHover
        link_cols=('#0','#5','#6')
        # 第 46 期第 1 条：右键＝查看（这一格）／删除（这一镜的首帧）。
        # 第 55 期第 2 条：#5（图片文件）那一列盖着缩略图，不再走高亮——打勾选框那一格照旧带图。
        table.cell_hover=CellHover(table,link_cols,lambda sid,col:self.safe(lambda:open_cell(sid,col)),cell_image=lambda sid,col:(self.win._tick_images[int(checked.get(sid,False))] if col=='#0' else None),checked=lambda sid:checked.get(sid,False),toggle=toggle_frame,delete=lambda sid:self.safe(lambda:delete_one(sid)))
        bind_row_toggle(table,toggle_frame,link_cols)
        # 第 53 期第 5 条：「图片文件」那一列盖一层首帧缩略图——已导入、Tk 读得出来的才盖；
        # 还没导入／图不在／格式 Tk 不认（jpg 等）就不盖，那一格退回原来写的文件名。
        # 盖住的那一格鼠标落到这层图上，照旧转给 CellHover（单击仍是打开图片，一条没改）。
        from cell_hover import CellImages,ZOOM_SIZE
        def frame_thumb(sid,column):
            try:
                shot=shot_row(sid)
                if shot.get('frame_deleted') or not exists(shot):return None
                image=asset_thumbs.thumbnail(self.win,frame(shot,False),THUMB_SIZE)
            except (ValueError,OSError):
                return None
            return None if image is None else (image,'')
        def frame_row_background(sid):
            try:
                return COLORS['border_default'] if exists(shot_row(sid)) else COLORS['background_card']
            except (ValueError,OSError):
                return COLORS['background_card']
        def frame_zoom(sid,column):
            """鼠标停在缩略图上：另解一张大图（第 57 期第 5 条）——把 72 像素的小图拉大只会糊。"""
            try:
                shot=shot_row(sid)
                if shot.get('frame_deleted') or not exists(shot):return None
                return asset_thumbs.thumbnail(self.win,frame(shot,False),ZOOM_SIZE)
            except (ValueError,OSError):
                return None
        table.cell_images=CellImages(table,('#5',),frame_thumb,hover=table.cell_hover,
                                     background=frame_row_background,zoom=frame_zoom)
        # 第 55 期第 1 条：视图一变就重排已经收进盖图那一层（watch_view），这儿不必再交代一遍。
        refresh()
        requested=getattr(self,'pending_frame_selection',None)
        if requested and table.exists(requested):
            table.selection_set(requested);table.focus(requested);table.see(requested);selection_changed()
        self.pending_frame_selection=None
        # 第 68 期任务 12：一屏里有几份分镜就盯几份（只有一份时与从前一样，就一个）。
        for _watched in sorted({str(item.resolve()) for _i,_s,item,_b,_e in rows}):
            watch_list(table_box,Path(_watched),refresh)
    def frame_checks_apply(self,source,ids):
        """「首帧制作」弹窗提交后回写勾选：页面、下拉框与弹窗共用同一份状态，刷新即同步。"""
        # 第 68 期任务 12：「全部分镜」把几份分镜的行合成一屏，勾选表也合成一张（storyboard 里按行
        # 编号记）；这一页记着那张表的钥匙，弹窗回写就先认它。
        if getattr(self,'_frame_checks_merged',False):
            key=getattr(self,'_frame_checks_key',None) or str(Path(source).resolve())
        else:
            key=str(Path(source).resolve())
        state=self.frame_checks.get(key)
        return state.keep(ids) if state is not None else []
    def delete_keyframe(self,shot,episode=None,base=None,source=None,ask=True,rebuild=True):
        """删除一镜的首帧（移入回收站）。

        第 46 期第 9 条：ask／rebuild 两个接缝给「批量删除首帧」用——批量时确认框只弹一次、
        循环里不重建页面，逐个删除（右键／按钮）照旧走默认值。
        """
        episode=episode or self.studio.episode;base=Path(base or self.studio.episode_dir).resolve()
        path=(base/shot['frame']).resolve()
        if not path.is_file():raise ValueError('首帧已不存在，请刷新列表')
        if ask and not confirm(self.win, '删除首帧', f'删除 {shot["id"]} 的首帧图片？\n{path}\n图片进首帧回收目录，可恢复；视频和记录保留。', dangerous=True):return False
        if not path.is_relative_to(base/'frames'):raise ValueError('仅允许删除所选JSON目录下frames中的首帧')
        if any(s['id']!=shot['id'] and (base/s['frame']).resolve()==path for s in episode['shots']):raise ValueError('其他镜头也在使用此图片，请先替换它们的首帧')
        from stage_execution_service import delete_stage_keyframe
        result=delete_stage_keyframe(base,source or base/'episode.json',episode,shot)
        if not result.ok:raise ValueError(result.reason)
        if rebuild:self.show(PAGE['keyframe']);self.status.set('首帧已删除并从列表移除')
        return True
    def restore_keyframe(self,shot,episode,base,source):
        sid=shot['id']
        if not confirm(self.win, '恢复首帧', f'将恢复 {sid} 的最近回收首帧。'):return
        from stage_execution_service import restore_stage_keyframe
        result=restore_stage_keyframe(base,source,episode,shot)
        if not result.ok:raise ValueError(result.reason)
        self.show(PAGE['keyframe']);self.status.set(sid+' 首帧已恢复')
    def previs(self):
        ui_plugin_registry.module('local_previs').show(self)
    def refresh_video_workspace(self):
        current=self.video
        if current is None:return
        if current.busy:
            current.write('后台任务处理中，保留当前界面；完成后自动更新。');return
        source=self.current_frame_json().resolve()
        if current.studio.episode_path.resolve()!=source:
            self.show(PAGE['video'],video_mode=self.video_mode);return
        current.studio.episode=read(current.studio.episode_path)
        current.refresh();current.update_progress();current.next_poll=0
        current.write('镜头与首帧已刷新，当前提示词草稿保留。')
    def set_video_workspace(self,folder=None,navigate=True):
        path=self.root/'ui_settings.json'
        prefs=_prefs(path)
        if folder is None:prefs.pop('cloud_video_workspace',None)
        else:
            folder=Path(folder).resolve()
            if not folder.is_relative_to((self.root/'cloud_video').resolve()):raise ValueError('云端任务目录不在当前项目内')
            prefs['cloud_video_workspace']=folder.relative_to(self.root.resolve()).as_posix()
        from stage_execution_service import publish_cloud_video_workspace_preference
        publish_cloud_video_workspace_preference(path,prefs)
        if navigate:self.show(PAGE['video'],video_mode='cloud' if folder is not None else 'local')
    def video_home(self):
        """07 步还没选生成方式时的落地页（第 26 期第 3 条）。

        未选方式前不需要分镜，所以这一页不摆「选择分镜」；改成先确认「分镜几份、首帧够不够、
        两种方式各用哪个模型、要不要无人值守补视频」这些本来要进了工作台才知道的事——
        进去之后就不用再翻回来问，两个入口也改成主色按钮，一眼能看见。
        """
        from video_navigation import confirm_rows,local_model
        self.title.configure(text='08  视频生成 · 选择生成方式')
        # 第 48 期第 2 条：这一屏不再挂「阶段配置」——选定方式后进工作台那一步也有一颗，两处是同一件事。
        # （仍是页标题右边没有入口的页面只剩 08／09／10，见 header_stage_config。）
        # 第 38 期第 2 条：「线上走」和「API（按秒计费）」之间那个空格是整句唯一的断点，
        # 窗口一窄就把这两个词劈成两行；改成不换行空格粘住，并自己在这里断句，两种方式各占一行。
        lead=ttk.Label(self.content,text='本地走本机 ComfyUI（免费，用显卡），线上走\u00a0API（按秒计费）。\n两种都用同一份分镜与首帧；先确认下面几项，选定方式后再挑镜头。',
                       wraplength=760,justify='left',style='Muted.TLabel')
        lead.pack(anchor='w',pady=(2,8))
        # 折行交给 _fit_content_now：它按内容框的实际宽度重排所有带 wraplength 的标签。
        # 自己再绑一个 <Configure> 会和它打架——标签按被压窄后的宽度折行，越折越窄。
        facts=ttk.LabelFrame(self.content,text='开工前先确认',padding=14);facts.pack(fill='x',pady=(0,10))
        for row,(label,value) in enumerate(confirm_rows(self)):
            ttk.Label(facts,text=label,width=10).grid(row=row,column=0,sticky='nw',pady=3)
            ttk.Label(facts,text=value,wraplength=640,justify='left',style='Muted.TLabel').grid(row=row,column=1,sticky='w',pady=3)
        local=ttk.LabelFrame(self.content,text='本地生成',padding=16);local.pack(fill='x',pady=(0,10))
        ttk.Label(local,text='用本机 ComfyUI 与已安装的视频模型出片，不花云端额度；缺视频的镜头可以交给无人值守自动补。',
                  wraplength=650,justify='left',style='Muted.TLabel').pack(anchor='w')
        self.pet.auto_variable('auto_video_var')
        auto=self.auto_video_var
        state=tk.StringVar()
        def say_state():
            state.set('已开启：缺视频的镜头按顺序自动提交并取回（免费通道）' if auto.get()
                      else '未开启：进去后仍可逐个镜头手动生成')
        say_state()
        ttk.Label(local,textvariable=state,style='Muted.TLabel').pack(anchor='w',pady=(4,0))
        PrimaryButton(local,text='进入本地生成',
                   command=lambda:self.safe(lambda:self.show(PAGE['video'],video_mode='local'))).pack(anchor='w',pady=(12,0))
        cloud=ttk.LabelFrame(self.content,text='线上生成',padding=16);cloud.pack(fill='x')
        ttk.Label(cloud,text='用万相 / Seedance API 出片，按秒计费；读取第 05 步的镜头与首帧，提交前会先问一次。',
                  wraplength=650,justify='left',style='Muted.TLabel').pack(anchor='w')
        entry=FlowBar(cloud);entry.pack(fill='x',pady=(12,0))
        PrimaryButton(entry,text='进入线上生成',
                   command=lambda:self.safe(lambda:self.show(PAGE['video'],video_mode='cloud'))).pack(side='left')
        ttk.Label(entry,text='（线上接口在「阶段配置」→「接口」里配）',
                  style='Muted.TLabel').pack(side='left',padx=(8,0))
    def videos(self):
        mode=getattr(self,'video_mode',None)
        if mode is None:
            self.video_home()
            return
        self.title.configure(text='08  视频生成 · '+('线上生成' if mode=='cloud' else '本地生成'))
        from video_navigation import show_back
        show_back(self)
        top=ttk.Frame(self.content);top.pack(fill='x',pady=(0,4))
        heading=ttk.Frame(top);heading.pack(side='left',fill='both',expand=True)
        def header_note(text):
            label=ttk.Label(heading,text=text,wraplength=600,style='Muted.TLabel',font=('Microsoft YaHei UI',9));label.pack(anchor='w',fill='x',pady=1)
            label.bind('<Configure>',lambda e,w=label:w.configure(wraplength=max(160,e.width)))
        prefs_path=self.root/'ui_settings.json'
        prefs=read(prefs_path) if prefs_path.is_file() else {}
        video_root=self.root
        if mode=='cloud' and prefs.get('cloud_video_workspace'):
            candidate=(self.root/prefs['cloud_video_workspace']).resolve()
            if candidate.is_relative_to((self.root/'cloud_video').resolve()) and (candidate/'config.json').is_file():video_root=candidate
        is_cloud=video_root!=self.root
        if is_cloud and read(video_root/'config.json').get('cloud_provider')=='openai':
            header_note('原视频服务商已移除，请重新选择服务商。历史文件仍保存在项目目录。')
            self.button(self.content,'配置线上视频 API',lambda:ui_plugin_registry.module('cloud_video').settings_window(self))
            return
        if mode=='cloud' and not is_cloud:
            header_note('首次使用线上生成，请先配置服务商、模型和API Key。保存后在此页面显示镜头工作台。')
            self.button(self.content,'配置线上视频 API',lambda:ui_plugin_registry.module('cloud_video').settings_window(self))
            return
        if is_cloud:
            video_root=ui_plugin_registry.module('cloud_video').align_source(self,video_root)
            self.header_model.configure(text='当前模型：'+read(video_root/'config.json')['model'])
        from shared_video_controls import build
        build(self,heading,is_cloud)
        def prepare_video_prompt(sid):
            from agent.shot_assets import prompt_task
            final_source=self.current_frame_json()
            final_episode=read(final_source)
            final_shot=next((s for s in final_episode.get('shots',[]) if s.get('id')==sid),None)
            if final_shot is None:raise ValueError('当前分镜定稿没有此镜头，请先选择正确的镜头 JSON')
            prompt=prompt_task(final_source,final_shot,self.video.studio.cfg,output_source=self.video.studio.episode_path)
            draft=self.video.prompt.get('1.0','end').strip()
            if draft:
                prompt+='\n当前编辑框中的提示词（作为待修订素材，结合以上镜头和资产检查）：\n'+json.dumps(draft,ensure_ascii=False)
            self.open_flow_agent('final','提示词渲染阶段',prompt)
        source=self.current_frame_json()
        session_key=(str(video_root.resolve()),str(source.resolve()))
        cached=self.video_sessions.get(session_key)
        if cached:
            self.video=cached;cached.window.pack(fill='both',expand=True);cached.footer.pack(side='bottom',fill='x',pady=3)
            if not cached.busy:
                cached.studio.cfg=read(video_root/'config.json')
                cached.studio.episode=read(cached.studio.episode_path)
                cached.refresh();cached.update_progress();cached.next_poll=0
            if is_cloud:self.header_status.configure(textvariable=cached.status)
            # 第 32 期第 6 条：这一页那颗「阶段配置」跟着工作台一起复用。
            self.stage_button=getattr(cached,'stage_button',None)
            return
        panel=ttk.Frame(self.content);panel.pack(fill='both',expand=True)
        from stage_models import manual_command
        self.video=App(panel,video_root,settings_callback=(lambda:ui_plugin_registry.module('cloud_video').settings_window(self)) if is_cloud else None,prompt_callback=prepare_video_prompt,episode_file=None if is_cloud else source,missing_frame_callback=lambda sid,source=source:self.focus_missing_frame(source,sid),stage_callback=lambda:ui_plugin_registry.module('skill_panel').open_for_page(self,PAGE['video']),report_callback=self.pet_report,prompt_stage_callback=lambda:ui_plugin_registry.module('skill_panel').show(self,'final'),manual_command_factory=manual_command)
        if is_cloud:self.header_status.configure(textvariable=self.video.status)
        self.video_sessions[session_key]=self.video
        self.stage_button=getattr(self.video,'stage_button',None)
        # The shared workspace owns script/project actions.
        self.video.writing_setup=lambda:self.show(PAGE['script']);self.video.import_json=self.import_json
    def open_tts_settings(self):
        from tts_settings import show
        show(self.win)
    def current_episode(self):
        """当前分镜 JSON：配音、字幕、对白脚本共用同一个入口，不再各写一遍读文件。"""
        return read(self.current_frame_json())
    def dialogue_entries(self,episode=None):
        """对白行与「时间轴是草稿」标记；已经读过盘就把 episode 传进来，不重复读。"""
        from subtitle_timing import timed_entries
        return timed_entries(self.current_episode() if episode is None else episode)
    def dialogue_assets(self):
        """角色名 → 音色／名称的对照表（资产库）；没有或读坏都当空表。"""
        asset_file=self.asset_base()/'assets.json'
        assets=read(asset_file) if asset_file.is_file() else {}
        return assets if isinstance(assets,dict) else {}
    def generate_tts(self):
        import tts_api
        entries,estimated=self.dialogue_entries();assets=self.dialogue_assets()
        if not entries:raise ValueError('当前分镜没有对白，无法生成配音')
        script=tts_api.build_script(entries,assets)
        if len(script)>4000:raise ValueError('整集对白超过 4000 字，请改用“逐句配音（分句）”生成')
        # 整段配音一次就是一次付费请求：台词与音色都没变、文件还在时直接沿用，双击或重复点击
        # 不会再扣一次费；改台词、改模型或改音色会得到新指纹，才重新合成。
        signature=tts_api.script_signature(script)
        previous=tts_api.reusable_full_track(self.root,signature)
        if previous:
            self.status.set('配音台词与音色都没变，沿用已有配音：'+str(previous)+'（未重复扣费）');return
        def work():
            raw=tts_api.synthesize(script)
            from stage_execution_service import publish_tts_full_track
            p=publish_tts_full_track(self.root,signature,raw)
            note='配音已生成：'+str(p)
            if estimated:note+='（时间轴为草稿均分，建议在剪映中听校）'
            return note
        self.async_(work)
    def generate_tts_per_line(self):
        import tts_api
        entries,estimated=self.dialogue_entries();assets=self.dialogue_assets()
        if not entries:raise ValueError('当前分镜没有对白，无法生成配音')
        tts_settings=tts_api.read_settings()
        lines=tts_api.build_lines(entries,assets,tts_settings.get('voices'),tts_settings.get('speeds'))
        from project_stages import audio
        folder=audio(self.root)/'配音分句'
        out=tts_api.resume_folder(folder,lines);resumed=out is not None
        out=out or dated_path(folder,'配音批次')
        # 付费闸口：逐句配音按句计费，点一次会发出「待合成句数」个请求。先在点按钮时把要花多少、
        # 有多少句沿用已生成文件摊开确认，取消时一句都不提交（沿用判定与批次内部同一口径）。
        pending=tts_api.pending_lines(lines,out)
        if not pending:
            self.status.set('逐句配音：本批 '+str(len(lines))+' 句都已有成品，无需重复合成，也没有产生新费用');return
        chars=sum(len(lines[index-1].get('text') or '') for index in pending)
        tip='将向 TTS 接口提交 '+str(len(pending))+' 句（共 '+str(chars)+' 字），按用量计费。'
        if len(pending)<len(lines):tip+='\n另有 '+str(len(lines)-len(pending))+' 句沿用已生成文件，不重复扣费。'
        if not confirm(self.win, '逐句配音（付费）', tip+'\n\n继续提交？', dangerous=True):
            self.status.set('已取消逐句配音：未提交任何句子，也没有产生费用');return
        def work():
            from stage_execution_service import run_tts_lines
            ok,reused,failed=run_tts_lines(lines,out)
            note=f'逐句配音完成：成功 {ok}/{len(lines)}，失败 {failed}'
            if reused:note+=f'（沿用已生成 {reused} 句，未重复扣费）'
            if resumed:note+='；已接续上次未完成的批次'
            return note+f'；目录 {out}'
        self.async_(work)
    def open_audio_skill(self):
        from workflow_tasks import audio_prompt
        source=self.current_frame_json()
        self.open_flow_agent('audio','配音制作',audio_prompt(self.root,source))
    def audio(self):
        from stage_workspace_service import ensure_audio_workspace
        result=ensure_audio_workspace(self.root)
        if not result.ok:raise ValueError(result.reason)
        audio_dir,subtitle_dir=result.data
        self.note('可导入配音或音乐；按剧本对白时间导出整集SRT。字幕时间需在剪映中听校。')
        # 对白读不出来时不要静默禁用按钮：把原因写在页面上，用户才知道该改哪里。
        dialogue_reason=''
        try:
            entries,_=self.dialogue_entries();has_dialogue=bool(entries)
            if not has_dialogue:dialogue_reason='当前分镜没有对白，配音生成与字幕导出暂不可用。'
        except (ValueError,OSError,TypeError) as exc:
            has_dialogue=False;dialogue_reason='对白无法读取，配音生成与字幕导出暂不可用：'+str(exc)
        if dialogue_reason:
            self.note(dialogue_reason)
            # 状态栏会在换页后被覆盖；在当前页面也保留原因，避免用户只看到灰按钮。
            ttk.Label(self.content,text=dialogue_reason,style='Muted.TLabel').pack(
                anchor='w',pady=(SPACING['none'],SPACING['xs']))
        production=FlowBar(self.content);production.pack(
            fill='x',pady=(SPACING['none'],SPACING['sm']))
        ttk.Label(production,text='配音制作').pack(
            side='left',padx=(SPACING['none'],SPACING['sm']))

        def audio_button(parent,text,command,primary=False):
            """保留既有事件封装，仅将本页按钮接入设计系统。"""
            button=self.button(parent,text,command)
            button.configure(style='Tokens.Primary.TButton' if primary else 'Tokens.Secondary.TButton')
            if isinstance(parent,FlowBar):
                button.pack_configure(padx=(SPACING['none'],SPACING['sm']),pady=SPACING['xs'])
            else:
                button.pack_configure(pady=SPACING['xs'])
            return button

        from stage_models import manual_command as _manual_audio
        _audio_button=audio_button(production,'手动制作配音',
                                   _manual_audio(self,'audio',self.open_audio_skill,self.win),primary=True)
        ui_plugin_registry.module('stage_flow').follow(_audio_button,'audio')
        self.stage_button=ui_plugin_registry.module('skill_panel').stage_button(production,self,PAGE['audio'])
        self.stage_button.pack(side='left',padx=(SPACING['none'],SPACING['sm']),pady=SPACING['xs'])
        dialogue_buttons=[]
        dialogue_buttons.append(audio_button(production,'生成配音（TTS）',self.generate_tts))
        dialogue_buttons.append(audio_button(production,'逐句配音（分句）',self.generate_tts_per_line))
        audio_button(production,'配音设置',self.open_tts_settings)
        audio_button(self.content,'导入配音 / 音乐',self.import_audio)
        dialogue_buttons.append(audio_button(self.content,'导出对白字幕 SRT',lambda:open_path(self.subtitles())))
        dialogue_buttons.append(audio_button(self.content,'导出对白脚本 TXT',lambda:open_path(self.dialogue_script())))
        for button in dialogue_buttons:button.configure(state='normal' if has_dialogue else 'disabled')
        audio_button(self.content,'打开音频目录',lambda:open_path(audio_dir))
        audio_button(self.content,'打开字幕目录',lambda:open_path(subtitle_dir))
        audio_button(self.content,'打开 ElevenLabs（浏览器）',lambda:self.safe(lambda:open_target('https://elevenlabs.io/app')))
    def import_audio(self):
        from stage_workspace_service import ensure_audio_workspace
        result=ensure_audio_workspace(self.root)
        if not result.ok:raise ValueError(result.reason)
        folder,_=result.data
        p=FileDialog(self.win).open_file(initialdir=folder,filetypes=[('音频','*.wav *.mp3 *.m4a *.aac')])
        if not p:return
        from stage_execution_service import import_stage_audio
        result=import_stage_audio(self.root,p)
        if not result.ok:raise ValueError(result.reason)
        dest=result.data
        self.status.set('音频已导入：'+str(dest))
    def subtitle_rows(self):
        """按剧本对白时间算出 SRT 行；没有对白时抛 ValueError。只读文件、不碰界面，可在工作线程里用。"""
        from subtitle_timing import srt_rows
        rows,estimated=srt_rows(self.current_episode())
        if not rows:raise ValueError('当前分镜没有对白，无法导出字幕')
        return rows,estimated
    def subtitles(self):
        from stage_execution_service import export_stage_srt
        result=export_stage_srt(self.root,self.current_episode())
        if not result.ok:raise ValueError(result.reason)
        p,estimated=result.data
        if estimated:self.status.set('字幕时间按镜头时长自动均分，属草稿，请在剪映中听校。')
        return p
    def dialogue_script(self):
        """Export a readable dialogue script with speaker names and timing for dubbing."""
        from stage_execution_service import export_stage_dialogue_script
        result=export_stage_dialogue_script(self.root,self.current_episode(),self.dialogue_assets())
        if not result.ok:raise ValueError(result.reason)
        p,estimated=result.data
        if estimated:self.status.set('对白时间按镜头时长自动均分，属草稿，请在剪映中听校。')
        return p

    def editing(self):
        from editing_page_controller import EditingPageController
        from stage_workspace_service import ensure_editing_workspace
        controller = EditingPageController(self.root, self.studio)
        result=ensure_editing_workspace(self.root)
        if not result.ok:raise ValueError(result.reason)
        edit_dir,=result.data
        from stage_models import manual_command as _manual_edit
        _edit_bar=FlowBar(self.content);_edit_bar.pack(fill='x',pady=(SPACING['xs'],SPACING['xs']))
        _edit_button=PrimaryButton(_edit_bar,text='手动制作剪辑',width=STAGE_ACTION_WIDTH,
                                command=lambda:self.safe(_manual_edit(self,'edit',
                                    lambda:ui_plugin_registry.module('stage_exec').show(self,'edit'),self.win)))
        _edit_button.pack(side='left',padx=(SPACING['none'],SPACING['xs']),pady=SPACING['xs'])
        ui_plugin_registry.module('stage_flow').follow(_edit_button,'edit')
        self.stage_button=ui_plugin_registry.module('skill_panel').stage_button(_edit_bar,self,PAGE['edit'])
        self.stage_button.configure(style='Tokens.Secondary.TButton')
        self.stage_button.pack(side='left',padx=(SPACING['sm'],SPACING['xs']),pady=SPACING['xs'])
        self.note('自动粗剪只拼装已验收的镜头：未验收的镜头会被跳过并列在状态栏，不再因为个别镜头卡住整集。剪映负责精剪、音量、字幕和转场；交接包保留镜头顺序。')
        edit_buttons=[]
        def edit_button(text,command,primary=False):
            """保留共享事件封装，只让后期页采用统一的视觉组件样式。"""
            button=self.button(self.content,text,command)
            button.configure(style='Tokens.Primary.TButton' if primary else 'Tokens.Secondary.TButton')
            button.pack_configure(pady=SPACING['xs'])
            return button
        def assemble_all():return controller.assemble()
        def assembled(path):
            message=controller.assembled_message(path)
            if message:self.status.set(message)
        edit_buttons.append(edit_button('自动粗剪整集（跳过未验收镜头）',lambda:self.async_(assemble_all,assembled),primary=True))
        import project_settings
        self.pet.auto_variable('auto_edit_var')
        self.pet.auto_variable('auto_handoff_var')
        edit_buttons.append(edit_button('整理剪映素材交接包',lambda:self.async_(self.handoff,open_path)))
        has_downloaded=controller.has_downloaded_video()
        for button in edit_buttons:button.configure(state='normal' if has_downloaded else 'disabled')
        if not has_downloaded:self.note('还没有已下载的镜头视频，自动粗剪与交接包暂不可用；请先在第07步生成并下载视频。')
        edit_button('启动剪映',self.launch_editor)
        edit_button('打开后期目录',lambda:open_path(edit_dir))
        f=edit_dir/'剪辑优化清单.md'
        from file_cache import read_text
        box=self.text(read_text(f,encoding='utf-8') if f.exists() else '□ 删除多余停顿\n□ 检查对白口型\n□ 校对字幕\n□ 统一人声与环境音量\n□ 检查角色、镜头衔接\n□ 检查片头片尾和导出比例',8)
        from stage_execution_service import save_stage_editing_checklist
        edit_button('保存剪辑优化清单',lambda:save_stage_editing_checklist(self.root,box.get('1.0','end-1c')),primary=True)
    def find_editor(self):
        saved=self.settings.get('jianying','')
        candidates=[Path(saved)] if saved else []
        local=Path(os.environ.get('LOCALAPPDATA',''))
        candidates.extend([
            local/'JianyingPro/JianyingPro.exe',
            local/'Programs/JianyingPro/JianyingPro.exe',
            Path(os.environ.get('ProgramFiles','C:/Program Files'))/'JianyingPro/JianyingPro.exe',
            Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)'))/'JianyingPro/JianyingPro.exe',
        ])
        candidates.extend(sorted((local/'JianyingPro/Apps').glob('*/JianyingPro.exe'),reverse=True))
        for drive in 'CDEFG':
            candidates.append(Path(f'{drive}:/JianyingPro/JianyingPro.exe'))
        for executable in candidates:
            if executable.is_file():
                if str(executable)!=saved:
                    from stage_execution_service import publish_desktop_preferences
                    result=publish_desktop_preferences(self.settings_file,self.settings,{'jianying':str(executable)})
                    if not result.ok:raise ValueError(result.reason)
                    self.settings=result.data
                return executable
        return None
    def find_editor_shortcut(self):
        """在后台查找开始菜单中的剪映快捷方式。"""
        for root in (Path(os.environ.get('APPDATA',''))/'Microsoft/Windows/Start Menu/Programs',
                     Path(os.environ.get('PROGRAMDATA',''))/'Microsoft/Windows/Start Menu/Programs'):
            if not root.is_dir():
                continue
            for shortcut in root.glob('**/*剪映专业版*.lnk'):
                if '卸载' not in shortcut.name:
                    return shortcut
        return None
    def launch_editor(self):
        executable=self.find_editor()
        if executable is not None:
            launch_windows_app(executable, '剪映专业版')
            return
        def open_shortcut(shortcut):
            def finish():
                if shortcut is not None:
                    open_path(shortcut)
                    return
                raise ValueError('未自动找到剪映专业版。请先安装剪映，然后重新点击“启动剪映”。')
            self.safe(finish)
        self.async_(self.find_editor_shortcut,open_shortcut,
                    label='正在在开始菜单中查找剪映专业版…')
    def handoff(self,auto=False):
        st=self.studio.state();rows=[]
        for s in self.studio.episode['shots']:
            vs=list(st['shots'][s['id']] or [])
            # 与自动粗剪取同一版：优先「已下载＋质检通过＋已验收」的最后版本。取最后一版会让
            # 重新生成后还没验收的新镜头混进交接包，和成片里用的版本对不上。
            approved=approved_versions(vs)
            v=(approved or vs)[-1] if vs else {}
            if v.get('file'):rows.append((s,v))
        subtitle=None
        if len(rows)==len(self.studio.episode['shots']):
            try:
                if auto:
                    texts,_estimated=self.subtitle_rows()
                    subtitle='\n'.join(texts).encode('utf-8-sig')
                else:
                    subtitle=self.subtitles()
            except ValueError:pass  # 无对白时不附字幕，交接包仍可用
        from stage_execution_service import publish_stage_handoff_bundle
        return publish_stage_handoff_bundle(self.root, self.studio.episode['shots'], rows,
                                            subtitle, auto)
    def delivery(self):
        from stage_workspace_service import ensure_delivery_workspace
        result=ensure_delivery_workspace(self.root)
        if not result.ok:raise ValueError(result.reason)
        delivery_dir,export_dir=result.data
        from stage_models import manual_command as _manual_deliver
        _deliver_bar=FlowBar(self.content);_deliver_bar.pack(fill='x',pady=(SPACING['xs'],SPACING['xs']))
        _deliver_button=PrimaryButton(_deliver_bar,text='手动制作交付',width=STAGE_ACTION_WIDTH,
                                   command=lambda:self.safe(_manual_deliver(self,'delivery',
                                       lambda:ui_plugin_registry.module('stage_exec').show(self,'delivery'),self.win)))
        _deliver_button.pack(side='left',padx=(SPACING['none'],SPACING['xs']),pady=SPACING['xs'])
        ui_plugin_registry.module('stage_flow').follow(_deliver_button,'delivery')
        self.stage_button=ui_plugin_registry.module('skill_panel').stage_button(_deliver_bar,self,PAGE['delivery'])
        self.stage_button.configure(style='Tokens.Secondary.TButton')
        self.stage_button.pack(side='left',padx=(SPACING['sm'],SPACING['xs']),pady=SPACING['xs'])
        self.note('查看本地任务和技术质检状态，再由您确认画面、对白和剧情。这里不会查询云端任务。')
        def delivery_button(text,command,primary=False):
            """保留共享事件封装，只让交付页采用统一的视觉组件样式。"""
            button=self.button(self.content,text,command)
            button.configure(style='Tokens.Primary.TButton' if primary else 'Tokens.Secondary.TButton')
            button.pack_configure(pady=SPACING['xs'])
            return button
        from video_progress import LABELS
        st=self.studio.state();lines=[]
        for s in self.studio.episode['shots']:
            vs=st['shots'][s['id']];v=vs[-1] if vs else {}
            state=LABELS.get(v.get('state'),v.get('state') or '未提交')
            qc={True:'通过',False:'未通过'}.get(v.get('qc_pass'),'未检查')
            review={'pass':'通过','revise':'需修改'}.get(v.get('review'),'待验收')
            lines.append(f'{s["id"]}  {s["title"]}  | 状态 {state} | 技术QC {qc} | 验收 {review}')
        box=self.text('\n'.join(lines),12);box.configure(state='disabled')
        delivery_button('导入剪映最终成片',self.final_import,primary=True)
        delivery_button('打开交付目录',lambda:open_path(delivery_dir))
        delivery_button('打开自动剪辑与QC报告目录',lambda:self.open_folder(export_dir))
    def open_folder(self,p):p.mkdir(exist_ok=True);open_path(p)
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

if __name__=='__main__':
    window=tk.Tk();Desktop(window);window.mainloop()
