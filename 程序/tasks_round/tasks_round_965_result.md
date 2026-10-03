# R965 协作治理轮：队列单实例与跨树 GUI 令牌

- 类型：用户任务书 A 指定的协作治理轮；不是功能轮。
- 测试：默认冒烟 8/8；架构复验 279/279（92.480 秒），首次 279 条中 1 红源于旧 last_full 字段未读取 R963 实际绿凭据；定向 58 条、0 红；本轮全量尚未运行。
- 欠账：尚未宣称清零；以本轮真实全量和 common-dir 凭据为准。
- 状态：[TASK_FAILED]（验收检查点，未完成全量，不得宣称完成）。
- 提交：实现基于 3254aeee6e1b37d45af833a9ad10ff0b8d3671d0；本检查点使用 R965-FAIL 前缀，实际验收提交 hash 在全量后补录。

## 范围与事实

1. 开工前停止本任务旧的 PID 29892 测量及其测试子进程；确认没有其他全量安全进程。两份指定测试文件无未提交改动，本轮不修改 test_asset_gating/test_pet_settings。历史 R963 的夹具改动已提交。
2. 已领取 R965，认领 A-collab-singleton-gui，owner=Codex-collab。R964 由架构独立树持有。
3. 唯一权威队列为 Git common-dir/maintenance-queue.json。首次按 worktree 副本 union，completed 优先、同状态晚租约优先、所有 note 拼接保留；独占原子发布，后续不重新种子。主树快照取消跟踪并忽略，仅自动导出，禁止手改。show/validate 在初始化后只读、不加写锁；首次访问的种子发布也不获取写锁，而以独占原子发布解决竞争。
4. GUI/full-safe 两令牌共用 PID 检查与死锁回收，同 PID 可重入；所有入口选中 GUI 即等待，默认 900 秒，可 --gui-wait 调整。超时返回 2，列明 GUI_DEFERRED，不计通过、不更新缓存或绿凭据。失败时有其他工作流持有 GUI 令牌则额外标 SUSPECT_CONCURRENCY，原始红项保留。
5. 新增真实临时 Git 仓库及两个 worktree 的互斥/种子合并测试；两个临时调用目录的活进程令牌争用与延期测试。全量锁测试的持有者 mock 改为不同 PID，以适配同 PID 重入契约；断言未删减，不涉及两份禁止改动文件。
6. writing-for-agents 技能用于 AGENTS 第 27 条，明确权威源与只读快照边界。

## 待补证据

- 修复后 smoke --architecture、定向计数及完整 --all --safe。
- 最终主树 show、claim/release 后 git status --porcelain 空输出。
- {tree, round, seconds, at} 和本轮欠账清零。
