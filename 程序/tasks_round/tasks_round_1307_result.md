# R1307：O06 首帧图片可用性与版本校验

类型：功能轮，承接 R1267 清单 O06（O01—O05 已完成）。中央轮次 1307。实现见本提交，全量回归状态见文件末尾。

## 实现
- 新增 L2 `keyframe_evidence.py`：PNG 块 CRC、FFmpeg 完整解码、尺寸与宽高比校验，并按内容摘要缓存解码事实（同一内容不重复整解码）；`source_evidence`/`make_evidence` 记录并核对分镜、提示词与参考资产版本；`frame_problem` 供门禁判定，损坏或类型异常的证据一律安全拒绝，不把旧图/外部替换误判为当前合格。
- 接入校验并保留失败证据：`keyframe_lifecycle_service.replace_keyframe`、`keyframe_import.register`/`publish_frame_reference`、`keyframe_comfy.run_seedream`、`batch_frames_tool/batch_frames._run`；失败时保留原图或生成图，不覆盖已有成果。
- `stage_parallel.frames_ready`（SG-04）接入可用性与版本检查，文案区分“缺首帧/首帧待复核”。
- 暂停恢复检查闭环：损坏 `frame_evidence`/`source` 结构不再抛 AttributeError；本地批量解码失败与缺少来源版本的旧任务改为确定失败，避免“查询同一坏结果”空转；Seedream 已拿到响应但未登记的结果保留图片并记为待核实，不自动重复提交，避免重复扣费。
- 测试：新增 `tests/image_fixtures.py`（真实 PNG 夹具）与 `tests/test_keyframe_evidence.py`；同步 `test_keyframe`、`test_keyframe_lifecycle_service`、`test_stage_parallel`、`test_batch_frames`；登记 L2 模块并同步 `维护记录/架构统一基数.json` 豁免清单（`exempt_count` 34→35）。

## 验证
- 定向：`keyframe_evidence keyframe_lifecycle_service test_keyframe stage_parallel batch_frames test_layers test_unification_ratchet` 153/153、3.8 秒、0 红。
- 默认冒烟 8/8；架构门禁 312/312。
- 干净树 `--all --safe`：待执行，结果随后回填。

## 风险与边界
- 未实发 Seedream/Comfy 外部调用、未重启应用；证据校验属技术核验，不替代内容审核。
- 手动替换传入的内存 episode 与磁盘不一致时仍按调用方视图发布（沿用 delete/restore 既有模式，本轮未改）。
- Seedream 参考图哈希计算与实际上传之间存在极短 TOCTOU 窗口，本轮记录来源时点，未消除。

[TASK_FAILED] 待干净树安全全量回归后收尾。
