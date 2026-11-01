# R1755：仓库卫生——忽略微信输入法日志目录（GITIGN）

## 三个问题

1. **本轮类型**：结构治理轮（仓库卫生，仅改 `.gitignore`）。不改任何生产代码、测试、用户数据。
2. **测试与基线**：未新增测试。验证为 `git status` 前后对比与 `git check-ignore -v` 命中规则；轮次基线门禁在提交脚本中运行。未跑全量（不触及源码，不计源码轮）。
3. **欠账**：无新增。

## 现象与改动

- 进程工作目录为 `程序\` 时，微信输入法（WeType）会在其下写 `Tencent\WeType\` 运行日志
  （`MM_TIP.mmap3`、`MM_TIP_20261019.xlog`、`wetype_tsf_ui.log`，共约 153 KB），
  使主树长期带一行 `?? 程序/Tencent/`，并在领号（`round_claim.py next` 要求干净树）时造成阻碍。
  这些文件与项目无关，不应入库。
- 改动：根 `.gitignore` 的「运行日志」段后追加 `/程序/Tencent/`。
- 不删除该目录里的现有文件（它们属输入法，不属项目）。

## 验证

- 改前 `git status --short`：`?? "程序/Tencent/"`；改后：不再出现该行。
- `git check-ignore -v 程序/Tencent/WeType/wetype_tsf_ui.log` 命中 `.gitignore` 新增规则。
- 断言未动（未触及任何测试）。

## 独立验收（Claude，主工作区）

- 改动仅 `.gitignore` 一处（新增 2 行含注释）；`git status --short` 在改动后不再显示 `程序/Tencent/`。
- 用户直接授权此项处理（选项 1：加入 .gitignore）；未删除输入法日志文件。
- 纯仓库卫生，未跑冒烟／架构／全量；提交脚本内运行 `test_round_baselines`。
