# R4587 删除左上角重复项目图标并同步上移对齐左右图标（REQ-UI-SIDEBAR-1）
<!-- round-evidence: {"commit_base": "f2004961a", "credential_hits": 0, "evidence_sha256": "c9972c0ace769b08", "exit": 0, "failed": 0, "passed": 18, "round": 4587, "tests": "run_selftests.py -k desktop_compact_layout sidebar_project_title"} -->

- **轮次类型**：3.1 功能轮（文档先行更新 `docs/specs/05_UIUX与交互规范.md` §13 `REQ-UI-SIDEBAR-1`，随后改码与测试）。
- **测试与三个基线**：
  1. 默认冒烟基线：`python -B smoke_test.py` — **9/9 通过，0 失败**（含 `scripts/gui_hidden.py --probe` 隐藏桌面自检）。
  2. 架构门禁：`python -B smoke_test.py --architecture` — **714/714 通过，0 失败**（改后零新增违规）。
  3. 全量回归与欠账：按 `scripts/dev.py debt`（`full-safe-receipts.json` 为唯一权威），上次全量 R4264（主干累计源码轮次 127）；本轮在功能分支 `remove_top_project_icon` 执行，未改动主干，未运行 `--all --safe`。
  4. 定向与先红后绿：先改测试跑 `run_selftests.py -k desktop_compact_layout` 稳定复现 **8/15 红**；改码后 `run_selftests.py -k desktop_compact_layout files_panel sidebar_project_title ui_batch3_shell ui_theme project_open project_rename_reconcile project_switch_guard` **9 文件 / 352 条全通过（0 红 0 跳）**，`test_static_names` **8/8 通过**。
- **欠账变化**：本轮零新增欠账，删除 122 净行数冗余项目二级列代码；历史主干全量欠账保持原样。

## 改动摘要

1. **文档先行**（`程序/docs/specs/05_UIUX与交互规范.md` §13 `REQ-UI-SIDEBAR-1`）：移除左上角重复「项目」主图标与二级图标列约定，明确顶部直接放当前项目胶囊、下方导航图标依次上移、右侧文件入口与 13 枚阶段文件图标同步上移并与左侧阶段图标保持同一高度对齐。
2. **侧栏项目区精简**（`程序/ui/desktop_sidebar_project.py`、`程序/ui/desktop_project_pages.py`、`程序/desktop.py`）：
   - 删除 `host.project_button` 与只由其展开的 4 枚重复二级图标（`ExpandIconColumn`、`sidebar_expand`、`project_group_buttons`、`project_new_button`、`project_open_button`、`project_buttons` 及 `toggle_project_expand`/`open_sidebar_expand`/`close_sidebar_expand`/`sidebar_expand_outside`）；原分组筛选（全部／在制作／已完成）与「+ 新建项目／打开目录／项目管理…」全部由紧接其下的悬停宽项目卡片（`ProjectNameList`）承载。
   - `host.project_name_list` 顶格置于 `host.project_block` 上沿，分隔线与全部导航图标（01–14、设置、会员账户）自然依次上移。
   - 保留 `ProjectPagesMixin._sync_project_group_styles` 兼容空实现（既有项目单测引用），删除死方法 `_close_sidebar_expand` 与未使用导入。
3. **弹层锚点与右侧对齐加固**（`程序/ui/desktop_page_nav.py`、`程序/ui/desktop_expand_column.py`）：
   - `_post_project_picker` 在无 `project_button`／`project_group_buttons` 时锚定到常驻的 `project_name_list.trigger`。
   - `align_stage_rows` 增加监听 `nav[PAGE_OF['script']]` 的 `<Configure>`，确保左侧首项阶段图标垂直位姿变化时右侧 13 枚阶段文件图标即时同步重算。

## 测试契约变化（AGENTS §2.4）

- `程序/tests/test_desktop_compact_layout.py`：
  - 将原断言 `project_button` 与项目二级列的 4 处用例同步为新契约：验证 `project_button`/`_project_expand_column` 已删除、`project_name_list` 顶格贴近 `project_block` 上沿、悬停宽项目卡片驱动分组筛选与「+ 新建项目／打开目录／项目管理…」、项目选择层锚定到 `project_name_list.trigger`。
  - 新增真实 Tk 四档窗口（`1280×900`、`942×1032`、`800×600`、`990×632`）及切离/切回非生产页后的几何对齐断言，核验右侧 `files_button` 与全部 13 枚阶段文件图标与左侧阶段图标垂直中心偏差 ≤ 1px。

## 先红后绿与实测几何证据

### 改前失败输出（`run_selftests.py -k desktop_compact_layout`）

```text
  test_desktop_compact_layout    15 条    15.2 秒  ✗ 8
- test_header_sidebar_and_file_area_remain_visible_after_shrink_and_grow (×4 sizes): AssertionError: True is not false (hasattr(d, 'project_button'))
- test_project_icon_buttons_are_compact_rail_controls: AssertionError: True is not false (hasattr(d, 'project_button'))
- test_sidebar_popup_clamps_to_anchor_monitor: AssertionError: 2532 != 2516 within 2 delta (16 difference)
- test_project_list_height_clamps_and_three_widths_fit: AssertionError: 38 not less than or equal to 1
- test_top_project_icon_removed_and_right_file_icons_shift_up_aligned: AssertionError: True is not false : 左上角重复项目图标应已删除
```

### 隐藏桌面真实 Tk 几何对照（相对窗口客户区顶 `win_y`）

| 窗口尺寸 | 改前 `project_block` / `pnl` / `nav[0]` / `files_button` / `stage[script]` | 改后 `project_block` / `pnl` / `nav[0]` / `files_button` / `stage[script]` | 上移量 & 13 阶段最大偏差 |
| --- | --- | --- | --- |
| `1280×900` | `block=(8,96)` `pnl=(52,52)` `nav0=(130,40,c=150)` `fbtn=(133,34,c=150)` `sb0=(130,40,c=150)` | `block=(8,52)` `pnl=(8,52)` `nav0=(86,40,c=106)` `fbtn=(89,34,c=106)` `sb0=(86,40,c=106)` | 上移 **44px**，偏差 **0px** |
| `942×1032` | 同上 | 同上 | 上移 **44px**，偏差 **0px** |
| `800×600` | `block=(8,90)` `pnl=(46,52)` `nav0=(124,34,c=141)` `fbtn=(127,28,c=141)` `sb0=(124,34,c=141)` | `block=(8,52)` `pnl=(8,52)` `nav0=(86,34,c=103)` `fbtn=(89,28,c=103)` `sb0=(86,34,c=103)` | 上移 **38px**，偏差 **0px** |
| `990×632` | 同上 | 同上 | 上移 **38px**，偏差 **0px** |

## 提交状态

- 分支：`remove_top_project_icon`（未改 `project_status.md`，未 push）。
- 提示：本次涉及主界面布局，合入并重启桌面应用后生效。
