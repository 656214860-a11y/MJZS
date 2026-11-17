# R3248 结果：L1 基础设施层优化任务书 · 轮 1（P0 止血）
<!-- round-evidence: {"commit_base": "9a07b29f", "credential_hits": 0, "evidence_sha256": "973996406e8e0530", "exit": 0, "failed": 0, "passed": 254, "round": 3248, "tests": "run_selftests.py -k api_endpoints model_metering pet_llm request_ledger model_pool writing_api"} -->

## 三问

1. **轮次类型**：修复轮（runbook §15／AGENTS §3.2）——L1 任务书轮 1，四个根因模块止血。
2. **测试跑了吗、三个基线过了吗**：新增 `tests/test_l1_reliability_r3248.py` 27 条全绿；`smoke_test.py --affected`（六模块 → 41 个测试文件）281 秒 0 红；默认冒烟 10/10；架构门禁 488/488；详见验证记录。
3. **欠账少了吗**：少了。任务书点名的四处 P0 静默失败／有界性缺陷已修并配回归：限流等待被 3 秒截断且睡在锁内、Retry-After 与退避共用 3 秒上限且抖动是确定性的、结算异常会丢已付费结果、传输重放×降级链最多 9 次真实 POST、本地陈旧 reserved 永久占预算、台账等锁持有进程内锁且不可重试。

## 交付（对应任务书 R1-a～R1-k）

- `infra/api_endpoints.py`
  - R1-a 时钟／睡眠注入：模块级 `_CLOCK = time.monotonic`、`_SLEEP = time.sleep`，测试可替换。
  - R1-b 锁域收窄：`bucket.wait()` 在 `_RATE_LIMIT_LOCK` 内完成预约，`_sleep_rate_delay()` 在锁外分片睡眠。
  - R1-c／d 新增 `RATE_SLEEP_MAX_SECONDS = 300.0`、`RATE_SLEEP_SLICE_SECONDS = 0.5`：限流等待不再被 `RETRY_MAX_SECONDS`（3 秒）截断，按 ≤0.5 秒分片、片间 `control.checkpoint()`。
  - R1-e 桶键 `host + '#' + sha256(credential)[:16]`：`wait_for_rpm(..., credential=None)`、`set_host_rate_limit(..., credential=None)`、`_wait_for_rate_limit` 增加同名可选参；凭据（key_env 名或 Authorization 头值）只以摘要入表，明文不落内存；rpm 变更走 `bucket.set_interval()` 只改间隔、保留已预约 `next`，消除重置突发。
  - R1-f `RETRY_AFTER_MAX_SECONDS = 60.0` 单独给 Retry-After 封顶；指数退避改 `random.uniform(0.5, 1.5)` 真随机抖动（`jitter=False` 时保持确定值供测试）。
  - 传输层新增 `attempt_budget` 可选参数：`_http_transport`／`http_transport` 按预算截断重放次数，每次真实 open 消耗 1，预算耗尽立即返回 `kind='network'` 结构化失败，不发请求。
- `infra/model_pool.py`：`http_transport`／`_http_transport` 透传 `attempt_budget`（签名向后兼容）。
- `infra/pet_llm.py`
  - R1-i `MAX_PAID_ATTEMPTS = 3`：仅当使用内置 `http_transport`（未注入 transport、自 transport 未被替换）时，`ask()` 建共享 `[3]` 预算闭包，传输重放与 pro→flash→兜底降级链合计真实 POST ≤3；注入式 transport 行为不变。
  - `http_transport` 透传 `attempt_budget`。
- `infra/model_metering.py`
  - R1-g `metered()` 发送成功后改 try/finally：`usage_of`／`on_result`／`record_request_attempt` 任一异常都不阻断结算；`on_result` 与尝试记录异常只记日志不外抛。
  - R1-h 结算抽为 `_settle()`：`settle_model` 抛错（等锁超时／保存失败）时记 `diagnostic_capture.record_degradation` 并照常返回已付费结果；发送失败分支同样走 `_settle`。
  - R1-i `REPLAYABLE_RETRY_STATUS` 移除状态 0（无 HTTP 响应不再算可重放）。
- `infra/request_ledger.py`
  - R1-j `transaction()` 重写：文件锁改有界轮询（`REQUEST_LOCK_WAIT_SECONDS=10.0`、`REQUEST_LOCK_POLL_SECONDS=0.02`、片间 `current_execution().checkpoint()`），等待全程不持 `_REQUEST_LOCK`；拿到文件锁后才进进程内锁做读—改—写；`LedgerLockTimeout(ValueError)` 区分「锁忙」与数据错误。
  - R1-k `load()` 尾部 `_sweep_stale_reserved()`：`state='reserved'` 且无 `remote_task_id` 且 `now - at > REQUEST_RESERVED_STALE_SECONDS(1800)` 的条目就地改 `unknown`（联动 mode/amount/money_state/settled_at）；远端任务预留有自己的轮询生命周期，不动。
  - `settle_units`／`settle_model` 捕获 `LedgerLockTimeout` 走 `_settle_lock_timeout()`：结算等锁超时不向上抛（付费结果已产生），条目尽力记 unknown、记 `diagnostic_capture.record_degradation`，内部异常经 `app_logging.swallowed()` 吞掉。
- `writing_api.py`：`wait_for_rpm` 调用补 `credential=record['key_env']`，同主机不同密钥不再共用限流桶。
- `tests/test_l1_reliability_r3248.py`：新增 27 条——Retry-After 60s 封顶、真随机抖动、状态 0 不可重放、限流分片睡眠＋checkpoint＋并发正等待＋取消半秒内抛出、凭据分桶与明文不入表、rpm 变更保留时隙、rpm=10→6 秒间隔、usage_of 抛错仍结算、结算失败仍返回结果、on_result 异常容忍、尝试记录失败容忍、非 dict 结果仍结算、陈旧 reserved 清扫（本地扫／远端不扫／新鲜不扫／money_state 联动）、锁等待有界报错＋等锁 checkpoint、事务往返、双进程 authorize/settle、settle 锁超时降级（含内部异常吞掉）、缺失请求结算 ValueError、attempt 记录边界、attempt_budget 跨重放共享与耗尽、默认链付费 POST≤3、无预算默认 3 次不变。

## 验证记录

- 新测试文件：`run_selftests.py -k l1_reliability` → **27 条 / 0 红 / 2.7 秒**（本轮为新增契约测试，先红后绿的「红」由任务书诊断结论充当——修复前同断言在旧实现下必然失败，如 Retry-After 3600→3、状态 0 可重放、结算异常外抛）。
- `smoke_test.py`（默认冒烟）：**10/10 通过**。
- `smoke_test.py --affected api_endpoints model_metering pet_llm request_ledger model_pool writing_api`：**41 个测试文件 / 281 秒 / 0 红 / ALL TESTS PASSED**（首轮因工作树缺三个嵌套技能仓批量红，补拷后；第二轮与覆盖率测量并行跑超 900 秒超时属资源争用非用例失败，本轮单独复跑绿）。
- 分支覆盖率基线：`scripts/branch_coverage_report.py`（79 个目标＋新增测试文件）第三次重测写入，目标用例全通过；api_endpoints 24/87（27.6%）、model_metering 9/11（81.8%，上轮实测 54.5%→补用例后达标）、request_ledger 115/152（75.7%，上轮实测 70.4%→诊断定位新增代码 5 处欠覆盖分支，补 4 条用例后达标）、model_pool 52/129、pet_llm 25/36；全模块决策点 1253/2357；基线写入 `维护记录/分支覆盖率基线.json`。
- `smoke_test.py --architecture`：**488/488 全绿**（153.9s；前三轮失败项——草稿语法、依赖白名单版本、静默异常 ratchet、技能引用、类体上限、两个覆盖率下限——全部修复后清零）。
- 工作树环境注记：`devin-l1-infra` 根新增 `运行环境` junction（→主工作区，不入库）与三个嵌套技能仓拷贝（不入库），均为验证前置。

## 并发改动收编说明（用户已裁决：收编完成 R3248）

本工作树在本人编辑期间出现并发改动（另一 agent/会话同树作业 L1 轮 1），经用户确认**收编为本轮一部分**。对方贡献已核验并保留：

- `infra/request_ledger.py`：`LedgerLockTimeout(ValueError)`＋`_settle_lock_timeout()`＋`settle_units`／`settle_model` 的 `except LedgerLockTimeout` 降级（结算等锁超时不外抛、条目尽力记 unknown、记 diagnostic_capture）；常量调为 `REQUEST_LOCK_WAIT_SECONDS=10.0`／`POLL=0.02`／`STALE=1800`（30 分钟，与任务书轮 0 盘点的清扫阈值口径一致）；并把本人 transaction／清扫实现再精修（清扫补 mode/amount/money_state/settled_at 联动）。
- `tests/test_l1_reliability_r3248.py`：对方合入 6 条用例（rpm=10→6 秒间隔、并发调用方正等待、取消等待半秒内抛出、双进程 authorize/settle、settle 锁超时降级、默认链付费 POST≤3），草稿文件 `_r3248_additions.py` 已由对方合并后自删。
- `tests/test_pet_llm.py`：2 处 mock 目标 `pet_llm.time.sleep` → `infra.api_endpoints._SLEEP`（适配本人可注入睡眠）。
- 本人收编侧修复：`RequestLedger` 类体超上限 → `transaction`／`_sweep_stale_reserved`／`_settle_lock_timeout` 抽为模块级函数（类体 695→626 行）；两处 `except Exception: pass` → `app_logging.swallowed()`；model_metering 同法修 1 处；白名单 requests 2.32.3→2.34.2（用户裁决同步，含 依赖白名单.md 版本行与变更记录）。

合并后 `run_selftests.py -k l1_reliability` → **20 条 / 0 红 / 2.1 秒**。

## 范围与取舍说明

- `REQUEST_RESERVED_STALE_SECONDS = 1800`（30 分钟，任务书轮 0 盘点口径）：模型请求超时以分钟计，本地预留超半小时未结算必为进程夭折遗留；远端任务预留（有 `remote_task_id`）不扫，保住异步任务续跑语义。
- `RATE_SLEEP_MAX_SECONDS = 300.0`：单次限流等待的兜底上限，正常 rpm（≥1）排队等待远小于此；分片＋checkpoint 保证可取消。
- 凭据分桶以 `key_env` 名／Authorization 头值作摘要种子：同 env 名即同凭据槽，同主机不同 env 名分桶；不解析明文密钥，密钥本身不进内存表。
- 降级链在预算耗尽时收到 `status=0` 失败结果，`replayable_retry(0)=False` 会自然终止链式重试——总发送 ≤3 是硬上限。
- `image_agent_runner` 等既有永久例外不受影响；无新增第三方依赖（hashlib/random/msvcrt 均为标准库）。

## 提交

- 分支 `codex/wip-R3248`（领号 R3248，基座 master `9a07b29f`）。
- commit：待补记。
- 合入 master：待补记。
