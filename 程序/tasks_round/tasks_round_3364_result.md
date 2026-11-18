# R3364 结果：L0 契约层防崩溃与协议补齐任务书 · 轮 7B（完成事件出口与空项目 — 可靠性轮）
<!-- round-evidence: {"commit_base": "bea4b548", "credential_hits": 0, "evidence_sha256": "9eb163a4f48ab4d5", "exit": 0, "failed": 0, "passed": 41, "round": 3364, "tests": "run_selftests.py -k stage_completion skill_orchestrator"} -->

## 三问

1. **本轮类型**：§3.9 可靠性轮（任务书轮 7B，`L0契约层防崩溃与协议补齐任务书.md:694-708`）——改变阶段完成行为，先改 `REQ-`／`DES-` 再改码。范围：D10-0 只读重测、D10-a L3 完成出口、D10-b 空项目判完成、D10-c 无界面测试。
2. **测试跑了吗、三个基线过了吗**：跑了。先红后绿：新测试文件 `tests/test_skill_orchestrator_completion.py` 改动前 4 条用例 5 处断言全红（stash 验证），改动后全绿；定向 `run_selftests.py -k stage_completion skill_orchestrator completion_gate` 39 条 0 红；`smoke_test.py --affected stage_completion_service skill_orchestrator` 10/10 通过（门禁 48 秒 0 红）；默认冒烟 **9/9**（任务书基线写 8/8，本树实测 9 项全过）；`smoke_test.py --architecture` 532 条、唯一红 `test_round_number_continuous`（3234 != 3344，状态页滞后既有欠账，与 R3343 同一失败集合、与本改动无关）。全量 `--all --safe`：可靠性轮不在 §4.2 必跑清单，未跑；`full-safe-receipts.json` 未新增本轮凭据，如实记录。
3. **欠账少了吗**：少了——R3230 §3.6「L3 只认 script／script_structure 两阶段」、§3.7「`completion_evidence(None)` 判完成」两项已闭环；S13 审查文档「结构剧本两套口径」随统一核验入口顺带收敛。新增欠账：无（边界观察与未细化项见 §备注）。

## 任务与决策来源

- 任务书轮 7B：D10-0 只读重测 R3230 §3.6；D10-a 13 阶段完成事件由 L3 经 `stage_completion_service` 核验后发出、UI 出口保留靠幂等防重；D10-b `root is None` 不再判完成且先查依赖调用方；D10-c 无界面非剧本阶段恰好一条 `stage.completed`＋空项目自动链不推进。
- 诊断出处：`tasks_round_3230_result.md` §3.6／§3.7。
- 领号：`round_claim.py next` → **R3364**（worktree `dsh-5158b800-34ae`，分支 `codex/wip-R3259`；R3344–3363 已被其他车道领走，next 为权威口径）。

## D10-0 只读重测结论（与 R3230 一致，任务书无需更正）

- `emit_verified_completion` 生产调用方仍只有 `ui/pet_ui_stages.py` 两处（自动队列 `_complete_if_verified`、手动 `report_done`），另有测试调用；L3 `skill_orchestrator` 此前不经过它。
- `verified_stage_output()`（旧 `skill_orchestrator.py:47-63`）只认 `script`／`script_structure`，其余 11 阶段一律 False → SKILL DONE 后只发 `stage.paused`。
- `completion_evidence` 旧 `root is None` 分支返回 `(True, '')`（`stage_completion_service.py` 旧 :711-712）。

## 文档先行（先于代码落盘）

- `docs/stages/S13_质检与交付.md`：新增 **REQ-S13-54**（完成事件出口与空项目：13 阶段统一经 `emit_verified_completion` 核验、`root=None` 判未完成）＋ **DES-S13-54**（`verified_stage_output` 全阶段委托 `completion_evidence`、`_step_result` DONE 经 `report_skill_completion`→`emit_verified_completion`、无项目路径不落成当前目录、`with_current_run` 同 run 去重）＋测试锚定表加行。
- `docs/stages/S10_视频生成.md`：**REQ-S10-22／DES-S10-22** 改写——`video_ready` 回调优先；无回调时由「目录有任意媒体文件即算」升级为 `stage_completion_service.edit_ready_for_project` 只读核验（同一选版口径，页面未开也能判）。
- `docs/review/02_阶段完成判定.md`：文首加 R3364 更新段，标注第 9 条旁路、第 31 行 root 空行、第 38/57 行 video 行、建议跟进 1 的处置（原文为时点评审，保留历史行不改写）。

## 实现

| 文件 | 改动 |
| --- | --- |
| `orchestrator/stage_completion_service.py` | `completion_evidence`：`root is None` 由 `(True,'')` 改 `(False,'未打开项目，无法核验阶段成果')`（:736-739）；`stage=='video'` 分支重写（:789-797）：有 `video_ready` 回调照旧，否则调本模块新 `edit_ready_for_project(root)`（:705-727，只读 `config.json`/`episode_file_of`/`data/state.json`，逐镜走 `engine.edit_ready_rows` 内核），无镜头 JSON／无已采用版本／摘要不符均判未完成，不再退到通用媒体文件兜底。 |
| `orchestrator/engine.py` | 抽出 `edit_ready_rows(root,shots,state_shots)`（:230-250）作选版内核；`Studio.auto_edit_ready`（:645-）改为委托它，行为不变（`tests/test_integration.py` 27 条含指纹稳定性用例全绿）。 |
| `orchestrator/skill_orchestrator.py` | `verified_stage_output`（:47-66）：去掉两阶段白名单、加 `project in (None,'')` 与 `Path` 构造守卫（防 `Path('')` 落成当前目录），全部 13 阶段委托 `completion_evidence`；新增模块级 `report_skill_completion`（:70-82）封装 `emit_verified_completion`＋`with_current_run` 注入；`_step_result` DONE 分支（:625-660）：`script.completed` 门控不变，`stage.completed` 改经 `report_skill_completion` 发出，未通过发 `stage.paused` 并附核验原因；`output_verified` 只对 script／script_structure 预检（避免 video／媒体阶段双倍磁盘核验）。 |
| `desktop_shared_input.py` | `upstream_send_error`（:90-93）加 `project in (None,'')` 显式放行——「无项目放行」是该门禁自己的契约（简报门禁由宿主负责），不再靠 `completion_evidence(None)==True` 的副作用顺带放行。 |
| `ui/pet_ui_stages.py` | `_completion_evidence` docstring 同步新口径（无项目一律判未完成）；UI 完成路径零逻辑改动。 |
| `tests/test_skill_orchestrator_completion.py` | 新增 4 条 REQ-S13-54 用例（见 §测试）。 |
| `tests/test_stage_completion_service.py` | `test_missing_project_keeps_lightweight_host_compatible` → `test_req_s13_54_missing_project_is_never_complete`（13 阶段 × `None` 全判 False 且带原因，另断言 `''`）；`MediaCompletionTests` 新增 `test_req_s10_22_video_without_callback_reads_episode_and_state`（无回调核验：无版本→False→补已验收版本→True→改文件→False）。 |

## 「root 为空＝通过」调用方核查（D10-b 前置）

`completion_evidence` 全仓生产调用面：`ui/pet_ui_stages._completion_evidence`（`desktop.root`，无项目时原先会误判完成——本轮顺带封死）、`desktop_shared_input.upstream_send_error`（已加显式放行守卫，行为不变）、`skill_orchestrator.verified_stage_output`（已加空值守卫）。探针脚本 `维护记录/基准脚本/探针_阶段门禁端到端.py` 传真实项目路径，不受影响。`emit_verified_completion` 生产调用方仍只有 `pet_ui_stages` 两处（D10-0 复核）。未发现依赖「空 root 判完成」的合法调用方；轻量宿主（无项目）现在只是不发完成事件，符合「阶段状态不该由空项目推进」。

## 先红后绿证据（D10-c）

新测试文件改动前（`git stash` 只回退生产码，测试文件保留）实测：

```
FAIL: test_req_s13_54_empty_project_does_not_advance_auto_chain   # paused 原因无核验详情
FAIL: test_req_s13_54_headless_storyboard_emits_exactly_one_completed  # 0 条 stage.completed
FAIL: test_req_s13_54_no_project_context_never_completes (project='')
FAIL: test_req_s13_54_no_project_context_never_completes (project=None)
FAIL: test_req_s13_54_verified_stage_output_covers_all_stages     # storyboard 恒 False
Ran 4 tests — FAILED (failures=5)
```

改动后同文件 4 条全绿；`test_stage_completion_service` 35 条全绿（含新 REQ-S10-22／REQ-S13-54 用例）。

## 测试与验证证据

| 命令 | 结果 |
| --- | --- |
| `run_selftests.py -k stage_completion skill_orchestrator completion_gate` | 39 条用例 0 红（`test_stage_completion_service` 35＋`test_skill_orchestrator_completion` 4）；`tests.architecture.test_completion_gate` 另经 `python -m unittest` 直跑 2 条 ok（完成事件发送者依赖核验服务／UI·Agent 不得直发，均过） |
| `smoke_test.py --affected stage_completion_service skill_orchestrator` | 10/10 通过；门禁 `run_selftests.py --serial` 30 个测试文件 48 秒 0 红 |
| `smoke_test.py`（默认） | **9/9** 通过（任务书基线 8/8，本树实测 9 项检查全过） |
| `smoke_test.py --architecture` | 532 条，唯一红 `test_round_number_continuous`（`3234 != 3344`）：`project_status.md` 停在 R3233 合并轮、本分支未回合 master 状态页，R3343 同失败集合；仅 master 可提交该文件，本轮如实记录不修 |
| 直接补跑（engine 消费者与相邻契约） | `test_integration` 27、`test_video`＋`test_video_generation_scope`＋`test_video_manifest_scope`＋`test_req_s10_anchors` 71、`test_critical_chains`＋`test_resume_preview`＋`test_script_structure_scope`＋`UpstreamGateTests` 46、REQ 锚定批 65 —— 全绿 |
| `run_selftests.py --all --safe` | 未运行（§4.2 可靠性轮不要求；全量凭据未新增） |

## 问题与处置

1. **GUI 令牌排队**：多车道并行期间跨树 GUI 令牌长时间被占（单次等待 >1200 秒）。首次自加 `engine desktop_shared_input pet_ui_stages` 关键词的 `--affected`（74 文件）在 smoke 900 秒门禁超时——属环境性超时非测试红；随后按任务书原样 `--affected stage_completion_service skill_orchestrator`（30 文件）48 秒通过。engine 消费面另以直接 unittest 补跑（上表）。
2. **行数棘轮两红**：初版把 `edit_ready_for_project` 放进 `engine.py`（1005>1000）且 `_step_result` 内联核验调用使 `Orchestrator` 类 722>719。处置：`edit_ready_for_project` 下沉到 `stage_completion_service`（完成核验权威模块，语义更贴），`edit_ready_rows` 留 engine 供 `auto_edit_ready` 与无界面核验共用；L3 发事件收敛为模块级 `report_skill_completion`。复跑棘轮全绿，未抬任何上限。
3. **`test_round_number_continuous`**：改前改后同一失败（状态页轮次滞后），与本改动无关，见上表。

## 自主决策记录

- **L3 完成出口形态**：`stage.completed` 不再由 `_step_result` 直发 `emit_safe`，统一走 `emit_verified_completion`（规则 20／架构门禁「发送者须依赖核验服务」）。`script.completed` 自动链武装信号保持原位、先于 `stage.completed` 发出（与 UI `report_done` 的 before_emit 同序语义）。`stage.paused` 保留并附核验失败原因（比旧固定文案信息量更大，与 UI `_complete_if_verified` 的「待校验：detail」口径一致）。
- **video 无回调口径**：选「同选版口径只读核验」而非保留弱媒体兜底——REQ-S10-22 原文允许更弱口径但任务书要求空项目不判完成；`edit_ready_for_project` 不建 `Studio`、不写 `config.json`（`Studio.__init__` 的 `remember_episode` 会回写配置，无界面路径不能有此副作用）。UI 侧仍传 `studio.auto_edit_ready`，两条路径判据同一（`edit_ready_rows` 内核）。
- **REQ 落点**：完成事件出口属阶段完成判定，伞形 REQ/DES 放 S13（REQ-S13-54/DES-S13-54），视频无回调核验放 S10（改写既有 REQ-S10-22/DES-S10-22，不新增编号）；未给 S01–S09/S11–S12 各加重复条款——各阶段磁盘证据规则本身未变。
- **`output_verified` 收窄**：仅 script／script_structure 预检（这两段有 FAILED 翻转与 `script.completed` 门控的特殊语义）；其余阶段由 `emit_verified_completion` 一次核验，避免 video（逐镜哈希）／媒体（ffprobe）阶段双倍磁盘扫描。
- **同阶段多 SKILL 各发一次 `stage.completed`**：`begin_run` 按 SKILL 执行计 run，跨 run 同文不互吞（R4A 语义）——与旧 script 阶段行为一致；`Auto.done` 按 index 前进天然幂等，自动链不受影响。如需「一阶段一 run 只发一次」属新口径，超出本轮范围，记入欠账观察。

## 剩余欠账与边界观察

- 任务书 §3c-3「降级开关按族命名（skip/disable 的 GUI 等价物）」在任务书中标注「未细化／细化」，不在本轮 D10 任务表内，未做，留待任务书细化轮。
- `docs/review/02` 其余失败模式（资产清单不核分镜版本、核验-发事件间无锁、门禁 fail-open、跨集幂等碰撞等）为既有观察，本轮未扩scope。
- `test_round_number_continuous` 需 master 侧状态页回合后自愈；本分支每轮都会报同一红。
- L3 每 SKILL DONE 都跑一次 `completion_evidence`：video 阶段逐镜文件哈希、媒体阶段 ffprobe 有实测耗时；按 SKILL 粒度核验是契约要求，如需按阶段粒度缓存属优化轮范畴。

## 提交

- 已提交：`R3364:` 前缀提交一条（`dev.py commit -m "R3364: …" --tests stage_completion skill_orchestrator`；commit hash 见 `git log`——结果文件随提交入库，hash 无法自指）；提交门禁生成证据 `tasks_round/evidence/R3364.json` 并入本提交：凭据扫描 0 命中、定向 `run_selftests.py -k stage_completion skill_orchestrator` 41 条 0 红。
- 提交内容仅授权范围：`程序/orchestrator/engine.py`、`程序/orchestrator/stage_completion_service.py`、`程序/orchestrator/skill_orchestrator.py`、`程序/desktop_shared_input.py`、`程序/ui/pet_ui_stages.py`、`程序/tests/test_stage_completion_service.py`、`程序/tests/test_skill_orchestrator_completion.py`（新）、`程序/docs/stages/S10_视频生成.md`、`程序/docs/stages/S13_质检与交付.md`、`程序/docs/review/02_阶段完成判定.md`、本结果文件。
- 不添加：`程序/project_status.md`（仅 master 可提交）、`程序/tasks_round/地基加固_跨车道交接单档.md`（无关未跟踪文件，保持未跟踪）。
