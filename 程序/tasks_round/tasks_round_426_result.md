# R426 修复轮：资产批处理页动态导入闭环

- **根因**：`asset_batch.py` 在 R423 后仍保留 `from importlib import import_module`，且该页没有列入动态导入门禁的 L4 扫描集合，导致旁路未被发现。
- **改动**：`_is_skill_api_engine()` 改经 `ui_plugin_registry.module('workflow_settings')` 读取；登记该按需模块；门禁把 `asset_batch` 纳入扫描，并验证登记存在。
- **范围**：仅 `asset_batch.py`、`ui_plugin_registry.py` 和动态导入门禁；未改用户数据或其他业务逻辑。
- **验证**：动态导入定向 **3/3** 通过；`python smoke_test.py --architecture` **37/37** 通过（15.960 秒）；默认 `python smoke_test.py` **8/8** 通过。
