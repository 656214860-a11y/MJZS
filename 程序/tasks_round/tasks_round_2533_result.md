# R2533 结果

1. 轮次类型：功能轮（工程闸门落地清单批次 3：O1／O3／O4／O5／O2，观测层）。
2. 测试：定向 `test_dora_report`、`test_auto_full_safe`、`test_commit_round`、`test_rule_guard_map`、`test_unification_ratchet` 全绿；证据文件 `tasks_round/evidence/R2533.json`。架构门禁 435 条仅 `test_round_number_continuous` 红，原因是工作分支的状态页只能在 master 更新（与本轮无关）；`test_unification_ratchet` 首次因两处新脚本裸 `json.loads` 红，改用 `file_cache.read_json`／`JSONDecoder` 后绿。
3. 欠账：无新增。断言未动。

## 改动

- `scripts/dora_report.py`（只读）：前置时间、失败检查点占比、7 天内被修复比例（启发式）、返工热点、红灯停留、按 `Agent:` 分组。
- `scripts/auto_full_safe.py`：后台全量每次真实结果追加 `full-safe-history.jsonl`；环境受阻不记，写失败不影响主流程。
- `scripts/commit_round.py`：`--agent <名称>` 写 `Agent:` 行。

## 首份基线（近 30 天，真实仓库）

- 提交 827 个，轮次提交 685 个；合并 43 次，前置时间中位约 0 小时、最长 6.6 小时。
- `R<n>-FAIL:` 提交 1 个，占 0.1%。
- 7 天内被修复的轮次比例 68.9%（219／318，**启发式**：同模块 7 天内又有标题含「修复」的提交，只是返工信号，不是严格失败率）。
- 返工热点前几位：desktop_idea_chat、scripts、desktop、ui_tokens、desktop_account_page。
- 红灯停留：数据不足（`full-safe-history.jsonl` 从本轮起才开始记录）；来源分组：全部「未标注」。
