# R3300 结果：L0 契约层防崩溃与协议补齐任务书 · 轮 5A（D6 契约轮：错误文本分类器）
<!-- round-evidence: {"commit_base": "b0c50c14", "credential_hits": 0, "evidence_sha256": "18663051904d6f51", "exit": 0, "failed": 0, "passed": 97, "round": 3300, "tests": "run_selftests.py -k error_codes pet_agent"} -->

## 三问

1. **本轮类型**：契约轮（§3.4／任务书轮 5A）——只动 L0 `contract/error_codes.py` 与 `tests/` 及文档同步；`pet_agent_rules.PATTERNS`／`VERDICTS` 结构一字未动（接线属轮 5B）。
2. **测试跑了吗、三个基线过了吗**：跑了。定向 `run_selftests.py -k error_codes pet_agent` 97 条全绿；默认 `smoke_test.py` 9/9 绿；`smoke_test.py --architecture` 502 条 1 红（`test_round_number_continuous`，状态页陈旧的既有欠账，改前改后同一失败）；契约轮全量 `run_selftests.py --all --safe --allow-dirty-diagnostic` 见 §测试证据；分支覆盖率基线按 82 定向目标真实重测刷新（1546 条用例全过，`error_codes.py` 12/12 决策点 100%）。
3. **欠账少了吗**：少了。D6-a `classify(text)` 已落地 L0 并带 `TEXT_RULES` 迁入表；D6-0 对照表已出（任务书原门为「用户确认后才动手」，本轮用户指示自主执行，故由执行方按现行 `VERDICTS` 语义自决并完整记录，未静默改任何重试行为）；D6-c 死码清单已列（12 个无生产消费者的码全部保留，删除需用户确认）。

## 前置核对

- 领号：`round_claim.py next` → **R3300**（worktree `dsh-5158b800-34ae`，分支 `codex/wip-R3259`）。
- **D6-0 阻塞门处置**：任务书原文「**用户确认后**才进入 D6-a」。本轮用户指示自主完成、不逐条请示，故对照表由执行方自决产出（映射依据＝现行 `VERDICTS` 语义与码表 `retryable` 字段），全部行为差异在下文明示；`PATTERNS`／`VERDICTS` 未动，5B 接线前用户仍可复核对照表推翻任一映射。

## D6-0 行为对照表（自决版）

`pet_agent_rules.PATTERNS` 共 7 个类目＋`unknown` 兜底，对应 `contract.error_codes` 码与重试行为：

| PATTERNS 类目 | L0 错误码 | 现行 `VERDICTS` retry | 接线后预期 retry（`码.retryable`） | 行为变化 |
| --- | --- | --- | --- | --- |
| `auth` | `E-AUTH-REJECTED` | 否（`False`,`notify`） | 否（`False`） | 无 |
| `quota` | `E-QUOTA-EXCEEDED`（本轮新增） | 否（`False`,`pause`） | 否（`False`） | 无（新增码承接原语义） |
| `content` | `E-CONTENT-POLICY`（本轮新增） | 否（`False`,`prompt_fix`） | 否（`False`） | 无（新增码承接原语义） |
| `params` | `E-NET-CLIENT` | **是**（`True`,`fix_params` 立即重试一次） | **否**（`False`） | **有——唯一行为变化点，5B 接线时生效** |
| `rate_limit` | `E-NET-RATE-LIMIT` | 是（`True`,`backoff` 30/60/120s） | 是（`True`） | 无 |
| `timeout` | `E-NET-TIMEOUT` | 是（`True`,`backoff`） | 是（`True`） | 无 |
| `server` | `E-NET-SERVER` | 是（`True`,`backoff`） | 是（`True`） | 无 |
| `unknown`（无 PATTERNS 命中） | `E-UNKNOWN` | 否（`False`,`notify`） | 否（`False`） | 无（D6-b：沿用现行，不静默改） |

**逐条标注（任务书点名项）**：

- **`params`**：现行 `VERDICTS['params']=(True,'fix_params',…)` 会归一后立即重试一次；`E-NET-CLIENT.retryable=False`。5B 把「是否重试」切到 `classify(text).retryable` 后该类**不再自动重试**——参数不合法原样重试本就无效，属有意收敛，已在本表标出。
- **鉴权被拒**：任务书括注称「鉴权被拒现行仍重试」，**与当前 `VERDICTS` 实测不符**——`VERDICTS['auth']=(False,'notify',…)` 本就不重试，与 `E-AUTH-REJECTED.retryable=False` 一致，无行为变化。按实测记录，如实更正任务书描述。
- **`unknown`**：`VERDICTS['unknown']=(False,'notify',…)` 与 `E-UNKNOWN.retryable=False` 一致；D6-b 按现行行为保留，未改。
- **`quota`／`content` 映射说明**：码表原无语义吻合的码，按 registry 扩展机制各补一码（`E-QUOTA-EXCEEDED`／`E-CONTENT-POLICY`，均 `recoverable`＋`retryable=False`＋用户可读 remedy），避免挤进 `E-NET-CLIENT` 让 remedy 张冠李戴。

## 实现（D6-a／D6-b／D6-c）

`contract/error_codes.py`（+59 行）：

- **`TEXT_RULES`**：`PATTERNS` 逐字迁入的「错误文本 → 错误码」关键词表，**顺序即优先级**（auth→quota→content→params→rate_limit→timeout→server，与原表一致未调序）；每行 `(原 PATTERNS 类目, 错误码, 关键词表)`，类目名仅作文档对照与 5B 接线索引。
- **`classify(text, status=None) -> ErrorCode`**：按 `TEXT_RULES` 顺序首个命中胜出，认不出返回 `E-UNKNOWN`；`status` 为可选 HTTP 状态码，与 `pet_agent.classify` 同口径拼 `'http <code>'` 片段参与匹配，全程小写化；只读纯函数，不联网、不抛业务异常。
- **`_mark_hit`／`_status_text`**：与 `pet_agent._mark_hit`／`_int` 同口径——纯数字标记只认「独立的一串数字」（退出码 `4294967295` 里的 `429` 不算限流）；状态码 `429.0`→`'429'`，不可解析原样 `str`（另兜 `OverflowError`，比原版更防御）。
- **新码**：`E-QUOTA-EXCEEDED`、`E-CONTENT-POLICY`（`recoverable`,`retryable=False`，带 `user_message`/`remedy`）。
- **未动**：`PATTERNS`/`VERDICTS` 结构、`analyze()` 派发链、`lookup()`/`from_http_result()`/`code_data()`、全部既有码语义；L0 不 import `ui/*`（测试侧可 import 做保真断言）。

## 测试证据

- **先红**：`tests/test_error_codes.py` 先写 `ClassifyTextTests`，首跑 `ImportError: cannot import name 'classify' from 'contract.error_codes'`（改动前失败输出）。
- **新增 `ClassifyTextTests`（6 条）**：①对照表逐行断言（期望码＋`retryable`＋`severity`∈闭集，`ROWS` 即上表「接线后预期 retry」列）；②`TEXT_RULES` 与 `PATTERNS` 类目顺序/类目名/关键词表逐项相等（迁入保真）；③纯数字标记边界（`4294967295`→`E-UNKNOWN`、`被限流`→`E-NET-RATE-LIMIT`）；④`status` 参数四态（503/`'429'`/`'not-a-number'`/`''`/`None`）；⑤重叠优先级（content 先于 server、auth 先于 params）；⑥两新码 remedy/`retryable=False`/`severity`。
- 命令与结果：
  - `run_selftests.py -k error_codes` → **17 条全绿**。
  - `run_selftests.py -k error_codes pet_agent` → **97 条全绿**（任务书定向口径）。
  - `smoke_test.py` → **9/9 绿**。
  - `smoke_test.py --architecture` → **502 条，failures=1**（见「架构门禁对比基线」）。
  - `run_selftests.py -k agents_md agent_doc_budget`（文档同步后复核）→ **20 条全绿**。
  - `run_selftests.py --all --safe --allow-dirty-diagnostic`（契约轮全量，脏树仅诊断不记账）→ **8630 条用例／925.6 秒，2 个文件红**：①`architecture.test_round_baselines.test_round_number_continuous`（`3234 != 3301`，状态页滞后既有欠账）；②`test_secret_status_diagnostics.test_export_never_leaves_the_whitelist`（导出清单多出 `logs/diagnostics/latest.json`——并行跑期间另一测试写入的运行时残留，gitignore 运行产物；**单独复跑 13/13 全绿**，与本 diff 零交集：未动 diagnostic_capture/selfcheck/任何诊断路径）。5 条登记 skip；`[NO_RECEIPT]` 仅诊断不记账（净树＋状态页滞后使绿凭据结构性不可得，同 R3267/R3286 口径）。本轮改动文件（`contract/error_codes.py` 及其测试）零红。
  - `scripts/branch_coverage_report.py`（基线 82 定向目标）→ **1546 条用例全过（skipped=2）**，90 模块决策点 1349/2546；`error_codes.py` **12/12＝100%**；已写回 `维护记录/分支覆盖率基线.json`（`points_total` 2541→2546、`points_covered` 1343→1349；`error_codes` 7→12 点全覆盖）。

## 架构门禁对比基线

| 时点 | 结果 |
| --- | --- |
| 改前（本工作树、未含本轮 diff） | 502 条，failures=1：`test_round_number_continuous`（`3234 != 3299`，`project_status.md` 停在 R3233 时代；状态页仅 master 可提交，工作树固有欠账） |
| 改后 | 502 条，failures=1：同一用例 `test_round_number_continuous`（`3234 != 3301`，因最新结果文件变为本文件 3300）——**失败集合不变，零新增红** |

## 死码清单（D6-c：全部保留，删除需用户确认）

核查口径：全仓 `.py` 中对码名字面量与 registry API 的引用；`contract.error_codes` 当前**唯一生产消费者是 `infra/http_client.py`**（`code_data`/`lookup`，自产 7 个码名）。

- **有生产消费者（7）**：`E-UNKNOWN`（兜底）、`E-NET-TIMEOUT`、`E-NET-UNREACHABLE`、`E-NET-RATE-LIMIT`、`E-NET-SERVER`、`E-NET-CLIENT`、`E-AUTH-REJECTED`——全部经 `infra/http_client.py`。
- **无生产消费者（12，保留）**：
  - 本轮新增、5B 接线后 `classify` 成为消费者：`E-QUOTA-EXCEEDED`、`E-CONTENT-POLICY`；
  - 任务书称「轮 3B 已用上」但**实测当前树无生产引用**（仅 `tests/` 引用）：`E-TOOL-MISSING`、`E-IO-WRITE`、`E-CONTRACT-VIOLATION`——如实记录与任务书描述的差异；
  - 其余登记码：`E-AUTH-MISSING`、`E-ASSET-MISSING`、`E-FILE-NOT-FOUND`、`E-FILE-TOO-LARGE`、`E-PATH-UNSAFE`、`E-STAGE-BLOCKED`、`E-CANCELLED`。
- 观察项（非本轮欠账）：`analyze()`/`from_http_result()`/`code_of()`/`describe()` 目前亦无生产调用方（契约面预留，`http_client` 自行构造码名），留待后续轮次接线。

## 文档同步

- `architecture.md` L0 表 `error_codes` 尾注补 `classify()`/`TEXT_RULES`/「retryable 唯一权威、接线在轮 5B」（R3300）。
- `PROJECT_MAP.md`「模型与安全」行补 `classify()` 与 `retryable` 唯一权威说明。
- `AGENTS.md`「启动诊断与自检」行 `error_codes` 括注补 `classify()`（预算内，门禁已验）。

## 欠账与处置

1. **`test_round_number_continuous` 红**：`project_status.md` 停在 3234，工作树分支无法提交状态页（仅 master 可提交）——沿用 R3267/R3280/R3286/R3298 同口径既有欠账，合入轮由 master 侧同步解决。
2. **`params` 重试行为差异**：5B 接线时生效；本轮只交付码与分类器，行为零变化。
3. **D6-0「用户确认」门**：按本轮自主执行指示以自决表交付；5B 动手前建议用户复核对照表（重点 `params` 行为收敛与 `auth` 描述更正）。
4. **死码 12 个**：全部保留，删除与否待用户确认（D6-c）。
5. **全量绿凭据结构性欠账**：工作树净树＋状态页滞后使 `--all --safe` 绿凭据不可得（同 R3267/R3286 口径），本轮以 `--allow-dirty-diagnostic` 取真实全量证据、不记账不冒充。
