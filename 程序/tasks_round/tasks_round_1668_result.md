# R1668 修复轮：按用户裁决落实阶段 05／06／07 的 ❓ 条目

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮（用户对 R1658／R1659／R1660 结果文件 C 节逐条裁决为“修复”或“你决定”）。
2. **测试跑了吗？三个基线过了吗？** 定向（assets_scope／continuity／storyboard_final／storyboard_scope／agents_md／distribution_selfcheck／layers／stage_parallel／stage_completion／asset／desktop_media）513 条全绿；默认冒烟（分支内 8/8）；架构门禁全量与安全全量待五组合入后统一跑。
3. **project_status.md 的欠账少了吗？** 全量欠账 +1，合入后统一补跑。

## A 改动

- REQ-S05-32：SG-01 以资产库根目录的图片登记表（`assets.json`）为准，资产清单内的 `image` 仅作旧数据兜底；新增复现用例。
- REQ-S06-24（用户授权“你决定”）：已采用分镜含镜头且台账存在时，台账镜头编号必须与分镜一致（缺镜／多镜均拦）；无台账或无采用分镜仍放行；0 镜头不再生成台账，空台账对有镜头的项目会被拦。只比镜头编号，不比资产内容。
- REQ-S06-33：`pet_start('continuity')` 经 `stage_handler_registry.start()` 新增 continuity 分支，与手动按钮共用同一生成实现，不另立入口。
- REQ-S06-32：依据 REQ-S06-10“不调用模型”，以实现为准，改 `pipeline-continuity` SKILL 为仅 structured-output、模型偏好清空；保留既有架构测试要求的 `repairList` 字样并注明对应 `continuity_issues.json`。
- REQ-S07-52：`storyboard_final.finalize` 读连贯性台账：台账未生成放行；与待定稿镜头不对应或仍有未裁决待办则拒绝并提示重新生成。段缝（D 锁）字段仍只由 SKILL 提示词约束，程序不核验。
- 新增用例分别在 `test_assets_scope`、`test_continuity_scope`、`test_storyboard_final_scope`，未改既有断言。

## B 验证

- 定向 513 条 0 红。分支内曾见 `test_skill_reference_injection` 红（worktree 缺嵌套子仓库），合入树补齐后不复现。

## C 待用户拍板

- SG-02 的比对口径只含镜头编号，是否要加入资产内容比对。
- 段缝（D 锁）是否要程序化核验。

## D 未做与局限

- 未跑架构门禁全量与安全全量。
