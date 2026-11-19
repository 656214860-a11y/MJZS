# R3543 — A10 第一批拆除请求台账到启动诊断的依赖
<!-- round-evidence: {"commit_base": "eda8d829", "credential_hits": 0, "evidence_sha256": "82de437f376e93d0", "exit": 1, "failed": 1, "passed": 74, "round": 3543, "tests": "run_selftests.py -k test_no_circular_import test_layers test_dynamic_import_registry test_rule_guard_map"} -->

## 三问

1. 类型为 §3.3 结构治理轮，基线 `eda8d829`，工作树 377e，分支 `codex/architecture-a10-ledger-diagnostic`。生产改动 3 模块。
2. 冒烟 8/8，隐藏桌面探针通过。故障定向、适用回归及完整架构前后对照见下。
3. 五模块环收缩为四模块。安全全量绿凭据停在 R3293，之后主干有 23 个源码轮次（门禁线 8）。本分支未跑安全全量，最近自动全量为 `f6138e7`，退出 1，红文件为 `test_selftests_gui_token` 与 `test_perf_baseline`。

## 前提和范围

- 核对任务书 A10、A3/R3409、A6/R3415 和 A9-9/R3541（含机器凭据）。A3 的诊断消费链和 A6 的失败注入方法适用，二者未宣称已覆盖这条台账降级边。R3541 指认的函数内导入实存于原树 `infra/request_ledger.py:146`。
- 现有契约有两种失败。锁超时走原 `LedgerLockTimeout` 分支，额度与模型结算都尽力在内存标记 `unknown` 及 `unknown_via=settle-lock-timeout`，日志继续记录码表中的 `E-IO-WRITE`。拿不到锁时磁盘保留 `reserved`，后续由持锁重试或陈旧预留清扫处理。拿到锁后的台账普通落盘失败则原样传播 I/O 异常，磁盘仍保留上次内容。两条路径的语义分别验证。
- 领号 R3543，无匹配队列项。领号返回成功，旧子进程报告 GBK 解码告警，后续设置 `PYTHONUTF8=1`。本树借用主树已有随附解释器，主树产品文件未改。scope 新增文件无重叠。全差异扫描在 `request_ledger.py` 与 L1/L2 等活跃车道有文件级重叠，架构登记与说明也有共享编辑。限定于当前基线的导入和记录调用，未接入任何在途分支。继承的状态页当前轮次为 3409，按仓规由主干合入轮处理连续性门禁。

## 最小断边

- `infra/diagnostic_state.py` 承接已有状态读写与降级记录，继续使用 `agent.core` 原子写和 `app_logging.redact`，复用其日志目录。沿用 `latest.json`、单一进程内锁、最近 50 条、诊断隔离环境变量和产物版本计数。
- `infra/request_ledger.py` 直接使用该 L1 记录入口。保留原有 `app_logging.swallowed()` 异常留痕、未知标记及结算策略。
- `infra/diagnostic_capture.py` 将同一份状态、写锁及降级实现委托给共享模块，保留旧入口、启动探针和导出。仅改 `app_logging` 文本日志会遗漏任务中心和诊断包读取的结构化记录。依赖装配回调会要求所有独立调用方先注册。此批移动现有持久化实现即可保留这两类消费者，无需新契约或装配模块。

## 验证

- 覆盖率元数据随实测刷新。初跑首帧测量发现专用树无 FFmpeg，复测从现有随附工具只读取可执行文件。分支测量初跑中止以将 Tk 用例移入隐藏桌面，随后补齐三个已登记的固定技能包，逐一校验提交及内容树，检出留在专用工作树。行覆盖率原有 115 条通过，662 个生产模块中 83 个有行覆盖。原有分支覆盖率目标执行 1746 条、2 条跳过，通过后发现发布事务实测 58.1% 低于既有 61.0% 下限。本轮将已有发布提交后清理测试加入测量目标。补测后发布事务为 61.3%，94 个计量模块均达到原下限。91 组共运行 1747 条，1745 条通过、2 条跳过。

- 红测执行 3 个故障测试中，单个测试的两个子场景均失败，关键行 `AssertionError: Expected 'record_degradation' to not have been called. Called 1 times.`，额度与模型结算均命中旧依赖。另 2 个故障用例通过。
- 绿测 3/3 通过，含 2 种结算的 `unknown`、`E-IO-WRITE`、持锁重试和单条结算。另验证诊断写入 ENOSPC 不覆盖原业务异常，台账 ENOSPC 原样传播且磁盘内容保持、重试仅结算一次。诊断状态同时保留旧启动记录。实际跨进程锁覆盖在本轮台账模块回归中运行。
- 受影响回归中，`smoke_test.py --affected …` 在隐藏桌面运行 26 个文件、512 条用例，0 跳过，初跑 511 条通过。唯一红项为旧替身仍挂在启动诊断入口的实锁测试（`0 != 2`）。迁移该测试及同模块的故障注入替身后，`tests.test_l1_reliability_r3248` 27/27 通过，其余模块结果沿用初跑。
- 静态和动态门禁专项执行 74 条，其中 73 条通过、1 条失败（1 个红文件），退出 1。生产静态环用例仍报告四模块环。包导入正反例、动态环、分层与动态入口守卫通过。零凭据命中，见 [R3543.json](evidence/R3543.json)。
- 用生产门禁相同解析器与 Tarjan 算法比较前后图。目标边消失，原 SCC 从 5 模块、8 条内部边降至 4 模块、5 条内部边。`diagnostic_capture → request_ledger` 和 `model_metering → request_ledger` 仍在图中，已成为分量外出边。其余已知 SCC `agent.core / agent.publication / infra.file_cache` 仍为 3 模块、5 条内部边。无新增环。
- 完整架构实测为改前 597/602（453.080 秒），中间态 594/602（371.445 秒），最终 598/602（400.122 秒），三次均退出 1。中间态新增的 3 条覆盖率口径失败已全部转绿。最终新增红项 0。固定技能包检出后，原 `test_script_stages_name_only_their_approved_00_references` 转绿。

| 终态红项 | 最终现场 |
| --- | --- |
| `test_performance_history_is_declared_as_historical_only` | 缺少本地的 `维护记录/基准历史.json` |
| `test_site_packages_whitelist` | 共用 Python 环境有 5 个未登记包 |
| `test_static_import_cycles_are_a_nonincreasing_baseline` | 仍可复现 A10 剩余四模块环 |
| `test_round_number_continuous` | 分支状态页轮号与最新结果不同步 |

## 剩余 A10 交接

下一批单独拆 `diagnostic_capture → model_pool`，把模型池空检查依赖接到既有启动组装点，保留旧诊断入口。覆盖有模型、空模型、读取异常三种结果，以及对应启动降级语义。仅模拟删该边时只剩已登记的三模块存量环，生产实现和验证留给该批。合入时须和 L1/L2 车道核对台账重叠位置。本轮不修改其他所有者的契约或消费者。

本轮以标准 `dev.py commit` 保存 FAIL 检查点，提交哈希以 `git log -1 --format=%H -- 程序/tasks_round/tasks_round_3543_result.md` 定位。
