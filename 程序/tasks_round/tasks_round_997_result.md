# R997：项目上下文历史名称审计

- 第二项范围中的 `asset_gating`、`keyframe`、`keyframe_api`、`previs`、`writing_files`、`writing_roles`、`writing_workflow` 均不存在于现行 L2 模块路径。
- 这些名称从现行 pending 清单移入 `historical_name_audit_pending`；它们既不算采用方，也不算豁免或完成，必须追溯替代入口后才可处置。
- 项目上下文棘轮补充范围四分组互斥和历史名称缺失校验，第二项现行待迁移服务为 23 个。

## 验证

- `tests.architecture.test_project_context_boundary` 与 `tests.architecture.test_service_return_contract`：12 项通过。
- `smoke_test.py --architecture` 在本轮工具时限内未完成，未取得全绿凭据。

状态：门禁未全绿，按失败门禁提交；路线图第二项及整份路线图仍未完成。

实施提交：待提交
