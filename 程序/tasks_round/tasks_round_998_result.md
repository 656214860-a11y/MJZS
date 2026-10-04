# R998：迁移剪辑和交接包项目上下文

- `edit_service` 与 `handoff_service` 的项目根入口可消费 L3 注入的 `ProjectContext`，并拒绝路径与上下文不一致的调用。
- 桌面交接包发布已由 L4 直调 L2 改为 `stage_execution_service.publish_stage_handoff_bundle()`；L3 负责上下文及发布器注入。
- `final_service` 只有纯派发决定、不读取项目路径或项目设置，作为明确豁免保留审计。

## 验证

- `tests.test_edit_service`、`tests.test_handoff_service`、`tests.test_final_service` 与对应发布／项目上下文架构门禁：26 项通过。

状态：门禁未全绿，按失败门禁提交；路线图第二项及整份路线图仍未完成。

实施提交：`24d2c95`
