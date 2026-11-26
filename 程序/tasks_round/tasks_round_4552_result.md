# R4552 S04-V2-UX-PERF：S04 分镜预演外置播放优先、Tkinter 防卡死改造与页内偏好条
<!-- round-evidence: {"commit_base": "5ae6d38d8", "credential_hits": 0, "evidence_sha256": "4d8f3a2a5ece70e8", "exit": 0, "failed": 0, "passed": 149, "round": 4552, "tests": "run_selftests.py -k animatic_page ui_edges_pages media_page_buttons copy_rules"} -->

## 三问

1. **本轮类型（§3）**：§3.1 功能轮（任务卡 `S04-V2-UX-PERF`，对应 `REQ-S04-106..111`、`DES-S04-33..35`，并完成 `S04_分镜预演.md` 中 `REQ-S04-100..112` / `DES-S04-30..35` 全量翻 ✅）。
2. **测试与三个基线**：
   - 默认冒烟（`smoke_test.py`）：9/9 通过（隐藏桌面 `--probe` + 8/8 检查项），0 失败，退出码 `0`。
   - 架构门禁（`smoke_test.py --architecture`）：711/711 全绿（287.3s），0 红，退出码 `0`（含 `_layers`、`LR-03`、`test_module_size_ratchet`、`test_button_boundary`、`test_dialog_boundary`、`test_ui_icons_boundary`、`test_native_control_boundary`、`test_form_control_boundary`、`test_token_boundary`、`test_requirement_traceability`、`test_coverage_baseline` 等；初跑曾命中 `test_native_control_boundary` 1 红，封面容器改用 `ttk.Frame(..., style='Card.TFrame')` 后 711/711 全绿）。
   - 定向自检（`run_selftests.py -k animatic_page ui_edges_pages media_page_buttons copy_rules`）：149/149 全绿（63.3s），0 红，0 跳过，退出码 `0`。
   - 覆盖率基线刷新（`scripts/coverage_report.py` 原 17 组核心目标）：230/230 全绿，更新为 `148/698` 模块（未触达 `550`），同步 `runbook.md` §11。
   - 全量安全回归（`--all --safe`）：未运行（功能分支开发轮，按约定由合并轮结算）。
3. **欠账变化**：本轮未新增欠账；保持与 Codex `codex/flow-model-pool` 15 个文件及 `ui/pet_settings_ui.py`、`ui/desktop_media_pages.py` 零文件冲突，`ui/animatic_page.py` 降至 940 行（严格 < 1000 行上限）。

## 改动摘要

- `程序/ui/animatic_prefs_bar.py`（新建 L4 模块，212 行）：
  - 实现只读模型池提取纯函数 `gflow_model_ids(records=None) -> list[str]`，筛出 `key.startswith('gflow-')` 且 `modality=='image'` 的有序 ID；模型池无条目时下拉展示 `（请先在模型管理添加 Google Flow）` 不报错，保存时落空串不写占位文案。
  - 实现页内零弹窗偏好条 `open_prefs_bar(page, state, *, container, on_saved=None)`，支持草图引擎（`text_card` / `gflow_cli` / `comfy_local`）、Google Flow 模型下拉、本地参考图模型名（`animatic_reference_model`）、2D 运镜开关（`animatic_ken_burns`）、信息/字幕烧录开关（`animatic_burn_overlay`）与默认播放方式（`animatic_player_mode`：`external` / `jianying` / `inline`）；保存走 `stage_execution_service.publish_desktop_preferences` 写入 `desktop_settings.json`（假宿主无 `settings_file` 时直接更新 `page.settings`）并收起，回车提交、Esc/关闭收起。
  - 承接同区域页内单行编辑条 `_open_inline_edit`，避免 `ui/animatic_page.py` 超行。
- `程序/ui/animatic_view_state.py`（L4 辅助模块）：
  - 新增纯函数 `timeline_page_slice(shots, page_number, page_size=20)`、`shot_page_for_id`、`shot_dialogue_seconds(project, row, probe=None)`（优先读时间线落盘的 `dialogue_seconds`，缺省再兜底 `probe` 兼容旧项目）、`player_mode_of(page)` 及 150ms `<Configure>` 防抖原语 `schedule_debounced_layout` / `cancel_debounced_layout`。
  - 承接无 Tk 的页面状态读取、外置播放/剪映打开/对白试听与文件面板挂钩辅助函数。
- `程序/ui/animatic_page.py`（L4 主页面，940 行 < 1000 行）：
  - 播放区默认渲染轻量 `ttk.Frame(..., style='Card.TFrame')` 封面（`asset_thumbs.media_thumbnail`，零 `VideoPreview` 预构造与解码开销），单击按 `animatic_player_mode` 分流（默认 `external` 调 `open_path`、`jianying` 调 `page.launch_editor()` 并定位预演视频目录、`inline` 按需挂载 `VideoPreview`）；右键菜单提供「用本地播放器打开」「在剪映中打开」「页内试播」「重新合成新版本」「本地生成参考草图」「预演设置…」。
  - 镜头格右键新增「试听本镜对白」：有 `dialogue_audio` 走 `media_page_services.open_path` 非阻塞试听，无则状态栏提示「该镜头暂无对白音频」。
  - 时间线按每页 20 镜分页渲染（≤20 镜自动隐藏翻页条，3000 镜常驻控件实测 ≤140）；`<Configure>` 改走 150ms 防抖并在 `<Destroy>` 取消挂起定时器；对白轨优先消费 `dialogue_seconds`。
- `程序/tests/architecture/_layers.py`：登记 L4 `animatic_prefs_bar` 及单向同层边 `('animatic_page', 'animatic_prefs_bar')`、`('animatic_prefs_bar', 'ui_widgets')`。
- `程序/维护记录/覆盖率基线.json`、`程序/runbook.md`：刷新覆盖率基线（148/698，17 组核心目标全绿）并同步 §11 模块数。
- `程序/docs/stages/S04_分镜预演.md`：将 `REQ-S04-100..112`、`DES-S04-30..35` 全部翻为 ✅，同步测试锚定表与交互表。

## 测试契约同步（§2.4）

因 `REQ-S04-106/107` 明确变更播放默认策略（由默认内嵌 `VideoPreview` 改为默认外置轻量封面、右键增剪映/页内试播/预演设置、镜头右键增「试听本镜对白」），同步 `tests/test_animatic_page.py` 中 4 处既有断言定位（`ConfirmBarTests.test_compact_880x600_keeps_lock_inside_and_restores_regular_sizes`、`ShotMenuTests.test_menu_items_and_redo`、`PlayAreaTests`、`SketchEntryTests`），未削弱任何既有行为覆盖。

## 先红后绿记录

改产品代码前先在 `tests/test_animatic_page.py` 补全 5 组边界测试与 `REQ-S04-109/111` 锚点：
- 改前红灯命令：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k animatic_page`
- 改前结果（退出码 `1`，共 83 条，15 条红）：
  1. `PaginationAndDialoguePerfTests`（4 红）：`test_timeline_page_slice_clamps_and_slices`（`ImportError: TIMELINE_PAGE_SIZE`）、`test_shot_dialogue_seconds_prefers_recorded_and_falls_back`（`ImportError: shot_dialogue_seconds`）、`test_65_shots_paginates_20_then_5_and_hides_pager_at_20`（`AssertionError: 20 != 65`）、`test_3000_shots_keeps_widget_count_bounded`（`AssertionError: 20 != 3000`，未分页耗时 21.5s）。
  2. `ExternalFirstPlaybackTests`（4 红）：默认构造了 `VideoPreview`、`用本地播放器打开`/`在剪映中打开`/`页内试播` 均缺失。
  3. `DialogueAuditionTests`（2 红）：镜头格右键缺少 `试听本镜对白`。
  4. `PrefsBarTests`（3 红）：`ModuleNotFoundError: No module named 'ui.animatic_prefs_bar'`，右键缺少 `预演设置…`。
  5. `DebounceAndPanelPerfTests`（2 红）：`test_five_configure_events_coalesce_to_one_sync`（`AssertionError: 0 != 6` 未防抖立即重绘）、`test_destroy_cancels_pending_debounced_configure`（`AssertionError: 0 != 2` 销毁前触发多次）。
- 改后转绿：
  - `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k animatic_page ui_edges_pages media_page_buttons copy_rules` → 149/149 全绿（63.3s，0 红 0 跳过，3000 镜分页分片降至 5.7s），退出码 `0`。
  - `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py` → 9/9 通过，退出码 `0`。
  - `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` → 711/711 全绿（287.3s），退出码 `0`。

## 未验证项与卡外发现

- **未验证项**：`run_selftests.py --all --safe` 未在本功能分支执行（留待合并轮统一验收）；真实桌面点击剪映专业版可执行文件与真实 `gflow.exe` 联调待合入 master 后实机核验（本轮已对 `launch_editor` 正常与缺失回退、模型池 `gflow-*` 有/无条目、真磁盘 `desktop_settings.json` 原子落盘全覆盖单测）。
- **卡外发现**：无阻断性卡外问题；`test_ui_edges_pages` / `test_media_page_buttons` 销毁旧窗口时 Tk 后台存在既有的 `start_update_check`/`start_account_renewal`/`_apply_idea_send_state` `after` 噪声日志（与本卡无关，不影响全部 149 条用例通过）。
