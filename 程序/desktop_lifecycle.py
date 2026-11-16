"""桌面窗口生命周期（L4，自 desktop.py 拆出的 LifecycleMixin；方法体原样迁出，行为不变）。

含定时器收回、窗口销毁清理、强制关闭、收摊与项目列表刷新。close 留在 desktop.py（确认框按 desktop.confirm 取，测试按该名打补丁）。
"""
import logging
import app_logging
import asset_thumbs
import orchestrator.page_navigation_controller as page_nav
import tkinter as tk

LOGGER = logging.getLogger(__name__)


class LifecycleMixin:
    def cancel_timers(self,event=None):
        # 先停掉定时器再销毁窗口：残留的 after 回调会在 Tk 里报 invalid command name。
        if event is not None and event.widget is not self.win:return
        self.shutting_down=True;self.cancel_resize()
        cancel=lambda job:self.win.after_cancel(job)    # 惰性取 win：最小替身没有登记任务时不会碰它
        page_nav.cancel_jobs(self,page_nav.NAV_TIMER_JOBS,cancel,tk.TclError)
        # 计时器回归会构造最小 Desktop 替身；真实窗口在 __init__ 中必定拥有这些
        # 生命周期登记器，但关闭路径也必须兼容尚未完成初始化的窗口。
        page_nav.cancel_lifecycles(self)
        # ``fit_content`` 的空闲布局任务属于桌面窗口；若关闭发生在首帧／重建之间，
        # 必须在销毁 Tcl 回调前取消，否则会留下 ``...run`` 的 after 噪声。
        page_nav.cancel_jobs(self,('_fit_job',),cancel,tk.TclError)
        self._fit_pending=False
        self._fit_again=False
        page_nav.cancel_jobs(self,page_nav.STARTUP_TIMER_JOBS,cancel,tk.TclError)
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
    def force_quit(self):
        """强制关闭（第 47 期第 7 条）：先把还在跑的引擎进程与白模批次收掉，再照常收摊。

        收不干净也照样退：这几件事都是尽力而为，用户要的是「关得掉」，不是「等它跑完」。
        """
        self._forcing_quit=True
        state=getattr(self,'previs_jobs',None)
        if isinstance(state,dict) and state.get('busy'):
            try:
                from orchestrator.previs_automation import force_stop
                force_stop(self.root,state)
            except Exception as exc:
                LOGGER.warning('强制关闭：白模批次未收干净（%s）', exc)
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
            from orchestrator.workflow_engines import terminate
            killed=terminate(self.root)
        except Exception as exc:
            LOGGER.warning('关闭：引擎进程未收干净（%s）', exc)
            return []
        self.flow_processes={}
        return killed
    def finish_close(self):
        """真的收摊：停表、停监视页、销毁窗口、清一次缓存（第 18 期从 close 里拆出来）。"""
        self.close_tray()
        self.cancel_timers()
        # 未标记 busy 的已派发任务也随程序退出，避免后台模型留存并拖慢下一次启动。
        self.stop_automation_processes()
        # 第 47 期第 2 条：白模那个浏览器监视页跟着程序一起收，端口不留着。
        state=getattr(self,'previs_jobs',None)
        if isinstance(state,dict) and state.get('monitor'):
            try:
                from orchestrator.previs_monitor import stop as stop_monitor
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
        from orchestrator.exit_maintenance import launch_cleanup
        launch_cleanup(self.app, forced=getattr(self, '_forcing_quit', False))
    def reload(self):
        self._sync_project_picker()
        self.refresh_sidebar_title()
        self.schedule_sidebar_fit()
        tree=getattr(self,'_project_home_tree',None)
        if tree is not None and tree.winfo_exists():self.fill_projects(tree)
    def flush_brief(self):
        """第 65 期任务 9：翻页只丢引用，不再自动另存——对话结束前一个字都不落盘。

        原来翻页会把创意栏里改过的字偷偷存成一份 创意_ 文件；现在这一页是跟模型对话，
        落盘只有一条路：模型回复设定／大纲／角色卡／剧本时自动存档，见 auto_save_script_reply。
        """
        self.preserve_idea_draft()
        self.brief_editor=None
