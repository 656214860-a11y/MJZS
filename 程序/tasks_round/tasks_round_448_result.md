# R448 结构治理轮结果

## 范围

- 迁移资产页单项/批量删除已登记图片时的回收与索引清空事务；未迁移恢复图片、参考图解绑、导入或设置路径。

## 改动

- \`asset_batch_service.remove_asset_image()\` 统一调用回收服务、清空登记索引；若索引保存失败，立即恢复刚回收的目标图片。
- \`desktop.delete_asset_image()\` 保留输入检查、确认、刷新和状态提示，委托服务处理持久化。
- 新增行为测试与窄静态边界，覆盖成功回收、保存失败后的图片与索引恢复。

## 验证

- \`python -m unittest tests.test_asset_image_removal_service tests.architecture.test_asset_image_removal_boundary tests.test_recycle tests.test_recycle_restore\`：13/13 通过。
- \`python smoke_test.py --architecture\`：58/58 通过。
- \`python smoke_test.py\`：8/8 通过。
- 全量安全自检未在本轮执行；最新可用全量基线仍为 R439 的 3,116/3,116。

## 自审与结束检查

- 通过：删除仍唯一经 \`storage_maintenance.recycle_paths()\`；服务失败时显式复原，不会默默留下“索引仍指向已回收文件”的状态。
- 通过：未改齿轮→设置、白模上传或用户项目配置入口。
- 项目已接续至 R449；统一阶段写入总项与白模真实上传授权仍未关闭。
