"""会员授权闸门判定：输入租约与当前时间，输出离线状态与是否放行某阶段。

纯函数，无网络、无 Tk、不写项目数据（设计文档 §4.3、§5.2）。状态：

- ``valid``：租约在有效期内且会员状态为 trial／active，全部功能可用；
- ``grace``：有效期已过、宽限未过，可用但提示联网续签；
- ``locked``：宽限已过或服务端判定 expired，付费阶段禁止新生成；
- ``signed_out``：无租约、验签失败或不是本机的租约；
- ``clock_suspect``：本机时间比最近一次已知服务器时间早超过容差，按过期处理。

免费阶段固定为 ``pet_bus.STAGES`` 的前 2 个阶段键，不按序号或中文名硬编码。
"""
from dataclasses import dataclass
import time

import lease_verifier
from pet_bus import STAGES, STAGE_NAMES

VALID = 'valid'
GRACE = 'grace'
LOCKED = 'locked'
SIGNED_OUT = 'signed_out'
CLOCK_SUSPECT = 'clock_suspect'
USABLE = frozenset({VALID, GRACE})
CLOCK_TOLERANCE = 300
FREE_STAGES = tuple(STAGES[:2])
PAID_STATES = frozenset({'trial', 'active'})
# 总开关：True 时付费阶段（前 2 个之外）在未登录、过期、时钟异常时拦截新生成；False 只判定不拦截。
GATE_ENFORCED = True


@dataclass(frozen=True)
class Entitlement:
    state: str
    payload: dict | None = None

    @property
    def usable(self):
        return self.state in USABLE


def evaluate(lease, *, now, device_id, last_server_time=0, keys=None):
    """按 §4.3 离线状态机判定；``now`` 与 ``last_server_time`` 均为 UTC 秒。"""
    payload = lease_verifier.verify(lease, keys) if lease else None
    if payload is None or not device_id or payload.get('did') != device_id:
        return Entitlement(SIGNED_OUT)
    try:
        expires_at = int(payload['expires_at'])
        grace_until = int(payload['grace_until'])
        floor = max(int(last_server_time or 0), int(payload.get('issued_at') or 0))
    except (KeyError, TypeError, ValueError):
        return Entitlement(SIGNED_OUT)
    if now + CLOCK_TOLERANCE < floor:
        return Entitlement(CLOCK_SUSPECT, payload)
    if payload.get('state') not in PAID_STATES or now >= grace_until:
        return Entitlement(LOCKED, payload)
    return Entitlement(VALID if now < expires_at else GRACE, payload)


WARN_DAYS = 3
DAY_SECONDS = 86400
REDEEM_HINT = '输入兑换码即可续期；请联系发放兑换码的渠道获取。'


def days_left(payload, now):
    """试用／会员距到期的剩余天数（向上取整，已过期为 0）；无到期时间返回 None。"""
    key = 'trial_ends_at' if (payload or {}).get('state') == 'trial' else 'period_end'
    try:
        end = int((payload or {})[key])
    except (KeyError, TypeError, ValueError):
        return None
    return max(0, -(-(end - int(now)) // DAY_SECONDS))


def _date(stamp):
    return time.strftime('%Y-%m-%d', time.localtime(int(stamp)))


def membership_view(entitlement, now):
    """账号页用的会员状态文案：``{lines, level}``，level 为 info／warn／expired。"""
    free = '「%s」「%s」永久免费，已有项目和素材始终在本机。' % (
        STAGE_NAMES.get(FREE_STAGES[0], ''), STAGE_NAMES.get(FREE_STAGES[1], ''))
    state, payload = entitlement.state, entitlement.payload or {}
    if state == SIGNED_OUT:
        return {'lines': ['新账号登录即免费试用 3 天，试用期内可使用全部制作阶段。', free],
                'level': 'info'}
    if state == CLOCK_SUSPECT:
        return {'lines': ['本机时间早于服务器时间，请校正系统时间后联网续签。', free],
                'level': 'warn'}
    paid = payload.get('state') in PAID_STATES
    if state == LOCKED and not paid:
        end = payload.get('trial_ends_at') or payload.get('period_end')
        head = '试用或会员已于 %s 到期。' % _date(end) if end else '试用或会员已到期。'
        return {'lines': [head, free, REDEEM_HINT], 'level': 'expired'}
    if state == LOCKED:
        return {'lines': ['离线授权已超过宽限期，请联网续签。', free], 'level': 'warn'}
    left = days_left(payload, now)
    name = '试用' if payload.get('state') == 'trial' else '会员'
    if left is None:
        return {'lines': [], 'level': 'info'}
    lines = ['%s还剩 %d 天。' % (name, left)]
    if left <= WARN_DAYS:
        lines.append(REDEEM_HINT)
        return {'lines': lines, 'level': 'warn'}
    return {'lines': lines, 'level': 'info'}


def expiry_summary(entitlement, now):
    """标题栏常驻的一行到期提示：「试用至 2026-10-28（还剩 3 天）」；未登录或拿不到到期时间返回空串。"""
    state, payload = entitlement.state, entitlement.payload or {}
    if state == SIGNED_OUT or not payload:
        return ''
    paid = payload.get('state') in PAID_STATES
    if state == LOCKED and not paid:
        return '试用或会员已到期，请到「00 会员账户」兑换续期'
    key = 'trial_ends_at' if payload.get('state') == 'trial' else 'period_end'
    left = days_left(payload, now)
    if left is None or not payload.get(key):
        return ''
    name = '试用' if payload.get('state') == 'trial' else '会员'
    if left <= 0:
        return '%s已到期，请到「00 会员账户」兑换续期' % name
    return '%s至 %s（还剩 %d 天）' % (name, _date(payload[key]), left)


def is_paid_stage(stage):
    return stage in STAGES and stage not in FREE_STAGES


def stage_block_message(entitlement, stage):
    """放行返回空串；拦截时返回给用户看的一句话。非阶段键（如三虎表演）一律放行。"""
    if not is_paid_stage(stage) or entitlement.usable:
        return ''
    title = STAGE_NAMES.get(stage, stage)
    if entitlement.state == SIGNED_OUT:
        reason = '需要登录账号（新账号可免费试用 3 天）'
    elif entitlement.state == CLOCK_SUSPECT:
        reason = '本机时间早于服务器时间，请校正系统时间后联网续签'
    elif (entitlement.payload or {}).get('state') not in PAID_STATES:
        reason = '试用或会员已到期'
    else:
        reason = '离线授权已超过宽限期，请联网续签'
    return '「%s」%s；请到「00 会员账户」处理。「%s」「%s」不受影响。' % (
        title, reason, STAGE_NAMES.get(FREE_STAGES[0], ''), STAGE_NAMES.get(FREE_STAGES[1], ''))
