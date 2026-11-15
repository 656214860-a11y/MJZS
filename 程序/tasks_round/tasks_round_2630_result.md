# R2630 结果：右键「设为定稿」确认完整重写稿时切换采用版本并撤销自然稿采用
<!-- round-evidence: {"commit_base": "e0f39147", "credential_hits": 0, "evidence_sha256": "5b67561fca27473b", "exit": 0, "failed": 0, "passed": 126, "round": 2630, "tests": "run_selftests.py -k writing_api writing_unconfirm preparation_confirmation writing_restart writing_edited_restart preparation_monitor"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   修复轮（§3.2）。任务源：`tasks_round/盘点_剧本准备逻辑分析.md`（用户指定「按照文件修复剧本准备逻辑」）。
   轮次号说明：本会话先领 R2623，提交时中央计数器已被其他车道推进到
   R2629，重新领取 **R2630**；R2623 成空号（无提交、无结果文件）。
   盘点所列七项经逐条对照现有代码与测试核实：**唯一真实缺陷**是冲突 3 的
   菜单确认分支——`writing_unconfirm.confirm_preparation_document`（右键
   「设为定稿」）把确认写入 `state['revision']['documents']` 后，即使重写稿
   三阶段全部确认，也不把 `revision` 切换为顶层采用版本 `documents`，更不
   撤销 `natural_script_selection.json` 的已采用自然稿。聊天确认路径经
   `save_decision()` 在 advancing 时完成同样的切换＋撤销（REQ-S01-14），
   两条确认入口口径不一致，旧采用版本与旧自然稿会继续被下游引用。
   其余盘点项均为误报或有意设计（见「未改动的盘点项」）。分支
   `codex/wip-R2630`，commit base `e0f39147`。

2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 **8/8** 通过（第 10 轮）。
   - `smoke_test.py --affected writing_api writing_unconfirm`：29 个测试文件
     **0 个文件有红**（149 秒；含 Tk 用例经隐藏桌面令牌）。首跑串行时
     `test_writing_quality.test_list_reports_maps_hash_folders_back_to_scripts`
     偶发 1 红（哈希目录映射），单跑该文件 17/17 绿、复跑门禁全绿，
     与本改动无关（本轮不触碰 quality 哈希映射）。
   - 定向：`test_preparation_confirmation` 11/11、`test_writing_restart` 11/11、
     `test_writing_edited_restart` 11/11、`test_writing_unconfirm` 9/9、
     `test_preparation_monitor` 9/9、`test_writing_restart_intent` 4/4；
     `test_writing_api`/`test_writing_quality`/`test_writing_status_line`/
     `test_script_workspace*`/`test_script_contract*`/`test_stage_completion_service`
     共 216 条全绿。
   - 先红后绿：新增回归用例 `test_confirm_last_rewrite_stage_promotes_revision_and_revokes_script`
     改动前失败输出（`AssertionError: 'revision' unexpectedly found`）已在会话留存，
     改动后通过。
   - 全量 `--all --safe`：未跑（修复分支不累计欠账；期间另一车道正在执行
     `run_selftests.py --all --safe`，本树定向证据以上述为准）。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账；修复使 REQ-S01-14 的两条确认入口（聊天＋右键菜单）在
   「采用版本切换＋自然稿撤销」上收敛到同一 helper，消除一份重复实现。

## 根因与修复

- 聊天确认：`_preparation_step.save_decision()` 在 `advancing`（产出下一阶段稿
  或自然剧本）且存在 `revision` 时，把 `revision.documents` 整体切换为
  `state['documents']`（可带未确认尾稿）、同步 `brief_hash`、并写
  `natural_script_selection.json` 失效记录，再通过 `update_index` 回写台账。
- 菜单确认：`confirm_preparation_document()` 此前只写 `revision.documents`
  并直接 `_save_preparation_state`，永远不做切换/撤销。
- 修复方式（最小改动）：
  - `writing_api` 新增两个私有 helper：`_revoke_natural_script_adoption`
    （失效 payload＋台账回写链）与 `_promote_revision`（pop revision、
    切换 documents/brief_hash、调撤销；无 revision 返回 False）。
  - `save_decision` 改为复用 `_promote_revision`，行为与原版完全一致
    （advancing 才触发；revision 缺失/为空回退普通保存）。
  - `_preparation_step` 三阶段齐全的早退分支调用 `_promote_revision`：
    兜底「菜单确认完整重写稿后再发起聊天」及遗留 revision。
  - `confirm_preparation_document`：`revision.documents` 达到三阶段齐全
    （len==3）时调 `_promote_revision`；中途确认仍留在 revision（与聊天
    「推进才采用」同口径，`test_right_click_confirmation_keeps_current_revision_when_brief_changed`
    为既有契约）。重写草稿未推进到目标阶段而回退到采用版本操作（rebound）
    时，采用版本同样变化，一并撤销自然稿采用。

## 未改动的盘点项（核实为误报或有意设计）

- 冲突 1（P0）：`natural_script_selection.json` 不是遗留——`script_contract`
  的 `natural_script_selection_path`/`resolve_script_source` 是自然稿采用唯一
  权威；`preparation_progress` 有意只判前三阶段（R2321），自然稿由
  `completion_evidence` 另行核验。
- 冲突 4（P0）：无 `brief_complete.json` 时 `confirmed=3` 是「门禁不适用」
  哨兵，`completion_evidence` 仍要求 `resolve_script_source`，空项目不会被
  判完成（`EmptyProjectBehaviorTests` 已覆盖）。
- 冲突 2（P1）：SHA256 精确绑定是有意约束，已有末尾换行容忍与
  「设为定稿/取消已确认」恢复路径（`test_preparation_confirmation` 覆盖）。
- 规则 1/3/4：串行顺序（REQ-S01-11）、质检报告为建议性（REQ-S01-22/23）、
  确认关键词（REQ-S01-12）均为既定需求，盘点建议与之冲突，不改。
- 优化 1–5：简报实时校验、模型/耗时字段、段落级采用、快照对比、
  next_actions——非阻断项，不在本轮范围。

## 改动清单

- `程序/writing_api.py`：新增 `_revoke_natural_script_adoption`、
  `_promote_revision`；`_preparation_step` 早退分支补 promote；
  `save_decision` 收敛到 helper（净 -8 行重复实现）。
- `程序/writing_unconfirm.py`：`confirm_preparation_document` 完整重写稿
  确认时切换采用版本并撤销自然稿采用；回退采用版本操作同步撤销。
- `程序/tests/test_preparation_confirmation.py`：新增回归用例
  `test_confirm_last_rewrite_stage_promotes_revision_and_revokes_script`
  （重写稿经右键确认到三阶段齐全 → documents 切换、revision 清除、
  natural_script_selection 写失效记录）。

## 提交

`dev.py commit` 一批一轮，凭据见 `tasks_round/evidence/R2630.json`。
