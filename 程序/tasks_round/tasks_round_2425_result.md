# R2425 结果：拆分 pet_llm 的请求台账子系统到 request_ledger（L1）

## 三个必答（§7）

- **轮次类型**：结构治理轮·执行（§3.3）——按「代码重构可优化清单」优先级一 A 项，把 `pet_llm.py` 里的「请求级可对账台账」子系统（REQUEST_* 常量、request_ledger_path、BudgetRejected、RequestLedger、record_request）原样迁到新 L1 模块 `request_ledger.py`，`pet_llm` 按原名转发，行为零变化。
- **测试跑了吗、三个基线过了吗**：
  - 默认冒烟 `smoke_test.py`：**8/8 通过**。
  - 定向 `run_selftests.py -k request_ledger money_invariants`：**47 条 0 红**（RequestLedger 记账与金额不变量全绿）。
  - 架构 `smoke_test.py --architecture`：**416 条，4 个既有红**（均非本轮引入）：`pet_agent.py 1184>1182`、`desktop_media_pages.py::MediaPagesMixin 892>890`（并发会话重复应用的净增行数去重）、`test_script_stages_name_only_their_approved_00_references`（缺失 SKILL 引用文件）、`test_performance_history_is_declared_as_historical_only`（runbook §10 缺内容）。本轮拆分的尺寸/复杂度/分层/覆盖率门禁全绿。
  - 全量：未跑（不命中 §5 强制全量条件；沙箱无法派生工作进程）。
- **project_status.md 的欠账少了吗**：无新增欠账；4 个既有架构红欠账在 master R2422 即存在，非本轮引入。

## 本轮内容

### 拆分：`pet_llm.py` → `request_ledger.py`（L1）

把 `pet_llm.py` 末尾的「请求级可对账台账」子系统（O29，原第 518–1189 行，672 行）原样迁出：

- **迁出的名字**（`pet_llm` 按原名转发，调用方无感）：
  - 常量：`REQUEST_LEDGER_PATH`、`REQUEST_KINDS`、`REQUEST_STATES`、`REQUEST_MODES`。
  - 函数：`request_ledger_path`、`record_request`。
  - 类：`BudgetRejected`、`RequestLedger`。
  - 模块级锁 `_REQUEST_LOCK`（仅 RequestLedger.transaction 使用）。
- **`pet_llm.py`**：1189 → **518 行**（低于 1000 上限，从 `OVERSIZE_CAPS` 登记表删除）。
- **验证**：`pet_llm.RequestLedger is request_ledger.RequestLedger`（转发同一类对象）；`from pet_llm import RequestLedger / record_request / BudgetRejected` 等 75+ 处调用方与测试不受影响。

### 同步治理台账

- `tests/architecture/_layers.py`：`request_ledger` 登记为 L1。
- `tests/architecture/test_module_size_ratchet.py`：`pet_llm.py` 从 `OVERSIZE_CAPS` 删除（已 ≤1000 行）。
- `tests/architecture/test_complexity_ratchet.py`：`RequestLedger`（CLASS_CAPS 639）与 `settle`（PARAM_CAPS 8）键由 `pet_llm.py` 改为 `request_ledger.py`。
- `tests/architecture/test_coverage_baseline.py`：`CORE_FLOORS` 的 `pet_llm.py:50.0` 改为 `request_ledger.py:50.0`（计费不变量随台账迁移）。
- `维护记录/覆盖率基线.json`：`modules_total` 360 → **361**（重跑 `coverage_report.py` 刷新，`request_ledger.py` 实测 89.5% 覆盖，超 50 下限）。
- `runbook.md` §11：覆盖率口径 360/58 → **361/59**。

## 改动文件

- `request_ledger.py`（新增，L1，693 行）
- `pet_llm.py`（移除台账子系统，1189 → 518 行）
- `tests/architecture/_layers.py`、`tests/architecture/test_module_size_ratchet.py`、`tests/architecture/test_complexity_ratchet.py`、`tests/architecture/test_coverage_baseline.py`
- `维护记录/覆盖率基线.json`、`runbook.md`

## 遗留欠账

- 4 个既有架构红（见上「三个必答」），均在 master R2422 即存在，非本轮引入；其中 `pet_agent.py`、`desktop_media_pages.py` 两处是并发会话重复应用的净增行数去重，已两度还原又两度被重新写入，须停掉并发会话后另行收口。
- R2417/R2422 欠完整安全全量，由 post-commit 钩子后台自动补跑。

## 提交

- 已提交：是。commit hash 见 git log。
- 提交信息：`R2425: 拆分 pet_llm 请求台账子系统到 request_ledger（L1）`。
