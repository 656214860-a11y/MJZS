# R2246 结果：模型管理表单排版——下拉框等宽、密钥名与协议并列、下拉框加高（功能轮）

## 三问
- 轮次类型：功能轮（UI 排版）。来源：用户截图与三条要求。
- 改动（只动 `pet_models_ui.py` 一个源文件）：
  1. 调用方式、Provider 两个下拉框改 `sticky='ew'`，第 1、3 列加 `uniform='fields'` 等分剩余宽度，两框等宽（总宽为奇数像素时差 1px，Tk 取整）。
  2. 「密钥名」输入框与「协议」下拉框并成一行（密钥名在左半边、协议在右半边，与 Provider、显示名同一竖线）；原来单独占一行的协议行去掉，`api_rows` 随之由 {2,3,4,5} 改为 {2,3,4}，本机程序模式照旧隐藏这几行。
  3. 紧凑下拉框上下内边距由 0 改为 `COMPACT_COMBOBOX_PAD_Y`（3px），框高约 19px → 25px（+32%）。
- 新增测试：`tests/test_ui_batch7_settings_models.py::test_manager_pairs_selects_on_equal_widths_and_taller_boxes`（等宽、协议与密钥名同行同列线、高度比零内边距高 25%～45%）。已有断言未动。
- 验证：`run_selftests.py -k batch7 pet_ui` 622 条全过；`smoke_test.py --affected pet_models_ui` 9 项全过。全量未手动运行，由提交后钩子后台补跑；真机截图未核对。

## 用户需做
重启应用后在「模型管理」页核对排版。
