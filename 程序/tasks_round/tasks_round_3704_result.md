# R3704-FAIL：A12 第八批——子进程取消与进程树回收
<!-- round-evidence: {"commit_base": "2b7ad889", "credential_hits": 0, "evidence_sha256": "c397c4d0a17da836", "exit": 0, "failed": 0, "passed": 59, "round": 3704, "tests": "run_selftests.py -k cli_streaming platform_tools workflow_engines_run"} -->

## 三问

1. 类型：可靠性功能轮；只修复已启动本地子进程在取消或 deadline 后仍等待原 timeout 的缺口。
2. 验证：定向、真实 Windows 父孙进程、默认冒烟与本轮架构门禁通过；完整架构 601/605，四项失败与 R3694 相同，因此按规则保留 FAIL 检查点。
3. 欠账：本地进程取消响应与登记进程树回收减少；跨卷/断电恢复、跨运行诊断归档、未决台账分段和整页长任务性能仍留 A12 后续。

## 范围与实现

- 生产模块仅 `contract/platform_tools.py`、`contract/process_wait.py`，没有修改业务状态机、UI、计费或供应商逻辑。
- `communicate_or_kill` 的流式与非流式等待在存在 `ExecutionControl` 时最多每 100 ms 检查一次 cancel/deadline。
- 停止发生在子进程启动后时，先调用既有 `terminate_process_tree`（Windows `taskkill /T /F`，登记进程仍有 Job Object 兜底），再抛 `ExecutionStopped(started=True)`；异常携带 `process_tree_terminated`，不能把本地停止误作远端未执行。
- 普通调用没有执行控制时保持原有单次 `communicate`/`wait` 行为；原 timeout 的 3 秒回收和父进程 kill 兜底保持。
- 轮询决策抽到纯 L0 模块，避免 `platform_tools.py` 超过 1000 行；新模块不直接导入 subprocess/time，宿主能力由适配器注入。

## 故障与性能证据

- 红测：原流式与非流式等待均不会在等待期间消费执行取消/deadline，只在整个 timeout 后进入回收。
- 真实 Windows 验收：Python 父进程再启动睡眠孙进程；30 ms 后取消，整棵树在 1.133 秒内退出，父句柄结束，孙 PID 不再出现在 `tasklist`。
- 取消反馈轮询上限 100 ms；进程树工具同步上限仍为 3 秒。若树终止工具失败，异常的 `process_tree_terminated=False` 显式暴露，不宣称已回收。

## 验证终态

- 进程/平台/工作流定向：61/61。
- 本轮行覆盖、分支覆盖、复杂度、模块体积、L0 纯度、分层及 skip 门禁：115/115。
- 默认冒烟：9/9。
- 完整架构：601/605；历史四项为缺 `维护记录/基准历史.json`、共享解释器额外包白名单、分支状态轮次未同步、缺 SKILL 引用文件。
- 行覆盖：`contract/process_wait.py` 33/44（75.0%）；分支覆盖 5/11（45.5%）。`platform_tools.py` 决策点 135→140，保守保留既有覆盖点 53，记录 37.9%，未降低下限 36%。
- 完整安全全量未重复运行；未调用真实供应商、未产生费用、未触碰用户项目。

## 剩余 A12

- 跨运行诊断归档与未决台账分段存储；不能删除 unknown/未决计费核心行。
- 其他后台队列和整页长任务响应、100/1000/10000 条长列表启动/切页测量。
- 真实满盘、跨卷、断电及其他发布入口的异常退出恢复。
- 供应商查单、跨进程幂等和真实账单核对属于 A15/C 依赖，不在本轮伪实现。
