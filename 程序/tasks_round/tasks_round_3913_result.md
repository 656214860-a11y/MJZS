# R3913 结果文件 — master 架构门禁红诊断：R3914 已根因修复，本轮收口为只读诊断（零代码变更）
<!-- round-evidence: {"commit_base": "91089411", "credential_hits": 0, "evidence_sha256": "79f22a53651cbfde", "exit": 0, "failed": 0, "passed": 0, "round": 3913, "tests": "docs-only"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.5 只读诊断轮（原计划为 §3.6 契约／架构治理轮的主干修复；诊断途中发现根因已被他车道修复，按诊断轮收口，不产生代码变更）。
2. **测试跑了吗、三个基线过了吗？** 定向实跑：`run_selftests.py -k unification_ratchet` 在登记 exempt 前 **5/5 绿**（本工作树实跑）；登记后复核 master 侧 `merge_round.py` 已无 `json.loads`（0 处），exempt 项将因 `_point_exists` 校验失败而成为**过期台账项**——故回退全部代码改动，仅保留本结果文件。
3. **欠账少了吗？** 如实记录：本轮未减少欠账（无需减少——R3914 `lane-lock-heartbeat` 合入已把 `release_merge_lane` 的锁读取改为 `_merge_lane_holder()`＋`lock_lease.release()` 租约机制，裸 `json.loads` 调用点从 master 消失，`test_unification_ratchet` 红项自然消解）；未新增任何债务与代码变更。

## 诊断过程与证据

- 起点：master `9767ab38` 架构门禁 `test_bare_json_load_debt_is_a_nonincreasing_subset` 红——未登记债务 `scripts/merge_round.py:release_merge_lane:json.loads:78de6374442893c8:1`（R3902 引入）。
- 曾准备的修复：第四项台账 exempt 登记（理由：Git 内部合并道锁 JSON 读取，非用户配置）。登记后本工作树 ratchet 5/5 绿。
- **中止依据（关键）**：复核 master `385dd7b6`（R3914 合入）后 `merge_round.py` 全文 `json.loads` 计数为 **0**——`release_merge_lane` 已改用 `_merge_lane_holder()`＋`lock_lease` 租约读写。棘轮测试对每个台账项执行 `_point_exists` 校验（`:json.loads:` 锚点必须命中当前实际债务集），若合入我的 exempt 项，在合并结果上将报「台账项不可定位」——**登记反而制造新红**。按「最简改动／不改根因所在模块」原则回退。
- 提交受阻佐证：期间 `dev.py commit` 两次被车道范围门禁拒绝（台账与 18 个活跃分支未合入改动重叠），该阻塞随方案中止一并消解。

## 三基线

- 定向：unification_ratchet 5/5（登记前本工作树实跑）。
- 默认冒烟：未跑（只读诊断轮，零代码变更）。
- 架构门禁：master `385dd7b6` 上 `test_unification_ratchet` 应已随 R3914 复绿；合并轮出口 CI 复核。

## 边界说明

- 工作树已回退至 `91089411`（master@`c4dedb53` 同步合并）＋本结果文件；`架构统一基数.json` 与 `project_status.md` 均无净改动。
- R3914 合入的 `tests/test_merge_round.py`（+156 行）覆盖租约锁新行为，属他车道验收范围。

## 后续轮次状态

- G-1 仍未满足（24 支 `codex/foundation-*` 命中四文件，抽查 integration-final/resume/c6-pages 各 4 命中复核属实），K1 起全部下游轮次继续阻塞。
- 本车道 `codex/l0-constitution` 分支并行会话诊断批 R3887–R3904 仍待合入；本结果文件与之一并走合并。

## 提交

- 分支 `codex/l0-constitution`；仅新增本结果文件（docs-only）；`dev.py commit` 自动生成 `evidence/R3913.json`；提交号与 hash 见提交记录。
