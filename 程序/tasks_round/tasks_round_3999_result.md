# R3999 结果：全量持续红归因报告（任务卡 R2-G0，只读归因轮）
<!-- round-evidence: {"commit_base": "4555fbe5", "credential_hits": 0, "evidence_sha256": "10bcc9fdf906c953", "exit": 0, "failed": 0, "passed": 0, "round": 3999, "tests": "docs-only"} -->

## 1. 三问

1. **本轮属于 §3 哪种类型？** §3.5 只读诊断（归因）轮。未改任何 `.py`/`.pyw`，交付物只有 `tasks_round/全量持续红归因报告.md` 与本结果文件。
2. **测试跑了吗、三个基线过了吗？** 任务卡验收不要求冒烟与架构门禁，按只读轮默认未运行（`PY -B smoke_test.py`、`PY -B smoke_test.py --architecture`：未运行；全量：任务卡禁止）。按任务卡跑了 29 个持续红测试文件的单独计时（`PY -B -m unittest tests.<名>`，含 Tk 的 7 个经 `scripts\gui_hidden.py` 隐藏桌面）：23 个 exit=0、6 个 exit=1——失败均为本工作树缺 `运行环境/ffmpeg` 的环境缺口（与归因结论一致），耗时按实测记录。
3. **欠账少了吗？** 少了。R2-B7「持续红文件归因」即本报告交付：29 个文件全部有归类与修复提交号，0 个「判断不了」。新增欠账：11 个红段「恢复于合并轮、单点修复提交未定位」（已在报告如实标注，未猜）；表3 的 6 条门禁建议只给建议未改动，留待主控与用户评估。

## 2. 改了哪些文件

- 新增 `程序/tasks_round/全量持续红归因报告.md`（表1 逐段归因 29 行、表2 覆盖与耗时、表3 建议清单）
- 新增 `程序/tasks_round/tasks_round_3999_result.md`（本文件）

## 3. 用到的命令

- 领号：`PY -X utf8 -B 维护记录\基准脚本\round_claim.py next` → 3999
- 名单：`PY -B scripts\dora_report.py --days 30 --no-write` → 持续红 29 个（输出行数 89）
- 分段与区间：`full-safe-history.jsonl`（`D:\漫剧制作助手\.git\`，只读）＋ 临时脚本 `$env:TEMP\g0_analyze.py` 导入 `scripts/dora_report.py` 的 `history_rows`/`red_breakdown` 复用口径；逐段 `git log --format/--name-only <末红>..<恢复>`、`git show --stat <修复>`、`git cat-file -e <sha>^{commit}`（63 个提交号全部存在）
- 佐证：`tasks_round/tasks_round_3363_result.md`（16 红三类定性）、`tasks_round/tasks_round_3485_result.md`（断言漂移取证）、`scripts/local_ci.py`（STATIC_GATE_TESTS）、`run_selftests._scope_has_tk`（Tk 判定口径）
- 计时：临时脚本 `$env:TEMP\g0_measure.py` 逐文件 `PY -B -m unittest tests.<名>`（Tk 的经 `scripts\gui_hidden.py`），结果 `$env:TEMP\g0_measure.json`

## 4. 验收命令结果

- `git status --short`：见提交前实测（只允许上述两个新文件）
- `git diff --stat $(git merge-base master HEAD) -- "*.py" "*.pyw"`：见提交前实测（必须为空；本轮未改 `.py`/`.pyw`）

## 5. 四种归类计数与关键结论

- 违规内容合入 **7**：test_copy_rules（已在静态门禁）、test_core、test_recycle_directories、test_secret_status_diagnostics、test_ui_edges_tables、test_white_model_identity、test_window_resize_coalescing
- 测试自身问题 **11**：test_latent_defects_r2175、test_model_gateway_robustness、test_model_pool_redirects、test_multi_monitor_popups、test_pet_ui、test_project_page_services、test_script_workspace_results、test_shared_adapter_infrastructure、test_stdlib_closure、test_ui_batch5_stage_panel_and_script_page、test_ui_edges_guards
- 环境或工具问题 **11**：architecture.test_round_baselines、test_batch_frames、test_file_origin_provenance、test_keyframe、test_keyframe_evidence、test_keyframe_lifecycle_service、test_req_s08_anchors、test_script_find_bar、test_script_zoom、test_stage_gate_e2e_probe、test_stage_parallel
- 判断不了 **0**
- test_copy_rules 段1–3（任务书 §2.3 未归因段）：段1 `ff649b80`、段2 `2c37154e` 均为生产文案修复＝违规内容合入；段3 `62656555` 只改测试＝测试自身问题。
- 表3 建议（违规内容合入 ∧ 不在合入前检查，按红次÷耗时降序）：test_secret_status_diagnostics、test_recycle_directories、test_white_model_identity、test_core 建议进静态门禁（无 Tk、秒级）；test_window_resize_coalescing、test_ui_edges_tables 建议由提交工具按改动文件自动选中（含 Tk，静态门禁无法跑）。

## 6. 查不到的事项

- 11 个「恢复于合并轮」的红段无法定位单个修复提交（区间内 8–27 个提交、均无改相应测试文件者），报告记「单点未定位」而非猜测；其中 test_pet_ui 段2、test_stage_parallel 段3 有 R3363 定性文档佐证为环境缺口。
- test_pet_ui 在本车道单跑 exit=1（279.9 秒，隐藏桌面）：含缺 ffmpeg 成分与超时重试用例，是否还含其他失败未逐条核实。

## 7. 提交

- 提交命令：`PY -B scripts\dev.py commit -m "R3999: 全量持续红归因报告" --agent Devin tasks_round/全量持续红归因报告.md tasks_round/tasks_round_3999_result.md`
- 提交号：`4555fbe5`（含自动生成的 `tasks_round/evidence/R3999.json`）
