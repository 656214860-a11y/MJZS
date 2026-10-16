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
| `python run_selftests.py --all --safe` | 安全全量（含架构门禁；后台自动补跑用的就是它） | 约 8–11 分钟（R1624 实测 502 秒） |

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

## 8. 辅助依赖清单（外部程序与网络服务）

运行时**零第三方 Python 包**（`tests/architecture/test_static_hygiene.py` 写明"本项目零运行时依赖"）；
所谓"辅助依赖"全部是外部程序与网络服务，缺谁都能在"环境自检"页看到。**清单的权威源是
`environment_check.py` 的检查项**（本表是投影）：

| 项 | 必需性 | 怎么找 | 缺了会怎样 | 权威源 |
| --- | --- | --- | --- | --- |
| FFmpeg / FFprobe | 成片合成与质检**必需** | `config.json` 的 `ffmpeg` / `ffprobe`；配了但不存在会退回 PATH 并给警告 | 成片合成、质检不可用 | `environment_check.check_ffmpeg` |
| ComfyUI 桌面程序 | 可选（只用云端模型可忽略） | 设置里的 `comfy_exe` → `C:\Program Files\Comfy Desktop\Comfy Desktop.exe` → `%LOCALAPPDATA%\Programs\ComfyUI\ComfyUI.exe` | 本地出图／视频不可用 | `environment_check.check_comfy`、`integrations.comfy_executable` |
| Blender | 可选（白模预演） | `white_model_service.find_blender` | 白模不可用 | `environment_check.check_blender` |
| Claude Desktop / Codex / Claude Code 命令行 | 可选（手动发送与命令行模型） | `workflow_settings.find_program` | 对应入口不出现 | `environment_check.check_desktop_programs` |
| Qwen Code | 可选 | 安装记录在 `安装信息.json`（`qwen` 字段） | 对应适配不可用 | `安装信息.json`、`qwen_adapter` |
| 模型密钥（网络服务） | 按需 | 环境变量 → 统一 `.env` → `private/.env`；**不落库** | 对应模型不可用，报「密钥无效或没配」 | `pet_llm.credential`、`README.md` 密钥表 |

密钥名（`README.md` 密钥表）：`DEEPSEEK_API_KEY`、`OPENAI_API_KEY`、`DASHSCOPE_API_KEY`（也认 `QWEN_API_KEY`）、
`COMFY_API_KEY`（Comfy 云）、`TTS_API_KEY`（配音）。

一个容易误判的点：**ComfyUI 的服务进程不是本助手的解释器**。Comfy Desktop 起的是它自己的
`.venv\Scripts\python.exe -s ComfyUI\main.py`，所以"强制关闭 ComfyUI"按命令行特征（含 `ComfyUI` 且含 `main.py`）认人，
而不是按进程名 `Comfy Desktop.exe` / `ComfyUI.exe`。

## 9. 解释器版本策略与 alpha → 稳定版迁移计划

现状：随附解释器 `运行环境\Python\python.exe`，当前 **Python 3.15.0a2（alpha）**；AGENTS §1 钉的就是这个路径，
**不使用全局 Python**。

**标准库是裁剪过的**：第 34 期从 `运行环境\Python\Lib` 剪掉 58 个模块，清单＝`tests/test_stdlib_closure.py`
的 `PRUNED`。两道静态闸：①从 `启动漫剧制作助手.pyw` 出发的 import 闭包必须逐层解析到盘上文件（**函数体里的
import 也算**；唯一放行的是只在 Blender 宿主里存在的 `bpy`）；②`PRUNED` 里的模块源码不许再 import、盘上也不许
悄悄出现，恢复要走归档（见该测试 docstring 指向的报告 §18.4／§21）。所以「某个标准库模块缺失」在这里通常是
**有意裁剪**而不是缺陷——本会话实测 `trace`／`symtable`／`sqlite3` 等都不可用，正是这份清单的结果。

迁移计划：

- **触发**：上游发布 3.15 稳定版，或 alpha 出现影响本项目的变更／安全问题。**没有硬期限**——现版本能跑，别为追新而迁。
- **前置**：记下当前基线（`.git/full-safe-receipts.json` 的绿凭据、架构门禁项数、默认冒烟 8/8、`本地CI.cmd exit` 出口绿）。
- **步骤**：
  1. 取官方 Windows 稳定版构建放进 `运行环境\`，先并列目录，**不覆盖**旧版；
  2. 用新解释器跑 `tests/test_stdlib_closure.py`：闭包必须全解析，并**重新决定裁剪清单**（稳定版标准库与 alpha 有差异，
     `PRUNED` 是「盘上事实」清单，必须与盘上一致）。注意 `venv`／`ensurepip` 也在裁剪范围内，别指望用随附解释器建虚拟环境；
  3. 依次跑 `smoke_test.py` → `smoke_test.py --architecture` → `run_selftests.py --all --safe`（≈8–11 分钟），全量绿才换默认路径；
  4. 手工过 GUI 面：Tk 启动、图标／快捷方式、白模宿主（`engine_probe.py` 可做真机探针）；
  5. 同步文档与记录：AGENTS §1 的解释器路径（若变）、`安装信息.json` 的 `version`／`installed_at`／`backup`、本表；
  6. **回滚**：旧解释器目录保留到全量绿＋一个完整使用周期之后再删。
- **风险**：alpha 的语法与标准库 API 变更；警告升级为硬错误的类别会先在门禁上暴露；裁剪清单随版本失效（必须重判）；
  启动耗时可能变化（`tests/architecture/test_startup_budget.py` 卡启动预算）。
- **红线**：不为迁移引入第三方依赖；不把裁掉的模块悄悄放回（要恢复走归档并同步 `PRUNED` 与文档）。
