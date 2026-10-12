# 当前快照

## 2026-10-12：O37 完成，继续 O38

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O36 已完成，**O37 已完成（R1362）**，下一项 O38（回收批次需要写前日志及失败恢复，P1／事实·风险，M）。
- O37（「测试连接成功」与完整工作流支持分开）：`model_pool.py`（L1）新增分层常量（`PROBE_DIMENSIONS`／`PROBE_WIRE_FIELDS`／`PROBE_FULL_TASK_STATE`／`VERIFY_TOKENS`／`HEALTH_KEY`）与纯函数 `config_version`／`request_spec`／`body_signals`／`classify`／`probe_summary`／`health`／`health_of`／`record_health`；`probe` 改经共享 `request_spec` 发最小请求，返回体在原有键之外追加 `checks`／`summary`／`config_version`／`signals`／`full_task`（最小请求的「完整任务」恒「未验证」），新增 `verify_sample` 由用户点名发一次真实短请求判完整任务；`pet_models_ui.py`（L4）`probe_line` 保留「连接成功，延迟 N ms」并追加五维分层＋配置版本＋最近完整任务，模型配置页加「小样本验证」按钮（只在默认模型这一条上发一次）与 `probe_sample` seam。见 [R1362](../程序/tasks_round/tasks_round_1362_result.md)。
- 契约变化：`probe` 返回为纯追加（`checks`／`summary`／`config_version`／`signals`／`full_task`），原键与「连接成功，延迟」不变；`架构统一基数.json` 第四项 `model_pool.py:576→808`、`:613→845`（行号位移，未新增裸 json.loads）；未新增顶层模块、`_layers.py` 未动。
- 验证证据：新增 `tests/test_model_probe_layers.py` 16/16；定向 `-k model_pool pet_models model_router model_diagnostics pet_ui token_saver request_ledger model_probe_layers` 771 条 1 红（主树未跟踪 `程序/配置/宠物/配置.json` 的桌面模型标签环境项，干净工作树绿）；`-k pet_settings copy_rules line_endings skip_hygiene model_probe_layers model_pool` 中新用例／copy_rules／pet_settings 全绿，2 红同为主树既有环境项（桌面模型标签＋主树 `desktop.py` 行尾 LF）；架构 `--layer architecture --all` 312/312；默认冒烟 `smoke_test.py` 8/8；默认增量运行 1 红（同一环境项）。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`、`.codex/`、`.agent-handoff/archive/`、`程序/outputs/`、`程序/配置/宠物/配置.json`，不读取、不修改、不暂存、不覆盖；提交只点名自己的路径，绝不 `git add -A`。
- 干净 master 工作树：`o07-fullsafe-master`（与主树共享 git common dir；勿动 `o06-fullsafe*` 等）；领号／全量前先 `git reset --hard HEAD`。
- 轮次：R1362 已在干净 master 工作树领到；`project_status.md` 的 `当前轮次` 已改为 1363（＝最新结果报告号＋1）。
- 提交：R1362 路径＝`程序/model_pool.py`、`程序/pet_models_ui.py`、`程序/tests/test_model_probe_layers.py`（新）、`程序/维护记录/架构统一基数.json`、`程序/tasks_round/tasks_round_1362_result.md`（新）、`程序/project_status.md`、`.agent-handoff/{snapshot,work-log,validation,backlog,risks}.md`；门禁与提交姿势见 [work-log](work-log.md)。
- 下一步：O38——证据 `storage_maintenance.py:78` 逐个移动文件、全移动后才存 manifest、缺整批回滚／提前落盘；建议 UUID 批次、写前计划、逐项状态、最终提交、中断可恢复／撤回（不永久删除）；复用已有恢复边界检查，不整体重写回收系统。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟 `smoke_test.py`；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`），并先查 `full-safe-receipts.json` 有无 7 天内同 `HEAD:程序` 内容树绿凭据可复用，只有命中 §5（启动路径／Tk 控件生命周期／删除语义／层级登记表）才强制重跑；全量失败先按定位文件定向修绿、只复验一次（报告写「第 N 次全量」，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑。`test_desktop_startup_perf`／`test_perf_baseline` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
