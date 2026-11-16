# R2958 结果：语音离线化·轮5——其余输入框接入＋文档/契约/门禁收尾
<!-- round-evidence: {"commit_base": "14356e62", "credential_hits": 0, "evidence_sha256": "34756acdee23a851", "exit": 0, "failed": 0, "passed": 233, "round": 2958, "tests": "run_selftests.py -k dialog_voice_input req_s09_anchors shared_input_voice white_model previs dynamic_import_registry no_circular_import"} -->

## 三问

1. **轮次类型**：功能轮（任务书《语音输入离线化与VocoType集成》轮 5：其余输入框按需接入＋文档同步＋门禁收尾）。
2. **测试跑了吗、三个基线过了吗**：跑了。新增 `tests/test_dialog_voice_input.py` 3 条；`--affected white_model workflow_settings_dialog desktop_voice_input desktop_shared_input` 9 项门禁全绿（含 `test_req_s09_anchors` 19、`test_dialog_voice_input` 3、`test_shared_input_voice` 9 等）；定向 `-k` 复测 382 条全绿；默认冒烟 8/8；`--architecture` 470 条仅余 `test_round_number_continuous` 已知分支态红（状态页只能由 master 提交，同 R2943/R2952 口径），环棘轮新增红已修复并定向复测全绿。
3. **欠账少了吗**：是。REQ-S01-71 文字与实现对齐（离线默认/VAD 逐句/后端切换/词典/AI/MCP/13 页与对话框挂点）；AGENTS.md §2.2 权威源表补齐第三条「语音词典与 AI 优化」；白模备注与调用设置补充要求两个内容型输入框接入听写；其余候选输入框按任务书「无明确清单记录待定不臆造」口径登记；升级保留边界经 gitignore 实测核验。

## 本轮交付（任务书轮 5 验收对照）

| 验收项 | 落地 |
|---|---|
| 其余输入框按需接入 | 白模预演「动作与机位备注」（`white_model.open_previs`）与阶段「调用设置」的「补充制作要求（可选）」（`workflow_settings_dialog.show_settings`）各挂一颗麦克风，复用 `desktop_voice_input.VoiceInput`（Windows 限定、非 Windows 不显示），状态分别写 `desktop.status` 与对话框 `feedback`，词典 AI 优化经 `project` 上下文生效。两处均经 `ui_plugin_registry.module('desktop_voice_input')` 延迟加载（规则 18），并在 `UI_PLUGINS` 登记。 |
| 无清单输入框记待定 | 逐一排查非共享输入控件：资产改名（`ask_string` 单行框＋`cell_hover.edit_name` 行内编辑）、`ui/pet_cloud.py` 回复框、`script_find_bar` 查找栏均为短文本/检索工具字段，听写收益边际且任务书无明确清单——**登记为待定，不臆造接入**。 |
| REQ-S01-71 文档同步 | `docs/stages/S01_剧本准备.md` REQ-S01-71 改写为实现口径：默认离线 FunASR 子进程 VAD 逐句、云端可切回、13 页共享同一听写实例、白模备注/补充要求同款按钮、词典（热词/替换表/AI 模板）存 `data/语音词典.json`、定稿先替换表纠错、AI 优化仅在区域未手改时回写、MCP `voice_transcribe` 说明、离线模型未装/下载失败等错误路径；REQ→测试锚定行补 6 个新测试文件。DES-S01-71 末尾追加 R2941–R2957 架构段（后端分流/词典注入/AI 生命周期/MCP 协议/设置双写）。 |
| AGENTS.md §2.2 权威源 | 三行齐备：`speech_api.create_session()` 后端路由、`voice_engine/offline_asr_server.py` 离线引擎、`data/语音词典.json`＋`voice_ai` 词典与 AI 优化（本轮新增第三行）。同步为守 16 KB 预算做了等量压缩，实测 15,997 字节。 |
| 分层表/模块地图 | `architecture.md` §3 L2 表含 `speech_api`/`offline_asr_client`/`voice_ai`，agent/ 行含 `voice_mcp_server`（轮 4 已登记）；`PROJECT_MAP.md`「离线语音识别」行覆盖引擎/客户端/词典/AI/MCP/设置界面全链路；`runbook.md` 覆盖基线 513 模块已同步（轮 4）。本轮新改动未新增生产模块，无需再登记。 |
| 升级安装保留 | `程序/data/` 为运行数据边界：`data/语音识别.json`、`data/语音词典.json`、`data/voice_models/`、`data/voice_asr_venv/` 经 `git check-ignore` 实测全部命中忽略规则——升级只覆盖程序文件，上述语音设置/词典/模型缓存/独立运行时全部保留；`test_gitignore_covers_runtime_and_secret_boundaries` 架构门禁同口径守卫。 |

## 环棘轮修复（本轮唯一返工）

首轮 `--architecture` 暴露 `test_dynamic_imports_do_not_add_import_cycles` 新红：函数级 `import desktop_voice_input` 让 `white_model→desktop_voice_input→desktop_automation_service→engine→white_model` 成环（`workflow_settings_dialog` 为入环边）。修复：两处改经 `ui_plugin_registry.module('desktop_voice_input')` 延迟加载（规则 18 唯一入口），`UI_PLUGINS` 登记该插件；定向复测 `test_no_circular_import` 2/2、`test_dynamic_import_registry` 3/3、`test_dialog_voice_input` 3/3 全绿。

## 验证证据

- `python -B smoke_test.py`：8/8 通过。
- `python -B smoke_test.py --affected white_model workflow_settings_dialog desktop_voice_input desktop_shared_input`：9 项门禁全绿，定向测试 0 红（`test_dialog_voice_input` 3、`test_req_s09_anchors` 19、`test_shared_input_voice` 9、`test_shared_input_ui` 13、`test_white_model_identity` 12、`test_previs*` 等）。
- `python -B run_selftests.py -k dialog_voice_input req_s09_anchors previs white_model model_manager shared_input_voice stage_reasoning skills`：382 条用例 0 红。
- `python -B smoke_test.py --architecture`：470 条，仅 `test_round_number_continuous` 红（2939 != 2959）——功能分支已知分支态，`project_status.md` 只能由 master 提交，同 R2943/R2952 口径如实记录；环棘轮修复后全量复跑确认无其它红。
- 欠账口径：功能分支不累计全量欠账（§5），`full-safe-receipts.json` 真实凭据为权威；合入 master 时按累计改源码轮次判定是否需 `--all --safe`。
- 真机麦克风/FunASR/MCP 客户端端到端未在本机实测（无麦克风与已下载模型环境），属机器级验收项，已在轮 1–4 结果文件持续标注。

## 遗留与边界

- `project_status.md` 轮次头仍为 2939：状态页只能由 master 提交，合并轮次时同步为最新结果轮次加一（当前应为 2959）。
- 其余短文本输入框（资产改名、云端回复框、查找栏）登记待定；如后续任务书点名再接入，组件已可直接复用。
- 任务书文件本身不入库（gitignored/未跟踪约定）。
