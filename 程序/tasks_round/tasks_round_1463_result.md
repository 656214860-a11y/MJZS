# R1463 结构治理轮：开发者统一入口（优化清单第 12、14 项的可安全落地部分）

1. **本轮类型？** 结构治理轮（只加调度，不改任何底层脚本）。
2. **测试与基线？** 新增 `tests/test_dev_entry.py`（3 项）通过；默认冒烟与架构门禁见提交前运行。断言未动。
3. **是否欠账？** 无；未触及启动入口、删除语义、层级表。

## 改动

- `scripts/dev.py`：`smoke／arch／full／debt／ci／dist／health／logs／claim` 九个子命令，每个只转调既有脚本（`smoke_test.py`、`run_selftests.py`、`auto_full_safe.py --status`、`local_ci.py`、`distribution_selfcheck.py`、`repo_health.py`、`maintain_logs.py`、`round_claim.py next`），参数原样透传；调度表由测试校验目标脚本存在。
- `CLAUDE.md` 常用命令加一行入口说明（测试校验该行存在）。

## 核查后有意不动

- 根目录的 `本地CI.cmd`／`ci_*.cmd`／`启动助手*.cmd`：用户双击入口与 post-commit 钩子、`.wt/ci` 流程都按这些文件名调用，改名或搬家会让并行车道里其他 Agent 的流程失效，保留。`dev.py` 是它们之上的统一文档化入口，不替换。
- 根目录整理（`AGENT_HANDOFF.md`、`GLOSSARY.md`、`reorganize_install.py`、图标等迁入子目录）：这些路径被 AGENTS／CLAUDE、钩子、测试与分发清单引用，且有其他 Agent 并行读写，迁移属于协议级改动，需用户确认后单独成轮。分发清单已按文件名把它们归入“排除”，不影响分发。

## 提交

已提交，见 git log 标题 `R1463:`。
