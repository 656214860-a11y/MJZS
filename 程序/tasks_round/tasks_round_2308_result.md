# R2308 结果：dev.py merge 先等验收锁再领号（修复轮）

## 三问
- 做了什么：`scripts/merge_round.py` 在试合并与领号之前先 `wait_for_lock`（最多 30 分钟）。
- 为什么：R2301 合入时领号后又在 `commit_round` 里等了几分钟锁，期间别会话领走下一个号，提交被钩子拒（R2304≠R2305），合并只能中止重来。
- 没做：未跑全量；断言未动；只改控制流，无新单测（等锁逻辑沿用 commit_round 已有实现）。

## 验证
- `ast` 语法检查通过；`tests/test_merge_round.py` 4 例仍过。凭据扫描：未触碰密钥。
