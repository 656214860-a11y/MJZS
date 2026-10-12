# 当前快照

## 2026-10-12：O26 完成，继续 O27

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O25 已完成，**O26 已完成（R1351）**，下一项 O27。
- O26（白模及外部工具工作区可配置且可写）：成果目录默认改为用户数据目录 `%LOCALAPPDATA%/漫剧制作助手/白模项目`，与 Blender 安装位置解耦，可用 `MANJU_WHITE_MODEL_WORKSPACE` 或 `white_model_settings.json` 配置；Blender 发现保留 PATH／`D:`、`E:/Blender`／Program Files 旧路径只读候选；新增 `write_check`／`blender_version`／`legacy_workspaces`／`diagnose` 首次配置检查（版本＋写权限＋可执行提示），白模页加环境摘要标签与「白模环境检查」按钮；探针写入下沉 L1 `file_cache.probe_writable`。见 [R1351](../程序/tasks_round/tasks_round_1351_result.md)。
- 验证证据：O26 定向 `-k white_model previs native_apps` 160/160、`-k white_model_workspace file_cache` 47/47、`-k ui_edges core paths stage_flow stage_parallel notification` 360/360、`-k stage_execution stdlib_closure import_error` 20/20、棘轮/卫生全绿、架构 312/312、默认冒烟 8/8，0 红；1351 − 1346 = 5 ≥ 5 命中五轮欠账，收口在干净 master 工作树跑一次 `--all --safe`。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只能点名自己的路径。主树永远“脏”，`content_tree()` 在脏树返回空，全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`（要求干净工作树）；本轮 1351；全量在干净 master 工作树 `run_selftests.py --all --safe`。主树提交后 master 前移会让 `o07-fullsafe-master` 显示为「已暂存改动」，领取／全量前先 `git reset --hard HEAD`。
- 下一步：O27（见 `tasks_round_1267_result.md` O27 条目：视频技术合格与创意验收分开；事实/产品裁决；M）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`）；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑（上次绿全量 1346，本轮 1351 补跑；下一欠账点 1356）。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
