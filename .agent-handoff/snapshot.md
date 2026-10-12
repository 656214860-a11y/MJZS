# 当前快照

## 2026-10-12：会话收尾（R1376—R1380 已收口，无待办）
- 本次仅做收尾复核并记录：确认 R1376—R1380（UI 统一入口覆盖轮：忙碌态／文案与复制／卡片容器／文字层级）已全部提交并收口，本次会话未新增功能改动、未改任何生产代码或测试。
- 状态一致：`程序/project_status.md` 当前轮次＝1381；中央 `.git/round-counter.json` `last_claimed=1380`；R1267 清单 O01—O48 全完成。
- 全量凭据口径（**修正**）：R1380 全量 4967/4967、0 红、631.2 秒的 tree=f62cd088…＝该轮**内容提交 `e25c70d:程序`**，**不**等于当前 `HEAD:程序`（＝3c0d7ead…）。其后 R1380 的 3 个记账提交（`633eb4e` 报告与状态页、`452fb73` 与本次收尾提交 接力）只改 `程序/tasks_round/` 与 `程序/project_status.md`，未改生产代码。因 `latest(1380)−last_full(1380)=0<5`，`test_round_baselines.test_full_safe_all_is_required_every_five_rounds` 走 `full_safe_required=False` 提前返回、**仍绿**（已实跑该文件 5/5 OK）；若后续某轮再次要求全量，须在干净 master 工作树对新树重跑，**勿复用此凭据**（树不同）。
- 工作区：master 仅余他人**已暂存** WIP（`程序/idea_chat.py`／`程序/idea_attachments.py`／`程序/配置/SKILL/预设.json`）与未跟踪产物（`outputs/`、`.codex/`、`.agent-handoff/archive/`、`程序/outputs/`、`程序/配置/宠物/配置.json`），不读／不改／不暂存／不覆盖；无属于本轮的未提交改动或阻塞。
- 下一步：无待办；开工即读 `程序/AGENTS.md` §0，测试按 §5 触发表（每轮 `smoke_test.py`，结构治理轮 `--architecture`，触及 `程序/` 生产文件后命中 §5 升级条件或 ≥5 欠账才全量）；文字层级旧页面 backlog（见 R1380 审计表）按单页粒度滚动迁移，非阻塞。等用户新指令。

## 2026-10-12：UI 统一入口覆盖轮完成（R1376—R1380，路线图 4 项全收口）
- 范围＝`程序/维护记录/UI统一入口路线图_v1.md` 尚未收口的 4 项：卡片容器、文字层级、忙碌态（提交/取消/成功/失败/迟到结果全链路）、文案与复制。用户 5 条硬要求：先读 `程序/AGENTS.md` §0/§2/§5 定轮型；单页粒度分批迁移（不整仓机械替换）；验收以各项「完成判据」原文为准、收口写「完成全量覆盖审计」；测试按 §5 触发表、不因收尾跑全量兜底；完成/暂停都更新接力。
- R1376 忙碌态：`app.py`／`native_assets.py` 的进度条 `start/stop` 收口到 `BusyState.set_busy`；`tests/architecture/test_busy_state_boundary.py` 7 条（含「生产代码 `ttk.Progressbar` 的 `.start/.stop` 只许出现在 `ui_widgets.py`」零容忍门禁）。架构 315→320。
- R1377 文案与复制：4 处复制失败术语统一为「复制失败：…」，禁止「复制成功／成功复制」；修正 `asset_detail.py` 锚点复制失败被成功文案覆盖的缺陷；`test_copy_entry_boundary.py` 增递归生产扫描。架构 320→321。
- R1378＋R1379 卡片容器：页面级信息/操作单元承载区 `ttk.LabelFrame`→`ui_widgets.Card`（标题改卡内标签）。R1378 迁 asset_detail(7)/native_assets/asset_batch；R1379 迁 keyframe_comfy(2 窗)/desktop(6 区：参考网站分类导航、连续性表格框、待办与裁决、开工前先确认、本地生成、线上生成)。架构 321→323→325。全站点审计：21 页已用 Card，其余（white_model/workflow_settings/cloud_video 的卡内小节、skill_panel 锁定几何阅读区、batch_frames_tool 独立脚本）豁免。**卡片容器完成全量覆盖审计**。
- R1380 文字层级：asset_batch/keyframe_comfy 的功能说明→`DescriptionBlock`、状态行→`ProgressLabel`、标题→`style='Tokens.Title.TLabel'`；`test_text_component_boundary.py` 的 `TEXT_PAGE_COMPONENTS` 增这两页（7 页门禁固化）。全站点审计：组件内部/主题/自绘、缩略图窄格豁免；标题层级无语义组件（登记改用 `Tokens.Title.TLabel`）；其余说明文字按单页粒度续跟（backlog）。**文字层级完成全量覆盖审计**。
- 验证：各轮定向＋默认冒烟 `smoke_test.py` 8/8，0 红。**R1380 命中 §5 五轮规则（1380−1375=5≥5）**，收口在干净 master 工作树 `o07-fullsafe-master` 跑 `run_selftests.py --all --safe`：**4967/4967、0 红、631.2 秒**（首次即绿）；凭据 round=1380、tree=f62cd088…＝`HEAD:程序`、last_full_safe_all_round=1380；同树架构门禁 325/325；`test_desktop_startup_perf` 14/14、`test_perf_baseline` 9/9 无阈值抖动。
- 提交：R1376 a44ad5c、R1377 ef25cde、R1378 dd87f02、R1379 6bdbc0f、R1380 e25c70d（内容）＋633eb4e（补记全量结果）。`project_status.md` 当前轮次＝1381。
- 下一步：路线图 4 项已全收口、无待办；R1267 清单 O01—O48 亦已全完成。文字层级旧页面 backlog（见 R1380 审计表）按单页粒度滚动迁移，非阻塞。等用户新指令。

## 2026-10-12：O48 完成 — R1267 清单 O01—O48 全部收口
- 按 R1267 清单 O01→O48 顺序逐个完成。**O48 已完成（R1375），R1267 清单全部完成**。
- O48（13 阶段、文档与界面标签使用一致权威源）= R1375：`pet_bus.py`（L0）新增 `stage_step(stage)`（按 `STAGES` 顺序给两位步号，与阶段目录、导航页 `PAGES` 同源，未知阶段空串）；13 个生产模块（`app`／`asset_context`／`asset_detail`／`batch_frames_tool/batch_frames`／`desktop`／`engine`／`local_video`／`storyboard_files`／`storyboard_selection`／`video_navigation`／`white_model`／`white_model_ref`／`agent/shot_assets`）的用户可见文案改由它现算，纠正 R1124 前旧步号（分镜 02→03、资产 03→05、定稿 04→07、首帧 05→08、白模 06→09、视频 07→10，共 24 处）；`architecture.md` §4 阶段表 12 行错位→13 行（序号 01—13／ID／中文名逐行＝`pet_bus.STAGES`／`stage_name`）、§5 并行表与 §8 输入输出表各补 `animatic` 成 13 行；`README.md` 第 61 期历史目录树加一行「历史记录」指回 PROJECT_MAP 与 `pet_bus.STAGES`（不动历史正文）。**不改业务逻辑、门禁、路径、分层；不重排页面**。见 [R1375](../程序/tasks_round/tasks_round_1375_result.md)。
- O48 验证证据：架构 315/315（原 312，+3 新用例）＋定向 1456 条 386.7 秒（仅 1 红为既有环境相关）＋交互验收 244/244（`tk scaling` 1.0／1.5／2.0、`<Return>` 发送、takefocus／焦点回归、禁用控件说明）＋默认冒烟 8/8，0 红。唯一红 `test_workflow.DesktopModelPoolTests.test_stage_model_selects_the_matching_desktop_agent`：主树未跟踪 `程序/配置/宠物/配置.json` 把 `claude-desktop` 标签改成「Claude Desktop」，出厂池为「Claude Code」；干净全量工作树单跑为绿（既有、用户配置相关，非本轮回退）。资产子步骤编号（固定角色＝1／场景道具＝2／图片＝3）属另一套口径，未改并列入新门禁白名单。
- 登记平移：`维护记录/架构统一基数.json` 第四项 `batch_frames_tool/batch_frames.py` point 13→14／77→78；`维护记录/TODO注释快照_20261003.json` `asset_detail.py` 350→351；`维护记录/skip台账.json` 用例更名 `..._points_to_step04`→`..._points_to_step07`。
- O48 全量：1375−1374=1<5，但 O48 为路线图收口项（§5「路线图条目收口」）→ 收口在干净 master 工作树 `o07-fullsafe-master` 跑 `run_selftests.py --all --safe`：**4957/4957、0 红、715.1 秒**（首次即绿，无二次全量）；凭据 round=1375、tree=c3df6a57…＝`HEAD:程序`、last_full_safe_all_round=1375；4957−4954=3＝本轮新增架构用例。提交：内容 d5de4df、报告与接力 afcc0a4。
## 2026-10-12：O47 完成（历史）
- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O46 已完成，**O47 已完成（R1374）**，下一项 O48（13 阶段、文档与界面标签使用一致权威源，P2／事实·建议，S/M）。
- O47（关键真实链路集成测试）= R1374：**无生产代码改动**，只新增 `tests/test_critical_chains.py` 17 条（合成数据＋注入传输／发布器，不调用真实付费 API、不依赖 Tk）。链路 A 回收站（O38/O39）：`recycle_paths` 提交／失败注入整批 `rolled_back`→`restore_recycle_batch` 复原字节、`version_retention` 六类保留原因、`edit_source_versions` 读 `13质检交付/导出成片` 的 `edit_bundle.json`、`clean_project` 只处理下载根下带 `config.json` 的项目且回收不永久删除；链路 B 模型请求链：URL／请求头／payload 冻结、密钥不入 payload、`response_meta` 白名单、`usage_of` 映射 `cached_tokens`、`model_diagnostics.record` 落盘不含任何正文、超时 `error_class=timeout` 不抛；链路 C 导入→完成证据（O02/O03）：`import_audio` 落 `11配音与字幕/音频` 且源文件保留、导入≠完成、非对白不能顶替对白、`prepare→confirm` 后才完成、`import_delivery_master` 落交付阶段；链路 D 剧本→结构→分镜：`write_structured_script` 由本地规则生成结构稿、`verified_stage_output(script_structure)` 真、`completion_evidence(storyboard)` 要有采用且含镜头；O04 `video_task_state.submission_block_reason` 区分需修改返工／未决禁投；O05/O06 `stage_parallel.frames_ready` 逐项报未配置／已删除／越界／缺失／空文件／损坏 PNG。见 [R1374](../程序/tasks_round/tasks_round_1374_result.md)。
- O47 验证证据：新增 17/17；定向 `-k critical_chains recycle audio_import stage_completion delivery_import script_contract stage_flow` 187/187、架构 312/312、默认冒烟 8/8，0 红。实测契约事实：`completion_evidence` 对 script/script_structure/storyboard 的返回 detail 是固定「未找到」文案，判定只看 ok；`stage_parallel.frames_ready` 在无可用帧且 keyframe 未跑过时按「上游还没做先不拦」放行，故用例需含真实非空帧文件。
- O47 全量：1374−1373=1<5 且未命中 §5（只新增测试），收口在干净 master 工作树跑一次 `--all --safe`：全量 4954/4954、0 红、665.09 秒（干净 master 工作树 `o07-fullsafe-master`，凭据 round=1374、tree=4778c99e…＝`HEAD:程序`、at=2026-10-12T18:47:48、last_full_safe_all_round=1374；4954−4937=17＝本轮新增用例；无阈值抖动）。

## 2026-10-12：O46 完成（历史）
- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O45 已完成，**O46 已完成（R1373）**，下一项 O47（测试从"数量多"补到关键真实链路，P2／验证·建议，M/L）。
- O46（模块治理与热点性能按段推进）= R1373：先测七条热点路径——Tk 侧复用 基准_启动与页面.py full（启动 ready 735.1→714.8ms、首帧 297.7→289.0ms、缩略图冷 2.8ms、300 资产页 1837.9→1515.5ms、滚动 20 步 0.2ms），缺的换项目／刷新目录／长对话／媒体导入新增无 Tk 探针 `基准_热点路径.py`（≤16ms）；纯服务层无瓶颈 → 不做全项目异步化。再做两段保持入口的迁移：`platform_tools`（L0）新增 `open_directory`／`find_editor_shortcut`，`desktop` 的 `find_editor_shortcut`／`open_folder` 变 1 行入口；`idea_chat_controller`（L3）接管 `bubble_timestamp`／`collapse_preview`／`speaker_name`，`desktop` 的 `bubble_time`／`bubble_preview`／`model_name` 变 1 行入口（desktop 7510→7491 行）。见 [R1373](../程序/tasks_round/tasks_round_1373_result.md)。
- O46 同步项：`tests/architecture/test_migrated_ui_boundaries.py` 适配入口集合登记 `find_editor_shortcut`／`open_directory`；`维护记录/TODO注释快照_20261003.json` 的 desktop.py 行号 2753→2741 平移（注释集合不变，沿 R1330 做法）。
- O46 验证证据：新增 `tests/test_idea_chat_presentation.py` 10/10、`tests/test_platform_tools.py` +3（20/20）；定向 30/30、Tk 消费者 `ui_edges idea_chat unification_ratchet` 259/259、架构 312/312、默认冒烟 8/8，0 红。
- O46 全量：1373−1372=1<5 无五轮欠账且未命中 §5，收口在干净 master 工作树跑一次 `--all --safe`：全量 4937/4937、0 红、710.39 秒（干净 master 工作树 `o46-fullsafe-master`，凭据 round=1373、tree=efdd7f8a…＝`HEAD:程序`、at=2026-10-12T18:24:25、last_full_safe_all_round=1373；4937−4924=13＝本轮新增用例；无阈值抖动）。

## 2026-10-12：O45 完成（历史）
- O45 = R1372（把分发声明变为可复验的干净安装流程：新增 `程序/scripts/distribution_build.py` 的 `parse_manifest`／`plan`／`build`／`verify`＋CLI，精化 `distribution_manifest.md`，新增 `tests/test_distribution_build.py` 12 条）；全量 4924/4924、0 红、688.63 秒（凭据 round=1372、tree=71554aa7…）。详情见 [R1372](../程序/tasks_round/tasks_round_1372_result.md)。
## 2026-10-12：O44 完成（历史）
- O44 = R1371（密钥四态可诊断＋诊断预览与回显脱敏）；全量 4912/4912、0 红、752.38 秒（凭据 round=1371、tree=de0084a9…）。详情见 [R1371](../程序/tasks_round/tasks_round_1371_result.md)。

## 2026-10-12：R1335 并入 master（阶段④分集增量上下文）
- 分支 `codex/episode-incremental-context` 已合入 master。`script_contract.split_script_episodes`＋分集账本 `write_dir(project,'script')/剧本分集增量账本.json`（每集 sha256＋based_on 其余集快照）；`writing_api.reply()` 前注入「只贴改动集正文」、唯一发布点 `_save_formal_script()` 后更新账本；`workflow_tasks._episode_change_notice()` 只给本地 Agent 报集号；首次／无账本退化为全量。见 [R1335](../程序/tasks_round/tasks_round_1335_result.md)。
- 未改 `skills/01 剧本准备SKILL/pipeline-script-preparation.skill.md` 与 `structure_script()` 场次解析。
## 2026-10-12：O43 完成（历史）
- O43 = R1370（检查点版本化＋只读恢复预览）；全量 4899/4899、0 红、963.97 秒（凭据 round=1370、tree=4a7be90a…）。详情见 [R1370](../程序/tasks_round/tasks_round_1370_result.md)。

## 2026-10-12：O40 完成（历史）

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O40 已完成（见上一节）。
- O40（项目管理、备份与清理统一空间和恢复说明）：`projects.py`（L2）新增 `_drop_registration_entry`（登记移出索引一律先改 deepcopy、发布成功才提交 `self.info`；`OSError` 时内存回退到磁盘事实并带 `ui_message` 重抛），`delete`／`unlink_registered_project`／`clear_missing_registration` 三条删除／清除路径统一改走它，删除路径在登记写失败时给出「内容已移入回收站、点『重新查找项目』或『重建项目索引』、仍可从回收站恢复」的定向指引；新增模块级 `_discover_candidates`（把 `reconcile_missing` 的一级目录扫描抽出复用、行为不变）与 `Projects.rebuild_registry`（按磁盘事实保留仍在的登记、移除失效登记、补登新目录；无变化不写盘；只读写一级目录与登记文件，不移动也不删除任何项目内容，回收站永不回流）。`desktop.py`（L4）新增 `Desktop.rebuild_project_index` 与主页「重建项目索引」按钮，主页状态栏与删除确认框把清屏／删历史／移入回收站／永久清除／可再生缓存分开表述（移入回收站＝可恢复、不是永久清除、同盘回收不等于释放空间）。见 [R1367](../程序/tasks_round/tasks_round_1367_result.md)。
- 契约变化：删除／清除路径的登记写失败不再让内存先显示成「已删除」（内存与磁盘登记都停在删除前状态）；新增 L2 公开方法 `rebuild_registry`（返回 `{kept,dropped,added,changed}`）；「永久清除」只做界面单独明示，**未新增任何永久删除入口**（`projects.py` 只回收，无 `rmtree`／`unlink()`）；「从备份恢复」本轮按「项目库回收站即删除前可恢复副本」实现与验证，未新建独立备份子系统。
- 验证证据：新增 `tests/test_project_recovery.py` 8/8；定向 `-k projects project_ backup recovery reconcile desktop storage recycle` 149/149；架构 `--layer architecture --all` 312/312；默认冒烟 `smoke_test.py` 8/8；0 红。
- 全量：1367−1364=3<5 无五轮欠账，但改动命中 §5（项目删除语义），收口在干净 master 工作树 `o40-fullsafe-master` 跑 `--all --safe`：第 1 次为新工作树环境未就绪（缺 4 个嵌套仓库与 3 个忽略运行文件）假红，补齐后定向修绿，第 2 次 4859/4859、0 红、527.6 秒，凭据 round=1367、tree=1d7630f1（＝`HEAD:程序`），`last_full_safe_all_round=1367`。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`、`.codex/`、`.agent-handoff/archive/`、`程序/outputs/`、`程序/配置/宠物/配置.json`，不读取、不修改、不暂存、不覆盖；提交只点名自己的路径，绝不 `git add -A`。
- 干净 master 工作树：`o07-fullsafe-master`（与主树共享 git common dir；勿动 `o06-fullsafe*` 等）；领号／全量前先 `git reset --hard HEAD`。
- 轮次：O40 为 R1367、O41 为 R1368；`project_status.md` 的 `当前轮次` 已改为 1369（＝最新结果报告号＋1）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟 `smoke_test.py`；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`），并先查 `full-safe-receipts.json` 有无 7 天内同 `HEAD:程序` 内容树绿凭据可复用，只有命中 §5（启动路径／Tk 控件生命周期／删除语义／层级登记表）才强制重跑；全量失败先按定位文件定向修绿、只复验一次（报告写「第 N 次全量」，2 次仍不过就升级单独修复轮）；`test_desktop_startup_perf`／`test_perf_baseline` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
