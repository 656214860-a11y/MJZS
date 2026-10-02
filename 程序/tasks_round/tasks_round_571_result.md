# R571｜结构治理轮（子场景：执行）

## 来源与范围

- 来源：`design_tokens.md`、`ui_components.md`、`ui_tokens.py`、`ui_widgets.py`。
- 任务对象为“分镜定稿”及其直接页面构造。核查后确认 `desktop.py:final_storyboard()` 只委派 `storyboard_files.show_final()`，没有自身的视觉控件；实际入口为 `storyboard_files.py:show_final()`。
- `show_final()` 未创建 `Toplevel`，因此没有同入口的弹窗页可迁移；未扩展至其他独立页面或弹窗。

## 改动

| 文件 | 改动行数 | 内容 |
| --- | ---: | --- |
| `storyboard_files.py` | 约 31 行调整 | 定稿页工具栏、状态操作、卡片、镜头导航、预览文本区和提示区的颜色、字体、间距与按钮全部复用既有 token/组件。 |
| `tests/test_final_viewer.py` | 2 行调整 | 将既有“主动作高亮”断言从历史样式名同步为 `Tokens.Primary.TButton`；断言仍验证高亮语义，未弱化。 |
| `project_status.md` | 2 行调整 | 登记本轮完成并推进轮次。 |

- `Card` 替代两个无标题 `LabelFrame`；间距取 `SPACING`。
- `PrimaryButton` 用于“手动同步资产”和当前选中的镜头；`SecondaryButton` 用于重试、补资产、刷新、目录和未选中镜头。选中／悬停／禁用均由现有 token 组件样式控制。
- `Treeview` 完成态、导航画布、预览文本区的背景、前景及字体改用 `COLORS`／`FONTS`；未新增或变更 token/组件。
- 没有修改控制器、保存、加载、后台读取、导航选择、定时器、事件绑定、目录或用户数据逻辑。

## 硬编码核查

`show_final()` 内本轮约定的直接 UI 常量（数字 `padx`/`pady`/`padding`、内联颜色、直接字体、直接创建的 `ttk.Button`）为 **30 → 0**。保留的列宽、文本换行宽度、画布高度、滚动条和 `insertwidth` 属于控件内容/结构参数，不属于本轮设计 token 范围，布局结构保持不变。

## 验证

- AST 解析：`storyboard_files.py` 通过。
- `python smoke_test.py --affected storyboard_files`：40/40 通过（`test_final_viewer` 13 条、控制器与缓存合计 40 条）。
- `python smoke_test.py --architecture`：101/101 通过。
- `python smoke_test.py`：8/8 通过。
- 当前自动化会话没有可操作的本机应用窗口，无法生成真实 UI 截图；未伪造截图。需重启应用后人工确认定稿页主动作、镜头选中态及窗口缩放视觉。

## 约束复核

- 实际应用模块只改 1 个，未超过“每次最多改 3 个模块”。
- 未改分层、数据契约或功能；架构门禁无新增红点。
