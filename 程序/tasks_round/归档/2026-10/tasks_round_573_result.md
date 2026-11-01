# R573｜结构治理轮（子场景：执行）

## 来源与范围

- 来源：`design_tokens.md`、`ui_components.md`、`ui_tokens.py`、`ui_widgets.py`。
- `desktop.py:Desktop.previs()` 不构造任何白模控件，只委派 `ui_plugin_registry.module('local_previs').show(self)`。白模预演实际页面入口是 `local_previs.py:show()`；它唯一直接创建的弹窗为线上白模说明窗口。
- 因此遵循“只改白模预演”的意图，仅迁移 `local_previs.py` 的主页面和该直接弹窗；没有改动 `desktop.py` 的路由委派、其他页面、服务或数据逻辑。

## 改动

| 文件 | 改动行数 | 内容 |
| --- | ---: | --- |
| `local_previs.py` | 约 60 行调整 | 白模主页面与线上白模弹窗复用既有设计 token 和组件。 |
| `project_status.md` | 2 行调整 | 登记本轮完成并推进轮次。 |

- 线上白模弹窗以 `Card` 承载；“打开线上白模并复制说明”为 `PrimaryButton`，导入与关闭为 `SecondaryButton`。
- 主页面的“手动制作白模”使用 `PrimaryButton`，停止、打开线上白模、播放视频、打开工程调整、白模目录、制作记录、进入视频生成及阶段配置入口使用既有 `SecondaryButton` 视觉契约。
- 页内 `padx`／`pady` 和卡片内边距复用 `SPACING`；完成态边框与文字颜色复用 `COLORS`。该模块没有直接 `font=(...)` 设置，因此无需引入 `FONTS`。
- 未新增或修改 `ui_tokens.py`、`ui_widgets.py`；没有改预演生成、导入、停止、播放、目录、后台任务、事件或用户数据。

## 硬编码核查

对白模预演实际入口的静态扫描中，约定范围内的直接 UI 常量源代码命中行数为 **21 → 0**：数字 `padx`／`pady`、卡片 `padding`、内联颜色、直接字体和直接 `ttk.Button` 创建均已消除。表格列宽、窗口尺寸、进度数值及文本内容宽度属于结构／内容参数，保持原样。

## 验证

- AST 解析：`local_previs.py` 通过。
- `python smoke_test.py --affected local_previs`：筛选器当前没有 `local_previs` 映射，结果为 0 条并按工具规则失败；未修改映射以免超出本轮范围。
- `python smoke_test.py --affected previs`：白模预演阶段既有受影响别名，78/78 通过。
- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --architecture`：101/101 通过。
- 当前自动化会话没有可操作的本机应用窗口，无法生成真实 UI 截图；未伪造截图。重启应用后可人工核对白模页主／次按钮及线上白模弹窗的悬停效果。

## 约束复核

- 实际应用模块仅改 `local_previs.py` 1 个，未超过“每次最多改 3 个模块”。
- 没有改分层、契约、功能或用户数据；架构门禁无新增红点。
