# R575｜结构治理轮（子场景：执行）

## 轮次结论

- 本轮类型：结构治理轮（子场景：执行）；来源为既有 UI 设计契约。
- “配音与字幕”主页面及其唯一自建的 TTS 设置弹窗已迁移至既有 token／组件体系；未新增 token 或组件。
- 默认冒烟 **8/8**、架构门禁 **101/101**、`--affected desktop` **9/9**、TTS 逻辑回归 **38/38** 通过。
- R182 结构债务未减少：本轮为视觉契约迁移，不对应 `tasks_round_547_result.md` 的剩余治理项；P0-3、P3-2 仍为既有阻塞项。

## 实际入口与范围

`desktop.py:Desktop.audio()` 是“配音与字幕”主页面的直接构造入口；其“配音设置”操作唯一打开 `tts_settings.py:show()` 的自建 `Toplevel`。因此仅迁移这两个实际入口。Tk 原生文件选择器、消息框以及既有音频生成／字幕导出／目录操作不属于自定义页面视觉构造，未越界改动。

## 改动

| 文件 | 改动行数 | 内容 |
| --- | ---: | --- |
| `desktop.py` | 约 32 | `Desktop.audio()` 的操作行间距改用 `SPACING`；在不改变既有安全回调、按钮状态和 FlowBar 换行行为的前提下，将该页主／次操作映射到既有 `Tokens.Primary.TButton`／`Tokens.Secondary.TButton` 样式。 |
| `tts_settings.py` | 约 27 | TTS 设置弹窗的容器、标签、输入项和操作行间距改用 `SPACING`；保存使用 `PrimaryButton`，检查／测试／打开控制台／取消使用 `SecondaryButton`。 |
| `project_status.md` | 2 | 登记本轮并推进下一轮状态。 |

- 未修改 `ui_tokens.py`、`ui_widgets.py`，也没有新增视觉 token／组件。
- 主页面通过既有 `Desktop.button()` 保持原有回调、禁用状态与响应式 FlowBar 行为，再以组件定义的 token 样式覆盖视觉层；没有改动按钮事件或布局结构。

## 硬编码核查

目标类别为数字 `padx`／`pady`／`padding`、内联颜色、直接字体和直接普通 `ttk.Button`。

| 实际 UI 入口 | 改前 | 改后 |
| --- | ---: | ---: |
| `Desktop.audio()` | 约 17 | 0 |
| `tts_settings.show()` | 约 20 | 0 |

窗口尺寸、控件宽度、进度数值和业务判断均属于结构／行为参数，不在本轮视觉 token 迁移范围内。

## 验证

- AST：`desktop.py`、`tts_settings.py` 解析通过。
- 目标类别静态扫描：两个入口均为 **0** 个直接命中。
- `python -m unittest tests.test_tts`：**38/38** 通过。
- `python smoke_test.py --affected desktop`：**9/9** 通过；测试运行器仅提示本机无权写其增量台账临时文件，不影响测试结论。
- `python smoke_test.py`：**8/8** 通过。
- `python smoke_test.py --architecture`：**101/101** 通过，无新增红点。

## 约束复核

- 应用代码仅改动 `desktop.py`、`tts_settings.py` 两个模块，未超过三模块上限。
- 未改分层、对外接口、配音／字幕逻辑、事件、目录、持久化或用户数据。
- 未自动重启正在运行的应用，也未伪造截图；请重启应用后核对配音页与 TTS 设置弹窗的主／次按钮悬停效果。
