# 当前快照

## 2026-10-12：O44 完成，继续 O45
- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O43 已完成，**O44 已完成（R1371）**，下一项 O45（把分发声明变为可复验的干净安装流程，P2／事实·验证，M/L）。
- O44（保留安全机制，补可诊断但不泄露的状态区分）：`model_secrets.py`（L1）新增 `_BLOB_HEADER`（DPAPI 密文头＝版本号 4B＋provider GUID 16B）＋`READY`／`UNCONFIGURED`／`OTHER_USER`／`CORRUPT`／`AUTH_FAILED`＋`_STATE_TEXT`、`looks_like_blob()`、`diagnose(name, program, root)`（缺文件／空名字→`unconfigured`；读不出或头不是 DPAPI 头→`corrupt`；头对但解不开→`other-user`；解得开→`ready`；返回 `{'name','path','state','ok','text'}`，**不含密钥**）、`verdict(..., error_class='')`（本机没配好以本机为准，本机 `ready` 且 `error_class∈{auth,authentication,unauthorized}` 才报 `auth`），`load`／`save`／`clear` 等原有契约不变。`diagnostic_capture.py`（L1）新增 `redact()`／`retention_note()`／`preview_detail()`（白名单＋`bytes`／`modified`／`keep_days`＝`log_maintenance.RETENTION_DAYS`／`expires_at`／`expired`，只看不删）与 URL 查询参数脱敏分支（`?api_key=`／`&token=`／`?signature=`）。`model_diagnostics.py`（L1）新增 `_scrub()`，让 `context`／`response_meta` 的字符串落盘前先脱敏。见 [R1371](../程序/tasks_round/tasks_round_1371_result.md)。
- O44 契约变化：`load`／`save`／`clear`／`path`／`redacted`／`preview`／`export`／`event` 输出全不变，只新增函数与常量；新增同层 import `diagnostic_capture → log_maintenance`、`model_diagnostics → diagnostic_capture`（L1→L1，不越层）；未新增顶层模块／裸 `json.loads`／`skipTest`／删除路径；架构 312/312。
- O44 验证证据：新增 `tests/test_secret_status_diagnostics.py` 13/13；定向 `-k secret_status_diagnostics diagnostic_capture model_diagnostics model_pool pet_llm writing_api hollmwood_roles pet_settings` 269 条、仅 `test_model_pool` 1 条红（claude-desktop「未安装」，已用路径限定 `git stash` 复现：不加载本改动同样红＝既知主树环境项）；`-k test_api test_recycle` 全绿；架构 312/312；默认冒烟 8/8。
- O44 边界：`other-user`／`corrupt` 用密文头启发式（头好中段坏会归 `other-user`，但绝不归 `ready`）；`preview_detail` 只显示保留期限不删文件（轮转仍归 `log_maintenance`）；`verdict` 依赖调用方已分好的 `error_class`；本轮未读任何真实明文密钥（测试全用假 `PROTECTOR`）。
- O44 全量：1371−1370=1<5 无五轮欠账且未命中 §5，收口在干净 master 工作树跑一次 `--all --safe`：全量结果待收尾补记。

## 2026-10-12：R1335 并入 master（阶段④分集增量上下文）
- 分支 `codex/episode-incremental-context` 已合入 master。`script_contract.split_script_episodes`＋分集账本 `write_dir(project,'script')/剧本分集增量账本.json`（每集 sha256＋based_on 其余集快照）；`writing_api.reply()` 前注入「只贴改动集正文」、唯一发布点 `_save_formal_script()` 后更新账本；`workflow_tasks._episode_change_notice()` 只给本地 Agent 报集号；首次／无账本退化为全量。见 [R1335](../程序/tasks_round/tasks_round_1335_result.md)。
- 未改 `skills/01 剧本准备SKILL/pipeline-script-preparation.skill.md` 与 `structure_script()` 场次解析。
## 2026-10-12：O43 完成（历史）
- O43 = R1370（检查点版本化＋只读恢复预览）；全量 4899/4899、0 红、963.97 秒（凭据 round=1370、tree=4a7be90a…）。详情见 [R1370](../程序/tasks_round/tasks_round_1370_result.md)。

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
