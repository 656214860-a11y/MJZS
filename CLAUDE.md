# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

「漫剧助手」是 Windows 桌面应用（Python + Tkinter，**零第三方依赖**），用于 AI 漫剧制作：12 个制作阶段（剧本准备 → 剧本结构 → 初步分镜 → 资产管理 → 连贯性清单 → 分镜定稿 → 首帧管理 → 白模预演 → 视频生成 → 配音与字幕 → 后期剪辑 → 质检与交付），通过 SKILL 文件驱动 Codex / Claude Code / Qwen / API 等引擎执行工作流。

- 源码根目录：`程序\`（约 200 个模块，单文件平铺 + `agent/`、`skills/`、`tests/` 等子目录）。
- 本仓库使用 Git 管理源码与文档；`升级备份\` 与 `.bak_*` 保留为历史证据，今后不再新增 `.bak_*`。

## 权威文档（开工前必读）

读取顺序、各文档阅读范围及完成条件唯一以 `程序\AGENTS.md` §0 为准；本入口不另设“只读头部”例外。文件索引：

1. `程序\AGENTS.md` — 硬约束、轮次协议、自检规则、权威源表（治理规则唯一权威）。
2. `程序\project_status.md` — 当前轮次、待办、验证基线与历史事实；阅读范围见上述 §0。
3. `程序\architecture.md` — 目录树、L0–L5 分层表、模块职责、已验证的发布边界。
4. `程序\PROJECT_MAP.md` — 核心模块地图、12 阶段目录、SG-01~05 门禁关系、数据边界。

## 常用命令

以下为 PowerShell 示例，先显式切换到程序目录；启动器位于仓库根目录，解释器位于根目录的 `运行环境\Python\`，不依赖 PATH 或 `.pyw` 文件关联。仅按 AGENTS.md §5 选择本轮需要的测试，不整块执行：

```powershell
Set-Location -LiteralPath 'D:\漫剧制作助手\程序'

# 启动应用（无控制台）
& '..\运行环境\Python\pythonw.exe' -I '..\启动漫剧制作助手.pyw'
# 也可双击仓库根目录的 启动助手.cmd；不以双击 .pyw 的系统关联代替随附解释器。

& '..\运行环境\Python\python.exe' -B smoke_test.py  # 默认冒烟；触发条件见 AGENTS.md §5
& '..\运行环境\Python\python.exe' -B smoke_test.py --affected idea_chat workflow
& '..\运行环境\Python\python.exe' -B smoke_test.py --gate  # 增量门禁
& '..\运行环境\Python\python.exe' -B smoke_test.py --architecture  # 全部架构门禁

& '..\运行环境\Python\python.exe' -B run_selftests.py  # 增量自检，可跳过未改测试
& '..\运行环境\Python\python.exe' -B run_selftests.py --all --safe  # 安全全量，触发／凭据复用见 AGENTS.md §5
& '..\运行环境\Python\python.exe' -B run_selftests.py --all --safe --force  # 强制复核，不复用绿凭据
& '..\运行环境\Python\python.exe' -B run_selftests.py -k pet keyframe  # 按测试文件名关键词筛选
& '..\运行环境\Python\python.exe' -B run_selftests.py --layer architecture --all
& '..\运行环境\Python\python.exe' -B run_selftests.py --list  # 仅列出测试文件
```

耗时以对应报告的受测版本、范围和环境为准；历史测量不代表当前执行时长，也不是性能保证。路径可用静态存在性检查验证，无需为文档核验启动真实项目。

## 架构要点

### 分层（architecture.md 第 3 节，架构门禁强制）

`L5 入口(app) → L4 UI(desktop/pet_ui/skill_panel) → L3 编排(stage_*/skill_*/workflow_*/各 controller) → L2 业务(各 *_service、asset*/storyboard*/keyframe*/video*) → L1 基础设施(model_pool、file_cache、ui_tokens) → L0 契约(pet_bus、*_contract、stage_layout)`

- **反向 import 一律禁止**；由 `tests\architecture\` 下 100+ 个门禁自动检查。
- 大页面持续拆分中：`desktop.py`（39 万+ 字节）保留 Tk 控件与事件绑定，无 Tk 状态/决策下沉为 `*_controller.py` / `*_service.py`（如 `AssetBatchController`、`StoryboardPageController`）。新拆分遵循"控制器不持有 Tk 控件、不写项目数据，UI 只注入回调"模式。

### 唯一权威源（禁止绕过、禁止另立第二入口）

| 事项 | 权威 |
| --- | --- |
| 阶段顺序/事件 | `pet_bus.STAGES` / `STAGE_NAMES` / 事件表 |
| 播报前缀 | `broadcaster`（仅 `【阶段 X/12】`、`【完成】`、`【门禁】` 等固定前缀，无前缀消息被拒绝） |
| 并行与重试 | `stage_parallel.CONFIG` |
| 文件路径 | `stage_layout` / `storyboard_paths` / `script_contract` / `asset_contract`；新写入走 `stage_path_service.write_dir()`，旧目录（`00_script`—`10_qc_delivery`）只读兼容 |
| SKILL | `skills/**/*.skill.md` + `skill_registry.py`（递归扫描，按 `01`—`12` 阶段目录归类） |
| 阶段启动 | `stage_handler_registry.start()`（手动/自动/三虎都走这里） |
| 动态导入 | L4 走 `ui_plugin_registry.module()`，L3 走 `stage_handler_registry`；登记表外名称拒绝加载 |
| 删除 | 用户可见删除一律 `storage_maintenance.recycle_paths()`（回收站可恢复） |
| 阶段完成 | `stage_completion_service` 核验产物，不接受模型文字/UI 提示作证据 |
| 密钥 | `model_secrets` + `pet_llm.credential`；`.env` / `private/密钥/*.dpapi`；禁止写入日志或任务 JSON |
| UI 设计值 | `ui_tokens.py`（`design_tokens.md` 的代码化），按钮/卡片只走 `ui_widgets`；禁止魔法数字与内联 hex |

### 门禁链（PROJECT_MAP.md）

资产 manifest+锚点 —SG-01→ 连贯性台账 —SG-02→ 分镜定稿 —SG-03→ 首帧 —SG-04→ 白模预演 —SG-05→ 视频生成。门禁只拦"已开始但不完整"，空项目放行。五类剧本 manifest：`character_manifest`、`scene_manifest`、`prop_manifest`、`scene_breakdown`、`emotion_curve`。

### 三虎（pet_*）

桌面宠物 Agent：进度播报、自动化等级（只提醒/半自动/全自动）、检查点、暂停恢复、跨重启续跑台账。`pet_bus` 定义事件，`pet_llm` 管模型调用与密钥，`pet_ui`/`pet_cloud` 是界面。

## 数据边界（不属于源码树，禁止改动）

- 用户项目/生成媒体：用户选定目录（默认 Documents\漫剧下载）；项目阶段配置在 `<项目>/skill_config.json`。
- 全局配置：`程序\配置\`；程序运行数据：`程序\data\`、`程序\logs\`、`程序\private\`。
- `程序\episode\` 只是演示目录，不是用户项目 `<项目>`，勿混淆。
- 升级安装只覆盖程序文件，保留 `config.json`、`projects.json`、`desktop_settings.json`、`private`、`data`、项目与素材。

## 开发流程约定（源自 AGENTS.md，本项目实际执行）

- **轮次制**：每轮开工先声明轮次类型（功能轮/修复轮/结构治理轮/契约轮/只读诊断轮/测试搬家轮/性能轮/可靠性轮/兼容轮/验证基线轮），不同类型协议不同。
- **每轮收尾**：认领与轮次一致性按 `程序\AGENTS.md` §2.5，提交按 §2.6，归档按 §7；只读诊断的报告／元数据写入边界按 §3.5，测试按 §5。未运行和历史凭据须如实区分，不写为本轮通过；普通只读问答不自动立轮。
- **禁止事项**：不改用户项目数据；不重复创建已有模块（先搜已有入口）；不重构范围外文件；不改测试迁就实现（契约有意变更时可同步改 mock/导入路径，但禁止弱化断言，且须在结果文件注明"断言未动"）；新测试一律放 `程序\tests\`；启动路径上禁止递归扫描目录（须缓存/后台加载/懒加载）；连续 5 个功能轮后必须插 1 个整理轮。
