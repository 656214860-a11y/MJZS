# R423 结构治理轮（子场景：执行）：资产页动态导入收敛

- **来源**：R418 J-3；资产批处理面板残余 UI 适配边界。
- **改动**：`asset_skill_batch` 与 `native_assets` 登记到 `ui_plugin_registry`；资产批处理页的用户触发延迟加载改经 `ui_plugin_registry.module()`，不再使用裸 `import_module()`。
- **验证**：动态导入门禁 3/3、默认冒烟 8/8 通过；全量架构与全量 3,059 未运行。
- **欠账**：未关闭完整 View/Service/Adapter 总项；已消除该页面两处 L4 动态导入旁路。
