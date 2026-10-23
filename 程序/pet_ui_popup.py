"""三虎弹窗节制（R1948）：有待办才弹、云朵停留随操作疏密伸缩、主动关闭后安静期逐次加长。

用户原话：「只有存在待办任务时才弹窗提醒，尽量能不弹窗就不弹窗……用户零操作时适当停留长一点，
用户任务多频繁操作时短暂停留，主动关闭减少对用户的打扰」。``Pet`` 通过继承 ``PetPopupMixin``
获得这些方法；只读内存里的台账与钟点，不读盘、不建控件。
"""
from pet_ui_support import STAGE_TODO_STATES
from ui_tokens import (PET_ACTIVITY_BUSY_COUNT, PET_ACTIVITY_WINDOW_SECONDS, PET_CLOUD_AUTO_CLOSE_MS,
                       PET_CLOUD_BUSY_CLOSE_MS, PET_CLOUD_IDLE_CLOSE_MS, PET_DISMISS_MUTE_SECONDS,
                       PET_DISMISS_WINDOW_SECONDS)


class PetPopupMixin:
    """Pet 的弹窗节制方法集（见模块说明）。"""
    def stage_has_todo(self, index):
        """R1948：换到这一页，有没有非弹不可的待办——没有就整条进页播报都不排。

        用户原话「只有存在待办任务时才弹窗提醒，尽量能不弹窗就不弹窗」。只读内存里的台账与
        阶段状态，不读盘、不碰控件：换页时先问这一句，答「没有」连定时器都不挂。
        待办只认三种：全自动档本阶段还没派发过；这一阶段压着失败待确认的项；阶段状态是
        失败／阻塞。暂停、免打扰、刚点掉云朵框的安静期里一律不算（全自动派发除外，它不是弹窗）。
        """
        stage = self.page_stage(index)
        if not stage:
            return False
        try:
            if getattr(self.agent, 'paused', False):
                return False
            if self.level() == 'auto':
                marker = (str(getattr(self.desktop, 'root', '') or ''), stage)
                if marker not in self._stage_auto_started:
                    return True
            if self.muted() or self.snoozing():
                return False
            if self.stage_failures(stage):
                return True
            return str(self.stage_states().get(stage) or '') in STAGE_TODO_STATES
        except Exception as exc:
            self.errors.append(('stage.todo', str(exc)))
            return False
    def dismissed(self, at=None):
        """R1948：用户主动点掉云朵——PET_DISMISS_WINDOW_SECONDS 里点得越勤，安静期越长。"""
        try:
            now = float(self.clock() if at is None else at)
        except (TypeError, ValueError) as exc:
            self.errors.append(('dismiss', str(exc)))
            return self.mute(at=at)
        self._dismissals = [item for item in self._dismissals if (now - item) <= PET_DISMISS_WINDOW_SECONDS]
        self._dismissals.append(now)
        steps = PET_DISMISS_MUTE_SECONDS
        return self.mute(seconds=steps[min(len(self._dismissals), len(steps)) - 1], at=now)
    def note_activity(self, at=None):
        """R1948：记一笔切页（按钮点击走 note_work）；只留 PET_ACTIVITY_WINDOW_SECONDS 内的钟点。"""
        try:
            now = float(self.clock() if at is None else at)
        except (TypeError, ValueError):
            return 0
        self._activity = [item for item in self._activity if (now - item) <= PET_ACTIVITY_WINDOW_SECONDS]
        self._activity.append(now)
        return len(self._activity)
    def cloud_dwell_ms(self, at=None):
        """R1948：云朵没人看着时停多久——用户零操作停久一点，忙着连按就短暂停留。"""
        try:
            now = float(self.clock() if at is None else at)
        except (TypeError, ValueError):
            return PET_CLOUD_AUTO_CLOSE_MS
        # 按钮点击已由 note_work 记在 _busy_taps 里，这里只补记切页那一路。
        recent = sum(1 for item in list(self._activity) + list(self._busy_taps)
                     if (now - item) <= PET_ACTIVITY_WINDOW_SECONDS)
        if recent == 0:
            return PET_CLOUD_IDLE_CLOSE_MS
        if recent >= PET_ACTIVITY_BUSY_COUNT:
            return PET_CLOUD_BUSY_CLOSE_MS
        return PET_CLOUD_AUTO_CLOSE_MS
