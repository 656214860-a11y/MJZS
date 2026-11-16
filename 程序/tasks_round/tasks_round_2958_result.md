# R2958 结果：语音离线化·轮5——其余输入框接入＋文档/契约/门禁收尾
<!-- round-evidence: {"commit_base": "a141a9b1", "credential_hits": 0, "evidence_sha256": "4a599e449fe0aab4", "exit": 0, "failed": 0, "passed": 0, "round": 2958, "tests": "docs-only"} -->

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

## 合并预备（交接，R2958 提交后补记）

- **分支状态**：`codex/wip-R2958` HEAD `74242f1b`，五轮提交 `68b6004c/54fb2fdd/9801cdd3/14356e62/74242f1b` 齐备，工作树干净（仅任务书未跟踪）。
- **合入阻塞**：主工作区 `D:\漫剧制作助手` 有另一车道在途合并——`project_status.md` 未提交改动声明「当前轮次 2960（R2959 合并轮：R2933+R2946+R2950 导航图标轨）」，`_master_verify.txt` 为其验证输出；`merge_round.py` 的 foreign-changes/MERGE_HEAD 检查会拒绝在脏树上合并。须等该车道提交后再合。
- **冲突预览**（`git merge-tree master codex/wip-R2958`，基线 merge-base `0581308b`，对 master@R2954）：9 个冲突文件——`desktop_shared_input.py`（master +505/−73 重构共享输入框嵌模型选择器、删 13 页阶段配置按钮；本支 +42/−4 加麦克风与听写实例，**语义冲突需把 voice 挂进新结构**）、`desktop_writing_page.py`（双方均重构，master +115/−185、本支 +48/−156）、`desktop_script_pages.py`、`desktop_idea_attachments.py`（master 仅 1 行）、`runbook.md`、`tests/test_idea_chat.py`、`tests/test_script_composer.py`、`tests/test_ui_edges_pages.py`、`维护记录/覆盖率基线.json`（双方重生成，取并集口径）；`PROJECT_MAP.md`/`architecture.md`/`desktop_page_nav.py` 自动合并无冲突。R2959 落地后冲突面可能再变，合并时以当时 master 为准重跑 merge-tree。
- **合并后验证**：冲突解决后跑 `smoke_test.py`＋`--affected desktop_shared_input desktop_writing_page desktop_script_pages desktop_idea_attachments`＋`--architecture`；共享输入框/写作页/附件是高险区，重点核对麦克风按钮位置、voice_input 生命周期绑定、composer 工具行契约；`test_round_number_continuous` 在合并提交后应转绿（状态页同步为最新结果+1）。
- **合并命令**：主工作区干净后 `dev.py merge codex/wip-R2958 -s "<说明>"`（含 local_ci 出口与领号）；合并提交后单独提交 `project_status.md` 补记（`R<n>: 补记分支 codex/wip-R2958 的轮次记录`），并把冲突解决命令原始输出贴进本文件（runbook §13 要求：第一条 diff 输出须为空、轮次号为并集）。

### 语义合并要点（已核实双方实现，合并时照此执行）

- **架构级冲突**：master R2942 已在共享栏加麦克风，但走 `on_voice` 回调——`SharedStageInput.voice_button`/`_toggle_voice`→`options['on_voice']`→`desktop_shared_send.host_options`→`_voice()`→`from desktop_writing_page import VoiceInput`（**旧云端版类**，构造签名 `VoiceInput(desktop, box, button)`）。本支轮 3 把 `VoiceInput` 提炼为 `desktop_voice_input.VoiceInput`（签名 `VoiceInput(box, button, *, status, listening_style, idle_style, project)`）并从 `desktop_writing_page` 删除旧类，共享栏改为自持 `mic_button`/`voice_input`/`_make_voice_input`。
- **`desktop_shared_input.py` 解法**：取 master 结构（`voice_button`＋`on_voice` 回调＋`_toggle_voice` 委托），**舍弃本支** `mic_button`/`self.voice_input`/`_make_voice_input`/自管 `_toggle_voice`——master 的宿主回调管线是更新的解耦设计且已被 `desktop_shared_send` 消费；本支独有的 docstring/layout 行说明合并时按 master 版微调。
- **`desktop_shared_send.py` 必修（自动合并不会报冲突但会炸）**：本支未动此文件，合并自动取 master 版——其中 `_voice()` 仍 `from desktop_writing_page import VoiceInput`，合并后该类已不存在。须改为 `from desktop_voice_input import VoiceInput` 并按新签名构造：`VoiceInput(box, button, status=desktop.status, project=desktop.root)`（`desktop.root` 为项目根、`desktop.status` 为 StringVar，均已在 `_voice` 作用域可用）；`desktop.shared_voice` 复用/重绑 `voice.button` 逻辑保留。
- **`desktop_writing_page.py` 解法**：取 master 的 R2942 页面重构（+115/−185）为底，**再移除旧 `VoiceInput` 类与 composer 内麦克风残留**（本支已做的提炼）；`page.idea_voice_input`/`idea_voice_button` 兼容引用按本支口径处理（共享栏唯一实例，不再有页级按钮）。
- **`desktop_script_pages.py`/`desktop_idea_attachments.py`/`runbook.md`/测试三件/`覆盖率基线.json`**：常规冲突，基线取 master、叠加本支增量；覆盖率基线两边重生成，按合并后实际模块集重跑生成脚本刷新，不手工挑行。
- **对话框两处**（`white_model.py`/`workflow_settings_dialog.py`）不在冲突列表，自动合并保留；其 `ui_plugin_registry.module('desktop_voice_input')` 调用不受影响。
- **合并后必跑**：`smoke_test.py`、`--affected desktop_shared_input desktop_shared_send desktop_writing_page desktop_script_pages desktop_idea_attachments desktop_voice_input`、`--architecture`；重点核对共享栏麦克风按钮存在且 `on_voice`→新 `VoiceInput` 链路通、13 页 `set_stage` 不重建会话、输入框销毁停录、`test_round_number_continuous` 转绿。
