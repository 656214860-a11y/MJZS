# R3312 结果：L2领域服务层优化任务书轮7（功能轮：infra/business_log＋8 模块业务字段日志）
<!-- round-evidence: {"commit_base": "105aeda3", "credential_hits": 0, "evidence_sha256": "863807ab8545e569", "exit": 0, "failed": 0, "passed": 17, "round": 3312, "tests": "run_selftests.py -k business_log"} -->

## 三问

**1. 本轮属于 §3 哪种类型？**
§3.1 功能轮。任务书轮 7「`infra/business_log.py` 实现＋8 个大模块接入」——前置轮 6（R3310）已交付 `infra/unit_of_work` 事务原语，本轮交付轮 7 全部三项：设施实现、8 个零日志大模块接入、`perf_counter` 主入口耗时。

**2. 测试跑了吗、三个基线过了吗？**

| 基线 | 结果 |
| --- | --- |
| 新测试文件 | `tests/test_business_log.py` 342 行 / **17 用例全绿**（设施直测 8＋八模块集成 8＋八入口 cost_ms 汇总 1） |
| 定向自检 | `run_selftests.py -k <11 关键词>` → **71 个测试文件 / 1009 条用例 / 288.9 秒 / 0 红文件 / ALL TESTS PASSED**（关键词覆盖 business_log 与 8 模块全部直接测试及消费者：idea_chat/white_model/recon/storyboard_catalog/idea_transcript/domain_cache_locks/message_parts/speech_api/voice/asset_batch/confirm_gates/domain_events/uow_write_paths/unit_of_work/previs/continuity/asset_detail/stage_wiring/script_composer/model_manager/offline_asr/req_s03/req_s05/req_s09/adoption_impact/ui_writing/seedream/test_assets） |
| `smoke_test.py --affected` | **绿**：门禁定向同上 71 文件串行 892 秒 / 0 红文件；冒烟合计 **10/10 通过** |
| 默认冒烟 `smoke_test.py` | **9/9 通过**，exit 0 |
| 架构门禁 `smoke_test.py --architecture` | **502 条 / 192.95s / FAILED（failures=2）**：失败集合 `{test_entry_files_stay_within_budget, test_round_number_continuous}` 与 R3275–R3310 记录的**分支固有红集合逐名一致**（AGENTS.md HEAD 即 16028>16000 字节预算；`project_status.md` 状态页 3259 冻结、仅 master 可提交，本轮对两文件零改动）。本轮曾引入的 2 条红已修复并复跑确认：① `business_log._emit` 同名触发事件总线边界「新增 _emit 包装器必须先登记」→ 改名 `_write_payload`（最小修复，不登记——它不是 pet_bus 状态事件转发器）；② `business_log.py` 分支决策点基线失配（0≠15）→ `scripts/branch_coverage_report.py` 工具重测刷新基线（82 个目标用例＝原 81＋`tests.test_business_log`，目标用例全通过，business_log 15 决策点 / 13 覆盖 / 86.7%） |
| 全量回归 `--all --safe` | **未运行**：本轮非 master 提交点累计触发条件；改动为日志旁路（finally 内一条 `log_event`），不触写入边界白名单、Tk 生命周期、删除语义与层级登记表 |

**3. 欠账少了吗？**
减少。R3310 遗留欠账中「轮 7 `business_log`＋8 模块接入」已交付：任务书点名的「`domain/` 38 条日志 0 业务字段」现状中，8 个零日志大模块主入口各有一条结构化业务事件（JSON：`kind`＋白名单字段＋`cost_ms`），日志设施自身异常全部吞掉不弄崩业务。剩余欠账如实记录：轮 8 `ServiceResult` 收口、轮 9 `tts_api`/`white_model` 两处硬违规、分支固有架构红 2 条、`business_log` 分支覆盖下限仍 0.0（棘轮上调属专项）。

## 设计决策

| 决策点 | 结论与理由 |
| --- | --- |
| **记录格式** | `logging.getLogger("business")` 单条 JSON：`{"kind": ..., <白名单字段按键名排序>, "dropped_fields": [...]?}`，与 `app_logging` 的 perf/swallowed/crash/startup 同根处理器随 `logs/app.log` 滚动落盘；logger 级别 NOTSET 时自设 INFO，保证 `install()` 前也能落盘 |
| **白名单外字段处置** | **丢弃＋留名**：白名单（`FIELDS = {stage, shot_id, asset_id, cost_ms, outcome}`）外的键不进 payload，字段名经安全字符集折叠后记入 `dropped_fields`（≤8 个、只记名不记值）。选择「丢弃＋留名」而非抛 `ValueError`：日志设施绝不能弄崩业务，登记遗漏在日志里可见即可 |
| **值清洗** | `stage`/`shot_id`/`asset_id`/`outcome` 只收 `[A-Za-z0-9_.-]` 形态短标识符（≤96 字符，bool/数字/含空白/路径分隔符/盘符/URL/中文自由文本一律丢弃）；`cost_ms` 只收有限 int/float（bool 除外）输出 1 位小数毫秒；`kind` 同安全字符集 ≤120 字符、不合法降级 `"unknown"`。调用方**不得**传自由文本——实现侧只做形态兜底，语义约束靠 docstring 与评审 |
| **绝不抛** | `log_event` 全函数体 try/except，内部任何异常（含序列化、logger 故障）经 `app_logging.swallowed("business_log.log_event")` 留痕后吞掉；有专测 `test_log_event_never_raises` 双路注入故障验证 |
| **计时口径** | 各模块选定主入口 `time.perf_counter()` 起点＋`try/finally` 落 `cost_ms`，成功/失败/缓存命中各给独立 `outcome`（`ok`/`error`，recon 幂等命中 `cached`、asset_batch 已有图 `skipped`、confirm_gates `passed`/`blocked`），最小侵入不改业务逻辑 |
| **与 paid.invoked 并存** | `recon_service` 业务日志是本地通道（每 `run` 一条、含幂等命中），`collect()` 内 `domain_events.PAID_INVOKED` 总线事件语义不动、不重复不混用 |

## 八模块接入清单（模块 → kind → 业务字段）

| 模块 | 选定主入口 | kind | 字段 |
| --- | --- | --- | --- |
| `domain/idea_chat.py` | `receive_brief` | `idea_chat.receive_brief` | `stage`（入参 stage，默认 script）、`outcome`(ok/error)、`cost_ms` |
| `domain/white_model_service.py` | `migrate_legacy_directories`（薄包装 `_migrate_legacy_directories`） | `white_model.migrate` | `stage='previs'`、`outcome`(ok/error)、`cost_ms` |
| `domain/recon_service.py` | `run` | `recon.run` | `stage='script'`（STAGE 常量）、`outcome`(ok/cached/error)、`cost_ms` |
| `domain/storyboard_catalog_service.py` | `catalog_snapshot` | `storyboard_catalog.snapshot` | `outcome`(ok/error)、`cost_ms`（跨 script＋storyboard 两目录，无单一 stage 语义） |
| `domain/idea_transcript.py` | `append` | `idea_transcript.append` | `stage='script'`、`outcome`(ok/error)、`cost_ms`（对话正文属用户内容绝不进字段） |
| `domain/speech_api.py` | `create_session` | `speech_api.create_session` | `outcome`(ok/error)、`cost_ms`（后端路由无阶段语义，密钥/后端名不进字段） |
| `domain/asset_batch_service.py` | `register_image` | `asset_batch.register_image` | `stage='assets'`、`asset_id`、`outcome`(ok/skipped/error)、`cost_ms`（资产名与图片路径属用户内容不进字段） |
| `domain/confirm_gates.py` | `run` | `confirm_gates.run` | `stage='continuity'`、`outcome`(passed/blocked/error)、`cost_ms`（门禁判定细节与项目内容不进字段） |

## 验收对照（任务书轮 7）

- [x] **每模块至少一条带业务字段的事件** → 上表 8 条 `log_event` 均带白名单业务字段（`cost_ms`＋`outcome` 全员具备，6 模块另带 `stage`/`asset_id`）；`tests/test_business_log.py` 8 个集成用例各触发选定入口并断言捕获对应 kind 事件。
- [x] **用例断言日志文本不含盘符、不含用户项目绝对路径** → `test_absolute_paths_never_reach_the_log`：以 `Path(tmp)` 绝对路径注入 `stage`/`shot_id`/`asset_id` 等字段，断言落盘文本不含 `[A-Za-z]:\\` 盘符形态与 `/`、`\\` 起头的绝对路径；8 个集成用例复用 `assert_no_path_leak` 逐条校验。
- [x] **用例断言 8 个模块主入口均有耗时字段** → `test_all_module_entries_emit_cost_ms` 汇总驱动 8 入口，逐条断言 `cost_ms` 为数值；各集成用例亦单独断言。
- [x] **`smoke_test.py --affected` 覆盖 8 模块** → `--affected business_log idea_chat white_model recon storyboard_catalog idea_transcript speech_api asset_batch confirm_gates domain_events uow_write_paths` → 门禁定向 71 个测试文件（含全部直接测试与消费者）串行 892 秒 0 红；冒烟合计 10/10。

## 改动清单（12 个文件）

| 文件 | 改动 |
| --- | --- |
| `infra/business_log.py` | 23 行空壳 → 126 行实现：`log_event(kind, **fields)`＋`_write_payload`/`_clean_text`/`_clean_ms`/`_clean_kind`/`_clean_dropped_name`；白名单 `FIELDS`、丢弃留名、值形态兜底、全异常吞掉 |
| `domain/idea_chat.py` | `receive_brief` 加 `perf_counter`＋`try/finally` 事件（复用既有 `import time` 场景外新增顶层 import） |
| `domain/white_model_service.py` | `migrate_legacy_directories` 拆薄包装＋`_migrate_legacy_directories` 原体，finally 发 `white_model.migrate` |
| `domain/recon_service.py` | `run` 整体入 try/finally；cached/ok/error 三分支 outcome；`paid.invoked` 语义不动 |
| `domain/storyboard_catalog_service.py` | `catalog_snapshot` 入 try/finally 发 `storyboard_catalog.snapshot` |
| `domain/idea_transcript.py` | `append` 入 try/finally 发 `idea_transcript.append` |
| `domain/speech_api.py` | `create_session` 入 try/finally 发 `speech_api.create_session` |
| `domain/asset_batch_service.py` | `register_image` 入 try/finally 发 `asset_batch.register_image`（ok/skipped/error） |
| `domain/confirm_gates.py` | `run` 入 try/finally 发 `confirm_gates.run`（passed/blocked/error） |
| `tests/test_business_log.py` | 新增 342 行 17 用例：设施直测（结构化 JSON/白名单处置/值清洗/cost_ms 校验/kind 清洗/永不抛/路径零泄漏）＋8 模块集成＋8 入口 cost_ms 汇总 |
| `维护记录/分支覆盖率基线.json` | `branch_coverage_report.py` 工具重测刷新：87 模块 / 决策点 1301/2435；`business_log.py` 15 决策点 / 13 覆盖 / **86.7%**；targets 81→82（＋`tests.test_business_log`），目标用例全通过 |
| `tasks_round/tasks_round_3312_result.md` | 本文件 |

## 实测基线汇总

- 新测试：`python -B tests/test_business_log.py` → **17 条 / OK**。
- 定向自检：`run_selftests.py -k business_log idea_chat white_model recon storyboard_catalog idea_transcript domain_cache_locks message_parts speech_api asset_batch confirm_gates domain_events uow_write_paths unit_of_work voice previs continuity asset_detail stage_wiring script_composer model_manager offline_asr req_s05 req_s03 req_s09 adoption_impact ui_writing seedream test_assets` → **71 文件 / 1009 用例 / 288.9s / 0 红 / ALL TESTS PASSED**。
- 受影响门禁：`smoke_test.py --affected <11 关键词>` → 门禁串行 71 文件 **892s / 0 红**；冒烟 **10/10**。
- 默认冒烟：`python -B smoke_test.py` → **9/9**，exit 0。
- 架构门禁：`python -B smoke_test.py --architecture` → **502 条 / 192.95s / failures=2**，失败集合 `{test_entry_files_stay_within_budget, test_round_number_continuous}` 与 R3275–R3310 分支固有红逐名一致；`git diff HEAD -- AGENTS.md project_status.md` 为空，两失败输入文件本轮零改动。本轮引入的 2 条红已修复：`_emit`→`_write_payload` 改名＋分支覆盖基线工具重测，`test_event_bus_boundary`/`test_branch_coverage_floor` 两文件 9 用例复跑全绿。
- 全量回归：`--all --safe` 未运行（理由见三问表）。

## 偏差与说明

1. **`_emit` 改名 `_write_payload`**：事件总线边界门禁对全体生产文件扫描名为 `_emit` 的函数并只登记 `pet_agent`/`pet_ui` 两个 pet_bus 转发包装器；`business_log` 的内部落盘函数同名触发「新增 _emit 包装器必须先登记」。它不是状态事件转发器，登记反而语义错误，故改名为最小修复（`_WRAPPERS` 声明表未动）。
2. **`speech_api`/`storyboard_catalog` 事件无 `stage`**：`create_session` 是跨阶段语音后端路由、`catalog_snapshot` 同时扫 script＋storyboard 两类目录，均无单一阶段语义；`outcome`＋`cost_ms` 已满足「至少一条带业务字段」，不虚构 stage 值。
3. **`recon.run` outcome 三值**：幂等命中（marker key 相同且 `load_card` 有缓存）记 `cached`，与 `ok`（真实重采＋落盘）区分；异常路径 `error`。`paid.invoked` 每真实付费调用一条的语义保持原样。
4. **分支覆盖率下限表未动**：`business_log.py` 下限仍 0.0（实测 86.7%）——下限表「只许人工上调」，棘轮收紧留待专项；与 `idempotency.py`（轮 6 新增、下限 0.0）先例一致。
5. **`targets` 增补 `tests.test_business_log`**：基线 targets 由 81 → 82，新增本轮专测使 L1 新模块获得真实分支覆盖度量；其余 80 个目标与全部既有模块测量值未变（基线 diff 仅 business_log 行、targets 与 totals）。
6. **未动外来文件**：`tasks_round/L2领域服务层优化任务书.md`（外来勘误改动）、R3276 外来未跟踪四件（诊断报告/结果文件/任务书×2）、`project_status.md`（仅 master 可提交）一律不入暂存区。

## 遗留欠账

- 任务书轮 8（4 处 `ServiceResult` 收口）、轮 9（`tts_api` 走 `http_client`、`white_model` 去盘符硬编码）——后续轮次。
- 分支固有架构红 2 条（AGENTS.md 字节预算、状态页轮次冻结）——存量问题，与本轮无关，待 master 合并轮处理。
- `infra/business_log.py` 分支覆盖下限 0.0（实测 86.7%）——棘轮上调留待专项轮次。
- 全量 `--all --safe` 未跑；若验收要求对最终树补跑可另行执行。
- 全部轮次收尾后输出 `tasks_round/任务完成/L2领域服务层优化·任务完成.md`（任务书 §7.2），本轮非末轮不产出。

## 提交

- 分支 `codex/wip-r3282`（领号 R3312，工作树 `dsh-864fd932-4054`；领号记录见 `<git common-dir>/round-claims.json`，R3311/R3313 属并行工作树 `dsh-5158b800-34ae`）。
- 主提交：待补记。
- 轮次证据以 `tasks_round/evidence/R3312.json` 为准（`--tests business_log` 定向重跑）。
