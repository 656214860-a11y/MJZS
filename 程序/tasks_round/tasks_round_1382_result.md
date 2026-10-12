# R1382：状态接续轮 — 更新项目阻塞与待办（含只读审计：生产文案阶段编号漂移）

类型：状态接续轮（§3.11，2026-10-12）。中央轮次 1382（`.git/round-counter.json` 的 `last_claimed=1382`）。范围＝用户要求「更新项目阻塞项、待办任务清单」＋「更新交接状态并收尾」；**本轮不改生产代码、无功能改动**。

## 三个必答
- 本轮类型：状态接续轮（§3.11）——只依据仓库事实与既有报告整理并更新 `project_status.md` 的「已知阻塞与待办」与接力文件；同时做一次只读审计，把新发现的「生产文案阶段编号漂移」登记为待办。
- 测试：默认冒烟 `smoke_test.py` **8/8、0 失败**（含「13 个制作阶段路由仍完整」，复确认权威序与显示名）。本轮未触任何 `程序/` 生产文件，§5 无升级触发；未跑架构门禁与全量。
- 欠账：本轮**不减少**功能欠账，反而**如实登记 1 条新待办**（阶段编号漂移，已审计未实现）。全量欠账不变：最近绿全量为 R1380（tree f62cd088、`last_full_safe_all_round=1380`），1382−1380=2<5。

## 本轮改动（仅文档／状态，无生产代码）
1. `程序/project_status.md`：轮次头 `当前轮次：1382 → 1383`，并前置 R1382 摘要；「已知阻塞与待办」新增条目《【待办·已审计未实现】生产文案阶段编号漂移（R1382 只读审计）》。
2. `.agent-handoff/snapshot.md`／`backlog.md`／`risks.md`／`work-log.md`／`validation.md`：同步本轮状态与新增待办。
3. 本结果文件。

## 只读审计：生产文案「NN 阶段名」过期编号
### 权威（唯一真源）
- 步号序：`pet_bus.STAGES`＝script／script_structure／storyboard／animatic／assets／continuity／final／keyframe／previs／video／audio／edit／delivery。
- 显示名：`pet_bus.STAGE_NAMES`＝01 剧本准备／02 剧本结构／03 初步分镜／04 分镜预演／05 资产管理／06 连贯性清单／07 分镜定稿／08 首帧管理／09 白模预演／10 视频生成／11 配音与字幕／12 后期剪辑／13 质检与交付。
- 导航标签：`desktop.PAGES`＝`f'{index:02d}  {pet_bus.stage_name(stage)}'`（另加 `14  参考网站` 工具页）。

### 结论
R1375（O48）只把 24 处用户可见「第N步」收口到 `pet_bus.stage_step`；**散落的「NN 阶段名」旧编号未同批处理**。R1124 插入 `animatic`（第 04 步）后，资产起整体偏移（资产 03→05、连贯性 04→06、定稿 05→07、首帧 06→08、白模 07→09、视频 08→10、配音 09→11、剪辑 10→12、质检 11→13）。

### 命中（排除 `stage_path_service.LEGACY_NUMBERED` 旧目录兼容常量）
- 生产 **14 文件 97 处**：`skill_tools.py` 56、`desktop.py` 15、`stage_parallel.py` 5、`keyframe_batch.py` 4、`pet_ui.py` 4、`app.py` 3、`asset_detail.py` 2、`skill_panel.py` 2、`animatic_service.py`／`asset_contract.py`／`continuity_ledger.py`／`prompt_window.py`／`storyboard_files.py`／`ui_theme.py` 各 1。
- `tests/` **19 文件 56 处**：`test_skills.py` 7、`test_stage_copy_on_write.py` 7、`test_pet_ui.py` 6、`test_ui_edges.py` 6、`test_storyboard_final_controller.py` 4、`test_recycle_restore.py` 3、`test_video_ui.py` 3，其余 12 文件各 1–2。

### 其中用户可见字符串（应优先修）
- `keyframe_batch.py:51/52/141/236`：`04 首帧管理` → `08 首帧管理`。
- `desktop.py:2484`：`02 初步分镜` → `03 初步分镜`；`desktop.py:7015/7058`：`08  视频生成` → `10  视频生成`。
- `pet_ui.py:2956` `02 初步分镜`→`03`、`pet_ui.py:2959` `06 首帧管理`→`08`。
- `stage_parallel.py:477/480/483/486/489`：`03 资产管理`→`05`、`04 连贯性清单`→`06`、`05 分镜定稿`→`07`、`06 首帧管理`→`08`、`07 白模预演`→`09`。
- `skill_tools.py` 的 `PAGES` 说明列 56 处（如 `04 资产管理`→`05`、`12 质检与交付`→`13`）。

### 明确勿误改
- `stage_path_service.py:26–28` 的 `LEGACY_NUMBERED`（`04资产管理`／`05连贯性清单`… 是 R1124 前旧目录，只读兼容，编号正确）。
- `desktop.py:5180`（`01剧本准备`）、`desktop.py:5212`（`02剧本结构`）——步号正确。

### 门禁缺口
`tests/architecture/test_stage_display_boundary.py` 只校验 `desktop.PAGES` 由 `pet_bus` 权威表生成，**未覆盖**上述散落字符串；路线图 §二 第 15 项「阶段显示」完成判据「任何阶段名称展示均从权威表取值」尚未满足。

## 修复轮建议入口（未执行，登记为待办）
- 按 §3.2 修复轮：依 `pet_bus.STAGES`／`STAGE_NAMES` 逐文件纠正上述编号，同步更新 `tests/` 19 文件 56 处断言，并新增/扩展架构门禁（AST 扫生产字符串常量，排除 docstring 与 `LEGACY_NUMBERED`）。
- 定向建议：`run_selftests.py -k "stage_parallel skill_tools keyframe_batch pet_ui video_ui text_component skills stage_display"` ＋ 默认冒烟；结构治理／加门禁时跑 `smoke_test.py --architecture`。

## 提交
- 本轮文档与状态改动已提交：**内容提交 `6c2c399`**（7 files changed，仅本轮 7 个路径，未混入主树他人已暂存 WIP）；hash 补记见后续提交。
