# R1404：并行分支与共享状态文件治理规则

类型：结构治理轮（§3，只改 `AGENTS.md` 规则文字；不改生产代码与测试）。中央轮次：1404。执行者：Claude Code（用户指定，不经 Codex）。

## 三个必答
- 本轮类型：结构治理轮——起因是 R1403 合并 `codex/R1308-idea-brief-split` 时 `project_status.md` 冲突被整块取一边，误删 R1357–R1312 共 26 条记录（已由 c7cdd96 补回）。
- 测试：架构 `smoke_test.py --architecture` **341/341**；默认冒烟通过。
- 欠账：只改规则文字、未命中 §5 → **不跑全量**（最近绿全量 R1403 eb66d89，5006/5006）。

## 改动（`程序/AGENTS.md`）
- 规则 27 并行硬规则：活跃 `codex/*` 车道由「≤2，用户可临时降到 1」改为「默认 1 条，经用户同意可升到 2 条（上限 2）」。
- 规则 41 补充：
  - 非 master 分支／worktree 不得写 `.agent-handoff/backlog.md`、`.agent-handoff/snapshot.md`；分支记录只写本轮结果文件，合入 master 后单独提交补记。
  - 合并时共享状态文件不得整块取一边；合并后须贴两条比对命令原始输出（删除行为空、轮次号为两边并集）。

## 核对
- R1403 合并后 `project_status.md` 与合并前 master（e1cfbdb）相比只差表头「当前轮次」一行；分支 71165f9 的全部 `R<n>` 记录在 master 均存在，无遗失。

## 提交
- 本文件＋`AGENTS.md`＋`project_status.md` 表头，一次提交（hash 见 git log）。
