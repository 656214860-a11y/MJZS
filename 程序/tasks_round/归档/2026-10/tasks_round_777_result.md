# R777｜UI 统一入口第一批第 2 项：表格首迁｜结构治理轮

## 结论

已交付 `DataTable` 的统一入口，并仅迁移剧本／分镜文件选择表；不改变其勾选、全选、行高适配、排序回调或文件选择业务语义。其余历史 `Treeview` 未在本轮迁移。

## 改动

- `ui_tokens.py` 与 `design_tokens.md`：登记表头、行文字、行高与空态留白 token。
- `ui_widgets.py`：新增 `DataTable`，统一列、双滚动条、空态、选择回调与通用排序；沿用 `setup_styles()` 的表格样式。
- `storyboard_table_ui.py`：`file_table()` 改经 `DataTable` 构造，仍向既有调用方暴露兼容的 `Treeview` 操作面。
- `ui_components.md`：规定新表格必须使用 `DataTable`，旧表格独立分批迁移。
- 新增组件、首迁页边界与行为回归；同步架构测试目录清单与 skip 台账。

## 回归与处置

首次完整安全全量发现 `test_ui_edges` 真实回归：`DataTable` 外壳使用 Card 样式，被既有页面层级断言计为额外信息卡，Card 数从 2 变为 4。外壳已调整为中性 `ttk.Frame`，视觉层级仍由既有页面 Card 负责；未放宽断言。

## 验证

- `python smoke_test.py`：8/8。
- `python smoke_test.py --affected ui_widgets storyboard_table_ui storyboard_files`：9/9。
- `python run_selftests.py -k ui_edges ui_widgets_table storyboard --safe`：144 条／0 红。
- `python run_selftests.py --layer architecture --all --safe`：144 条／0 红。
- 首次全量仅 `test_perf_baseline` 受 150.47ms／150ms 边界波动影响；独立复跑通过，随后完整安全全量重跑：3,533 条／0 红／866.2 秒。

本轮改动 Tk 表格映射／选择事件，按 AGENTS.md §5 升级完整安全全量；`维护记录/测试分层基线.json` 的 `last_full_safe_all_round` 已推进至 777。

## Git

- 已提交：否。
- commit hash：无。
- 建议提交信息：`feat(ui): add shared DataTable and migrate storyboard picker`
