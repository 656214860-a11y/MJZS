# R2851 结果：T10 批次2收尾——platform_tools 迁入 contract/＋边界棘轮包化口径补齐
<!-- round-evidence: {"commit_base": "8d22d2cb", "credential_hits": 0, "evidence_sha256": "174653a99ef65955", "exit": 0, "failed": 0, "passed": 594, "round": 2851, "tests": "run_selftests.py -k agents_md atomic_write function_size gate_selfaudit http_boundary import_error legacy_facade notification_boundary outbound_http path_authority platform_process print_ratchet recycle_service secret_sink shared_state silent_exception stage_display todo_comment token_boundary layers no_circular_import coverage static_hygiene platform_tools script_contract cli_streaming client_profiles claude_program_detection desktop_attachment_send desktop_idea_chat_desktop_paste desktop_send_ledger execution_deadline idea_download_import model_failure_route open_https_redirect req_s04 req_s09 req_s13 runtime_projection script_composer speech_api stage_completion_service video_revision test_workflow account_offline master_skill_update"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   结构治理轮（§3.3，T10 批次 2 收尾：`platform_tools`——出站 HTTP 唯一建连点 `open_https`、`open_websocket`、进程启动与平台适配——迁入 `contract/`；同轮把 14 个只扫顶层文件的边界棘轮切到 `module_scan_files()`，消除包实体盲区）。分支 `codex/wip-R2851`（T10 工作树，叠于 R2835）。队列：无对应 ID。

2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 **8/8** 通过。
   - `smoke_test.py --architecture` 466 条：本轮修复 platform_tools 迁移引发的 7 项红（http_boundary／outbound_http_authority／silent_exception／import_error_boundaries／coverage 基线 ×2）＋自审计回归 2 项；复跑后仅剩 `test_round_number_continuous` 1 红——分支固有状态页滞后（仅 master 可提交 `project_status.md`，同 R2832 记录）。
   - 定向 `run_selftests.py` 平台工具与 HTTP 边界相关用例全绿；`coverage_report.py` 9 组定向用例全过，基线 **402→403** 模块；`runbook.md` §11 同步。
   - 提交前补跑定向 `run_selftests.py -k`（覆盖本轮全部改动测试文件与受影响门禁，594 条）：**0 红**；证据 `tasks_round/evidence/R2851.json`。
   - `distribution_build.py --plan` undecided=0。
   - 全量 `--all --safe`：未跑（分支不累计欠账）。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账；contract/ 达 30 个 L0 模块，**批次 2（L0 契约族）全部完成**。

## 交付

- `git mv platform_tools.py → contract/platform_tools.py`＋顶层显式再导出门面；65 个生产文件 import 改写为 `contract.platform_tools`。
- **门面语义修补（提交前补做）**：门面把 `open_path` 等函数对象再导出，但 `contract.platform_tools` 内部跨调用（`open_target`/`open_directory`→`open_path`、`downloads_directory`→`windows_registry`、`communicate_or_kill`→`terminate_process_tree`）解析的是 contract 模块全局，测试 `patch('platform_tools.X')` 打在门面属性上拦截不到。22 个测试文件同步 mock 与导入路径到 `contract.platform_tools`（`import platform_tools`→`import contract.platform_tools as platform_tools`、`from platform_tools import`→`from contract.platform_tools import`、patch 字符串同步）；断言原样未动，`account_client.platform_tools`／`update.platform_tools` 这类经消费方引用的 patch 本就命中 contract 模块，未改。
- `_scan.py` 新增 `registry_key()`：T10 包实体归一为 `<模块名>.py` 登记键（与搬家前一致），`agent/` 等非包路径保持 posix 原样。
- 14 个边界棘轮由 `production_files()`（仅顶层）切到 `module_scan_files()`（顶层非门面＋包实体）：agents_md／atomic_write／function_size／legacy_facade_manifest／notification／path_authority／platform_process／print／recycle_service／secret_sink／shared_state／stage_display／todo_comment_snapshot／import_error_boundaries；`test_todo_comment_snapshot` 与 `test_token_boundary` 的登记键同步改 `registry_key`，快照与冻结基线口径不变。
- `test_silent_exception_ratchet` 扫描面补五个包目录，豁免键改 `contract/platform_tools.py`。
- `test_http_boundary`／`test_outbound_http_authority` 白名单键改包路径；`test_import_error_boundaries` 换 `module_scan_files`（实体按 stem 登记，断言原样）。
- `architecture.md` contract/ 计数 28→30；`维护记录/覆盖率基线.json`、`runbook.md` §11 同步。

## 机制记录

- **盲区根因**：`production_files()` 只 glob 顶层，包实体迁入后边界棘轮看不到实体代码——本轮把模式扫描类棘轮统一切到 `module_scan_files()`；`test_layers` 顶层登记检查与 `test_busy_state`／`test_token_boundary` 自带递归扫描维持原口径。
- 门面不进入 `module_scan_files()`，棘轮键（`path.name`／`module_name`）与搬家前完全一致，登记表零改动。
- `registry_key()` 解决 posix 路径键棘轮（`_REPLACE_REGISTERED`、token 基线、TODO 快照）在包化后的键漂移。

## 环境处置（与本 diff 无关）

- `AIGC创作全流程` 子模块在本工作树缺检出：按 HEAD gitlink `1a43ae5` 从主工作区嵌入仓库本地克隆补齐，`test_skill_reference_injection` 转绿；不影响提交内容。
- `reference/HoLLMwood`、`剧本锻造`、`编剧技能集` 三个 gitlink 同样缺检出：按 HEAD gitlink（`3ef9f99`/`6c3d739`/`357d134`）从主工作区嵌入仓库本地克隆补齐，`test_script_contract` 的 SKILL 审计转绿；克隆内容不入提交（gitlink 只记提交号）。
- `维护记录/基准历史.json`（gitignore 运行文件）从主工作区复制到位，`test_agents_md` 历史基准检查转绿。
- `test_round_number_continuous` 仍红：状态页轮次为分支基线值，合入 master 状态同步后自解。
- **分支基线既有红（与本轮无关，已在基线 `8d22d2cb` 干净检出复验同样红）**：`test_flow_agent_launch`（context_budget 断言）、`test_req_s07_anchors`（3 条 ValueError not raised）；master 上同名用例全绿，属分支落后主干的既有欠账，合入后自解，未在本轮扩大处理。

## 未覆盖／下一步

- 批次 2 完成。批次 3（infra/，约 50 个 L1 模块）起，每包先在 `distribution_manifest.md` 登记 `程序/<包>/**`，再按族迁移；边界棘轮已包化，剩余风险集中在按 posix 路径键控的登记表与动态导入字符串。
