# Round 222 结果：分镜目录变更签名下沉

## 改动文件

- `storyboard_catalog_service.py`
- `storyboard_files.py`
- `tests/test_storyboard_plan_service.py`

## 改动摘要

将文件目录变更快照迁入无 Tk 目录服务，页面观察器继续使用同名兼容入口；验证忽略空文件和内部历史目录。

## 验证结果

- `test_storyboard_plan_service`：4/4 通过。
- 默认 `smoke_test.py`：8/8 通过。
