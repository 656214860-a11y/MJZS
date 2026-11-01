# R2167 结果：模型管理底栏「保存并关闭」改为「关闭」，去掉保存（功能轮）

## 三问
- 轮次类型：功能轮（§3.1）。用户要求把模型管理窗右下角「保存并关闭」改为「关闭」，去掉其中的保存功能。无对应队列 ID。
- 测试和三个基线：在 worktree 分支 `codex/wip-R2167` 上运行（经 gui_hidden）。
  - `run_selftests.py -k model_manager ui_batch7 pet_models speech_settings button_consistency`：ALL TESTS PASSED。
  - 默认冒烟：8/8 通过。
  - `smoke_test.py --affected pet_models_ui`：8/9，失败项是 `test_skills` 的 2 条（`71 != 73`）。原因是主树 `程序\skills\` 里有未纳入 Git 的 SKILL 文件（如 `00全流程SKILL/AIGC创作全流程/*`），worktree 只有 11 份而主树有 51 份，注册数因此少 2；与本轮改动无关，本轮未处理。
  - `--architecture`、全量 `--all --safe` 本轮未运行（单个 UI 模块改动）；全量由提交后钩子后台补跑。
- `project_status.md` 欠账：没有减少，也没有新增（本分支不写状态页，合并轮登记）。

## 改动
- `pet_models_ui.py`：底栏最右按钮文字改为「关闭」，命令改为 `self.win.destroy`（与 Esc 一致），不再保存表单；删除只给它用的 `save_and_close`。按 `test_button_consistency` 规则补 `padx=(BUTTON_GAP, SPACING['none'])`。按钮仍是 `PrimaryButton`、仍贴最右。保存只走左侧「保存这条」。

## 测试（契约有意变更，同步测试）
- `tests/test_model_manager_actions.py`：按钮名改为「关闭」；断言不再有「保存并关闭」按钮；删除「保存失败留在窗口」「保存成功后关闭」两条（行为已按用户要求取消），新增 `test_close_with_filled_form_does_not_save`：表单填了模型 ID 点「关闭」也不调 `save_pool`、窗口关闭。
- `tests/test_ui_batch7_settings_models.py`：`test_model_manager_save_and_close_is_rightmost_primary` 改名为 `test_model_manager_close_is_rightmost_primary`，按钮名改为「关闭」；最小尺寸动作区测试按钮名同步。其余断言未动。
- 改实现前先跑：5 处 `AssertionError: 找不到可见按钮：关闭`；改后通过。

## 用户需做
重启应用后生效。填了表单未点「保存这条」就点「关闭」，改动不会保存。
