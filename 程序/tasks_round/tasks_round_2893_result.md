# R2893 功能轮结果：任务书轮 3/5——共享输入框组件＋`/` 命令解析＋发送门禁＋模型快照
<!-- round-evidence: {"commit_base": "d625f023", "credential_hits": 0, "evidence_sha256": "1df56c7deb8d2f0f", "exit": 0, "failed": 0, "passed": 25, "round": 2893, "tests": "run_selftests.py -k test_skill_command test_shared_input_ui"} -->

- 轮次类型：功能轮（§3.1，用户任务书《共享输入框与skill体系重构任务书》轮 3，核心轮）。
- 任务书：`程序/tasks_round/共享输入框与skill体系重构任务书.md`。
- 分支：`codex/wip-R2893`（领号时工作树干净，直接切自 codex/wip-R2881）。

## 改动

- `skill_command.py`（新，L2 纯标准库无 Tk）：`parse_command` 三形态——`/skill名`（精确＋ASCII 忽略大小写，先于阶段判定）、`/阶段别名`（`pet_bus.STAGES`/`STAGE_NAMES` 反向映射：id、中文名、`NN`、`NN 名称`；重名取阶段顺序第一条）、`/子引擎`（`skills/00全流程SKILL/AIGC创作全流程/` 下一层含 SKILL.md/README 的目录）；`completions` 补全排序＝当前阶段已装 skill→其余 skill→阶段别名→子引擎，去重保序；`command_token` 供输入框取当前 `/` token；自由聊天返回 `None`。
- `desktop_shared_input.py`（新，L4）：`SharedStageInput(ttk.Frame)` 单实例底部输入框——`[技能][附件] | TextArea | [模型][发送]`；`/` 键与 `Esc` 经宿主 `ShortcutRegistry` 登记（scope `shared_input`），`/` 补全弹层在输入框下方、当前阶段 skill 优先；`set_stage` 只换上下文不重建实例；`upstream_send_error(project, stage)` 发送门禁——有 `stage_parallel` 门禁行走 `evaluate`（UPSTREAM_BLANK→「请先完成/确认「X」阶段」，BLOCKED→`blocked_text`），无门禁行的非 script 阶段看紧邻上游 `stage_completion_service.completion_evidence`（上游 skipped 豁免），script/无项目放行（简报门禁仍归宿主发送路径）；`send()` 顺序＝门禁→解析→`writing_api.capture_request` 快照→`on_send(text, parsed)`，`in_flight`/`end_request()` 表达在途，模型切换只影响下一次请求；三个入口（技能/附件/模型）走宿主回调，缺省给状态栏兜底。
- `tests/architecture/_layers.py`：`skill_command`→L2、`desktop_shared_input`→L4。
- `architecture.md` SKILL 节、`PROJECT_MAP.md` 阶段配置行：登记两模块与门禁/快照口径。
- `维护记录/架构统一基数.json`：`skill_command` 入 L2 `exempt_items`（纯解析器，无 service_contract 采用）；`维护记录/覆盖率基线.json`、`runbook.md` §11：模块基数同步至 408。
- 架构棘轮收口（同轮）：`desktop_shared_input` 裸 `tk.Toplevel` 改经 `ui_plugin_registry.module('skill_panel').show()`（BaseDialog 统一边界）；`width/height` 数字改 `TEXT_ROWS`/`width=0` 自适应、`padx/pady` 0 改 `SPACING['none']`、Listbox 字体改 `FONTS['hint']`；4 处 `except Exception: pass` 改 `app_logging.swallowed()` 留痕。
- `tests/test_skill_command.py`（新，12 例）：解析六形态、别名映射与消歧、引擎目录扫描、补全排序/前缀过滤、`command_token`。
- `tests/test_shared_input_ui.py`（新，13 例，真 Tk）：四入口布局与 pack 序、`/` 补全开合与当前阶段优先、上游空白拒发（continuity→资产管理、script_structure→剧本准备）、script 放行、命令解析送达、在途快照语义、`set_stage` 不重建；`UpstreamGateTests` 5 例 mock 门禁本体验证放行/拦截分支。

## 三问

- 本轮属于 §3.1 功能轮（任务书 5 轮中的第 3 轮）。
- 测试跑了：`smoke_test.py` 8/8；`run_selftests.py -k test_skill_command test_shared_input_ui` 25 例全绿（首轮 skill_command 1 红为 `_SUB_ENGINE_PARENT` 多拼一层 `skills/`，已修）；`-k idea_chat writing_api` 回归 265 例 ALL PASSED（748.3 秒，含 test_shared_input_ui 13 例）；`smoke_test.py --architecture` 470 例仅余 `test_round_number_continuous` 1 红——project_status 2872 滞后于最新结果 2893，属 master 侧状态页同步欠账（仅 master 可提交 project_status.md），功能分支不代改，如实记录。
- 欠账：无新增；`project_status.md` 轮次同步留待 master 合并轮。

## 提交

待补：commit hash 由 dev.py commit 回执填写。
