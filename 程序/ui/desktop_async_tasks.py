"""桌面后台任务队列与结果轮询（从 desktop.Desktop 原样迁出，SPLITD 结构治理轮）。

方法体未改、self 语义不变；Desktop 通过继承 AsyncTasksMixin 获得。仍与 Tk 控件紧耦合，
故与 desktop 同属 L4。
"""
import queue
import threading

import infra.app_logging as app_logging
from ui.desktop_page_registry import page_title


class AsyncTasksMixin:
    def async_(self,fn,done=None,show_progress=True,label=None):
        self._async_ticket+=1;ticket=self.background_tasks.submit(self._async_ticket,label=label,project=getattr(self,'root',None))
        self.worker=True
        self.busy_state.set_busy(True, message=label or '正在处理… 界面保持响应')
        def run():
            try:self.q.put((ticket,True,self.background_tasks.run(ticket,fn),done))
            except Exception as e:
                # 先交付失败结果：诊断记录自己抛错时，worker／忙碌态仍要靠这条结果复位。
                self.q.put((ticket,False,str(e),None))
                try:
                    import infra.diagnostic_capture as diagnostic_capture
                    diagnostic_capture.record_degradation(
                        e, page=page_title(getattr(self,'page_index',0)),
                        project=str(getattr(self,'root', '') or ''),
                        automatic_daily_open=bool(getattr(self,'_startup_project_choice',False)))
                except Exception:app_logging.swallowed()
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
    def _set_automation_error(self,prefix,exc):
        try:
            self.status.set(prefix+str(exc))
        except Exception:app_logging.swallowed()
    def _async_failed(self,value):
        """主后台任务失败：恢复发送框与剧本中断按钮、清掉思考气泡、弹错误。"""
        # 创意对话失败也要恢复发送框；否则一次网络错误会把唯一发送入口永久锁住。
        if getattr(self,'_idea_requesting',False):
            self.idea_chat_controller.cancel_request()
            send=getattr(self,'idea_send',None)
            if send is not None and send.winfo_exists():send.state(['!disabled'])
        self._script_agent_launching=False
        self.update_script_interrupt_button()
        self.clear_thinking()
        import contract.error_codes as error_codes;self.notifier.error(error_codes.user_text(value), title='操作未完成')
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
            was_active=self.background_tasks.accepts(ticket)
            if not self.background_tasks.finish(ticket, succeeded=ok, error='' if ok else str(value)) or ticket!=self._async_ticket:
                if was_active and ticket==self._async_ticket:
                    self.worker=False;self.busy_state.set_busy(False)
                    self.status.set('本机已停止等待；在途任务与迟到结果可在运行状况核对。')
                    self._start_next_queued()
                return
            self.worker=False;self.busy_state.set_busy(False)
            if ok and done:done(value)
            elif ok:self.status.set(str(value))
            elif not ok:self._async_failed(value)
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
