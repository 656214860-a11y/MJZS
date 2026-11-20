# R3907 结果：治理分支同步主干检查点并收口根目录 `.agents` 污染

## 1. 三问

- 轮次类型：合并同步轮（功能分支对齐主干检查点 `5d010101`），叠加本轮治理收口。
- 测试跑了吗：合并后定向回归 `lane_flow_gates round_baselines structure doc_registry design_coverage coverage_floor selftests` 全绿（ALL TESTS PASSED，0 跳过）；安全全量与退出档随后在同一候选树复跑并以回执为准。
- 欠账少了吗：是——清掉主干检查点误入库的根目录 `.agents/**` 78 个产物（`test_root_layout` 的未登记根入口红项消除，Git 历史 `5d010101` 可追溯）；把主干新增的车道闭环测试指向迁移后的 `docs/` 路径，避免两套文档位置；`structure.json` 补登 `test_lane_flow_gates` 测试归属并重写基线；文档登记补 ADR 0015（86 份）。

## 2. 冲突与处置（3 处冲突 + 1 类污染）

| 文件 | 处置 |
|---|---|
| `程序/runbook.md` | 保留主干新增的「现行开发闭环」整段（车道闭环、`full-safe-runner.lock`、`merge-lane.lock`、出口 CI、只快进），并保留本分支「功能分支不得改状态页、按主干共同基点校验」条款 |
| `程序/docs/records/工程文档登记表.md` | 取本分支治理登记表，补登主干新增 `docs/adr/0015-lane-flow-does-not-block-sessions.md`（权威，R3902） |
| `程序/维护记录/文档登记快照.json` | 由 `doc_registry.py` 重新生成（86 份一致） |
| `.agents/**`（主干检查点 `5d010101` 带入的 78 个文件） | 从合并结果中删除：属于开发过程产物、不是产品/文档内容；原内容仍在 `5d010101` Git 历史中可追溯。删除后根目录不再有未登记的 `.agents` 入口 |
| `程序/tests/architecture/test_lane_flow_gates.py` | 路径随治理迁移修正：`说明/发布检查单.md`→`docs/process/发布检查单.md`、`说明/已知坑与不可破坏契约.md`→`docs/contracts/已知坑与不可破坏契约.md`、`说明/工程文档登记表.md`→`docs/records/工程文档登记表.md`、ADR 索引改查 `docs/adr/README.md`；断言语义不变 |
| `程序/governance/structure.json` / `structure-baseline.json` | 新增 `test_lane_flow_gates.py` 的 `test_ownership` 归属（targets 指向合并/队列/领号/自检调度实现）；显式 `--write-baseline` 重写，仍只保留 1 条已接受存量 |

## 3. 回执

- `governance/check_structure.py --check --summary` → 退出 0，`ok:true`，`finding_count:1`。
- `doc_registry.py --check` → 退出 0，86 份文档。
- 定向回归 → `ALL TESTS PASSED`，0 跳过（退出 0）。
- 安全全量与退出档在同一候选树复跑，回执见任务完成文件 §3 与 `tasks_round/evidence/R3907.json`。

## 4. 后续

- 合并轮 `dev.py merge codex/governance-land` 在 master 主工作区执行；状态页抬头只在合并轮推进，不提前填写合并 hash。
