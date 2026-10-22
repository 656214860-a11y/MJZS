# R1861 结果：全量 --all --safe 体检，修 R1853 遗留的 test_force_quit 假进程签名（修复轮）

- 三问：本轮是 §3 修复轮：只改 `tests/test_force_quit.py` 一行 mock 签名；全量结果见“验证”；`project_status.md` 欠账未变（分支不写状态页）。
- 计划来源：vibe coding 体检计划批次 4；队列无对应 ID。原领 R1856，因并行树已领到 R1860、提交钩子要求最新号，改领 R1861；R1856 空号作废。

## 修复
R1853 把 `qwen_adapter.run_background` 改成 `platform_tools.communicate_or_kill(process, prompt, timeout)`，它调用 `process.communicate(data, timeout=...)`。`test_force_quit.FakeQwen.communicate` 仍是旧签名 `(prompt=None)`，于是 4 条 `BackgroundProcessTests` 报 TypeError；随后 `terminate_process_tree` 在桩住的 `subprocess.Popen` 上再抛错，连累全量工作进程里自检器自己的 `git rev-parse` 调用，全量在 GUI 池中途崩溃（本轮第一次全量即因此中断）。
- 改法：`communicate(self, prompt=None, timeout=None)`。契约有意变更，同步 mock；**断言未动**。
- 验证：`tests.test_force_quit`（隐藏桌面）17 条全过。

## 验证
（全量待补）
