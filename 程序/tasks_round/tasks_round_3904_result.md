# R3904 结果：G-1 命中分支对 IF 定版的匹配度分层（§3.5 只读诊断）
<!-- round-evidence: {"commit_base": "e555307e", "credential_hits": 0, "evidence_sha256": "3c50527216bc34b0", "exit": 0, "failed": 0, "passed": 0, "round": 3904, "tests": "docs-only"} -->

## 三问

- 轮型：§3.5 只读诊断轮。新 IF（`d8acf12e`）快照折叠重建后，其 4 个 G-1 文件 tip blob 与旧 IF/c8-updater 逐字节全同——因此「IF 合入后 master 的 4 文件定版」已可预知，本轮把 24 支命中分支按「tip blob 与 IF 定版的匹配度」分层，供地基车道处置矩阵直接取用。
- 测试：不跑（只读诊断；全部结论 `git rev-parse <ref>:<path>` blob 比对实测）。
- 欠账：无代码改动；把「24 支命中」进一步收敛为「真正需要内容裁决的少数文件/分支」。

## 领号说明

- R3904 于 11:03 领号（`codex/l0-constitution`），原为 G-1 状态快照所留；R3898（中断续作）已覆盖该快照后，本轮改作匹配度分层诊断，领号沿用。

## 分层表（master `b19e62e0`，IF 定版 blob = `4490b155ce`/`90f1508e67`/`a14ccbc812`/`437799948c`）

| 层 | 分支 | 命中文件数 | 与 IF 定版匹配 | 解读 |
| --- | --- | --- | --- | --- |
| **A·零契约差** | `integration-final`、`c8-updater` | 4/4 全中 | **4/4** | tip 四文件与 IF 定版全同；合入属纯手续（IF 合入后 master 定版即其内容） |
| **B·仅 platform_tools 版本差** | `next`、`c6-catalog/extension/owner/pages/skill-pages`、`resume`、`update-admission` | 4/4 全中 | 3/4 | 仅 `platform_tools.py` 持 next 版 `afb3ca9a07`（IF 版 `4490b155ce`＝next＋38/−27）；其余 3 文件与定版全同 |
| **C·两文件版本差** | `pre-sync-squash`、`round2–5-history`（4 支） | 4/4 全中 | 2/4 | `platform_tools.py`＋`test_dependency_whitelist.py` 与定版不同 |
| **D·单文件实质分歧** | `api-disk`、`asset-disk`、`image-disk`、`rebase-preview`（各 3 中文件） | 3 | 1/3 | 仅 `platform_tools.py` 与定版不同（持旧版 `daada659be`） |
| | `hardening`、`resume-history` | 4 | 1/4 | `platform_tools.py` 旧版＋`budget`/`whitelist` 各持变体 |
| **E·独有变体** | `context-policy`（budget 单中）、`context-preflight`（budget 单中）、`ffmpeg-runtime`（platform_tools 单中） | 1 | 0 | context 三支的 budget/whitelist 变体（`266c771465`/`896da38221`/`929ac4780c`/`9e9d29a3e9`）与定版均不同；`ffmpeg-runtime` 持最旧 platform_tools |

## 解读

- **G-1 终局实质是 `platform_tools.py` 的版本选拔**：24 支中 21 支的分歧收敛到这一个文件（5 个存活版本：master 旧版已被 IF 取代、next 版、IF 版、context 变体、daada 旧功能支共版）。`service_contract.py`/`budget`/`whitelist` 在 IF 定版下已被绝大多数分支共享或仅剩零星变体。
- **「形式命中」与「真实分歧」可机械区分**：A/B/C 层 12 支与定版差异 ≤2 文件且均为已知版本漂移，合入/放弃均不产生契约内容损失；D/E 层 12 支需逐支看 platform_tools 变更意图（尤其 context 三支与 ffmpeg-runtime 的独有变体）。
- 处置顺序建议（供地基车道参考，本车道不代做）：先合 IF 或 c8-updater 定版 → A/B/C 层按手续清理 → D/E 层逐支裁决 platform_tools 取舍。
- 注意：三点 diff 命中不因 tip 内容等于 master 而消除——上表「匹配」仅表示合入后无契约净差，**每支仍须实际合入或明确放弃**才脱离命中集。

## 验证

- 全部 blob 哈希 `git rev-parse <ref>:<path>` 实测；命中集与 R3898 一致（38/24）。未运行测试（只读诊断）。

## 提交

- 分支 `codex/l0-constitution`；docs-only，`dev.py commit` 生成 `evidence/R3904.json` 并回填机器头。
