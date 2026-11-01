# R2012 生产模块行数上限 1500→1000（结构治理轮·执行）

来源：`tasks_round/tasks_round_1983_result.md` J 节 **J7**。日期：2026-10-25。
基线：`codex/wip-R2009` @ ccda9aac。零行为变更（只改测试门禁）。

轮次类型：结构治理轮·执行（AGENTS.md §3.3）。三套基线：架构门禁仅剩 3 条已知历史红；默认冒烟 8/8；覆盖率基线不变（无新模块）。债务：`--all --safe` 欠账 +1。

## 改动

- `tests/architecture/test_module_size_ratchet.py`：`LIMIT` 1500→1000；16 个超 1000 行的现存生产模块按现值登记进 `OVERSIZE_CAPS`（只许下降，登记值＝当前实际行数）：app.py 1499、stage_execution_service.py 1447、ui_widgets.py 1383、desktop.py 1375、writing_api.py 1373、pet_cloud.py 1357、script_contract.py 1293、skill_panel.py 1203、pet_ui_stages.py 1202、pet_ui_voice.py 1201、pet_llm.py 1197、pet_agent.py 1182、workflow_settings.py 1176、desktop_idea_chat.py 1148、model_pool.py 1117、cell_hover.py 1016。
- 偏差：任务单写 17 个超 1000 行，本树（306 个生产模块）实测 16 个，以实测为准。不降到 500（会逼出机械拆分）。

## 验证（本轮实测，经 gui_hidden）

- `smoke_test.py --architecture`：410 条，仅 3 条已知红（`test_agents_md`、`test_round_baselines`、`test_skill_reference_injection`）。
- 默认 `smoke_test.py`：8 项通过。未跑 `--all --safe`，欠账 +1。
- **断言未动**：没有弱化任何既有断言；本轮是把上限收紧。

## 回滚

还原 `test_module_size_ratchet.py`。

## 下一步

契约轮（AutoState／PetBroadcast 旧属性名转发是否退役）；launch_comfy mock 同步测试轮。
