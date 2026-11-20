# R3893 结果：G-1 四文件版本谱系普查（只读诊断·续 R3890/R3892）
<!-- round-evidence: {"commit_base": "3ef9a85e", "credential_hits": 0, "evidence_sha256": "616ae362a28ea41f", "exit": 0, "failed": 0, "passed": 0, "round": 3893, "tests": "docs-only"} -->

## 三问

- 轮型：§3.5 只读诊断轮。只新增结果文件；全部结论由 `git rev-parse <ref>:<path>` blob 哈希实测。
- 测试：不跑（只读诊断；纯 blob 引用查询，无工作树改动）。
- 欠账：无代码改动；把「24 支命中」从分支视角转成「每文件几个版本」的裁决视角。

## 新证据（master = `bcbf337e`，测量时点 2026-11-20 09:0x）

对 master＋24 支命中分支共 25 个 ref，逐文件取 tip blob 哈希分组：

### `contract/platform_tools.py` —— 5 个版本

| blob | 持有者 | 解读 |
| --- | --- | --- |
| `daada659be` | 13 支旧功能支（api/asset-disk、ffmpeg-runtime、hardening、image-disk、pre-sync-squash、rebase-preview、resume、resume-history、round2–5-history） | 地基早期共用版 |
| `afb3ca9a07` | next＋C6 五支＋update-admission（7 支） | next 版（相对 master 30+/41−） |
| `4490b155ce` | integration-final＋c8-updater（2 支） | IF 版（next 之上 +38/−27） |
| `9e9d29a3e9` | context-policy＋context-preflight（2 支） | 自有变体 |
| `298b7c12b1` | master（1 支） | 现状版——**无任何地基分支持有** |

### `contract/service_contract.py` —— 仅 2 个版本（高度收敛）

| blob | 持有者 |
| --- | --- |
| `90f1508e67` | **21 支**：next/IF/C6 全家/c8-updater/update-admission＋全部旧功能支（除 context 三支与 ffmpeg-runtime） |
| `cf2ffb172e` | master＋context-policy/context-preflight/ffmpeg-runtime（4 支） |

### `contract/workflow_context_budget.py` —— 4 个版本

| blob | 持有者 |
| --- | --- |
| `a14ccbc812` | 15 支：next/IF/C6 全家/c8-updater＋pre-sync-squash/resume/round2–5-history/update-admission（大扩展版 +136/−34） |
| `a06be76968` | 6 支：master＋api/asset-disk/ffmpeg-runtime/image-disk/rebase-preview（旧版） |
| `266c771465` | 3 支：context-policy、hardening、resume-history（变体） |
| `896da38221` | context-preflight（唯一） |

### `tests/architecture/test_dependency_whitelist.py` —— 4 个版本

| blob | 持有者 |
| --- | --- |
| `e9f287c7a7` | 11 支旧功能支（api/asset-disk、hardening、image-disk、pre-sync-squash、rebase-preview、resume-history、round2–5-history） |
| `437799948c` | 10 支：next/IF/C6 全家/c8-updater＋resume/update-admission（next 版） |
| `929ac4780c` | context 三支（变体） |
| `aef4cdbc71` | master（唯一） |

## 解读

- **「24 支命中」实为每文件 2–5 个版本的选择问题**，不是 24 路内容分歧：service_contract 已事实收敛（21/25 ref 同 blob）；budget 与 whitelist 各 4 版；platform_tools 5 版。
- IF 合入后 master 四文件将定版为 IF 版（`4490b155ce`/`90f1508e67`/`a14ccbc812`/`437799948c`）。届时逐支核对「tip blob 是否等于 IF 版」即可区分**形式命中**（内容已一致、仅差合入/放弃手续）与**真实分歧**（持有不同版本需裁决）。
- 版本混合支已现：`resume`（platform_tools 旧版＋其余 3 文件新/next 版）、`pre-sync-squash` 与 `round2–5-history`（platform_tools/whitelist 旧版＋service_contract/budget 新版）、`hardening`/`resume-history`（budget 持变体 `266c771465`）、`ffmpeg-runtime`（4 文件全旧/变体，分歧最大）。
- context 三支为白名单/budget 的独有变体来源（`9e9d29a3e9`/`929ac4780c`/`266c771465`/`896da38221`），裁决时须单独看其变更意图。

## 结论

- 维持 G-1 未满足：命中 24 支不变；K1–K23 继续 `[TASK_BLOCKED]`。
- 裁决工作量比「24 支」表象小：每文件版本数有限，IF 合入后按 blob 比对即可把命中支分成「内容已一致待手续」与「真实分歧待裁决」两类。
- 本车道不代做裁决；以上谱系供地基车道处置矩阵刷新参考。

## 验证

- 全部结论由 `git rev-parse <ref>:<path>` 实测 blob 前缀；未运行测试（只读诊断）。

## 提交

- 分支 `codex/l0-constitution`；docs-only 诊断轮，`dev.py commit` 自动生成 `evidence/R3893.json` 并回填本文件机器头；提交号与 hash 见提交记录。
