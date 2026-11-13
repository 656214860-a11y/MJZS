# R2404 修复轮结果：采用角色卡定稿误报「请先确认所选阶段之前的文件」

## §7 三问

1. **本轮类型**：修复轮（§3.2）——修 bug；因 `writing_api.py` 已顶到行数上限（1372），本轮随修复把 `confirm_preparation_document` 拆到 `writing_unconfirm.py`（与既有的 `unconfirm_preparation_document` 对称收口），属「为过架构门禁而做的必要拆分」，非顺手重构。
2. **测试跑了吗、三个基线过了吗**：
   - 定向（先红后绿）：`run_selftests.py -k preparation_confirmation writing_unconfirm writing_edited_restart --serial` 28 条 0 红。新增 `test_confirm_character_card_falls_back_to_adopted_when_revision_incomplete` 修复前红（`ValueError: 请先确认所选阶段之前的文件`，精确复现用户现场），修复后绿。
   - 架构门禁：`run_selftests.py -k test_module_size_ratchet test_layers --serial` 8 条 0 红（行数棘轮、分层门禁均绿；本轮曾引入的两个红——`writing_api.py` 1383 行超限、`_repro_confirm_bug.py` 未登记层级——已分别经拆分与删除临时文件消除）。
   - 默认冒烟：`smoke_test.py` 8/8 通过。
   - 受影响回归：`smoke_test.py --affected writing_api` 9 项全绿（覆盖 test_idea_chat、test_writing_* 等全部消费者）。
   - 全量：未跑（修复轮只改 L3 剧本准备确认逻辑与模块归属，不命中 §5 强制全量条件）。
3. **project_status.md 的欠账少了吗**：不涉及欠账条目；本轮是纯 bug 修复 + 必要拆分。

## 根因与修复

- **根因**：`writing_api.confirm_preparation_document`（右键「设为 X 定稿」）判断「前置阶段是否已确认」时用 `_working_documents(state)`，它在存在 `revision`（重写草稿）时返回 `revision.documents`，而该列表只保留「重写起点之前的已确认前缀」。例如重写「剧本大纲」后 `revision.documents` 只有 `[项目设定✓]`（长度 1），此时用户右键「设为角色卡定稿」（index=2），`_confirmed_prefix(documents, 2)` 因长度不足返回 None，误报「请先确认所选阶段之前的文件」——尽管采用版本（顶层 `documents`）里设定、大纲、角色卡其实都已确认。
- **修复**：在 `_confirmed_prefix` 于重写草稿上失败、但采用版本（顶层 `documents`）前置已确认时，回退到采用版本操作并清理进行中的重写草稿（`revision`／`pending_restart`）。保持既有语义：重写草稿已推进到目标阶段时仍在 revision 上操作（不破坏 `test_right_click_confirmation_keeps_current_revision_when_brief_changed`）。

## 拆分（必要，为过架构门禁）

- `writing_api.py`：删除 `confirm_preparation_document`（-45 行），1383 → 1327 行，回到上限 1372 以下。
- `writing_unconfirm.py`：新增 `confirm_preparation_document`（含上述回退逻辑），与既有的 `unconfirm_preparation_document` 对称收口；模块 docstring 改为「剧本准备阶段确认与取消」。
- `stage_execution_service.py`：`confirm_writing_preparation` 的 import 由 `writing_api` 改为 `writing_unconfirm`。
- `outputs/_head_ses.py`（被 gitignore 的本地副本）：同步 import，不影响提交。

## 测试资产

- `tests/test_preparation_confirmation.py`：新增 `test_confirm_character_card_falls_back_to_adopted_when_revision_incomplete`（采用版本三阶段全确认 → 重写大纲 → 设为角色卡定稿应成功并回落采用版本、清 revision）；既有 6 处调用随函数搬家由 `writing_api.` 改为 `writing_unconfirm.`，断言未弱化。
- `tests/test_writing_edited_restart.py`：1 处 `confirm_preparation_document` 调用同步改为 `writing_unconfirm.`。

## 复现步骤

1. 项目三阶段（设定、大纲、角色卡）均已确认。
2. 右键「重写剧本大纲」，产生 `revision`（其 `documents` 只保留设定，长度 1）。
3. 右键角色卡文件「设为角色卡定稿」。
4. 修复前：报 `请先确认所选阶段之前的文件`；修复后：成功采用，`revision` 被清除，顶层 documents 更新为角色卡定稿。

## 提交

- 已提交：是/否（见提交记录）。
