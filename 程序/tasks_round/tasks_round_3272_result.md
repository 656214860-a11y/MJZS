# R3272 结果：L2 领域服务层优化任务书（只读诊断轮）
<!-- round-evidence: {"commit_base": "8317c4cc", "credential_hits": 0, "evidence_sha256": "5242b259d16fea54", "exit": 0, "failed": 0, "passed": 0, "round": 3272, "tests": "docs-only"} -->

## 三问

**1. 本轮属于 §3 哪种类型？**
只读诊断轮（`AGENTS.md` §3.5）。保持 `.py` 不变，不搬目录、不重命名、不删文件。写入范围：新增 2 份任务书文档 + 8 处文档口径统一，零生产代码改动。

**2. 测试跑了吗、三个基线过了吗？**

| 基线 | 结果 |
| --- | --- |
| 默认冒烟 | **9/9 通过**（`smoke_test.py`，0 失败） |
| 依赖门禁 | **15/15 通过**（`tests.architecture.test_dependency_whitelist`） |
| 架构门禁 | **未运行**——只读诊断轮按 §5 默认不跑；本轮无 `.py` 改动，无层级登记变动 |
| 全量回归 | **未运行**——同上，且本轮不产生源码改动 |

**3. 欠账少了吗？**
不少也不增。本轮把 L2 的全部欠账**固化成了可领走的需求**（10 轮拆解 + 8 条跨层需求编号），但未关闭任何一项——这是只读诊断轮的定义边界。

---

## 交付物

| 文件 | 内容 |
| --- | --- |
| `程序/tasks_round/L2领域服务层优化任务书.md` | 主任务书：7 节结构、10 轮拆解（轮 0–9）、新增 4 模块设计、验收总清单、12 项明确不做 |
| `程序/tasks_round/L2跨层依赖需求单.md` | 跨层需求：8 条编号需求（L2-X1–X8），分属 L0 契约轮 / L3 编排轮 / 用户拍板 |
| 8 处文档口径统一 | 见下表 |

### 文档口径统一清单

| # | 文件 | 原口径 | 改后 |
| --- | --- | --- | --- |
| 1 | `维护记录/依赖白名单.md` §一 | 「谨慎白名单：按实际用途逐项评估」 | 「白名单准入」+ 新增「已登记能力优先复用成熟实现，不自造通用轮子」准入段 |
| 2 | `AGENTS.md` §1 | 「白名单依赖」 | 「白名单依赖（准入规则见 `维护记录/依赖白名单.md`）」 |
| 3 | `CLAUDE.md` | 「谨慎白名单依赖」 | 「白名单依赖（准入规则见 …）」 |
| 4 | `pyproject.toml` 首行 | 「运行时零第三方依赖」 | 「生产运行时只交付 requirements.txt 锁定的白名单包」 |
| 5 | `README.md:340` | 「运行期零第三方依赖」 | 「生产运行时只交付白名单锁定的第三方包」 |
| 6 | `dev-requirements.txt` 首行 | 「运行时仍零第三方依赖」 | 「生产运行时只交付 requirements.txt 锁定的白名单包」 |
| 7 | `project_status.md:33` | 「零第三方依赖，12 阶段」 | 「白名单依赖，13 阶段」（阶段数亦过时，一并纠正） |
| 8 | `GLOSSARY.md:12`、`说明/账户会员云端立项前清单.md:11` | 「零第三方依赖」 | 「只含白名单锁定的第三方包」／「只交付白名单包」 |

**保留未改（判定为准确事实或历史证据）**：
- 描述**单个脚本**只用标准库的表述（`coverage_report.py`、`branch_coverage_report.py`、`aigc_lint.py`、`ui_snapshot.py`、`platform_tools.py` WebSocket/waveIn、`voice_mcp_server.py`）——这些是准确的技术事实。
- `tasks_round/`、`docs/review/`、`维护记录/状态历史归档.md` 等历史记录——证据不追改。
- `说明/零依赖边界与媒体预览预案.md`——该任务书已完成，属历史。
- `说明/账户会员云端设计.md`——云端依赖策略是独立议题，只登记不改。

---

## 关键技术结论（全部本树实测）

### 推翻的两个常见误判

1. **「L2 依赖倒置被大面积破坏」——不成立。** `domain/` 内 `json.dump` 0 处、`write_text`/`write_bytes` 0 处、`os.replace` 0 处、`import tkinter` 0 处。写入边界被 `test_atomic_write_boundary.py` 守死，底座是干净的。
2. **「新增模块会触发门禁硬阻塞」——不成立（本人上轮判断有误，已作废）。** 门禁只要求**同步刷新基线**，工具已存在（`scripts/coverage_report.py`），9 组目标用例体量 1.5–36 KB，覆盖率为 0 不触发失败（653 模块里 579 个本就是 0）。企业标准（InvokeAI 55 个子目录、Dify 31 个能力目录）恰恰是单独建模块。

### 真实缺陷分布

| 类别 | 数量 | 关键位置 |
| --- | --- | --- |
| 事务重复实现 | 7 处，其中回滚不完整 5 处 | `asset_batch_service:198-208`、`video_prompt_publication:99-104`、`white_model_service:599-606`、`idea_chat:450-456` |
| 并发缓存无锁 | 3 模块 / 6 个 dict | `white_model_service:18-23`、`idea_transcript:20`、`video_task_state:30` |
| 付费调用无幂等 | 1 个致命（`recon_service`）+ 2 个无标记 | `recon_service:117/141` |
| 自造结果契约 | 5 处 / 5 模块 | `recon_service:398`、`voice_ai:63-87`、`handoff_service:136,173`、`pet_test_service:46`、`white_model_service:262` |
| 硬违规 | 2 处 | `tts_api:512-537`（规则 42）、`white_model_service:414`（规则 12） |
| 版本键名 | 3 套并存 + 10 模块无版本 | 见跨层需求单 L2-X1–X3 |
| 重复事实 | 5 组 | 见跨层需求单 L2-X4–X6 |
| 领域事件 | 0 | `pet_bus.emit_safe` 在 domain 零调用 |

### 新增模块决策（用户 Q9 修正后）

| 新模块 | 层 | 替代掉的重复 |
| --- | --- | --- |
| `infra/unit_of_work.py` | L1 | 7 处事务 + 3 套备份底座 |
| `infra/business_log.py` | L1 | 38 条零字段中文日志 |
| `infra/idempotency.py` | L1 | 14 模块手搓 sha256（39 处 hashlib） |
| `domain/domain_events.py` | L2 | 0 → 1 事件出口 |

前三项属 L1 而非 L2：它们不含业务规则；只有第四项需知道业务语义。

---

## 分轮表（10 轮）

| 轮 | 类型 | 内容 | 触发全量 |
| --- | --- | --- | --- |
| 0 | 只读诊断轮 | 本任务书 + 需求单 + 口径统一 | 否 |
| 1 | 结构治理轮 | 空壳落地 + `_layers` + `architecture.md` §3 + 基线刷新 | 是 |
| 2 | 功能轮 | `idempotency.py` + `recon_service` 幂等 | 否 |
| 3 | 修复轮 | 3 处并发缓存加锁 | 否 |
| 4 | 功能轮 | `domain_events.py` + 3 个高频事件 | 否 |
| 5 | 功能轮 | `unit_of_work.py` 实现 | 否 |
| 6 | 修复轮 | 事务原语接入 7 处 | 是 |
| 7 | 功能轮 | `business_log.py` + 8 大模块接入 | 否 |
| 8 | 结构治理轮 | 4 处自造契约收口 | 否 |
| 9 | 修复轮 | 2 处硬违规 | 否 |

排序依据是**改动风险**（L2-D11），不是业务痛感：单模块幂等最先（风险最小、收益最直接），7 处事务最后（横扫 7 模块、碰写入边界白名单）。

---

## 与 L0/L1 的适配关系（重点）

当前树实测：**L0/L1 的代码改动为零**。L1 只合入了轮 0 文档盘点（R3245 经 R3247 进 master）；L0 只完成轮 0，唯一代码改动 R3246 悬于 `codex/wip-R3246`／`R3255`／`R3259` 三条未合并分支。

三处会砸到 L2 的计划接口，已在任务书与需求单标注依赖：

| L0/L1 计划 | 会砸到 | 处置 |
| --- | --- | --- |
| L0 轮 4A 收紧 `artifact_schema.stamp()` | `recon_service.py:141` 直调 | 轮 2 做幂等时不动 `stamp()` 调用；需求单 L2-X1–X3 交 L0 |
| L0 轮 4B 点名改 `animatic_service` 写方 | `animatic_service.py:173` | 不在本任务书范围 |
| L1 轮 1 改 `request_ledger.transaction()` 语义（超时记 `unknown` 不抛） | L2 有 4 处 `RequestLedger` 消费方 | 轮 9 改 `tts_api` 时核对新语义 |

**策略**（L2-D6）：默认只做不受 L0/L1 影响的部分；确需按计划接口写的，必须附接口定义原文并在落地时逐字核对。

---

## 并发协调

`domain/` 已被至少 3 条车道碰过，任务书 §7.3 已登记独占清单：

- `codex/wip-R3225`：`domain/task_center_service.py`、`domain/video_task_state.py`（未提交 240 项）
- `codex/wip-R3210`／`R3230`：`ui/asset_thumbs.py`、`local_video.py`
- `dsh-876e046e-e055`／`codex/wip-R3164`：6 个共同 Python 文件

本任务书涉及的 7 个事务模块与 3 个缓存模块**当前不在**上述清单内，但每轮开工须重新核验。

**轮 3 会改 `video_task_state.py`，与 `codex/wip-R3225` 的未提交改动直接重叠**——该轮开工前必须先核验车道状态。

---

## 状态

- 用户已授权按任务书执行全部轮次（2026-11-18 目标会话），本轮视为已确认，按 §2.6 提交。
- 轮次号 3272 已领取（`round_claim.py next`，归属本工作树 `dsh-864fd932-4054`）。
- `程序/project_status.md` 的口径改动（零第三方依赖→白名单依赖、12→13 阶段）**不在本分支提交**：pre-commit 钩子规定该文件仅 master 可提交；改动已撤回，合入 master 时随合并轮落到主干。
- 状态页轮次头未同步（分支侧不写 `project_status.md`），由合并轮在 master 统一处理。

## 未运行

- 架构门禁（`smoke_test.py --architecture`）：只读诊断轮默认不跑，本轮无 `.py` 改动
- 全量回归（`run_selftests.py --all --safe`）：同上
- `--affected`：无模块改动

## 下一步

1. 合入 master@R3268 同步主干（L1 轮 1 已合入；任务书行号与基数基于 R3258，执行轮须按新树重测）
2. 轮 1（结构治理轮）开工前，先核验 `codex/wip-R3225` 等活跃车道状态（任务书 §7.3）
