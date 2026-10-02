# 第 164 轮：剧本结构阶段契约测试迁移

## 改动

- 将 `test_script_structure.py` 的实际测试实现迁入 `tests/test_script_structure.py`。
- 根目录保留兼容入口，保障旧的直接运行命令。

## 验证

- 用例只建立临时项目，覆盖自然剧本来源解析、结构化输出、Writer/Editor 修订和阶段执行；不调用真实模型或修改用户项目。
- `python test_script_structure.py`：11 条通过。
- `python -m unittest tests.test_script_structure`：11 条通过。
- `python run_selftests.py --serial -k test_script_structure`：11 条通过，增量台账刷新。

## 风险与下一步

- 已覆盖创意目录、Provider/模型子目录和 Agent 原稿作为剧本结构阶段输入的路径，防止上游剧本无法读取的回归。
- 下一轮继续整理其他无外部副作用的阶段契约测试；保留真正集成型的测试在根目录直到发现策略统一。
