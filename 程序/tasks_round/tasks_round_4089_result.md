# R4089 结果：分支覆盖率下限还原为 78.0，基线按实测补上 file_index 新增的决策点
<!-- round-evidence: {"commit_base": "023c1e1f", "credential_hits": 0, "evidence_sha256": "2f57f6517c832794", "exit": 0, "failed": 0, "passed": 62, "round": 4089, "tests": "run_selftests.py -k branch_coverage_floor file_index"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮，队列项 UX-B34 返工的第二段，车道 codex/ux-dock-content，由验收/监督窗口直接做。依据是会话接续记录验收窗口一节「已定的决定」：覆盖率下限、基线这类门禁数字只由验收窗口用项目工具实测后改。来源是验收窗口对 R4077 的复核意见：R4077 为过架构门禁把 `维护记录/分支覆盖率下限.json` 里 file_index.py 的下限从 78.0 调到 56.0，并整份重写了 `维护记录/分支覆盖率基线.json`（file_index.py 一行写成 63/110，和实测对不上）。本轮把这两份文件改回正路：下限还原，基线只补本车道给 infra/file_index.py 新增的决策点（93 变成 110）。
- （二）测试跑了吗、三个基线：定向守卫 tests.architecture.test_branch_coverage_floor 改后 5 条全过；覆盖率用项目工具实测，file_index.py 三次都是 91/110（见「命令与结果」）；提交工具代跑的定向测试以本文件的证据行为准；架构门禁整套在本轮提交之后由验收检查另跑（见「未覆盖项」）；默认冒烟、全量自测没跑（用户验证期间不跑全量）。
- （三）欠账少了吗：少了一条（R4077 放松的棘轮收回，下限回到 78.0）；没有新增欠账；整份基线没有重测重写，另有两行实测与基线不同、本轮没有动，见「如实说明」。

## 改了哪些文件

- 维护记录/分支覆盖率下限.json：还原成主干 7ea1ddeb 的版本（file_index.py 的下限 56.0 改回 78.0，文件末尾的换行也恢复），和主干没有差异。
- 维护记录/分支覆盖率基线.json：先还原成主干 7ea1ddeb 的版本，再只改 5 个数字：file_index.py 一行的 points 93 改成 110、covered 74 改成 91、percent 79.6 改成 82.7；points_total 3065 改成 3082；points_covered 1749 改成 1766。和主干相比 5 行新增 5 行删除，其余 102 行、目标清单、tests_ok 都没有动。
- tasks_round/tasks_round_4089_result.md 是本文件。
- 没有改测试和产品代码。

## 命令与结果

下表的命令都在车道的 程序 目录下跑，进程优先级降到 BelowNormal；实测时 HEAD 是 023c1e1f（R4086）。

| 命令 | 结果 |
| --- | --- |
| python.exe -B scripts\branch_coverage_report.py 〈基线登记的 102 个目标〉（20:01 跑完一次，20:06–20:10 又跑一次） | 两次都是「file_index.py 82.7% 91/110」「模块：103；决策点：1764/3082；目标用例：存在失败／错误」，工具因此不写基线。第二次留了完整输出：「Ran 1972 tests in 238.842s」「FAILED (failures=1)」，失败的是 tests.test_script_contract.AuditTests.test_the_audit_covers_every_script_skill（车道里没有主工作区那几个内嵌的技能仓库，列出的技能少两项），与 file_index.py 无关。第一次用的是安静模式，没有留下失败明细 |
| python.exe -B scripts\branch_coverage_report.py 〈去掉 tests.test_script_contract 的 101 个目标〉 --json 系统临时目录里的文件（20:14–20:18） | 「Ran 1914 tests in 240.096s」「OK」；「file_index.py 82.7% 91/110」；「模块：103；决策点：1704/3082；目标用例：全通过」；写出的结果里 tests_ok 为 true，file_index.py 一行是 points 110、covered 91、percent 82.7 |
| python.exe -B scripts\branch_coverage_report.py 〈只取和文件索引、发布事务有关的 5 个目标〉（20:13） | 「Ran 77 tests in 8.467s」「OK」；「file_index.py 66.4% 73/110」。说明另有 18 个决策点是靠其余目标带到的，所以基线取上一行 101 个目标的数，不取这一行 |
| git checkout master -- 两份文件，再用仓库外的小脚本改基线里的 5 个数字（每个锚点必须恰好命中一次，改完按门禁的口径自检，不对就不写） | 脚本输出「entity infra\file_index.py decision points now 110」「rows changed: ['file_index.py']」「totals now 1766 / 3082 ; floor 78.0」「lines changed 5」 |
| git diff --stat master -- 两份文件 | 只有基线 1 个文件，5 行新增 5 行删除；下限表与主干没有差异 |
| python.exe -B -m unittest tests.architecture.test_branch_coverage_floor -v（改后） | 「Ran 5 tests in 0.543s」「OK」 |
| python.exe -B scripts\dev.py claim | 领到轮次 4089 |

## 如实说明

- （一）基线没有整份重测重写，沿用 R4061 的做法：只改代码变了的那一行和两个合计。原因也和 R4061 一样：在车道里用登记的 102 个目标整体重跑，有 1 条目标用例因缺主工作区的技能数据而失败，测量工具拒绝写整份基线。file_index.py 这一行的 91 来自去掉那 1 个目标后 101 个目标全通过的实测，并且和两次 102 个目标的实测一致。
- （二）这几次实测里另有两行比基线各少 1：process_wait.py 实测 4/11（基线 5/11，下限 36.4），unit_of_work.py 实测 19/49（基线 20/49，下限 32.0）。两行都不低于各自的下限，原因没有查。这两行本轮没有改，基线里仍是原值；要不要更新，留给以后整份重测时一起定。
- （三）写基线的不是测量工具，是仓库外的一个小脚本按实测数字改的 5 处；改动范围已用 git diff 和守卫测试核对。
- （四）本轮由验收/监督窗口直接改门禁数据文件，和写 R4075、R4077 的窗口是同一种模型；提交后另派一张不同型号的只读审查卡核对这 5 行和下限表。
- （五）R4077 的结果文件里「基线更新为真实测量值、没有新增欠账」一句与事实不符（当时下限被调低，基线那一行写成 63/110），以本文件为准；R4077 的结果文件本轮没有改。

## 未覆盖项

- 未跑全量自测、默认冒烟。架构门禁整套和队列项登记的定向测试（file_index、files_panel、stage_file_index_publication）由本轮提交之后的验收检查代跑，结果登记在队列里，不在本文件。
- 未 push、未 merge。
