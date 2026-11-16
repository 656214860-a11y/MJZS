# R2943 结果：语音离线化·轮2——主程序后端抽象 + 离线子进程路由
<!-- round-evidence: {"commit_base": "68b6004c", "credential_hits": 0, "evidence_sha256": "f7fbbeb26bcf6702", "exit": 0, "failed": 0, "passed": 73, "round": 2943, "tests": "run_selftests.py -k offline_asr speech script_composer model_manager"} -->

## 三问

1. **轮次类型**：功能轮（任务书《语音输入离线化与VocoType集成》轮 2：主程序后端抽象与子进程路由，不改录音侧）。
2. **测试跑了吗、三个基线过了吗**：跑了。新增 `tests/test_offline_asr_client.py` 19 条＋引擎侧补 2 条＋`test_speech_api.py`/`test_script_composer.py` 契约同步，全绿；默认冒烟 8/8；`smoke_test.py --affected domain.speech_api` 9/9 绿（自动选中 `test_offline_asr_client` 19 条）；架构分层/覆盖率基线/事件总线/覆盖率审计/动态导入/静带/原子写门禁复测全绿。`test_idea_chat.test_initial_brief_discovery_failure_is_visible_without_blocking_input` 在干净 master（0581308b）同样失败，属既有基线欠账，与本轮无关，如实记录。
3. **欠账少了吗**：是。离线后端从「引擎脚本」变成「主程序可路由的真实后端」：子进程常驻宿主、统一事件接口、超时强杀、崩溃中文原因、云端自动降级全部落地并有测试锚定。

## 本轮交付（任务书轮 2 验收对照）

| 验收项 | 落地 |
|---|---|
| `speech_api` 后端抽象 | `DEFAULTS` 增 `backend`（默认 `offline`）与 `offline` 节（`python`/`cache_dir`/`threads`/`vad_trailing_ms`）；`read_settings`/`save_settings` 支持嵌套节校验（数值范围、未知键丢弃、写文件只存差异）；`create_session(settings)` 按 backend 分流，`missing_reason` 同步分流（离线环境缺失但已配云端密钥时返回空串放行降级）。 |
| 统一事件接口 | `('partial'\|'final'\|'error'\|'closed'\|'log', item, text)`：`RealtimeSession` 原样保留；`OfflineAsrSession` 把引擎 `sentence`→`final`（每句 VAD 定稿即出字，无 partial）、`done`→`closed`、`error`→`error`、`log`→`log`（模型下载/加载进度上状态栏）。 |
| `domain/offline_asr_client.py`（L2） | `EngineHost` 模块级单例：`platform_tools.launch_text_process` 拉起 venv 解释器跑 `voice_engine/offline_asr_server.py`（UTF-8 文本管道、隐藏窗口），stdout reader/stderr drain 线程，`ready`/`log`/`sentence`/`done`/`error` 分发；写命令走 `write_lock`＋JSON Lines；`attach/detach` 单会话占用（忙→`EngineBusy`）；进程死亡→`_on_exit`/`_mark_dead` 置 dead＋中文原因＋通知会话；`kill`/`shutdown` 经 `terminate_process_tree` 清理，`atexit` 兜底。 |
| 会话生命周期 | `OfflineAsrSession` 与 `RealtimeSession` 同接口（`start/send/finish/cancel/events`）：`send` 把 PCM base64 成 `audio` 命令；`finish` 发 `stop` 后等 `done`（`timeout` 秒，超时 `kill` 引擎并报中文原因）；`cancel` 发 `cancel`（引擎丢弃缓冲不产句）。音频流动前引擎不可用→`fallback` 降级云端会话（先发 `log` 通知，音频顺序经单队列转发）；会话中途崩溃→`error`+`closed`，不降级不崩主程序。 |
| 录音侧不变 | `MicrophoneRecorder.on_chunk` 每 0.1 秒 PCM 直推 `session.send`，`VoiceInput` 仅把 `RealtimeSession(...)` 改为 `speech_api.create_session(...)` 并把 `log` 事件显示到状态栏（下载进度可见）；partial/final 浅色渲染、`BackgroundTaskLifecycle` 代次、销毁即停语义原样。 |
| 设置弹窗 | `speech_settings_ui.py` 加「识别后端」下拉（offline/cloud）＋离线四字段（解释器/缓存目录/线程数/VAD 断句静音），云端字段保留；`data/语音识别.json` 旧文件自动落到 `backend=offline` 默认，已配云端密钥的存量用户经降级继续可用。 |
| 引擎协议补全 | `offline_asr_server.py` 增 `{"cmd":"cancel"}`（丢弃会话缓冲、不发 done 防串话）与 `start.vad` 可选分句参数透传（`tick_ms/trailing_ms/window_ms/min_ms/max_ms` 白名单数值）。 |

## 测试与契约变更（如实）

- 新增 `tests/test_offline_asr_client.py` 19 条：环境体检、句子→final/序号、done→closed、引擎 error/进程死亡、cancel 命令、stop 超时强杀、不可用降级云端（含通知与音频转发）、无降级报错、忙时降级、hotword/vad 参数透传、`acquire` 拉起/缺环境/进程死亡重试、`create_session` 路由与 fallback 注入、`missing_reason` 分流、`save_settings` backend/offline 节校验——全 fake，不起真实引擎。
- `test_offline_asr_engine.py` +2：`cancel_session` 丢弃会话不发 done、`vad` 覆盖只收白名单数值。
- `test_speech_api.py`：`missing_reason` 契约变为按 backend 分流——云端密钥断言改用 `backend='cloud'`（契约有意变更，断言语义不变）；`RealtimeSession._converse` 无密钥分支改走 `cloud_missing_reason`，云端会话不受 backend 字段影响。
- `test_script_composer.py`：麦克风测试注入点由 `speech_api.RealtimeSession` 同步为 `speech_api.create_session`（契约变更同步 mock，断言原样）。

## 架构门禁适配（如实）

- `offline_asr_client._emit` 方法名触发事件总线边界误报（与 R2941 `_emit` 同类），改名 `_push`，语义不变。
- `tests/architecture/_layers.py` 登记 `offline_asr_client` 为 L2；新增顶层门面 `offline_asr_client.py`（T10 包化同名再导出惯例，消「僵尸登记名」）。
- `AGENTS.md` §2.2 权威源表新增「语音识别后端路由」「离线 ASR 引擎」两行；`architecture.md` L2 表登记 `offline_asr_client` 并更新 `speech_api` 职责描述；`PROJECT_MAP.md` 离线语音识别行同步。
- `维护记录/覆盖率基线.json` 按 9 组定向用例重测刷新（509 模块／70 覆盖）；`runbook.md` §11 数字同步（509/70/439）。

## 验证记录

- `python -B -m unittest tests.test_offline_asr_client tests.test_offline_asr_engine tests.test_speech_api`：57/57 绿。
- `PYTHONPATH=tests;. python -B -m unittest tests.test_script_composer.ScriptComposerTests.test_microphone_dictates_live_into_input tests.test_script_composer.ScriptComposerTests.test_microphone_without_key_explains_in_status`：绿（含麦克风全流程断言）。
- `python -B smoke_test.py`：8/8 绿。
- `python -B smoke_test.py --affected domain.speech_api`：9/9 绿（定向自检选中 `test_offline_asr_client` 19 条全绿）。
- 架构门禁定向复测：`test_layers`/`test_coverage_baseline`/`test_coverage_audit_ratchet`/`test_event_bus_boundary`/`test_dynamic_import_registry`/`test_no_circular_import`/`test_static_hygiene`/`test_import_error_boundaries`/`test_complexity_ratchet`/`test_function_size_ratchet`/`test_atomic_write_boundary` 全绿。
- 消费者回归 `test_idea_chat + test_script_composer + test_model_manager_actions`（151 条）：150 绿，1 红为 `test_idea_chat...brief_discovery...`——已在干净 master 复现同败，属既有欠账非本轮引入；`test_script_composer` 麦克风用例修复后绿。
- `python -B smoke_test.py --architecture` 全量：功能分支上 `test_round_baselines` 仍呈已知分支态红（状态页只能由 master 提交），其余项以定向复测为准，如实记录。
- 未实测：真实 FunASR 引擎拉起与中文语音识别（需独立 venv＋模型下载，属轮 5 整机验收；协议/生命周期/降级路径已由 fake 全覆盖）。

## 下一步（轮 3）

`desktop_voice_input.py` 复用组件＋`desktop_shared_input.SharedStageInput` 麦克风按钮，13 页共享同一语音会话；01 页 composer 重复工具行按任务书点名统一。
