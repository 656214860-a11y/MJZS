# R4070 — 文档轮：分发清单声明本机对话与派单工具目录不分发（docs-only）
<!-- round-evidence: {"commit_base": "5c85dd13", "credential_hits": 0, "evidence_sha256": "8244ac91083032b9", "exit": 0, "failed": 0, "passed": 21, "round": 4070, "tests": "run_selftests.py -k distribution"} -->

## 三问

1. **轮次类型**：文档轮（docs-only）。只改 `程序/distribution_manifest.md` 一行，不动代码、测试和其他文档。
2. **测试跑了吗、三个基线各是什么结果**：跑了 `tests.test_distribution_selfcheck`（3/3）、`tests.test_distribution_build`（18/18）、`smoke_test.py --architecture`（696/696，失败集合为空）。默认冒烟与全量未跑（文档轮不要求）。这三项是在新增行补上 `.devin/**` 之前跑的；补上之后重跑的结果见「验证」一节末尾。
3. **欠账少了吗**：少了主工作区上一直存在的 2 条红（`test_manifest_covers_every_file`、`test_built_copy_imports_entry_modules`），根因是项目根目录下几个本机目录没有在分发清单里声明。

## 改了什么

| 文件 | 改动 |
|---|---|
| `程序/distribution_manifest.md` | 「必须排除」表在 `.claude/**`、`.codex/**`、`.agents/**` 那一行之后新增一行，声明 `.agent-chat/**`、`.agent-tmp/**`、`.cpa-stage-fast/**`、`.devin/**` 不分发（类别「本机对话与派单工具产物」）。已有行未改。 |

`git diff --numstat`：仅 `程序/distribution_manifest.md`，1 增 0 删。

## 为什么

主工作区里 `tests.test_distribution_selfcheck` 的 3 条用例红 2 条（`test_manifest_covers_every_file`、`test_built_copy_imports_entry_modules`）。原因是项目根目录下的 `.agent-chat/`（对话工具写的会话记录）、`.cpa-stage-fast/`（派单技能留下的暂存脚本）未在清单里声明保留或排除；`.agent-tmp/` 是同一工具约定的临时目录，本机当前没有，一并预先声明。这些目录只在本机存在、未纳入版本管理，不是运行时内容，因此声明为「不分发」。

`.devin/` 是后来补上的：派单技能给 Devin 写本机权限配置时，会在工作树根目录生成这个目录（`config.local.json`、`.cpa-exec-allow.json`，已被 .git/info/exclude 忽略）。本轮第四次派工改由 Devin 执行，车道根目录因此出现了它，提交工具跑 `run_selftests.py -k distribution_selfcheck` 时 `test_manifest_covers_every_file` 红了，失败原文是 `AssertionError: Lists differ: ['.devin/.cpa-exec-allow.json', '.devin/config.local.json'] != []`。它和前三个目录一样是派单工具留在本机的产物，所以并进同一行声明；不补的话，凡是派过 Devin 的工作树里这条用例都会红。

## 验证

工作目录 `程序`。核对命令用车道里的清单去核对主工作区文件列表，只打印未声明文件数与所在顶层目录名：

```
& "D:\漫剧制作助手\运行环境\Python\python.exe" -B -c "import sys; sys.path.insert(0, 'scripts'); import distribution_build as d; from collections import Counter; u = d.plan(d.ROOT.parents[2], d.parse_manifest())['undecided']; print('undecided', len(u), dict(Counter(x.split('/')[0] for x in u)))"
```

- 改前输出：`undecided 27 {'.agent-chat': 21, '.agent-tmp': 2, '.cpa-stage-fast': 4}`。改前输出由本卡前一位执行者在改动之前运行，本次接管没有重跑。
- 改后输出：`undecided 0 {}`。

测试：

- 改后 `python -B -m unittest tests.test_distribution_selfcheck -v`：`Ran 3 tests`，`OK`。
- 改后 `python -B -m unittest tests.test_distribution_build`：`Ran 18 tests`，`OK`。
- 改后 `python -B smoke_test.py --architecture`：`Ran 696 tests`，`OK`，失败集合为空。

说明：车道工作树里这个测试改前就是绿的，红只出现在主工作区，所以改前改后是拿车道清单核对主工作区文件列表得到的；主工作区里的测试要等合入后才会变绿。

补上 `.devin/**` 之后重跑（Devin 执行，工作目录 `程序`）：`run_selftests.py -k distribution`（`test_distribution_selfcheck` 和 `test_distribution_build` 两个文件）共 21 条用例，全过；`smoke_test.py --architecture`：Ran 696 tests，OK，失败集合为空。

本轮由六次派工接力完成：改前输出和新增的那一行由前两次派工的执行者（OpenCode）完成；现场核对、改后核对、上面「测试」里的三项、领号和本结果文件的初稿由第三次派工的执行者（OpenCode）完成，它在提交之前因免费额度用尽退出；第四次派工由 Devin 执行，改了这段接力说明，提交时被门禁拦下（点名测试红 1 条，原因见「为什么」）；第五次派工仍由 Devin 执行，给新增行补上 `.devin/**`、重跑上面两项并更新了本结果文件，提交时被提交工具拒绝（原文「显式提交停止：轮次已归属其他工作树、分支或命令参数：R4070.json」；那次命令的 `--tests` 参数与第四次不同，而提交工具对同一轮次的重试只接受与上一次完全相同的命令和文件内容）；第六次派工由 OpenCode 执行，只改了这一段，没有改分发清单，也没有另外重跑上面的测试：先用 `git add` 按路径暂存分发清单和本结果文件，再用提交工具不带文件参数的用法提交已暂存的内容（点名测试 `--tests distribution` 和门禁由提交工具自己跑），第四次留下的那份重试登记没有动。

## 没做的

- 没跑全量自测（`run_selftests.py --all --safe`）。
- `.agent-chat/`、`.agent-tmp/`、`.cpa-stage-fast/` 要不要删由负责人另定；本轮只声明「不分发」。
