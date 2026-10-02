# R629 功能轮结果：开发目录清理脚本

## 开头三问

- 本轮是功能轮：新增仅供开发目录使用的清理脚本，不进入分发逻辑。
- 测试已跑：`smoke_test.py` 8/8 通过；`smoke_test.py --architecture` 102/102 通过。
- `project_status.md` 的功能欠账未减少；本轮新增的是开发维护能力，台账已推进至下一轮。

## 改动

- 新增 `scripts/clean_dev.py`。只使用标准库的 `shutil.rmtree`、`os.remove` 与 `zipfile`；不调用系统删除命令，也不导入项目模块。
- 默认清理程序目录中不受保护的 `__pycache__`、`程序/.selftmp`（若存在）以及实际运行时发现的分发根目录 `.selftmp`、`data/SH001`、`SH002`、`SH004`。
- `--dry-run` 只输出计划；`--deep` 只找 `logs/` 与 `维护记录/` 下超过 30 天的 `.log`；`--archive` 只归档 R500 及之前的结果文件，保留 R501 及之后。
- 所有删除前均逐项检查：运行环境 Python、`skills/`、`tests/`、`配置/`、`assets/`、启动/测试脚本、生产 `.py`、一般 `.md` 均拒绝。任务结果归档和明确临时目录是受限例外。
- 脚本在运行时设置 `sys.dont_write_bytecode = True`；推荐命令也带 `-B`。

## 演练与实际清理

演练命令：

```powershell
D:\漫剧制作助手\运行环境\Python\python.exe -B scripts\clean_dev.py --dry-run
```

初次演练发现：5 个非受保护 `__pycache__`（21.04 MiB）、根 `.selftmp`（0.17 MiB）、三组 `data/SH*` 测试残留（16.66 MiB）。`tests/__pycache__` 与 `tests/architecture/__pycache__` 被保护规则拒绝。

在用户对四个明确目标重新授权后，默认模式实际删除 753 个文件、37.70 MiB：三组 `data/SH*` 已不存在，生产侧根 `__pycache__` 已不存在。清理前为 104.49 MiB、清理后为 66.79 MiB，目录净释放 37.70 MiB。

`.selftmp` 的删除被 Windows ACL 阻断：残留项的所有者为 `CodexSandboxOffline`，当前运行身份无删除权限。脚本如实报告 `WinError 5`，没有提升权限或绕过 ACL；这是本次唯一未清除项。后续直接双击/运行时，脚本会继续尝试清理，不会误删受保护目录。

`--deep --archive` 演练结果：没有超过 30 天的候选 `.log`；可归档 R500 及之前结果 348 份（0.24 MiB），演练未创建 ZIP、未删除文件。

## 内置保护与启动确认

- 清理前后 `run_selftests.py` 与 `smoke_test.py` 的 SHA-256 不变。
- `skills/` 文件数保持 501；`tests/` 的 `.py` 源文件数保持 215。测试目录缓存被明确跳过。
- 清理后以 `python.exe -B app.py` 启动，8 秒后进程仍存活：PID 15524。应用未因清理而退出。
- 未修改用户项目数据、产品 `.py`、测试、配置或分发包逻辑；仅新增本轮脚本、结果报告及台账条目。

## 验证汇总

```text
python -B smoke_test.py                 通过：8 项，失败：0 项
python -B smoke_test.py --architecture  Ran 102 tests，OK
```

## J 后续

若后续使用证明 `--deep` / `--archive` 有价值，可另行评估每 30 天的定期触发；不得默认自动删除。对于遗留 `.selftmp`，应由拥有该目录的系统账户或用户手工处理 ACL 后再运行脚本，不能由脚本越权接管。

## 自审

- 只新增 `scripts/clean_dev.py`，未改产品代码、测试、配置或用户项目数据。
- 默认删除路径均经内置保护检查；`tests/`、`skills/`、启动/测试脚本已核验未触碰。
- `--archive` 仅做演练，未压缩或删除任何既有结果文件。
