# R2231 剧本结构完成判据收成一份（修复轮）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 06 的 J16：「skill_orchestrator 的剧本结构完成判据改委托 stage_completion_service」；测试计划「先写失败用例贴出改前输出」。

## 基线
分支 `codex/wip-R2231`，自 R2228。

## 轮次类型／三套基线／债务
修复轮：两处判据不一致。`skill_orchestrator.verified_stage_output` 要求结构剧本在且 manifest 核验无问题；`stage_completion_service.completion_evidence` 只要结构剧本在就放行，缺 manifest 也算完成。以更严的一方为准，行为只在完成服务一侧收紧，编排器侧结果不变。分层无变化，无新增债务。

## 改前输出（先写失败用例）
`run_selftests.py -k script_structure_scope`：
`AssertionError: True is not false : 缺 manifest 时完成服务不应放行`

## 改动
- `stage_completion_service.completion_evidence`：`script_structure` 在结构剧本合规后追加 `script_contract.structure_manifest_problems`，有问题则不通过并给出首条原因。
- `skill_orchestrator.verified_stage_output`：`script`／`script_structure` 改委托 `completion_evidence`，其他阶段仍返回 False（原行为）。

## 新增测试
`tests/test_script_structure_scope.py::test_completion_service_and_orchestrator_share_one_script_structure_criterion`：缺 manifest 时两处都判未完成，补齐后都判完成。既有断言未动。

## 测试
`run_selftests.py -k script_structure critical_chains skill_orchestrator stage_completion resume_preview script_contract`：本轮相关用例通过；另有环境既有红项 `test_script_contract.AuditTests.test_the_audit_covers_every_script_skill`（本机缺 skills 目录内容，与本改动无关）。`smoke_test.py --architecture` 仅余两条环境既有红项。未运行全量。

## 回滚
`git revert` 本轮提交。

## 下一步
J17（三处续跑状态是否同一概念，先判定）。
