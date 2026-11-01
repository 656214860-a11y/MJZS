# R1677 修复轮：文档先行锚点与需求文字同步 R1667–R1674 的剪辑依赖变更

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮。根因：R1667–R1674 给 `stage_flow.DEPENDS['edit']` 加了 `audio`（REQ-S12-04 已按此修复并写明），但 R1664 写的 `tests/test_video_generation_scope.py::test_req_s10_03_flow_dependency_names_keyframe_only` 与 `REQUIREMENTS.md` 的 REQ-S12-01 仍写 `('video',)`。判定为“代码有意变更后锚点过期”，而不是代码偏离需求（REQ-S12-04 与 `tests/test_editing_scope.py:35` 均以 `('video','audio')` 为准）。
2. **测试跑了吗？三个基线过了吗？** 定向 `-k scope script_contract request_ledger pipeline_stage_io agents_md round_baselines`：21 个文件 / 320 条，唯一红为 `test_round_baselines.test_full_safe_all_is_required_after_eight_source_rounds`（R1676 欠全量，后台自动补跑机制负责，与本轮无关，未手动跑全量）。默认冒烟 8/8。未跑架构门禁全量与安全全量。
3. **project_status.md 的欠账少了吗？** 不变。

## A 改动

- `tests/test_video_generation_scope.py`：`DEPENDS['edit']` 期望值 `('video',)` → `('video','audio')`。契约有意变更，同文件其余断言未动，断言未弱化。
- `docs/REQUIREMENTS.md` REQ-S12-01：依赖描述同步为 `('video','audio')` 并指向 REQ-S12-04。

## C 待用户裁决

REQ-S10-03（`DEPENDS['video']` 是否并入 `previs`）仍为 🟡，本轮不动。

## 提交

见提交信息 `R1677:`。
