# Round 224 结果：分镜目录派生下沉

## 改动文件

- `storyboard_catalog_service.py`
- `storyboard_files.py`
- `tests/test_storyboard_plan_service.py`

## 改动摘要

将 JSON 工作目录和用户可读文档目录的阶段路径派生迁入无 Tk 目录服务；页面模块保留兼容门面。

## 验证结果

- 服务与既有路径兼容回归：6/6 通过。
- 默认 `smoke_test.py`：8/8 通过。
