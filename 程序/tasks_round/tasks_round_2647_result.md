# R2647 结果：阶段稿台账记录生成元数据（REQ-S01-85）＋质检排序测试去抖
<!-- round-evidence: {"commit_base": "85fd99c3", "credential_hits": 0, "evidence_sha256": "c637c89f7d97fc76", "exit": 0, "failed": 0, "passed": 89, "round": 2647, "tests": "run_selftests.py -k test_writing_api test_writing_quality"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   功能轮（§3.1，文档先行）＋测试基建修复。任务源：优化项 2——
   `preparation_state.json` 的每次确认记录模型ID、生成时间、token 用量。
   附带闭环一条反复拦截门禁的并发 flake（见下）。分支 `codex/wip-R2647`
   （R2643–R2646 为中央计数器空号）。

2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 **9/9** 通过；`smoke_test.py --affected writing_api` 自检门禁
     **466 条 / 0 个文件有红**。
   - 先红后绿：`test_preparation_document_records_model_time_and_token_usage`
     改动前 `KeyError: 'model_id'`，已实现转绿。
   - `test_writing_quality.test_list_reports_maps_hash_folders_back_to_scripts`
     在本会话三次并行/串行门禁中反复 1 红：两份报告写入可能落在同一
     mtime 精度刻度，`list_reports` 的 mtime 倒序退化为目录字母序。
     测试侧显式拉开时间戳（`os.utime` 第一稿提前 60 秒）消除不确定性，
     断言本身不弱化；修复后门禁含该文件全绿。
   - 全量 `--all --safe`：未跑（功能分支不累计欠账）。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账；一条跨轮反复出现的 flake 被根因修复，减少后续轮次噪音。

## 实现

- `writing_api._preparation_step` 建阶段稿记录时写入
  `model_id`（`chosen`）、`generated_at`（`datetime.now().isoformat(timespec='seconds')`），
  `result['usage']` 为非空 dict 时另写 `token_usage` 副本
  （prompt_tokens/completion_tokens/cached_tokens）。
- 菜单「设为定稿」登记的用户文件不伪造生成元数据（REQ-S01-85 明确）。
- `tests/test_writing_quality.py`：`os.utime` 拉开两稿报告 mtime，
  「按 mtime 倒序」断言确定性成立。

## 文档先行（§2.7）

`docs/stages/S01_剧本准备.md`：新增 REQ-S01-85、DES-S01-85、锚点行。

## 改动清单

- `程序/writing_api.py`：document 记录加 `model_id`/`generated_at`/`token_usage`。
- `程序/tests/test_writing_api.py`：新增元数据断言用例。
- `程序/tests/test_writing_quality.py`：mtime 排序测试确定性化。
- `程序/docs/stages/S01_剧本准备.md`：REQ/DES/锚点。

## 提交

`dev.py commit` 一批一轮，凭据见 `tasks_round/evidence/R2647.json`。
