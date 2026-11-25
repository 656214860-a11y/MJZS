# tasks_round_4512_result — UX-USAGE-HOVER-CARD（W2）
<!-- round-evidence: {"commit_base": "444b6a359", "credential_hits": 0, "evidence_sha256": "e0203ad4d48d1664", "exit": 0, "failed": 0, "passed": 61, "round": 4512, "tests": "run_selftests.py -k usage_indicator_ui ui_status_bar desktop_compact_layout hover_card_states"} -->

## 三问

- **本轮类型**：修复轮（§3.2，取消页面底部 Token 用量提示点击弹窗，改为被动悬停卡片 `UsageHoverCard`）。
- **测试跑了吗、三个基线过了吗**：跑了。
  - 定向：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k usage_indicator_ui ui_status_bar desktop_compact_layout hover_card_states` → 改后 61 条用例（改前既有 58 条 + 新增 3 条）、0 个文件有红、0 条跳过、`ALL TESTS PASSED`，退出码 0。
  - 架构门禁：`..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` → `Ran 708 tests in 278.529s`、`OK`、`✅ 架构治理测试：tests/architecture`，退出码 0（当轮实测）。
  - 默认冒烟基线 8/8 与全量 `--all --safe`：本轮验收清单未包含，未运行；全量欠账口径以 `full-safe-receipts.json` 为准。
- **欠账少了吗**：取消底部 Token 用量提示点击模态弹窗并改为被动悬停卡片，精确保持 `ui/ui_usage_indicator.py` 既有 1 处 `tk.Label` 计数、`ui/ui_usage_detail.py` 0 处裸 `tk.*` 与 0 处手写字体/颜色标签、以及既有图层依赖边，零新增 `.py` 模块、零新增依赖、零架构豁免，未引入新欠账。

## 缺陷复现（先红后绿）

- **复现方式**：在 `程序/tests/test_usage_indicator_ui.py` 中将旧点击弹窗用例更新为校验点击不再打开 `UsageDetailDialog`，并新增 3 条悬停卡片行为用例（被动弹层与实时刷新、卡片内打开 `TodayDetailsDialog` 并收起卡片、移出/隐藏/销毁清理），在未改生产代码前执行第一条验收命令。
- **改前红测结果**（基线 `444b6a359`，退出码 1，共 61 条用例，57 条绿、4 条红、0 条跳过）：

```text
  test_hover_card_states        10 条     1.1 秒
  test_usage_indicator_ui       14 条     1.3 秒  ✗ 4
  test_ui_status_bar#2           9 条     3.0 秒
  test_ui_status_bar#1          14 条     4.3 秒
  test_desktop_compact_layout    14 条    22.0 秒

共 61 条用例，29.1 秒；1 个文件有红
```

1. `test_click_does_not_open_detail_dialog`：`AssertionError: Lists differ: [<ui.ui_usage_detail.UsageDetailDialog object .!usagedetaildialog>] != [] : 点击底部 Token 指示器或其子标签不应再弹出 UsageDetailDialog`。
2. `test_hover_card_shows_passive_overview_and_live_refresh`：`AssertionError: False is not true : 缺少 UsageHoverCard 类`。
3. `test_hover_card_action_opens_today_details_and_hides_card`：`AssertionError: False is not true : UsageIndicator 应暴露 hover_card`。
4. `test_hover_card_hides_on_leave_hide_and_indicator_destroy`：`AssertionError: False is not true : UsageIndicator 应暴露 hover_card`。

## 改动清单（文件:行号）

1. `程序/ui/ui_usage_detail.py`（145 → 310 行，+170/-5）：
   - `L14-L21`：从已有导入源补充 `TclError`、`TOOLTIP_BORDER_WIDTH`（`ui_tokens`）与 `SecondaryButton`、`Tooltip`（`ui_widgets`），不导入 `ui_popup`，零裸 `tk.*`。
   - `L43-L71`：新增 `_snapshot_data`、`_overview_fields`、`_summary_text` 实时读取与整理「今日」「项目累计」与可选「余额」（无有效余额时不展示、不伪造 0）。
   - `L74-L204`：新增 `UsageHoverCard(Tooltip)`（默认 `mode='card', pin_on_click=False`），转发 `indicator._labels.values()` 的 `<Enter>`/`<Leave>`/`<FocusIn>`/`<FocusOut>`/`<Button-1>`；重写 `_populate(tip)` 使用 `Card.TFrame`、`CardHeading.TLabel`、`HintLabel`、`ttk.Label`、`ttk.Separator` 与 `SecondaryButton(..., width=0, style='Tokens.Text.TButton')`（「查看今日明细」）；重写 `refresh()` 支持展开期间无闪烁实时刷新和余额行动态增删；点击「查看今日明细」先取顶层主窗为 `parent` 再 `hide()` 收起卡片并打开 `TodayDetailsDialog`。
   - `L207-L309`：原样保留 `UsageDetailDialog` 与 `TodayDetailsDialog`（含 UTF-8-SIG CSV 导出）向后兼容。
2. `程序/ui/ui_usage_indicator.py`（119 → 124 行，+15/-10）：
   - `L16`：导入 `UsageHoverCard`（复用已登记的 `('ui_usage_indicator', 'ui_usage_detail')` 边，不导入 `ui_widgets`/`ui_popup`）。
   - `L25-L36`：移除 `self` 与各子标签的 `<Button-1>` 打开 `UsageDetailDialog` 绑定及 `_open_detail` 方法，创建并暴露 `self.hover_card = UsageHoverCard(self, desktop)`；保持唯一 1 处 `tk.Label`、三档阈值色、`STATUS_BAR_FONT` 及 `StatusBar` 布局几何不变。
   - `L82-L84`：`refresh()` 在刷新文字后同步调用 `self.hover_card.refresh()` 保持展开中悬停卡片实时同步。
   - `L116-L123`：重写 `destroy()` 销毁前主动 `hide()` 收起悬停卡片，防止浮层残留。
3. `程序/tests/test_usage_indicator_ui.py`（197 → 349 行，+160/-8）：
   - `L108-L150`：将 `test_click_opens_detail_dialog` 按契约更新为 `test_click_does_not_open_detail_dialog`，验证点击指示器本体及 `token`/`money`/`balance` 子标签均不再弹出 `UsageDetailDialog`。
   - `L152-L266`：新增 3 条用例覆盖悬停卡片被动弹层属性（`overrideredirect`、`_positioned_once`、无 `grab_current()`）、实时刷新与余额动态显隐、点击「查看今日明细」收起卡片并打开 `TodayDetailsDialog`、指针留在控件/卡片上经 grace 不关闭、移出后自动关闭及 `hide()` / `indicator.destroy()` 干净清理。

## 改后验收输出尾部（退出码均为 0）

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k usage_indicator_ui ui_status_bar desktop_compact_layout hover_card_states`（退出码 0）：
   ```text
     test_hover_card_states        10 条     1.2 秒
     test_usage_indicator_ui       14 条     1.7 秒
     test_ui_status_bar#2           9 条     3.0 秒
     test_ui_status_bar#1          14 条     4.4 秒
     test_desktop_compact_layout    14 条    22.7 秒

   共 61 条用例，54.9 秒；0 个文件有红
   实际跳过 0 条用例：本机没有任何登记位被跳过
   ALL TESTS PASSED
   ```
2. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（退出码 0）：
   ```text
   ----------------------------------------------------------------------
   Ran 708 tests in 278.529s

   OK
   ✅ 架构治理测试：tests/architecture
   ```

## 未验证项与卡外发现

- **未验证项**：
  - `smoke_test.py` 默认档（8/8）与 `run_selftests.py --all --safe`（本卡验收清单未要求，未运行）。
  - 真实可见桌面窗口下人工鼠标悬停与跨屏底边翻转视觉复核（隐藏桌面真 Tk 测试已验证被动弹层属性、事件状态机、样式与几何）。
- **卡外发现**：无。

## 提交

- 通过 `scripts/dev.py commit` 提交至分支 `codex/ux-usage-hover-card`，不合入、不 push。
