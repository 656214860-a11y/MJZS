# Round 387 — 云朵框主体几何拆分

- `pet_cloud_geometry.py` 新增参数化的方框图元和尾巴根部计算。
- `pet_cloud.py` 的原公共 `square_parts()`、`shape_root()` 仅保留兼容配置入口，行为不变。
- 纯几何回归增加方框图元数量及尾巴根部坐标覆盖。

验证：云朵框纯模块、架构层级测试及 `smoke_test.py` 待本轮改动后执行。
