# R2193 发送边界校验→取设置→冻结收口（结构治理轮·执行）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 01 的 J4。

## 基线
分支 `codex/wip-R2193`，自 R2191（e9b34d3b）。

## 轮次类型／三套基线／债务
结构治理轮；不改行为；层级台账不变；无新增债务。

## 改动
- `workflow_settings.resolve_for_send(project, stage, *, config, intake_only, direct_api, model_snapshot, adjust)`：按 校验 → 取当前设置 → adjust 改写 → 冻结 SKILL 的固定顺序完成；`config` 给定时沿用（安全重试不重读）；仅剧本准备的正式发送校验并冻结。
- `writing_api.capture_request` 与旧调用方回退两处、`desktop_idea_chat` 的 `_FlowAgentLaunch.build` 一处改调它；`capture_request` 中模型／引擎／invocation_mode 的改写经 `adjust` 放在冻结前，顺序不变。
- `desktop_idea_chat` 中仅校验的一处（发送前模型捕获）保持原样，它不取设置也不冻结。

## 登记
`test_module_size_ratchet`：workflow_settings 1056→1069（新入口）；writing_api 1373→1371、desktop_idea_chat 1148→1109 按实际下调。

## 新增测试
`tests/test_workflow_settings_cache.py::ResolveForSendTests`（3 项，无 Tk，直接打新入口，验证顺序、config 沿用、intake_only／非 writing 不校验不冻结）。

## 测试
- `smoke_test.py --architecture`：仅 2 项环境红（test_round_number_continuous、基准历史缺失），非回归。
- `test_request_freeze_entries`、`test_workflow_settings_cache`：通过。
- `--affected workflow_settings writing_api idea_chat`：另有 test_skills（73≠71）、test_master_skill 3 项红，与本轮改动无关（技能目录内容差异），未在基线上逐项复核。
- 同步 `test_request_freeze_entries` 的源码锚点（改指向新入口），断言意图未弱化；其余断言未动。

## 回滚
`git revert` 本轮提交。

## 下一步
J5–J7（候选 02）。
