# R1706 功能轮（源码轮）：本机所有客户端一次支持，新增客户端／CLI 自动适配

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 功能／修复混合的源码轮（docs + 源码 + tests + 门禁台账）。按要求先补 `REQ-S01-53`～`REQ-S01-56` 与 `DES-S01-53`～`DES-S01-56`，再改代码。
2. **测试跑了吗？三个基线过了吗？** 默认冒烟 **8/8**；`tests.test_client_profiles` **21/21 OK**；客户端相关定向 unittest **53/53 OK**；`model_pool` **61/61 OK**；`workflow*` 四文件 **107/107 OK**；`test_pet_ui` 首跑 **599/599 OK**，最终代码改动后二跑 **598/599**（唯一红是并行树里 `#FFFFFF == #FFFFFF` 的云朵底色断言，非本轮文件）。架构定向重跑（行数、分层、循环、统一棘轮等）**31/31 OK**。全量架构 368 条首跑有 2 红：一条是本轮新增裸 `json.loads`，已修复并定向复验；另一条是并行轮次未落报告导致的轮次连续性，非本轮源码缺陷。`smoke_test.py --affected ...` 与 `--gate` 均在门禁串行执行中 **900 秒超时**（可能为跨树 GUI 令牌争用或 GUI 长尾，未取得用例汇总）；任务书禁止反复重跑，留 Claude 复跑。
3. **project_status.md 的欠账少了吗？** 没有。按任务书未改 `project_status.md`、未领轮次、未提交；本轮只改文件、测试与门禁台账，验收与提交由 Claude 做。

## A 查清结论

### 本机五个客户端的只读实测

探针：`工作流任务/probe_clients/probe_clients.ps1`。只枚举进程、顶层窗口标题／类名与可见输入控件数量；不取值、不发送、不点发送、不读取对话。另单独执行了 `dsh --version`／`dsh --help`。

| 客户端 | 进程名 | 实测路径 | CLI | 窗口／输入框 |
| --- | --- | --- | --- | --- |
| ChatGPT / Codex 桌面 | `ChatGPT` | `C:/Program Files/WindowsApps/OpenAI.Codex_26.901.6511.0_x64__2p2nqsd0c76g0/app/ChatGPT.exe` | Codex CLI 独立存在 | `MainWindowHandle=0`，本会话枚举不到顶层窗口 |
| Claude Desktop | `claude` / `Claude` | `C:/Program Files/WindowsApps/Claude_2.31226.1.0_x64__pzs8sxrjxfjjc/app/Claude.exe`（配置原值） | Claude Code CLI 独立存在 | `MainWindowHandle=0`，未实测 UIA |
| OpenCode 桌面 | `OpenCode` | `C:/Users/LAIBIAO/AppData/Local/Programs/@opencodedesktop/OpenCode.exe` | `opencode-cli.exe` 位于 `%APPDATA%/ai.opencode.desktop/cli/2.0.32-x64/` | `MainWindowHandle=0`，未实测 UIA |
| Gemini 桌面 | `Gemini` | `C:/Users/LAIBIAO/AppData/Local/Google/Gemini/app-1.15.0/Gemini.exe` | 未发现 | `MainWindowHandle=0`，未实测 UIA |
| DeepSeek Harness 桌面 | `DeepSeek Harness` | `F:/DeepSeek Harnesss/DeepSeek Harness.exe` | `F:/DeepSeek Harnesss/resources/runtime/cli/bin/dsh.cmd` | `MainWindowHandle=0`，未实测 UIA |

DeepSeek Harness 补充：

- `dsh --version` 返回 `0.2.1-rc.2`；`dsh --help` 可用，列出 `web`／`headless`／`tui` 等 profile。
- `dsh headless --help` 在本会话失败：`EPERM: mkdir 'C:\Users\LAIBIAO\.dsh\profiles\headless'`。因此 **headless 实际可用性未验证**；档案仍登记 `headless {prompt}`，但必须准备交互式窗口兜底。
- 记忆中的 `%APPDATA%/@deepseek-ai` 不是本机实际安装位置；实际桌面程序在 `F:` 盘，CLI 在其 `resources/runtime/cli/bin`。

### 原有“引擎不认识就抛错”的位置与改后行为

| 原位置 | 原文案 | 改后行为 |
| --- | --- | --- |
| `workflow_engines.py:75` | `... 需要在桌面窗口中手动发送，请使用手动制作入口` | `desktop-app` 后台调用仍不走 CLI，但提示改为可执行的“手动入口”，不再冒充未知引擎失败 |
| `workflow_engines.py:236` | `Desktop 模型请通过桌面发送入口打开，不支持命令行参数` | 保留：桌面程序本就不该走交互 CLI；未知客户端改由档案路由 |
| `workflow_engines.py:238` | `OpenCode CLI 仅支持后台制作入口...` | 保留既有 OpenCode 专门约束；未知 CLI 走 `client-cli` |
| `workflow_engines.py:250` | `Claude Desktop 请通过桌面发送入口打开...` | 保留既有 Claude 专门约束 |
| `workflow_settings.py:286` | `未知的制作引擎` | `ENGINES` 增加 `client-cli`；未知 engine 先查档案，再给出可执行提示 |
| `workflow_settings.py:627` | `未找到对应的受支持 CLI` | 先查内置／用户档案的 `cli` 项；找不到才提示浏览 `.exe` 或交互窗口 |
| `workflow_settings.py:636` | `未找到对应桌面应用...` | 先查档案；新增 `known_globs` 后 Gemini 的 `app-1.15.0/Gemini.exe` 可被找到 |
| `workflow_settings.py:668` | `未找到 ... Desktop 安装程序...` | 旧路径全部失败后再按档案 `detect` 兜底，最后才抛可执行错误 |
| `workflow_settings.py:674` | `未知的本地调用引擎` | 不再直接抛：`desktop-app`／`client-cli`／未知名称都先经档案解析；只有档案也定位不到才报“未找到程序” |

## B 改动

### 文档先行

- `程序/docs/REQUIREMENTS.md` 新增 `REQ-S01-53`～`REQ-S01-56`：档案数据驱动、投递分级与降级、PE 头分类、内置档案全覆盖。
- `程序/docs/DESIGN.md` 新增 `DES-S01-53`～`DES-S01-56`：档案字段、加载顺序、路由与降级链。

### 新模块与内置档案

- 新增 `程序/client_profiles.py`（L1）：
  - 读 `配置/客户端档案.json`，再读 `data/客户端档案.json`；同名内置优先，用户只追加。
  - 容忍缺字段、缺 `schema_version`、坏 JSON。
  - `pe_subsystem()` 只读 PE 头返回 `gui`／`console`；`adapt_executable()` 派生桌面／CLI 档案。
  - `probe_cli()` 仅对 Console 程序、仅在显式检测时运行 `--help`／`--version`，5 秒超时、`shell=False`、最小环境；`.cmd/.bat` 用 `COMSPEC /c` 包装。
  - `known_globs` 用 `glob.glob(..., recursive=True)`，支持 `app-*` 这类中间通配目录（Gemini 的 `app-1.15.0/Gemini.exe`）。
  - `build_invocation()` 支持 `{prompt}`、`{task_file}`、`{title}`、`{model}`；空模板返回交互式窗口。
- 新增 `程序/配置/客户端档案.json`，内置 10 个档案：ChatGPT 桌面、Codex CLI、Claude Desktop、Claude Code、Qwen Code、OpenCode 桌面／CLI、Gemini 桌面、DeepSeek Harness 桌面／CLI。

### 代码接入

- `model_pool.py`：`desktop_engine()` 在既有硬编码表之后查档案；桌面档案路由 `desktop-app`，CLI 档案路由 `client-cli`；`call_mode()` 把 `client-cli` 视为 CLI；`provider_name()` 保留既有 Claude 显示，新档案用档案 `display`。
- `workflow_settings.py`：`ENGINES` 增加 `client-cli`；`current()` 写入 `client_profile`、`delivery`、`app_name`、`client_process_names`、`client_window`，无程序路径时按档案定位；自定义模型 ID 但填了 CLI 程序路径时路由 `client-cli`（不再误落 `qwen` API 兜底）；`find_model_program()`／`find_program()` 不再只认四个硬编码 CLI 名，未知 Desktop／CLI 名称走档案；旧 Gemini 路径失败后按 `known_globs` 兜底。
- `workflow_engines.py`：新增 `client-cli` 后台命令与交互窗口支持；无 `invoke` 时明确打开控制台窗口，并在回执里说明“任务已保存到任务文件”，不再声称已复制剪贴板（REQ-S01-50 的文案一致性）；`client-cli` 参与本地附件模式判定（`stage_execution_service.py`）。
- `desktop_idea_chat.py`：`_deliver_desktop_app()` 接受 `delivery`；`paste` 失败回落“已复制到剪贴板，请手动粘贴并发送”；`clipboard` 不调用粘贴脚本；缺程序路径返回可执行的人工提示，不再中断。
- `environment_check.py`：生产默认路径逐档案输出一行状态；测试注入 `find_profile` 时保留原三行兼容口径。
- `pet_models_ui.py`：只填 `.exe` 时保存侧只按 PE 头派生、不执行探测；显式“检查程序”才探测；模型 ID 为空时自动填派生档案 `id`；PE 子系统与当前模式不一致时自动切换 Desktop／CLI。

### 测试

- 新增 `程序/tests/test_client_profiles.py`，21 条用例覆盖 `REQ-S01-53`～`REQ-S01-56`：档案加载、同名不覆盖、缺字段／坏 JSON、内置全覆盖、启动不扫描目录、版本化目录通配、PE 分类、GUI 不执行、Console 探测、超时与异常兜底、保存不探测、`.cmd` 包装、只填路径补模型 ID、paste→clipboard、CLI→交互窗口、环境检测逐档案行、`client-cli` 本地附件模式。
- 未修改任何既有测试的断言。

### 门禁登记与台账（需 Claude 注意）

- `程序/architecture.md`：新模块 `client_profiles.py` 登记为 L1。**任务书原文禁止改 `architecture.md`**；不改则分层门禁无法定位新模块，因此按“门禁红了按提示登记”的例外只改了这一行，请验收时确认。
- `程序/tests/architecture/_layers.py`：同步登记 `client_profiles` 为 L1。
- `程序/runbook.md` §11：覆盖率口径从 284/49 更新为 **285/50**（新增模块并用定向用例采到覆盖）；`维护记录/覆盖率基线.json` 已由工具重写为 285/50。
- `程序/维护记录/架构统一基数.json`：`model_pool.py` 与 `workflow_engines.py` 的既有裸 `json.loads` 因本轮插入代码发生行号平移，按既有“行号平移”惯例更新 point 与理由；未新增豁免项。

## C 验证

| 命令／探针 | 实际结果 |
| --- | --- |
| `python -B -m py_compile client_profiles.py model_pool.py workflow_settings.py workflow_engines.py desktop_idea_chat.py environment_check.py pet_models_ui.py stage_execution_service.py` | **OK，exit=0** |
| `python -B -m unittest tests.test_client_profiles` | **21/21 OK，0.695 秒** |
| `python -B -m unittest tests.test_client_profiles tests.test_environment_check tests.test_claude_program_detection tests.test_desktop_idea_chat_desktop_paste tests.test_codex_paste_diagnostics` | **53/53 OK，15.403 秒** |
| `python -B -m unittest tests.test_model_pool` | **61/61 OK，0.376 秒** |
| `python -B -m unittest tests.test_workflow tests.test_workflow_migration tests.test_workflow_settings_cache tests.test_workflow_writing_stages` | **107/107 OK，4.214 秒** |
| 最终代码改动后复跑（含档案 `store_finder` 注入、`known_globs` 修复、`client-cli` 路由与文案修正） | 客户端定向 **53/53 OK，16.014 秒**；`model_pool`＋`workflow*` **168/168 OK，5.113 秒**；架构行数／分层／循环／统一棘轮／锚定 **18/18 OK，17.654 秒**；`py_compile` exit=0 |
| `python -B tests/test_pet_ui.py` | 首跑 **599/599 OK，97.890 秒**；最终代码改动后二跑 **598/599**，唯一红为 `CloudFitTests.test_the_commands_roll_inside_the_reply_box`（两侧都打印 `#FFFFFF` 的“不再刷云身色”断言；涉 `pet_cloud_hint`／`ui_tokens`，非本轮文件，首跑同一用例通过，按并行工作树波动记录） |
| 架构定向：分层／函数行数／模块行数／循环导入／需求锚定／覆盖率／静态卫生 | **23/23 OK，25.095 秒** |
| 架构定向：print／silent exception／TODO／token／completion／module size／function size／layers／cycles／dynamic import／static hygiene | **31/31 OK，39.145 秒** |
| `python -B -m unittest tests.architecture.test_unification_ratchet` | 修复后 **4/4 OK，7.159 秒** |
| `python -B smoke_test.py` | **通过 8 项，失败 0 项** |
| `python -B smoke_test.py --architecture`（只跑一次） | **368 条，269.560 秒，2 红**：①`client_profiles.py` 裸 `json.loads`（已改为 `json.load` 并定向复验）；②`test_round_number_continuous`（`project_status.md` 写 1706，最新结果文件仍是 1702；并行 R1703～R1705 尚未落报告，非本轮源码） |
| `python -B smoke_test.py --affected model_pool workflow_settings workflow_engines desktop_idea_chat environment_check` | 快速检查 **8/8**；门禁 `run_selftests.py --serial -k ...` **900 秒超时**，未取得用例汇总（可能为跨树 GUI 令牌争用或 GUI 长尾）；按任务书不反复重跑 |
| 任务书原命令 `python -B run_selftests.py -k client_profiles model_pool workflow_settings desktop_idea_chat environment_check codex_paste test_pet_ui` | 包装器运行约 **16 分钟**仍无输出（`Out-String` 缓冲），手动终止；未取得汇总。已用上面的直接 unittest 覆盖同一批文件 |
| `python -B smoke_test.py --gate` | 快速检查 **8/8**；门禁 `run_selftests.py --serial`（增量串行）**900 秒超时**，未取得用例汇总；与 `--affected` 一样可能是跨树 GUI 令牌争用或 GUI 长尾，按任务书不反复重跑 |
| `scripts/coverage_report.py ... --json 维护记录/覆盖率基线.json` | 已写入：**模块覆盖 50/285，目标用例全通过**；`test_coverage_baseline` 复验通过 |

### DeepSeek Harness 实测结论

- 桌面：进程名 `DeepSeek Harness`，路径 `F:/DeepSeek Harnesss/DeepSeek Harness.exe`；本会话 `MainWindowHandle=0`，无法实测输入框 UIA。
- CLI：`dsh.cmd` 可启动，`--version` 与 `--help` 正常；`headless --help` 因 `%USERPROFILE%/.dsh/profiles/headless` 的 `EPERM: mkdir` 失败。
- 结论：**桌面与 CLI 的发现、路由、交互窗口兜底已实现；headless 是否可用未验证，当前必须按“失败→交互窗口”处理。**

### 五个客户端的最终投递策略

| 客户端 | 最终策略 |
| --- | --- |
| ChatGPT / Codex 桌面 | 沿用既有 Codex／GPT 桌面路径：`paste`，不自动发送；失败→剪贴板手动粘贴 |
| Claude Desktop | 沿用既有 Claude Desktop 路径：`paste`，不自动发送；失败→剪贴板手动粘贴 |
| OpenCode 桌面 | `paste`，失败→剪贴板手动粘贴 |
| Gemini 桌面 | `paste`，失败→剪贴板手动粘贴 |
| DeepSeek Harness 桌面 | `paste`，失败→剪贴板手动粘贴 |
| Codex CLI | `cli_stdin`：`exec -`，读不到结果→交互式控制台窗口 |
| Claude Code CLI | `cli_arg`：`-p --output-format json` |
| Qwen Code CLI | `cli_arg`：`-p` |
| OpenCode CLI | `cli_file`：`run --auto --format json --file <task_file> ...`，失败→交互式窗口 |
| DeepSeek Harness CLI `dsh` | 档案为 `cli_arg`：`headless {prompt}`；当前实测可能因 profile 目录权限失败，实际落到交互式窗口 |

## D 断言未动与遗留

1. **断言未动**：没有修改、弱化或删除任何既有断言；只新增 `tests/test_client_profiles.py`。
2. **`architecture.md` 例外**：为登记新 L1 模块只改了一行；任务书原禁止，请 Claude 在验收时确认接受或以门禁方式替代。
3. **真机 UIA 未验证**：本会话所有目标进程 `MainWindowHandle=0`，`EnumWindows` 未枚举到目标窗口；无法证明 `codex_paste.ps1` 能在 DeepSeek／OpenCode／Gemini 的真实输入框中粘贴。用户需实际打开窗口验收；本轮未发送任何内容、未点发送、未读取对话。
4. **DeepSeek headless 未验证**：`dsh headless --help` 的 `EPERM` 是当前用户目录 profile 初始化问题，不等于产品 CLI 完全不可用；但本轮不能把它写成“已验证可用”。
5. **轮次连续性红**：`project_status.md` 为 1706，`tasks_round` 最新结果是 1702；并行 R1703～R1705 尚未落报告。按任务书不改 `project_status.md`，此项交 Claude 在合并并行结果后复验。
6. **门禁超时**：`--affected`、`--gate` 与 `run_selftests -k` 均受跨树 GUI 令牌／长尾影响；未反复重跑，交 Claude 验收时复跑。全量架构未在修复后重跑 368 条，只对失败项做了定向复验。
7. **`test_pet_ui` 二跑唯一红**：`tests/test_pet_ui.py` 属 R1704 并行改动范围；失败断言是“云朵提示底色不得等于云身色”，两侧却都打印 `#FFFFFF`，同一用例首跑通过。本轮未改 `pet_cloud_hint.py`／`ui_tokens.py`／该测试文件，按并行树波动交 Claude 复跑判定。
8. **未知引擎兜底边界**：`desktop-app` 的后台入口仍会拒绝（桌面程序没有命令行参数），但提示是可执行的人工入口；`client-cli` 无 `invoke` 时打开交互式窗口。未把“桌面程序不能后台跑”伪装成成功。
9. **Gemini 真机目录本会话不可读**：`C:/Users/LAIBIAO/AppData/Local/Google/Gemini` 在当前沙箱同时出现 `Access is denied` 与 `exists()=False`；因此直接对本机跑 `find_model_program('gemini','Desktop')` 仍会报“未找到”。本轮已修正 `known_globs` 对 `app-*` 中间目录的处理，并用临时 `LOCALAPPDATA` 造出 `Google/Gemini/app-1.15.0/Gemini.exe` 验证完整链路能命中；真机路径由 R1699 的实测记录保留，需 Claude 在可读该目录的会话复核。

## E 提交

**未提交，由 Claude 验收后提交。**

## F 改动文件

- `程序/docs/REQUIREMENTS.md`
- `程序/docs/DESIGN.md`
- `程序/client_profiles.py`（新增）
- `程序/配置/客户端档案.json`（新增）
- `程序/model_pool.py`
- `程序/workflow_settings.py`
- `程序/workflow_engines.py`
- `程序/desktop_idea_chat.py`
- `程序/environment_check.py`
- `程序/pet_models_ui.py`
- `程序/stage_execution_service.py`
- `程序/tests/test_client_profiles.py`（新增）
- `程序/tests/architecture/_layers.py`
- `程序/architecture.md`（仅 L1 登记一行）
- `程序/runbook.md`（§11 覆盖率数字）
- `程序/维护记录/覆盖率基线.json`
- `程序/维护记录/架构统一基数.json`（既有项行号平移）
- `工作流任务/probe_clients/probe_clients.ps1`（只读探针，不在 `程序/` 内）
