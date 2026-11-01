# R2292 结果：合并命令忽略本机设置文件改动（修复轮）

## 三问
- 做了什么：`dev.py merge` 的脏检查去掉 `.claude/settings.local.json`（缓存 TTL 钩子会改它），新增 `foreign_changes` 与测试。
- 为什么：主检出该文件常被钩子改动，会让合并命令误拒。
- 没做：未跑全量；断言未动。

## 验证
- `tests/test_merge_round.py` 4 例全过（含新增的 settings.local.json 忽略与他人改动仍拦截两条断言）。凭据扫描：未触碰密钥。
