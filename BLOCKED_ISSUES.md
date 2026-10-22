# 应用优化执行记录：跳过项与无需修改项

本文件记录《应用优化清单》执行中**未改代码**的条目及原因。编号对应清单序号。

## 实测后无需修改

| # | 项 | 实测结果 |
|---|---|---|
| 2 | `_fit_content_now` 整树测量 | 240 个文件时仅调用 27 次、合计 66ms，调用次数与文件数无关（`schedule_layout` 每批取消并重排，批次中途不会真的测量）。清单里"N/24 次整树测量"的推断不成立。 |
| 3 | `ui_theme.place` 同步布局 | 主窗口路径上只剩 1 次 `update_idletasks`（`ui_theme.py:315`），是最终尺寸下必需的那一次布局；去掉只是把同样的布局推迟到下一轮空闲。 |

## 需要单独一轮处理（已跳过）

| # | 项 | 跳过原因 | 建议 |
|---|---|---|---|
| 4 | `agent/publication.access()` 持进程锁长等文件锁、损坏事务无隔离 | 这是全应用成果发布的事务层，读路径加锁与"日志损坏即停止读取以保护旧成果"都是**刻意的安全设计**。自动隔离损坏事务会放弃回滚，可能留下半写成果，需要你拍板策略；30 秒上限内的等待只在另一进程持锁时出现，事务本身很短，未复现真实卡顿。 | 若要动，先决定：损坏事务是隔离继续运行，还是仍然停读并提示用户处理。 |
| 6 | 拆分 `workflow_settings.py`（约 1000 行业务 + Tk 对话框） | 涉及约 30 个源文件的 import 和 47 个测试文件；测试大量用 `patch('workflow_settings.find_program')` 等路径打桩，拆分后全部要改指向。超出"一次只改一个文件、可立即测试"的范围。 | 单独开一轮：先建 `workflow_settings_service` 并迁移，再分批改 L3 调用方和测试 mock 路径。 |
| 8 | `.env` 从项目配置 `project_dir` 读取密钥（`api_endpoints.py:29-35`、`cloud_video_service.py:97-107`） | `configured_key` 同时服务于程序自己拥有的目录（`model_pool.py:385`、`model_router.py:108` 的旧密钥迁移）和项目配置驱动的调用（`agent/volcengine.py`、`agent/wan.py`、`engine.py`）。直接禁用会让仍存放在旧 `.env` 的用户读不到密钥。`cloud_video_service` 那处已经要求 `base_url` 等于官方地址，密钥不会发往别处，风险低。 | 需要你决定旧 `.env` 兼容的终止时间；之后对"项目配置驱动"的调用关掉 `project_dir` 读取，只保留程序自有目录。 |

## 实测后无需修改（续）

| # | 项 | 实测结果 |
|---|---|---|
| 15 | 150ms tick 内的分镜目录扫描 | 901 个 JSON 的 `tree_signature` 约 61ms，且已有 5 秒节流与指纹短路。改用 `os.scandir` 能再省一些，但 `discover_files` 被 5 处共用并承担符号链接排除，收益小、风险高，暂不动。 |
| 16 | 剧本文件列表主线程枚举 | 1000 个文件枚举共 365ms，已按 24 个一批、每批约 9ms 分摊到空闲回调，不构成卡顿。`draft_document` 全文比对分支未在此场景触发，未测。 |
| 17 | `read()` 每次取跨进程文件锁 | 每次约 385µs，裸读约 78µs，即每次多约 0.3ms；与第 4 项同属事务层设计，不单独改。 |

## 需要单独一轮处理（续）

| # | 项 | 跳过原因 | 建议 |
|---|---|---|---|
| 18 | 拆分 `stage_execution_service.py`（1454 行，扇出 63，被 42 个模块引用）与 `script_contract.py`（L0 夹带 L3 门面） | 上帝对象重构，牵动约 42 个调用方与大量 mock 路径，且 `script_contract` ⇄ `script_skill_report` 是已登记的环（`KNOWN_DYNAMIC_CYCLES`），拆法需先定接口。 | 单开一轮：先按"阶段启动／完成核验／报告"划分接口，再迁移；每拆一块就删 `KNOWN_DYNAMIC_CYCLES` / `KNOWN_DYNAMIC_UPWARD` 里对应的行。 |
| 19 | `Desktop`／`IdeaChatMixin` 等 Mixin 上帝类 | 逐步改为注入回调的 controller 是长期重构，无已证实的缺陷，没有"一次只改一个文件"的切分点。 | 随功能迭代逐个拆，先 `IdeaChatMixin`、`MediaPagesMixin`。 |
| 20 | `asset_thumbs`（L1）与 `storyboard_selection.source_selector`（L3）引入 Tk | `asset_thumbs` 的调用方全是 L4，改登记为 L4 即可，但它同时出现在 `架构统一基数.json` 的两处台账（行 944、1360）和 `smoke_test.py` 里，要连带改多处；`source_selector` 只有 `desktop.py:1181` 一个调用方，可迁到 L4 模块，但需同步测试。 | 单独一轮做：先迁 `source_selector`，再改 `asset_thumbs` 的登记并同步台账。 |

## 接受的信任边界（不改代码）

- 第 21 项：已在 R1777 审计中判定为产品既定的信任边界，不属于缺陷。
- 第 25 项：`-ExecutionPolicy Bypass` 只用于应用自己生成的脚本（`app_shortcut` 用 `mkstemp` 在用户临时目录建随机名脚本，`codex_paste.ps1` 随程序分发），不执行外部输入；用户机器若设了 AllSigned 就没法跑，Bypass 是必须的。固定名 `.lock` 文件都是应用自己目录或项目目录里的咨询锁，不是权限边界。

## 已加棘轮、真正的重构需单独一轮（第 28／29／30 项）

- 新增 `程序/tests/architecture/test_complexity_ratchet.py`：嵌套深度 ≥6（19 处，最深 `pet_ui.click` 10 层）、参数 >7 个（52 处，最多 `ui_widgets._configure_button` 13 个）、类 >600 行（14 个，最大 `pet_cloud.Cloud` 1524 行）全部冻结当前值，只许下降、不许新增，降到线内必须从登记表删除。
- 没有当场重构：改 52 个函数签名、拆 14 个大类会同时动几十个调用点与 UI，违反「一次只改一处、能单独测」；每处该单独成轮做并跑对应页面测试。

## 第 33–38 项的处理结论

- 33（内联 hex）：`pet_ui_support.py` 的 39 处已经是具名调色板常量（`SANHU_*`、`MOODS`、`LEVEL_COLORS` 等），集中在一处；挪进 `ui_tokens` 只是搬位置，棘轮数字不变，不动。已按实测把 hex／padx／pady 基线收紧（hex 46→41，padding 199→62）。
- 34（数字 width／height／wraplength）：在 `test_token_boundary.py` 新增 `LAYOUT_NUMBER_BASELINE`（39 个文件、132 处）冻结，只许下降；迁移到 `ui_tokens` 需逐处裁定像素布局，另起一轮。
- 35（重复代码，6 组）：合并 5 组——`workflow_engines` 槽位参数、`file_cache` 三个读取函数、`toggle_focus_check`（新增 `responsive_ui.bind_space_toggle`）、`desktop_media_pages` 后期／交付页顶栏（新增 `stage_action_bar`）、`seedream_api.protect` 转发到 `model_secrets.protect`。**未合并**：`edit_service.automatic_assemble_decision` 与 `handoff_service.automatic_decision`（9 行纯函数）——抽共享须新增顶层模块，要同步登记层级表、覆盖率基线、架构清单等 4 处台账，得不偿失；两处是不同业务的自动流程，放着重复。
- 36（超长函数）与 37（接近 1500 行的模块）：现有 `test_function_size_ratchet`、`test_module_size_ratchet` 已冻结，本轮把函数登记值收紧到实测值；真正拆分需按页面单独成轮。
- 38（285 个顶层模块平铺）：有意取舍，长期事项，不动。
