# R2638 结果：采用基线变化即撤销自然稿采用——取消确认/简报变化/换文件重确认收口
<!-- round-evidence: {"commit_base": "0acbc0bf", "credential_hits": 0, "evidence_sha256": "45fb30b5770b3af7", "exit": 0, "failed": 0, "passed": 26, "round": 2638, "tests": "run_selftests.py -k test_preparation_confirmation test_writing_unconfirm"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   修复轮（§3.2）。任务源：用户验收 R2630 后追问「是否完全修复剧本准备的逻辑冲突」，
   明确指令「需要收口缝隙」。R2630 只把撤销采用绑定在「重写确认」上；取消已确认、
   简报变化后重确认、同阶段换文件设为定稿这三条**不改写 revision 的路径**同样会改
   采用版本（顶层 `documents` 的已确认内容），却从不撤销 `natural_script_selection.json`
   的已采用自然稿——旧自然稿继续被 `resolve_script_source` 当有效采用返回。
   分支 `codex/wip-R2638`（R2631–R2637 为中央计数器被其他车道占用的空号）。

2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟基线：`smoke_test.py --affected writing_api writing_unconfirm`
     前 8 项检查全过；自检门禁并行首跑 461 条仅
     `test_writing_quality.test_list_reports_maps_hash_folders_back_to_scripts`
     1 红（哈希目录映射，R2630 已记录的同一条并发 flake，与本轮改动无关）；
     该文件单跑 17/17 两连绿；门禁 29 个测试文件 **串行复跑 461/461 全绿**。
   - 先红后绿：新增 5 条用例在旧代码（仅暂存生产文件）上 4 红 1 绿——
     `test_unconfirm_revokes_natural_script_adoption`、
     `test_confirm_different_adopted_file_revokes_natural_script_adoption`、
     `test_confirm_after_brief_change_revokes_natural_script_adoption`
     均 `resolve_script_source` 仍返回旧剧本（应撤销）；
     `test_unconfirm_then_reconfirm_different_file_keeps_adoption_revoked`
     另含测试自身 mkdir 缺失已修；`test_confirm_unchanged_adopted_file_…`
     在旧代码同样绿（验证不误伤）。
   - 修复中途发现并闭环一次真回归：`read_json` 对不存在文件抛
     `FileNotFoundError`（聊天首次写台账时 `preparation_state.json` 尚不存在，
     `test_writing_api` 16 红），守卫补 `is_file()` 后 71/71 绿。
   - 定向：`test_preparation_confirmation` 14/14、`test_writing_unconfirm` 12/12、
     `test_writing_restart`/`test_writing_edited_restart`/`test_preparation_monitor`/
     `test_writing_status_line`/`test_writing_restart_intent`/`test_script_contract*`/
     `test_req_s01_anchors` 共 103 条全绿。
   - 全量 `--all --safe`：未跑（修复分支不累计欠账）。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账；REQ-S01-14 的「撤销采用」从单点绑定（重写确认）收口为
   单一守卫（`_save_preparation_state_guarded`），覆盖全部非重写写台账路径。

## 设计与实现

- 新增 `writing_api._confirmed_basis(state)`：采用版本里已确认内容的
  `{(stage, sha256)}` 集合，即自然稿采用的依据基线。
- 新增 `writing_api._save_preparation_state_guarded(project, target, state, publish)`：
  写台账前比对盘上与新状态的确认基线；**基线变化且存在有效采用记录**
  （selection 的 `path` 非空）时先落失效 payload（
  `前置阶段已更新，请重新生成或明确采用自然剧本`）再回写台账；
  基线未变或无有效采用时直接保存——不给从未采用过的项目写多余失效记录，
  重确认同内容文件不误伤采用。
- 换用守卫的四处写点：菜单 `confirm_preparation_document` 非推进分支
  （含 rebound 回退采用版本，原 elif 分支被守卫吸收且更精确）、
  `unconfirm_preparation_document`、`_preparation_step` 简报重置/待重写弹出、
  `save_decision` 非推进分支（聊天推进不改 revision 时同样收口）。
  `restart_preparation` 两条与 `pending_restart` 询问写不改采用版本，保持原写口。
- 事务语义不变：守卫内的撤销仍走 `_revoke_natural_script_adoption`
  （先写 selection 失效、update_index 回写台账），嵌套事务失败回滚链
  （`test_adoption_failure_restores_selection_and_pending_version`）不受影响。

## 文档先行（§2.7）

- `docs/stages/S01_剧本准备.md`：REQ-S01-14 补「采用版本以任何方式变化
  同样撤销采用；重确认内容未变的文件不撤销」；DES-S01-14 记录守卫与
  `_promote_revision` 的分工；DES-S01-78 写口改为守卫。

## 改动清单

- `程序/writing_api.py`：新增 `_confirmed_basis`、`_save_preparation_state_guarded`；
  两处 `_save_preparation_state` 写点换守卫。
- `程序/writing_unconfirm.py`：confirm/unconfirm 写点换守卫；移除被吸收的
  rebound 分支与 `_revoke` 直接调用。
- `程序/docs/stages/S01_剧本准备.md`：REQ/DES-S01-14、DES-S01-78 条文更新。
- `程序/tests/test_preparation_confirmation.py`：新增 3 条（基线变化撤销 ×2、
  基线不变保留 ×1）。
- `程序/tests/test_writing_unconfirm.py`：新增 3 条（取消撤销、无采用不写失效记录、
  取消后重确认维持撤销）。

## 已知边界（如实记录）

- 守卫以「确认基线集合」为判据：取消确认后重确认**同一文件**（sha 不变）时
  采用在取消动作发生的那一刻已撤销、不复原——与「显式取消确认即质疑采用」的
  语义一致，属有意取舍。
- `test_writing_quality.test_list_reports_maps_hash_folders_back_to_scripts`
  为并行负载下既有 flake，串行与单跑均绿，非本轮引入。

## 提交

`dev.py commit` 一批一轮，凭据见 `tasks_round/evidence/R2638.json`。
