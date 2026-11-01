# R590 结构治理轮结果：P0-3 交付成片迁移

## 改动文件

- `delivery_import_service.py`：`import_final_master()` 增加可选的发布器注入参数；无注入时保留现有直接复制兼容行为。
- `desktop.py`：交付页面的正式导入路径注入 `stage_execution_service.publish_stage_bytes()`。
- `tests/test_delivery_import_service.py`：新增注入式正式发布回归。
- `project_status.md`：登记迁移范围与剩余债务。

## 迁移结果

生产 UI 的“导入剪映最终成片”现在通过统一二进制发布器完成字节发布。L2 交付服务仍负责 MP4/MOV、非空校验、阶段目录和目标命名；L4 负责把 L3 发布器作为依赖传入，故没有 L2 导入 L3 的逆向依赖。

来源文件仍不修改，目标目录与文件命名规则不变。由于交付导入没有独立索引写入，传给统一发布器的索引回调为空操作；发布失败会继续抛出而不会返回“导入成功”。

## 验证

- `python -m unittest tests.test_delivery_import_service tests.test_stage_execution_service`：8/8 通过。
- `python smoke_test.py --affected delivery_import_service`：通过（定向 3/3）。
- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --architecture`：101/101 通过。

受限沙箱仍会在定向自检末尾提示增量台账临时文件权限；该环境差异已由 R588 在真实项目权限上下文复核，不影响结果。

## 债务状态

P0-3 未完成：交付成片已迁移，首帧与其余媒体成果仍需在保留回收与来源恢复语义的前提下迁入统一入口。不能将本轮的交付迁移宣称为整个 P0-3 完成。
