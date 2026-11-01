# R994 结果：旧队列入口统一 common-dir

- 认领并完成 `A-legacy-queue-gateway`：移除旧 `claim_queue.py` 的工作树私有队列读写，实现为到 `基准脚本/round_claim.py` 的纯兼容转发。
- 三项基线：定向 `tests.test_claim_queue_gateway tests.test_round_claim` 15/0；默认冒烟 8/8；R993 最近完整安全凭据为 3824/0、306.312 秒。

## 交付

- 旧 CLI 的 `show`、`claim` 等原有调用格式保留，但其默认队列、锁和校验完全由 common-dir 权威入口处理；传入工作树快照参数仍会被权威入口拒绝。
- 协作说明明确快照是自动导出的只读视图，所有新命令改用 `round_claim.py`。
- 新增三项回归，覆盖转发、参数原样交由权威校验、以及旧模块不再保留 `DEFAULT` / `publish` 私有写入实现。

## 边界

- 未修改工作树快照、用户项目、`程序/data`、`程序/private` 或生产业务语义；未新增 `.bak_*`。
- 提交哈希：待本结果最小暂存后填写。
