# R4467 结果：L3-W1 锁定基线和契约（docs-only 只读盘点收尾轮）
<!-- round-evidence: {"commit_base": "f7c27bb8f", "credential_hits": 0, "evidence_sha256": "d4fe8d0f0a59c3ef", "exit": 0, "failed": 0, "passed": 60, "round": 4467, "tests": "run_selftests.py -k stage_completion_service skill_orchestrator_completion delivery_scope"} -->

## 一、开头三问

1. **本轮属于 §3 哪种类型？** §3.5 只读诊断／盘点轮的文档化变体：零改动 `.py`、测试、配置、`project_status.md`；只新增本结果文件、勾选任务书 W1 行，提交门禁自动生成 `tasks_round/evidence/R4467.json`。
2. **测试跑了吗、三个基线过了吗？** 本轮按卡面只跑两条验收命令，均退出码 0：定向单测 `run_selftests.py -k stage_completion_service skill_orchestrator_completion delivery_scope`（3 个测试文件、共 60 条用例、6.7 秒、0 个文件有红、`ALL TESTS PASSED`）；架构门禁 `smoke_test.py --architecture`（`Ran 708 tests in 370.920s`、`OK`、`✅ 架构治理测试：tests/architecture`）。默认冒烟 `smoke_test.py` 未跑（docs-only 轮，§5 只读诊断默认不跑）；全量 `run_selftests.py --all --safe` 未跑（不在本轮范围）。
3. **欠账少了吗？** 未减少代码欠账；本轮把 L3-W1 的基线冻结、13 阶段入口、L0–L5 真实符号与直接测试锚点、三类验收样本固定为可验收证据，并逐条闭环 N554/N636/N637 六项历史退回问题。W2–W6 仍待执行。

## 二、基线冻结

采样时点：2026-11-25（会话系统日期；会话内命令按文序实跑；`date`/`Get-Date` 不在本车道 exec 白名单前缀内，时钟未独立核实，记为未核实项见 §八）。

- 工作树分支：`codex/l3-w1-clean`（`git rev-parse --abbrev-ref HEAD`，退出码 0）。
- 开工 `git status --porcelain`：无输出（退出码 0），工作树干净。
- **HEAD（双 SHA 之一）**：完整 `f7c27bb8f408d79fd45e86dcbcda9fe1bb83ca13`，短 `f7c27bb8f`（`git rev-parse HEAD`，退出码 0）＝卡面基准版本，即 R4465「合入 codex/git-lock-g0 到 master」提交。
- **master（双 SHA 之二）**：完整 `1e569a9ea873a88299c7e71238b4616d5b1b5851`，短 `1e569a9ea`（`git rev-parse master`，退出码 0）＝ R4466「合入 codex/doc-s03-sections 到 master」提交。
- **两 SHA 关系**：HEAD 与 master 不一致——本车道自 `f7c27bb8f`（R4465）拉出后，主干前进了 2 个提交：`af52a97d4`（R4464 DOC-S03 阶段文件补接口与交互两节）与 `1e569a9ea`（R4466 合并轮）；`f7c27bb8f` 出现在 `git log --oneline -n 12 master` 第 3 位，即 HEAD 是 master 的祖先（`master = HEAD + 2 commits`）。落后部分为 S03 阶段文档合入，与本卡允许文件（任务书、`tasks_round_*_result.md`、`evidence/`）零重叠。
- **A12 合入状态**：已合入。`git log --oneline --grep=A12 -n 20`（HEAD）命中 `0e2b7e729 R3719: A12资源与恢复缺口修复收尾审计` 与 `fbb56c295 A12 整合检查点：压缩 R3653-R3713 历史`；`git log --oneline master..0e2b7e729` 无输出（退出码 0），A12 顶点已在 master。
- **L2M 合入状态**：未合入。`git log --oneline master..76a00981d` 列出 11 个未合入提交（退出码 0）：`76a00981d`（R3579 REQ-L2M 十三阶段验收行为矩阵）、`c19582ae6`（R3433）、`e3ee00676`（R3432）、`196c87679`（R3426）、`a60823750`（R3422）、`e376eac14`（R3420）、`4c988a0bd`（R3418）、`dc18fdfc0`（R3410）、`f33d28d50`（R3399）、`e4c855790`（R3397）、`d7e7aa09a`（R3394 L2企业级成熟度评估与升级任务书）。`git ls-files tests/test_l2m_operation_wiring.py` 无输出（退出码 0），master 仍无该用例。
- **主干现状**：任务书 §「当前依据与任务归属」登记的审查基线为桌面 master `86e863bb`；当前 master 已前进至 `1e569a9ea`，任务书口径仍以 L3 拆分／受理／并发／取消／恢复／终态汇总为范围，W1 仅承接仍存在的差额。

### 在途负责人与重叠文件（卡面快照 2026-11-25 15:00 UTC+8，时点事实非永久事实）

| 车道／任务 | 负责人 | 快照中的改动 | 与本卡允许文件是否重叠 |
|---|---|---|---|
| `codex/lock-liveness-p0`（LOCK-LIVENESS-P0） | Devin | `selftest_env`／`commit_round`／`test_selftest_lock_liveness`／全量锁任务书 | 否 |
| `codex/ux-chat-input-extras`（UX-CHAT-INPUT-EXTRAS，并发 fast 窗口） | — | 共享输入框／extras／`_layers`／覆盖率基线 | 否 |
| `codex/doc-s03-sections`（DOC-S03，正在合入 master） | — | S03 阶段文档 | 否；且已于开工前合入（master 顶点 `1e569a9ea` 即其合并轮） |
| `codex/doc-s04-sections`（DOC-S04，正在合入 master） | — | S04 阶段文档 | 否 |

领号：`..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` 输出 `4467`（退出码 0），本轮结果文件即 R4467。

## 三、13 阶段入口标记表

权威阶段顺序：`contract/pet_bus.py:19-23`（`STAGES` 13 项、`STAGE_NAMES`）。统一启动口径：`orchestrator/stage_handler_registry.py:104-153`（`start()`，AGENTS 硬约束 17「阶段启动唯一入口」）；手动按钮文案 `orchestrator/stage_flow.py:27-33`（`MANUAL_LABELS`）；恢复提示 `stage_flow.py:35-49`（`RECOVERY_HINTS`，13 项全登记）；依赖图 `stage_flow.py:61-65`（`DEPENDS`）；自动队长 `stage_flow.py:398`（`class Auto`）与 `stage_flow.py:516`（`AUTO = Auto()`）；自动化档位 `stage_flow.py:71`（`AUTO_LEVELS=('semi','auto')`）；付费阶段 `stage_flow.py:77`（`PAID_STAGES=('assets','video','audio')`）；未勾选跳过 `stage_flow.py:242`（`unchecked`）；呈现指令 `stage_handler_registry.py:14-17`（`StagePresentation`），由 `desktop.py:157`（`_present_stage`）承接。

| 阶段 | 手动入口 | 自动入口 | 恢复／续跑入口 | 适用性与缺口归属 |
|---|---|---|---|---|
| `script` 剧本准备 | 页面输入链＋`MANUAL_LABELS['script']='手动制作剧本'`（`stage_flow.py:27`）；剧本落盘后 `script_downloaded()` 核验并发完成（`ui/pet_ui_stages.py:1117`）；`stage_handler_registry.py:28` 对手动 script 免制作锁门禁 | `PetBridgeMixin.pet_start('script')` → `start(trigger='auto')`（`ui/desktop_pet_bridge.py:54-66`）；fallback → `stage_run_action(unattended=True)`（`ui/pet_ui_stages.py:16-18`）；自动链 `Auto` 按 `script.completed` 起步 | `RECOVERY_HINTS['script']`（`stage_flow.py:36`）；`script.completed` 事件契约（`contract/pet_bus.py:55`）；`Auto` 按 `DONE_STATES` 跳过已完成（`stage_flow.py:74`）；`preparation_progress()` 只读诊断（`orchestrator/stage_completion_service.py:594`） | 有入口；剧本内容须用户确认，自动链不替代内容确认。缺口：无 |
| `script_structure` 剧本结构 | `MANUAL_LABELS['script_structure']='手动制作结构剧本'`（`stage_flow.py:27`）；`stage_models.manual_command()`（`orchestrator/stage_models.py:346-363`）→ `stage_exec.run/show()` → `_run_script_structure()` 本地规则提取／校验／写正稿（`orchestrator/stage_exec.py:32-81,129-148`） | `pet_start` → registry；`_execute_unattended_stage()` 直接派 `pet_script_structure_batch(trigger)`（`ui/desktop_pet_bridge.py:71-76`） | `RECOVERY_HINTS['script_structure']`（`stage_flow.py:37`）；写正稿走 `script_contract.write_structured_script()`（`contract/script_contract.py:822`），由 `tests/architecture/test_structured_script_write_boundary.py:33-48` 守「stage_exec 必须委托契约发布」 | 有入口；本地规则链不调用模型（`stage_exec.py:84` 同口径注释见 delivery 分支，structure 分支 :32-81 无模型调用）。缺口：无 |
| `storyboard` 初步分镜 | `pet_storyboard_batch(trigger='manual')` → `start()`（`ui/desktop_pet_bridge.py:94-103`）；registry 特判 `_start_storyboard()` 返回 `OPEN_STORYBOARD`/`REPORT_STORYBOARD`（`stage_handler_registry.py:50-68,123-124`）；S03 手动发送 `start_storyboard_send()`（`desktop_pet_bridge.py:105-117`） | `pet_start('storyboard')` → `trigger='auto'`；工作计划由 `orchestrator/storyboard_plan_service.py:25`（`storyboard_work_plan`）产出；`StagePresentation` 由 `desktop._present_stage`（`desktop.py:157-175`）呈现 | `RECOVERY_HINTS['storyboard']`（`stage_flow.py:38`）；自动采用 `poll_auto_adopt()`（`ui/desktop_auto_flows.py:356`）；采用判定 `domain/storyboard_adoption_service.py:4`（`automatic_poll_decision`） | 有入口；分镜产物须采用后才算完成。缺口：无 |
| `animatic` 分镜预演 | `MANUAL_LABELS['animatic']='手动制作分镜预演'`（`stage_flow.py:28`）；registry 对 animatic 固定返回 `SHOW_ANIMATIC`＋人工确认文案（`stage_handler_registry.py:125-128`） | `pet_start('animatic')` → registry；自动档只引导到预演页，不自动确认节奏 | `RECOVERY_HINTS['animatic']`（`stage_flow.py:39`）；上游就绪判据 `animatic_input_ready/animatic_ready`（`orchestrator/stage_parallel.py:667-689`） | 有入口但强人工确认；自动链不越过确认。缺口：无 |
| `assets` 资产管理 | `MANUAL_LABELS['assets']='手动制作资产'`（`stage_flow.py:29`）；生产模型 `assets_choices()`（`orchestrator/stage_models.py:45-48`）、`manual_command()` 外套 | `pet_start('assets')` → registry；未勾选 SKILL 走 `skip_unchecked`（`stage_handler_registry.py:114-121`，`ui/pet_ui_stages.py:34-56`）；无人值守 `poll_auto_asset()`（`ui/desktop_auto_flows.py:523`） | `RECOVERY_HINTS['assets']`（`stage_flow.py:40`）；`PAID_STAGES` 含 `assets`（`stage_flow.py:77`），半自动档先付费确认；`domain/asset_resume` 续跑台账 | 有入口；付费阶段，半自动档需用户确认。缺口：无 |
| `continuity` 连贯性清单 | `MANUAL_LABELS['continuity']='手动生成连贯性清单'`（`stage_flow.py:30`）；`_execute_unattended_stage()` 直接调 `pet_continuity_ledger()`（`ui/desktop_pet_bridge.py:77-78`） | `pet_start('continuity')` → registry → fallback 同上 | `RECOVERY_HINTS['continuity']`（`stage_flow.py:41`）注明可选、建议、不阻塞 SG-02；清单可重新生成 | 有入口；定位为可选审计而非硬门禁。缺口：无 |
| `final` 分镜定稿 | `MANUAL_LABELS['final']='手动同步资产'`（`stage_flow.py:31`）；`stage_flow.blockers()`（`stage_flow.py:301`）按 `DEPENDS`/`stage_parallel.blocked_stages()` 拦截 | `pet_start('final')` → registry；`poll_auto_final()` 需 `pet.should_auto_run('final')` 且无制作批次占用（`ui/desktop_auto_flows.py:324`） | `RECOVERY_HINTS['final']`（`stage_flow.py:42`）；定稿判定 `domain/final_service.py:4`（`automatic_finalize_decision`） | 有入口；定稿移动工作稿，占用检测是关键恢复约束。缺口：无 |
| `keyframe` 首帧管理 | `MANUAL_LABELS['keyframe']='手动制作首帧'`（`stage_flow.py:31`）；生产模型 `keyframe_choices()`（`orchestrator/stage_models.py:51-74`） | `pet_start('keyframe')` → registry；`_execute_unattended_stage()` 直接派 `pet_frame_batch(trigger)`（`ui/desktop_pet_bridge.py:79-80`）；补缺口 `poll_auto_keyframe()`（`ui/desktop_auto_flows.py:438`） | `RECOVERY_HINTS['keyframe']`（`stage_flow.py:43`）只重试失败项、保留已采用；轮询判定 `domain/keyframe_batch.py:20`（`automatic_poll_decision`）；完成后 `emit_verified_completion` 落 `frames.json` 清单（`stage_completion_service.py:869-873,879`） | 有入口；本地 ComfyUI 与云端首帧分路。缺口：无 |
| `previs` 白模预演 | `MANUAL_LABELS['previs']='手动制作白模'`（`stage_flow.py:31`） | `pet_start('previs')` → registry；`poll_auto_previs()` 只对复杂动作自动派发，中等动作只提示（`ui/desktop_auto_flows.py:461`）；`orchestrator/previs_automation.py:88`（`start`） | `RECOVERY_HINTS['previs']`（`stage_flow.py:44`）；证据发布 `record_previs_evidence()`（`stage_execution_service.py:694`）；`emit_verified_completion` 落 `previs.json` 清单（`stage_completion_service.py:869-873`） | 有入口；自动只覆盖复杂动作子集。缺口：无 |
| `video` 视频生成 | `MANUAL_LABELS['video']='手动制作视频'`（`stage_flow.py:32`） | `pet_start('video')` → registry；`poll_auto_video()` 仅本地 `LocalStudio` 自动补齐，云端视频仍由页面／付费路径触发（`ui/desktop_auto_flows.py:576`） | `RECOVERY_HINTS['video']`（`stage_flow.py:45`）先查询未知任务再重试；`PAID_STAGES` 含 `video`（`stage_flow.py:77`）；`CONFIG['video']` 带 `rate_limit`（`orchestrator/stage_parallel.py:78-81`） | 有入口；云端付费视频不自动发起。缺口：无 |
| `audio` 配音与字幕 | `MANUAL_LABELS['audio']='手动制作配音'`（`stage_flow.py:32`） | `pet_start('audio')` → registry；`poll_auto_*` 清单（`desktop_auto_flows.py:324-614`：final/adopt/edit/keyframe/previs/asset/video/handoff）中无 `poll_auto_audio`，自动链主要靠完成事件与人工确认推进 | `RECOVERY_HINTS['audio']`（`stage_flow.py:46`）；`PAID_STAGES` 含 `audio`（`stage_flow.py:77`）；`confirm_media_completion()` 要求人工确认（`stage_completion_service.py:167-186`，测试覆盖 audio 分支 `test_stage_completion_service.py:475-526`）；未知回执释放 `domain/tts_api.py:828`（`release_unknown`） | 有入口但强人工确认；无同级常驻无人值守轮询。缺口归 W4 生命周期／费用未知验证 |
| `edit` 后期剪辑 | `MANUAL_LABELS['edit']='手动制作剪辑'`（`stage_flow.py:32`）；edit 经 SKILL 编排／页面，`stage_exec` 无专属程序化分支（`stage_exec.py:142-148` 只特判 script_structure/delivery） | `pet_start('edit')` → registry；`poll_auto_edit()` 全部镜头验收后自动粗剪一次（`ui/desktop_auto_flows.py:402`） | `RECOVERY_HINTS['edit']`（`stage_flow.py:47`）；粗剪判定 `domain/edit_service.py:55`（`automatic_assemble_decision`） | 有入口；自动只做粗剪合成，不做全部后期。缺口：无 |
| `delivery` 质检与交付 | `MANUAL_LABELS['delivery']='手动制作交付'`（`stage_flow.py:33`）；`stage_exec._run_delivery()` 四步程序化核验→打包→报告→清单（`orchestrator/stage_exec.py:83-107`） | `pet_start('delivery')` → registry；依赖 edit 完成与人工确认；`CONFIG['delivery']` 并行检查项 `on_exhaust=ON_REPORT`（`stage_parallel.py:88-90`） | `RECOVERY_HINTS['delivery']`（`stage_flow.py:48`）；`delivery_record/package_delivery/publish_delivery_report` 只读已确认且有效清单（`stage_completion_service.py:189-228`） | 有入口；交付完成必须人工确认，商用授权与内容审查单独完成。缺口：无 |

## 四、L0–L5 真实符号、路径、分层与直接测试锚点

说明：实体已包化到 `contract/`（L0）、`infra/`（L1）、`domain/`（L2）、`orchestrator/`（L3）、`ui/`＋`desktop.py`（L4）、`app_shortcut.py`／`desktop_launcher.py`（L5）；`程序/` 根下同名 `.py` 为 `sys.modules` 转发 facade（实证：`stage_models.py:1-3`、`desktop_automation_service.py:1-10`、`pet_bus.py:6-37`）。分层一律以 `tests/architecture/_layers.py` 的 `_register` 登记为准（`LAYER_NAMES` 见 `_layers.py:4-5`）；登记键与真实文件的解析规则由 `test_layers.py:507-520` 断言（实体 `.py` ∨ `TOOLS` ∨ 历史名称台账）。下表「登记」列为 `_layers.py` 行号；测试锚点逐条经 `git ls-files tests/` 命中核实，未命中的如实标注。

| 层 | `_layers.py` 登记 | 真实文件 · 符号（行号） | 用途 | 直接测试锚点（`git ls-files tests/` 核实） |
|---|---|---|---|---|
| L0 | :22 `contract`、:38 扁平键 | `contract/pet_bus.py` · `STAGES/STAGE_NAMES:19-23`、`CONTRACT:48-69`、`STAGE_EVENTS/LIVE_EVENTS:70-73`、`SHEDDABLE_EVENTS:92`、`emit_safe:141` | 13 阶段唯一顺序、事件契约、幂等 run、背压让路 | `tests/test_pet_bus.py`、`tests/test_stage_flow.py`、`tests/architecture/test_dynamic_import_registry.py` |
| L0 | :38 | `contract/service_contract.py` · `ServiceResult` | L2 写服务四字段结果契约 | `tests/test_service_contract.py` |
| L0 | :38 | `contract/project_context.py` · `ProjectContext` | L3 注入项目上下文 | `tests/test_project_context.py` |
| L0 | :38 | `contract/stage_path_service.py` · `write_dir/read_dirs` | 阶段路径新写旧读 | `tests/test_stage_path_service.py` |
| L0 | :38 | `contract/script_contract.py` · `save_natural_script:61`、`structure_script:695`、`review_structured_script:764`、`revise_structured_script:813`、`write_structured_script:822`、`STAGE_LOCK_REQUIREMENTS:979`、`PRODUCTION_LOCK_DEFINITIONS:985`、`stage_lock_requirements:1041` | 剧本契约、原子发布、制作锁口径 | `tests/test_script_contract.py`、`tests/test_script_structure.py` |
| L0 | :38 | `contract/stage_layout.py` · `STAGES:36`、`validate_stage_contract:268` | 阶段目录契约与 `pet_bus.STAGES` 同序守卫 | `tests/architecture/test_layers.py`（登记一致性）；`tests/test_selfcheck.py`（`default_checks` 含 `_stage_contract_check`，`contract/selfcheck.py:105`） |
| L0 | :121 `diagnostics/selfcheck`、:124 `infra_errors` | `contract/diagnostics.py` · `Severity:18`、`StartupPhase:34`、`Diagnostic:45`；`contract/selfcheck.py` · `run:84`、`default_checks:139`；`contract/infra_errors.py` | 启动诊断类型、注入式自检、L1 技术异常层级 | `tests/test_selfcheck.py`、`tests/test_startup_selfcheck.py`、`tests/test_infra_errors.py`、`tests/architecture/test_infra_errors_boundary.py` |
| L0 | :38 | `contract/error_codes.py` | 错误码登记 | `tests/test_error_codes.py` |
| L1 | :23 `infra`、:43-45 扁平键 | `infra/executors.py` · `submit:283`、`CancelFlag:45`、`_VendorGate:79` | 命名有界执行器与供应商并发闸门 | `tests/test_executors.py` |
| L1 | :43 | `infra/file_cache.py` · `read_json:234`、`read_json_shared:238`、`read_text:258` | 正式 JSON 读缓存 | `tests/test_file_cache.py`、`tests/test_file_cache_bounds.py` |
| L1 | :34 `infra.storage_maintenance` | `infra/storage_maintenance.py` · `recycle_paths:315` | 用户可见删除／回收唯一边界 | `tests/test_publication_recovery.py`、`tests/test_files_panel.py`、`tests/test_storage.py` |
| L1 | —（`infra` 包 :23 覆盖） | `infra/job_store.py` · `JobStore:65`、`enqueue:104`、`note_attempt:165`、`checkpoint:186`、`reconcile:217` | 通用作业库与崩溃恢复对账 | `tests/test_job_store.py` |
| L1 | —（`infra` 包 :23 覆盖） | `infra/artifact_index.py` · `ArtifactIndex:84`、`register:108`、`set_state:161`、`duplicates:187`、`rebuild:202` | 产物索引与四态机 | `tests/test_artifact_index.py` |
| L1 | —（`infra` 包 :23 覆盖） | `infra/resources.py` · `snapshot:114`、`ensure_free:136`、`note_rate_limited:174` | 资源感知、磁盘与限流原语 | `tests/test_resources.py` |
| L1 | —（`infra` 包 :23 覆盖） | `infra/budget.py` · `check_amount:58`、`headroom:72`、`reserve:90`、`settle:112`、`cancel:117`、`summary:152` | 预算机制层 | `tests/test_budget.py` |
| L1 | :43 | `infra/workflow_process_registry.py` · `reserve_process_slot:198`、`register_supervised:383` | 子进程槽位与登记（容量相关） | `tests/test_workflow_process_registry.py` |
| L1 | :155 | `infra/unit_of_work.py` · `RollbackFailedError:75`；`infra/business_log.py` · `log_event`；`infra/idempotency.py` | 写事务、业务流水、幂等 | `tests/test_unit_of_work.py`、`tests/test_uow_write_paths.py`、`tests/test_business_log.py`；`infra/idempotency.py` 本轮 `git ls-files tests/`＋grep 未命中直接调用测试（如实记录，非「无守护」断言） |
| L2 | :29 `domain`、:46-53 扁平键 | `domain/confirm_gates.py` · `record:323`、`run:385` | 人工确认闸门 `pending/failed/applied` | `tests/test_confirm_gates.py`、`tests/test_confirm_gates_cache.py` |
| L2 | :52 | `domain/final_service.py` · `automatic_finalize_decision:4` | 自动定稿决策 | `tests/test_final_service.py` |
| L2 | :52 | `domain/edit_service.py` · `automatic_assemble_decision:55` | 自动粗剪决策 | `tests/test_edit_service.py` |
| L2 | :52 | `domain/storyboard_adoption_service.py` · `automatic_poll_decision:4` | 自动采用去重决策 | `tests/test_storyboard_adoption_service.py` |
| L2 | :49-50 | `domain/asset_batch_service.py` · `unattended_retry_decision:429` | 无人值守计划与重试判定 | `tests/test_assets.py:858-869`（`unattended_signature`/`unattended_retry_decision` 直接调用）、`tests/test_req_s05_anchors.py:211`（`current_model`）、`tests/test_uow_write_paths.py:16-94`（`rename_asset`/`import_asset_image`）；另有 `test_asset_versions/test_asset_rename_service/test_asset_image_*_service` 直接 import |
| L2 | :51 | `domain/keyframe_batch.py` · `automatic_poll_decision:20` | 首帧批次轮询判定 | `tests/test_keyframe_batch_plan.py`（:12 `import keyframe_batch as kb`，含 uncertain 尝试态用例）；`tests/test_keyframe_batch.py` 不存在（已核实，不误用） |
| L2 | :52 | `domain/previs_routing.py` · `automatic_notice:146` | 白模自动通知与签名 | `tests/test_previs.py:332-341`（`automatic_notice`/`automatic_signature`）、`tests/test_previs_scope.py:59-66,155-168`（`LEVELS/ROUTES/ready`）、`tests/test_req_s09_anchors.py:140-164`（`dispatch`） |
| L2 | :51 | `domain/tts_api.py` · `audio_kind:153`、`release_unknown:828` | TTS 种类判定、未知回执释放 | `tests/test_tts.py:920-933`（`release_unknown` 只重发已放开句）；`tests/test_tts_api.py` 不存在（已核实） |
| L2 | :52 | `domain/delivery_import_service.py` · `ALLOWED_SUFFIXES:11`、`import_final_master:15` | 外部成片导入校验 | `tests/test_delivery_import_service.py` |
| L2 | :46 | `domain/task_center_service.py` | 任务中心业务 | `tests/test_task_center.py` |
| L3 | :25 `orchestrator`、:79-80 扁平键 | `orchestrator/stage_handler_registry.py` · `start:104-153`、`_workflow_lock_error:20`、`_start_storyboard:50`、`StagePresentation:14`、`unchecked_skip_text:44`（顶层无同名 `.py`，实体唯一） | 三虎阶段启动唯一入口、制作锁门禁、分镜计划呈现 | `tests/test_stage_command_contract.py`（直接调 `stage_handler_registry.start`，:12,:22-29）；`tests/architecture/test_stage_command_contract.py:41-48`（L4→registry 入口静态守卫）；`tests/architecture/test_dynamic_import_registry.py:320-465`（`stage_handler_registry`/`orchestrator.stage_handler_registry` 均按 L3 审计） |
| L3 | :25、:59 扁平键 | `orchestrator/stage_flow.py` · `MANUAL_LABELS:27`、`RECOVERY_HINTS:35`、`DEPENDS:61`、`AUTO_LEVELS:71`、`PAID_STAGES:77`、`unchecked:242`、`blockers:301`、`Auto:398`、`AUTO:516` | 按钮状态、依赖门禁、自动推进队长、恢复提示 | `tests/test_stage_flow.py` |
| L3 | :25、:59 扁平键 | `orchestrator/stage_parallel.py` · `UNIT_NAMES:37`、`GLOBAL_LIMIT:46`、`CONFIG:50-91`、`Governor:252`、`shared:341`、`parallel_map:376`、`GATES:518`、`evaluate:927` | 13 阶段并行度／重试／全局并发 8、阶段门禁表 | `tests/test_stage_parallel.py`、`tests/architecture/test_pipeline_stage_io_contract.py:45-48` |
| L3 | :25、:60 扁平键 | `orchestrator/skill_orchestrator.py` · `DONE…MISSING:33`、`verified_stage_output:47`、`report_skill_completion:70`、`Orchestrator:181`、`execute:562`、`retry:849`、`default_orchestrator:897` | SKILL 校验、DAG 执行、完成核验出口 | `tests/test_skill_orchestrator_completion.py`（:41-140 端到端＋`failures/retry`）、`tests/test_skills.py`、`tests/test_critical_chains.py` |
| L3 | :25、:59 扁平键 | `orchestrator/stage_exec.py` · `_run_script_structure:32`、`_run_delivery:83`、`failures:113`、`progress_text:120`、`run:129`、`show:151` | 次级执行页与两条程序化阶段链 | 无专属 `tests/test_stage_exec.py`（`git ls-files` 未命中）；`failures`/`retry` 口径由 `tests/test_skill_orchestrator_completion.py:119-140` 直接覆盖，`run/show` 经 `tests/test_stage_command_contract.py` 与 `tests/test_manual_plan.py` 间接覆盖 |
| L3 | :25、:61 扁平键 | `stage_execution_service.py`（顶层实体，`orchestrator/` 下无同名） · `build_orchestrator:835`、`stage_context:844`、`record_stage_confirmation:633`、`adopt_asset_plan_choice:648`、`run_stage_confirmation_gate:677`、`record_previs_evidence:694`、`publish_stage_handoff_bundle:810`、`start_pet_performance_check:141`、`start_pet_test_check:161`；`publish_stage_text/bytes/bundle` 再导出自 `orchestrator/stage_publication.py`（`stage_execution_service.py:76-81`） | L3 对 L2 的发布器注入与阶段成果发布边界 | `tests/test_stage_execution_service.py`（:9 import `publish_stage_bundle/publish_stage_bytes/publish_stage_text`，:49-112 原子发布与索引回滚） |
| L3 | :25、:61-63 扁平键 | `orchestrator/stage_completion_service.py` · `media_output_folders:10`、`media_scope:24`、`media_manifest_path:41`、`prepare_media_completion:91`、`confirm_media_completion:167`、`delivery_record:189`、`package_delivery:202`、`publish_delivery_report:212`、`preparation_progress:594`、`completion_evidence:720`、`emit_verified_completion:864`、`publish_stage_manifest:879` | 产物核验、媒体人工确认、交付打包与报告、完成事件受控出口 | `tests/test_stage_completion_service.py`（:8-9 import 后 55 处直接调用）；`emit_verified_completion` 直接锚点 `tests/test_skill_orchestrator_completion.py`（REQ-S13-54 端到端），另直接调用见 `tests/test_req_s13_anchors.py:216-225`、`tests/test_req_s01_anchors.py:56-68`、`tests/test_req_anchor_s02.py:257-264`、`tests/test_preparation_monitor.py:182-210`、`tests/test_fault_injection_chain.py:91-111`；`package_delivery`/`publish_delivery_report` 直接锚点 `tests/test_delivery_scope.py:149-151` |
| L3 | :25、:59 扁平键 | `orchestrator/stage_models.py` · `assets_choices:45`、`keyframe_choices:51`、`plan:161`、`plan_window:236`、`open_config:255`、`before_manual:305`、`manual_command:346`、`production_choices:366`、`default_model:375`、`chosen:384`、`is_production:396`、`belongs_to_other_stage:402` | 「手动制作XX」精简窗、模型提醒、生产模型选择 | `manual_command` 直接 `tests/test_manual_gate.py:131-220`；`before_manual` 直接 `tests/test_manual_gate.py:63-127`、`tests/test_manual_plan.py`；`plan` 直接 `tests/test_manual_plan.py:61-88,267-274`；`production_choices`/`chosen`/`is_production` 本轮 `git ls-files tests/`＋grep 未命中直接调用（`tests/test_req_s08_anchors.py:297`、`tests/test_keyframe_model_service.py:5-16` 命中的是 `keyframe_model_service.production_choices`，不同符号）；`tests/test_stage_models.py` 不存在（已核实） |
| L3 | :25、:61 扁平键 | `orchestrator/desktop_automation_service.py` · `DesktopAutomationScheduler:36`、`BackgroundTaskQueue:119`、`PersistentBackgroundTaskQueue:171`、`BackgroundTaskLifecycle:387` | 无 Tk 定时调度、后台任务生命周期与持久队列 | `tests/test_desktop_automation_service.py` |
| L3 | :63 | `orchestrator/stage_publication.py` · `publish_stage_text/bytes/bundle`（经 `stage_execution_service.py:76-81` 再导出） | 阶段成果原子发布器 | `tests/test_stage_execution_service.py:9,49-112` |
| L3 | :62 | `orchestrator/storyboard_plan_service.py` · `storyboard_work_plan:25`、`build_work_plan` | 分镜工作计划 | `tests/test_storyboard_plan_service.py:6`、`tests/test_storyboard_scope.py:12,49` |
| L3 | :61 | `orchestrator/desktop_auto_state.py` · `PET_STAGE_POLL`、`UNATTENDED_SWITCH`、`UNATTENDED_NEXT`、`flow_get/flow_set`、`AutoState` | 无人值守轮询登记表与自动状态 | `tests/test_desktop_auto_state.py`、`tests/test_unattended_chain_tables.py:5-22`、`tests/test_sanhu_mode.py:14` |
| L4 | :26 `ui`、:64 扁平键 | `desktop.py` · `_present_stage:157`（`StagePresentation` import :151） | 阶段呈现指令承接 | `tests/test_stage_command_contract.py`、`tests/test_stage_flow.py` |
| L4 | :82 | `ui/desktop_pet_bridge.py` · `PetBridgeMixin:20`、`pet_start:54-66`、`_start_unattended_stage:67`、`_execute_unattended_stage:71-92`、`pet_storyboard_batch:94-103`、`start_storyboard_send:105`、`pet_advance:40-53` | 宠物启动桥接与无人值守派发 | `tests/test_stage_command_contract.py`（:13 import）、`tests/test_unattended_chain_tables.py:11-12` |
| L4 | :64 | `ui/pet_ui.py` · `Pet:353`、`StageQueue:193`、`watch_status:226`、`report_done:251`、`_emit:541`、`sync_errors:547` | 宠物核心、队列、状态装饰、事件转发 | `tests/test_pet_ui.py` |
| L4 | :82 | `ui/pet_ui_stages.py` · `stage_run_action:16`、`skip_unchecked:34`、`PetStagesMixin:58`、`_completion_evidence:60`、`_complete_if_verified:70`、`start_stage:299`、`generate:431`、`one_click:866`、`enter_stage:1082`、`script_downloaded:1117` | 阶段动作分发、跳过未勾选、产物核验完成 | `tests/test_stage_command_contract.py`（:15 import）、`tests/test_stage_flow.py`、`tests/test_pet_ui.py` |
| L4 | :82 | `ui/desktop_auto_flows.py` · `_tick_auto_*:105-317`、`poll_auto_final:324`、`poll_auto_adopt:356`、`poll_auto_edit:402`、`poll_auto_keyframe:438`、`poll_auto_previs:461`、`poll_auto_asset:523`、`poll_auto_video:576`、`poll_auto_handoff:614` | 各阶段无人值守轮询、签名去重、退避 | `tests/test_ui_edges_autopilot.py`（含 `previs_routing`/`previs_automation` patch 用例 :522-623） |
| L4 | :64 | `ui/ui_stage_popups.py` · `_show_stage_execution:50`、`_show_manual_plan:112`、`install_stage_presenters:161` | L4 呈现器注册，避免 L3 反向依赖 UI | `tests/architecture/test_dynamic_import_registry.py` |
| L5 | :65 `app_shortcut`、:91 `desktop_launcher` | `app_shortcut.py`、`desktop_launcher.py`、根目录 `启动漫剧制作助手.pyw`（`find` 命中） | 启动装配与快捷方式入口 | `tests/test_startup_selfcheck.py`、`tests/architecture/test_dynamic_import_registry.py`（L5 装配审计） |

## 五、三类验收样本

### 1. 有副作用的生成（assets／keyframe／previs／video）

- **入口链**：`PetBridgeMixin.pet_start(stage)` → `stage_handler_registry.start(trigger='auto', fallback=_start_unattended_stage, skip_action=skip_unchecked, run_action=stage_run_action)`（`ui/desktop_pet_bridge.py:54-66`）→ `stage_run_action(unattended=True)` → `desktop._execute_unattended_stage()`（`ui/pet_ui_stages.py:16-18` → `ui/desktop_pet_bridge.py:71-92`）：keyframe 直派 `pet_frame_batch`（:79-80），其余经 `PET_STAGE_POLL` 打开无人值守开关＋`pet_advance`（:81-92），再由 `poll_auto_asset/keyframe/previs/video`（`ui/desktop_auto_flows.py:523/438/461/576`）续跑。
- **并发与重试**：`stage_parallel.CONFIG`（`orchestrator/stage_parallel.py:50-91`）按阶段给 unit/min/max/limit/retry；全局 `GLOBAL_LIMIT=8`（:46）、`Governor`（:252）、`parallel_map`（:376）。
- **完成判定**：不凭返回值——`stage_completion_service.completion_evidence`（:720）读磁盘证据，`emit_verified_completion`（:864-876）核验通过才发 `stage.completed`，并对 keyframe/previs 先落清单（:869-873、`publish_stage_manifest:879`）。
- **测试锚点**：`tests/test_skill_orchestrator_completion.py`（无界面恰好一条 `stage.completed` 且 `run=1`）；`tests/test_keyframe_batch_plan.py`（只补缺失／重试失败／uncertain 态）；`tests/test_ui_edges_autopilot.py`（无人值守轮询签名去重）。
- **样本结论**：生成类入口存在；「已受理」「已执行」「已采用」是三件事，部分受理与重复提交属 W2，未知回执处置属 W4（`tts_api.release_unknown:828` 与 `video` `RECOVERY_HINTS` 先查后重试已是既有口径）。

### 2. 纯本地操作（script_structure／delivery）

- **入口链**：`stage_exec.run()`（`orchestrator/stage_exec.py:129-148`）特判两支：`script_structure` → `_run_script_structure()`（:32-81，`script_contract.structure_script/review_structured_script/revise_structured_script/write_structured_script` 本地规则链）；`delivery` → `_run_delivery()`（:83-107，注释明确「不调用模型」，四步 `delivery_record`→`package_delivery`→`publish_delivery_report`→写清单）。
- **判定点**：`stage_flow.blockers()`（:301）只读状态与门禁；`stage_parallel.CONFIG` 两支均 `limit:1`（:54-56,:88-90 中 script_structure limit 1、delivery CHECK 并行检查项）。
- **测试锚点**：`tests/test_delivery_scope.py:149-151`（`publish_delivery_report`/`package_delivery` 直接调用）；`tests/architecture/test_structured_script_write_boundary.py:33-48`（`stage_exec` 必须委托 `script_contract.write_structured_script`，不得直接发布）。
- **样本结论**：纯本地链路已有程序化入口；其完成仍需阶段产物核验，不把「函数跑完」当完成。

### 3. 人工确认（manual_command／confirm_media_completion／adopt_asset_plan_choice／animatic）

- **入口链**：`stage_models.manual_command()`（`orchestrator/stage_models.py:346-363`）先 `plan()`（:161）弹精简窗、`before_manual()`（:305）拦模型未配，闸放行才执行；`confirm_media_completion()`（`orchestrator/stage_completion_service.py:167-186`）只把 `prepare_media_completion()`（:91）生成的 `pending_review` 写成 `status='complete', reviewed=True`；`adopt_asset_plan_choice()`（`stage_execution_service.py:648`）记 `pending→applied/failed`；`animatic` 自动入口固定回 `SHOW_ANIMATIC`＋人工确认文案（`stage_handler_registry.py:125-128`）。
- **测试锚点**：`tests/test_manual_gate.py:131-220`（manual_command 三去处）、`tests/test_manual_plan.py:61-88,267-274`（plan）；`tests/test_stage_completion_service.py:101-214`（confirm_media_completion 逐阶段）。
- **样本结论**：人工确认边界真实存在且多点；W5 核对接口时须保持「确认动作」与「产物核验」分离。

## 六、N554/N636/N637 六项历史问题逐条自检

| # | 历史问题 | 本轮闭环证据 | 结论 |
|---|---|---|---|
| P1-1（N636） | 主干冻结双 SHA＋采样时间＋A12/L2M 合入实证 | §二记录 `git rev-parse HEAD`=`f7c27bb8f408d79fd45e86dcbcda9fe1bb83ca13`（短 `f7c27bb8f`）与 `git rev-parse master`=`1e569a9ea873a88299c7e71238b4616d5b1b5851`（短 `1e569a9ea`）、采样时点 2026-11-25、两 SHA 真实关系（HEAD 为 master 祖先、落后 2 个 DOC-S03 提交）；A12 经 `git log --oneline master..0e2b7e729`（无输出）核实已合入；L2M 经 `git log --oneline master..76a00981d`（11 个提交）核实未合入 | 已闭环；两 SHA 不一致已如实说明而非照抄「两者一致」 |
| P1-2（N636） | L0–L5 以 `_layers.py` 真实登记与真实路径为准 | §四逐行引用 `_layers.py` 登记行；`stage_completion_service`（orchestrator 实体）与 `stage_models`（orchestrator 实体）均 L3：`orchestrator` 包 :25 ＋ 顶层兼容键 :59-63，未写为 L2/domain 或 L4；facade 转发关系实证 `stage_models.py:1-3`、`desktop_automation_service.py:1-10` | 已闭环 |
| P1-3（N637） | `git ls-files tests/` 逐一核实直接测试，不误标「无守护」 | §四每个锚点经 `git ls-files tests/`＋tests/ grep 双向核实：曾被误标的 `tests/test_script_contract.py`、`tests/test_selfcheck.py`、`tests/test_file_cache.py`、`tests/test_desktop_automation_service.py`、`tests/test_tts.py` 全部命中（verbatim 输出见 §七）；另核实 `test_keyframe_batch_plan.py`、`test_assets.py`、`test_previs.py`、`test_previs_scope.py`、`test_storyboard_plan_service.py`、`test_desktop_auto_state.py`、`test_business_log.py` 均存在并被引用；不存在项（`test_stage_exec.py`/`test_stage_models.py`/`test_tts_api.py`/`test_keyframe_batch.py`/`test_l2m_operation_wiring.py`）写明「不存在（已核实）」而非「无守护」 | 已闭环 |
| P1-4（N637） | 修正直接测试锚点 | `emit_verified_completion` 直接测试锚点＝`tests/test_skill_orchestrator_completion.py`（REQ-S13-54，端到端恰好一条 `stage.completed`），并附 `test_req_s13_anchors.py:216-225` 等直接调用；`package_delivery`/`publish_delivery_report` 直接锚点＝`tests/test_delivery_scope.py:149-151`，并列 `tests/test_stage_completion_service.py`（覆盖 prepare/confirm/completion_evidence/media_scope/media_manifest_path） | 已闭环 |
| P1-5（N637） | 落盘真实测试/架构门禁证据到 `evidence/R<N>.json` | 提交命令带 `--tests stage_completion_service skill_orchestrator_completion delivery_scope`，由 `scripts/commit_round.py`→`round_evidence.write_evidence` 自跑 `run_selftests.py -k` 并生成非空 `tasks_round/evidence/R4467.json`（`judge` 要求 passed>0 才放行）；`smoke_test.py --architecture` 独立运行完整退出码、用例总数 708、耗时 370.920s 与尾部原文逐字粘贴于 §七 | 已闭环（提交后 evidence 落盘在最终完成报告中核验） |
| P2（N554） | 严禁「应无输出/见收尾/应显示/提交后补」等占位符 | 全文只写会话内已实跑并观察到的命令输出；提交后 `git status`/`git log` 只出现在会话完成报告，不进本文件 | 已闭环 |

## 七、验证记录（全部为会话内实跑原样）

| 命令（工作目录见注） | 退出码 | 关键输出原文 |
|---|---:|---|
| `git rev-parse --abbrev-ref HEAD`（工作树根） | 0 | `codex/l3-w1-clean` |
| `git rev-parse HEAD`（工作树根） | 0 | `f7c27bb8f408d79fd45e86dcbcda9fe1bb83ca13` |
| `git rev-parse master`（工作树根） | 0 | `1e569a9ea873a88299c7e71238b4616d5b1b5851` |
| `git status --porcelain`（工作树根，开工） | 0 | 无输出 |
| `git log --oneline --grep=A12 -n 20`（工作树根） | 0 | `0e2b7e729 R3719: A12资源与恢复缺口修复收尾审计`、`fbb56c295 A12 整合检查点：压缩 R3653-R3713 历史` |
| `git log --oneline master..0e2b7e729` | 0 | 无输出（A12 已合入） |
| `git log --oneline master..76a00981d` | 0 | 列出 11 个未合入 L2M 提交（顶点 `76a00981d` R3579，含 R3394–R3579，见 §二） |
| `git ls-files tests/test_l2m_operation_wiring.py` | 0 | 无输出（master 无该用例） |
| `git ls-files tests/test_script_contract.py tests/test_selfcheck.py tests/test_file_cache.py tests/test_desktop_automation_service.py tests/test_tts.py tests/test_delivery_scope.py tests/test_skill_orchestrator_completion.py tests/test_stage_completion_service.py` | 0 | `tests/test_delivery_scope.py`、`tests/test_desktop_automation_service.py`、`tests/test_file_cache.py`、`tests/test_script_contract.py`、`tests/test_selfcheck.py`、`tests/test_skill_orchestrator_completion.py`、`tests/test_stage_completion_service.py`、`tests/test_tts.py`（8 个全部命中） |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim`（`程序/`） | 0 | `4467` |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_completion_service skill_orchestrator_completion delivery_scope`（`程序/`） | 0 | 见下方尾部原文 |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（`程序/`） | 0 | 见下方尾部原文 |

定向单测输出尾部原文（逐字）：

```
IMPORT OK: all modules imported
定向：忽略增量台账，执行 3 个匹配测试文件
跑 3 个测试文件 / 6 路工作单元（8 路并行）
  test_skill_orchestrator_completion     5 条     0.6 秒
  test_delivery_scope           18 条     1.1 秒
申请跨树 GUI 令牌（最多等待 1800.0 秒）
  test_stage_completion_service#1     4 条     0.0 秒
  test_stage_completion_service#4     1 条     0.2 秒
  test_stage_completion_service#3    16 条     2.1 秒
  test_stage_completion_service#2    16 条     3.5 秒

共 60 条用例，6.7 秒；0 个文件有红
最慢 6 路工作单元：
  test_stage_completion_service#2    3.5 秒 / 16 条
  test_stage_completion_service#3    2.1 秒 / 16 条
  test_delivery_scope           1.1 秒 / 18 条
  test_skill_orchestrator_completion    0.6 秒 / 5 条
  test_stage_completion_service#4    0.2 秒 / 1 条
  test_stage_completion_service#1    0.0 秒 / 4 条
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新：D:\漫剧制作助手\.git\selftest-incremental.json
最近 5 轮自检中位基线：2.8 秒

ALL TESTS PASSED
```

架构门禁输出尾部原文（逐字）：

```
----------------------------------------------------------------------
Ran 708 tests in 370.920s

OK
✅ 架构治理测试：tests/architecture
```

## 八、未验证项与卡外发现

- 未运行默认冒烟 `smoke_test.py`、全量 `run_selftests.py --all --safe`（docs-only 轮按卡面与 §5 不跑；全量欠账以 `full-safe-receipts.json` 真实凭据为唯一权威，本轮未读未改）。
- 未逐行复读全部 L0–L5 模块；§四为「核心入口＋直接守护」清单，非全量导出清单。「未命中直接调用测试」表示本轮 `git ls-files tests/`＋tests/ grep 未定位直接调用，不代表无任何间接覆盖。
- 采样时钟未由白名单命令独立核实：`date`（Git Bash）与 `Get-Date` 不在本车道 `.devin/config.local.json` 放行前缀内（一次 `date` 调用被拒），故采样时间只记会话系统日期 2026-11-25。
- 在途快照来自卡面 2026-11-25 15:00 UTC+8；本轮未运行 `git worktree list` 或读取其他工作树状态。
- 卡外发现（只记录不修）：`audio` 无与 asset/keyframe/previs/edit 同级的常驻无人值守轮询（`poll_auto_*` 清单实证，`desktop_auto_flows.py:324-614`）；`stage_models.production_choices/chosen` 与 `infra/idempotency.py` 本轮未命中直接调用测试；`stage_parallel.parallel_map` 部分受理问题已由任务书登记，属 W2 不在本轮处理。
