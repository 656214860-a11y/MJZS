# 待办索引

## 当前阻塞与待办（2026-10-12 复核，R1381—R1391；R1391 内容 `37ed5bc` 已提交）

- 阻塞·需用户输入／外部条件（未满足不得勾选，也不自动开工）：
  - 白模视频真实上传验收 —— 需用户指定已采用且已生成预演视频的镜头并授权发送素材。
  - P1 启动白屏用户侧复验 —— 需用户重启当前实例后实机确认；若仍白屏须留启动时刻／是否自动打开今日项目／截图，不得以 R536 局部结论当已解决。
  - 会员订阅制（Mode A）—— **显式推迟**，11 项前置决策未定。
  - 流水线代码级分段编排（方案 3b）—— **显式推迟**，待真实需求触发。
  - P3-2 兼容 facade 退役 —— 先查生产调用方，统一淘汰日 2027-03-31。
- 可执行待办·无外部前置（按单项／单页粒度推进，验收以各自「完成判据／原报告」为准）：
  - UI 统一入口路线图 v1：卡片容器／文字层级／忙碌态／文案与复制 已全站收口（R1376—R1380）；弹窗门禁已递归化（R1381，全生产模块 0 裸窗）。**R1381 复核校正**：表格／输入／下拉／提示／右键菜单／文件选择／快捷键／Tooltip／图标／滚动条 均已递归零容忍收口；真正剩余＝设计 token 内联视觉常量（§三 覆盖率审计 7 项已由 R1386／R1390／R1391 全部收口）；文字层级旧页面为已登记 backlog。**按钮已由 R1387 收口**：`test_button_boundary` 由固定页清单升为递归零容忍（`ROOT.rglob`，含子目录，豁免 `ui_widgets.py`），站点实测 269 个生产 `.py` 0 裸 `tk/ttk.Button`，架构 331/331。
  - **【已审计未实现·R1388】设计 token 内联视觉常量**（路线图 §一 第 2 项）：业务页内联 hex **111 处/8 文件**（pet_ui 45／desktop 31／asset_detail 21／cell_hover 6／keyframe_comfy 3／app 2／storyboard_table_ui 2／previs_monitor 1）、数字 padx/pady **213 处/19 文件**、数字字号尺寸候选 **189 处/32 文件**；**双调色板风险**：ui_tokens.py（14 hex）与 ui_theme.py（53 hex）各自硬编码且 ui_theme 未 import ui_tokens。现状无 token 专用门禁。**R1389 已加棘轮门禁** `tests/architecture/test_token_boundary.py`（内联 hex 与数字 padx/pady 按文件「只减不增」，新增文件即违规；架构 336/336）；**迁移仍待做**：先统一调色板（ui_theme 复用 ui_tokens，可能改视觉须先确认）→逐页迁 hex→padx/pady 与字号按单页粒度另批。明细见 [R1388](../程序/tasks_round/tasks_round_1388_result.md)／[R1389](../程序/tasks_round/tasks_round_1389_result.md)。
  - **【已收口·R1390／R1391】§三 覆盖率审计**：7 项全部收口（第 2 事件总线／第 5 删除／第 6 阶段完成 R1390 由根目录门禁升为递归门禁 `production_files_recursive`；第 1 配置读写／第 3 缓存失效／第 7 SKILL 说明与标签 已有门禁；**第 4 项「项目进入路径」R1391 新增 `tests/architecture/test_project_entry_boundary.py` 覆盖门禁**：冻结 `desktop.py` 进入入口集合＋首帧必经 `DesktopStartupController`＋当天选择委托 `desktop_settings_service`，架构 336→341、全量 4983/4983）。见 [R1390](../程序/tasks_round/tasks_round_1390_result.md)／[R1391](../程序/tasks_round/tasks_round_1391_result.md)。
  - **【已收口·R1386】生产文案阶段编号漂移（R1382 登记 → R1386 修复轮）**：`pet_bus.stage_label` 为「NN 阶段名」唯一权威、6 个展示位点改现算、`test_stage_display_boundary` 新增编号一致性／位点冻结／导航序对齐 3 条门禁（架构 326→329）；定向 1275/1275、默认冒烟 8/8、干净 master 全量 4971/4971、0 红（tree=d9aee73c＝`4cb02d3:程序`）；审计口径更正 97→96（删 animatic_service.py:1 的 L2 层级前缀误报）。原登记明细（历史）：生产文案「NN 阶段名」过期编号（旧编号未随 animatic 插入整体偏移）。权威＝pet_bus.STAGES／STAGE_NAMES；导航标签＝desktop.PAGES。排除 stage_path_service.LEGACY_NUMBERED 后命中生产 14 文件 97 处（skill_tools.py 56／desktop.py 15／stage_parallel.py 5／keyframe_batch.py 4／pet_ui.py 4／app.py 3／asset_detail.py 与 skill_panel.py 各 2／animatic_service.py·asset_contract.py·continuity_ledger.py·prompt_window.py·storyboard_files.py·ui_theme.py 各 1）＋tests/ 19 文件 56 处。用户可见：keyframe_batch.py:51/52/141/236、desktop.py:2484/7015/7058、pet_ui.py:2956/2959、stage_parallel.py:477/480/483/486/489、skill_tools.py PAGES。已有 test_stage_display_boundary.py 只查 desktop.PAGES 生成源。对应路线图 §二 第 15 项「阶段显示」。
  - 优化待办队列未完成项：J20／J22／J23／J24／J25／J26，及「后续报告执行项」R1068 真实清理（仅 CRT-026/027/028，逐项批准）、R1052 J3（测得同步 I/O 阻塞才做）、R1059 J19 后续（迁移须明确批准）。
  - O 系列后备注：O35／O36／O37／O38／O39／O40／O41／O42／O43／O46（各自边界见本条以下各段）。
- 已收口、不构成继续授权：R1267 清单 O01—O48 全部完成；UI 统一入口覆盖轮 4 项完成。以下历史段落仅为记忆索引。
- R1267 清单 **O01—O48 已全部完成**（O45 = R1372、O46 = R1373、O47 = R1374、O48 = R1375）。O48（13 阶段、文档与界面标签使用一致权威源，P2／事实·建议，S/M）已收口：阶段步号改由 `pet_bus.stage_step` 唯一权威生成、`architecture.md` §4／§5／§8 三表补齐为 13 行、README 历史目录树加指向当前权威的提示；架构 315/315、定向 1456 条（1 条既有环境相关红）、交互验收 244/244、默认冒烟 8/8；O48 为路线图收口项，已在干净 master 跑 `--all --safe`。清单无剩余项；后续改进按新任务另立轮次。

- O46 后备注（非本轮欠账）：段 1／段 2 只搬不引用 `self` 的纯逻辑；「脚本会话／媒体任务／阶段配置」这些带状态的控制器涉及 Tk 控件生命周期，须单独立项并按其节奏评估是否触发 §5 强制全量；既有交互协调器提案仍待独立实施。Tk 侧页冷切／300 资产页单跑抖动 4～5 倍，判 Tk 回归须多次取多数（归 O48）。旧工作树数量不等于活跃车道数，清理须按 `worktree_ledger.py` 台账另开授权轮。

- O43 后备注（非本轮欠账）：`resume_preview()` 已实现并测试但未接界面（`pet_ui` 含冻结行号注释，接线要另用等行数技巧或改 TODO 快照）；步骤摘要只覆盖阶段＋序号＋步骤名（L3 不能取 L4 的模型/SKILL 冻结摘要）；`artifact_verified` 只认 script／script_structure 两段。

- O42 后备注（非本轮欠账）：背压只让 `stage.executing`／`notify.aggregate` 在待处理数 ≥ `PENDING_LIMIT`(=1024) 时让路，不同事件仍软上限（未做硬丢）；`unsubscribe`／`release` 已提供并测试但未接入 `pet_ui`（含冻结行号注释，且现无订阅累积）；订阅者异常持久诊断按 `ERROR_PERSIST_LIMIT`(=128) 封顶。

- O35 后备注（非本轮欠账）：闭包已落在请求快照 `skill_injection`，若要再在聊天气泡文案上显示「直接内联几项／未展开几项」，需改 `程序/idea_chat.py`；该文件主树里带他人已暂存的无关改动，须等其落地或另行确认后再动。

- O36 后备注（非本轮欠账）：模型窗口只在注入适配器带 record 时才生效；CLI（Codex/qwen）任务书路径没接窗口（desktop 只传 report=True 拿分项预估），如需在 CLI 预览里也按窗口判断，要另接模型记录来源。
- O37 后备注（非本轮欠账）：小样本验证只发一次真实短请求，不覆盖真实长文本上限／真流式通道／工具调用与阶段文档级负载；「完整任务」在「测试连接」下恒「未验证」；body_signals 只存元数据。CLI／API／桌面未各接一条独立检查路径（当前集中在 model_pool＋模型配置页），如需 CLI 侧也跑小样本验证要另接入口。
- O38 后备注（非本轮欠账）：`rollback_recycle_batch` 只在 L1 权威模块，服务层与桌面回收站 UI 未接撤回入口；回收 UI 仍只做「恢复」，未撤回也不能撤回已 committed 批次。若要让用户撤回未提交批次，需另接服务层／页面入口。
- O39 后备注（非本轮欠账）：版本保留原因（`RETAIN_REASONS`）与可回收原因（`VERSION_CLEAN_REASON`）只在 `storage_maintenance` 内给出并写入版本记录，未在界面上「清前先列清单」；若要给用户看「哪些旧版可回收／为什么留」，需另接页面入口。用户锁定（`locked`）暂无写入入口。
- O40 后备注（非本轮欠账）：「重建项目索引」以「路径是否存在」判定保留，被手工移动的项目会作为新目录补登并按目录名取 `name`、丢失原 `status`；要保留状态需走「重新查找项目」（`reconcile_missing`，按分镜指纹认领），两条路径本轮未统一。独立项目备份子系统与「永久清除」入口均未新建（后者只做界面单独明示，需另行授权）。回收站恢复在原位置被同名目录占用时仍零移动，只能由用户先改名占用者再恢复。

- O41 后备注（非本轮欠账）：项目里没有可调用的「远端取消」接口，取消本机等待不撤销远端任务，故 `cancellation_status` 的 `remote` 在生产路径恒为 `pending`／`unknown`（「confirmed」只在调用方拿到远端确认时才真）；`late_results()` 只在内存保留最近 8 条、进程退出即消失，若要跨重启查迟到结果需另接持久化；四角色 hollmwood 取消路径未接 `archive` 归档通道；桌面「中断」文案未在真实 Tk 实机验收。

- R1265 用户授权的技能保障四项已完成、验收通过，无本轮待办；完成后停止，不从历史索引推断新任务。见 [报告](../程序/tasks_round/tasks_round_1265_result.md)。

- R1208 用户最新授权的 API 阶段顺序修复已完成，见 [报告](../程序/tasks_round/tasks_round_1208_result.md)。本任务收尾后停止，不从下列历史待办推断新授权。

- R1198 报表清理修复与其他生成文件机制扫描已完成；后续清理 J1～J8 及对应测试计划见 [清理审计](../程序/tasks_round/tasks_round_1198_cleanup_audit.md)，尚未执行，不从审计发现推断实施授权。

唯一任务列表见 [优化队列](../程序/维护记录/优化待办队列.md)，范围见 [项目状态](../程序/project_status.md)。
以下仅恢复导航，不是新授权或独立状态表：

- 最新授权 R1173 附件 J/K 已按优先级全部完成，见 [R1186](../程序/tasks_round/tasks_round_1186_result.md)。用户要求完成后停止；以下历史待办不作为自动继续授权。

- R1162 已完成桌面全文投递统一；若继续处理用户关于 Codex 仅显示路径的疑问，先核对真实投递回执／输入框，区分深链草稿和全文粘贴。此项是待确认的实机验证，不是已定位缺陷；CLI 改全文尚未授权。

- 当前用户授权：[R1089 J/K](../程序/tasks_round/tasks_round_1089_result.md) 4 项修复后分批简化。F1/R1090、F3/R1091、F4/R1092、F2/R1093 已通过适用验证；下一步行为保持的分批简化，不将历史清理候选作为本次删除授权。

1. 恢复自动优化时先核对 [R1068 J](../程序/tasks_round/tasks_round_1068_result.md)：CRT-026～028 隔离证明完成，真实实施未完成；仍需逐候选审批、安全与回归约束。
2. J19 F/K 聊天协调已在 R1073 完成；候选 03 的保守退出调度重构已在 [R1074](../程序/tasks_round/tasks_round_1074_result.md) 完成。不重复迁移；后台完成回执协议及实机退出未由本轮派发摘要证明。
3. R1052 J3 同步 I/O：测量证据触发，不机械线程化。
4. 服务迁移待办为 0，不重复已完成迁移；其他条件项遵循原队列前置条件。

每项通过验收并收尾后才推进下一项。减少全量频率不等于省略必要定向回归或默认冒烟。
