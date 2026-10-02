# R699 功能轮结果：统一提示词／功能说明／进度文字

## 结果

已建立三类文字的唯一构建入口：`HintLabel`（短提示）、`DescriptionBlock`（可折行说明）和 `ProgressLabel`（状态/进度）。它们只消费 `TEXT_HINT`、`TEXT_DESC`、`TEXT_PROGRESS`，统一字体、颜色、折行宽度、锚点与内边距；Tk `Label` 没有单独的行距配置，行距语义由对应 token 的统一纵向留白表达并可由组件实例读取。

阶段配置弹窗已优先收敛：模型/外部包提示使用 Hint，HOLLMWOOD/路由/预设共享说明使用 Description，预设保存与统筹状态使用 Progress。没有改变配置写入、事件绑定、用户项目数据或其他业务页面。

## 变更文件

- `ui_tokens.py`：新增三组 `TEXT_*` token，全部复用既有 `FONTS`、`COLORS`、`SPACING`。
- `ui_widgets.py`：新增三种文字组件，并登记标题样式以移除阶段配置页的原地字体设置。
- `skill_panel.py`：只替换阶段配置弹窗中对应语义的散落文字标签。
- `design_tokens.md`、`ui_components.md`：登记文字层级、选用规则与唯一入口。
- `tests/test_ui_theme.py`：新增三类组件 token 回归。
- `tests/architecture/test_text_component_boundary.py`：守卫阶段配置页不得以原始 `tk/ttk.Label` 直接设 `font`、`foreground` 或 `fg`。
- `tests/test_skills.py`：随文字组件语义迁移更新类型/文案断言；断言强度未降低。

## 验证

- `python -m unittest tests.test_ui_theme tests.architecture.test_text_component_boundary`：13/13 通过。
- 阶段配置受影响用例：4/4 通过。
- `python smoke_test.py --affected ui_widgets skill_panel`：`test_skills` 136 条通过。
- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --architecture`：103 条中 101 条通过。新增文字边界守卫通过；两条既存红仍为 `idea_chat.py:609` 的 L2→L3 依赖和 `desktop.py:1403 workflow.get` 的阶段入口守卫，未由本轮引入，已高于历史 94 条架构基线。

## 三个基线数

- 默认冒烟：8/8 通过。
- 架构门禁：101/103 通过（两条既存红如上）。
- 全量回归：3,230 条历史基线；本功能轮未要求、未触发全量安全回归。

界面改动需重启应用后生效。

[TASK_COMPLETE]
