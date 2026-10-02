# R812 结果：架构统一第 3 项首批 L3 发布器接入

## 完成项

- `white_model_service.write_record()` 不再直接导入正式 JSON 发布器；白模 UI 经 L3 `white_model_persistence_controller` 注入发布器，媒体导入与备注保存沿用同一注入链。
- `asset_batch_settings_service.remove_model()`／`save_settings()` 改为接收 L3 `asset_batch_settings_gateway()` 注入的发布器；资产批量设置 UI 仅委托 L3。
- 第 3 项待迁移数从 14 降至 11。为避免白模 UI 接入大型通用编排器导致静态循环，白模记录使用独立 L3 编排器；其只拥有发布器注入，不反向导入 L2。
- 第 4 项三条既有 `stage_execution_service.py` 裸读取行号因本轮新增 L3 函数重定位为 449／480／493；未新增债务。

## 测试契约说明

本次同步调整架构测试的导入目标与注入断言，原因是 L4→L3→L2 的接口迁移；未删除、跳过或弱化任何断言。

## 实测命令原始输出

```text
> python -m unittest tests.architecture.test_no_circular_import tests.test_previs tests.architecture.test_white_model_import_boundary tests.architecture.test_white_model_service_json_boundary tests.test_asset_batch_settings_service tests.architecture.test_asset_batch_settings_boundary tests.architecture.test_round_baselines
Ran 69 tests in 5.066s
OK

> python smoke_test.py
通过：8 项
失败：0 项
✅ 冒烟测试通过，可以进入下一轮

> python smoke_test.py --architecture
Ran 178 tests in 43.875s
OK
✅ 架构治理测试：tests/architecture

> git diff --check
退出码 0（仅 CRLF 工作树提示）

> 凭据形态扫描（本轮差异）
credential_shape_matches=0
```

完整安全全量基线为 R810；R812 - R810 = 2，未达到每三轮强制重跑阈值。
