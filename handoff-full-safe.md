# 交接：拿到 R1734 之后第一张全量绿凭据

仓库 `D:\漫剧制作助手`（规则以 `程序\AGENTS.md` 为准），master 已到 R1805，状态页轮次头为 1806。解释器 `D:\漫剧制作助手\运行环境\Python\python.exe`。用户要求所有工作亲自完成，不派发给其他模型。

## 当前状态（2026-10-21 晚）
- 用户要求跑一次全量。20:35 已在 master HEAD `31072b01` 上用 `程序\scripts\auto_full_safe.py --spawn` 启动后台全量。截至交接，这次运行一直在等跨树 GUI 令牌（日志 `程序\logs\auto_full_safe.log`，`[GUI_WAIT]` 已等 600 秒以上，队列第 2 位，最长 900 秒）。
- `D:\repo-meta\漫剧制作助手.git\auto-full-safe-result.json` 里还是更早那次的结果：HEAD `78974488`，11:36 结束，红 4 个，分别是 `test_copy_rules`、`test_pet_ui`、`test_sanhu_mode`、`test_video_ui`。其中 `test_pet_ui`、`test_video_ui` 已在 R1800 修好；`test_copy_rules` 这次应该会被"您"文案修复带绿。以新一次运行的结果为准。
- 本会话已完成的轮次，详见各自的 `程序\tasks_round\tasks_round_N_result.md`：
  - R1781：修红 + 红后冷却 `RED_COOLDOWN_SECONDS`
  - R1788：死代码清理
  - R1794
  - R1796：恢复 `project_settings.set_auto_submit`，它被 `getattr` 动态引用
  - R1800：修 3 个红
  - R1805：资产清单发布包内容不变就跳过落盘
- 旧 worktree 的补丁已归档到 `D:\repo-meta\wt-archive-20261021.zip`。

## 下一步
1. 等后台全量结束：`程序\scripts\auto_full_safe.py --status`，再看 result json 和日志里的 `### ` 红文件行。如果锁一直被别的进程占着，告诉用户，不要强抢。
2. 如果绿：确认 `full-safe-receipts.json` 新增了凭据、欠账清零，然后向用户报告。
3. 如果红：逐个查根因，开修复轮修掉，不弱化断言，结果文件写"断言未动"。提交流程如下：
   1. 先存补丁，`git reset --hard`。
   2. `程序\维护记录\基准脚本\round_claim.py next` 领号（工作树必须干净）。
   3. `git apply --index` 还原补丁。
   4. 结果文件改成领到的号。
   5. 带 `CODEX_STAGE_ALLOWLIST` 提交，首行写 `R<n>: ...`。
   6. 在 `D:\漫剧制作助手` 里 `git merge --ff-only` 到 master。
   7. 在 master 上单独提交状态页轮次头（满足规则 27：N == M+1）。分支上不能改 `project_status.md`。
   
   领号常被别的会话抢，所以以上步骤要放在一条命令里完成。
4. 已知的环境性红：worktree 里 gitlink 是空的（`AIGC创作全流程`、`剧本锻造`、`编剧技能集`），`基准历史.json` 被 gitignore。这些在 worktree 里会让 writing／idea_chat 系列测试红，属于环境问题，不是回归。用户拒绝过搭建临时验证副本，不要再提。
5. 可选优化，必须先问用户：
   - `_sync_plan` 按输入签名缓存
   - 重型 GUI 测试收起可见窗口
   - 用确定性 pump 替换 `settle` sleep
   - 架构门禁去重
   - 复查约 83 个只被测试使用的符号（删之前先查动态引用）

## 建议使用的 skill
无专用 skill，按 `程序\AGENTS.md` §0／§5／§7 执行。
