# R870 协作治理轮：队列认领强制化

## 目标

落实队列 `P2-queue-enforcement`：开工前必须认领队列项，60 分钟租约到期后才能由其他人抢占。

## 实现

- `round_claim.py` 新增 `claim <任务ID> --owner <署名>` 和 `release <任务ID> --owner <署名>` 子命令。
- 认领、释放与轮次计数共用 Git common-dir 排他锁；队列 JSON 通过临时文件原子替换写入。
- 已完成项与其他署名持有的有效租约都会明确拒绝；租约过期后可抢占，原持有人与抢占人会写入 `note`；释放也保留留痕。
- `AGENTS.md` 的开工协议现要求先领轮次、再认领队列项；无法继续时必须释放。
- 本轮实际使用 `claim P2-queue-enforcement --owner Codex --lease-minutes 60` 验证 CLI 写入。

## 验收

- `D:\漫剧制作助手\运行环境\Python\python.exe -m unittest tests.test_round_claim`：6 条／0 红（包含有效租约拒绝、释放、过期抢占和已完成项拒绝）。
- `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py`：8 项／0 红。

## 备注

- R868 的完整安全全量仍有独立性能临界失败，未将其作为本轮或共享基线的全绿凭据。
