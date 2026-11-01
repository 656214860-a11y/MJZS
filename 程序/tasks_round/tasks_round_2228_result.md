# R2228 无人值守链路对照表收成一份（结构治理轮·执行）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 06 的 J15：「下一阶段表收成一份 L3 定义，desktop_pet_bridge、desktop_auto_flows 改用」。

## 基线
分支 `codex/wip-R2228`，自 R2227。

## 轮次类型／三套基线／债务
结构治理轮·执行，数据原样搬迁，不改行为；分层无变化（落在已登记 L3 的 `desktop_auto_state`），无新增模块、无新增债务。

## 改动
`PET_STAGE_POLL`、`UNATTENDED_SWITCH`、`UNATTENDED_NEXT` 三张表迁入 `desktop_auto_state`，`desktop_pet_bridge`、`desktop_auto_flows` 改为导入；`desktop.py` 的原名转发入口不变。三张表是「阶段→轮询名」「轮询名→开关」「轮询名→下游」三种不同映射，不是三份重复，本轮收的是定义位置，并新增一致性断言。

## 新增测试
`tests/test_unattended_chain_tables.py` 3 条：两个消费方与单一定义是同一对象；三表引用同一组轮询名；下游表无环。既有断言未动。

## 测试
`run_selftests.py -k unattended_chain pet_ui desktop_auto auto_flow pet_bridge` 通过；`smoke_test.py --architecture` 仅余两条环境既有红项。未运行全量。

## 回滚
`git revert` 本轮提交。

## 下一步
J16（先写失败用例，贴改前输出）、J17。
