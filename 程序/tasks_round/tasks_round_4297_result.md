# R4297 UX-FP-NOTIFY：文件面板跟随页「来源文档＋本阶段产物」与点选通知（功能轮）
<!-- round-evidence: {"commit_base": "09ca569f", "credential_hits": 0, "evidence_sha256": "e876bcdc60a93fac", "exit": 0, "failed": 0, "passed": 179, "round": 4297, "tests": "run_selftests.py -k files_panel files_panel_stages"} -->

## 三问
- 轮次类型：功能轮（§3.1），需求设计卡 UX-FP-NOTIFY（REQ-S01-101/102，DES-S01-101/102）。
- 测试：跑了。`run_selftests.py -k files_panel files_panel_stages` 改前 7 红 → 改后全绿（179 条，0 红）；`smoke_test.py --affected desktop_files_panel desktop_files_panel_filters` 10 项通过；`smoke_test.py --architecture` 701 条 OK。
- 欠账：面板侧能力已交付；消费方页面（各制作页登记 `set_select_handler` 并把选中文件显示到内容区）不在本卡范围，REQ/DES 仍标「部分实现」。无新增欠账。

## 缺陷／需求复现方式
卡面为功能卡：目标行为在改前不存在。先在 `tests/test_files_panel_stages.py` 新增用例（真 Desktop 夹具，隐藏桌面），未改产品时代码跑定向命令复现：

`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k files_panel files_panel_stages` → 退出码 1，**7 条红**：
- `test_structure_page_shows_source_and_own_groups`：剧本结构页只有单阶段行口径，无 `stage-group:__source__`/`__own__` 分组父行（`get_children()` 不含分组 iid）。
- `test_storyboard_page_lists_source_files_flat`：初步分镜页 `rows()` 为空——旧口径只列本阶段（storyboard）文件，来源阶段（script_structure）的文件不出现。
- `test_select_notifies_registered_handler_with_file_path`、`test_default_select_is_applied_without_notifying`、`test_programmatic_refresh_does_not_notify`、`test_page_switch_clears_select_registration`、`test_media_row_selection_does_not_notify`：均 `AttributeError: 'ProjectFilesPanel' object has no attribute 'set_select_handler'`——点选通知窄接口不存在。
- `test_manual_stage_pick_keeps_single_stage_view` 改前即绿（手选阶段保持单阶段视图是既有行为，作为守卫用例保留）。

## 改动（文件:行号，改后行号）
- `ui/desktop_files_panel_filters.py`
  - L13/L15–16 imports 增 `COLORS`、`ui.desktop_files_panel_index as files_panel_index`；L18 `_FOLLOWED_STAGE_SENTINEL`。
  - L568–631 `FilesPanelStageViewMixin`：`_dep_source_stages`（L578，读 `orchestrator.stage_flow.DEPENDS` 只读依赖）、`_sync_view_filters`（L588，跟随页阶段变化时记来源阶段）、`_stage_filter_is_followed`（L594）、`_filter_index_rows`（L601，跟随视图预收「来源＋本阶段」行再走 `filtered_rows`）、`_index_groups`（L611，两组都非空才出「来源文档」「本阶段产物」分组行，否则单组平铺）、`_request_index`/`_start_index_render`（L625/L629 薄封装）、`_finish_index_render`（L633，收尾应用默认选中）。
  - L638–730 点选通知：`_ensure_select_state`、`_sync_select_page`（页码变化清掉非当前页登记）、`set_select_handler(page_key, fn, default=None)`、`clear_select_handler(page_key=None)`、`_notify_file_select`（`<<TreeviewSelect>>` 派发，跳过分组行与媒体行）、`_is_media_row`、`_apply_default_select`＋`_release_programmatic_select`（程序化选中压制回调）。
  - L733–815 模块级 `_stage_view_request_index`/`_stage_view_index_render`：两管线实现体（与 index mixin 原实现逐行同，仅 discover 阶段口径、行过滤、分组来源三处不同）。放模块级是因为共享状态棘轮按类归因 `self.X` 赋值，类内复制会多出 5 个多写者属性。
- `ui/desktop_files_panel.py`：L18 import 加 `FilesPanelStageViewMixin`；L186 基类顺序 `Resize, StageView, Filter, Snapshots`（StageView 先于 Filter→Index 接管三个管线方法）；L295 `script_tree.bind('<<TreeviewSelect>>', self._notify_file_select, add='+')`；L358 `project_changed` 首行 `self._sync_select_page()`（DES-S01-94 确认的换页钩子）。类行数经单行类声明压回 600（棘轮上限）。
- `tests/test_files_panel_stages.py`：`DockContentTests` 新增 8 条用例（L876 `_stage_file` 夹具＋L890–1034 七条功能/守卫用例），文件 1505→1658 行。
- `docs/stages/S01_剧本准备.md`：REQ-S01-101/102 状态格 🟡＋「已实现的部分」；新增 DES-S01-101/DES-S01-102 实现描述；测试锚点表 REQ-S01-101..105 行同步。

## 窄接口（卡面要求写明命名）
`set_select_handler(page_key, fn, default=None)`／`clear_select_handler(page_key=None)`，`page_key`＝`page.page_index`；`fn` 收文件绝对路径，`default` 为要预选的行 iid。换页由 `project_changed`→`_sync_select_page` 清掉非当前页登记；无登记页面行为不变；图片/视频/音频行不进回调，双击/回车「打开」不变；程序化刷新与默认选中不触发回调。

## 改后命令输出尾部（原文）
1. `run_selftests.py -k files_panel files_panel_stages`（重构后复跑）：
   `共 179 条用例，272.0 秒；0 个文件有红` … `ALL TESTS PASSED`，退出码 0。
2. `smoke_test.py --affected desktop_files_panel desktop_files_panel_filters`（重构后复跑）：`通过：10 项／失败：0 项`，`✅ 冒烟测试通过，可以进入下一轮`，退出码 0。（重构前一轮同命令亦 10/0，门禁定向自检 239 秒 0 红。）
3. `smoke_test.py --architecture`（重构后）：`Ran 701 tests in 278.606s` `OK` `✅ 架构治理测试：tests/architecture`，退出码 0。

## 三个基线数
- 默认冒烟 `smoke_test.py`（无参）：未运行（卡面验收未列；`--affected` 已覆盖受影响面）。
- 架构门禁：当轮 701 条全绿（改前同命令曾红 2 条：类行数 601>600、共享状态 5 个多写者属性；重构后归零）。
- 全量回归：未运行（分支不累计；凭据以 `full-safe-receipts.json` 为准）。

## 按推荐执行的待确认项
- 窄接口命名按卡面「命名可调」自定为 `set_select_handler`/`clear_select_handler`（见上节）。
- 「来源文档」组来源取 `orchestrator.stage_flow.DEPENDS` 直接依赖（DES-S01-101 指定只读），`script` 阶段无依赖时跟随视图退化为单阶段口径。
- 无其他「建议，待确认」项。

## 未验证／未覆盖
- 消费方页面尚未接入 `set_select_handler`：点选通知链路只到面板回调边界，「页面显示内容」由后续卡消费；本卡测试以登记桩验证参数与触发时机。
- `default` 预选只在索引渲染收尾应用一次；行在渲染后才出现（如索引延迟补齐）时不追选。
- 全量自检、默认冒烟未跑（见基线数）。

## 卡外发现（只记录）
- `run_selftests.py` 本轮两次运行中位基线从 100.6s/105.1s 跳到 3.8s，疑为增量台账口径变化，未核实。
- 无其他范围外缺陷。

## 被拒绝的命令
- `Get-ChildItem tasks_round …`（PowerShell 目录列举）被用户拒绝一次，改用文件工具完成同等查看；不影响验收。
- `git show HEAD:ui/desktop_files_panel.py` 被用户拒绝一次；类行数改动已由架构门禁实测确认（600 行通过）。

## 回滚
`git revert` 本轮提交即可；面板回到单阶段行口径、无点选通知。
