# R1757：修复轮——窗口 <Configure> 后代控件事件不再触发整页重排，消除 R1751 起 test_ui_edges 卡死（RESIZEHANG2）

## 三问

1. **轮次类型**：修复轮（含全量基线验证待调度方执行）。
2. **测试跑了吗／三基线**：任务书窄命令已跑。默认冒烟 8/8；架构门禁未跑（任务书禁止）；全量未跑（任务书禁止），故三个基线未全部实测，不声明全绿。
3. **`project_status.md` 欠账少了吗**：没有。执行方按任务书不改状态页、不领号；本轮无新增欠账，未闭环历史欠账。

## 真根因（已验证部分与未证实部分）

- **已证实**：`LayoutMixin.watch_window_resize()` 把 `_on_resize_configure` 绑在顶层 `win` 上；Tk 的 bindtags 使该绑定收到所有后代控件的 `<Configure>`。本环境探针（包住 `Desktop._on_resize_configure` 记录事件来源）在原测试中记录 `descendant=132`，样本含 `.!frame2.!frame.!label3 64x23`、`.!sizegrip 15x15`、`.!frame.!canvas.!frame.…`，与调度方事件样本同类。原处理函数对非 `win` 事件不做来源判断，直接走 `fit_content()`。
- **本环境未复现**：原命令 `tests/test_ui_edges.py UiEdgeTests.test_frame_checks_follow_the_frame_state` 本机 1.2 s OK，未进入调度方真实环境的自激状态；因此“后代事件触发整页重排，再改子控件尺寸形成不收敛循环”的**完整因果在真实环境由确定性新用例与来源过滤验证**，本机只验证了前半段（后代事件确实进入处理函数）以及过滤后的行为。
- **与上次补丁的关系**：上次的 `_own_content_configure` / `_content_applied_*` 守卫针对“内容框同尺寸回喂”，不是本轮真根因。在临时进程里把它改成恒 `False` 后，它自带的用例 `test_layout_does_not_feed_on_its_own_content_resize` 失败（1 条），说明它对内容框同尺寸回喂仍有独立作用，故**保留**；它与本次问题并存，但单靠它不能阻止后代事件触发重排，也不是本轮成果。
- **上次新增的测试**保留原样（既有用例一条未改、断言未动）；只在同文件**追加**一条确定性回归用例。

## 改动清单

- `desktop_layout.py`：`LayoutMixin._on_resize_configure`（第 35 行）——事件来源不是 `None`／`win`／`canvas`／`content` 时直接返回；其余逻辑（窗口宽高去重、拖动合并、`fit_content`）不变。绑定点 `watch_window_resize()` 不动，生产路径仍是“拖动合并、松手补做”。
- `tests/test_window_resize_coalescing.py`：`import` 增加 `tkinter.ttk`；追加 `test_descendant_configure_does_not_trigger_page_relayout`，构造 `SimpleNamespace(widget=后代 ttk.Label)` 的 `<Configure>` 喂给处理函数，断言不触发重排；并正向喂 `widget=self.win`、宽高各 +1，断言会重排。无 `skipTest`。
- 未改 `desktop.py`（1420 行）；`desktop_layout.py` 321 行，未突破 1500 行棘轮；未新增模块；未改 `project_status.md`、`AGENTS.md`；未读 `private\`、`.env`。

## 先红证据

- 在**未改** `desktop_layout.py` 过滤前跑新用例：`AssertionError: 2 != 0 : 后代子控件 .!frame2.!frame2.!canvas.!frame.!label3 的 <Configure> 触发了整页重排 2 次`（断言在 `tests/test_window_resize_coalescing.py:264`）。
- 已改后同一文件 7/7 OK（5 条既有 + 上次 1 条 + 本轮 1 条）。

## 变异验证

- 在临时探针进程内把 `_on_resize_configure` 换回无来源过滤版本（含上次守卫），单独跑新用例：`failures=1 errors=0`，报 `2 != 0`（少了来源过滤仍红）；最终版测试代码复做一次，结果同上（`MUTATION-FINAL failures=1`）。
- 再把上次守卫也失效后跑新用例：`failures=1 errors=0`，同样 `2 != 0`。
- 恢复源文件后用一条全新进程跑整个 `tests/test_window_resize_coalescing.py`：`Ran 7 tests ... OK`。
- 探针文件 `_rz3_probe.py` 已删除，没有留在工作树。

## 事件来源探针（本环境，未修复基线）

- 包住 `Desktop._on_resize_configure` 记录来源，跑任务书那条 `test_ui_edges` 原命令：`total=148`，其中 `descendant=132`、`content=6`、`win=2`、`canvas=8`；样本 `.!frame2.!frame.!label3 64x23`、`.!sizegrip 15x15`、`.!frame.!canvas.!frame 154x799`，与调度方真实环境样本同型。
- 含义：约 89% 的处理函数入口来自后代控件；在未加过滤时这些入口都会走到 `fit_content()`，而整页重排又会配置子控件（`wraplength`／`bindtags`／尺寸），提供下一批后代事件。
- 本机这条命令 1.2 s OK，说明本机布局在有限次后收敛；真实环境的持续供给条件更强（调度方已稳定复现）。因此本机探针只证明“入口来源”，不能证明“必然不收敛”；不收敛性由新用例的先红／后绿与真实性证据共同支撑。

## 实际命令计数

| 命令 | 结果 | 耗时 |
| --- | --- | --- |
| `python -B tests/test_window_resize_coalescing.py` | 7/7 OK | 18.5 s（最终复跑） |
| `python -B tests/test_ui_edges.py UiEdgeTests.test_frame_checks_follow_the_frame_state` | 1/1 OK | 5.0 s（最终复跑） |
| `python -B tests/test_page_paint_metric.py` | 5/5 OK | 5.6 s |
| `python -B smoke_test.py` | 通过 8／失败 0 | 0.3 s |

任务书要求“不跑 `run_selftests.py`／`--architecture`／全量／`--affected`”，均未运行；调度方验收时复跑原命令即可。

## 断言未动声明

既有测试断言一条未改、未弱化、未跳过。新增用例只有新断言；上次新增的用例完整保留。

## 需裁决事项

1. **新用例设置 `self.held = False`，但 `setUp` 装了拖动判定桩**：用例正向部分依赖 `ResizeCoalescer` 对 `win` 的合并行为；在本环境通过。调度方真实环境复跑若仍不通过，先检查是否被本地拖动探测判为未拖动；这不影响生产过滤逻辑。
2. **本机未复现真实卡死**：任务书 A 项的真实环境 15 秒 OK 只能由调度方在主工作区复跑确认；本机已用事件来源探针与变异红证据证明过滤有效，但不替代真实环境验收。
3. **三基线未全测**：按任务书禁用清单，架构门禁与全量未跑；结果文件不写成通过，需调度方验收时补。

## 独立验收（Claude，真实环境，车道 lane_rz3 内直接运行，补丁未打到主树）

- 复现与根因：主树 master 上原命令 `timeout 90` 被杀；三次 `sys._current_frames()` 采样均停在 `update()`→`ui_theme.place`→`update_idletasks`→`desktop_layout.run`→`_fit_content_now`；调用计数探针 10 秒内 `_on_resize_configure` 6695 次，事件来源多为后代控件。上一次修复（仅内容框同尺寸回喂守卫）在真实环境仍超过 120 秒，已否决并带证据重派；本次执行方在其沙箱无法复现，机制由确定性用例与本验收的真实环境复跑共同证明。
- 真实环境：`test_frame_checks_follow_the_frame_state` 2.3 秒 OK（改前 >120 秒）；`test_window_resize_coalescing` 7/7；`smoke_test` 8/8。
- 变异：`git apply -R` 回退生产修复后，原命令再次 `timeout` 退出码 124；两条新用例均红（`2 != 0`、`1 != 0`）；还原后哈希一致、两条均绿。
- 消费方：`run_selftests -k idea_chat` 在补齐车道环境后 ALL PASSED、0 红；首次 5 个 idea_chat 文件红及架构门禁 2 条红（`test_agents_md`、`test_skill_reference_injection`）均因车道缺被 gitignore 的 `基准历史.json` 与内嵌技能包内容，补齐后重跑 24/24 OK。架构门禁 375 条，除上述 2 条环境红外全绿。
- `-k test_ui_edges window_resize desktop_startup_perf page_paint_metric idea_chat` 合并运行的首轮：292 条、5 个文件有红，全部为上述环境缺文件所致，已按上条复核。
- 范围：只改 `desktop_layout.py`（+14，321→348 行）与 `tests/test_window_resize_coalescing.py`（+52）；`desktop.py` 仍 1420 行；无新增模块。
- 例外：本轮验收前我曾在主树临时应用过一次补丁做对照，已用 `git apply -R` 撤回并确认主树干净；此后验收均在车道内进行。
- 未决：执行方 `_own_content_configure` 守卫（内容框同尺寸回喂）并非本次卡死根因，但有独立变异用例，保留。
