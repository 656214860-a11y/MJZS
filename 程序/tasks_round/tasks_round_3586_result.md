# R3586 — A10 第五批独立 ASR 协议与读帧边界
<!-- round-evidence: {"commit_base": "9f48cb26", "credential_hits": 0, "evidence_sha256": "08fdf0ed7b9b4ea7", "exit": 0, "failed": 0, "passed": 145, "round": 3586, "tests": "run_selftests.py -k test_offline_asr_client test_offline_asr_engine test_offline_asr_setup test_distribution_build test_distribution_selfcheck test_dynamic_import_registry test_static_names test_static_hygiene test_complexity_ratchet"} -->

1. 结构治理轮。以 `9f48cb26`（R3582）为起点，在 `0f9b` 专用工作树的 `codex/architecture-a10-asr-protocol` 分支执行。两处生产模块，领号 R3586，中央队列无对应项，开工范围扫描无活跃车道重叠。
2. 默认冒烟 9/9（8 项业务检查及隐藏桌面探针），受影响冒烟 10/10，终态定向门禁 145/145。完整架构与覆盖率数据见下。
3. 收口识别进程协议缺口；未触发主干安全全量复验，既有安全全量凭据与历史欠账沿用。

## 协议与失败语义

- `domain/offline_asr_client.py` 与 `voice_engine/offline_asr_server.py` 保留 stdio JSON-Lines。新服务通过 `ready.protocol_version=1` 声明支持版本。新客户端收到该声明后为每个命令加版本。旧服务缺版本时客户端沿用旧命令格式，旧客户端的无版本命令仍受新服务支持。显式未知或类型错误的版本在客户端拒绝就绪并回收进程，在服务端产生错误事件并跳过该命令。
- 双向按 UTF-8 原始字节执行 `readline(8 MiB + 1)`，帧上限 8 MiB 含换行符及可选 CR。超限无需等待行尾。客户端终止当前引擎并给出字节超限原因，服务回复协议错误并以 3 退出。服务端畸形 JSON 和无效 UTF-8 回复错误后继续，客户端忽略畸形响应。EOF 的半帧在客户端按连接结束处理，服务拒绝半帧并以 3 退出。
- v1 利用同一 stdout 的有序性。新会话携带递增 ID，收到对应的开始确认才接受识别结果，期间仅接收属于本次开始命令的错误。旧进程的读线程无法向新进程会话投递。取消后的识别结果和已关闭会话的结果被忽略。停止超时回收引擎，活跃会话遇到进程退出收到 error/closed。无版本对端延续旧会话边界。
- 启动继续复用现有 `launch_text_process` 的隐藏控制台入口，仅在识别 stdout 读取其字节缓冲区。安装仍是独立的一次性 bootstrap/下载进程，使用已有 progress/done/error 流。安装消息的 framing 加固可单独立项；本轮启动和安装链只做回归。

## 红测与回归

- 改生产代码前运行四个新增测试，出现四个失败子项和一个错误。客户端发出无版本命令（`None != 1`），未知版本与过长响应均只得到通用退出，服务端 ready 缺 `protocol_version`，过长命令仍返回 0（期望 3）。使用无换行或多字节数据验证读端只取上限加一个字节。
- 专项覆盖版本一致、双向旧调用、未知版本、畸形命令、识别/取消/超时/退出及迟到结果。分发门禁与动态进程闭包包含引擎六个运行文件。实际构建计划包含六文件及 README，运行期 ASR 文件为零。临时源预放两个代表性缓存文件时，旧清单会把它们收入 keep；连同缺少精确六文件发布验证的缺口保留给 A15。未下载真实模型。
- 补做真实 stdio 联调。用桩替换模型加载，经产品客户端启动独立服务，验证 v1 就绪、取消、在同一进程复用会话、正常停止和退出码 0。
- 行覆盖按原十组目标实测 115/115，83/662 个生产模块有覆盖，11 个核心路径达现有下限。首跑因功能树缺随附 FFmpeg 的 PATH 入口导致一个关键帧替换测试失败，添加只读来源的随附 FFmpeg 后通过。
- 分支覆盖保留仓库快照目标，追加 ASR 三组，隐藏桌面执行 1850 条，1846 条通过、4 条登记跳过。94 个 L0/L1 模块全部达标，1535/2737 个决策点双结果覆盖。复杂度修复只在计量范围外的 L2 客户端改动，终态 ASR 客户端与复杂度门禁专项通过。覆盖率下限及快照保留。
- `--gate` 的共享增量台账在该树选择了 749 个文件，启动后停止这一遍串行扫描。有效的本轮定向证据见 [R3586.json](evidence/R3586.json)。未启动安全全量，中央真实凭据 `last_full_safe_all_round` 为 3544。

## 完整架构、提交与交接

以 R3582 同一起点的完整架构实测 601/603 为比较基线。新工作树首轮额外暴露缺性能基准历史和缺技能包两项环境问题，分别复用只读历史副本并校验哈希，以及在专用树恢复三个锁定技能包并校验树哈希。新增客户端嵌套深度问题已修复并专项复验。

终态完整架构 601/603，460.070 秒，退出 1。失败集合与 R3582 一致。

| 失败项 | R3586 实测 |
| --- | --- |
| `DependencyWhitelistTests.test_site_packages_whitelist` | 随附环境仍存在白名单外的 `annotated-types`、`pydantic`、`pydantic-core`、`typing-extensions`、`typing-inspection`。 |
| `RoundBaselineTests.test_round_number_continuous` | 专用树继承状态轮次 3409，最新结果 3586，期望 3587。仅主干同步状态页。 |

通过标准入口保存 `R3586-FAIL` 检查点。提交哈希由 `git log -1 --format=%H -- 程序/tasks_round/tasks_round_3586_result.md` 定位。A10 的识别协议实现已交付，正式收口仍需在授权合并时复核 A9 前置、同步状态页并验证白名单。安装流的 `_phase()` 仍按文本整行读取，后续若纳入协议加固，边界是 `offline_asr_setup.py` 与 bootstrap、下载两个消息生产方。A15 继续承接精确分发闭包、运行时缓存排除及依赖锁校验。本轮未合入、推送或建立下一任务。
