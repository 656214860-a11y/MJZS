# tasks_round_4452_result — FIX-FULLSAFE-S03-AND-AUDIO-TESTS：三测试文件 7 条既有红清零
<!-- round-evidence: {"commit_base": "1abd6d878", "credential_hits": 0, "evidence_sha256": "41133ce4a9586976", "exit": 0, "failed": 0, "passed": 75, "round": 4452, "tests": "run_selftests.py -k ui_edges_autopilot ui_edges_controls ui_edges_tables"} -->

## 三问

1. 本轮类型：§3.2 修复轮（任务卡 FIX-FULLSAFE-S03-AND-AUDIO-TESTS，W2）。六条为 R4346/R4380 有意契约变更的测试同步，一条为真实产品回归的最小修复（`ui/desktop_page_nav.py`）。
2. 测试：跑了。卡面两条验收命令均退出码 0（见下「验收」节尾部原文）；另补跑默认冒烟 9 项全过。三基线数见末节。
3. 欠账：无新增欠账；基线 1abd6d878 上 ui_edges_autopilot／controls／tables 合计 7 条既有红清零（75 用例 0 红）。

## 改动文件

- `tests/test_ui_edges_autopilot.py`：+13/−4
- `tests/test_ui_edges_controls.py`：+60/−32
- `tests/test_ui_edges_tables.py`：+22/−28
- `ui/desktop_page_nav.py`：+19/−0（`_sync_shared_input` 内）
- 本结果文件

## 改前 7 红（基线 1abd6d878 实测）

1. `test_ui_edges_autopilot:1030` `test_per_line_tts_stop_and_line_progress`：len(states) 4 != 2
2. `test_ui_edges_autopilot:2188` `test_adopt_skips_adopted_without_confirm`：找「手动采用分镜」按钮 IndexError
3. `test_ui_edges_controls:98` `test_file_table_click_rules`：len(storyboard_tables) 0 != 2
4. `test_ui_edges_controls:710` `test_renumber_shots_button_fixes_script_order`：找「重排镜头编号」按钮 0 != 1
5. `test_ui_edges_tables:703` `test_the_action_row_stays_inside_the_visible_canvas`：找「手动采用分镜」按钮 [] is not true
6. `test_ui_edges_tables:893` `test_a_real_page_keeps_its_height_after_the_storyboard_page_is_put_away`：growable_extra(storyboard) 0 not > 0
7. `test_ui_edges_tables:538` `test_same_page_rebuild_keeps_scroll_offset`：canvasy(0) 210.0 != 316.0（delta=2）

## 7 项根因与契约变更逐条说明

1. **autopilot:1030（测试同步，R4346 契约）**：`domain/tts_api.py:677-681` 的 `run_lines` 在批次开始就把整批句子先落盘到时间轴 manifest，未发句预记 `'state':'failed','file':''`。断言由「停止后 2 条全 ok」同步为「4 条：前 2 条 ok、后 2 条 failed（非 sending、非 ok）」；后半段「续跑 4 条全 ok、前两句沿用不重复扣费」的断言原样保留，停止与续跑防重复扣费的检验未弱化。
2. **autopilot:2188（测试同步，R4380 契约）**：R4380（7b2354c9e）把 03 初步分镜页改版为单编辑器、删除顶部「手动采用分镜」按钮，动作收进编辑器右键菜单，菜单项调用的就是页面方法 `adopt_selected()`（`ui/storyboard_files.py:938`）。改驱动 `d.storyboard_editor_page`：置 `active_board_json=None`（`_target_boards` 按 storyboard_files.py:932-936 回落为目录里全部分镜 JSON，真实等价于文件栏停在非分镜文档上）后调 `adopt_selected()`。已采用分镜跳过、不弹确认、`ui_settings.json` 只记新采用的原断言全部保留。
3. **controls:98（测试同步，R4380 契约）**：03 页不再摆文件表后，同一套点击契约（`bind_row_toggle` 文本格勾选＋`CellHover` 链接格＋`CellImages` 盖图）在 04 首帧页镜头状态表仍在用，用例整体挪到该页：文本格「内容」列单击勾/再点取消；「图片文件」格盖着缩略图时单击只点亮不勾不开（04 页现行差异契约，新增一条断言）；「未勾先勾再打开」经 `cell_images.view((row,'#5'))`——这是双击与右键「查看」共用的同一条打开路径（`event_generate` 造不出 Tk 的 Double 事件）；「提示词」列链接格打开提示词窗口。勾选/取消/未勾先勾/已勾不取消四类不变量全部保留。
4. **controls:710（测试同步，R4380 契约）**：「重排镜头编号」按钮同样撤进右键菜单，菜单项调 `renumber_shots()`（storyboard_files.py:893-918）。改驱动 `page.renumber_shots()`；`storyboard_files.confirm` 打桩、同步 `d.async_`、确认框文案「镜头编号」、EP002 重排后编号连续、「无需重排」不再弹框等断言全部保留。
5. **tables:703（测试同步，R4380 契约）**：03 页动作行已撤；「贴底动作行＋内容框让高」的同款布局在 04 首帧页仍在用（target_row/actions_row `pack(side='bottom')`，内容框最后填充）。把分镜堆到 16 镜让表格超高后，按该页「手动制作首帧」按钮测同一几何不变量（按钮行不顶出画布上沿、不被挤出可视区）。
6. **tables:893（测试同步，R4380 契约）**：两个整页缓存页（初步分镜／结构剧本）现均为单编辑器、无可伸缩表格，`growable_extra` 前提无法再靠真页表格满足。为保住「收进缓存的页里登记的表格不许从当前页扣高」这条不变量的真实路径验证，在收进缓存前的初步分镜页上登记一张真实 Treeview（`self.table` 与 `auto_height` 同一 `register_growable` 口径），换到分镜定稿页、拉矮窗口后断言 scrollregion 高度只按当前页内容计算。
7. **tables:538（产品回归，根因修复于 `ui/desktop_page_nav.py`）**：真因链——`SharedStageInput` 输入框行高自适应排在 `after_idle`（desktop_shared_input.py `_fit_input_height`，按显示行数量）；换页瞬间输入框真实宽度还没传下来（`width=1`），占位提示折出满档 10 行（`TEXT_ROWS['xl']`），dock 高 250px；同一页第二次重建在真宽下算出 4 行、dock 缩到 136px。dock 是画布列底部共享件（desktop.py:337-382 `input_dock`），同一页两建量出不同 dock 高 → 画布视口 591→705 → `restore_scroll` 把已存的 316px 偏移按新 scrollregion 夹到 210（desktop_layout.py:205-212 `_pending_scroll_restore` 只消费一次，补不回去）。修复在 `_sync_shared_input`：输入框宽 ≤40 时先撤掉 `set_stage` 排下的那波刷新，并给输入框绑一次性 `<Configure>` 守卫，真实宽度一落定就补一轮合并刷新，dock 高度按真宽收口。几何探针实证：修复前两建 `dock=250/vh=591` vs `dock=136/vh=705`；修复后两建均为 `dock=136 ih=4 vh=705`，断言通过。首版修复（after_idle 轮询 8 次）失败原因：几何传播慢于 8 轮 idle，轮询兜底仍在 width=1 下重算了 10 行，已按规则 32 补证据后改为事件驱动。
   - 测试断言未动（仍断言同页重建 `canvasy(0)` 差 ≤2px、换页后回 0）。

## 验收

工作目录 `程序/`。

命令一：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k ui_edges_autopilot ui_edges_controls ui_edges_tables`（退出码 0）尾部原文：

```
  test_ui_edges_autopilot#2     16 条    69.6 秒

共 75 条用例，70.7 秒；0 个文件有红
最慢 6 路工作单元：
  test_ui_edges_autopilot#2    69.6 秒 / 16 条
  test_ui_edges_autopilot#3    65.4 秒 / 14 条
  test_ui_edges_tables#2       62.0 秒 / 10 条
  test_ui_edges_controls       59.2 秒 / 18 条
  test_ui_edges_autopilot#1    31.9 秒 / 6 条
  test_ui_edges_tables#1       24.5 秒 / 11 条
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新：D:\漫剧制作助手\.git\selftest-incremental.json
最近 5 轮自检中位基线：70.7 秒

ALL TESTS PASSED
```

命令二：`..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（退出码 0）尾部原文：

```
----------------------------------------------------------------------
Ran 708 tests in 389.905s

✅ 架构治理测试：tests/architecture
OK
```

补充：`..\..\..\..\运行环境\Python\python.exe -B smoke_test.py` 默认冒烟「通过：9 项 / 失败：0 项 / ✅ 冒烟测试通过」，退出码 0。

## 三基线数

- 默认冒烟：实测 9 项通过 0 失败（分层基线 `smoke_checks_expected=8` 为登记值，当轮实跑输出「通过：9 项」）。
- 架构门禁：当轮实测 708 用例、失败集合为空（`tests/architecture` 全 OK；分层基线下界 `architecture_gate_files_min=123` 文件）。
- 全量回归欠账（`dev.py debt` 实读）：上次全量 R4264；最新 R4449；其间改过源码的轮次 71（门禁线 8）；本分支提交不累计主干口径。后台自动全量备注「环境不允许派生工作进程，未能测量」——是环境限制非测试失败。

## 未验证项

- `_sync_shared_input` 在窄宽下撤掉的那波刷新同时带候选扫描；`<Configure>` 补刷会把扫描一并做掉，未见功能回归（75 用例全绿），但隐藏桌面下不做端到端弹层验证。
- 输出里的 `invalid command name "...start_update_check/start_account_renewal"` 噪音为既有模式（win.destroy 后滞留 after 回调），非本轮引入。
- 全量 `--all --safe` 未跑（分支轮不强制；欠账口径见上）。
