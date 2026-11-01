# R2227 引擎适配器共用实现（结构治理轮·执行）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 08 的 J13、J14：J13「`NoRedirect` 收成一份，其余模块改用」；J14「子进程 `_run` 去重；`WanAdapter` 接到 `VideoAdapter`」。

## 基线
分支 `codex/wip-R2227`，自 R2223。

## 轮次类型／三套基线／债务
结构治理轮·执行，等价委托，不改行为；分层无变化，无新增生产模块，无新增债务。

## 改动
- J13：`api_endpoints.no_redirect()` 为唯一实现；`model_pool`、`local_video`、`seedream_api`、`tts_api`、`agent/volcengine` 删除各自副本改用它。`batch_frames_tool` 内的副本不在本组范围，保留。
- J14：`workflow_process_registry.run_registered(args, project, prompt, streams, timeout, *, timeout_label, env=None)` 为唯一「启动＋登记＋超时结束进程树」实现；`workflow_engines._run` 与 `qwen_adapter` 委托它（超时文案由 `timeout_label` 区分）。进程启动经 `platform_tools.launch_text_process`（新增，包装 `launch_background`），生产代码不再直接 `subprocess.Popen`，`_BACKGROUND_BOUNDARIES` 因而去掉 `qwen_adapter`、`workflow_engines`，审计 21 命中保持 0。
- `agent/wan.WanAdapter` 继承 `VideoAdapter`。

## 新增测试
`tests/test_shared_adapter_infrastructure.py`：各适配器共用同一 `no_redirect` 实现且重定向被拒；引擎 `_run` 委托并注销登记；子进程超时被结束并带调用方文案；`WanAdapter` 是 `VideoAdapter`。

## 测试
- `run_selftests.py -k shared_adapter workflow_engines qwen local_video seedream tts wan volcengine cloud_video model_pool platform_tools` 全部通过。
- `smoke_test.py --architecture` 仅余环境既有红项（`test_round_number_continuous`、`test_performance_history_is_declared_as_historical_only`）。
- `tests/test_workflow_engines_run.py` 仅同步 patch 目标到新位置，断言未动。
- 未运行：全量 `--all --safe`（留待候选全部完成后）。

## 回滚
`git revert` 本轮提交。

## 下一步
J15–J17（候选 06 无人值守决策；J16 先写失败用例）。
