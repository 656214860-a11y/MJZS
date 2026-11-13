# R2423 修复轮结果

- 轮次类型：修复轮（§3.2）。
- 测试跑了吗、三个基线过了吗：
  - 定向 `tests/test_idea_download_kind.py` 3/3 通过（含新增回归用例，红→绿：改动前 `download_kind(回退提示)=='角色卡'` 失败，改动后返回 `''`）。
  - `tests/test_workflow_writing_stages.test_role_card_heading_uses_existing_classifier` 通过（标题归类不回归）。
  - 默认冒烟 8 项检查通过；`smoke_test.py --affected idea_chat` 的门禁子步骤因沙箱无法派生 `multiprocessing.Pipe`（WinError 5）中断，属环境限制，非本轮代码导致。
  - 架构门禁、全量 `--all --safe` 未跑（沙箱内无法派生工作进程；AGENTS.md §5 要求沙箱外跑）。
- `project_status.md` 的欠账少了吗：本轮为缺陷修复，未新增欠账；全量欠账计数不变（未跑全量，不产生绿凭据）。

## 根因与复现

**现象**：回退确认提示（「回退到「项目设定」重新创作，会使已确认的「项目设定」「剧本大纲」「角色卡」失效…」）被自动存档成「角色卡」文件，而它根本不是模型返回的文档。

**根因**：`idea_document_paths._project_file_type()` 对正文做了「全文字符串包含」兜底归类（`'角色卡' in value` 等），只要模型回复里顺带提到「角色卡」「项目设定」等字样就被判成对应文档。回退确认提示恰好包含这些字样，于是 `download_kind` 返回 `'角色卡'`，随后 `auto_save_reply` 把它写进文件表。

## 修复

`idea_document_paths._project_file_type()` 改为**只认标题行**（行首即类型标签，可带 `#` 等标记），不再对正文任意位置做「包含」匹配。标题行不在首行的类型标签仍能被识别；未命中任何标题的类型默认归自然剧本，再由 `download_kind` 用 `looks_like_script` 闸门兜底（回退提示过短，不会被当成剧本）。

改动文件：
- `程序/idea_document_paths.py`（`_project_file_type` 兜底归类收紧为标题行匹配）
- `程序/tests/test_idea_download_kind.py`（新增 `test_control_prompt_mentioning_type_is_not_a_document`，锚定 REQ-S01-76）

## 验证

- 改动前：`test_control_prompt_mentioning_type_is_not_a_document` FAIL，`AssertionError: '角色卡' != ''`。
- 改动后：3/3 通过；直连 `download_kind` 复测：`# 项目设定/项目大纲/角色卡/分集大纲` 仍正确归类，回退提示与普通闲聊返回 `''`。

## 提交

- 已提交：是（commit hash 见提交回执）。
