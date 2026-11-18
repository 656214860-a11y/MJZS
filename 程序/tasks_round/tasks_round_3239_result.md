# R3239 结果：L0 契约层任务书轮 0 — 基线同步与重测
<!-- round-evidence: {"commit_base": "3a2d169c", "credential_hits": 0, "evidence_sha256": "93e0530a358af8b4", "exit": 0, "failed": 0, "passed": 0, "round": 3239, "tests": "docs-only"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.11 状态接续轮（任务书轮 0）。不改任何 `.py`；合入 master、重测任务书 §2 行号与计数并就地更新、核对三项前置条件。
2. **测试跑了吗、三个基线过了吗？** 未运行。任务书 R0 验收明确「不跑 smoke／selftest」；本轮无代码改动，三个基线沿用 master R3233 状态，如实标注未复测。
3. **欠账少了吗？** 没有减少。本轮只同步基线与更新任务书；新增核对结论见 §3，其中 R0-e 的 Q9 不符记为欠账移交。

---

## 1. R0-a 基线同步

- 工作树：`D:\漫剧制作助手\.agents\worktrees\dsh-5158b800-34ae`，领号时 `round_claim.py next` 因脏树（任务书＋R3230 结果未跟踪）自动切到 `codex/wip-R3239` 并原样带入。
- 分支基点：R3213 `d29e1e83`（detached 于 master 历史内，ahead=0）。
- `git merge master`（master=`3a2d169c` R3233，领先 23 个提交）→ **快进合并**，无冲突，分支现与 master 同点。
- 合并带入：T10 包化实体迁移（`ui/`、`infra/`、`domain/`、`orchestrator/`）、`维护记录/依赖白名单.md`、`tests/architecture/test_dependency_whitelist.py`、R3214–R3233 各结果文件等。

## 2. R0-b 重测对照表（任务书 §2 已就地更新）

| 项 | 旧值（R3213） | 新值（master R3233） | 结论 |
| --- | --- | --- | --- |
| `contract/` 模块数 | 32（含 `__init__` 33） | 32（含 `__init__` 33） | 不变 |
| `contract/` 总行数 | 5,990 | **6,028** | +38 |
| `script_contract.py` | 1,112 行 | **1,103 行** | -9 |
| `platform_tools.py` | 810 行 | **809 行** | -1 |
| `stage_layout.py` | 473 行 | **472 行** | -1 |
| L0 登记 | 32/32 | 32/32（`_register(0,...)` 现分散多处） | 不变 |
| 顶层同名门面 | 6 | 6（同名单） | 不变 |
| `contract→agent.*` 反向 import | 11 处 / 7 文件 | 11 处 / 7 文件（`script_contract` 行号 :834/:908） | 数量不变，行号已更新 |
| `agent/` 子模块行数 | core 282 / media 123 / publication 210 / shot_assets 157 / prompt_optimizer 225 / volcengine 107 / wan 85 / video 13 / voice_mcp_server 256 / optimizer_mcp_bridge 54 | core **305** / media **122** / publication **209** / shot_assets **156** / prompt_optimizer **224** / volcengine **106** / wan **84** / video **12** / voice_mcp_server **255** / optimizer_mcp_bridge **53** | 全部重测 |
| `agent.media` 消费者 | 约 5 个文件 | **约 11 个文件**（新增 engine/stage_completion_service/stage_gate_gateways/keyframe_import/skill_tools 等） | 「不得整删」结论加强 |
| 扇入排行 | project_context 51 居第 3 | `project_context` 直接契约 import 实为 **29**（旧口径含约 24 个 L3 工厂再导出）；榜首仍 platform_tools 73 / pet_bus 66 | 口径已在任务书 §2.2 注明 |
| `domain/message_parts.py` 登记 | 未登记（D0） | **仍未登记** | D0 仍需轮 1 执行 |

### 关键行号漂移（已写回任务书 §2.3／新增 §2.5b 实体位置表）

- `pet_ui_stages.py` → `ui/pet_ui_stages.py:35,99`；`emit_verified_completion` 定义在 `orchestrator/stage_completion_service.py:779`。
- `broadcaster.py` → `infra/broadcaster.py`（`PREFIX_PATTERNS:9`、匹配 `:28`）；顶层实体已删。
- `continuity_ledger.py` → `infra/continuity_ledger.py`（`{'version':1}` 写入仍 `:236,585,610`）。
- `pet_state.py` → `infra/pet_state.py:87-89`；`usage_snapshot.py` → `infra/usage_snapshot.py:182`；`desktop_automation_tick.py` → `ui/desktop_automation_tick.py:69,78,101`；`desktop_settings_service.py` → `domain/`（`.corrupt` 回落 `:9-24`，`desktop.py:220` 注入）；`storyboard_catalog_service.py` → `domain/`（`os.walk:46`）；`stage_parallel.py` → `orchestrator/`（`retry_attempts:128`）；`skill_orchestrator.py` → `orchestrator/`（`verified_stage_output:47`、`self.errors:156`、emit_safe `:569,621,627,631,634`）。
- `service_contract.py`：四字段 `:15-18`（`recoverable:17`）；`success()` 仍传 `recoverable=False`（`:44`）；`is_failure()` `:47-49`；`UserError`/`SystemError` 默认值仍同为 `recoverable=True`（`:23`/`:30`）；新增 `Cancelled` 类（`:34-38`）。
- 启动路径四入口复测：`app.py`（1486 行，`validate_`×2 均为 `:678,:685` 的 `validate_episode` 内容校验，非契约自检）、`desktop.py`（964 行全 0）、`desktop_launcher.py`（28 行全 0，`:27` 构造 `Desktop`）、`启动漫剧制作助手.pyw`（仅 `MessageBoxW`×1 `:119`）。
- §9.2.1 启动器保护有洞**在 master 上仍成立**：`pyw:9` `import hash_backend`、`:10` `from contract.app_metadata import APP_NAME`、`:13` `app_logging.install` 均在 `try`（`:14`）之外；`except` 分支 `:111` 仍 `from contract.app_metadata import VERSION`。
- `agent/core.py:13,36,67,72,76` 仍 import `agent.publication`；`prompt_optimizer.py:7-14` 仍 import tkinter/ui 件；`shot_assets.py:118`、`voice_mcp_server.py:136` 交叉依赖仍在。
- `contract/` 全目录 grep `severity|health|readiness|degraded` 仍零命中。

## 3. R0-c / R0-d / R0-e 核对

- **R0-c**：`git merge-base --is-ancestor codex/whitelist-framework master` → **NOT_MERGED**。whitelist 分支领先 master 4 个提交（R3218 命名规范、R3220 requests 传输、R3224 白名单锁定、R3227 运行环境闭包）。**轮 3B、4B 在其合入 master 前不得开工**；轮 1、2、3A、4A、5A、6A–6D、7A、7B 不受影响，可先行。
- **R0-d**：`程序/维护记录/依赖白名单.md` 与 `程序/tests/architecture/test_dependency_whitelist.py` 已在合并后的树中存在 → 轮 3B 的「依赖白名单不符」检查项具备落点（仍受 R0-c 门控）。
- **R0-e**：whitelist 树 `contract/platform_tools.py:552` 的 `RequestsJsonOpener.open()` **每次调用新建 `requests.Session()` 并在 finally `session.close()`**，不是 Q9 要求的「懒建 Session 单例，首次调用建一次」。按任务书「本任务书不代做」，结论：**不满足 Q9**。处置建议（移交）：whitelist 线合入前补懒建单例，或由用户裁定接受逐次建 Session。已记入任务书 §6「R3239 轮 0 实测状态」。

## 4. 本轮改动清单

- `程序/tasks_round/L0契约层防崩溃与协议补齐任务书.md`（新建入库＋§2 行号计数就地更新＋§6 增 R3239 实测状态）
- `程序/tasks_round/tasks_round_3230_result.md`（R3230 只读诊断结果补登入库）
- `程序/tasks_round/tasks_round_3239_result.md`（本文件）

## 5. 验证与基线

- 测试：未运行（轮 0 不跑）。
- 冒烟基线 8/8：未复测（无代码改动）。
- 架构门禁：未复测。
- 全量凭据：未运行。

## 6. 下一步

轮 1（D0＋D1 修复轮）：`storyboard_contract.py` 的 `writing.py` 路径修复＋`tests/architecture/_layers.py` 登记 `domain.message_parts`。开工前按规则 27 重新领号。
