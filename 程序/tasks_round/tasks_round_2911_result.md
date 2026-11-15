# R2911 修复轮结果：R2897 侧栏图标轨合入门禁修复
<!-- round-evidence: {"commit_base": "0e8e22b9", "credential_hits": 0, "evidence_sha256": "a7be8bb88556acb5", "exit": 0, "failed": 0, "passed": 179, "round": 2911, "tests": "run_selftests.py -k module_size complexity shared_state data_table agents_md compact_layout sidebar_project_title account_page page_lock ui_batch3 button_consistency project_switch_guard project_rename_reconcile ui_icons startup_perf asset_roster asset_detail"} -->
- 轮次类型：修复轮（§3.2）。根因：R2897 合并轮 exit CI 静态/架构门禁红——合并树上模块行数棘轮、类规模棘轮、共享状态多写者属性、Treeview 边界契约四处失败，合并被 helper 自动回滚。
- 分支：`codex/wip-R2911`（R2911 已领号，基于 R2897 提交 `0e8e22b9`，该提交已含 master 的 contract.* 导入迁移）。
- 三个基线：冒烟 8/8 ✔；架构门禁当轮实测见下；全量未跑（分支不累计欠账，合并轮按 §5 判定）。

## 改动（只动根因所在模块）

### `desktop_project_pages.py`（ProjectPagesMixin 613 → 597 行）
- `_build_project_rail` 压缩：分组筛选与「新建/打开」两排按钮改循环构建，`<<ComboboxSelected>>` 与 `<Button-3>` 两个 bind 合并一行。
- `_build_asset_roster_nav`、`mark_nav` 迁入 `PageNavMixin`（`desktop_page_nav.py`）：二者本就是侧栏导航职责，`mark_nav` 的唯一调用点就在 `page_nav.show()` 内。
- 移除不再使用的 `ASSET_ROSTER_ICON` 导入。

### `desktop_page_nav.py`（PageNavMixin 272 → 286 行）
- 收纳上述两个方法；补 `SecondaryButton`/`Tooltip`/`IconLoader`/`ASSET_ROSTER_ICON` 导入。

### `desktop.py`（996 行）
- 删除 `self.asset_list_button=None` 预置——该属性改由 `PageNavMixin` 单点写入，共享状态多写者属性 46 → 45（恢复上限内）。

### `ui_widgets.py`（1128 → 1125 行）
- `RailIcon.TButton`/`Selected.RailIcon.TButton` 样式定义压缩三行，回到冻结上限内。

### `tests/architecture/test_data_table_boundary.py`
- 契约性更新（§2.4）：侧栏项目树已按 R2897 需求改为分组筛选＋`SelectBox` 选择器，`desktop.py` 不再构造 Treeview；断言改为 `{'desktop_project_pages.py': 2}` 与 `len(direct)==1`（仅项目主页保留树形导航选择器）。

## 测试证据

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 架构门禁 | `run_selftests.py -k module_size complexity shared_state data_table agents_md` | 42/42 ✔ |
| 冒烟 | `smoke_test.py` | 8/8 ✔ |
| 侧栏定向 | `run_selftests.py -k compact_layout sidebar_project_title account_page page_lock ui_batch3 button_consistency project_switch_guard project_rename_reconcile ui_icons startup_perf asset_roster` | 89/89 ✔ |
| 资产详情 | `run_selftests.py -k asset_detail` | 48/48 ✔ |

合计定向 179 条全绿（另有非 GUI 架构 42 条）。Tk teardown 的 `invalid command name "..."` 为既有并行拆卸噪音，非失败。
