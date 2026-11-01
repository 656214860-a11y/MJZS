# R2149 结果：弹窗首次定位不再裁内容（缺陷轮）

## 三问
- 轮次类型：缺陷轮（§3）。用户报「语音识别设置」底部按钮被裁、「已绑定设备」右侧「解绑」被裁。
- 测试和三个基线：在 worktree 分支 `claude/dialog-fit` 上运行（经 gui_hidden）。
  - `run_selftests.py -k ui_theme model_manager speech_api account dialog popup pet_models pet_settings skill_panel ui_widgets window placement button_consistency asset_reference`：307 条全过。
  - 默认冒烟：通过。
  - `--architecture`：411 项全过（函数行数上限：新逻辑抽成 `ui_theme._fit_dialog`）。
  - 全量 `--all --safe` 本轮未手动运行，由提交后钩子后台补跑。
  - 真机未手动核对，只在隐藏桌面验证。
- `project_status.md` 欠账：没有减少，也没有新增（本分支不写状态页，合并轮登记）。

## 根因
`ui_theme.install_window_placement` 首次摆放弹窗时把尺寸压到 `min(业务页写死尺寸, 主窗口尺寸)` 并写死 `geometry('WxH+X+Y')`：
- 写死的尺寸在高 DPI 或主窗口偏小时装不下表单（语音识别设置：写死 560x420）。
- 写死后窗口不再随内容变化；联网读回的设备列表晚于定位才加载，撑不开窗口（已绑定设备）。

## 改动
- `ui_theme.py`：新增 `_fit_dialog`。首次尺寸不小于内容请求尺寸（只有工作区放不下时让步）；尺寸恰为自然尺寸时只摆位置（`geometry('')` 后 `+x+y`），保留调用方声明的 minsize，之后加载的内容仍能撑大窗口；写死尺寸的弹窗照旧可由用户缩小。
- `speech_settings_ui.py`：去掉写死的 `SPEECH_GEOMETRY`，只声明最小宽度，高度随内容。
- `ui_components.md`：更新弹窗定位规则，新弹窗优先声明最小宽度而非写死高度。

## 测试
- 新增 `tests/test_ui_theme.py::DialogFitsContentTests` 三条（写死尺寸撑到内容、内容比主窗口宽不被裁、定位后加载的内容仍能撑宽）；修复前三条均失败，修复后通过。
- `tests/test_model_manager_actions.py` 语音设置用例追加「窗口不小于请求尺寸」两条断言。
- 已有测试断言未动（含 `test_ui_widgets_dialogs` 的「首次尺寸不超主窗口、之后可缩小」契约）。

## 用户需做
重启应用后生效。
