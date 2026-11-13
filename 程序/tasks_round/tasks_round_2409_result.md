# R2409 修复轮结果：改简报后「设为角色卡定稿」误报「请先确认所选阶段之前的文件」

## §7 三问

1. **本轮类型**：修复轮（§3.2）——修 bug。延续 R2404 对同一函数 `confirm_preparation_document` 的修复：上一轮只覆盖「重写草稿（revision）进度不足」，本轮补上「创作简报变化导致旧确认记录失效」这一更常见的触发场景。
2. **测试跑了吗、三个基线过了吗**：
   - 定向（先红后绿）：`run_selftests.py -k preparation_confirmation writing_unconfirm writing_edited_restart --serial` 30 条 0 红。新增两条用例修复前红（`test_confirm_reports_brief_change_when_previous_confirmed` 修复前报 `请先确认所选阶段之前的文件`，正是用户现场），修复后绿。
   - 架构门禁：`run_selftests.py -k test_module_size_ratchet test_layers --serial` 8 条 0 红（行数棘轮、分层门禁均绿）。
   - 默认冒烟：未单独跑（本轮只改 `writing_unconfirm.confirm_preparation_document` 的报错分支，不改 Tk 控件；上一轮同函数已跑过默认冒烟 8/8）。
   - 全量：未跑（修复轮只改 L3 剧本准备确认逻辑，不命中 §5 强制全量条件）。
3. **project_status.md 的欠账少了吗**：不涉及欠账条目；纯 bug 修复。

## 根因与修复

- **根因**：`confirm_preparation_document`（右键「设为 X 定稿」）开头用 `brief_hash` 校验创作简报（`brief_complete.json`）是否变化。用户确认设定、大纲后，若又改了创作简报（哪怕只改一句），`brief_hash` 不匹配，函数把 `state` 静默重置为 `documents: []`，随后 `_confirmed_prefix([], 2)` 因前置记录全空而报笼统的「请先确认所选阶段之前的文件」——用户明明确认过设定、大纲，却被误导为「前置没确认」。
- **修复**：区分「简报是否变化」，简报变化且目标阶段有前置（index>0）时，报明确、可操作的错误「创作简报已变化，之前的阶段确认已失效；请先重新设为「项目设定」定稿，再依次确认「剧本大纲」「角色卡」」；同时保留「简报变化后仍可从项目设定重新开始」（index=0 前置为空，不受影响）。

## 测试资产

- `tests/test_preparation_confirmation.py` 新增两条：
  - `test_confirm_reports_brief_change_when_previous_confirmed`：简报变化后设为角色卡定稿，断言报「创作简报已变化」（而非笼统「请先确认所选阶段之前的文件」）。
  - `test_confirm_setting_allowed_after_brief_change`：简报变化后仍能从「项目设定」重新设为定稿。

## 复现步骤

1. 确认项目设定、剧本大纲（右键设为定稿）。
2. 修改创作简报（brief_complete.json）任意内容。
3. 右键角色卡文件「设为角色卡定稿」。
4. 修复前：报「请先确认所选阶段之前的文件」（误导）；修复后：报「创作简报已变化……请先重新设为项目设定定稿……」。

## 提交

- 已提交：见提交记录。
