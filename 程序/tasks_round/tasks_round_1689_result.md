# R1689 契约轮（源码轮）：UI 整体优化批次 1“契约对齐”

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 契约轮（源码轮）。依据产品负责人对 UI 评审报告的裁决（紧凑密度、不保留橙色、系统字体 Microsoft YaHei UI），先让令牌与文档达成一致，再由后续批次改页面。不动页面布局，不动用户数据。
2. **测试跑了吗？三个基线过了吗？** 定向 `-k ui_tokens ui_token_contract ui_theme ui_widgets production_lock design_tokens video_ui pet_ui_support test_layers function_size_ratchet agents_md module_size_ratchet`：145 条 0 红；默认冒烟 8/8。未跑 `--all`。
3. **project_status.md 的欠账少了吗？** 没有减少。本轮改源码，源码轮全量欠账 **+1**。

## A 改动

- `ui_tokens.py`：`text_secondary` #4B5563（白底 7.56:1）、`text_muted` #6B7280（白底 4.83:1，页面底 #F7F8FA 上 4.55:1）；新增 `focus` #2563EB；删除 `warning_hover`、`warning_pressed`、`emphasis`、`emphasis_pressed`（橙色退场）；新增 `CONTROL_HEIGHT`、`CONTROL_HIT_MIN`（均取 `SPACING["2xl"]`=32）。
- `ui_widgets.py`：6 处按钮禁用态前景由 `text_muted` 改为 `disabled_text`，使“弱文字”恢复可读、“禁用”独立成色。
- `production_lock_fields.py`：提示文字改用 `warning_text`（原 `warning` 在白底不足 4.5:1）。
- `ui_theme.py`：删除未被引用的 `StageConfig.TButton`；`Highlight.TButton` 由橙色改为 `primary_pressed` 深蓝，悬停 `primary_hover`，焦点色 `focus`（唯一使用点 `app.py:255`，`test_video_ui` 只核对样式名）。
- `design_tokens.md`：颜色表同步；新增字体表（四档层级，`caption` 与 `body` 同为 10pt 为有意合并）；新增“控件尺寸与密度（R1689 裁决）”。
- `ui_components.md`：主/次按钮规格对齐（10pt、32px、`color.focus` 焦点环、Highlight 不用橙色）；通知节增加“可恢复错误非模态”的目标策略，并注明当前 `error()` 默认 `modal=True` 为已知偏差。
- `tests/test_ui_theme.py`：两条禁用态前景的期望令牌由 `COLORS['text_muted']` 改为 `COLORS['disabled_text']`。**断言未动**——断言结构、被测样式名与比较方式不变，仅因契约有意拆分了“弱文字”与“禁用文字”两个令牌而更新期望值。
- 新增 `tests/test_ui_token_contract.py`（6 条）：文字令牌在白底／页面底对比度 ≥4.5:1；实心按钮白字可读；`disabled_text` 与 `text_muted` 不同；橙色令牌不再存在；`CONTROL_HEIGHT`=32 且正文 10pt；`design_tokens.md` 登记了代码里的每个颜色与字体令牌。
- `project_status.md`：当前轮次改为 1690，并新增 R1689 条目。

## C 待裁决

- **未目视验证**：本轮只验令牌、文档与测试，没有人眼看过界面。`Highlight` 按钮（“MCP 优化”）由橙变深蓝，需要产品负责人亲眼确认。
- **契约先于代码**：`ui_theme.apply()` 与 `ui_widgets.setup_styles()` 仍各定义一套 `TButton`/`Primary.TButton`，实际生效的是后者（内边距 (12,4)）；32px 控件高度、焦点环、状态栏按级别着色、可恢复错误非模态均未落到代码。这些归批次 2（样式引擎合并，需实测高度）和批次 5／7。
- **对比度只钉了令牌对**：未覆盖各页面内联或例外的颜色组合；由批次 10 的视觉契约验收测试扩展。
- **全量欠账**：源码轮 +1，累计欠账见 `project_status.md`。
