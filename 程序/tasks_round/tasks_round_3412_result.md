# R3412 结果 —— K8 Severity 统一
<!-- round-evidence: {"commit_base": "0e3fc763", "credential_hits": 0, "evidence_sha256": "fb4904744797e32a", "exit": 0, "failed": 0, "passed": 241, "round": 3412, "tests": "run_selftests.py -k error_codes diagnostics selfcheck startup_selfcheck pet_agent branch_coverage"} -->

1. **本轮属于 §3 哪种类型？** 对照表阶段 §3.5 只读诊断＋实施阶段 §3.4 契约轮（任务书「轮 K8」明示双阶段）。车道 L0，前置 K0＋G-0（已满足）＋G-2（执行模型按判据自决，用户已授权）。
2. **测试跑了吗、三个基线过了吗？** 跑了。定向 `run_selftests.py -k error_codes diagnostics selfcheck startup_selfcheck pet_agent`：**210 条全绿**（0 红 0 跳过，107.5s，含 test_error_codes 19、test_selfcheck 16、startup_selfcheck 四片 45、pet_agent 六片 80、diagnostics 相关 50）；默认冒烟 9/9；`smoke_test.py --architecture` 542 条——`test_round_number_continuous` 为特性分支预期形态（合并轮抬头解决）、`test_baseline_decision_points` 因 error_codes 决策点 12→11 已重测刷新基线后转绿；`run_selftests.py --all --safe` 已实际跑完（排队等 `full-safe-selftest.lock` 后获锁执行，约 17 分钟）：5 个测试模块各 1 条红——`architecture.test_round_baselines.test_round_number_continuous`（状态页 3409≠最新结果 3412+1，特性分支结构性形态：`project_status.md` 仅 master 可提交、合并轮 `MERGE_HEAD` 豁免，分支上必红）＋`test_shared_adapter_infrastructure`/`test_ui_edges_guards`/`test_pet_ui`/`test_perf_baseline` 四项，与 master 侧 auto_full_safe 在 HEAD `0e3fc763` 的红集完全相同（`auto-full-safe-result.json` returncode=1，2026-11-18T21:07，含资产页 CPU 10.5×>10.0× 负载敏感断言），系既有 master 欠账，与本轮 contract 改动零相关，K8 归因新增红=0（汇总打印段 GBK 控制台 UnicodeEncodeError 属已知环境噪声，测试本体已全部执行）。绿色凭据按 runbook §4 由合入后 master 侧 auto_full_safe 补跑产生，`.git/full-safe-receipts.json` 为唯一权威（末笔绿树凭据为 R3293）。
3. **欠账少了吗？** 无新增欠账；FF-10（severity 词表双轨）从 2 套收敛为 1 套——`contract.diagnostics.Severity` 五值枚举成为唯一权威，`error_codes` 字符串闭集删除。

## 开工与领号

- 车道 `devin-l0-constitution`／分支 `codex/l0-constitution`；K9 合入后分支快进至 master `0e3fc763`；`round_claim.py next` 领 **R3412**。

## K8-1 旧→新对照表与消费者清单（G-2 自决留痕）

### 旧词表（改前）

| 词表 | 位置 | 值 |
| --- | --- | --- |
| `diagnostics.Severity`（str Enum） | `contract/diagnostics.py` | fatal / error / warn / degraded（4 值） |
| `error_codes` severity（字符串闭集 `SEVERITIES`） | `contract/error_codes.py` | fatal / degraded / recoverable / info（4 值） |

### 统一后词表（K8 判据 4：并集减 recoverable）

`Severity` = **fatal / error / warn / degraded / info**（5 值；`diagnostics.Severity` 补 `INFO`，`error_codes` 删 `recoverable`）。

### 逐值映射（error_codes 侧）

| 旧值 | 新值 | 涉及码 |
| --- | --- | --- |
| fatal | `Severity.FATAL` | 无（码表本就无 fatal 码） |
| degraded | `Severity.DEGRADED` | E-CONTRACT-VIOLATION、E-TOOL-MISSING |
| recoverable | `Severity.WARN`（判据 5） | 其余 16 码 |
| info | `Severity.INFO` | E-CANCELLED |

### `diagnostics.Severity` 各值消费者清单

| 值 | 生产消费者 | 行为 |
| --- | --- | --- |
| FATAL | `desktop_launcher.launch()`（`is Severity.FATAL` → `notify_startup_fatal`＋`SystemExit(1)`，fail-closed）；`infra/diagnostic_capture.py:682`（FATAL→DEGRADED 降级挂 escape_hint）；`contract/selfcheck.py:79`（内建检查失败产出） | 拦截启动 |
| DEGRADED | `desktop_launcher`（非 FATAL 全部进 `degraded_items` → `window._selfcheck_degraded` 放行＋可见警告）；`diagnostic_capture.py:237` 产出、`:687` 降级目标；`selfcheck.py:37`（检查自身异常永不升级 FATAL） | 放行降级播报 |
| ERROR／WARN | 仅枚举定义与测试构造（`test_selfcheck` 注入检查用 WARN/ERROR），生产零产出零消费 | — |
| INFO | 新增（K8）；生产零产出零消费 | — |

### `error_codes.severity` 消费者清单

**生产代码零消费者**：`lookup/describe/code_data/classify/analyze` 均不暴露 severity；`pet_agent.retry_plan` 与 `VERDICTS` 只读 `retryable` 与类目动作；`infra/http_client`、`model_router`、`tts_api` 只用 `code`/`retryable`/`code_data`。测试侧 `test_error_codes.py` 断言闭集与抽查值，已同步。

### 判据逐条自决

1. **启动行为不变** ✓：Diagnostic 侧 severity 值与 `is Severity.FATAL` 判定逐字未动；error_codes.severity 不参与启动路径。`test_startup_selfcheck` 45 条全绿。
2. **重试行为不变** ✓：`retryable` 字段与取值未动；全仓无任何 `severity`→重试 分支（判据 5 的「改读 retryable」情形不存在——生产本就只读 retryable）。`pet_agent` 80 条全绿。
3. **用户可见级别不变** ✓：`diagnostic_capture` 序列化经 `.value` 取字符串，枚举值不变 → 报告行 `severity` 字段逐字一致（`test_startup_selfcheck:192` 断言 `'degraded'` 仍绿）；`【警告】` 播报由 degraded_items 驱动，触发条件不变。error_codes.severity 无任何 UI 展示路径，`recoverable→warn` 不可见。
4. **词表＝并集减 recoverable** ✓：`Severity` 五值，无新增。
5. **recoverable→warn** ✓：16 个码映射完成；`severity=='recoverable'` 分支生产零处（仅测试断言，已改 `Severity.WARN`）；`test_recoverable_value_is_rejected` 证明旧值构造即 `ValueError`。
6. **兼容读取退路**：不需要——判据 1–3 全部满足，无行为变化。

## K8-2 类型统一

- `ErrorCode.severity: Severity`（`contract.diagnostics.Severity`），`__post_init__` 经 `Severity(self.severity)` 归一：收枚举成员与 `'fatal'/'warn'/...` 字符串，非法值（含 `recoverable`）`ValueError`。
- `SEVERITIES` 改为 `frozenset(m.value for m in Severity)` 派生值——不再是字符串字面量闭集；`_ITEMS` 表直接写枚举成员。
- 全仓复扫：无第二处错误级 severity 字符量闭集（`infra/continuity_ledger.SEVERITIES` 是连续性问题「高/中」展示级、`media_page` severity 列同域，属另一词表不在本轮范围，已注明）。

## K8-3 recoverable 删除

- 码表 16 处 `'recoverable'` → `Severity.WARN`；`SEVERITIES` 字面量闭集删除；重试判定唯一权威仍是 `retryable`（`pet_agent.retry_plan`、`VERDICTS` 路径未动）。
- 测试证明：`test_golden_table_code_severity_retryable`＋`test_recoverable_value_is_rejected`＋`pet_agent` 80 条回归。

## K8-4 黄金样本

`test_error_codes.py::test_golden_table_code_severity_retryable`：19 个码整份对照 `(Severity, retryable)`，含集合相等断言（新增删码必改黄金样本）。

## 改动清单

- `程序/contract/diagnostics.py`：`Severity` 增 `INFO='info'`，docstring 更新为五值闭集并注明与 error_codes 同词表。
- `程序/contract/error_codes.py`：import `contract.diagnostics.Severity`；`SEVERITIES` 改枚举派生；`ErrorCode.severity` 类型 `Severity`＋`__post_init__` 归一；`_ITEMS` 全部枚举成员（recoverable→WARN×16）。
- `程序/tests/test_error_codes.py`：闭集断言改五值派生口径；抽查值改枚举；新增黄金样本与 recoverable 拒绝测试。
- `程序/tests/test_selfcheck.py`：四值→五值闭集断言。

## 分支覆盖率基线刷新（同 K2 口径）

`error_codes.py` 决策点 12→11（`__post_init__` 由 `if … not in SEVERITIES` 校验改为 `Severity()` 归一，少一个分支点）。按 `scripts/branch_coverage_report.py` 原 90 个目标全量重测（`tests_ok=true`）：error_codes 11/11=100%（下限 100 保持）；连带 publication 64.5→61.3（下限 61.0）、file_index 80.6→79.6（下限 78.0）为同一次定向测量波动、均在棘轮下限之上；基线已写回 `维护记录/分支覆盖率基线.json`，`run_selftests.py -k branch_coverage` 31 条全绿。

## 边界与后续

- `diagnostics.Severity` 的 ERROR/WARN/INFO 生产侧仍零产出（枚举保留位，判据 4 要求并集五值）；后续轮次若要启用 INFO 级诊断，词表已就位。
- K8 后 FF-10 口径：severity 词表 2→1。FF-04/FF-05 台账不受影响（error_codes 新增的 `contract.diagnostics` import 属第一方包，纯度门禁不计）。
- 剩余轮次：K1/K3–K7/K10–K11E/K12–K20 均前置 K1 或 G-1（6 个地基分支未合），K8 完成后本车道无其他可解锁轮次，转入门态监控。
