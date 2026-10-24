"""桌面换页与导航（L4，自 desktop.py 拆出的 PageNavMixin；方法体原样迁出，行为不变）。

含侧栏导航入口 go_page／go、整页缓存、show 及其前置 _show_reset_page、按页首帧耗时装饰器，以及两条页内提示。
"""
import app_logging
import page_navigation_controller as page_nav
import pet_bus
import tkinter as tk
from agent.core import read, save
from desktop_page_registry import CACHED_PAGES, PAGE, PAGE_ACCOUNT, PAGE_SITES, page_title
from desktop_page_support import _prefs
from pathlib import Path
from tkinter import ttk
from ui_tokens import DESKTOP_LAYOUT, FONTS, SPACING
from ui_widgets import SelectBox


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
        mode=page_nav.sidebar_video_mode(index,PAGE,getattr(self,'video_mode_picked',False))
        # 即刻反馈最后一次点击，包括连续点击后又回到当前页的情况。
        try:
            self.mark_nav(index)
            self.title.configure(text=page_title(index))
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
        from script_workspace_service import script_structure_signature
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
            self.stage_button=entry['stage_button']
            if entry['note']:self.status.set(entry['note'])
            return
        holder=ttk.Frame(self.canvas)
        holder.bind('<Configure>',self.fit_content)
        self.content=holder
        self.canvas.itemconfigure(self.content_id,window=holder)
        builder()
        cache[index]=page_nav.cache_entry(holder,self.root,self.stage_button,self.status.get(),str(self.root))
        if index==PAGE['script_structure']:
            from script_workspace_service import script_structure_signature
            cache[index]['signature']=script_structure_signature(self.root)
    @app_logging.timed('page.show',800)
    @_page_paint_timed
    def show(self,index,video_mode=None):
        scroll_offset, page_cache = self._show_reset_page(index, video_mode)
        if index in (PAGE_SITES,PAGE_ACCOUNT):
            (self.reference_sites if index==PAGE_SITES else self.account_page)()    # 两页都与项目无关：没打开项目也能进
            # 与普通制作页一样会在这里新增内容；不能提前返回而把 Canvas window 留在 1px 高度。
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
        choosing_video=page_nav.choosing_video(index,PAGE,getattr(self,'video_mode',None))
        def adopted_storyboards():
            from storyboard_selection import prefs
            return prefs(self.root).get('adopted_storyboards')
        if page_nav.needs_adopted_storyboard(index,PAGE,choosing_video,adopted_storyboards):
            message='请先在'+pet_bus.stage_step('storyboard')+'采用一份或多份分镜 JSON。'
            # 不能只写到底部状态栏：视频工作台被阻止时，用户的视线仍在当前内容区。
            ttk.Label(self.content,text=message,style='Muted.TLabel').pack(anchor='w',padx=SPACING['lg'],pady=SPACING['lg'])
            self.note(message)
            self.fit_content()
            return
        if page_nav.needs_source_selector(index,PAGE,choosing_video,bool(getattr(self,'asset_detail_id',None) or getattr(self,'asset_roster',False))):
            from storyboard_selection import source_selector
            source_selector(self,index,select_box=SelectBox)
        # 08／09 步直接读工作集：切换分镜或自动采用后必须先让工作集跟上，否则会按旧分镜拼接和交付。
        if index in (PAGE['edit'],PAGE['delivery']):self.align_studio()
        if index==PAGE['script'] and getattr(self.win,'_desktop_loading_project',False):
            # 自动续开原先在一个 Tk 回调中拆掉“我的项目”再同步建完整剧本页，
            # Windows 因而一直只能显示旧页。先摆出当前阶段的轻量壳，等一个
            # 确定的绘制时隙后才创建聊天、文件表和它们的绑定。
            target=self.root
            ttk.Label(self.content,text='剧本准备',font=FONTS['heading_1']).pack(anchor='w',padx=SPACING['lg'],pady=(SPACING['lg'],SPACING['sm']))
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
            self.progress.pack(fill='x',pady=(SPACING['sm'],SPACING['none']));self.status_label.pack(fill='x',pady=DESKTOP_LAYOUT['status_gap'])
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
        # 第 71 期任务 2：二级入口只在它自己那一屏高亮
        if self.asset_list_button is not None:self.asset_list_button.configure(style='Selected.Sub.Nav.TButton' if (index==PAGE['assets'] and self.asset_roster) else 'Sub.Nav.TButton')
        self.header_status.configure(text='',textvariable='');self.header_model.configure(text='');self.title.configure(text=page_title(index));self.status.set(str(self.root))
        self.stage_button=None                 # 那一行随页面重建：旧按钮这会儿已跟着 content 一起销毁
        if self.header_stage_button is not None:
            self.header_stage_button.destroy();self.header_stage_button=None    # 页标题旁那颗同理
        # 只有真正换页才回到顶部：同一页重建（切换分镜、刷新列表）保留当前位置，否则看起来就是内容抖动。
        if not scroll_offset:
            self._pending_scroll_restore=None
            self._pending_scroll_layout=None
            self.canvas.yview_moveto(0)
        return scroll_offset, page_cache
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
