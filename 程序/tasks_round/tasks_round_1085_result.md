# R1085 fcntl 平台加载修复

- 类型：修复轮（含全量基线验证），用户明确授权修复平台加载。
- 验证：定向 115/115、默认冒烟 8/8；受影响冒烟、架构和全量待记录。未完成全部验收，当前不标 TASK_COMPLETE。
- 欠账：原闭包两项失败已定向消除，全量欠账暂未清零，凭据以执行器实写为准。

## 根因与最小修复

Windows 随附运行环境不含 Unix 专用 fcntl。标准库闭包测试会扫描 POSIX 条件分支中的静态 import，原版两条断言因此失败。沿用 clipboard_lock 的平台延迟加载先例，在 codex_tasks.task_lock 的 POSIX 分支调用 import_module('fcntl')。Windows msvcrt 分支、非阻塞排他锁、忙锁错误与 finally 解锁保持原样；未改闭包扫描器或缺失模块豁免名单。

新增 tests/test_codex_task_lock.py 五条测试覆盖 POSIX 延迟加载、成功/异常解锁、忙锁拒绝、缺失后端不静默忽略、Windows 不加载 fcntl 及本机重复持锁拒绝。POSIX 行为以后端打桩验证，未声称在真实 POSIX 主机运行。

## 验证记录

统一在隔离树程序目录使用随附 Python，带 -B，顺序执行：

1. 改前 run_selftests.py -k stdlib_closure：两项失败，均为 codex_tasks.py / fcntl；新测试先红，之后修复。
2. 改后 run_selftests.py -k codex_task_lock stdlib_closure clipboard_lock workflow：115 条，0 红，4.2 秒。
3. smoke_test.py：8/8。
4. smoke_test.py --affected idea_chat workflow：9/9，定向门禁 0 红。
5. run_selftests.py --all --safe --force：检查点 5d4a9ab 首次 4064 条、358.6 秒，2 个文件失败：test_baseline_history 缺隔离树中被忽略的基准历史.json；架构棘轮登记行号由 47 移至 48。fcntl 闭包已通过。后续仅从主树复制原始本地基准历史（不提交、不伪造），并同步原有两处登记行号 47→48、134→136；不新增豁免、不改基数或断言。待重新全量。
6. run_selftests.py --layer architecture --all：待执行。

## 边界、自审与接续

中央入口领取 1085；主树临时保留于 codex/r1085-preserve-local，用户预设和输出不改。产品仅改一个平台加载点，不读取用户创作项目，不启动真实外部 Agent，不弱化已有断言。R1084 待授权事项不在本轮范围。diagnosing-bugs 复用已证实根因；minimal-diff-fix 限制补丁范围；scoped-tests 用于相关回归；tech-writer 区分证据与待验收事项。

提交：首个检查点 5d4a9ab；全量通过前不能宣称收尾完成。
