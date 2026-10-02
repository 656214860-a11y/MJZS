# R569｜结构治理轮（子场景：执行）

## 来源、范围与约束

- 来源：`design_tokens.md`、`ui_components.md`、`ui_tokens.py`、`ui_widgets.py`。
- 范围仅为 `storyboard_files.py` 的 `show(desktop)`——即“初步分镜”页面；未触及同文件的 `show_final()` 定稿页或其他页面。
- 只复用了现有 token / 组件；未重建、追加或改变 `ui_tokens.py`、`ui_widgets.py`，未变更事件、业务逻辑、布局层级、用户数据或目录契约。

## 改动文件清单

| 文件 | 改动范围 | 视觉构造迁移量 |
| --- | --- | --- |
| `storyboard_files.py` | `show(desktop)` 及其两个导入行 | 14 个页面按钮实例、13 组间距字面量、1 个字体字面量、5 个内联颜色属性。 |
| `project_status.md` | 本轮状态摘要 | 登记 R569 完成，轮次推进至 R570。 |
| `tasks_round/tasks_round_569_result.md` | 本结果 | 新增本轮证据。 |

应用代码只改动 1 个模块，符合“最多改 3 个模块”。

## 迁移结果

| 项目 | 改前 | 改后 |
| --- | --- | --- |
| 间距 | `show()` 内散落 `0/2/4/6/8/12/16` 等 `padx`、`pady`、`padding` 字面量 | 全部改从 `SPACING["none"/"xs"/"sm"/"md"]` 获取。 |
| 按钮 | 工具栏、操作栏使用 `ttk.Button`，手动制作使用自绘 `tk.Button` | 主动作经 `PrimaryButton`，其余经 `SecondaryButton`；既有命令与 `stage_flow.follow()` 绑定未变。 |
| 卡片 | 初步分镜容器使用页面本地 `Box.TFrame` 与 `padding=6` | 改为既有 `Card`，内边距使用 `SPACING["sm"]`。 |
| 字体与颜色 | 手动制作按钮含 `Microsoft YaHei UI` 和 5 个本地颜色属性 | 由 `PrimaryButton` 的既有 token 样式提供，无页面内联颜色/字体。 |

- 硬编码视觉构造：**改前 14 个按钮实例 + 13 组间距字面量 + 1 个字体字面量 + 5 个颜色属性；改后为 0 个页面内联按钮/字体/颜色构造，间距全部引用 token。**
- 未新增 token 或组件；`FONTS` / `COLORS` 不适用于剩余页面构造，因此没有为凑迁移而添加无用引用。
- “阶段配置”按钮原本已由 `skill_panel.stage_button()` 产出 `SecondaryButton`；本轮仅将其与相邻按钮的页面间距收口为 `SPACING`，避免重复封装。

## 视觉核对

- 已尝试通过本机桌面会话截图核对，但当前自动化环境没有可操作的本机应用窗口（仅空白浏览器会话），不能得到可信的“改前／改后”截图。
- 因此没有伪造截图。组件语义核对以现有 `PrimaryButton` / `SecondaryButton` / `Card` 的统一样式和初步分镜布局回归为准；请重启应用后在“初步分镜”页面做最终人工视觉确认。

## 验证

- `python -m unittest tests.test_ui_edges.StoryboardRowLayoutTests`：1/1 通过。
- `python smoke_test.py --affected storyboard_files`：9/9 通过。
- `python smoke_test.py --architecture`：101/101 通过，无新增红点。
- `python smoke_test.py`：默认冒烟 8/8 通过。

## 结论

- 初步分镜页的页面级硬编码 UI 值已迁入既有 token / 组件，逻辑、事件、布局结构与用户数据均未改动。
- R182 架构债务状态不受本次设计系统迁移影响；既有阻塞项仍为 P0-3、P3-2。
