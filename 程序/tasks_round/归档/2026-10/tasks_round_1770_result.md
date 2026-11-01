# R1770：修复轮——剧本准备纯文本发送回退为故事梗概（不再误判缺失）

1. 本轮类型：§3.2 修复轮。剧本准备发送纯文本（无「标签：值」）时，故事梗概未被识别、被误列为缺失项，补充创作信息表单里显示为空。

2. 测试跑了吗、三个基线过了吗：
   - 先红后绿：新增 `tests.test_idea_chat.SendMessageTests.test_unlabelled_prose_falls_back_to_story_summary`，改前红（'故事梗概' 出现在缺失列表），改后绿。
   - 定向回归：test_idea_inline_brief／test_idea_local_brief／test_idea_semantic_brief／test_idea_attachment_brief／test_idea_chat_attachment_refresh 全绿（exit=0）；发送流程 4 用例 OK；test_layers＋function_size_ratchet＋requirement_traceability 12 项 OK。
   - 默认冒烟 8/8。
   - 架构门禁全量、完整安全全量：未跑（改动为纯 L2 函数，按 §5 未命中强制条件；全量由 post-commit 后台补跑）。

3. project_status.md 欠账少了吗：本轮改源码 +1（idea_brief_form.py），全量欠账由后台补跑清账。

## 根因
send_message 用 `inline_required_missing`（idea_brief_form.py）计算缺项，它只用 `extract_brief_creation`（只认「标签：值」）解析草稿；纯文本无标签时返回空，故事梗概被误判缺失。而 `idea_chat._brief_fields` 里「无标签整段正文＝故事梗概」的回退在这条路径没有被应用（`receive_brief` 在 `inline_required_missing` 通过后才走到，纯文本时永远到不了）。

## 修复
`idea_brief_form.py` 新增 `unlabeled_story_summary()`：无标签整段非空正文回退为故事梗概，有显式「故事梗概」标签（含别名）则只认标签值；`inline_required_missing` 计算 draft 后、故事梗概为空时套用该回退。

## 校验
- 边界：空正文／「故事梗概：」空标签／别名（故事主体等）都不误回退。
- 断言未动：仅新增 1 条测试，未改既有断言。

## 独立验收（advisor，主树真实环境直接运行）

- 范围：idea_brief_form.py（新增 unlabeled_story_summary + inline_required_missing 套用回退）、tests/test_idea_chat.py（新增 1 条测试）。
- 先红证据：新增用例改前 `AssertionError: '故事梗概' unexpectedly found in ('故事梗概','故事题材','故事角色','故事集数','单集时间','交付形态')`。
- 定向回归：test_idea_inline_brief／test_idea_local_brief／test_idea_semantic_brief／test_idea_attachment_brief／test_idea_chat_attachment_refresh exit=0；发送流程 4 用例 OK；test_layers＋function_size_ratchet＋requirement_traceability 12 项 OK；冒烟 8/8。
- test_idea_chat 全模块有 4 失败＋3 错误，均为交接单 §5「旧遗留：test_idea_chat 多条」（气泡／附件／用量显示类，与本改动无关）。
- 断言未动：仅新增 1 条测试，未改既有断言。
