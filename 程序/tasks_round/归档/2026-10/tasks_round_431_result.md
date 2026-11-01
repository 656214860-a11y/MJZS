# R431 只读诊断轮：阶段成果写入清单

- **范围**：执行 R418 J-2 的静态盘点；只扫描根目录生产模块中 `save*` / `write_*` 入口和 `stage.completed` 发送链，不改生产代码、测试、架构文档或用户数据。

## 成果发布清单（按下一批迁移优先级）

| 阶段成果族 | 现有发布入口 | 证据 | 状态 / 下一步 |
| --- | --- | --- | --- |
| 剧本结构 | `script_contract.write_structured_script()` | `script_contract.py:502` | 已收敛（R429）。 |
| 初步分镜 / 定稿 | `storyboard_storage.publish_final_bundle()` | `storyboard_storage.py:11-27` | 已收敛（R422/R428）。 |
| 资产计划 | `asset_plan.publish_plan_bundle()` | `asset_plan.py:7-34` | 已收敛（R430）。 |
| 连续性清单 | `continuity_ledger` 同步写 JSON 与 Markdown | `continuity_ledger.py:294-295` | **下一批**：收敛为可回滚双文件发布包。 |
| 首帧 | `keyframe_import` / `keyframe_comfy` 导入和生成记录 | `keyframe_import.py:70`、`keyframe_comfy.py:157-164` | 后续按“媒体 + 清单”成对发布评估。 |
| 白模预演 | `previs_*` 任务、进度和路由状态 | `previs_automation.py`、`previs_batch_service.py` | 内部状态优先，不与未授权真实上传混轮。 |
| 视频生成 | `engine.py` 请求、下载、质检和剪辑清单 | `engine.py:235-312`、`425-446` | 后续按单镜版本账本与媒体成果拆分。 |
| 配音 / 字幕 | `tts_api` 音频与任务数据 | `tts_api.py:153`、`216` | 后续单独处理媒体与元数据一致性。 |
| 剪辑 / 交付 | `engine.py` 交接清单与 QC | `engine.py:438-446` | 后续处理交接包发布，不合并白模上传验收。 |

## 非成果写入（不纳入本批迁移）

- **内部状态**：资产批次台账、后台派发/执行状态、工作流续跑、Comfy 请求记录；其中资产批次台账已在 R419 收敛。
- **配置与偏好**：`project_settings`、模型设置、页面偏好；不属于阶段产物。
- **缓存、缩略图和临时文件**：`file_cache`、`asset_thumbs`、快捷方式/图标生成等；遵循现有受控清理边界。
- **外部阻塞**：白模真实上传与视频验收仍未获用户授权，本轮未启动上传或生成。

## 完成事件核验

- `stage_completion_service.py:66` 是 `stage.completed` 的实际发送点；`tests/architecture/test_completion_gate.py` 已静态禁止 UI / Agent 直接发送。
- 本轮未发现需放宽该门禁的例外。

## 结论与下一轮

- 清单表明可按成果族继续收敛，不需要新增通用“万能写入模块”。R432 应只处理连续性清单的 JSON + Markdown 双文件发布包，并补失败回滚、落盘复核和静态委托门禁。
- 验证：`python smoke_test.py` **8/8** 通过；只读诊断轮按 AGENTS 3.6 不运行架构门禁。
