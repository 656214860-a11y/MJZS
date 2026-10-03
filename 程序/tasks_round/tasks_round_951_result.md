# R951：第 1 项分镜编辑结果契约迁移

类型：结构收口执行；来源：R948 的 J1/J2 与 K 验收要求。实际目录 master；保留其他任务未提交改动。

## 实现

- `storyboard_edit_service.save_edited_json` 返回既有 ServiceResult：成功 data 为解析后的目标路径；非 JSON 为 UserError；OSError 记录日志并返回通用 SystemError。缺少发布器和编程错误继续抛出。
- `storyboard_final_controller` 检查结果，只有保存成功才重新载入预览；受控失败交给既有错误展示流程。
- 采用方棘轮增加该模块，并验证台账采用方、豁免分母与清单一致；旧台账剩余 34 项。
- 仅修改 2 个生产模块，不改数据格式、布局或跨分支同步。

## 范围审计（尚未完成）

冻结时的清单不等同于当前 L2 集合。不能用旧清单清零宣称全量完成；下一批必须区分实际写入口、纯查询与历史兼容名并校正范围。

当前 L2 中未在旧清单登记：asset_batch_settings_service、asset_plan、asset_resume、audio_import_service、desktop_settings_service、hollmwood_roles、legacy_adoption_service、project_naming、projects、recycle_recovery_service、script_preview_service、script_workspace_service、stage_workspace_service、storyboard_adoption_contract、storyboard_rows_service、storyboard_storage、subtitle_export_service、video_lifecycle_service、video_prompt_publication、video_task_state、workflow_context、writing、writing_tools。

旧清单中没有对应当前 L2 源文件：asset_gating、keyframe、keyframe_api、previs、writing_files、writing_roles、writing_workflow。不得直接当成已迁移，应核对实际替代入口。

继续核对源码后确认：`project_naming` 仅生成未占用路径；`script_preview_service` 仅读取/分块；`storyboard_adoption_contract` 仅读取已采用分镜事实；`storyboard_rows_service` 只生成统计和行数据；`video_task_state` 只读取任务状态和计算提示。以上 5 项不属于写结果契约的迁移对象，但仍须登记审计依据，不能视作“已迁移”。

新增实际写入口已确认：`desktop_settings_service.publish_desktop_settings`、`audio_import_service.import_audio`、`legacy_adoption_service.record_legacy_adoption`、`stage_workspace_service.ensure_*`、`recycle_recovery_service.restore_*`。它们尚未纳入旧分母，需在下一批校正台账；其他差异模块仍待逐个核验。

## 验证

- 定向测试 14 项通过，覆盖成功、格式拒绝、发布故障、缺失发布器、编程错误和失败后文件/预览/导航状态保留。
- 默认冒烟 8/8；受影响自检 10 条、0 红，增量台账已刷新。
- 架构门禁 273 条中 2 项失败：轮次连续性及完整安全全量欠账。轮次已修正为 952，单独重跑轮次门禁后仅剩全量欠账。
- 已调用完整安全全量入口，但 R950 的 PID 33936 正在持锁；通过系统进程及子进程查询确认仍在运行。本次入口虽然显示绿色退出，但只是拒绝重复运行，不作为 R951 通过凭据。后续需等该进程结束，核对结果及覆盖树，再完成本轮全量验证。
- 后续观察确认 PID 33936 已结束，未取得可引用凭据；已启动本轮独立 `run_selftests.py --all --safe`，会话 42561，等待真实完成结果。当前共享工作区不干净，不能生成干净提交树的验收凭据。
- 会话 42561 已结束：3784 条用例、467.9 秒，1 个文件有红。失败为 `test_pet_ui.DefaultLevelTests.test_the_hint_level_does_not_wake_the_next_step`：预期空字符串，实际“【阶段 2/12】超时”。未修改或放宽该断言；单例重跑通过，同类重复 10 次（50 条）通过，尚未稳定复现，继续检查整文件执行顺序。
- 本轮尚未提交；保留其他任务工作区变更。

## 下一批

按 R948 顺序继续第 1 项。先校正上述范围，再选择最多 3 个实际写服务，同轮迁移调用方、测试和棘轮；第 2 项及后续条目仍未完成。
