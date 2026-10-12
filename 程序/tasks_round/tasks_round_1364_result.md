# R1364：O39 清理旧视频前必须保护被采用及被引用版本

类型：功能轮（§3.1；本项为「事实／风险」→ 可靠性实现＋回归）。承接 R1267 清单 O39（O01—O38 已完成；依赖的 O18 来源账本、O38 回收写前日志均已落地）。中央轮次 1364（在干净 master 工作树 o07-fullsafe-master 领取）。本轮 1364 − 1363 = 1 < 5，无五轮欠账；但改动命中 §5 全量升级条件（删除语义 `storage_maintenance.py`），收口在干净 master 工作树跑一次 `--all --safe`。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：新增 `tests/test_video_retention.py` 12/12；定向 `-k storage exit_maintenance force_quit integration core video edit retention adaptation cleanup recycle pet_report` 536/536；架构门禁 `--layer architecture --all` 312/312；默认冒烟 `smoke_test.py` 8/8；均为 0 红。全量见「全量判定」。
- 欠账：O39 关闭，清单剩 O40—O48；1364 − last_full_safe_all_round(1363) = 1 < 5，无五轮欠账；但命中 §5 删除语义，收口跑一次干净 master 全量（结果见「全量判定」）。

## 目标（R1267 清单 O39）
- 证据：`storage_maintenance.py`：旧目录与超过期限的非最新非 pending 视频进入回收，判断时未查询最终剪辑／采用引用；递归台账还需排除回收区。
- 建议：按成果引用图标记保留，保护采用版本、剪辑来源、交付引用、未结算任务、用户锁定版本；先给可回收原因及保留原因。恢复区不能再次当生产目录递归处理。
- 验收：最新失败但旧版采用、剪辑引用旧版、回收站里含旧台账、待结算任务全部受保护；真正无引用旧版才入候选。

## 实现（storage_maintenance.py，L1）
- 新增常量：`EXPORT_MANIFEST_NAMES`＝(edit_bundle.json, edit_manifest.json)（成片清单文件名权威在 engine（L3），L1 不得向上导入，故在此复名，并用架构测试锁死与 engine 常量一致，避免漂移）、`SETTLED_STATES`＝frozenset(downloaded, failed, rejected)、保留原因 `RETAIN_UNSETTLED`／`RETAIN_LOCKED`／`RETAIN_EDIT_SOURCE`／`RETAIN_APPROVED`／`RETAIN_LATEST`／`RETAIN_FRESH` 与 `RETAIN_REASONS`（中文说明）、`VERSION_CLEAN_REASON`（可回收原因）。
- 新增 `edit_source_versions(root)`：只读 `13质检交付/导出成片` 下的已发布成片清单（`edit_bundle.json` 优先，老成片退回 `edit_manifest.json`），返回被引用的 `(镜头, 版本)` 与 `(镜头, sha256)`；读不动或不是清单的条目跳过；只读、不重写、不删除成片记录。
- 新增 `version_retention(version, shot, newest, referenced, digests, now)`：返回保留原因，可回收时空串。保留口径（任一成立）：任务未结算（state 在 `PENDING`，或不属 `SETTLED_STATES`，含空状态）／用户锁定（`locked`）／已进入已发布成片来源（按 `(镜头, 版本)` 或 `(镜头, sha256)` 命中）／已验收通过（`review==pass`，含无人值守自动放行——「最新失败但旧版采用」必须留住旧版）／该镜头最新版本／不足保留期（`created` 缺失按「未到期」保守留住）。
- `clean_project` 的版本清理循环：开始时取一次成果引用图；台账扫描范围排除回收区（`工作流任务/回收站` 里的旧台账不再当生产目录递归处理，也不会去碰回收站里的内容）；逐版先问 `version_retention`，只有真正无引用的过期旧版才 `recycle`，回收后除原有 `cleaned_at`／`file=None`／`qc_pass=False` 外，另写 `cleaned_reason`（可回收原因，可追溯）。
- 保留原因与可回收原因都由同一个纯函数给出，可直接断言；本轮不新增 UI 入口（自动清理仍是退出后后台执行）。

## 契约变化与同步
- 版本清理变得更保守：新增 4 类保护（成片来源引用／已验收通过／用户锁定／非定局状态）。原先会被清掉的「已过期且非最新、非 pending」旧版中，只要被采用或已进成片，现在一律保留。
- `AGE_SECONDS`（7 天保留期）与「每镜最新版必留」不变；`PENDING`（queued／running／succeeded／unknown／submitting）语义不变，另把未知状态并入未结算。
- 只读成片清单，不改 engine 的剪辑／采用口径（`approved_versions`／`adopted_edit_version` 未动）；未新增跨层导入（L1 只依赖 L0 `project_stages` 与 L1 `file_cache`）。
- 未新增顶层模块，`tests/architecture/_layers.py` 未动；未新增裸 `json.loads`（统一走 `file_cache.read_json`）／L2 直写／`skipTest`／动态导入。

## 验证
- 新增 `tests/test_video_retention.py` 12 条：`version_retention` 六种保留原因逐一（未结算含空状态／锁定／成片来源按版本或按 sha256／已验收通过／最新版／不足 7 天且缺 `created` 保守留住）与「只有定局且无引用的过期旧版才可回收」；`EXPORT_MANIFEST_NAMES` 与 engine 的两个清单名一致；`edit_source_versions` 同时读懂 `edit_bundle.json`（取 `manifest`）与老成片 `edit_manifest.json`（顶层数组）并忽略垃圾条目、没有成片目录时返回空；`clean_project` 端到端四例——最新失败但旧版采用时两版都留、无引用的过期旧版进回收站且版本记录写下 `cleaned_reason`、成片清单引用保护旧版、锁定／queued／unknown 全部留住、回收站里的旧台账不再被当生产目录处理（文件留在回收站、不产生新批次、不改写那份台账）、坏台账跳过不动任何文件。
- 定向 `-k storage exit_maintenance force_quit integration core video edit retention adaptation cleanup recycle pet_report` 536 条 0 红（含 `test_storage.py`／`test_exit_maintenance.py`／`test_integration.py`／`test_core.py`／`test_video*.py`／`test_edit*.py`／`test_recycle*.py`／`test_pet_report.py` 与相关架构边界）。
- 架构门禁 `--layer architecture --all` 312/312（0 红，与基线一致）。默认冒烟 `smoke_test.py` 8/8。

## 边界
- 成片来源只在 `13质检交付/导出成片` 下找：该目录被删、或成片在别处产出时引用保护失效；不猜测外部剪辑产物，也不据此反推版本。
- 「用户锁定版本」按版本记录的 `locked` 标记保留；当前产品还没有写这个标记的入口，属向前兼容（测试用注入验证），不假装已有用户可见的锁定按钮。
- 「交付引用」由「已发布成片清单」覆盖：用户手工导入的整集成片是整段文件，不按镜头版本引用，因此不参与版本保护。
- 未实机验收退出清理的桌面体验；自动清理仍是退出后后台执行。未改变 `recycle` 的写前日志／回滚语义（O38 已覆盖）。
- 未新增 skipTest／裸 json.loads／L2 直写／动态导入；未改启动路径、Tk 控件生命周期、层级登记表。

## 全量判定
- 1364 − last_full_safe_all_round(1363) = 1 < 5，无五轮欠账；但本轮直接改 `storage_maintenance.py`（§5 明列「删除语义」），命中当次全量升级条件，收口必须跑一次干净 master 全量。
- 复用检查：`.git/full-safe-receipts.json` 现有最近绿凭据为 round=1363、tree=f19816aa…（2026-10-12T14:44:12，7 日内），但本轮改了 `storage_maintenance.py` 与测试，`HEAD:程序` 内容树不同，不能复用。
- 全量结果：见收尾记录（干净 master 工作树 `o07-fullsafe-master`，`run_selftests.py --all --safe`）。

## 提交
- 本轮改动：`程序/storage_maintenance.py`、`程序/tests/test_video_retention.py`（新）、`程序/tasks_round/tasks_round_1364_result.md`（新）、`程序/project_status.md`、`.agent-handoff/{snapshot,work-log,validation,backlog,risks}.md`。
- 提交状态：见下方收尾提交记录。
