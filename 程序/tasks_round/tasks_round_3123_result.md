# R3123 功能轮结果：文件卡片与 HITL·轮 4/8——HITL 信封 + 审批门 + 用户选择卡
<!-- round-evidence: {"commit_base": "0da2284a", "credential_hits": 0, "evidence_sha256": "3a621fc063809b4b", "exit": 0, "failed": 0, "passed": 9, "round": 3123, "tests": "run_selftests.py -k hitl"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（任务书《文件卡片与 HITL 交互任务书》轮 4/8）。
2. **测试跑了吗、三个基线过了吗？** 跑了：`tests/test_hitl.py`（7/7）、`tests/test_hitl_ui.py`（2/2）、默认冒烟、架构门禁（见下）。未跑全量 `--all --safe`（非 master 提交点）。
3. **欠账少了吗？** 无新增欠账；把「选择卡/审批门/红绿 Diff 共用同一套 HITL 信封」落成 L2 数据契约 + L4 卡片组件。

## 改动

- 新增 `domain/hitl.py`（L2 纯数据契约，无 Tk/网络/读写盘）：
  - `RequestKind{CHOICE, APPROVE, DIFF}`、`Risk{LOW, HIGH}`、`Decision{APPROVE, REJECT, REGENERATE, EDIT, TIMEOUT}`；
  - `make_request(kind, payload, risk, timeout, request_id)`：统一信封（JSON 可序列化）；
  - `risk_of`：选择卡低风险；审批门按动作（delete/publish/overwrite/adopt/release/replace 为高风险）；
  - `auto_decision`：低风险自动放行，高风险返回 None（必须等人工，避免橡皮图章）；
  - `expired(request, now=)` + `timeout_decision()`：超时竞速（默认 300s，超时默认拒绝）；
  - `decide` / `apply_decision`：决策构造与回填（EDIT 合并 `updated_payload`，选择卡回填 `selected`）；
  - `from_confirm_result`：把 `confirm_gates.run()` 的 `ask` 结果转成选择卡请求。
- 新增 `ui/ui_hitl.py`（L4）：
  - `build_approval_gate`：确认采用／拒绝／重新生成 三按钮（`PrimaryButton`/`SecondaryButton` 语义组件），点击回调 `on_decision`；
  - `build_choice_card`：候选单选 + 确认，选中值随 `EDIT` 决策回填；
  - 间距全部取自 `SPACING`，按钮走 `ui_widgets` 语义组件（通过 `test_button_boundary` 与 `test_token_boundary`）。
- 新增测试 `tests/test_hitl.py`（7 条，无 Tk）与 `tests/test_hitl_ui.py`（2 条，真 Tk）。
- 基线同步：覆盖率基线 535→537（新增 `domain/hitl.py`、`ui/ui_hitl.py`）；skip 台账 +1（`HitlUiTests.setUp`）；`runbook §11` 同步。

## 测试证据

- `python -B tests/test_hitl.py` → `Ran 7 tests ... OK`。
- `python -B tests/test_hitl_ui.py` → `Ran 2 tests ... OK`。
- `python -B -m unittest tests.architecture.test_button_boundary tests.architecture.test_token_boundary` → 32 tests OK（语义按钮 + token 间距）。
- `python -B smoke_test.py` → `通过：9 项`、`失败：0 项`（退出码 0）。
- `python -B smoke_test.py --architecture` → `Ran 483 tests ... OK`（`✅ 架构治理测试：tests/architecture`；覆盖率基线 537、skip 台账 297 口径同步）。

## 契约变更（§2.4）

- 新增 L2 `domain/hitl.py` 信封与 L4 `ui/ui_hitl.py` 卡片组件；既有 `confirm_gates` 不改签名，新增 `from_confirm_result` 适配器（调用点收编留待 UI 接线）。
- 零第三方依赖不变。

## 范围外 / 已知缺口

- `confirm_gates` 现有调用点「全部走信封」的 UI 接线留待审批面板/阶段 UI 轮；本轮已提供适配器与卡片组件。
- 审批超时 `after()` 计时器绑定 UI 留待接线（数据层 `expired()` 已就绪）。
- 未跑全量 `--all --safe`（非 master 提交点）。

## 提交

- 分支 `codex/wip-R3123`；commit hash 见回填。
