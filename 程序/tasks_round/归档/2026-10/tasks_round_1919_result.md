# R1919 结果：性能轮（视频页 tick 减负收尾，含 R1914～R1916 合入）

- 本轮类型：性能轮。分支 `codex/wip-perf-tick`，变基到 master `6198a839` 后快进合入。
- 提交（最终合入 master 的 hash）：R1914 `9f98e639`、R1915 `fa0aa62b`、R1916 `e1d37bc9`、R1919 `153cda22`；master 快进到 `153cda22`（合入前因 master 被别的会话推进两次，变基两次，均无冲突）。
- 起因：用户反馈应用卡顿。度量显示 import 总耗时仅约 160ms，卡顿来自 `app.py` 的 150ms `tick` 在 UI 线程上每秒做的重复读盘与路径解析。

## 改动

- `file_cache.read_json_shared`：不拷贝、签名未变时不加发布事务锁（`read_json` 每次命中也要开 `writer.lock`）。
- `video_progress`、`video_prompt_results`、`video_task_state` 改用它。
- `video_task_state.generation_active`：按「工作集清单＋config/state 文件签名」缓存其他工作集的活跃镜头集合。
- `storyboard_paths.resolved_path／config_listing／file_signature`：`resolve()` 与 `cloud_video` 清单复用（放这里而不是 `video_task_state`，因为后者的公开入口被 `architecture.test_service_return_contract` 固定）。
- `app.py`：行内进度仅在文字变化时写表格；`update_prompt_controls(periodic=True)` 仅 tick 周期调用走签名跳过，其他调用点行为不变。
- 新增 `tests/test_video_task_state_cache.py`、`tests/test_file_cache.py::ReadJsonSharedTests`。断言未动。

## 实测（隐藏桌面，60 镜头＋4 个云端工作集，每次 100 轮）

| 项目 | 改前 | 改后 |
| --- | --- | --- |
| tick 每秒一套合计 | 22.8ms | 5.0ms |
| update_prompt_controls | 10.7ms | 1.8ms |
| refresh_shared_progress | 9.4ms | 1.2ms |
| prompt_results.poll | 2.7ms | 2.0ms |
| 60 镜头逐个 prompt_locked 一轮 | 208ms | 49ms |

内置 Python 无 `cProfile`，用 `perf_counter` 逐函数计时。数字来自模拟数据，真实项目会有出入。

## 验证

- `smoke_test.py --affected file_cache video_task_state video_progress video_prompt_results app`：改前一次 843 条用例有 2 个文件红——`architecture.test_service_return_contract`（本轮造成，已通过搬迁辅助函数修复，断言未动）与 `test_ui_edges.test_pet_storyboard_batch_dispatches_the_selected_scripts`（会员登录闸门，**在干净 master 上同样失败**，R1913 引入，与本轮无关，未处理）。
- 修复后复验：`run_selftests.py --architecture` 全绿；`-k video_task_state_cache test_video test_cloud_video video_ui video_result file_cache request_ledger paths` 全绿。**未重跑完整 `--affected`（约 7.5 分钟），也未跑 `--all --safe`**。
- 未经实机操作界面验证；缓存失效依赖 mtime＋大小，外部工具写入同大小且 mtime 不变的极端情形未覆盖。

## 未做

- `engine.Studio.state()` 每次加锁读取（约 0.5ms/次）未动，改动面较大。
- 另有 `req_anchor` 相关测试在本 worktree 因缺外部 SKILL 文档失败，与本轮无关。
