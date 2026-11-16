# R3031 修复轮结果
<!-- round-evidence: {"commit_base": "5f83d7fd", "credential_hits": 0, "evidence_sha256": "21a2c4f9de2c7893", "exit": 0, "failed": 0, "passed": 58, "round": 3031, "tests": "run_selftests.py -k shared_input"} -->

## 三问（§7.2）

1. **轮次类型**：修复轮（§3.2）。用户报告共享输入框两处弹层定位缺陷：① 点 ✦（skill）／＋（添加）图标后弹出的选项卡列表底部没有贴着被点图标，其上方隔着整个文本输入区；② 输入框内输入 `/` 时 skill 候选浮层位置不正确、内容被遮挡。
2. **测试**：跑且本轮范围全绿。默认冒烟 **8/8**；新增真实 Tk 几何回归 2 条**先红后绿**；`run_selftests.py -k shared_input`（test_shared_input_stages／ui／voice）共 58 条全绿；`smoke_test.py --affected desktop_shared_input desktop_shared_menus` 消费方门禁 4 文件：共享输入 3 文件全绿，`test_skills` 2 红＝注册表计数 71≠73（工作树缺 `skills/00全流程SKILL/AIGC创作全流程/` 嵌套仓库内容，R3012 已记录的同源环境限制；stash 本轮改动后单跑复现同一断言，与本轮无关）。三个基线：冒烟 8/8 通过；架构门禁未跑（不改分层，`ui_popup` 与 `desktop_shared_menus` 同为 L4）；全量未跑、欠账口径不变。
3. **欠账**：未新增。

## 根因

- **图标面板悬空**：`AnchoredPanel.place_panel()` 以输入卡顶部 `card.winfo_rooty()` 为锚，把面板底边放在卡顶上方——面板实际渲染在整个 TextArea 之上，与被点图标之间隔着约 100px 文本区（隐藏桌面探针实测：卡顶 697／图标行顶 795／面板底 791，间隔 ≈102px）。
- **候选浮层错位与遮挡**：`CandidatePopup.place()` 用 `winfo_screenwidth/height`（恒为主屏尺寸）做可视区钳制，窗口/光标在副屏时可用矩形算错，浮层被钳成窄缝或贴错位置；且 `place()` 后未 `lift()`，浮层作为顶层子件仍可能被页面后绘内容盖住。

## 改动清单

- `desktop_shared_menus.py`：
  - `AnchoredPanel.place_panel()` 锚点由输入卡顶改为 `host.icon_row` 顶（无 `icon_row` 时回退卡顶），面板底边＝图标行顶 − `SPACING['xs']`；place 相对 y 钳制 ≥0（Tk `place` 画不出 master 窗口外，负 y 会被整体裁掉）；`place()` 后 `lift()`。
  - `CandidatePopup.place()` 可视区改为 `monitor_bounds(top, 光标x, 光标y)`（光标所在显示器矩形）∩ 顶层窗矩形 ∩ 屏边距，不再用主屏宽高；保留下方优先／空间不足上翻／四边钳制；`place()` 后 `frame.lift()`。
- `desktop_shared_input.py`：布局期保存 `self.icon_row`；`_show_skill_card` 说明卡屏边界同步改用 `monitor_bounds`（副屏上不再被拽回主屏矩形）。
- `tests/test_shared_input_ui.py`：新增 2 条真实 Tk 几何回归（下述）。

## 回归测试（先红后绿）

- `test_icon_panels_bottom_sits_one_row_above_icon_row`：输入框贴窗口底部落定布局后，分别开 ✦／＋面板，以 `winfo_rootx/y` 实测断言面板底边 ≤ 图标行顶且间距 ≤ `SPACING['sm']`。改前红（底边悬在卡顶上方、与图标行隔整个文本区），改后绿。
- `test_candidates_clamped_to_cursor_monitor_not_primary_screen`：窗口移到主屏右缘之外并 patch `monitor_bounds` 模拟副屏矩形，输入 `/` 开候选浮层，断言浮层宽度 > `SPACING['md']*8` 且 `winfo_rootx` 锚在光标处（非被钳到窗口左缘）。改前红，改后绿。

## 探针证据（一次性脚本 `_probe_popups.py`，已删除）

- 改前：skill/add 面板底 791，输入卡顶 697、图标行顶 795——面板悬在文本区上方，与图标间隔 ≈102px（FAIL）。
- 改后：两面板底均＝图标行顶 −4px；候选浮层在窗内光标附近且 `winfo_containing` 命中自身（ALL PASS）。

## 范围与边界

- 状态页轮次头同步留待合入 master 时随合并提交完成（与 R3012/R3026 同口径）。
- `test_skills` 2 红为工作树缺嵌套 SKILL 仓库的既有环境限制（R3012 同源记录）；`test_multi_monitor_popups.py` 直跑时 `_Tip` 桩缺 `winfo_exists` 为既有桩兼容问题。两者均与本轮改动无关，未扩大范围修复。
