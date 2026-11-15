# R2881 功能轮结果：任务书轮 2/5——SKILL 仓库导入（薄 git 层）＋面板导入入口
<!-- round-evidence: {"commit_base": "8f5c2990", "credential_hits": 0, "evidence_sha256": "686a8bd6fbfaeadf", "exit": 0, "failed": 0, "passed": 293, "round": 2881, "tests": "run_selftests.py -k skill complexity_ratchet coverage_baseline coverage_audit_ratchet"} -->

- 轮次类型：功能轮（§3.1，用户任务书《共享输入框与skill体系重构任务书》轮 2）。
- 任务书：`程序/tasks_round/共享输入框与skill体系重构任务书.md`。
- 分支：`codex/wip-R2881`（领号时工作树携未提交改动自动切自 codex/wip-R2862）。

## 改动

- `skill_import_service.py` 新增仓库导入段（约 +230 行）：
  - `parse_repo_ref`：`owner/repo` 简写（默认 github.com）、`https://`／`git@` 完整地址、`@分支` 后缀（含带 `/` 的分支名）、本地目录；userinfo 里的 `@` 不误判为 ref，台账标签 `repo_label` 去 userinfo 不回显凭据。
  - `_git_clone`：唯一 git 调用 `git clone --depth 1 [--branch ref]`，`shutil.which('git')` 缺失、超时（180s）、非零退出均抛 `ImportBlocked`，stderr 经 `_sanitize_git_error` 脱敏截断。
  - `_repo_candidates`：含 `SKILL.md` 的目录＝外部包（不向内递归），其余 `*.skill.md`＝清单；点开头目录与 `__pycache__` 跳过；候选上限 100。
  - `_candidate_stage`：frontmatter `stage` → 仓库内 `NN` 目录 → 面板阶段提示。
  - `import_from_repo`（install＝新增/覆盖）：克隆到 `data/skills/.仓库克隆-*`（注册表不可见）或本地目录直读 → 逐候选 `plan_import` → 汇总问题一次确认 → 逐候选 `perform_import`（复用预检→暂存→换入→试冻结→登记全管线，旧版回收站、失败回滚不变）；克隆暂存 finally 回收；单候选失败不影响其他。
  - `update_from_repo`＝同入口刷新（旧版走回收站）；`uninstall_skill` 按注册名回收（整包收目录、清单收文件，限 `skill_roots` 内）；`validate_skill` 即试冻结闸；`list` 沿用 `skill_registry.getAll()`。
  - `record()` 台账 `source` 支持 `plan['ledger_source']`，仓库导入记 `github.com/o/r@ref` 标签而非临时克隆路径。
- `skill_panel.py`：SKILL 操作下拉新增「从仓库地址导入」项；面板类行数触顶复杂度棘轮（723），故把「新增 SKILL」两条入口（`add_skill_from_file`／`add_skill_from_repo`）连同 `_reload_panel_skills` 整体拆到新模块 `skill_panel_import.PanelImportMixin`（L4 已登记），`Panel` 经 Mixin 继承、`Panel.add_skill_from_file` 调用锚点不变；`_git_clone` 改走 `contract.platform_tools.run_process`（白名单进程入口，覆盖率审计 21 不新增待办）。
- 测试 patch 锚点同步（契约有意变更）：`test_skill_import_validation`／`test_skill_user_layer`／`test_skill_notes` 中守卫 `add_skill_from_file` 的 `FileDialog`／`confirm` patch 目标由 `skill_panel` 改为 `skill_panel_import`（名字已迁居）；`test_skills.py` 下拉值断言改 `MANAGE_LABELS`。
- `tests/test_skill_repo_import.py`（新，15 例）：地址解析六形态、扫描包/清单/隐藏目录、包内不递归、本地仓库整包+清单分阶段落位、NN 目录与提示兜底、confirm=False 零写入、空仓库/缺目录拦截、mock 克隆全链路+台账来源标签+暂存清理、克隆失败清理、update 覆盖回收、uninstall、validate 闸。
- `tests/architecture/_layers.py`＋`test_complexity_ratchet.py`：登记 `skill_panel_import`（L4）；Panel 实测 668 行，登记值 723→683（棘轮口径＝实测+15）。
- `维护记录/覆盖率基线.json`＋`runbook.md` §11：重跑 `scripts/coverage_report.py`（同 9 组定向用例、全绿）刷新模块集合 405→406；runbook 数字同步。
- `architecture.md` §55、`PROJECT_MAP.md`：登记仓库导入生命周期、暂存目录与 `skill_panel_import`。

## 三问

- 本轮属于 §3.1 功能轮（任务书 5 轮中的第 2 轮）。
- 测试跑了：`smoke_test.py` 8/8；`run_selftests.py -k test_skill_repo_import test_skill_import_validation test_skills test_skill_notes` 171 例 0 红；`-k skill_panel skill_registry skill_user` 30 例 0 红；拆分后复跑 `-k test_skill_repo_import test_skill_import_validation test_skills test_skill_notes test_skill_panel test_skill_user_layer test_skill_registry` 全绿；`--architecture` 469/470——唯一红 `test_round_number_continuous`（2872≠2882）为 master 既有欠账：master `project_status.md` 当前轮次 2872、最新结果文件已到 2886，同断言在 master 上同样失败（2872≠2887），本分支无权改 `project_status.md`，如实记录不修。
- 欠账：无新增产品欠账；git 缺失环境下仓库导入明确报 `ImportBlocked`（不引第三方、不伪造成功）。

## 提交

待补：commit hash 由 dev.py commit 回执填写。
