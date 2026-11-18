"""L3 账号编排：登录、续签、退出、兑换、设备、注销、导出与阶段闸门，不持有 Tk 控件。

网络与落盘都在 ``submit`` 注入的后台任务里执行（桌面传入 ``Desktop.async_queued``，
经 ``BackgroundTaskLifecycle`` 收尾）；完成回调由 UI 线程调用。启动后自动发起的续签与
版本检查改走 ``background``：不占独占后台、不写状态栏，否则联网期间用户点什么都被
“当前操作尚未结束”拦下（R1959）；不传时与 ``submit`` 相同。闸门判定只读本机
会话并验签，不联网，启动路径与阶段启动都不等待网络（设计文档 §4.3、§5.4）。
"""
import platform
import threading
import time
from contextlib import nullcontext
from pathlib import Path

import domain.account_client as account_client
import infra.account_store as account_store
import domain.entitlement_service as entitlement_service
import infra.update_notice as update_notice
from agent.core import save
from agent.publication import access
from contract.service_contract import SystemError, success

RENEW_INTERVAL = 12 * 3600
RENEW_VIEW_INTERVAL = 60      # R2064：进账号页、窗口回前台时的最短续签间隔（秒），后台改了到期日能很快看到
# 这些错误码说明本机会话已不可能续上：删除令牌与租约，回到未登录。
SESSION_DEAD = frozenset({'session_invalid', 'account_pending_deletion', 'invalid_device'})


class AccountController:
    def __init__(self, *, submit, background=None, clock=time.time, store=account_store, client=account_client,
                 enforce=None, monotonic=time.monotonic):
        self._submit, self._clock, self._store, self._client = submit, clock, store, client
        self._background = background or submit
        self._monotonic = monotonic
        self._clock_mark = None
        # 正常入口始终走租约授权，只有显式注入可关闭拦截。
        self.enforce = enforce is None or bool(enforce)
        self._device_id = ''
        self.last_renew_at = 0.0
        self._renew_lock = threading.Lock()      # 刷新令牌一次一换：并发续签拿旧令牌会被服务端当重放吊销会话

    @property
    def device_id(self):
        if not self._device_id:
            self._device_id = self._store.device_fingerprint()
        return self._device_id

    def session(self):
        return self._store.load()

    def now(self):
        return int(self._clock())

    def _estimated_now(self, now):
        """进程存活期间用单调钟推进过期判断，即使系统时间停止。"""
        tick = self._monotonic()
        last_tick, last_now = self._clock_mark or (tick, now)
        estimate = max(now, last_now + max(0, tick - last_tick))
        self._clock_mark = (tick, estimate)
        return int(estimate)

    def clock_backup_available(self):
        status = getattr(self._store, 'clock_backup_available', None)
        return status() if status is not None else None

    def entitlement(self):
        data = self.session()
        floor = data.get('server_time') or 0
        baseline = getattr(self._store, 'clock_baseline', None)
        if baseline is not None:
            floor = baseline(floor)
        now = self.now()
        return entitlement_service.evaluate(data.get('lease'), now=now, device_id=self.device_id,
                                            last_server_time=floor, estimated_now=self._estimated_now(now))

    def stage_gate(self, stage):
        """阶段启动前置判定：放行返回空串，否则返回拦截原因；只有显式注入关闭拦截时才直接放行。"""
        if not self.enforce or not entitlement_service.is_paid_stage(stage):
            return ''
        return entitlement_service.stage_block_message(self.entitlement(), stage)

    def page_gate(self, pages):
        """侧栏换页闸：``pages`` 为 (页序号, 阶段键或 None, 标题)；返回 {页序号: 锁定原因}，只判一次授权。"""
        if not self.enforce:
            return {}
        entitlement = self.entitlement()
        reasons = {index: entitlement_service.page_block_message(entitlement, stage, title)
                   for index, stage, title in pages}
        return {index: reason for index, reason in reasons.items() if reason}

    def device(self):
        return {'id': self.device_id, 'name': platform.node()[:64], 'os': (platform.system() + ' ' + platform.release())[:64]}

    CODE_LABELS = {'login': '发送登录验证码', 'register': '发送注册验证码', 'reset': '发送重置密码验证码'}

    def request_code(self, email, done, *, purpose='login'):
        email = str(email or '').strip()
        self._run(lambda: self._client.send_code(email, purpose), done, self.CODE_LABELS[purpose])

    def login(self, email, code, *, age_confirmed, done):
        """验证码登录（邮箱未注册时服务端顺带建号）。"""
        email, code = str(email or '').strip(), str(code or '').strip()
        device = self.device()

        def work():
            result = self._client.verify_code(email, code, device, age_confirmed=age_confirmed)
            return self._accept(result.data, email=email) if result.ok else result
        self._run(work, done, '登录账号')

    def password_login(self, email, password, done):
        email, device = str(email or '').strip(), self.device()

        def work():
            result = self._client.password_login(email, password or '', device)
            return self._accept(result.data, email=email) if result.ok else result
        self._run(work, done, '登录账号')

    def register(self, email, code, password, *, age_confirmed, done):
        email, code, device = str(email or '').strip(), str(code or '').strip(), self.device()

        def work():
            result = self._client.register(email, code, password or '', device, age_confirmed=age_confirmed)
            return self._accept(result.data, email=email) if result.ok else result
        self._run(work, done, '注册账号')

    def reset_password(self, email, code, password, done):
        """凭重置验证码设新密码；服务端吊销该账号全部会话，本机若登着同一账号也一并退出。"""
        email, code = str(email or '').strip(), str(code or '').strip()

        def work():
            result = self._client.reset_password(email, code, password or '')
            if result.ok and str(self.session().get('email') or '').lower() == email.lower():
                self._store.clear_session()
            return result
        self._run(work, done, '重置密码')

    def change_password(self, password, done, *, old_password=None):
        """已登录设置或修改密码（已有密码须带原密码）。无会话返回 False。"""
        def saved(result):
            if result.ok:
                self._store.save_session({'has_password': True})
            return result
        return self._lease_call(lambda lease: self._client.change_password(lease, password or '', old_password),
                                done, '设置密码', then=saved)

    def renew(self, done=None, *, quiet=False):
        """有刷新令牌才续签；网络失败保留旧租约静默等下次，会话失效则清掉。``quiet`` 为自动续签。"""
        data = self.session()
        token = data.get('refresh_token')
        if not token:
            return False
        device_id = self.device_id
        self.last_renew_at = self._clock()

        def work():
            result = self._renew_once(token, device_id)
            if result is None:
                return success({'already_renewed': True, 'lease': self.session().get('lease')})
            return result
        self._run(work, done, '续签会员授权', quiet=quiet)
        return True

    def _renew_once(self, token, device_id):
        """序列化同会话的续签，等待者重读。项目发布锁只覆盖最后的本机写入。"""
        with self._renew_lock, self._account_process_lock():
            current = self.session().get('refresh_token')
            if current != token:
                return self._changed_renewal(current)
            result = self._client.renew(token, device_id)
            with access():
                current = self.session().get('refresh_token')
                if current != token:
                    return self._changed_renewal(current)
                if result.ok:
                    return self._accept(result.data)
                if (result.data or {}).get('code') in SESSION_DEAD:
                    self._store.clear_session()
                return result

    def _account_process_lock(self):
        lock_path = getattr(self._store, 'renew_lock_path', None)
        return access(lock_path=lock_path()) if lock_path else nullcontext()

    @staticmethod
    def _changed_renewal(current):
        if current:
            return None
        return SystemError('登录已失效，请重新登录', data={'code': 'session_invalid'})

    def check_update(self, done):
        """联网读 ``/v1/meta`` 判定是否有新版；结果 data 为 ``update_notice.evaluate`` 的字典，
        另带 ``proactive``（该版本尚未主动提示过；强制升级恒为 True）。提示过的软提示版本记在本机。"""
        def work():
            result = self._client.meta()
            if not result.ok:
                return result
            notice = update_notice.evaluate(result.data, self._client.CLIENT_VERSION)
            notice['proactive'] = notice['level'] == update_notice.HARD or (
                notice['level'] == update_notice.SOFT and notice['version'] != self._store.update_seen())
            if notice['level'] == update_notice.SOFT and notice['proactive']:
                self._store.mark_update_seen(notice['version'])
            return success(notice)
        self._run(work, done, '检查新版本', quiet=True)

    def redeem(self, code, done):
        """用本机租约兑换；成功后服务端返回的新租约替换本机租约。无会话返回 False。"""
        code = str(code or '').strip()

        def accept(result):
            return self._accept(result.data, rotate=False) if result.ok else result
        return self._lease_call(lambda lease: self._client.redeem(lease, code), done, '兑换会员', then=accept)

    def devices(self, done):
        """已绑定设备列表（含 ``current``、``unbind_left``、``next_unbind_at``）。无会话返回 False。"""
        return self._lease_call(self._client.devices, done, '读取设备列表')

    def providers(self, done):
        """读取推荐线路预设（不含 Key）。无会话返回 False。"""
        return self._lease_call(self._client.providers, done, '读取推荐线路')

    def unbind(self, device_id, done, *, current=False):
        """解绑一台设备；解绑的是本机时服务端已吊销本机会话，这里同步清掉本机会话。"""
        device_id = str(device_id or '').strip()

        def cleared(result):
            if result.ok and current:
                self._store.clear_session()
            return result
        return self._lease_call(lambda lease: self._client.unbind_device(lease, device_id), done, '解绑设备', then=cleared)

    def request_delete_code(self, done):
        """向账号邮箱发注销用途验证码（与登录码分开，登录码不能确认注销）。"""
        return self._lease_call(self._client.delete_code, done, '发送注销验证码')

    def request_deletion(self, code, done):
        """凭注销验证码进入 7 天冷静期；服务端吊销全部会话，成功后清本机会话。"""
        code = str(code or '').strip()

        def cleared(result):
            if result.ok:
                self._store.clear_session()
            return result
        return self._lease_call(lambda lease: self._client.delete_request(lease, code), done, '申请注销账号', then=cleared)

    def cancel_deletion(self, email, code, done):
        """冷静期内凭登录验证码撤销注销（会话已全部吊销，不带租约）；撤销后须重新登录。"""
        email, code = str(email or '').strip(), str(code or '').strip()
        self._run(lambda: self._client.delete_cancel(email, code), done, '撤销注销')

    def export(self, target, done):
        """导出账号数据 JSON 到用户选定的 ``target``；内容只写这个文件，不进日志。"""
        target = Path(target)

        def written(result):
            if not result.ok:
                return result
            try:
                save(target, result.data)
            except OSError as exc:
                return SystemError('导出文件写不进去：%s' % exc, data={'code': 'write_failed'})
            return success({'path': str(target)})
        return self._lease_call(self._client.export, done, '导出账号数据', then=written)

    def _lease_call(self, call, done, label, *, then=None):
        """后台用本机租约调 ``call(lease)``；无租约返回 False，否则提交并返回 True。

        租约已过期（401 ``session_invalid``）时先续签一次再重试；续签判定会话已死则清本机
        会话。``then`` 在后台线程收尾结果（落盘等），一律返回结果、不抛异常。
        """
        data = self.session()
        lease, token = data.get('lease'), data.get('refresh_token')
        if not lease:
            return False
        device_id = self.device_id

        def work():
            result = call(lease)
            if not result.ok and (result.data or {}).get('code') == 'session_invalid' and token:
                renewed = self._renew_once(token, device_id)
                if renewed is None:             # 别处刚续过：用本机现成的新租约重试
                    fresh = self.session().get('lease')
                    if not fresh:
                        return result
                    result = call(fresh)
                elif not renewed.ok:
                    return renewed
                else:
                    result = call(renewed.data['lease'])
            return then(result) if then else result
        self._run(work, done, label)
        return True

    def _run(self, work, done, label, *, quiet=False):
        """经注入的 ``submit``（``quiet`` 时经 ``background``）后台执行；工作函数意外抛错也收成失败结果。

        异常原文可能夹带令牌、租约或邮箱，不交给后台任务的诊断记录，只留异常类型名。
        """
        def guarded():
            try:
                return work()
            except Exception as exc:
                return SystemError('账号操作出错（%s），请稍后重试' % type(exc).__name__,
                                   data={'code': 'client_error'})
        (self._background if quiet else self._submit)(guarded, done, label)

    def renew_due(self, interval=RENEW_INTERVAL):
        return self._clock() - self.last_renew_at >= interval

    def last_email(self):
        """上次登录用的邮箱：登录框默认填它（退出登录也保留）。"""
        getter = getattr(self._store, 'last_email', None)
        return getter() if getter else ''

    def logout(self, done=None):
        """先尝试服务端吊销，失败仍清本机。桌面回调走后台线程。"""
        if done is None:
            return self._logout_once()
        self._run(self._logout_once, done, '退出登录')
        return True

    def _logout_once(self):
        with self._renew_lock, self._account_process_lock():
            before = self.session()
            lease = before.get('lease')
            try:
                remote_ok = self._client.logout(lease).ok if lease else not before.get('refresh_token')
            except Exception:
                remote_ok = False
            with access():
                after = self.session()
                token = before.get('refresh_token')
                if after.get('refresh_token') != token or (not token and after.get('lease') != lease):
                    return SystemError('登录状态已变化，请重试退出登录', data={'code': 'session_changed'})
                if not self._store.clear_session():
                    return SystemError('无法清除本机会话，请重试退出登录', data={'code': 'local_clear_failed'})
        if not remote_ok:
            return SystemError('本地已登出，服务端会话将在到期后失效',
                               data={'code': 'remote_logout_unconfirmed', 'local_cleared': True})
        return success({'local_cleared': True})

    def _accept(self, data, *, email=None, rotate=True):
        """先验签再落盘：返回原结果或 SystemError，不抛异常（完成回调总能收到结果）。

        ``rotate=False``（兑换）只替换租约，刷新令牌不变。
        """
        data = data if isinstance(data, dict) else {}
        fields = {'lease': data.get('lease')}
        if rotate:
            fields['refresh_token'] = data.get('refresh_token')
        if email is not None:
            fields['email'] = email
        user = data.get('user')
        if isinstance(user, dict) and 'has_password' in user:
            fields['has_password'] = bool(user['has_password'])
        if (rotate and not fields['refresh_token']) or not fields['lease']:
            return SystemError('账号服务返回的登录结果不完整', data={'code': 'bad_response'})
        checked = entitlement_service.evaluate(fields['lease'], now=int(self._clock()), device_id=self.device_id)
        if checked.state == entitlement_service.SIGNED_OUT:
            # 验签失败或不是本机的租约：不覆盖本机已有的有效会话。
            return SystemError('账号服务返回的授权无法验证，请稍后重试', data={'code': 'lease_unverified'})
        payload = checked.payload
        fields['server_time'] = max(int(payload.get('iat_server') or 0), int(payload.get('issued_at') or 0))
        self._store.save_session(fields)
        return success(data)
