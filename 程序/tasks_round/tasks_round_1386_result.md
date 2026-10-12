# R1386：阶段显示收口 — 生产文案阶段编号漂移纠正 ＋ 权威标签现算 ＋ 架构门禁

类型：修复轮（§3.2，2026-10-12）。中央轮次：领号时为 1383，提交前发现中心计数器已被并发车道推进到 1385，重新领号得 **1386**（`.git/round-counter.json` 的 `last_claimed=1386`），故本轮记为 R1386；1383／1384／1385 由其它车道持有、无结果文件（下文「编号说明」）。范围＝R1382 只读审计登记的待办「生产文案阶段编号漂移」，对应 `维护记录/UI统一入口路线图_v1.md` §二 第 15 项「阶段显示」（完成判据原文「任何阶段名称展示均从权威表取值」）。

## 三个必答
- 本轮类型：修复轮（§3.2）——不改业务逻辑、阶段、路径与分层；只把用户可见的阶段标签改成从 `pet_bus` 权威表现算，并纠正写死处的过期编号。
- 测试：定向 `run_selftests.py -k "pet_ui stage_parallel video_ui skills cell_menu core final_viewer frame_sources manual_gate ui_edges stage_display keyframe_batch asset_contract continuity_ledger prompt_window storyboard_files ui_theme pet_bus"` **1275 条 / 0 文件红 / 305.5 秒**；架构 `smoke_test.py --architecture` **329/329**（326→+3）；默认冒烟 `smoke_test.py` **8/8**。
- 欠账：本轮**清掉 R1382 登记的那条待办**（阶段编号漂移）。全量：路线图条目收口触发，在干净 master 工作树 `o07-fullsafe-master` 跑 `run_selftests.py --all --safe`：**4971/4971、0 红、534.1 秒**（凭据 `tree=d9aee73c335f3fe6f43dd9e8d9f3797b5d73fba8`、`round=1382`）。

## 编号说明（并发车道）
- 本轮开工领到 1383；提交时 `commit-msg` 门禁报「R1383 不等于中央已领取轮次 R1385」，说明期间有并发车道把中心计数从 1383 推到 1385。按门禁要求重新 `round_claim.py next` 得 1386，提交消息据此写 R1386。
- 因此 1383／1384／1385 无结果文件；`project_status.md` 轮次头按「最新结果轮次＋1」写成 **1387**。
- 全量凭据的 `round` 字段为 **1382**：`run_selftests.py` 用 `latest_completed_round()`（扫 `tasks_round/tasks_round_*_result.md` 取最大号）给凭据编号，而跑全量时本轮结果文件尚未落盘，故取到 1382。凭据的 `tree=d9aee73c` 正是本轮内容提交 `4cb02d3:程序`，与实际验证的代码一致（结果文件不参与代码验证）。不重跑第二次全量：同一内容树重复全量既无新信息，也违反用户「减少全量频率、不做重复测试」的要求。

## 审计口径修正（相对 R1382 登记）
- R1382 登记为「生产 14 文件 97 处」。复核发现其中 `animatic_service.py:1` 是**误报**：`"""L2 分镜预演：…"""` 里的「2 分镜预演」是层级前缀 `L2`，不是阶段步号。
- 加词边界 `(?<![A-Za-z0-9_])(\d{1,2})\s*<显示名>` 后准确口径＝**生产 13 文件 96 处**、`tests/` 19 文件 56 处。已同步更正 `project_status.md` 与接力记录。

## 实现
### 1. 权威标签（新入口，唯一来源）
- `pet_bus.stage_label(stage)`：`'%02d %s' % (STAGES.index(key)+1, STAGE_NAMES[key])`，未知阶段退回 `stage_name`。与 `desktop.PAGES` 的 `f'{index:02d}  {stage_name(stage)}'` 同源同步号（步号＝`STAGES` 序）。
### 2. 用户可见文案改为现算
- `keyframe_batch.py`：`STATE_EMPTY`／`STATE_DELETED` 说明与两处 `ValueError`（首帧空文件／已删除／显式替换）由 `'04 首帧管理'` 改 `pet_bus.stage_label('keyframe')`（新增 `import pet_bus`）。
- `stage_parallel.py`：`GATES` 的 SG-01..SG-05 `reject` 文案改由 `pet_bus.stage_label('assets'|'continuity'|'final'|'keyframe'|'previs')` 现算（新增 `import pet_bus`）。
- `pet_ui.py`：`gaps` 气泡两处 `'02 初步分镜'`／`'06 首帧管理'` 改 `%s` 现算。
- `desktop.py`：视频页标题两处 `'08  视频生成 · …'` 改 `pet_bus.stage_label('video')+' · …'`；`shot_numbering_hint()` 的提示改现算。
- `skill_tools.py`：导出工具 `note` 里「10 后期剪辑」改 `stage_label('edit')`。
- `skill_panel.py`：本文件的 `stage_label()` 退化为对 `pet_bus.stage_label` 的薄封装（去重入口，§2.5.28）。
### 3. 死字面量与注释／docstring
- `skill_tools.py` 的 `PAGES` 原始字面量（约 62 行）去掉已死的「旧编号 ＋ 名称 ＋ →」前缀：第 503 行重建时只用「→」右侧动作文本，行为不变（`hint.split('→',1)[-1].strip()`）。
- 其余注释／docstring 的过期编号按权威序纠正：资产 03→05、连贯性 04→06、定稿 05→07、首帧 06→08、白模 07→09、视频 08→10、配音 09→11、剪辑 10→12、质检 11→13（`app.py`／`asset_detail.py`／`asset_contract.py`／`continuity_ledger.py`／`prompt_window.py`／`storyboard_files.py`／`ui_theme.py`／`desktop.py`／`pet_ui.py`／`skill_panel.py`）。
- **不改**：`stage_path_service.LEGACY_NUMBERED`（R1124 前旧目录名，只读兼容，编号本就有意不同）、`desktop.PAGES`（已由权威表生成）、`stage_layout.STAGES`（阶段目录名元组，编号已与 `pet_bus` 同步）。
### 4. 架构门禁（`tests/architecture/test_stage_display_boundary.py`，已在 §5 门禁清单内，未增删文件）
- `test_production_stage_numbers_match_authority`：AST 扫全部生产模块字符串常量（含 docstring），凡出现「NN 阶段名」处，NN 必须等于 `pet_bus.STAGES` 步号；只豁免 `stage_path_service.py`（LEGACY）。
- `test_display_sites_derive_stage_labels_from_authority`：冻结 6 个已迁移展示位点（keyframe_batch／stage_parallel／pet_ui／desktop／skill_tools／skill_panel），不得退回写死。
- `test_stage_label_matches_navigation_order`：`stage_label` 步号与导航序一致、未知阶段原样退回。
- 效果：修复前该门禁会命中全部 96 处；修复后 0 命中（LEGACY 除外）。

## 测试契约同步（§2.4）
- 同步 `tests/` 里写死旧编号的断言与注释：test_pet_ui（1＋5）、test_stage_parallel（1）、test_video_ui（3）、test_skills（7）、test_cell_menu（2）、test_core（1）、test_final_viewer（2）、test_frame_sources（2）、test_manual_gate（1）、test_ui_edges（5）。
- `架构统一基数.json` 第四项 `stage_parallel.py` 行号 454→455（文件顶部新增 `import pet_bus` 使原 `json.loads` 平移），reason 记明 R1386 平移原因。

## 验证
- 定向：**1275 条、0 文件红、305.5 秒**。
- 架构：`smoke_test.py --architecture` **329/329、0 红**（原 326，本轮 +3 条新用例）。
- 默认冒烟：**8/8、0 失败**。
- 全量（§5 路线图条目收口触发，干净 master 工作树 `o07-fullsafe-master`，`git reset --hard master` 后跑）：**4971/4971、0 红、534.1 秒**，凭据 `tree=d9aee73c`、`round=1382`（编号说明见上）；`test_desktop_startup_perf` 14/14、`test_perf_baseline` 9/9 均通过，无阈值抖动。
- 新增 `skipTest`：无。

## 提交
- 内容提交：**`4cb02d3`**（26 files，仅本轮路径，未混入主树他人已暂存 WIP）。
- 报告与状态／接力：另一次提交（hash 见后续补记）。

## 复盘：路线图 §二 第 15 项「阶段显示」
- 完成判据原文「任何阶段名称展示均从权威表取值」。本轮做到：**所有此前漂移的用户可见展示位点改为由 `pet_bus.stage_label`／`stage_step` 现算**；**全生产模块写死的「NN 阶段名」编号受门禁约束必须等于权威步号**。
- 未做（并说明理由）：把**阶段目录名**（`05资产管理` 这类，同时是磁盘路径）也改成运行时拼接——目录名是 `stage_layout.STAGES` 的声明式常量、到处当路径用，改成拼接会污染路径语义且收益为零；门禁以「编号必须正确」覆盖它们。
