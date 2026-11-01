# R778｜UI 统一入口第一批第 3 项：输入框首迁｜功能轮

## 结论

已交付 `LineInput` 与 `TextArea` 统一输入组件，并只将“填写创作信息”表单的两个多行创意字段首迁至 `TextArea`。字段采集、统筹锁、提交及既有 `Text` 取值协议均未改变；其余历史输入框留待独立批次迁移。

## 开工三问

1. 本轮是功能轮：只做范围锁定允许的 UI 入口统一。
2. 已完成默认、受影响、架构、定向与完整安全全量验证。
3. UI 输入组件入口债务减少一个首迁页；未改动架构统一基数台账。

## 改动

- `ui_tokens.py`、`design_tokens.md`：登记输入控件的字体、前景、背景、边框、错误态和内边距 token。
- `ui_widgets.py`：新增 `LineInput`／`TextArea`，统一占位提示、只读态、错误态和输入样式；`TextArea` 保留 `tk.Text` 的 `get('1.0', 'end-1c')` 调用面。
- `desktop.py`：仅把创作信息弹窗的紧凑／详细创意字段迁至 `TextArea`，不改任何采集或保存逻辑。
- `ui_components.md`：补充两个组件的选用规则；新增首迁边界门禁，禁止该表单退回裸 `tk.Text`。
- 同步架构测试清单与 Tk display skip 台账。

首次定向测试捕获 `ttk.Style.configure()` 重复关键字这一确定性实现错误；已修正组件样式参数构造后复跑通过，未弱化断言。

## 验证

- `python smoke_test.py`：8/8。
- `python smoke_test.py --affected desktop ui_widgets`：9/9（子测试 27 条／0 红）。
- `python run_selftests.py -k ui_widgets_inputs ui_widgets_dialogs input_boundary skip_hygiene --safe`：10 条／0 红。
- `python smoke_test.py --architecture`：145/145。
- 本轮触及 Tk 输入控件与事件绑定，按 AGENTS.md §5 运行 `python run_selftests.py --all --safe`：3,536 条／0 红／878.9 秒。

完整安全基线已推进至 R778；本轮未触及用户项目数据、密钥或阶段语义。

## 自审

- 验收范围已完成：是。
- 新增依赖：无。
- 测试变更只新增组件／边界契约，既有断言未动。
- Git：已提交：否；commit hash：无。
- 建议提交信息：`feat(ui): add shared input widgets and migrate creation form`
