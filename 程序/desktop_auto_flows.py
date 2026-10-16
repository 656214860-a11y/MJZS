"""桌面无人值守流程（自动定稿／粗剪／首帧／资产／视频／白模／交接／采用／云监控／下载收件箱）的轮询与收尾。

从 ``desktop.Desktop`` 原样迁出（R%d 拆分步骤 1）：方法体未改，``self`` 的语义不变，
``Desktop`` 通过继承 ``AutoFlowsMixin`` 获得这些方法。这些方法与 ``self.auto_*`` 状态、状态栏、
三虎播报紧耦合，所以放在 L4（同属桌面层），不冒充无 Tk 的 L3 服务；真正的无 Tk 调度仍由
``desktop_automation_service`` 承担。
"""
import logging
import queue
import threading
import time
from pathlib import Path

import asset_resume
import pet_state
from agent.core import read
from storyboard_paths import media_root

LOGGER = logging.getLogger(__name__)
PAGE = pet_state.PAGE_OF

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


class AutoFlowsMixin:
    """Desktop 的无人值守流程方法集（见模块说明）。"""
    def _stop_expired_auto(self, name):
        setattr(self,name+'_busy',False)
        setattr(self,name+'_due',float('inf'))
        self.status.set('本批已停止等待；请先核对运行状况和远端任务，再手动继续。')
    def _poll_auto_edit_result(self):
        self._auto_edit_result_poll_id=None
        if getattr(self,'shutting_down',False) or not getattr(self,'_startup_tick_paused',False):return
        self._drain_auto_edit_result()
        if getattr(self,'auto_edit_busy',False):self._schedule_auto_edit_result_poll()
    def _poll_auto_handoff_result(self):
        self._auto_handoff_result_poll_id=None
        if getattr(self,'shutting_down',False) or not getattr(self,'_startup_tick_paused',False):return
        self._drain_auto_handoff_result()
        if getattr(self,'auto_handoff_busy',False):self._schedule_auto_handoff_result_poll()
    def _tick_download_inbox(self):
        """每 5 秒把桌面 Agent 已下载到「下载」文件夹的目标文件收回项目（只在有登记时读盘）。"""
        now=time.monotonic()
        if self.root is None or now<getattr(self,'_download_inbox_due',0):return []
        self._download_inbox_due=now+5
        from stage_execution_service import collect_download_inbox
        try:done=collect_download_inbox(self.root)
        except (OSError, ValueError) as exc:
            LOGGER.warning('下载收件箱收回失败：%s', exc);return []
        if done:
            self.status.set('已从下载文件夹放回 '+str(len(done))+' 个文件：'+'、'.join(path.name for path in done[:3])+('…' if len(done)>3 else ''))
            if self.page_index==PAGE['script']:
                refresh=getattr(self,'refresh_script_list',None)
                if callable(refresh):refresh()
        return done
    def _poll_auto_due(self,due_name,delay,poll,*,busy_name=None,on_error,errors):
        """把自动阶段共同的到期、节流和异常处理交给无 Tk 调度器。"""
        return self.automation_scheduler.run_due(
            now=time.monotonic(), due_at=lambda:getattr(self,due_name),
            delay_seconds=delay,
            allowed=lambda:self.root is not None and not (busy_name and getattr(self,busy_name)),
            set_due=lambda value:setattr(self,due_name,value), poll=poll,
            on_error=on_error, handled_exceptions=errors)
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
                    # 收尾会重建分镜定稿页面，所以先做收尾再写状态栏，顺序反了用户就看不到结果。
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
            if not self.auto_edit_tasks.finish(ticket,succeeded=ok,on_stopped=lambda:self._stop_expired_auto('auto_edit')):return False
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
            if not self.auto_keyframe_tasks.finish(ticket,succeeded=ok,on_stopped=lambda:self._stop_expired_auto('auto_keyframe')):return
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
            if self.auto_previs_tasks.finish(ticket,succeeded=ok,on_stopped=lambda:self._stop_expired_auto('auto_previs')):self.pet_report('previs',value,ok=ok)
    def _tick_auto_asset(self):
        """处理自动补资产的消息、续跑台账、后台收尾与轮询。"""
        try:
            while True:
                ticket,text=self.auto_asset_messages.get_nowait()
                if self.auto_asset_tasks.accepts(ticket):self.status.set('自动补资产：'+text)
        except queue.Empty:pass
        try:
            ticket,ok,value,signature=self.auto_asset_queue.get_nowait()
            if not self.auto_asset_tasks.finish(ticket,succeeded=ok,on_stopped=lambda:self._stop_expired_auto('auto_asset')):return
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
            if not self.auto_video_tasks.finish(ticket,succeeded=ok,on_stopped=lambda:self._stop_expired_auto('auto_video')):return
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
            if not self.auto_handoff_tasks.finish(ticket,succeeded=ok,on_stopped=lambda:self._stop_expired_auto('auto_handoff')):return False
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
    def _tick_cloud_monitor(self):
        """处理云端任务监控结果与下一轮轮询。"""
        try:
            ticket,ok,value=self.cloud_monitor_result.get_nowait()
            if not self.cloud_monitor_tasks.finish(ticket,succeeded=ok,on_stopped=lambda:self._stop_expired_auto('cloud_monitor')):return
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
        分镜定稿页显式勾选才走；同一份工作稿只生成一次，资产没齐时在状态栏和定稿页那条提示条
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
        ticket=self.auto_edit_tasks.submit(self._auto_edit_ticket,project=getattr(self,'root',None))
        self.status.set('全部镜头已验收，正在自动粗剪整集…')
        def produce():
            path=studio.assemble()
            from stage_execution_service import save_automatic_assemble_marker
            save_automatic_assemble_marker(self.root,digest,path,time.time())
            return path
        def worker():
            # 只在工作线程里做文件与队列操作，不碰 Tk。
            try:
                path=self.auto_edit_tasks.run(ticket,produce)
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
        from previs_routing import automatic_notice, automatic_signature
        from stage_execution_service import previs_automatic_candidates, previs_automatic_engine
        try:
            frame_pending = None
            if self.pet.should_auto_run('keyframe'):
                from keyframe_comfy import pending_shots
                frame_pending = lambda rows: [shot['id'] for shot in pending_shots(rows, media_root(source))]
            candidates=previs_automatic_candidates(self.root,source,shots,bool(frame_pending),frame_pending)
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
            engine=previs_automatic_engine(self.root,current,ENGINES)
        except Exception as exc:
            self.auto_previs_signature=None;self.auto_previs_due=time.monotonic()+300
            self.auto_previs_error='白模调用设置无法读取：'+str(exc);self.status.set('无人值守自动补白模暂缓：'+str(exc));return
        self.status.set('无人值守自动补白模：使用 '+engine+' 制作 '+str(len(pending))+' 镜复杂动作…')
        try:
            from previs_automation import start
            self._auto_previs_ticket+=1
            ticket=self.auto_previs_tasks.submit(self._auto_previs_ticket,project=getattr(self,'root',None))
            start(self.root,source,pending,state,ticket=ticket,is_current=self.auto_previs_tasks.accepts,
                  execute=lambda fn:self.auto_previs_tasks.run(ticket,fn))
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
        ticket=self.auto_asset_tasks.submit(self._auto_asset_ticket,project=getattr(self,'root',None))
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
            try:self.auto_asset_queue.put((ticket,True,self.auto_asset_tasks.run(ticket,lambda:auto_batch(project,base,sources,'adopted',lambda text:self.auto_asset_log(ticket,text))),signature))
            except Exception as exc:self.auto_asset_queue.put((ticket,False,'自动补资产未完成：'+str(exc),signature))
        threading.Thread(target=worker,daemon=True).start()
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
        ticket=self.auto_video_tasks.submit(self._auto_video_ticket,project=getattr(self,'root',None))
        self.status.set('无人值守自动补视频：准备提交 '+str(len(submit))+' 镜、查询 '+str(len(poll))+' 镜…')
        studio=self.studio
        def worker():
            from local_video import auto_batch
            try:self.auto_video_queue.put((ticket,True,self.auto_video_tasks.run(ticket,lambda:auto_batch(self.root,source,lambda text:self.auto_video_log(ticket,text),studio=studio)),signature))
            except Exception as exc:self.auto_video_queue.put((ticket,False,'自动补视频未完成：'+str(exc),signature))
        threading.Thread(target=worker,daemon=True).start()
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
        ticket=self.auto_handoff_tasks.submit(self._auto_handoff_ticket,project=getattr(self,'root',None))
        self.status.set('全部镜头已验收，正在自动整理剪映素材交接包…')
        def produce():
            out=self.handoff(auto=True)
            from stage_execution_service import save_automatic_handoff_marker
            save_automatic_handoff_marker(self.root,digest,out,len(studio.episode['shots']))
            return out
        def worker():
            try:
                out=self.auto_handoff_tasks.run(ticket,produce)
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
        ticket=self.cloud_monitor_tasks.submit(self._cloud_monitor_ticket,project=getattr(self,'root',None))
        def work():
            try:
                from local_video import open_studio
                studio=open_studio(root)
                result=self.cloud_monitor_tasks.run(ticket,lambda:studio.poll(sid))
                self.cloud_monitor_result.put((ticket,True,result))
            except Exception as exc:self.cloud_monitor_result.put((ticket,False,str(exc)))
        threading.Thread(target=work,daemon=True).start()
