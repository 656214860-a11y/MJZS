# R4258 结果：FIX-AUD-US03-G08 修复 G-08 连贯性裁决不生效
<!-- round-evidence: {"commit_base": "79fa309b", "credential_hits": 0, "evidence_sha256": "5829c031dc70eaa5", "exit": 0, "failed": 0, "passed": 63, "round": 4258, "tests": "run_selftests.py -k confirm_gates asset_plan continuity_ledger"} -->

## 开头三问

1. **本轮类型**：修复轮（任务卡 FIX-AUD-US03-G08，波次 W2，车道 codex/fix-aud-us03-g08，基准 79fa309b）。
2. **测试与基线**：新增复现测试改前 2 条红（与卡面缺陷一致）；改后定向 `run_selftests.py -k confirm_gates asset_plan continuity_ledger` 63 条用例全绿、退出码 0；`smoke_test.py --architecture` 700 条全绿、退出码 0。默认冒烟与全量未运行（不在卡面授权范围）。
3. **欠账**：本轮无新欠账。

## 缺陷复现（卡面证据核实链）

- `domain/asset_plan.py:236-238`（改前行号）：`_apply_gate_choice` 只认 `anchor:`/`canon:` 头，`conflict:` 选择静默返回 `None`、不落盘。
- `ui/desktop_automation_tick.py`：`pick_gate`（改前 284-287 行）与 `auto_decide_gates`（改前 332-333 行）都不看 `apply_asset_plan_gate_choice` 的返回值，无条件 `record_stage_confirmation`（默认 `state='applied'`），状态栏照写「已确认」。
- 结果：点 G-08「采用推荐」后 `gate_confirmations.json` 记 `state=applied`、`pending()` 不再摆出该条，界面显示已确认；而 `infra/continuity_ledger.adjudicate()` 仍是「先出现者优先」，人工裁决没有落点、等于没生效。

## 改前红（复现测试，未改产品时运行）

`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k confirm_gates asset_plan continuity_ledger`：63 条用例、1 个文件有红、退出码 1：

- `test_pick_gate_rejects_a_conflict_choice_instead_of_confirming_it` — `AssertionError: 'applied' == 'applied'`（conflict: 选择被误记 APPLIED）。
- `test_auto_decide_does_not_confirm_a_conflict_choice` — `AssertionError: 'applied' == 'applied'`（自动那一拍同样误记 APPLIED）。

## 修改位置（最小修复，保守方案）

- `ui/desktop_automation_tick.py` `pick_gate`：`apply_asset_plan_gate_choice` 返回 `None`（不支持的 key 没落盘）时改记 `state=FAILED` 留痕、状态栏写「该项暂不支持采用，未确认：…」、不再写「已确认」；anchor:/canon: 行为不变。
- `ui/desktop_automation_tick.py` `auto_decide_gates`：apply 返回 `None` 时 `continue`——不落盘、不记确认、不计入已处理条数。
- `domain/asset_plan.py`：仅 docstring，把「不支持的 key 返回 `None`＝明确拒绝、调用方据此拒绝记确认」写成明文契约；无行为改动。
- `tests/test_confirm_gates.py`：新增 `UnsupportedChoiceTests` 3 条（apply 拒绝契约、pick_gate 拒绝路径、auto_decide 不记确认）。

`conflict:` 裁决语义未扩展：台账 `adjudicate()` 与 G-08 候选生成原样未动；FAILED 记录在 `confirmations` 中保留 `choice` 字段（`test_stage_wiring.py:258` 既有断言继续通过）。

## 改后验证输出尾部

`run_selftests.py -k confirm_gates asset_plan continuity_ledger`（退出码 0）：

```
共 63 条用例，2.3 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
ALL TESTS PASSED
```

`smoke_test.py --architecture`（退出码 0）：

```
----------------------------------------------------------------------
Ran 700 tests in 246.897s

OK
✅ 架构治理测试：tests/architecture
```

## 未验证项

- 默认冒烟 `smoke_test.py` 与全量 `run_selftests.py --all --safe` 未运行（卡面只授权两条命令）。
- 真 Tk 界面下连贯性页点「采用推荐」的完整观感未跑（`pick_gate` 经 `AutomationTickMixin.__new__` 桩验证状态栏与确认账本；`test_stage_wiring.py:252-258` 既有用例覆盖真 Desktop 路径，未在本轮范围内运行）。
- `adopt_asset_plan_choice`（资产详情页 `_pick`）对 `conflict:` key 仍会把 `None` 返回当成功记 APPLIED——该路径 UI 只挂 G-05/G-06（`ui/asset_detail.py:267`），本轮不可达且文件不在允许范围，未改。
- 半自动／全自动档下 `pending_gate_asks` 中的 conflict: 项会每拍重试一次 no-op（不落盘不写文件），item 保持待办直到支持为止。

## 卡外发现

- `stage_execution_service.adopt_asset_plan_choice` 不看 apply 返回值，若未来给 `conflict:` 接通裁决落点，这条路径需一并复核（本轮范围外，未改）。
