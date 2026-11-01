# R1854 结果：把 R1853 的潜伏缺陷变成门禁，补无断言测试（修复轮）

- 三问：本轮是 §3.2 修复轮（含 R1853 引入的一处架构红）；定向与架构门禁见“验证”；`project_status.md` 欠账未变（分支不写状态页）。
- 计划来源：vibe coding 体检计划批次 2；队列无对应 ID。

## 新门禁（`tests/architecture/`，均为 AST 扫描 `production_runtime_files()`，含 `agent/`）
1. `test_atomic_write_boundary.py` 新增两条：直接 `os.replace(a, b)` 与单参数 `X.replace(target)`（Path.replace）只许出现在登记写入器内，且每模块处数只许减少。登记现状 17 处：`agent/core.py` 1（权威）、`agent/publication.py` 2、`image_agent_runner.py` 1、`log_maintenance.py` 2、`skill_import_service.py` 2、`skill_registry.py` 1、`stage_execution_service.py` 3、`stage_write_preparation_service.py` 3、`white_model_service.py` 2。另有检测器自测（`str.replace` 两参数不误报）。
2. `test_subprocess_timeout_boundary.py`：`subprocess.run/call/check_call/check_output` 无 `timeout=`、任何 `.communicate()` 无 `timeout=`、零参数 `.wait()` 均判违规。扫描时生产运行时代码已为 0 处（R1853 已修完），登记表为空。
3. `test_workflow_dir_ratchet.py`：含“工作流任务”的字符串常量（不计 docstring）按模块计数，只许减少，新模块出现即红。登记 23 个模块共 37 处；`stage_layout`／`stage_path_service` 目前没有这个目录的入口，收口需先在路径权威加入口。
4. `test_read_json_definitions.py`：`def read_json` 只许 `agent/core.py`（失败返回默认值）、`file_cache.py`（抛错、返回拷贝）、`video_navigation.py`（坏文件即 `{}`）三处，禁止新增。
5. `test_pet_error_log_boundary.py`：pet_* 模块类内不得把 `errors` 赋为 `[]`／`list()`；唯一例外 `pet_bus.Bus`（`_record_error` 自行按 `error_limit` 裁剪）。

`architecture.md` §“当前架构门禁清单”同步加入 4 个新文件（`test_agents_md` 的集合相等检查依赖它）。

## 先红后绿
在程序根目录临时放 `pet_zz_gate_probe.py`（含 `os.replace`、无超时 `subprocess.run`、手拼“工作流任务”、`def read_json`、`self.errors = []`），5 条门禁全部变红；删除后 14 条全绿：
```
FAIL: test_direct_replace_is_limited_to_registered_writers
AssertionError: Lists differ: ['pet_zz_gate_probe.py: 1 处直接 replace > 登记 0 处'] != []
FAIL: test_production_waits_carry_timeout
AssertionError: Lists differ: ['pet_zz_gate_probe.py:9'] != []
FAIL: test_hand_built_workflow_dir_only_shrinks
AssertionError: Lists differ: ['pet_zz_gate_probe.py: 1 处 > 登记 0 处'] != []
FAIL: test_no_new_read_json_definitions
AssertionError: Lists differ: ['pet_zz_gate_probe.py:3'] != []
FAIL: test_pet_errors_use_bounded_error_log
AssertionError: Lists differ: ['pet_zz_gate_probe.py:7'] != []
Ran 14 tests — FAILED (failures=5)；删除探针后 Ran 14 tests — OK
```

## 无断言测试补断言（断言只增不减）
用 AST 扫 `tests/` 找出没有任何断言调用的测试方法 4 个；`test_video.test_poll_recovers_persisted_identity_after_restart` 委托给带断言的同类方法，不算。补了 3 个：
- `test_app_logging.test_swallowed_outside_except_is_noop`：返回 None、`_swallow_counts` 为空、最近吞异常列表不变、`app.log` 不含“已忽略”。
- `test_assets.test_valid_safetensors`：`assertIsNone(validate_safetensors(p))`。
- `test_ui_motion.test_destroying_spinner_cancels_animation`：销毁后 `running` 为假、原定时器 id 不在 `after info` 里、`report_callback_exception` 未收到异常。

## 修 R1853 引入的架构红
`test_unification_ratchet.test_bare_json_load_debt_is_a_nonincreasing_subset` 红：`qwen_setup.load` 改为 `utf-8-sig` 后，那条已豁免 `json.loads` 的 AST 指纹从 `d8914783a47c6a77` 变成 `ac18a8a332712bed`。`维护记录/架构统一基数.json` 里更新锚点，仍为 exempt；原 reason 写“外部进程／网络响应解析，非文件读”与事实不符（它读的是本机 `LOCALAPPDATA/漫剧制作助手/qwen-api.json`），一并改为如实描述。R1853 结果文件里的定向回归没有覆盖架构门禁，所以当时没发现。

## 验证
- `run_selftests.py -k test_app_logging test_assets test_ui_motion`（隐藏桌面）：ALL TESTS PASSED。
- `smoke_test.py --architecture`（隐藏桌面），改前首次跑 394 条：3 失败 1 错误——上面这条棘轮红（本轮已修），其余见下。复跑结果见下一行。
- 环境／分支固有红（与本轮无关）：`test_agents_md.test_performance_history_is_declared_as_historical_only`（未跟踪的 `维护记录/基准历史.json`）、`test_skill_reference_injection`（`skills/00全流程SKILL/AIGC创作全流程` 子模块未检出）、`test_round_baselines.test_round_number_continuous`（分支不得提交 `project_status.md`，状态页轮次头停在 1849，合入 master 补记后恢复）。
- 默认冒烟、全量未在本轮跑；全量在 R1856 统一跑。

## 复跑
- `smoke_test.py --architecture`：Ran 394（本轮新增 10 条，改前 384），2 失败 1 错误，正是上面三条环境／分支固有红；棘轮红已消除。
- 默认冒烟 `smoke_test.py`：通过 8 项，失败 0 项。

- 已提交：见提交记录。未 push。
