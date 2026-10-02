# R554｜结构治理轮（子场景：执行）｜剧本准备页 Token 化

## 完成结论

- 已按 `design_tokens.md` 与 `ui_components.md` 将 `Desktop.writing()` 中全部直接写入的 `padx`/`pady`、Text 颜色与字体替换为 `SPACING`、`COLORS`、`FONTS`。
- 发送改用 `PrimaryButton`；附件、中断、刷新、下载及剧本文件操作改用 `SecondaryButton`。布局层级、回调、事件绑定、数据读写与页面逻辑均保持不变。
- 设计文档此前未代码化；本轮新增只读 token 模块与 Tk 组件入口，并登记到既有 L1/L4 分层。

## 改动文件与行数

| 文件 | 改动 | 行数 |
| --- | --- | --- |
| `desktop.py` | 仅 `writing()` 页面：以 token 替换间距、颜色、字体，并换用主/次按钮。 | 约 40 行替换 |
| `ui_tokens.py` | 新增颜色、间距（含零间距）、圆角、字体 token。 | 25 行新增 |
| `ui_widgets.py` | 新增 `PrimaryButton`、`SecondaryButton`、`Card` 的唯一 Tk 组件入口。 | 38 行新增 |
| `tests/architecture/_layers.py`、`architecture.md`、`PROJECT_MAP.md` | 登记 L1 token 与 L4 组件边界。 | 约 8 行修改 |
| `project_status.md` | 登记本轮结果。 | 2 行修改 |

## Token 覆盖与边界

- `writing()` 范围内扫描结果：无直接数字 `padx=` / `pady=`，无内联 Text `bg`/`fg`/选择色 hex，无 `font=(...)`。
- `0` 间距使用 `SPACING['none']`；原先的 2/3/6/10px 间距归一为设计系统规定的 4/8/12px 档位，未改变控件排列、pack/grid 次序或伸缩规则。
- 仅影响剧本准备页；未改其他页面、模型调用、附件、聊天记录、文件表数据或用户项目文件。

## 截图说明

- 改前：本轮开始前没有同一环境、同一窗口尺寸的可复现截图，不能伪造对比图。
- 改后：已尝试启动本地应用并通过可用 UI 自动化表面获取截图；该表面未暴露原生 Tk 窗口，故无法取得可信截图。代码级扫描和桌面定向回归已覆盖本轮变更。

## 验证

| 检查 | 结果 |
| --- | --- |
| `python smoke_test.py --affected desktop` | 7/7 通过 |
| `python smoke_test.py` | 8/8 通过 |
| `python smoke_test.py --architecture` | 95/95 通过，无新增架构红点 |

## 自检

- 生产模块改动为 3 个：`desktop.py`、`ui_tokens.py`、`ui_widgets.py`。
- 未改 UI 以外的生产逻辑；所有 `writing()` 事件、命令与布局结构保留。
