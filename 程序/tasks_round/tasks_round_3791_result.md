# R3791 结果：L1 任务书门控复核（G-A1–G-A5、G-B、G-C 对 master@2c0dce41）
<!-- round-evidence: {"commit_base": "d717c4ba", "credential_hits": 0, "evidence_sha256": "c51315320c8d8791", "exit": 0, "failed": 0, "passed": 0, "round": 3791, "tests": "docs-only"} -->

## 三问

- 轮型：§3.10 验证／基线轮（门控复核，只读核对＋结果文件，docs-only）。
- 测试：不跑（无 `.py` 改动；核对命令为 `git`／文件存在性检查，输出见下）。
- 欠账：无代码改动；门状态按 master `2c0dce41`（R3784）实测刷新。

## 背景

I0-6（R3386）后已过约 500 个轮次、master 推进至 R3784；上轮 I22（R3752）合入后本车道剩余轮次全部处于门控阻塞。本轮按任务书 §2.3「核对方式」列逐门重测，结论供下一轮开工判定。

## 门核对（master = 2c0dce41）

| 门 | 内容 | 实测 | 结论 | 阻塞轮次 |
| --- | --- | --- | --- | --- |
| G-A1 | L0 K6 弃用机制合入；`tests/architecture/test_deprecation_ledger.py` 存在 | 文件**缺失**；`维护记录/弃用台账.json` 缺失；`git log master` 无 K6 提交 | **未满足** | I2、I4、I5（门面保留轮） |
| G-A2 | K3–K5 `__all__`/契约清单/破坏性变更检测合入 | `test_contract_manifest.py`、`test_contract_api_diff.py` **均缺失** | **未满足** | I20 |
| G-A3 | K15 文档生成器＋K17 import-linter 合入 | `scripts/contract_docs.py`、`scripts/gen_importlinter.py` **均缺失** | **未满足** | I24 |
| G-A4 | K12 `contract/ports.py`＋`foundation/` 合入 | `contract/ports.py`、`程序/foundation/` **均缺失** | **未满足**（无硬阻塞） | — |
| G-A5 | K18 `app_dirs` 合入 | `contract/app_dirs.py`、`infra/app_dirs.py` **均缺失** | **未满足**（无硬阻塞） | — |
| G-B | 地基分支对 `model_router`/`storage_maintenance`/`token_saver`/`project_settings` 的改动已合入或放弃 | **16 支 `codex/foundation-*` 分支仍命中**（I0-6 时为 4 支）：api-disk(17)、asset-disk(17)、config-project-profile(4)、config-write-safety(1)、context-preflight(2)、hardening(19)、image-disk(18)、next(11)、pre-sync-squash(16)、rebase-preview(15)、resume(11)、resume-history(20)、round2–5-history(12–14) | **未满足** | I5b、I13、I23；I21 范围含 `model_router`（门 G-B） |
| G-C | `contract/` 新建文件登记契约清单（若 K4 已合入） | K4 未合入，本门不适用 | 不适用 | — |

核对命令（在 master 工作树 `D:/漫剧制作助手` 执行）：

```powershell
# G-A：文件存在性（全部 MISSING）
Test-Path 程序/tests/architecture/test_deprecation_ledger.py   # False
git log --oneline master | Select-String 'K6'                  # 无命中
# G-B：git diff --name-only master...codex/foundation-* 按 4 文件过滤 → 16 支命中（ahead 数见上表）
```

## L0 宪法车道供给侧状态（G-A 提供方）

master 上已合入 K 轮：KR（R3378）、K0（R3380）、K2（R3385）、K9（R3404）、K8（R3412）。未交付：K1、K3–K7、K10–K23。按其 §2.3，K1/K10/K11 另受自身 G-1 阻塞（地基分支仍命中 `platform_tools`/`service_contract`/`workflow_context_budget`/`test_dependency_whitelist`，15 支）；K3–K7 经 K1 工具链间接受 G-1 传导。本车道不代做、不越权。

## 本车道剩余轮次与解锁条件

| 轮次 | 解锁门 | 备注 |
| --- | --- | --- |
| I2、I4、I5 | G-A1（K6 弃用台账）；I5b 另需 G-B | 门面迁移需弃用机制兜底 |
| I13 | G-B | 范围含 `model_router` 冷却联动 |
| I20 | G-A2＋I4、I5 | `__all__` 门禁与清单机制 |
| I21 | 范围含 `model_router`（门 G-B） | §6.1 硬边未列 I21←G-B，但轮内范围明示 G-B；保守按阻塞处理 |
| I23 | I13＋G-B | 范围核心为 `model_router` |
| I24 | G-A3＋I1 | 需 K15/K17 生成器 |
| I25–I27 | I1–I24 全部 | 收口次序 |

## 结论与下一步

- 本车道可实施轮次已全部完成并合入 master（I0–I22 中 17 轮；I22 合入提交 `d717c4ba`，本分支 HEAD 同点）。
- 剩余 11 轮（I2、I4、I5、I13、I20–I27）全部阻塞于门；根阻塞为地基车道 16 支在途分支对共享 L1/L0 文件的未决改动，同时卡住本车道 G-B 与 L0 宪法 G-1→K1→K3–K7→本车道 G-A。
- 最小解锁动作（属他人车道，需用户调度）：地基车道将 `foundation-*` 分支合入 master 或明确放弃；L0 宪法车道推进 K1–K18 交付。本车道待命，不空转。
- 分支状态：`codex/l1-enterprise` = `d717c4ba`（已是 master 祖先）；master 领先 3 个提交（R3780/R3782/R3784 文档预算门禁分档），下轮开工前按 §2.2 同步。

## 验证

- 门核对命令输出如上表（docs-only，无测试可跑）。
- 三个基线：冒烟／架构门禁／全量均未运行（无代码改动）；沿用最近凭据不视为本轮实测。
- 提交：`dev.py commit` 文档轮口径（同 R3741）。

## 提交

- （提交后回填）
