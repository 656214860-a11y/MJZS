# R999：审计纯计算项目上下文范围

- `asset_batch_selection_service`、`storyboard_adoption_service`、`subtitle_timing` 均仅接收调用方数据并返回计算结果；不接收项目根、设置、缓存、发布器或文件路径。
- 三项登记为带理由的第二项豁免；不冒充 ProjectContext 采用方。
- 第二项现行迁移待办由 20 项减至 17 项；历史名称仍单独待追溯。

## 验证

- `tests.architecture.test_project_context_boundary`、`tests.test_asset_batch_selection_service` 与纯模块编译检查：8 项通过。

状态：门禁未全绿，按失败门禁提交；路线图第二项及整份路线图仍未完成。

实施提交：待提交
