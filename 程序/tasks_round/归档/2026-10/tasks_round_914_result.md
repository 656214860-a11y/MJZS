# R914 UI 统一入口：资产详情语义按钮

- 资产详情、资产清单、正典板、状态变体与原始 JSON 折叠区的操作按钮，已由裸 `ttk.Button` 统一接入 `PrimaryButton` 或 `SecondaryButton`。
- “采用推荐”“重新生成”保留主操作；返回、编辑、复制、绑定、删除与展开等保留为次级操作，既有回调不变。
- 按钮边界测试新增 `asset_detail.py`，防止回退为裸 `ttk.Button`。

验证：

- `python -m py_compile asset_detail.py` 通过。
- `python -m unittest tests.architecture.test_button_boundary`：16 条通过。
- `python smoke_test.py`：8 项通过、0 失败。
- `tests/test_asset_detail.py` 在状态变体 GUI 用例处超过 30 秒运行窗口，没有失败堆栈；本轮未将其视为通过，留待后续单独诊断。

全站按钮覆盖和路线图其它入口仍未完成。
