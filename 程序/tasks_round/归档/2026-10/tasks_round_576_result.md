# R576｜结构治理轮（子场景：执行）

## 轮次结论

- 本轮类型：结构治理轮（子场景：执行）；来源为 `design_tokens.md`、`ui_components.md`、`ui_tokens.py`、`ui_widgets.py`。
- 后期剪辑页面 `desktop.py:Desktop.editing()` 已迁移为既有 token／组件样式；该页面没有自建弹窗，未误改其它页面共用的“阶段配置”弹窗。
- 测试已运行：默认冒烟 **8/8**、架构门禁 **101/101**、受影响 `desktop` 门禁 **9/9**、后期剪辑禁用态 UI 回归 **1/1** 均通过。
- `project_status.md` 欠账未减少：本轮是视觉契约迁移，不对应 R547 的剩余治理条目；P0-3、P3-2 仍为既有阻塞项。

## 实际入口与范围

“后期剪辑”的直接页面构造入口是 `desktop.py:Desktop.editing()`。它不创建 `Toplevel`；页面只调用通用的 `skill_panel.stage_button()`，该通用入口同时为其它阶段服务，不属于本轮可迁移的专属弹窗。故应用代码仅改动 `desktop.py` 的该方法。

## 改动

| 文件 | 改动行数 | 内容 |
| --- | ---: | --- |
| `desktop.py` | 约 24 | 后期剪辑操作栏及阶段配置间距改用 `SPACING`；“手动制作剪辑”改用 `PrimaryButton`；自动粗剪、交接、启动剪映、打开目录、保存清单等按钮复用统一主／次按钮视觉样式。 |
| `project_status.md` | 2 | 登记本轮并推进下一轮状态。 |

- 未修改 `ui_tokens.py`、`ui_widgets.py`，未新增 token／组件。
- `edit_button()` 仅复用既有 `Desktop.button()` 的安全回调、宠物点击播报、禁用态和垂直布局，再覆盖为 `Tokens.Primary.TButton`／`Tokens.Secondary.TButton` 并替换本页间距；未改事件、行为或布局结构。

## 硬编码核查

目标类别为数字 `padx`／`pady`／`padding`、内联颜色、直接字体与直接普通 `ttk.Button`。`Desktop.editing()` 的目标视觉实例为 **约 9 → 0**。页面未直接定义颜色或字体；控件宽度、清单文本内容及业务状态判断属于结构／行为参数，未改变。

## 验证

- AST：`desktop.py` 解析通过。
- `Desktop.editing()` 目标类别静态扫描：**0** 个直接命中。
- `python -m unittest tests.test_ui_edges.UiEdgeTests.test_editing_actions_disabled_without_downloads`：**1/1** 通过。
- `python smoke_test.py --affected desktop`：**9/9** 通过；测试运行器提示本机无权写增量台账临时文件，不影响测试结论。
- `python smoke_test.py`：**8/8** 通过。
- `python smoke_test.py --architecture`：**101/101** 通过，无新增红点。

## 自审

**通过。** 本轮满足验收；应用代码只触及一个模块，未越过“后期剪辑”页面范围，未引入新依赖、接口、功能或用户数据变更；全部指定门禁通过。

请重启应用后核对后期剪辑页按钮的主／次层级及悬停可读性；本轮未伪造截图。
