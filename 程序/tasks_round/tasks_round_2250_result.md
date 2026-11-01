# R2250 结果：stage_config 无项目读取不再把 None 写成缓存键（缺陷轮）

## 三问
- 轮次类型：缺陷轮（§3）。用户「先查全量红」的第一处根因。
- 测试和三个基线：
  - 新增 `tests/test_stage_config_empty_project_cache.py`（2 条）。改前红：`stage_config.get(None, …)` 把 `None` 存进 `_GET_CACHE`，随后 `put` 在 `_invalidate_cache` 里 `key[0]` 抛 `TypeError: 'NoneType' object is not subscriptable`（1 失败 1 错误）；改后 2 条过。
  - 定向 `run_selftests.py -k stage_config stage_model_value stage_prompt_governance writing_status_line`：全过。
  - `smoke_test.py --architecture`（经 gui_hidden）411 项，仅 worktree 缺子模块的两项红（`test_agents_md`、`test_skill_reference_injection`，主检出不红）。
  - 全量未手动跑；合并后看后台全量。
- `project_status.md` 欠账：未增减（本分支不写状态页）。

## 查全量红的结论（HEAD 994993db 后台全量，17:34，557 秒）
- 红：test_clipboard_lock、test_stage_model_value、test_stage_prompt_governance、test_writing_response_preservation、test_writing_status_line、test_leak_teardown。前一次（c9a6890）的四个架构红已由 R2239 消除；其余 test_* 红单跑全过。
- 根因一（本轮修）：某测试用空项目调用 `stage_config.get`，`None` 进了进程级缓存，同进程内后续任何 `put`／`save_all` 都崩，表现为按分组随机红。真实应用里项目为空时同样会留下这个坏键。
- 根因二（未改，环境类）：`test_clipboard_lock` 用真实的跨进程剪贴板锁，另一个进程（运行中的应用、别的会话的测试）正持有时必红；与代码无关，单跑可过。

## 改动
- `stage_config.py`：`get` 两处写缓存前判 `key is not None`。断言未动。
