# R809 结果：定稿分镜退役别名发布 L3 注入迁移

## 范围

- `storyboard_lifecycle.retire()` 的定稿退役别名发布必须接收 L3 注入的 JSON 发布器。
- `storyboard_final_controller.retire_stage_storyboard()` 成为该发布能力的唯一装配入口；定稿流程继续只经控制器发起退役。
- 第 3 项台账 pending 从 15 降至 14；第 4 项未变。

## 验证

- `run_selftests.py -k "test_workflow final_bundle_boundary unification_ratchet coverage_audit_ratchet round_baselines stage_command_contract" --safe`：117 条／0 红。
- `smoke_test.py`：8/8；`smoke_test.py --affected storyboard_lifecycle storyboard_final_controller storyboard_final desktop`：9/9（定向 27 条／0 红）。
- `smoke_test.py --architecture`：171/171。
- R809−R806=3，按完整安全全量算式本应触发；本轮代码已先于本次接续记录进入现有 HEAD，完整安全全量未在本轮可审计日志中重跑，留待下一轮按基线纪律补做，不能将本轮记为全量绿。

## 提交

- 本轮补齐既有迁移的验收记录；提交状态待收尾凭据扫描与暂存清单核对后填写。
