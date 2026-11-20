# R3930 结果：重测地基门禁
<!-- round-evidence: {"commit_base": "9f41ec1d", "credential_hits": 0, "evidence_sha256": "2a5dba134cc8dc5f", "exit": 0, "failed": 0, "passed": 0, "round": 3930, "tests": "docs-only"} -->

## 1. 三问

- 轮次类型：状态接续轮（`runbook.md` §15 的 3.11）。只重测 `git diff --name-only master...codex/foundation-*` 对 G-1、G-B 点名文件的命中，并改状态页。没有改 C6、C8、整合、disk 分支的名字或内容。
- 测试跑了吗、三个基线过了吗：本轮未跑冒烟、架构门禁和全量。R3927、R3928、R3929 各自的出口 CI 已通过。最新绿全量仍是 R3849。
- 欠账少了吗：G-1 从本轮开工时的 18 支降到 16 支。G-B 仍命中 17 支。门没有归零，K1–K23 没有开工。

## 2. 本轮合入的三支

测量点是合入后的 master `9f41ec1d`（R3929）。

| 分支 | 合入 | 销掉的门 |
| --- | --- | --- |
| `codex/foundation-ffmpeg-runtime` | R3927 `0c4bbe62` | G-1 |
| `codex/foundation-context-policy` | R3928 `80e2f272` | G-1 |
| `codex/foundation-config-write-safety` | R3929 `9f41ec1d` | G-B 的 `project_settings.py` |

合入时补过两处主干已有门禁，没有改这三支自己的行为结论：随包 FFmpeg 查找压回 1000 行；未知窗口的写作夹具补了显式 `context_length`，上下文预算决策点按全目标实测记为 12/22；损坏配置改为抛 `ConfigError`，仍是 `ValueError`，文件未被覆盖。

## 3. 仍命中

G-1 点名：`platform_tools.py`、`service_contract.py`、`workflow_context_budget.py`、`test_dependency_whitelist.py`。G-B 点名：`model_router.py`、`storage_maintenance.py`、`token_saver.py`、`project_settings.py`。领先数是 `master...<branch>` 右侧。

| 分支 | 领先 | 检出 | G-1 文件数 | G-B 文件数 |
| --- | --- | --- | --- | --- |
| `codex/foundation-api-disk` | 17 | 否 | 3 | 3 |
| `codex/foundation-asset-disk` | 17 | 否 | 3 | 3 |
| `codex/foundation-c6-catalog` | 9 | 是 | 4 | 4 |
| `codex/foundation-c6-extension` | 17 | 是 | 4 | 4 |
| `codex/foundation-c6-owner` | 15 | 是 | 4 | 4 |
| `codex/foundation-c6-pages` | 9 | 是 | 4 | 4 |
| `codex/foundation-c6-skill-pages` | 11 | 是 | 4 | 4 |
| `codex/foundation-c8-updater` | 18 | 是 | 4 | 4 |
| `codex/foundation-config-project-profile` | 4 | 否 | 0 | 1 |
| `codex/foundation-context-preflight` | 2 | 否 | 1 | 1 |
| `codex/foundation-hardening` | 19 | 否 | 4 | 3 |
| `codex/foundation-image-disk` | 18 | 否 | 3 | 3 |
| `codex/foundation-integration-final` | 5 | 是 | 4 | 4 |
| `codex/foundation-next` | 16 | 是 | 4 | 4 |
| `codex/foundation-rebase-preview` | 15 | 否 | 3 | 3 |
| `codex/foundation-resume` | 11 | 是 | 4 | 4 |
| `codex/foundation-update-admission` | 14 | 是 | 4 | 4 |

G-1 共 16 支。G-B 是这 16 支里除「只少 `project_settings.py`」的几支之外，再加只碰 `project_settings.py` 的 `config-project-profile`，共 17 支。`context-preflight` 仍命中 `workflow_context_budget.py`；疏通任务书的 U3 只点名 `context-policy`，没有授权合入它。

检出事实来自 `git worktree list`。disk、hardening、rebase-preview 这次测量时没有工作树，但任务书 D4 和 U5 仍禁止改名或合入。C6、next、c8、resume、update-admission、integration-final 都还检出，分支名与测量前相同。

## 4. 没有做的事

没有合入 `integration-final`，没有动它的未提交覆盖率基线和 `程序/tmp*`。没有开始 K1–K23。没有推送。门归零需要另一次授权：整支合入，或对点名的活跃分支做与历史快照相同的改名放弃。
