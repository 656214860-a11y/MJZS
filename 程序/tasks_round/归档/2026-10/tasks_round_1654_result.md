# R1654 修复轮：补声明 R1625 遗留的三份开发文档（distribution_manifest）

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮（修全量唯一遗留红）。根因：R1625 新增 `data_model.md`、`runbook.md`、`task_states.md` 时未在 `distribution_manifest.md` 声明保留或排除，`test_distribution_selfcheck.test_manifest_covers_every_file` 只在全量跑，故自 R1624 后首次全量才暴露（R1651 结果文件 D 节已登记）。同类扫描：该测试列出的未声明文件仅此三份。
2. **测试跑了吗？三个基线过了吗？** 定向 `tests.test_distribution_selfcheck` 3/3；默认冒烟见 B。未跑架构门禁全量与安全全量（只改 .md）。
3. **project_status.md 的欠账少了吗？** 欠账计数不变（纯文档）；但后台全量上次红的唯一原因即本测试，补声明后下次后台全量预期转绿，**尚未实测**。

## A 改动

`程序/distribution_manifest.md` 第 44 行（开发文档类）追加 `程序/data_model.md`、`程序/task_states.md`、`程序/runbook.md`。归类依据：三份文档自述为“文档是投影、以代码为准”的字段字典／状态词表／运行手册，面向开发与运维，不是用户资料，与同行的 `architecture.md`、`design_tokens.md` 同类。

## B 验证

- `python -B -m unittest tests.test_distribution_selfcheck` → 3/3 OK
- `python -B smoke_test.py` → 失败 0 项

## D 未做与局限

- 归类为“开发文档”意味着升级包不携带 `runbook.md`；若希望用户机器上也随附运行手册，应改为“保留”，需用户裁决。
- 未手动触发全量验证后台全量转绿，等 post-commit 钩子自动补跑。
