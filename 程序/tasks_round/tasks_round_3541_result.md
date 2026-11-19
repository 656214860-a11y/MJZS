# R3541 — A9-9 生产静态依赖环门禁

1. 类型为 §3.3 结构治理轮。基线 `4ebc8373`，专用分支 `codex/architecture-a9-ring`。变更限环守卫、架构说明和本轮记录。
2. 冒烟业务检查 8/8，隐藏桌面探针通过。生产门禁按预期拒绝实际环，完整架构及定向结果见下。
3. 生产环仍待 A10；未新增豁免。安全全量未触发。读取到的上次绿凭据是 R3293，其后主干计数 23 个源码轮次，门禁线 8。最近后台运行 `e65e8b4` 退出 1。

## 前提与范围

- 已核对任务书 A9、A1/R3405、A3/R3409、A4/R3411、A6/R3415、A9-1/R3419 和 A9-8/R3519 的相关证据。未匹配本批队列任务。领号成功返回 3541，旧子进程报告 GBK 解码告警，后续命令设置 `PYTHONUTF8=1`。
- 明确使用仓库根相对路径执行 scope。活跃车道与架构文档存在重叠，本轮只向门禁节增补扫描口径。基础设施生产源码归 L1 车道，`codex/l1-enterprise` 只读核对至 `5ec0783e`，其中 `6ecf2b1d` 修改过台账异常；当前分支未合入该车道。
- 本树借用主树的现有随附解释器，主树产品文件未修改。本树继承的状态页为 3409，与本轮结果 3541 不连续，状态页留给合入轮同步。

## 复现与验证

- 生产图按 662 个运行时源文件的完整标识、静态 AST 边和 Tarjan 重建。两个多节点 SCC 为既有 `agent.core / agent.publication / infra.file_cache` 和下表五个 `infra` 模块。实际闭环之一为 `api_endpoints → model_metering → diagnostic_capture → model_pool → api_endpoints`，另有 `diagnostic_capture ↔ request_ledger`，旧候选顺序不是实际闭环链。
- 旧生产静态/动态棘轮 2/2 通过。先写合成负例和无环对照，旧守卫运行 2 项中 1 红，负例为 `AssertionError: AssertionError not raised`。迁移至现有包解析后，合成负/正例及旧动态棘轮共 3 项通过，生产静态测试 1 项如实失败，定位 11 处导入。
- 静态存量环沿用原分量，按完整名称记录。常量动态导入仍使用既有动态棘轮；本批的精确图覆盖静态声明及函数内静态懒导入。该图表示代码依赖，未测定某条运行路径是否触发初始化失败。
- 架构定向由项目凭据工具执行，74 条用例通过，1 个红文件，退出 1。红文件是环守卫，专项结果确认其唯一红用例为生产静态环检查。标准 `dev.py commit` 生成失败检查点 `4afe8f9a` 后，用 `round_evidence.py` 补跑并保存实际红凭据。检查点暂存新增行的凭据形态扫描零命中。
- 完整架构前置 597/600（386.614 秒），后置 597/602（367.549 秒），均退出 1。保留三个历史红项：基准历史文件缺失、轮次不连续、编剧参考文件缺失。
- 后置新增生产环和 `test_site_packages_whitelist` 两个红项。白名单单测独立复现，报告共享解释器 `purelib` 中的 `annotated-types`、`pydantic`、`pydantic-core`、`typing-extensions`、`typing-inspection`。这批包的安装元数据目录于后置运行期间创建，前置白名单检查通过。本轮未改白名单、依赖锁及运行环境。
- 实跑凭据见 [R3541.json](evidence/R3541.json)，测试代码与检查点一致。最终提交由 `git log -1 --format=%H -- 程序/tasks_round/tasks_round_3541_result.md` 定位。

## A10 拆环交接

以下路径均以 `程序/infra/` 为基准。八条不同的环内边由 L1 基础设施车道负责。诊断装配若需接线，由 L1 与现有启动装配所有者协调。

| 来源及行号 | 目标 | 职责 |
|---|---|---|
| `api_endpoints.py:9` | `model_metering` | 共用可重放重试状态 |
| `diagnostic_capture.py:294` | `model_pool` | 启动模型池为空检查 |
| `diagnostic_capture.py:473,504` | `request_ledger` | 台账损坏和未知积压的只读探测取路径 |
| `model_metering.py:20` | `diagnostic_capture` | 计量降级诊断 |
| `model_metering.py:31` | `request_ledger` | 记录单次请求尝试 |
| `model_pool.py:22` | `model_metering` | 共用可重放重试状态 |
| `model_pool.py:24,958,964` | `api_endpoints` | 供应商 HTTP 辅助与兼容调用 |
| `request_ledger.py:146` | `diagnostic_capture` | 锁超时后的 `E-IO-WRITE` 降级记录 |

- 两组环边互不相交，至少要断两条边。仅在内存图删除 `request_ledger → diagnostic_capture` 与 `diagnostic_capture → model_pool` 后重新求 SCC，只剩既有三模块存量环。建议先核对 L1 已有实现，再将降级输出接入现有诊断 sink，将模型池读取作为探针依赖接入现有启动组装。按每批最多三模块划分，保留现有调用入口。
- 第一批验证台账锁超时仍按现有规则标记 unknown、错误代码照常记录、重试不重复结算、诊断失败不会替换业务失败。第二批验证有模型、空模型和读取异常三种探针结果，保留启动诊断的降级行为和兼容入口。复跑生产静态与既有动态守卫，再核对启动、模型池、端点、计量及台账定向。
