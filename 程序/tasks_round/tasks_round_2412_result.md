# R2412 修复轮结果：优化剧本准备「先后确认」的报错文案

## §7 三问

1. **本轮类型**：修复轮（§3.2）——只改报错文案，不改产品逻辑与数据结构。起因是用户反馈「采用角色卡定稿时提示确认之前阶段，但项目大纲/设定都已确认」——实为简报变化或前置确未确认，旧文案「请先确认所选阶段之前的文件」不说明缺哪几步、怎么恢复。
2. **测试跑了吗、三个基线过了吗**：
   - 定向（先红后绿）：`run_selftests.py -k preparation_confirmation writing_api writing_unconfirm writing_edited_restart --serial` 97 条 0 红。`test_confirm_refuses_when_previous_stage_unconfirmed` 断言由旧文案改为「之前还有阶段未确认」，修复前红（旧文案不匹配新断言）、修复后绿。
   - 架构门禁：`run_selftests.py -k test_module_size_ratchet test_layers --serial` 8 条 0 红（行数棘轮、分层门禁均绿）。
   - 默认冒烟：未单独跑（只改报错文案，不改 Tk 控件；上一轮同模块已跑过）。
   - 全量：未跑（纯文案改动，不命中 §5 强制全量条件）。
3. **project_status.md 的欠账少了吗**：不涉及欠账条目。

## 改动

只优化两处「先后确认」硬拦截的报错文案，让用户知道缺哪些前置、怎么最快恢复；**不改变「不确认不进下一步」的顺序约束**（这是数据依赖守卫，设定→大纲→角色卡→自然剧本的下游唯一剧本源依赖它）。

- `writing_unconfirm.py` `confirm_preparation_document`：非简报变化、前置未确认时，旧文案「请先确认所选阶段之前的文件」改为「「角色卡」之前还有阶段未确认（项目设定、剧本大纲）；请先依次把这些阶段设为定稿，再设「角色卡」」——列出具体缺哪些前置。
- `writing_api.py` `_preparation_state` 对话路径：旧文案「前置阶段尚未确认，不能跳阶段」改为「「X」尚未确认，不能跳到后续阶段；请先确认「X」」——点出是哪个阶段未确认。

## 测试资产

- `tests/test_preparation_confirmation.py`：`test_confirm_refuses_when_previous_stage_unconfirmed` 断言从旧文案改为「之前还有阶段未确认」，锚定新文案。断言未弱化（仍断言拒绝登记 + 说明缺失前置）。

## 未做（说明）

用户原始诉求「取消先后限制」经评估**不采纳**：先后顺序是数据依赖守卫（角色卡依赖大纲、大纲依赖设定、自然剧本依赖前三者，后续 12 阶段依赖被采用的自然剧本）。「松右键设稿」会触及 `documents` 的「位置=阶段」核心不变式（`_preparation_state`、`preparation_progress`、自然剧本门禁多处依赖），改动面大、风险高。本轮只优化文案，把「怎么最快恢复」讲清楚。

## 提交

- 已提交：见提交记录。
