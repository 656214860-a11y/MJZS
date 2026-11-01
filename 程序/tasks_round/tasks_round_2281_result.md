# R2281 Pet 追问状态收进 PetOfferState（J-Pet 结构治理轮·执行）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 07 的 J-Pet：「挑一簇多写者属性收进只由一个 Mixin 写的状态对象（仿 `pet_broadcast_state`），棘轮下调」。

## 基线
分支 `codex/wip-R2281`，自 `codex/wip-R2280`。

## 轮次类型／三套基线／债务
结构治理轮；行为等价；无新增债务。

## 改动
- `pet_broadcast_state.py`：新增 `PetOfferState`（`at/sig/open/backoff/declined`，默认值与原 `Pet.__init__` 一致）；`PetBroadcastAliasesMixin` 对绕过 `__init__` 的 Pet 懒建 `offer`（原先靠 `getattr(self,'_offer_*',默认)` 兜底）。
- `pet_ui.py`：五个 `_offer_*` 初始化换成 `self.offer = PetOfferState()`。
- `pet_ui_voice.py`：五个属性的读写改 `self.offer.<字段>`，不再用 `getattr` 兜底；行数不变。
- `tests/test_pet_ui.py`：三处断言的读取路径 `pet._offer_sig/_offer_open` → `pet.offer.sig/open`（契约有意变更，只同步读取路径，断言内容与期望值未动）。
- `tests/architecture/test_shared_state_ratchet.py`：`Pet` 上限 59 → 54（实测 -5）。`architecture.md` 同步。

## 新增测试
`tests/test_pet_broadcast_state.py`：`PetOfferState` 默认值、绕过 `__init__` 时懒建。

## 测试
- 已跑（隐藏桌面）：`run_selftests.py -k pet_ui pet_broadcast pet_core` 616 条全过；`smoke_test.py --architecture` 413 条，仅已知环境红。
- 未运行：`--all --safe`。

## 回滚
`git revert` 本轮提交。

## 下一步
J-Cloud：Cloud 的 `_hint_*` 簇收进单写者状态对象。
