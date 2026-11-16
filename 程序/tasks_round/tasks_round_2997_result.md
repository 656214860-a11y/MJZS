# R2997 修复轮结果
<!-- round-evidence: {"commit_base": "ae577ab7", "credential_hits": 0, "evidence_sha256": "768767d0fd6b1b32", "exit": 0, "failed": 0, "passed": 19, "round": 2997, "tests": "run_selftests.py -k hover_card compact_widgets script_file"} -->

## 三问（§7.2）

1. **轮次类型**：修复轮（§3.2）。按 R2993 只读诊断的 J 整改路线 **R1** 执行：根因＝诊断候选 1（技能悬停说明卡片未豁免 `ui_theme` 的 grab 接管，Leave/Enter 循环反复弹出）＋候选 2（点击/键盘焦点与悬停无互斥，关闭弹层后焦点回弹再弹）＋共享 Tooltip 缺 pin/grace/reshow 状态机。
2. **测试**：跑且全绿。默认冒烟 **8/8**；`smoke_test.py --affected hover_card compact_widgets script_file` **9/9**（19 条 0 红，126 秒）；gui_hidden 官方入口定向同 3 文件 **19 条 0 红**。三个基线：冒烟 8/8 通过；架构门禁未跑（本轮不改分层、非跨层/结构治理，层级登记与架构测试清单未变）；全量未跑、欠账口径不变（本轮不触发全量）。新增测试 10 条先红后绿（红证据见下）。
3. **欠账**：未新增。R2993 漏洞清单 21 条中 #1/#2/#3/#6/#7/#8/#9/#10/#17/#20 闭环，#12/#16/#21 部分闭环（见边界），#4/#5/#11/#13/#14/#15/#18/#19 按 J 路线留 R2。

## 改动清单

- `ui\ui_tooltip.py`（重写，蓝本 ttkbootstrap `tooltip.py`，MIT，注释注明来源；reshow/grace 语义参考 Radix Tooltip/HoverCard）：排程先取消旧计时器；`mode='tip'` 移出立即隐藏、`mode='card'` 移出 closeDelay 300ms 后隐藏并在到点复核指针（`winfo_containing`）、卡片自身 Enter/Leave 保活；关闭后 reshow 150ms 窗口内再进入跳过延迟；点击不拦原动作但抑制重弹直到指针离开/失焦（`_suppress`）；`pin_on_click` 点击钉住、钉住期间悬停不触发、点空白处/Escape/再点解除（Escape 同时在根窗口与浮层窗口挂监听，覆盖焦点在浮层上的按键投递）；同帧单例可见（`_VISIBLE_TIP`，防多实例叠窗）；可见时 `refresh()` 按最新文本刷新（修 #17）。
- `desktop_shared_input.py`：技能菜单 `overrideredirect(True)`＋`make_passive_popup`（豁免 grab/居中接管）＋点外部收起（`_skill_menu_outside_press`，✦ 按钮与菜单内点击放行）；技能悬停说明卡片迁移到 `Tooltip(mode='card')`（`place` 定位浮层右侧，`wraplength=SKILL_CARD_WRAP`，空说明回退「（该技能没有填写 description）」）；删除野实现 `_show_skill_card`／`_hide_skill_card`。
- `ui_tokens.py`：`TOOLTIP_DELAY_MS` 400→**300**，新增 `TOOLTIP_RESHOW_MS=150`、`TOOLTIP_CLOSE_DELAY_MS=300`（数值按用户确认的契约）。
- `ui_components.md`：Tooltip 契约同步（300ms 出现、150ms reshow、card closeDelay、pin、点击抑制）。
- `tests\test_hover_card_states.py`（新增 10 条）：点击抑制重弹、重复排程取消、reshow、closeDelay 隐藏与保留、pin 切换/移出不藏、点空白解除、Escape 解除、被动弹层豁免、单例可见。

## 红→绿证据（§5 先红后绿）

改动后首次 gui_hidden 运行：10 条用例 **7 红**（`test_card_close_delay_hides_after_grace`、`test_card_close_delay_keeps_card_when_pointer_still_on_widget`、`test_click_suppresses_repop_until_leave`、`test_escape_unpins_card`、`test_pin_click_toggles_and_leave_does_not_hide`、`test_reshow_window_skips_enter_delay`、`test_window_is_passive_popup`）。定位：7 红均为**测试环境问题而非产品缺陷**——① 未映射窗口上的合成 `<Enter>` 事件被 Tk 丢弃（setUp 只 `update_idletasks` 不 `update`）；② 隐藏桌面上后建的 Tk 根不自动获得焦点，按键事件无处投递（前一个测试销毁 root 后新 root 焦点为 None）。修正 setUp（`update()`＋`focus_force()`，与 `test_asset_detail`／`test_idea_chat` 同一惯例）后 10/10；期间产品代码修正 1 处真实缺口：钉住后焦点在浮层窗口上时 Escape 收不到（浮层窗口补绑 Escape）。复跑三次全绿（单文件 unittest 10/10、官方入口 19 条 0 红、affected 门禁 19 条 0 红）。

## 行为契约变化（已同步文档，用户已确认）

- Tooltip 出现 300ms、移出立即隐藏（tip）／closeDelay 300ms（card）、reshow 150ms；点击钉住仅卡片且 `pin_on_click` 显式开启；纯文字 Tooltip 点击＝原动作＋抑制重弹。既有 9 条 Tooltip/TreeRowTooltip 测试断言未动、全部通过。

## 范围与边界

- **R2 未动**：缩略图互斥（#4/#11）、模型按钮并存（#5）、TreeRowTooltip Motion/FocusIn 互斥（#12 部分）、Flyout 压指针与悬挂窗口期（#13/#19）、云朵 220ms 计时（#15）、孤儿 Label（#18）、附件 3 实例合并（#20 部分）、tip 模式高频建窗销毁（#21 部分：既有测试契约要求 destroy 语义，单例可见已防叠窗）。
- **show 路径严格指针复核未落地**：与既有 `event_generate` 测试（合成事件坐标≠真实指针）冲突；根因「Leave 被吞」已由 grab 豁免消除，留 R2 观察。
- 状态页轮次头同步留待合入 master 时随合并提交完成（工作树门禁只写 `tasks_round`，与 R2993 同口径）。
