"""云朵气泡的提示条（HINT）方法集（从 pet_cloud.Cloud 原样迁出，R1621）。

方法体未改、self 语义不变，Cloud 通过继承 CloudHintMixin 获得；HINT_*／REPLY_HINTS 随方法迁出，
由 pet_cloud 按原名转回。仍与 Tk 控件紧耦合，故与 pet_cloud 同属 L4。
"""
import app_logging
from ui_tokens import SPACING


# 回复框为空时介绍右键菜单的主要入口。它不是命令清单：用户可以直接右键选择，也可以在此输入
# 对应指令。提示只在空框且未聚焦时出现，避免盖住输入光标。
REPLY_HINTS = '右键功能：进度面板 · 设置模型 · 切换自动化等级 · 暂停／继续 · 重试失败项 · 退出程序'
                                          # 小字比回复框再小一档，仍从设计系统辅助字号推导
HINT_MS = 420                           # 每步挪多少毫秒（第 39 期第 1 条：慢下来）
HINT_STEP_PX = 2                         # 每拍向右平移像素数：慢而连续
HINT_X = SPACING['xs']                  # 小字离回复框左沿几个像素（从最左侧起步）


class CloudHintMixin:
    # ── 回复框里那条滚动小字（第 37 期第 4 条） ─────────────────────────────
    def _focus_reply(self, _event=None):
        """提示层被点到时把焦点还给输入框，让光标立即可见。"""
        self._hint_user_focus = True
        try:
            self.reply.focus_set()
            self.reply.icursor('end')
        except Exception as exc:
            self.errors.append(('hint.focus', str(exc)))
        self._sync_hint()
        return 'break'

    def _restore_hint_after_reply(self, _event=None):
        """用户离开空输入框后，恢复右键功能说明。"""
        self._hint_user_focus = False
        self._sync_hint()

    def _hint_idle(self):
        """这会儿该不该露小字：回复框为空、且用户没有点进提示层。"""
        if self.hint is None or not self._hint_on or self.busy or not self._replies():
            return False
        try:
            return not str(self.reply.get()).strip() and not self._hint_user_focus
        except Exception:
            return False

    def _sync_hint(self):
        """按「框里有没有字」立刻摆一次小字（打字／粘贴／清空都从这里过）。"""
        if self.hint is None:
            return ''
        text = REPLY_HINTS if self._hint_idle() else ''
        try:
            self.hint.configure(text=text)
            self.hint.place_configure(x=self._hint_x)
        except Exception as exc:
            self.errors.append(('hint', str(exc)))
        return text

    def _hint_show(self):
        """把这条小字亮起来并开始滚（空下来的那一拍叫它）。"""
        if self.hint is None:
            return None
        self._hint_on = True
        self._hint_x = HINT_X
        self._sync_hint()
        return self._hint_schedule()

    def _hint_schedule(self):
        if self._hint_job is not None:
            return self._hint_job
        try:
            self._hint_job = self.parent.after(HINT_MS, self._hint_tick)
        except Exception as exc:
            self.errors.append(('hint.after', str(exc)))
            self._hint_job = None
        return self._hint_job

    def _hint_tick(self):
        """整句从左向右移动；完全离场后才从左侧重新开始。"""
        # 正常由 after 触发时，Tcl 已经取走这一次任务；但自检与主动刷新也会直接调用
        # 本方法。那种情况下旧任务仍在队列里，若只清掉标识，随后 _hint_stop() 只能撤掉
        # 新排的一次，窗口销毁后就会留下 ``invalid command name ..._hint_tick``。
        # 和 _expire 一样，先无条件回收当前登记项：正在执行的任务再次取消是安全空操作。
        job, self._hint_job = self._hint_job, None
        if job is not None:
            try:
                self.parent.after_cancel(job)
            except Exception:
                app_logging.swallowed()
        if not self._hint_on or self.hint is None:
            return None
        try:
            row_width = max(1, int(self.chat_row.winfo_width()))
        except Exception:
            row_width = 1
        self._hint_x += HINT_STEP_PX
        if self._hint_x >= row_width:
            self._hint_x = HINT_X
        self._sync_hint()
        return self._hint_schedule()

    def _hint_stop(self):
        """收起来：定时器收回、字清空（云收起了／三虎在忙着想，都不该再滚）。"""
        self._hint_on = False
        job, self._hint_job = self._hint_job, None
        if job is not None:
            try:
                self.parent.after_cancel(job)
            except Exception:
                app_logging.swallowed()
        if self.hint is not None:
            try:
                self.hint.configure(text='')
            except Exception:
                app_logging.swallowed()
        return None
