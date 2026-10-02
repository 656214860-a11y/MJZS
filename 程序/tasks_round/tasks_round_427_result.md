# R427 结构治理轮：资产批处理选择服务收敛

- **范围**：执行 R418 J-3 的一个最小子项，仅处理资产批处理窗口的无界面选择状态；未改生成、网络、落盘、目录或用户数据。
- **改动**：在既有 `asset_batch_selection_service` 增加类别选中、集合反选、整体选择和全选判定四条纯规则；`asset_batch.show()` 改为调用这些规则，保留 Tk 回调、表格刷新和界面状态。
- **测试**：`tests/test_assets.py` 新增 3 项集合语义测试；此次测试改动是服务职责下沉的契约变更，未弱化、删除或跳过断言。
- **验证**：`python -m unittest tests.test_assets` **79/79** 通过；`python smoke_test.py --architecture` **37/37** 通过（15.472 秒）；默认 `python smoke_test.py` **8/8** 通过。
- **边界**：这不是整个资产批处理页的 View／Service／Adapter 完整拆分；下一次 J-3 子项应单独审计其配置/执行适配边界。
