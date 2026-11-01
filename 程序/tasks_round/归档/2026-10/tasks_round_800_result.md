# R800 结果｜结构治理轮（架构统一第 3 项资产域第二批）

日期：2026-10-02

## 完成项

`asset_detail_service._publish()` 的回滚字节发布改为必须由 L3 `asset_detail_gateway()` 注入。资产详情页正典板及状态变体绑定均改走 L3 编排入口；图片、索引与失败时双文件回滚语义不变。

第 3 项 pending 从 23 降至 22；第 4 项仍为 21，仅重定位 `stage_execution_service.py` 三条既有裸 JSON 读取行号。

## 验证

- `run_selftests.py -k asset_detail_service asset_detail_binding_boundary --safe`：6 条，0 红。
- `smoke_test.py`：8/8，0 失败。
- `smoke_test.py --architecture`：168/168，0 失败（47.643 秒）。
- `run_selftests.py --all --safe`：3,591 条，0 红，958.6 秒；末尾 Tk 回调报文未导致测试失败，权威结论为 `ALL TESTS PASSED`。

## 收尾

完整安全全量基线已推进至 R800。凭据形态扫描通过，暂存区未含私有数据、日志或运行路径；已提交 `e72602a`（`R800: 资产详情发布接入 L3（全量3591/0红）`）。
