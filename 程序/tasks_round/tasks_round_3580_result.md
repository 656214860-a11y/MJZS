# R3580 结果文件 — 关闭整体验收发现的模型池丢写
<!-- round-evidence: {"commit_base": "84582f1a", "credential_hits": 0, "evidence_sha256": "f7220bd4772f1e84", "exit": 0, "failed": 0, "passed": 112, "round": 3580, "tests": "run_selftests.py -k l1_lost_update l1_transport_requests model_pool model_delete"} -->

## 三问

1. 本轮为修复轮。会员加固合并候选全量执行 8999 条，发现模型池双进程保存可能覆盖较新的健康记录。相同旧快照在既有 master 上可稳定复现。
2. 模型池、严格读写、传输和删除定向 112/112 通过，含原双进程断言与新增的确定性回归。HTTPS 验收在 PATH 增加本机已有 Git OpenSSL 后通过。分支覆盖率原目标组重测 1762 条无失败，model_pool 56/135，覆盖率门禁复验 5/5。候选全量复验待完成。
3. 普通配置保存持发布锁重读并保留后台健康记录；已在锁内变更配置的入口用同一落盘函数，保留其严格读取契约。快照和其他字段写入方式沿用既有机制。

## 证据

- 候选首跑红项为 `test_l1_lost_update.py:264` 的健康记录缺失及 `test_l1_transport_requests.py:160` 的 OpenSSL 发现失败。
- 保留双进程测试原断言。新回归明确构造先读、后台写入健康记录、再保存旧配置的顺序。
