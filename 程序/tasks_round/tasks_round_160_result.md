# 第 160 轮：提示词模板测试迁移

## 改动

- 将 `test_prompt_templates.py` 的实际测试实现迁入 `tests/test_prompt_templates.py`。
- 根目录保留同名兼容入口，以支持旧的直接执行方式。

## 验证

- 用例只校验本地纯文本模板、资产规范和分镜契约；不读取真实项目、素材、密钥或 Provider 配置。
- `python test_prompt_templates.py`：15 条通过。
- `python -m unittest tests.test_prompt_templates`：15 条通过。
- `python run_selftests.py --serial -k test_prompt_templates`：15 条通过，增量台账刷新。

## 风险与下一步

- 迁移未改变提示词、契约或模型配置，只改变测试实现的位置。
- 下一轮继续审查根目录的纯逻辑测试；对依赖真实桌面实例或外部命令的测试保持审慎。
