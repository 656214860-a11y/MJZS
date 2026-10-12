# 当前快照

## 2026-10-12：R1335 并入 master（阶段④分集增量上下文）
- 分支 `codex/episode-incremental-context` 已合入 master。`script_contract.split_script_episodes`＋分集账本 `write_dir(project,'script')/剧本分集增量账本.json`（每集 sha256＋based_on 其余集快照）；`writing_api.reply()` 前注入「只贴改动集正文」、唯一发布点 `_save_formal_script()` 后更新账本；`workflow_tasks._episode_change_notice()` 只给本地 Agent 报集号；首次／无账本退化为全量。见 [R1335](../程序/tasks_round/tasks_round_1335_result.md)。
- 未改 `skills/01 剧本准备SKILL/pipeline-script-preparation.skill.md` 与 `structure_script()` 场次解析。
## 2026-10-12：O42 完成，继续 O43

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O41 已完成，**O42 已完成（R1369）**，下一项 O43（自动流程统一检查点版本、幂等和恢复预览，P2／建议·验证，M）。
- O42（事件队列背压、异常容量和关闭释放）：`pet_bus.py`（L0）新增 `PENDING_LIMIT=1024`／`ERROR_LIMIT=64`／`ERROR_PERSIST_LIMIT=128`／`SHEDDABLE_EVENTS=('stage.executing','notify.aggregate')` 与 `is_sheddable(kind)`；`Bus.__init__` 新增 `pending_limit`／`error_limit`／`shed`／`errors_total`／`water`／`_queued`／`_lock`；`Bus.publish` 入队前按幂等键合并重复上报（记 `dropped`），待处理数 ≥ `pending_limit` 时只让 `SHEDDABLE_EVENTS` 让路（记 `shed`），**终态（stage.completed／stage.failed／script.completed／delivery.ready／各 `*task.failed`）与 `stage.paused`（带并发号归还）永不因背压丢弃**；`pump` 出队即 `_dequeued`；`_deliver` 异常走 `_record_error`（有界环形＋`errors_total`＋`bus.subscriber.error` 持久诊断，按 `ERROR_PERSIST_LIMIT` 封顶）；新增只读 `pending`／`water`／`stats()` 与 `unsubscribe`／`release`。未改 `pet_ui`／`pet_agent`／`pet_state`／`stage_flow`／`desktop`，未改事件契约。见 [R1369](../程序/tasks_round/tasks_round_1369_result.md)。
- O42 契约变化：`CONTRACT`／`event`／`identify`／`emit_safe` 不变；`touched`／`dropped` 语义不变（`test_pet_bus` 既有 18 条照旧通过）；默认参数、水位以下、非重复场景的入队与分发逐字不变；未新增顶层模块／裸 `json.loads`／L2 直写／`skipTest`，未改 `维护记录/架构统一基数.json` 与 `TODO注释快照_20261003.json`（`pet_bus.py` 无冻结关键词注释，新增行不引起行号漂移）。
- O42 验证证据：新增 `tests/test_pet_bus_backpressure.py` 15/15；定向 `-k pet_bus pet_agent pet_state stage_flow skill_orchestrator` 186/186；主消费者 `-k test_pet_ui test_pet_cloud` 606/606；架构 `--layer architecture --all` 312/312；默认冒烟 `smoke_test.py` 8/8；0 红。
- O42 测量（合成风暴）：重复上报 200000 条 → `qsize()==1`、0.50 µs/条；不同事件 50000 条 `publish` 11.45 µs/条、`pump` 2.95 µs/条（每拍 200 条约 0.6 ms）；订阅者异常 20000 次 → `len(errors)==64`、`errors_total==20000`。结论：能撑大内存的两条路径（重复上报、异常累积）已受控且可测；不同事件队列规模由生产者事件数决定，未观测到线上泄漏，故不做有损丢弃。
- O42 全量：1369−1368=1<5 无五轮欠账且未命中 §5，收口在干净 master 工作树跑一次 `--all --safe`：全量结果待收尾补记。

## 2026-10-12：O40 完成（历史）

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O40 已完成（见上一节）。
- O40（项目管理、备份与清理统一空间和恢复说明）：`projects.py`（L2）新增 `_drop_registration_entry`（登记移出索引一律先改 deepcopy、发布成功才提交 `self.info`；`OSError` 时内存回退到磁盘事实并带 `ui_message` 重抛），`delete`／`unlink_registered_project`／`clear_missing_registration` 三条删除／清除路径统一改走它，删除路径在登记写失败时给出「内容已移入回收站、点『重新查找项目』或『重建项目索引』、仍可从回收站恢复」的定向指引；新增模块级 `_discover_candidates`（把 `reconcile_missing` 的一级目录扫描抽出复用、行为不变）与 `Projects.rebuild_registry`（按磁盘事实保留仍在的登记、移除失效登记、补登新目录；无变化不写盘；只读写一级目录与登记文件，不移动也不删除任何项目内容，回收站永不回流）。`desktop.py`（L4）新增 `Desktop.rebuild_project_index` 与主页「重建项目索引」按钮，主页状态栏与删除确认框把清屏／删历史／移入回收站／永久清除／可再生缓存分开表述（移入回收站＝可恢复、不是永久清除、同盘回收不等于释放空间）。见 [R1367](../程序/tasks_round/tasks_round_1367_result.md)。
- 契约变化：删除／清除路径的登记写失败不再让内存先显示成「已删除」（内存与磁盘登记都停在删除前状态）；新增 L2 公开方法 `rebuild_registry`（返回 `{kept,dropped,added,changed}`）；「永久清除」只做界面单独明示，**未新增任何永久删除入口**（`projects.py` 只回收，无 `rmtree`／`unlink()`）；「从备份恢复」本轮按「项目库回收站即删除前可恢复副本」实现与验证，未新建独立备份子系统。
- 验证证据：新增 `tests/test_project_recovery.py` 8/8；定向 `-k projects project_ backup recovery reconcile desktop storage recycle` 149/149；架构 `--layer architecture --all` 312/312；默认冒烟 `smoke_test.py` 8/8；0 红。
- 全量：1367−1364=3<5 无五轮欠账，但改动命中 §5（项目删除语义），收口在干净 master 工作树 `o40-fullsafe-master` 跑 `--all --safe`：第 1 次为新工作树环境未就绪（缺 4 个嵌套仓库与 3 个忽略运行文件）假红，补齐后定向修绿，第 2 次 4859/4859、0 红、527.6 秒，凭据 round=1367、tree=1d7630f1（＝`HEAD:程序`），`last_full_safe_all_round=1367`。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`、`.codex/`、`.agent-handoff/archive/`、`程序/outputs/`、`程序/配置/宠物/配置.json`，不读取、不修改、不暂存、不覆盖；提交只点名自己的路径，绝不 `git add -A`。
- 干净 master 工作树：`o07-fullsafe-master`（与主树共享 git common dir；勿动 `o06-fullsafe*` 等）；领号／全量前先 `git reset --hard HEAD`。
- 轮次：O40 为 R1367、O41 为 R1368；`project_status.md` 的 `当前轮次` 已改为 1369（＝最新结果报告号＋1）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟 `smoke_test.py`；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`），并先查 `full-safe-receipts.json` 有无 7 天内同 `HEAD:程序` 内容树绿凭据可复用，只有命中 §5（启动路径／Tk 控件生命周期／删除语义／层级登记表）才强制重跑；全量失败先按定位文件定向修绿、只复验一次（报告写「第 N 次全量」，2 次仍不过就升级单独修复轮）；`test_desktop_startup_perf`／`test_perf_baseline` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
