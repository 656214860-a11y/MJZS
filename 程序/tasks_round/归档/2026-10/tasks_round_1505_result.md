# R1505 结构治理轮：拆分 desktop.py 步骤 3（其余页面与方法成批迁出）

1. **本轮类型？** 结构治理轮（只搬代码，不改逻辑；同类改动批量成轮）。
2. **测试与基线？** 默认冒烟 8/8；架构门禁全绿（首次 27 项红，均为“被检代码换了文件／按文件的基线”，处理见下，断言未动）；全量与干净检出验证见提交后记录。
3. **是否欠账？** 改了层级登记表（风险路径），须全量转绿。

## 改动

`desktop.py` 5003 → **2226 行**（累计自 7820 降 5594 行）。其余页面与方法按主题原样迁入 5 个 L4 Mixin 模块（方法体未改，`self` 语义不变），`Desktop` 继承它们：

| 模块 | 内容 | 行数 |
|---|---|---|
| `desktop_asset_pages.AssetPagesMixin` | 资产页、资产详情／清单、参考图、资产删除／重命名等 39 个方法 | 约 780 |
| `desktop_script_pages.ScriptPagesMixin` | 剧本结构页、剧本质量、下载／确认等 15 个方法 | 约 570 |
| `desktop_media_pages.MediaPagesMixin` | 首帧、视频、配音、剪辑、交付、连贯性、动态分镜等 49 个方法 | 约 980 |
| `desktop_project_pages.ProjectPagesMixin` | 项目首页、项目切换／删除／恢复、遗留项目迁移等 28 个方法 | 约 470 |
| `desktop_idea_menus.IdeaMenusMixin` | 创意对话菜单、附件打开与删除确认（R1490 因测试补丁名而暂留的 6 个） | 约 90 |

- 迁页用 AST 脚本批量完成：迁出方法用到的模块级名字逐个解析——外部导入原样导入；只被迁出方法用的常量／函数随迁；被多个模块或留下代码共用的移入 `desktop_page_support`（`STAGE_ACTION_WIDTH`、`ASSET_*`、`_prefs`），`desktop` 重新导入，旧的 `desktop.<名字>` 引用不变；`LOGGER` 各模块自建。
- **补丁兼容**：测试按 `desktop.<名字>` 打补丁的 `confirm／open_path／ContextMenu／FileDialog／open_studio／open_directory／find_editor_shortcut／comfy_executable／messagebox`，以及方法体里直接写的 `Desktop.asset_write_base(self)`，在 `desktop_page_support` 里是转发函数／转发对象，调用时取 `desktop` 的当前值，补丁照常生效；仍无导入环。

## 测试与门禁的调整（断言未动）

- 读 `desktop.py` 源码或按类找方法的架构门禁共 24 个文件改读 `desktop_text()／parse_desktop()`（合并 Desktop 全部来源）；个别按“文件名”登记的基线改成按新位置：`test_token_boundary`（`desktop.py` 的 40 处数字 padding 按迁出位置分到各模块，合计不增）、`test_data_table_boundary`（项目树 3 处中 2 处随项目首页迁入 `desktop_project_pages.py`）、`test_stage_display_boundary`（视频标题在 `desktop_media_pages.py`）、`test_startup_budget`（`choose_project` 仍在启动链上，改查 `ProjectPagesMixin`）、`test_handoff_publication_boundary`（`handoff` 在 `MediaPagesMixin`）。
- 非架构测试 10 个文件同样改读合并源码；`test_stage_wiring`、`test_task_center` 里按“下一个固定方法名”截取方法体的写法改为“到下一个 `def` 为止”（方法体语义不变）。
- `_scan.DESKTOP_PARTS`、`_layers.py`（5 个新模块登记 L4）、`test_module_size_ratchet`（`desktop.py` 上限 5100 → 2300）、TODO 注释快照、`architecture.md`、`PROJECT_MAP.md` 同步。

## 仍留在 `desktop.py` 的内容

外壳与启动（`__init__`、`load`、`show`、`go_page`）、异步任务（`async_`／排队／重试）、自动链调度（`_tick_*` 编排、`_initialize_automation_state`）、定稿与门禁小方法、`pet_*` 桥接、页面路由与缓存。它们彼此强耦合，是 `Desktop` 的核心，不再继续拆。

## 提交

已提交，见 git log 标题 `R1505:`。

## 补记

全量复测唯一的红 `test_script_agent_delivery_paths`（用 `desktop.__file__` 读源码找 `start_script_workflow`）已改读合并源码，断言未动。
