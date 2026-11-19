# R3519 — A9-8 工具消费与独立 ASR 分发闭包
<!-- round-evidence: {"commit_base": "3388dd36", "credential_hits": 0, "evidence_sha256": "b676caf674d955dd", "exit": 0, "failed": 0, "passed": 463, "round": 3519, "tests": "run_selftests.py -k test_layers test_service_return_contract test_no_circular_import test_gate_selfaudit test_rule_guard_map test_checkpoint_tree test_branch_tree_ui test_asset_hovercard test_citation test_code_highlight test_diff_view test_hitl_ui test_media_render test_video_audio_card test_multimodal_upload test_param_panel test_background_task test_edit_habits test_direct_chat_metering test_artifact_schema_wiring test_file_index test_file_naming test_global_library_service test_migrate_legacy_layout test_dynamic_import_registry test_stage_command_contract test_offline_asr_client test_offline_asr_engine test_offline_asr_setup test_distribution_build test_distribution_selfcheck test_batch_frames test_codex_paste_diagnostics test_codex_task_lock test_keyframe_comfy test_dispatch test_desktop_send_ledger test_desktop_idea_chat_desktop_paste test_pet_test_service"} -->

## 三问

1. 类型为 AGENTS §3.3 结构治理执行，来源《六层架构收口与企业级演进任务书》A9、R3411 G/I/J、R3416 F05/J 与 R3506。三模块为 `_scan.py`、`test_dynamic_import_registry.py`、`architecture.md`，另有结果及验证证据。
2. 已完成先红后绿验证。完整架构前置 587/590，原有 2 个失败和 1 个错误。后置、冒烟和标准定向凭据见验证段。
3. 列出了分发及层级缺口，历史全量欠账保持原状。规则、守卫和分发证据在同一条消费链核对。

## 领号与边界

- 从干净的 A9-7 基线 `4b527bfda72077f5de93469a37e6496d300f3894` 建立 `codex/architecture-a9-tools`。首次 `dev.py claim --branch` 在 detached HEAD 被拒且未领号，建立分支后通过项目随附解释器运行 `dev.py claim` 得 R3519。中央队列无匹配项。
- 开工 scope 扫描 100 个分支，40 个重叠，`errors={}`。重叠包含已延续的 A9 扫描器和架构说明等路径，重叠分支未发现本批等价守卫。仅在本工作树进行操作。
- 实现保留原层级登记、传统静态/动态导入图及既有豁免。31 个既有扫描函数 AST 逐个一致，仍精确拒绝 15 项模块身份，阶段注册严格入口仍有 29 条拒绝。原规则生成索引继续校验。

## 逐项裁定

| 组件 | 角色、消费入口与发布证据 |
| --- | --- |
| `codex_tasks` | 应用运行模块、候选 L1。调度使用 `task_lock`，工作流和创意对话使用 `prepare_task`，发送选择使用 `task_file_reference`。真实计划保留 Python 文件。 |
| `codex_paste` | 应用运行模块、候选 L1。创意对话及发送选择导入 `paste_existing` / `paste_attachment`。脚本参数由现有 mock 行为测试覆盖，构建计划同时保留 `codex_paste.py` 和 `codex_paste.ps1`。 |
| `console_submit` | 应用运行模块、候选 L1。工作流两处调用 `send`。它用随附解释器重启自身，脚本入口调用 `deliver`。同一文件由构建计划保留。 |
| `batch_frames_tool` | 应用运行模块、候选 L2。出图执行、云资产/ComfyUI 基础设施、三处 UI 文件共八个生产导入。构建计划保留真实模块、`config.json`、独立首帧启动器及随附说明和示例。 |
| `blender_previs_template` | 生成模板。预演批次提示引用同名文件，Blender 执行其 `build` 与脚本入口。构建计划保留该模板，Blender 提供 `bpy` 和 `mathutils`。这是第五个旧登记项。 |
| `voice_engine` | 独立进程。`speech_api.create_session` 路由到 `offline_asr_client`，经平台文本子进程入口启动识别服务。`offline_asr_setup` 经随附解释器执行 bootstrap，再用 venv 解释器 `-m voice_engine.download_models`。构建计划含这三个入口、`__init__.py`、`funasr_config.py` 和独立 `requirements.txt`。 |

`TOOLS` 登记 5 项，旧顶层层级扫描命中 4 项。旧扫描的差集为包 `batch_frames_tool`。新守卫从生产导入解析到精确文件，覆盖无 `__init__.py` 的 namespace 包。开发自检器和分发构建器属于开发工具，实际计划排除构建器自身。

## 负例与正例

- 先以合成包树执行旧扫描口径，4 项断言均红。关键断言分别为 `unclassified-import not found in set()`、`('missing-file', 'ghost.py', 'ghost') not found in ()`、`('process-import', 'worker/settings.py:2', 'app') not found in ()`、`('release-missing', 'worker/settings.py', 'worker') not found in ()`。
- 正例含命名空间生产导入、独立入口和相对导入的传递闭包。负例还覆盖缺失入口符号、未声明第三方依赖、进程导入应用代码、缺失独立模块、变量动态导入、运行工具越层、生产消费者消失。分发负例由真实构建计划将成员移出保留集触发。
- 实际源审计见 [R3519-tools-audit.json](evidence/R3519-tools-audit.json)。其中记录具体消费者、入口、进程依赖边、真实分发命中与探针。新严格入口遇任何诊断均失败。默认回归逐项核对现有拒绝，有新增诊断就失败。

## 分发与依赖缺口

- **A10 批处理分层**。L2 候选批处理模块使用 `agent.shot_assets`、`asset_context`、`keyframe_batch`、`keyframe_evidence`，形成 `infra/cloud_assets.py:70`、`infra/comfy_service.py:133/146` 三条 L1→L2 边。处理实际职责和消费位置后再接入正式层级登记。
- **A10 ASR 协议**。识别命令为 `start/audio/stop/cancel/shutdown`，事件为 `ready/log/sentence/done/error`。安装与模型下载报告 `progress/done/error`。识别进程先从 I/O 读取整行，再 strip 后检查 `len(line)`。客户端 stdout 同样按行读取，stdio 帧暂无协商版本。取消当前会话、停止超时终止及进程退出由既有行为测试覆盖。
- **A15 随包数据**。`程序/*.py` 选中八个自检文件，`程序/data/` 选中 `voice_asr_venv/pyvenv.cfg` 与 `voice_models/model.bin` 两个模拟生成文件。本次使用合成路径探测清单。发布层需排除生成目录并保留目标机上的升级数据。
- **A15 正式版自检入口**。三虎显式测试意图从 `ui/pet_ui_stages.py:505/604` 经阶段注册器和 `stage_execution_service.start_pet_test_check` 到 `domain/pet_test_service.py:97`，另有同步启动位点 :78。两处启动 `run_selftests.py --incremental`。分发保留运行器且排除 `程序/tests/**`，清单改动应同批核验正式版入口的处置。
- **A15 ASR 发布校验**。`voice_engine/**` 按至少一个匹配检查必需模式。向真实构建器及其 `verify` 提供缺 `funasr_config.py` 的临时源和原通配模式，构建摘要自洽，`verify.ok=True`。当前跟踪源码六文件均在实际构建计划里，发布副本仍需精确文件校验。独立依赖声明已有版本范围和直接固定版本，bootstrap 使用 `pip install -r`。传递锁和哈希仍需在干净的受支持解释器环境中验证。

## 验证与提交

- 完整架构前置 587/590（382.610 秒），最终 597/600（407.147 秒）。前后均为 2 失败、1 错误。相同测试 ID 对应缺少 `维护记录/基准历史.json`、状态页编号未同步和缺少 `short-drama-director/references/screenplay-gate-engine.md`。
- 默认冒烟 9/9（8 项业务检查和 1 项隐藏探针）。ASR 协议、启动和安装链及分发构建定向 85/85。最终新增负例/正例和生产审计 10/10。切入三虎测试意图之前的架构定向 77/77，规则生成索引同步。架构文档文字定稿后核对三项一致性检查均通过。
- 五个预定文件的新增行凭据形态扫描（含专项审计证据）零命中，47 个审计源文件内容哈希一致。
- 安全全量未运行。上次绿回执为 R3293，其后源码轮次 23、门禁线 8。最近后台回执 HEAD `93e3ef6` 退出 1。
- 标准定向沿用 R3506 的全部关键词并追加工具消费者、ASR、构建和三虎自检的定向关键词。为缺少运行环境目录的工作树，仅在该测试进程 PATH 注入现有随附 FFmpeg 9.0.1。
- 标准提交入口按 `R3519-FAIL` 提交检查点 `3388dd36`，`scripts/commit_round.py:40` 的标题匹配跳过了自动定向。沿用项目 `round_evidence.py` 生成真实凭据并补入同一提交。证据的测试基线是结果及凭据补记前的检查点，受测源码相同。最终哈希由 `git log -1 --format=%H -- 程序/tasks_round/tasks_round_3519_result.md` 定位。
- 状态页仅 master 可提交，本树状态页 3409 与新增结果 3519 不连续，留给合入轮同步。

## A9 剩余

仍需环扫描子批。先接收 L1 五模块环拆分的证据，再把环守卫迁到增强包解析。批处理和 ASR 的生产与发行修复分别移交 A10/A15。
