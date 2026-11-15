# 安全说明

## 信任边界

- **本地用户**：应用运行在用户自己的 Windows 会话里，能读写用户目录。项目数据只在用户选定目录；删除统一经回收站（`storage_maintenance.recycle_paths()`），可恢复。
- **云端模型与 API**：密钥由用户在「模型管理」配置，经 `model_secrets`／DPAPI 加密保存在 `程序/private/`（不入库、不进日志）。出站请求集中在 `api_endpoints` 传输层与 `platform_tools`，带超时、重试与响应体上限。
- **第三方本地服务**：ComfyUI、ffmpeg、剪映等路径由用户配置（`config.json`），程序不内置、不校验其二进制来源；`external_tools.lock.json` 只锁随附解释器。
- **用户导入内容**：SKILL 包与工作流 JSON 是不可信输入。导入经 `skill_import_service`：体积上限、符号链接拒绝、暂存区、换入后试冻结、失败回滚、导入台账。

## 已有防线

- 提交时凭据形态扫描（`维护记录/基准脚本/round_evidence.py` 的 SECRET_PATTERNS：私钥、OpenAI/AWS/GitHub/Slack/Google 风格密钥、赋值形态密钥），命中即拒绝提交。
- `tests/architecture/test_secret_sink_audit.py`：密钥不得流入日志、JSON、prompt。
- `.gitignore` 排除 `private/`、`.env`、`.dpapi`、日志与用户项目目录。
- 分发副本按 `distribution_manifest.md` 白名单生成，不携带私有数据与开发工具。

## 开发者工具

`dev.py lint` = ruff（E9/F821/F601）+ mypy（契约层严格）+ `tools_lock.py --check`。配置见 `pyproject.toml`、`dev-requirements.txt`，均不进分发副本。历史密钥扫描可用 gitleaks（`.gitleaks.toml`），属 CI/发布前检查。

## 发现漏洞

请勿在公开渠道贴密钥或用户数据。私下联系仓库维护者；涉及凭据泄漏时先吊销该密钥，再评估历史提交是否需要清理（改写历史需全体协作者协调，本项目目前无公开远端协作）。
