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
| `开发者工具/启动助手.cmd` | 命令行启动（保留 stdout，便于看启动期输出） |
| `开发者工具/启动助手_测试模式.cmd` | 测试模式 |
| `开发者工具/本地CI.cmd` / `开发者工具/本地CI.cmd quick` / `开发者工具/本地CI.cmd exit` | 自检（见 §3） |

启动失败先看根目录 `启动错误.log` 与 `程序\logs\app.log`。

## 3. 验证与自检（按代价从低到高）

| 命令（工作目录 `程序`） | 作用 | 代价 |
| --- | --- | --- |
| `python smoke_test.py` | 默认冒烟 8 项 | 秒级 |
| `python smoke_test.py --architecture` | 架构门禁（分层／契约／棘轮，当前 356 项） | 约 3 分钟 |
| `开发者工具/本地CI.cmd exit` | 默认冒烟 → 静态门禁 → 架构门禁（Q10 出口，非 0 即失败） | 约 4 分钟 |
| `开发者工具/本地CI.cmd quick` | 默认冒烟 → 增量门禁 | 分钟级 |
| `开发者工具/本地CI.cmd targets` | 按 `程序\logs\ci_targets.txt` 逐行定向复跑 | 按清单 |
| `python run_selftests.py --all --safe` | 安全全量（含架构门禁；后台自动补跑用的就是它） | 约 8–11 分钟（R1624 实测 502 秒） |

跑测试要带 `PYTHONPATH`：`<程序>\tests;<程序>`（`ci_*.cmd` 已包装）。纪律：**全量不当排错工具**，
失败先用 `--affected` / `-k` 在定向层面修到绿，再复验全量；GUI 锁等待就等到底，不要中途终止后又重跑。

**隐藏桌面强制执行（R3039 起）**：含 Tk 的测试一律由运行器强制在隐藏桌面运行——`run_selftests.py`／`smoke_test.py`
检测本轮范围含 Tk（静态扫 `import tkinter`／`tk.Tk(`）即自包装到 `scripts/gui_hidden.py` 的临时桌面（`DRAMA_HIDDEN_DESKTOP=1` 防递归）；
隐藏桌面创建失败即中止（退出码 3），绝不降级为可见桌面直跑。`--visible` 仅人工调试（默认关，打印醒目警告），后台补跑禁止使用。
每轮 smoke 自带 `scripts/gui_hidden.py --probe` 秒级自检（建桌面即销毁），失败记冒烟失败。
`auto_full_safe.py` 用入库包装（随 `.wt/ci` 干净检出走），包装缺失或退出码 2/3/4 一律记 BLOCKED（环境阻塞，不冒充测试红、不触发红冷却）。
仓库外钩子 `~/.claude/hooks/gui_test_guard.py`（R1837 所装）已废弃，职责收敛到上述入库硬闸。门禁守护：`tests/architecture/test_hidden_desktop_gate.py`。

## 4. 全量欠账与绿色凭据

- 规则：主干提交序列里累计 **8 个改过源码的轮次**（R2538 起曾为 5、R3169 起回 8：高并发期全量实测 600–1100 秒，用户拍板降频；批次 3 基线显示 7 天内被修复的轮次比例约 69%，欠账越长返工越难定位）要求一次完整安全全量；启动入口、
  `storage_maintenance.py`、`tests/architecture/_layers.py` 属风险路径，另有宽限计数（权威阈值在 `run_selftests`）。
- 凭据：`.git/full-safe-receipts.json`（同一 `HEAD:程序` 内容树 7 日内可复用）。补跑由 post-commit 触发，
  日志 `程序\logs\auto_full_safe.log`，结果 `.git/auto-full-safe-result.json`。
- 门禁报「欠一次完整安全全量」时**不要手动全量**，等后台；只有后台确实没起来（锁丢了）才手动 `--all --safe`。

### 详细口径（自 AGENTS §5 迁入）

**全量欠账口径（R1439，用户批准）**：唯一实现是 `run_selftests.FULL_SAFE_ROUND_INTERVAL`（8）、`source_rounds_since()`、`full_safe_required()`。只数 `last_full_safe_all_round` 之后、提交标题为 `R<n>:`／`R<n>-FAIL:` 且改过源码的轮次；纯文档、测试、`tasks_round/`、`维护记录/`、`说明/` 的轮次不计（`skills/` 下的 md 是 SKILL 源，计入）；读不出 git 历史时退回按全部轮次计。本节所列风险触发不受阈值影响：启动入口（`启动漫剧制作助手.pyw`／`开发者工具/启动助手.cmd`）、`storage_maintenance.py`（删除语义）、`tests/architecture/_layers.py`（层级登记表）由 `has_risk_change()` 按路径自动判定，任一轮改过就**立即触发后台补跑**，但门禁有宽限（`FULL_SAFE_RISK_GRACE`＝2）：自最早一次风险改动之后再积累 2 个源码轮次仍无凭据才报红，连续几轮改启动文件合并成一次全量（`risk_overdue()`）；Tk 控件生命周期（销毁／重建）无法静态判定，仍由执行者人工判断并手动跑全量；仅替换 `desktop.py` 注入点且未改变控件生命周期不单独触发全量。

**后台自动补跑**（带防抖）：欠账达到门禁线前 `FULL_SAFE_AUTO_LEAD`（2）个源码轮次，master 的 git post-commit 钩子（`维护记录/基准脚本/hooks/post-commit`，由 `install_git_hooks.py` 安装）调用 `scripts/auto_full_safe.py --spawn`，先起一个后台等待者（`--wait-run`，同一时刻只有一个）：等「安静」15 分钟（期间每有新提交就重新计时）再跑一次，连续拆分系列的 N 轮只补跑 1 次；欠账已让门禁报红或等满 60 分钟则立即跑。跑时在根目录 `.wt/ci` 干净分离检出上后台跑 `--all --safe`，绿凭据写入 common-dir 的 `full-safe-receipts.json`，日志在 `程序/logs/auto_full_safe.log`。钩子失败或已有同类任务在跑都静默跳过，不阻塞提交；后台运行期间（`auto_full_running()`）架构门禁不报「欠全量」，手动 `--all --safe` 也会被拒绝并提示等待（`--force` 可强制）——**欠账红灯出现时不要立刻手动跑全量，先看后台是否已在补跑**；`scripts/auto_full_safe.py --status` 查看欠账。后台全量红了不会自动改任何文件，按 §8 失败处置人工接续；**红后冷却**（R1781，`RED_COOLDOWN_SECONDS`＝4 小时）：上次后台全量是真红时，同一 HEAD 不再自动重跑，换了 HEAD 也要等冷却期过去才补跑，只有门禁已因欠账报红才越过时间冷却，避免红着不修时每次提交都白跑约 16 分钟，`--status` 显示「红后冷却」；结果写入 common-dir 的 `auto-full-safe-result.json`，post-commit 钩子每次提交先跑 `--notice`，上次未通过就在提交输出里打印红的测试文件与日志路径，`--status` 也会显示。`round_claim.py next` 领号时会自检 git 钩子，缺失或与版本受控源不一致就自动安装，新克隆无需手工装钩子。

**合并门禁与红后冷却的关系（R2995）**：合并出口门禁（`tests/architecture/test_round_baselines.py` 欠账项）在 required 且无在跑全量、无同树绿凭据、非全量进程本身时，「同 HEAD 已红」冷却（`auto-full-safe-result.json` 的 head 与当前 HEAD 相同）不报红放行——合并提交推进 HEAD 是该冷却降级为 'time'（required 下自动补跑）的唯一途径，此时拦合并即死锁（2026-11-16 事故：全量红在 test_ui_batch5→同 HEAD 冷却→合并全卡，靠手动 `--run` 陪跑解开）；'time' 冷却与 BLOCKED 环境受阻结果仍报红。冷却判定唯一实现 `auto_full_safe.current_cooling()`／`red_cooldown()`。

## 5. 升级、备份与回滚

- 发布流程以 `说明/发布检查单.md` 为准；安装后对照 `安装信息.json` 与 `distribution_manifest.md` 核对落位（旧文档里的 `reorganize_install.py`／`install_release.py` 仓库里已不存在）。
- 回滚靠 Git：`升级备份/` 与 `.bak_*` 是历史证据、今后不再新增（AGENTS §2.6）。回滚后跑 §3 第一档自检。
- `程序\outputs\`、`程序\logs\`、私有配置不进发布包。

### 远端备份与服务器 CI（T1）

私有服务器 `backup`（`root@8.138.223.126`，仓库 `/srv/git/manju-assistant.git`）承担三件事，全部只用 python3 标准库、不依赖 Tk 与项目解释器：

- **pre-receive 门禁**：`维护记录/基准脚本/remote_pre_receive.py` 部署为 `hooks/pre-receive`——推送 `.py` 编译检查、凭据形态扫描、gitleaks（可选）、`master`/`main` 轮次证据门禁。参照副本 `/srv/git/ci/remote_pre_receive.py`。
- **post-receive 远端 CI**：`维护记录/基准脚本/remote_post_receive_ci.py` 部署为 `hooks/post-receive`——对 `master`/`main`/`codex/*` 推送把 bare 仓库 `--shared` 克隆到 `/srv/git/ci/work/<ref>`（含 `.git`，gitlink 技能包按 `维护记录/外部技能包哈希.json` 检出固定提交），在 `程序/` 下跑静态门禁＋架构门禁（平台边界用例按脚本内显式清单排除）；结果在 `/srv/git/ci/results/`（`last_ci_status.json` 与 `<ref>.status.json` 汇总，逐 ref 日志同目录）。post-receive 不能拒绝推送，红了看状态文件与日志。
- **每周 bundle 备份**：`/etc/cron.d/manju-bundle` 每周一 04:00 跑 `/srv/git/ci/weekly_bundle.sh`，产物 `/srv/git/backups/manju-<日期>.bundle`，只留最近 4 份。校验：`python -B scripts/backup_verify.py /srv/git/backups`（自动以同级 `manju-assistant.git` 作 verify 上下文；bundle verify 必须在仓库内跑）。

**覆盖差异（T1 口径）**：Linux 远端只覆盖「静态门禁＋架构门禁」；默认冒烟（Tk）、增量门禁、安全全量自检仍在 Windows 本机（`scripts/local_ci.py exit`、`run_selftests.py --all --safe`、auto_full_safe 凭据）。服务器 Python 3.11 与本机 3.15 有版本差，远端绿不等于本机绿——合入 master 仍以本机 CI 出口为准。

**夜间全量**：`auto_full_safe.py` 在 master 欠账到线时由 post-commit 自动补跑；计划任务 `ManjuNightlyFullSafe` 每天 03:30 对 `.wt/ci` 干净树兜底跑一次（机器未开机错过的当天不补，下个欠账触发点自然覆盖）。安装/卸载：`维护记录/基准脚本/install_nightly_task.cmd [install|uninstall]`。

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
| 模型密钥（网络服务） | 按需 | 本机加密存储（`.env` 与 `private/.env` 的密钥第一次读取时一次性迁入，文件不删、之后不再读）→ 环境变量；**不落库** | 对应模型不可用，报「密钥无效或没配」 | `pet_llm.credential`、`README.md` 密钥表 |

**最低版本（建议值）**：`environment_check.MIN_VERSIONS`——FFmpeg／FFprobe ≥ 4.4、Blender ≥ 3.6。只在用户点「环境自检」时启动程序读版本（`run_checks_with_versions()`；`run_checks()` 本身不启动程序），低于最低版本只给「提示」、不拦截，版本认不出（如 git 构建）原样保留状态。

密钥名（`README.md` 密钥表）：`DEEPSEEK_API_KEY`、`OPENAI_API_KEY`、`DASHSCOPE_API_KEY`（也认 `QWEN_API_KEY`）、
`COMFY_API_KEY`（Comfy 云）、`TTS_API_KEY`（配音）。

一个容易误判的点：**ComfyUI 的服务进程不是本助手的解释器**。Comfy Desktop 起的是它自己的
`.venv\Scripts\python.exe -s ComfyUI\main.py`，所以"强制关闭 ComfyUI"按命令行特征（含 `ComfyUI` 且含 `main.py`）认人，
而不是按进程名 `Comfy Desktop.exe` / `ComfyUI.exe`。

## 9. 解释器版本策略与 alpha → 稳定版迁移计划

现状（2026-11-17，用户批准依赖迁移）：共享路径 `运行环境\Python\python.exe` 此前已切为 **Python 3.14.7 完整标准库**；本任务的功能树另建同版本隔离生产环境，只预装 requirements.txt 锁定六包，不复制个人 site 或开发工具。AGENTS §1 路径不变，**不使用全局 Python**。旧3.15裁剪环境保留为回滚备份；新版本全量与桌面启动验收未完成前，不宣称正式发布。

历史：2026-11-02 的3.15.0裁剪版、其3.15.0a2备份及当时7082条绿凭据只证明当时检出，不证明当前3.14.7及依赖迁移通过。当前候选副本已验证隔离导入/本地HTTP与可复制路径；默认桌面启动、退出和最终全量仍按本次结果追踪。

**标准库恢复是本次有意契约变更**：不再要求历史58项裁剪模块物理缺失。`tests/test_stdlib_closure.py` 保留启动 import 闭包逐层可解析（包括函数体import）与包子模块真实存在的行为检查；第三方模块须来自 requirements.txt 明确锁定且当前环境内可解析，不能用个人site兜底，也不能放行任意缺包。历史裁剪清单仅作迁移证据，不作为完整运行环境的禁止列表。

迁移计划：

- **触发**：上游发布 3.15 稳定版，或 alpha 出现影响本项目的变更／安全问题。**没有硬期限**——现版本能跑，别为追新而迁。
- **前置**：记下当前基线（`.git/full-safe-receipts.json` 的绿凭据、架构门禁项数、默认冒烟 8/8、`开发者工具/本地CI.cmd exit` 出口绿）。
- **步骤**：
  1. 取官方 Windows 稳定版构建放进 `运行环境\`，先并列目录，**不覆盖**旧版；
  2. 用新解释器跑 `tests/test_stdlib_closure.py`：闭包必须全解析；当前采用完整标准库，历史 `PRUNED` 仅追溯迁移，不能继续要求其缺失。生产依赖按 requirements.txt 在隔离环境安装，不依赖用户 site；
  3. 依次跑 `smoke_test.py` → `smoke_test.py --architecture` → `run_selftests.py --all --safe`（≈8–11 分钟），全量绿才换默认路径；
  4. 手工过 GUI 面：Tk 启动、图标／快捷方式、白模宿主（`engine_probe.py` 可做真机探针）；
  5. 同步文档与记录：AGENTS §1 的解释器路径（若变）、`安装信息.json` 的 `version`／`installed_at`／`backup`、本表；
  6. **回滚**：旧解释器目录保留到全量绿＋一个完整使用周期之后再删。
- **风险**：alpha 的语法与标准库 API 变更；警告升级为硬错误的类别会先在门禁上暴露；裁剪清单随版本失效（必须重判）；
  启动耗时可能变化（`tests/architecture/test_startup_budget.py` 卡启动预算）。
- **红线**：生产依赖只按 requirements.txt 与白名单评估；解释器变更须同步闭包测试和本节，发布前全量及桌面启动未通过不发正式版。历史备份不在本任务清理。

## 10. 性能基准口径

`维护记录\基准历史.json` 是**历史参考，不作当前判据**：它是三类离线探针（启动与页面／热点路径／长列表）的自愿归档，最新记录停在 R1373（2026-10-12）；它记录的指标名（如 `first_frame_ms`、`ready_total_ms`、`cold_ms`、`warm_ms`、`row_count`）与现行契约**不同名、不同口径**，两者不能直接比较。

当前性能判据只有两处权威源：

- `tests\performance_contract.py`：11 条阈值常量（含 `STARTUP_RECURSIVE_SCAN_COUNT = 0`、`STARTUP_FIRST_FRAME_MS`、`LONG_LIST_SCROLL_MEDIAN_MS`、`MEMORY_DELTA_MB`、`BATCH_PLAN_PER_SHOT_MS`、`QUEUE_ITEM_MS`、`CONCURRENT_SUBMIT_ITEMS_PER_SECOND` 等）。
- `tests\test_perf_baseline.py`：把上述阈值写成用例，只拦明显退化；口径与放宽理由见其模块 docstring。

要让归档重新成为判据，必须先把探针指标名与 `performance_contract` 对齐、再在真机重跑一次；对齐之前，不得用 `基准历史.json` 的数字声称「回归」或「达标」。门禁在 `tests\architecture\test_agents_md.py`：断言本节存在，并在 `performance_contract` 的指标名与 `基准历史.json` 出现同名时报警，逼一次口径更新。

R2979 起探针侧已按 `performance_contract.py` 末尾对照表补齐同口径指标：长列表新增 `scroll_median_ms`（与 `LONG_LIST_SCROLL_MEDIAN_MS` 同为 60 帧中位数）、`fill_ms`（分批插行长齐总时长），长列表滚动测量前先等行长齐（与 `test_perf_baseline` 同口径 settle）；`first_frame_ms` 本就同口径。归档其余指标（页面墙钟、行数、内存绝对值、热点路径）仍无契约常量对应物，只作期间趋势参考、不作判据。

## 11. 覆盖率口径

`维护记录\覆盖率基线.json` 是**定向测量**，不是整仓覆盖率。当前基线：生产运行时模块 665 个，其中 85 个有行覆盖（其余 580 个在这 12 组定向用例里没被碰到），测量使用 12 组定向用例，测量时刻这些用例全通过。

- 字段口径：`modules_total` ＝ 生产运行时模块总数；`modules_covered` ＝ 其中被覆盖到的模块数；`targets` ＝ 本次测量使用的定向用例组；`tests_ok` ＝ 测量时刻目标用例是否全绿。
- 因此「580 个模块覆盖率 0」**不等于**「整仓覆盖率 12%」，也不能据此列出「未覆盖模块」清单——它只说明这 10 组定向用例碰过哪些模块。
- 测量工具 `scripts\coverage_report.py`（`sys.settrace`，零第三方依赖）。本仓随附解释器没有标准库 `trace`，也不引入 `coverage.py`；**不重跑测量**，刷新基线必须显式重跑工具，工具在目标用例失败时拒绝写基线。
- 诚实边界：阈值只对「基线里记录的那次测量」成立。门禁 `tests\architecture\test_coverage_baseline.py` 只做结构自洽、磁盘存在性、口径相等与核心路径下限四件事。

要一份真实的「未覆盖模块」清单，须另立一次全量 `sys.settrace` 测量（成本高，须用户同意）。

分支覆盖率（SWE-2 T8.4，L0/L1 棘轮）：`维护记录\分支覆盖率基线.json` 同样是**定向测量**，不是全量套件分支覆盖率。口径：对 `_layers.LAYERS` 登记层 0/1 的 97 个实体模块（含迁包与无顶层门面的实体）统计「决策点双结果覆盖」——`if`／`while`／`for`／`try`（含 `except*`）／`match` 每个决策点要求两个方向都被真实执行过；单行复合语句（`if x: y`）、表达式短路（`and`／`or`／三元／推导式 if）、`try/finally`（无 handler）不计入分母；`while` 退出＝条件判假、`for` 耗尽＝迭代器走完（`break` 离开不算）；`match` 末位 `case _` 时只要求 case 被进入。动态证据按 `(文件, co_qualname)` 归属代码对象作用域。测量工具 `scripts\branch_coverage_report.py`（同 `sys.settrace`、零第三方依赖），棘轮下限在 `维护记录\分支覆盖率下限.json`（只许人工上调，工具重测不改写），门禁 `tests\architecture\test_branch_coverage_floor.py` 只做结构自洽、模块集合相等、下限不回退与工具可用性四件事，不重跑测量。刷新基线必须显式重跑工具并同步上调下限表，目标用例失败时工具拒绝写基线。

## 12. 领号、并行车道与工作树流程（自 AGENTS §2.5 规则 27／34a 迁入）

AGENTS 只保留触发条件；本节是细则全文。开工领号、建工作树、回收车道时读本节。

**领号与队列（规则 27）**：开工先运行 `维护记录/基准脚本/round_claim.py next` 领取轮次，有匹配队列任务时再 `claim <队列ID> --owner <署名>`，没有则记录无对应 ID，不冒领无关任务。轮次计数器与唯一可写队列 `<git common-dir>/maintenance-queue.json` 共用认领锁；`next` 同时把「轮次→认领工作树」写进 `<git common-dir>/round-claims.json`（独立文件，旧版领号不感知也不破坏），commit-msg 据此校验归属而非「最新领号」，多车道并行时先领号者不再被后领号者顶掉提交；升级前已领、无归属记录的在途轮次可在认领工作树运行 `round_claim.py record <轮次号>` 补登，或按旧规则等 `last_claimed`。工作树内 `维护记录/任务队列.json` 仅为只读快照，不手工编辑。默认租约 60 分钟，他人的有效租约不得覆盖；`release`／`complete`／`show`／`validate` 语义不变。每轮结束检查 `N == M + 1`（N 为 project_status.md 当前轮次，M 为最新结果文件轮次），不连续时先修正编号再继续。

**轮的定义**：一轮＝一个可独立回滚的完整变更集。同类改动必须批量成轮（如 UI 卡片迁移按页面一次 ≥5 处），不做一卡一轮、一字段一轮。

**全量触发条件**：统一见 AGENTS §5；计数行为以 `run_selftests.full_safe_required()` 与 `tests/architecture/test_round_baselines.py` 为核对依据，不在此另设周期。

**并行硬规则**：同一时刻活跃 `codex/*` 车道上限 20 条（冻结期内只有主树可提交）；一个队列 id 全局只允许一条线持有；分支 ahead>10 必须先回合或 rebase，否则 `round_claim.py next` 拒绝领号（ahead 口径按源码提交计，纯文档／结果文件提交不计，B3 落地）；detached HEAD 工作树不得开工；分支 behind>20 或 ahead=0 且 48 小时无活动即列入待回收。回收前保存未提交内容、核验活跃租约；用 `维护记录/基准脚本/worktree_ledger.py --plan` 生成计划，删除须用户逐条确认，台账不自动删除。

**高并发治理（R3108 起，机制随 B 轮逐项落地）**：车道活跃状态以 `<git common-dir>/lanes.json` 登记为准（lane→分支→工作树→owner→role→last_seen，B3 落地，落地前以 `worktree_ledger.py --plan` 为准）；合并走合并请求队列＋专职合并车道，会话不再各自阻塞 `dev.py merge`（B1 落地）；GUI 密集改动优先走 `role: gui` 车道，其余车道 GUI 测试排队优先级降低（B2 落地）；队列租约支持心跳续约，失联车道警告不阻断、MERGE_HEAD 超龄只提示人工处置不自动 abort（B1/B3 落地）。

**脏树处置协议（并行吞吐治理任务书 A2 起）**：台账把脏树一律 KEEP，删除前按三类裁定——① 仅未跟踪草稿（截图、_snapshot、nul、preview_* 等）：复制到 <git common-dir>/rescue/<lane>/ 留档后可删；② 含已跟踪改动：先 git -C <树> add -N . && git -C <树> diff HEAD > <common-dir>/rescue/<lane>.patch 保存补丁（rescue 目录在 .git 内、不入库、不随工作树删除），再由用户逐条确认；③ 百级以上文件的大改动活树视为在途工作，不动。分支删除只走 git branch -d（拒绝未合并项），前缀提交等价已由 ledger 的 MERGED／PARKED／ACTIVE-WT 分类给出，patch 等价核验用 git cherry master <分支>（全 '-' 即内容已在主干）。

**检查点**：认领因脏树拒绝时，先区分本轮改动与用户既有改动；只对授权文件建立可恢复检查点。创建分支本身不保存未提交内容，不得把用户改动混入 WIP 提交。大规模跨文件修改应分阶段建立检查点，检查点不等于任务完成。

**主工作区＝镜像 + 功能工作树开发（规则 34a）**：每个独立任务（新功能、Bug 修复）在专用功能工作树中进行；主工作区只做「同步 → 合并 → 提交」三个动作，不直接开发。开工顺序：① 进主工作区跑 `scripts/dev.py sync`（`fetch <远端>` 后仅 `--ff-only` 快进，**只拉不推**），确保基于最新干净基线；② 用 `git worktree add -b codex/<任务>` 从最新主干创建并进入功能工作树——Git 的分支唯一检出限制保证主工作区占用 master、功能工作树检出各自独立分支，互不干扰；③ 在工作树内完成全部开发；④ 交付前在该工作树内 `git rebase master`（或最新主干）解决冲突，再回合主工作区。这套纪律靠「保持主工作区干净」维持：主工作区有未提交改动时不切换分支、不同步，`sync` 与 `round_claim.py next` 都会因脏树拒绝。工作树命名、并行车道上限与回收见本节及 `worktree_ledger.py`。

**统一命名（R3218）**：agent 新建功能分支统一为 `codex/<小写kebab-case任务名>`，如 `codex/whitelist-framework`；仅允许 ASCII 小写字母、数字与单个连字符分段，不接受大写、下划线、空段或多层路径。`dev.py claim --branch codex/<任务>` 转交 `round_claim.py next --branch`，显式新名在领号和状态写入前校验；自动停泊生成 `codex/wip-r<N>`。已检出的 `codex/*`（含 legacy `wip-R<N>`）保留原名，不追溯改名。Git 手工建树不会调用此入口，agent 必须使用合规名；本规则不授权改名/清理他人的活跃树。工作树目录可沿用现有管理位置，不把目录名当作分支名；Git 元数据 `.git/worktrees/` 不是 checkout 目录。

**第一步硬性动作**：任何功能轮／修复轮，动手改 `程序/` 源码之前，第一件事是 `dev.py claim`（领取轮次）或先确认自己已在功能工作树分支上；在 master 主工作区上直接编辑 `程序/` 源码即违反规则 34a。`pre-commit` 钩子已强制：master/main 上非合并提交任何功能 `程序/` 文件都会被拒绝（合并提交与 tasks_round／project_status.md／任务队列.json 除外）；`round_claim.py next` 与 `commit-msg` 钩子也在领号／提交时分别拦截脏 master 与轮次号未领或不属于本工作树。三道闸（pre-commit、round_claim、commit-msg）共同兜底，纪律起点仍是「先领号、再动码」。

## 13. Git 提交与合并（自 AGENTS §2.6 迁入）

提交与领号由当前执行 agent 执行。复核全绿后才提交；一批一轮，只暂存本批文件；提交信息带轮次号，涉及需求的带 `REQ-`（及 `DES-`）编号。

35. 每轮通过基线、写完结果文件且凭据形态扫描未命中后，执行一次收尾 `git add` + `git commit`；私有数据、日志和用户项目内容保持在暂存区之外。
36. 收尾提交信息以轮次号开头，例如 `R745: 说明`；在 `[TASK_FAILED]` 或 `[TASK_BLOCKED]` 时可保留诊断性检查点提交，且必须以 `R745-FAIL:` 开头。
37. 提交前检查 `git status` 与暂存清单；命中凭据形态或受忽略运行路径即拒绝提交，并在结果文件记录阻断原因。
38. 只在用户明确要求时 `git push`。
39. 用户要求回滚时，优先用 `git revert` 保留历史，而非 `git reset --hard`。
40. 每轮结果文件 `tasks_round_N_result.md` 中记录本轮是否已提交，以及 commit hash（若已提交）。
41. 协作 hooks 源码位于 `维护记录/基准脚本/hooks/`；每个工作树初始化后运行 `维护记录/基准脚本/install_git_hooks.py` 安装到共享 Git hooks。提交包含非默认文档的 `程序/` 文件时，必须显式设置 `CODEX_STAGE_ALLOWLIST`（分号分隔 repo 相对路径）；以最小暂存清单提交，不用 `git add -A`。仅 master 可提交 `project_status.md`。

分支记录只写 `程序/tasks_round/tasks_round_<n>_result.md`，合入 master 后单独提交一次补进 `project_status.md`（提交信息 `R<n>: 补记分支 <分支名> 的轮次记录`）。

合并时上述共享状态文件不得整块取一边，必须保留双方全部记录；合并提交后把下列命令的原始输出贴进结果文件，只写「已解决冲突」不算通过——第一条输出必须为空，第二条轮次号必须是两边的并集：

- `git diff <合并前master>..HEAD -- 程序/project_status.md | grep '^-' | grep -v '^---' | grep -v '当前轮次：'`（表头「当前轮次」行每轮都会改，故排除）
- `git show HEAD:程序/project_status.md | grep -oE '^R[0-9]+' | sort -u`

**轮次证据与合入门禁（R2527 起）**：`dev.py commit` 对 R2527 及以后的提交生成 `tasks_round/evidence/R<N>.json`（`维护记录/基准脚本/round_evidence.py`）：凭据扫描由脚本对已暂存的新增行执行，只记「文件:行:规则名」；定向测试由 `--tests <模块关键词>` 触发 `run_selftests.py -k`。改了 `程序/` 下 `.py` 而没带 `--tests`、凭据命中或测试有红，一律拒绝提交；纯文档提交记为 `docs-only`，合并提交记为 `merge-ci-exit`。`round_gate.py` 读这份证据，不再匹配结果文件里的文字，阈值取自 `维护记录/测试分层基线.json` 的 `architecture_gate_files_min`／`skill_registry_count`／`smoke_checks_expected`（只增不减）。`dev.py merge` 流程（R3117 起）：merge --no-commit → `local_ci.py exit` → 等全量验收锁 → 领号 → 提交；CI 失败与等锁超时都中止还原且不领号（不烧轮次），提交失败且 MERGE_HEAD 确属本分支时自动还原防僵死；MERGE_HEAD 超 45 分钟未结会报警提示人工处置，绝不自动 abort。pre-commit 在暂存了 `程序/*.py` 时先跑 `tests.test_static_names` 与 `tests.architecture.test_static_hygiene`（约 6 秒），红则拒绝提交。

**车道范围门禁（R2611 起）**：两条并行车道各自实现同一需求时会「新增」同名文件，合入时变 add/add 冲突（R2542 对 R2538 工程闸门批次4 的重复实现）。防线有两层：① 开工前 `dev.py scope <路径>...`（`维护记录/基准脚本/branch_scope.py`）把计划触及的路径与各活跃工作树分支相对 master 的改动求交，重叠即提示；`--added` 只看新增文件口径，`--json` 机器可读。② `dev.py commit` 时暂存区新增文件与其他活跃分支新增文件同名即拒绝提交（`commit_round.check_scope_overlap`，exit 5）；合并提交（MERGE_HEAD）与 master/main 不触发。「活跃分支」＝`git worktree list` 中带分支引用的工作树，排除主干与当前分支；无工作树的未合并分支视为停放或遗留，不阻断，其风险由合并轮 CI 兜底。

**规则文件预算与规则守卫（R2530 起）**：`tests/architecture/test_agent_doc_budget.py` 限制 `程序/AGENTS.md` ≤16000 字节、根 `AGENTS.md` ≤2000、`CLAUDE.md` ≤4000，并要求 §5、§8、§2.6 的标题落在前 16384 字节内、相对链接都存在；超了先删旧规则，细则写进本手册。`scripts/rule_guard_map.py --write` 生成 `维护记录/规则守卫对照.md`（规则编号→守卫测试，登记在 `维护记录/规则守卫基线.json`，`test_rule_guard_map.py` 校验同步）；没有守卫的规则上限固定在该测试的 `UNGUARDED_CEILING`，只许减少。可选的外部体检：`npx agents-md-polish audit 程序/AGENTS.md`（需联网，不进 CI）。出站 HTTP 只许经 `platform_tools.open_https()`（规则 42，`test_outbound_http_authority.py` 守卫，ComfyUI 本机请求也已迁入）。

**结果侧观测（R2533 起）**：`python -B scripts/dora_report.py [--days 30]` 只读输出前置时间（分支首个独有提交到合入 master）、`R<n>-FAIL:` 占比、「7 天内被修复」比例（同模块又有「修复」提交，启发式）、返工热点前 15 个模块、红灯停留与按 `Agent:` 来源的分组，并写 `程序/logs/dora_最近.md`。红灯停留的原始数据是后台全量每次结束追加到 common-dir `full-safe-history.jsonl` 的一行（环境受阻不记）。`dev.py commit --agent <名称>` 在提交信息末尾加 `Agent: <名称>`。这些是结果侧信号，不设阈值、不是目标；冒烟 8/8 与架构门禁数量只是健康检查。

**其余闸门工具（R2538 起）**：① `scripts/typecheck_baseline.py --check|--update`——开发机用 `npx pyright@1.1.414`（basic、Python 3.13）数每个生产模块的类型错误，基线 `维护记录/类型检查基线.json` 只许减少，需要 Node 与联网，不进产品和发布包；`tests/architecture/test_type_check_baseline.py` 只守基线文件自洽。② `scripts/skill_package_pins.py --check|--update`——外部技能包（gitlink）的来源、固定提交与 git 内容树哈希登记在 `维护记录/外部技能包哈希.json`，已检出的包被改过或漂移即红，升级外部包后用 `--update` 重新登记。③ `tests/architecture/test_gate_selfaudit.py`——路径权威、删除权威、静默异常、秘密出口、分层 5 个门禁各有坏／好样本，门禁被改坏时先红。④ `tests/test_fault_injection_chain.py`——传输层注入超时／429／5xx／半截响应，核对计量台账不重复计费、未知用量不算已花费、没有产物时模型嘴上说完成也不发 `stage.completed`。⑤ 结果文件标题行之后由 `dev.py commit` 写一行 `<!-- round-evidence: {...} -->`（类型、命令、退出码、通过／失败数、证据文件摘要、基线提交），已有则替换。
**测试搬家守卫（规则 16）**：`scripts/test_move_audit.py` 核对暂存区或某个提交——测试文件新增／删除、或新旧内容除 `import` 行外有任何差异都不通过；`dev.py commit` 在提交信息首行以「R<n>: 测试搬家」开头时自动核对，不通过拒绝提交。规则 26 由 `test_rule_guard_map.py` 守卫（新增规则不登记守卫即红）。暂无守卫的规则只剩 25、30a、32，均为纯流程要求。
**服务器端闸门（R2716 起已部署）**：备份服务器 `/srv/git/manju-assistant.git/hooks/pre-receive` 即 `维护记录/基准脚本/remote_pre_receive.py`（静态编译＋新增行凭据形态＋可选 gitleaks＋master/main 证据门禁四合一）。证据门禁判据与 `维护记录/基准脚本/server_hooks/pre-receive`、`round_evidence.judge` 同口径：推到 master/main 的 R2527 及以后源码轮次提交必须带同一提交里的绿色证据文件，删除 master/main 一律拒绝，其它分支不受此限。更新钩子＝把 `remote_pre_receive.py` 传到 hooks/ 下并 `chmod +x`；紧急绕过只能由服务器管理员临时摘掉钩子。注意：backup 远端 master 落后本地较多时，首次同步推送会因历史提交缺证据被拒（R2716 实测 186 个待推提交中 8 个缺证据），需管理员一次性摘钩推送后再装回。

## 14. 文档先行：需求 → 设计 → 实现（自 AGENTS §2.7 迁入）

适用范围：`docs/stages/` 下已建需求与设计的阶段（01–13 已全部建立）。

1. **何时必须先改文档**：只有**功能轮**与**契约轮**改变阶段行为时，先改需求（`REQ-<阶段>-<序号>`），再改设计（`DES-<阶段>-<序号>`，标注对应 REQ），最后改代码与测试。**修复轮**按下文第 15 节 3.2 先判断是代码偏离需求还是需求要改；性能、可靠性、兼容、结构治理、测试搬家、验证基线、只读诊断、状态接续各轮不要求先改文档，但改动使某条 REQ 的事实变化（含锚点测试变红）时，同轮同步该条 REQ／DES 文字，结果文件注明。
2. **文档原地修改，不记历史**：历史看 git；删除的编号不复用；状态用 ✅ 已实现／🟡 部分实现或与代码不一致／⬜ 未实现／❓ 待人拍板。
3. **需求与代码冲突时不自行选边**：标 🟡 或 ❓，列出两边证据，由用户拍板；执行者不为了让文档与代码一致而擅自回退或改写另一边。
4. **测试锚定需求（有门禁）**：测试名或 docstring 写 `REQ-xx`（支持 `REQ-S10-01/02` 简写），锚点必须真的检验需求内容。`tests/architecture/test_requirement_traceability.py` 强制：新增的 ✅ 需求没有测试锚定即红（补测试或降为 🟡）；测试引用不存在的编号即红；历史欠账登记在 `维护记录/需求锚定基线.json`，只许减少，补上锚点后必须同轮从基线删除。查某条需求的相关测试用 `python -B tests/architecture/test_requirement_traceability.py --find REQ-S01-51`，不手工维护对照表。
5. **阶段级条款只写在 docs/**：已建文档的阶段，其专属规则（字段、流程、文件名、产出范围）写入对应阶段文件（`docs/stages/Sxx_*.md` 的 `## 需求`／`## 设计`），不再追加到 AGENTS 或 `architecture.md`；AGENTS 只保留跨阶段硬约束。
6. **与 `architecture.md` 的分工**：全局分层、权威源表、目录树仍以 `architecture.md` 与 AGENTS §2.2 为准；阶段文件的 `## 设计` 节只描述该阶段内部的模块分工与设计条目，不另立第二套分层。
7. **编号链**：`REQ-Sxx-nn` → `DES-Sxx-nn`（标注所实现的 REQ）→ 测试 docstring 写 REQ → 结果文件和提交信息写 REQ／DES。

## 15. 轮次类型细则（自 AGENTS §3 迁入）

AGENTS §3 只有类型总表；各类型的完整边界在此。每轮开工前先声明类型。

### 3.1 功能轮（默认）
新增或扩展功能。涉及已建 `docs/` 的阶段时，先按第 14 节改需求与设计，再写代码；结果文件注明 REQ／DES。只改本轮任务涉及的模块；不改分层、契约或权威源。完成后跑 `smoke_test.py --affected <模块>`。越界依赖须回退。

### 3.2 修复轮
修 bug、修偶发红、修阻塞。先定位根因，输出复现步骤。涉及已建 `docs/` 的阶段时，先判断是代码偏离了需求还是需求本身要改（第 14 节第 3 条）；前者修代码，后者先改文档。只改根因所在模块，不顺手重构；测试契约按 AGENTS §2.4。

失败回归导致产品或测试资产修复时，一律归类为**修复轮（含全量基线验证）**，遵守根因、最小改动与同类问题复核要求；全量只是验证范围。仅记录、复核或更新基线而未修复资产时，归类为 3.10 **验证/基线轮**；报告和状态台账只使用已定义的类型名。

### 3.3 结构治理轮
合并重复、收口路径、拆循环、删僵尸。不加功能、不改用户数据；每次最多改 3 个模块。自检统一按 AGENTS §5。SKILL 说明文件（`skills/**/*.md`）改动不与代码改动同轮：`run_selftests.py` 的 `data_moved` 判定会让增量台账整表失效。更新 `architecture.md`，结果写 `tasks_round/tasks_round_N_result.md`。

**纯元数据批量例外**（2026-11-18 起，用户授权以提高效率）：本轮改动只限于添加或修正 `__all__`、类型注解、docstring、契约清单与登记表条目、`warnings.deprecated` 标注，且不改变任何运行时行为（逻辑、签名、返回值、模块级状态、import 副作用均不变）时，每轮最多改 12 个模块。条件：跑 `run_selftests.py --all --safe`；结果文件逐模块列出改动清单并逐条声明「无行为变化」；任一模块出现行为变化，该模块退出批量、按普通结构治理轮（≤3 模块）另立轮次。

**子场景**：用户已确认的任务书中已排定的结构治理轮，视为用户已指定子场景为「执行」，来源写任务书文件名与轮次编号，不再反问。其余情况开工前由用户明确指定子场景：

- **只读诊断**：扫描结构，输出含 A-M 的新报告，末尾含 J 整改路线、K 测试迁移计划；写入边界按 3.5。
- **执行**：读指定报告的 J/K，执行其中一条，写明来源报告路径与条目编号。用户未指定子场景时，先反问："本轮是只读诊断，还是按某份报告执行？"，由用户回答后再开工。

### 3.4 契约轮
只改 L0 契约层：`contract/` 包内全部模块（2026-11-18 起由原五个点名模块放宽，用户授权以提高效率），含新建模块与为迁出实体保留的 `sys.modules` 别名门面；新建模块须同轮登记 `tests/architecture/_layers.py` 为 L0，契约清单（`contract/_manifest.py`）建立后同轮登记清单与 `contract/CHANGELOG.md`。L0P 平台基座（`foundation/`）建立后，契约轮可同轮改其中承接本轮迁出实体的模块，合计不超过 3 个。不动 L1 以上，跑全量自检，同步 `architecture.md`；只有新增或改变硬约束时才改 AGENTS §2.3（并按规则 26 配测试）。仅审计、核对或记录 L0 契约而未改实现时同样归类为契约轮。

### 3.5 只读诊断轮
只诊断，不改代码：不修改任何 `.py`，不搬目录、重命名、删文件。仅新增未占用的 `tasks_round/tasks_round_N_result.md`，不覆盖历史结果。轮次元数据例外仅限：经规则 27 入口认领／完成中央队列并导出快照、同步状态页轮次头为最新报告号加一；不改状态正文，不把诊断结论记为修复完成。人工待办勾选须有对应诊断任务已完成的证据及用户授权。用户明确要求“任何文件不改”或更窄的写入范围时，先说明与轮次归档的冲突并请求明确范围。普通只读问答（如查看 git status）不自动立轮、认领或写报告。等确认后再进入修复。

### 3.6–3.11 其他轮次

| 节 | 类型 | 边界与验收 |
| --- | --- | --- |
| 3.6 | 测试搬家轮 | 只迁移、重命名或归档测试与相关收集／导入；不改产品行为、测试逻辑、断言或 fixture；无双份或伪迁移，定向、默认冒烟及完整安全全量通过。 |
| 3.7 | 性能/资源轮 | 以可复现基线和目标为依据，不以正确性、可恢复性或用户数据安全换指标；记录测量条件、改前后指标和资源边界，定向与默认冒烟通过。 |
| 3.8 | 可靠性/数据迁移轮 | 旧数据可读，迁移可重复或可恢复，不静默丢数据；覆盖迁移前后、失败恢复和旧数据兼容，必要时跑跨层全量。 |
| 3.9 | 兼容/平台适配轮 | 不改既有主平台行为，平台分支集中在适配边界；目标平台验证通过，路径与编码符合权威服务，默认冒烟通过。 |
| 3.10 | 验证/基线轮 | 只验证、记录和必要的测试资产维护，不混入无关功能；记录命令、环境、结果及基线差异，失败项有可追踪结论。 |
| 3.11 | 状态接续轮 | 只依据仓库事实、验证结果和已有报告，不把推测写成完成；`project_status.md` 与结果报告的轮次、范围、验证状态一致。 |

## 16. 任务书与任务完成文件（自 AGENTS §2.5 规则 35 迁入）

- **任务书**：自包含（执行者无需会话上下文），放 `程序/tasks_round/<主题>任务书.md`。结构含：总目标、已确认决策清单（不得自行变更）、现状盘点、分轮拆解（每轮改动＋验收勾选）、测试方案、风险与回滚、交付留痕。
- **任务完成文件**：任务书全部轮次收尾后，输出 `程序/tasks_round/任务完成/<任务书名>·任务完成.md`。逐条任务列完成证据（轮次号、结果文件、测试凭据、commit hash）；未完成项如实标注并给处置（转欠账／请求授权／放弃原因），由用户确认。无完成文件不得宣称任务书完成。
- **汇总**：规则 35 生效前项目无独立任务完成文件（`docs/review/` 的评审文档不算）；生效后一律落该目录，同主题同名维护一份，不散落他处。文件夹内 README 建档。
- **与轮次纪律的关系**：每轮仍按 §7 单独出 `tasks_round_N_result.md`（三问）；任务完成文件是任务书维度的收口，不替代轮次结果文件。
