# R4501 旧签名租约换代保护
<!-- round-evidence: {"commit_base": "d13bb0a22", "credential_hits": 0, "evidence_sha256": "db45c24c4a711fc6", "exit": 0, "failed": 0, "passed": 73, "round": 4501, "tests": "run_selftests.py -k test_account_client test_renew_concurrency"} -->

- 修复轮。补充 R4500 账号会话验收：历史租约的签名密钥已不可识别时，客户端不能证明新租约和原账号属于同一主体。续签或兑换必须保留当前存储并要求显式登录。
- 回归先红后绿：真实控制器、临时会话文件和签名测试租约。修改前新主体覆盖旧租约，修改后返回失败，旧租约和刷新令牌保持原值。已验签旧会话仍支持续签更换 sid。
- 测试计数由提交凭据记录。默认冒烟和架构以合并出口 CI 为准；本轮未单独执行全量。已知风险沿用 [PROJECT_HEALTH](../../PROJECT_HEALTH.md)。
