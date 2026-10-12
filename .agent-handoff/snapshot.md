# 当前快照

## 2026-10-12：O29 完成，继续 O30

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O28 已完成，**O29 已完成（R1354）**，下一项 O30。
- O29（预算由多个计数器汇总为请求级可对账记录）：`pet_llm.py`（L1）新增 `class RequestLedger` 与 `REQUEST_LEDGER_PATH`／`REQUEST_KINDS`（tokens/seconds/images/videos/requests）／`REQUEST_STATES`（reserved/settled/unknown/cancelled/duplicate）／`REQUEST_MODES`；`reserve` 幂等、`link` 同一远端任务唯一账单（后来者 duplicate）、`settle` 优先 total_tokens 否则 prompt+completion、缺量转 `mark_unknown`、`cancel` 只改本机不伪造远端退款、`report` 按 kind 分列 token/秒/次数**不跨量纲相加**且金额只在显式传带时间 `price_table` 时输出（含 table_version/table_at/missing_rates）。`model_pool.probe` 增 `ledger` 与 `PROBE_USAGE_NOTE`（探测「可能产生用量」并记未知），`pet_models_ui` 探测文案标注。见 [R1354](../程序/tasks_round/tasks_round_1354_result.md)。
- 验证证据：`tests/test_request_ledger.py`（新）11 条；定向 `-k request_ledger pet_llm model_router pet_models_ui` 73/73、架构 312/312、默认冒烟 8/8，0 红；1354 − 1351 = 3 < 5 且未命中 §5 升级条件，本轮不跑全量。上次绿全量 1351（tree c97c1336），下一五轮欠账点 1356。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只点名自己的路径。主树永远“脏”，全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`；本轮 1354；全量在干净 master 工作树 `run_selftests.py --all --safe`。`project_status.md` 的 `当前轮次` 须＝最新结果报告号＋1（`tests/architecture/test_round_baselines.py` 会校验）。提交后 master 前移会让 `o07-fullsafe-master` 显示为「已暂存改动」，领取／全量前先 `git reset --hard HEAD`。
- 下一步：O30（见 `tasks_round_1267_result.md` O30 条目：字幕估算轴与实际音频轴建立校准流程；`subtitle_timing.py:35` 无明确时间时按镜头时长分配；M）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`）；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑（上次绿全量 1351，下一欠账点 1356）。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
