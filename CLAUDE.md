# CLAUDE.md

入口导航。规则以 `程序\AGENTS.md` 为准；与本文件冲突时以 AGENTS.md 为准。

## 项目

「漫剧助手」：Windows 桌面应用，Python + Tkinter，**零第三方依赖**，用于 AI 漫剧制作。13 个制作阶段（顺序以 `pet_bus.STAGES` 为准）：剧本准备 → 剧本结构 → 初步分镜 → 分镜预演 → 资产管理 → 连贯性清单 → 分镜定稿 → 首帧管理 → 白模预演 → 视频生成 → 配音与字幕 → 后期剪辑 → 质检与交付。通过 SKILL 文件驱动 Codex／Claude Code／Qwen／API 等引擎。

- 源码根目录 `程序\`：约 280 个顶层模块，另有 `agent/`、`skills/`、`tests/` 等子目录。
- 解释器和启动器都在仓库根目录：`运行环境\Python\`、`启动漫剧制作助手.pyw`；不依赖 PATH 或 `.pyw` 文件关联。
- `升级备份\` 与 `.bak_*` 是历史证据，不再新增 `.bak_*`，回滚靠 Git。

## 必读（顺序、范围、完成条件唯一以 AGENTS.md §0 为准）

1. `程序\AGENTS.md` — 硬约束、权威源表（§2.2）、轮次类型（§3）、自检规则（§5）
2. `程序\project_status.md` — 当前轮次、待办、验证基线
3. `程序\architecture.md` — 目录树、L0–L5 分层表、模块职责
4. `程序\PROJECT_MAP.md` — 核心模块地图、阶段目录、门禁关系、数据边界

## 命令

PowerShell，先切到程序目录。测试只按 AGENTS.md §5 选本轮需要的，不整块执行：

```powershell
Set-Location -LiteralPath 'D:\漫剧制作助手\程序'
& '..\运行环境\Python\pythonw.exe' -I '..\启动漫剧制作助手.pyw'   # 启动（无控制台）；也可双击根目录快捷方式「漫剧助手」；备用脚本在 开发者工具\
& '..\运行环境\Python\python.exe' -B scripts\dev.py                  # 开发者统一入口：列出全部子命令
& '..\运行环境\Python\python.exe' -B smoke_test.py                   # 默认冒烟
& '..\运行环境\Python\python.exe' -B run_selftests.py -k pet keyframe  # 按测试文件名关键词筛选
```

`--affected`、`--gate`、`--architecture`、`--all --safe` 等选项及触发条件见 AGENTS.md §5。

提交用 `& '..\运行环境\Python\python.exe' -B scripts\dev.py commit -m "R<N>: 说明" [文件...]`：自动暂存、生成白名单，并在进程内等后台全量验收锁（失效锁自动回收），不要再手写 `sleep 20` 重试循环（实测最长卡 41 分钟）。文档轮、状态页同步轮不跑 smoke／selftest。

## 架构

- 分层：`L5 入口(app) → L4 UI(desktop/pet_ui/skill_panel) → L3 编排(stage_*/skill_*/workflow_*/各 controller) → L2 业务(*_service 等) → L1 基础设施(model_pool、file_cache) → L0 契约(pet_bus、*_contract、stage_layout)`。反向 import 一律禁止，由 `tests\architecture\` 门禁自动检查；分层表以 architecture.md 第 3 节为准。
- 大页面拆分模式：`desktop.py` 只留 Tk 控件与事件绑定；无 Tk 的状态与决策放 `*_controller.py`／`*_service.py`，控制器不持有 Tk 控件、不写项目数据，UI 只注入回调。
- 唯一权威源（完整表见 AGENTS.md §2.2；不绕过、不另立第二入口），最常碰的几条：
  - 路径：`stage_layout`／`stage_path_service`；新写入走 `write_dir()`，旧编号目录只读兼容
  - 阶段启动：`stage_handler_registry.start()`（手动、自动、三虎都走它）
  - 阶段完成：`stage_completion_service` 核验产物，不接受模型文字或 UI 提示作证据
  - 删除：用户可见删除一律 `storage_maintenance.recycle_paths()`
  - 密钥：`model_secrets` + `pet_llm.credential`，不写入日志或任务 JSON
  - UI：`ui_tokens` + `ui_widgets`；禁止魔法数字和内联 hex
- 门禁（定义在 `stage_parallel.GATES`）：SG-A（初步分镜→分镜预演）、SG-B（分镜预演→资产管理）要求上游成果已就绪；SG-01～05（资产→连贯性→定稿→首帧→白模预演→视频）只拦“已开始但不完整”，空项目放行。
- 三虎（`pet_*`）：桌面宠物 Agent，管进度播报、自动化等级、检查点、暂停恢复、跨重启续跑台账。

## 数据边界（不属于源码，禁止改动）

- 用户项目与生成媒体：用户选定目录（默认 Documents\漫剧下载）；项目阶段配置在 `<项目>\skill_config.json`。
- 全局配置 `程序\配置\`；运行数据 `程序\data\`、`程序\logs\`、`程序\private\`。
- `程序\episode\` 只是演示目录，不是用户项目。
- 升级安装只覆盖程序文件，保留 `config.json`、`projects.json`、`desktop_settings.json`、`private`、`data`、项目与素材。

## 工作约定

- **执行与提交方**：所有任务由当前执行 agent 自己完成（改代码、跑测试、领号、提交），不再派发给其他模型；同一时刻由哪个运行时（如 Claude Code、DeepSeek Assistant 等）承载，就以该运行时为执行与提交方。含 Tk 的测试一律经 `工作流任务\gui_hidden.py` 在隐藏桌面运行。
- 每轮开工先声明轮次类型（AGENTS.md §3），收尾按 §2.6、§7；未运行和历史凭据如实区分，不写成本轮通过。
- 先搜已有入口再新建，不重构范围外文件。
- 不改测试迁就实现：契约有意变更时可同步 mock 和导入路径，禁止弱化断言，并在结果文件注明“断言未动”。
- 新测试放 `程序\tests\`。
- 启动路径上禁止递归扫描目录，须缓存、后台加载或懒加载。
- **Token 成本**：新会话开张约 8 万 token，提示缓存约 5 分钟过期，过期后整份上下文按 1.25 倍重写。要等超过 5 分钟的结果（如全量约 16–21 分钟）时，用前台 `sleep 270` 每 4 分半看一次状态续住缓存，不要空等；预计等 1 小时以上才写交接单并清空会话。交接只在一轮收尾（提交、合入）后做，不在中途。
