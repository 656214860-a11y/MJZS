# R1307：O06 首帧图片可用性与版本校验

类型：功能轮，承接 R1267 清单 O06（O01—O05 已完成）。中央轮次 1307。实现见本提交，全量回归状态见文件末尾。

## 实现
- 新增 L2 `keyframe_evidence.py`：PNG 块 CRC、FFmpeg 完整解码、尺寸与宽高比校验，并按内容摘要缓存解码事实（同一内容不重复整解码）；`source_evidence`/`make_evidence` 记录并核对分镜、提示词与参考资产版本；`frame_problem` 供门禁判定，损坏或类型异常的证据一律安全拒绝，不把旧图/外部替换误判为当前合格。
- 接入校验并保留失败证据：`keyframe_lifecycle_service.replace_keyframe`、`keyframe_import.register`/`publish_frame_reference`、`keyframe_comfy.run_seedream`、`batch_frames_tool/batch_frames._run`；失败时保留原图或生成图，不覆盖已有成果。
- `stage_parallel.frames_ready`（SG-04）接入可用性与版本检查，文案区分“缺首帧/首帧待复核”。
- 暂停恢复检查闭环：损坏 `frame_evidence`/`source` 结构不再抛 AttributeError；本地批量解码失败与缺少来源版本的旧任务改为确定失败，避免“查询同一坏结果”空转；Seedream 已拿到响应但未登记的结果保留图片并记为待核实，不自动重复提交，避免重复扣费。
- 测试：新增 `tests/image_fixtures.py`（真实 PNG 夹具）与 `tests/test_keyframe_evidence.py`；同步 `test_keyframe`、`test_keyframe_lifecycle_service`、`test_stage_parallel`、`test_batch_frames`；登记 L2 模块并同步 `维护记录/架构统一基数.json` 豁免清单（`exempt_count` 34→35）。

## 验证
- 定向（修复前）：`keyframe_evidence keyframe_lifecycle_service test_keyframe stage_parallel batch_frames test_layers test_unification_ratchet` 153/153、3.8 秒、0 红；默认冒烟 8/8；架构门禁 312/312。
- 第 1 次全量（干净 detached 工作树，`HEAD:程序`=e0df829a）：4504 条、566.7 秒、4 文件红——`test_pet_ui`（空头 PNG 夹具不再满足新门禁）、`test_aspect_ratio_priority`（mock 未提供来源证据）、`test_stage_gate_e2e_probe`（探针首帧无证据，且内嵌 base64 PNG 的 IDAT CRC 实际损坏）、`test_asset_gating`（并行下的 Tk 计时抖动，定向 18/18 绿）。全部为测试夹具／环境问题，未改业务逻辑。
- 第 2 次全量（干净 detached 工作树，`HEAD:程序`=0e2a2f06）：4504 条、536.7 秒、0 红、ALL TESTS PASSED。执行器未写绿凭据：`save_full_safe_verification` 要求当前检出在 `master` 分支，而该工作树是 detached HEAD；`full-safe-receipts.json` 仍停在 R1306/tree 48d5df7e。
- 第 3 次全量（同一内容树 0e2a2f06，master 分支临时工作树，目的只是取得正式凭据）：并行阶段全部通过后，行至串行性能用例 `test_desktop_startup_perf` 时主进程被并发活动中断（另一条工作车道同一时刻在跑 `程序/smoke_test.py --architecture`），退出 1、无汇总；残留全量锁持有人已退出并回收。按"不反复重跑赌稳定"，不再重跑。
- 收口回归修复后：`test_context keyframe_evidence test_keyframe test_stage_execution_service test_asset_gating` 128/128、18.3 秒、0 红；接缝相关 `pet_ui stage_gate_e2e_probe aspect_ratio_priority` 591 条、38.0 秒、0 红。

## 收口修复（本轮引入／暴露的回归）
- `tests/test_pet_ui.py`、`tests/test_aspect_ratio_priority.py`、`维护记录/基准脚本/探针_阶段门禁端到端.py`：夹具改为真实可解码 PNG 并登记 `frame_evidence`；探针补 `config.json`、已登记资产表与角色／场景图片；修正内嵌 base64 PNG 的损坏 IDAT CRC。断言语义未削弱。
- `platform_tools.tool_path`：只缓存 `which` 结果，未命中不再把 None 写死进缓存；否则先发生的无兜底查询（`stage_execution_service`）会让后续带兜底的调用拿到 None，首帧完整解码就会把 None 交给 subprocess 抛 TypeError。这是 O06 新增解码暴露出的真实潜在缺陷。
- 台账：`project_status.md` 当前轮次 1307→1308，满足 AGENTS 2.5 规则 27（N = M + 1）。

## 风险与边界
- 未实发 Seedream/Comfy 外部调用、未重启应用；证据校验属技术核验，不替代内容审核。
- 手动替换传入的内存 episode 与磁盘不一致时仍按调用方视图发布（沿用 delete/restore 既有模式，本轮未改）。
- Seedream 参考图哈希计算与实际上传之间存在极短 TOCTOU 窗口，本轮记录来源时点，未消除。

[TASK_COMPLETE] 实现 a167b7c／回归修复与台账 8760e41／tool_path fbdd23d；定向与默认冒烟绿，干净内容树 0e2a2f06 全量 4504/4504 通过（无执行器绿凭据，原因见"验证"）。
