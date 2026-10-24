# R2002 结果：下拉框“请选择”占位 + 总控下拉框“检查更新”（功能轮）

## 做了什么
- `ui_widgets.SelectBox`：只读下拉框取值为空时，框内显示灰色“请选择”（`ui_tokens.COMBOBOX_PLACEHOLDER`／`COMBOBOX_PLACEHOLDER_COLOR`）。只是显示层占位，取值仍是空串，已有默认值（分辨率、模式、模型等）一律不变，不影响生成与已存配置；点占位文字同样弹出列表；可编辑下拉框不加占位。未传 `textvariable` 的只读框自管一个变量。
- 阶段配置页总控下拉框新增动作项“检查更新”（`skill_panel_workflow.CHECK_UPDATE`）：选中后立即触发手动检查，下拉框还原为已保存的总控。
- `desktop_master_update.start_master_update_check(manual=True)`：手动检查时，已是最新、检查失败、仅提示型检出（带 `.git`）都会明确告知（状态栏＋提示框）；有新版本沿用确认→下载覆盖→指纹同步流程。自动检查行为不变（失败静默）。加了防重入标志。

## 范围裁定
用户确认“仅空值显示占位”：不把所有下拉框的既有默认值改成“请选择”（那会改变生成默认行为）。

## 三问
1. 改了什么：见上；改 ui_tokens／ui_widgets／skill_panel_workflow／desktop_master_update，新增 tests/test_select_placeholder.py，扩 test_master_skill_update、test_skill_panel_production_locks。
2. 验证：新增占位 5 条、手动检查 5 条、面板 2 条通过；相关定向 `-k skill_panel combobox ui_widgets select ui_theme` 全绿；默认 smoke 8/8；`--architecture` 406 项剩 4 条红，均为旧红（Desktop 类行数 1303>1302、round_number_continuous、skill_reference_injection、agents_md 性能历史），断言未动。
3. 未运行：`--all --safe`；真实界面目测占位位置与点击弹出（仅隐藏桌面几何测试）；真实联网手动检查。
- 未 push；合入 master 待用户指示。
