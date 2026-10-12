# R1363：O38 回收批次需要写前日志及失败恢复

类型：功能轮（§3.1；本项为「事实／风险」→ 可靠性实现＋回归）。承接 R1267 清单 O38（O01—O37 已完成）。中央轮次 1363（在干净 master 工作树 o07-fullsafe-master 领取）。本轮 1363 − 1361 = 2 < 5，无五轮欠账；但改动命中 §5 全量升级条件（删除语义 `storage_maintenance.py`），收口在干净 master 工作树跑一次 `--all --safe`。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：新增 `tests/test_recycle_write_ahead.py` 9/9；更新 `tests/test_pet_report.py` 71/71；定向 `-k recycle storage retention deletion_gateway remove_authority exit_maintenance force_quit pet_report video_ui` 213/213；删除调用方 `-k asset keyframe storyboard projects skill_panel stage_execution codex_skill reference_images` 441/441；架构门禁 `--layer architecture --all` 312/312；默认冒烟 `smoke_test.py` 8/8；均为 0 红。全量见「全量判定」。
- 欠账：O38 关闭，清单剩 O39—O48；1363 − last_full_safe_all_round(1361) = 2 < 5，无五轮欠账；但命中 §5 删除语义，收口跑一次干净 master 全量（结果见「全量判定」）。

## 目标（R1267 清单 O38）
- 证据：`storage_maintenance.py:78` 逐个移动文件，全部移动后才保存 manifest；中途异常缺少整批回滚／提前落盘记录。
- 影响：第二个文件移动或最后清单写入失败时，前面已移动内容可能没有有效恢复清单；批次名称的秒级时间也需在并发测试中核对。
- 建议：UUID 批次、写前计划、逐项状态、最终提交；中断后可恢复／撤回。复用已有恢复边界检查，不整体重写回收系统。
- 验收：每一步注入失败、占用文件、磁盘满、进程中断和并发回收，原文件或恢复记录至少一方完整可用；不永久删除。

## 实现（storage_maintenance.py，L1）
- 新增常量：`MANIFEST_NAME`＝「恢复位置.json」、`BATCH_PREFIX`＝「自动维护_」、批次态 `BATCH_PLANNED`／`BATCH_COMMITTED`／`BATCH_ROLLED_BACK`、逐项态 `ITEM_PLANNED`／`ITEM_MOVED`／`ITEM_FAILED`／`ITEM_UNDONE`。
- 新增 `batch_name(now)`：秒级时间给人看，UUID8 后缀保证同一秒并发也各成一个独立批次。
- 新增 `_write_batch_manifest`（经既有 `agent.core.save` 原子落盘，含 `created_at`／`reason`／`state`／`items`）、`plan_recycle`（写前计划：只算这一项该去哪，越界／链接／不存在／目标已占一律返回 None，不移动文件）、`move_planned`（按计划移动并把状态改 `moved`）、`_undo_moves`（按「文件是否真的在回收站」撤回 `moved` 与中断时仍记 `planned` 的项；被占用或已不在的跳过，绝不覆盖用户新文件）。
- `recycle_paths` 重写：写前计划先落盘（state=planned、逐项 status=planned）→ 逐项移动并在每项后落盘（逐项状态）→ 全部成功写 `committed`；任一项 `OSError` 时把该项记 `failed` 与 `异常名：原因`、撤回本批已搬项、落 `rolled_back`、再把原异常原样重抛。始终只移动，不永久删除。
- `read_recycle_batch` 返回体增加 `state` 键（纯追加，既有键不变）。
- `restore_recycle_batch`：在既有的越界／链接／占用／嵌套校验之前，对 `status` 为 `planned`／`failed` 的记录，只要回收站里确实没有该文件就跳过——不让一条没搬成的记录挡住同批其余项；其余边界检查与回滚语义不变。
- 新增 `rollback_recycle_batch(root, batch)`：撤回一个中断／未提交的批次（把已搬项移回原位）；只认有 `state` 的写前批次，`committed` 拒绝并提示改用恢复，项目范围校验复用 `_restore_location` 与回收站边界检查。
- `restore_latest_recycled_path`／`restore_latest_recycled_child`：跳过 `state=rolled_back` 的批次（已撤回的批次不是可恢复内容），其余排序与匹配不变。
- `clean_project`：批次名改用 `batch_name(now)`，内部回收改为「写前计划 → 逐项落盘 → 全部完成写 `committed`」；单项移动失败如实记 `failed` 与原因后再抛出，其余项按调用方既有 `except OSError: continue` 继续清理。

## 契约变化与同步
- 每次 `recycle_paths` 调用生成独立 UUID 批次；不再把同一秒的多次调用并进同一份清单（旧行为正是并发回收的竞态来源）。批次名仍以 `自动维护_` 开头，「最新批次」排序与筛选前缀不变。
- 多路径调用由「逐项移动、可能部分成功」改为「整批原子」：任一项失败整批撤回并原样重抛；单路径调用语义与既有断言不变。
- 需迁移的调用方断言：`tests/test_pet_report.py` 周报保留期用例原断言「回收清单里恰好 2 条」（依赖旧的同秒合并），改为「两条过期日报都进了回收站且能原样恢复」。生产调用方 `pet_report.prune` 未改（仍逐项调用，只是不再共享清单）。
- 未新增顶层模块，`tests/architecture/_layers.py` 未动；未新增裸 `json.loads`、L2 直写、`skipTest`、动态导入，`架构统一基数.json` 无需改动（本轮无新增扫描命中，ratchet 复验通过）。

## 验证
- 新增 `tests/test_recycle_write_ahead.py` 9 条：写前计划在任何移动之前就已落盘且逐项状态随移动推进（第一次移动前＝planned/planned，第二次移动前＝moved/planned，最终 committed/moved,moved）；第二项被占用（PermissionError）时整批回滚、原异常 errno 原样、清单 rolled_back、回收站里除清单无残留、`restore_latest_recycled_path` 不再把它当可恢复；磁盘满（ENOSPC）同样整批回滚；「两项都搬完但未写 committed」的中断批次既可 `rollback_recycle_batch` 全部移回、也可 `restore_recycle_batch` 全部恢复（按文件是否真在回收站判定）；`committed` 批次拒绝撤回；同一秒两次回收得到两个独立批次且各自可恢复；`clean_project` 走写前计划（history 目录进回收站、清单 committed、原目录已不在）。
- 更新 `tests/test_pet_report.py`：71/71（含周报保留期用例的新断言）。
- 定向 `-k recycle storage retention deletion_gateway remove_authority exit_maintenance force_quit pet_report video_ui` 213 条 0 红（含 `test_recycle.py`／`test_recycle_restore.py`／`test_recycle_directories.py`／`test_recycle_recovery_service.py`／`test_asset_batch_retention.py`／`test_storage.py` 与架构删除门禁 `test_deletion_gateway`／`test_remove_authority`／`test_recycle_service`）。
- 删除调用方 `-k asset keyframe storyboard projects skill_panel stage_execution codex_skill reference_images` 441 条 0 红。
- 架构门禁 `--layer architecture --all` 312/312（0 红，与基线一致，无新增／删除架构测试）。默认冒烟 `smoke_test.py` 8/8。

## 边界
- 写前计划／逐项状态只保证「文件或清单至少一方完整可用」：中断发生在「移完、清单还没更新」之间时，清单仍写 planned，恢复按「文件真的在回收站」判定可还原，撤回也会把它移回；不会出现「文件搬走却没有恢复记录」。
- `recycle_paths` 改为整批原子后，依赖「能搬几条算几条」的调用方需自行改成分多次单路径调用；本轮生产调用方均未依赖该部分成功语义。
- `rollback_recycle_batch` 只落在 L1 权威模块；服务层（`recycle_recovery_service`）与桌面回收站 UI 未新增撤回入口，也未实机验收桌面交互——本轮范围边界，不假称已覆盖。
- 真实磁盘满／真实文件占用（Windows 句柄）下的恢复体验未实机验收；注入式失败覆盖的是同一失败路径。
- 未新增 skipTest／裸 json.loads／L2 直写／动态导入；未改启动路径、Tk 控件生命周期、层级登记表。

## 全量判定
- 1363 − last_full_safe_all_round(1361) = 2 < 5，无五轮欠账；但本轮直接改 `storage_maintenance.py`（§5 明列「删除语义」），命中当次全量升级条件，收口必须跑一次干净 master 全量。
- 复用检查：`.git/full-safe-receipts.json` 现有最近绿凭据为 round=1361、tree=3e20f7c4…（2026-10-12T14:00:08，7 日内），但本轮改了 `storage_maintenance.py` 与测试，`HEAD:程序` 内容树不同，不能复用。
- 全量结果：见收尾记录（干净 master 工作树 `o07-fullsafe-master`，`run_selftests.py --all --safe`）。

## 提交
- 本轮改动：`程序/storage_maintenance.py`、`程序/tests/test_recycle_write_ahead.py`（新）、`程序/tests/test_pet_report.py`、`程序/tasks_round/tasks_round_1363_result.md`（新）、`程序/project_status.md`、`.agent-handoff/{snapshot,work-log,validation,backlog,risks}.md`。
- 提交状态：见下方收尾提交记录。
