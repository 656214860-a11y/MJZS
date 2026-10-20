# R1765：契约轮——阶段声明的定稿产出由 storyboard_final.json 改为实际文件名（C4，S07-43）

- 轮次类型：**契约轮**（`AGENTS.md` §3.4；只改 L0 `stage_layout` 契约声明，不动运行时代码逻辑）。
- 需求／设计：`REQ-S07-43`、`DES-S07-43`。

## 三问

1. **本轮属于 §3 哪种类型？** 契约轮。
2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟：**8/8 通过**（`python -B smoke_test.py`）。
   - 架构门禁：任务书指定的 `tests.architecture.test_requirement_traceability`＋`tests.architecture.test_layers` 共 **10/10 通过**。任务书明确禁止跑 `--architecture`、`--all --safe`、`run_selftests.py`，故未跑全量架构门禁，由调度方验收。
   - 全量回归与欠账：**未运行**（任务书禁止全量）；未使用、未伪造任何 `full-safe-receipts.json` 凭据。
   - 消费方测试：`grep -ln "stage_layout\|contract_rows\|stage_contract_report" tests/*.py` 命中的 **29 个测试文件逐个单文件运行，全部 exit=0 / OK**（见下）。
3. **`project_status.md` 的欠账少了吗？** 执行方不改状态页，无法从状态页核对；`project_status.md` 里没有 `REQ-S07-43`／`storyboard_final.json` 字样。本轮把 S07 文档中唯一一条 🟡（REQ-S07-43）转为 ✅，文档欠账减少 1 条，状态页如需同步由提交方处理。

## 根因与改动

根因：`stage_layout.STAGES` 的 07 输出声明与 08／09／11 输入声明沿用了历史名 `storyboard_final.json`，而实际定稿产物是 `episode.json`＋`assets.json`；全仓没有代码写 `storyboard_final.json`。该字段只用于 `readme_text()` 生成阶段 README 与 `stage_contract_report.contract_rows()` 展示，不参与运行时路径解析（`stage_path_service` 只用 `row[0]`；`git grep` 未发现其它消费 `row[4]`／`row[5]` 的运行时代码），与任务书判断一致。

改动（文件:常量／条目）：

- `stage_layout.py:STAGES`
  - 07 `final` 输出：`('storyboard_final.json',)` → `('episode.json', 'assets.json')`
  - 08 `keyframe` 输入：`('storyboard_final.json',)` → `('episode.json', 'assets.json')`（下游 `agent.shot_assets.asset_rows` 优先读定稿目录的 `assets.json` 快照）
  - 09 `previs` 输入：`('storyboard_final.json', 'frames.json')` → `('episode.json', 'assets.json', 'frames.json')`（`previs_batch_service` 经 `agent.shot_assets.assets` 读定稿快照；`frames.json` 为既有声明，保留）
  - 11 `audio` 输入：`('storyboard_final.json',)` → `('episode.json',)`（`dialogue_assets()` 读的是项目资产库 `assets.json`，不读定稿快照，故不列 `assets.json`）
- `stage_layout.py:json_md_rows()`：`'storyboard_final.json · batch_id'` → `'episode.json · batch_id'`，目标路径不变。
- `docs/stages/S07_分镜定稿.md`：REQ-S07-43 由 🟡 改 ✅ 并按现状重写（去掉行号与“待统一后处理”口吻，改用函数／常量名）；新增 DES-S07-43；原“待定（REQ-S07-43）”一句收窄为“待定：无”；测试锚定表补 `REQ-S07-43` 行。
- `docs/stages/S08_首帧管理.md`：DES-S08-01 的输入名同步。
- `docs/stages/S11_配音与字幕.md`：REQ-S11-02、DES-S11-01 的输入名同步。
- `README.md`：仅 1412～1416、1485 表格单元里的 `storyboard_final.json` 同步为实际文件名；旧目录名与同行其它内容未动。
- `tests/test_req_s07_anchors.py`：新增 `REQ-S07-43` 锚点（docstring 写 `REQ-S07-43`，断言 07／08／09／11 的具体元组、声明中无旧名、`json_md_rows()` 对照行）。
- 既有测试预期同步：见“改了哪些既有测试的哪个预期”。

未改：任何运行时逻辑、文件名、目录名、别名规则、产出文件；未新增模块或产物。

## V1–V5 实测

### V1（声明正确、旧名清零、下游与实读一致）

新增 `tests/test_req_s07_anchors.py::S07AnchorTests::test_req_s07_43_stage_layout_declares_the_real_final_files`，断言：

- `final` 输出 `== ('episode.json', 'assets.json')`
- `keyframe` 输入 `== ('episode.json', 'assets.json')`
- `previs` 输入 `== ('episode.json', 'assets.json', 'frames.json')`
- `audio` 输入 `== ('episode.json',)`
- 遍历 `STAGES` 全部输入／输出，`storyboard_final.json` 不出现
- `json_md_rows()` 含 `('episode.json · batch_id', '07分镜定稿/docs/batch_plan.md', '批次是机器切的，说明给人看')`

结果：改后 **PASS**（单文件 1 test OK）。

### V2（全仓 grep）

改后 `git grep -n "storyboard_final\.json" -- .` 剩余：

| 位置 | 性质 |
| --- | --- |
| `docs/stages/S07_分镜定稿.md:44` | 解释性：REQ-S07-43 正文说明“`stage_layout.STAGES` 不再出现这个旧名” |
| `tests/test_req_s07_anchors.py:648` | 解释性：`assertNotIn('storyboard_final.json', declared)` 反向锚点 |
| `tasks_round/tasks_round_1660_result.md:20` | 历史结果文件 |
| `tasks_round/tasks_round_1762_result.md:115` | 历史结果文件 |
| `维护记录/20260919_自主优化总结.md:14401,14403,14405,14409,14547` | 历史记录（V2 明确排除） |
| `维护记录/第63期_交付物与验收_20260923.md:245` | 历史记录（V2 明确排除） |
| **`skills/templates/final_process_template.yaml:19`** | **仍在役的流程模板，非历史／解释性；不在允许改的文件内，列入需裁决事项** |

`stage_layout.py`、`README.md`、`S07/S08/S11` 文档中的声明与表格已无该名（S07 仅保留上述解释性一句）。`升级备份/`、`.bak` 未命中。

### V3（先红后绿＋变异验证）

- 改前（先加新断言／同步三处旧预期，未改 `stage_layout.py`）运行四个目标文件：**4 failures**，其中新锚点首行断言 `('storyboard_final.json',) != ('episode.json', 'assets.json')`；其余三处为旧的 README／audio／keyframe 预期未满足。
- 实现后同一命令：**65 tests OK**。
- 变异：临时把 07 输出改回 `('storyboard_final.json', 'assets.json')`，单跑 V1 锚点 → **1 failure**（`('storyboard_final.json', 'assets.json') != ('episode.json', 'assets.json')`）；还原后单跑 → **OK**。
- 还原比对：`stage_layout.py` sha256 变异前／还原后均为 `C10E5E183987545F48176A3887A6215125EA912656904DA481FDD1F375EC7738`，字节一致。

### V4（既有测试预期同步）

只同步预期值，未删除／弱化其它断言：

1. `tests/test_audio_subtitle_scope.py::test_req_s11_02_depends_only_on_final_storyboard`：`_audio_row()[4]` 预期 `('storyboard_final.json',)` → `('episode.json',)`。
2. `tests/test_keyframe_scope.py::test_req_s08_01_stage_is_eighth_and_reads_final_storyboard`：`assertIn('storyboard_final.json', row[4])` → `assertIn('episode.json', row[4])`。
3. `tests/test_stage_layout.py::test_readme_is_the_input_output_contract`：07 README 文本断言 `assertIn("storyboard_final.json", text)` → `assertIn("episode.json", text)`。

**断言未动**：上述三处仅为预期值同步，断言形式与强度保持不变；三个文件其余断言、其它测试文件均未改动。

### V5（文档）

- `docs/stages/S07_分镜定稿.md`：REQ-S07-43 已改 ✅ 且改为现状描述（函数／常量名，不再写行号）；补 DES-S07-43；原“待定（REQ-S07-43）”收窄为“待定：无”；测试锚定表补行。
- `docs/stages/S08_首帧管理.md`、`docs/stages/S11_配音与字幕.md`：相应输入名同步。
- `tests/test_req_s07_anchors.py`：新增锚点 docstring 写 `REQ-S07-43`；`python -B tests/architecture/test_requirement_traceability.py --find REQ-S07-43` 已能定位到该用例。
- 需求追溯门禁通过（10 tests OK）。

## 实际命令计数

本轮实际执行测试／验证进程 **38 次**：

- 四文件合并：4 次（1 次缺 `PYTHONPATH=tests` 导入失败后重跑、1 次基线绿、1 次先红、1 次实现后绿）
- V1 变异：2 次（变异红、还原绿）
- 架构门禁（两项）：1 次
- 默认冒烟：1 次
- 消费方单文件：29 次（每个文件一个独立进程，全部 exit=0 / OK）
- 需求追溯 `--find`：1 次

另执行 2 次 `sha256` 校验（不计测试进程）。

消费方 29 个文件及结果（全部 OK）：`test_agents_md`、`test_path_authority`、`test_pipeline_stage_io_contract`、`test_stage_paths`、`test_animatic_scope`、`test_animatic_service`、`test_asset_detail`、`test_audio_subtitle_scope`、`test_confirm_gates`、`test_confirm_gates_cache`、`test_continuity_issues`、`test_continuity_ledger`、`test_continuity_scope`、`test_delivery_scope`、`test_editing_scope`、`test_keyframe_scope`、`test_legacy_adoption_service`、`test_previs_scope`、`test_recon_service`、`test_req_s07_anchors`、`test_script_contract`、`test_script_structure_scope`、`test_slowpage_first_paint`、`test_smoke_affected_consumers`、`test_stage_layout`、`test_stage_wiring`、`test_storyboard_final_scope`、`test_video_generation_scope`、`test_video_manifest_scope`。其中 `tests/architecture/_layers.py` 是辅助模块、非测试文件，未计入。

## 需裁决事项

1. **`skills/templates/final_process_template.yaml:19`** 仍写 `name: 写入 storyboard_final.json`（第 20 行 `action: write_final_storyboard`），是仍在役的流程模板，不属于历史／解释性语境，且不在任务书允许改的文件内，本轮未动。建议下一轮把它改成实际产物（`episode.json`／`assets.json`）或与真实动作名对齐；这是 V2 “只剩历史／解释性语境”唯一未闭合项。除该模板自身外，全仓未发现其它模块依赖这个旧名。

## 交付前自检

- 验收标准：V1–V5 均按任务书实测，证据见上；V2 唯一例外已列需裁决。
- 改动范围：只改任务书允许的 9 个文件（1 生产＋4 文档＋4 测试）；无越界。
- §5 适用验证：默认冒烟、指定架构门禁、全部消费方单文件均通过；全量按任务书未跑。
- 新问题：未发现；`DOCS`／阶段 README 生成仅文本随声明变化，无其它副作用（消费方测试覆盖）。
- 结论：**通过**（V2 的模板项待裁决）。

## 独立验收（Claude，车道 lane_c4 内隐藏桌面真实环境直接运行）

- 范围：`stage_layout.py` 常量与对照行（`git diff` 逐行读过，无运行时逻辑改动）、README 表格行、S07／S08／S11 文档、4 个测试文件；其中 `test_audio_subtitle_scope`、`test_keyframe_scope`、`test_stage_layout` 只把预期文件名同步为 `episode.json`，断言结构未动；`test_req_s07_anchors` 新增 REQ-S07-43 一条。
- 定向：`grep stage_layout|contract_rows|storyboard_final` 找到的 27 个消费方测试文件逐个跑，26 个全绿；`test_asset_detail` 的失败与主干基线一致（keyboard_buttons 3 条基线同样失败，`test_reload_restores_focus` 为已确认的偶发）。
- 门禁：`smoke_test.py` 8/8；`smoke_test.py --architecture` 375/375。
- 遗留：`skills/templates/final_process_template.yaml:19` 的“写入 storyboard_final.json”是在役流程模板，不在本轮允许改的文件内，另派小轮对齐。
