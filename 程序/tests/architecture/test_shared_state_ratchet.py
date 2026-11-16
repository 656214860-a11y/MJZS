"""Mixin 组合类的共享状态只许减少：多个类都给同一个 ``self`` 属性赋值，就算一处耦合。

R1983 只读诊断的 J0（R1984 落地）：R1618–R1622 按行数把大类拆成 Mixin 文件，但各 Mixin
仍读写同一个 ``self``，耦合只是换了文件。本门禁按 AST 统计每个组合类（自身＋全部本仓库基类）里
「被 ≥2 个类赋值的 self 属性」个数，登记值只许下降、下降后必须同步下调。

口径：赋值＝``self.X`` 出现在 Store 上下文（含增量赋值、嵌套函数里的赋值）；``setattr``／
``getattr`` 动态访问不计。初始化写一次和运行中反复写一视同仁，所以只看趋势，不当绝对评分。

组合了 ≥3 个本仓库基类的生产类必须在 ``SHARED_STATE_CAPS`` 登记，新冒出来的组合类也会被拦住。
"""
import ast
import unittest
from collections import defaultdict

from tests.architecture._scan import parse, module_scan_files

SHARED_STATE_CAPS = {
    'Desktop': 44,  # R2933：app_title／header_slogan 等侧栏浮层属性删除后实测 44；R2029：方法拆到 PageNavMixin/LifecycleMixin 后跨类写入计数被动 +7；R2032：gate_due／gate_error 迁入 AutoState 后 -1；气泡框台账写入收进 _clear_bubble_view 单一入口 -3
    'Pet': 54,    # R2281 J-Pet：_offer_* 五件收进 Pet.offer（PetOfferState）-5
    'Cloud': 11,    # J-Cloud：_hint_* 四件收进 Cloud.hint_state（CloudHintState）-4
    'Panel': 4,  # R2862：总控/预设/模型选择行删除后跨类写入实测 4
    'IdeaChatMixin': 2,  # R2505：加第三个 Mixin 基类（IdeaAttachmentsMixin）后按实测登记；只许下降
}
MIXIN_BASE_THRESHOLD = 3


def _classes():
    found = defaultdict(list)
    for path in module_scan_files():
        for node in parse(path).body:
            if isinstance(node, ast.ClassDef):
                found[node.name].append((path.name, node))
    return found


def _local_bases(node, classes):
    return [base.id for base in node.bases if isinstance(base, ast.Name) and base.id in classes]


def _self_writes(node):
    return {sub.attr for sub in ast.walk(node)
            if isinstance(sub, ast.Attribute) and isinstance(sub.ctx, ast.Store)
            and isinstance(sub.value, ast.Name) and sub.value.id == 'self'}


def _shared_state(name, classes):
    """返回 (多写者属性→写入它的类集合, 歧义类名列表)。"""
    writers = defaultdict(set)
    ambiguous = []
    seen = set()
    pending = [name]
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        defs = classes[current]
        if len(defs) > 1:
            ambiguous.append(current)
        node = defs[0][1]
        for attr in _self_writes(node):
            writers[attr].add(current)
        pending.extend(_local_bases(node, classes))
    shared = {attr: owners for attr, owners in writers.items() if len(owners) > 1}
    return shared, ambiguous


class SharedStateRatchet(unittest.TestCase):
    def test_shared_state_does_not_grow(self):
        classes = _classes()
        over = []
        for name, cap in sorted(SHARED_STATE_CAPS.items()):
            shared, _ = _shared_state(name, classes)
            if len(shared) > cap:
                over.append(f'{name}: {len(shared)} 个多写者属性 > 上限 {cap}')
        self.assertEqual(over, [], '新状态请放进单一 Mixin 或独立状态对象，不要让多个 Mixin 写同一个 self 属性')

    def test_caps_track_real_counts(self):
        classes = _classes()
        stale = []
        for name, cap in sorted(SHARED_STATE_CAPS.items()):
            if name not in classes:
                stale.append(f'{name}: 类已不存在，请从登记表删除')
                continue
            actual = len(_shared_state(name, classes)[0])
            if actual < cap:
                stale.append(f'{name}: 实际 {actual}，登记 {cap}，请下调到 {actual}')
        self.assertEqual(stale, [])

    def test_registered_classes_resolve_unambiguously(self):
        classes = _classes()
        ambiguous = {name: _shared_state(name, classes)[1]
                     for name in SHARED_STATE_CAPS if name in classes}
        self.assertEqual({k: v for k, v in ambiguous.items() if v}, {},
                         '组合类或其基类在多个生产模块重名，统计口径不可靠')

    def test_mixin_composites_are_registered(self):
        classes = _classes()
        unregistered = sorted(
            f'{name}（{defs[0][0]}）'
            for name, defs in classes.items()
            if len(_local_bases(defs[0][1], classes)) >= MIXIN_BASE_THRESHOLD
            and name not in SHARED_STATE_CAPS)
        self.assertEqual(unregistered, [], '新的 Mixin 组合类须登记共享状态上限')


if __name__ == '__main__':
    unittest.main()
