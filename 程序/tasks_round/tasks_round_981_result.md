# R981：第 1 项只读范围验证

验证/基线轮。核验 project_naming、script_preview_service、storyboard_adoption_contract 三个待审模块及 read_prefs、resolved_alias 的实际依赖路径：只查询、解析或生成内存数据，不发布项目数据。将三项从 scope_audit_pending 转为带理由的豁免，未修改生产代码及调用形状；其他历史豁免仍不视为已审完。

既有契约门禁增加只读审计记录与公开入口集合核验，以及临时项目的查询前后内容一致性测试，覆盖命名冲突、预览缺失/损坏、采用路径别名、去重及非法路径拒绝。原测试断言不变。

验证：定向 14 项通过（0.355 秒），冒烟 8/8；架构 283 项（97.210 秒），仅轮次基线 963 != 982 失败。默认增量 3636 项（328.5 秒），5 个文件 6 条红：轮次基线、缺失基准历史、资产首批行数 31 != 24、剧本 SKILL 清单与两条 SKILL 数量 71 != 73。未修改这些断言或复制缺失依赖。

后续范围风险：旧豁免中的 edit_service、handoff_service、cloud_video_service、asset_detail_service、asset_generated_import_service、idea_attachments 实际包含写入口，须复审，不能把旧豁免当成已完成。此次三项只读结论不适用于它们。

[TASK_FAILED] 整体门禁未全绿，不宣告路线图收口。已诊断性提交 `641e1c1`，仅在 `codex/architecture-contracts`，未同步 master。
