# 变更日志

本项目按轮次（R<N>）演进，详细记录见 `程序/tasks_round/`。此处只保留对用户可见的里程碑。

## 未发布

- 统一错误码注册表（`error_codes.py`）：网络、凭据、资产、契约类失败带可重试标记与修复建议。
- SKILL 导入护栏：单文件与包体积上限、符号链接拒绝。
- 提交凭据扫描扩展 GitHub／Slack／Google 密钥形态；新增开发期 ruff＋mypy＋工具哈希核对（`dev.py lint`）。
- 安全说明（`SECURITY.md`）、术语表（`GLOSSARY.md`）、ADR 起步（`docs/adr/`）。
