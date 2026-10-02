# R572｜结构治理轮（子场景：执行）

## 来源与范围

- 来源：`design_tokens.md`、`ui_components.md`、`ui_tokens.py`、`ui_widgets.py`。
- 首帧管理的实际页面构造入口为 `desktop.py:Desktop.storyboard()`；页面路由为 `PAGE['keyframe']`。
- 此入口不创建 `Toplevel`：首帧提示词由 `prompt_window.show()` 独立构造，文件选择／确认由 Tk 原生对话框提供，首帧制作窗由 `keyframe_comfy.show()` 独立构造。遵循“只改 desktop.py 首帧管理构造”的范围，本轮未越界迁移它们。

## 改动

| 文件 | 改动行数 | 内容 |
| --- | ---: | --- |
| `desktop.py` | 约 55 行调整 | 首帧管理的页内间距、完成态／首帧行颜色和按钮样式改为复用既有 token 组件样式。 |
| `tests/test_ui_edges.py` | 1 行调整 | 既有首帧页“手动制作首帧”为主动作的样式断言同步到 token 样式名。 |
| `project_status.md` | 2 行调整 | 登记本轮完成并推进轮次。 |

- `选中镜头`行、动作行、阶段配置入口和页内按钮最终生效的间距均使用 `SPACING`；没有遗留直接的 `padx`／`pady` 数字。
- 完成态与无首帧行背景、完成文字颜色均使用 `COLORS`；该入口没有直接的 `font=(...)` 设置。
- “手动制作首帧”使用 `Tokens.Primary.TButton`；选中镜头行的六个操作统一为 `Tokens.Secondary.TButton`。保留 `Desktop.button()` 的共享安全回调与事件包装，仅在本页覆盖其视觉样式和最终间距。
- “阶段配置”已有 `skill_panel.stage_button()` 返回 `SecondaryButton`，本轮只将其页面间距改为 `SPACING`。
- 未新增或修改 `ui_tokens.py`、`ui_widgets.py`，没有触及首帧导入、删除、恢复、制作、文件路径、后台任务或用户数据逻辑。

## 硬编码核查

`Desktop.storyboard()` 中本轮约定的直接 UI 常量（数字 `padx`／`pady`、内联颜色、直接字体、该入口创建并最终配置的 `ttk.Button`）为 **10 → 0**。列宽、Treeview 行高、缩略图尺寸和文本内容宽度是控件内容／结构参数，不属于设计 token 的替换范围，保持原样。

## 验证

- AST 解析：`desktop.py`、`tests/test_ui_edges.py` 通过。
- 首帧页精确布局回归：`tests.test_ui_edges.UiEdgeTests.test_frame_page_batch_row_moved_below_table`，1/1 通过。
- `python smoke_test.py --affected desktop`：9/9 通过。
- `python smoke_test.py --architecture`：101/101 通过。
- `python smoke_test.py`：8/8 通过。
- 当前自动化会话没有可操作的本机应用窗口，无法生成真实 UI 截图；未伪造截图。重启应用后可人工确认首帧页主动作、次按钮悬停与缩窗换行视觉。

## 约束复核

- 实际应用模块只改 `desktop.py` 1 个；未超过“每次最多改 3 个模块”。
- 本次改测试因 UI 样式契约变更，断言未动。
- 未改分层、数据契约或功能；架构门禁无新增红点。
