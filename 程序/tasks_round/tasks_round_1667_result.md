# R1667 修复轮：按用户裁决落实阶段 02／03 的 ❓ 条目

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮（用户对 R1655／R1656 结果文件 C 节逐条裁决为“修复”，使代码与 REQ 一致）。
2. **测试跑了吗？三个基线过了吗？** 定向（script_structure／script_contract／storyboard／pipeline_stage_io／ui_edges／agents_md／distribution_selfcheck／layers／workflow_settings／stage_parallel／stage_completion）409 条全绿；默认冒烟、架构门禁全量、安全全量本轮未单独跑（五组修复合入后统一跑，见最后一轮结果文件）。
3. **project_status.md 的欠账少了吗？** 全量欠账 +1（源码轮），合入后统一补跑全量。

## A 改动

- REQ-S02-23：结构剧本发布时同步生成角色／场景／道具三份 manifest（`02剧本结构/output/`），阶段完成核验其存在、抬头、编号唯一、条目合规、名单与结构剧本一致。
- REQ-S02-25：manifest 按产出阶段登记落盘目录（02 三份、03 `scene_breakdown.json`、01 `emotion_curve.json`），`00_script` 仅作旧名别名。
- `runbook.md` 列入随附文件（`distribution_manifest.md`）。
- REQ-S03-19：文案与 03 页表头统一为“分镜初稿”，“分镜定稿”留给 07。
- REQ-S03-20：用户授权“你决定”——03 不写 `batch_id`，批次划分归 07；删除并行提示中的该要求。
- REQ-S03-43／44：采用、取消采用、清理失效采用时写 `03初步分镜/output/storyboard_draft.json`，并派生 `scene_breakdown.json`；阶段完成与 SG-A 核验二者与当前已采用分镜一致；旧项目缺文件时核验处补写一次。
- 测试：`test_pipeline_stage_io_contract`、`test_script_contract` 由“全在 00_script”收紧为“各在其产出阶段目录”；`test_ui_edges` 表头断言同步；新增 `StructureManifestTests`、`DraftOutputTests`。

## B 验证

- 定向 409 条，0 红（合入树需补齐嵌套 `skills` 子仓库内容后审计用例才绿，属环境，非改动）。

## C 待用户拍板

- 旧项目已完成 02 的，缺三份 manifest，02 会显示未完成，需重新整理一次结构剧本。
- 03 不检查场景／角色编号形态（`LOC_`／`CHAR_`），该职责在 SG-01。

## D 未做与局限

- 修改了既有测试的 3 处断言，均为收紧或随规格同步，未放宽。
- 未跑架构门禁全量与安全全量。
