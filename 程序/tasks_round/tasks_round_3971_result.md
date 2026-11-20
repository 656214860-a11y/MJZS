# R3971 结果：项目文件面板阶段图标列恢复可见（L4-U1）

<!-- round-evidence: {"commit_base": "b3544e90", "credential_hits": 0, "evidence_sha256": "026e73b8802fb12c", "exit": 0, "failed": 0, "passed": 102, "round": 3971, "tests": "run_selftests.py -k files_panel"} -->

## 1. 三问

- 轮次类型：修复轮（§3.2）。P0 回归 L4-B1：停靠面板右缘阶段图标列被压成 1px 宽。
- 测试跑了吗、三个基线过了吗：
  - 默认冒烟：9/9 通过（当轮实际项数 9，输出「通过：9 项」）。
  - 架构门禁：当轮实际 684 条。首跑 1 失败（test_round_number_continuous，与本卡无关，见 §5）；把车道 `git rebase master` 到主干头 b3544e90 后复跑，684 条全 OK、退出码 0（logs\smoke_arch3.txt）。注：经 `2>&1 | Tee | Select` 管道复跑时控制台显示全绿但工具侧报退出码 1——PS 5.1 把 unittest 逐条写到 stderr 的行转成 NativeCommandError 记录造成的管道假象；不带管道直跑确认 python 退出码为 0。
  - 全量回归：未跑（任务书规定执行者不跑，合入后由主控按欠账规则补跑，以 `full-safe-receipts.json` 为准）。
  - 定向：`tests.test_files_panel_stages` 全模块 94 条 OK；`smoke_test.py --affected desktop_files_panel` 选中 6 个测试文件、全过。
- 欠账少了吗：少了。修掉 P0 缺陷 L4-B1（阶段图标列恢复可见），未新增欠账。

## 2. 改动文件

| 文件 | 改动 |
| --- | --- |
| `ui/desktop_files_panel_filters.py` | `_build_stage_rail()`：齿轮设置钮改到列顶（pack 先于滚动画布，原位置落在滚动条与画布之间的中间腔）；外框 `stage_rail` 钉固定宽＝图标内容宽＋竖滚动条宽并 `pack_propagate(False)`，画布在其中填满、请求宽不再参与外层几何协商（与 R3214「画布钉 1px」等价切断振荡回路）。 |
| `tests/test_files_panel_stages.py` | `test_scroll_rail_requests_minimum_width_without_geometry_feedback`：把「画布宽度等于 1」这一条断言换成任务卡 T1＋T2 断言（见 §3）。用例其余断言与其他用例一条未动。 |
| `tasks_round/tasks_round_3971_result.md` | 本文件。 |

`tk_test_support.py` 未改：本卡需要的「定窗口大小」「取控件宽度」用现有 `win.geometry()` 与 `winfo_*` 即可完成，未新增辅助函数。

## 3. 测试契约变更说明（任务卡 T3 要求写明）

- 改了哪一行：`tests/test_files_panel_stages.py` 原第 99 行 `self.assertEqual(int(panel.stage_rail_scroller.canvas.cget('width')), 1)`。
- 为什么：R3214 为修窄窗抖动把画布请求宽钉成 1px，该断言把「画布宽＝1」当成期望固定下来——这正是任务书 §2.2 认定的缺陷本身（图标列被压到 1px、全部按钮不可见）。换成 T1（1280×800 与 880×600 两档窗口下「全部」＋13 个阶段钮＋资料库钮实际宽 ≥ 请求宽且已映射）和 T2（880×600 连续泵 10 次文件表高度不变）。其余断言 `assertGreater(stage_rail.winfo_width(), 1)` 保留原样。
- 界面元素可见性变化（L4-D6 要求写明）：齿轮钮（设置素材库目录）原 pack 在滚动条与画布之间的中间腔，改动后固定在图标列顶行——仍然可见、仍只出现一次，只是从「中缝顶部」移到「列顶」。

## 4. 验收命令结果

| 命令 | 结果 |
| --- | --- |
| `PY -B scripts\gui_hidden.py logs\l4u1.log . -- PY -B -m unittest tests.test_files_panel_stages -v` | 退出码 0；94 条全过，日志末尾 `OK`（91 秒） |
| `PY -B smoke_test.py` | 9/9 通过 |
| `PY -B smoke_test.py --affected desktop_files_panel` | 选中 6 个测试文件（test_files_panel、test_files_panel_stages、test_latent_defects_r2175、test_writing_page_controller、test_writing_page_services、test_writing_unconfirm），ALL TESTS PASSED |
| `PY -B smoke_test.py --architecture` | 首跑 684 条 1 失败（与本卡无关，见 §5）；rebase 到主干头后直跑复跑：684 条全 OK（351.8 秒），`$LASTEXITCODE=0`，末尾 `OK`＋「✅ 架构治理测试：tests/architecture」（logs\smoke_arch3.txt） |

## 5. 与本卡无关的架构门禁失败与处置

- 首跑 `--architecture`：684 条中唯一失败 `test_round_number_continuous`（`Lists differ: ['主干状态轮次未紧接已合入结果']`）。原因：本车道从任务书车道的未合入尖端 4968a665 切出，该基点 `project_status.md` 写「当前轮次：3970」而基点树里最新结果已是 3970，连续性要求 3971——基点本身不自洽，与本卡改动无关。
- 处置：按 runbook §12 车道交付前 `git rebase master`（主干已推进到 R3976 合并轮 b3544e90，状态页 3977＝3976+1 自洽）把工作树基点移到主干头；功能分支不改状态页。复跑结果见 §4。

## 6. 改前失败输出（先红后绿证据）

`PY -B scripts\gui_hidden.py logs\l4u1_red.log . -- PY -B -m unittest tests.test_files_panel_stages.StageRailTests.test_scroll_rail_requests_minimum_width_without_geometry_feedback -v`（退出码 1）：

```
FAIL: test_scroll_rail_requests_minimum_width_without_geometry_feedback (tests.test_files_panel_stages.StageRailTests.test_scroll_rail_requests_minimum_width_without_geometry_feedback)
R3971（任务书 L4-U1）：阶段图标列整列可见，且文件表高度不随刷新振荡。
AssertionError: 1 not greater than or equal to 34 : 1280x800: .!frame2.!frame.!frame.!frame.!frame.!canvas.!frame.!secondarybutton 实际宽 1 < 请求宽 34
Ran 1 test in 5.112s
FAILED (failures=1)
```

改后同一用例 ok；整模块 94 条 OK（logs\l4u1.log）。

## 7. 已提交

- 提交命令：`PY -B scripts\dev.py commit -m "R3971: 项目文件面板阶段图标列恢复可见" --agent Devin ui/desktop_files_panel_filters.py tests/test_files_panel_stages.py tasks_round/tasks_round_3971_result.md --tests files_panel`
- 提交号：见 `tasks_round/evidence/R3971.json` 与 git log（结果文件与提交同批写入）。
