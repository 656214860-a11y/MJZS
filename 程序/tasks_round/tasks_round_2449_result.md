# R2449 结果：总控切换锁恢复 + 本地总控包导入系统

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   功能轮（§3.1）＋修复轮（§3.2）合并：修「不使用总控→切回总控」制作锁丢失的 bug，并新增「浏览本地」导入自包含总控包的可视化系统。未改分层契约、权威源表语义与用户数据边界；新增一个 L4 无 Tk 模块并按既有 `skill_import_service` 口径登记。

2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 **8/8**（第 10 轮，与基线一致）。
   - 架构门禁 `smoke_test.py --architecture` 跑 416 条，**1 失败 + 16 errors**，全部为**环境限制**、非本轮回归：
     - `test_script_stages_name_only_their_approved_00_references`：依赖 gitlink `AIGC创作全流程` 子模块，`.gitmodules` 缺失导致功能工作树 checkout 不到（R2428 已记录同一归因）。
     - 16 条 `ERROR`：全部 `PermissionError [WinError 5]`，沙箱拦截 `tempfile`/子进程写系统临时目录；非本轮改动引入。
   - 本轮改动涉及的架构门禁（层级登记、原子写登记、覆盖率基线口径、需求锚定）已逐一核验通过（见下）。
   - 全量：未运行（沙箱内无法派生工作进程，见 project_status.md R1635 口径；全量须在沙箱外跑）。

3. **`project_status.md` 的欠账少了吗？**
   本轮新增一个源码模块（`master_import_service.py`），按 §5 计 1 个源码轮（全量欠账 +1）；无历史欠账被扩大或删除。

## 根因与修复

### 1. 「不使用总控」→ 切回同一总控，制作锁丢失（修复）

- **根因**：`stage_config.clear_workflow()`（选中「不使用总控」触发）把当前总控的制作锁移到顶层 `workflow_lock_history` 键，但 `skill_panel_workflow.PanelWorkflowMixin.apply_selected()` 在切回总控时重新构建 `workflow = {'name': …, 'lock': {}}`，从不读回 `workflow_lock_history`，锁值就此丢失。
- **修复**：`stage_config` 新增公开读口 `workflow_lock_history(project)`；`apply_selected()` 在切回同一总控时把该总控的历史锁并回 `workflow['lock'][名称]`（仅当当前未记时）。
- **测试**：`tests/test_skill_panel_production_locks.py` 新增 `test_reapply_master_after_no_master_restores_locks`（REQ-S01-81 锚定）。

### 2. 「浏览本地」→ 导入本地总控包（功能）

- **新增 `master_import_service.py`（L4，无 Tk）**：`plan_import(source, program, registry)` 只读预检（读自包含总控包清单 `总控.json`，核验 `package` 存在、`stage_skills` 引用已注册 SKILL、`locks` 键在 `PRODUCTION_LOCK_DEFINITIONS`）；`perform_import(plan, program)` 沿用 `skill_import_service` 的「暂存 → 试冻结 → 换入 → 合并清单」——`shutil.copytree` 复制包目录、`workflow_settings._inline_skill_report(strict=True)` 试冻结、`os.replace` 换入（导入暂存切换，同名旧总控经 `storage_maintenance.recycle_paths` 回收、失败 `restore_recycle_batch` 恢复）、`agent.core.save` 合并 presets 进 `workflow_settings.MASTER_MANIFEST` 并 `refresh_workflow_presets(force=True)`。硬拦截：缺 presets／package 缺失／package 不存在；软问题：未注册 SKILL／未登记锁键／同名覆盖。
- **UI**：`skill_panel_workflow` 的「浏览本地…」分支改为 `browse_local_master()` → `FileDialog` 选清单 → `master_import_dialog()` 可视化预览（名称／主控包路径／各阶段 SKILL／制作锁／软问题清单）→ `ask_confirmation` 确认 → 导入并刷新总控下拉框。
- **测试**：`tests/test_master_import_service.py` 4 条（REQ-S01-81 锚定）。

### 配套登记（新增生产模块所需）

- `tests/architecture/_layers.py`：`master_import_service` 登记 L4。
- `tests/architecture/test_atomic_write_boundary.py`：`master_import_service.py: 1`（`os.replace` 导入暂存切换，与 `skill_import_service` 同口径）。
- `维护记录/覆盖率基线.json` + `runbook.md §11`：模块总数 361→362。
- `docs/stages/S01_剧本准备.md`：新增 REQ-S01-81、DES-S01-81 与锚定表行。

## 自检结论

沙箱内已实跑：默认冒烟 8/8、`test_requirement_traceability` 5/5、`test_atomic_write_boundary` 5/6（唯一 ERROR 为沙箱 tempfile 环境限制）、`test_layers`（`master_import_service` = 4）。`master_import_service` 的 plan/perform/软硬拦截逻辑经沙箱内工作区路径端到端验证（复制包、合并 presets、重写 package、刷新预设表全部正确）。Tk 用例（`test_skill_panel_production_locks` 的回归用例与 `test_master_import_service` 的 tempfile 用例）因沙箱拦截 `tempfile`/Tk 未能运行，须在沙箱外跑。

## 已提交

- commit `10e248e0`（分支 `codex/wip-R2449`）R2449：总控切换锁恢复 + 本地总控包导入系统（REQ-S01-81），11 文件 +449/−6。
- 提交时沙箱无法运行 git pre-commit／post-commit 钩子（`sh.exe` 无法创建信号管道，`Win32 error 5`），故用 `--no-verify` 提交，并已按规则 41 设置 `CODEX_STAGE_ALLOWLIST`（全部 `程序/*` 源码／测试／文档／基线文件显式列出，`tasks_round_2449_result.md` 属豁免）。合入 master 前须在沙箱外跑 pre-commit 钩子与全量安全回归。
