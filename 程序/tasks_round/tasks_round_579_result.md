# R579｜结构治理轮（子场景：执行）

## 轮次结论

- 本轮类型：结构治理轮（子场景：执行）；来源为 `design_tokens.md`、`ui_components.md`、`ui_tokens.py`、`ui_widgets.py`。
- 实际“设置窗口”入口为 `pet_settings_ui.open_hub()`，模型配置／模型管理专属子窗入口为 `pet_models_ui`；`desktop.py` 仅挂接三虎，不是 UI 构造者，因此没有空改。
- 设置专项及受影响门禁 **52/52**、默认冒烟 **8/8**、架构门禁 **101/101** 全部通过。
- 本轮不对应 R547 的债务条目，欠账数量不变；P0-3、P3-2 仍为既有阻塞项。

## 范围与改动

| 文件 | 改动行数 | 内容 |
| --- | ---: | --- |
| `pet_settings_ui.py` | 约 75 | 设置主窗、六个分页、Token 页及开发信息页的标题／填充／字段与操作栏间距改复用 `FONTS`／`SPACING`；所有操作和页签改用 `PrimaryButton`／`SecondaryButton`，页签选中态对应主按钮样式。 |
| `pet_models_ui.py` | 约 60 | 模型配置、模型管理、密钥操作栏和表单紧凑样式改复用 `FONTS`／`SPACING` 与主／次按钮组件。 |
| `tests/test_pet_settings.py` | 3 | 将旧 `Compact/Selected.Compact` 样式断言改为 token 组件样式名，保留“同排”“唯一选中”“独立窗存在”语义。 |
| `smoke_test.py` | 4 | 为两条真实设置入口登记同一 `pet_settings` 定向回归映射。 |
| `project_status.md` | 2 | 登记 R579 并推进下一轮。 |

未修改 `desktop.py`、`pet_ui.py`、`ui_tokens.py` 或 `ui_widgets.py`；未新增 token／组件。没有硬编码颜色可迁移；该范围内直接字体和 `padx`／`pady`／`padding` 数字已迁移为 token。几何尺寸、文本换行宽度、输入框宽度与 Treeview 列宽属于既有布局结构，未变更。

## 硬编码与截图核查

- 目标类别扫描：改前在两个入口中发现直接字体、`padx`／`pady`／`padding` 与旧按钮样式共 **约 100** 处；改后直接字体、直接颜色、数值间距与 `ttk.Button(...)` 命中均为 **0**，全部由 token 或共享按钮组件承接。
- 未生成运行中截图：本轮没有启动真实主窗口，以免对用户当前设置、模型池或宠物运行状态造成干扰；专项 Tk 回归覆盖了两个窗口的控件创建、页签切换、按钮样式与模型管理交互。

## 验证

- `python -m unittest tests.test_pet_settings`：**52/52** 通过。测试过程出现一条 Tk 过期 `after` 回调提示，以及增量台账临时文件无写权限；均不影响该专项的成功结果。
- `python smoke_test.py --affected pet_settings_ui pet_models_ui`：两条真实入口均映射到 `test_pet_settings.py`，**52/52** 通过（1 个测试文件／7 路工作单元／0 个文件有红）。
- `python smoke_test.py`：**8/8** 通过。
- `python smoke_test.py --architecture`：**101/101** 通过，无新增红点。

## 自审

**通过。** 本轮仅迁移两个真实设置窗口构造模块的视觉常量与按钮组件，没有修改任何配置、模型、密钥、宠物或用户数据逻辑；测试断言同步到设计系统，避免旧样式名反向固化。
