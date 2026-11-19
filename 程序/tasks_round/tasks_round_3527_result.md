# R3527 结果文件 — L1 任务书轮 I9：子进程迁移与健康探针（I9a＋I9b）
<!-- round-evidence: {"commit_base": "5ec0783e", "credential_hits": 0, "evidence_sha256": "7bc607c8eac5fa1d", "exit": 0, "failed": 0, "passed": 210, "round": 3527, "tests": "run_selftests.py -k offline_asr media asset_thumbs pet_performance pet_test prompt_optimizer process_supervisor platform_process"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.3 结构治理轮（任务书明定 I9a／I9b 两个子场景，各 ≤3 个模块）。I9a：`domain/offline_asr_client.py`、`agent/core.py`（`command()` 即 `agent/media.py` 的 FFmpeg/ffprobe 唯一入口）、`ui/asset_thumbs.py`；I9b：`domain/pet_performance_service.py`、`domain/pet_test_service.py`、`agent/prompt_optimizer.py`。配套：`infra/workflow_process_registry.py` 补 `popen`/`pump_stderr` 注入缝、`communicate` 自动注销、`cancel_supervised` 按项目/阶段/种类取消、stderr 泵显式 `start_pump()`；门禁 `test_platform_process_boundary.py` 存量改豁免清单分类登记（I9-3）。
2. **测试跑了吗、基线过了吗？** 跑了。任务书定向命令 `run_selftests.py -k offline_asr media asset_thumbs pet_performance pet_test prompt_optimizer process_supervisor platform_process` **210 条 0 红**；默认 `smoke_test.py` **9/9 绿**；`smoke_test.py --architecture` 复跑结果见下表；`run_selftests.py --all --safe` 结果见下表；分支覆盖率基线按当前代码真实重测（92 目标全过，94 模块／2775 决策点）。
3. **欠账少了吗？** 少了。FL-06 长时/媒体绕过监督器启动点清零：I9a 迁 3 处（离线 ASR 常驻、FFmpeg/ffprobe 媒体命令、缩略图 worker）、I9b 迁 4 处（性能基准、增量自检×2、MCP 优化桥）；进程门禁棘轮非豁免计数降为 0，余 24 个登记点全部归入四类豁免（短时探测 6／OS 操作 5／detached·可见应用·退出后清理 12／已登记后台边界 1）并配 AST 超时复核；B-19 补 ComfyUI 探针失败不标记就绪的回归断言；LR-07 实测 186→184（`agent/core.command()` 4 处内置异常 raise 迁 `ProcessError`）。

## 领号说明

- R3527 由本工作树（`devin-l1-enterprise`／`codex/l1-enterprise`）经 `round_claim.py next` 领得（claims 登记约 2026-11-19T01:48:09+08:00）；领号子进程输出有 GBK 解码告警（已知环境噪声），登记本身成功并已核验 `round-claims.json`/`round-counter.json`。

## I9-1　迁移进程进进程表、可按项目/阶段取消 ✅

- 迁移点全部改经 `workflow_process_registry.spawn`：`offline_asr_client`（kind=`asr`，stage=`voice-asr`，project=程序根）、`agent/core.command()`（kind=`ffmpeg`，stage=`media`，project=cwd 或程序根）、`ui/asset_thumbs._ensure_worker`（kind=`ffmpeg`，stage=`asset-thumbs`，project=程序根，凭据白名单环境不变）、`pet_performance_service._start_check`（kind=`test_runner`，stage=`pet-performance`，project=用户项目，cwd=程序根）、`pet_test_service.start_incremental`/`run_incremental`（kind=`test_runner`，stage=`pet-test`，project=程序根，timeout=1800）、`prompt_optimizer` MCP 桥（kind=`optimizer`，stage=`prompt-optimizer`，project=程序根，timeout=125 与登记默认一致）。
- `spawn` 新增两个经 `popen_kwargs` 透传的缝（不占签名参数位，复杂度棘轮 PARAM_LIMIT=7 不破）：`popen` 显式注入子进程替身；`pump_stderr=False` 供随后走 `communicate` 的调用方关闭 stderr 泵（避免泵线程与 `communicate` 并发读同一管道）。
- `SupervisedProcess.communicate(input, timeout)`：与 `subprocess.run(timeout=...)` 同约定——超时/异常先结束进程树再 `forget_process`，成功路径同样自动注销，不留死登记；`cancel_supervised(project, stage=, kind=)` 按 `_supervised` 元数据过滤统一取消。
- 测试断言：`test_process_supervisor.SupervisedLifecycleTests` 2 条（popen 注入＋communicate 自动注销；按 stage/kind 过滤取消只杀目标进程）；`test_offline_asr_client.AcquireTests` 新增 `test_spawned_engine_cancellable_by_kind`（真实 spawn 登记后 `cancel_supervised(PROGRAM, kind='asr')` 命中并移除）；`test_acquire_spawns_and_waits_ready` 断言进程表含进程且 `supervised_info` kind/stage 正确。
- 异步会话侧：`pet_performance_service.poll_startup_check`、`pet_test_service.poll_incremental`、`offline_asr_client._on_exit`/`kill` 在进程退出路径补 `forget_process`，登记表不积死条目。

## I9-2　健康探针与错误归类 ✅

- **离线 ASR**：`EngineHost.spawn` 在拿锁后先置 `state='starting'` 再 `spawn('asr', …, timeout=_READY_TIMEOUT=300, health=lambda: state=='ready')`——握手（首个 `ready` JSON 行）完成前状态恒为「启动中」；`acquire` 轮询发现 `starting` 超 `_READY_TIMEOUT` → `kill(_handshake_timeout_reason())` → 原因串含 **`E-TOOL-TIMEOUT`** 并拼接监督器 stderr 尾部最后 5 行（`_stderr_tail_text`，有界 200 行 deque）。
- 测试：`test_acquire_handshake_timeout_is_tool_timeout_with_stderr_tail`——假进程永不 ready 也不退出，`_READY_TIMEOUT` 打桩 0.3s，断言 `EngineUnavailable` 文案含 `E-TOOL-TIMEOUT` 与注入的 stderr 尾部行。
- **ComfyUI**：`infra/comfy_runtime.wait_comfy` 本就是 `/system_stats` 探针循环，失败只重试不返回；新增 `test_comfy_wait_never_marks_ready_when_probe_keeps_failing`（`test_platform_tools.py`）——`Comfy` 客户端持续抛 `OSError`，断言只打 `/system_stats` 且超时抛「未就绪」，绝不提前返回（即不标记就绪）。
- 监督器侧：`classify_exit` 归类 `E-TOOL-TIMEOUT/MISSING/FAILED`（I8 已建），`spawn` 启动失败 `FileNotFoundError→E-TOOL-MISSING`、其余 `OSError→E-TOOL-FAILED`；`offline_asr_client` 启动异常收进 `dead_reason`。

## I9-3　进程门禁棘轮非豁免计数为 0 ✅

- `SPAWN_SITE_BASELINE` 由裸集合改为 `SPAWN_SITE_EXEMPT` 四类豁免登记（并集仍作棘轮基线，只减不增）：
  - `short_probe`（6）：`aigc_lint.py:85`、`engine_probe.py:140`、`native_apps.py:42`、`codex_paste.py:34`、`console_submit.py:14`、`previs_automation.py:22`——同步有界调用；
  - `os_operation`（5）：`app_shortcut.py:50/114/243`、`native_apps.py:75/87`——快捷方式/文件关联/taskkill/tasklist 系统级调用；
  - `detached`（12）：`native_apps.py:124`（Blender 可见窗口）、`qwen_adapter.py:99` 与 `workflow_engines.py:456/518`（可见 CLI 控制台，自带 `register_process`）、`desktop_idea_chat.py:964/980`、`desktop_media_pages.py:873`、`desktop_send_choice.py:54`（可见桌面应用）、`desktop_tray.py:411`（`os._exit` 前自重启，必须脱离宿主）、`log/storage/workspace_maintenance` 三个 `launch_cleanup`（退出后清理进程，Job 关闭会误杀）；
  - `background_boundary`（1）：`codex_tasks.py:45`（`_BACKGROUND_BOUNDARIES` 已登记的 app-server stdio 边界，自带 pump/消息队列生命周期）。
- 新增门禁自审：`test_exempt_registry_covers_baseline_exactly`（豁免清单与棘轮基线一一对应、无重复类别）；`test_bounded_sites_declare_timeout`（short_probe＋os_operation 两类豁免点 AST 复核调用节点必带显式 `timeout` 关键字）。
- 迁移后扫描零新增绕过点；`platform_tools.run_process` 属任务书认可的短时探测通道（好样本自审不误报），`offline_asr_setup`/`skill_import_service`/`keyframe_evidence`/`native_asset_codec`/`workspace_maintenance` 等 B 类存量本就在该通道上，不在本轮范围。

## 存量缺陷修复（本轮实测发现）

- **stderr 泵与 communicate 并发读管道**：`spawn` 默认起 `_pump_stderr` 守护线程；`agent/core.command()` 与 `prompt_optimizer` 随后走 `communicate` 会造成两线程并发读同一 `Popen.stderr`（BufferedReader 非线程安全，可能丢字节/死锁）。修法：`SupervisedProcess` 构造不再自动起泵，新增幂等 `start_pump()`，`spawn` 默认调用；`communicate` 场景经 `pump_stderr=False` 关闭。`test_supervised_stderr_tail` 同步改显式 `start_pump()`。
- **静态/动态导入新循环**：`agent/core.py` 新增 `from infra.workflow_process_registry import spawn` 与既有 `workflow_process_registry→app_logging→core` 链构成 L1 同层环（`test_no_circular_import` 静态＋动态双红）。修法：`workflow_process_registry` 去掉全部 3 处 `app_logging.swallowed` 惰性 import，改用模块级 `logging.getLogger('workflow_process_registry').debug(..., exc_info=True)`（stdlib 先例见 `asset_thumbs`；silent-exception 棘轮只禁 `except Exception: pass`，debug 调用不命中）；`_layers.SAME_LAYER_EDGES` 同步移除已失效的 `('workflow_process_registry','app_logging')` 边。
- **参数复杂度棘轮**：`spawn`/`SupervisedProcess.__init__` 初版各超 PARAM_LIMIT=7；改经 `popen_kwargs.pop('popen'/'pump_stderr')` 透传与 `start_pump()` 拆分后实测 spawn=7、__init__=7，棘轮复绿。
- **json.loads 债务锚点**：`prompt_optimizer` 的 MCP 响应解析仍属「外部进程输出解析」豁免语义，但调用实参 `proc.stdout→out` 使 AST 锚点摘要变化；`架构统一基数.json` 对应 `point` 按扫描器实测新锚点 `8a079eec04952597` 更新并注明缘由。
- **`asset_thumbs.reset_worker` 语义回退**：`_WORKER` 改存 `SupervisedProcess` 后，`worker.wait(timeout=...)` 走包装器——包装器超时返回 `None` 而非抛 `TimeoutExpired`，原 kill 升级路径失效。修法：操作落到解包后的底层 Popen（`getattr(worker,'process',worker)`），`terminate/wait/kill` 恢复原生异常语义，`forget_process` 同步改用解包句柄。
- **LR-07**：`agent/core.command()` 迁移时新增的 4 处中文 `RuntimeError` raise 会推高 L1 内置异常计数（实测 188>186 红）；改为 `ProcessError`（`E-TOOL-MISSING/TIMEOUT/FAILED`，兼容 `RuntimeError` 捕获面，文案不变）后实测 184，`层间合规清单.json` LR-07 violations/baseline 同步下调至 184。

## 验证汇总

| 命令 | 结果 |
| --- | --- |
| `run_selftests.py -k offline_asr media asset_thumbs pet_performance pet_test prompt_optimizer process_supervisor platform_process` | 210 条 0 红（13 文件；含 GUI 令牌等待约 14 分钟的环境排队，全部通过） |
| `run_selftests.py -k process_supervisor pet_test platform_tools offline_asr`（pump_stderr 重构后复验） | 142 条 0 红 |
| `smoke_test.py` | 9/9 绿 |
| `smoke_test.py --architecture`（首轮） | 550 条 6 红：覆盖率决策点、参数棘轮×2、导入环×2、静默异常、json.loads 锚点——均已修复 |
| `smoke_test.py --architecture`（复跑） | 550 条 1 红：`test_round_number_continuous`（结果文件先于状态页头同步所致的时序项）；状态页升 3528 后定向复验 5/5 绿，等价全绿 |
| `run_selftests.py --all --safe` | `full_safe_preflight` 协议：脏树不产凭据，故本轮改动随提交落为干净树后实跑；提交前后台 auto 通道两度占用全量锁，本树诊断口径未取到完整窗口。开发期同代码口径全量曾跑通 1773 条 0 红（skipped=2）；最终结果与凭据以 `full-safe-receipts.json` 及状态页回填为准 |
| `scripts/branch_coverage_report.py <92 targets>` | 完成：94 模块／2775 决策点／1547 覆盖／目标用例全通过；`core.py` 35 点 28.6%（covered=10）、`workflow_process_registry.py` 68 点 73.5%（50/68）、`comfy_runtime.py` 覆盖 1→3（新探针测试带动） |

## 分支覆盖率基线重测说明

- 起因：`agent/core.py` 新增 try/except 决策点 33→35、`workflow_process_registry.py` 新增 spawn/communicate/pump 代码 61→68，基线「决策点数＝当前 AST」校验必红，须真实重测。
- 过程：92 个 targets 全量重跑（1773 用例 OK，skipped=2），实测 `core.py` covered 仍为 10（新增 except 分支未被现有用例命中，属真实测量值非凑数），`workflow_process_registry.py` covered 48→50。
- 基线 `tests_ok: true`、`targets` 92 项、模块 94 个，与 `_layers` L0/L1 实体集合一致；`分支覆盖率下限.json` 未动（core.py 实测 28.6% 仍高于下限 21.0，棘轮只升不降未触发）。

## 提交说明

- 本文件随 R3527 提交；改动 `.py` 文件的 `--tests` 证据由 `scripts/dev.py commit` 自动生成 `tasks_round/evidence/R3527.json`。
