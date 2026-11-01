# R2223 重试口径显式命名（结构治理轮·执行）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 04 的 J12；A 节记录的口径冲突：`pet_llm` 把 HTTP 500 当可重试，`model_router.failure_policy` 把 500 当「可能已受理、不重试」。

## 基线
分支 `codex/wip-R2223`，自 R2221。

## 轮次类型／三套基线／债务
结构治理轮·执行，等价委托，不改行为；分层无变化，无新增债务。

## 改动
- `model_metering` 新增两个显式命名的口径：`replayable_retry(status)`（对话可重放，状态集 `REPLAYABLE_RETRY_STATUS` 由 `pet_llm.RETRYABLE_STATUS` 原值迁入）与 `submission_retryable(acceptance, reason_code)`（提交可能已受理，原 `failure_policy` 内联表达式迁入）。
- `pet_llm.is_retryable`、`RETRYABLE_STATUS` 与 `model_router.failure_policy` 委托它们；`model_pool` 注释同步。两种口径都保留，未裁决合并。
- `ModelRouter.chat` 目前按提交口径（`failure_policy`）判断是否换备选模型，且无生产调用方；它处理的是对话请求，是否改用对话口径属于行为改动，等有真实调用方时按调用方核实，本轮不改并在此登记。

## 新增测试
`tests/test_model_metering.py::RetryPolicyNamingTests` 3 条：500 在对话口径可重发、提交口径不可；提交口径只放行确认未受理的限流／服务端错误；旧入口与新命名一致。既有断言未动。

## 测试
`run_selftests.py -k model_metering model_router model_failure adapter_failure pet_llm model_pool` 通过；`smoke_test.py --architecture` 仅余环境既有红项。

## 回滚
`git revert` 本轮提交。

## 下一步
候选 04 完成。下一组：J13–J14（候选 08 引擎适配器去重）。
