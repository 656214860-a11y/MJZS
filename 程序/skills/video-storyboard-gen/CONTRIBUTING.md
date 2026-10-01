# 贡献指南

感谢改进本技能。提交应保持中文视频分镜这一核心用途，避免引入需要密钥、网络或付费 API 的基础验证流程。

## 开发流程

1. 从最新主分支创建短生命周期分支。
2. 行为变更先添加会失败的 `unittest`，再实现最小修复。
3. 保持 `SKILL.md` 聚焦，将大型词库和背景说明放入 `references/`。
4. 更新受影响的 README、示例、eval 或 changelog。
5. 运行：

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_repo.py
python3 -m compileall -q scripts tests
```

## 约定

- Python 仅使用标准库，并保持确定性、跨平台路径和 UTF-8 行为。
- 不提交生成产物、凭据、个人数据或无授权素材。
- 示例中的产品、平台和健康声明必须中性、可核验，不暗示授权或保证效果。
- 使用 Conventional Commits，例如 `feat: add csv output`、`fix: reject empty platform`。
- 提交贡献即表示贡献者确认其拥有所提交内容的必要权利，并有权按本仓库适用的 MIT License 提供该内容。

问题与拉取请求应说明动机、行为变化、测试证据和任何兼容性影响。
