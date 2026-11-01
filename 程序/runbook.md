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

### 详细口径（自 AGENTS §5 迁入）

**全量欠账口径（R1439，用户批准）**：唯一实现是 `run_selftests.FULL_SAFE_ROUND_INTERVAL`（8）、`source_rounds_since()`、`full_safe_required()`。只数 `last_full_safe_all_round` 之后、提交标题为 `R<n>:`／`R<n>-FAIL:` 且改过源码的轮次；纯文档、测试、`tasks_round/`、`维护记录/`、`说明/` 的轮次不计（`skills/` 下的 md 是 SKILL 源，计入）；读不出 git 历史时退回按全部轮次计。本节所列风险触发不受阈值影响：启动入口（`启动漫剧制作助手.pyw`／`启动助手.cmd`）、`storage_maintenance.py`（删除语义）、`tests/architecture/_layers.py`（层级登记表）由 `has_risk_change()` 按路径自动判定，任一轮改过就**立即触发后台补跑**，但门禁有宽限（`FULL_SAFE_RISK_GRACE`＝3）：自最早一次风险改动之后再积累 3 个源码轮次仍无凭据才报红，连续几轮改启动文件合并成一次全量（`risk_overdue()`）；Tk 控件生命周期（销毁／重建）无法静态判定，仍由执行者人工判断并手动跑全量。

**后台自动补跑**（带防抖）：欠账达到门禁线前 `FULL_SAFE_AUTO_LEAD`（2）个源码轮次，master 的 git post-commit 钩子（`维护记录/基准脚本/hooks/post-commit`，由 `install_git_hooks.py` 安装）调用 `scripts/auto_full_safe.py --spawn`，先起一个后台等待者（`--wait-run`，同一时刻只有一个）：等「安静」15 分钟（期间每有新提交就重新计时）再跑一次，连续拆分系列的 N 轮只补跑 1 次；欠账已让门禁报红或等满 60 分钟则立即跑。跑时在根目录 `.wt/ci` 干净分离检出上后台跑 `--all --safe`，绿凭据写入 common-dir 的 `full-safe-receipts.json`，日志在 `程序/logs/auto_full_safe.log`。钩子失败或已有同类任务在跑都静默跳过，不阻塞提交；后台运行期间（`auto_full_running()`）架构门禁不报「欠全量」，手动 `--all --safe` 也会被拒绝并提示等待（`--force` 可强制）——**欠账红灯出现时不要立刻手动跑全量，先看后台是否已在补跑**；`scripts/auto_full_safe.py --status` 查看欠账。后台全量红了不会自动改任何文件，按 §8 失败处置人工接续；**红后冷却**（R1781，`RED_COOLDOWN_SECONDS`＝4 小时）：上次后台全量是真红时，同一 HEAD 不再自动重跑，换了 HEAD 也要等冷却期过去才补跑，只有门禁已因欠账报红才越过时间冷却，避免红着不修时每次提交都白跑约 16 分钟，`--status` 显示「红后冷却」；结果写入 common-dir 的 `auto-full-safe-result.json`，post-commit 钩子每次提交先跑 `--notice`，上次未通过就在提交输出里打印红的测试文件与日志路径，`--status` 也会显示。`round_claim.py next` 领号时会自检 git 钩子，缺失或与版本受控源不一致就自动安装，新克隆无需手工装钩子。

## 5. 升级、备份与回滚

- 发布流程以 `说明/发布检查单.md` 为准；安装后对照 `安装信息.json` 与 `distribution_manifest.md` 核对落位（旧文档里的 `reorganize_install.py`／`install_release.py` 仓库里已不存在）。
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

## 10. 性能基准口径

`维护记录\基准历史.json` 是**历史参考，不作当前判据**：它是三类离线探针（启动与页面／热点路径／长列表）的自愿归档，最新记录停在 R1373（2026-10-12）；它记录的指标名（如 `first_frame_ms`、`ready_total_ms`、`cold_ms`、`warm_ms`、`row_count`）与现行契约**不同名、不同口径**，两者不能直接比较。

当前性能判据只有两处权威源：

- `tests\performance_contract.py`：11 条阈值常量（含 `STARTUP_RECURSIVE_SCAN_COUNT = 0`、`STARTUP_FIRST_FRAME_MS`、`LONG_LIST_SCROLL_MEDIAN_MS`、`MEMORY_DELTA_MB`、`BATCH_PLAN_PER_SHOT_MS`、`QUEUE_ITEM_MS`、`CONCURRENT_SUBMIT_ITEMS_PER_SECOND` 等）。
- `tests\test_perf_baseline.py`：把上述阈值写成用例，只拦明显退化；口径与放宽理由见其模块 docstring。

要让归档重新成为判据，必须先把探针指标名与 `performance_contract` 对齐、再在真机重跑一次；对齐之前，不得用 `基准历史.json` 的数字声称「回归」或「达标」。门禁在 `tests\architecture\test_agents_md.py`：断言本节存在，并在 `performance_contract` 的指标名与 `基准历史.json` 出现同名时报警，逼一次口径更新。

## 11. 覆盖率口径

`维护记录\覆盖率基线.json` 是**定向测量**，不是整仓覆盖率。当前基线：生产运行时模块 341 个，其中 52 个有行覆盖（其余 289 个在这 8 组定向用例里没被碰到），测量使用 8 组定向用例，测量时刻这些用例全通过。

- 字段口径：`modules_total` ＝ 生产运行时模块总数；`modules_covered` ＝ 其中被覆盖到的模块数；`targets` ＝ 本次测量使用的定向用例组；`tests_ok` ＝ 测量时刻目标用例是否全绿。
- 因此「240 个模块覆盖率 0」**不等于**「整仓覆盖率 7%」，也不能据此列出「未覆盖模块」清单——它只说明这 8 组定向用例碰过哪些模块。
- 测量工具 `scripts\coverage_report.py`（`sys.settrace`，零第三方依赖）。本仓随附解释器没有标准库 `trace`，也不引入 `coverage.py`；**不重跑测量**，刷新基线必须显式重跑工具，工具在目标用例失败时拒绝写基线。
- 诚实边界：阈值只对「基线里记录的那次测量」成立。门禁 `tests\architecture\test_coverage_baseline.py` 只做结构自洽、磁盘存在性、口径相等与核心路径下限四件事。

要一份真实的「未覆盖模块」清单，须另立一次全量 `sys.settrace` 测量（成本高，须用户同意）。
