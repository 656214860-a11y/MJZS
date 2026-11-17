# R2993 只读诊断轮结果
<!-- round-evidence: {"commit_base": "6ecbfd5f", "credential_hits": 0, "evidence_sha256": "25cdd4d8c0a3c96c", "exit": 0, "failed": 0, "passed": 0, "round": 2993, "tests": "docs-only"} -->

## 三问（§7.2）

1. **轮次类型**：只读诊断轮（AGENTS.md §3.5／runbook §15 3.5）。未修改任何 `.py`，不搬目录、不重命名、不删文件；仅新增本结果文件。状态页轮次头按门禁规则留在合入 master 时随合并提交同步（§2.6：仅 master 可提交 `project_status.md`；本工作树只写 `tasks_round`），同步目标为 2994（最新报告 2993＋1）。
2. **测试**：未跑（§5：只读诊断默认不跑测试）。三个基线不适用本轮（无代码改动、无新增欠账）。
3. **欠账**：未减少也未新增；悬停卡片既有缺陷待用户确认后进入修复轮闭环，此处不记为已修复。

## 背景与已锁定决策（grilling 结论）

用户报告：**「上一个点击图标显示的悬停卡片，鼠标移动后还会自动弹出」**。要求：全面盘点应用所有悬停卡片的功能漏洞；查找 GitHub 成熟组件/悬停卡片框架并复用代码。经逐项确认锁定：

- 复用方式：**内化改写**（保持零第三方依赖），蓝本 = ttkbootstrap `tooltip.py`（MIT），grace/pin 语义移植自 Radix/floating-ui（概念移植，非代码直搬）。
- 行为契约：悬停 **300ms 出现、移出立即隐藏、reshow 150ms**；点击「钉住」仅用于卡片类；纯文字 Tooltip 点击＝执行原动作＋**抑制重弹**直至鼠标离开再进入；点空白处／Escape 解除。
- grace：简单 **closeDelay 300ms＋`winfo_containing` 复核**，不做 safePolygon 三角判定。
- 修复分批两轮：R1＝共享 Tooltip 升级＋技能卡片迁移（闭环报告的 bug）；R2＝其余互斥与零散项。

基线：master `6ecbfd5f`（R2988 合并）。盘点起初基于 `0145c77f`（R2982），快进后对 3 个位移文件（`desktop.py`、`desktop_page_nav.py`、`desktop_writing_page.py`→`desktop_files_panel.py`）复核行号；其余悬停文件两基线间零改动。

## 一、悬停/气泡实现清单（6＋1 处）

**A. 统一 Tooltip（权威共享组件）** `程序\ui\ui_tooltip.py:7-110`（经 `ui_widgets.py:29` 转出；`ui_components.md:95-99` 契约；token `ui_tokens.py:208-221`，默认延迟 400ms）
- 绑定（17-21）：`<Enter>`→`_schedule_from_pointer`（23-26，指针＋偏移定位）、`<Leave>`→hide、`<FocusIn>`→`_schedule_from_focus`（28-35，控件正下方）、`<FocusOut>`→hide、`<Destroy>`→清理。
- `schedule()` 用 `after(delay_ms, show)` 重入只留最新（37-45）；`show()` 建无边框 Toplevel（54-56）＋`make_passive_popup` 摘 grab（56）＋按显示器钳位（62-69）；`hide()` 取消 job＋销毁窗（90-106）。
- 子类 `TreeRowTooltip`（112-133）：树 `<Motion>`（119）逐行重排、`<MouseWheel>` 收起（120）、换行先 hide 再重排（122-128）、FocusIn 取选中行（130-133）。
- 调用点：`desktop.py:260/268`（侧栏 15 个导航图标＋设置）、`desktop.py:369-370`＋`ui_widgets.py:1069`（页标题 EllipsisLabel）、`desktop_project_pages.py:210/218`、`pet_ui_support.py:315-318`、`desktop_shared_input.py:300-304`（✦技能/附件/语音/发送/模型 5 钮）、`production_lock_fields.py:332`、`skill_panel.py:332`、`white_model.py:151`、`workflow_settings_dialog.py:73`、`desktop_idea_attachments.py:78/81`。

**B. 文件表逐行预览卡片** `desktop_file_card.py:11-27` `TreeRowCard(TreeRowTooltip)`（重写 `_populate`），文本源 `script_row_card`（30-44）。使用点：**`desktop_files_panel.py:70`**（R2962 起，原 `desktop_writing_page.py:246` 迁出）。纯悬停，无点击联动。

**C. 共享输入框两个卡片浮层** `desktop_shared_input.py`
1. `/` 补全卡片 `CompletionPopup`（99-198）：Frame＋place 覆盖层（非 Toplevel）；`<Motion>` 只跟随高亮（121,187-198）。
2. 技能列表浮层（点击 ✦，382-439）：`BaseDialog(self,'技能',modal=False,chrome=False)`（388）；行悬停→右侧说明卡片；行点击→`_pick_skill`（557-567）写 `/技能名`。
3. 技能悬停说明卡片 `_show_skill_card`（525-541）：`BaseDialog(chrome=False,modal=False)`（**532**），定位浮层右侧（538-540）；`_hide_skill_card`（455-462）；行绑定 hover/leave/click（399-423）。

**D. 表格缩略图悬停放大卡** `cell_hover.py` `CellImages`（419-1016）：`<Enter>`→`zoom_in`（848,598-642）指针右上 6px（`ZOOM_NEAR=6`，40,779）放 960px 放大 Label（宿主窗口内，616-619）；`<Leave>`→`zoom_leave` 90ms 复检（`ZOOM_HIDE_MS=90`，37,788-814）；250ms 看门狗（`ZOOM_WATCH_MS=250`，38,689-711,726-748）；滚轮即收（850）；单击交树选择、双击打开（856-859）。使用点：`app.py:196-197/1018-1024`、`asset_reference_images.py:545`、`storyboard_files.py:702`。同文件 `CellHover`（266-416）仅为格子高亮覆盖层。

**E. 点击弹卡浮层 Flyout（共享组件）** `ui\ui_popup.py:8-26`（overrideredirect＋`make_passive_popup` 17-18；`make_passive_popup` 29-38；`monitor_bounds` 41-73，ctypes `GetMonitorInfo`）
- 模型选择器卡片：`stage_model_picker.py:62-64`（toggle）→`_open_popup`（189-202，Flyout 192，点外部/Esc 198-201）→`_place_popup`（204-223，锚上方、放不下翻下）；行悬停底色（283-307）；模型芯片悬停（336-348）。
- 侧栏二级选择层：`desktop_page_nav.py:371-394`（Flyout 374，贴底翻上，点外部/Esc 390-391，Destroy 兜底 393）；`_sidebar_popup_outside` 395-404、`_sidebar_popup_destroyed` 408、`_close_sidebar_popup` 423；入口 `_assets_nav_toggle` 440、`_post_project_picker` 467；行悬停换底色（495 附近）。

**F. 三虎气泡（云朵框）** `ui\pet_cloud.py` `Cloud`（261+）：无边框置顶 Toplevel（`win` 270）、`overrideredirect`（332）、建窗即 `_positioned_once=True` 豁免 ui_theme（328）；show/deiconify（477+）、close→渐隐→withdraw（529-576）；时长定时 `ui\pet_cloud_timing.py`（`_arm_hold` 95-106、`_expire` 250-263）；关闭按钮悬停变色（415）。点击宠物：`pet_ui_view.py:785-791`→`orchestrator\pet_chat_coordinator.py:31-46`，`CLICK_MS=220`（`pet_ui.py:115,401-403`）区分单击/双击；**移动鼠标不取消待决计时器**（仅窗口销毁时 `pet_ui_view.py:421,820-827` cancel）。

**G. 仅悬停样式（非卡片）**：按钮悬停渐变 `ui/ui_hover_fade.py`；行悬停淡入 `ui_motion.bind_row_hover`；猫爪提亮 `pet_ui_view.py:575-614`。

## 二、漏洞清单（21 条 → 6 类）

**类 1：点击与悬停/焦点无互斥（报告的 bug 主因）**
1. 统一 Tooltip：点击图标→按钮获焦→`<FocusIn>` 排 400ms 弹卡（`ui_tooltip.py:19,28-35,43`），与点击动作（打开 Flyout／切页）并存，无任何抑制/互斥 API。
2. 关闭弹层后焦点回弹→再次 FocusIn 弹出；鼠标移动重新掠过即再排（17）。
3. 技能悬停说明卡片：卡片抢 grab→行 Leave/Enter 循环→show→destroy→再 show（详根因候选 1）。
4. 缩略图放大卡：单击选择行后指针仍压在图上→`<Enter>` 再弹（`cell_hover.py:848,598`），无点击后抑制。
5. `StageModelPicker` 触发按钮同时挂点击弹卡（`stage_model_picker.py:62-64`）与 Tooltip（`desktop_shared_input.py:304`）：点击后焦点触发的 Tooltip 与上方卡片并存。

**类 2：未豁免 ui_theme 接管（grab/居中/置顶）**
6. 技能菜单与技能说明卡片均为 `BaseDialog(chrome=False,modal=False)`（`desktop_shared_input.py:388,532`）而**未调 `make_passive_popup`**——全库无边框浮层中唯一未豁免（对比 `ui_tooltip.py:56`、`ui_popup.py:18`、`pet_cloud.py:328`）；`ui_theme.py:287-300` 对启用 `install_window_placement`（`desktop.py:238`）的根挂 `-alpha 0`＋`<Map>`→grab。R1982 同源（`tasks_round/归档/2026-10/tasks_round_1982_result.md:9`「卡片刚显示就被收掉，而且一直是透明的」）。

**类 3：无隐藏延迟、无钉住、无 grace**
7. 统一 Tooltip 离开图标立即销毁（`ui_tooltip.py:18,99-106`），从图标滑向卡片旁无停留窗口；无钉住语义。
8. 技能卡片无 Enter/Leave/隐藏延迟：指针移进卡片区→行 `<Leave>` 立即 destroy（`desktop_shared_input.py:402-403,455-462`）；移回行立即重建（399-400）。
9. 技能卡片每建必 destroy 重建（527 先 hide 再建），高频建窗/抢 grab 造成闪烁与 CPU 空转。
10. 技能菜单无点外部关闭监听（382-439，对比 Flyout：`desktop_page_nav.py:390-391`、`stage_model_picker.py:198-201`）；仅 BaseDialog 自带 Esc（`ui_widgets.py:882`），grab 生效时点外面到不了主窗。

**类 4：贴指针布局引起 Leave/Enter 抖动与竞态**
11. 放大图贴指针 6px（`cell_hover.py:40,779`），极易滑入卡片区；卡片区 Enter 只续命不收起（656）。
12. `TreeRowTooltip`：`<Motion>` 每次划过行都 hide＋重建 after（`ui_tooltip.py:119,122-128`）；点选行经 FocusIn 再弹（130-133），与 Motion 显示状态可打架。
13. Flyout 贴底翻上时出现在锚点上方压住指针（`desktop_page_nav.py:371-377` 区域；`stage_model_picker.py:217-218`），无卡片自身 Enter/Leave 处理。
14. 浮层行悬停与点击同绑：悬停底色覆盖选中态提示（视觉弱，`desktop_page_nav.py:495` 附近）。

**类 5：定时器/生命周期不随鼠标移动取消**
15. 三虎云朵单击 220ms 待决计时器不随鼠标移动取消（`pet_ui.py:115,401-403`；仅窗口销毁 `pet_ui_view.py:421` 才 cancel）：点击后立刻移开鼠标，云朵仍在原点击时刻弹出。
16. 统一 Tooltip `show()` 不校验指针是否仍在控件上（`ui_tooltip.py:47-50` 只查 `_window/text/winfo_exists`）：`<Leave>` 被吞时定时到点照样弹。
17. 可见卡片文本被改（如 `desktop_account_page.py:222-224` 改 `tip.text`）不刷新已显示窗口（`show()` 有窗即早退，49）。
18. 放大图看门狗在指针读不出时判「还在看」（`cell_hover.py:713-724`），无真指针场景滞留；换页/重建仅靠 `refresh→zoom_hide`（945-946）兜底，绕过的销毁路径留孤儿 Label（994-1016 收尾）。
19. Flyout 主窗 `<Button-1>` 外部关闭绑定靠 `<Destroy>` 兜底解绑（`desktop_page_nav.py:393,408`），事件乱序有短暂悬挂窗口期。

**类 6：重复实例与建窗开销**
20. `desktop_idea_attachments.py:76-78` 同一 chip 绑 3 个 Tooltip 实例且面板重建（59）又新建一批；各实例独立 `_window`，同帧多实例可叠窗。
21. 每个 Tooltip 一个 Toplevel 用后即毁（`ui_tooltip.py:54,101-106`），高频悬停反复建/毁系统窗口。

## 三、用户报告 bug 的根因候选（降序）

**候选 1（最高）：技能悬停说明卡片未豁免 ui_theme 的 grab 接管 → Leave/Enter 循环反复弹出**
触发链：点 ✦ → `open_skill_list`（`desktop_shared_input.py:382-439`）建 BaseDialog 菜单，首次 `<Map>` 被 `ui_theme.py:293-300` 抢 grab 并居中聚焦（151-159,393-403,314-359）；鼠标移到技能行 →`<Enter>`→`_show_skill_card`（525-541）建卡片（532 未豁免）→ 首次 `<Map>` 抢走 grab → 行收 `<Leave>`→`_hide_skill_card` destroy（402-403,455-462）→ grab 释放 → 指针仍在行上，Windows 补发 `<Enter>`→ 再建卡 → 循环。此后每次移动鼠标掠过行都再弹。测试环境未启用 `install_window_placement` 故从未暴露。

**候选 2（高）：点击图标＝键盘焦点触发 Tooltip 且无互斥，关掉弹层后焦点回弹**
点击任一挂 Tooltip 的图标（`desktop.py:260,268`；`desktop_project_pages.py:207-218`；`desktop_shared_input.py:277-304`）→ 按钮获焦 → 400ms 后弹卡，与点击打开的 Flyout 并存；关闭弹层焦点回弹再弹；此后 `<Enter>`/Tab 回焦都会再弹。

**候选 3（中）：表格缩略图放大卡点击后悬停再次弹出**（`cell_hover.py:848,856-859,598-642`，无点击后抑制状态）。

**候选 4（中）：三虎云朵单击 220ms 待决计时器不随鼠标移动取消**（表现同为「点击后鼠标移动，卡片照样弹出」）。

**候选 5（低）：TreeRowTooltip 的 `<Motion>`＋FocusIn 双通道**（`ui_tooltip.py:119,130-133`）。

## 四、开源调研结论与蓝本

调研方式：GitHub REST API（stars/license/archived/pushed_at，2026-11-16）、raw 源码逐行核实、Microsoft Learn（`TTM_SETDELAYTIME`）与 W3C ARIA APG tooltip 模式。主要数据：

| 名称 | stars | 活跃度 | License | 依赖 | 亮点 |
| --- | --- | --- | --- | --- | --- |
| **ttkbootstrap tooltip.py（373 行）** | 2665 | 2026-11 活跃 | MIT | 包依赖 Pillow；screeninfo 可选 | 先 unschedule 再排新（防竞态）、topmost 默认、锚定＋跟随双定位、全方向 clamp、funcid 精确解绑、`<Destroy>` 自动释放 |
| gnikit/tkinter-tooltip（192 行） | 48 | 2026-11 活跃 | MIT | **纯标准库** | OUTSIDE/INSIDE/VISIBLE 三态，显示回调内复核状态（免 after_cancel） |
| Radix primitives（Tooltip/HoverCard） | 19505 | 活跃 | MIT | React | delayDuration 700/skipDelay 300/closeDelay 300；DismissableLayer（Escape＋外部 pointerdown） |
| floating-ui safePolygon | 32810 | 活跃 | MIT | 零运行时依赖 | 矩形槽＋三角区 grace 判定、requireIntent 40ms 复核 |
| AwesomeTkinter tooltip | 112 | 停更 5 年 | MIT | 零第三方 | waittime 500ms、schedule 先 unschedule |
| CTkToolTip | 149 | 2026-03 | CC0 | 依赖 customtkinter | delay 0.2s；destroy 不带 id 全量 unbind（反面教材） |
| CPython idlelib/tooltip.py | — | 活跃 | PSF | 纯标准库 | hover_delay 1000；绑定 id 存 `_id1/_id2/_id3` |

**选定蓝本：ttkbootstrap `tooltip.py` 为主**（状态机最完整，直接覆盖类 1/3/5 大部分），grace/pin 概念移植自 Radix/floating-ui。**pin（点击钉住）是所有 Tk 库都没有的，须按 Q3 契约自研**。数值规范：Windows 原生 initial 500ms/reshow 100ms；Radix 700/300；MUI 100/0；本次已锁定 300/150/0（见背景）。

证据 URL（本次实际抓取）：github.com/israel-dryer/ttkbootstrap（raw `src/ttkbootstrap/widgets/tooltip.py`、`src/ttkbootstrap/internal/positioning.py`）；github.com/gnikit/tkinter-tooltip（raw `tktooltip/tooltip.py`）；github.com/radix-ui/primitives（raw `packages/react/tooltip/src/tooltip.tsx`、`hover-card/src/hover-card.tsx`）；github.com/floating-ui/floating-ui（raw `packages/react/src/safePolygon.ts`）；github.com/python/cpython（`Lib/idlelib/tooltip.py`）；learn.microsoft.com/en-us/windows/win32/controls/ttm-setdelaytime；w3.org/WAI/ARIA/apg/patterns/tooltip/。

## 五、行为契约（修复轮执行标准，用户已确认）

1. 悬停出现延迟 300ms；移出立即隐藏；关闭后 150ms 内再进入跳过延迟立即显示（reshow）。
2. closeDelay 300ms＋隐藏前 `winfo_containing` 复核指针位置（简单 grace）。
3. 「钉住」仅用于卡片类浮层（技能说明卡等）：点击卡片触发控件切换钉住；钉住期间悬停逻辑不触发；点空白处／Escape／再点图标解除并隐藏。
4. 纯文字 Tooltip 点击＝执行控件原动作，且点击后抑制重弹，直至鼠标离开控件并重新进入；键盘焦点同理（FocusIn 排程时若卡片刚被点击关闭则跳过）。
5. 所有无边框浮层必须过 `make_passive_popup`（豁免 ui_theme 接管）。
6. 参数与组件契约登记 `design_tokens.md`／`ui_components.md`；Escape 经 `ui_shortcuts` 登记，冲突则上报用户裁决。

## 六、J 整改路线（两轮，用户已确认分批）

**R1（修复轮，闭环报告的 bug）**：`ui\ui_tooltip.py` 升级为完整状态机（ttkbootstrap 蓝本内化：schedule 先 unschedule、show 复核指针、closeDelay 300ms＋winfo_containing、reshow 150ms、pin 选项、点击/焦点抑制选项、单例当前可见引用）；`desktop_shared_input.py` 技能卡片迁移到 Tooltip（卡片模式＋pin），删 `_show_skill_card`/`_hide_skill_card` 野实现；技能菜单接 `make_passive_popup`＋点外部关闭；`ui_tokens.py` 更新延迟 token；`ui_components.md` 同步契约。测试：新 test_hover_card_*（红→绿）。

**R2（修复轮，其余互斥与零散项）**：`cell_hover.py` 点击后抑制＋卡片区 Enter 收起；`TreeRowTooltip` Motion/FocusIn 互斥；`stage_model_picker.py` 触发钮 Tooltip 与弹卡互斥；`pet_ui.py` 单击待决计时器随鼠标移出取消；`desktop_idea_attachments.py` 3 实例合并；Flyout 悬挂窗口期兜底；技能菜单外部关闭收口。每轮独立测试、领号、提交。

## 七、K 测试计划

- 现有相关测试：`tests\test_script_file_hover_card.py`（TreeRowCard）、`tests\test_ui_compact_widgets.py:75`（TreeRowTooltip）——R1 改动不得破坏其断言（契约变化需同步并注明）。
- 新增（修复轮内，含 Tk 的经 `工作流任务\gui_hidden.py` 隐藏桌面）：pin 切换与悬停抑制、点击后抑制重弹、closeDelay＋winfo_containing 复核、reshow 窗口、`make_passive_popup` 豁免验证（不抢 grab）、`after` 定时器取消竞态。
- 回归：默认冒烟 8/8＋`--affected`（ui_tooltip 消费者全量）＋定向 `-k`；涉及 `ui_theme` 时跑相关批次。

## 八、边界与风险

1. 并行车道 2990/2991/2992 在途（devin-perf／devin-skill-t1／devin-dead-symbols），修复轮开工前须 `dev.py sync` 或 rebase 最新 master；状态页轮次头同步到 2994 在合入 master 时完成，如有冲突按合并轮流程解决。
2. R2962 已把项目文件表迁入 `desktop_files_panel.py`（TreeRowCard 使用点 `desktop_files_panel.py:70`），修复轮以此为准。
3. 候选 1 依赖 `install_window_placement` 启用路径（`desktop.py:238`），测试需构造等价 grab 接管环境才能复现。
4. 修复轮动手前先 `dev.py claim` 领号（本工作树分支 `dsh-52a9b6ff-8ed3` 已属功能工作树）。
