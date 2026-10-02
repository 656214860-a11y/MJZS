# R564｜结构治理轮（子场景：执行）

## 开工核对

- 来源：`design_tokens.md`、`ui_components.md`、`ui_tokens.py`、`ui_widgets.py`。
- 范围只限 `desktop.py` 的 `Desktop.script_structure()`；未修改其他页面、业务逻辑、事件绑定、布局结构或用户数据。
- 已复核现有 `COLORS`、`SPACING`、`FONTS`、`PrimaryButton`、`SecondaryButton`，本页所需项均已具备，未新增 token 或组件。

## 完成结果

- 容器、预览区、来源/操作/输出区和操作按钮的全部 `padding`、`padx`、`pady` 都改为 `SPACING` 引用。
- 结构稿编辑 `Text` 的背景、前景和字体改为 `COLORS["background_card"]`、`COLORS["text_primary"]` 和 `FONTS["caption"]`。
- “修改内容”“恢复删除”迁入 `SecondaryButton`；“保存修改”和高亮的“手动制作结构剧本”迁入 `PrimaryButton`。后者复用组件既有可读悬停态（浅主色背景、主色文字），不再依赖页面内的按钮样式。
- `script_structure()` 未构造 `Toplevel`；其中的右键 `tk.Menu` 没有显式颜色、字体、间距或 `ttk.Button`，因此不存在本范围内尚未 token 化的弹窗样式。阶段配置弹窗由范围外的 `skill_panel` 组装，本轮未触碰。

## 硬编码清点

统计口径为本页要求迁移的视觉声明（间距声明、颜色、字体、直接 `ttk.Button`），不把控件尺寸、`after` 时长和业务参数计入。

| 类型 | 改前 | 改后 |
| --- | ---: | ---: |
| 直接间距声明 | 13 | 0 |
| 内联颜色 | 2 | 0 |
| 内联字体元组 | 1 | 0 |
| 直接 `ttk.Button` | 4 | 0 |
| 合计 | 20 | 0 |

## 改动文件

| 文件 | 改动 | 变动行数 |
| --- | --- | ---: |
| `desktop.py` | 剧本结构页视觉 token 与主/次按钮组件迁移。 | 约 24 行 |
| `project_status.md` | 记录 R564 完成状态。 | 2 行 |
| `architecture.md` | 记录设计系统边界已覆盖剧本结构页。 | 1 行 |
| `tasks_round/tasks_round_564_result.md` | 本轮结果。 | 新增 |

未追加 `ui_tokens.py` 或 `ui_widgets.py`。

## 验证与审阅

- `D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py --affected desktop`：通过 9 项、失败 0 项；定向自检 7 条通过。自检增量台账因环境对 `维护记录` 临时文件的既有权限限制未写入，不影响测试结论。
- `D:\漫剧制作助手\运行环境\Python\python.exe -B -m unittest tests.test_stage_wiring.LayoutWiringTests.test_script_structure_page_shows_its_input_and_output_contract`：1/1 通过，真实构造剧本结构页并核对既有输入/输出预览契约。
- `D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py`：默认冒烟 8/8 通过。
- `D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py --architecture`：98/98 通过，无新增红点。
- Reviewer 静态复核：目标方法不再包含数值 `padding`／`padx`／`pady`、内联十六进制颜色、内联字体元组或直接 `ttk.Button`；所有页面级视觉取值均经既有 token/组件入口，控件命令、状态和排布未改变。
