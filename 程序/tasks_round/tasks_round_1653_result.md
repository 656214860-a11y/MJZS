# R1653 功能轮（文档与测试）：文档先行试点，阶段 01 剧本准备

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（流程试点）。只改文档与新增测试，未改任何 `.py` 产品代码、不改行为。来源：用户 2026-10-16 提出把开发方式从“往 AGENTS.md 持续加限制”改为需求 → 设计 → 实现的文档先行流程，先以阶段 01 试点。
2. **测试跑了吗？三个基线过了吗？** 新增 `tests.test_script_preparation_roles` 2/2、`tests.test_script_preparation_manifest_scope` 4/4；`tests.architecture.test_agents_md` 除 1 项外全绿（见 D）；`test_root_layout`、`test_token_saver` 通过；默认冒烟 **8/8**。**未跑架构门禁全量、未跑安全全量**。
3. **project_status.md 的欠账少了吗？** 没有变化：本轮不改源码，不计入全量欠账（纯文档与测试）。

## A 改动

1. 新增 `程序/docs/REQUIREMENTS.md`：阶段 01 共 17 条 `REQ-S01-xx`，含状态标记与非目标。
2. 新增 `程序/docs/DESIGN.md`：模块分工表、`DES-S01-xx` 设计条目（每条标注对应 REQ）、需求到测试的锚定表。
3. 新增 `程序/tests/test_script_preparation_roles.py`（REQ-S01-15）、`程序/tests/test_script_preparation_manifest_scope.py`（REQ-S01-23）。
4. `程序/AGENTS.md`：新增 §2.7“文档先行”6 条；§3.1／§3.2 各加一条；删除已迁入 DESIGN 的“锁采集”行与 SKILL 行中的 AUDIT／manifest 尾句。
5. `程序/architecture.md`、`程序/PROJECT_MAP.md`：纠正两处与代码不符的描述——剧本准备锁值为交付形态、赛道、素材来源三项（原写“只要求交付形态”，来自 R1127，已被 R1496 取代）；剧本准备只产出 `emotion_curve.json`（原写五类 manifest 均由本阶段产出），其余按 `script_manifest_schema.PRODUCERS` 归属。
6. `程序/distribution_manifest.md`：声明 `docs/REQUIREMENTS.md`、`docs/DESIGN.md` 为开发文档（`test_distribution_selfcheck` 要求）。

## B 用户在本轮的决策

- 锁值以代码（`script_contract.STAGE_LOCK_REQUIREMENTS`）为准，不回退 R1496。
- manifest：本阶段只产出 `emotion_curve.json`；编辑角色已并入 `pipeline-script-preparation` SKILL（HOLLMWOOD 框架 R1441 已移除）。
- REQ-S01-15、REQ-S01-23 补测试。
- 试点验收后再决定是否推广到其他阶段。

## C 验证命令

- `run_selftests.py -k agents_md root_layout token_saver script_preparation doc`
- `python -B -m unittest tests.test_distribution_selfcheck`
- `python -B smoke_test.py` → 失败 0 项

## D 未做与局限

- `test_agents_md.test_performance_history_is_declared_as_historical_only`：在隔离 worktree 里红，原因是被 gitignore 的 `维护记录/基准历史.json` 只存在于主树；与本轮改动无关，合入 master 后以主树文件为准。
- `test_distribution_selfcheck` 仍红：`程序/data_model.md`、`程序/runbook.md`、`程序/task_states.md` 未声明（R1625 遗留，R1651 结果文件 D 节已登记），本轮不修，属范围外。
- `project_status.md:271` 那条写死行号的“勿误改”条款本轮未动（规则 41：仅 master 可提交该文件）；合入后单独处理。
- AGENTS.md §2.2 的总控宪法 ③ 属于阶段 00，不属 S01，暂不迁移。
- 试点只覆盖 S01；其余阶段的需求与设计文档未建。

## E 提交

提交于分支 `codex/wip-R1653`，合入 master 的方式与 hash 见合入后的状态页记录。
