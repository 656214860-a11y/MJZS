# R2427 结果：修复全量红（2 处撞棘轮的 DRY 去重 + 弹窗文案 + 测试适配 + 大纲误判回归）

## 三个必答（§7）

- **轮次类型**：修复轮（§3.2）——修复全量安全回归中的 5 个红：2 个「行数只降」棘轮违规（我此前 DRY 去重引入）、1 个弹窗文案超长、1 个模型管理页签化后的测试假设失效、1 个 R2423 引入的大纲正文归类回归（`test_idea_chat`）。
- **测试跑了吗、三个基线过了吗**：
  - 定向（全部 6 个原红文件）：`run_selftests.py -k test_copy_rules test_pet_settings test_complexity_ratchet test_module_size_ratchet` **78/78**；`-k test_idea_chat test_idea_download_kind` **164/164**。均 0 红。
  - 默认冒烟 **8/8**。
  - 全量：post-commit 自动触发后台全量（HEAD=cd7908ff，474 秒）——我的 4 个红已转绿，剩 `test_idea_chat`（R2423 回归）与 `test_round_baselines`（轮次头欠账）两红；后者已由「轮次头 2428」修复，前者由本轮 amend 补充修复。最终全量凭据待 post-commit 再触发一次确认。
- **project_status.md 的欠账少了吗**：本轮清掉全量 5 个红 + 轮次头欠账；`test_full_safe_all_is_required_after_eight_source_rounds` 的「R2427 欠全量凭据」状态红待全量绿灯后自动消失。

## 根因与修复

### 红1：writing_unconfirm 弹窗文案超长（test_copy_rules）

- **根因**：`writing_unconfirm.py` 的 `confirm_preparation_document` 抛出的 ValueError 文案「创作简报已变化，之前的阶段确认已失效；请先重新设为「项目设定」定稿，再依次确认「剧本大纲」「角色卡」」首行 50 字，超过弹窗上限 45 字。
- **修复**：缩短为「创作简报已变化，前置确认已失效；请先重设为「项目设定」定稿，再确认「剧本大纲」「角色卡」」首行 44 字。

### 红2：test_pet_settings 页签化后测试假设失效（KeyError: ChatGPT Desktop · Codex）

- **根因**：R2398 模型管理页签化后，模型列表按 API/Desktop/CLI 页签分组显示，`ChatGPT Desktop · Codex` 在 Desktop 页签、`Claude Code` 在 CLI 页签、`GPT-4o` 在 API 页签。旧测试 `test_the_manager_groups_gpt_entries_and_sorts_rows_by_label`、`test_the_list_shows_the_call_mode_and_leaves_api_details_to_the_form` 假设列表全量显示，直接索引 `providers['ChatGPT Desktop · Codex']` 触发 KeyError。
- **修复**：两个测试分别切到对应页签再验证，断言不变（只改定位，不改断言语义）。

### 棘轮红：2 处 DRY 去重撞「行数只降」门禁

- **根因**：此前为消重引入 `OPEN_PROGRESS_PANEL` 常量（pet_agent.py 1182→1184）与 `configure_video_api` helper（desktop_media_pages.py::MediaPagesMixin 890→892），超「模块/类行数只许下降」上限。
- **修复**：回退这 2 处 DRY 去重，恢复两处字面量。**放弃这 2 处去重**——DRY 加常量/helper 必然加行数，与行数棘轮硬门禁冲突；正确做法是「随文件拆分时顺带去重」，而非单独加行。两处短文案重复（`'好，把进度面板打开。'` ×2、`配置线上视频 API` button ×2）可接受。

### 红5：test_idea_chat 大纲正文归类回归（R2423 引入，'项目剧本' != '项目大纲'）

- **根因**：R2423 为修复「回退确认提示被误判成角色卡」（REQ-S01-76），把 `idea_document_paths._project_file_type()` 的「正文任意位置关键词兜底」**整段删除**，只留标题行匹配。这矫枉过正：模型回复常直接写「模型写的纲要：…」这类正文，不含标题行，于是被归到「自然剧本」→存成「项目剧本」，而非期望的「项目大纲」。
- **关键区分**：回退确认提示里只有「项目设定/剧本大纲/角色卡」，**没有**「纲要/故事大纲/分集大纲」。所以「大纲」的正文兜底是安全的（不命中回退提示），误判根源仅在「角色卡/项目设定」的正文兜底。
- **修复**：恢复「大纲」的正文兜底（`项目大纲/故事大纲/分集大纲/纲要` in 正文 → 项目大纲）；「角色卡」「项目设定」仍只按标题行归类，保住 R2423 的 REQ-S01-76 目标。
- **验证**：`test_idea_chat`（164 条，含 `test_only_the_model_output_lands_in_the_creative_file`）与 `test_idea_download_kind`（含 R2423 新增的 `test_control_prompt_mentioning_type_is_not_a_document`）均绿——既修了误伤，又没重蹈回退提示误判。

## 决策依据（保留，供追溯）

- **资产提示词两条文案**（asset_prompt_check_dialog vs asset_reference_prompts_dialog）不去重：两处标点不同（`；` vs `，`），非逐字相同，强行统一改变用户可见文字。
- **「登录成功」**（desktop_login_gate vs desktop_account_page）不去重：跨文件 4 字串引入 import 耦合得不偿失，两入口非同时出现。
- **大纲正文兜底 vs 角色卡/设定正文兜底**：只恢复大纲的正文兜底，因为回退确认提示（及同类控制提示）只顺带提「角色卡/项目设定」字样、从不提「纲要」，故大纲正文兜底不会复现 REQ-S01-76 的误判。

## 已提交

- commit：`cd7908ff` R2427（amend 后：5 个红修复，含 `idea_document_paths.py` 的大纲兜底与 `project_status.md` 轮次头 2428）
- 文件：`desktop_media_pages.py`、`idea_document_paths.py`、`pet_agent.py`、`project_status.md`、`tests/test_pet_settings.py`、`writing_unconfirm.py`

## 并发冲突处理记录（本次任务全程）

- 本 DSH 会话与另一 Claude Code 会话共用 master 主树并发，导致「领号被脏树拒绝 → 提交被轮次校验拒绝」死锁，持续约 9.5 小时。
- 最终处理：用户让另一会话停止后，本会话将其遗留 WIP（6 文件）与自己的交接文件 stash 保存（`stash@{1}`=遗留 WIP、`stash@{0}`=旧交接文件），使 master 干净 → 领 R2427 → 恢复并提交本轮的修复文件。
- 另一个会话的遗留 WIP 与用户改动的 AGENTS.md（车道 5 条）仍在 stash 中待其恢复：`stash@{1}`（遗留 6 文件）、`stash@{2}`（AGENTS.md）。
