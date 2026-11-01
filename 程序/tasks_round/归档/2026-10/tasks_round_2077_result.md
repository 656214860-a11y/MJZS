# R2077 用户导入的 SKILL 独立到 data/skills（同名用户优先、迁移旧导入）（修复轮）

轮次类型：修复轮（§3）。日期：2026-10-30。分支 `codex/wip-R2077`（基于 master `47df1bce`）。

- 轮次号：开工时领的是 R2073，收尾前另一会话领了并提交 R2074（`53b3be87`）；commit-msg 钩子只认中央最新号，按用户决定等 R2074 提交后再领 R2075；提交时 R2076（合入 R2074 到 master，`4bbf8411`）又被另一会话领走，等其提交后领 R2077 改号提交。R2073、R2075 空号。

- **三问**
  - 本轮类型：修复轮。用户导入的 SKILL 原先和内置 SKILL 同放在 `程序/skills/`，分发构建会把整个 `skills/` 当作内置资源打包，所以升级可能覆盖或丢失用户 SKILL。
  - 测试与三个基线：
    - 默认冒烟 8/8 通过。
    - 架构门禁 410 条，红 2 条，都不是本轮引入（见“验证”）。
    - 本轮没有跑全量 `--all --safe`，需要合入后由后台补跑。
  - `project_status.md` 欠账：没有减少，也没有新增。本分支不改 `project_status.md`，合入时由 master 同步。

## 改动

- `skill_registry.py`：注册表改为两层合并。
  - 内置层是 `skills/`，用户层是 `data/skills/`，用户层的阶段目录名与内置层相同。
  - 新增 `default_user_root`、`skill_roots`、`resolve_reference`，以及 `Registry.user_stage_directory_for`。`Skill.layer` 的取值为 `builtin` 或 `user`。
  - 同名时用户版优先，内置版跳过并记一条软警告。删除用户版后，内置版恢复。
  - 用户层 SKILL 里的 `../00全流程SKILL/…` 引用会回退到内置层解析。
- `workflow_settings.py`：内联冻结时，两层都算允许目录，引用经 `resolve_reference` 解析。
- `skill_import_service.py`：
  - 导入台账改到 `data/skills/导入台账.json`（`ledger_path`）。
  - 导入目标在用户层、并且与内置 SKILL 同名时，从硬拦截改为软提示“将覆盖内置 SKILL”。用户层内部重名仍然硬拦。
  - 新增 `program_of`，从阶段目录推出程序目录。
  - 新增 `migrate_legacy_imports`，把旧台账 `skills/导入台账.json` 里登记过的条目迁到用户层：
    - 文件移动走 `agent.core.replace`。
    - 迁移后试冻结一次，失败就移回原处。
    - 用户层已有同名目标时不覆盖。
    - 台账键必须是“阶段目录/条目”形式，否则不迁。
    - 全部迁完后，旧台账经 `recycle_paths` 移入回收站。
- `skill_panel.py`：“新增 SKILL”写入 `user_stage_directory_for`。删除范围加上 `data/skills/`。
- `codex_skill_sync.py`：
  - 用户层来源也会同步到 Codex。共享路径固定指向内置层的 `00全流程SKILL`。
  - `start_codex_skill_sync(before=)` 在同一个后台线程里先跑注入的前置步骤，失败时走 `app_logging.swallowed`，不影响后续同步。
- `desktop_automation_tick.py`：首帧后注入 `migrate_legacy_imports`，不占启动路径，也不在启动路径上递归扫描。
- 文档：
  - `distribution_manifest.md` 的“必须排除”表加入 `程序/data/skills/**`，构建器直接读这张表。
  - `AGENTS.md` §2.2 的 SKILL 行。
  - `architecture.md` 的注册规则、导入台账路径和唯一权威条款。

## 测试

- 新增 `tests/test_skill_user_layer.py`，10 条用例：
  - 用户版覆盖内置版，删除后恢复内置版；
  - 导入目录落在用户层；
  - 引用回退到内置层；
  - 导入落在用户层，台账写在新位置，并给出软提示；
  - 用户层内部重名仍然硬拦；
  - 迁移只搬台账里的条目，台账外的文件留在原处；
  - 旧台账迁完后被回收，重跑不做任何事；
  - 试冻结失败时移回原处，用户层已有同名时不覆盖；
  - Codex 同步用户层 SKILL；
  - 注入的前置步骤先于同步执行。
- 改动前失败输出：生产代码临时换回 HEAD 版本后运行，结束后已还原。
  ```
  共 10 条用例，1.0 秒；1 个文件有红
  AssertionError: 'user-extra' not found in ['pipeline-script-preparation']
  TypeError: start_codex_skill_sync() got an unexpected keyword argument 'before'
  AttributeError: module 'skill_import_service' has no attribute 'migrate_legacy_imports'（×3）
  TypeError: Registry.__init__() got an unexpected keyword argument 'user_root'（×4）
  AttributeError: module 'skill_registry' has no attribute 'resolve_reference'
  ```
- 契约有意变更，同步了旧测试，断言未动：
  - `tests/test_skill_import_validation.py`、`tests/test_skill_notes.py`：mock 从 `_stage_directory_for` 改为 `user_stage_directory_for`。
  - `tests/test_skill_import_validation.py`：台账路径改为 `skill_import_service.ledger_path(program)`。

## 验证

所有命令都经 `工作流任务/gui_hidden.py` 在隐藏桌面运行。

- 环境准备：这个 worktree 里 3 个 SKILL 子模块没有检出（`00全流程SKILL/AIGC创作全流程`、`01 剧本准备SKILL/剧本锻造`、`01 剧本准备SKILL/编剧技能集`），导致 test_skills、test_master_skill、test_workflow_writing_stages、test_writing_quality 和 reference_injection 红。这些红项在 HEAD 上同样出现。我从主检出的本地子模块克隆，检出到 gitlink 指定的提交。补齐后这些用例全绿。
- `run_selftests.py -k skill workflow desktop_automation test_writing_quality test_master_skill`：456 条，0 红。
- `run_selftests.py -k distribution`：通过。
- `smoke_test.py`（默认冒烟）：8/8 通过。
- `smoke_test.py --affected skill_registry workflow_settings skill_import_service skill_panel codex_skill_sync desktop_automation_tick`：2121 条，5 个文件红。
  - test_idea_chat、test_ui_edges：单独重跑全绿，属于并行负载下的间歇红。
  - test_core `ResidualProjectTests.test_script_stage_project_loads_without_storyboard_json`（`'ProjectList' object has no attribute 'exists'`）：HEAD 上同样红，与本轮无关，本轮未修。
- `smoke_test.py --architecture`：410 条，第一次运行红 5 条，其中 3 条由本轮引入，已修复：
  - `skill_panel` 行数超过上限：路径推导移到 `skill_import_service.program_of`。
  - `Panel` 类体积超过上限：同一处修复。
  - codex_skill_sync 新增了静默 `except: pass`：改为 `app_logging.swallowed`。
- 修复后复跑架构门禁，剩 2 条，都不是本轮引入：
  - `test_agents_md.test_performance_history_is_declared_as_historical_only`：`维护记录/基准历史.json` 是被 gitignore 的本机文件，worktree 里没有。
  - `test_round_baselines.test_round_number_continuous`（改号前为 `2072 != 2073`）：`project_status.md` 只由 master 同步，合入时补齐。

## 已知限制

- Claude Code、Qwen 等 CLI 引擎按文件路径直接读 SKILL。用户层 SKILL 里的 `../00全流程SKILL/…` 引用对它们不会回退到内置层，只有 API 内联和 Codex 同步做了处理。
- 用户手动放进 `skills/`、没有登记在台账里的文件不会迁移，因为它们和内置文件分不开。

## 合入提示

- R2074（`53b3be87`，已由 R2076 `4bbf8411` 合入 master，不在本分支祖先里）同样改了 `skill_panel.py` 和 `workflow_settings.py`。合入 master 时要处理冲突，并对合并结果重跑 `--architecture`，因为两轮叠加后 `skill_panel` 的行数和 `Panel` 类体积可能超过上限。

## 未运行

- `--all --safe` 全量。
- 真实界面目测。
- 没有 push。

## 提交

本轮提交见 `git log`。提交信息：`R2077: 用户 SKILL 独立到 data/skills（同名用户优先、旧导入迁移）（修复轮）`。
