# R4005 结果：文件面板文件名完整显示（任务书 L4-U3）
<!-- round-evidence: {"commit_base": "379292a3", "credential_hits": 0, "evidence_sha256": "8fb51d1d03e99435", "exit": 0, "failed": 0, "passed": 136, "round": 4005, "tests": "run_selftests.py -k files_panel"} -->

## 三问

1. **本轮属于哪种类型**：修复轮（任务卡 L4-U3，L4-B4）。
2. **测试跑了吗、三个基线**：跑了。默认冒烟 9/9 通过；架构门禁 `--architecture` 实测 684 条全绿、失败集合为空（中途曾因类行数棘轮与未登记同层依赖边各红 1 次，均已修复后复验）；全量 `--all --safe` 按本卡禁令未运行（`--safe` 同属禁令）。
3. **欠账少了吗**：少了——「属性列须横向滚动访问」的旧交互缺陷消除，文件名在两档窗口下都能完整读出。新发现一条**预存在**欠账（见「已知遗留」），与本卡无关。

## 改动的文件

- `程序/ui/desktop_files_panel.py`：`_fit_script_width` 重写——sizer 仍按最长文件名驱动面板请求宽（保住 `test_file_list_width_fits_longest_filename` 的回落契约），但列隐藏与省略预算改按 `tree.winfo_width()` **实宽**算（窄窗时停靠列会被内容区挤到请求宽之下）；放不下的属性列按 meta→size→kind→mtime 整列 `displaycolumns` 隐藏；实宽缺口一次性补进 sizer、靠 `<Configure>` 收敛；`script_tree` 增加 `<Configure>` 去抖重算（R5）；`_apply_columns` 把 name 列 `minwidth` 从 184 收为 `SCRIPT_NAME_MIN_WIDTH`（96），否则预览列＋minwidth 必然顶出横向滚动。
- `程序/ui/desktop_files_panel_index.py`：`_full_labels` 记录各行完整显示名（供量宽与省略还原）；`_apply_name_labels`/`_elide_label` 放这里（`ProjectFilesPanel` 类行数棘轮 600 上限——拆出去后实测回落，类行数从 605 降到 566）；测宽函数由调用方注入 `measure_text_width`，不产生 `index→ui_popup` 新同层依赖边；`script_row_details` 悬停提示补「时长／分辨率」列内容。
- `程序/ui/desktop_files_panel_filters.py`：`_refresh_media_meta` 后补 meta 时同步 `script_row_details`；顺既有 `filters→index` 边回导 `SCRIPT_NAME_CELL_PAD`，避免 `panel→index` 新同层依赖边。
- `程序/tests/test_files_panel_stages.py`：新增 `FilenameDisplayTests`（T1–T6＋共用种文件/收尾辅助）；`test_metadata_columns_use_index_fields_and_keep_filename_id` 末尾同步契约断言（见「契约同步」）。

## 改前的失败输出（改前红，`logs/l4u3_red.log`）

- T1 `test_long_filename_fully_visible_at_wide_window`：`AssertionError: 184 not greater than or equal to 367 : 文件名列可见宽 184 < 文字宽 359＋留白`
- T2 `test_long_filename_middle_elided_at_narrow_window`：`AssertionError: '…' not found in '面板文件名完整显示样例素材ABCDEFGHIJKLMNOPQR_0001.png'`
- T3 `test_table_never_scrolls_horizontally`：`AssertionError: 0.5857558139534884 != 1.0 within 3 places : 1280x800`
- T4 `test_no_column_half_visible`：`AssertionError: 688 not less than or equal to 409 : 1280x800：显示列合计宽 688 超出表格可见宽 407`
- T5 `test_tooltip_keeps_full_name_and_hidden_columns`：`AssertionError: '2.5s · 320×180' not found in '悬停样例.mp4 · 资产 · 2.0 KB（2048 字节）· 2026-11-17 08:30:00\n05资产管理/assets/悬停样例.mp4'`
- T6 `test_elided_row_opens_the_full_filename`：`AssertionError: '…' not found in '…_0001.png' : 前置：该行应处于省略显示`

## 每条验收命令的结果（验收命令同 U1，日志名 logs\l4u3.log）

| 命令 | 结果 |
| --- | --- |
| `PY -B scripts\gui_hidden.py logs\l4u3.log . -- PY -B -m unittest tests.test_files_panel_stages -v` | 退出码 0；`Ran 128 tests`，日志末尾 `OK`（含 FilenameDisplayTests 18 条全绿） |
| `PY -B smoke_test.py` | 通过 9 项 / 失败 0，✅ 冒烟通过 |
| `PY -B smoke_test.py --affected desktop_files_panel` | 选中 6 个测试文件（test_files_panel、test_files_panel_stages、test_latent_defects_r2175、test_writing_page_controller、test_writing_page_services、test_writing_unconfirm），`ALL TESTS PASSED`（191 秒），退出码 0 |
| `PY -B smoke_test.py --architecture` | `Ran 684 tests`，`OK`，失败集合为空（`logs/l4u3_arch2.log`） |

补充验证（非点名但相关）：`tests.test_files_panel` 8/8 OK（`test_file_list_width_fits_longest_filename` 宽随最长名增长且删后回落、Esc/收起/停靠路径均过）；`tests.architecture.test_text_measure_boundary`、`test_complexity_ratchet`、`test_layer_relations` 定向复验全绿。

## 契约同步说明（AGENTS §2.4，R4 要求的有意契约变更）

`test_metadata_columns_use_index_fields_and_keep_filename_id` 原第 498–501 行：

```python
self.assertTrue(panel.script_list.horizontal_scrollbar.winfo_ismapped())
tree.xview_moveto(1)
self.win.update()
self.assertGreater(tree.xview()[0], 0, '字段列须可横向滚动访问')
```

这正是本卡 R4「表格不再需要横向滚动」要替换的旧契约。已按 §2.4 同步为新契约断言（`xview()==(0.0,1.0)`＋隐藏列内容进 `script_row_details`），同用例其余断言（列标识五元组、表头文案、行 values、组归属、面板宽 ≤ 内容区一半、details 含文件名/字节数/修改时间）一条未动。除此之外不删除、不跳过、不放宽任何断言。

## 任务卡逐条对照

- R1：隐藏顺序 meta→size→kind→mtime，整列 `displaycolumns`，不许半露（T4 实测各显示列右边缘不超可见区）。
- R2：只剩 name 仍不够宽时中间省略，保留开头 ≥8 字符＋扩展名，「…」居中（T2）。
- R3：悬停提示 `script_row_details` 含完整文件名＋类型/大小/修改时间/时长／分辨率（T5）。
- R4：横向滚动范围恒 `(0.0, 1.0)`（T3，两档窗口实测）。
- R5：`<Configure>`（窗口缩放）去抖重算；刷新/换阶段走 `_finish_index_render`→`_fit_script_width` 重算。
- 接口契约：列标识不变；行 iid 仍是项目相对路径（T6：省略行「打开」拿到完整文件名对应文件）；`SCRIPT_PANEL_MAX_WIDTH`/`MAX_SHARE` 未动；文件索引数据结构未动。
- 测宽唯一入口：省略与量宽全走 `ui_popup.measure_text_width`（`index→ui_popup` 会新增未登记同层边，故测宽函数由 `_fit_script_width` 注入）。

## 已知遗留（范围外，如实记录）

- `test_files_panel_stages` 与 `test_files_panel` 同进程连跑（stages 先）时，`test_collapse_button_outside_press_and_escape` 的 `Esc 收起` 断言失败（`_open` 仍 True）；`test_files_panel` 单跑、`--affected` 分片跑均过。**在完全未改动的基线代码上按同样顺序复现同样失败**（`logs/l4u3_esc_base.log`），属分支预存在顺序敏感问题，与本卡无关，未处置。
- 棘轮提示 LR-09/LR-10 实测 59 < 基线 60（建议下调 `层间合规清单.json`）：既有漂移，该文件不在本卡允许修改范围，未动。
- 全量 `--all --safe` 本卡禁止，欠账口径以 `full-safe-receipts.json` 既有凭据为准。
