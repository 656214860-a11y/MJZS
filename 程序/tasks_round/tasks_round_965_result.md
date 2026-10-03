# R965 协作治理轮：队列单实例与跨树 GUI 令牌

- 类型：用户任务书 A 指定的协作治理轮；不是功能轮。
- 三个基线：默认冒烟 **8/8**；架构 **279/279**（92.480 秒）；完整安全全量 **3808 条/0 个失败文件**（439.508 秒）。指定定向 **58 条/0 红**。
- 欠账：真实全量后 `last_full_safe_all_round=965`，历史全量欠账清零。C4 的 ≤420 秒是另一队列项，仍未完成，不冒充性能达标。
- 状态：[TASK_COMPLETE]（任务书 A 两项目标与验收均已有实测；收尾文档变更后的最终内容树仍执行完整复验，凭据自动落 common-dir，不再写脏树）。
- 已提交并实测的检查点：**76c1dd3280703e70507c05ffd4f298c1b216cace**，此前因尚未全量而正确使用 R965-FAIL 前缀；只有本次真实全绿后才允许收尾 R965: 提交。最终提交可由 `git log --format=%H --grep='^R965: close' -1` 定位，不能把待生成的自身 hash 写进自身提交。

## 范围与事实

1. 开工前停止本任务旧的 PID 29892 测量及其测试子进程；确认没有其他全量安全进程。两份指定测试文件无未提交改动，本轮不修改 test_asset_gating/test_pet_settings。历史 R963 的夹具改动已提交。
2. 已领取 R965，认领 A-collab-singleton-gui，owner=Codex-collab。R964 由架构独立树持有。
3. 唯一权威队列为 Git common-dir/maintenance-queue.json。首次按 worktree 副本 union，completed 优先、同状态晚租约优先、所有 note 拼接保留；独占原子发布，后续不重新种子。主树快照取消跟踪并忽略，仅自动导出，禁止手改。show/validate 在初始化后只读、不加写锁；首次访问的种子发布也不获取写锁，而以独占原子发布解决竞争。
4. GUI/full-safe 两令牌共用 PID 检查与死锁回收，同 PID 可重入；所有入口选中 GUI 即等待，默认 900 秒，可 --gui-wait 调整。超时返回 2，列明 GUI_DEFERRED，不计通过、不更新缓存或绿凭据。失败时有其他工作流持有 GUI 令牌则额外标 SUSPECT_CONCURRENCY，原始红项保留。
5. 新增真实临时 Git 仓库及两个 worktree 的互斥/种子合并测试；两个临时调用目录的活进程令牌争用与延期测试。全量锁测试的持有者 mock 改为不同 PID，以适配同 PID 重入契约；断言未删减，不涉及两份禁止改动文件。
6. writing-for-agents 技能用于 AGENTS 第 27 条，明确权威源与只读快照边界。

## 验收证据

- 原架构红项为旧 last_full 字段未接续 R963 的真实绿记录；修复后 279/279，不删除或放宽该门禁。
- 队列回归 10 条：临时仓库 + 两个 worktree，活租约互斥；12/20 条不同 id 集的并集为 26 个 id；completed 不回退，同状态晚租约胜出，note 保留；种子幂等；validate 拒绝重复 id 和 claimed 空 owner，租约偏差只 WARN。
- GUI 调度回归 7 条：两个临时目录中的独立进程争用同一令牌、真实等待与超时；死 PID 回收；同进程重入与最后一层释放；默认、-k、gui-e2e 延期不计通过；全量先持全量锁再持 GUI；异常释放；竞争红项保留且标记。
- 现场主树 `show` 包含 `A-collab-singleton-gui pending owner= lease=`，随后以 Codex-collab claim 成 claimed、release 成 pending。紧接着的原始输出边界如下，两行之间无内容：

```text
git status --porcelain BEGIN
git status --porcelain END
```

- 全量命令：`python run_selftests.py --all --safe`，PID 33324；启动 `HEAD=76c1dd3280703e70507c05ffd4f298c1b216cace`，干净树；全过程 HEAD 不变。默认 2 路 Tk，未借用 3/4 路性能测量。
- 输出：`共 3808 条用例，439.5 秒；0 个文件有红`，`ALL TESTS PASSED`。stdout 无 GUI_DEFERRED；stderr 留有 Tk `invalid command name ... (after script)` 清理诊断，未变成 unittest 红项，本轮不声称修复该历史诊断。
- 实际凭据（`Git common-dir/full-safe-receipts.json`）：

```json
{"tree":"db02f159b6f59996c3474197d190ebc87fb8b2fe","round":965,"seconds":439.508,"at":"2026-10-04T05:26:11"}
```

- 最终提交的内容树变更后同样完整复验，新增凭据以同一权威文件中匹配最终 `HEAD:程序` 的记录为准；不复用上面不同树的记录，不在测量中途提交。
- 自审：仅改队列、测试调度、其回归与规定文档；未动指定两份测试、用户项目数据及配置/data/private；按显式 allowlist 暂存，无 add -A、无新增备份文件。所有断言门槛保留。首次诊断检查点与真实成功收尾分开留史。
