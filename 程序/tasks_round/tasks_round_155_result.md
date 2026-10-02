# 第 155 轮：生成图片自动导入测试迁移

## 改动

- 将 `test_auto_import.py` 的实际测试实现迁入 `tests/test_auto_import.py`。
- 根目录保留同名兼容入口，继续支持旧的直接执行方式。

## 验证

- `python test_auto_import.py`：2 条通过。
- `python -m unittest tests.test_auto_import`：2 条通过。
- `python run_selftests.py --serial -k test_auto_import`：2 条通过，增量台账刷新。

## 风险与下一步

- 该测试只使用临时目录与内存 PNG 字节，不读取用户项目、网络或 GUI；迁移风险低。
- 下一轮继续逐个审查根目录测试的隔离性，再迁移可安全移动的实现；不删除兼容入口。
