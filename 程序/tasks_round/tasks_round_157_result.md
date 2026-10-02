# 第 157 轮：三虎阶段模板测试迁移

## 改动

- 将 `test_skill_templates.py` 的实际测试实现迁入 `tests/test_skill_templates.py`。
- 根目录保留同名兼容入口，避免既有脚本或人工执行命令失效。

## 验证

- `python test_skill_templates.py`：3 条通过。
- `python -m unittest tests.test_skill_templates`：3 条通过。
- `python run_selftests.py --serial -k test_skill_templates`：3 条通过，增量台账刷新。

## 风险与下一步

- 用例只使用临时目录中的状态文件，并以本地回调模拟阶段动作；不触发 GUI、网络或真实项目写入。
- 下一轮继续审查根目录测试，优先迁移同等隔离的逻辑用例；兼容入口继续保留。
