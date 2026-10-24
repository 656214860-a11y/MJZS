# R2020 在 master 上合入 codex/wip-R2017（合并轮）

轮次类型：合并轮（行为零变化；冲突只做两边记录并存）。日期：2026-10-25。

三套基线（合并后，在主目录 master 工作区）：
- 默认冒烟：工作树预演 8/8（合并 03754a6c 时）；合入 R2018 后的最终树未重跑。
- 架构门禁 `smoke_test.py --architecture`：410 条，仅剩 `test_full_safe_all_is_required_after_eight_source_rounds` 一条红（R2018 欠一次完整安全全量，主干历史问题，合并提交的 post-commit 钩子会后台补跑；本轮不手动全量）。此前在工作树里看到的 3 条红（`test_agents_md`、`test_skill_reference_injection`、旧 `test_round_baselines`）是工作树缺 `00全流程SKILL/AIGC创作全流程` 嵌套仓库造成，主目录无此问题。
- 覆盖率基线：319 个模块、50 个有行覆盖（`runbook.md` §11 同步）。

债务变化：模块行数棘轮被动抬高两处（见下）；`--all --safe` 本轮未运行；未 push。

## 合并内容

- 分支 `codex/wip-R2017`（J3–J7、R2013、R2015、R2017：结构治理＋旧名转发退役）并入 master（a752a217，含 R1990…R2019 的全部功能轮，其中 R2018 强制登录进入主界面）。工作树里 `git merge master` 会被“只有 master 可更新 project_status.md”拦下，所以与 R2016 一样改在主目录 master 上合入；先在工作树里做过一次完整冲突预演（合 03754a6c），最终在主目录对 a752a217 重做。
- 冲突处理（5 个文件）：
  - `desktop.py`：`class Desktop(AutoStateHolderMixin, AccountPageMixin, LoginGateMixin, MasterUpdateMixin, …)`；`__init__(self,win,root=ROOT,*,require_login=False,**page_services)` 配分支的 `_init_window_and_sidebar(win, root, page_services)`（master 旧签名里的 `script_page_services` 形参已随分支重构并入 `page_services`）。
  - `architecture.md`：L3／L4 两行按词块做三方合并（基点＝合并基），无冲突；R2017 旧名退役句、master 的 `desktop_master_update`／`master_skill_update`／登录闸门说明都在。
  - `runbook.md` §11：模块数／未覆盖数按合并后基线重算。
  - `维护记录/覆盖率基线.json`：以分支为底，master 在基点之后改过且分支未改的模块取 master 条目，并集后按 `(percent, module)` 排序。
  - `tasks_round_2006_result.md`：同号冲突（master 的“总控更新提示改简明可读”与分支的“Pet 播报状态下沉”），两份记录并存于同一文件。

## 行数棘轮（被动抬高，非本轮新增代码）

- `ui_widgets.py` 上限 1383→1425：master 的 R2002／R2007 把它推到 1425 行，master 当时上限是 1500，并入 1000 行上限后才暴露。
- `desktop.py` 上限 1375→1377：多了 `from desktop_master_update import MasterUpdateMixin` 与 master 登录闸门接口的两行。
- 两处都应由后续拆分轮下调，建议先把 `ui_widgets.py` 里的 NoticeDialog／下拉占位拆出。

## 验证

- 定向 825 条（`login_gate`、`pet_ui`、`desktop_auto_state`、`page_navigation`、`coverage_baseline`、`master_skill_update`、`desktop_automation`、`req_s07`、`pet_broadcast`、`core`）只剩 `test_pet_ui` 两条红：`test_it_opens_the_unattended_switch_then_starts_the_step` 与云朵几何 `test_the_cloud_stands_left_of_the_pet_with_its_bottom_lined_up`。同样用例在合并前的 master（a752a217，临时 worktree）上是 6 条红，这两条都在其中；合并后 R2017 的迁移让另外 4 条登录闸门红转绿。断言未动。
- 在工作树预演（03754a6c）里：`test_ui_edges` 把 `master_skill_update.check` 打成离线后 115 条全过；不打桩时，首帧 `after` 里的 `start_master_update_check`（`desktop_automation_tick._after_first_paint` 排程）会真联网，遇到“有新版本”弹确认窗卡住隐藏桌面（主目录 master 上同一文件跑出 115 条、110 秒、1 红 `BriefTintTests`，是否撞上取决于网络返回）。这是 master 侧的测试隔离缺口，非合并引入，建议另起一轮给测试套件统一离线桩。
- `project_status.md` 校验（合并提交前对暂存区执行，合并基点即 master 本身）：
  - `git diff --cached a752a217 -- 程序/project_status.md | grep '^-' | grep -v '^---' | grep -v '当前轮次：'` → 输出为空。
  - `git show :程序/project_status.md | grep -oE '^R[0-9]+' | sort -u` → 100 个轮次号，与 a752a217 的一致（分支不改 `project_status.md`，并集即 master 全部记录）。
- 未运行：`--all --safe`（合并提交会触发后台补跑）；真实界面目测；合并后重跑默认冒烟。
