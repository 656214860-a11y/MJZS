"""L3 账号编排：登录、续签、退出与阶段闸门的状态机，不持有 Tk 控件。

网络与落盘都在 ``submit`` 注入的后台任务里执行（桌面传入 ``Desktop.async_queued``，
经 ``BackgroundTaskLifecycle`` 收尾）；完成回调由 UI 线程调用。闸门判定只读本机
会话并验签，不联网，启动路径与阶段启动都不等待网络（设计文档 §4.3、§5.4）。
"""
import platform
import time

import account_client
import account_store
import entitlement_service
from service_contract import SystemError, success

RENEW_INTERVAL = 12 * 3600
# 这些错误码说明本机会话已不可能续上：删除令牌与租约，回到未登录。
SESSION_DEAD = frozenset({'session_invalid', 'account_pending_deletion', 'invalid_device'})


class AccountController:
    def __init__(self, *, submit, clock=time.time, store=account_store, client=account_client, enforce=None):
        self._submit, self._clock, self._store, self._client = submit, clock, store, client
        self.enforce = entitlement_service.GATE_ENFORCED if enforce is None else bool(enforce)
        self._device_id = ''
        self.last_renew_at = 0.0

    @property
    def device_id(self):
        if not self._device_id:
            self._device_id = self._store.device_fingerprint()
        return self._device_id

    def session(self):
        return self._store.load()

    def entitlement(self):
        data = self.session()
        return entitlement_service.evaluate(data.get('lease'), now=int(self._clock()),
                                            device_id=self.device_id,
                                            last_server_time=data.get('server_time') or 0)

    def stage_gate(self, stage):
        """阶段启动前置判定：放行返回空串，否则返回拦截原因；总开关关闭时一律放行。"""
        if not self.enforce or not entitlement_service.is_paid_stage(stage):
            return ''
        return entitlement_service.stage_block_message(self.entitlement(), stage)

    def device(self):
        return {'id': self.device_id, 'name': platform.node()[:64], 'os': (platform.system() + ' ' + platform.release())[:64]}

    def request_code(self, email, done):
        email = str(email or '').strip()
        self._submit(lambda: self._client.send_code(email), done, '发送登录验证码')

    def login(self, email, code, *, age_confirmed, done):
        email, code = str(email or '').strip(), str(code or '').strip()
        device = self.device()

        def work():
            result = self._client.verify_code(email, code, device, age_confirmed=age_confirmed)
            return self._accept(result.data, email=email) if result.ok else result
        self._submit(work, done, '登录账号')

    def renew(self, done=None):
        """有刷新令牌才续签；网络失败保留旧租约静默等下次，会话失效则清掉。"""
        data = self.session()
        token = data.get('refresh_token')
        if not token:
            return False
        device_id = self.device_id
        self.last_renew_at = self._clock()

        def work():
            result = self._client.renew(token, device_id)
            if result.ok:
                return self._accept(result.data)
            if (result.data or {}).get('code') in SESSION_DEAD:
                self._store.clear_session()
            return result
        self._submit(work, done, '续签会员授权')
        return True

    def redeem(self, code, done):
        """用本机租约兑换；租约已过期（401）时先续签一次再重试。无会话返回 False。"""
        data = self.session()
        lease, token = data.get('lease'), data.get('refresh_token')
        if not lease:
            return False
        code, device_id = str(code or '').strip(), self.device_id

        def work():
            result = self._client.redeem(lease, code)
            if result.ok:
                return self._accept(result.data, rotate=False)
            if (result.data or {}).get('code') != 'session_invalid' or not token:
                return result
            renewed = self._client.renew(token, device_id)
            if not renewed.ok:
                if (renewed.data or {}).get('code') in SESSION_DEAD:
                    self._store.clear_session()
                return renewed
            accepted = self._accept(renewed.data)
            if not accepted.ok:
                return accepted
            result = self._client.redeem(renewed.data['lease'], code)
            return self._accept(result.data, rotate=False) if result.ok else result
        self._submit(work, done, '兑换会员')
        return True

    def renew_due(self):
        return self._clock() - self.last_renew_at >= RENEW_INTERVAL

    def logout(self):
        """只清本机会话；服务端会话由刷新令牌过期或在别处解绑本机来吊销。"""
        return self._store.clear_session()

    def _accept(self, data, *, email=None, rotate=True):
        """先验签再落盘：返回原结果或 SystemError，不抛异常（完成回调总能收到结果）。

        ``rotate=False``（兑换）只替换租约，刷新令牌不变。
        """
        data = data if isinstance(data, dict) else {}
        fields = {'lease': data.get('lease'), 'server_time': data.get('server_time') or 0}
        if rotate:
            fields['refresh_token'] = data.get('refresh_token')
        if email is not None:
            fields['email'] = email
        if (rotate and not fields['refresh_token']) or not fields['lease']:
            return SystemError('账号服务返回的登录结果不完整', data={'code': 'bad_response'})
        checked = entitlement_service.evaluate(fields['lease'], now=int(self._clock()), device_id=self.device_id)
        if checked.state == entitlement_service.SIGNED_OUT:
            # 验签失败或不是本机的租约：不覆盖本机已有的有效会话。
            return SystemError('账号服务返回的授权无法验证，请稍后重试', data={'code': 'lease_unverified'})
        self._store.save_session(fields)
        return success(data)
