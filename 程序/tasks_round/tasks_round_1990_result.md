# R1990 结果（修复轮）

## 用户反馈
1. 阶段配置页（剧本准备）红框标签「编剧风格」改为「风格」；全部标签文字左对齐并缩进。
2. 全部下拉框长度再缩短 1/3。

## 改动
- `ui_tokens.STAGE_PANEL_LAYOUT`：`select_width` 12 → 8（一个令牌控制预设／厂商／总控／SKILL／制作锁全部下拉框）；新增 `label_indent`（取 `SPACING['xs']`）。
- `production_lock_fields`：
  - `CompactLabel` 默认 `anchor='w'` 加左缩进，请求宽度含缩进；
  - 制作锁与总控行的标签改 `sticky='w'` 并带同样缩进；
  - `label_pixel_width` 的量宽探针带同样缩进，列宽与实际标签一致。
- `skill_panel`：「编剧风格」标签改「风格」（按钮「编辑编剧风格」文字未动）；预设／厂商／风格／SKILL 标签去掉 `anchor='e'`，走新默认左对齐。
- 测试：
  - `test_skills`、`test_skill_panel_dropdown_layout` 里引用旧标签文字「编剧风格」的两处改为「风格」；
  - `test_lock_dropdowns_fill_ordered_rows` 契约有意变更：下拉框变窄后 1280 宽一行放 6 项，「更多制作锁」按钮与提示落在行中间，其后字段 x 随提示宽度浮动，原“按全部锁字段序号比列”会误判，改为只比每行开头连续的字段；等宽、不越界、顺序、标签紧贴等其余断言未动。

## 验证
- gui_hidden 定向：skill_panel／production_lock／test_skills／pet_ui／ui_tokens／stage_config 共 796 条。
- 红项均非本轮引入：
  - `test_pet_ui` 6 条（登录闸门、云朵位置），干净 master 同样红；
  - `test_skills` 2 条技能总数 71≠73，仅 worktree 缺外部技能仓库 `00全流程SKILL/AIGC创作全流程/.git`，主目录绿。
- 未跑 smoke 与 `--all --safe`；未在真实窗口目测，缩进量与下拉框宽度观感待用户确认。
