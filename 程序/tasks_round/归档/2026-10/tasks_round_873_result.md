# R873 全量安全自测错峰锁

## 范围与结论

- `run_selftests.py --all --safe` 现在在 Git common-dir 创建跨工作树排他锁；已有活动持有者时拒绝启动，并显示其 PID 和轮次。
- 异常中断留下的失效锁会在下次领取时自动回收；正常 Python 进程退出时通过 `atexit` 释放锁。

## 实现

- 锁文件使用 `O_CREAT | O_EXCL` 原子创建，记录 PID、轮次和开始时间，避免两个工作树同时运行全量安全回归。
- Windows 以 `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` 判断锁持有 PID，修复 `os.kill(pid, 0)` 将活动进程误判过期的问题；其他平台仍使用既有信号探测。
- 新增回归覆盖活动锁拒绝、释放后重新领取；回归期间还验证了此前被中断留下的失效 PID 锁可被识别。

## 验收

- `python -m unittest tests.test_selftests`：25 条／0 红。
- `python -m unittest tests.test_selftests tests.test_round_claim tests.test_git_hooks`：35 条／0 红，3.518 秒。

## 后续

- 全量安全回归仍应按队列和锁顺序执行；本轮只提供错峰互斥，不替代内容树全量零红凭据。
