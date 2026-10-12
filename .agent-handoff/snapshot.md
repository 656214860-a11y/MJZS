# 当前快照

## 2026-10-12：O38 完成，继续 O39

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O37 已完成，**O38 已完成（R1363）**，下一项 O39（清理旧视频前必须保护被采用及被引用版本，P1／事实·风险，M，依赖 O18、O38）。
- O38（回收批次写前日志及失败恢复）：`storage_maintenance.py`（L1）新增 `MANIFEST_NAME`／`BATCH_PREFIX`／批次态 `BATCH_PLANNED|BATCH_COMMITTED|BATCH_ROLLED_BACK`／逐项态 `ITEM_PLANNED|ITEM_MOVED|ITEM_FAILED|ITEM_UNDONE`，新增 `batch_name`（秒级时间＋UUID8，同秒并发各自成批）、`_write_batch_manifest`（原子落盘）、`plan_recycle`（写前计划）、`move_planned`、`_undo_moves`（按「文件是否真的在回收站」撤回，含中断时仍记 planned 的项）、`rollback_recycle_batch`（撤回未提交批次，committed 拒绝）；`recycle_paths` 重写为「写前计划先落盘 → 逐项移动并随时落盘 → 全成功写 committed；任一项失败记 failed 与原因、撤回本批已搬项、落 rolled_back、原异常原样重抛」；`restore_recycle_batch` 对 planned／failed 且回收站确无该文件的记录不再阻挡同批；`restore_latest_recycled_path`／`restore_latest_recycled_child` 跳过 rolled_back 批次；`clean_project` 走同一写前计划并逐项落盘。见 [R1363](../程序/tasks_round/tasks_round_1363_result.md)。
- 契约变化：每次 `recycle_paths` 调用生成独立 UUID 批次（不再把同一秒的多次调用并进同一份清单）；多路径调用由「可能部分成功」改为整批原子（任一项失败整批撤回），单路径调用语义不变；批次名仍以 `自动维护_` 开头，「最新批次」排序与筛选前缀不变。
- 需迁移的断言：`tests/test_pet_report.py` 周报保留期用例原断言「同一份清单里 2 条」（旧同秒合并行为）改为「两条过期日报都进回收站且可原样恢复」；生产调用方 `pet_report.prune` 未改。
- 验证证据：新增 `tests/test_recycle_write_ahead.py` 9/9；`tests/test_pet_report.py` 71/71；定向 `-k recycle storage retention deletion_gateway remove_authority exit_maintenance force_quit pet_report video_ui` 213/213；删除调用方 `-k asset keyframe storyboard projects skill_panel stage_execution codex_skill reference_images` 441/441；架构 `--layer architecture --all` 312/312；默认冒烟 `smoke_test.py` 8/8；0 红。
- 全量：1363−1361=2<5 无五轮欠账，但改动命中 §5（删除语义 `storage_maintenance.py`），收口在干净 master 工作树 `o07-fullsafe-master` 跑 `--all --safe`：第 1 次 4832/4832、0 红、425.6 秒，凭据 `round=1363`、`tree=f19816aa…`（＝`HEAD:程序`），`last_full_safe_all_round=1363`。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`、`.codex/`、`.agent-handoff/archive/`、`程序/outputs/`、`程序/配置/宠物/配置.json`，不读取、不修改、不暂存、不覆盖；提交只点名自己的路径，绝不 `git add -A`。
- 干净 master 工作树：`o07-fullsafe-master`（与主树共享 git common dir；勿动 `o06-fullsafe*` 等）；领号／全量前先 `git reset --hard HEAD`。
- 轮次：R1363 已在干净 master 工作树领到；`project_status.md` 的 `当前轮次` 已改为 1364（＝最新结果报告号＋1）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟 `smoke_test.py`；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`），并先查 `full-safe-receipts.json` 有无 7 天内同 `HEAD:程序` 内容树绿凭据可复用，只有命中 §5（启动路径／Tk 控件生命周期／删除语义／层级登记表）才强制重跑；全量失败先按定位文件定向修绿、只复验一次（报告写「第 N 次全量」，2 次仍不过就升级单独修复轮）；`test_desktop_startup_perf`／`test_perf_baseline` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
