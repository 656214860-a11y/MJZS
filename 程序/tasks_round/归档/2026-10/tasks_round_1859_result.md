# R1859 结果（修复轮）：R1857 变基到 master 后的整合修正

## 改动
- 大模块拆分（Mixin 组合，R1621 模式）：`skill_panel_workflow.py`（总控套用 6 个方法＋对话框留白常量），skill_panel 再导出常量，外部导入路径不变；已登记 `_layers.py`，Panel 类复杂度登记下调到 972。pet_cloud 与构思气泡的拆分 master 已由 R1804／R1806 完成，变基时放弃本轮的重复拆分。
- 令牌化：desktop／asset_reference_images／native_assets／qwen_setup 魔法间距改走 SPACING；三虎调色板 40 色收进 `ui_tokens.PET_PALETTE`，pet_ui／pet_ui_support 不再内联 hex。token_boundary 基线按实测下调（棘轮只降不升）。
- 项目选择弹窗空态提示（EmptyState）。
- 齿轮按钮悬停提示（Tooltip）。
- 减少动态：`ui_motion.reduce_motion()`（环境变量 `DRAMA_REDUCE_MOTION` 优先，否则读 Windows 客户区动画设置），悬停渐变与云朵淡入淡出遵守；自检入口固定为 0 保持测试确定。
- 门禁同步：覆盖率基线重测 300／50，runbook §11 同步；主窗口翻页键绑定并入既有绑定行，Desktop 类行数不增。native_assets 已被 R1827 改写成类，本轮只保留仍能对上的 2 处间距替换。

## 未做与说明
- 第 3 项（三虎字号放大）：契约测试要求云朵字号比正文小一档、提示比回复小一档，放大即违约，保留不改。
- 第 8／9／10 项核查后无需改：native_assets 等待已在 app.async_ 内，qwen_setup 的 urlopen 在线程里，messagebox 命中处就是统一分派器本身。
- ui_widgets 拆出弹窗模块的尝试已撤回：违反按钮边界门禁（只有 ui_widgets 可用原生 ttk.Button）。

## 验证
- `smoke_test.py --architecture`（隐藏桌面）：384 项，3 红均为环境性：基准历史.json 被 gitignore、SKILL gitlink 为空、分支上状态页轮次头落后 master。
- `run_selftests.py -k pet_cloud pet_ui pet_offer idea skill_panel desktop_shortcuts ui_ token project_page`：修掉一处拆分漏导入（DIALOG_SCREEN_MARGIN_*）后，剩余红 test_ui_edges、test_skill_panel_dropdown_layout（干净 HEAD 同样红，隐藏桌面尺寸）与 idea 系列（gitlink 为空），非本轮回归。
- 断言未动。
