# Round 231 结果：工作流目录服务直连

## 改动文件

- `workflow_context.py`

## 改动摘要

`workflow_context.snapshot()` 直接依赖 L2 `storyboard_catalog_service` 的目录查询与忽略规则，不再在运行时导入 L4 分镜页面模块。

## 验证结果

- 工作流与分层校验：78/78 通过。
- 默认 `smoke_test.py`：8/8 通过。
