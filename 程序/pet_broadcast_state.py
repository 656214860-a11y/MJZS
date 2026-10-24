"""Pet 播报状态容器（L3，无 Tk）。

R1983 J5：``_advance_at``／``_announced``／``_held_broadcast``／``_last_broadcast``／``last_status``／
``notice`` 六个属性原先散在 ``pet_ui``／``pet_ui_stages``／``pet_ui_voice``／``pet_ui_view`` 四个文件里直接读写。
这里把它们收进 ``PetBroadcastState``，``Pet.bstate`` 持有；除 ``notice`` 与 ``last_status``
（状态栏原文，写入面太宽，仍由旧属性名转发）外，判重、压住、节流这几类写入都改走本对象的方法，
所以「同一句不连说两遍」「压住后补说」「推进节流」的规则只在这一处。

- ``notice``／``last_status`` 是 Pet 的公开属性（各 Mixin 与桌面端都在读写），由 ``PetBroadcastAliasesMixin``
  继续转发到 ``Pet.bstate``；``_announced``／``_last_broadcast``／``_held_broadcast``／``_advance_at`` 四个下划线旧名
  已退役（R1983 契约轮），读写一律走 ``pet.bstate.<字段>``。
- 只放状态与纯判定，不持有 Tk 控件、不读时钟（时钟由调用方传入）。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PetBroadcastState:
    """播报相关的运行状态。默认值与原 ``Pet.__init__`` 逐项一致。"""

    notice: str = ''
    last_status: str = ''
    announced: tuple = ()
    last_broadcast: str = ''
    held_broadcast: str = ''
    advance_at: float | None = None

    def remember_status(self, text):
        """状态栏原文去重：与上一句相同返回 False，否则记下并返回 True。"""
        if text == self.last_status:
            return False
        self.last_status = text
        return True

    def is_repeat(self, text):
        """同一句话不连着说两遍。"""
        return text == self.last_broadcast

    def spoke(self, text):
        self.last_broadcast = text

    def forget_spoken(self):
        """清掉判重指纹（稍后再说／恢复播报／招呼重置共用）。"""
        self.announced = ()
        self.last_broadcast = ''

    def new_failure_batch(self, stamp):
        """失败批次判重：空批次清指纹；与上一批相同返回 False；否则记下并返回 True。"""
        if not stamp:
            self.announced = ()
            return False
        if stamp == self.announced:
            return False
        self.announced = stamp
        return True

    def hold(self, text):
        self.held_broadcast = text

    def take_held(self):
        """取出被压住的那句话并清空；没有则返回空串。"""
        text = self.held_broadcast
        self.held_broadcast = ''
        return text

    def advance_throttled(self, now, seconds):
        return self.advance_at is not None and (now - self.advance_at) < seconds

    def mark_advance(self, now):
        self.advance_at = now

    def reset_advance(self):
        """清掉推进节流：下一拍立刻可推。"""
        self.advance_at = None


class _Forward:
    """把 ``pet.<公开属性>`` 的读写转发到 ``pet.bstate.<字段>``。"""

    def __init__(self, state_field):
        self.state_field = state_field

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        return getattr(obj.bstate, self.state_field)

    def __set__(self, obj, value):
        setattr(obj.bstate, self.state_field, value)


class PetBroadcastAliasesMixin:
    """公开属性 ``notice``／``last_status`` 的转发；``bstate`` 缺失（测试里绕过 __init__ 的 Pet.__new__）时首次访问补默认状态。"""

    def __getattr__(self, name):
        if name == 'bstate':
            state = vars(self)['bstate'] = PetBroadcastState()
            return state
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")


for _name in ('notice', 'last_status'):
    setattr(PetBroadcastAliasesMixin, _name, _Forward(_name))
del _name
