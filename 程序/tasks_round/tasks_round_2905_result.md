# R2905 功能轮结果：任务书轮 5/5——三虎自动适配"默认勾选 skill"
<!-- round-evidence: {"commit_base": "c81ee860", "credential_hits": 0, "evidence_sha256": "6f597e91fc355c7a", "exit": 0, "failed": 0, "passed": 677, "round": 2905, "tests": "run_selftests.py -k stage_flow stage_command skill_templates pet_ui"} -->

- 轮次类型：功能轮（§3.1，用户任务书《共享输入框与skill体系重构任务书》轮 5，最后一轮）。
- 任务书：`程序/tasks_round/共享输入框与skill体系重构任务书.md` §4 轮 5。
- 分支：`codex/wip-R2905`（R2905 已领号）。
- 前置：R2862（删总控）→ R2881（skill 仓库导入）→ R2893（共享输入框组件）→ R2898（13 阶段接入＋取消按模型隔离，commit `c81ee860`）。

## 任务书轮 5 要求与落点

- 三虎全自动：每阶段执行"阶段配置里**默认勾选的 skill**"（可能多个，按面板顺序），子引擎天然对应阶段；不再依赖总控清单。
- `stage_flow.py`/`stage_handler_registry.py` 自动编排：把"取总控 skill"改为"取该阶段已勾选 skill 列表"；无勾选 skill 的阶段自动跳过并提示。
- 自动模式沿用发送门禁与成果核验（`stage_completion_service`），不因删总控放宽。

## 改动（全部在本轮范围内）

### `stage_flow.py`
- 新增 `unchecked(project, stage)`：自动编排的勾选门禁。只管 `OWN_ORDER`（13 个制作阶段）；`pet_performance`/`pet_test` 等宿主自检阶段不设闸；项目路径不可解析时不设闸（与"读不出来就当空"老口径一致）。返回 `'未勾选 SKILL'` 或空串。
- `selected_skills(project, stage)` 沿用 `stage_config.get(...)['skills']`——勾选列表唯一读取口，`clean_skills` 保序，配置顺序即面板顺序。

### `stage_handler_registry.py`（阶段启动唯一入口，硬约束 17）
- `start()` 在账号闸、工作流锁闸之后、各专用 handler 之前新增：`trigger == 'auto'` 且 `stage_flow.unchecked(...)` → `skip_unchecked()`。
- `skip_unchecked(desktop, stage)`（公开）：`machine.skip(stage, '未勾选 SKILL')`＋`machine.save()`（`skipped` 本就在 `pet_state.DONE_STATES`/`stage_flow.DONE_STATES` 内，自动链照常推进）＋`auto.done(stage, True)`＋`pet.broadcast('【警告】…已跳过这一步（阶段配置里勾选后可重跑）')`。**不发 `stage.completed`**——跳过的阶段没有产物可验，完成事件仍只走 `stage_completion_service` 核验路径。
- 手动 `trigger != 'auto'` 不受此闸——手动发送有 `validate_selected_skills` 门禁兜底。

### `pet_ui_stages.py`
- `start_stage()`：自动档下在付费审批（`agent.approve`）之前先查 `unchecked`——反正不会跑，没必要先问"要不要花钱"；命中直接 `skip_unchecked` 返回提示语。L3 入口内同一道门禁兜底。
- `run_skill()`（`enter_stage` 全自动进页与三虎"跑 SKILL"共用）：勾选交集改为**按阶段配置勾选顺序（面板顺序）**取 `picked`，原来按注册表遍历顺序；全部取消勾选时仍提示"都被您取消勾选了"。

### `stage_exec.py`
- `run()`：`only` 未给时取 `stage_flow.selected_skills`；结果为空时直接回 `{'ok': False, 'skipped': True, …}` 汇总并提示"请先在阶段配置里勾选，或点「恢复默认」"——空勾选是"这一步没勾"，不是"跑全部"。`script_structure`/`delivery` 专用模板路径在此之前返回，不会空跑。

### `skill_orchestrator.py`
- `run_stage_with_template()`：`names=None` 才回退该阶段全部已启用 SKILL；显式空表 `[]` 视为"一个都没勾"，`selected` 为空 → 无 `execute_action` 时返回 `【阻塞】…未启用可执行 SKILL` 的非成功 Run，不再隐式全跑。
- `run()`：`wanted` 为空时返回 `ok=False` 的 Run（"没点到要跑的 SKILL"），既有行为保持。

### `PROJECT_MAP.md`（任务书要求轮 5 后更新两节）
- 「三虎与自动化」：补登 `stage_handler_registry.py`/`stage_exec.py`，职责注明阶段启动唯一入口、自动档按勾选 SKILL（面板顺序）派发、无勾选跳过并提示、成果仍经 `stage_completion_service` 核验。
- 「模型与安全」：补记共享输入发送瞬间模型快照（`desktop_shared_input.request_snapshot`，R2893），在途请求不受中途切模影响。

## 验收对照

- **勾选单/多 skill 自动按序执行**：`selected_skills`/`stage_config.clean_skills` 保序；`run_skill` 的 `picked` 改按配置顺序；`stage_exec.run`/`run_stage_with_template`/`orchestrator.run` 均按传入 names 顺序分层执行。✔
- **未勾选阶段跳过并提示**：`unchecked` 门禁在 `pet.start_stage`（先于付费审批）与 `stage_handler_registry.start`（L3 兜底）两处生效；`machine.skip` 落 `skipped` 终态、自动链推进、`【警告】`播报；不发 `stage.completed`。✔
- **成果核验不放宽**：跳过路径不产生完成事件；正常路径仍走 `pet_ui_stages._completion_evidence`/`_complete_if_verified`/`stage_completion_service.emit_verified_completion()`，缺产物发 `stage.paused`。自动模式发送门禁（账号闸、工作流锁、上游完成门）全部保留在门禁之后。✔
- **`-k stage_flow automation` 回归**：见下。✔
- **smoke 8/8**：见下。✔

## 测试证据

- 新增/更新用例：
  - `tests/test_stage_flow.py`：`unchecked` 门禁——无配置不设闸、空勾选返回原因、勾选返回空串、非 OWN_ORDER 阶段不设闸。
  - `tests/test_stage_command_contract.py`：自动档空勾选 → skipped＋提示＋自动链放行；手动档不受闸；失败仍发 `stage.failed`。
  - `tests/test_skill_templates.py`：`run_stage_with_template(names=[])` 返回非成功 Run，不回退全量。
  - `tests/test_pet_ui.py::AutoStartTests`：新增 `test_a_stage_without_checked_skills_is_skipped_before_any_dispatch`——半自动档付费阶段空勾选时 `pet_start` 不被调用、不叫醒轮询、状态机落 `skipped`。
- 定向：`run_selftests.py -k stage_flow stage_command skill_templates pet_ui_stages` 等 9 文件 **687 例 ALL PASSED**（32.8 秒，0 文件红）。
- 更早一轮受影响回归：12 文件 **780 例** ALL PASSED。
- `smoke_test.py`：**8/8**。
- `smoke_test.py --affected` 串行 44 文件 / 129 工作单元：**0 文件红**；1 条既有登记位跳过（`test_core.test_stage_profile_wrong_preset_rejected`，需打包 skill 产物，本机环境缺失，非本轮引入）。
- `smoke_test.py --architecture`：470 例，**1 红**——`test_round_number_continuous`（`project_status.md` 停在 2872、最新结果 R2905→期望 2906；仅 master 可提交状态页，功能分支不代改，合并轮前预期红，与 R2893/R2898 同口径如实记录）。

## 三问

- **轮次类型**：功能轮（§3.1，任务书第 5/5 轮）。
- **测试跑了吗、三个基线过了吗**：跑了。冒烟 8/8 ✔；定向/受影响回归全绿（687＋780＋44 文件串行 0 红）✔；架构门禁 469/470，唯一红为 `test_round_number_continuous` 的 master 侧状态页欠账（非功能回归）；全量 `--all --safe` 未跑（分支不累计欠账，凭据以 master 合并轮为准）。
- **`project_status.md` 的欠账少了吗**：本轮未新增欠账；`project_status.md` 轮次同步仍是 master 侧既有欠账（2872 vs 最新结果），仅 master 可提交该文件，留待合并轮，与 R2893/R2898 记录一致。

## 备注

- 任务书五轮全部完成：R2862 → R2881 → R2893 → R2898 → 本轮 R2905。
- 未提交的 `tasks_round/` 下其他任务书（副本编剧自动保存、剧本体验优化、盘点、费用统计）与本轮无关，不入暂存。

## 提交

已通过 `scripts/dev.py commit` 提交（分支 `codex/wip-R2905`，commit 见 `git log` 的 R2905 条目）；验收证据 `tasks_round/evidence/R2905.json`：定向 `run_selftests.py -k stage_flow stage_command skill_templates pet_ui` 677 例、0 失败、exit 0。
