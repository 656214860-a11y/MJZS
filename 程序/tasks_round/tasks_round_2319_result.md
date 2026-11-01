# R2319 结果：继续拆 stage_execution_service，降到 1000 行内（J 路线后续 #18，重构轮）

## 改动（行为不变）
- 新增四个 L3 模块，函数原样迁出，`stage_execution_service` 在文件头按原名重新导出，旧调用点与 `patch('stage_execution_service.<名>')` 补丁点不变：
  - `stage_animatic_gateways`：动画预演发布、参考图导入、运行、确认等 9 个函数。
  - `stage_previs_gateways`：分镜预演路由、进度发布与分镜来源查询 22 个函数。
  - `stage_gate_gateways`：云视频设置、TTS、音频清单、媒体导入发布器、视频生命周期网关。
  - `stage_handoff_gateways`：交接包、写作准备、创意稿、自动标记、连贯性清单等 17 个函数。
- 被测试补丁的名字（`record_stage_confirmation`、`apply_asset_plan_gate_choice` 等）及调用它们的确认闸门函数（`adopt_asset_plan_choice` 等）留在门面，补丁继续生效。
- `_json_gateway` 并入 `stage_asset_gateways`。
- `stage_execution_service.py` 1332 → 约 900 行，从 `OVERSIZE_CAPS` 删除登记。
- 新增 `_scan.stage_execution_source()`：门面加五个拆出模块的源码拼接；18 个读门面源码／AST 的门禁改读它，检查的断言一字未动。
- 同步：层级登记、覆盖率基线（357 模块，未覆盖 304）、`runbook.md` §11、`architecture.md`、`test_atomic_write_boundary` 计数、`架构统一基数.json` 里 3 条豁免项只改文件名（债务不增不减）。

## 验证
- `run_selftests -k stage animatic previs handoff confirm tts cloud writing idea storyboard continuity asset keyframe delivery audio video edit architecture`：2353 条，0 个文件有红。
- 中途发现首版把确认闸门函数一起迁走导致 `test_confirm_gates`／`test_asset_detail` 红（补丁点失效），已改为留在门面后全绿。
- 未跑全量。断言未动。
