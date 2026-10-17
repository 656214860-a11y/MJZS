# R1669 修复轮：按用户裁决落实阶段 08／09 的 ❓ 条目

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮（用户对 R1661／R1662 结果文件 C 节逐条裁决为“修复”）。
2. **测试跑了吗？三个基线过了吗？** 定向（keyframe／previs／white_model／stage_execution／stage_parallel／stage_completion／agents_md／distribution_selfcheck／layers／pipeline_stage_io）432 条全绿；分支内默认冒烟 8/8；架构门禁全量与安全全量待五组合入后统一跑。
3. **project_status.md 的欠账少了吗？** 全量欠账 +1，合入后统一补跑。

## A 改动

- REQ-S08-40／41：首帧清单统一为 `08首帧管理/output/frames.json`，阶段核验通过后写入，仅作回执，写不进去则本次完成不成立；`keyframeManifest` 在 SKILL 中作为同一文件的别名。
- REQ-S09-35：`09白模预演/output/previs.json` 为项目内权威索引，`预演记录.json` 仍为逐镜记录；模板与架构文档去掉 `previs_manifest.json`。
- REQ-S09-36：预演视频校验通过时在项目内复制一份到 `09白模预演/assets/<镜头>/`；仅当工作区没有可用预览时才用该副本判就绪。
- REQ-S09-37：SG-05 对复杂与中等动作镜头都要求有预演，缺中等镜头时拦截并提示改选“简单”或用线上白模导入。
- REQ-S09-41：代码默认值不变，`pipeline-previs` 写明两条入口（全流程预设用 `pipeline-previs`，桌面白模页默认 `create-blender-story-video`）。

## B 验证

- 定向 432 条 0 红。

## C 待用户拍板

- 白模工作区未整体迁入项目（既有测试与迁移逻辑钉死了布局），只做“项目内副本加索引”；是否要整体迁移。
- 视频阶段取参考视频仍走 `预演记录.json`，`previs.json` 仅用于 SG-05 就绪判定。

## D 未做与局限

- 未跑架构门禁全量与安全全量。
