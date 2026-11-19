# R3564 结果文件 — L1 任务书轮 I10：命名执行器与并发闸门
<!-- round-evidence: {"commit_base": "6c23fc3a", "credential_hits": 0, "evidence_sha256": "e0c4cc7337dda2a2", "exit": 0, "failed": 0, "passed": 27, "round": 3564, "tests": "run_selftests.py -k executors thread_boundary gate_selfaudit"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.3 结构治理轮（任务书明定：新增 1 个模块＋门禁）。新增 `infra/executors.py`（L1-H8）：`submit(pool, fn, *, cancel=None, label='', vendor=None)` 命名有界执行器（io/cpu/network/gpu 四池，`QUEUE_LIMIT=256`）＋按供应商桶并发闸门（`set_vendor_limit` 热调）；新增 `tests/test_executors.py`（13 条）与 `tests/architecture/test_thread_boundary.py`（I10-4 棘轮）；`_layers.py` 登记 L1 实体与 `('executors','app_logging')` 同层边。
2. **测试跑了吗、基线过了吗？** 跑了。任务书定向命令 `run_selftests.py -k executors thread_boundary gate_selfaudit` **27 条 0 红**；默认 `smoke_test.py` **9/9 绿**；`smoke_test.py --architecture` **554 条 1 红**——唯一红项 `test_site_packages_whitelist` 为跨分支环境污染（详见「环境问题」节），与本轮改动零因果；行覆盖基线重测 663 模块（executors 实测 87.9%），分支覆盖基线重测 95 模块／2813 决策点（executors 38 点 71.1%，下限登记 65.0）。
3. **欠账少了吗？** 结构性减少、数值未减：FL-08（L2/L3 直接建线程 12 文件 15 位点）自本轮起有 `test_thread_boundary` 棘轮门禁——按 I0 F11 实测登记基线、只减不增、坏样本自审，新增位点即红；实际迁移在 I11（前置本轮）。LR-07 实测维持 184（新模块零内置异常中文 raise）；覆盖率两份基线按真实重测刷新。

## 领号说明

- R3564 由本工作树（`devin-l1-enterprise`／`codex/l1-enterprise`）经 `维护记录/基准脚本/round_claim.py next` 领得；领号子进程输出有 GBK 解码告警（已知环境噪声），登记本身成功，`round-counter.json` 已核验 `last_claimed=3564`。

## I10-1　队列满抛 QuotaError，不静默丢弃 ✅

- `_Pool._queue = queue.Queue(maxsize=QUEUE_LIMIT=256)`；`submit` 走 `put_nowait`，`queue.Full` → `QuotaError('执行器队列已满（256）：<pool>')`（`code=E-QUOTA-EXCEEDED`，I6 已合入故直接用族异常）；池已关闭同样抛 `QuotaError`（RuntimeError 兼容，`concurrent.futures` 同款语义）。
- 测试：`test_full_queue_raises_quota_error`——`QUEUE_LIMIT` 打桩 4，gpu 池 1 worker＋4 槽后第 6 次提交即抛，断言 `code=='E-QUOTA-EXCEEDED'`；`test_submit_after_shutdown_rejected` 断言关闭后提交抛 `RuntimeError`。

## I10-2　取消语义 ✅

- `cancel` 接受 `threading.Event`、`CancelFlag` 或任意带 `is_set()`/`cancelled()` 的对象（`_cancelled` 探测式判定）；K12 `contract/ports.py` 合入前用普通可调用对象，按任务书 §2.4 登记为待切换项（I25 收口）。
- 出队时已取消 → `future.cancel()` 不执行；执行中任务由 `fn` 自读同一标记（测试断言任务体内 `flag.is_set()==True`）；`set_running_or_notify_cancel` 兼容 `future.cancel()` 外部取消。
- 测试：`test_cancelled_before_start_never_runs`（预取消任务 Future 置 cancelled、函数体零调用）、`test_running_task_reads_cancel_marker`（运行中任务读到标记且正常返回）。

## I10-3　限时关闭 ✅

- `shutdown(wait=SHUTDOWN_WAIT=5.0)`：置 `_closing` 拒新任务 → 排空队列中未开始项（逐个 `fut.cancel()`，异常走 `app_logging.swallowed`）→ worker 按 `_deadline` 退出 → `join(timeout=剩余)`；仍有存活 worker 记 `WARNING` 诊断（含池名与等待秒数），daemon 线程不阻塞进程退出。
- 测试：`test_shutdown_cancels_queued_tasks`（排队任务全 cancelled、耗时 <3s）、`test_shutdown_waits_for_running_up_to_limit`（运行中任务不被强杀、等待有界后 Future 未完成、释放后正常跑完）、`test_shutdown_logs_stragglers`（`assertLogs` 断言「关闭超时」诊断）。

## I10-4　test_thread_boundary 棘轮 ✅

- 检测口径与 I0 F11 一致：`threading.Thread(...)`、裸 `Thread(...)`、`ThreadPoolExecutor(...)`（含 `concurrent.futures` 属性形式）、`threading.Timer`、`class X(threading.Thread)` 基类写法，按「文件:计数」登记。
- `THREAD_SITE_BASELINE`＝I0 实测 12 文件 15 位点（domain 3＋orchestrator 9）；`test_thread_sites_within_baseline` 只减不增，`test_baseline_covers_current_modules` 要求登记值与实测逐文件相等（迁移后必须同步下调，防基线虚高）。
- 坏样本自审 2 条：`test_detector_catches_all_thread_forms`（四种写法＋Thread 子类共 5 处全计数）、`test_detector_ignores_executor_submit`（`executors.submit` 不误报）。
- 实测当前 12 文件计数与基线全等 → 棘轮就位；I11 每迁一批同步下调对应行。

## 并发闸门（任务书目标内的供应商桶能力）

- `_VendorGate` 用 `Condition` 而非 Semaphore：`set_vendor_limit` 可热调上限并 `notify_all` 唤醒重估；`limit<=0` 移除闸门不限。
- `submit(..., vendor='x')` 的任务在 worker 内先 `gate.acquire(cancel)` 占槽再执行，`finally` 释放；network 池 worker 数＝各供应商上限总和（下限 `_NETWORK_MIN_WORKERS=2`，只增不减）。
- 测试：`test_vendor_limit_caps_concurrency`（limit=1 时 4 任务峰值并发=1、`vendor_status` 归零）、`test_network_workers_scale_with_vendor_limits`（2+3 上限→worker≥4）、`test_set_vendor_limit_validates`（空名/非整数 `ConfigError`、0 移除闸门）。

## 存量缺陷修复与门禁补登（本轮实测发现）

- **内置异常中文 raise**：初版 `raise RuntimeError('执行器已关闭')` 触发 LR-07（实测 185>184）与 `test_infra_errors_boundary`（新模块未登记）；改 `QuotaError`（RuntimeError 兼容、准入拒绝语义一致）后两门禁复绿。
- **静默 except**：`shutdown` 排空循环 `except Exception: pass` 触发 silent-exception 棘轮；改 `app_logging.swallowed('executors.shutdown fut.cancel')`，并登记 `SAME_LAYER_EDGES ('executors','app_logging')`。
- **架构门禁清单**：`architecture.md`「当前架构门禁清单」补 `test_thread_boundary.py`；§3 L1 模块表补 `executors` 并加 R3564 轮注；`PROJECT_MAP.md` 成本与运行保障行登记。
- **规则守卫对照**：`规则守卫基线.json` LR-08 守卫清单补 `test_thread_boundary.py`，`scripts/rule_guard_map.py --write` 重生成对照.md。
- **覆盖率两基线**：`coverage_report.py`（11 目标）重测 → `覆盖率基线.json` 663 模块／83 覆盖（executors 87.9%）；`branch_coverage_report.py`（93 目标）重测 → `分支覆盖率基线.json` 95 模块／2813 点／1574 覆盖（executors 38 点 71.1%），`分支覆盖率下限.json` 登记 `executors.py: 65.0`；`runbook.md` §11 口径数字同步（662→663、80→83、10→11、582→580；94→95）。两次重测既有模块百分比零回退（行覆盖 `agent/core.py` 43.3→41.8 为 I9 代码变更后的真实值，无下限约束）。

## 环境问题（如实记录，非本轮回归）

- `test_dependency_whitelist.test_site_packages_whitelist` 红：随附解释器 purelib 多出 `annotated-types/pydantic/pydantic-core/typing-extensions/typing-inspection` 五包。本工作树 `requirements.txt`（＝master 口径六包）不含它们；溯源：`codex/foundation-resume` 工作树（`.agents/worktrees/dsh-21046c9e-e504`）R3540 `b9cf8e36`「C4正式准入Pydantic生产依赖」已在**该分支** requirements.txt 锁定同五包并于 2026-11-19 02:17–03:06 安装进共享 `运行环境`（非本任务会话操作）。卸载会破坏该分支在途验证、加进本分支 requirements 属范围外吸收未合入依赖，故保持现场如实上报；待 foundation-resume 合入 master 后两分支 requirements 对齐即自然转绿。
- 该红项与本轮 diff 零因果：本轮未新增/改动任何第三方依赖，测试只读枚举 purelib。

## 验证汇总

| 命令 | 结果 |
| --- | --- |
| `run_selftests.py -k executors thread_boundary gate_selfaudit` | 27 条 0 红（3 文件：test_executors 13、test_thread_boundary 4、test_gate_selfaudit 10） |
| `run_selftests.py -k executors thread_boundary infra_errors_boundary silent_exception layer_relations`（修复后复验） | 29 条 0 红 |
| `run_selftests.py -k test_coverage_baseline test_branch_coverage_floor test_agents_md test_rule_guard_map` | 32 条 0 红 |
| `smoke_test.py` | 9/9 绿 |
| `smoke_test.py --architecture`（首轮） | 554 条 11 红：门禁清单、守卫对照、覆盖率基线×4、LR-07×3、静默异常、依赖白名单——前 10 项已全部修复 |
| `smoke_test.py --architecture`（复跑） | 554 条 1 红：仅 `test_site_packages_whitelist`（环境污染，见上节） |
| `scripts/coverage_report.py <11 targets>` | 完成：663 模块／83 覆盖／目标用例全通过 |
| `scripts/branch_coverage_report.py <93 targets>` | 完成：95 模块／2813 决策点／1574 覆盖／目标用例全通过 |

## 分支覆盖率基线重测说明

- 口径不变（决策点双结果覆盖，`sys.settrace` 零依赖）；targets 92→93（+`tests.test_executors`），modules 94→95（+`executors.py`，38 点 27 覆盖 71.1%）。既有 94 模块百分比逐一比对零变化；`points_total` 2775→2813、`points_covered` 1547→1574。
- 下限表新增 `executors.py: 65.0`（实测 71.1% 向下取档，与 file_cache/http_client 等既有下限同法）；既有 94 条下限未动。
