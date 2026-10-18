# R1721：契约轮——4 条待拍板需求裁决落地（REQ-S04-60/61/62、REQ-S06-26）

- 类型：修复轮（按任务书只改声明与提示文字；派发执行，不领号、不提交、不改 `project_status.md`）。
- 改动文件：`confirm_gates.py`、`stage_flow.py`、`docs/REQUIREMENTS.md`、`docs/DESIGN.md`、`tests/test_animatic_scope.py`、`tests/test_continuity_scope.py`、本结果文件。
- 未改：`stage_layout.py`、`skills/**`、UI 批次文件、`client_profiles`、`workflow_settings`。

## 1. 每条裁决改了哪里

- **REQ-S04-60：未落地（按任务书停止）**。消费者核查命中 `storyboard_draft.json`，故没有改 `stage_layout.py:44` 的输入声明，也没有删 `DOCS['04分镜预演']` 的 `animatic_notes.md`。`docs/REQUIREMENTS.md` 仍为 ❓，已把“没有任何代码读写”的旧表述改成实测证据，见该条 2026-10-19 复核注。
- **REQ-S04-61**：`docs/REQUIREMENTS.md` 的 REQ-S04-21、REQ-S04-61 改写为“03 不写 `batch_id`、07 划定；默认只有 `default` 一批；批间并行是保留能力”；`docs/DESIGN.md` 的 DES-S04-05 补充同口径，并新增 DES-S04-12。新增 `tests/test_animatic_scope.py::test_req_s04_61_without_batch_id_defaults_to_one_default_batch`。
- **REQ-S04-62**：`docs/REQUIREMENTS.md` REQ-S04-62 改为 ✅（2026-10-19 裁决）：预演成果只供本阶段核对与追溯，下游不读、不消费，文件保留；`docs/DESIGN.md` 新增 DES-S04-13。新增 `tests/test_animatic_scope.py::test_req_s04_62_animatic_products_stay_upstream_only`。
- **REQ-S06-26**：`confirm_gates.py` 的 G-08 `condition`／`reject` 及模块说明改为“可选、建议，可跳过，不影响 SG-02 放行”；`stage_flow.py` 的 continuity `RECOVERY_HINTS` 改为“可按……（可选、建议；不阻塞 SG-02）”；`docs/REQUIREMENTS.md` REQ-S06-26 改为 ✅（2026-10-19 裁决）；`docs/DESIGN.md` 新增 DES-S06-26。新增 `tests/test_continuity_scope.py::test_req_s06_26_g08_is_optional_and_sg02_does_not_depend_on_it`。
- SKILL（只列位置，未改）：`skills/06连贯性SKILL/continuity-conflict-adjudicate.skill.md:32`（“等用户……点一下”）、`:43`（`continuity.resolveConflict`）；`skills/06连贯性SKILL/pipeline-continuity.skill.md:29`、`:57`（保留人工裁决／人工裁定入口）。

## 2. 消费者核查结果

执行 `git grep -n -F -- storyboard_draft.json` 与 `git grep -n -F -- animatic_notes.md`：

- `storyboard_draft.json` **有真实消费者**：`storyboard_selection.py:203,244-248` 写入；`storyboard_selection.py:258-272` 的 `draft_problems` 读取；`stage_parallel.py:674-675` 的 SG-A `animatic_input_ready` 调用 `draft_problems`。`tests/test_animatic_service.py:42,101,133,148`、`tests/test_storyboard_scope.py:103` 也使用该文件。
- `animatic_notes.md` 只有声明：`stage_layout.py:124` 与 docs；无生产代码读写。
- 结论：命中任务书“若有，停下”，因此 REQ-S04-60 未改声明，也未单独删除 notes。

## 3. 命令实际计数

- `python -B -m unittest tests.architecture.test_requirement_traceability`（`PYTHONPATH=tests`）：**4/4 OK**，0 红。
- `python -B run_selftests.py -k stage_layout animatic continuity stage_flow`：**9 个测试文件、147 条用例、0 文件有红、0 跳过**，3.2 秒。
- `python -B smoke_test.py --affected confirm_gates stage_flow`：**9/9 通过**；内层定向 **4 个测试文件、79 条用例、0 文件有红**，7.8 秒。
- 补充直接定向：`python -B -m unittest tests.test_animatic_scope tests.test_continuity_scope`：**25/25 OK**。
- 未运行：默认 8/8 单跑、架构门禁单跑、完整安全全量；`project_status.md` 未改，欠账数字不变。

## 4. 需裁决事项

1. **REQ-S04-60**：`storyboard_draft.json` 已有生产消费者，不能按原裁决把它从输入声明中拿掉；`animatic_notes.md` 无消费者。请裁决：只删除 `animatic_notes.md` 声明并保留 `storyboard_draft.json`，还是接受 `storyboard_draft.json` 作为“已采用分镜清单”的落盘索引并改写需求口径？该项确认前不能改 ✅，也不能补对应测试锚定。
2. 无其他需裁决事项；其余三条已按裁决落地。

## 自检

- 未改既有断言；只新增针对新口径的测试，原有测试文件中的既有方法未改。
- 未执行任何 git 写命令；未碰其他执行者的未提交改动。
- 代码改动仅限 G-08／恢复提示文字；无行为、路径、分层或依赖变化。

## G DEC4b（REQ-S04-60 收尾）

- 类型：修复轮收尾（派发执行；未执行 git 写命令、未领号、未提交、未改 `project_status.md`）。
- 沿用 DEC4 已落地的 S04-61／62、S06-26，未回退。

### 1. 改动

- `stage_layout.py`：`DOCS['04分镜预演']` 删除 `animatic_notes.md` 条目，改为显式空元组并加注释（确认记录以 `animatic_manifest.json` 的 `confirmed` 为准）。`STAGES` 中本阶段输入 `storyboard_draft.json` 原样保留。
- `tests/test_animatic_scope.py`：新增 2 条 REQ-S04-60 锚点：
  - `test_req_s04_60_sga_reads_storyboard_draft_index_for_readiness`：`sync_draft_outputs` 写出索引 → SG-A 通过；篡改索引 `sources` 后 SG-A 拒绝，`detail` 指向 `storyboard_draft.json`；
  - `test_req_s04_60_animatic_docs_no_longer_declare_notes_file`：`docs_rows()` 与 `readme_text` 均不再出现 `animatic_notes.md`。
- `tests/test_stage_layout.py`：既有 `test_every_stage_has_a_chinese_name_and_a_docs_list` 的“每阶段 docs 清单非空”断言与裁决冲突，做最小契约同步：仍要求每阶段在 `DOCS` 有显式清单，只允许 04 为显式空元组，其余 12 阶段仍必须非空。**该文件不在任务书允许清单，见需裁决事项 1。**
- `docs/REQUIREMENTS.md`：REQ-S04-60 从「待拍板」移到「输入与启动」，改 ✅ 并写「（2026-10-19 裁决）」：`storyboard_draft.json` 是采用时写下的落盘索引、SG-A 经 `draft_problems` 读取；确认记录以 `animatic_manifest.json` 的 `confirmed` 为准，不再登记 `animatic_notes.md`。
- `docs/DESIGN.md`：新增 DES-S04-14（REQ-S04-60）；「待定」行只保留 REQ-S04-52；测试锚定表补 REQ-S04-60。仅动 S04 节。

### 2. 消费者核查

删除前 `git grep -n -F -- animatic_notes.md`：命中 `docs/DESIGN.md:186`、`docs/REQUIREMENTS.md:216`、`stage_layout.py:124`、历史结果 `tasks_round_1657_result.md:19`；`tests/`、`skills/` 无引用。两条 docs 引用已随本轮改写（表述为“不再登记”）；历史结果文件未改。删除后无生产代码读写 `animatic_notes.md`。

`storyboard_draft.json` 复核确认有真实消费者：`storyboard_selection.sync_draft_outputs` 写入（`storyboard_selection.py:244-250`）、`draft_problems` 读取核验（`:258-282`）、SG-A `animatic_input_ready` 经 `draft_problems` 判定（`stage_parallel.py:666-680`）。

### 3. 先红后绿（删除声明前）

```
test_req_s04_60_sga_reads_storyboard_draft_index_for_readiness ... ok
test_req_s04_60_animatic_docs_no_longer_declare_notes_file ... FAIL
AssertionError: 'animatic_notes.md' unexpectedly found in ['animatic_notes.md']
Ran 2 tests in 0.125s
FAILED (failures=1)
```

删除 `animatic_notes.md` 声明并同步契约后：

```
test_req_s04_60_sga_reads_storyboard_draft_index_for_readiness ... ok
test_req_s04_60_animatic_docs_no_longer_declare_notes_file ... ok
Ran 2 tests in 0.090s
OK
```

### 4. 命令实际计数

- `PYTHONPATH=tests python -B -m unittest tests.architecture.test_requirement_traceability`：**4/4 OK**，0 红。
- `python -B tests/architecture/test_requirement_traceability.py --find REQ-S04-60`：命中 `tests/test_animatic_scope.py` 2 个方法（另有模块 docstring 与 `tests/test_stage_layout.py` 的契约测试）。
- `python -B run_selftests.py -k stage_layout animatic continuity stage_flow storyboard_selection stage_parallel`：**202 条用例、0 文件有红、0 跳过**，3.6 秒。
- `python -B smoke_test.py --affected stage_layout`：**9/9 通过**（内层 `test_stage_layout` 21 条、0 红）。
- 未运行：默认 8/8 单跑、`--architecture` 单跑、完整安全全量；`project_status.md` 未改，欠账数字不变。

### 5. 需裁决事项

1. **`tests/test_stage_layout.py` 超出允许清单**：裁决删除 04 唯一 docs 声明后，既有断言“每阶段 docs 清单非空”必红（`run_selftests -k stage_layout` 验收命令内含该文件）。最小同步为：仍要求每阶段在 `DOCS` 有显式清单，仅允许 04 为空，其余阶段保持非空。请确认接受该契约同步；若不接受，需要另定方案（例如为 04 保留一份非确认用途的 docs 占位，或删除该断言）。
2. **`DOCS['04分镜预演']` 保留显式空元组**：效果等同“无 docs 声明”，但让“每阶段都声明 docs 清单”的契约仍可检查。若要求连键一起删除，则 `test_stage_layout.py` 与 `docs_rows()` 的契约需要重定。
3. 无其他阻塞；未碰 `skills/`、UI 批次文件、`client_profiles`、`workflow_settings` 及其他执行者的未提交改动。

## 独立验收（Claude，隔离验证工作树 HEAD＋本批文件）

- 定向 `-k stage_layout animatic continuity stage_flow storyboard_selection stage_parallel confirm_gates readme`：0 红。
- `smoke_test.py --affected confirm_gates stage_flow stage_layout`：0 失败。
- `smoke_test.py --architecture`：368/368 OK。
- 接受 `tests/test_stage_layout.py` 契约同步：仅 04 允许显式空 docs 清单，其余 12 阶段仍须非空，断言未弱化。
- SKILL 中相关措辞只列位置未改（见结果文件第 1 节）。
