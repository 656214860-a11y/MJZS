# R547｜只读诊断轮：R182 长期架构债务拆分报告

## 本轮边界

- 轮次类型：只读诊断轮。
- 已读取：`tasks_round/tasks_round_182_optimization_checklist.md` 全文，并静态审阅当前生产模块及其服务依赖。
- 未修改任何 `.py`、`project_status.md` 或既有文件；本报告是本轮唯一新增文件。
- 未运行测试：本轮不改代码，结论仅陈述静态审计事实，不以测试结果替代实施验收。

## 审计结论

R182 的三项宏观债务不能整体标为“未完成”：它们的底层能力和第一批迁移已落地，但尚未达到“所有阶段／所有页面／所有旧入口”的验收口径。

| R182 宏观项 | 当前事实 | 判定 |
|---|---|---|
| 统一阶段写入服务 | `agent/core.py:53-63` 已有唯一临时文件和原子 `save_text()`；`subtitle_export_service.py:14` 已接入字幕发布。尚未发现一个覆盖阶段成果、校验、索引更新的统一编排入口。 | 部分完成，仍为 P0 债务 |
| view/service/adapter 拆分 | 已有 `script_workspace_service`、`storyboard_catalog_service`、`asset_batch_service` 等无 Tk 服务；但 `desktop.py` 5,763 行，`storyboard_files.py` 773 行、`asset_batch.py` 361 行仍同时含 Tk 创建、事件回调与流程编排。 | 部分完成，仍为 P1 债务 |
| 旧接口 facade | `legacy_compat.py` 现为 78 行的集中门面，`confirm_gates.py`、`idea_chat.py` 已调用它；R182 对该首段本身标为 `[x]`。 | 主体已完成；仅余退役治理，不应再作为泛化“大拆分”任务 |
| 巨型初始化／多职责函数 | `Desktop.__init__`、`tick()` 和 8 个 `poll_auto_*()` 仍在 `desktop.py`；文件发现已迁至服务，但自动流程、对话和按钮编排仍在桌面类。 | 未收口，P1 债务 |
| 增量加载与上下文预算 | `file_cache.py` 已有 mtime/大小/哈希缓存，剧本预览已有异步能力；R182 仍明确保留目录增量加载、全页面按需预览，以及非剧本阶段的摘要/并发限制。 | 部分完成，P2 债务 |

## J. R182 剩余债务的可执行子项

以下 17 项只覆盖上述长期架构债；不把 R182 中响应式布局、删除回收站、跨平台真实环境验收等其他专项重复计入。每项应单独建轮、单独测试和验收，不与相邻项捆绑提交。

| 编号 | 一句话任务 | 涉及模块 | 预估轮数 | 优先级 |
|---|---|---|---|---|
| P0-1 | 建立阶段成果发布编排契约：统一执行临时写入、内容校验、原子替换和索引更新，并定义失败时不得完成阶段。 | `agent/core.py`、`stage_execution_service.py`、`stage_workspace_service.py`、阶段契约测试 | 2-3 轮 | P0 |
| P0-2 | 将剧本与分镜正式成果的现有发布路径迁入 P0-1 的统一入口，保留来源关系和恢复语义。 | `script_contract.py`、`storyboard_*`、`stage_execution_service.py` | 2-3 轮 | P0 |
| P0-3 | 将媒体／交付／首帧等非剧本文本成果的正式发布路径迁入统一入口；字幕已在 R512 接入，作为回归样本而非重复改造对象。 | `keyframe_lifecycle_service.py`、`video_prompt_publication.py`、`audio_import_service.py`、`delivery_import_service.py` | 1 轮 | P0 |
| P1-1 | 将 `Desktop.__init__` 中窗口生命周期、首帧调度和依赖装配拆成可无 Tk 验证的启动控制器，视图仅创建窗口和绑定事件。 | `desktop.py`、新 desktop 启动服务／适配器、启动测试 | 2-3 轮 | P1 |
| P1-2 | 提取 `tick()` 与各 `poll_auto_*()` 的自动流程调度器，统一队列轮询、取消、异常和下一次调度，不改变阶段状态机。 | `desktop.py`、`stage_flow.py`、自动化相关服务 | 2-3 轮 | P1 |
| P1-3 | 提取剧本准备页对话的状态、发送节流、流式回调和附件注入控制器，保留 `desktop.py` 的控件绑定。 | `desktop.py`、`idea_chat.py`、`idea_attachments.py` | 2-3 轮 | P1 |
| P1-4 | 将 `storyboard_files.show_final()` 的预览、保存、导航状态移为控制器／服务，页面函数只组装 Tk 控件。 | `storyboard_files.py`、`storyboard_edit_service.py`、`storyboard_storage.py` | 1 轮 | P1 |
| P1-5 | 将 `storyboard_files.show()` 的表格刷新、选择和回收操作从 Tk 回调抽为可测试的页面控制器。 | `storyboard_files.py`、`storyboard_catalog_service.py`、`storyboard_recycle_service.py`、`storyboard_selection.py` | 2-3 轮 | P1 |
| P1-6 | 将 `asset_batch.show()` 的表单状态、模型配置、检测和启动决策移出 UI，保留 `asset_batch.py` 作为兼容入口及窗口组装层。 | `asset_batch.py`、`asset_batch_settings_service.py`、`asset_batch_execution.py`、`asset_batch_service.py` | 2-3 轮 | P1 |
| P1-7 | 为已迁移的 desktop／分镜／资产边界补静态架构门禁，禁止服务导入 Tk、禁止 view 直连进程/网络，并冻结允许的适配器入口。 | `tests/architecture/`、`desktop.py`、`storyboard_files.py`、`asset_batch.py` | 1 轮 | P1 |
| P2-1 | 为剩余文件表实现可取消的增量目录加载与批量 UI 提交，避免大项目刷新时一次性枚举和渲染全部条目。 | `storyboard_catalog_service.py`、`script_workspace_service.py`、`desktop.py` | 2-3 轮 | P2 |
| P2-2 | 将尚未覆盖的分镜 JSON／资产预览接入按需、分片和可取消的读取协议，复用已有哈希缓存。 | `file_cache.py`、`script_preview_service.py`、`storyboard_files.py`、资产预览模块 | 2-3 轮 | P2 |
| P2-3 | 定义文件发布、回收、外部覆盖后的缓存失效事件，替代页面各自刷新或被动依赖 mtime 的做法。 | `file_cache.py`、`storyboard_recycle_service.py`、`script_workspace_service.py`、发布服务 | 1 轮 | P2 |
| P2-4 | 为非剧本阶段建立阶段级上下文摘要策略及可观测预算，避免不同模型调用重复携带全量项目文本。 | `model_router.py`、`workflow_tasks.py`、`agent_dispatch.py`、模型诊断 | 2-3 轮 | P2 |
| P2-5 | 建立跨阶段模型请求的并发槽与排队／取消策略，并让 UI 显示等待而不在主线程阻塞。 | `model_router.py`、`agent_dispatch.py`、`desktop.py`、后台任务服务 | 2-3 轮 | P2 |
| P3-1 | 建立 facade 调用方清单、唯一所有者、淘汰日期和逾期测试，确认所有历史兼容入口均集中到 `legacy_compat` 或已声明门面。 | `legacy_compat.py`、`tests/architecture/`、历史别名调用方 | 1 轮 | P3 |
| P3-2 | 在 P3-1 清单稳定后，逐个删除已无调用方或已过兼容窗口的 facade 包装，并为旧项目只读迁移留可验证的失败提示。 | `legacy_compat.py`、`project_stages.py`、`stage_path_service.py`、兼容测试 | 1 轮 | P3 |

### 债务余额与排序

- 剩余为 **17 个独立子项**：P0 3 项、P1 7 项、P2 5 项、P3 2 项；其中 P3-1/P3-2 是 facade 的收尾治理，不表示 R182 的 facade 首段回退为未完成。
- 按表中估算，最少约 **28 轮**；将 2-3 轮事项按风险拆开验收，则约 **28-39 轮**。
- 建议执行序列：**P0-1 → P0-2 → P0-3 → P1-1/P1-2 → P1-3 至 P1-7 → P2-1 至 P2-5 → P3-1/P3-2**。P0-1 是后续迁移的唯一前置；其余同优先级项可分别立轮。
- 因而“从 R182 挂到 R540”的表述应更新为：宏观项长期未收口，而不是 358 轮均无进展。当前可量化的剩余工作已被以上 17 项取代，后续状态台账应逐项关闭，不再保留不可验收的总括句。

## K. 本轮自检

- 本报告仅做读取、搜索和静态依赖核对；没有执行写入型命令。
- 未改动 `.py` 和 `project_status.md`，符合本轮禁止项。
