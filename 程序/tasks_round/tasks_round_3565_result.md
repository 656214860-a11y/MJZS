# R3565 — A10 第二批拆除启动诊断到模型池的生产依赖
<!-- round-evidence: {"commit_base": "b8725bac", "credential_hits": 0, "evidence_sha256": "f9970ea819b0a1a0", "exit": 0, "failed": 0, "passed": 189, "round": 3565, "tests": "run_selftests.py -k test_startup_selfcheck test_request_ledger test_l1_reliability_r3248 test_no_circular_import test_layers test_dynamic_import_registry test_rule_guard_map"} -->

1. 类型为 §3.3 结构治理轮，生产变更 3 个模块。
2. 默认冒烟业务检查 8/8，隐藏桌面探针通过。专项 189/189，通过受影响回归。完整架构 599/602，新增红项 0。
3. 四模块 SCC 已拆除。安全全量未触发，绿凭据仍为 R3293，之后主干累计 23 个源码轮次，门禁线 8。最近自动安全全量为 `ec62feb`，退出 1，红文件为架构依赖白名单和文件面板阶段测试。

## 基线与范围

- 原分支 `codex/architecture-a10-diagnostic-pool` 保留在 `6d091932`。领号工具实测报告相对 master 有 11 个独有源码提交，超过上限 10。master 在分叉后另有 74 个原链未修改的路径变化。授权后从共同基点 `0e3fc76355eaa63cecb2d8220ea2f7fdb0842787` 构造新分支 `codex/architecture-a10-compact` 的机械整合检查点 `ecb5912f8f83699e927cba0796ba57a26ed92b47`。直接复用旧提交的 tree 对象，避免带入 master 后续文件变化。两者 tree 均为 `22cde559641023df491d2f3a147310461da7ae56`，逐文件差异为空。检查点相对 master 的独有源码提交数为 1，按仓库凭据规则扫描新增行命中 0。检查点用 Git tree 对象构造，R3565 正式轮另走 dev.py。
- 原链中的 R3541 对应 `eda8d829`，R3543 对应 `6d091932`。行级证据留在原分支，机器凭据保留在两棵相同的基线文件树中，见 [R3541.json](evidence/R3541.json)、[R3543.json](evidence/R3543.json)。
- 复核 A3/R3409 的启动诊断消费链、A6/R3415 的故障与启动约束。领号 R3565，队列无匹配条目。本批集中于 `infra/config_snapshot.py`、`infra/diagnostic_capture.py`、`infra/model_pool.py`。scope 扫描提示诊断与存储模块在若干活跃分支有文件重叠，当前改动限定为读探针和配置路径。其他车道未合入。解释器及 FFmpeg 从现有随附运行环境调用。
- `config_snapshot` 用同一个程序级模型配置路径提供只读非空探针。旧 `model_pool.config_file()`、`raw()`、启动自检及诊断导出入口继续可用。配置缺失按空池，解析或读取异常交给 `contract.selfcheck.run()`，产出 `DEGRADED/check-error` 并继续启动。读取仍经现有 `agent.core.read`，无新配置缓存和诊断状态写入入口。

## 验证

- 红测 4 项，3 通过、1 失败。损坏配置被误判，关键断言为 `'model-pool-empty' unexpectedly found`。有模型、模型表为空或缺失、配置文件缺失的既有行为已固定。绿测作为启动专项执行，损坏配置产生降级诊断并写入现有自检状态，启动结果无 FATAL。
- 启动自检、请求台账、L1 可靠性、静态与动态环、分层、动态入口和规则映射定向 189/189。台账覆盖锁超时 `unknown`、`E-IO-WRITE`、原始 I/O 错误、持锁重试和单次结算，以及共享诊断写入失败时原业务路径的行为。受影响回归覆盖 11 个测试文件且无红。
- 生产 AST 解析与 Tarjan 同口径扫描 663 个文件。原分量 `api_endpoints / diagnostic_capture / model_metering / model_pool` 消失，目标边已移除，无新增环。存量 `agent.core / agent.publication / infra.file_cache` 原样保留。冷进程导入和空池探针无 Tk、模型池模块加载或 socket 连接和 DNS 查询。
- 原行覆盖目标 115/115，实测 83/662 模块有行覆盖。分支覆盖初跑因三个固定技能包未检出而红；已从前轮工作树在本树检出仓库锁定的提交，并逐一核对 tree hash。原 91 组目标复测共 1750 条，1748 通过、2 跳过。94 个计量模块达到原下限，1529/2735 个决策点达到双结果覆盖。覆盖率快照由实测生成，下限文件保持原值。

## 完整架构

改前 597/602（391.266 秒），改后 599/602（366.762 秒），两次退出均为 1。生产静态环门禁转绿，锁定技能包检出后编剧参考门禁也转绿。没有新增红项，剩余集合如下。

| 终态红项 | 实测原因 |
| --- | --- |
| `test_performance_history_is_declared_as_historical_only` | 本地缺少 `维护记录/基准历史.json` |
| `test_site_packages_whitelist` | 随附 Python 共享环境多出 `annotated-types`、`pydantic`、`pydantic-core`、`typing-extensions`、`typing-inspection` |
| `test_round_number_continuous` | 分支继承值 3409，按本轮结果应为 3566；状态页由主干合入轮同步 |

## A10 交接

两批指定拆环边均已消失。合入时应基于原逐轮链的等价源码核对本轮差异及活跃车道重叠，再同步主干状态和评估 A11 前置条件。按标准 `dev.py commit` 保存 FAIL 检查点，机器凭据见 [R3565.json](evidence/R3565.json)。提交哈希用 `git log -1 --format=%H -- 程序/tasks_round/tasks_round_3565_result.md` 定位。
