# R559｜修复轮

## 问题与结果

剧本准备页的“发送”已使用 `PrimaryButton`，但其悬停态只切换为浅主色背景，未将白色文字同步切回深色，导致按钮标签在鼠标移入后近乎不可见。“阶段配置”仍使用旧的暖色 `StageConfig.TButton`，未接入设计系统组件；阶段配置弹窗也残留旧字体、间距、颜色和通用按钮写法。

现已统一为设计系统写法：

- `PrimaryButton`：默认主色底/白字；悬停为 `primary_subtle` 底/`primary` 字；禁用为边框色底/弱文字。
- `SecondaryButton`：默认卡片底/主文字；悬停为 `primary_subtle` 底/`primary` 字；禁用为边框色底/弱文字。
- 全阶段“阶段配置”入口改由 `SecondaryButton` 创建，与“发送”形成主次操作层级；保留 16 字符宽度与原有命令、模型标签和弹窗行为。
- 阶段配置主弹窗、HOLLMWOOD 规则弹窗、预设共享弹窗的标题、操作按钮、文本区、字体和间距均改接 `COLORS`、`FONTS`、`SPACING` 与主/次按钮组件。

未改发送、阶段配置保存、模型选择、SKILL 选择、弹窗打开或用户项目数据逻辑。

## 改动文件

| 文件 | 变更 |
| --- | --- |
| `ui_widgets.py` | 补齐主/次按钮的悬停与禁用前景色映射，保证浅色背景上的文字可读。 |
| `skill_panel.py` | 阶段配置入口和关联弹窗全面复用 `PrimaryButton` / `SecondaryButton` 与视觉 token。 |
| `ui_components.md` | 明确 `Toplevel` 弹窗与普通页面同样必须遵守 token/组件及可读悬停规则。 |
| `tests/test_ui_theme.py` | 新增主/次按钮悬停、禁用颜色 token 回归。 |
| `tests/test_ui_edges.py` | 阶段配置入口以语义标记定位，并断言其使用次按钮组件，不再依赖废弃样式名。 |
| `project_status.md` | 登记 R559 完成状态。 |

## 验证

- `python -B -c "…TokenButtonStateTests…"`：2/2 通过（主/次按钮悬停及禁用 token 回归）。
- `python -B -c "…StageConfigEntryTests…"`：1/1 通过（12 阶段入口与对应弹窗）。
- `python -B smoke_test.py --affected desktop`：7/7 通过。
- `python -B smoke_test.py`：默认冒烟 8/8 通过。
- `python -B smoke_test.py --architecture`：95/95 通过。

## 后续约束

后续新增或改造页面（包含 `Toplevel`）必须直接复用 `ui_widgets` 组件和 `ui_tokens`，不得以通用 ttk 样式或内联颜色、间距、字体另起一套视觉状态。
