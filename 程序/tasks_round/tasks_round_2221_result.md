# R2221 直连文本模型也过计量（修复轮）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 04 的 J11：`edit_habits`、`skill_notes` 直连 `PoolAdapter` 改走计量入口。

## 基线
分支 `codex/wip-R2221`，自 R2216。

## 轮次类型／三套基线／债务
修复轮；分层无新增（`model_metering` 仍无导入），无新增债务。

## 改动
- 缺陷：修改习惯归纳（`edit_habits`）与技能说明翻译（`skill_notes`）直接调 `adapter.chat`，不授权、不结算，项目设了金额上限也拦不住，用量也不入账。
- 修复：`model_metering.chat_metered(adapter, ledger, stage, messages, options, model, system)`；有台账走 `metered`（授权被拒抛 ValueError，发送失败结算后重抛），无项目则是原来的普通调用。两处各自 `RequestLedger(project)` 后传入（避免 L1 内部循环导入）。
- 项目来源：`edit_habits.summarize` 用已有的 `root`；`skill_notes.translate` 新增可选 `project`，`skill_panel` 传 `desktop_project(self.desktop)`（可为空，则不计量）。

## 新增测试
`tests/test_direct_chat_metering.py` 3 条：金额上限 0 时两处都在发送前被拒、适配器未被调用；归纳成功后台账文件落盘。先写后实现，改前输出 `TypeError: _api_summarizer() takes 1 positional argument but 2 were given`（旧接口没有项目入口，即无法计量）。

## 测试
`run_selftests.py -k direct_chat_metering edit_habits skill_notes skill_panel model_metering writing_api pet_llm` 通过；`smoke_test.py --architecture` 仅余环境既有红项（轮次连续、基准历史）。既有断言未动。未做：真机跑修改习惯归纳／技能翻译的实际计费目视。

## 回滚
`git revert` 本轮提交。

## 下一步
J12（重试口径收进一处，两种口径显式命名）。
