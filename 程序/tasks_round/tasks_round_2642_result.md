# R2642 结果：进度报告区分「不适用/未开始」、报告自然稿采用状态与下一步动作（REQ-S01-84）
<!-- round-evidence: {"commit_base": "0d9d86c6", "credential_hits": 0, "evidence_sha256": "b139d5a75960e64e", "exit": 0, "failed": 0, "passed": 13, "round": 2642, "tests": "run_selftests.py -k test_preparation_monitor"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   功能轮（§3.1，文档先行）。任务源：用户指令「未改的冲突也必须修改」＋「优化项 1-5
   必须执行」中的可落地子集——冲突 4（空项目进度报告无法区分「门禁不适用」与
   「未开始」）、冲突 1（自然稿采用状态与准备进度分列两份台账，判读割裂）、
   冲突 2 的恢复路径提示（SHA256 失效错误不指路）、优化 5（`next_actions`）。
   冲突 1 的「双权威」实质维持既有架构（selection 仍是采用唯一权威、progress 仍只
   判前三阶段），本轮以报告级字段消除判读割裂而非改权威。分支 `codex/wip-R2642`
   （R2639–R2641 为中央计数器空号）。

2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 **9/9** 通过；`smoke_test.py --affected stage_completion_service
     writing_api` 自检门禁 **0 个文件有红**（含 `test_writing_quality`，本轮无红）。
   - 先红后绿：新增 5 条断言新字段的用例改动前 KeyError（`applicable`/`script`/
     `next_actions`），已实现并转绿。
   - 定向：`test_preparation_monitor` 13/13、`test_writing_api` 五片＋边界 71/71、
     `test_stage_completion_service` 三片全绿。
   - 全量 `--all --safe`：未跑（功能分支不累计欠账）。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账；`preparation_progress` 从「四键判据」扩为「判据＋采用状态＋下一步」，
   三虎监控与完成核验共用同一报告，未另立入口。

## 实现

- `stage_completion_service.preparation_progress` 返回新增三键：
  - `applicable`：无已确认简报为 False——`confirmed==3` 哨兵语义明确为
    「门禁不适用」，与 applicable=True+confirmed=0 的「未开始」区分（冲突 4）；
  - `script`：`_script_adoption_state` 报告级采用状态——失效记录（reason 且
    path 空）→「需重新采用」、记录路径存在→「已采用」、否则「待采用」；
    sha 完整核验仍归 `resolve_script_source`，不重复判据（冲突 1 的判读面）；
  - `next_actions`：卡住点名阶段（缺文件→「生成并设为定稿」；未确认→
    「确认（右键设为定稿或聊天回复确认）」），三阶段齐全后按采用状态给
    「生成自然剧本并明确采用」／「重新生成或明确采用自然剧本」／空（优化 5）。
- `writing_api._preparation_state` 「原确认失效」提示补恢复路径：
  「或确认文件无误后右键『设为定稿』重新登记」（冲突 2——SHA256 精确绑定
  的契约不变，补用户可执行的恢复指引）。

## 文档先行（§2.7）

`docs/stages/S01_剧本准备.md`：新增 REQ-S01-84、DES-S01-84、锚点行
（`test_preparation_monitor`）。

## 改动清单

- `程序/stage_completion_service.py`：`preparation_progress` 新增
  `applicable`/`script`/`next_actions`；新增 `_script_adoption_state`。
- `程序/writing_api.py`：失效提示补恢复路径一句。
- `程序/tests/test_preparation_monitor.py`：新增 5 条用例（适用性区分、
  采用三态、next_actions 缺文件/未确认/待采用/已采用/需重新采用）。
- `程序/docs/stages/S01_剧本准备.md`：REQ/DES/锚点。

## 提交

`dev.py commit` 一批一轮，凭据见 `tasks_round/evidence/R2642.json`。
