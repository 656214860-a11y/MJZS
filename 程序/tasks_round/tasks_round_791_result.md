# R791 结果｜结构治理轮（执行）

## 完成内容

- 迁移 `asset_batch_service.py` 与 `asset_batch_lifecycle.py`：L2 正式读写必须接受 L3 `asset_batch_gateway()` 注入，缺少网关明确拒绝。
- 由 `stage_execution_service` 提供唯一资产批处理网关，桌面及既有执行调用方只装配；没有改变项目数据格式、路径结果或授权语义。
- 第 3 项台账将 9 条记录标为 `migrated`：资产登记、导入、改名、删除、恢复，以及批次 attach/fail/prepare/reconcile；第 3 项 pending `50 → 41`，第 4 项 `21 → 21`。
- 修正迁移过程中暴露的两项真实回归：测试替身缺少网关、`writing_api` 未装配创意聊天网关；另移除资产批处理中的裸动态导入，避免新增覆盖率审计债务。随后发现的 `stage_execution_service → writing_api` 循环依赖，已将写作网关实现留在 `writing_api` L3 适配层而非反向导入。

## 验证

- `smoke_test.py`：8/8。
- `smoke_test.py --affected asset_batch_service asset_batch_lifecycle stage_execution_service desktop`：9/9。
- `run_selftests.py -k "asset_batch asset_image lifecycle unification_ratchet" --safe`：48 条／0 红。
- `smoke_test.py --architecture`：156/156。
- 按 §5：`791 - 788 = 3`，必须完整安全全量；`run_selftests.py --all --safe`：3,572 条／0 红／901.3 秒。`last_full_safe_all_round` 已推进为 791。

## 后续

按既定批次，下一轮为 `tts_api.py`＋`cloud_video_service.py`。剩余量只作台账读数，不以点数机械估算轮数。

## Git

- 本轮未提交，commit hash：无。
