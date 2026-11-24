# R4273 OPS-LANES-TO-C：开发车道迁固态盘（junction 脚本＋并入台账测试，续做收尾）
<!-- round-evidence: {"commit_base": "e4577591", "credential_hits": 0, "evidence_sha256": "0c5791b47ba3a3f4", "exit": 0, "failed": 0, "passed": 20, "round": 4273, "tests": "run_selftests.py -k worktree_ledger"} -->

## 三问

- 轮次类型：§3.1 功能轮（新增运维脚本 `scripts/relocate_lanes.py`、runbook 一小节、既有 frozen 测试文件并入用例；不改任何既有模块行为）。
- 测试跑了吗、三个基线过了吗：跑了卡面指定验收。定向 `run_selftests.py -k worktree_ledger` 20 条全绿退出码 0（原 7＋新增 13）；`smoke_test.py --architecture` 700 条全绿退出码 0。默认冒烟与全量 `--all --safe` 未跑（卡面验收未要求）；`--plan` 被工具权限层拒绝 2 次未能执行（原文见下）。
- 欠账少了吗：R4256 的 STR006 登记欠账按治理裁决闭环——用例并入 frozen `tests/test_worktree_ledger.py`，不新增测试文件、不动 governance；脚本随本轮入库。

## 范围与基线（续做现场核对）

- 基准版本：`e45775919c4e2b7afc1d58359db8db83ccb7099e`。开工三查：`git status --porcelain` 输出 2 行与卡面预期逐行一致（` M 程序/runbook.md`、`?? 程序/scripts/relocate_lanes.py`，中文路径为八进制转义）；`git log -1 --format=%h` 输出 `e4577591`；`git rev-parse --abbrev-ref HEAD` 输出 `codex/ops-lanes-to-c`。
- 车道 HEAD 上保留 R4256-FAIL 结果文件提交 `e4577591`，未动。
- 任务：OPS-LANES-TO-C / 波次 W2 / 共享资源 `all-lanes, lane:ops-lanes-to-c`。目标：`.agents\worktrees` 整目录经 NTFS junction 迁到 `C:\dev-lanes`，应用本体、解释器、data、logs 留 D 盘；本卡只交脚本与测试，真实 `--apply` 由验收择机执行。

## 续做：保留与修改了上一位执行者的哪些改动

保留（核对后不改）：

- `程序/runbook.md` +18 行「车道迁到固态盘」一节（含执行窗口、三条命令、手动回滚等价命令、不动清单），已逐条对照脚本行为与设计卡，无需改动。
- `程序/scripts/relocate_lanes.py` 草稿主体：`--plan` 默认只读预演（目录大小/目标盘余量/占用进程/prune 预演/车道数/show-toplevel 实测）；`--apply` 四项前置（在派项、cwd 占用、余量≥2×、目标为空）＋源内 junction 拒绝、源已是 junction 拒绝、检测读不到需 `--i-know-lanes-idle`；robocopy `/E /MOVE /COPY:DAT /R:1 /W:1`（另加 `/XJ /NP`）；搬后文件/目录/字节、逐车道 `git status --porcelain`、`worktree list` 快照比对；失败删 junction 自动回搬；`--rollback` 摘 junction 搬回并同样校验；PEB 进程 cwd 探测（64 位与 Wow64）；`_queue_claimed` 只做 `"status":"claimed"` 正则存在性检查（R4256 已消 `json.loads` 棘轮项）。

修改（对照设计卡补缺/修错，未推倒重写）：

- `relocate_lanes.py:320-326` `_inside`：原实现调用 `os.path.commonpath` 后丢弃返回值，同盘任意路径（如 cwd 在 `D:\漫剧制作助手` 主检出而非 `.agents\worktrees` 下）都被误判「在源目录内」，造成占用误报、`--apply` 误拒。改为 `commonpath(...) == 规范化 root` 才算 inside。
- `relocate_lanes.py:437-442`：`--apply` 搬前 git 快照（`porcelain_map`/`worktree_entries`）包 try，失败干净拒绝（return 2）而非 traceback。
- `relocate_lanes.py:448-452`：robocopy 成功后 `tree_stats(target)` 包 try，统计异常走 `_restore_from_failure` 回搬（原实现异常直接崩出，不回搬）。
- `relocate_lanes.py:461-466`：junction 建立后的 git 快照比对包 try，异常走 `_restore_from_failure`（junction 已建，必须回搬）。
- `relocate_lanes.py:483-487`、`492-500`：`--rollback` 目标统计与搬前 git 状态读取包 try，失败干净拒绝（return 2，此时尚未动任何数据）。
- `relocate_lanes.py:508-511`、`515-519`：`--rollback` 回搬后统计/git 读取包 try，异常按既有「警告＋return 3」口径报告（数据已回搬完，只剩核对）。
- `tests/test_worktree_ledger.py`：旧草稿 `.agent-tmp/ops-lanes-to-c-old-drafts/test_relocate_lanes.py` 的 12 条用例并入新类 `RelocateLanesTests`，方法名统一加 `test_relocate_` 前缀；原有 7 条用例逐字未动。草稿辅助函数 `git/snapshot/porcelain/porcelain_map/worktree_count/idle_dispatch/empty_cwds/free_probes` 并入为模块级函数（沿用草稿名）；`import json` 改用文件顶部既有导入（草稿为方法内局部导入）；未用的 `WINDOWS`/`skip_reasons` 导入未带入（本文件无 skip）。
- 新增第 13 条用例 `test_relocate_apply_ignores_same_drive_cwd_outside_source`（`test_worktree_ledger.py:239-249`）：cwd 在与 source 同盘但目录外时不算占用，覆盖 `_inside` 修复。

## 改动内容（文件:行号）

- `程序/scripts/relocate_lanes.py`（新建，未跟踪→本轮提交）：全文 584 行；本轮相对草稿改动见上（`_inside` L320-326；apply 校验段 L437-470；rollback 校验段 L483-522）。
- `程序/tests/test_worktree_ledger.py`：L3/L6/L9 新增 `io`/`sys`/`redirect_stdout` 导入；L18-22 新增 `relocate` 模块装载（沿用 `ledger` 的 importlib 模式）；L120-163 并入草稿辅助函数；L166-350 新增 `RelocateLanesTests`（13 条 `test_relocate_*` 用例）。
- `程序/runbook.md`：上一位执行者新增的「车道迁到固态盘」节，本轮未改。
- `程序/tasks_round/tasks_round_4273_result.md`：本文件。
- `程序/tasks_round/evidence/R4273.json`：由 `scripts\dev.py commit` 自动生成。

## 缺陷复现 / 改前红

续做现场已有实现：R4256 已写出脚本与全部用例并自测 12/12 绿（见 `tasks_round_4256_result.md`），本卡未观察到针对本轮改动的改前红，按接口契约第一条如实记录；改前红由验收在基线临时工作树独立复核。

新增用例 `test_relocate_apply_ignores_same_drive_cwd_outside_source` 针对的 `_inside` 缺陷：旧实现下 `commonpath` 不抛异常即返回 True，mock 的 cwd=`container/elsewhere`（与 source 同盘不同支）会被误判占用 → `apply` 拒绝（返回 2≠0）→ 该用例在旧代码下应红；修复后 `commonpath==root` 才算 inside → 绿（推断，未对旧代码实测）。

## 验证命令与结果

Python 命令工作目录均为 `程序`，逐条单独执行。

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k worktree_ledger`：退出码 0，尾部原文：
   ```text
     test_worktree_ledger          20 条    22.4 秒
   共 20 条用例，23.2 秒；0 个文件有红
   ALL TESTS PASSED
   ```
   （7 条原用例＋13 条 `test_relocate_*`，条数 = 改前 7＋新增 13。）
2. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`：退出码 0，尾部原文：
   ```text
   Ran 700 tests in 264.802s
   OK
   ✅ 架构治理测试：tests/architecture
   ```
3. `..\..\..\..\运行环境\Python\python.exe -B scripts\relocate_lanes.py --plan`：被工具权限层拒绝 2 次（原文见「被拒绝的命令」），未能执行、无退出码。只读 `--plan` 路径已由 `test_relocate_plan_is_read_only_and_reports_facts` 在临时目录覆盖：退出码 0、输出含「字节/余量/worktree/占用」、源目录逐字节不变、目标目录不产生。
4. `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim`：退出码 0，输出 `4273`。

## 提交

- 提交命令（文件参数按 `程序` 相对路径——`commit_retry.stage_inputs` 以 `程序` 为 cwd 跑 `git add`；`--tests` 为 `nargs='*'` 须放在文件参数之后，否则吞掉文件路径，沿用 R4249 实证口径）：
  `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4273: OPS-LANES-TO-C 修复" scripts/relocate_lanes.py tests/test_worktree_ledger.py runbook.md tasks_round/tasks_round_4273_result.md --tests worktree_ledger`
- 提交哈希以完成报告与证据回执为准，不在本文件自引用。
- 未合入、未 push；真实 `--apply`/`--rollback` 未对任何真实车道执行（测试全部在临时目录）。

## 未验证项 / 未核实

- 真实盘上的 `--plan`/`--apply`/`--rollback` 未执行：`--apply`/`--rollback` 本卡禁止对真实车道跑；`--plan` 被权限层拒绝。搬迁正确性由测试在临时目录全真验证（真 git worktree、真 robocopy /MOVE、真 mklink /J junction、真 git status/worktree list 比对）。
- `cpa auto status` 真实输出格式未核实：exit≠0/读不到/判不出一律按 unknown，`--apply` 需 `--i-know-lanes-idle`；`cpa` 若只是 PowerShell 函数而非 cmd 可达命令，`dispatch_state` 的 `shell=True` 调用必然走队列文件兜底（`维护队列.json` 存在性检查），行为已按 unknown 兜底设计。
- junction 后 `git rev-parse --show-toplevel` 返回 D:/ 还是 C:/ 写法未在真机核实：`--plan` 内置实测打印（`toplevel_probe`），留验收窗口；测试只断言该命令在 junction 后 exit 0。
- 进程 cwd 探测受权限/位宽限制的受关注进程如实列「未能检测」，`--apply` 按 unknown 处理。
- `.agents\worktrees` 真实目录大小、C 盘余量、在册车道数未实测（`--plan` 被拒）；卡面记 53 个目录/git worktree list 约 35 条，未核实。
- `.claude\worktrees`（卡面称 3 个）与 `.wt\ci`（卡面称 1 个）按卡面只列出不动，未实测核对。
- 默认冒烟 `smoke_test.py` 与全量 `run_selftests.py --all --safe` 未跑（卡面验收未要求）。

## 卡外发现（只记录，未顺手修）

- `dispatch_state` 用 `shell=True` 调 `cpa auto status`：在 cmd 下若 `cpa` 仅是 PowerShell 别名/函数则恒 fallback 队列文件；不影响正确性（unknown→需 flag），但真实 `--apply` 前建议验收窗口先手动跑一次 `cpa auto status` 确认可达性。
- `_restore_from_failure` 在「junction 删除失败」分支会跳过回搬并仅告警（避免经 junction 把目标拷回自身），属保守设计，未改。

## 被拒绝的命令（原文）

- `..\..\..\..\运行环境\Python\python.exe -B scripts\relocate_lanes.py --plan`（本工作目录 `程序`，2 次；R4256 会话另有 3 次同命令被拒记录，见 `tasks_round_4256_result.md`）
- `..\..\..\..\运行环境\Python\python.exe -B -c "import sys; print(sys.version)"`（1 次；且属卡面禁止的 `python -c`，弃用）
- `Get-ChildItem "D:\漫剧制作助手\运行环境\Python" -Filter "python*.exe"` 及同目录 `*.cfg` 列举（2 次；改用文件检索工具确认 `Path.is_junction` 在仓内既有使用、解释器版本足够）

## git diff --numstat 原文（提交前工作树）

```text
18	0	"\347\250\213\345\272\217/runbook.md"
241	0	"\347\250\213\345\272\217/tests/test_worktree_ledger.py"
```

（`程序/scripts/relocate_lanes.py`、本结果文件为未跟踪新文件，不入 numstat。）

## 仍留在车道里的未跟踪文件清单（提交前）

- `程序/scripts/relocate_lanes.py`（本轮提交）
- `程序/tasks_round/tasks_round_4273_result.md`（本轮提交）
- `.agent-tmp/`（含 `ops-lanes-to-c-old-drafts/test_relocate_lanes.py` 旧草稿，已被忽略、不进提交，按卡面只读未动）
