# 第 173 轮：自动链失败阶段回退保护

## 问题

- 历史项目状态可能不一致：结构化剧本已失败，但下游阶段被错误标成完成。
- 自动档续跑必须从第一个未完成或失败阶段接手，不能因下游状态越过结构化剧本。

## 改动

- 在 `test_stage_flow.py` 增加回归用例：`script_structure=failed` 且 `storyboard=success` 时，自动链下一步仍为 `script_structure`。
- 同时复查已有的“剧本完成后切自动档”覆盖；该路径已经由 `ArmFromTests` 验证，无需重复实现。

## 验证

- `python test_checkbox_column.py; python test_column_fit.py; python test_frame_checks.py`：43 条通过。
- `python test_script_contract.py; python test_idea_chat.py`：98 条通过。
- `python test_stage_flow.py`：45 条通过。
- `python run_selftests.py test_stage_flow`：45 条通过。
- `python smoke_test.py --affected stage_flow`：9 项冒烟检查通过。

## 风险与下一步

- 本轮只增加自动推进的回归保护，不改模型配置、项目文件或用户素材。
- 下一轮继续审计阶段状态持久化与自动入口的异常恢复路径。
