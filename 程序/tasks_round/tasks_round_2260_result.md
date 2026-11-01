# R2260 网关字典收成一个 JSON 发布器底座（J21 结构治理轮·执行）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 10 的 J21：「`stage_execution_service` 的网关字典收成一个基础构造，各 `*_gateway()` 只补差异字段，对外接口不变」。

## 基线
分支 `codex/wip-R2260`，自 `codex/wip-R2254`。

## 轮次类型／三套基线／债务
结构治理轮；行为等价（键集合与发布器对象不变，仍在调用时才 import）；无新增债务。

## 改动
- `stage_execution_service.py`：新增 `_json_gateway(**extra)`（`{'publish_json': save, **extra}`）；9 个只含 `publish_json` 的网关（pet_performance／pet_test／desktop_settings／asset_batch_settings／cloud_video／video_lifecycle／confirm_gates／previs_routing／storyboard_edit）改为一行委托，`legacy_adoption_gateway` 只补 `make_dir`。其余带多项能力的网关（local_video_settings／video_prompt／idea_chat／asset_*／tts／storyboard）本轮不动，避免扩大范围。
- 体量上限 1447→1442。

## 新增测试
`tests/test_stage_gateway_base.py`：9 个纯 JSON 网关键集合恰为 `publish_json` 且为 `agent.core.save`；legacy 网关仅多 `make_dir`。

## 测试
- 已跑（隐藏桌面）：`run_selftests.py -k stage_gateway stage_execution gateway pet_performance pet_test desktop_settings legacy_adoption asset_batch cloud_video confirm_gates previs storyboard_edit` 全过；`smoke_test.py --architecture` 412 条，仅两项已知环境红。
- 未运行：`--all --safe`。既有测试断言未动。

## 回滚
`git revert` 本轮提交。

## 下一步
候选 10 完成。下一组：候选 09（J22、J23+、J-回收、J-配置）。
