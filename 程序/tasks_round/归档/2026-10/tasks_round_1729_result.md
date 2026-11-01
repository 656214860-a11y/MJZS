# R1729：需求锚定轮——S01 十四条需求补测试锚点（REQ01）

执行方交付件，未领号、未提交、未改 `project_status.md`；`[TASK_COMPLETE]` 由派发方复核后判定。

## 三个必答（§7.3）

1. **轮次类型**：需求锚定／测试资产维护轮（§3.10 验证/基线轮范围；只补测试锚点与台账，不改产品行为）。
2. **测试跑了吗、基线过了吗**：跑了。定向 `run_selftests.py -k ...` 295 条用例、139.8 秒、0 个文件有红、实际跳过 0 条，`ALL TESTS PASSED`；锚定门禁 `tests.architecture.test_requirement_traceability` 6 项 OK。默认冒烟／架构门禁属提交方收口范围，本执行方未越权改状态页。
3. **`project_status.md` 的欠账少了吗**：状态页由提交方在合入后补记；本轮事实是锚定基线 `维护记录/需求锚定基线.json` 欠账 73→59（减少 14 条，全部为 S01）。

## 改动范围

- 新增 `tests/test_req_s01_anchors.py`（无现成锚点的 2 条）。
- 在既有 S01 测试文件的对应用例 docstring 中补 `REQ-S01-xx`（只加 docstring，未改任何断言）：`test_idea_chat.py`／`test_idea_attachments.py`／`test_preparation_confirmation.py`／`test_script_contract_production_locks.py`／`test_script_structure.py`／`test_writing_api.py`／`test_writing_restart.py`。
- `维护记录/需求锚定基线.json`：仅删除 14 条 S01 编号，未新增、未改其他阶段。
- `docs/REQUIREMENTS.md`：未改（14 条全部锚定成功，无 ✅→🟡）。
- `维护记录/skip台账.json`：未改（无新增 skip）。

## 锚点对照表

| 编号 | 锚点测试 | 断言 → 需求原文 | 结论 |
| --- | --- | --- | --- |
| REQ-S01-01 | `test_idea_chat.py::...::test_the_conversation_round_trips_and_feeds_the_next_prompt`；`test_idea_attachments.py::...::test_local_markdown_reuses_conversion_without_embedding_text` | 创意对话落盘后重载原样取回、并作为下一次请求上下文；附档转 Markdown 引用后正文不入提示词 | 锚定 |
| REQ-S01-02 | `test_idea_chat.py::...::test_brief_intake_writes_raw_then_complete_only_after_required_fields` | 必填项缺一时不写 complete，补齐后才完成 | 锚定 |
| REQ-S01-03 | `test_script_contract_production_locks.py::...::test_gate_old_warns_new_blocks_and_selected_passes` | 旧项目缺项只提示、新项目阻断、选定值放行 | 锚定 |
| REQ-S01-04 | `test_idea_chat.py::...::test_model_rename_keeps_history_and_deleted_message_identity` | 改名后历史仍可寻址，删除消息身份不漂移 | 锚定 |
| REQ-S01-10／13 | `test_writing_api.py::...::test_preparation_requires_each_confirmation_and_hands_all_documents_to_script_request` | 四步固定，第④步只在①②③全确认后才收到完整文档并启动 | 锚定 |
| REQ-S01-11 | `test_writing_api.py::...::test_incomplete_preparation_output_never_publishes_or_advances`；`test_preparation_confirmation.py::...::test_confirm_refuses_when_previous_stage_unconfirmed` | 不合格输出不发布、不推进；前一步未确认拒绝下一步登记 | 锚定 |
| REQ-S01-12 | `test_writing_api.py::...::test_confirmation_uses_user_message_not_attachment_context` | 只认输入框原文首行的确认，附档正文中的“确认”不顶替 | 锚定 |
| REQ-S01-14 | `test_writing_restart.py::...::test_confirm_new_outline_invalidates_character_and_script`；`...::test_restart_each_stage_preserves_adopted_until_confirmation` | 确认重写后该步及下游确认失效、已采用稿撤销；重写未确认前旧稿仍在 | 锚定 |
| REQ-S01-20 | `test_writing_api.py::...::test_api_formal_script_reuses_download_path_and_versions_changed_text` | 同一阶段多稿并存可区分，正文有变才另存新稿、不覆盖旧稿 | 锚定 |
| REQ-S01-21 | `test_script_structure.py::...::test_multiple_model_drafts_require_explicit_adoption_and_pin_content` | 多份自然稿必须用户明确采用，不按时间自动采用 | 锚定 |
| REQ-S01-22 | `test_req_s01_anchors.py::S01AnchorTests::test_req_s01_22_completion_evidence_is_the_adopted_script_source` | 无可解析剧本源时 `completion_evidence` 为假且不发完成事件；出现被采用源后才发 `stage.completed` | 锚定 |
| REQ-S01-30 | `test_writing_api.py::...::test_custom_desktop_model_uses_its_program_without_api`；`...::test_direct_api_uses_complete_brief_and_auto_saves` | 桌面模型直投其程序不走 API 配置；API 方式按完整简报自动归档正文 | 锚定 |
| REQ-S01-31 | `test_writing_api.py::...::test_missing_selection_survives_refresh_and_blocks_transport`；`test_req_s01_anchors.py::S01AnchorTests::test_req_s01_31_oversized_or_missing_skill_blocks_send_without_truncation` | 已勾选 SKILL 缺失时阻止发送（刷新后仍阻止）；SKILL 超预算抛错而不截断，预算内原样返回 | 锚定 |

## 命令与计数（实际运行）

- `python -B -m unittest tests.test_req_s01_anchors tests.architecture.test_requirement_traceability` → `Ran 6 tests`，`OK`，exit 0。
- `python -B run_selftests.py -k test_req_s01 test_idea_chat test_idea_attachments test_writing_api test_preparation_confirmation test_writing_restart test_script_contract_production_locks test_script_structure` → `295 条用例，139.8 秒；0 个文件有红`，`实际跳过 0 条用例`，`ALL TESTS PASSED`。
- 基线核对：`untested_done` 计数 73→59，`REQ-S01*` 残留为空。

## 需裁决事项

- **REQ-S01-01 的“气泡式对话界面”**：非 Tk 锚点落在对话持久化往返与受控附档上；界面呈现仅由既有 S01 Tk 测试间接覆盖。若要求“气泡式 UI”本身也必须有独立锚点，请裁决是否另开真 Tk 几何锚点。
- **基线 JSON 格式**：原文件为 `indent=1` 且无结尾换行；本轮按任务书显式要求写为 `indent=2` + 结尾换行，故 diff 含整表缩进变化（语义仅删除 14 条 S01）。若要求最小 diff 可改回 `indent=1`。

## 自审（§4.2）

- 验收标准：14 条全部有真实行为锚点，删除对应实现即变红；无源码字符串断言。通过。
- 改动范围：仅任务书允许的测试文件、基线 JSON；未碰产品代码、S04/S06、UI 批处理文件、`private/`、`.env`、状态页。通过。
- 未运行项：默认冒烟 `smoke_test.py`、架构门禁 `--architecture`、全量安全回归（属提交方收口；本执行方不越权）。
- 新问题：无；无新增 skip、无断言弱化、无测试逻辑改动。

## 独立验收（Claude，主工作区）

- 车道 diff 在 R1728 之上干净应用；测试改动仅 docstring 补锚点，断言未动。
- 定向 `run_selftests.py -k`（同执行方范围）295 条 1 红：`test_writing_api::test_api_formal_script_reuses_download_path_and_versions_changed_text`，读取本机真实模型配置导致，干净 HEAD 绿、主树红，与本批无关，另行处理。
- `tests.architecture.test_requirement_traceability` OK；`smoke_test.py` 默认 8/8；`--architecture` 368 条仅全量欠账 1 红（后台自动补跑，不阻断）。
- 需裁决（沿用执行方）：REQ-S01-01 气泡式界面是否另开真 Tk 锚点；基线 JSON 缩进 indent=2 是否接受。
