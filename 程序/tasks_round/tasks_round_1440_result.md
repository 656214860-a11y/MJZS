# R1440 结果：全量欠账改按源码轮次计数、阈值 8、后台自动补跑

三个收尾问题：
- 本轮类型：可靠性轮（验证治理变更，用户批准三条建议）。
- 测试与基线：`test_selftests`、`test_git_hooks`、`test_round_baselines` 定向通过（新增 3 条用例）；默认冒烟 8/8；架构层 `--layer architecture --all` 只剩 `test_full_safe_all_is_required_after_eight_source_rounds` 一条红，这是真实欠账而非回归：本机 common-dir 的最后一次全量凭据是 R1420，其后改过源码的轮次 16 个。该欠账由本轮提交触发的后台全量补跑，未在本轮手工跑全量。
- 欠账：未减少。R1420 之后的全量欠账仍待后台跑完才能清零。

## 改动

1. 阈值 5 → 8（`run_selftests.FULL_SAFE_ROUND_INTERVAL`，唯一常量）。
2. 只数改过源码的轮次：`is_source_change()`／`count_source_rounds()`／`source_rounds_since()` 读 git 历史，标题 `R<n>:`／`R<n>-FAIL:` 的提交按轮次归并；`tests/`、`tasks_round/`、`维护记录/`、`说明/`、`logs/` 与非 `skills/` 的 md 不计；读不出历史时退回按全部轮次计。`full_safe_required()` 增加 `source_rounds` 参数，缺省行为保守不变。
3. 后台自动补跑：新增 `scripts/auto_full_safe.py`（`--status`／`--spawn`／`--run`），在根目录 `.wt/ci` 的干净分离检出上跑 `--all --safe`；新增 git post-commit 钩子（`维护记录/基准脚本/hooks/post-commit`，登记进 `install_git_hooks.HOOKS`），欠账达到门禁线前 2 个源码轮次时触发，同类任务运行中或任何异常都静默跳过，不阻塞提交。
4. `AGENTS.md` §5 表行与「全量欠账口径」「后台自动补跑」两段同步。风险触发条款不变。

## 测试

- `test_selftests`：阈值边界、源码判定与归并计数、后台触发点比门禁线提前。
- `test_git_hooks`：安装清单含 post-commit；post-commit 钩子退出码恒为 0。
- `test_round_baselines`：用例改名并改用源码轮次计数，断言结构未弱化。

## 未验证

- 后台脚本的真实端到端（`.wt/ci` 对齐、全量跑完写凭据）以本轮提交触发的那一次为首次实测，结果看 `程序/logs/auto_full_safe.log`。
- 钩子在本机 `.git/hooks` 已安装；他处克隆需运行 `install_git_hooks.py`。
