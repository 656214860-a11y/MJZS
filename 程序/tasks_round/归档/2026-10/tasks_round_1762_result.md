# R1762：功能轮——切批失败中止定稿，定稿派生批次说明与镜头表（C1）

- 工作目录：`D:\漫剧制作助手\.wt\lane_c1\程序`
- 轮次类型：**功能轮**（`AGENTS.md` §3.1）；涉及已建文档阶段 S07，按 §2.7 先改需求与设计，再改代码与测试。
- 解释器：`D:\漫剧制作助手\运行环境\Python\python.exe -B`
- 执行方未执行任何 git 写命令、未领号、未提交、未改 `project_status.md` / `AGENTS.md` / `private`。
- 车道开工前 `git status` 为干净树（无前一个执行方的未提交改动），本轮从头按任务书执行。

## 三问（§7 第 3 条）

1. **本轮属于 §3 哪种类型？** 功能轮（S07-15 改变用户可见行为：切批失败中止定稿；S07-44 新增两份派生 Markdown）。
2. **测试跑了吗、三个基线过了吗？**
   - 定向/消费方测试：全部通过（逐条见下“验证记录”）。
   - 默认冒烟：`python -B smoke_test.py` → 通过 8 项 / 失败 0 项（当前基线 8/8）。
   - 架构门禁：按任务书只跑 `test_requirement_traceability`＋`test_layers`（10 tests，OK）；另跑与本轮改动直接相关的 7 个门禁（`test_final_bundle_boundary`、`test_json_io_boundary`、`test_function_size_ratchet`、`test_module_size_ratchet`、`test_silent_exception_ratchet`、`test_path_authority`、`test_no_circular_import`，合计 12 tests，OK）。失败集合为空。未跑完整 `--architecture`（任务书禁止）。
   - 全量回归与欠账：**未运行**（任务书明确禁止 `run_selftests.py`、全量；分支不累计全量欠账，本文件不冒用任何全量凭据）。
3. **`project_status.md` 的欠账少了吗？** 本轮不领号、不改状态页，无法也不应改动其欠账条目。需求侧：`REQ-S07-15`、`REQ-S07-44` 由 🟡 改为 ✅，并各补一条真实行为锚点；`维护记录/需求锚定基线.json` 原本不含这两条（它们此前是 🟡），因此无需同步删除，本轮未新增“未锚定的 ✅”。

## 一、REQ-S07-15：切批失败中止定稿

### 根因
`storyboard_final.finalize` 的切批段用 `try: … assign(…) … except Exception: app_logging.swallowed()` 把切批异常整体吞掉，随后继续发布**没有 `batch_id`** 的定稿；残缺产物只在 SG-03 暴露。

### 改动（文件:函数）
- `storyboard_final.py:finalize`：`assign` 抛任何异常时，先 `app_logging.swallowed()` 记一次日志，再抛
  `ValueError('批次划分失败，已中止定稿：' + str(exc))`，并 `from exc`（原异常即 `__cause__`）。异常发生在 `dest.mkdir`、别名登记、发布与 `retire_working` 之前，因此失败路径不产生任何定稿产物。
- `shot_batches.py`：**未改**（切批规则原样）。
- `storyboard_final_controller.py`：**未改**。先读现有调用链确认已有 `ValueError` 展示通路，无缺口：
  - 手动：`desktop.make_final_storyboard` → `async_` 捕获后把 `str(e)` 入队 → `desktop_async_tasks._tick_async_result` 走 `self.notifier.error(str(value), title='操作未完成')`。
  - 自动：`desktop_auto_flows.poll_auto_final` 后台线程 `except Exception as exc` → `('自动定稿未完成：'+str(exc))` 入队 → `_tick_auto_final` `self.status.set(value)`。

## 二、REQ-S07-44：定稿派生 `batch_plan.md` 与 `shot_table.md`

### 根因
`stage_layout.DOCS['07分镜定稿']`（`batch_plan.md`、`shot_table.md`）与 `stage_layout` 的 JSON/MD 对照表都声明了这两份人读文档，但全仓无任何代码生成，属于“声明有、实现无”。

### 改动（文件:函数）
- `storyboard_final.py` 新增模块级辅助：
  - `_batch_plan_markdown(episode)`：按 `shot_batches.batches` 归组，逐批列 `## B01`、镜头号、数量、合计时长、三元组（场景／角色／状态变体），并给出一句切批依据（三元组变化／满 4 镜／累计超 18 秒）。
  - `_shot_table_markdown(episode)`：`# 镜头表` + 一镜一行表格（镜头号、批次、场景、角色、时长）。
  - `_publish_final_docs(project, episode)`：路径用 `stage_layout.dirname_of('final')` + `stage_layout.paths(...)['docs']`（不手拼目录名）；写入沿用 `finalize` 写 `episode.json` 的同一 L3 入口 `stage_execution_service.publish_stage_text`（经 `agent.publication` 事务原子发布），**不直接 `save_text`/`write_text`**。
- `storyboard_final.py:finalize`：在 `publish_stage_text(...)` 成对发布 `episode.json`/`assets.json` 且 `_record_lineage` 之后、`retire_working` 之前调用 `_publish_final_docs(project, episode)`。签名复用分支与切批失败路径都不会走到这里。
- 内容完全由 `episode['shots']`（已带 `batch_id`）派生，无时间戳或其它不确定字段；重复定稿（同一内容签名）输出稳定一致；权威仍是 `episode.json`。

## 验收实测

### REQ-S07-15
- **V1 通过**：`tests/test_req_s07_anchors.py::S07AnchorTests.test_req_s07_15_batch_assignment_failure_aborts_finalize`。用 `mock.patch.object(shot_batches, 'assign', side_effect=RuntimeError('三元组字典损坏'))` 替换切批（未改生产规则）；`finalize` 抛 `ValueError`，消息含“批次”与原因文本；`caught.exception.__cause__ is failure`。
- **V2 通过**（同一用例）：`07分镜定稿/分镜` 下无新建子目录、无 `ALIAS_FILE`、`docs/*.md` 为空、源文件字节与调用前一致，且注入的 `retire_working` 一次未被调用。
- **V3 通过**：`tests.test_req_s07_anchors` 17 tests OK（其中原有正常定稿用例 `test_req_s07_16/17/19/20/21/30/31` 仍绿）；`tests.test_shot_batches` 27 tests OK（`assign` 正常回填 `B01…` 的既有断言未变）。
- **V4 通过**：先红见下；变异验证见下，还原后 sha256 一致。
- **V5 通过**：`docs/stages/S07_分镜定稿.md` 的 REQ-S07-15 改为 ✅（去掉“待定”口吻与行号，改函数名）；DES-S07-13 并入中止语义；测试锚定表补 `REQ-S07-15`；`tests/test_req_s07_anchors.py` docstring 写 `REQ-S07-15`。

### REQ-S07-44
- **V1 通过**：`tests/test_req_s07_anchors.py::S07AnchorTests.test_req_s07_44_finalize_derives_batch_plan_and_shot_table`。两镜三元组不同 → 2 个批次；`07分镜定稿/docs/` 下出现 `batch_plan.md` 与 `shot_table.md`；`batch_plan.md` 中每个 `B0x` 与镜头号都出现在 `episode.json` 的 `shot_batches.batches` 结果里；`shot_table.md` 数据行数＝镜头数（表头 1 行 + 一镜一行），且每行含该镜 `shot_id`/`batch_id`/`scene_id`/`estimated_duration`。
- **V2 通过**（同一用例）：同输入再 `finalize` 走签名复用分支（返回同一目录），`batch_plan.md` 字节不变，`docs/` 下仍只有这两份 `.md`，无重复文件。
- **V3 通过**（同一用例第二段）：新建临时项目，`assign` 抛异常时 `finalize` 抛 `ValueError`，`docs/batch_plan.md`、`docs/shot_table.md` 均不存在。
- **V4 通过**：先红见下；变异验证见下，还原后 sha256 一致。
- **V5 通过**：REQ-S07-44 改为 ✅ 并改写现状；新增 DES-S07-44（并入“待定”行同步收窄为只剩 REQ-S07-43）；测试锚定表补 `REQ-S07-44`；docstring 写 `REQ-S07-44`。
  - `architecture.md:337` 的“分镜定稿 … 输出类型 JSON、Markdown”现在已有代码对应，但该文件不在任务允许改动范围，本轮未改（无需改动即已一致）。
  - 同一阶段文件内 `storyboard_final.py:NN-NN` 一类易漂移行号引用顺带改为函数名（本轮插入代码使其漂移），事实内容未变。
  - `README.md:1467/1468/1485` 仍写旧内部目录名 `04_storyboard_final/docs/…`，属文档陈述，写入“需裁决事项”。

## 先红证据（实现前）

两条用例在实现前一起运行：

```
FAIL: test_req_s07_15_batch_assignment_failure_aborts_finalize
AssertionError: ValueError not raised          # 旧逻辑吞掉 assign 异常、继续发布
FAIL: test_req_s07_44_finalize_derives_batch_plan_and_shot_table
AssertionError: False is not true              # plan.is_file() 为假，全仓未生成 docs
Ran 2 tests ... FAILED (failures=2)
```

正常路径回归在同一轮由既有 `test_req_s07_anchors`（15 条旧用例）继续通过。

## 变异验证（生产改动）

1. **S07-15 变异**：临时删除 `raise ValueError(...) from exc`（恢复“只 `swallowed()` 后继续”的旧行为）。
   - `test_req_s07_15_…` 变红：`AssertionError: ValueError not raised`。
   - 附加诊断脚本显示旧行为确实发布残缺品：`PUBLISHED_DIR EP001_分镜定稿_20261020`、`BATCH_IDS [None, None]`、`ANY_BATCH False`。
   - 还原后 `storyboard_final.py` sha256＝`4BEFA7C14277C80514C75030E3AC2D842852922C3DC7E3CA88D91EB77D8C7963`，与变异前一致；用例复跑 OK。
2. **S07-44 变异**：临时删除 `finalize` 中的 `_publish_final_docs(project, episode)` 调用。
   - `test_req_s07_44_…` 变红：`plan.is_file()` 断言失败。
   - 还原后 sha256 同为 `4BEFA7C1…C7963`，与变异前一致；`tests.test_req_s07_anchors` 17 tests OK。

## 验证记录（实际执行）

- `tests/test_req_s07_anchors.py`：17 tests OK（改动前后均跑；改前 15 条绿、新增 2 条红→绿）。
- 消费方测试（`grep -ln "storyboard_final\|finalize\|shot_batches\|batch_plan\|shot_table" tests/*.py` 命中的全部文件，逐个单文件）：
  `performance_contract`（常量模块，非用例模块，`Ran 0 tests`/exit 5）、`test_audio_subtitle_scope` 16 OK、`test_confirm_gates` 31 OK、`test_continuity_ledger` 19 OK、`test_file_cache` 26 OK、`test_final_service` 1 OK、`test_keyframe_batch_plan` 15 OK、`test_keyframe_scope` 10 OK、`test_perf_batch_queue` 3 OK、`test_recycle_write_ahead` 9 OK、`test_req_s07_anchors` 17 OK、`test_req_s08_anchors` 19 OK、`test_shot_batches` 27 OK、`test_stage_layout` 21 OK、`test_stage_wiring` 16 OK、`test_storyboard_final_controller` 5 OK、`test_storyboard_final_scope` 19 OK、`test_video_ui` 66 OK。
  （`test_stage_layout`/`test_stage_wiring`/`test_video_ui` 需 `PYTHONPATH=tests` 才能导入 `skip_reasons`，加上后全绿；未改任何测试。）
- `PYTHONPATH=tests python -B -m unittest tests.architecture.test_requirement_traceability tests.architecture.test_layers`：10 tests OK。
- 相关架构门禁 7 个模块：12 tests OK。
- `python -B smoke_test.py`：通过 8 / 失败 0。
- `test_requirement_traceability.py --find REQ-S07-15` → `tests/test_req_s07_anchors.py: S07AnchorTests.test_req_s07_15_batch_assignment_failure_aborts_finalize`；`--find REQ-S07-44` → 对应 `.test_req_s07_44_finalize_derives_batch_plan_and_shot_table`。
- 未运行：`run_selftests.py`、`smoke_test.py --architecture/--affected`、全量回归（均按任务书禁止）。

**实际命令计数**：40 次 Python 解释器调用（基线 2、先红 1、实现后定向 4、消费方单文件 17＋需 PYTHONPATH 的 3、任务书架构门禁 1、相关架构门禁 1、冒烟 1、变异与还原 5、诊断/展示脚本 2、`--find` 2、收尾复验 3（含测试加固后与文档改后复跑））。

## 改了哪些既有测试的哪个预期

**无。** 本轮只在 `tests/test_req_s07_anchors.py` 新增两个测试方法；未修改、未弱化、未跳过任何既有测试的断言或预期值。

## 断言未动声明

**断言未动**（既有测试的断言与预期值一条未改；新增用例按 REQ-S07-15/44 验收条件新增）。

## 需裁决事项

1. **docs 的粒度**：两份 Markdown 写在 `stage_layout` 声明的阶段级 `07分镜定稿/docs/`，多集项目共用同一对文件，后一次新定稿会覆盖前集内容。若要按集分目录（如 `<EP>_分镜定稿/docs/`），需要同时改 `stage_layout` 的 DOCS/对照表契约，超出本轮允许范围。
2. **docs 与定稿 JSON 非同事务**：`episode.json`/`assets.json` 先成对原子发布，随后两份 docs 各自经 `publish_stage_text` 发布；若 docs 发布失败，定稿已在盘上而 `finalize` 抛错。是否要求三者整包原子，需契约层裁决。
3. **文档旧内部目录名**：`README.md:1467/1468/1485` 仍写 `04_storyboard_final/docs/…`（`architecture.md` 本轮无需改、已与代码一致），超出允许改动范围，未动。
4. **`stage_layout.STAGES` 对 07 的产出声明 `storyboard_final.json`**（REQ-S07-43，仍 🟡）与本轮无关，未动。

## 独立验收（Claude，车道 lane_c1 内隐藏桌面运行）

- 范围：1 个生产文件（storyboard_final.py）、1 份 docs/stages（S07）、1 个测试文件（test_req_s07_anchors 追加两条，既有断言未动）。执行方为官方 deepseek-v4-flash（免费档 WorkBuddy 国内站账号被限，已回落）。
- 锚点与消费方：S07 锚点 17/17，消费方 shot_batches、storyboard_final_scope、storyboard_final_controller、confirm_gates、continuity_ledger、file_cache、final_service、stage_layout、stage_wiring、req_s08_anchors、keyframe_batch_plan、keyframe_scope、audio_subtitle_scope、recycle_write_ahead 逐个全绿；架构追溯与分层 10/10。
- 门禁：smoke_test.py 8/8；smoke_test.py --architecture 通过。
- 变异：回退 storyboard_final.py 的全部生产改动，S07-15 与 S07-44 两条锚点变红（17 条中失败 2），还原后 sha256 一致（4befa7c1…）。
- test_video_ui 的 PromptBoxHeightTests 4 条在隐藏桌面上失败，主分支同样复现，是隐藏桌面不做字体行高排版所致，与本轮无关；执行方在可见桌面跑 66/66 通过。
- 未跑：run_selftests 全量与 --all --safe（本轮不属触发条件）。
- 已登记待裁决：docs 为阶段级共用目录，多集会互相覆盖；docs 与 episode.json 非同事务；README 旧目录名。
