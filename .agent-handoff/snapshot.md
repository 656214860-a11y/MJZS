# 当前快照

## 2026-10-12：O07 完成，继续 O08

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O05 已完成（R1303）、O06 已完成（R1307）、**O07 已完成（R1312）**，下一项 O08。
- O07（白模工作目录缺项目唯一身份与集维度）：`white_model_service` 目录改为「工作区／项目身份／集／镜头」——身份取项目 `config.json` 的 `project_id`（随项目改名／移动走），集号按 `EP…_` 前缀 → 本次传入 `source` → `ui_settings` 聚焦分镜 → 配置 `episode_file` 判定，项目移动后按阶段目录名在项目内重定位；没有身份时仍用旧布局，旧成果只读兼容。`projects.create` 新建项目即写 `project_id`。`migrate_legacy_directories`＋L3 包装器把旧目录迁入身份布局：可重复、不覆盖、失败原样回滚，清单落 `工作流任务/白模目录迁移/<时间>/迁移清单.json` 并记来源版本；白模页（09）打开时在无任务运行时调用一次。
- 验证证据：定向 `white_model_identity`（新增 12 条）与 `white_model/previs/project` 相关 136/136；接缝 `white_model previs project stage_execution local_previs desktop stage_parallel stage_completion storyboard keyframe asset` 669/669、48.9 秒、0 红；默认冒烟 8/8；架构门禁 312/312（同步 `架构统一基数.json` 第四项行号漂移）。全量结论见 [R1312](../程序/tasks_round/tasks_round_1312_result.md)。

- 收口全量（R1312）：干净 master 工作树（`HEAD=b0c6716`、`HEAD:程序`=12ad4759）跑 `run_selftests.py --all --safe`；第 1 次 4500 条、21 文件红，红全在写作／技能／剧本组，根因是新建工作树缺 3 个嵌套子模块（与本轮代码无关），补齐后同树定向 489/489；第 2 次 4516 条、388.1 秒、0 红并写入绿凭据（round=1312、tree=12ad4759）。新建工作树必须先补 4 个 gitlink（`skills/00全流程SKILL/AIGC创作全流程`、`skills/01 剧本准备SKILL/剧本锻造`、`skills/01 剧本准备SKILL/编剧技能集`、`reference/HoLLMwood`）及 `维护记录/基准历史.json`、`projects.json`。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/` 目录，不读取、不暂存、不覆盖；**任何提交只能点名自己的路径**（`git commit -m "R<n>: …" -- <paths>`），否则会连带他人 WIP。
- 中央轮次已到 1312（并行车道此前领走 1309—1311）；`round_claim.py next` 要求工作树干净，本树因他人在做工不干净，本轮从干净临时 worktree `%TEMP%/o07-claim` 领取；`git worktree list` 里还留着多个历史 master 工作树（o06-fullsafe-master、r1248/r1249/r1256 等）。
- 下一步：O08（P1，S/M）——`previs_routing.py:51` 合并 `episode|shot` 手工覆盖，`stage_parallel.py:726` 直接 `classify(shot)`，页面与门禁可能不一致；验收「自动→复杂、复杂→简单、跨集相同镜头 ID、删除覆盖」四场景显示／调度／门禁一致。默认只跑 `-k previs stage_parallel` + 默认冒烟。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` + 默认冒烟；全量只在收口／合入 master 前跑一次，且用 master 分支临时工作树取凭据；全量失败先按定位文件定向修绿，只复验一次；`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
