# Round 195 结果：资产与分镜模块循环依赖消除

## 轮次类型

功能轮（优化清单 P0「view/service/adapter 拆分」的依赖层级子范围）。

## 完成内容

- `asset_context`、`asset_plan` 直接依赖无界面 `storyboard_catalog_service`。
- `storyboard_selection` 直接依赖目录服务，不再回调旧 `storyboard_catalog` facade。
- `storyboard_storage` 使用 `project_stages.assets()` 取得权威阶段路径，移除对资产上下文的反向依赖。

## 改动文件

- `asset_context.py`
- `asset_plan.py`
- `storyboard_selection.py`
- `storyboard_storage.py`
- `project_status.md`
- `tasks_round/tasks_round_195_result.md`

## 验证结果

- 受影响模块 `py_compile`：通过。
- `tests.architecture.test_no_circular_import` + 资产、文件缓存、工作流、回收回归：165/165 通过。
- 默认 `smoke_test.py`：8/8 通过。

## 审查结论

通过。旧 facade 保持对外兼容，但领域服务不再从中反向导入，静态架构循环门禁恢复全绿。
