# R3687 结果文件 — G-0/G-1 门控复核（master 多轮合入后续验）
<!-- round-evidence: {"commit_base": "0f884e5b", "credential_hits": 0, "evidence_sha256": "8d990b933e6b96ac", "exit": 0, "failed": 0, "passed": 0, "round": 3687, "tests": "docs-only"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.10 验证／基线轮（门控续验第四轮：master 自 R3537 后合入 skill-official-final R3589、本车道 R3537 复核 R3593、member-security-hardening R3615/R3619/R3633 及 eng-docs R3544 等多轮，G-1 命中分支由 11 增至 15，按既有口径复核 G-0/G-1 并刷新任务书状态行与 E24 明细；全程未改任何 `.py`，仅修订任务书与本结果文件）。
2. **测试跑了吗、三个基线过了吗？** 测量命令全部实跑（`taskbook_closure.validate()` 输出 `[]`、`git -c core.quotepath=false diff --name-only master...codex/foundation-*`、`git rev-list --count master..`、`git merge-base --is-ancestor` 全量核对 26 支 foundation-* 分支无一合入）；默认冒烟 `smoke_test.py` 9/9 绿（本工作树实跑）；架构门禁未整轮重跑（本轮零代码改动，同 R3384/R3465/R3537 口径）；全量回归未触发（无源码变更），欠账以 `.git/auto-full-safe-result.json` 为准——最近一笔 `0f884e5b` 全量 **0 红**（1879 秒，07:28 完成）。
3. **欠账少了吗？** 无新增欠账；master 全量凭据由上一轮 1 文件红（`test_publication_fsync_budget`，f82f40f3 轮）翻为 **0 红**；修正任务书 2 处（状态行门态、E24 明细改 15 分支矩阵），使任务书与 master `0f884e5b` 实测一致。

## 复核基线

- 工作树：`devin-l0-constitution`（分支 `codex/l0-constitution`，已 `git merge master` 同步至 `0f884e5b`；合并时本工作树存在 159 个被 ignore 的 `程序/skills/00全流程SKILL/AIGC创作全流程/` 本地文件与 R3589 入库的同名跟踪文件冲突，经比对与入库版不同、属本地未跟踪旧副本，已整体移至 `D:/_backup_aigc_skill_l0_20261119/` 备份后完成合并，不丢内容）。
- 复核时点 master：`0f884e5b`（R3633 合并轮）。

## 门复核（续验）

### G-0 —— 已满足 ✓（持续）

| 核对项 | 命令 | 结果 |
| --- | --- | --- |
| L0 v2 合入 master | `git merge-base --is-ancestor`（R3384 已验） | master 又多轮前进仍成立 |
| L0 v2 完成文件存在 | `ls 程序/tasks_round/任务完成/` | `L0契约层防崩溃与协议补齐·任务完成.md` 在 |
| 闭环校验 | `python -B -c "... import taskbook_closure; print(validate())"` | 输出 `[]`（0 problems，本轮于 master `0f884e5b` 实跑） |

### G-1 —— 未满足 ✗（阻塞 K1 及全部下游轮次）

`git -c core.quotepath=false diff --name-only master...codex/foundation-*` 仍命中 4 个点名文件的分支，**由 R3537 的 11 个增至 15 个**：

| 分支 | 命中文件 | 领先 master | 分支最新提交 |
| --- | --- | --- | --- |
| `codex/foundation-api-disk` | `platform_tools`、`service_contract`、`test_dependency_whitelist` | 17 | R3366 |
| `codex/foundation-asset-disk` | 同上 3 个 | 17 | R3377 |
| `codex/foundation-context-policy` | `workflow_context_budget` | 1 | R3365 |
| `codex/foundation-context-preflight` | `workflow_context_budget` | 2 | R3395-FAIL |
| `codex/foundation-ffmpeg-runtime` | `platform_tools` | 1 | R3345 |
| `codex/foundation-hardening` | 4 个文件全中 | 19 | R3388-FAIL |
| `codex/foundation-image-disk` | `platform_tools`、`service_contract`、`test_dependency_whitelist` | 18 | R3392 |
| `codex/foundation-pre-sync-squash` | 4 个文件全中 | 16 | WIP 同步提交 `1a017534`（**新命中**） |
| `codex/foundation-rebase-preview` | `platform_tools`、`service_contract`、`test_dependency_whitelist` | 15 | R3349 |
| `codex/foundation-resume` | 4 个文件全中 | 8 | R3599（活跃，rebase 后 ahead 13→8） |
| `codex/foundation-resume-history` | 4 个文件全中 | 20 | R3430 |
| `codex/foundation-round2-history` | 4 个文件全中 | 12 | R3504 |
| `codex/foundation-round3-history` | 4 个文件全中 | 13 | R3530（**新命中**） |
| `codex/foundation-round4-history` | 4 个文件全中 | 14 | R3545（**新命中**） |
| `codex/foundation-round5-history` | 4 个文件全中 | 14 | R3567（**新命中**） |

- R3537 的 11 个命中分支全部仍在命中集内，无一合入或放弃；新增 4 支：`pre-sync-squash`（地基功能树整合支线，WIP）、`round3-history`/`round4-history`/`round5-history`（三期补记历史支线，均 4 文件全中）。
- `git merge-base --is-ancestor <branch> master` 对全部 26 支 `codex/foundation-*` 核对：**无一已合入**（其中 11 支不命中点名文件、不计入 G-1）。
- `resume` 经 rebase 后 ahead 13→8，仍活跃：最新 `6dc8b636 R3599`（C3 DPI 感知接入，05:23），前序 `31f09a3b R3594-FAIL`（C7 准入契约第二静态引用修复中）、`3e4dd3d5 R3594`（整合树安全全量共享锁占用补记）。
- 按阻塞纪律：不代做他人车道合并、不代填验收勾选。K1（白名单测试）、K10（`service_contract`）、K11（`platform_tools`）继续标注「阻塞于 G-1」；K1 起全部下游轮次（K3–K7、K10–K11E、K12–K20、K21–K23）因前置链断于 G-1 同步阻塞。

## 漂移复核（自 R3537）

| 项 | R3537 值 | R3687 复测（`0f884e5b`） | 处置 |
| --- | --- | --- | --- |
| G-1 命中分支 | 11 | 15（见上表，4 支新命中） | 任务书 E24/状态行已改 |
| `codex/foundation-*` 分支总数 | 未统计 | 26（15 命中＋11 不命中） | 任务书 E24 注记 |
| master 全量凭据 | e65e8b6f 轮 5 文件红 | `0f884e5b` 轮 **0 红**（1879 秒，07:28；上一笔 f82f40f3 轮 1 红 test_publication_fsync_budget 已由会员车道 R3631/R3633 修复并翻绿） | 无欠账 |
| 共享解释器 purelib | pydantic 全家桶未在白名单（C4 准入在途） | 仍在（pydantic/pydantic_core/annotated_types/typing_extensions 实测 find_spec 全中）；合并出口 CI 须续用 python3147 干净环境口径（R3593 先例） | 非本车道权责，仅记录 |
| 并发车道 | — | l2-maturity-taskbook、requirements-architecture-review、architecture-a12-thumbnail-bounds 等新车道活跃（10:02 前后领号 R3684–R3686） | 仅记录 |

## 本轮改动清单

- `程序/tasks_round/L0契约宪法化演进级任务书.md`：状态行（追加 R3687 复核结论）、E24 明细改 15 分支矩阵＋复核注记（未改任何决策与勾选行文字）。
- `程序/tasks_round/tasks_round_3687_result.md`：本文件。

## 后续轮次状态

- **可执行**：无——K1 前置 K0✓/G-0✓/**G-1✗**，K3–K23 全部经前置链断于 G-1；本车道继续门态监控。
- **阻塞于 G-1**：K1、K3–K7、K10–K11E、K12–K20、K21–K23。
- 下一动作：监控 `codex/foundation-*` 合入 master 或明确放弃；G-1 翻转后按 §6 排程从 K1 开始。

## 三基线

- 默认冒烟：9/9 绿（本工作树实跑）。
- 架构门禁：未整轮重跑（零 `.py` 改动；R3384/R3465/R3537 同口径）。
- 全量回归：未触发（无源码变更）；凭据以 `.git/auto-full-safe-result.json` 为准——`0f884e5b` 轮 0 红。

## 提交

- 分支 `codex/l0-constitution`；docs-only 轮，`dev.py commit` 自动生成 `evidence/R3687.json`；提交号与 hash 见提交记录。
