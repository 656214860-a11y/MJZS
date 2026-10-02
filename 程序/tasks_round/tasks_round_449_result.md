# R449 结构治理轮结果

## 范围

- 迁移资产页恢复已登记图片时的文件恢复与索引登记事务；未迁移资产导入、参考图解绑、设置或其他阶段写入。

## 改动

- `asset_batch_service.restore_asset_image()` 统一恢复回收图片并登记索引；若索引保存失败，会将刚恢复图片重新移入回收站。
- `desktop.restore_asset_image()` 保留输入检查、用户确认、页面刷新和状态提示，委托服务处理持久化。
- 新增行为测试与窄静态边界，覆盖成功恢复、索引保存失败后的文件回滚与旧索引保留。

## 验证

- `python -m unittest tests.test_asset_image_restore_service tests.architecture.test_asset_image_restore_boundary tests.test_recycle tests.test_recycle_restore`：13/13 通过。
- `python smoke_test.py --architecture`：59/59 通过。
- `python smoke_test.py`：8/8 通过。
- 全量安全自检未在本轮执行；最新可用全量基线仍为 R439 的 3,116/3,116。

## 自审与结束检查

- 通过：恢复与失败补偿均复用回收服务；不会留下“图片已恢复而索引未登记”的不一致状态。
- 通过：未改齿轮→设置、白模上传或用户项目配置入口。
- 项目已接续至 R450；统一阶段写入总项与白模真实上传授权仍未关闭。
