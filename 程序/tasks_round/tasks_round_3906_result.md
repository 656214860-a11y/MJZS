# R3906 结果：治理基线收口——结构基线、文档登记与分支覆盖重测

## 1. 三问

- 轮次类型：结构治理轮（元数据与基线刷新，无产品源码改动）。
- 测试跑了吗：本提交只改治理元数据与基线；证据记 `docs-only`，结构/文档/覆盖门禁已在当轮定向跑过（`check_structure --check` 退出 0、`doc_registry --check` 85 份通过、分支覆盖率真实重测 102 目标全通过）。安全全量与退出档在随后同一候选树执行并留回执。
- 欠账少了吗：是——结构基线从 6 条旧身份降到 1 条（docs/review 迁移后 5 条版本后缀违规自然消失）；冻结测试名单去掉已删除的重复退役测试（582→581）；文档登记补登主干新 ADR 0014；分支覆盖率基线由真实重测刷新（103 实体、1744/3062 决策点）。

## 2. 改动

| 文件 | 说明 |
|---|---|
| `程序/governance/structure.json` | `frozen_contract_tests.paths` 移除已删除的 `程序/tests/test_builtin_controller_retirement.py`（该文件在 R3903 去重时删除），其余 581 条精确路径不变 |
| `程序/governance/structure-baseline.json` | 显式 `--write-baseline` 重写：仅保留 `程序/batch_frames_tool/启动批量首帧.pyw` 存量命名，policy/inventory 摘要同步；删除 docs/review 下 5 条已随迁移消失的身份 |
| `程序/docs/records/工程文档登记表.md` | 登记主干新增的 `docs/adr/0014-remove-builtin-skill-orchestrator.md`（权威，R3899） |
| `程序/维护记录/文档登记快照.json` | `doc_registry.py` 重新生成，85 份文档一致 |
| `程序/维护记录/分支覆盖率基线.json` | `scripts/branch_coverage_report.py` 对 102 个目标真实重测：`tests_ok=true`、103 实体、1744/3062 决策点；不降 floor |

## 3. 命令与回执

- `python -B governance/check_structure.py --check --summary` → 退出 0，`ok:true`，delta 空，`finding_count:1`（已接受存量）。
- `python -B 维护记录/基准脚本/doc_registry.py --check` → 退出 0，「登记表核对通过：85 份文档」。
- 分支覆盖：`scripts/branch_coverage_report.py`（经 `scripts/gui_hidden.py`）→ 退出 0，`LAND_COVERAGE_METRICS 103 1744 3062`。
- 安全全量与默认冒烟/架构门禁在 R3903/R3906 同树执行，回执见 R3903 结果与最终任务完成文件。

## 4. 后续

- 任务完成文件与全量回执在最终候选轮提交后，走合并轮 `dev.py merge` 合入 master；状态页抬头只在合并轮推进。
