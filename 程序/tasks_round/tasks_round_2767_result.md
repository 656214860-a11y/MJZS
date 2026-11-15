# R2767 结果：三阶段草稿并行起草与修订（REQ-S01-89，规则 1）
<!-- round-evidence: {"commit_base": "d4001aa0", "credential_hits": 0, "evidence_sha256": "a0507ce3e9255412", "exit": 0, "failed": 0, "passed": 7, "round": 2767, "tests": "run_selftests.py -k test_preparation_parallel"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   功能轮（§3.1，文档先行）。任务源：盘点文档「不合理规则」规则 1——
   前三阶段强制串行、无法并行编辑。用户已拍板覆盖 R2412 不采纳结论，
   并同步修订 REQ-S01-11（草稿并行，确认仍按序）。分支
   `codex/wip-R2767`（R2712–R2766 为中央计数器空号/他车道）。

2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 **9/9** 通过；`smoke_test.py --affected writing_api
     writing_unconfirm` 自检门禁 **486 条 / 0 个文件有红**（504 秒，
     含跨树 GUI 令牌等待）。
   - 先红后绿：新文件 `test_preparation_parallel` 7 条，实现前 6 条红
     （旧串行模型下并行草稿被越序确认/报错），实现后 7/7 绿。
   - 失败闭环（规则 32）：两轮定向回归各暴露一类真回归，均已修复——
     - `test_writing_edited_restart` 3 红：重写口令指向未确认草稿但
       **存在已确认前缀**时，旧语义走 revision 重写（前缀重绑留在
       revision 副本、采用稿不动）。`draft_target` 收窄为「目标未确认
       **且**无已确认前缀」才按重起草处理；`_preparation_step` 早查
       同步加 `_confirmed_prefix` 条件。
     - `test_writing_response_preservation` 1 红：`「确认，输出角色卡」`
       是确认词领衔的推进请求，被点名路由误拦。`_preparation_work_index`
       增加 `_PREPARATION_ADVANCE_LEAD`：首行以确认/推进词开头时仍走
       默认位次、由模型语义判定。
   - 相关消费者回归：writing_api/restart/unconfirm/edited_restart/
     confirmation/monitor/parallel/source_priority/cancellation/
     workflow_writing_stages 等 192 条全绿（修复后复验）。
   - 全量 `--all --safe`：未跑（功能分支不累计欠账）。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账。盘点「剧本准备逻辑分析」队列 1–7 至此全部落地：
   优化 2（R2647）、优化 1（R2663）、规则 4+3（R2678）、优化 4+规则 2
   （R2685）、优化 3（R2711）、规则 1（本轮）。

## 实现（REQ-S01-89）

`writing_api.py`：

- `_preparation_state`：删除「非末尾记录必须已确认」的串行不变式；
  **任一**未确认记录的正文指纹可按用户手改重绑（`user_edited`）；
  重写口令目标是未确认草稿且无已确认前缀时跳过采用稿重写校验
  （`draft_target`），其余照旧。
- `_preparation_work_index(documents, message)`：本轮位次——确认/推进词
  领衔→默认位；点名未确认稿→该位；点名紧邻未起草位→追加位；点名更远
  未起草位→报错提示先起草；未点名→首个未确认位或追加位。
- `_preparation_step`：`advancing` 增加 `_confirmed_prefix(documents,
  index)` 门禁——前置未确认时产出只落为并行草稿（
  `documents[:selected]+[新稿]+其后草稿`），不越序确认；确认动作落在
  `documents[index]` 而非固定末尾。
- `_preparation_task`：`pending` 按本轮位次判定；前置文件标注区分
  「已确认前置文件／并行未确认草稿／当前待修改草稿」。
- `_PREPARATION_ADVANCE_LEAD`：确认/推进词领衔的消息不做草稿路由。

`writing_unconfirm.py`：`confirm_preparation_document` 写入确认记录时
保留其后未确认草稿记录（已确认下游照旧作废）。

文档：`docs/stages/S01_剧本准备.md` 新增 REQ/DES-S01-89 并在
REQ-S01-11 上标注放宽口径（一次请求仍只产出一份阶段稿、确认仍按序、
自然剧本仍须三阶段全确认）。

## 设计取舍（覆盖 R2412）

R2412 的顾虑是 `documents[i]=阶段` 位置不变式被多处依赖。本轮保留
位置不变式与连续起草不变式（追加仅限紧邻下一位），只放宽「未确认
记录唯一」约束；确认依赖、快照基线、自然稿门禁、进度报告全部复用
既有口径，位置不变式零改动。

## 未覆盖

- 并行草稿的命名修订依赖原话点名；UI 无专门的「起草下一阶段」按钮，
  聊天自然语言是唯一入口（与既有交互一致）。
