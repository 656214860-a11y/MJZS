# R2106 结果：模型管理窗口腾出空间给模型列表（功能轮）

## 用户要求
1. 顶部说明文字上移一行；2. 模型列表尽量多显示几行；3. 调用方式为本地程序时「模型 ID」改名「程序名」（用户确认：CLI 和 Desktop 改名，API 保留「模型 ID」）；4. 下方表单输入框高度减半，把空间让给列表。

## 改动（`pet_models_ui.py`）
- `heading()`：标题与说明放进同一行 Frame，说明跟在标题右侧；只有模型管理窗口调用它。
- 新增 `CompactLineInput`（`LineInput` 子类，三种状态样式加 `Compact.` 前缀）与 `install_compact_form_styles()`：派生样式只把纵向 padding 设为 `SPACING['none']`，颜色、边框、状态映射沿用父样式；表单三个下拉框用 `Compact.Tokens.Combobox.TCombobox`。
- `text_row()` 把标签记进 `self.labels`；`refresh_connection_fields()` 按调用方式把模型那一栏标签设为 `MODEL_FIELD_LOCAL`（程序名）或 `MODEL_FIELD_API`（模型 ID）；`win._pet_labels` 供自检读取。
- 列表本身仍是 `TEXT_ROWS['4xl']` 行、占剩余高度；表单变矮后，950×780 窗口里列表可见约 15 行（原约 8 行）。

## 测试
- 新增 `tests/test_pet_ui.py::ModelPoolTests::test_manager_layout_leaves_room_for_the_model_list`：说明与标题同属一个父控件；表单输入框是 `CompactLineInput`，请求高度不超过常规 `LineInput` 的 0.7 倍；Desktop／CLI 显示「程序名」、API 显示「模型 ID」。未改已有断言。

## 验证（本轮运行）
- `run_selftests -k pet_ui pet_settings client_profiles model_probe button_consistency`：ALL TESTS PASSED。
- 默认 `smoke_test.py`：通过。
- 隐藏桌面截图（CLI、API 两种调用方式）目测：说明在标题右侧，列表约 15 行，表单行高约减半。
- `smoke_test.py --architecture`：3 项红均非本轮引入：`test_performance_history_is_declared_as_historical_only`（基准历史.json 未入库）、`test_round_number_continuous`（2105 != 2106）、`test_new_done_requirement_needs_a_test_anchor`（REQ-S01-68，来自 master 上 R2104 合入的 R2098）。

## 未验证
- 未在用户真机（高 DPI、实际字体）上目测。
