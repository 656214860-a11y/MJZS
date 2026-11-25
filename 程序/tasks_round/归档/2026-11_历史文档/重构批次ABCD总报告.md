# 重构批次 A+B+C+D 总报告（2026-10-22）

分支 `claude/project-handoff-f6eb50`，HEAD `f767e937`（R1841）。master 最新为 `a1e42b1b`（R1835）。分支未 push，也未合并。

## 结论

- 函数长度上限登记 `OVERSIZE_CAPS` 已清空：12 个超长函数全部拆到 150 行以内。
- 嵌套深度上限登记 `NESTING_CAPS` 已清空：深度为 6 的函数全部压平。
- 每一轮都是“差分测试先行”：旧实现取 HEAD 原文内嵌，先让旧实现自比为绿，再改写；改写后做变异检验，确认差分测试能变红。每轮的结果文件都注明了“断言未动”。

## 各轮清单

| 轮次 | 提交 | 内容 |
|---|---|---|
| R1816 | 51f1f224 | assets → `_AssetPage`；script_structure → `_ScriptStructurePage` |
| R1817 | cb78aa40 | writing → `_WritingPage` |
| R1818 | 87260694 | `_preparation_step` 改用参数对象 |
| R1819 | fcd30bc0 | 只补测试：三虎的重试与动画开关 |
| R1820–R1825 | ce34a0a4…eb66015b | 压平嵌套：flourish／open_cell、storage_summary、_tick_async_result、App.tick、run_batch、run_background |
| R1827／R1828／R1830 | 4155a11f／6a39edca／c7d3d3a1 | attach_controls、reference_wall.show、cloud_video.settings_window 改写成类 |
| R1831 | bfe59035 | send_message 的回调 `received` 提升为方法 |
| R1832 | c808e590 | content_box → `_ContentBox` |
| R1833 | def80a9d | install_window_placement 的辅助函数提到模块级（子进程差分测试） |
| R1834 | f973521f | asset_batch.show → `_AssetBatchWindow` |
| R1836 | 6a8e20bc | local_previs.show → `_LocalPrevisWindow` |
| R1840 | 6c599cb2 | open_flow_agent → `_FlowAgentLaunch` |
| R1841 | f767e937 | keyframe_comfy.show → `_KeyframeComfyWindow`，build 再切出两块 |

**缺号说明：** 1826、1829、1835、1837、1838、1839 被其他工作树领走。其中 R1826、R1829、R1835、R1837、R1838 已提交在 master 上。没有因领号而丢失的工作。

## 需要用户知道的事

1. **master 上的 Splash 回归（未修）。** master 的 R1788 误删了 `ui_widgets.Splash`。`启动漫剧制作助手.pyw` 第 54 行在 try/except 里引用它，导入失败会被静默吞掉，所以 master 上启动画面不会出现，也不报错。本分支已在 R1801 恢复（R1807 又补回漏掉的 `APP_NAME` 导入）。截至 `a1e42b1b`，master 仍然没有 `class Splash`。分支合并后自然修复；如果不合并，就需要在 master 单独补。建议再加一条守护：`.pyw` 引用的名字不得被死代码清理删除。
2. **分支合并到 master 仍在等用户决定。** 分支领先 master 39 个提交，没有 push，也没有合并。合并后需要在 master 更新 `project_status.md` 的轮次头，这样 `test_round_number_continuous` 才会转绿。它在分支上是预期的常驻红。
3. **一处有意的可见变化（R1836）。** HEAD 上，白模预演页“成果目录／Blender”那一行的 `StringVar` 会被回收，所以这一行一直是空的。改写成类后它能正常显示，并有单独的测试断言。
4. **既有的红灯（在 HEAD 原文上同样红，不是本批引入的）：**
   - `test_idea_chat.SavingTests.test_initial_brief_discovery_failure_is_visible_without_blocking_input`
   - `test_stage_wiring.AssetDetailRoutingTests.test_the_main_page_keeps_the_table_and_gains_the_entry`
5. **为配合改写同步过定位方式的测试**（断言一条未删、未放宽）：`test_asset_batch_settings_callers`、`test_request_freeze_entries`、`test_codex_skill_sync`。

## 拆分引入的回归及修复（R1843）

R1828–R1841 各轮结果文件写了“`--architecture` 通过”，但 `-k architecture`（按文件名筛全部架构测试）实际有 9 处红，都是这批改写引入的回归，上一棒报告“全部完成”时没有发现。R1843 已全部修复：

| 红灯 | 引入轮 | 原因 | 修复 |
|------|------|------|------|
| test_card_boundary：cloud_video／reference_wall／keyframe_comfy 三条 | R1830／R1828／R1841 | 测试按函数名找 Card 调用，函数改写成类以后找不到 | 测试改为按类定位（断言未动） |
| test_local_previs_json_boundary、test_project_context_boundary 各一条 | R1836 | 同上 | 改为按 `_LocalPrevisWindow` 定位（断言未动） |
| test_writing_publication_boundary | R1840 | 局部变量变成实例属性 | 期望串同步为 `self.project,self.stage`（断言未动） |
| test_complexity_ratchet：`_KeyframeComfyWindow` 639 行 > 600 | R1841 | 窗口类过长 | 拆出 `_KeyframeComfyRows`（列宽、勾选），不登记 |
| test_complexity_ratchet：`_FlowAgentLaunch.__init__`、`_ContentBox.__init__` 参数 10 > 7 | R1840／R1832 | 改写成类时照搬参数 | 分别用参数对象 `_FlowAgentRequest`、`*spec` 收拢 |
| test_complexity_ratchet：`IdeaChatMixin` 登记 1031 | R1840 | 方法迁出后没下调 | 下调到实际值 770 |
| test_unification_ratchet 第四项 | R1825 | `json.loads` 移入 `_run_claude_json`，台账身份含函数名 | 台账 point 改名，豁免理由不变 |

修复后 `-k architecture` 只剩预期常驻红 `test_round_number_continuous`。`test_skill_reference_injection`（父会话记为 R1830 基线即红）本轮 9 条全绿，未改它。教训：整理轮自检要跑 `-k architecture`，不能只跑 `--architecture`。

## 验证范围

- **本批跑过的：** 每轮跑了差分测试、相关模块测试和 `run_selftests.py --architecture`，Tk 测试一律在隐藏桌面运行。
- **没跑过的：** 完整安全全量（`--all --safe`）本批没有跑，建议合并前跑一次。
