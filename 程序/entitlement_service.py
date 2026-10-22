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
