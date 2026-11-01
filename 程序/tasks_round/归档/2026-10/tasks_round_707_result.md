# R707 结构治理轮（执行）结果：L3 注入项目上下文

## 独立任务书

来源：`架构模块接口统一.txt` 第一批第 2 项。建立 L0 项目上下文契约，并以交付成片导入这一既有 L2 写服务为试点，固定“L3 构造、L2 消费”的依赖边界。

## 完成内容

- 新增 L0 `project_context.ProjectContext`：字段严格为 `{root, stage_resolver, settings_snapshot, cache}`；设置快照复制后冻结，调用方后续变更不会影响本次服务操作。
- `stage_execution_service.project_context()` 是唯一生产构造入口；`import_delivery_master()` 统一装配该上下文和 `publish_stage_bytes`，桌面仅委派 L3。
- `delivery_import_service.import_final_master()` 现仅消费注入上下文的 `stage_resolver('delivery')`；不再导入 `project_stages`，也不自行拼接项目内部路径。
- 新增 `test_project_context.py` 与 `test_project_context_boundary.py`：覆盖快照隔离、阶段解析、L2 不构造上下文、L3 唯一构造及无项目路径拼接；既有交付导入测试改用真实注入上下文。
- `AGENTS.md`、`architecture.md` 和 `PROJECT_MAP.md` 已同步唯一权威与分层职责。

## 测试说明

本次改测试因架构接口契约变更，断言强度未弱化：原导入格式、空文件、源文件保留、发布器调用及系统失败结果断言全部保留；仅将原始项目根参数改为 L3 构造的真实上下文，并新增 L3/L2 边界守卫。

## 验证

| 项目 | 结果 |
| --- | --- |
| 受影响 `smoke_test.py --affected project_context delivery_import_service stage_execution_service desktop` | 9 项通过；定向 24 条 / 0 红 |
| 默认 `smoke_test.py` | 8/8 |
| `smoke_test.py --architecture` | 107/107 |
| 完整 `run_selftests.py --all --safe` | 3,415 条 / 0 红（747.1 秒） |

完整安全日志：`维护记录/r707_project_context_safe_all.log`。

## 边界与后续

本轮只为交付成片导入建立生产试点；其余 L2 服务尚未迁入 `ProjectContext`。下一独立批次应继续“架构模块接口统一”第一批第 3 项：由 L3 向更多 L2 写服务注入发布器，单轮最多三个服务。未触碰用户项目数据、SKILL、注册表或 UI 布局。

`[TASK_COMPLETE]`
