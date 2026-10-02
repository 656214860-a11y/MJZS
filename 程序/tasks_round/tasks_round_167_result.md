# 第 167 轮：项目上下文测试归位

## 改动

- 将不依赖桌面界面的项目上下文、剧本读取、Skill 定位和工具路径缓存测试迁入 `tests/test_context.py`。
- 根目录 `test_context.py` 改为兼容入口，既有的直接运行命令仍然有效。
- 测试实现以自身位置计算项目根目录，不再依赖调用时的当前目录。

## 验证

- `python test_context.py`：13 条通过。
- `python -m unittest tests.test_context`：13 条通过。
- `python run_selftests.py --serial -k context`：实际执行 1 个测试文件、13 条通过。

## 风险与下一步

- 本轮仅整理测试代码；不改业务流程、模型配置、用户数据或项目素材。
- `test_copy_rules.py` 是全程序静态扫描器，迁移会改变扫描根和文案计数基线，已保留在根目录，后续单独审计。
