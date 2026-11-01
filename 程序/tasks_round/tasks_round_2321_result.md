# R2321 三虎统一监控剧本准备阶段确认顺序结果

## §7 三个问题

- **本轮类型**：功能＋收口轮（§3.1 功能轮为主，叠加查重/收口）。未改 L0 契约、未改分层表，不触发契约轮/结构治理轮协议。
- **测试跑了吗、三个基线过了吗**：
  - 默认冒烟 `smoke_test.py`：**8/8 通过**（本轮实测，EXIT=0）。
  - 架构门禁 `smoke_test.py --architecture`：**415 项跑完，2 项红**，且两项均为本 worktree 环境缺件（非本轮改动引入，见下「未验证项」）：①`test_agents_md` 读 `维护记录/基准历史.json`（git 忽略、干净 worktree 未物化）；②`test_skill_reference_injection` 读 `skills/00全流程SKILL/AIGC创作全流程/...`（git 子模块未 checkout）。本轮改动未引入任何架构红（`test_module_size_ratchet`、`test_layers` 均通过）。
  - 全量回归：**未触发、未运行**（本轮非 master 提交点、分支不累计全量欠账；提交由调度方执行）。
- **project_status.md 欠账少了吗**：本轮未改 `project_status.md`（调度方提交/合入后处理），欠账条目数不变。

## 查重清单（先搜后改，唯一权威收口）

结论：仓库内**没有第二份**「设定→大纲→角色卡」顺序/确认的运行时判定。唯一新增权威为 `stage_completion_service.preparation_progress()`（只读判据），写侧仍走 `writing_api` 既有确认/校验，无需删除任何重复实现。

| 位置 | 是否保留 | 如何收口 |
| --- | --- | --- |
| `writing_api.py`：`PREPARATION_STAGES`、`preparation_state.json`、`_confirmed_prefix`、`confirm_preparation_document`、`_preparation_state`（「前置阶段未确认则不推进」） | 保留（写侧/校验侧唯一权威） | 三虎与完成核验只读复用其**只读面**；不新增第二份顺序判定。因 `writing_api.py` 已达体量上限 1372 行，新增只读判据不放入该文件（见「改动文件」说明）。 |
| `confirm_gates.py`：门禁候选确认记录（资产锚点 G-05 等） | 保留 | 与剧本准备四阶段无关，不在本轮范围，未改。 |
| `stage_parallel.GATES` / `evaluate` / `blocked_text`（SG-A/B、SG-01~05） | 保留 | 只拦分镜之后阶段；剧本准备阶段无阶段间门禁，不涉及四阶段顺序。 |
| `stage_completion_service.completion_evidence`（阶段完成核验） | 保留并补强 | 原对 `script` 只核验自然剧本（`resolve_script_source`），未核验四阶段顺序——本轮补上：调用新增 `preparation_progress`，成为唯一完成核验入口。 |
| `script_contract.resolve_script_source` / `natural_script_selection_path` | 保留 | 阶段④「剧本」（自然剧本）解析唯一权威；`preparation_progress` 不重复它，只判前三阶段，自然剧本仍由 `resolve_script_source` 核验。 |
| `script_workspace_service.py` / `idea_chat.py` / `idea_brief_form.py` / `desktop_script_pages.py` / `desktop_writing_page.py` / `desktop_idea_chat.py` | 保留 | 文件发现/分类/采用/删除提示；确认状态均委托 `writing_api.confirmed_preparation_files` / `preparation_file_labels`，无独立顺序判定。 |
| `desktop_send_ledger.py`：`_confirmed_documents` / `current_step` | 保留 | 已委托 `writing_api.confirmed_preparation_files`；其 `done` 计数是「续发材料范围」而非「阻塞判定」，不参与推进，已复用唯一权威。 |
| `pet_agent.py` / `pet_state.py` / `pet_report.py` / `pet_chat_coordinator.py` | 保留 | 三虎状态机/进度/日报/对话协调均无四阶段顺序判定；阶段推进经 `stage_completion_service`（完成核验）与 `stage_parallel`（门禁）。 |
| `master_skill.gate` / `stage_handler_registry`（制作锁/简报门禁/阶段命令入口） | 保留 | 不涉及四阶段顺序，未改。 |

## 改动文件

1. `程序/stage_completion_service.py`：新增只读判据 `preparation_progress(project)`，并在 `completion_evidence(root, 'script')` 中于自然剧本核验**之前**先查四阶段顺序——卡住时返回「剧本准备卡在「阶段」：文件缺失/尚未确认」，从而同时拦住三虎的完成核验、`stage.completed`/`script.completed` 播报与自动续跑（`script.completed` 是三虎自动链唯一启动信号，见 `skill_orchestrator.verified_stage_output` / `pet_ui_stages.script_downloaded` / `desktop.py`）。
   - 说明：任务书建议把判定放 `writing_api` 薄封装，但 `writing_api.py` 已达体量硬上限 1372 行（`test_module_size_ratchet` 卡死），故把纯只读判据收进无 Tk 的完成核验服务（`stage_completion_service`，L3），只读走 `file_cache.read_json`，路径走 `stage_path_service.write_dir`；`PREPARATION_STAGES` 沿用 `writing_api` 的既有常量（L3→L2 向下，架构门禁通过）。无已确认简报时不设卡，保持普通对话路径与旧项目行为不变。
2. `程序/AGENTS.md`：§2.2 权威源表新增一行「剧本准备顺序确认 | `stage_completion_service.preparation_progress()`」。
3. `程序/tests/test_preparation_monitor.py`：新增 9 条用例（对应任务书 5 个场景 + 2 条边界）。

## 测试命令与实际结果

- `run_selftests.py -k preparation_monitor`：**9 条 0 红，EXIT=0**。
- `run_selftests.py -k preparation pet confirm`：**32 个文件 / 1115 条 / 0 文件有红，EXIT=0**（`ALL TESTS PASSED`）。
- `smoke_test.py`（默认冒烟）：**8/8 通过，EXIT=0**。
- `smoke_test.py --architecture`：**415 项，1 fail + 1 error**，均为本 worktree 环境缺件（`维护记录/基准历史.json` 未物化、`skills/00全流程SKILL/AIGC创作全流程` 子模块未 checkout），**非本轮改动引入**；`test_module_size_ratchet` 与 `test_layers` 通过。
- `run_selftests.py -k preparation writing pet confirm` 中的 `writing` 关键字：命中 `test_writing_api` 两条用例时红在 `workflow_settings.freeze_skills` 读取 `skills/00全流程SKILL/AIGC创作全流程/sd-decision-engine/SKILL.md`（子模块未物化，FileNotFoundError），与本轮改动无关。

## 「断言未动」声明

本轮未改任何既有测试断言，未弱化/删除/跳过任何用例。新增测试 `tests/test_preparation_monitor.py` 全部为新增断言；既有测试契约（`test_preparation_confirmation.py`、`test_req_s01_anchors.py` 等）未动，且已在 `-k preparation pet confirm` 中复验通过。

## 未验证项 / 环境限制

- 全量安全回归未运行（非 master 提交点、分支不累计欠账；调度方提交后由 CI/提交方补跑）。
- 架构门禁 2 项红为本 worktree 环境缺件，与本轮改动无关：`维护记录/基准历史.json`（git 忽略，干净检出缺）、`skills/00全流程SKILL/AIGC创作全流程`（git 子模块未 `submodule update --init`）。建议调度方在主树/完整环境复验 `smoke_test.py --architecture`。
- 未实机启动桌面应用；三虎播报文案（「剧本准备卡在…」）经 `completion_evidence` 返回值与 `report_done`/`script_downloaded` 链路推导，未在真 Tk 界面上目视验证（该链路已有既有用例覆盖其完成事件门禁语义）。
