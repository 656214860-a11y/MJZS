# R2214 模型调用计量收成一个入口（结构治理轮·执行）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 04 的 J10：计量序列（估算 → 授权 → 结算）收进一个入口，`writing_api` 改调。

## 基线
分支 `codex/wip-R2214`，自 R2208。

## 轮次类型／三套基线／债务
结构治理轮·执行，等价委托，不改行为。分层：新增 L1 `model_metering`（无导入），`层级` 台账不变；无新增债务。

## 改动
- 新增 `model_metering.py`：`metered(ledger, request, send, usage_of, on_result=None)` → `(result, usage, rejected)`。授权被拒（ValueError／OSError）只来自授权那一步，发送里抛的 ValueError 不会被误当预算错误；发送抛错按未知用量结算后原样抛出；`on_result` 在结算前调用。
- `pet_llm._attempt`、`writing_api.WritingRequestAdapter._call` 改调；无项目（无台账）路径仍是直接调用。
- 起初放在 `RequestLedger` 方法里，触发类行数／参数个数／模块行数三个棘轮，不抬登记值，改放新模块；`pet_llm.py` 上限随实际降到 1190。
- 保留差异（统一会搬数据位置，属行为改动，不在结构轮做）：`pet_llm` 诊断写 `<项目>/model_diagnostics`，`writing_api` 若有诊断写 `<项目>/logs/model_diagnostics`；两处拒绝返回的字段与 reason 各自保留。

## 登记
`_layers.py` L1 += `model_metering`；覆盖率基线 338/51；runbook 138 行；architecture.md L1 行与段落。

## 新增测试
`tests/test_model_metering.py` 4 条（顺序、授权被拒不发送、发送异常结算后重抛、发送内 ValueError 不当预算错误），无 Tk、无网络。

## 测试
`run_selftests.py -k request_ledger pet_llm writing_api token_saver` 通过。`tests/test_writing_api_output_budget.py::test_transport_crash_releases_money_reservation_and_reraises` 仅同步 mock（真实 `RequestLedger` 只替换授权／结算两端），断言未动。`smoke_test.py --architecture` 仅余环境既有红项（轮次连续、基准历史），提交前复跑确认。

## 回滚
`git revert` 本轮提交。

## 下一步
J11（`edit_habits`、`skill_notes` 直连 `PoolAdapter` 改走计量入口，先写失败用例）。
