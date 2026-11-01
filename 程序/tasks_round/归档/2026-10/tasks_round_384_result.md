# Round 384 — 云朵框几何职责拆分

- 将圆角图元、图元位移、多边形命中和描边扩展迁入 `pet_cloud_geometry.py`，该模块不依赖 Tk。
- `pet_cloud.py` 保留原有导入名称，调用者和既有公共几何入口无需调整。
- 架构分层已登记新模块；新增纯函数单测覆盖圆角、位移、命中与扩展。

验证：`tests.test_pet_cloud_geometry`、`tests.test_pet_cloud_text`、`tests.architecture.test_layers` 通过；`smoke_test.py` 待本轮改动后执行。
