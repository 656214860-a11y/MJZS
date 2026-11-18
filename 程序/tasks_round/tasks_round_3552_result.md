# R3552 结果文件 — 会员登录安全加固轮 4：签名覆盖服务端时钟
<!-- round-evidence: {"commit_base": "7a8c15e5", "credential_hits": 0, "evidence_sha256": "a19e8ac3d08dd0e1", "exit": 0, "failed": 0, "passed": 0, "round": 3552, "tests": "docs-only"} -->

## 三问

1. 本轮为功能轮，对应 B-4 前半和 D3。服务端统一签发入口把 UTC 秒级 `iat_server` 纳入签名。响应体继续返回 `server_time`。桌面仓只同步设计与轮次证据。
2. 服务端 `.venv/Scripts/python.exe -m pytest --tb=short` 退出码 0，收集 107 条。兼容测试验证登录与续签的 `iat_server` 一致，改动该字段会被拒绝，无此字段的旧租约仍可访问账户接口。桌面仓纯文档，本轮未运行桌面冒烟、架构门禁与全量。
3. 新租约提供可由客户端信任的服务端时钟来源。租约仍是签名字符串，无数据库迁移。

## 提交

- 服务端 `main` 提交 `c5615bf`，未推送。
- 桌面端补记租约字段表和时钟读法，提交证据由 dev.py 生成。
