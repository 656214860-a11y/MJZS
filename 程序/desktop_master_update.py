"""总控包更新提示（L4，只放弹窗与回调注入）。

检测、比对、下载覆盖都在 ``master_skill_update``；本 Mixin 首帧后在独立线程里检查一次
（沿用账号页的 ``_account_background``：不占独占后台、不写状态栏），有新版本才弹确认窗，
用户点“确定”后才经 ``async_queued`` 下载覆盖并同步当前项目。自动检查联网失败静默；
阶段配置页总控下拉框的“检查更新”走 ``manual=True``，无更新、失败也会明确告知。
"""
import master_skill_update
from ui_widgets import ask_confirmation


class MasterUpdateMixin:
    def start_master_update_check(self, manual=False):
        """首帧后自动检查一次（每次启动至多弹一次）；``manual=True`` 是用户主动点“检查更新”。"""
        if getattr(self, 'shutting_down', False) or getattr(self, '_master_update_busy', False):
            return
        self._master_update_busy = True
        if manual:
            self.status.set('正在检查总控包更新…')

        def work():
            try:
                return master_skill_update.check()
            except Exception as exc:
                return {'level': master_skill_update.ERROR, 'reason': type(exc).__name__}
        self._account_background(work, lambda result: self._master_update_checked(result, manual),
                                 '检查总控包更新')

    def _master_update_checked(self, result, manual=False):
        self._master_update_busy = False
        if getattr(self, 'shutting_down', False):
            return
        if result.get('level') != master_skill_update.AVAILABLE:
            if manual:
                failed = result.get('level') == master_skill_update.ERROR
                message = ('检查更新失败：%s' % (result.get('reason') or '联网失败') if failed
                           else result.get('reason') or '总控包已是最新版本。')
                self.status.set(message)
                (self.notifier.warning if failed else self.notifier.info)(message, title='检查总控包更新')
            return
        text = master_skill_update.describe(result)
        if not result.get('can_apply'):
            message = '总控包有新版本，但当前环境需手动更新：' + (result.get('blocked_reason') or '')
            self.status.set(message)
            if manual:
                self.notifier.info(text, title='总控包有更新')
            return
        self.status.set('总控包有新版本，等待确认更新。')
        if not ask_confirmation(self.win, '总控包有更新', text + '\n\n是否现在下载并更新？更新前的旧版本会进回收站。'):
            self.status.set('已暂不更新总控包；下次启动会再次提示。')
            return
        project = getattr(self, 'root', None)
        self.async_queued(lambda: master_skill_update.apply(result, project=project),
                          self._master_update_applied, label='更新总控包', show_progress=True)

    def _master_update_applied(self, outcome):
        if getattr(self, 'shutting_down', False):
            return
        message = (outcome or {}).get('message') or '总控包更新未完成'
        self.status.set(message)
        if not (outcome or {}).get('ok'):
            self.notifier.warning(message, title='总控包更新未完成')
