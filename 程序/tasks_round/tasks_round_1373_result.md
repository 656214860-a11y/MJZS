# R1373：O46 模块治理与热点性能按段推进（先测，再保持入口地搬一段）

类型：结构治理轮（§3.3；本项「事实／建议」→ 先量七条热点路径，再按功能边界做一段**保持入口**的迁移，不做全项目异步化）。承接 R1267 清单 O46（O01—O45 已完成）。中央轮次 1373（主树含他人已暂存 WIP，故在干净临时工作树 `o46-claim` 调用 round_claim.py next 领取）。本轮 1373 − last_full_safe_all_round(1372) = 1 < 5，无五轮欠账；改动未命中 §5（无启动路径、无 Tk 控件生命周期、无删除语义、未改 `tests/architecture/_layers.py`），收口仍按流程在干净 master 工作树跑一次 `--all --safe`。

## 三个必答
- 本轮类型：结构治理轮。
- 测试：新增 `tests/test_idea_chat_presentation.py` 10/10、`tests/test_platform_tools.py` 补 3 条（共 20/20）；定向 `-k platform_tools idea_chat_presentation` 30/30；Tk 消费者 `-k ui_edges idea_chat unification_ratchet` 259/259；架构 `--layer architecture --all` 312/312；默认冒烟 `smoke_test.py` 8/8；均 0 红。
- 欠账：O46 关闭，清单剩 O47—O48；1373 − 1372 = 1 < 5，无五轮欠账；未命中 §5；收口跑一次干净 master 全量（结果见「全量判定」）。

## 目标（R1267 清单 O46）
- 依据：`desktop.py`、`pet_ui.py` 等仍是数千行模块，但已有 L3 服务、ProjectContext、UI 注册和主动任务生命周期；不能把大文件等同全部架构失败。
- 建议：以脚本会话、媒体任务、阶段配置等独立功能边界拆控制器，复用现有服务；先测启动、换项目、刷新目录、滚动、缩略图、长对话、媒体导入的耗时/内存。旧工作树按已有台账计划处理，数量不等于活跃车道数，不直接删除。
- 验收：每段迁移保持入口与交互，定向回归通过并记录性能前后值；未测出瓶颈不做全项目异步化。既有交互协调器提案尚待独立实施，不能记成已落地。

## 先测：七条热点路径的耗时/内存
模块规模（改前实测）：`desktop.py` **7510 行**（`Desktop` 类 7247 行，含 15 个不引用 `self` 的方法）、`pet_ui.py` **4816 行**（`Pet` 类 3887 行，含 7 个不引用 `self` 的方法）、`app.py` 1449 行。

覆盖方式：Tk 渲染相关的「启动／页面切换／滚动／缩略图／长列表」复用既有 `维护记录/基准脚本/基准_启动与页面.py full`（离线、自建并销毁窗口）；本轮缺的「换项目／刷新目录／长对话／媒体导入」新增无 Tk 的服务层探针 `维护记录/基准脚本/基准_热点路径.py`（合成负载：24 项目／1500 文件／800 条消息／400 文件）。

改前（`基准结果_启动与页面_full_改前.json`、`基准结果_热点路径_改前.json`）：
- 启动：import_tkinter 15.5ms／import_desktop 135.9ms／Desktop() 226.3ms／首帧 297.7ms／ready 735.1ms；导入后 34.3MB、启动后 48.2MB。
- 11 页冷切：page6 2222.7ms、page7 1415.7、page0 1264.0、page8 962.2、page2 818.2（其余 226～496ms）。
- 缩略图冷/热平均 2.8／0.0ms；300 资产页 1837.9ms、热 2963.3ms、滚动 20 步 0.2ms；300 资产后 60.9MB。
- 热点探针：换项目 5.3ms／刷新目录 15.3ms／长对话 2.8ms／媒体导入 3.3ms。

改后（`基准结果_启动与页面_full.json`、`基准结果_热点路径.json`）：
- 启动：import_desktop 133.9ms／Desktop() 221.3ms／首帧 289.0ms／ready 714.8ms。
- 11 页冷切：page6 519.9ms、page7 1466.6、page0 1259.3、page2 890.8、page8 793.1（其余 226～496ms）。
- 300 资产页 1515.5ms、热 544.1ms、滚动 0.2ms。
- 热点探针：换项目 5.1ms／刷新目录 15.4ms／长对话 3.1ms／媒体导入 3.3ms。

结论：**纯服务层路径都在十几毫秒以内**（≤16ms），没有测出瓶颈，因此本轮**不做**全项目异步化；Tk 侧单跑抖动极大（page6 2222.7→519.9ms、300 资产页热值 2963.3→544.1ms，两次相差 4～5 倍），单次 Tk 数字不足以判定回归——与已知 `test_desktop_startup_perf` / `test_perf_baseline` 阈值抖动同源，若要判 Tk 回归必须多次取中位（归 O48）。两段迁移是行为保持的重构，探针与启动数值变化都在噪声内，没有系统性差异。

## 实现（两段保持入口的迁移）
段 1（本机适配下沉 L0）：向 `platform_tools.py`（L0）新增 `open_directory(path)`（先 `mkdir(exist_ok=True)` 再用宿主默认程序打开）与 `find_editor_shortcut(name='剪映专业版', *, skip=('卸载',))`（开始菜单扫描、跳过卸载项、无匹配返回 None）；`desktop.py` 的 `Desktop.find_editor_shortcut`／`Desktop.open_folder` 改成等语义的 1 行入口（`return find_editor_shortcut()`／`open_directory(p)`）。行为不变：仍不引用 `self`、仍可 `Desktop.find_editor_shortcut(object())` 直呼（`test_ui_edges` 的既有两条断言 `test_launch_editor_only_queues_the_start_menu_scan`／`test_start_menu_worker_retains_the_existing_shortcut_rule` 未改且转绿），`launch_editor` 仍把扫描丢给后台队列。
- 该下沉命中架构门禁 `tests/architecture/test_migrated_ui_boundaries.py` 的「本机适配入口登记表」：按门禁要求把 `find_editor_shortcut`／`open_directory` 登记进 `desktop` 允许的 `platform_tools` 适配入口集合（这是适配入口登记，不是 `_layers.py` 层级登记表）。

段 2（对话气泡纯展示下沉 L3）：向 `idea_chat_controller.py`（L3，无 Tk）新增 `BUBBLE_COLLAPSE_CHARS`／`BUBBLE_COLLAPSE_LINES` 与 `bubble_timestamp(at)`／`collapse_preview(text, *, chars, lines)`／`speaker_name(row, *, you, prefix, fallback)`；`desktop.py` 的 `bubble_time`／`bubble_preview`／`model_name` 变成 1 行入口，原折叠阈值常量从 `desktop.py` 移走。读 Tk Text 标签的 `Desktop.bubble_target_at` 留在 L4 不动（界面对话区仍由 L4 持有）。
- 结果：`desktop.py` 7510 → 7491 行（−19）；15 个无 `self` 方法仍作为 L4 注入点保留。
- 未新增顶层模块（`platform_tools`／`idea_chat_controller` 早已在 `_layers.py` 登记）、未改 `_layers.py`、未改 Tk 控件生命周期、未动启动路径与删除语义。

## 契约变化与同步
- 新增 `程序/维护记录/基准脚本/基准_热点路径.py`（无 Tk 热点探针）＋结果 `基准结果_热点路径.json`／`基准结果_热点路径_改前.json`，以及 `基准结果_启动与页面_full_改前.json` 改前留档（沿用仓库 `_改前/_改后` 惯例）。
- `程序/维护记录/TODO注释快照_20261003.json`：段 2 让 `desktop.py` 里那条含「暂时」的行注释上移 12 行，行号 2753 → 2741 平移；**注释集合不变**（仍 3 条：`asset_detail.py` 350、`desktop.py` 2741、`pet_ui.py` 2801；内容／分类／处置／理由都未改）。这是 R1330「修复全量第 1 次红——TODO 注释快照行号平移」的既有做法。
- `desktop`（L4）仍只经 L0 适配器做本机操作，符合 `test_migrated_ui_boundaries` 的边界口径；没有新的直接 `subprocess`／`os.startfile`／`socket` 调用。
- 未新增顶层模块、未加 `skipTest`、未改 `_layers.py`／架构统一基数；架构门禁 312/312（基线只增不减）。

## 测试
- 新增 `tests/test_idea_chat_presentation.py`（10 条）：时间戳两种形状与认不出留空；短消息不折叠、超 360 字符折到字符预算、超 8 行折到行预算；署名「您」与「对话AI · 模型名／兜底」；并逐条断言 L4 入口 `bubble_time`／`bubble_preview`／`model_name`／`open_folder`／`find_editor_shortcut` 与 L0/L3 实现口径一致（把「入口不变」变成可回归的断言）。
- `tests/test_platform_tools.py` 补 3 条（共 20 条）：`open_directory` 先建目录再委托 `open_path`；开始菜单扫描优先已安装项、跳过「卸载」；无匹配返回 `None`。
- 定向 `-k platform_tools idea_chat_presentation` 30/30；Tk 消费者 `-k ui_edges idea_chat unification_ratchet` 259/259（`test_ui_edges` 既有的 `Desktop.find_editor_shortcut(object())` 与「点击按钮不主线程扫描开始菜单」断言保持绿，证明段 1 入口与行为未变）；架构 `--layer architecture --all` 312/312；默认冒烟 `smoke_test.py` 8/8。

## 边界
- 「旧工作树按已有台账计划处理」：本轮只做**测量与迁移**，未删除任何工作树；`git worktree list` 里数量不少，但数量不等于活跃车道数，清理须另开授权轮按 `worktree_ledger.py` 台账执行。
- 页面冷切与 300 资产页的单跑差异很大（4～5 倍），本轮未做多次取中位；判定 Tk 回归应按 §5 已知抖动口径多次复测取多数，不能拿单次数字下结论。
- 本轮只下沉**纯逻辑**（不引用 `self` 的两处）。「脚本会话／媒体任务／阶段配置」这些带状态的控制器涉及 Tk 控件生命周期，须单独立项、按其节奏评估是否触发 §5 强制全量；「既有交互协调器提案」仍未实施，不记为已落地。
- 探针用的是合成负载（24 项目／1500 文件／800 条消息／400 文件），只用于横向比较与找热点，不等于真实项目规模。

## 全量判定
- 1373 − last_full_safe_all_round(1372) = 1 < 5，无五轮欠账；改动未命中 §5（无启动路径、无 Tk 控件生命周期、无删除语义；`_layers.py` 未改，只登记了 `test_migrated_ui_boundaries.py` 的适配入口集合）。
- 复用检查：`.git/full-safe-receipts.json` 最近绿凭据为 round=1372、tree=71554aa7…（2026-10-12，7 日内），但本轮改了 `platform_tools.py`／`idea_chat_controller.py`／`desktop.py` 并新增测试，`HEAD:程序` 内容树不同，不能复用。
- 全量结果：待收尾补记。

## 提交
- 本轮改动：`程序/platform_tools.py`、`程序/idea_chat_controller.py`、`程序/desktop.py`、`程序/tests/test_idea_chat_presentation.py`（新）、`程序/tests/test_platform_tools.py`、`程序/tests/architecture/test_migrated_ui_boundaries.py`、`程序/维护记录/TODO注释快照_20261003.json`、`程序/维护记录/基准脚本/基准_热点路径.py`（新）、`程序/维护记录/基准脚本/基准结果_热点路径.json`（新）、`程序/维护记录/基准脚本/基准结果_热点路径_改前.json`（新）、`程序/维护记录/基准脚本/基准结果_启动与页面_full.json`、`程序/维护记录/基准脚本/基准结果_启动与页面_full_改前.json`（新）、`程序/tasks_round/tasks_round_1373_result.md`（新）、`程序/project_status.md`、`.agent-handoff/{snapshot,work-log,validation,backlog}.md`。
- 内容提交：待收尾补记（未含主树他人已暂存的 `程序/idea_chat.py`／`程序/idea_attachments.py`／`程序/配置/SKILL/预设.json`）。
- 提交状态：待收尾补记。
