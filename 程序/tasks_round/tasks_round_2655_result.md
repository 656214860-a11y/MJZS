# 轮次 2655 结果

## 三问

- 类型：§3.2 修复轮（合并阻断级·T7 拆分的契约同步遗漏）
- 测试：跑了——`unittest tests.test_line_endings tests.test_account_offline` 20/20 绿
- 三个基线：冒烟未跑（两处契约引用同步）；架构门禁未跑；全量未跑
- `project_status.md` 欠账：不少——解锁修复

## 改动

- `tests/test_line_endings.py`：`WRITERS` 由 `run_selftests.py` 改为 `selftest_receipts.py`——
  文本写入面已随 T7 拆分迁到凭据模块，facade 不再写文件。
- `tests/test_account_offline.py`：`test_selftest_runner_sets_the_switch` 读源对象由
  `run_selftests.py` 改为 `selftest_env.py`——`os.environ.setdefault("DRAMA_SUPPRESS_NETWORK","1")`
  随拆分迁到环境模块。

断言意图不变（抑制开关仍由自检进程入口设置、文本写入仍走 line_endings 助手），仅同步检查对象到拆分后的归属模块。
