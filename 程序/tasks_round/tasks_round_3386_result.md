# R3386 结果文件 — L1 任务书轮 I0：基线重测、盘点与门控核对
<!-- round-evidence: {"commit_base": "00ff7962", "credential_hits": 0, "evidence_sha256": "1d86bb37af4e920e", "exit": 0, "failed": 0, "passed": 0, "round": 3386, "tests": "docs-only"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.10 验证／基线轮（不改任何 `.py`；只新增本结果文件，并按 I0-1 就地修订任务书 §0.1／§1.3 的数字与坐标）。
2. **测试跑了吗、三个基线过了吗？** 测量命令全部实跑：AST 扫描复用 `tests/architecture/_scan.py`／`_layers.py` 同口径；`smoke_test.py` 默认冒烟 **9/9 绿**；`smoke_test.py --architecture` 整轮实跑 **532 条用例，1 失败＋1 错误，均为工作树缺本机文件的环境性红**（补齐后两条定向复跑全绿，见下）；全量回归未触发（零源码变更），欠账以 `full-safe-receipts.json` 为准（最近凭据 `dc3b3bb8` 有 4 个红文件，非本车道引入）。
3. **欠账少了吗？** 无新增欠账；顺带修正立书数字漂移 9 处（F1 口径注明、F3 层别构成、F5 口径注明、F7 总数 263、F8 私有访问 1、F11 L4=18、F19 扇入三值、F20 补列 asset-disk、FL-02/04/06/09/10/17 实测回填），使任务书与 master `00ff7962` 实测一致。

## 测量口径

- 工作树：`devin-l1-enterprise`（分支 `codex/l1-enterprise`，基于 master `00ff7962`＝R3383 合并轮）；解释器：主工作区 `运行环境\Python\python.exe`（Python 3.14.7，工作树内无 `运行环境`）。
- 分层登记：`tests/architecture/_layers.py` 的 `LAYERS`；文件扫描：`tests/architecture/_scan.py` 的 `module_scan_files()/module_name()/parse()`（`contract.x`／`infra.x` 等包路径归一为扁平登记名；`from infra import X` 的别名按包名＋成员名展开）。
- AST 私有访问／线程／动态导入／扇入均为自写一次性扫描脚本（`%TEMP%\l1_i0_audit2.py`），口径在各节注明。
- **工作树环境注记**：本工作树缺两个只存在于主工作区的本机文件——`维护记录/基准历史.json`（.gitignore:63）与 `skills/00全流程SKILL/AIGC创作全流程/`（gitlink 160000、无 .gitmodules 映射）。已从主工作区复制补齐（不入库）；缺失时架构门禁 `test_agents_md` 报 ERROR、`test_skill_reference_injection` 报 FAIL，补齐后两条定向复跑 24/24 绿。此为**环境性红**，非代码问题，后续各轮在本工作树沿用此补齐状态。

## I0-1　F1–F21 重测（命令与输出摘要）

| # | 立书值 | R3386 实测 | 结论 |
| --- | --- | --- | --- |
| F1 | L0 35、L1 59、L2 87、L3 79、L4 149、L5 2 | `LAYERS` 登记计数 **35/59/87/79/149/2（合计 411）**，与立书一致。注：按 `module_scan_files()` 实际文件数 L2 仅 81——6 个登记名（`writing_files`、`writing_workflow`、`asset_gating`、`keyframe`、`keyframe_api`、`previs`）无对应扫描文件（登记在册但实体不在扫描面，历史遗留，不属本书范围） | 登记口径一致；已在本书 F1 行补注文件口径差异 |
| F2 | L1 静态反向依赖 3 条 | AST 重扫确认 **3 条**：`engine_probe→workflow_engines`(L3)、`h3_reference_adapter→shot_assets`(L2)、`native_apps→white_model`(L4)；`架构统一基数.json`「层级」`baseline_exempt=18` | 一致 |
| F3 | `ui_plugin_registry` 动态加载 23 个 L4 插件 | 实测 `UI_PLUGINS` frozenset **23 项**；`module()`（`:24`）`import_module(text)` 变量导入。**新发现**：23 项中并非全是 L4——含 L2 `agent.shot_assets`、L3 `agent_dispatch/stage_exec/stage_flow/previs_automation/workflow_settings`、L5 `desktop_launcher`，即该登记表实际跨 L2–L5 加载 | 数量一致；层别构成已补注（对 I2 重要：上移 L4 后方可合法加载 L3，反向不行） |
| F4 | L1 界面支撑模块 | `ui_tokens`（扇入 96）、`tk_timers`（11）、`ui_plugin_registry`（20）、`app_icon`、`clipboard_lock` 均在 L1 登记 | 一致 |
| F5 | 业务语义命中数（continuity_ledger 14、project_settings 10 等） | 用本书未给的正则无法逐字复现；改用宽口径词表（阶段\|剧本\|分镜\|资产\|镜头\|首帧\|配音\|字幕\|交付\|预演\|白模\|连贯\|角色\|场景\|台词）重测：`continuity_ledger` 59、`asset_prompt_rules` 54、`pet_state` 33、`project_settings` 21、`h3_reference_adapter` 14、`script_text_reader` 8、`stage_model_value` 等。**模块排序与立书一致**（同一批业务语义模块居前），绝对值因词表口径不同不可比 | 结论不变；已在书中注明口径 |
| F6 | 2/59 有 `__all__`（file_index、global_library_service 门面） | 根级门面 `file_index.py:9`、`global_library_service.py:5` 均有 `__all__`；`infra/` 实体文件 **0/59** 有 `__all__`（`infra/file_index.py` 无；`global_library_service` 尚未包化、无 infra 实体） | 一致（门面口径 2/59） |
| F7 | 约 140 处中文用户文案通用异常 | AST 实测 **263 处／37 个模块**（口径：`raise` 节点的异常表达式含 CJK 字符串常量；行正则口径 262，差 1 为多行 raise）。立书「约 140」实为其列出的头部 12 模块之和（32+20+14+10+9+9+8+8+7+7+7+6≈137），非全层总数。逐模块明细见 FL-04 | **总数已修订为 263** |
| F8 | 上层访问 L1 私有名 0 处 | AST 实测 **1 处**：`ui/task_center_ui.py:15` `diagnostic_capture._state()`（L4→L1 私有名访问） | **立书值有误，已修订为 1** |
| F9 | 子进程两套入口 | 确认：`workflow_process_registry`（Job Object＋并发槽＋`run_registered`）vs `platform_tools.run_process/launch_background/launch_text_process`（无 Job Object）＋零星 `subprocess.run` 直调。明细见 FL-06 | 一致 |
| F10 | 进程门禁盲区 | `test_platform_process_boundary.py` 仍只识别字面 `subprocess.Popen(`；绕过写法（`(popen or subprocess.Popen)`、`popen=` 参数、`subprocess.run`、`launch_*`）依旧存在，见 FL-06 清单 | 一致 |
| F11 | 线程无统一治理 | 实测：L2 **3** 文件（`offline_asr_client`、`offline_asr_setup`、`speech_api`）、L3 **9** 文件（`agent_skill_sync`、`codex_skill_sync`、`desktop_automation_service`、`idea_chat_controller`、`previs_automation`、`previs_monitor`、`qwen_adapter`、`stage_parallel`、`storyboard_direct_api`）、L4 **18** 文件（立书约 17，实测 18）、L1 自身 2 文件（`temporary_sweep`、`tk_timers`）、L0 边界 1 文件（`platform_tools`） | L2/L3 与立书一致；L4 17→18 已修订 |
| F12 | 上层私有诊断日志 | 见 I0-5：诊断/事件日志写入点 **4 个文件**；引擎 IPC 与产物文件不计 | 见 I0-5 |
| F13 | 预算判定在 L4 | `pet_agent.py:44-48` `BUDGET_KINDS` 五类＋`DEFAULT_BUDGET` 上限、`:449` `Budget` 类、`:909-916` `spend()` 判定；L3 `skill_orchestrator.py:245,558` 发 `budget.exceeded` 事件；L1 仅 `model_metering`/`request_ledger` 计量 | 一致 |
| F14 | 无聚合指标 | `infra/business_log.py` 无 counter/histogram/按维度汇总；L1 grep `metrics|histogram` 无命中 | 一致 |
| F15 | 资源感知只有磁盘一处 | `infra/diagnostic_capture.py:274` `shutil.disk_usage` 为唯一磁盘读数；无内存/网络/显存探测 | 一致 |
| F16 | 无自调优 | L1–L3 grep `adaptive|autotune|AIMD` 仅 `agent/volcengine.py:29` `'ratio':'adaptive'`（视频宽高比参数，非调优） | 一致 |
| F17 | DPAPI 仅 model_secrets | `infra/model_secrets.py:43-53` CryptProtect/UnprotectData 唯一实现；`domain/tts_api.py:24`、`infra/cloud_assets.py:19` 仍 `os.environ['LOCALAPPDATA']` 直取 | 一致 |
| F18 | 无统一产物索引 | 无 `artifact_index` 模块；去重在 `hash_backend`、血缘在 L0 `contract/artifact_lineage.py`、回收走 `storage_maintenance.recycle_paths():318` | 一致 |
| F19 | L1 扇入前列 | 实测：`core` **108**（书 105）、`ui_tokens` 96、`file_cache` **72**（书 71）、`app_logging` 69、`storage_maintenance` **37**（书 36）、`model_pool` 24、`pet_state` 21、`ui_plugin_registry` 20、`project_settings` 17、`pet_llm` 17 | 小幅漂移，已修订 |
| F20 | 地基分支占用 | 见 I0-6/G-B：4 支分支命中（hardening/api-disk/asset-disk→model_router+storage_maintenance+token_saver；config-write-safety→project_settings）。立书漏列 `foundation-asset-disk`（领先 17） | **分支清单已补全** |
| F21 | 可扩展门禁 8 项 | `test_platform_process_boundary`、`test_subprocess_timeout_boundary`、`test_print_ratchet`、`test_secret_sink_audit`、`test_layers`、`test_dynamic_import_registry`、`test_http_boundary`、`test_json_io_boundary`、`test_deletion_gateway` 全部存在于 `tests/architecture/` | 一致 |

## I0-2　FL 起点值实测（逐模块明细）

### FL-02 — L0–L3 非字面量动态导入：**1 处**

AST 扫描 `import_module`/`__import__` 全部调用（L0–L3，12 处中 11 处为字面量、已被登记/棘轮覆盖）：

| 位置 | 形态 | 目标 |
| --- | --- | --- |
| `infra/ui_plugin_registry.py:24` | `import_module(text)`（`text` 为变量，先经 `UI_PLUGINS` frozenset 白名单校验） | 23 个登记插件（跨 L2–L5，见 F3） |

结论：FL-02 起点＝1，即本书预判的唯一后门。

### FL-04 — L1 中文用户文案通用异常：**263 处／37 模块**

口径：`raise` 节点的异常表达式含 CJK 字符串常量（AST；行正则复核 262）。逐模块：

| 模块 | 处数 | 模块 | 处数 | 模块 | 处数 |
| --- | --- | --- | --- | --- | --- |
| storage_maintenance | 45 | publication | 7 | stage_model_value | 2 |
| request_ledger | 34 | continuity_ledger | 7 | model_router | 1 |
| comfy_service | 25 | file_index | 7 | pet_state | 2 |
| core | 15 | qwen_setup | 2 | project_settings | 1 |
| seedream_api | 13 | script_text_reader | 5 | ui_plugin_registry | 1 |
| unit_of_work | 12 | asset_prompt_rules | 1 | workflow_process_registry | 3 |
| media | 11 | app_icon | 1 | workspace_maintenance | 1 |
| model_secrets | 9 | file_cache | 2 | account_store | 1 |
| cloud_assets | 8 | diagnostic_capture | 2 | api_endpoints | 6 |
| h3_reference_adapter | 8 | global_library_service | 6 | integrations | 1 |
| native_asset_codec | 4 | native_apps | 2 | broadcaster | 3 |
| comfy_runtime | 3 | client_profiles | 2 | line_endings | 3 |
| log_maintenance? — 见脚本明细 | | temporary_sweep? — 见脚本明细 | | | |

（完整 37 模块 JSON 明细见测量脚本输出；上表按处数降序列出全部非零模块——零处模块略。）

I7 第一批覆盖 `request_ledger`(34)、`comfy_service`(25)、`unit_of_work`(12) 合计 71 处；棘轮起点取全层 263。

### FL-06 — 长时/媒体子进程不经监督器的启动点：**28 处调用点／20 个文件**

AST 扫描全部进程启动调用，按「是否经 `workflow_process_registry`（Job Object）」分类。`platform_tools.*` 为 L0P 边界本体（其内部 Popen 合法，`platform_tools.py` 自身 4 处 Popen＋1 处 run＋1 处 launch_background 不计）；`workflow_process_registry.py:303` 的 `launch_text_process` 为监督器内部调用不计。下列为**绕过监督器**的调用点：

**A. `subprocess.run` 直调（9 处／5 文件，不进 Job Object）**

| 文件:行 | 层 | 性质 |
| --- | --- | --- |
| `infra/aigc_lint.py:85` | L1 | 跑机检脚本（`sys.executable -B`，timeout） |
| `infra/engine_probe.py:126` | L1 | 引擎探测 `run()` 包装（timeout 可配） |
| `infra/native_apps.py:32,65,77` | L1 | 本机应用探测（3 处） |
| `orchestrator/previs_automation.py:22` | L3 | 预演自动化调用 |
| `app_shortcut.py:50,114,243` | L5 | OS 快捷方式/文件关联操作（3 处，系统级非媒体） |

**B. `platform_tools.run_process` 调用方（12 处／11 文件，短时探测通道但无 Job Object）**

| 文件:行 | 层 | 性质 |
| --- | --- | --- |
| `agent/core.py:255`（`command()` 内） | L1 | FFmpeg/ffprobe 媒体探测与处理（`agent/media.py:51,89` 两处经此入口） |
| `domain/offline_asr_setup.py:53` | L2 | 离线语音识别设置（git clone 等，REPO_CLONE_TIMEOUT） |
| `agent/prompt_optimizer.py:188` | L4 | 提示词优化器进程 |
| `domain/skill_import_service.py:427` | L4 | git clone 导入（REPO_CLONE_TIMEOUT） |
| `ui/asset_thumbs.py:858,907` | L4 | FFmpeg 缩略图（2 处） |
| `domain/keyframe_evidence.py:76` | L2 | 首帧证据抽帧（ffmpeg） |
| `infra/native_asset_codec.py:51` | L1 | 媒体转码 |
| `domain/pet_test_service.py:79` | L2 | 宠物测试服务进程 |
| `stage_layout.py:444` | L0 | `--version` 探测（timeout=15，短探测） |
| `domain/white_model_service.py:495` | L2 | Blender `--version` 探测（timeout=15，短探测） |
| `infra/workspace_maintenance.py:179` | L1 | 维护扫描 |

**C. `platform_tools.launch_background` 调用方（6 处／6 文件，无 Job Object、脱离父进程）**

| 文件:行 | 层 | 性质 |
| --- | --- | --- |
| `ui/asset_thumbs.py:757` | L4 | FFmpeg 后台工作进程 |
| `infra/log_maintenance.py:141` | L1 | 日志清理 |
| `domain/pet_test_service.py:100` | L2 | 宠物测试后台 |
| `infra/storage_maintenance.py:54` | L1 | 存储清理 |
| `infra/workspace_maintenance.py:384` | L1 | 工作区清理 |
| `ui/desktop_tray.py:411` | L4 | 托盘自重启 helper（`os._exit` 前拉起新实例） |

**D. `platform_tools.launch_text_process` 调用方（1 处，常驻进程）**

| 文件:行 | 层 | 性质 |
| --- | --- | --- |
| `domain/offline_asr_client.py:129` | L2 | **离线语音识别常驻子进程**（stdio JSON-Lines） |

**分类小结**：按 L1-Q4「长时与媒体子进程必须经监督器；短时探测继续走 `run_process`」口径——
- **长时/媒体类（I8/I9 收编对象）23 处**：A 中 aigc_lint、engine_probe、native_apps×3、previs_automation（6）；B 中除 stage_layout/white_model_service 两个 `--version` 短探测外的全部 10 处（core.command 媒体、offline_asr_setup、prompt_optimizer、skill_import_service、asset_thumbs×2、keyframe_evidence、native_asset_codec、pet_test_service、workspace_maintenance）；C 全部 6 处；D 1 处。
- **短时探测豁免 2 处**：`stage_layout.py:444`、`white_model_service.py:495`（`--version`，timeout=15）。
- **OS/系统操作 3 处**：`app_shortcut.py`×3（快捷方式与文件关联，非媒体非长时，I8/I9 可登记豁免或随平台边界处理）。

FL-06 起点按「不经监督器的启动点」严格口径记 **28 处／20 文件**；I8/I9 目标收编 23 处长时/媒体＋门禁补盲区，2 处短探测按 L1-Q4 保留 `run_process` 通道，3 处 OS 操作登记豁免。

### FL-09 — L2 及以上私有诊断日志写入点：**4 个文件／5 处**

`open('a'/'w')` 诊断与事件日志写入（L2+，不经 `app_logging`/`business_log`）：

| 文件:行 | 内容 | 分类 |
| --- | --- | --- |
| `image_agent_runner.py:26` | `<批次>/执行日志.txt` 追加执行消息 | 诊断日志 → I12 迁 `logging` 命名记录器 |
| `writing_api.py:157` | `logs/claude_empty_response.log` 追加空响应元数据 JSONL | 诊断日志 → I12 |
| `orchestrator/stage_parallel.py:477` | `log_write()` → `logs/<stage>.agent_logs.jsonl` 追加阶段代理日志 | 诊断日志 → I12 |
| `pet_agent.py:989` | `_journal()` → `工作流任务/宠物/事件日志.jsonl` 追加宠物事件 | **业务事件流** → I12 迁 `business_log`（非诊断日志） |

**排除项（非诊断日志）**：`orchestrator/qwen_adapter.py:57` 写 `process.qwen_input`（Qwen CLI stdin IPC 通道）；`qwen_adapter.py:135`、`orchestrator/workflow_engines.py:210-290` 的 `logfile`/`response_temp` 为**引擎 stdout/stderr 捕获与响应产物文件**（I0-5 区分要求）；`image_agent_runner.py` 同函数内 `执行状态.json` 为状态文件非日志。

FL-09 起点＝4 文件（立书估「约 6 个」偏高，实测 4）；I12 迁移清单即上表 4 项。

### FL-10 — L1 以外直接读密钥类环境变量：**0 处**

AST 扫描全部 `os.environ`/`os.getenv` 调用，第一参数为字符串常量或模块级常量且命中 `KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH`：**0 命中**（L1 `model_secrets`/`client_profiles` 等自身读取除外——口径为「L1 以外」）。密钥读取已全部收口 L1，I13 的工作是给 `model_secrets` 加门禁与元数据而非迁移读取点。

### FL-17 — 冷启动与首屏耗时：**实测 16/16 绿**

- 命令：`run_selftests.py -k desktop_startup_perf`（隐藏桌面；因跨树 GUI 令牌排队约 700 秒，实跑 11.7 秒）。
- 结果：**16 条用例全绿，0 红**（`test_desktop_startup_perf` 单文件）。
- 契约阈值（`tests/performance_contract.py`）：`SHOW_LOADED_PROJECT_SECONDS=1.0`、`CHAT_FIRST_TEXT_SECONDS=1.5`、`FIRST_EVENT_LOOP_SECONDS=2.6`、`FIRST_DAY_SELECTOR_SECONDS=1.0`、`AUTO_RESUME_TO_SCRIPT_SECONDS=1.0`、`STARTUP_RECURSIVE_SCAN_COUNT=0`、`STARTUP_FIRST_FRAME_MS=1500`、`LONG_LIST_SCROLL_MEDIAN_MS=150`、`MEMORY_DELTA_MB=30`。
- 本轮实测写入 `.git/startup-perf-history.jsonl`（round 3384 记录）：`empty_project=0.964s`、`first_day=0.497s`、`same_day=0.799s`——均显著低于契约界。
- **FL-17 起点基线**＝上述契约阈值＋本机实测分布；守护目标「不超过基线 110%」。

## I0-3　Q2 定稿清单（L1-H1 判据）

判据复核：L1-H1 三条——①import tkinter 或只服务界面→L4；②公开接口以阶段/剧本/资产/镜头等业务概念命名或持久化项目业务字段→L2；③其余留 L1。拆分型：技术存取留 L1、业务语义移 L2。

| 模块 | 判定 | 依据 | L1 内消费者 | 迁移批次 | 备注 |
| --- | --- | --- | --- | --- | --- |
| `ui_plugin_registry` | **→ L4** | 纯 UI 延迟加载登记表（23 插件跨 L2–L5，L4 为唯一可合法全量加载的层） | 无 | **I2** | ⚠ L3 消费者 `orchestrator/stage_models.py:251` `open_config()` 直接 `module('skill_panel').show()`——上移后成 L3→L4 越层，I2 须先把开面板动作改注入或上移该函数 |
| `ui_tokens` | **→ L4** | 纯 UI 常量（颜色/字体/间距），扇入 96 全部 L4 | 无 | **I4** | 无 L1 消费者，干净迁移 |
| `tk_timers` | **→ L4** | 窗口定时器（`repeat(widget,…)` 绑定 Tk 控件生命周期） | 无 | **I4** | ⚠ L3 消费者 `orchestrator/stage_flow.py:166` `tk_timers.repeat(widget,…)` 刷按钮文本——上移后成 L3→L4 越层，I4 须改注入或把该 UI 刷新上移 L4 |
| `app_icon` | **→ L4** | 应用图标资源与快捷方式（消费者 L4×1、L5×1） | 无 | **I4** | L5→L4 为合法下行 |
| `clipboard_lock` | **→ L4** | 剪贴板锁（UI 防串扰），消费者 L4×1 | 无 | **I4** | 干净迁移 |
| `continuity_ledger` | **→ L2** | 连贯性台账（阶段/镜头业务概念），F5 命中最高之一 | 无 | **I5a** | 消费者 L2×1、L3×4、L4×2，全部下行合法 |
| `asset_prompt_rules` | **→ L2** | 资产提示词规则（资产业务语义），F5 命中 54 | 无 | **I5a** | 消费者 L2×1、L3×2、L4×4 |
| `script_text_reader` | **→ L2** | 剧本文本读取（剧本业务语义），F5 命中 8 | **`integrations`(L1):19** | **I5a** | ⚠ 唯一 L1 消费者：`infra/integrations.py` `from infra.script_text_reader import script_text`——上移后成 L1→L2 越层，须先改注入；做不到则推迟并记入结果文件（L1-H1） |
| `h3_reference_adapter` | **→ L2** | H3 参考适配（资产/镜头业务），兼消 F2 反向依赖 `→shot_assets`(L2) | 无 | **I3a**（随 Q2 先行） | 消费者 L4×1；迁 L2 后其自身对 shot_assets 的依赖转为同层合法 |
| `stage_model_value` | **→ L2** | 阶段模型取值（阶段业务语义） | 无 | **I5a** | 消费者 L2×2、L3×4、L4×1 |
| `project_settings` | **拆分** | 项目设置：读写/锁/损坏处置=技术（留 L1），字段含义/默认值/业务校验=语义（→L2） | 无 | **I5b**（需 G-B） | 消费者 L2×3、L3×2、L4×12；`foundation-config-write-safety` 占用中 |
| `pet_state` | **拆分** | 阶段状态机：文件原子读写/恢复=技术（留 L1），13 阶段枚举/状态语义/ETA=业务（→L2） | 无 | **I5b** | 消费者 L3×3、L4×18；`阶段状态.json` 是三虎台账之一（见 I0-4） |

**Q2 汇总**：判出 L4 5 个（含 I2 的 ui_plugin_registry）、L2 5 个（h3 走 I3a、其余 4 个走 I5a）、拆分 2 个（I5b）；留 L1 不动的其余 47 个模块不在本表。**3 处越层风险**已标注：`stage_models→ui_plugin_registry`(L3→L4)、`stage_flow→tk_timers`(L3→L4)、`integrations→script_text_reader`(L1→L2)，对应轮次须先处理消费者再迁移本体。

## I0-4　三虎续跑台账盘点（I18 输入）

「三虎」＝桌面宠物无人值守自动链（`pet_bus.STAGES` 13 阶段序、`desktop_auto_state` 八条自动流程）。**持久化续跑台账 6 份**（`checkpoint_tree.CheckpointStore` 经查仅测试引用、无生产接线，不计；`desktop_auto_state.AutoState` 为纯内存态、不落盘，不计）：

| # | 文件 | 写入方 | 读取方 | 字段 | 状态语义 |
| --- | --- | --- | --- | --- | --- |
| 1 | `工作流任务/宠物/阶段状态.json`（项目内，`infra/pet_state.py` Machine） | `Machine.save()`→`agent.core.save` 原子写；`load()` 启动恢复 | `Machine.load()`、`snapshot()` 供进度/ETA | `updated_at`、`stages{stage:{state,reason,attempts,…}}`、`elapsed{}`、`units{}`、`run_units{}` | state∈pending/running/success/failed/retrying/skipped；损坏按「未知」重观测不猜 |
| 2 | `工作流任务/宠物/事件日志.jsonl`（项目内，`pet_agent._journal`） | `Pet._journal()` 追加 JSONL | 三虎进度面板/播报判重 | 事件 item（kind、时间、负载） | 只追加，无状态机 |
| 3 | `<项目>/workflows/资产续跑台账.json`（`domain/asset_resume.py`） | L3 注入发布器写（`record()`，直写被禁） | `attempts()`、`read()` 供重试决策；`clear()` 缺图补齐/手动关闭时整份删除 | 按资产编号：`attempts`、`last_try`、`next_try`（指数退避 `STEP*tries`）、`state`∈waiting/stopped | 到 limit 次标 stopped 等人工；读不出按空台账 |
| 4 | `<项目>/sanhu_project_status.json`（`orchestrator/skill_orchestrator.py`） | `before_step()`→`save_project_status` 原子写（写失败抛错、阻断付费动作）；`clear_checkpoint()` | `recover_from_checkpoint()`（版本/项目/摘要三重核对） | `current_stage`、`checkpoint{stage,step,step_name,completed_steps,version,at,project,skills,digest}`＋运行时状态 | checkpoint 版本不符/项目不符/摘要不符→需人工核实；旧版无 version 一律人工 |
| 5 | `程序/private/桌面续发/<path_key>.json`（`orchestrator/desktop_send_ledger.py`，本机不随项目走） | 发送成功后记录 | `plan()` 判 full/choice 续发 | 键 `<stage>\|<engine>\|<display_model>`；值 `skill_hash`、`materials{路径:sha256}`、`mode`、`sent_at`、`task_file` | 读不出按无记录（宁可多发不漏发） |
| 6 | `<项目>/workflows/资产批量记录.json`（`domain/asset_batch_state_service.py`） | `save_ledger()` 经 L3 注入 publish | `read_ledger()` 恢复批次；`record` 路径回读子记录 | job 条目含 `state`（record/submitting…）、`record`（子记录路径）等 | 子记录读回失败标 submitting 重试 |

**I18 映射要点**：6 份台账语义异构——#1 阶段状态机、#2 事件流、#3/#6 资产批次续跑、#4 步骤级检查点、#5 发送幂等指纹。通用作业库选型（I18）须覆盖「attempt/next_try 退避」「checkpoint+digest 核对」「skill_hash+materials 指纹」「state 子记录」四类字段语义；A8 假设（可映射不丢字段）逐字段对照在 I18 展开。

## I0-5　F12 诊断日志 vs 引擎产物文件区分（I12 迁移清单）

**迁移清单（4 项，全部为诊断/事件日志）**：

1. `image_agent_runner.py:26` — 批次 `执行日志.txt`（诊断）→ `logging` 命名记录器
2. `writing_api.py:157` — `logs/claude_empty_response.log`（诊断）→ `logging`
3. `orchestrator/stage_parallel.py:477` — `log_write()`→`logs/<stage>.agent_logs.jsonl`（诊断）→ `logging`
4. `pet_agent.py:989` — `_journal()`→`事件日志.jsonl`（**业务事件**）→ `business_log`

**不迁移（引擎产物/IPC，I0 区分要求）**：`qwen_adapter.py:57`（stdin IPC）、`qwen_adapter.py:135` 与 `workflow_engines.py:210-290`（引擎 stdout/stderr 捕获 `logfile` 与响应产物 `response_temp`）——属引擎工件边界，由 I9 进程监督器的「标准错误输出采集」统一接管，不走诊断日志通道。

## I0-6　门核对（G-A1–G-A5、G-B）

核对方式：文件存在性＋`git log master`＋`git diff --name-only master...codex/foundation-*`（工作树 HEAD `00ff7962`）。

| 门 | 判据 | 实测 | 结论 |
| --- | --- | --- | --- |
| G-A1 | L0 K6 弃用机制合入；`test_deprecation_ledger.py` 存在 | 文件**缺失**；`git log master --grep K6` 无命中 | **未满足** → 阻塞 I2、I4、I5（门面保留需弃用台账兜底） |
| G-A2 | K3–K5 `__all__`/契约清单/破坏性变更检测合入 | `test_contract_manifest.py`、`test_contract_api_diff.py` **均缺失** | **未满足** → 阻塞 I20 |
| G-A3 | K15 文档生成器＋K17 import-linter 合入 | `scripts/contract_docs.py`、`scripts/gen_importlinter.py` **均缺失** | **未满足** → 阻塞 I24 |
| G-A4 | K12 `contract/ports.py`＋`foundation/` 合入 | 两者**均缺失** | **未满足**（无硬阻塞：I3/I10 有注入退路，I25 收口） |
| G-A5 | K18 `app_dirs` 合入 | `contract/app_dirs.py`、`infra/app_dirs.py` **均缺失** | **未满足**（无硬阻塞：I14/I17 先落 `程序/data/`，I25 切换） |
| G-B | 地基分支对 4 个 L1 文件的改动已合入或放弃 | **4 支分支仍命中**：`foundation-hardening`(领先17)、`foundation-api-disk`(17)、`foundation-asset-disk`(17) 改 `model_router.py`+`storage_maintenance.py`+`token_saver.py`；`foundation-config-write-safety`(1) 改 `project_settings.py` | **未满足** → 阻塞 I5b、I13、I23 |

**排程影响**：I0→I1 不受门影响可立即执行；I2/I4/I5 因 G-A1 阻塞（门面/弃用台账缺失）；I3a（h3 上移）不依赖 G-A（无门面保留则无需弃用台账）；I5b/I13/I23 因 G-B 阻塞；I20/I24 因 G-A2/G-A3 阻塞。按 §0.0.2 纪律：门未满足的轮次标注「阻塞于门 G-x」，转做其他可做轮次，不空等、不代做他人车道。

## 与立书值不一致项（已同步修订本任务书）

1. **F1**：补注 L2 登记 87 vs 扫描文件 81 的口径差异（6 个登记名无扫描实体）。
2. **F3**：补注 23 个插件的实际层别构成（L2×1、L3×5、L4×16、L5×1），非「全是 L4」。
3. **F5**：注明立书命中数为窄口径，本书改宽口径词表重测、模块排序一致、绝对值不可比。
4. **F7／FL-04**：「约 140」修订为 **263 处／37 模块**（立书值系头部 12 模块之和）。
5. **F8**：「0 处」修订为 **1 处**（`task_center_ui.py:15`→`diagnostic_capture._state`）。
6. **F11**：L4 线程文件「约 17」修订为 **18**。
7. **F19**：扇入 `core` 105→108、`file_cache` 71→72、`storage_maintenance` 36→37。
8. **F20**：补列 `codex/foundation-asset-disk`（领先 17，同样命中 3 个 L1 文件）。
9. **FL-09**：立书估「约 6 个文件」修订为 **4 个文件**（另 1 处为引擎 IPC、其余为产物文件，已区分）。

## 三个基线

- **默认冒烟**：`python -B smoke_test.py` → **9/9 绿**（EXIT=0）。
- **架构门禁**：`python -B smoke_test.py --architecture` → **532 条用例，1 失败＋1 错误**；两处均为工作树缺本机文件的环境性红（`维护记录/基准历史.json` gitignore、本机 skills gitlink 内容缺失）。补齐后 `run_selftests.py -k test_agents_md test_skill_reference_injection` 定向复跑 **24/24 绿**。净结论：代码面 532 条全绿，环境补齐项已记录。
- **全量回归**：未触发（零 `.py` 改动）；最近权威凭据 `.git/full-safe-history.jsonl` @ `dc3b3bb8`（R3382）ok=false、4 个红文件（`test_shared_adapter_infrastructure`、`test_ui_edges_guards`、`test_pet_ui`、`test_idea_chat`），非本车道引入。
- **启动性能**（FL-17）：`run_selftests.py -k desktop_startup_perf` → **16/16 绿**（实跑 11.7s，GUI 排队约 700s）；实测 empty_project 0.964s／first_day 0.497s／same_day 0.799s，全部低于契约界。

## 提交

- 分支 `codex/l1-enterprise`，轮次号 **R3386**；变更集＝本结果文件＋任务书 §0.1/§1.3 数字与坐标修订（I0 允许范围，不改决策）。

## 下一步

- **I1**（层间关系规范 LR-01~10＋`层间合规清单.json`＋`test_layer_relations` 骨架）：前置无、无门依赖，I0 完成后即可领号执行。
- 门阻塞预告：I2/I4/I5 待 G-A1；I5b/I13/I23 待 G-B；I20 待 G-A2；I24 待 G-A3。解锁前按 §0.0.2 做不依赖门的轮次（I1、I3a、I6–I12、I14–I19 中无门项）。
- 接力要点：工作树 `D:\漫剧制作助手\.agents\worktrees\devin-l1-enterprise`；解释器用主工作区 `运行环境\Python\python.exe`；本机文件补齐（`基准历史.json`＋skills gitlink 内容）已做、勿提交；主工作区有他道暂存文件，本车道只在本工作树 `dev.py commit`。

[TASK_CONTINUE]
