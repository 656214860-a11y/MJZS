# R447 结构治理轮结果

## 范围

- 迁移资产页“重命名资产”的双文件持久化；未处理资产图片导入、删除/恢复、阶段执行或设置页面。

## 改动

- 复用既有 `asset_batch_service` 增加 `rename_asset()`：更新资产清单名称、保留旧名别名，并同步已登记图片索引。
- 两个文件任一保存失败时恢复两份原始字节，避免半改名状态。
- `desktop.rename_asset()` 只保留交互、输入校验、刷新和状态提示；新增服务行为与静态委托边界测试。

## 验证

- `python -m unittest tests.test_asset_rename_service tests.architecture.test_asset_rename_boundary tests.test_asset_plan`：5/5 通过。
- `python smoke_test.py --architecture`：57/57 通过。
- `python smoke_test.py`：8/8 通过。
- 全量安全自检未在本轮执行；最新可用全量基线仍为 R439 的 3,116/3,116。

## 自审与结束检查

- 通过：只扩展已有资产服务；断言新增以约束迁移为因，未删除、skip 或弱化既有断言。
- 通过：未改齿轮→设置入口、外部服务、用户可见删除或白模上传路径。
- 项目已接续至 R448；统一阶段写入总项与白模真实上传授权仍未关闭。
