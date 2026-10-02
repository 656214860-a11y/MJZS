# R570｜结构治理轮（子场景：执行）

## 来源、范围与约束

- 来源：`design_tokens.md`、`ui_components.md`、`ui_tokens.py`、`ui_widgets.py`。
- 范围仅为资产管理的页面构造：`desktop.py` 中 `asset_page()` / `assets()` 及其名称、外观详情弹窗；`asset_batch.py` 中 `show()` 批量资产制作弹窗。
- `asset_detail.py` 是独立的资产详情子路由，不是由上述页面函数直接构建的弹窗，未在本轮扩范围修改。
- 只复用既有 token/组件；没有新增或改动 `ui_tokens.py`、`ui_widgets.py`，没有改变资产流程、事件、布局层级、用户数据或目录契约。

## 改动文件清单

| 文件 | 改动范围 | 迁移内容 |
| --- | --- | --- |
| `desktop.py` | `asset_page()` / `assets()` 和 `detail()` 弹窗 | 操作栏、分类选中态、表格完成态、文字详情弹窗的间距、颜色与按钮。 |
| `asset_batch.py` | `show()` | 滚动表单、模型配置区与底部操作栏的背景、标题字体、间距与按钮。 |
| `project_status.md` | 状态台账 | 登记 R570 并推进至 R571。 |
| `tasks_round/tasks_round_570_result.md` | 本结果 | 新增本轮证据。 |

应用代码改动 2 个模块，符合“最多改 3 个模块”。

## 迁移结果

| 项目 | 改前 | 改后 |
| --- | --- | --- |
| 间距 | 页面/弹窗内散落 `2/3/4/5/6/8/10/12/14` 等 `padx`、`pady`、`padding` 字面量 | 全部从 `SPACING` 取值。 |
| 颜色 | 批量弹窗背景、资产完成行和缩略图背景使用本地 hex | 分别使用 `COLORS["background_primary"]`、`COLORS["border_default"]`、`COLORS["success"]`、`COLORS["background_card"]`。 |
| 字体 | 批量弹窗标题使用本地 `Microsoft YaHei UI` 字面量 | 改用 `FONTS["title"]`。 |
| 按钮 | 页面与弹窗直接创建 `ttk.Button`，并依赖 `Asset` / `Compact` / `Primary` 等遗留样式 | 主操作经 `PrimaryButton`，其他操作经 `SecondaryButton`；分类已选中为主按钮、未选中为次按钮。 |

- 本轮构造范围内，页面按钮、详情弹窗按钮和批量弹窗按钮均已迁入共享组件；“阶段配置”仍复用既有 `skill_panel.stage_button()`，仅把相邻间距迁为 token。
- 没有新增 token/组件。`Card` 不适用于本页既有 Treeview/LabelFrame 结构，未为了形式一致而改变布局。
- 静态复核已确认上述范围没有残留直接 `ttk.Button` / `tk.Button` 创建、内联 hex、字体字面量或数值 `padx` / `pady` / `padding`。

## 视觉核对

- 当前自动化环境没有可操作的本机应用窗口，无法生成可信的运行时改前/改后截图；未伪造截图。
- 本轮保留原控件层级、命令和事件绑定；请重启应用后人工核对“资产管理”和“资产图片制作”弹窗的主/次按钮悬停可读性与窄窗口换行表现。

## 验证

- 无缓存写入的 AST 解析：`desktop.py`、`asset_batch.py` 均通过。
- `python smoke_test.py --affected asset_batch`：9/9 通过。
- `python smoke_test.py --affected desktop`：9/9 通过。
- `python smoke_test.py --architecture`：101/101 通过，无新增红点。
- `python smoke_test.py`：默认冒烟 8/8 通过。

## 结论

- 资产管理主页面、其直接文字详情弹窗及批量制作弹窗的页面级视觉常量已收口至既有设计系统；未改变资产业务行为。
- R182 架构债务状态不受本次 UI 迁移影响；既有阻塞项仍为 P0-3、P3-2。
