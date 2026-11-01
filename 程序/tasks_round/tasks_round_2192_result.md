# R2192 结果：后台排队／执行记录不再等落盘，成果发布事务少等 fsync（性能/资源轮）

## 三问
- 轮次类型：性能/资源轮（§3.7）。用户「逐步修复2-7项」第 3 项，取舍按用户裁决「元数据不 fsync，成果合并」：队列状态等元数据只做临时文件＋os.replace，进程崩溃仍安全，断电可能丢最近一次写入或整份需重建；用户成果仍 fsync，同一事务从 5 次降到 1–2 次。无对应队列 ID。
- 测试和三个基线：见文末「验证」。全量 `--all --safe` 本轮未手动运行。
- `project_status.md` 欠账：没有减少，也没有新增（本分支不写状态页，合并轮登记）。

## 根因
- 界面线程上每次后台提交、收尾、入队、领取都包在 `agent.publication.transaction()` 里：开事务写空日志、登记目标时复制旧版本并重写日志、正文临时文件、提交写 committed，共 4–5 次 fsync。本机 D 盘每次 20–100 ms，每项合计约 120–175 ms。
- `tests/performance_contract.py` 原注释把其中约 100 ms 记成「目录扫描」，实为 fsync。本轮已更正。

## 改动
- `agent/core.py`：`save`／`save_text` 加关键字参数 `durable=True`。`durable=False` 照样先写临时文件再原子替换，只是不 fsync。用户成果一律用默认值。
- `desktop_automation_service.py`：
  - 持久队列与执行记录（`outputs/desktop-task-queue.json`、`desktop-task-history.json`）的读写由 `transaction()` 改为 `access()`（同一把跨进程锁），写入用 `save(..., durable=False)`。
  - 新增 `_read_runtime_record`：JSON 读不出（断电后的全零、半份、空文件、乱码）时把原文件改名为 `<名>.corrupt` 留存，按空记录重建；改名失败也按空记录继续，写日志。读得出但版本或结构不对的，仍报原有错误、不覆盖。
  - `pop` 合并为一次 `access()` 内一次读取，去掉先查再嵌套事务的结构。
- `agent/publication.py`：
  - 待回滚日志推迟到第一次登记目标时才写；空事务不写日志。
  - 旧版本备份 `_backup`：同卷本机普通文件建硬链接（替换只改目录项，旧内容留在链接上）；跨卷、FAT、链接数满、云盘占位或脱机文件（REPARSE_POINT／OFFLINE／RECALL_*）照旧复制并 fsync。建链接前先删同名残留，防止回退复制时顺着链接截断原成果。
  - 提交改为删掉日志（`_commit`）；没有日志的事务目录恢复时按已提交丢弃。旧版本留下的 committed／pending／rolled_back 日志仍按原语义恢复。
- 测试：`test_publication_recovery.py` 只同步 mock（崩溃注入点 `committed` 改挂在 `_commit` 上），**断言未动**。`tests/performance_contract.py`、`tests/test_perf_batch_queue.py` 只改注释，门槛数字未动。

## 断电与崩溃语义
- 进程崩溃：队列、执行记录、成果事务都和改前一样，读到的是完整旧版或新版；崩溃注入测试 7 个点全过。
- 断电：
  - 队列与执行记录可能丢最近一次写入，或读出坏文件后改名留存、按空记录重建（用户已接受）。在途任务本就「只登记、不自动重提」，丢记录不会重复扣费。
  - 成果事务：日志在替换每个目标前已落盘，回滚保证不变。删日志即提交，NTFS 不保证删除立刻落盘，提交后几秒内断电可能回到完整旧版——和改前 committed 标记改名未 flush 同级，不会出现半份。
  - 硬链接备份的持久性与原文件相同：替换前原文件早已落盘。
  - 跨卷目标的原子性漏洞（各卷各自日志）是既有问题，本轮未引入也未修。

## 实测（本机，同一时段，每项 10 次中位数，两轮）
改前＝HEAD 模块经 importlib 加载，改后＝工作树。

| 操作 | 改前 ms（fsync 次数） | 改后 ms（fsync 次数） |
| --- | --- | --- |
| 队列入队 `enqueue_descriptor` | 121.7／121.6（4–5） | 6.2／5.9（0） |
| 队列领取 `pop` | 121.9／121.7（5） | 5.7／5.6（0） |
| 队列收尾 `_finish` | 121.8／116.2（5） | 5.9／6.0（0） |
| 执行记录 `submit` | 171.7／149.7（4–5） | 5.8／5.7（0） |
| 执行记录 `finish` | 176.9／154.9（5） | 5.8／6.2（0） |
| 同卷覆盖发布一份成果 | 115.4／143.8（5） | 44.2／44.2（2） |
| 跨卷（C:）覆盖发布一份成果 | 91.6／94.0（5） | 44.7／46.6（3） |

## 测试
- 新增 `tests/test_publication_fsync_budget.py`（7 条）、`tests/test_background_record_rebuild.py`（6 条）。改前红（被测模块换成 HEAD 版，测试取工作树）：`Ran 13 tests … FAILED (failures=7, errors=6)`，摘录：
  ```
  test_queue_round_trip_never_waits_for_disk        AssertionError: 38 != 0
  test_task_submit_and_finish_never_wait_for_disk   AssertionError: 14 != 0
  test_empty_transaction_does_not_wait_for_disk     AssertionError: 2 != 0
  test_link_failure_falls_back_to_flushed_copy      AssertionError: 5 != 3
  test_new_file_waits_for_body_and_journal_only     AssertionError: 4 != 2
  test_replacing_existing_file_waits_for_body_and_journal_only  AssertionError: 5 != 2
  test_old_version_is_kept_as_hard_link_and_restored_on_failure AssertionError: Lists differ: [79938893386083481] != [192810359046838217]
  test_unreadable_queue_file_is_set_aside_and_rebuilt（4 种坏文件）  json.decoder.JSONDecodeError / UnicodeDecodeError
  test_unreadable_history_file_is_set_aside_and_rebuilt             json.decoder.JSONDecodeError
  test_rebuild_continues_when_damaged_file_cannot_be_renamed        json.decoder.JSONDecodeError
  ```
  改前就绿的 3 条（日志在替换前列出目标、旧格式日志仍能恢复、读得出的未知版本不覆盖）用来防止改过头。
- 新测试里我自己写错的一处期望（落盘行顺序）已改为按标签比对状态；不是改旧测试迁就实现。

## 验证（含 Tk 的都经 `工作流任务/gui_hidden.py`）
- 定向 `run_selftests.py --serial -k ui_edges publication persistent_task_queue desktop_automation perf_batch perf_concurrent background_record fsync_budget`：198 条，仅 `test_ui_edges::BriefTintTests::test_the_users_own_words_show_up_on_the_display` 红。该用例单跑通过；随后单独整份 `-k ui_edges` 串行：本分支 115 条全过，**干净 master（e4b34961）同命令却红在这一条**。同一用例在同一代码上时红时绿，是存量的顺序／时序相关偶发红，与本轮无关，未处理。
- 此前另一次定向（`-k publication persistent_task_queue desktop_automation perf_batch perf_concurrent core asset_plan cancellation execution_deadline task_center state_transition runtime_projection background_record fsync_budget`）：279 条全过。
- `smoke_test.py --affected agent desktop_automation_service`：143 个测试文件 2151 条，红 2 个文件：`test_ui_edges` 同上；`test_agents_md::test_performance_history_is_declared_as_historical_only` 是 worktree 缺受忽略的 `维护记录/基准历史.json`，之后从主检出临时拷入重跑，已删除、未提交。
- 默认冒烟 `smoke_test.py`：通过 8 项，失败 0 项。
- `--architecture`：411 项中 1 项红：`test_skill_reference_injection`，worktree 未检出 skills 子模块（`screenplay-gate-engine.md` 在主检出存在），环境原因，与本轮无关。其余全过。
- 全量 `--all --safe` 本轮未手动运行；提交在 worktree 里做，提交后钩子是否补跑见合并轮。

## 未做
- 跨卷事务的原子性（既有问题）。
- R2179 合并轮提交后的后台全量：已完成，只有已知存量红 `test_desktop_compact_layout`（已由 R2181／R2183 修复合入），`test_soak_light` 通过。

## 提交
提交在分支 `codex/wip-R2192`，hash 见 git log；合入 master 由合并轮完成。
