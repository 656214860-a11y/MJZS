# R4137 结果：S05「使用情况」块与删图确认接引用清单——需求设计（文档先行）
<!-- round-evidence: {"commit_base": "3383684c", "credential_hits": 0, "evidence_sha256": "3b1fc04d9e427e94", "exit": 0, "failed": 0, "passed": 34, "round": 4137, "tests": "run_selftests.py -k stage_doc_sections requirement_traceability design_coverage agent_doc_budget"} -->

## 开头三问

- （一）本轮属于哪种类型：功能轮·文档先行（§3.1／§2.7）。只改文档、不改任何 `.py`：把已定需求（用户决定 2026-11-21，DOC-D9-2 与 DOC-D9-1 前半件）设计成 REQ／DES／IF／UX 条目写进 S05 阶段文档与专题册 09。车道 `codex/doc-s05-usage-block`，工作树 `.agents/worktrees/doc-s05-usage-block`。
- （二）测试跑了吗、三个基线：跑了文档门禁。`run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage` 退出码 0，34 条用例全过；`smoke_test.py --architecture` 退出码 0，700 条全绿。默认冒烟未单独跑；全量自测未跑（纯文档轮）。
- （三）欠账少了吗：少了——S05 的「使用情况」块与删图确认接引用清单两项从「待定」推进到「设计已定」（专题册 09 §9／§12 状态同步）。实现欠账（`asset_usage` 领域函数、L3 封装、详情页块、弹窗接线、对应测试）已在测试锚定行标 ⬜ 待实现；无新增欠账，未动任何门禁阈值、基线和登记表。

## 改了哪些文件

- `docs/stages/S05_资产管理.md`：
  - `## 需求` 新增小节「资产详情页与删图确认（目标，未实现）」：REQ-S05-51（资产详情页只读「使用情况」块，角色／场景／道具三类都有，摆在「参考职责」「状态变体」之后、「资产 JSON 原文」之前；顶部汇总＋逐镜行，首帧「最新／过期／缺失」三档、视频「已生成／未生成」两档，角色另列「出现过的镜头视频」；全部现算只读）与 REQ-S05-52（单项／批量删图确认弹窗追加引用摘要，只提醒不拦截、样式不变），均 ⬜。
  - `### 设计条目` 新增 DES-S05-51（`domain/asset_plan.asset_usage(project, aid, *, episode_dir='')` 只读函数的返回结构与逐镜判定做法，含异常按该镜头 `stale` 处理；经 L3 `stage_execution_service` 同名薄封装，UI 只经它调用）与 DES-S05-52（复用未接线的 `domain/asset_plan.deletion_references` 接单项／批量删图弹窗，封装抛错退回纯文案不阻塞删除）。
  - `### 测试锚定` 新增 REQ-S05-51/52 行：`test_asset_impact`（首帧三档、孤立、已生成视频、读不出分镜按过期不抛错）、`test_asset_detail`（块位置、孤立与失败空态、逐镜行条数，真 Tk 量几何）、`test_asset_batch_window`（删图弹窗引用摘要断言）——计划新增用例，⬜ 待实现。
  - `### 写出` 新增 IF-S05-35（使用情况数据，只读返回）与 IF-S05-36（删图引用摘要），状态 ⬜。
  - `### 控件与操作`：UX-S05-53「使用情况」由「待定」填满（位置、只读、`COLORS` success／warning／muted 三色、孤立与加载失败空态、行区可滚动）；新增 UX-S05-54（单项删图弹窗引用摘要）、UX-S05-55（批量删图弹窗「其中 N 项被采用镜头引用」），均 ⬜。
- `docs/specs/09_资产数据生命周期.md`：§9「使用情况」块行与 §12「使用情况」块与标记行状态改为「🟡（设计已定：S05 REQ-S05-51；首帧三档与视频有无先做，视频『过期』待 §8 视频持久过期标记）」并链接到 S05；§9「删图确认」行与 §12「删图弹窗接入 `deletion_references`」行注明设计已定 S05 REQ-S05-52，状态保持 🟡；§13 未决事项未动。
- `tasks_round/tasks_round_4137_result.md`：本文件。

## 命令与结果

以下命令都在车道的 `程序` 目录下跑（建车道与 scope 在主树／车道根），解释器 `D:\漫剧制作助手\运行环境\Python\python.exe`，先设 `PYTHONIOENCODING=utf-8` 与 UTF-8 控制台。

| 命令 | 结果 |
| --- | --- |
| `git worktree add -b codex/doc-s05-usage-block .agents/worktrees/doc-s05-usage-block master`（主树根） | 新建车道，基线 `3383684c`（R4136） |
| `python.exe -B scripts\dev.py claim`（车道 `程序`） | 领到轮次 4137 |
| `python.exe -B scripts\dev.py scope docs/stages/S05_资产管理.md docs/specs/09_资产数据生命周期.md` | 无车道重叠（36 个工作树分支均无重叠） |
| `python.exe -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage` | 退出码 0；34 条用例 0 红，ALL TESTS PASSED |
| `python.exe -B smoke_test.py --architecture` | 退出码 0；Ran 700 tests in 245.9s，OK |
| `python.exe -B scripts\dev.py commit -m "R4137: S05 使用情况块与删图确认的需求设计" <三文件> --tests stage_doc_sections requirement_traceability design_coverage agent_doc_budget` | 见下方提交记录 |

## 如实说明

- （一）IF-S05-35／36 是只读接口，但编号段 20–39 只允许落在「写出」表，故放在 `### 写出` 末尾，「位置」列写「不落盘（只读返回）」；若评审认为应属「读入」段，需改用 17／18 号另议。
- （二）REQ-S05-52 的来源按任务书写「用户决定 2026-11-21」；专题册 09 §12 该项原载「来源：盘点报告 F31」，此处以用户决定为准、正文未引 F31。
- （三）「做法」类句子（函数签名、判定顺序、弹窗文案）均按任务书标「建议，待确认」；REQ／DES／IF／UX 一律 ⬜，无 ✅。
- （四）事实核对：`asset_plan.asset_impact`／`deletion_references`／`_adopted_storyboard_shots`、`keyframe_evidence.frame_problem`、`contract.storyboard_paths.media_root`、`stage_execution_service` 对 `asset_impact` 的 re-export、`ui/desktop_asset_pages.py` 删图入口、`ui_tokens.COLORS` 的 success／warning／text_muted 色系均已在代码中核实存在。

## 未覆盖项

- 未跑默认冒烟、未跑全量自测（纯文档轮）；未实现任何代码，`asset_usage` 与弹窗接线待实现轮；未 push、未 merge、未动主工作树与 master。
