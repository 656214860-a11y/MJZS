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

## 后台首次实测发现（同轮补记）

- 第一次后台全量在干净检出里出 100+ 条红：本仓库的 4 个 SKILL／参考包登记为 gitlink（无 .gitmodules），检出里是空目录。`auto_full_safe.py` 增加 `_fill_embedded_repos()`，把它们连 `.git` 从主树拷入 `.wt/ci`，检出保持干净（status 无输出）。
- 修好后第二次后台全量（555 秒、HEAD 7efd764）只剩 2 条红，均为 R1439 的回归：`test_core` 的两个旧桩对象没有 `root`／`projects.info`／`win` 属性，而 `project_row_text`／`mark_current_project` 直接访问。已改成 `getattr` 容错（装饰性标记失败不得影响打开项目），`test_core`＋`project_switch_guard`＋`project_rename_reconcile` 定向通过。教训：R1439 当时只跑了 `-k project desktop_startup ui_edges`，漏掉了 `test_core`，这正是全量欠账要兜住的那类漂移。
- 该次全量未全绿，所以没有写凭据；本提交触发的下一次后台全量用于清账。
- 后台全量清账：HEAD `4407068` 的干净检出上 `--all --safe` 全绿（577 秒、退出码 0），凭据已写入 common-dir，`--status` 欠账归零，架构门禁 `test_full_safe_all_is_required_after_eight_source_rounds` 随之转绿。
- 真实提交时钩子没起进程、手动 `git hook run post-commit` 却正常：原因是钩子环境里 git 导出的 `GIT_INDEX_FILE` 等变量被子进程继承。`spawn()` 现在剔除全部 `GIT_*` 再起子进程，`run()` 的启动异常写进日志；新增 `tests/test_auto_full_safe.py`（3 条）。该修复在下一次自然提交时做端到端复核。
- 更正：上一条「清账」不成立。577 秒那次全绿没有写凭据——`run_selftests` 只在 master 分支检出上写凭据，而 `.wt/ci` 是分离检出。新增 `receipt_checkout_allowed()`：主干检出，或环境变量 `AUTO_FULL_SAFE_HEAD` 等于当前 HEAD（由 `auto_full_safe.py` 设置）时才写；新增 1 条用例。此前 `--status` 仍显示上次全量 R1420，欠账尚未清零，待本提交触发的后台全量写入凭据后再确认。
- 钩子端到端已确认：上一次真实提交（144b341）正确起了后台进程，说明剔除 `GIT_*` 的修复有效。
