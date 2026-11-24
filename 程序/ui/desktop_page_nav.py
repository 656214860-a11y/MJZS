"""桌面换页与导航（L4，自 desktop.py 拆出的 PageNavMixin；方法体原样迁出，行为不变）。

含侧栏导航入口 go_page／go、整页缓存、show 及其前置 _show_reset_page、按页首帧耗时装饰器，以及两条页内提示。
"""
import infra.app_logging as app_logging
import desktop_shared_send
import orchestrator.page_navigation_controller as page_nav
import contract.pet_bus as pet_bus
import tkinter as tk
from agent.core import read, save
from ui.desktop_page_registry import (ASSET_ROSTER_ICON, CACHED_PAGES, PAGE, PAGE_ACCOUNT, PAGE_NAV_ICONS,
                                   PAGE_SITES, page_title)
from ui.desktop_page_support import _prefs
from pathlib import Path
from tkinter import ttk
from ui.ui_icons import IconLoader
from ui_popup import Flyout, monitor_bounds
from ui_tokens import COLORS, DESKTOP_LAYOUT, FONTS, SPACING
from ui_widgets import SecondaryButton, SelectBox, Tooltip


# 「页面第一次画完」按页指标名：用 PAGE 稳定键区分 14 页，不用会变的中文标题。
_PAGE_PAINT_KEYS = {index: stage for stage, index in PAGE.items()}
_PAGE_PAINT_KEYS[PAGE_SITES] = 'sites'
_PAGE_PAINT_KEYS[PAGE_ACCOUNT] = 'account'


def _page_paint_key(index):
    return 'page.paint.' + _PAGE_PAINT_KEYS.get(index, str(index))

def _page_paint_timed(func):
    """在 ``page.show`` 之外补记「从 show() 到该页第一次画完」的按页耗时。"""
    import functools
    @functools.wraps(func)
    def wrapper(self, index, *args, **kwargs):
        app_logging.begin_page_paint(self, _page_paint_key(index))
        # 旧页留在屏幕上直到新页排好：拆旧建新、逐轮排版都在冻结期间完成，布局稳定后一次画出。
        self.freeze_page_paint()
        try:
            return func(self, index, *args, **kwargs)
        except BaseException:
            self.thaw_page_paint()    # 建页失败不等超时：立刻放回画面，让错误提示和现场都看得见
            raise
    return wrapper


class PageNavMixin:
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
        if index==PAGE_ACCOUNT and hasattr(self,'refresh_membership_view'):self.refresh_membership_view()    # R2064：点进会员账户顺手静默续签
        mode=page_nav.sidebar_video_mode(index,PAGE,getattr(self,'video_mode_picked',False))
        # 即刻反馈最后一次点击，包括连续点击后又回到当前页的情况。
        try:
            self.mark_nav(index)
            self.set_status_segment('page',page_title(index))
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
        except Exception as exc:
            # 先记录再提示：翻页失败的原始异常事后要查得到；记录自己出错不影响提示。
            try:
                import infra.diagnostic_capture as diagnostic_capture
                diagnostic_capture.record_degradation(
                    exc, page=page_title(getattr(self,'page_index',0)),
                    project=str(getattr(self,'root', '') or ''),
                    automatic_daily_open=bool(getattr(self,'_startup_project_choice',False)))
            except Exception:app_logging.swallowed()
            import contract.error_codes as error_codes;self.notifier.error(error_codes.user_text(exc), title='页面无法显示')
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
        from domain.script_workspace_service import script_structure_signature
        for key in page_nav.stale_cache_keys(cache,index,PAGE,root=self.root,
                rebuild=same_page or not getattr(self,'_reuse_cached_page',False),
                alive=lambda entry:entry['holder'].winfo_exists(),signature=script_structure_signature):
            entry=cache.pop(key)
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
            if entry['note']:self.status.set(entry['note'])
            return
        holder=ttk.Frame(self.canvas)
        holder.bind('<Configure>',self.fit_content)
        self.content=holder
        self.canvas.itemconfigure(self.content_id,window=holder)
        builder()
        cache[index]=page_nav.cache_entry(holder,self.root,self.status.get(),str(self.root))
        if index==PAGE['script_structure']:
            from domain.script_workspace_service import script_structure_signature
            cache[index]['signature']=script_structure_signature(self.root)
    @app_logging.timed('page.show',800)
    @_page_paint_timed
    def show(self,index,video_mode=None):
        scroll_offset, page_cache = self._show_reset_page(index, video_mode)
        locks = getattr(self, 'page_lock_reasons', None)
        def adopted_storyboards():
            from orchestrator.storyboard_selection import prefs
            return prefs(self.root).get('adopted_storyboards')
        plan=page_nav.decide(index,PAGE,{
            'lock_reason':(locks().get(index) if callable(locks) and index != PAGE_ACCOUNT else ''),
            'has_root':self.root is not None,'video_mode':getattr(self,'video_mode',None),
            'adopted':adopted_storyboards,'asset_detail':getattr(self,'asset_detail_id',None),
            'asset_roster':getattr(self,'asset_roster',False),
            'loading_project':getattr(self.win,'_desktop_loading_project',False)},
            free_pages=(PAGE_SITES,PAGE_ACCOUNT),cached_pages=CACHED_PAGES)
        shared_input=getattr(self,'shared_input',None)
        if shared_input is not None and plan.route in ('locked','free','home'):
            shared_input.pack_forget()
        if plan.route=='locked':
            self.locked_page(plan.reason)       # 未登录或授权失效：免费阶段与会员页之外整页换成锁定说明
            self.fit_content()
            return
        if plan.route=='free':
            (self.reference_sites if index==PAGE_SITES else self.account_page)()    # 两页都与项目无关：没打开项目也能进
            # 与普通制作页一样会在这里新增内容；不能提前返回而把 Canvas window 留在 1px 高度。
            self.fit_content()
            return
        if plan.route=='home':
            self.set_status_segment('page','我的项目');self.status.set('选择项目开始创作');self.project_home()
            # 首屏此前在这里提前返回，项目树虽已创建却没有重新量画布；窗口刚映射时
            # content window 常仍是 1px 高，于是用户只看到白屏和底部状态栏。
            self.fit_content()
            return
        # 第 26 期第 3 条：07 步还没选生成方式时不需要分镜——「选择分镜」下拉框与那道
        # 「先采用分镜」的闸门都留到选定方式之后，选定方式那一页本来也不挑镜头。
        if plan.route=='blocked':
            message='请先在'+pet_bus.stage_step('storyboard')+'采用一份或多份分镜 JSON。'
            # 不能只写到底部状态栏：视频工作台被阻止时，用户的视线仍在当前内容区。
            ttk.Label(self.content,text=message,style='Muted.TLabel').pack(anchor='w',padx=SPACING['lg'],pady=SPACING['lg'])
            self.note(message)
            self.fit_content()
            return
        if plan.selector:
            from ui.storyboard_source_selector import source_selector
            source_selector(self,index,select_box=SelectBox)
        # 08／09 步直接读工作集：切换分镜或自动采用后必须先让工作集跟上，否则会按旧分镜拼接和交付。
        if plan.align:self.align_studio()
        if plan.route=='startup_shell':
            # 自动续开原先在一个 Tk 回调中拆掉“我的项目”再同步建完整剧本页，
            # Windows 因而一直只能显示旧页。先摆出当前阶段的轻量壳，等一个
            # 确定的绘制时隙后才创建聊天、文件表和它们的绑定。
            target=self.root
            ttk.Label(self.content,text='剧本准备',font=FONTS['heading_1']).pack(anchor='w',padx=SPACING['lg'],pady=(SPACING['lg'],SPACING['sm']))
            ttk.Label(self.content,text='正在打开剧本准备…',style='Muted.TLabel').pack(anchor='w',padx=SPACING['lg'])
            # R3056：加载提示只留在内容区标签；状态变量静默落项目路径——二次进壳与慢构建
            # 都不再把它覆盖回「正在打开…」，启动验收探针与三虎始终读到已落位的事实。
            self._set_status_quiet(str(self.root))
            self.status_bar.set_segment('path',str(self.root),tooltip=str(self.root))
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
                # R3016：路径是已知事实，先落位（StringVar 静默+底栏段），再开始慢构建；
                # 构建期间状态不再停留在「正在打开…」假加载文案。
                self._set_status_quiet(str(self.root))
                self.status_bar.set_segment('path',str(self.root),tooltip=str(self.root))
                self.writing()
                self.fit_content()
                self.pet_at_stage(PAGE['script'],automatic=True)
                self._request_tick_resume_after_first_paint()
                self._schedule_project_recovery(target)
            # 不能用 after_idle：空闲队列会在 Windows 处理首帧绘制之前继续执行，
            # 仍会把完整建页压回同一帧。40ms 给出一次实际消息循环机会。
            self._startup_script_build_job=self.win.after(40,build_startup_script_page)
            return
        if plan.route=='roster':
            # 第 71 期任务 2：侧栏「资产清单」那一格摆的是清单页（每个角色的正典板与状态变体）。
            from ui.asset_detail import show_roster
            show_roster(self)
        elif plan.route=='detail':
            # 第 64 期任务 13：资产详情页是资产管理页的子路由（附件 v3.0 任务 2.1／2.3）。
            from ui.asset_detail import show as asset_detail_page
            asset_detail_page(self,self.asset_detail_id)
        else:
            builder=[self.writing,self.script_structure,self.storyboard_creation,self.animatic_page,self.asset_page,self.continuity_page,self.final_storyboard,self.storyboard,self.previs,self.videos,self.audio,self.editing,self.delivery][index]
            if plan.cached:self._show_cached_page(index,builder,page_cache)
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
        job=getattr(self,'_pet_stage_job',None);self._pet_stage_job=None
        if job is not None:
            try:self.win.after_cancel(job)
            except tk.TclError:pass
        if not self.pet_stage_wanted(index):return   # R1948：没有待办就不弹，也不排播报
        def speak():
            self._pet_stage_job=None
            if self.page_index==index and not getattr(self,'shutting_down',False):self.pet_at_stage(index)
        # 1ms 会在布局尚未结束时到期，气泡的同步重排仍抢在首帧之前；留出短暂导航稳定期，期间再次切页会取消旧播报。
        try:self._pet_stage_job=self.win.after(150,speak)
        except tk.TclError:self._pet_stage_job=None
    def _show_reset_page(self, index, video_mode):
        """换页前置：取消待办导航、记录页码与滚动位置、视频模式偏好、清掉旧内容并刷新导航高亮，从 show 原样切出，R1809。"""
        pending=getattr(self,'_navigation_job',None)
        if pending is not None:
            self.win.after_cancel(pending)
            self._navigation_job=None
        # 换页先收掉侧栏选择浮层与项目二级列（REQ-UI-SIDEBAR-1），避免旧列表浮在新页面上。
        close_popup=getattr(self,'_close_sidebar_popup',None)
        if callable(close_popup):close_popup()
        close_expand=getattr(self,'_close_sidebar_expand',None)
        if callable(close_expand):close_expand()
        from ui.video_navigation import hide_back
        hide_back(self)
        # 同一页重建（切换分镜、刷新列表、自动流程刷新）保留原来的滚动位置：
        # 旧行为每次都把整页拉回顶部，换文件时看起来就是「内容抖动」。换页仍回到顶部。
        previous_index=getattr(self,'page_index',None)
        if previous_index==PAGE['script']:
            self._idea_brief_generation=getattr(self,'_idea_brief_generation',0)+1
            self.preserve_idea_draft()
        scroll_offset=self.canvas.canvasy(0) if previous_index==index else 0
        self.page_index=index
        self._sync_shared_input()
        # R3191（任务书 M3，D11）：页面切换不再收起文件面板，只有项目根变化时才收起；
        # 与 REQ-S01-94「页切换保持、项目切换收起」对齐，入口显隐仍随 root/page_index 同步。
        files_panel=getattr(self,'files_panel',None)
        if files_panel is not None:
            files_panel.project_changed()
        # 第 71 期任务 2：资产详情页与资产清单页都是「05 资产管理」的子路由；翻到别的页就回主页面。
        if index!=PAGE['assets']:self.asset_detail_id=None;self.asset_roster=False

        # L4-U7d：视频页也显示统一状态栏——收起它会让画布列多 43px，input_dock 的共享输入框
        # 跟着下沉、与其他页错位。工作台自带底栏（按钮/进度/日志）照留；其状态文字经
        # bind_status_segment('video', …) 并进左区分段，两条栏各管各的内容、不重复。
        self.status_bar.pack(side='top',fill='x',pady=DESKTOP_LAYOUT['status_gap'])
        if index==PAGE['video']:
            prefs_path=self.root/'ui_settings.json' if self.root else None
            prefs=_prefs(prefs_path)
            # 第 32 期第 3 条：本次启动第一次进这一页，先摆「选择生成方式」；用户在这里选过一次
            # 之后，来回切页仍按他刚选的那个模式进，不会被反复拦在选择页上。
            self.video_mode,picked,save=page_nav.next_video_mode(video_mode,getattr(self,'video_mode_picked',False),prefs.get('last_video_mode'))
            if picked!=getattr(self,'video_mode_picked',False):self.video_mode_picked=picked
            if save and prefs_path:
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
        self.mark_nav(index)
        # 第 R2946 期：资产清单不再是常驻二级钮——点「05 资产管理」图标弹选择层；
        # 清单页激活时把该图标临时换成清单字形，离开资产页即还原。
        nav_buttons=getattr(self,'nav',None)
        if nav_buttons is not None and len(nav_buttons)>PAGE['assets']:
            assets_button=nav_buttons[PAGE['assets']]
            if assets_button is not None and assets_button.winfo_exists():
                key=ASSET_ROSTER_ICON if getattr(self,'asset_roster',False) else PAGE_NAV_ICONS.get(PAGE['assets'])
                image=IconLoader.nav_icon(self.win,key)
                if image is not None:
                    assets_button.configure(image=image)
                    assets_button._nav_icon_name=key
        # R3016 P2：页标题与项目路径进统一底栏左区常驻段；页面专用段（用量摘要等）换页即清。
        # 路径另以静默方式保留在 StringVar（启动验收探针与三虎读它），不桥进右区消息。
        self.status_bar.set_segment('page',page_title(index))
        self.status_bar.set_segment('path',str(self.root),tooltip=str(self.root))
        self._set_status_quiet(str(self.root))
        self.clear_page_segments()
        self.stage_button=None                 # 那一行随页面重建：旧按钮这会儿已跟着 content 一起销毁
        if self.header_stage_button is not None:
            self.header_stage_button.destroy();self.header_stage_button=None    # 页标题旁那颗同理
        # 只有真正换页才回到顶部：同一页重建（切换分镜、刷新列表）保留当前位置，否则看起来就是内容抖动。
        if not scroll_offset:
            self._pending_scroll_restore=None
            self._pending_scroll_layout=None
            self.canvas.yview_moveto(0)
        return scroll_offset, page_cache
    def _sync_shared_input(self):
        """共享输入框跟页走（R2923：13 个阶段页共用同一实例，剧本准备页也显示）；
        非阶段页（参考网站／会员账户／首页）隐藏；锁定／免费路由由 ``show`` 再隐藏一次。"""
        shared=getattr(self,'shared_input',None)
        if shared is None:return
        stage=desktop_shared_send.stage_for_index(getattr(self,'page_index',None))
        if not stage:
            shared.pack_forget()
            return
        shared.set_stage(stage)
        if stage=='script':
            # 剧本页的「发送／终止合一」改写作用在共享发送键上：切回本页时按当前
            # 任务态重挂（任务进行中→终止图标），其余阶段已由 set_stage 复位默认。
            sync=getattr(self,'update_script_interrupt_button',None)
            if callable(sync):
                try:sync()
                except Exception:app_logging.swallowed()
        # R3060：宿主是画布列底部的 input_dock（与聊天框同宽），状态栏在 body 另一层，不再用 before。
        shared.pack(side='top',fill='x')

    def shot_numbering_hint(self):
        """编号与剧本顺序不一致时返回一句提示。只提示不自动改名：重排会改写项目里的文件名与
        文本引用，属于用户可见的改动，必须由人在 03 初步分镜 点「重排镜头编号」确认后执行。"""
        import ui.shot_numbering as shot_numbering
        try:
            # 看的是目录里全部分镜 JSON，而不是只看已采用的：编号错了要在 03 初步分镜 就发现，
            # 不必等采用之后才在下游暴露。
            from stage_execution_service import storyboard_catalog as catalog
            problems=shot_numbering.verify(self.root,[entry['path'] for entry in catalog(self.root,'storyboard')])
        except (OSError,ValueError):return ''
        return '；镜头编号与剧本顺序不一致（'+problems[0]+'），可在 '+pet_bus.stage_label('storyboard')+' 点“重排镜头编号”修正' if problems else ''
    def final_storyboard_hint(self,source=None):
        """当前分镜还是工作稿、且引用的资产都已导入时，提示可以去分镜定稿页生成定稿。

        只提示不自动做：生成定稿会把工作稿移入回收站（用户可见的改动），按约定必须由人确认。
        """
        try:source=self.current_frame_json() if source is None else source
        except (OSError,ValueError):return ''
        if not source:return ''
        from contract.storyboard_paths import is_final_dir
        if is_final_dir(Path(source).parent.name):return ''
        episode=read(source)
        shots=episode.get('shots',[]) if isinstance(episode,dict) else []
        if not shots:return ''
        if self.final_missing_assets(source):return ''
        return '；当前分镜引用的资产都已导入，可在'+pet_bus.stage_step('final')+'「分镜定稿」生成定稿（定稿接管后续流程，工作稿移入回收站）'
    def mark_nav(self,index):
        """侧栏高亮：阶段页按钮与「00 会员账户」只亮当前那一颗（R2933 起纯图标轨）。"""
        for i,b in enumerate(self.nav):b.configure(style='Selected.RailIcon.TButton' if i==index else 'RailIcon.TButton')
        account_button=getattr(self,'account_button',None)
        if account_button is not None:account_button.configure(style='Selected.RailIcon.TButton' if index==PAGE_ACCOUNT else 'RailIcon.TButton')
    # ── 侧栏图标弹出选择层（第 R2946 期）────────────────────────────────────
    # 「05 资产管理」的二级入口「资产清单」与项目分组的项目列表都走这一个弹层：
    # 无边框 Toplevel 贴在图标下方，点外部／Esc／选中即关；锚点本身的点击放行给按钮。
    def _open_sidebar_popup(self,anchor,fill,placement='below'):
        """在 ``anchor`` 旁开一层选择浮层；``fill(body)`` 负责填内容。返回 Toplevel。

        ``placement='right'``（REQ-UI-SIDEBAR-1）时贴锚点所在停靠列的右缘，
        用于「点击后在右侧展开一列隐藏图标」；摆不下时依次退到锚点左侧、再退到下方。
        """
        close_expand=getattr(self,'_close_sidebar_expand',None)
        if callable(close_expand):close_expand()
        self._close_sidebar_popup()
        top=Flyout(self.win)
        fill(top.body)
        top.update_idletasks()
        width=top.winfo_reqwidth();height=top.winfo_reqheight()
        if placement=='right':
            edge=anchor
            try:
                while edge.master is not None and edge.master is not self.win:
                    edge=edge.master
            except tk.TclError:
                edge=anchor
            x=edge.winfo_rootx()+edge.winfo_width();y=anchor.winfo_rooty()
        else:
            x=anchor.winfo_rootx();y=anchor.winfo_rooty()+anchor.winfo_height()+2
        # 钳位必须落在锚点所在显示器：winfo_screenwidth 只给主屏尺寸，
        # 主窗在副屏时旧写法会把浮层拽回主屏（R2950 修复「点了图标看不到弹层」）。
        left,stop,right,sbottom=monitor_bounds(self.win,x,y)
        if placement=='right' and x+width>right-4:
            alt=anchor.winfo_rootx()-width-2
            if alt>=left+4:x=alt
            else:x=anchor.winfo_rootx();y=anchor.winfo_rooty()+anchor.winfo_height()+2
        if x+width>right-4:x=max(left+4,right-4-width)
        if y+height>sbottom-4:y=max(stop+4,anchor.winfo_rooty()-height-2)
        top.geometry('%dx%d+%d+%d'%(width,height,x,y))
        self._sidebar_popup_win=top
        self._sidebar_popup_anchor=anchor
        # 监听挂在主窗自己的绑定上（bindtags 让主窗内所有控件的点击都经过它），不用 bind_all：
        # Tcl 的 bind 不支持按 funcid 摘除 all 标签上的单条绑定，unbind_all 会连坐别人的监听。
        # 主窗 unbind(seq, funcid) 能精确摘除；浮层内的点击根本到不了这条绑定，不会误关。
        self._popup_button_bind=self.win.bind('<Button-1>',self._sidebar_popup_outside,add='+')
        self._popup_escape_bind=self.win.bind('<Escape>',lambda event:self._close_sidebar_popup(),add='+')
        # 浮层内控件 takefocus=0，焦点留在主窗——Esc 由上面主窗那条绑定兜住，不再给浮层单独挂。
        top.bind('<Destroy>',self._sidebar_popup_destroyed)
        return top
    def _sidebar_popup_outside(self,event):
        """浮层外按下左键即关；锚点按钮与浮层内部的点击放行。"""
        top=getattr(self,'_sidebar_popup_win',None)
        if top is None:return
        try:
            if not top.winfo_exists():
                self._close_sidebar_popup();return
            widget=event.widget
            if widget is getattr(self,'_sidebar_popup_anchor',None):return
            if widget is not None and widget.winfo_toplevel() is top:return
        except (tk.TclError,AttributeError):
            self._close_sidebar_popup();return
        self._close_sidebar_popup()
    def _sidebar_popup_destroyed(self,event=None):
        """浮层被外部销毁时只清绑定，不再重复 destroy（_close 先清引用，这里自然跳过）。"""
        top=getattr(self,'_sidebar_popup_win',None)
        if top is None:return
        if event is not None and event.widget is not top:return
        button_bind=getattr(self,'_popup_button_bind',None)
        escape_bind=getattr(self,'_popup_escape_bind',None)
        self._sidebar_popup_win=None;self._sidebar_popup_anchor=None
        self._popup_button_bind=None;self._popup_escape_bind=None
        if button_bind:
            try:self.win.unbind('<Button-1>',button_bind)
            except tk.TclError:pass
        if escape_bind:
            try:self.win.unbind('<Escape>',escape_bind)
            except tk.TclError:pass
    def _close_sidebar_popup(self):
        """关掉侧栏选择浮层并摘掉点外部／Esc 监听（unbind 带 funcid，只摘自己那条）。"""
        top=getattr(self,'_sidebar_popup_win',None)
        button_bind=getattr(self,'_popup_button_bind',None)
        escape_bind=getattr(self,'_popup_escape_bind',None)
        self._sidebar_popup_win=None;self._sidebar_popup_anchor=None
        self._popup_button_bind=None;self._popup_escape_bind=None
        if button_bind:
            try:self.win.unbind('<Button-1>',button_bind)
            except tk.TclError:pass
        if escape_bind:
            try:self.win.unbind('<Escape>',escape_bind)
            except tk.TclError:pass
        if top is not None:
            try:
                if top.winfo_exists():top.destroy()
            except tk.TclError:pass
    def _assets_nav_toggle(self):
        """点「05 资产管理」图标：弹「资产清单」二级选择层；选择层开着时再点进资产管理主页。"""
        top=getattr(self,'_sidebar_popup_win',None)
        if top is not None and top.winfo_exists():
            self._close_sidebar_popup()
            # 清单页激活时再点图标要回主页面：asset_roster 不复位的话 show(assets) 仍停在清单。
            if getattr(self,'asset_roster',False):self.asset_roster=False
            self.go_page(PAGE['assets']);return
        self._open_asset_flyout()
    def _open_asset_flyout(self):
        """「05 资产管理」的二级入口「资产清单」——REQ-UI-SIDEBAR-1：点击后在侧栏右侧
        展开一列隐藏图标，与右侧文件图标列共用 ``ExpandIconColumn`` 部件。"""
        buttons=getattr(self,'nav',None)
        if buttons is None or len(buttons)<=PAGE['assets']:return
        anchor=buttons[PAGE['assets']]
        if anchor is None or not anchor.winfo_exists():return
        from ui.desktop_expand_column import ExpandIconColumn
        def fill(body):
            column=ExpandIconColumn(body,self.win,scrollbar=False,
                                    hug_height=True,keys=True)
            column.frame.pack(fill='x')
            column.add('asset_roster',ASSET_ROSTER_ICON,'','资产清单',
                       lambda:(self._close_sidebar_popup(),self.safe(self.open_asset_roster)),
                       label='资产清单')
            column.finalize()
        self._open_sidebar_popup(anchor,fill,placement='right')
    def _open_rail_settings(self):
        """图标轨末尾的设置钮（第 R2946 期）：走三虎既有设置 hub，pet.act 保持原语义。"""
        pet=getattr(self,'pet',None)
        if pet is None:return
        pet.act(pet.open_settings)
    # ── 项目分组选择层（第 R2946 期）────────────────────────────────────────
    # 「在制作／已完成」图标点了弹的项目列表；弹层基座与资产清单层共用 _open_sidebar_popup。
    def _post_project_picker(self,state=None):
        """点分组图标弹出的项目选择层：列出该组项目（● 标当前项），点项走切换确认流。

        第 R2946 期：下拉框删除，选择器改为图标下的弹层；同一分组图标再点一次收起。
        """
        state=state or getattr(self,'_project_group','making')
        button=getattr(self,'project_group_buttons',{}).get(state)
        if button is None or not button.winfo_exists():return
        # REQ-UI-SIDEBAR-1：分组钮收在按需展开的二级列里，开浮层会先把它收起；
        # 选择层统一锚在常驻的「项目」主图标上，位置才稳定。
        anchor=getattr(self,'project_button',None) or button
        top=getattr(self,'_sidebar_popup_win',None)
        if top is not None and top.winfo_exists() and getattr(self,'_sidebar_popup_anchor',None) is anchor:
            self._close_sidebar_popup();return
        items=list(getattr(self,'_picker_items',()))
        root=getattr(self,'root',None)
        def fill(body):
            if not items:
                tk.Label(body,text='该分组暂无项目',bg=COLORS['background_primary'],
                         fg=COLORS['text_secondary'],font=FONTS['body'],anchor='w',
                         padx=SPACING['sm'],pady=SPACING['xs']).pack(fill='x')
            for p in items:
                name=p.get('name') or Path(p['path']).name
                current=root is not None and Path(str(p.get('path')))==root
                row=self._popup_row(body,('● ' if current else '')+name)
                row.bind('<Button-1>',lambda event,path=p['path']:self._popup_pick_project(path))
                row.bind('<Button-3>',lambda event,item=p:self._project_item_menu(item,event))
            ttk.Separator(body).pack(fill='x',pady=(SPACING['xs'],SPACING['xs']))
            manage=self._popup_row(body,'项目管理…')
            manage.bind('<Button-1>',lambda event:self._popup_manage_projects())
        self._open_sidebar_popup(anchor,fill)
    def _popup_row(self,body,text):
        """选择层里的一行项目：tk.Label 承载，悬停换底色、单击选择、右键出项目菜单。"""
        row=tk.Label(body,text=text,bg=COLORS['background_primary'],fg=COLORS['text_primary'],
                     font=FONTS['body'],anchor='w',cursor='hand2',padx=SPACING['sm'],pady=SPACING['xs'])
        row.pack(fill='x')
        row.bind('<Enter>',lambda event,r=row:r.configure(bg=COLORS['surface_hover']))
        row.bind('<Leave>',lambda event,r=row:r.configure(bg=COLORS['background_primary']))
        return row
    def _popup_pick_project(self,path):
        """选择层里点中一个项目：先收层，再走既有的切换确认流程（取消就留在原项目）。"""
        self._close_sidebar_popup()
        if Path(path)!=self.root:self.safe(lambda:self.request_project_switch(path))
    def _popup_manage_projects(self):
        """选择层底部「项目管理…」：打开既有项目选择窗（标记完成／删除等入口都在里面）。"""
        self._close_sidebar_popup()
        self.safe(self.choose_project)
