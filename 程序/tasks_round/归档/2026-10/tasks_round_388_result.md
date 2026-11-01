# Round 388 — 云朵框图元命中拆分

- `pet_cloud_geometry.inside_parts()` 集中圆、椭圆、矩形和多边形的命中规则。
- `pet_cloud.inside_shape()` 保留形状配置与公共入口，委派无 Tk 的图元命中计算。
- 新增四种图元和未命中位置的纯函数回归。

验证：云朵框纯模块、架构层级测试及 `smoke_test.py` 待本轮改动后执行。
