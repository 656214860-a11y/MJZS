# R1446 名称分类与兼容性审计

本附件对应任务 1。显示名唯一来源为 `程序/app_metadata.py` 的 `APP_NAME = "漫剧助手"`；版本保持 V0.7。

扫描使用 `git -c core.quotepath=false grep -n -I`（本机无 rg），全仓跟踪文本中旧名命中 107 行。按任务书排除 `升级备份/`、`.wt/`、`tasks_round/`、`.bak_*`、`维护记录/`；用户项目登记表及 private 数据不作为源码/显示名改写对象。下表行号是改动前定位，共逐行分类 107 条，其中混合行 `.agent-handoff/workspace.md:3` 同时含 A 产品说明和 B 安装目录。

分类计数：A 36 行，B 52 行，C 19 行。

## A：当前产品名称与说明

| 改动前位置 | 处理 |
| --- | --- |
| `.agent-handoff/workspace.md:3` | 产品说明同步；同一行仓库路径 D:/漫剧制作助手 属 B，保留。 |
| `CLAUDE.md:7` | 当前文档产品称谓同步为“漫剧助手”；代码路径不替换。 |
| `GLOSSARY.md:1` | 当前文档产品称谓同步为“漫剧助手”；代码路径不替换。 |
| `使用说明.md:1` | 当前文档产品称谓同步为“漫剧助手”；代码路径不替换。 |
| `使用说明.txt:1` | 当前文档产品称谓同步为“漫剧助手”；代码路径不替换。 |
| `使用说明.txt:5` | 当前文档产品称谓同步为“漫剧助手”；代码路径不替换。 |
| `使用说明.txt:7` | 当前文档产品称谓同步为“漫剧助手”；代码路径不替换。 |
| `启动漫剧制作助手.pyw:95` | 运行时显示/身份文案改取 app_metadata.APP_NAME；不更改既有标识。 |
| `程序/AGENTS.md:26` | 当前文档产品称谓同步为“漫剧助手”；代码路径不替换。 |
| `程序/PROJECT_MAP.md:1` | 当前文档产品称谓同步为“漫剧助手”；代码路径不替换。 |
| `程序/README.md:1` | 当前文档产品称谓同步为“漫剧助手”；代码路径不替换。 |
| `程序/README.md:1134` | 当前文档产品称谓同步为“漫剧助手”；代码路径不替换。 |
| `程序/README.md:2059` | 当前文档产品称谓同步为“漫剧助手”；代码路径不替换。 |
| `程序/README.md:2088` | 当前文档产品称谓同步为“漫剧助手”；代码路径不替换。 |
| `程序/README.md:2169` | 当前文档产品称谓同步为“漫剧助手”；代码路径不替换。 |
| `程序/app_shortcut.py:24` | 运行时显示/身份文案改取 app_metadata.APP_NAME；不更改既有标识。 |
| `程序/app_shortcut.py:228` | 运行时显示/身份文案改取 app_metadata.APP_NAME；不更改既有标识。 |
| `程序/architecture.md:1` | 当前文档产品称谓同步为“漫剧助手”；代码路径不替换。 |
| `程序/design_tokens.md:3` | 当前文档产品称谓同步为“漫剧助手”；代码路径不替换。 |
| `程序/desktop.py:292` | 运行时显示/身份文案改取 app_metadata.APP_NAME；不更改既有标识。 |
| `程序/desktop.py:310` | 运行时显示/身份文案改取 app_metadata.APP_NAME；不更改既有标识。 |
| `程序/desktop.py:3782` | 运行时显示/身份文案改取 app_metadata.APP_NAME；不更改既有标识。 |
| `程序/desktop.py:4137` | 运行时显示/身份文案改取 app_metadata.APP_NAME；不更改既有标识。 |
| `程序/pet_llm.py:62` | 运行时显示/身份文案改取 app_metadata.APP_NAME；不更改既有标识。 |
| `程序/pet_llm.py:73` | 运行时显示/身份文案改取 app_metadata.APP_NAME；不更改既有标识。 |
| `程序/pet_settings_ui.py:42` | 运行时显示/身份文案改取 app_metadata.APP_NAME；不更改既有标识。 |
| `程序/pet_ui.py:2236` | 运行时显示/身份文案改取 app_metadata.APP_NAME；不更改既有标识。 |
| `程序/pet_ui.py:3895` | 源码说明中的产品称谓同步；不改变执行逻辑。 |
| `程序/scripts/clean_dev.py:238` | 运行时显示/身份文案改取 app_metadata.APP_NAME；不更改既有标识。 |
| `程序/tests/__init__.py:1` | 当前文档产品称谓同步为“漫剧助手”；代码路径不替换。 |
| `程序/tests/test_app_shortcut.py:187` | 测试快捷方式名称夹具改取 app_shortcut.NAME；文案同步，行为断言未动。 |
| `程序/tests/test_pet_settings.py:781` | 显示名期望改取 desktop.APP_NAME；断言文案同步、逻辑未动。 |
| `程序/tests/test_pet_settings.py:785` | 显示名期望改取 desktop.APP_NAME；断言文案同步、逻辑未动。 |
| `程序/ui_widgets.py:1127` | 运行时显示/身份文案改取 app_metadata.APP_NAME；不更改既有标识。 |
| `程序/说明/维护约定.md:1` | 当前文档产品称谓同步为“漫剧助手”；代码路径不替换。 |
| `程序/说明/维护约定.md:5` | 当前文档产品称谓同步为“漫剧助手”；代码路径不替换。 |

## B：持久标识与真实路径

| 改动前位置 | 处理 |
| --- | --- |
| `.gitignore:71` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `CLAUDE.md:26` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `CLAUDE.md:29` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `reorganize_install.py:7` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `使用说明.md:7` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `启动助手.cmd:3` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/AGENTS.md:4` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/AGENTS.md:5` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/AGENTS.md:28` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/AGENTS.md:354` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/AGENTS.md:360` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/README.md:640` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/app_shortcut.py:4` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/app_shortcut.py:5` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/app_shortcut.py:25` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/app_shortcut.py:28` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/app_shortcut.py:30` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/app_shortcut.py:98` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/app_shortcut.py:103` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/app_shortcut.py:113` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/asset_thumbs.py:19` | 用户数据/缓存路径（或其说明）；兼容旧数据目录，保留。 |
| `程序/asset_thumbs.py:56` | 用户数据/缓存路径（或其说明）；兼容旧数据目录，保留。 |
| `程序/cloud_assets.py:16` | 用户数据/缓存路径（或其说明）；兼容旧数据目录，保留。 |
| `程序/distribution_manifest.md:7` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/distribution_manifest.md:13` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/distribution_manifest.md:19` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/pet_ui.py:197` | Windows Run 注册表持久标识；保留，避免旧开机启动项失联。 |
| `程序/pet_ui.py:764` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/qwen_setup.py:15` | 用户数据/缓存路径（或其说明）；兼容旧数据目录，保留。 |
| `程序/run_selftests.py:495` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/scripts/clean_dev.py:6` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/scripts/maintain_logs.py:4` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/seedream_api.py:40` | 用户数据/缓存路径（或其说明）；兼容旧数据目录，保留。 |
| `程序/skill_panel.py:1778` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/tests/test_app_shortcut.py:24` | 既有路径/文件名兼容性夹具或断言；保持旧数据/启动器标识。 |
| `程序/tests/test_distribution_build.py:20` | 既有路径/文件名兼容性夹具或断言；保持旧数据/启动器标识。 |
| `程序/tests/test_distribution_build.py:27` | 既有路径/文件名兼容性夹具或断言；保持旧数据/启动器标识。 |
| `程序/tests/test_distribution_build.py:71` | 既有路径/文件名兼容性夹具或断言；保持旧数据/启动器标识。 |
| `程序/tests/test_manual_plan.py:266` | 既有路径/文件名兼容性夹具或断言；保持旧数据/启动器标识。 |
| `程序/tests/test_manual_plan.py:457` | 既有路径/文件名兼容性夹具或断言；保持旧数据/启动器标识。 |
| `程序/tests/test_pet_ui.py:615` | 既有路径/文件名兼容性夹具或断言；保持旧数据/启动器标识。 |
| `程序/tests/test_pet_ui.py:625` | 既有路径/文件名兼容性夹具或断言；保持旧数据/启动器标识。 |
| `程序/tests/test_pet_ui.py:667` | 既有路径/文件名兼容性夹具或断言；保持旧数据/启动器标识。 |
| `程序/tests/test_selftests.py:350` | 既有路径/文件名兼容性夹具或断言；保持旧数据/启动器标识。 |
| `程序/tests/test_stdlib_closure.py:8` | 既有路径/文件名兼容性夹具或断言；保持旧数据/启动器标识。 |
| `程序/tests/test_white_model_workspace.py:48` | 既有路径/文件名兼容性夹具或断言；保持旧数据/启动器标识。 |
| `程序/tests/test_white_model_workspace.py:207` | 既有路径/文件名兼容性夹具或断言；保持旧数据/启动器标识。 |
| `程序/tts_api.py:23` | 用户数据/缓存路径（或其说明）；兼容旧数据目录，保留。 |
| `程序/white_model_service.py:286` | 用户数据/缓存路径（或其说明）；兼容旧数据目录，保留。 |
| `程序/说明/版本文件校验.json:2` | 既有分发校验清单的真实启动器文件名；不改路径或伪造哈希。 |
| `程序/说明/维护约定.md:7` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |
| `程序/说明/维护约定.md:9` | 安装目录、启动器/图标文件名或对应维护/分发规则；保留真实标识。 |

## C：历史证据

| 改动前位置 | 处理 |
| --- | --- |
| `.agent-handoff/history/r1418-handoff-before/project_status_header.before.md:1` | 已有历史/审计/状态记录，保留原始证据；不倒改历史。 |
| `.agent-handoff/work-log.md:80` | 已有历史/审计/状态记录，保留原始证据；不倒改历史。 |
| `outputs/code-rot-cleaner/R1063/CODE-ROT-REPORT.md:22` | 已有历史/审计/状态记录，保留原始证据；不倒改历史。 |
| `outputs/code-rot-cleaner/R1063/CODE-ROT-REPORT.md:23` | 已有历史/审计/状态记录，保留原始证据；不倒改历史。 |
| `outputs/code-rot-cleaner/R1063/CODE-ROT-REPORT.md:24` | 已有历史/审计/状态记录，保留原始证据；不倒改历史。 |
| `outputs/code-rot-cleaner/R1063/CODE-ROT-REPORT.md:29` | 已有历史/审计/状态记录，保留原始证据；不倒改历史。 |
| `outputs/code-rot-cleaner/R1064/CODE-ROT-REPORT.md:5` | 已有历史/审计/状态记录，保留原始证据；不倒改历史。 |
| `outputs/code-rot-cleaner/R1064/CODE-ROT-REPORT.md:21` | 已有历史/审计/状态记录，保留原始证据；不倒改历史。 |
| `outputs/code-rot-cleaner/R1064/proof.json:4` | 已有历史/审计/状态记录，保留原始证据；不倒改历史。 |
| `outputs/code-rot-cleaner/R1064/proof.json:9` | 已有历史/审计/状态记录，保留原始证据；不倒改历史。 |
| `outputs/code-rot-cleaner/R1064/proof.json:10` | 已有历史/审计/状态记录，保留原始证据；不倒改历史。 |
| `outputs/code-rot-cleaner/R1064/proof.json:11` | 已有历史/审计/状态记录，保留原始证据；不倒改历史。 |
| `outputs/code-rot-cleaner/R1068/CODE-ROT-REPORT.md:5` | 已有历史/审计/状态记录，保留原始证据；不倒改历史。 |
| `outputs/code-rot-cleaner/R1068/proof.json:4` | 已有历史/审计/状态记录，保留原始证据；不倒改历史。 |
| `程序/project_status.md:50` | 已有历史/审计/状态记录，保留原始证据；不倒改历史。 |
| `程序/project_status.md:636` | 已有历史/审计/状态记录，保留原始证据；不倒改历史。 |
| `程序/project_status.md:795` | 已有历史/审计/状态记录，保留原始证据；不倒改历史。 |
| `程序/project_status.md:1069` | 已有历史/审计/状态记录，保留原始证据；不倒改历史。 |
| `程序/project_status.md:1076` | 已有历史/审计/状态记录，保留原始证据；不倒改历史。 |

## 运行时单一来源与验证

- `desktop.py`：主窗口标题、侧栏、切换项目后的标题、项目选择对话框；`ui_widgets.py`：启动画面。
- `pet_settings_ui.APP_TITLE` 与 `app_shortcut.NAME` 保留原接口，但均直接取 `APP_NAME`；快捷方式描述同源。
- `pet_ui.py` 退出确认、启动器错误窗口、`clean_dev.py` 帮助描述、`pet_llm.py` 两类模型身份前缀同源。
- `tests/test_app_metadata.py` 新增 5 项：显示常量/模型身份、八个显示生产文件的同源引用、这些文件只保留已批准 B 类旧字面量、六类旧数据路径与启动器/图标/注册表标识、七份当前文档标题。
- 已实际运行：随附 Python `-B -m unittest tests.test_app_metadata -v`，5 项通过，1.094 秒；未访问 API，未读写用户配置。
- 旧名称测试覆盖关键词（现有测试统一由主执行者运行并记入主结果）：`test_app_shortcut`、`test_distribution_build`、`test_manual_plan`、`test_pet_settings`、`test_pet_ui`、`test_selftests`、`test_stdlib_closure`、`test_white_model_workspace`。新增测试自身保留旧名作兼容性基准，关键词 `test_app_metadata`。另需 `test_pet_llm`、`test_clean_dev` 覆盖身份文案和帮助。
- 任务 2—6 相关 UI 几何、core/ui_edges/startup_perf、smoke gate 和整体结论见 `tasks_round_1446_result.md`；本附件不提前宣称未执行测试通过。

## 断言文案同步、逻辑未动

| 原位置 | 同步内容 |
| --- | --- |
| `程序/tests/test_pet_settings.py:781` | 窗口标题期望的应用名改取 `desktop.APP_NAME`；版本和标题格式断言保持。 |
| `程序/tests/test_pet_settings.py:785` | 侧栏文本期望改取 `desktop.APP_NAME`；仍验证侧栏含应用名。 |
| `程序/tests/test_app_shortcut.py:187` | 快捷方式名称夹具改取 `app_shortcut.NAME`；目标路径、图标、命令及升级行为的断言保持。 |

`test_pet_settings` 同一用例中齿轮几何期望因任务 3 调整；这属于布局断言更新，不计入“文案同步、逻辑未动”。

## 兼容性与影响

- 旧目录/文件名/注册表项不迁移；没有改动入口文件名、ICO 名称、数据目录、缓存目录或用户配置键。
- 现有历史快捷方式文件不主动删除；未来生成的快捷方式显示名与描述采用新名称。
- 模型身份固定前缀更新只替换应用称谓；首次请求可能失去一次旧前缀缓存命中，重试、路由和业务提示内容保持。
- 当前文档的静态标题/说明使用新名；历史结果、审计文件和状态记录保留旧名作为历史证据。

## 最终复扫证明

最终以同样排除项重跑跟踪文本扫描，并与 git grep --untracked --exclude-standard 的结果合并，纳入本轮新增源码；共剩余 74 行：B 55 行、C 19 行，A 0 行。B 中包括原 52 行未改动标识、workspace 混合行保留的仓库路径、新增兼容性测试中的旧名基准与启动器路径各 1 行。逐行对照原 B 分类，52/52 原始行原样保留。两种扫描并集避免 ignore 规则隐藏已跟踪的历史资料。

`git diff --check` 已运行，退出码 0。附加组件测试 `程序/tests/test_ui_compact_widgets.py` 的 3 项真实 Tk 用例已通过；最终命令、覆盖和正式门禁限制见 [本轮结果](tasks_round_1446_result.md)。
