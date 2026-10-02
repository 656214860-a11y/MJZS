# R589 结构治理轮结果：P0-3 二进制发布能力（拆分一）

## 执行范围

按自动处理推荐清单采用 R550 记录的“两轮拆分”方式推进 P0-3。本轮只建立不依赖 L2→L3 反向导入的二进制正式发布原语；不迁移首帧、媒体、交付现有调用方，避免一次跨越多个活跃模块。

## 改动文件

- `stage_execution_service.py`：新增 `publish_stage_bytes(target, data, validate, update_index)`。
- `tests/test_stage_execution_service.py`：新增二进制成功发布、索引失败恢复旧字节两条回归。
- `project_status.md`：登记本轮进展并将当前轮次推进至 R590。

## 行为与契约

`publish_stage_bytes()` 接受 bytes-like 成果，拒绝空内容；调用顺序固定为：校验 → `agent.core.save_bytes()` 原子写入 → 索引更新。索引回调抛错时，`agent.core.restore_bytes()` 恢复旧文件（或移除本轮新文件），异常继续上抛，因此调用方不能把失败标记为阶段完成。

缓存、路径和阶段状态机均未修改；对外已有 `publish_stage_text()` 行为不变。

## 验证

- `python -m unittest tests.test_stage_execution_service`：5/5 通过。
- `python smoke_test.py --affected stage_execution_service`：通过（定向自检 5/5）。
- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --architecture`：101/101 通过。

定向自检末尾的增量台账权限提示仅发生于当前受限沙箱；R588 已以项目真实权限上下文验证同一原子台账写入成功，不影响本轮测试结论。

## 债务状态

P0-3 尚未完成，现处于拆分一完成：统一二进制发布与回滚能力已就位。拆分二将把首帧／媒体／交付的正式发布调用迁移至该入口，并保留来源关系和恢复语义；在此之前不宣称债务条目已减少。
