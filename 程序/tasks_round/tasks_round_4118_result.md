# R4118 结果：预览工具里一句拒绝提示从 51 个字压到 38 个字（合入出口检查的静态门禁拦下后的更正）
<!-- round-evidence: {"commit_base": "28cde767", "credential_hits": 0, "evidence_sha256": "8c9a624b25308e79", "exit": 0, "failed": 0, "passed": 29, "round": 4118, "tests": "run_selftests.py -k preview_app"} -->

## 开头三问

- （一）本轮属于哪种类型：修正轮。队列项 DEV-PREVIEW，车道目录 l4-empty-pages，分支 `codex/dev-preview`，轮次 4118，接在 R4099 的提交后面。来源：验收窗口 2026-11-22 23:44 把这条分支合入主干时，出口档 CI 第 2 步（静态门禁）没过，合并工具没有占主干、没有领号，主干仍是 `89fdb829`。合并工具在跑 CI 之前已经把本分支变基到主干上：R4099 的提交号从 `e7653b1b` 变成 `28cde767`，EC-2 的两笔变成 `a1faadf2`（R4098）、`4b8583e4`（R4102），内容没有变；本轮接在 `28cde767` 后面。做的人：验收窗口（Claude Fable 5.2），也就是 R4099 的接手人。
- （二）测试跑了吗、三个基线：静态门禁九个模块改前红（合入时出口档 CI 跑的那一遍，47 条里红 1 条）、改后绿（在车道里单独跑，47 条，`OK`）。点名测试 `preview_app` 由提交工具在提交时跑，结果记在 `tasks_round/evidence/R4118.json` 和本文件第二行的戳里。默认冒烟、整套架构门禁本轮没有单独跑：本轮只改了一句提示文字，这两样在下一次合入的出口档 CI 里会跑（第 1 步、第 3 步），没过就合不进去。全量自测没有跑（用户验证期不跑全量；欠账以 `full-safe-receipts.json` 为准，本轮没有改变它）。
- （三）欠账少了吗：消掉 R4099 带进来的一处违规（提示文字超过 45 个字）。没有新增欠账，没有改任何门禁、基线或豁免表。

## 拦下的原文

合入命令 `scripts\dev.py merge codex/dev-preview`（主工作区，23:44），出口档 CI 在车道里跑，日志是车道的 `logs/ci_最近.log`（23:44:06 开始，23:44:37 写完）：

```text
[CI] 默认冒烟 退出码 0，用时 0.2 秒
[CI] === 静态门禁 ===
FAIL: test_no_popup_goes_over_the_limit (tests.test_copy_rules.PopupCopyTests.test_no_popup_goes_over_the_limit)
scripts/preview_app.py:363（1 行 51 字）预览窗口只在车道工作树里打开：主工作区的代码目录里放着正式应用的数据，要看主干上的效果请直接开正式应用
Ran 47 tests in 30.713s
FAILED (failures=1)
[CI] 静态门禁 退出码 1，用时 31.6 秒
[CI] 失败
```

规则是 `tests/test_copy_rules.py` 的提示文字上限（不超过 3 行、45 个字），它也扫 `scripts/` 下 `raise ValueError("…")` 里的文字。

## 改了哪些文件

| 文件 | 改动 |
|---|---|
| `scripts/preview_app.py` | 2 增 2 删（第 363–364 行，同一句话的两段字符串）：「预览窗口只在车道工作树里打开：主工作区的代码目录里放着正式应用的数据，要看主干上的效果请直接开正式应用」（51 个字）改成「预览只能在车道工作树里开：主工作区放着正式应用的数据，看主干效果请开正式应用」（38 个字）。判断条件、抛出的异常类型、别的行都没动。 |
| `tasks_round/tasks_round_4118_result.md` | 本文件。 |

搜索过 `tests/` 下所有 `.py`：只有 `tests/test_preview_app.py` 提到预览工具；它用 `in_linked_worktree` 的返回值和「不开窗口、不建数据、不改环境」来断言这条拒绝，没有哪条用例按这句话的原文断言，所以测试文件没有改。`runbook.md` 里没有引用这句原文，没有改。

## 如实说明

- （一）这处违规是 R4099 带进来的，当时没有查出来，原因在验收窗口：DEV-PREVIEW 的验收命令是点名测试加 `smoke_test.py --architecture`，不含 `tests.test_copy_rules`；提交工具只跑凭据扫描和点名测试，提交钩子只跑两个静态检查模块（R4099 结果文件「如实说明」第（八）条）。静态门禁的九个模块要到合入的出口档 CI 才会全跑。R4099 的验收依据里「验证通过」指的是那两条验收命令，不含这一组。
- （二）为了不再发生：验收窗口从 23:46 起对等合入的车道逐个预跑静态门禁九个模块（脚本在仓库外的 `.agent-tmp/ccc4a5fe_static_gate.ps1`，只跑测试，不写车道），并在心跳里请各窗口交付前自己跑这一组。这是做法上的补救，没有改工具：验收命令和提交工具仍然不含这一组，要不要把它加进提交工具（每次提交多约 35 秒）另开一项，由需求机动窗口定。
- （三）这两行更正没有经过另一个模型的只读审查：DEV-PREVIEW 本体的只读审查是在改之前做的。写本文件时正要在心跳里请编码预备、推进预备两个窗口看一眼这两行，还没有回复。
- （四）文字改短以后少了两处信息：「代码目录里」（说明正式应用的数据放在主工作区的哪里）和「直接」。这句话只在命令行里打给运行预览命令的人看，不在应用界面里出现；完整的缘由在 R4099 结果文件「预览隔开了什么」第 3 条和 `runbook.md` 的「合入前看效果」一段。
- （五）没有在真实窗口或命令行里实际触发过这句提示（要在主工作区运行预览命令才会出现，没有这样做）。
- （六）测试进程降到 BelowNormal 优先级；没有新建工作目录。

## 命令与退出码

工作目录都是车道的 `程序`，`PY` 指主工作区 `运行环境\Python\python.exe`；时间是 2026-11-22 本机时钟，取自命令输出。

| 命令 | 退出码 | 结果 |
|---|---|---|
| 合入时的出口档 CI（23:44:06–23:44:37，改前） | 1 | 第 1 步默认冒烟退出码 0；第 2 步静态门禁 `Ran 47 tests`，`FAILED (failures=1)`，原文见上；第 3 步没有跑到 |
| `PY -B scripts\dev.py claim`（23:46:51） | 0 | 领到轮次 4118 |
| `PY -B -m unittest tests.architecture.test_static_hygiene tests.test_static_names tests.architecture.test_print_ratchet tests.architecture.test_module_size_ratchet tests.architecture.test_function_size_ratchet tests.architecture.test_silent_exception_ratchet tests.architecture.test_todo_comment_snapshot tests.architecture.test_skip_hygiene tests.test_copy_rules`（23:46:46–23:47:26，改后） | 0 | `Ran 47 tests in 38.189s`，`OK` |
| 提交工具点名 `preview_app` | 见第二行的戳 | 提交时由工具跑 |

## 未覆盖项

- 未跑全量自测（用户 2026-11-22 19:52 决定验证期间不跑全量）；默认冒烟和整套架构门禁本轮没有单独跑，由下一次合入的出口档 CI 跑。
- 没有另一个模型审过这两行（见「如实说明」第（三）条）。
- 没有实际触发过这句提示。
- R4099 结果文件「未覆盖项」里列的各条都还在，本轮没有动。
- 未 push。

## 提交

本文件随 R4118 的提交一起入库（分支 `codex/dev-preview`）。写本文件时提交号还没有产生，提交号见 `git log` 和会话接续记录里验收窗口一节。
