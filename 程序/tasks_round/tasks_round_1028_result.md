# R1028 历史层级名称职责追溯

- 本轮为整理轮：结构治理执行，来源 `tasks_round/tasks_round_1027_result.md` 最终接续条目，落实优化清单的服务结果/上下文范围审计；不是整体路线图收口。
- 测试：结果/上下文定向 28/28（0.506 秒），默认冒烟 8/8；完整架构 301/301（95.095 秒），相较 R1027 基线数量不减、失败仍为 0。安全全量本轮不重复运行：最近真实 R1027 凭据 3930/3930、376.202 秒，本轮差 1，无生产代码、启动、Tk、删除或层级登记表变更。历史凭据不冒充当前树全量通过。
- 欠账：7 个未实体化名称完成现行职责追溯，采用方、豁免数量、第二项 37 个原始基数均保留，不补造历史迁移或验收。

## 范围与事实

只修改架构台账、两个架构测试及 architecture.md、状态头、本报告。没有修改生产 .py、配置、密钥、用户项目、private/、episode/、writing/，未清理日志或缓存。

`git log --all -S writing_files -- 程序/tests/architecture/_layers.py` 定位初始登记提交 `c00a5f8`；初始树及当前树均无七个同名根模块，各同名路径的 `git log --all` 无记录。故分类为未实体化登记名称，而非已删除死代码或已完成重命名。职责映射只基于当前源码，不声称历史继承关系。

| 历史名称 | 现行职责入口（源码证据） |
| --- | --- |
| asset_gating | asset_batch_selection_service.py:4 selectable_rows、:16 initial_excluded；asset_batch.py:127 show |
| keyframe | keyframe_import.py:56 register、:113 launch；keyframe_batch.py:59 image_prompt |
| keyframe_api | keyframe_model_service.py:7 production_choices、:26 current_model |
| previs | previs_routing.py:12 classify、:140 dispatch；white_model_service.py:38 import_previs_media、:70 save_previs_notes |
| writing_files | writing_tools.py:53 list_files、:66 read_file、:74 write_file；script_workspace_service.py:69 iter_script_documents、:264 rename_script_document |
| writing_roles | hollmwood_roles.py:237 default_role_rules、:322 run |
| writing_workflow | writing_api.py:335 reply；writing.py:35 prepare、:95 import_project |

测试交叉证据：test_keyframe.py:11 实际导入 keyframe_import；test_previs.py:10–12 实际使用 previs_routing、previs_automation 与上下文工厂；test_asset_gating.py 检验桌面/资产交互，并不导入 asset_gating。

## 契约与回归边界

历史名称从 `historical_name_audit_pending` 转入 `historical_name_audited`，共享 `historical_name_audit` 保存分类、证据和现行符号。它们没有变成 adopters，也没有从原始集合消失。两个台账的 status 仍为 active。

本次测试因台账契约有意变更，将原“缺失集合等于待审计集合”扩展为“缺失集合等于待审计与已审计的不交并集”；原完整覆盖、无重复、分类不重叠、基数 37 和豁免理由检查保留，并增加两个台账已审计集合一致、现行文件及顶层符号存在检查。没有删除测试、skip 或放宽生产约束。

## 验收与提交

自审通过：范围仅六个治理文件，其中两个测试模块，无生产行为变化；新增入口事实检查，未弱化原基数和覆盖约束；轮次 N=1029、M=1028；没有修改历史报告。已使用 codex/wip-R1028 保存变更分支，再回 master 更新状态。git diff --check 通过；最小清单暂存并扫描凭据形态后，以 `R1028: 追溯历史层级名称与现行职责入口` 收尾提交，不 push。最终提交 hash 由 Git 历史与交付回复提供，不预填尚未生成的 hash。

[TASK_COMPLETE] 本轮名称职责审计和适用验收完成。下一项按优化清单继续后台任务生命周期；结果/上下文整体覆盖仍以现行采用方和既有门禁约束为准，不能把本轮名称审计当作整体迁移验收。
