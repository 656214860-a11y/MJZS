# R1469 修复轮：根目录整理后分发清单漏掉本机 outputs/ 草稿目录

1. **本轮类型？** 修复轮。
2. **测试与基线？** R1468 提交后手动全量（5139 条）仅 `test_distribution_selfcheck` 红：144 个文件“未决定”，全部在根目录 `outputs/` 下。修复后该文件通过；全量重跑见下。断言未动。
3. **是否欠账？** 全量需重跑转绿。

## 根因

R1468 把已入库的 `outputs/` 报告搬进 `程序/维护记录/代码腐烂审计/`，同时从分发清单排除行里去掉了 `outputs/**`。但根目录 `outputs/` 在本机仍存在——里面是被 `.git/info/exclude` 忽略的 Agent 草稿（`agent-tmp/`、`cache-hygiene/` 等，不入库）。清单只管磁盘上的文件，不管 git 是否忽略，于是这些草稿被判为“未决定”。另外 `git mv` 目录时这些草稿被一起搬走过一次，我随即用 Python 把它们原样移回根目录 `outputs/`，内容未丢。

## 改动

- `distribution_manifest.md`：排除行恢复 `outputs/**`，并注明它是本机 Agent 草稿目录。

## 提交

已提交，见 git log 标题 `R1469:`。
