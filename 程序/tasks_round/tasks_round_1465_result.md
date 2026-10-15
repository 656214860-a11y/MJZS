# R1465 修复轮：分发自检在干净检出里误报 `.git`

1. **本轮类型？** 修复轮。
2. **测试与基线？** R1464 提交后的后台全量 5135 条里 `test_distribution_selfcheck` 2 条红（HEAD 4903dd7）；修复后该文件与 `test_distribution_build` 通过，并在 `.wt/ci` 干净检出里复验（见下）。断言未动。
3. **是否欠账？** 后台全量须在本提交后重跑转绿。

## 根因

`.wt/ci` 这类 git worktree 里 `.git` 是一个**文件**（指向主库），《分发清单》和 `ALWAYS_EXCLUDE` 只覆盖 `.git/**`（目录），于是它被判成“未决定文件”，构建拒绝继续。R1462 只在主检出（`.git` 为目录）里验证过，没覆盖干净检出，是我的验证盲区。

## 改动

- `scripts/distribution_build.py`：`ALWAYS_EXCLUDE` 加入 `.git`。
- `test_distribution_selfcheck.py` 增 1 项，锁住该规则。

## 提交

已提交，见 git log 标题 `R1465:`。
