# R2575 结果：全量测量自我作废修复（/程序/log.txt 纳入忽略）

## 三问

1. **轮次类型**：修复轮（§3.2）——R2554 偿债轮的延续补丁。
2. **测试与基线**：改动仅一行 `.gitignore`（非源码），无 `--affected` 目标；验证方式是随后在同树上重跑 `auto_full_safe --run`——此前实测（6d14bfa8 树）全部用例绿、仅因 `?? 程序/log.txt` 脏项被判「测量期间工作树变化」而不写凭据。冒烟 8/8（R2554 已测）、架构门禁 428/428（R2554 已测）未退化。
3. **欠账**：本次修复消除全量凭据的结构性障碍（任何树全量跑都会写 `程序/log.txt` 导致 dirty），是全量欠账清偿链路的必要一环。

## 根因

- `.wt/ci` 干净检出跑 `--all --safe` 时，测试进程在 `程序/` 下产生 0 字节运行日志 `log.txt`；`.gitignore` 只覆盖 `*.log` 与 `/程序/logs/`，`log.txt` 未匹配。
- `run_selftests.measurement_unchanged()` 视 `--untracked-files=normal` 下的 `??` 为脏 → `content_tree()` 返回空 → 不写凭据，退出码 2。
- 影响是全项目性的：master 历史多次全量「测量期间 HEAD/工作树变化」与本项同源，此前仅绿凭据时代（R2427）该文件尚未出现或被清理。

## 改动

- `.gitignore`：`*.log` 之后追加 `/程序/log.txt`（沿用文件内「运行日志不入库」既有条款，最小改动）。

## 验证计划（提交后执行）

- `scripts/auto_full_safe.py --run`（本工作树检出）：预期全绿且写凭据 `{tree: <本提交 HEAD:程序>, round: 2575}`，`last_full_safe_all_round` 前移至 2575。

断言未动。
