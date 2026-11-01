# R414 功能轮结果：资产图片回收服务收敛

## 改动

- `desktop.py`：资产图片的单项删除、批量删除与确认重做统一移入项目回收站；恢复操作调用统一服务，不再维护独立“历史版本”目录。
- `storage_maintenance.py`：`restore_recycle_batch()` 支持按原始相对路径筛选；新增按精确路径及按目录/资产 ID/后缀定位的最近单项恢复，均不连带恢复同批其他文件。
- `tests/test_recycle_restore.py`：新增同批次单项恢复及未知原始后缀的资产恢复测试；资产 UI 回归断言和提示同步为项目回收站，并覆盖删除后恢复。
- 状态与优化清单已登记 R414；删除总项仍保留其他页面的后续专项。

## 验证

- `run_selftests.py --safe --serial -k recycle_restore asset_gating`：20/20 通过。
- `smoke_test.py --architecture`：34/34 通过。
- `smoke_test.py`：8/8 通过。
- 补充回归：`tests.test_recycle_restore` 与 `AssetCellDeleteTests`：8/8 通过。

## 自审

通过：仅迁移资产图片这一条用户可见物理删除路径；逻辑取消、模型配置隐藏和其他页面未改。恢复仍先验证项目范围、回收批次和目标冲突。
