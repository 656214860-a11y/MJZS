# R2883 修复轮结果：三虎簇架构门禁修复——猫爪布局四法迁入 PetPatchLayoutMixin
<!-- round-evidence: {"commit_base": "5cb480a0", "credential_hits": 0, "evidence_sha256": "fba7386cea6acb36", "exit": 0, "failed": 0, "passed": 620, "round": 2883, "tests": "run_selftests.py -k pet_ui desktop_compact complexity_ratchet shared_state_ratchet"} -->

- 轮次类型：§3.2 修复轮（合并轮 CI 架构门禁红灯的根因修复，不改外部行为）。
- 背景：R2876（codex/wip-R2876）首次合入 master 时 `merge_round.py` 出口档 CI 中止——`pet_ui_view.py::PetViewMixin` 实测 832 行超登记上限 774、`Pet` 多写者属性 56 个超上限 54、且 master 全量安全凭据欠账未清。本轮只修前两项代码债，凭据由主工作区后台 `--all --safe` 补跑闭环。
- 轮次号说明：先后领号 R2880（提交时中央已前进至 R2882 被拒）→ R2883，实际使用 **R2883**（`codex/wip-R2883`）。

## 改动

- `程序/pet_ui_view.py`：新建 `PetPatchLayoutMixin`（同文件、`PetViewMixin` 之前），迁入 `_paw_col_top`／`_align_paws`／`_sync_patch_room`／`_build_paws` 四个猫爪列布局方法；`PetViewMixin(PetPatchLayoutMixin)`，`draw_paws` 等渲染方法留在原类。类体跨度 832→731。
- `程序/pet_ui.py`：`Pet.__init__` 删除 `_paw_col_y` 实例状态（列顶由 `_paw_col_top()` 每次按小字实高现算，无需缓存）；`patch_room` 唯一写者收进 `PetPatchLayoutMixin._sync_patch_room`，多写者属性 56→54。
- `程序/tests/architecture/test_complexity_ratchet.py`：`CLASS_CAPS` 登记值按规则「只许下降」同步 774→746（实际 731＋slack 15），注释注明 R2876 拆分类由来。

行为不变：小字位置、猫爪列对齐、命中区、patch_room 动态收缩逻辑逐行迁移，未改一行业务语义。

## 三问

- 本轮属于 §3.2 修复轮。
- 测试跑了：`run_selftests.py -k test_complexity_ratchet test_shared_state_ratchet` 8/8 绿；`run_selftests.py -k test_pet_ui test_desktop_compact_layout` 612/612 绿（0 文件红）；提交证据定向测试见 evidence/R2883.json。
- 欠账少了：架构登记表欠账清零（PetViewMixin 由超限回落登记内）；master 全量安全凭据欠账由后台 `auto_full_safe.py` 补跑（最近一次 530s 跑挂在 `test_script_zoom` 键盘缩放时序断言，定向复跑曾 10/10 绿，属负载敏感型偶发），合并轮前以真实绿凭据为准。

## 验证

- 改前（合并轮 CI 实测）：`PetViewMixin 832 行 > 上限 774`；`Pet: 56 个多写者属性 > 上限 54`。
- 改后：`PetPatchLayoutMixin` 跨度 100 行（< CLASS_LIMIT 600，无需登记）；`PetViewMixin` 731 行 ≤ 登记 746；`Pet` 多写者属性 54 = 登记上限；两个 ratchet 测试文件 8/8 通过。
- `test_pet_ui`＋`test_desktop_compact_layout` 612 条用例全绿，含小字下移、列底对齐、命中区、标题行高度全部几何断言。

## 提交

待补：commit hash 由 dev.py commit 回执填写。
