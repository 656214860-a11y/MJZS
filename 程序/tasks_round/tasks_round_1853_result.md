# R1853 结果：修 7 处测试抓不到的潜伏缺陷（修复轮）

- 三问：本轮是 §3.2 修复轮；测试见下（定向全绿，受影响消费者回归结果见“验证”）；`project_status.md` 欠账未变（分支不写状态页）。
- 背景：用户读了 vibe coding 风险文章后要求体检。只读体检列出 7 处潜伏缺陷；每处先写复现测试（`tests/test_latent_defects_r1853.py`），确认变红后再改。
- 修复：
  1. `file_cache.read_json` 原先把缓存里的同一个对象给所有调用方；`engine_probe.record` 改完再写盘、写失败时，缓存与磁盘不一致；`white_model_service.read_record` 也就地改。用户选“返回拷贝”：只重建 dict／list 骨架（实测 109 KB 约 1 ms，比重新解析 1.5 ms 便宜），仍免读盘和解析。契约变更：`tests/test_file_cache.py` 里三处 `assertIs` 改为“相等 + 不重新解析（patch json.loads 抛错）”，共享对象测试改为断言不是同一对象；断言强度未降。
  2. 引擎子进程 `communicate()` 无超时：新增 `platform_tools.communicate_or_kill`（超时结束整棵进程树）。`workflow_engines` 默认 2 小时（`ENGINE_TIMEOUT_SECONDS`，阶段配置 `timeout_seconds` 可改，用户拍板）；`qwen_adapter` 默认 2 小时 10 分钟，比 CLI 自带的 `--max-wall-time 2h` 晚，让 CLI 先自停。
  3. `codex_tasks.RPC`：输出含一个非 UTF-8 字节就会结束读取线程，误报“Codex接口已关闭，请确认Codex已登录”。改为 `errors='replace'`；退出改为结束整棵进程树，`wait` 加超时。
  4. `workflow_process_registry` 用 `str(project)` 作键，Path 与正斜杠写法不一致时“强制停止”找不到进程。改为 `normcase(abspath())`。
  5. 三虎 `Pet`／`Cloud`／`Agent`／`StageQueue` 的 `errors` 无上限，150 ms 心跳里的持续异常会一直累积。新增 `pet_bus.ErrorLog`（list 子类，只留 `ERROR_LIMIT` 条，`total` 记累计数）。
  6. `qwen_setup.load` 用 `utf-8` 读设置，带 BOM 的文件解析失败后被静默当成默认值（用户的模型、地址丢失）。改为 `utf-8-sig`。体检里 `agent/publication.py` 那处只读程序自己写的日志，不会有 BOM，未改。
  7. `asset_detail_service` 直接调 `os.replace`，绕过 Windows 共享冲突重试与发布记录，一次瞬时“拒绝访问”就整次绑定失败。改走 `agent.core.replace`。
- 改前红（摘录）：
```
===== test_stage_queue_and_agent_errors_are_bounded (test_latent_defects_r1853.BoundedErrorLogTests.test_stage_queue_and_agent_errors_are_bounded) =====
AssertionError: 74 != 64 : StageQueue
===== test_same_folder_spelled_differently_finds_the_process (test_latent_defects_r1853.ProcessRegistryKeyTests.test_same_folder_spelled_differently_finds_the_process) =====
AssertionError: Lists differ: [] != [<object object at 0x0000021DD2EC15B0>]
===== test_settings_saved_with_bom_keep_user_values (test_latent_defects_r1853.QwenSettingsBomTests.test_settings_saved_with_bom_keep_user_values) =====
AssertionError: 'qwen3.7-plus' != 'my-model'
===== test_failed_ledger_write_leaves_cache_matching_disk (test_latent_defects_r1853.SharedCacheCopyTests.test_failed_ledger_write_leaves_cache_matching_disk) =====
AssertionError: {'sch[16 chars]s': {'codex': {'engine': 'codex', 'at': 'now',[32 chars]now'} != {'sch[16 chars]s': {}}
===== test_mutating_a_read_does_not_leak_into_the_next_read (test_latent_defects_r1853.SharedCacheCopyTests.test_mutating_a_read_does_not_leak_into_the_next_read) =====
AssertionError: {'engines': {'codex': {'ok': False}}, 'shots': [1, 2], 'extra': 1} != {'engines': {'codex': {'ok': True}}, 'shots': [1]}
===== test_transient_sharing_violation_is_retried (test_latent_defects_r1853.AssetBindingReplaceRetryTests.test_transient_sharing_violation_is_retried) =====
    raise ValueError(result.reason)
ValueError: 资产图片绑定失败，请检查文件权限和磁盘空间。
===== test_error_log_keeps_recent_entries_and_counts_all (test_latent_defects_r1853.BoundedErrorLogTests.test_error_log_keeps_recent_entries_and_counts_all) =====
    log = pet_bus.ErrorLog()
AttributeError: module 'pet_bus' has no attribute 'ErrorLog'
===== test_invalid_utf8_line_does_not_close_the_connection (test_latent_defects_r1853.CodexDecodeTests.test_invalid_utf8_line_does_not_close_the_connection) =====
    if reply is None:raise ValueError('Codex接口已关闭，请确认Codex已登录')
ValueError: Codex接口已关闭，请确认Codex已登录
===== test_default_timeout_is_two_hours_and_config_overrides (test_latent_defects_r1853.EngineTimeoutTests.test_default_timeout_is_two_hours_and_config_overrides) =====
AttributeError: module 'workflow_engines' has no attribute 'engine_timeout'
===== test_hung_engine_is_killed_and_unregistered_after_timeout (test_latent_defects_r1853.EngineTimeoutTests.test_hung_engine_is_killed_and_unregistered_after_timeout) =====
TypeError: _run() got an unexpected keyword argument 'timeout'
```
- 验证：
  - `run_selftests.py -k latent_defects file_cache` 全部通过（10＋26 条）。
  - 受影响消费者：`smoke_test.py --affected <13 个改动模块>` 的门禁在 900 秒上限内没跑完；改用同一份 `-k` 清单在隐藏桌面不设上限直跑（约 133 个测试文件）。只剩 4 个文件红，均为本工作树环境问题，与本轮改动无关：`test_workflow_writing_stages`／`test_writing_api_output_budget`／`test_master_skill` 缺 `skills/00全流程SKILL/AIGC创作全流程`（子模块，本工作树未检出）；`architecture.test_agents_md` 缺未跟踪的 `维护记录/基准历史.json`。
  - 契约同步（断言未动）：`tests/test_workflow_engines_run.py` 的假进程 `communicate` 与 `tests/test_run_background_equivalence.py` 的假 `_run` 补上 `timeout` 参数。
  - 全量 `--all --safe` 未跑，留到批次 2 合入后统一跑。
- 已提交：见提交记录。未 push。
