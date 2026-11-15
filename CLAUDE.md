# CLAUDE.md

规则全文在 `程序\AGENTS.md`（硬约束、权威源、轮次类型、自检、执行协议）；与本文件不一致时以它为准。本文件只放 Claude Code 开工所需的最小信息。

## 项目

「漫剧助手」：Windows 桌面应用，Python + Tkinter，零第三方依赖，用于 AI 漫剧制作。13 个制作阶段，顺序以 `pet_bus.STAGES` 为准。源码根目录 `程序\`；解释器 `运行环境\Python\`、启动器 `启动漫剧制作助手.pyw` 都在仓库根目录（工作树里可能缺 `运行环境`，此时用主工作区的解释器）。

必读与阅读范围见 `程序\AGENTS.md` §0；架构与分层见 `程序\architecture.md`，模块地图见 `程序\PROJECT_MAP.md`。

## 命令

PowerShell，先切到 `程序` 目录。测试只按 AGENTS.md §5 选本轮需要的：

```powershell
& '..\运行环境\Python\python.exe' -B scripts\dev.py                  # 开发者统一入口：列出全部子命令
& '..\运行环境\Python\python.exe' -B smoke_test.py                   # 默认冒烟
& '..\运行环境\Python\python.exe' -B run_selftests.py -k pet keyframe  # 按测试文件名关键词筛选
& '..\运行环境\Python\python.exe' -B scripts\dev.py commit -m "R<N>: 说明" [文件...]   # 提交：自动暂存、白名单、等验收锁
```

不用手写 `sleep` 重试循环；文档轮、状态页同步轮不跑 smoke／selftest。

## 数据边界（不属于源码，保持原样）

- 用户项目与生成媒体在用户选定目录；项目阶段配置在 `<项目>\skill_config.json`。
- 全局配置 `程序\配置\`；运行数据 `程序\data\`、`程序\logs\`、`程序\private\`。`程序\episode\` 只是演示目录。
- 升级安装只覆盖程序文件，保留 `config.json`、`projects.json`、`desktop_settings.json`、`private`、`data`、项目与素材。
- `升级备份\` 与 `.bak_*` 是历史证据，回滚靠 Git。

## 工作约定

- 先搜已有入口再新建，只改范围内文件。测试契约有意变更时可同步 mock 和导入路径，断言保持原样并在结果文件注明。
- 含 Tk 的测试经 `工作流任务\gui_hidden.py` 在隐藏桌面运行；新测试放 `程序\tests\`。
- **Token 成本**：新会话开张约 8 万 token，提示缓存约 5 分钟过期。要等超过 5 分钟的结果（全量约 16–21 分钟）时，前台 `sleep 270` 每 4 分半看一次状态续住缓存；预计等 1 小时以上才写交接单并清空会话，交接只在一轮收尾后做。
