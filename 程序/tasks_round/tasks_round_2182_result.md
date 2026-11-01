# R2182 结果：master 提交后后台全量从不启动（修复轮）

## 三问
- 轮次类型：修复轮（§3.2）。来源：原会话「剧本准备页面调用逻辑检查」发现 R2150、R2152、R2169、R2173 提交 master 后都没有起后台全量，`auto-full-safe.lock` 不出现，`程序/logs/auto_full_safe.log` 不写，只能手动 `auto_full_safe.py --spawn` 补跑。代码偏离 runbook §4 的后台补跑约定，改代码，不改规则。
- 测试和三个基线：在 worktree 分支 `codex/wip-R2182` 上运行（经 gui_hidden），解释器用主检出的 `运行环境/Python/python.exe`。
  - 新测试改动前失败、改动后通过，见「测试」。
  - `run_selftests.py -k auto_full_safe git_hooks`：41 条，0 红。
  - `smoke_test.py --affected auto_full_safe`：通过 9 项，失败 0 项。
  - 默认冒烟：通过 8 项，失败 0 项。
  - `--architecture` 未运行：没有跨层改动，没动层级表。
  - 全量 `--all --safe` 本轮未运行。worktree 里没有 `运行环境`，提交后钩子直接跳过。
  - 完成标准（从 Claude 会话的 Bash 工具用 `dev.py commit` 提交 master 后，锁出现、日志开始写）要合入 master 才能现场核对，本轮未核对。本轮在真实仓库上模拟钩子环境做了对照，见「验证」。
- 轮次号：提交前一刻用 `dev.py claim` 领取 R2182，改动随之转到分支 `codex/wip-R2182`。
- `project_status.md` 欠账：没有减少，也没有新增（分支不写状态页，合并轮登记）。

## 复现与排查
1. 排除「进程被杀」：Bash 工具里起一个 `&` 后台进程，它再用 `spawn()` 同样的标志（`CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS | CREATE_NO_WINDOW`）派生子进程。Bash 命令返回后，两个进程都按时写出了心跳（实验 A）。在临时仓库里装同样结构的 post-commit 钩子，从 Bash 工具提交，结果相同（实验 C）。
2. 看钩子拿到的环境（实验 D）：用 `--separate-git-dir` 建 gitfile 布局的临时仓库，钩子收到的是绝对路径的 `GIT_DIR=<临时目录>/repoD-meta.git`，另有 `GIT_INDEX_FILE`、`GIT_PREFIX`、`GIT_EDITOR=:` 等，没有 `GIT_WORK_TREE`。在这个环境里从子目录 `sub/` 执行 `git rev-parse --show-toplevel`，返回 `<临时目录>/repoD/sub`，不是仓库根。
3. 在主检出上对照（实验 E）：用主检出的 `auto_full_safe.py` 算欠账。普通环境：前缀 `程序/`，改过源码的轮次 16，`required` 真，`auto_due` 真。带上钩子导出的 `GIT_DIR`、`GIT_INDEX_FILE`：前缀为空，轮次 0，`required` 假，`auto_due` 假，`--spawn` 因此静默退出。

## 根因
主检出的 `.git` 是指向 `D:/repo-meta/漫剧制作助手.git` 的 gitfile。这种布局下，git 给钩子导出绝对路径的 `GIT_DIR`，不导出 `GIT_WORK_TREE`。git 的规则是：有 `GIT_DIR`、没有 `GIT_WORK_TREE` 和 `core.worktree` 时，把当前目录当成工作树顶层。

`--spawn` 先调 `status()` 判断欠账，`status()` 经 `run_selftests` 在 `程序/` 目录下调 git（`cwd=HERE`）。于是 `--show-toplevel` 返回 `程序/` 本身，`_round_commits()` 算出的前缀为空，`程序/…` 路径一条也匹配不上，改过源码的轮次算成 0，`auto_due` 为假，`spawn()` 不起进程。原代码只给派生出去的子进程摘了 `GIT_*`，判断本身仍在钩子环境里做。

问题出在 git 给钩子的环境，与是否从 Claude 会话提交无关；按 git 的这条规则，从终端提交 master 也会中。

## 改动
- `scripts/auto_full_safe.py`：`main()` 入口先摘掉继承来的 `GIT_*`，返回时原样还原；原来的分派逻辑原样移到 `_dispatch()`。`--status`、`--notice`、`--spawn`、`--wait-run`、`--run` 都只看脚本所在的检出。`spawn()` 给子进程摘 `GIT_*` 的做法保留。
- 钩子 `hooks/post-commit` 未改：`--notice` 之后，`--spawn` 仍以 `>/dev/null 2>&1 &` 放到后台，不占提交输出、不阻塞提交，`--spawn` 里的异常仍被吞掉。钩子调用的是主检出的 `程序/scripts/auto_full_safe.py`，合入 master 即生效，不用重装钩子。

## 测试
- 新增 `tests/test_auto_full_safe.py::AutoFullSafeTests::test_hook_environment_does_not_shrink_the_repository_to_the_program_folder`。用 `git init --separate-git-dir` 建 gitfile 布局的临时仓库，带钩子会导出的 `GIT_DIR`、`GIT_INDEX_FILE` 调 `main(['--spawn'])`。断言三件事：在欠账判断运行时的环境里，真 git 从「程序」子目录查到的顶层是仓库根；派生一次；返回后调用方的环境原样还原。
- 改动前失败：

```
FAIL: test_hook_environment_does_not_shrink_the_repository_to_the_program_folder (tests.test_auto_full_safe.AutoFullSafeTests.test_hook_environment_does_not_shrink_the_repository_to_the_program_folder)
AssertionError: False is not true : 欠账判断看到的仓库顶层是 C:/Users/LAIBIAO/AppData/Local/Temp/tmpwkqhmdmp/top/程序
Ran 1 test in 0.097s
FAILED (failures=1)
```

- 改动后：`test_auto_full_safe` 32 条 OK。
- 已有测试断言未动，只改了测试文件首行说明。

## 验证（真实仓库，模拟钩子环境）
在本 worktree 根目录按钩子的方式运行 `python -I -B 程序/scripts/auto_full_safe.py`，`GIT_DIR` 取 `git rev-parse --absolute-git-dir`：

| 环境 | 代码 | 其间改过源码的轮次 |
| --- | --- | --- |
| 无 `GIT_*` | 修复后 | 15 |
| 钩子导出的 `GIT_DIR`、`GIT_INDEX_FILE` | 修复后 | 15 |
| 钩子导出的 `GIT_DIR`、`GIT_INDEX_FILE` | 修复前（HEAD 版临时副本，跑完已删） | 0 |

分支上「主干」为假，三种情况的后台触发都是假，这是分支不累计欠账的正常结果。

## 合入后核对（留给合并轮）
在主检出用 Claude 会话的 Bash 工具执行 `dev.py commit` 提交 master，看 `D:/repo-meta/漫剧制作助手.git/auto-full-safe.lock` 是否出现、`程序/logs/auto_full_safe.log` 是否开始写。master 欠账已过门禁线（`required` 为真），等待者不防抖，会立即开跑；上次后台全量是红，但新 HEAD 的时间冷却会被 `required` 越过。

## 范围外（只记录，未改）
- master 上 `tests/test_desktop_compact_layout.py` 的真红（期望锚点 `w`，R2131 已改为 `nw`）由原会话处理，本轮未动。
- 10-30 的两次后台全量（R2105、R2124）是否由钩子触发，未查证。钩子环境下只有不带 `程序/` 前缀的根目录风险文件还能命中，可能是原因之一。
