# 部署与运维手册（runbook）

面向「接手机器的人」：怎么装、怎么起、怎么验证、出事看哪里。规则权威是 `AGENTS.md`，验收事实是
`project_status.md`，分层是 `architecture.md`；本文件只讲可执行动作，不复制规则全文。

## 1. 运行环境

| 项 | 值 |
| --- | --- |
| 解释器 | `运行环境\Python\python.exe`（当前 **Python 3.15.0a2**，alpha；迁移计划见 R1610 清单 Q12） |
| 运行时第三方依赖 | **无**（门禁要求只用标准库：可移植、可分发包） |
| 平台 | Windows（图形界面＝Tk） |
| 关键路径 | 程序根 `程序\`；日志 `程序\logs\`；产物 `程序\outputs\`；轮次报告 `程序\tasks_round\`；分层 `程序\architecture.md` |
| 密钥 | 项目 `.env`，不入库；日志经 `app_logging.redact` 脱敏后再落盘 |

## 2. 启动

| 入口 | 场景 |
| --- | --- |
| `启动漫剧制作助手.pyw` | 正常图形启动（无控制台窗口） |
| `启动助手.cmd` | 命令行启动（保留 stdout，便于看启动期输出） |
| `启动助手_测试模式.cmd` | 测试模式 |
| `本地CI.cmd` / `本地CI.cmd quick` / `本地CI.cmd exit` | 自检（见 §3） |

启动失败先看根目录 `启动错误.log` 与 `程序\logs\app.log`。

## 3. 验证与自检（按代价从低到高）

| 命令（工作目录 `程序`） | 作用 | 代价 |
| --- | --- | --- |
| `python smoke_test.py` | 默认冒烟 8 项 | 秒级 |
| `python smoke_test.py --architecture` | 架构门禁（分层／契约／棘轮，当前 356 项） | 约 3 分钟 |
| `本地CI.cmd exit` | 默认冒烟 → 静态门禁 → 架构门禁（Q10 出口，非 0 即失败） | 约 4 分钟 |
| `本地CI.cmd quick` | 默认冒烟 → 增量门禁 | 分钟级 |
| `本地CI.cmd targets` | 按 `程序\logs\ci_targets.txt` 逐行定向复跑 | 按清单 |
| `python run_selftests.py --all --safe` | 安全全量（含架构门禁；后台自动补跑用的就是它） | 约 11 分钟 |

跑测试要带 `PYTHONPATH`：`<程序>\tests;<程序>`（`ci_*.cmd` 已包装）。纪律：**全量不当排错工具**，
失败先用 `--affected` / `-k` 在定向层面修到绿，再复验全量。

## 4. 全量欠账与绿色凭据

- 规则：主干提交序列里累计 **8 个改过源码的轮次**要求一次完整安全全量；启动入口、
  `storage_maintenance.py`、`tests/architecture/_layers.py` 属风险路径，另有宽限计数（权威阈值在 `run_selftests`）。
- 凭据：`.git/full-safe-receipts.json`（同一 `HEAD:程序` 内容树 7 日内可复用）。补跑由 post-commit 触发，
  日志 `程序\logs\auto_full_safe.log`，结果 `.git/auto-full-safe-result.json`。
- 门禁报「欠一次完整安全全量」时**不要手动全量**，等后台；只有后台确实没起来（锁丢了）才手动 `--all --safe`。

## 5. 升级、备份与回滚

- 升级前用 `reorganize_install.py` 对照 `安装信息.json` 与 `distribution_manifest.md` 核对落位。
- 回滚靠 Git：`升级备份/` 与 `.bak_*` 是历史证据、今后不再新增（AGENTS §2.6）。回滚后跑 §3 第一档自检。
- `程序\outputs\`、`程序\logs\`、私有配置不进发布包。

## 6. 常见故障

| 现象 | 先看 | 处置 |
| --- | --- | --- |
| 启动即退 | `启动错误.log`、`程序\logs\app.log` | 多为解释器路径／工作目录不对 |
| 点按钮没反应 | `程序\logs\app.log`（运行期诊断都进这里） | 与云朵／对话框相关时留意 `NameError` 类回归（见 R1624） |
| 任务卡在途 | 任务中心页、`程序\outputs\desktop-task-queue.json` | 在途＝等核实，绝不自动重提（见 `task_states.md`） |
| 费用对不上 | 项目费用台账（逐笔）与 Token 台账 | 缺单价的档位不给金额，不当 0 记 |
| 门禁红 | 报告里的 `文件:行号` | 先核验原始证据，不补造验收 |

## 7. 清理与卸载

- 程序可整目录删除；用户数据在项目目录（`episode`／`workflows`／`cloud_video`／`outputs`）内，按项目保留策略处理。
- 日志轮转先 `python scripts/maintain_logs.py --dry-run` 看范围，确认再实跑。
