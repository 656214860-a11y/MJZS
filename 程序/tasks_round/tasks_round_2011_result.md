# R2011 结果（功能轮）

## 用户需求
预设要包含「总控＋厂商＋风格＋SKILL」，下拉选项按创作模式分组：短视频、短剧、影视、动画。

## 改动
- `stage_config`（预设版本 2 → 3）
  - 预设记录新增可选项：`mode`（创作模式）、`workflow`（总控名、总控包路径、该总控的制作锁；名称为空表示「不使用总控」）、`writer_style`（仅剧本页）。模型 id 本身决定厂商，套用时厂商下拉随模型联动，所以不另存厂商字段。
  - `save_preset(..., extra=None)`：mode／workflow／lock／writer_style 收在 `extra` 里（`extra` 以外的签名不变，旧调用照常）；同名覆盖时不传 mode 则保留原模式。
  - `apply_preset(..., known_workflows=None)`：模型、SKILL 之外，记了风格就写风格，记了总控就写总控（记成「不使用」则退出统筹）；总控已不在总控清单里则跳过，不写半截数据。旧预设没有这些项，套用时不动当前总控与风格。
  - 新增 `PRESET_MODES`、`PRESET_MODE_NONE`（旧预设归「未分类」，排最后）、`preset_mode`、`preset_groups`。
- `skill_panel_presets`
  - 预设下拉按模式分组，组标题形如「—— 短剧 ——」，选中标题不套用，下拉框退回原选择。
  - 保存预设：名称之后再弹「预设的创作模式」选择（取消即不保存）；保存时一并记当前总控、制作锁与（剧本页的）风格。
  - 套用后状态行提示总控已不存在而未套用的情况。
- `pet_ui_voice` → `pet_ui_popup`：R2010 的 `in_main_view`／`can_pop` 两个方法搬到 `PetPopupMixin`（行为不变），把 `PetVoiceMixin` 压回登记上限 1119 以内（R2010 提交时漏了这条类行数红）。
- 测试：`test_skills` 新增 `test_preset_keeps_master_style_and_mode_and_groups_the_dropdown`；既有 `test_preset_picker_starts_with_placeholder_and_can_overwrite_selection` 仅增加「模式对话框」的替身，断言未动。

## 验证
- gui_hidden：test_skills／test_manual_plan／test_pet 系共 1213 条；红项均为既有基线：`test_pet_ui` 登录闸门 5 条、云朵位置 1 条，`test_skills` 技能总数 71≠73（仅 worktree 缺外部技能仓库）。
- `smoke_test.py --architecture`：剩 agents_md、round_baselines、skill_reference_injection 与 `Desktop 1303>1302`，均为既有；本轮引入的 `save_preset` 参数数、`PetVoiceMixin` 行数两条已清。
- 未跑默认 smoke 与 `--all --safe`；未在真实窗口目测分组下拉与模式对话框。
