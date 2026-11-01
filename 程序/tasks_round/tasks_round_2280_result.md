# R2280 阶段配置文件路径收成一个入口 stage_layout.skill_config_path（J-配置 结构治理轮·执行）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 09 的 J-配置：「`skill_config.json` 路径收成一个入口」。

## 基线
分支 `codex/wip-R2280`，自 `codex/wip-R2279`。

## 轮次类型／三套基线／债务
结构治理轮；路径与文件名逐字等价；无新增债务。

## 改动
- `stage_layout.py`（L0）：新增 `SKILL_CONFIG_NAME`、`skill_config_path(project)`。
- `stage_config.py`：`CONFIG_NAME`、`path()` 委托给 stage_layout（`stage_config` 为 L3，不能被 L1 的 `stage_model_value` 依赖，所以权威落 L0）。
- `stage_model_value.py:13`、`skill_panel.py:642`：不再自拼，分别用 `stage_layout.skill_config_path`、`stage_config.path`。
- `architecture.md` 防复发条目登记新测试。

## 新增测试
`tests/architecture/test_skill_config_path_single_entry.py`：生产代码里只有 `stage_layout.py` 能写 `'skill_config.json'` 字面量。既有断言未动。

## 测试
- 已跑（隐藏桌面）：`run_selftests.py -k stage_config stage_model skill_panel stage_layout skill_config` 48 条全过；`smoke_test.py --architecture` 413 条，仅已知环境红（另 `test_architecture_guard_list…` 因 architecture.md 未登记新测试而红，登记后复跑 `test_agents_md` 仅剩已知环境错）。
- 未运行：`--all --safe`。

## 回滚
`git revert` 本轮提交。

## 下一步
07：J-Pet／J-Cloud 多写者属性收进单写者状态对象。
