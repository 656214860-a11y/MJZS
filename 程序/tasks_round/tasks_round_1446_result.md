# R1446 功能轮结果

- **本轮类型：功能轮。** 范围为应用显示名及主窗口紧凑布局，不改业务流程、命令入口、持久化标识或门禁。
- **测试跑了吗、基线过了吗：已运行定向验证，合并失败单例复验后，24 个模块共 1284 个不同用例中 1283 通过、1 按原规则跳过。正式增量基线未通过验收。** `run_selftests.py -k` 与 `smoke_test.py --gate` 均受工作树外 GUI 令牌写权限阻塞，未取得正式门禁通过凭据；不能以直接工作单元的通过替代门禁。
- **欠账有无变化：既有欠账记录未修改、未清零。** 本轮已发现的功能/断言失败均完成单例复验；正式定向门禁及 smoke 门禁仍待可写共享 Git 令牌的环境补验。全量 `--all --safe` 未运行，合并后后台干净检出全量验证仍由用户安排。

## 任务 1：名称、兼容标识与历史证据

显示名统一取 `程序/app_metadata.py` 的 `APP_NAME = "漫剧助手"`，版本保持 V0.7。主窗口和侧栏、项目选择窗口、启动画面、设置标题、退出及启动异常提示、快捷方式显示名称/说明、清理脚本帮助及模型身份前缀均使用该常量；静态当前文档同步新称谓。

初始扫描使用 `git -c core.quotepath=false grep -n -I`（环境无 rg），按任务书排除 `升级备份/`、`.wt/`、`tasks_round/`、`.bak_*`、`维护记录/`。用户项目登记及 private 数据不作为源码显示名改写对象。跟踪文本共命中 107 行，逐行分类为 A 36、B 52、C 19；下表保留改动前定位。workspace 同一行的产品称谓属于 A，实际仓库路径属于 B。完整审计附件为 [R1446_name_audit.md](R1446_name_audit.md)，本报告直接纳入逐项清单。

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

## 名称复扫与兼容性证明

最终跟踪文本扫描与 `git grep --untracked --exclude-standard` 结果取并集，纳入新增源码且保留被忽略但已跟踪的历史资料：剩余 74 行旧名，A 0、B 55、C 19。B 包括原 52 行兼容标识、workspace 保留的仓库路径、新增兼容性测试旧名称基准及启动器路径各 1 行；原 B 分类逐行比对 52/52 原样保留。

`test_app_metadata.py` 新增 5 项覆盖共享显示名/模型身份、八个显示生产文件同源引用、允许保留的 B 字面量、六类数据目录与启动器/图标/注册表标识、七份当前文档标题。没有重命名仓库目录、启动器文件、ICO、用户数据/缓存目录或注册表项；不会主动删除旧快捷方式。固定模型身份前缀仅替换产品称谓，首次请求可能失去一次旧前缀缓存命中。

## 任务 2—5：布局改动与几何验证

新增设计取值集中在 `ui_tokens.py`，通用行为在 `ui_widgets.py`；主窗口沿用现有数据加载和回调入口。宽度、位置和溢出判断使用控件真实请求尺寸与布局后的几何信息。

| 任务 | 实现 | 对应真实 Tk 验证与当前证据 |
| --- | --- | --- |
| 2 项目按钮与列表 | “新建项目”“打开项目目录”使用紧凑项目按钮样式；侧栏仅项目列表所在 grid 行分配剩余高度，按真实高度、行高和边框计算可见行数，最低 3 行。 | `CompactDesktopGeometryTests.test_project_buttons_are_half_the_previous_layout_height` 在同 DPI、字体下重建旧布局作相对比较：942×1032 的新按钮高度为旧值约一半，容差 ±2px。`test_header_sidebar_and_file_area_remain_visible_after_shrink_and_grow` 验证 942×1032→800×600→942×1032 的列表行预算、项目控件和导航不相交。两项均通过。 |
| 3 齿轮与标题 | 齿轮 x 使用标题实际位置及 `winfo_reqwidth()` 加 token 间距；底边跟随标题实际底边，绑定相关尺寸变化。 | 同一往返缩放测试验证齿轮横向跟随标题请求宽度、底边与标题底边相差不超过 2px；不是旧标题固定 x 值。 |
| 4 阶段标题与聊天区 | 阶段标题在独立标题行右移并上对齐；标题行高度依项目列表真实顶边计算，使聊天区顶边与列表顶边对齐。内容画布根据已有控件的请求尺寸收敛重排，解决缩小后残留旧画布高度。 | 往返缩放测试验证聊天区与列表顶边 ±2px、阶段标题相对上移/右移，以及四栏文件区底边不越出画布。请求尺寸收敛只遍历已创建控件，不新增启动目录扫描。 |
| 5 宠物、爪印与提示 | 头像及爪印缩小上移，尺寸与间距统一取 PET_LAYOUT；命中、默认菜单落点和云朵锚点跟随真实头像坐标。 | Geometry 8/8、CaptionTests 失败单例复验 1/1 通过。覆盖 942×1032/800×600 绘制边界、爪印命中、提示避让、宿主窗口移动后的默认菜单和云朵锚点。原头像没有拖拽绑定，本轮没有新增；没有合成真实右键事件，不将窗口移动测试称为鼠标拖拽验证。 |

实测摘要（坐标相对窗口客户区，同一次 Tk/DPI 环境）：942×1032 下两个项目按钮由 45/46px 收紧至 21px，列表高 407px、16 个完整行；阶段标题从约 (168,43) 调整到 (180,8)，聊天区顶边由 118px 调整到与列表一致的 103px。800×600 下两个按钮高 19px、列表容纳 4 个完整行。头像为 48px，爪子单元为 16px、容器 52×18px，头像与爪子间距 2px。数值用于说明本环境实测，不替代测试中对真实请求尺寸的相对判断。

**800×600 的按钮高度取舍：** 942×1032 按任务书验证约减半；800×600 时按字体保留最小 19px，使文字完整可读。把旧小窗口按钮再机械减半至约 11px 会裁字，因此小窗口验证不溢出、文字可容纳、项目列表至少三行，不把裁字作为“减半达标”。

主窗口几何测试使用临时项目及四分类长文件名夹具，路径按实际发现契约放在 `writing / 测试提供方 / 测试模型 / 创意_20261015 / 分类`。夹具块已独立经 `discover_script_documents` 验证发现 character、outline、script、setting 四类；没有通过空文件列表掩盖 tooltip 断言，也没有为夹具增加递归发现逻辑。

## 任务 6：可读性结论表

| 项 | 结论与改动 | 验证与边界 |
| --- | --- | --- |
| a 底部状态 | 用 EllipsisLabel 按真实字体及可用宽度省略，保留全文 tooltip；状态和会话信息分别分配伸缩宽度。 | 新组件测试覆盖窄宽度省略、全文提示、扩宽恢复、文本更新及极窄宽度；组件测试 3/3 通过。 |
| b 质检按钮 | 完整显示“查看质检报告”；操作按钮宽度由文字请求宽度决定，沿用 FlowBar 自动换行。 | 主窗口 `test_actions_hint_and_full_file_details` 在 800×600 检查按钮足以容纳文本，已通过。 |
| c 长项目名 | 项目列表按行悬停显示现有完整文本，离开隐藏；不在悬停时读盘。 | TreeRowTooltip 新测试覆盖不同真实行切换、原提示销毁、空白/离开隐藏，并断言悬停不调用文件/目录读取入口；组件测试 3/3 通过。 |
| d 空已完成组 | 空组默认折叠并使用已有弱化文字颜色；保留组行及展开能力。 | 主窗口动作/文件测试验证空组初始折叠且可展开。`test_core` 简化 Tree 替身补 `tag_configure` 方法，原缺项目目录断言保持。 |
| e 四类文件 | 表头居中；悬停显示完整文件名及修改时间。tooltip 数据从原有分批加载返回的 name/modified_at 预存，悬停只查内存。 | 主窗口动作/文件测试验证四类实际文件均出现、全文与本地格式时间正确、表头居中；已通过。 |
| f 输入提示 | placeholder 从 Text 的 inside 边界左侧定位，复用其内部文字边距，避免重复累加 padx。 | 主窗口动作/文件测试和既有 ui_edges 用例均以首字符 bbox 验证真实左边 ±2px；两项最后复验通过。 |
| g 空闲进度 | 主窗口 BusyState 开启 idle_determinate：忙时 indeterminate，空闲 stop 并恢复 determinate/value=0。其他调用的默认行为保持。 | 新组件测试覆盖两轮忙闲转换、按钮启禁及状态文本；组件测试 3/3 通过。 |
| h 其他低风险项 | 集中紧凑表头/按钮/宠物 token；修正缩放后画布内容高度重排；不扩大到业务功能。 | 通过真实主窗口往返尺寸检查约束不遮挡；启动性能 14/14、core 126 通过/1 跳过、ui_edges 115/115；smoke 门禁环境阻塞，详见下节。 |

## 实际验证

解释器均为 `D:\漫剧制作助手\运行环境\Python\python.exe`（以下记 `$PY`）。只做定向及失败单例复验，没有运行 `--all --safe`。同一用例的复验不重复累计到 1284 个用例中。

### 正式入口：实际尝试，未取得通过凭据

```powershell
& $PY -B 程序/run_selftests.py -k test_desktop_compact_layout
& $PY -B 程序/run_selftests.py --gui-wait 0 -k 'test_app_metadata test_app_shortcut test_distribution_build test_manual_plan test_pet_settings test_pet_ui test_selftests test_stdlib_closure test_white_model_workspace test_pet_llm test_clean_dev test_core test_ui_edges test_desktop_startup_perf test_desktop_compact_layout test_ui_compact_widgets test_ui_widgets test_responsive_ui test_pet_cloud'
& $PY -B 程序/smoke_test.py --gate
```

- 两次 `run_selftests.py` 均停在“申请跨树 GUI 令牌”，没有开始正式测试队列。`acquire_pid_lock` 在共享主仓库 `.git` 下创建临时文件；该路径在 R1446 沙箱可写范围外，`tempfile.mkstemp` 的 PermissionError 重试使 `--gui-wait 0` 也不能及时退出，已停止本次启动的进程。日志：`.selftmp/r1446_geometry_tests.log`、`.selftmp/r1446_formal_tests.log`。
- `smoke_test.py --gate` 的 8 项静态检查通过，随后启动原 `run_selftests.py --serial`，同样阻塞于 GUI 令牌；本地外层限时器在 45.09 秒结束本次进程树，记录退出码 124。**门禁测试未运行，smoke 整体不能记通过。** 日志：`.selftmp/r1446_smoke_gate.log`、`.selftmp/r1446_required_summary.log`。
- 未改门禁实现、令牌位置、锁策略或权限设置；以下直接测试没有生成正式门禁台账或基线凭据。

### 直接定向验证与增量复验

初批由本地辅助脚本逐个启动 `unittest discover`（`程序/tests` 下按对应 `test_*.py` 文件筛选），日志汇总为 `.selftmp/r1446_validation_summary.log`。其后使用未修改的 `run_selftests._run_unit`，保留原 `protect_tk` 初始化与 cleanup；只将 TextTestRunner 输出引向实时本地日志。工作单元内容仍为原测试模块/原测试方法。

辅助命令记录（均在本工作树执行，脚本与日志位于已忽略的 `.selftmp/`；首行列出初批实际执行到的模块范围，未执行到的排队项不算覆盖）：

```powershell
& $PY -B .selftmp/r1446_validate.py test_app_metadata test_app_shortcut test_distribution_build test_manual_plan test_pet_settings test_pet_ui test_selftests test_stdlib_closure test_white_model_workspace test_pet_llm test_clean_dev test_core test_ui_edges
& $PY -B .selftmp/r1446_validate.py test_ui_edges.StageConfigEntryTests.test_every_page_opens_its_own_panel test_desktop_startup_perf test_ui_compact_widgets test_idea_chat
& $PY -B .selftmp/r1446_validate.py test_ui_edges.StageConfigEntryTests.test_every_page_opens_its_own_panel test_ui_edges_remaining test_core.DailyProjectChoiceTests.test_missing_project_is_marked_in_project_lists test_manual_plan.ExecPageTests.test_the_page_shows_the_failures_and_can_retry_them test_pet_ui.CaptionTests.test_the_caption_clears_the_patch test_pet_ui.GeometryTests test_ui_widgets_dialogs test_ui_widgets_inputs test_ui_widgets_table test_pet_cloud_contract test_pet_cloud_geometry test_pet_cloud_shape test_pet_cloud_tail test_pet_cloud_text
& $PY -B .selftmp/r1446_validate.py test_ui_edges.UiEdgeTests.test_the_writing_page_gives_the_brief_more_room test_desktop_compact_layout.CompactDesktopGeometryTests.test_actions_hint_and_full_file_details
```

主窗口完整几何文件实际另以 `unittest discover -s tests -p test_desktop_compact_layout.py -v` 运行：3/3，6.281 秒。最后对提示实际左边坐标加严后，只复验相关两个方法（1.903 秒、3.405 秒），均通过。辅助命令在初跑与后续阶段分别采用上述两种加载方式，不把当前脚本内容冒称为初跑时的内容。

| 模块（均以 test_ 为前缀） | 去重后最终结果 | 执行与闭环依据 |
| --- | --- | --- |
| app_metadata | 5 通过 | 1.098 秒；共享显示名及兼容路径。 |
| app_shortcut | 37 通过 | 9.801 秒；原含旧名文件。 |
| distribution_build | 12 通过 | 0.627 秒；原含旧名文件。 |
| manual_plan | 30 通过 | 初跑 29 通过、1 初始化错误；原失败方法在正常 `_run_unit` 初始化后 1/1（0.182 秒），生产代码未为此修改。 |
| pet_settings | 54 通过 | 11.615 秒；包含名称/齿轮几何契约。 |
| pet_ui | 591 通过 | 初跑 590 通过、1 旧 Caption 断言失败；原失败方法 1/1（0.165 秒），关联 Geometry 8/8（0.752 秒）。 |
| selftests | 47 通过 | 1.400 秒；原含旧名文件。 |
| stdlib_closure | 10 通过 | 4.015 秒；原含旧名文件。 |
| white_model_workspace | 21 通过 | 0.105 秒；原含旧名文件。 |
| pet_llm | 54 通过 | 0.309 秒；模型身份前缀。 |
| core | 126 通过、1 跳过 | 初跑 125 通过、1 替身 API 错误、1 skip；Tree 替身补齐 tag_configure 后失败方法 1/1（0.004 秒）。原 skip 为 ValidateProfileTests.test_stage_profile_wrong_preset_rejected，随附技能不存在时的既有 REQUIRES_BUNDLED_SKILL 分支。 |
| ui_edges | 115 通过 | 首批前 35 项通过；第 36 项工作区探测受限，改用临时工作区后 1/1（7.562 秒）；其余 79 项初跑 78 通过、1 旧居中断言失败（133.963 秒），失败方法最终 1/1（1.903 秒）。没有整卷重跑已通过项。 |
| desktop_startup_perf | 14 通过 | 16.445 秒；启动读取/扫描约束。 |
| desktop_compact_layout | 3 通过 | 6.281 秒；真实双尺寸与恢复尺寸；最后提示方法单独复验 3.405 秒。 |
| ui_compact_widgets | 3 通过 | 0.268 秒；省略全文/悬停无 IO/空闲进度。 |
| idea_chat | 120 通过 | 77.919 秒；完整语义改从 tooltip 读取。 |
| ui_widgets_dialogs / inputs / table | 7 / 9 / 3 通过 | 分别 0.503 / 0.525 / 0.186 秒。 |
| pet_cloud_contract / geometry / shape / tail / text | 12 / 4 / 2 / 2 / 2 通过 | 分别 0.003 / 0.001 / 0.000 / 0.001 / 0.001 秒。 |

原旧名所在的八个测试文件（app_shortcut、distribution_build、manual_plan、pet_settings、pet_ui、selftests、stdlib_closure、white_model_workspace）全部纳入以上执行。`test_clean_dev` 的独立文件不存在，初次 discovery 为 0 tests/退出 5，不计作通过；其名称引用由 metadata 测试覆盖。`test_responsive_ui` 也无对应独立文件，不计覆盖。关键词 `test_ui_widgets`、`test_pet_cloud` 由上表实际存在的分文件覆盖。

证据日志：`.selftmp/r1446_direct_geometry_v2.log`、`r1446_validation_summary.log`、`r1446_remaining_v2_summary.log`、`r1446_final_selected_summary.log`、`r1446_placeholder_final_summary.log` 及对应逐模块 `.r1446.log`；只在报告记录摘要，不粘贴整份日志。

### 失败与环境限制闭环

1. manual_plan 的直接加载缺少 presenter 安装：正常 protect_tk 导入 desktop→ui_widgets 后完成安装，原失败用例通过；未改生产代码。
2. core 的极简 Tree 替身缺少新增样式 API：仅补空 tag_configure，原缺失项目目录断言保留并通过。
3. pet Caption 旧公式重复计算提示占位：改以两种尺寸下头像/文字/窗口真实边界验证，原失败用例及 Geometry 均通过；不是名称文案同步。
4. ui_edges 在预演页调用真实 probe_writable，默认目录在沙箱外。通过现有 `MANJU_WHITE_MODEL_WORKSPACE` 进程环境变量指定工作树内已经创建的 TemporaryDirectory；真实可写检查仍执行，没有 mock 探测或写外部配置。该 case 通过。初次受限堆栈不是布局递归。
5. 旧输入提示断言要求居中，与本轮左对齐目标冲突。同步为左对齐并增加首字符 bbox 的真实坐标校验，发现并修复 Text inside 已含内边距而再次加 padx 的偏移；最后两条相关用例通过。垂直居中和禁止动画回调的原断言均保留。
6. 800×600 按钮可读高度取舍见前表；不同 DPI/字体、持续鼠标拖动及真实右键事件未运行，不将双尺寸结果扩张为这些场景通过。系统截图捕获为黑图，未用其声称视觉验收；真实 Tk 几何断言已执行。
7. 正式定向/烟测门禁未运行，原因是共享 Git 令牌路径的写权限；全量未运行，原因是任务书明确禁止。两者均未伪造通过。

## 断言文案同步、逻辑未动

| 改动前位置 | 同步内容 | 保持的判断 |
| --- | --- | --- |
| `程序/tests/test_pet_settings.py:781` | 窗口标题期望的应用名改取 `desktop.APP_NAME`。 | 版本及标题格式断言。 |
| `程序/tests/test_pet_settings.py:785` | 侧栏文本期望改取 `desktop.APP_NAME`。 | 侧栏包含应用名。 |
| `程序/tests/test_app_shortcut.py:187` | 快捷方式名称夹具改取 `app_shortcut.NAME`。 | 目标路径、图标、命令及升级行为断言。 |

`test_pet_settings` 同用例中的齿轮位置断言属于本轮任务 3 的几何契约调整；宠物 CaptionTests 属于提示实际边界验证；core Tree 替身增加 tag_configure 属于测试 API 替身同步。聊天状态测试改读完整 tooltip、输入提示居中改左对齐也属于本轮显示契约调整。以上均不计入上面的“断言文案同步、逻辑未动”清单。新增名称/组件/主窗口几何测试用于验证可观察行为，不替换原业务测试。

## 最终边界与未完成验证

- 仅在当前 R1446 工作树修改本轮代码、当前文档、测试及结果附件；未操作提交/合并/push/切分支/认领轮次，未修改主树、R1445、用户数据、凭据、project_status 或接力 snapshot/backlog。
- 保留业务行为、数据格式、快捷键、命令入口及门禁；路径/标识和历史证据按 B/C 分类保留。
- 已完成最终改动清单核对与差异空白检查，`git diff --check` 退出 0；29 个已有文件修改、5 个新增文件，已有文件 diffstat 为 399 insertions / 126 deletions（不含未跟踪新文件）。工作树只有本轮预期改动。`git status --short` 与 `git diff --stat` 随最终答复提交供验收，未执行 git add/commit。
- 未完成：可写共享 Git 令牌环境下的正式定向与 smoke 门禁；用户合并后的后台全量。当前不宣称正式基线已绿，也不将局部通过记为全量欠账已还。

## 验收复测单点修复：800×600 文件区溢出

- 接受真实桌面验收失败：文件区底边 781，画布底边 +2 为 664，超出 117px。此前本机通过不代表该桌面环境通过；本机未复现相同的 117px 数值。
- 原因：`writing()` 的 `page_fixed` 只在建页/文件加载时测量，缩窄后操作栏换行等固定区域变化没有更新聊天高度预算；原测量还用父容器请求高度减子控件请求高度，Tk 分批传播时可能读到不同批次的尺寸。表格预留采用单棵树的固定行数，未直接保留完整文件区实际请求高度。
- 修复仅涉及 `程序/desktop.py`：每次重排直接累加固定兄弟控件的请求高度及 pack 留白，完整预留文件区；在画布空闲重排中更新聊天高度，按 Text 实际字体计算行高。避免依赖父子请求高度差，不改全局 growable 逻辑，不放宽任何测试断言。
- 本次交付文件仅 `程序/desktop.py` 与本结果说明；主树未修改。
- 验证仅运行指定两个测试文件：`test_desktop_compact_layout` 最终 3/3（8.774 秒），覆盖 942×1032 → 800×600 → 942×1032；`test_pet_ui` 591/591（75.843 秒）。未运行其他测试文件或全量。
- 修复过程中发现 pack 的单值 pady 返回 int，已兼容该形式并重跑几何文件；最终几何日志与 pet 日志均无 Tk 回调异常。
- 同一真实 Tk 窗口补充测量：固定预算分别为 216 / 253 / 216px；文件区底边与画布底边分别同为 1094 / 662 / 1094，均满足原断言。该测量属于本机环境，用户原桌面环境仍需验收复测。
- 证据：`.selftmp/test_desktop_compact_layout.r1446.log`、`.selftmp/test_pet_ui.r1446.log`、`.selftmp/r1446_geometry_probe.log`。上文旧测试时长和差异统计是首次交付记录，本节为本次单点复测结果。
