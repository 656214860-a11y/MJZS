# 当前快照

## 2026-10-12：O39 完成，继续 O40

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O38 已完成，**O39 已完成（R1364）**，下一项 O40（项目管理、备份与清理统一空间和恢复说明，P2／建议·风险，M）。
- O39（清理旧视频前必须保护被采用及被引用版本）：`storage_maintenance.py`（L1）新增 `EXPORT_MANIFEST_NAMES`（成片清单名；权威在 engine（L3），L1 不能向上导入，故复名并由 `tests/test_video_retention.py` 锁死与 engine 常量一致）、`SETTLED_STATES`＝(downloaded, failed, rejected)、保留原因常量 `RETAIN_UNSETTLED|LOCKED|EDIT_SOURCE|APPROVED|LATEST|FRESH` 与中文 `RETAIN_REASONS`、`VERSION_CLEAN_REASON`；新增 `edit_source_versions(root)`（只读 `13质检交付/导出成片` 下的 `edit_bundle.json`／老成片 `edit_manifest.json`，返回被引用的 `(镜头,版本)` 与 `(镜头,sha256)`）与 `version_retention(...)`（保留口径：未结算含未知状态／用户锁定／已进成片来源／`review==pass` 已验收通过／最新版／不足 7 天；缺 `created` 按未到期保守留住）。`clean_project` 版本清理先取引用图、台账扫描排除回收区（回收站里的旧台账不再当生产目录），只有定局且无引用的过期旧版才回收，并写 `cleaned_reason`。见 [R1364](../程序/tasks_round/tasks_round_1364_result.md)。
- 契约变化：版本清理新增 4 类保护（成片来源引用／已验收通过／用户锁定／非定局状态），更保守；`AGE_SECONDS`（7 天）与「每镜最新版必留」不变；只读成片清单，未改 engine 的 `approved_versions`／`adopted_edit_version` 口径，未新增跨层导入（只用 L0 `project_stages` 与 L1 `file_cache`）。
- 验证证据：新增 `tests/test_video_retention.py` 12/12；定向 `-k storage exit_maintenance force_quit integration core video edit retention adaptation cleanup recycle pet_report` 536/536；架构 `--layer architecture --all` 312/312；默认冒烟 `smoke_test.py` 8/8；0 红。
- 全量：1364−1363=1<5 无五轮欠账，但改动命中 §5（删除语义 `storage_maintenance.py`），收口在干净 master 工作树 `o07-fullsafe-master` 跑 `--all --safe`（结果与凭据见 [validation](validation.md) 与 R1364 报告）。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`、`.codex/`、`.agent-handoff/archive/`、`程序/outputs/`、`程序/配置/宠物/配置.json`，不读取、不修改、不暂存、不覆盖；提交只点名自己的路径，绝不 `git add -A`。
- 干净 master 工作树：`o07-fullsafe-master`（与主树共享 git common dir；勿动 `o06-fullsafe*` 等）；领号／全量前先 `git reset --hard HEAD`。
- 轮次：R1364 已在干净 master 工作树领到；`project_status.md` 的 `当前轮次` 已改为 1365（＝最新结果报告号＋1）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟 `smoke_test.py`；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`），并先查 `full-safe-receipts.json` 有无 7 天内同 `HEAD:程序` 内容树绿凭据可复用，只有命中 §5（启动路径／Tk 控件生命周期／删除语义／层级登记表）才强制重跑；全量失败先按定位文件定向修绿、只复验一次（报告写「第 N 次全量」，2 次仍不过就升级单独修复轮）；`test_desktop_startup_perf`／`test_perf_baseline` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
