# R1085 fcntl 平台加载修复

- 类型：修复轮（含全量基线验证），用户明确授权修复平台加载。
- 验证：定向 115/115、默认冒烟 8/8、受影响冒烟 9/9、独立架构 309/309、安全全量 4064/4064。适用检查均通过。
- 欠账：原闭包两项失败已消除，执行器写入真实全量凭据 round=1085，历史全量欠账已偿还；R1084 待确认事项保持未完成。

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
6. 失败项复测 run_selftests.py -k codex_task_lock stdlib_closure baseline_history unification_ratchet：23/23，3.5 秒。
7. 检查点 cd7cfae 重新 run_selftests.py --all --safe --force：4064/4064，348.967 秒；真实凭据 tree=24cb94f0911cb0fc070e0cd52ad95c5d85ea1bad、round=1085、at=2026-10-07T06:49:53。
8. run_selftests.py --layer architecture --all：309/309，30.4 秒；与既有 309 基线相比无增减。执行器更新测试分层基线的架构耗时元数据，未手写全量凭据。
9. 收尾 run_selftests.py -k agents_md round_baselines：15/15，0.7 秒。

最终归档只更新本报告、状态、快照和执行器实测元数据，不将这些后续文档树宣称为同树全量。默认冒烟、架构和全量三个基线均为本轮实测。

附带发现：独立架构执行器将 common-dir 的全量记录合并写回受跟踪分层基线。按现有规则，收尾仅保留其 architecture 实测字段，移除本次新写入的全量记录副本；common-dir 原始凭据不改。执行器这一范围外写回行为留待独立诊断，本轮未扩大修改执行器。

## 边界、自审与接续

中央入口领取 1085；主树临时保留于 codex/r1085-preserve-local，用户预设和输出不改。产品仅改一个平台加载点，不读取用户创作项目，不启动真实外部 Agent，不弱化已有断言。R1084 待授权事项不在本轮范围。diagnosing-bugs 复用已证实根因；minimal-diff-fix 限制补丁范围；scoped-tests 用于相关回归；tech-writer 区分证据与待验收事项。

收尾自审：产品改动限定平台加载；既有断言未弱化；未新增运行依赖；Windows 真实锁与 POSIX 打桩通过；用户预设 SHA-256 前后一致。post-task-cleanup 的脚本 dry-run 被系统执行策略拒绝，改为只读枚举；245 个候选含任务开始前的缓存，未确认全部归属，不删除。验收用原始基准历史和隔离工作树保留，以便复核。

提交：修复检查点 5d4a9ab，登记修正与受测检查点 cd7cfae；通过后执行本轮收尾提交，不推送远端。本轮 fcntl 修复 TASK_COMPLETE，不代表 R1084 交付路径任务完成。

收尾回执：验收归档提交 ea7c510；主目录已恢复 master，隔离树保留在 codex/r1085-validation。主目录唯一既有跟踪改动仍是用户预设，其 SHA-256 核对未变；既有未跟踪输出未纳入提交。后续本回执为纯文档补记，不改变受测产品代码。
