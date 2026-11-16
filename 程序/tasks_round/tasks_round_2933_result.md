# R2933 功能轮结果
<!-- round-evidence: {"commit_base": "48bf43c7", "credential_hits": 0, "evidence_sha256": "70b4a782d09e3d7c", "exit": 0, "failed": 0, "passed": 726, "round": 2933, "tests": "run_selftests.py -k desktop pet_ui ui_usage_indicator ui_tokens ui_icons"} -->

- 轮次类型：功能轮（§3.1）。用户任务书见 `~/.devin/plans/plan-c7fd9da9fac35669.md`（9 项侧栏/页头改版需求，用户已确认「执行」）。
- 测试跑了吗：跑了。三个基线：冒烟检查 8/8；架构门禁当轮实测 470/470 全绿；定向门禁 `--affected desktop pet_ui ui_usage_indicator ui_tokens ui_icons` 共 2593 条用例，仅 `test_skills` 一文件红（环境原因，见下），补齐后 127/127 复绿。`project_status.md` 欠账：未新增；历史欠账未扩大。
- 说明：接续会话恢复时发现 R2922 领号后未提交，按 `round_claim.py next` 重新领得 R2933 并切 `codex/wip-R2933`（未提交改动由工具原样带入）；全库 `R2922` 注释同步改为 `R2933`。

## 需求落法（9 项）

1. 左侧列表删编号：导航钮 `compound='image'` 纯图标，PNG 缺失回退编号；全名留 Tooltip。
2. 删左上角「项目名＋把灵感变成故事」：`app_title`/`header_slogan` 浮层移除，项目名留窗口标题与选择器「●」。
3. 阶段名在左：页标题「01  剧本准备」保留在内容区标题行。
4. Token 同行：`UsageIndicator` pack 进 `title_row` 紧随标题；`place_in_title_row` 浮层函数删除。
5. 齿轮：Fluent `settings.png`（新生成）经 `GearButton` 画布渲染，PNG 缺失退回手绘齿轮；置于侧栏底栏 `settings_gear_layer`。
6. 三虎簇入 `pet_dock`：头像上、小字紧贴下（`DOCK_CAPTION_GAP` 收紧）、猫爪列贴右沿对「头像＋小字」整组垂直居中（`_paw_col_top`/`_align_paws` 随小字换行重算）。
7. 分组图标弹列表：「在制作/已完成」图标 `set_project_group(state, popup=True)` 切组并 `ttk::combobox::Post` 展开各自项目下拉。
8. 上移：侧栏顶部浮层删除、标题行收成单行，内容区与状态栏上移。
9. 连带：锁页图标换 `assets/nav/lock.png`（`NAV_LOCK_ICON`），文字锁标仅作资源缺失兜底；`refresh_nav_locks` 做图标交换。

## 主要改动

- 新增 `assets/nav/settings.png`、`assets/nav/lock.png`（`scripts/build_nav_icons.py` +2 字形）。
- `desktop.py`：侧栏 `sidebar_dock`（齿轮行＋`pet_dock`，先于滚动区 pack 永不滚动）、纯图标 `RailIcon` 导航、账户钮上移至阶段钮之上、页头标题行重排。
- `desktop_layout.py`：`align_header` 重写（pet_dock 高度跟 `patch_room`、标题行高按标题/用量/信息实测）；`on_window_map` 移植 master R2925 修复——非本窗口 `<Map>` 不再误撤销拖动合并（本改版新增 dock 后代映射会触发该缺陷）。
- `desktop_project_pages.py`：分组图标 popup、`_post_project_picker`、选择器「●」同步；`ProjectPagesMixin` 压回 598 行（登记上限 600）。
- `desktop_account_page.py`/`desktop_page_registry.py`/`desktop_page_nav.py`：锁图标交换与导航图标名/Tooltip 登记。
- `pet_ui_view.py`/`pet_ui_support.py`/`pet_ui_settings.py`/`pet_ui.py`/`pet_ui_voice.py`：dock 几何常量与布局、GearButton Fluent 渲染、`except Exception: pass` 收紧为 `TclError`（静默异常棘轮）。
- `ui_usage_indicator.py`：指示器改 pack 进标题行；`ui_tokens.py` 删除无人引用的布局键。
- `ui_components.md` 同步新侧栏结构。

## 测试契约变更（§2.4）

- `test_video_ui.py`：页头收成单行后日志可多占提示词让出的行数，旧「最多比最小多一行」上限作废，改守「让路＋不超剩余空间＋不低于最小行数」三条；实测 after=5、room=4，行为正确。
- `test_pet_ui.py`/`test_pet_settings.py`/`test_desktop_compact_layout.py`/`test_ui_batch3_shell.py`/`test_sidebar_project_title.py`/`test_page_lock.py`/`test_login_gate.py`/`test_account_entry.py`/`test_page_cache.py`/`test_usage_indicator_ui.py`：FakeDesktop 补 `pet_dock`/`pet_layer`，断言迁移到 dock 几何、RailIcon 样式、锁图标图像名（Tcl 图像名归一化）。
- 架构登记同步（只许下降）：`PetViewMixin` 746→732（实测 717）、`Desktop` 共享状态 45→44。

## 验证记录

- `smoke_test.py --affected desktop pet_ui ui_usage_indicator ui_tokens ui_icons`：本轮检查 8/8；门禁 2593 条，唯一红 `test_skills`（71≠73）——工作树三个 gitlink 子模块（`AIGC创作全流程`/`剧本锻造`/`编剧技能集`）未初始化，按各自 gitlink 提交从主工作区本地克隆补齐后 `test_skills` 127/127 复绿。子模块内容与 gitlink 一致，未进暂存区。
- `smoke_test.py --architecture`：470/470 全绿（首轮 4 红 1 错已修：类行数、两处登记下调、静默异常、`基准历史.json` 工作树缺失——该文件为未跟踪性能历史，从主工作区复制验证用，不入库）。
- 定向复跑（压缩/改名后）：`test_desktop_compact_layout`、`test_ui_batch4_desktop_project_pages`、`test_pet_ui` 全部分片、`test_pet_settings`、`test_ui_batch9_pet_accessibility` 全绿。
- 遗留噪声：`invalid command name ...start_update_check/start_account_renewal/_apply_idea_send_state` 为各 GUI 测试 teardown 后 after 回调打到已毁命令，基线同现，与本轮无关；`desktop_writing_page.py:346` `stop_input_hint` Destroy 绑定参数错误为基线既有缺陷，未动。

## 提交

- 待 `dev.py commit` 回填 commit hash 与证据。
