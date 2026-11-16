# R2952 结果：语音离线化·轮4——自定义词典/热词＋AI 文本优化＋MCP 语音转文字
<!-- round-evidence: {"commit_base": "9801cdd3", "credential_hits": 0, "evidence_sha256": "c76fb88d3d4fdc30", "exit": 0, "failed": 0, "passed": 107, "round": 2952, "tests": "run_selftests.py -k voice_dict voice_ai_optimize voice_mcp shared_input_voice model_manager_actions speech_api offline_asr_engine offline_asr_client"} -->

## 三问

1. **轮次类型**：功能轮（任务书《语音输入离线化与VocoType集成》轮 4：词典/AI/MCP 三件套，不改录音与识别主链路）。
2. **测试跑了吗、三个基线过了吗**：跑了。新增 `tests/test_voice_dict.py` 12 条、`tests/test_voice_ai_optimize.py` 8 条、`tests/test_voice_mcp.py` 9 条；`test_offline_asr_engine` 37 条、`test_speech_api` 4 条、`test_offline_asr_client` 19 条、`test_shared_input_voice` 9 条（含 AI 优化生命周期 4 条）、`test_model_manager_actions` 9 条；`--affected` 15 文件 197 条全绿；默认冒烟 8/8；架构门禁 470 条仅余 `test_round_number_continuous` 已知分支态红（状态页只能由 master 提交，同 R2943 口径）。
3. **欠账少了吗**：是。词典（热词/同音替换/AI 开关）从「无」变为「`data/语音词典.json`＋设置弹窗可编辑＋会话注入」；AI 优化走模型池＋`writing_api` 计量、不引 VocoType 客户端；MCP `voice_transcribe` 零第三方依赖暴露给 agent 客户端；顺带修复轮 2 遗留的 `speech_api.read_settings` 重复定义缺陷（旧版遮蔽新版，`offline` 节合并失效）。

## 本轮交付（任务书轮 4 验收对照）

| 验收项 | 落地 |
|---|---|
| 自定义词典（热词/替换） | `data/语音词典.json`：`hotword`（逗号/分号/顿号/空白切分、去重保序、≤200 条单条 ≤100 字）、`replace`（`{错词:正词}` ≤500 条）、`ai`（enabled/template/prompt）。`speech_api.normalize_dictionary/read_dictionary/save_dictionary` 校验读写（发布器注入，坏节回默认不拖垮好节）；`apply_replacements` 用正则交替按键长降序**一次扫描**——长键优先且已替换文本不被短键二次改写（`子进程` 不被 `进程` 改成 `线程`）；`hotword_text` 拼空格分隔串。 |
| 热词下发引擎 | 协议早已端到端（`offline.hotword` → `start.hotword` → `PcmSession.hotword`）；本轮补引擎侧：`Segmenter._transcribe` 把会话热词传给 `asr_fn`；`FunAsrBackend.asr` 仅当模型带 `proc_hotword` 能力位时传 `hotwords=`，模型不收该入参（TypeError）退回无热词识别并在 stderr 留诊断——普通 Paraformer 不支持热词时确定性纠错由替换表承担。`create_session` 把词典热词与 `offline.hotword` 合并下发。 |
| 替换表后处理 | `create_session` 在替换表非空时返回 `_DictionarySession` 包装（独立 daemon 线程转发事件，`final` 先过 `apply_replacements`，partial/log/closed 原样）；离线与云端两后端同口径；空表零包装零开销。 |
| AI 优化文本 | 新 L2 `domain/voice_ai.py`（顶层 `voice_ai.py` 门面）：fix/polish/translate/custom 四模板拼 system＋user 消息，`clean_result` 去空白/代码围栏，`optimize_text` 走**注入式 `chat`**（签名同 `WritingRequestAdapter.chat`）返回 `{ok,text,reason}`，任何失败保留原文给中文原因。`desktop_voice_input` 会话正常关闭后：词典 `ai.enabled` 且项目已注入 → 用会话首尾 mark（`voice_ai_start`/`voice_ai_end`）圈出听写区域，区域文本与累计 final 不一致（用户中途手改）跳过；一致则 `writing_api._writing_adapter`（模型池＋RPM＋计量）异步优化，`BackgroundTaskLifecycle` 代次 ticket＋120ms 轮询，回写前**再次复核区域未变**才替换——迟到/ stale 结果、AI 报错、空返回都不碰已确认文本；`SharedStageInput`/`desktop_writing_page` 均把 project 传入。 |
| MCP 语音转文字 | 新 `agent/voice_mcp_server.py`：零第三方依赖手写 JSON-RPC 2.0 over stdio（`initialize`/`ping`/`tools/list`/`tools/call`，通知不回包、坏 JSON 回 `id:null` 错误）。`voice_transcribe` 入参 `audio_path`（16-bit PCM 单声道 WAV）或 `pcm_base64`+`sample_rate` 二选一，手写 RIFF chunk 解析（**产品运行时是裁剪版 Python，无 `wave`/`audioop` 标准库**），线性重采样到 16 kHz，PCM 分块喂 `speech_api.create_session`（backend 固定 offline），收齐 final 拼接返回；`hotword` 参数覆盖词典热词，识别同样过替换表；超时按音频时长 5×+60s 封顶 900s。 |
| 设置界面 | `speech_settings_ui` 同窗加「语音词典与 AI 优化（可选）」区：热词输入、替换词表多行编辑（每行 `错词=正词`，`#` 注释）、AI 开关/模板/自定义提示词、MCP 用法说明；保存先 `normalize_dictionary` 校验再 `save_settings`+`save_dictionary` 双写，任一失败中文提示且不动文件；「恢复默认」两边同复位。 |

## 测试与契约变更（如实，§2.4）

- 新增三个测试文件按任务书点名：`test_voice_dict.py`（规范化/读写/替换/热词/create_session 注入与包装）、`test_voice_ai_optimize.py`（模板/清洗/注入 chat 全路径）、`test_voice_mcp.py`（WAV/PCM/重采样/协议/stdio 循环）。
- `test_offline_asr_engine.py`：fake `asr` 签名同步 `hotword` 关键字（断言不变）；新增热词透传、能力位转发、TypeError 回退、stderr 诊断 4 条。
- `test_shared_input_voice.py`：新增 AI 优化生命周期 4 条（成功回写/关闭跳过/手改区域拒绝覆盖/失败保留原文）。
- `test_model_manager_actions.py`：保存用例补 `save_dictionary` mock（契约为「设置+词典同窗保存」），断言补 `save_dict.assert_called_once()`；其余断言原样。
- **顺带修复轮 2 回归缺陷**：`domain/speech_api.py` 存在两个 `read_settings` 定义，旧版（第 86 行）遮蔽合并 `offline` 节的新版——用户离线设置实际不生效；已删旧版，`offline` 逐键合并与 `DEFAULTS` 深拷贝语义由既有测试锚定。

## 架构门禁适配（如实）

- `tests/architecture/_layers.py`：`voice_ai` 登记 L2；`agent/voice_mcp_server.py` 属 agent/ 子包（不在分层扫描面），无需登记。
- `维护记录/架构统一基数.json`：`offline_asr_client`、`voice_ai` 补登 `第一项.exempt_items`（均不发布项目数据、不走 ServiceResult，与 `speech_api` 同口径），`exempt_count` 46→48。
- `tests/test_shared_input_voice.py`：8 处内联 skip 理由改引 `skip_reasons.PLATFORM_WINDOWS_ONLY`（轮 3 引入的台账欠账，本轮被 skip 卫生门禁照出）；`维护记录/skip台账.json` 按采集器实测补 16 行（装饰器 skipIf 双记 ordinal 1/2）。
- `speech_settings_ui.py`：替换词表 `TextArea height=4` 改 `TEXT_ROWS['sm']`（数字布局棘轮）。
- `AGENTS.md`：超 16 KB 预算 379 字节，按「细则进 runbook」口径压缩 §0/§2.4/§2.5/§4/§5/§6/§8 冗余表述至 15966 字节，语义不变；AGENTS.md §2.2 权威源表词典条目按任务书归**轮 5**（当前仅剩 34 字节余量，新增条目须先继续瘦身）。
- `architecture.md`：目录树 `agent/` 行补 MCP 服务；L2 表模块列加 `voice_ai`，`speech_api` 职责段补词典注入与 `voice_ai` 说明。
- `PROJECT_MAP.md`「离线语音识别」行补 `domain/voice_ai`、`agent/voice_mcp_server`、词典文件与 MCP 工具。
- `维护记录/覆盖率基线.json` 重测刷新（**513 模块／70 覆盖**，+3＝`voice_ai.py` 门面、`domain/voice_ai.py`、`agent/voice_mcp_server.py`）；`runbook.md` §11 数字同步（513/70/443）。
- REQ-S01-71 文档更新与 `AGENTS.md` §2.2 权威源表新增按任务书归**轮 5**，本轮未动。

## 验证记录

- `python -B run_selftests.py -k shared_input_voice model_manager voice_dict voice_ai_optimize voice_mcp`：47 条全绿（含 GUI 共享输入 9 条）。
- `python -B run_selftests.py -k offline_asr_engine voice_mcp`：46 条全绿（引擎 37＋MCP 9）。
- `python -B smoke_test.py --affected speech_api voice_ai offline_asr_client offline_asr_server desktop_voice_input desktop_shared_input desktop_writing_page speech_settings_ui voice_mcp_server`：9/9 门禁、15 文件 **197 条**全绿。
- `python -B smoke_test.py`：8/8 绿。
- `python -B smoke_test.py --architecture`：470 条，仅 `test_round_number_continuous` 红——功能分支已知分支态（`project_status.md` 只能由 master 提交，状态页 2939 落后结果文件 2952→应为 2953），与 R2943 同口径如实记录；skip 卫生/服务契约登记/数字布局/文档预算四项修复后定向复测 24 条全绿。
- 架构定向复测：`test_skip_hygiene`/`test_service_return_contract`/`test_token_boundary`/`test_agent_doc_budget` 24 条全绿。
- 未实测：真实麦克风＋真实 FunASR＋真实 MCP 客户端端到端（属轮 5 整机验收；协议/会话/渲染/优化路径已由 fake 全覆盖）。

## 下一步（轮 5）

设置/模型/运行时管理收尾、REQ-S01-71 与 AGENTS.md §2.2 权威源表同步、打包安装更新文档、最终全量回归。
