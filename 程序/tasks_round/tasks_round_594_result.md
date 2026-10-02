# R594 状态接续轮结果：R182 债务台账复核

## 范围

本轮不修改任何生产或测试 `.py`。依据当前 `legacy_compat.py`、生产调用点与 R589–R593 结果，校正 `project_status.md` 中仍引用 R550 的过期阻塞结论。

## 核查事实

| facade | 当前生产调用方 | 是否可删除 |
| --- | --- | --- |
| `resolved_storyboard_alias` | `engine` | 否 |
| `canonical_stage_name` | `confirm_gates` | 否 |
| `optional_workflow_model_name` | `local_previs` | 否 |
| `optional_model_identity` | `idea_chat` | 否 |
| `optional_asset_counts` | `pet_ui` | 否 |

全部条目的 `retire_after` 均为 2027-03-31；当前日期早于该日，故 P3-2 没有可安全删除的 facade。

## 状态修正

- P0-3 已由 R590（交付）、R591（音频）、R592（首帧）与 R593（视频提示）完成，不再登记为阻塞。
- R182 拆分债务从旧台账中的“8 项”校正为 1 项，即 P3-2。
- 全页面响应式布局、删除入口统一仍是独立产品专项，未被伪装计入或排除 R182 债务。

## 验证

- `python -m unittest tests.architecture.test_round_baselines`：3/3 通过。

## 后续条件

P3-2 的下一步必须等任一 facade 无生产调用，或在 2027-03-31 之后依已批准的旧项目迁移提示策略执行；目前不具备安全自动删除条件。
