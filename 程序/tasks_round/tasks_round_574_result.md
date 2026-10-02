# R574｜结构治理轮（子场景：执行）

## 轮次结论

- 本轮类型：结构治理轮（子场景：执行）；来源为既有 UI 设计契约。
- 测试：默认冒烟 **8/8**、架构门禁 **101/101**、视频工作台 UI 精确回归 **64/64** 通过。
- R182 结构债务：未减少；本轮是视觉契约迁移，不对应 `tasks_round_547_result.md` 的剩余治理条目。P0-3、P3-2 仍为既有阻塞项。

## 实际入口与范围

`desktop.py:Desktop.videos()` 仅负责路由与工作台宿主；实际视频工作台由 `app.py:App` 创建，云端／本地设置弹窗分别由 `cloud_video.py:settings()` 与 `local_video.py:settings_window()` 创建。因此在“不改流程且每次最多三个应用模块”的约束下，只迁移这三个实际 UI 构造入口；没有改 `desktop.py` 路由、视频提交／轮询、设置持久化或用户数据。

## 改动

| 文件 | 改动行数 | 内容 |
| --- | ---: | --- |
| `app.py` | 约 75 | 视频工作台的间距、颜色、字体、输入区、资产选择窗与本地设置窗复用既有 token／组件。 |
| `cloud_video.py` | 约 35 | 云端设置弹窗的布局与动作按钮复用 token／组件。 |
| `local_video.py` | 约 25 | 本地设置弹窗的布局与动作按钮复用 token／组件。 |
| `tests/test_video_ui.py` | 2 | 主按钮风格断言迁移为既有 `Tokens.Primary.TButton` 契约；琥珀色 MCP 优化断言保留。 |
| `project_status.md` | 2 | 登记本轮并推进状态。 |

- 普通主操作使用 `PrimaryButton`，辅助操作使用 `SecondaryButton`；悬停时由既有共享组件提供浅主色背景＋主色文字，禁用态使用弱文字。
- `MCP 优化`保留既有 `Highlight.TButton`：它代表额外调用成本的警示层级，不被错误降级为普通主按钮。
- 未新增或修改 `ui_tokens.py`／`ui_widgets.py`。同一模块中与视频无关的“编剧任务书”弹窗未越界迁移。

## 硬编码核查

对上述三个实际视频入口，目标类别（数字 `padx`／`pady`／`padding`、内联颜色、直接字体、直接普通 `ttk.Button`）静态命中为 **约 48 → 0**。窗口尺寸、控件宽高、表格列宽和进度数值属于结构参数，未改变。

## 验证

- AST 解析：`app.py`、`cloud_video.py`、`local_video.py` 通过。
- `python -m unittest tests.test_cloud_video`：11/11 通过。
- `python -m unittest tests.test_video_ui`：64/64 通过。
- `python smoke_test.py --affected video`：执行了视频定向门禁；测试运行器在本机受限环境无法写入其增量台账，须以同一门禁的精确单测结果为准。
- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --architecture`：101/101 通过，无新增红点。

## 约束复核

- 应用模块仅改动 `app.py`、`cloud_video.py`、`local_video.py` 三个，未超过上限。
- 未改分层、对外接口、生成流程、事件、目录或用户数据。
- 本轮无法安全重启用户正在使用的桌面应用，未伪造截图；请重启应用后核对视频工作台与两类设置弹窗的主／次按钮悬停效果。
