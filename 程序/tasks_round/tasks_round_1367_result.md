# R1367：O40 项目管理、备份与清理统一空间和恢复说明

类型：功能轮（§3.1；本项为「建议／风险」→ 恢复性与索引重建实现＋回归）。承接 R1267 清单 O40（O01—O39 已完成；依赖的 O38 回收写前日志、O39 版本保护均已落地）。中央轮次 1367（原领 1365 被并行合入的 R1366 顶掉，按 `round_claim.py next` 重新领到 1367；在干净 master 工作树 o07-fullsafe-master 领取）。本轮 1367 − 1364 = 3 < 5，无五轮欠账；但改动触及项目删除语义（回收成功但登记未落盘），命中 §5 全量升级条件，收口在干净 master 工作树跑一次 `--all --safe`。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：新增 `tests/test_project_recovery.py` 8/8；定向 `-k projects project_ backup recovery reconcile desktop storage recycle` 149/149；架构门禁 `--layer architecture --all` 312/312；默认冒烟 `smoke_test.py` 8/8；均为 0 红。全量见「全量判定」。
- 欠账：O40 关闭，清单剩 O41—O48；1367 − last_full_safe_all_round(1364) = 3 < 5，无五轮欠账；但命中 §5 删除语义（项目删除先回收再改登记），收口跑一次干净 master 全量（结果见「全量判定」）。

## 目标（R1267 清单 O40）
- 依据：`projects.py` 删除项目先回收再改登记，已有链接／越界保护；文件清理、项目登记及备份是不同机制。
- 建议：界面区分清屏、删历史、移入回收站、永久清除、可再生缓存；说明同盘回收不等于释放磁盘。登记写失败要能重建索引。
- 验收：项目回收成功但登记写失败、移动项目、恢复重名、仅清登记、从备份恢复分别可恢复；永久清除单独明示，不能把本报告当授权删除。

## 实现（projects.py，L2；desktop.py，L4）
- `_drop_registration_entry(path, *, message=None)`（`projects.py`，新增）：把一条登记移出索引并发布。一律先改 `deepcopy` 再发布，发布成功才提交 `self.info`；`OSError` 时把内存回退到磁盘事实并带上 `ui_message` 重抛。`delete`／`unlink_registered_project`／`clear_missing_registration` 三条删除／清除路径统一改走它——原先它们就地改 `self.info` 再发布，登记写失败会让内存先显示成“已删除”而磁盘仍留着旧条目。
- `_project_write_result`（`projects.py`）：`OSError` 分支优先用 `exc.ui_message` 作结果原因；没有时仍是原通用文案。删除路径据此给出「回收已发生、登记未落盘」的定向指引，而不是一句泛化失败。
- `delete` 的登记失败文案：明确「项目内容已移入回收站，但项目登记未更新：可点『重新查找项目』或『重建项目索引』恢复索引；项目内容仍可从回收站恢复」。`unlink_registered_project`／`clear_missing_registration` 同法各给一条可重试指引。
- `_discover_candidates(base)`（`projects.py`，模块级，新增）：把原 `reconcile_missing` 内联的一级目录扫描（含 `config.json` 或任一阶段骨架目录、排除 `工作流任务` 回收站）抽成复用纯函数；`reconcile_missing` 改为调用它，行为不变。
- `Projects.rebuild_registry()`（新增，L2 写服务结果）：按磁盘事实重建项目索引——保留 `path` 仍存在的登记（含 `status` 与 `created_at`）、移除 `path` 已不存在的失效登记、补登 `_discover_candidates` 扫到但未登记的新目录；`active` 失效时落到首个有效项目或 `None`；无变化时返回 `changed=False` 且不写盘。只读写一级目录与登记文件，不移动、不删除任何项目内容，回收站永不回流。
- `Desktop.rebuild_project_index()`（`desktop.py`，L4，新增）：调 `rebuild_registry` 后 `reload()` 刷新两处项目树，状态栏报告「补登 N 个、移除失效 M 个（未改动磁盘文件）」；`project_home` 增加「重建项目索引」按钮。
- `project_home` 说明文案：把「删除项目＝移入项目库回收站（可恢复，不是永久清除）；同一块磁盘上回收不等于释放空间；登记与磁盘不一致时点『重建项目索引』；可再生缓存由自动清理单独回收」写进状态栏，界面层面把清屏／删历史／移入回收站／永久清除／可再生缓存分开表述。
- 删除确认框文案补「（可恢复，不是永久清除；同一块磁盘上回收不等于释放空间）」。

## 契约变化与同步
- `clear_missing_registration` 的失败语义变严：登记写失败时内存与磁盘登记都保持删除前状态（不再出现内存先清、磁盘后留的不一致），失败仍以 `SystemError` 上抛、桌面降级为可重试提示（`tests/test_project_rename_reconcile.py` 既有断言不变）。
- 新增 L2 公开方法 `rebuild_registry`（返回 `{kept, dropped, added, changed}`）；只增不改既有 `delete`／`unlink_registered_project`／`clear_missing_registration`／`reconcile_missing` 的对外形态。
- `reconcile_missing` 的扫描逻辑搬进 `_discover_candidates`，返回结构与匹配规则完全不变（既有 `tests/test_project_rename_reconcile.py` 全绿）。
- 未新增顶层模块（`tests/architecture/_layers.py` 未动）；未新增裸 `json.loads`／L2 直写／`skipTest`／动态导入；未改启动路径与 Tk 控件生命周期（只新增普通按钮与状态栏文案）。

## 验证
- 新增 `tests/test_project_recovery.py` 8 条：①项目回收成功但登记写失败——内容确在项目库回收站且 `restore_recycle_batch` 能完整恢复，内存与磁盘登记都停在删除前事实，结果原因含「回收站」「重建项目索引」；②`rebuild_registry` 移除失效登记并补登新目录、写回磁盘；③登记与磁盘一致时 `changed=False` 不写盘；④`clear_missing_registration` 只清登记、目录仍存在时拒绝、磁盘目录始终不动；⑤恢复重名——原位置被同名目录占用时 `restore_recycle_batch` 零移动（内容仍留回收站），占用者改名后可完整恢复；⑥项目层源码无 `rmtree`／`unlink()`，删除只走 `recycle_paths`；⑦确认框与主页文案把「移入回收站」与「不是永久清除／回收不等于释放空间」分开表述；⑧桌面 `rebuild_project_index` 解包结果、刷新并报告计数。
- 定向 `-k projects project_ backup recovery reconcile desktop storage recycle` 149 条 0 红（含 `test_projects.py`／`test_project_rename_reconcile.py`／`test_project_open.py`／`test_project_stages.py`／`test_recycle*.py`／`test_storage.py` 与相关架构边界）。
- 架构门禁 `--layer architecture --all` 312/312（0 红，与基线一致）。默认冒烟 `smoke_test.py` 8/8。

## 边界
- 「从备份恢复」本轮按「项目库回收站即删除前的可恢复副本」实现与验证（`restore_recycle_batch` 可完整还原被删项目）；未新建独立项目备份子系统（那属新授权范围）。程序级 `升级备份`／分镜历史版本是另一条既有机制，本轮不改、也不合并口径。
- 「永久清除」只做界面层面单独明示（确认框与主页文案），**未新增任何永久删除入口**：`projects.py` 只回收（`recycle_paths`），无 `rmtree`／`unlink()`；本报告不作为永久删除授权。
- `rebuild_registry` 以「路径是否存在」判定保留，被手工移动的项目会作为新目录补登、丢失原 `status`；要保留状态请用「重新查找项目」（`reconcile_missing`，按分镜指纹认领），两条路径各司其职、本轮未统一。
- 未实机点击桌面「重建项目索引」按钮；桌面测试用注入式登记（方案与服务层同源），未在真实 Tk 里验收布局。
- 未改 `storage_maintenance.py` 的回收写前日志／回滚语义（O38 已覆盖），也未改 O39 的版本保留口径。

## 全量判定
- 1367 − last_full_safe_all_round(1364) = 3 < 5，无五轮欠账；但本轮改 `projects.py` 的项目删除语义（回收成功、登记未落盘的可恢复性）且新增删除相关 UI 入口，命中当次全量升级条件，收口必须跑一次干净 master 全量。
- 复用检查：`.git/full-safe-receipts.json` 现有最近绿凭据为 round=1364、tree=0db16c0f…（2026-10-12，7 日内），但本轮改了 `projects.py`／`desktop.py`／测试，`HEAD:程序` 内容树不同，不能复用。
- 全量结果：第 1 次在干净 master 工作树 `o40-fullsafe-master`（新建，未初始化 4 个嵌套仓库与 3 个被忽略的运行文件）跑 `--all --safe` 出现假红：`skills`／`writing`／`idea` 系用例因 `SKILL 引用缺失`（`screenplay-gate-engine.md` 不存在）与 `维护记录/基准历史.json` 缺文件而红，定位为**工作树环境未就绪，非本轮代码问题**。先按已知可用的 `o07-fullsafe-master` 环境把 4 个嵌套仓库（`程序/reference/HoLLMwood`、`程序/skills/00全流程SKILL/AIGC创作全流程`、`程序/skills/01 剧本准备SKILL/剧本锻造`、`程序/skills/01 剧本准备SKILL/编剧技能集`）与 3 个被忽略运行文件（`程序/logs/`、`程序/projects.json`、`程序/维护记录/基准历史.json`）补齐，定向复验受影响的 13 个模块全绿，再跑**第 2 次全量** `--all --safe`：**4859/4859、0 红、527.6 秒**。凭据已写 `.git/full-safe-receipts.json`：`round=1367`、`tree=1d7630f1df3ce72658d1918650741760e16e7f38`（已核对 ＝ `HEAD:程序`）、`at=2026-10-12T15:40:10`，`last_full_safe_all_round=1367`。`test_desktop_startup_perf`／`test_perf_baseline` 本轮均绿，未出现阈值抖动。

## 提交
- 本轮改动：`程序/projects.py`、`程序/desktop.py`、`程序/tests/test_project_recovery.py`（新）、`程序/tasks_round/tasks_round_1367_result.md`（新）、`程序/project_status.md`、`.agent-handoff/{snapshot,work-log,validation,backlog,risks}.md`。
- 提交状态：内容提交 `4494ab3`（只含本轮 10 个文件；未含主树他人已暂存的 `程序/idea_chat.py`／`程序/idea_attachments.py`／`程序/配置/SKILL/预设.json`）。全量结果（4859/4859、tree=1d7630f1）由紧随其后的收尾提交记入本报告、`project_status.md` 与接力文件（沿用同一轮次 R1367，中央 `last_claimed` 仍为 1367）。O40 原领 1365 被并行合入的 R1366（阶段④分集增量上下文）顶掉，按 `round_claim.py next` 重新领到 1367。
