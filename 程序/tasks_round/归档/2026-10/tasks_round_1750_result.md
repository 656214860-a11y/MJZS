# R1750：可靠性轮——跨树令牌识别 PID 复用（TOKFIX）

**本轮属于 §3 哪种类型？** 可靠性轮（§3.8，可靠性／数据迁移类），按要求先红后绿。

**测试跑了吗、三个基线过了吗？** 新测试改前 2 红＋2 错 → 改后 5/5 绿；默认冒烟 8/8 绿。窄关键词 `run_selftests.py -k pid_reuse_tokens gui_token selftest_lock` 输出 18 条用例、0 红，但进程在报告后**未退出，600 秒上限到点被结束**，按任务书口径**不算通过**（见“实际命令计数”）。架构门禁与全量按任务书指定由调度方执行，本轮未运行。

**`project_status.md` 的欠账少了吗？** 未改 `project_status.md`（任务书禁止），本轮不领号、不提交，欠账清点留给提交方。

## 根因

- Windows 上 `_pid_is_alive` 只判断进程句柄能否打开，不核对进程创建时间；PID 被系统复用给无关进程后，死票据／死锁一直被当作活跃持有者。
- 队列层面还有第二处误判：`_drop_dead_gui_tickets` 原先对 `pid == os.getpid()` 的票据无条件跳过；`acquire_pid_lock(reentrant=True)` 也对同 PID 先返回“重入”。仅比较 PID 时，这两条会让“本进程同号的历史票据”永久留在队首。
- 真实票据与锁都已写 `started_at`，没有写文件格式的改动。

## 改动清单

| 位置 | 改动 |
| --- | --- |
| `run_selftests.py:69` | 新增 `PID_REUSE_TOLERANCE_SECONDS = 120`（不改 `GUI_WAIT_SECONDS` 等常量） |
| `run_selftests.py:213` | `_process_created_at(pid)`：Windows `ctypes` 调 `OpenProcess`＋`GetProcessTimes`，FILETIME 换算 epoch；非 Windows、句柄失败、调用失败、异常一律返回 `None` |
| `run_selftests.py:256` | `_record_is_reused(pid, started_at)`：`started_at < 创建时间 - 容差` 判复用；缺少或非法 `started_at`、创建时间取不到、`started_at` 晚于“当前时间＋容差”均判“不复用”（宁可漏清，不可误清） |
| `run_selftests.py:271` | `_pid_is_alive(pid, started_at=None)`：首先判复用；否则保持原探活；旧单参调用兼容 |
| `run_selftests.py:303` | `acquire_pid_lock`：普通持有者判断传 `started_at`；重入仅在同 PID **且未被判复用**时生效 |
| `run_selftests.py:377` | `_drop_dead_gui_tickets`：`None`／本 PID 票据仅在“未被判复用”时保留原跳过语义；判复用则按探活结果清理 |
| `run_selftests.py:503` | `other_gui_holder`：传锁的 `started_at`，避免并发告警把复用 PID 误报为其他持有者 |
| `tests/test_pid_reuse_tokens.py` | 新增 5 条测试，全部用 `tempfile` 临时目录，不接触真实 common-dir |

**容差取值理由（120 秒）**：票据的 `started_at` 在父进程排队时写入，实际执行在子进程；`run_selftests._popen_unit` 在任务书点名的 `_pid_is_alive` 之前还有模块导入，`smoke_test.py --affected` 的父进程还会先跑全部测试。正常记录只会**晚于**进程创建时间，所以容差只可能让真正的复用晚一点被识别；120 秒覆盖检测自身漂移，同时把“伪造或时钟异常的未来时间”挡在误清之外。代价：进程创建后不到 120 秒内复用同号（极小窗口）可能漏清一次。

## 五个调用点的处理

| 原行号 | 调用点 | 处理与原因 |
| --- | --- | --- |
| :264 | `acquire_pid_lock` 判持有者 | 传 `holder['started_at']`；锁由本函数写入，字段可用 |
| :320 | `_drop_dead_gui_tickets` 清死票 | 传 `holder['started_at']`；票据由 `_join_gui_queue` 写入，字段可用；同 PID 跳过改为仅在未判复用时生效 |
| :442 | `other_gui_holder` | 传锁的 `started_at`；同锁文件，字段可用，防止告警误判 |
| :657 | `auto_full_running` | **保持原样（只传 PID）**。`scripts/auto_full_safe.py` 把 `auto-full-safe.lock` 写成纯 PID 文本，没有 `started_at`；凭空加字段会超出“只改 `run_selftests.py` 与新增测试”的范围。该锁另有 `AUTO_FULL_STALE_SECONDS` 时限作为后备 |
| :710 | `participating_full_safe_run` | **保持原样（只传 PID）**。这里的 `pid` 已先限定为本进程或父进程，不会出现“PID 被无关进程复用而放行”的情形；父进程才是锁的 `started_at` 所有者，而子进程当前 PID 的创建时间晚于父进程发出的票据，此时传入会引入误清风险 |

## 先红输出（改前）

命令：`python.exe -B -m unittest tests.test_pid_reuse_tokens` → `FAILED (failures=2, errors=2)`，共 5 条，改前基线为 1 条本来就该绿的“正常票据不被误清”。

```
ERROR test_current_pid_with_old_record_is_dead_but_recent_record_is_alive
  TypeError: _pid_is_alive() takes 1 positional argument but 2 were given
ERROR test_creation_time_failure_falls_back_to_pid_check
  AttributeError: <module 'run_selftests'> does not have the attribute '_process_created_at'
FAIL test_dead_gui_ticket_is_dropped_and_new_ticket_becomes_first
  AssertionError: True is not false        (死票据未被清掉)
FAIL test_gui_lock_old_record_is_reclaimed_but_live_record_rejects
  AssertionError: 1792369816.435783 == 1792369816.435783   (旧锁被当作重入，未被回收)
Ran 5 tests; FAILED (failures=2, errors=2)
```

## 实际命令与计数

| 命令 | 结果 |
| --- | --- |
| `python -B -m unittest tests.test_pid_reuse_tokens`（改前） | 2 红＋2 错＋1 绿／5 |
| `python -B -m unittest tests.test_pid_reuse_tokens`（改后） | `Ran 5 tests ... OK`，0 红 |
| `python -B smoke_test.py` | 通过 8 项，失败 0 项 |
| `python -B run_selftests.py -k pid_reuse_tokens gui_token selftest_lock` | 输出 `共 18 条用例，2.7 秒；0 个文件有红`，随后进程 600 秒未退出、被结束。**未计为通过** |
| import 清单查询 | `Grep` 返回“未找到”且无命中（只读查询本身未成功）；改用 `Select-String` 得到 1 个命中：`tests/test_selftests_gui_token.py`，该文件在上面的 18 条中并已 0 红 |

**进程未退出的观察**：报告完成后进程只剩 1 个线程、无窗口句柄、CPU 仍在增长，判断问题发生在用例结束后的解释器退出／临时目录清理阶段，而不是测试仍在运行。收尾复查时曾瞬时见到 1 个 `python.exe`，随后连续两次清单为 0；无法排除那是一次性的清理进程。未做代码级确认，也不排除令牌或其它收尾等待。建议调度方单独重跑并观察，再决定归属。

## 断言未动声明

`tests/` 既有测试文件一字未改；本轮新增测试文件中的断言均为本次新增，没有删除、弱化、跳过任何既有断言，也没有新增 skip。

## 需裁决事项

1. **窄关键词运行未退出**：18 条 0 红但 600 秒超时，不属于完成。需要调度方复跑判定是环境／退出清理问题，还是令牌缺陷。本轮仅解决“PID 复用”这一死票根因。
2. **`auto_full_running` 仍只看 PID**：`scripts/auto_full_safe.py` 的锁是纯 PID 文本，本任务范围不能改；如需覆盖此路径，需另派任务让脚本写入 `started_at`，`run_selftests.py` 只改读取端。
3. **真实死票仍留在标准 common-dir**：按任务书未触碰 `D:\repo-meta\漫剧制作助手.git\`；修复生效后，下一次按原有逻辑运行的清理会回收它，调度方核对前不要手工删除。
4. **`started_at` 缺失或未来时间选择“宁可漏清”**：若认为缺失字段在旧票据上应视为可疑，需要另行拍板，本轮不扩大语义。

## 轮次与提交

未领号、未执行 git 写命令、未提交（执行方职责，§2.6／§4.2）。改动仅限 `run_selftests.py`、`tests/test_pid_reuse_tokens.py` 与本结果文件。

## 独立验收（Claude，主工作区）

- 执行链：Codex group/group-4 一次完成（约 15 分钟）。改动仅 run_selftests.py（+72/-5）与新增 tests/test_pid_reuse_tokens.py，车道与主工作区逐字节一致。
- 先红：执行方改前 `unittest tests.test_pid_reuse_tokens` 2 红 2 错 1 绿；改后 5/5 绿（主工作区复跑 0.029 秒）。
- **真实死票探针（只读，未删除任何票据）**：对 `D:/repo-meta/漫剧制作助手.git/gui-selftest.queue` 里那张 03:47 的票（pid 12912，started_at 1792439227.93）：旧接口 `_pid_is_alive(12912)` 返回 True（误判活着）；新接口 `_pid_is_alive(12912, started_at)` 返回 False；当前活进程用 `started_at=now` 仍返回 True。PID 12912 现为 SearchHost.exe，创建于 05:09:39，晚于票据 1 小时 22 分。
- 复跑：`run_selftests -k pid_reuse_tokens gui_token selftest_lock` 18 条 0 红，**5 秒正常退出，退出码 0**——执行方报告的「报告后进程不退出、600 秒被杀」在主工作区未复现，判断为其沙箱现象（沙箱写不了 D:/repo-meta，与此前已知的台账写入挂起一致）。消费方 `-k test_selftests` 65 条 0 红；import 清单：scripts/auto_full_safe.py、tests/architecture/test_round_baselines.py、tests/test_selftests.py、tests/test_selftests_gui_token.py。`smoke_test` 通过；`smoke_test --architecture` 375 条仅 1 条红，即已知的「欠一次完整安全全量」后台补跑项。
- 逻辑审查：`_drop_dead_gui_tickets` 对本进程旧票现在按复用判断清理，别人的死票照旧；创建时间取不到、缺 started_at、未来时间都退回只看 PID。`auto_full_running` 与 `participating_full_safe_run` 两处按执行方说明保持只看 PID（锁是纯 PID 文本 / 已限定本进程或父进程），记为后续项。
- 需用户知悉：本提交不动 D:/repo-meta；那张真实死票会在下次有人排队 GUI 令牌时由新逻辑自动回收，提交后将核对。
- 断言未动；未新增 skip。
