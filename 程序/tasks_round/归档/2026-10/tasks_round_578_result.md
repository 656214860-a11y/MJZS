# R578｜结构治理轮（子场景：执行）

## 轮次结论

- 本轮类型：结构治理轮（子场景：执行）；来源为 `design_tokens.md`、`ui_components.md`、`ui_tokens.py`、`ui_widgets.py`。
- `desktop.py` 只经 `pet_ui.attach()` 挂接三虎；实际“三虎对话框”构造入口是 `pet_cloud.py:Cloud.build()`，故以真实入口为准完成视觉 token 化。
- 测试已运行：专项 UI／契约回归 **4/4**、受影响 `pet_cloud` 门禁 **9/9**、默认冒烟 **8/8**、架构门禁 **101/101** 均通过。
- `project_status.md` 欠账未减少：本轮是视觉契约迁移，不对应 R547 的剩余治理条目；P0-3、P3-2 仍为既有阻塞项。

## 实际入口与范围

`Desktop.__init__()` 仅调用 `pet_ui.attach(self, ...)`，没有构造三虎对话控件。`pet_ui` 再委派 `pet_cloud.Cloud`，由 `Cloud.build()` 创建无边框 Canvas `Toplevel`、文字／输入行及专属关闭入口；这是本轮唯一应用模块改动。

该窗口不含普通 `ttk.Button`：关闭入口为了叠放在 Canvas 中使用 `tk.Label`，不能不改变布局地强行替换为 `PrimaryButton` 或 `SecondaryButton`。本轮改用相同 token 的正常／悬停前景与背景组合，保留控件类型、坐标、事件、尺寸、动画与窗口语义。

## 改动

| 文件 | 改动行数 | 内容 |
| --- | ---: | --- |
| `pet_cloud.py` | 约 31 | 云框、四类提示框、正文、输入提示、状态行、关闭入口的颜色／字体／输入提示偏移改为 `COLORS`、`FONTS`、`SPACING`；关闭悬停为浅主色底＋危险色文字。 |
| `tests/test_pet_ui.py` | 4 | 将过时的固定 13px 断言改为验证 `FONT` 直接复用 `FONTS['body']`，并保留 Tk 控件有效字体检查。 |
| `project_status.md` | 2 | 登记本轮并推进下一轮状态。 |

- 未修改 `ui_tokens.py` 或 `ui_widgets.py`，未新增 token／组件。
- 未改 `desktop.py`：它不是三虎对话框的构造者；避免了范围内的空改。

## 硬编码核查

目标类别为颜色、直接字体，以及 `padx`／`pady`／`padding` 数字。`pet_cloud.py` 的实际对话框构建和其专属视觉常量从 **约 16 → 0** 个直接命中。Canvas 几何、尾巴比例、窗口位置、动画时间和内容排版参数属于交互／布局结构，未改变。

## 验证

- AST：`pet_cloud.py` 解析通过。
- 目标类别静态扫描：**0** 个直接命中。
- `python -m unittest tests.test_pet_cloud_contract tests.test_pet_ui.CloudTests.test_the_record_text_uses_the_shared_font`：**4/4** 通过。
- `python smoke_test.py --affected pet_cloud`：**9/9** 通过；测试运行器提示本机无权写增量台账临时文件，不影响测试结论。
- `python smoke_test.py`：**8/8** 通过。
- `python smoke_test.py --architecture`：**101/101** 通过，无新增红点。

## 自审

**通过。** 本轮只改一个应用模块，以真实构造入口完成三虎对话框及其专属控件的视觉 token 化；未引入依赖、接口、功能或用户数据变更，所有指定门禁通过。

请重启应用后核对三虎云框的文字层级与关闭入口悬停可读性；本轮未伪造截图。
