"""三虎半自动档的轮询放行策略（纯逻辑 L4：不建窗口、不写盘）。

SANHU-FIX-1B / S-01：半自动走手动控制面（``mode='manual'``、页面自动开关全关），
但免费轮询组仍须放行——否则三虎说「已自动开始」后 8 条轮询全被 ``mode != 'auto'``
无声拦死。付费轮询组（资产／视频）仅当本次运行显式授权（grant_paid）时放行；
``auto_submit``／``auto_review`` 在半自动恒不放行（付费步骤先问用户，决定题 1 按
建议 A）。storyboard／audio 不在半自动自动链上，与其余未登记项一样不放行。
全自动口径不变：照旧读三虎变量本身，不看分组。
"""
from ui.pet_ui_support import AUTO_STAGE_VARIABLES, AUTO_VARIABLE_NAMES

FREE_SEMI_VARS = frozenset({
    'auto_adopt_var', 'auto_final_var', 'auto_first_frame_var',
    'auto_previs_var', 'auto_edit_var', 'auto_handoff_var'})
PAID_SEMI_VARS = frozenset({'auto_asset_var', 'auto_video_var'})
NEVER_SEMI_VARS = frozenset({'auto_submit_var', 'auto_review_var'})


def canonical_var(stage_id):
    """把短 stage_id、process_id 或变量名本身归一到三虎自动变量名；认不出返回空串。"""
    key = str(stage_id or '').strip()
    if key in AUTO_VARIABLE_NAMES:
        return key
    return AUTO_STAGE_VARIABLES.get(key, '')


def allowed(level, mode, stage_id, granted=(), *, read_auto_var=None):
    """某一轮询变量当前档是否放行。半自动不读开关，全自动照旧读开关。"""
    key = str(stage_id or '').strip()
    if level == 'auto' or mode == 'auto':
        try:
            name = AUTO_STAGE_VARIABLES.get(key)
            return bool(name and read_auto_var(name))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return False
    if level != 'semi':
        return False
    name = canonical_var(key)
    if not name or name in NEVER_SEMI_VARS:
        return False
    if name in FREE_SEMI_VARS:
        return True
    if name not in PAID_SEMI_VARS:
        return False
    aliases = {key, name}
    aliases.update(k for k, v in AUTO_STAGE_VARIABLES.items() if v == name)
    return bool(aliases & {str(g).strip() for g in granted}
                or name in {canonical_var(g) for g in granted})


def grants(host):
    """宿主对象上本次运行的付费轮询授权集合：懒初始化、不落盘。"""
    granted = getattr(host, '_auto_granted', None)
    if granted is None:
        granted = host._auto_granted = set()
    return granted


def grant_paid(host, stage):
    """授权一个付费轮询阶段：规范阶段名（'assets'／'video'）或对应 process_id。"""
    name = canonical_var(stage)
    if name:
        grants(host).add(name)


def revoke_paid(host, stage):
    """撤销一个付费轮询授权：阶段完成、失败与切档都走这里。"""
    grants(host).discard(canonical_var(stage))


def clear_paid_grants(host):
    """任何一次切档都清空全部付费授权。"""
    grants(host).clear()
