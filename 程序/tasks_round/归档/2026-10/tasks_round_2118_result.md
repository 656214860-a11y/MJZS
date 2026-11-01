# R2118 桌面续发材料按步骤取、SKILL 引用按需按节内联（REQ-S01-72／72）（功能轮）

- 本轮类型：功能轮（§3.1）。日期：2026-10-30。分支 `codex/wip-R2118`（领号时由 `claude/distracted-gagarin-2ffc8e` 带出；工作树 `happy-jennings-48da69`），起点 `878cc1d7`。
- 测试与基线：定向测试、默认冒烟通过；受影响冒烟有 1 项并行偶发红（见下），单独复跑通过。全量未运行（分支不累计欠账）。
- `project_status.md` 欠账：未减少；分支不改状态页，合入 master 后补记。

## 起因

用户在项目大纲修改阶段用 Gemini 发送「查看附件项目大纲：分析分集大纲的逻辑矛盾……」，附件任务文件（`摄影侠_20260930/工作流任务/writing/4f11d07178272324ecc7.md`，204 KB）里却带着自然剧本全文。原因有两处：

1. `desktop_send_ledger.material_targets()` 不看当前步骤，完整发送时无条件附带项目设定、项目大纲、角色卡、自然剧本和「当前采用的自然剧本」。
2. 材料只按当前模型的交付目录取。当前模型「Google Gemini 4 Argon」经 `storage_identity()` 识别为 Provider「自定义」，而它此前交付的设定和大纲在 `01剧本准备/Google/Google Gemini 4 Argon/创意_20261018/` 下，所以已确认的项目设定和要分析的大纲反而没带上。

另外，冻结 SKILL 把每个直接引用整份内联，不看「仅……时追加」条件和链接锚点（R2110 评估）。

## 改动

- 需求先行：`docs/stages/S01_剧本准备.md` 新增 REQ-S01-72／DES-S01-72、REQ-S01-73／DES-S01-73，锚定表加两行。
- `desktop_send_ledger.py`：新增 `STEP_OF`、`request_step()`（只看用户原话，`【附档：` 之后不算）、`current_step()`（点名优先，否则数连续已确认的准备文件，都没有按自然剧本步骤）、`_confirmed_documents()`、`_latest_document()`、`_material_path()`。`material_targets()`／`snapshot()` 增加 `request_text`，只收当前步骤及之前的材料；路径依次取确认件、本模型交付文件、本项目任一模型交付的同类最新一份。
- `workflow_tasks.py`：新增 `creative_source()`，取任务书里最后一段 `<剧本正文>` 内的用户输入。
- `desktop_send_choice._resend_plan()`：把本次输入传给 `snapshot()`。
- `skill_registry.reference_targets()`：Markdown 与其他相对链接条目加 `start`（链接在正文中的位置）。
- `workflow_settings.py`：新增 `_condition_unmet()`、`_anchor_slug()`、`_section()`；`_skill_blocks()` 增加 `locks`，条件不满足记 `conditional` 不读，带锚点只内联该节记 `section`，锚点找不到仍内联全文。`_inline_skill_report()`／`_inline_skill()` 透传 `locks`；`freeze_skills()` 与 `_one_skill_prompt()` 传 `workflow_lock`；`master_gate()` 不传，照旧核验全部引用。
- `skills/01 剧本准备SKILL/pipeline-script-preparation.skill.md`：「仅解说叙事类追加」改为「仅 `track` 为解说叙事类时追加」，与同行海外剧条件写法一致，便于按锁判定。
- 本轮途中误把 `desktop_send_choice.py`、`desktop_send_ledger.py`、`workflow_tasks.py` 存成 CRLF，已改回 LF，与 HEAD 一致。
- 新测试：`tests/test_desktop_send_steps.py`（6 条，REQ-S01-72）、`tests/test_skill_conditional_sections.py`（4 条，REQ-S01-73）。既有测试断言未动。

## 实测（用户项目，只读）

- 材料：「查看附件项目大纲：分析分集大纲的逻辑矛盾」判为项目大纲步骤，附带简报（779 字）、已确认项目设定（3,398 字）、项目大纲（35,270 字，Google 目录下 20261018 那份），不带角色卡和自然剧本。改动前带的是自然剧本，设定和大纲缺失。
- SKILL：剧本准备 SKILL 冻结正文，国内剧、原创项目从 59,960 字降到 20,594 字；不传锁（门禁）时 23,725 字，海外剧／解说／采风三份引擎只内联对应一节。

## 验证（本轮实际运行，经 `工作流任务/gui_hidden.py`）

- `run_selftests.py -k desktop_send_steps skill_conditional_sections skill_reference_closure desktop_send_ledger desktop_attachment_send master_skill request_freeze stage_prompt_governance writing_quality flow_agent_launch claude_writing_session req_s01_anchors requirement_traceability complexity_ratchet`：134 条，0 个文件有红。
- `run_selftests.py -k workflow skill layer writing desktop`：714 条，0 个文件有红。
- 加入大纲兜底后 `run_selftests.py -k desktop_send skill_conditional skill_reference_closure desktop_attachment requirement_traceability complexity_ratchet layer writing`：244 条，0 个文件有红。
- `smoke_test.py`（默认）：8/8 通过；`smoke_test.py --affected workflow_settings skill_registry desktop_send_ledger desktop_send_choice workflow_tasks`：9/9 通过（均在加入大纲兜底之前）。
- `smoke_test.py --affected desktop_send_ledger workflow_settings`（大纲兜底之后）：1,697 条中 `test_ui_edges.BriefTintTests.test_the_users_own_words_show_up_on_the_display` 红（创意草稿显示，与本轮改动无关）；单独 `run_selftests.py -k ui_edges` 115 条全绿，判为并行负载下的偶发红。
- 未运行：真实 Gemini 窗口里的端到端发送；`--architecture` 全部门禁；全量。

## 已知情况（未处理，范围外）

- 「Google Gemini 4 Argon」被识别为 Provider「自定义」，新交付会落到 `01剧本准备/自定义/…`，与旧交付不在同一目录。本轮只让续发材料能找到旧交付，没有改模型身份识别。

## 提交

见提交记录（`dev.py commit`）；未 push，未合入 master。

## 补记：需求改号

合入前发现 R2112（已合入 master 的 3498aee8）用了 REQ-S01-71／DES-S01-71。本轮需求顺延为 REQ-S01-72／DES-S01-72（材料按步骤）、REQ-S01-73／DES-S01-73（SKILL 按需按节），文档、锚定表、测试名与本文件同步改号，断言未动。
