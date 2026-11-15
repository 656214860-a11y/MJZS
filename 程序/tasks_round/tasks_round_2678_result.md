# R2678 结果：重写二次确认收窄为明确词＋采用稿质检报告纳入完成门禁（REQ-S01-12/22）
<!-- round-evidence: {"commit_base": "34cbabf0", "credential_hits": 0, "evidence_sha256": "e05173c09fcaf106", "exit": 0, "failed": 0, "passed": 37, "round": 2678, "tests": "run_selftests.py -k test_writing_restart_intent test_preparation_monitor test_writing_quality"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   功能轮（§3.1，文档先行；同类规则收口批量成轮）。任务源：盘点文档「不合理规则」
   整改——规则 4（重写确认意图识别过宽）与规则 3（质检未纳入确认流程）。
   分支 `codex/wip-R2678`（R2664–R2677 为中央计数器空号/他车道）。

2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 **9/9** 通过；`smoke_test.py --affected writing_api
     stage_completion_service writing_quality` 自检门禁 **873 条 / 0 个文件有红**。
   - 先红后绿：
     - 规则 4：`test_casual_reply_keeps_status_quo_and_clears_pending_restart`
       改动前三个子用例（好的／继续／ok）都触发重写模型调用
       （`AssertionError: 随口应答不得调用模型重写`），收窄后调不到重写路径。
     - 规则 3：stash 生产文件复跑，`assertFalse(ok)` 红（fail 报告不拦截）
       与 `KeyError: 'script_quality'` 红；恢复后 32/32 绿。
   - 相关消费者回归：`writing_restart*`／`writing_unconfirm`／
     `preparation_confirmation` 等 152 条全绿。
   - 全量 `--all --safe`：未跑（功能分支不累计欠账）。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账；盘点「不合理规则」剩规则 1（并行编辑，大改）与规则 2（差异对比，
   并入优化 4 快照轮）待后续轮。

## 实现

### 规则 4：二次确认收窄（REQ-S01-12）

- `_PREPARATION_AFFIRMATIVE` 从 16 个词收窄为
  `('确认', '确定', '确认重写', '重写', 'yes')`——与询问文案
  「回复“确认”即从该阶段重写；回复其他内容则保持现状」一致。
- 语义边界：该词表只用于 pending_restart 二次确认闸门；阶段推进本就走
  模型语义判断（任务书明示「不要依赖固定确认词」），不受影响。
- 随口应答（好／继续／ok 等）按「保持现状」：`pending_restart` 随正常
  轮次写回清除，采用稿不动、不产 revision。
- 审计举例「好的，我知道了」「继续提问」本就被首行整词匹配挡住，
  本次收窄的是独立成词的随口应答。

### 规则 3：质检硬门禁（REQ-S01-22）

- `writing_quality.adopted_quality(script_path, quality_root)`：按
  `publish_reports` 同一定位口径（路径 sha256 前 12 位／正文 sha256）查
  采用稿正文的四项质检状态；无报告返回 None。
- `completion_evidence('script')`：采用源解析成功后，报告存在且任一项
  属 `QUALITY_BLOCKING=('fail','invalid')` → 完成核验不通过并点名报告；
  `missing`／`incomplete` 属待人工复核不硬卡；无报告（手动添加、下载收回、
  未启用质检）不受限——与 REQ-S01-21/83 手动采用契约兼容。
- `preparation_progress` 增 `script_quality` 报告字段；已采用且质检未过时
  `next_actions` 指向「重新生成或修订后重新采用」。

## 文档先行（§2.7）

`docs/stages/S01_剧本准备.md`：REQ-S01-12 补二次确认收窄条款、
DES-S01-12 明确词表只管 pending_restart；REQ-S01-22 补质检报告门禁、
DES-S01-22 补 `adopted_quality` 定位与 `script_quality` 字段。

## 改动清单

- `程序/writing_api.py`：肯定词表收窄。
- `程序/writing_quality.py`：`adopted_quality`＋`QUALITY_BLOCKING`。
- `程序/stage_completion_service.py`：完成核验挂质检门禁、
  `preparation_progress` 增 `script_quality` 与质检未过 next_actions。
- `程序/tests/test_writing_restart_intent.py`：随口应答保持现状用例。
- `程序/tests/test_preparation_monitor.py`：质检报告拦截／放行／无报告兼容用例。
- `程序/docs/stages/S01_剧本准备.md`：REQ/DES 更新。

## 提交

`dev.py commit` 一批一轮，凭据见 `tasks_round/evidence/R2678.json`。
