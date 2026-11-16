# R2962 功能轮：「项目文件」栏迁出剧本准备页——主界面右上角图标入口＋右侧停靠面板
<!-- round-evidence: {"commit_base": "25a12c55", "credential_hits": 0, "evidence_sha256": "3b0cff3a0ee8c8da", "exit": 0, "failed": 0, "passed": 243, "round": 2962, "tests": "run_selftests.py -k files_panel idea_chat compact_layout writing_page latent_defects script_workspace"} -->

## 三问

1. **本轮类型**：功能轮（§3.1）。用户要求把「剧本准备」页内「项目文件」栏移动到主界面右上角作为全局固定目录：纯图标钮（与项目目录图标同套 Fluent Filled 风格）＋默认隐藏、点击向左侧打开的右侧停靠面板；UI 契约有意变更（REQ-S01-90／DES-S01-90 先行），测试定位同步、断言不弱化（§2.4）。
2. **测试与三个基线**：
   - 默认冒烟基线：**9/9** ✅（`python smoke_test.py`，含 `--affected desktop_files_panel` 门禁项）
   - `--affected desktop_files_panel`：4 文件 39 用例 0 红 ✅
   - 定向回归 `run_selftests.py -k files_panel idea_chat ui_edges_pages compact_layout`：9 文件 221 用例，仅 `test_ui_edges_pages` 2 红——均为**落后基线的 master 既有回归**（`header_status` justify 契约、`video_navigation.show_back` 跨父级 pack），master R2966 已修，本支 rebase 后复验；本支新增 `test_files_panel` 6/6、`test_desktop_compact_layout` 5/5、`test_idea_chat` 全分片 0 红 ✅
   - 架构门禁：**470/470** ✅（`python smoke_test.py --architecture`；覆盖率基线已随新模块刷新，runbook §11 数字同步）
   - 全量：未跑（累计未达全量阈值；欠账口径见 runbook §4）。
3. **欠账**：无新增。`project_status.md` 轮次头随 master 合并轮更新（仅 master 可提交）。

## 需求与设计

- `docs/stages/S01_剧本准备.md` 新增 **REQ-S01-90**（契约）与 **DES-S01-90**（设计），测试锚点表登记 `test_files_panel` 等 7 个文件。
- 用户确认细节：纯图标钮＋悬停提示；右侧停靠面板（主内容区收窄）；所有生产页显示，会员页／参考网站页／无项目隐藏；点击开合＋面板外按下／Esc 关闭＋切页切项目自动收起。

## 产品改动

- 新增 L4 `desktop_files_panel.ProjectFilesPanel`（继承 `WritingSnapshotsMixin`，`self.page` 即 Desktop）：
  - `build()`：标题行 `pack(before=header_info, side='right')` 建 `project_files` 图标钮（`IconLoader.nav_icon`＋`RailIcon.TButton`＋Tooltip「项目文件」）；内容画布父框右侧建停靠框 `script_box`（「项目文件」标签＋收起钮＋单列 `DataTable`）。
  - 兼容面：`script_box`／`script_tree`／`script_title`／`script_toggle`／`script_row_category`／`script_file_tips`／`refresh_script_list`／`open_script_file` 按原名挂到 Desktop，`desktop_auto_flows`／`desktop_idea_chat`／`desktop_script_pages` 的 `getattr(self,'refresh_script_list')` 消费方不变。
  - 开合：`_open`/`_panel_root` 只存实例；`sync_entry()` 按「root 非空且 page_index 非会员账户／参考网站」显隐；`project_changed()` 由 `PageNavMixin._show_reset_page` 每次换页调用（`load()`→`show(0)` 同路），页序号变化 `collapse()`；面板外 `<Button-1>` 与 `<Escape>` 仿 `_open_sidebar_popup` funcid 绑定，仅打开期间挂接。
  - 文件列表方法体自 `_WritingPage` 原样迁入（发现/渐进批次/双击回车打开/右键菜单/重命名/删除回收/采用/取消确认/设为定稿/按段落采用/历史快照），`alive()` 增 `_open` 判据，面板关闭不再触发目录扫描。
- `desktop_writing_page.py`：删除 `script_box` 构建块与全部文件列表方法（原 632–869 行整段迁出，-304 行）；`cancel_recon_state` 的 Destroy 兜底改绑 `talk`。
- `desktop.py`：`import ProjectFilesPanel`＋`build()` 内联装配（类体净 -1 行，棘轮 819 内）；`self.canvas.pack` 改 `side='left'`——默认 `top` 打包会让右侧停靠奴隶只分到底部剩余条带（实测面板缩成右下角小块、画布不收窄），`left` 后面板拿全高竖条、画布正确收窄。
- `desktop_layout.py`：`align_header` 行高最小值循环纳入 `files_button`。
- `desktop_page_nav.py`：`_show_reset_page` 挂面板收起/同步（+6 行）。
- 图标：`scripts/build_nav_icons.py` 登记 `project_files`（Fluent Filled 字形）＋生成 `assets/nav/project_files.png`（28×26），与 `project_open` 同套。
- 登记：`architecture.md` §3 L4 表、`PROJECT_MAP.md`、`tests/architecture/_layers.py`（L4）、`tests/architecture/_scan.py` `DESKTOP_PARTS`、`runbook.md` §11 覆盖率数字（534→535/463→464）、`维护记录/覆盖率基线.json` 重测刷新。

## 测试改动（契约同步，断言不弱化）

- 新增 `tests/test_files_panel.py`（6 例）：入口图标钮形态、显隐随项目/页码、默认隐藏与停靠几何（右缘贴合＋画布收窄）、收起钮/外点/Esc/切页/切项目、渐进填表。
- `test_idea_chat.py`：5 处文件列表用例改为先 `files_panel.open_panel()` 再等批次；折叠用例改写为面板开合契约（`test_project_files_panel_toggle_and_page_switch`）。
- `test_ui_edges_pages.py`/`test_desktop_compact_layout.py`：文件列表断言前开面板；几何断言改为打开后底边不越内容区。
- `test_writing_page_services.py`/`test_writing_unconfirm.py`/`test_writing_page_controller.py`/`test_latent_defects_r2175.py`/`test_script_workspace_results.py`：夹具从 `_WritingPage` 迁到 `ProjectFilesPanel`。
- `tests/architecture/test_script_rename_boundary.py`：扫描域加 `ProjectFilesPanel`（已入 `DESKTOP_PARTS`）。

## 验证明细

- 修复中发现并解决：`Desktop.__init__` 早期 `self.root` 未赋值，`_entry_allowed`/`project_changed`/`fill_script_list` 的 `self.page.root` 直取会触发 `__getattr__` AttributeError（全量 Desktop 构造红）——改 `getattr(...,None)` 防御。
- 工作树环境补齐（不入库）：`skills/00全流程SKILL/AIGC创作全流程` 子模块内容自主工作区复制（`.gitmodules` 映射缺失无法 `submodule update`）、`维护记录/基准历史.json` 自主工作区复制——两者为未跟踪运行数据，非本轮代码改动。
- `test_ui_edges_pages` 2 红定性：HEAD 上 `header_status` 写死 `justify='left'`（测试要 `'right'`）、`show_back` 以 `before=desktop.title` 跨 master 打包（title 自 R2946 在侧栏滚动区）——master `abec90bd`（R2966 修复轮）已修，本支 rebase 后复验。
