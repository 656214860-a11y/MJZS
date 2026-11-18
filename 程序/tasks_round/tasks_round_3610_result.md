# R3610 结果文件 — L1 任务书轮 I12：诊断日志统一与写盘门禁（FL-09 = 0）
<!-- round-evidence: {"commit_base": "2ee0ca83", "credential_hits": 0, "evidence_sha256": "d5fd4e5ed8f5dd52", "exit": 0, "failed": 0, "passed": 241, "round": 3610, "tests": "run_selftests.py -k log_sink_boundary app_logging secret_sink_audit image_agent_runner writing_api stage_parallel pet_agent"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.3 结构治理轮（任务书明定：每轮 ≤ 3 个模块，按 I0 清单分批）。I0-5（R3386 F12/FL-09）清点的 4 文件/5 位点一次清完：3 处诊断写盘迁往 `logging` 命名记录器（经 `infra/app_logging` 落 `logs/app.log`、`_Redact` 脱敏、RotatingFileHandler 轮转）；1 处裁定为功能性期录登记产物白名单不迁移（裁定依据见下）。新增 `tests/architecture/test_log_sink_boundary.py` 门禁。
2. **测试跑了吗、基线过了吗？** 跑了。任务书定向命令 `run_selftests.py -k log_sink_boundary app_logging secret_sink_audit image_agent_runner writing_api stage_parallel pet_agent` **241 条 0 红**；`smoke_test.py` 默认冒烟 **9/9 绿**；`smoke_test.py --architecture` 结果见「验证汇总」。
3. **欠账少了吗？** 是。FL-09 由 I0 实测 4 文件/5 位点 → 诊断写盘 0（非白名单口径）；LR-08 日志横切能力守卫落地（`test_log_sink_boundary` 已进 architecture.md LR-08 行与 `规则守卫基线.json`）；I12-1/I12-2 验收点全部落实。

## 领号说明

- R3610 由本工作树经 `维护记录/基准脚本/round_claim.py next` 领得（输出含已知 GBK 解码噪声，登记成功，`round-claims.json` 可查本工作树/`codex/l1-enterprise`）。

## I0-5 清单逐项处置（4 文件/5 位点）

| I0 位点 | 处置 | 说明 |
| --- | --- | --- |
| `image_agent_runner.py:26` `<批次>/执行日志.txt` 追加 | **迁移** → `logging.getLogger(__name__).info` | 批次工作目录里的诊断流水；`print` 与 `执行状态.json` 状态文件原样保留 |
| `writing_api.py:157` `logs/claude_empty_response.log` 追加空响应元数据 | **迁移** → 命名记录器输出同一 JSON 元数据 | `EMPTY_RESPONSE_LOG` 常量移除；诊断元数据（status/stop_reason/block_types/usage）不变，只改落盘通道 |
| `stage_parallel.py:479`（I0 记 477）`log_write()` → `logs/<阶段>.agent_logs.jsonl` | **迁移** → 命名记录器输出同一 `log_row` JSON | `log_write` 返回值兼容为 `None`；`log_path`/`log_read`/`log_row`/`log_line` 保留，历史 jsonl 仍可读回；`pet_agent.log_stage` 的内存行（UI 阶段日志面板数据源）不受影响 |
| `pet_agent.py:989` `_journal()` → `工作流任务/宠物/事件日志.jsonl` | **产物白名单，不迁移** | 裁定为功能性幂等期录：`pet_bus.Bus(journal=同路径)` 共写同一文件、幂等键 submit/skip 记录是持久台账；`business_log.FIELDS` 白名单（stage/shot_id/asset_id/cost_ms/outcome）无法承载 id/stage/shot/model/params 键集，迁移会丢数据并破坏与 pet_bus 的共文件协议。I0 建议的「迁 business_log」经消费者分析证伪，如实记录偏离 |

**排除项复核（I0-5 原判不变）**：`qwen_adapter.py:58` `process.qwen_input` 为 Qwen CLI stdin IPC；`qwen_adapter.py:136`、`workflow_engines.py:211/235/272/291` 的 `logfile`/`response_temp` 为引擎 stdout/stderr 捕获与响应产物（I9 进程监督器边界）——全部登记 `LOG_SINK_PRODUCT_WHITELIST`，不属于诊断日志。

## 门禁实现（I12-2）

`tests/architecture/test_log_sink_boundary.py`：

- **检测器**（AST）：L2–L5 登记模块（`_layers.LAYERS` layer≥2）中写模式打开（mode 含 `w`/`a`/`x`）且目标「日志样」的位点——`.log`/`.txt` 字面量、名字含 `log` 的变量/调用（`logfile`、`EMPTY_RESPONSE_LOG`、`log_path()`）、或外层函数名含 log 记号（`_LOG_TOKEN` 边界正则，`log_write` 类命中、`catalog`/`dialog` 不误伤）；显式排除 `webbrowser.open(url)`、`os.devnull`。
- **棘轮**：`log_sink_sites_by_module()` 实测 {`workflow_engines`:3 @211/272/291, `qwen_adapter`:1 @136}，与 `LOG_SINK_PRODUCT_WHITELIST`（引擎工件，值＝当前位点数）逐模块 `count ≤ 白名单` 断言；非白名单模块必须为 0，只减不增。
- **坏样本自审**：`.log`/`.txt` 字面量、log 变量、log 函数内间接 `path.open` 命中；读打开、`.json`/`.lock`/`.lock` 后缀、devnull、webbrowser 不命中（2 条样本用例钉死口径）。
- **I12-1 验收**（`MigratedDiagnosticsSinkTests`，3 条）：patch `app_logging.LOGS/APP_LOG/FAULT_LOG` 到临时目录＋`install()` 后——`Events.put` 注入 `api_key=sk-FAKE-12345` 断言 app.log 含「执行」「[已脱敏]」不含密钥原文；`_record_empty_response` 断言 `block_types` 落 app.log；`log_write` 断言 stage/task/detail 落 app.log。

## 测试契约变更（§2.4，如实记录）

| 文件 | 变更 | 断言实质 |
| --- | --- | --- |
| `tests/test_stage_parallel.py` `LogTests.test_it_lands_in_the_stage_folder_and_reads_back` → `test_it_lands_in_the_diagnostic_log_and_legacy_files_still_read` | `log_write` 断言由「返回路径且 jsonl 落盘可读回」改为「assertLogs 捕获 INFO 记录＋返回 None」；另手工写历史 jsonl 验证 `log_read` 只读兼容 | 五键行结构、`log_line` 人话格式、`log_read` 兼容语义不变 |
| `tests/test_stage_parallel.py` `AgentWiringTests.test_the_stage_log_lands_in_the_project` | 「返回路径 is_file」改为「assertLogs＋返回 None」 | `agent_logs` 内存行（UI 数据源）断言原样保留 |
| `tests/test_writing_api.py` `test_empty_claude_response_retries_once_then_records_failure` | `patch.object(EMPTY_RESPONSE_LOG)`＋`meta.log is_file` 改为 `assertLogs('writing_api')` 断言 `block_types` | 重试 2 次、返回 text='' 断言原样 |

`pet_agent.py` 仅 docstring 同步（`log_stage` 不再写 jsonl）；`_journal` 零代码改动。

## 基线与门禁同步

- `architecture.md`：新增 R3610 轮次记要；「依赖与平台边界」门禁清单补 `test_log_sink_boundary.py`；LR-08 行原已含该守卫名（I1 预登记），本轮实体落地。
- `维护记录/规则守卫基线.json`：LR-08 数组补 `tests/architecture/test_log_sink_boundary.py`（JSON 校验通过）。
- 任务书 I12-1/I12-2 勾选同步。
- `pet_agent`/`image_agent_runner`/`writing_api`/`stage_parallel` 定向与受影响回归全绿，无覆盖率基线触发项（无新模块、无新增大函数）。

## 验证汇总

- `run_selftests.py -k log_sink_boundary app_logging secret_sink_audit image_agent_runner writing_api stage_parallel pet_agent`：**241 条 0 红**（初跑 `test_the_stage_log_lands_in_the_project` 一条契约红，按 §2.4 同步后复绿；`test_stage_parallel` 单独复跑 54/54 绿）。
- `smoke_test.py`：**9/9 绿**。
- `smoke_test.py --architecture`：首跑 560 条 2 红——`test_generated_report_is_in_sync`（规则守卫对照.md 未随基线同步，`scripts/rule_guard_map.py --write` 重生成后 7/7 绿）＋ `test_site_packages_whitelist`（环境项见下）；复跑 **560 条仅余 1 红 `test_site_packages_whitelist`**（pydantic 五包跨分支污染，R3564 已详录，与本轮零因果）。

## 环境备注

- R3590 已录环境项不变：共享运行环境 pydantic 五包污染（`test_site_packages_whitelist` 红，跨分支环境问题，与本轮零因果）；隐藏桌面 ffmpeg `0xC0000142` 间歇抖动（R3407 立项跟踪）。
