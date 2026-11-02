# R2358 代码审查修复（缺陷修复轮）

来源：对 2026-11-01 起 104 个提交的审查，8 条发现。

## 已修
- 密钥迁移失败不再静默：`model_secrets.import_env_keys` 失败时 `app_logging.swallowed` 记录（不含密钥），仍不标记已迁、下次重试。
- 清空模型历史（R2350）：改写旧版残留文件前，先把原文件备份移入回收站（`recycle` 注入入口），失败则抛错不改写。
- `stage_execution_service` 补回函数间两个空行。

## 无需改动
- AppUserModelID 在窗口创建后才设（R2351）：R2354 已在启动器 `启动漫剧制作助手.pyw` 于 `tk.Tk()` 之前调用，合入 master。

## 有意不改（需用户决定）
- 项目 .env 并入全局加密存储会跨项目串用、迁移后不再读 .env 且不覆盖同名密钥：这是 R2301 的明确契约，`test_env_key_import` 的断言就是它，改动需先改契约。
- 取消确认截断下游台账记录：阶段指针即 documents 长度，与确认路径一致；改动需契约。
- `restart_writing_preparation` 仅测试在用，删除需同步测试，另轮处理。

## 验证
- 已跑：run_selftests -k env_key_import idea_transcript idea_chat model_secrets writing_unconfirm stage_execution（经 gui_hidden）ALL PASSED，断言未动。
- 架构门禁：仅 `test_performance_history_is_declared_as_historical_only` 红，原因是本工作树缺 gitignored 的 `基准历史.json`（环境问题，与本轮无关）。
- 未跑：全量。回滚：git revert 本轮提交。
